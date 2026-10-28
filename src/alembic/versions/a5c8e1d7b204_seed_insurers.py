"""Seed insurer records."""
from typing import Sequence, Union
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa


revision: str = 'a5c8e1d7b204'
down_revision: Union[str, None] = '606b762bcbb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INSURER_NAMES = (
    'Porto Seguro', 'Bradesco Seguros', 'SulAmérica', 'Tokio Marine Seguradora', 'Allianz Seguros',
    'MAPFRE Seguros', 'Zurich Seguros', 'HDI Seguros', 'Sompo Seguros', 'Chubb Seguros',
    'AXA Seguros', 'Icatu Seguros', 'MAG Seguros', 'Prudential do Brasil', 'Seguros Unimed',
    'Pottencial Seguradora', 'Junto Seguros', 'Sancor Seguros', 'Akad Seguros', 'Too Seguros',
)


def insurer_ids() -> list[str]:
    return [str(uuid5(NAMESPACE_URL, f'insurance-broker:insurer:{name}')) for name in INSURER_NAMES]


def upgrade() -> None:
    insurers = sa.table(
        'insurers',
        sa.column('id', sa.String(length=36)),
        sa.column('name', sa.String(length=255)),
    )
    op.bulk_insert(insurers, [
        {'id': insurer_id, 'name': name}
        for insurer_id, name in zip(insurer_ids(), INSURER_NAMES, strict=True)
    ])


def downgrade() -> None:
    insurers = sa.table('insurers', sa.column('id', sa.String(length=36)))
    op.execute(sa.delete(insurers).where(insurers.c.id.in_(insurer_ids())))