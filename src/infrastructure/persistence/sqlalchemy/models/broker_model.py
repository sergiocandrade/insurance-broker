from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from domain.models.broker import BrokerStatus
from infrastructure.persistence.sqlalchemy.models.user_model import Base


class BrokerModel(Base):
    __tablename__ = "brokers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[BrokerStatus] = mapped_column(
        Enum(BrokerStatus, name="broker_status", native_enum=False, create_constraint=True, validate_strings=True),
        nullable=False,
        default=BrokerStatus.PENDING,
        server_default=BrokerStatus.PENDING.value,
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.current_timestamp(),
    )