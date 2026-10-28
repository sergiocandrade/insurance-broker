from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class UserStatus(StrEnum):
    PENDING = "PENDING"
    REGISTERED = "REGISTERED"


@dataclass()
class UserModel:
    id: str
    email: str
    external_id: str | None
    status: UserStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    activated_at: datetime | None = None