from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from infrastructure.persistence.sqlalchemy.models import InsuranceCategoryModel


class InsuranceCategorySeedMigrationTests(unittest.TestCase):
    def test_seed_migration_adds_and_removes_only_the_seeded_categories(self) -> None:
        category_names = {
            'Automóvel e Mobilidade', 'Residencial e Patrimonial', 'Pessoas', 'Saúde e Benefícios',
            'Financeiros e Crédito', 'Transporte e Logística', 'Responsabilidade Civil',
            'Grandes Riscos e Especializados', 'Agrícola e Rural', 'Garantias', 'Viagem',
            'Eletrônicos e Equipamentos', 'Vida e Previdência', 'Odontológico', 'Riscos Cibernéticos',
        }
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurance_categories.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "b1c6e8f409a2")
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(InsuranceCategoryModel.__table__.insert().values(
                        id="custom-category-id", name="Custom Category",
                    ))

                command.upgrade(config, "head")
                sessions = sessionmaker(bind=engine)
                with sessions() as session:
                    records = session.scalars(select(InsuranceCategoryModel)).all()
                    self.assertEqual({record.name for record in records}, category_names | {"Custom Category"})
                    for record in records:
                        if record.id != "custom-category-id":
                            UUID(record.id)

                command.downgrade(config, "b1c6e8f409a2")
                with engine.connect() as connection:
                    remaining = connection.execute(select(InsuranceCategoryModel.__table__.c.name)).scalars().all()
                self.assertEqual(remaining, ["Custom Category"])
            finally:
                engine.dispose()