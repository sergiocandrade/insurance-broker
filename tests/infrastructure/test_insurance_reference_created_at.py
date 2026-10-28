from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from domain.models.customer import CustomerType
from infrastructure.persistence.sqlalchemy.models import (
    Base,
    BrokerModel,
    InsuranceBranchModel,
    InsuranceCategoryModel,
    InsuranceProductModel,
    InsurerModel,
    CustomerModel,
    PolicyModel,
)


class InsuranceReferenceCreatedAtTests(unittest.TestCase):
    def test_orm_defaults_created_at_for_all_tables_that_require_it(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)

        with sessions.begin() as session:
            session.add_all([
                BrokerModel(id="broker-id"),
                InsurerModel(id="insurer-id", name="Insurer"),
                InsuranceCategoryModel(id="category-id", name="Category"),
            ])
        with sessions.begin() as session:
            session.add_all([
                CustomerModel(
                    id="customer-id", name="Customer", customer_type=CustomerType.PERSON,
                    phone="+15555550123", email="customer@example.com", broker_id="broker-id",
                ),
                InsuranceBranchModel(id="branch-id", category_id="category-id", name="Branch"),
            ])
        with sessions.begin() as session:
            session.add(InsuranceProductModel(
                id="product-id", branch_id="branch-id", name="Product", product_code="P-001",
            ))
        with sessions.begin() as session:
            session.add(PolicyModel(
                id="policy-id", customer_id="customer-id", amount=Decimal("100.00"),
                insurance_product_id="product-id", policy_number="POL-001",
                start_date=datetime(2026, 1, 1).date(), end_date=datetime(2027, 1, 1).date(),
            ))
        with sessions.begin() as session:
            session.add(InsuranceCategoryModel(id="another-category", name="Another Category"))

        with sessions() as session:
            for model, record_id in (
                (CustomerModel, "customer-id"),
                (InsurerModel, "insurer-id"),
                (InsuranceCategoryModel, "category-id"),
                (InsuranceBranchModel, "branch-id"),
                (InsuranceProductModel, "product-id"),
                (PolicyModel, "policy-id"),
            ):
                with self.subTest(model=model):
                    created_at = session.get(model, record_id).created_at
                    self.assertIsNotNone(created_at)

    def test_migration_backfills_existing_rows_and_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurance_created_at.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "c7e2a5b8d103")
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(text("INSERT INTO brokers (id) VALUES ('broker-id')"))
                    connection.execute(text("INSERT INTO insurers (id, name) VALUES ('insurer-id', 'Existing Insurer')"))
                    connection.execute(text(
                        "INSERT INTO insurance_categories (id, name) VALUES ('category-id', 'Existing Category')",
                    ))
                    connection.execute(text(
                        "INSERT INTO customers (id, name, customer_type, phone, email, broker_id) "
                        "VALUES ('customer-id', 'Existing Customer', 'PERSON', '+15555550123', "
                        "'customer@example.com', 'broker-id')",
                    ))
                    connection.execute(text(
                        "INSERT INTO insurance_branches (id, category_id, name) "
                        "VALUES ('branch-id', 'category-id', 'Existing Branch')",
                    ))
                    connection.execute(text(
                        "INSERT INTO insurance_products (id, branch_id, name, product_code) "
                        "VALUES ('product-id', 'branch-id', 'Existing Product', 'OLD-001')",
                    ))
                    connection.execute(text(
                        "INSERT INTO policies (id, customer_id, amount, policy_number, start_date, end_date, insurance_product_id) "
                        "VALUES ('policy-id', 'customer-id', 100.00, 'POL-001', '2026-01-01', "
                        "'2027-01-01', 'product-id')",
                    ))

                before_migration = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
                command.upgrade(config, "head")
                engine.dispose()

                record_ids = {
                    "customers": "customer-id",
                    "insurers": "insurer-id",
                    "insurance_categories": "category-id",
                    "insurance_branches": "branch-id",
                    "insurance_products": "product-id",
                    "policies": "policy-id",
                }
                for table_name, record_id in record_ids.items():
                    column = next(column for column in inspect(engine).get_columns(table_name) if column["name"] == "created_at")
                    self.assertFalse(column["nullable"])
                    self.assertIn("CURRENT_TIMESTAMP", column["default"].upper())
                    with engine.connect() as connection:
                        created_at = connection.execute(
                            text(f"SELECT created_at FROM {table_name} WHERE id = :record_id"),
                            {"record_id": record_id},
                        ).scalar_one()
                    self.assertGreaterEqual(datetime.fromisoformat(created_at), before_migration)

                command.downgrade(config, "c7e2a5b8d103")
                engine.dispose()

                for table_name, record_id in record_ids.items():
                    self.assertNotIn("created_at", {
                        column["name"] for column in inspect(engine).get_columns(table_name)
                    })
                    with engine.connect() as connection:
                        remaining = connection.execute(
                            text(f"SELECT id FROM {table_name} WHERE id = :record_id"),
                            {"record_id": record_id},
                        ).scalar_one()
                    self.assertEqual(remaining, record_id)
            finally:
                engine.dispose()