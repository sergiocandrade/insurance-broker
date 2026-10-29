import os
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import Column, MetaData, Table, inspect, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateIndex, CreateTable

from domain.models.user import UserModel as DomainUserModel, UserStatus
from infrastructure.persistence.exceptions import PersistenceError
from domain.services.authentication import AuthenticationEngine, SignUpResult
from infrastructure.config.settings import DatabaseSettings
from infrastructure.persistence.sqlalchemy.database import create_database_engine
from infrastructure.persistence.sqlalchemy.models.user_model import Base, UserModel
from infrastructure.persistence.sqlalchemy.user_mapper import UserMapper
from infrastructure.persistence.sqlalchemy.repositories.user_repository import SqlAlchemyUserRepository
from presentation.apis.bff.containers import Container


class UserRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_database_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.repository = SqlAlchemyUserRepository(self.sessions)

    def test_add_persists_identity_and_email_without_password(self) -> None:
        user = DomainUserModel(id="user-id", email="user@example.com", external_id="cognito-sub", status=UserStatus.REGISTERED)

        self.repository.add(user)

        with self.sessions() as session:
            saved = session.get(UserModel, "user-id")
            self.assertIsNotNone(saved)
            self.assertEqual(saved.email, "user@example.com")
            self.assertEqual(saved.external_id, "cognito-sub")
            self.assertEqual(saved.status, UserStatus.REGISTERED)
            self.assertEqual(saved.created_at, user.created_at.replace(tzinfo=None))
        self.assertNotIn("password", UserModel.__table__.columns)

    def test_get_by_external_id_returns_domain_user_with_status(self) -> None:
        user = DomainUserModel(
            id="local-id", email="user@example.com", external_id="cognito-sub",
            status=UserStatus.EMAIL_CONFIRMED, name="Example User",
            created_at=datetime(2026, 10, 27, tzinfo=UTC),
        )
        self.repository.add(user)

        found = self.repository.get_by_external_id("cognito-sub")

        self.assertEqual(found, user)
        self.assertIs(type(found), DomainUserModel)

    def test_user_mapper_round_trip_preserves_domain_values(self) -> None:
        user = DomainUserModel(
            id="local-id", email="user@example.com", external_id="cognito-sub",
            status=UserStatus.EMAIL_CONFIRMED, name="Example User",
            created_at=datetime(2026, 10, 27, tzinfo=UTC),
        )

        model = UserMapper.to_model(user)
        restored = UserMapper.to_domain(model)

        self.assertIsInstance(model, UserModel)
        self.assertIsNone(model.created_at.tzinfo)
        self.assertEqual(restored, user)
        self.assertIs(type(restored), DomainUserModel)

    def test_user_mapper_normalizes_aware_timestamps_to_utc(self) -> None:
        model = UserModel(
            id="local-id", email="user@example.com", name="Example User", external_id="cognito-sub",
            status=UserStatus.REGISTERED,
            created_at=datetime(2026, 10, 27, 2, tzinfo=timezone(timedelta(hours=2))),
        )

        user = UserMapper.to_domain(model)

        self.assertEqual(user.created_at, datetime(2026, 10, 27, tzinfo=UTC))
        self.assertIs(user.created_at.tzinfo, UTC)

    def test_get_by_external_id_returns_none_for_unknown_user(self) -> None:
        self.assertIsNone(self.repository.get_by_external_id("unknown-sub"))

    def test_get_by_external_id_rejects_ambiguous_profiles(self) -> None:
        self.repository.add(DomainUserModel(
            id="first-user", email="user@example.com", external_id="same-sub", status=UserStatus.REGISTERED,
        ))
        self.repository.add(DomainUserModel(
            id="second-user", email="other@example.com", external_id="same-sub", status=UserStatus.COMPLETED,
        ))

        with self.assertRaises(PersistenceError):
            self.repository.get_by_external_id("same-sub")

    def test_get_by_external_id_sanitizes_database_errors(self) -> None:
        Base.metadata.drop_all(self.engine)

        with self.assertRaises(PersistenceError) as error:
            self.repository.get_by_external_id("cognito-sub")

        self.assertEqual(str(error.exception), "Unable to load user profile")

    def test_container_wires_signup_to_persistence(self) -> None:
        authentication_engine = Mock(spec=AuthenticationEngine)
        authentication_engine.sign_up.return_value = SignUpResult(user_id="user-id", user_confirmed=False)
        container = Container()

        with (
            container.authentication_engine.override(authentication_engine),
            container.session_factory.override(self.sessions),
        ):
            result = container.sign_up_use_case().execute(
                email="user@example.com", password="test-password",
            )

        self.assertEqual(result.user_id, "user-id")
        with self.sessions() as session:
            self.assertEqual(session.get(UserModel, "user-id").email, "user@example.com")
            self.assertEqual(session.get(UserModel, "user-id").external_id, "user-id")

    def test_email_confirmation_transitions_registered_user(self) -> None:
        self.repository.add(DomainUserModel(id="user-id", email="user@example.com", external_id="cognito-sub", status=UserStatus.REGISTERED))

        self.repository.mark_email_confirmed("user@example.com")
        self.repository.mark_email_confirmed("user@example.com")

        with self.sessions() as session:
            self.assertEqual(session.get(UserModel, "user-id").status, UserStatus.EMAIL_CONFIRMED)

    def test_email_confirmation_does_not_downgrade_completed_user(self) -> None:
        self.repository.add(DomainUserModel(
            id="user-id", email="user@example.com", external_id="cognito-sub", status=UserStatus.COMPLETED,
        ))

        self.repository.mark_email_confirmed("user@example.com")

        with self.sessions() as session:
            self.assertEqual(session.get(UserModel, "user-id").status, UserStatus.COMPLETED)

    def test_email_confirmation_requires_existing_user(self) -> None:
        with self.assertRaises(PersistenceError):
            self.repository.mark_email_confirmed("missing@example.com")

    def test_email_confirmation_database_errors_are_sanitized(self) -> None:
        Base.metadata.drop_all(self.engine)

        with self.assertRaises(PersistenceError) as error:
            self.repository.mark_email_confirmed("user@example.com")

        self.assertEqual(str(error.exception), "Unable to update user registration status")

    def test_duplicate_email_rolls_back_and_next_transaction_succeeds(self) -> None:
        self.repository.add(DomainUserModel(id="first-user", email="user@example.com", external_id="first-sub", status=UserStatus.REGISTERED))

        with self.assertRaises(PersistenceError):
            self.repository.add(DomainUserModel(id="duplicate-user", email="user@example.com", external_id="duplicate-sub", status=UserStatus.REGISTERED))

        self.repository.add(DomainUserModel(id="second-user", email="other@example.com", external_id="second-sub", status=UserStatus.REGISTERED))
        with self.sessions() as session:
            self.assertIsNone(session.get(UserModel, "duplicate-user"))
            self.assertEqual(len(session.scalars(select(UserModel)).all()), 2)

    def test_duplicate_external_id_is_allowed(self) -> None:
        self.repository.add(DomainUserModel(id="first-user", email="user@example.com", external_id="same-sub", status=UserStatus.REGISTERED))

        self.repository.add(DomainUserModel(id="second-user", email="other@example.com", external_id="same-sub", status=UserStatus.REGISTERED))

        with self.sessions() as session:
            self.assertEqual(session.get(UserModel, "first-user").external_id, "same-sub")
            self.assertEqual(session.get(UserModel, "second-user").external_id, "same-sub")

    def test_missing_table_returns_sanitized_error(self) -> None:
        Base.metadata.drop_all(self.engine)

        with self.assertRaises(PersistenceError) as error:
            self.repository.add(DomainUserModel(id="user-id", email="user@example.com", external_id="cognito-sub", status=UserStatus.REGISTERED))

        self.assertEqual(str(error.exception), "Unable to save user profile")

    def test_users_table_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(UserModel.__table__).compile(dialect=mysql.dialect()))
        self.assertIn("CREATE TABLE users", statement)
        self.assertIn("PRIMARY KEY (id)", statement)
        self.assertIn("UNIQUE (email)", statement)
        index = next(index for index in UserModel.__table__.indexes if index.name == "ix_users_external_id")
        self.assertEqual(
            str(CreateIndex(index).compile(dialect=mysql.dialect())),
            "CREATE INDEX ix_users_external_id ON users (external_id)",
        )

    def test_database_url_is_required_and_masked(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValidationError):
                DatabaseSettings()
            settings = DatabaseSettings(
                DATABASE_URL="mysql+pymysql://test-user:private-password@localhost/test-db",
            )

        self.assertNotIn("private-password", repr(settings))


class UserMigrationTests(unittest.TestCase):
    def test_status_migration_defaults_existing_rows_and_preserves_users(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/status.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "174038895e42")
            engine = create_database_engine(database_url)
            try:
                users = Table("users", MetaData(), autoload_with=engine)
                with engine.begin() as connection:
                    connection.execute(users.insert().values(
                        id="user-id", email="user@example.com", external_id="cognito-sub",
                        created_at=datetime(2026, 10, 27),
                    ))

                command.upgrade(config, "head")

                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                with sessions() as session:
                    self.assertEqual(session.get(UserModel, "user-id").status, UserStatus.REGISTERED)
                self.assertFalse(next(
                    column for column in inspect(engine).get_columns("users") if column["name"] == "status"
                )["nullable"])

                command.downgrade(config, "174038895e42")
                self.assertNotIn("status", {column["name"] for column in inspect(engine).get_columns("users")})
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(select(users.c.id)).scalar_one(), "user-id")
            finally:
                engine.dispose()

    def test_external_id_migration_creates_non_unique_index(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/migration.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "head")
            engine = create_database_engine(database_url)
            try:
                columns = {column["name"]: column for column in inspect(engine).get_columns("users")}
                self.assertFalse(columns["external_id"]["nullable"])
                self.assertNotIn("extern_id", columns)
                self.assertNotIn("cognito_sub", columns)
                index = next(
                    index for index in inspect(engine).get_indexes("users")
                    if index["name"] == "ix_users_external_id"
                )
                self.assertEqual(index["column_names"], ["external_id"])
                self.assertFalse(index["unique"])

                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                repository = SqlAlchemyUserRepository(sessions)
                repository.add(DomainUserModel(id="first-user", email="user@example.com", external_id="same-sub", status=UserStatus.REGISTERED))
                repository.add(DomainUserModel(id="second-user", email="other@example.com", external_id="same-sub", status=UserStatus.REGISTERED))
                with sessions() as session:
                    self.assertEqual(session.scalars(select(UserModel.external_id)).all(), ["same-sub", "same-sub"])

                command.downgrade(config, "base")
                self.assertFalse(inspect(engine).has_table("users"))
                command.upgrade(config, "head")
                self.assertIn("external_id", {
                    column["name"] for column in inspect(engine).get_columns("users")
                })
            finally:
                engine.dispose()


@unittest.skipUnless(os.environ.get("TEST_MYSQL_URL"), "TEST_MYSQL_URL is not configured")
class MySqlUserRepositoryTests(unittest.TestCase):
    def test_mysql_insert_and_rollback_using_temporary_table(self) -> None:
        engine = create_database_engine(os.environ["TEST_MYSQL_URL"])
        self.addCleanup(engine.dispose)
        temporary_users = Table(
            "users",
            MetaData(),
            *(
                Column(
                    column.name, column.type,
                    primary_key=column.primary_key, nullable=column.nullable, unique=column.unique,
                )
                for column in UserModel.__table__.columns
            ),
            prefixes=["TEMPORARY"],
        )
        with engine.connect() as connection:
            temporary_users.create(connection)
            connection.commit()
            try:
                sessions = sessionmaker(bind=connection, expire_on_commit=False)
                repository = SqlAlchemyUserRepository(sessions)
                repository.add(DomainUserModel(id="first-user", email="test@example.com", external_id="first-sub", status=UserStatus.REGISTERED))
                with self.assertRaises(PersistenceError):
                    repository.add(DomainUserModel(id="duplicate-user", email="test@example.com", external_id="duplicate-sub", status=UserStatus.REGISTERED))
                repository.add(DomainUserModel(id="second-user", email="other@example.com", external_id="second-sub", status=UserStatus.REGISTERED))

                with sessions() as session:
                    self.assertEqual(session.get(UserModel, "first-user").email, "test@example.com")
                    self.assertEqual(session.get(UserModel, "first-user").external_id, "first-sub")
                    self.assertIsNone(session.get(UserModel, "duplicate-user"))
                    self.assertEqual(len(session.scalars(select(UserModel)).all()), 2)
            finally:
                temporary_users.drop(connection)
                connection.commit()