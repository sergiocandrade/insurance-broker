from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class UserStatus(StrEnum):
    REGISTERED = "REGISTERED"
    EMAIL_CONFIRMED = "EMAIL_CONFIRMED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class UserModel:
    id: str
    email: str
    external_id: str
    status: UserStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))