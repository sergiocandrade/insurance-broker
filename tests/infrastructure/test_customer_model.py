from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from domain.models.customer import CustomerType
from infrastructure.persistence.sqlalchemy.models import Base, BrokerModel, CustomerModel


class CustomerModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def test_customer_persists_fields_and_broker_relationship(self) -> None:
        with self.sessions.begin() as session:
            session.add(BrokerModel(id="broker-id"))
            session.add(CustomerModel(
                id="customer-id",
                name="Example Customer",
                customer_type=CustomerType.PERSON,
                phone="+15555550123",
                email="customer@example.com",
                broker_id="broker-id",
            ))

        with self.sessions() as session:
            customer = session.get(CustomerModel, "customer-id")
            self.assertEqual(customer.name, "Example Customer")
            self.assertEqual(customer.customer_type, CustomerType.PERSON)
            self.assertEqual(customer.phone, "+15555550123")
            self.assertEqual(customer.email, "customer@example.com")
            self.assertEqual(customer.broker_id, "broker-id")

    def test_customer_type_is_constrained(self) -> None:
        with self.assertRaises(StatementError):
            with self.sessions.begin() as session:
                session.add(CustomerModel(
                    id="customer-id", name="Invalid", customer_type="INVALID",
                    phone="+15555550123", email="customer@example.com", broker_id="broker-id",
                ))

    def test_customer_requires_an_existing_broker(self) -> None:
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(CustomerModel(
                    id="customer-id", name="Example Customer", customer_type=CustomerType.BUSINESS,
                    phone="+15555550123", email="customer@example.com", broker_id="missing-broker",
                ))

    def test_customer_table_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(CustomerModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("CREATE TABLE customers", statement)
        self.assertIn("customer_type VARCHAR(8) NOT NULL", statement)
        self.assertIn("FOREIGN KEY(broker_id) REFERENCES brokers (id) ON DELETE RESTRICT", statement)

    def test_customer_migration_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/customers.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "e4a8c21f6d93")
            engine = create_engine(database_url)
            try:
                command.upgrade(config, "head")
                engine.dispose()

                self.assertIn("customers", inspect(engine).get_table_names())
                self.assertEqual(
                    {column["name"] for column in inspect(engine).get_columns("customers")},
                    {"id", "name", "customer_type", "phone", "email", "broker_id"},
                )
                self.assertEqual(
                    inspect(engine).get_foreign_keys("customers")[0]["referred_table"],
                    "brokers",
                )

                command.downgrade(config, "e4a8c21f6d93")
                engine.dispose()
                self.assertNotIn("customers", inspect(engine).get_table_names())
            finally:
                engine.dispose()