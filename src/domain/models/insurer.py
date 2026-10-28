from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class InsurerModel:
    id: str
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))