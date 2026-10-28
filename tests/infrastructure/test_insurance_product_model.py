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

from infrastructure.persistence.sqlalchemy.models import (
    Base,
    InsuranceBranchModel,
    InsuranceCategoryModel,
    InsuranceProductModel,
)


class InsuranceProductModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def test_product_persists_branch_name_and_code(self) -> None:
        with self.sessions.begin() as session:
            session.add(InsuranceCategoryModel(id="category-id", name="Health"))
        with self.sessions.begin() as session:
            session.add(InsuranceBranchModel(id="branch-id", category_id="category-id", name="Individual"))
        with self.sessions.begin() as session:
            session.add(InsuranceProductModel(
                id="product-id", branch_id="branch-id", name="Standard Cover", product_code="STD-001",
            ))

        with self.sessions() as session:
            product = session.get(InsuranceProductModel, "product-id")
            self.assertEqual(product.branch_id, "branch-id")
            self.assertEqual(product.name, "Standard Cover")
            self.assertEqual(product.product_code, "STD-001")

    def test_product_requires_existing_branch(self) -> None:
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(InsuranceProductModel(
                    id="product-id", branch_id="missing-branch", name="Standard Cover", product_code="STD-001",
                ))

    def test_product_table_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(InsuranceProductModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("CREATE TABLE insurance_products", statement)
        self.assertIn("product_code VARCHAR(64) NOT NULL", statement)
        self.assertIn("FOREIGN KEY(branch_id) REFERENCES insurance_branches (id) ON DELETE RESTRICT", statement)

    def test_product_migration_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurance_products.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "f6a2c9d184b3")
            engine = create_engine(database_url)
            try:
                command.upgrade(config, "head")
                engine.dispose()

                self.assertIn("insurance_products", inspect(engine).get_table_names())
                self.assertEqual(
                    {column["name"] for column in inspect(engine).get_columns("insurance_products")},
                    {"id", "branch_id", "name", "product_code"},
                )
                self.assertEqual(
                    inspect(engine).get_foreign_keys("insurance_products")[0]["referred_table"],
                    "insurance_branches",
                )

                command.downgrade(config, "f6a2c9d184b3")
                engine.dispose()
                self.assertNotIn("insurance_products", inspect(engine).get_table_names())
            finally:
                engine.dispose()