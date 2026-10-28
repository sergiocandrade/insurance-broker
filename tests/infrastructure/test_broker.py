from datetime import datetime
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, inspect, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from infrastructure.persistence.sqlalchemy.database import create_database_engine
from infrastructure.persistence.sqlalchemy.models.user_model import Base, UserInvitationModel, BrokerModel, UserModel


class BrokerTests(unittest.TestCase):
    def test_broker_schema_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(BrokerModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("CREATE TABLE broker", statement)
        self.assertIn("id VARCHAR(36) NOT NULL", statement)
        self.assertIn("name VARCHAR(255)", statement)
        self.assertIn("created_at DATETIME NOT NULL", statement)
        self.assertIn("PRIMARY KEY (id)", statement)

    def test_broker_migration_preserves_existing_users(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/broker.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "b70d8c2f910a")
            engine = create_database_engine(database_url)
            try:
                created_at = datetime(2026, 10, 27)
                with engine.begin() as connection:
                    connection.execute(UserModel.__table__.insert().values(
                        id="user-id", email="user@example.com", external_id="cognito-sub",
                        created_at=created_at,
                    ))

                command.upgrade(config, "head")

                self.assertEqual(
                    {column["name"] for column in inspect(engine).get_columns("broker")},
                    {"id", "name", "created_at"},
                )
                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                with sessions.begin() as session:
                    session.add(BrokerModel(id="broker-id", name="Example Brokerage", created_at=created_at))
                with sessions() as session:
                    broker = session.get(BrokerModel, "broker-id")
                    self.assertIsNotNone(broker)
                    self.assertEqual(broker.name, "Example Brokerage")
                    self.assertEqual(broker.created_at, created_at)

                command.downgrade(config, "b70d8c2f910a")

                self.assertFalse(inspect(engine).has_table("broker"))
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(select(UserModel.id)).scalar_one(), "user-id")

                command.upgrade(config, "head")
                self.assertTrue(inspect(engine).has_table("broker"))
            finally:
                engine.dispose()


    def test_name_migration_preserves_existing_brokers(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/broker_name.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "f386a1d9e072")
            engine = create_database_engine(database_url)
            try:
                broker = Table("broker", MetaData(), autoload_with=engine)
                created_at = datetime(2026, 10, 27)
                with engine.begin() as connection:
                    connection.execute(broker.insert().values(id="existing-broker", created_at=created_at))

                command.upgrade(config, "head")

                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                with sessions() as session:
                    saved = session.get(BrokerModel, "existing-broker")
                    self.assertIsNotNone(saved)
                    self.assertIsNone(saved.name)
                    self.assertEqual(saved.created_at, created_at)

                command.downgrade(config, "f386a1d9e072")

                self.assertNotIn("name", {column["name"] for column in inspect(engine).get_columns("broker")})
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(select(broker.c.id)).scalar_one(), "existing-broker")
            finally:
                engine.dispose()


class BrokerInvitationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_database_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.created_at = datetime(2026, 10, 27)
        self.expires_at = datetime(2026, 11, 3)

    def invitation(self, invitation_id: str = "invitation-id") -> UserInvitationModel:
        return UserInvitationModel(
            id=invitation_id,
            email="invitee@example.com",
            created_at=self.created_at,
            expires_at=self.expires_at,
        )

    def test_invitation_persists_without_broker_inviter_or_code(self) -> None:
        with self.sessions.begin() as session:
            session.add(self.invitation())

        with self.sessions() as session:
            invitation = session.get(UserInvitationModel, "invitation-id")
            self.assertEqual(invitation.email, "invitee@example.com")
            self.assertEqual(invitation.expires_at, self.expires_at)
            self.assertIsNone(invitation.broker_id)
            self.assertIsNone(invitation.accepted_at)
            self.assertIsNone(session.scalar(select(UserModel.id)))
        self.assertNotIn("code", UserInvitationModel.__table__.columns)
        self.assertNotIn("code_hash", UserInvitationModel.__table__.columns)
        self.assertNotIn("invited_by_user_id", UserInvitationModel.__table__.columns)
        self.assertIn("broker_id", UserInvitationModel.__table__.columns)

    def test_multiple_invitations_for_same_email_are_allowed(self) -> None:
        with self.sessions.begin() as session:
            session.add(self.invitation())
            session.add(self.invitation("another-id"))

        with self.sessions() as session:
            self.assertEqual(len(session.scalars(select(UserInvitationModel)).all()), 2)

    def test_invitation_has_broker_foreign_key(self) -> None:
        foreign_key = next(iter(UserInvitationModel.__table__.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "broker.id")
        self.assertEqual(foreign_key.ondelete, "RESTRICT")

    def test_invitation_rejects_nonexistent_broker(self) -> None:
        invitation = self.invitation()
        invitation.broker_id = "missing-broker"

        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(invitation)

    def test_invitation_can_reference_existing_broker(self) -> None:
        with self.sessions.begin() as session:
            session.add(BrokerModel(id="broker-id", name="Example Brokerage", created_at=self.created_at))
        with self.sessions.begin() as session:
            invitation = self.invitation()
            invitation.broker_id = "broker-id"
            session.add(invitation)

        with self.sessions() as session:
            self.assertEqual(session.get(UserInvitationModel, "invitation-id").broker_id, "broker-id")

    def test_invitation_can_be_accepted_without_broker(self) -> None:
        with self.sessions.begin() as session:
            invitation = self.invitation()
            invitation.accepted_at = self.created_at
            session.add(invitation)

        with self.sessions() as session:
            invitation = session.get(UserInvitationModel, "invitation-id")
            self.assertEqual(invitation.accepted_at, self.created_at)
            self.assertIsNone(session.scalar(select(BrokerModel.id)))

    def test_invitation_schema_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(UserInvitationModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("CREATE TABLE broker_invitation", statement)
        self.assertNotIn("code_hash", statement)
        self.assertNotIn("invited_by_user_id", statement)
        self.assertIn("FOREIGN KEY(broker_id) REFERENCES broker (id) ON DELETE RESTRICT", statement)

    def test_invitation_migration_preserves_existing_brokers_and_users(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/invitation.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "a6c2b9e8d430")
            engine = create_database_engine(database_url)
            try:
                previous_invitations = Table("broker_invitation", MetaData(), autoload_with=engine)
                with engine.begin() as connection:
                    connection.execute(UserModel.__table__.insert().values(
                        id="inviter-id", email="inviter@example.com", external_id="cognito-sub",
                        created_at=self.created_at,
                    ))
                    connection.execute(BrokerModel.__table__.insert().values(
                        id="broker-id", name="Existing Brokerage", created_at=self.created_at,
                    ))
                    connection.execute(previous_invitations.insert().values(
                        id="legacy-invitation", email="legacy@example.com", invited_by_user_id="inviter-id",
                        code_hash=hashlib.sha256(b"legacy-code").hexdigest(),
                        broker_id="broker-id",
                        created_at=self.created_at, expires_at=self.expires_at,
                    ))

                command.upgrade(config, "head")

                self.assertTrue(inspect(engine).has_table("broker_invitation"))
                self.assertNotIn("invited_by_user_id", {
                    column["name"] for column in inspect(engine).get_columns("broker_invitation")
                })
                self.assertNotIn("code_hash", {
                    column["name"] for column in inspect(engine).get_columns("broker_invitation")
                })
                self.assertIn("broker_id", {
                    column["name"] for column in inspect(engine).get_columns("broker_invitation")
                })
                self.assertIn("ix_broker_invitation_broker_id", {
                    index["name"] for index in inspect(engine).get_indexes("broker_invitation")
                })
                self.assertNotIn("uq_broker_invitation_code_hash", {
                    constraint["name"] for constraint in inspect(engine).get_unique_constraints("broker_invitation")
                })
                self.assertNotIn("ix_broker_invitation_invited_by_user_id", {
                    index["name"] for index in inspect(engine).get_indexes("broker_invitation")
                })
                foreign_keys = inspect(engine).get_foreign_keys("broker_invitation")
                self.assertEqual(len(foreign_keys), 1)
                self.assertEqual(foreign_keys[0]["constrained_columns"], ["broker_id"])
                self.assertEqual(foreign_keys[0]["referred_table"], "broker")
                self.assertEqual(foreign_keys[0]["referred_columns"], ["id"])
                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                with sessions.begin() as session:
                    session.add(self.invitation())
                with sessions() as session:
                    self.assertEqual(session.get(UserInvitationModel, "invitation-id").email, "invitee@example.com")
                    self.assertEqual(session.get(UserInvitationModel, "legacy-invitation").email, "legacy@example.com")
                    self.assertIsNone(session.get(UserInvitationModel, "legacy-invitation").broker_id)

                command.downgrade(config, "f7b2c8a9d015")
                self.assertNotIn("broker_id", {
                    column["name"] for column in inspect(engine).get_columns("broker_invitation")
                })
                command.upgrade(config, "head")

                command.downgrade(config, "a6c2b9e8d430")
                restored = Table("broker_invitation", MetaData(), autoload_with=engine)
                with engine.connect() as connection:
                    self.assertEqual(len(connection.execute(select(restored.c.id)).all()), 2)
                    self.assertEqual(connection.execute(select(restored.c.invited_by_user_id)).scalars().all(), [None, None])
                    self.assertEqual(connection.execute(select(restored.c.code_hash)).scalars().all(), [None, None])
                    self.assertEqual(connection.execute(select(restored.c.broker_id)).scalars().all(), [None, None])
                command.upgrade(config, "head")

                command.downgrade(config, "d0e6f4a8c219")

                self.assertFalse(inspect(engine).has_table("broker_invitation"))
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(select(UserModel.id)).scalar_one(), "inviter-id")
                    self.assertEqual(connection.execute(select(BrokerModel.id)).scalar_one(), "broker-id")
            finally:
                engine.dispose()
