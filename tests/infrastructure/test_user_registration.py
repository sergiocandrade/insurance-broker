from dataclasses import replace
from datetime import datetime
import unittest
from unittest.mock import Mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from application.use_cases.sign_up import SignUpUseCase
from domain.exceptions.authentication import AuthenticationError
from infrastructure.persistence.exceptions import PersistenceError
from domain.models.broker import BrokerStatus
from domain.models.user import UserStatus
from domain.services.user import UserService
from domain.services.broker import BrokerService
from domain.services.authentication import AuthenticationEngine, SignUpResult
from infrastructure.persistence.sqlalchemy.models import Base, BrokerModel, UserBrokerModel, UserModel
from infrastructure.persistence.sqlalchemy.repositories.user_repository import SqlAlchemyUserRepository
from infrastructure.persistence.sqlalchemy.repositories.broker_repository import SqlAlchemyBrokerRepository


class UserRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.repository = SqlAlchemyUserRepository(self.sessions)
        self.created_at = datetime(2026, 10, 27)
        with self.sessions.begin() as session:
            session.add_all([
                UserModel(
                    id="local-user-id", email="user@example.com", name="Existing User", external_id="provisioned-id",
                    status=UserStatus.PENDING, created_at=self.created_at,
                ),
                UserModel(
                    id="unlinked-user", email="unlinked@example.com", name="Unlinked User", external_id="unlinked-id",
                    status=UserStatus.PENDING, created_at=self.created_at,
                ),
                BrokerModel(id="first-broker", created_at=self.created_at),
                BrokerModel(id="second-broker", created_at=self.created_at),
                BrokerModel(id="unrelated-broker", created_at=self.created_at),
            ])
        with self.sessions.begin() as session:
            session.add_all([
                UserBrokerModel(user_id="local-user-id", broker_id="first-broker", created_at=self.created_at),
                UserBrokerModel(user_id="local-user-id", broker_id="second-broker", created_at=self.created_at),
            ])

    def test_email_lookup_returns_users_without_memberships(self) -> None:
        user = self.repository.fetch_user_by_email("user@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user.id, "local-user-id")
        self.assertIsNotNone(self.repository.fetch_user_by_email("unlinked@example.com"))
        self.assertIsNone(self.repository.fetch_user_by_email("missing@example.com"))

    def test_broker_lookup_returns_only_brokers_related_to_user(self) -> None:
        brokers = SqlAlchemyBrokerRepository(self.sessions).list_brokers_for_user("local-user-id")

        self.assertEqual([broker.id for broker in brokers], ["first-broker", "second-broker"])
        self.assertTrue(all(broker.status == BrokerStatus.PENDING for broker in brokers))

    def test_update_persists_model_fields_without_changing_identity_or_creation_time(self) -> None:
        user = self.repository.fetch_user_by_email("user@example.com")
        updated = replace(
            user, email="updated@example.com", external_id="updated-cognito-sub",
            status=UserStatus.REGISTERED, created_at=datetime(2030, 1, 1),
        )

        self.repository.update(updated)

        with self.sessions() as session:
            saved = session.get(UserModel, "local-user-id")
            self.assertEqual(saved.email, "updated@example.com")
            self.assertEqual(saved.external_id, "updated-cognito-sub")
            self.assertEqual(saved.status, UserStatus.REGISTERED)
            self.assertEqual(saved.name, "Existing User")
            self.assertEqual(saved.created_at, self.created_at)
            self.assertEqual(session.get(BrokerModel, "first-broker").status, BrokerStatus.PENDING)
            self.assertEqual(len(session.scalars(select(UserModel)).all()), 2)

    def test_update_rejects_missing_user_instead_of_inserting(self) -> None:
        user = self.repository.fetch_user_by_email("user@example.com")

        with self.assertRaises(PersistenceError):
            self.repository.update(replace(user, id="missing-user"))

        with self.sessions() as session:
            self.assertIsNone(session.get(UserModel, "missing-user"))
            self.assertEqual(len(session.scalars(select(UserModel)).all()), 2)

    def test_update_with_duplicate_email_rolls_back_all_changes(self) -> None:
        user = self.repository.fetch_user_by_email("user@example.com")

        with self.assertRaises(PersistenceError) as error:
            self.repository.update(replace(
                user, email="unlinked@example.com", external_id="changed-sub", status=UserStatus.REGISTERED,
            ))

        self.assertEqual(str(error.exception), "Unable to update user profile")
        with self.sessions() as session:
            saved = session.get(UserModel, "local-user-id")
            self.assertEqual(saved.email, "user@example.com")
            self.assertEqual(saved.external_id, "provisioned-id")
            self.assertEqual(saved.status, UserStatus.PENDING)

    def test_user_activation_preserves_local_id_without_changing_brokers(self) -> None:
        user = self.repository.fetch_user_by_email("user@example.com")
        UserService(self.repository).activate_user(user=user, external_id="new-cognito-sub")

        with self.sessions() as session:
            user = session.get(UserModel, "local-user-id")
            self.assertEqual(user.external_id, "new-cognito-sub")
            self.assertEqual(user.status, UserStatus.REGISTERED)
            self.assertEqual(user.name, "Existing User")
            self.assertEqual(user.created_at, self.created_at)
            self.assertEqual(session.get(BrokerModel, "first-broker").status, BrokerStatus.PENDING)
            self.assertEqual(session.get(BrokerModel, "second-broker").status, BrokerStatus.PENDING)
            self.assertEqual(session.get(BrokerModel, "unrelated-broker").status, BrokerStatus.PENDING)
            self.assertEqual(len(session.scalars(select(UserModel)).all()), 2)
            self.assertEqual({link.user_id for link in session.scalars(select(UserBrokerModel))}, {"local-user-id"})

    def test_signup_activates_all_brokers_associated_with_user(self) -> None:
        authentication = Mock(spec=AuthenticationEngine)
        authentication.sign_up.return_value = SignUpResult(user_id="new-cognito-sub", user_confirmed=False)
        use_case = SignUpUseCase(
            authentication,
            UserService(self.repository),
            BrokerService(SqlAlchemyBrokerRepository(self.sessions)),
        )

        result = use_case.execute(email="user@example.com", password="test-password")

        self.assertTrue(result.user_confirmed)
        with self.sessions() as session:
            user = session.get(UserModel, "local-user-id")
            self.assertEqual(user.external_id, "new-cognito-sub")
            self.assertEqual(user.status, UserStatus.REGISTERED)
            self.assertEqual(session.get(BrokerModel, "first-broker").status, BrokerStatus.ACTIVE)
            self.assertEqual(session.get(BrokerModel, "second-broker").status, BrokerStatus.ACTIVE)
            self.assertEqual(session.get(BrokerModel, "unrelated-broker").status, BrokerStatus.PENDING)
            self.assertEqual(len(session.scalars(select(UserModel)).all()), 2)
