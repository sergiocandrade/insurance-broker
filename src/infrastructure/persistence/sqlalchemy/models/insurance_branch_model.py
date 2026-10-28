from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.sqlalchemy.models.user_model import Base


class InsuranceBranchModel(Base):
    __tablename__ = "insurance_branches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    category_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "insurance_categories.id",
            name="fk_insurance_branches_category_id_insurance_categories",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.current_timestamp(),
    )