from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from infrastructure.persistence.sqlalchemy.models import Base, BrokerModel, UserBrokerModel, UserModel


class BrokerageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.created_at = datetime(2026, 10, 27)
        with self.sessions.begin() as session:
            session.add_all([
                UserModel(id="first-user", email="first@example.com", external_id="first-sub", created_at=self.created_at),
                UserModel(id="second-user", email="second@example.com", external_id="second-sub", created_at=self.created_at),
                BrokerModel(id="first-brokerage", name="First Brokerage", created_at=self.created_at),
                BrokerModel(id="second-brokerage", name="Second Brokerage", created_at=self.created_at),
            ])

    def test_brokerage_name_is_persisted(self) -> None:
        with self.sessions() as session:
            self.assertEqual(session.get(BrokerModel, "first-brokerage").name, "First Brokerage")

    def test_brokerage_requires_name(self) -> None:
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(BrokerModel(id="unnamed", created_at=self.created_at))

    def test_users_and_brokerages_have_many_to_many_memberships(self) -> None:
        with self.sessions.begin() as session:
            session.add_all([
                UserBrokerModel(user_id="first-user", brokerage_id="first-brokerage", created_at=self.created_at),
                UserBrokerModel(user_id="first-user", brokerage_id="second-brokerage", created_at=self.created_at),
                UserBrokerModel(user_id="second-user", brokerage_id="first-brokerage", created_at=self.created_at),
            ])
        with self.sessions() as session:
            self.assertEqual(len(session.scalars(select(UserBrokerModel)).all()), 3)

    def test_duplicate_membership_is_rejected(self) -> None:
        with self.sessions.begin() as session:
            session.add(UserBrokerModel(user_id="first-user", brokerage_id="first-brokerage", created_at=self.created_at))
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(UserBrokerModel(user_id="first-user", brokerage_id="first-brokerage", created_at=self.created_at))

    def test_memberships_require_existing_user_and_brokerage(self) -> None:
        for user_id, brokerage_id in (("missing-user", "first-brokerage"), ("first-user", "missing-brokerage")):
            with self.subTest(user_id=user_id, brokerage_id=brokerage_id):
                with self.assertRaises(IntegrityError):
                    with self.sessions.begin() as session:
                        session.add(UserBrokerModel(user_id=user_id, brokerage_id=brokerage_id, created_at=self.created_at))

    def test_linked_users_and_brokerages_cannot_be_deleted(self) -> None:
        with self.sessions.begin() as session:
            session.add(UserBrokerModel(user_id="first-user", brokerage_id="first-brokerage", created_at=self.created_at))
        for model, record_id in ((UserModel, "first-user"), (BrokerModel, "first-brokerage")):
            with self.subTest(model=model):
                with self.assertRaises(IntegrityError):
                    with self.sessions.begin() as session:
                        session.delete(session.get(model, record_id))

    def test_schema_compiles_for_mysql(self) -> None:
        brokerage = str(CreateTable(BrokerModel.__table__).compile(dialect=mysql.dialect()))
        membership = str(CreateTable(UserBrokerModel.__table__).compile(dialect=mysql.dialect()))
        self.assertIn("CREATE TABLE brokerage", brokerage)
        self.assertIn("name VARCHAR(255) NOT NULL", brokerage)
        self.assertIn("PRIMARY KEY (user_id, brokerage_id)", membership)
        self.assertIn("FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT", membership)
        self.assertIn("FOREIGN KEY(brokerage_id) REFERENCES brokerage (id) ON DELETE RESTRICT", membership)

    def test_migration_preserves_existing_users(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/brokerage.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "b70d8c2f910a")
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(UserModel.__table__.insert().values(
                        id="existing-user", email="user@example.com", external_id="cognito-sub", created_at=self.created_at,
                    ))

                command.upgrade(config, "head")
                engine.dispose()

                foreign_keys = inspect(engine).get_foreign_keys("user_brokerage")
                self.assertEqual({key["referred_table"] for key in foreign_keys}, {"users", "brokerage"})
                self.assertEqual(inspect(engine).get_pk_constraint("user_brokerage")["constrained_columns"], ["user_id", "brokerage_id"])
                self.assertIn("ix_user_brokerage_brokerage_id", {
                    index["name"] for index in inspect(engine).get_indexes("user_brokerage")
                })
                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                with sessions.begin() as session:
                    session.add(BrokerModel(id="brokerage-id", name="Example Brokerage", created_at=self.created_at))
                with sessions.begin() as session:
                    session.add(UserBrokerModel(user_id="existing-user", brokerage_id="brokerage-id", created_at=self.created_at))
                with sessions() as session:
                    self.assertIsNotNone(session.get(UserBrokerModel, ("existing-user", "brokerage-id")))

                command.downgrade(config, "b70d8c2f910a")

                self.assertFalse(inspect(engine).has_table("user_brokerage"))
                self.assertFalse(inspect(engine).has_table("brokerage"))
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(select(UserModel.id)).scalar_one(), "existing-user")

                command.upgrade(config, "head")
                self.assertTrue(inspect(engine).has_table("brokerage"))
            finally:
                engine.dispose()