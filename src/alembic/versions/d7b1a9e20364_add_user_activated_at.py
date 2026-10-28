"""Add user activation timestamp."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd7b1a9e20364'
down_revision: Union[str, None] = 'c9bf9b1eb451'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('activated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'activated_at')