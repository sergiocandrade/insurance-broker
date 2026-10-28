from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID, NAMESPACE_URL, uuid5

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from infrastructure.persistence.sqlalchemy.models import InsuranceBranchModel, InsuranceCategoryModel


class InsuranceBranchSeedMigrationTests(unittest.TestCase):
    def test_seed_migration_adds_branch_category_pairs_and_removes_only_seeded_rows(self) -> None:
        expected_pairs = {
            ('Automóvel e Mobilidade', 'Automóvel'),
            ('Automóvel e Mobilidade', 'Motocicleta'),
            ('Automóvel e Mobilidade', 'Frota de Veículos'),
            ('Automóvel e Mobilidade', 'Responsabilidade Civil de Veículos'),
            ('Residencial e Patrimonial', 'Residencial'),
            ('Residencial e Patrimonial', 'Condomínio'),
            ('Residencial e Patrimonial', 'Empresarial'),
            ('Residencial e Patrimonial', 'Equipamentos'),
            ('Residencial e Patrimonial', 'Riscos de Engenharia'),
            ('Pessoas', 'Vida Individual'),
            ('Pessoas', 'Vida em Grupo'),
            ('Pessoas', 'Acidentes Pessoais'),
            ('Pessoas', 'Funeral'),
            ('Pessoas', 'Diária por Incapacidade Temporária'),
            ('Saúde e Benefícios', 'Saúde'),
            ('Saúde e Benefícios', 'Odontológico'),
            ('Saúde e Benefícios', 'Vida Empresarial'),
            ('Financeiros e Crédito', 'Prestamista'),
            ('Financeiros e Crédito', 'Crédito'),
            ('Financeiros e Crédito', 'Garantia Estendida'),
            ('Financeiros e Crédito', 'Riscos Financeiros'),
            ('Transporte e Logística', 'Transporte Nacional'),
            ('Transporte e Logística', 'Transporte Internacional'),
            ('Transporte e Logística', 'Responsabilidade Civil do Transportador'),
            ('Transporte e Logística', 'Casco Marítimo'),
            ('Transporte e Logística', 'Riscos Aeronáuticos'),
            ('Responsabilidade Civil', 'Responsabilidade Civil Geral'),
            ('Responsabilidade Civil', 'Responsabilidade Civil Profissional'),
            ('Responsabilidade Civil', 'D&O'),
            ('Responsabilidade Civil', 'Responsabilidade Civil de Produtos'),
            ('Grandes Riscos e Especializados', 'Riscos Operacionais'),
            ('Grandes Riscos e Especializados', 'Energia'),
            ('Grandes Riscos e Especializados', 'Grandes Riscos Empresariais'),
            ('Agrícola e Rural', 'Agrícola'),
            ('Agrícola e Rural', 'Pecuário'),
            ('Agrícola e Rural', 'Penhor Rural'),
            ('Garantias', 'Seguro Garantia'),
            ('Viagem', 'Seguro Viagem'),
            ('Eletrônicos e Equipamentos', 'Celular'),
            ('Eletrônicos e Equipamentos', 'Equipamentos Portáteis'),
            ('Vida e Previdência', 'Vida'),
            ('Vida e Previdência', 'Acidentes Pessoais'),
            ('Odontológico', 'Seguro Odontológico'),
            ('Riscos Cibernéticos', 'Riscos Cibernéticos'),
        }
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/insurance_branches.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "b1c6e8f409a2")
            engine = create_engine(database_url)
            try:
                custom_category_id = str(uuid5(NAMESPACE_URL, "insurance-broker:category:Automóvel e Mobilidade"))
                with engine.begin() as connection:
                    connection.execute(text(
                        "INSERT INTO insurance_branches (id, category_id, name) "
                        "VALUES ('custom-branch-id', :category_id, 'Custom Branch')"
                    ), {"category_id": custom_category_id})

                command.upgrade(config, "head")
                sessions = sessionmaker(bind=engine)
                with sessions() as session:
                    rows = session.execute(
                        select(InsuranceCategoryModel.name, InsuranceBranchModel.name)
                        .join(InsuranceBranchModel, InsuranceBranchModel.category_id == InsuranceCategoryModel.id),
                    ).all()
                    self.assertEqual(set(rows), expected_pairs | {("Automóvel e Mobilidade", "Custom Branch")})
                    for branch in session.scalars(select(InsuranceBranchModel)):
                        if branch.id != "custom-branch-id":
                            UUID(branch.id)

                command.downgrade(config, "b1c6e8f409a2")
                with engine.connect() as connection:
                    remaining = connection.execute(select(InsuranceBranchModel.__table__.c.name)).scalars().all()
                self.assertEqual(remaining, ["Custom Branch"])
            finally:
                engine.dispose()