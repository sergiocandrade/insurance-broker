from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from domain.exceptions.domain import NotFoundException
from domain.models.broker import BrokerModel as DomainBrokerModel, BrokerStatus
from domain.services.broker import BrokerService
from infrastructure.persistence.sqlalchemy.repositories.broker_repository import SqlAlchemyBrokerRepository
from infrastructure.persistence.sqlalchemy.models import Base, BrokerModel


class BrokerStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.created_at = datetime(2026, 10, 27)
        self.repository = SqlAlchemyBrokerRepository(self.sessions)

    def test_update_persists_domain_status_and_activation_time(self) -> None:
        with self.sessions.begin() as session:
            session.add(BrokerModel(id="broker-id", created_at=self.created_at))

        activated_at = datetime(2026, 10, 28)
        self.repository.update(DomainBrokerModel(
            id="broker-id", status=BrokerStatus.ACTIVE, created_at=datetime(2030, 1, 1),
            activated_at=activated_at,
        ))

        with self.sessions() as session:
            saved = session.get(BrokerModel, "broker-id")
            self.assertEqual(saved.status, BrokerStatus.ACTIVE)
            self.assertEqual(saved.activated_at, activated_at)
            self.assertEqual(saved.created_at, self.created_at)

    def test_update_rejects_missing_broker(self) -> None:
        with self.assertRaises(NotFoundException):
            self.repository.update(DomainBrokerModel(
                id="missing-broker", status=BrokerStatus.ACTIVE, created_at=self.created_at,
            ))

    def test_broker_activation_sets_activated_at(self) -> None:
        with self.sessions.begin() as session:
            session.add(BrokerModel(id="broker-id", created_at=self.created_at))

        broker = DomainBrokerModel(
            id="broker-id", status=BrokerStatus.PENDING, created_at=self.created_at,
        )
        activated = BrokerService(self.repository).activate(broker, user_id="user-id")

        with self.sessions() as session:
            saved = session.get(BrokerModel, "broker-id")
            self.assertEqual(saved.status, BrokerStatus.ACTIVE)
            self.assertIsNotNone(saved.activated_at)
            self.assertEqual(activated.activated_at.replace(tzinfo=None), saved.activated_at)

    def test_new_brokers_default_to_pending(self) -> None:
        with self.sessions.begin() as session:
            session.add(BrokerModel(id="broker-id", created_at=self.created_at))

        with self.sessions() as session:
            self.assertEqual(session.get(BrokerModel, "broker-id").status, BrokerStatus.PENDING)

    def test_both_status_values_can_be_persisted(self) -> None:
        with self.sessions.begin() as session:
            session.add_all([
                BrokerModel(id="pending-broker", status=BrokerStatus.PENDING, created_at=self.created_at),
                BrokerModel(id="active-broker", status=BrokerStatus.ACTIVE, created_at=self.created_at),
            ])

        with self.sessions() as session:
            self.assertEqual(session.get(BrokerModel, "pending-broker").status, BrokerStatus.PENDING)
            self.assertEqual(session.get(BrokerModel, "active-broker").status, BrokerStatus.ACTIVE)

    def test_invalid_status_is_rejected_by_orm_and_database(self) -> None:
        with self.assertRaises(StatementError):
            with self.sessions.begin() as session:
                session.add(BrokerModel(id="invalid-broker", status="INVALID", created_at=self.created_at))

        for status in ("INVALID", None):
            with self.subTest(status=status):
                with self.assertRaises(IntegrityError):
                    with self.engine.begin() as connection:
                        connection.execute(
                            text("INSERT INTO brokers (id, status, created_at) VALUES (:id, :status, :created_at)"),
                            {"id": "invalid-broker", "status": status, "created_at": self.created_at},
                        )

    def test_mysql_schema_has_default_and_allowed_statuses(self) -> None:
        statement = str(CreateTable(BrokerModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("status VARCHAR(7) NOT NULL DEFAULT 'PENDING'", statement)
        self.assertIn("CONSTRAINT broker_status CHECK", statement)
        self.assertIn("'PENDING'", statement)
        self.assertIn("'ACTIVE'", statement)

    def test_migration_backfills_pending_and_preserves_brokers(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/status.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "3179ffb054c2")
            engine = create_engine(database_url)
            try:
                brokers = Table("brokers", MetaData(), autoload_with=engine)
                with engine.begin() as connection:
                    connection.execute(brokers.insert().values(id="existing-broker", created_at=self.created_at))

                command.upgrade(config, "head")
                engine.dispose()

                sessions = sessionmaker(bind=engine, expire_on_commit=False)
                with sessions() as session:
                    self.assertEqual(session.get(BrokerModel, "existing-broker").status, BrokerStatus.PENDING)
                migrated_brokers = Table("brokers", MetaData(), autoload_with=engine)
                with engine.begin() as connection:
                    connection.execute(migrated_brokers.insert().values(id="new-broker", created_at=self.created_at))
                with sessions() as session:
                    self.assertEqual(session.get(BrokerModel, "new-broker").status, BrokerStatus.PENDING)

                with self.assertRaises(IntegrityError):
                    with engine.begin() as connection:
                        connection.execute(migrated_brokers.insert().values(
                            id="invalid-broker", status="INVALID", created_at=self.created_at,
                        ))

                command.downgrade(config, "3179ffb054c2")
                engine.dispose()

                self.assertNotIn("status", {column["name"] for column in inspect(engine).get_columns("brokers")})
                with engine.connect() as connection:
                    self.assertEqual(set(connection.execute(select(brokers.c.id)).scalars()), {"existing-broker", "new-broker"})
            finally:
                engine.dispose()

    def test_activated_at_migration_preserves_existing_brokers_and_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/broker_activated_at.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "d7b1a9e20364")
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(text("INSERT INTO brokers (id) VALUES ('existing-broker')"))

                command.upgrade(config, "e4a8c21f6d93")
                engine.dispose()

                column = next(column for column in inspect(engine).get_columns("brokers") if column["name"] == "activated_at")
                self.assertTrue(column["nullable"])
                with engine.connect() as connection:
                    self.assertIsNone(connection.execute(text("SELECT activated_at FROM brokers")).scalar_one())

                command.downgrade(config, "d7b1a9e20364")
                engine.dispose()

                self.assertNotIn("activated_at", {column["name"] for column in inspect(engine).get_columns("brokers")})
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(text("SELECT id FROM brokers")).scalar_one(), "existing-broker")
            finally:
                engine.dispose()