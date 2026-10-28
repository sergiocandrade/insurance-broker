from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from infrastructure.persistence.sqlalchemy.models import Base, InsurerModel


class InsurerModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def test_insurer_persists_fields(self) -> None:
        with self.sessions.begin() as session:
            session.add(InsurerModel(
                id="insurer-id", name="Example Insurer",
            ))

        with self.sessions() as session:
            insurer = session.get(InsurerModel, "insurer-id")
            self.assertEqual(insurer.name, "Example Insurer")

    def test_insurer_table_compiles_for_mysql(self) -> None:
        statement = str(CreateTable(InsurerModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("CREATE TABLE insurers", statement)
        self.assertIn("name VARCHAR(255) NOT NULL", statement)
        self.assertNotIn("phone", statement)
        self.assertNotIn("email", statement)

    def test_insurer_migration_is_reversible(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurers.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "f1c4a8d263b7")
            engine = create_engine(database_url)
            try:
                command.upgrade(config, "head")
                engine.dispose()

                self.assertIn("insurers", inspect(engine).get_table_names())
                self.assertEqual(
                    {column["name"] for column in inspect(engine).get_columns("insurers")},
                    {"id", "name"},
                )

                command.downgrade(config, "f1c4a8d263b7")
                engine.dispose()
                self.assertNotIn("insurers", inspect(engine).get_table_names())
            finally:
                engine.dispose()