"""Create waiting list table."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8f3b6c9e205'
down_revision: Union[str, None] = 'c7e2a5b8d103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('waiting_list',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=128), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=False),
    sa.Column('region', sa.String(length=128), nullable=False),
    sa.Column('insurance_categories', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )


def downgrade() -> None:
    op.drop_table('waiting_list')
