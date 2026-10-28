"""Seed insurance category records."""
from typing import Sequence, Union
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa


revision: str = 'b6d9f2a4c107'
down_revision: Union[str, None] = 'a5c8e1d7b204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORY_NAMES = (
    'Automóvel e Mobilidade', 'Residencial e Patrimonial', 'Pessoas', 'Saúde e Benefícios',
    'Financeiros e Crédito', 'Transporte e Logística', 'Responsabilidade Civil',
    'Grandes Riscos e Especializados', 'Agrícola e Rural', 'Garantias', 'Viagem',
    'Eletrônicos e Equipamentos', 'Vida e Previdência', 'Odontológico', 'Riscos Cibernéticos',
)


def category_ids() -> list[str]:
    return [str(uuid5(NAMESPACE_URL, f'insurance-broker:category:{name}')) for name in CATEGORY_NAMES]


def upgrade() -> None:
    categories = sa.table(
        'insurance_categories',
        sa.column('id', sa.String(length=36)),
        sa.column('name', sa.String(length=255)),
    )
    op.bulk_insert(categories, [
        {'id': category_id, 'name': name}
        for category_id, name in zip(category_ids(), CATEGORY_NAMES, strict=True)
    ])


def downgrade() -> None:
    categories = sa.table('insurance_categories', sa.column('id', sa.String(length=36)))
    op.execute(sa.delete(categories).where(categories.c.id.in_(category_ids())))