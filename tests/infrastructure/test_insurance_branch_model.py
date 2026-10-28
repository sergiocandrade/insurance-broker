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

from infrastructure.persistence.sqlalchemy.models import Base, InsuranceBranchModel, InsuranceCategoryModel


class InsuranceBranchModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def test_branch_persists_id_category_and_name(self) -> None:
        with self.sessions.begin() as session:
            session.add(InsuranceCategoryModel(id="category-id", name="Health"))
        with self.sessions.begin() as session:
            session.add(InsuranceBranchModel(id="branch-id", category_id="category-id", name="Individual"))

        with self.sessions() as session:
            branch = session.get(InsuranceBranchModel, "branch-id")
            self.assertEqual(branch.category_id, "category-id")
            self.assertEqual(branch.name, "Individual")

    def test_branch_requires_existing_category(self) -> None:
        with self.assertRaises(IntegrityError):
            with self.sessions.begin() as session:
                session.add(InsuranceBranchModel(
                    id="branch-id", category_id="missing-category", name="Individual",
                ))

    def test_branch_table_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(InsuranceBranchModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("CREATE TABLE insurance_branches", statement)
        self.assertIn("FOREIGN KEY(category_id) REFERENCES insurance_categories (id) ON DELETE RESTRICT", statement)

    def test_branch_migration_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurance_branches.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "e9a1f3b7c205")
            engine = create_engine(database_url)
            try:
                command.upgrade(config, "head")
                engine.dispose()

                self.assertIn("insurance_branches", inspect(engine).get_table_names())
                self.assertEqual(
                    {column["name"] for column in inspect(engine).get_columns("insurance_branches")},
                    {"id", "category_id", "name"},
                )
                self.assertEqual(
                    inspect(engine).get_foreign_keys("insurance_branches")[0]["referred_table"],
                    "insurance_categories",
                )

                command.downgrade(config, "e9a1f3b7c205")
                engine.dispose()
                self.assertNotIn("insurance_branches", inspect(engine).get_table_names())
            finally:
                engine.dispose()