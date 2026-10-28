from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.sqlalchemy.models.user_model import Base


class InsurerProductModel(Base):
    __tablename__ = "insurer_products"

    insurer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("insurers.id", name="fk_insurer_products_insurer_id_insurers", ondelete="RESTRICT"),
        primary_key=True,
    )
    product_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("insurance_products.id", name="fk_insurer_products_product_id_insurance_products", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.current_timestamp(),
    )