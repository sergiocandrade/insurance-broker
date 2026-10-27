"""Track user registration progress."""

from alembic import op
import sqlalchemy as sa


revision = "b70d8c2f910a"
down_revision = "174038895e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "status",
            sa.Enum("REGISTERED", "EMAIL_CONFIRMED", "COMPLETED", native_enum=False, length=32),
            nullable=False,
            server_default="REGISTERED",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("status")