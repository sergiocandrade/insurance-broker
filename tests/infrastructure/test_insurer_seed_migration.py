from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from infrastructure.persistence.sqlalchemy.models import InsurerModel


class InsurerSeedMigrationTests(unittest.TestCase):
    def test_seed_migration_adds_and_removes_only_the_seeded_insurers(self) -> None:
        insurer_names = {
            "Porto Seguro", "Bradesco Seguros", "SulAmérica", "Tokio Marine Seguradora",
            "Allianz Seguros", "MAPFRE Seguros", "Zurich Seguros", "HDI Seguros", "Sompo Seguros",
            "Chubb Seguros", "AXA Seguros", "Icatu Seguros", "MAG Seguros", "Prudential do Brasil",
            "Seguros Unimed", "Pottencial Seguradora", "Junto Seguros", "Sancor Seguros", "Akad Seguros",
            "Too Seguros",
        }
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurers.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "f3a8c1d620b4")
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(InsurerModel.__table__.insert().values(
                        id="custom-insurer-id", name="Custom Insurer",
                    ))

                command.upgrade(config, "head")
                sessions = sessionmaker(bind=engine)
                with sessions() as session:
                    records = session.scalars(select(InsurerModel).order_by(InsurerModel.name)).all()
                    self.assertEqual({record.name for record in records}, insurer_names | {"Custom Insurer"})
                    for record in records:
                        if record.id != "custom-insurer-id":
                            UUID(record.id)

                command.downgrade(config, "f3a8c1d620b4")
                with engine.connect() as connection:
                    remaining = connection.execute(select(InsurerModel.__table__.c.name)).scalars().all()
                self.assertEqual(remaining, ["Custom Insurer"])
            finally:
                engine.dispose()