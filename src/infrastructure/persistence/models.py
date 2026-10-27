from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from domain.models.user import UserStatus

class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    external_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, length=32, validate_strings=True),
        nullable=False,
        default=UserStatus.REGISTERED,
        server_default=UserStatus.REGISTERED.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)