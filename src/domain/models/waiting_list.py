from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class WaitingListEntryModel:
    id: str
    email: str
    phone: str
    region: str
    insurance_categories: tuple[str, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
