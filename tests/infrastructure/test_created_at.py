from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from infrastructure.persistence.sqlalchemy.models import Base, BrokerModel, UserBrokerModel, UserModel


class CreatedAtTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def test_orm_inserts_populate_current_creation_times(self) -> None:
        before = datetime.now(UTC).replace(tzinfo=None)
        with self.sessions.begin() as session:
            session.add(UserModel(id="user-id", email="user@example.com", name="Example User"))
            session.add(BrokerModel(id="broker-id"))
        with self.sessions.begin() as session:
            session.add(UserBrokerModel(user_id="user-id", broker_id="broker-id"))
        after = datetime.now(UTC).replace(tzinfo=None)

        with self.sessions() as session:
            for model, record_id in (
                (UserModel, "user-id"), (BrokerModel, "broker-id"),
                (UserBrokerModel, ("user-id", "broker-id")),
            ):
                with self.subTest(model=model):
                    created_at = session.get(model, record_id).created_at
                    self.assertLessEqual(before, created_at)
                    self.assertLessEqual(created_at, after)
                    self.assertTrue(model.__table__.c.created_at.default.is_callable)

    def test_direct_sql_inserts_use_database_defaults(self) -> None:
        before = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id, email, name) VALUES ('user-id', 'user@example.com', 'Example User')"))
            connection.execute(text("INSERT INTO brokers (id) VALUES ('broker-id')"))
            connection.execute(text("INSERT INTO users_brokers (user_id, broker_id) VALUES ('user-id', 'broker-id')"))
        after = datetime.now(UTC).replace(tzinfo=None)

        with self.sessions() as session:
            for model, record_id in (
                (UserModel, "user-id"), (BrokerModel, "broker-id"),
                (UserBrokerModel, ("user-id", "broker-id")),
            ):
                with self.subTest(model=model):
                    created_at = session.get(model, record_id).created_at
                    self.assertLessEqual(before, created_at)
                    self.assertLessEqual(created_at, after)

    def test_explicit_creation_time_is_preserved_on_insert_and_update(self) -> None:
        created_at = datetime(2020, 1, 1)
        with self.sessions.begin() as session:
            session.add(UserModel(id="user-id", email="user@example.com", name="Original Name", created_at=created_at))
        with self.sessions.begin() as session:
            session.get(UserModel, "user-id").name = "Updated Name"
        with self.sessions() as session:
            self.assertEqual(session.get(UserModel, "user-id").created_at, created_at)

    def test_activated_at_defaults_to_none_and_preserves_explicit_timestamp(self) -> None:
        activated_at = datetime(2026, 10, 27, 12, 0)
        with self.sessions.begin() as session:
            session.add(UserModel(id="pending-user", email="pending@example.com", name="Pending User"))
            session.add(UserModel(
                id="active-user", email="active@example.com", name="Active User", activated_at=activated_at,
            ))

        with self.sessions() as session:
            self.assertIsNone(session.get(UserModel, "pending-user").activated_at)
            self.assertEqual(session.get(UserModel, "active-user").activated_at, activated_at)

    def test_activated_at_migration_preserves_existing_users_and_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/activated_at.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "c9bf9b1eb451")
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(text(
                        "INSERT INTO users (id, email, name) VALUES ('existing-user', 'existing@example.com', 'Existing User')"
                    ))

                command.upgrade(config, "d7b1a9e20364")
                engine.dispose()

                column = next(column for column in inspect(engine).get_columns("users") if column["name"] == "activated_at")
                self.assertTrue(column["nullable"])
                self.assertIsNone(column["default"])
                with engine.connect() as connection:
                    self.assertIsNone(connection.execute(text("SELECT activated_at FROM users")).scalar_one())

                command.downgrade(config, "c9bf9b1eb451")
                engine.dispose()

                self.assertNotIn("activated_at", {column["name"] for column in inspect(engine).get_columns("users")})
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(text("SELECT id FROM users")).scalar_one(), "existing-user")
            finally:
                engine.dispose()

    def test_mysql_tables_include_current_timestamp_default(self) -> None:
        for model in (UserModel, BrokerModel, UserBrokerModel):
            with self.subTest(model=model):
                statement = str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
                self.assertIn("created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP", statement)

    def test_migration_preserves_existing_timestamp_and_defaults_new_rows(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/created_at.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "287e26e1ddaf")
            engine = create_engine(database_url)
            try:
                created_at = datetime(2020, 1, 1)
                with engine.begin() as connection:
                    connection.execute(UserModel.__table__.insert().values(
                        id="existing-user", email="existing@example.com", name="Existing User", created_at=created_at,
                    ))

                command.upgrade(config, "head")
                engine.dispose()

                for table in ("users", "brokers", "users_brokers"):
                    column = next(column for column in inspect(engine).get_columns(table) if column["name"] == "created_at")
                    self.assertIn("CURRENT_TIMESTAMP", column["default"].upper())
                with engine.begin() as connection:
                    connection.execute(text("INSERT INTO users (id, email, name) VALUES ('new-user', 'new@example.com', 'New User')"))
                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                with sessions() as session:
                    self.assertEqual(session.get(UserModel, "existing-user").created_at, created_at)
                    self.assertIsNotNone(session.get(UserModel, "new-user").created_at)

                command.downgrade(config, "287e26e1ddaf")
                engine.dispose()

                for table in ("users", "brokers", "users_brokers"):
                    column = next(column for column in inspect(engine).get_columns(table) if column["name"] == "created_at")
                    self.assertIsNone(column["default"])
                with sessions() as session:
                    self.assertEqual(session.get(UserModel, "existing-user").created_at, created_at)
            finally:
                engine.dispose()