"""Seed insurance branch records."""
from typing import Sequence, Union
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa


revision: str = 'c7e2a5b8d103'
down_revision: Union[str, None] = 'b6d9f2a4c107'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORY_BRANCHES = (
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
)


def branch_id(category_name: str, branch_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f'insurance-broker:branch:{category_name}:{branch_name}'))


def category_id(category_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f'insurance-broker:category:{category_name}'))


def upgrade() -> None:
    branches = sa.table(
        'insurance_branches',
        sa.column('id', sa.String(length=36)),
        sa.column('category_id', sa.String(length=36)),
        sa.column('name', sa.String(length=255)),
    )
    op.bulk_insert(branches, [
        {
            'id': branch_id(category_name, branch_name),
            'category_id': category_id(category_name),
            'name': branch_name,
        }
        for category_name, branch_name in CATEGORY_BRANCHES
    ])


def downgrade() -> None:
    branches = sa.table('insurance_branches', sa.column('id', sa.String(length=36)))
    ids = [branch_id(category_name, branch_name) for category_name, branch_name in CATEGORY_BRANCHES]
    op.execute(sa.delete(branches).where(branches.c.id.in_(ids)))