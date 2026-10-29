from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.sqlalchemy.models.user_model import Base


class WaitingListModel(Base):
    __tablename__ = "waiting_list"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    insurance_categories: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        server_default=func.current_timestamp(),
    )
