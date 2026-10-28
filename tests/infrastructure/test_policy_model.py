from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from domain.models.customer import CustomerType
from domain.models.policy import PolicyModel as DomainPolicyModel
from infrastructure.persistence.sqlalchemy.models import (
    Base,
    BrokerModel,
    CustomerModel,
    InsuranceBranchModel,
    InsuranceCategoryModel,
    InsuranceProductModel,
    InsurerModel,
    PolicyModel,
)


class PolicyModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def add_policy_dependencies(self) -> None:
        with self.sessions.begin() as session:
            session.add(BrokerModel(id="broker-id"))
        with self.sessions.begin() as session:
            session.add(CustomerModel(
                id="customer-id", name="Customer", customer_type=CustomerType.PERSON,
                phone="+15555550123", email="customer@example.com", broker_id="broker-id",
            ))
            session.add_all([
                InsuranceCategoryModel(id="category-id", name="Health"),
                InsurerModel(id="insurer-id", name="Insurer"),
            ])
        with self.sessions.begin() as session:
            session.add(InsuranceBranchModel(id="branch-id", category_id="category-id", name="Individual"))
        with self.sessions.begin() as session:
            session.add(InsuranceProductModel(
                id="product-id", branch_id="branch-id", name="Health Cover", product_code="HLT-001",
            ))

    def test_policy_persists_customer_and_decimal_amount(self) -> None:
        self.add_policy_dependencies()
        start_date = date(2026, 10, 28)
        end_date = date(2027, 10, 28)
        with self.sessions.begin() as session:
            session.add(PolicyModel(
                id="policy-id", customer_id="customer-id", amount=Decimal("125.50"),
                insurance_product_id="product-id", policy_number="POL-2026-001", status="ACTIVE",
                start_date=start_date, end_date=end_date,
            ))

        with self.sessions() as session:
            policy = session.get(PolicyModel, "policy-id")
            self.assertEqual(policy.customer_id, "customer-id")
            self.assertEqual(policy.amount, Decimal("125.50"))
            self.assertEqual(policy.insurance_product_id, "product-id")
            self.assertEqual(policy.status, "ACTIVE")
            self.assertEqual(policy.policy_number, "POL-2026-001")
            self.assertEqual(policy.start_date, start_date)
            self.assertEqual(policy.end_date, end_date)

    def test_policy_status_defaults_to_pending(self) -> None:
        self.add_policy_dependencies()
        with self.sessions.begin() as session:
            session.add(PolicyModel(
                id="policy-id", customer_id="customer-id", amount=Decimal("125.50"),
                insurance_product_id="product-id", policy_number="POL-2026-002",
                start_date=date(2026, 10, 28), end_date=date(2027, 10, 28),
            ))

        with self.sessions() as session:
            policy = session.get(PolicyModel, "policy-id")
            self.assertEqual(policy.status, "PENDING")

    def test_policy_rejects_missing_customer_or_insurance_product(self) -> None:
        self.add_policy_dependencies()
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(PolicyModel(
                    id="policy-id", customer_id="customer-id", amount=Decimal("100.00"),
                    insurance_product_id="missing-product", policy_number="POL-2026-003",
                    start_date=date(2026, 10, 28), end_date=date(2027, 10, 28),
                ))
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(PolicyModel(
                    id="another-policy", customer_id="missing-customer", amount=Decimal("100.00"),
                    insurance_product_id="product-id", policy_number="POL-2026-004",
                    start_date=date(2026, 10, 28), end_date=date(2027, 10, 28),
                ))

    def test_policy_table_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(PolicyModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("CREATE TABLE policies", statement)
        self.assertIn("amount NUMERIC(12, 2) NOT NULL", statement)
        self.assertIn("status VARCHAR(32) NOT NULL DEFAULT 'PENDING'", statement)
        self.assertIn("policy_number VARCHAR(64) NOT NULL", statement)
        self.assertIn("start_date DATE NOT NULL", statement)
        self.assertIn("end_date DATE NOT NULL", statement)
        self.assertIn("insurance_product_id VARCHAR(36) NOT NULL", statement)
        self.assertIn("FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE RESTRICT", statement)
        self.assertIn("FOREIGN KEY(insurance_product_id) REFERENCES insurance_products (id) ON DELETE RESTRICT", statement)
        self.assertNotIn("insurance_id", statement)

    def test_policy_domain_model_stores_foreign_keys_and_amount(self) -> None:
        policy = DomainPolicyModel(
            id="policy-id", customer_id="customer-id", amount=Decimal("99.95"),
            insurance_product_id="product-id", policy_number="POL-2026-001",
            start_date=date(2026, 10, 28), end_date=date(2027, 10, 28),
        )
        self.assertEqual(policy.amount, Decimal("99.95"))
        self.assertEqual(policy.insurance_product_id, "product-id")
        self.assertEqual(policy.policy_number, "POL-2026-001")

    def test_policy_migration_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/policies.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "13a589717224")
            engine = create_engine(database_url)
            try:
                command.upgrade(config, "head")
                engine.dispose()

                self.assertIn("policies", inspect(engine).get_table_names())
                self.assertEqual(
                    {column["name"] for column in inspect(engine).get_columns("policies")},
                    {
                        "id", "customer_id", "amount", "status", "insurance_product_id",
                        "policy_number", "start_date", "end_date",
                    },
                )
                self.assertEqual(
                    {foreign_key["referred_table"] for foreign_key in inspect(engine).get_foreign_keys("policies")},
                    {"customers", "insurance_products"},
                )
                self.assertNotIn("insurances", inspect(engine).get_table_names())
                policy_columns = {column["name"]: column for column in inspect(engine).get_columns("policies")}
                self.assertEqual(policy_columns["status"]["default"], "'PENDING'")
                self.assertFalse(policy_columns["insurance_product_id"]["nullable"])
                self.assertFalse(policy_columns["policy_number"]["nullable"])
                self.assertFalse(policy_columns["start_date"]["nullable"])
                self.assertFalse(policy_columns["end_date"]["nullable"])

                command.downgrade(config, "13a589717224")
                engine.dispose()
                restored_policy_columns = {column["name"] for column in inspect(engine).get_columns("policies")}
                self.assertIn("expires_at", restored_policy_columns)
                self.assertNotIn("policy_number", restored_policy_columns)
            finally:
                engine.dispose()