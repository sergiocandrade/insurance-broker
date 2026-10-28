"""Add broker activation timestamp."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4a8c21f6d93'
down_revision: Union[str, None] = 'd7b1a9e20364'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('brokers', sa.Column('activated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('brokers', 'activated_at')