from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from infrastructure.persistence.sqlalchemy.models import Base, InsuranceCategoryModel


class InsuranceCategoryModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def test_category_persists_id_and_name(self) -> None:
        with self.sessions.begin() as session:
            session.add(InsuranceCategoryModel(id="category-id", name="Health"))

        with self.sessions() as session:
            category = session.get(InsuranceCategoryModel, "category-id")
            self.assertEqual(category.name, "Health")

    def test_table_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(InsuranceCategoryModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("CREATE TABLE insurance_categories", statement)
        self.assertIn("name VARCHAR(255) NOT NULL", statement)

    def test_migration_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurance_categories.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "a2c7d9e451b6")
            engine = create_engine(database_url)
            try:
                command.upgrade(config, "head")
                engine.dispose()

                self.assertIn("insurance_categories", inspect(engine).get_table_names())
                self.assertEqual(
                    {column["name"] for column in inspect(engine).get_columns("insurance_categories")},
                    {"id", "name"},
                )

                command.downgrade(config, "a2c7d9e451b6")
                engine.dispose()
                self.assertNotIn("insurance_categories", inspect(engine).get_table_names())
            finally:
                engine.dispose()