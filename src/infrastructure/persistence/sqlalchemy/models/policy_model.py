from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, ForeignKeyConstraint, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.sqlalchemy.models.user_model import Base


class PolicyModel(Base):
    __tablename__ = "policies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["insurer_id", "insurance_product_id"],
            ["insurer_products.insurer_id", "insurer_products.product_id"],
            name="fk_policies_insurer_product_insurer_products",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("customers.id", name="fk_policies_customer_id_customers", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING", server_default="PENDING",
    )
    policy_number: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    insurance_product_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "insurance_products.id",
            name="fk_policies_insurance_product_id_insurance_products",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    insurer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.current_timestamp(),
    )