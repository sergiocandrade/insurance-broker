from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import NAMESPACE_URL, UUID, uuid5

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from infrastructure.persistence.sqlalchemy.models import (
    InsuranceBranchModel,
    InsuranceCategoryModel,
    InsurerModel,
)


class ReferenceSeedMigrationTests(unittest.TestCase):
    def test_seed_migrations_create_insurers_categories_and_branches(self) -> None:
        expected_insurers = {
            'Porto Seguro', 'Bradesco Seguros', 'SulAmérica', 'Tokio Marine Seguradora', 'Allianz Seguros',
            'MAPFRE Seguros', 'Zurich Seguros', 'HDI Seguros', 'Sompo Seguros', 'Chubb Seguros',
            'AXA Seguros', 'Icatu Seguros', 'MAG Seguros', 'Prudential do Brasil', 'Seguros Unimed',
            'Pottencial Seguradora', 'Junto Seguros', 'Sancor Seguros', 'Akad Seguros', 'Too Seguros',
        }
        expected_categories = {
            'Automóvel e Mobilidade', 'Residencial e Patrimonial', 'Pessoas', 'Saúde e Benefícios',
            'Financeiros e Crédito', 'Transporte e Logística', 'Responsabilidade Civil',
            'Grandes Riscos e Especializados', 'Agrícola e Rural', 'Garantias', 'Viagem',
            'Eletrônicos e Equipamentos', 'Vida e Previdência', 'Odontológico', 'Riscos Cibernéticos',
        }
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/reference_seeds.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "73a9cdfab8aa")
            engine = create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.execute(InsurerModel.__table__.insert().values(
                        id="custom-insurer-id", name="Custom Insurer",
                    ))
                    connection.execute(InsuranceCategoryModel.__table__.insert().values(
                        id="custom-category-id", name="Custom Category",
                    ))
                    connection.execute(InsuranceBranchModel.__table__.insert().values(
                        id="custom-branch-id", category_id="custom-category-id", name="Custom Branch",
                    ))

                command.upgrade(config, "head")
                sessions = sessionmaker(bind=engine)
                with sessions() as session:
                    insurers = session.scalars(select(InsurerModel)).all()
                    categories = session.scalars(select(InsuranceCategoryModel)).all()
                    branches = session.execute(
                        select(InsuranceCategoryModel.name, InsuranceBranchModel.name)
                        .join(InsuranceBranchModel, InsuranceBranchModel.category_id == InsuranceCategoryModel.id),
                    ).all()

                self.assertEqual({row.name for row in insurers}, expected_insurers | {"Custom Insurer"})
                self.assertEqual({row.name for row in categories}, expected_categories | {"Custom Category"})
                self.assertEqual(len(branches), 45)
                self.assertIn(("Automóvel e Mobilidade", "Automóvel"), branches)
                self.assertIn(("Riscos Cibernéticos", "Riscos Cibernéticos"), branches)
                for row in [*insurers, *categories]:
                    if not row.id.startswith("custom-"):
                        UUID(row.id)

                command.downgrade(config, "73a9cdfab8aa")
                with sessions() as session:
                    self.assertEqual(
                        session.scalars(select(InsurerModel.name)).all(), ["Custom Insurer"],
                    )
                    self.assertEqual(
                        session.scalars(select(InsuranceCategoryModel.name)).all(), ["Custom Category"],
                    )
                    self.assertEqual(
                        session.scalars(select(InsuranceBranchModel.name)).all(), ["Custom Branch"],
                    )
            finally:
                engine.dispose()