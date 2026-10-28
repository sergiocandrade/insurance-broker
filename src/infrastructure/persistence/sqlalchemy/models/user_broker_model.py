from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.sqlalchemy.models.broker_model import BrokerModel
from infrastructure.persistence.sqlalchemy.models.user_model import Base


class UserBrokerModel(Base):
    __tablename__ = "users_brokers"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", name="fk_user_broker_user_id_users", ondelete="RESTRICT"),
        primary_key=True,
    )
    broker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(BrokerModel.id, name="fk_user_broker_broker_id_brokers", ondelete="RESTRICT"),
        primary_key=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.current_timestamp(),
    )