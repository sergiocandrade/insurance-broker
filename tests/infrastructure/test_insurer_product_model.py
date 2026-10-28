from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from infrastructure.persistence.sqlalchemy.models import (
    Base,
    BrokerModel,
    InsuranceBranchModel,
    InsuranceCategoryModel,
    InsuranceProductModel,
    InsurerModel,
    InsurerProductModel,
)


class InsurerProductModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def add_parents(self) -> None:
        with self.sessions.begin() as session:
            session.add_all([
                InsurerModel(id="insurer-id", name="Insurer"),
                BrokerModel(id="broker-id"),
                InsuranceCategoryModel(id="category-id", name="Health"),
            ])
        with self.sessions.begin() as session:
            session.add(InsuranceBranchModel(
                id="branch-id", category_id="category-id", name="Individual",
            ))
        with self.sessions.begin() as session:
            session.add(InsuranceProductModel(
                id="product-id", branch_id="branch-id", name="Cover", product_code="COV-001",
            ))

    def test_association_persists_both_ids(self) -> None:
        self.add_parents()
        with self.sessions.begin() as session:
            session.add(InsurerProductModel(insurer_id="insurer-id", product_id="product-id"))

        with self.sessions() as session:
            relation = session.get(InsurerProductModel, ("insurer-id", "product-id"))
            self.assertEqual(relation.insurer_id, "insurer-id")
            self.assertEqual(relation.product_id, "product-id")
            self.assertIsNotNone(relation.created_at)

    def test_association_rejects_missing_parent(self) -> None:
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(InsurerProductModel(insurer_id="missing-insurer", product_id="missing-product"))

    def test_association_has_composite_primary_key_and_mysql_foreign_keys(self) -> None:
        self.assertEqual(
            [column.name for column in InsurerProductModel.__table__.primary_key.columns],
            ["insurer_id", "product_id"],
        )
        statement = str(CreateTable(InsurerProductModel.__table__).compile(dialect=mysql.dialect()))
        self.assertIn("CREATE TABLE insurer_products", statement)
        self.assertIn("created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP", statement)
        self.assertIn("FOREIGN KEY(insurer_id) REFERENCES insurers (id) ON DELETE RESTRICT", statement)
        self.assertIn("FOREIGN KEY(product_id) REFERENCES insurance_products (id) ON DELETE RESTRICT", statement)

    def test_migration_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurer_products.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "d8a4c1f703e6")
            engine = create_engine(database_url)
            try:
                category_id = "category-id"
                with engine.begin() as connection:
                    connection.execute(InsuranceCategoryModel.__table__.insert().values(
                        id=category_id, name="Migration Category",
                    ))
                    connection.execute(InsuranceBranchModel.__table__.insert().values(
                        id="branch-id", category_id=category_id, name="Migration Branch",
                    ))
                    connection.execute(InsurerModel.__table__.insert().values(
                        id="insurer-id", name="Migration Insurer",
                    ))
                    connection.execute(InsuranceProductModel.__table__.insert().values(
                        id="product-id", branch_id="branch-id", name="Migration Product", product_code="MIG-001",
                    ))
                    connection.exec_driver_sql(
                        "INSERT INTO insurer_products (insurer_id, product_id) VALUES (?, ?)",
                        ("insurer-id", "product-id"),
                    )

                command.upgrade(config, "head")
                engine.dispose()

                self.assertIn("insurer_products", inspect(engine).get_table_names())
                self.assertIn("created_at", {
                    column["name"] for column in inspect(engine).get_columns("insurer_products")
                })
                self.assertEqual(
                    inspect(engine).get_pk_constraint("insurer_products")["constrained_columns"],
                    ["insurer_id", "product_id"],
                )
                self.assertEqual(
                    {foreign_key["referred_table"] for foreign_key in inspect(engine).get_foreign_keys("insurer_products")},
                    {"insurers", "insurance_products"},
                )
                with engine.connect() as connection:
                    saved_at = connection.execute(
                        select(InsurerProductModel.__table__.c.created_at)
                        .where(InsurerProductModel.__table__.c.insurer_id == "insurer-id"),
                    ).scalar_one()
                self.assertIsNotNone(saved_at)

                command.downgrade(config, "d8a4c1f703e6")
                engine.dispose()
                self.assertNotIn("created_at", {
                    column["name"] for column in inspect(engine).get_columns("insurer_products")
                })
            finally:
                engine.dispose()