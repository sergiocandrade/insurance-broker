from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class User:
    id: str
    email: str
    external_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))