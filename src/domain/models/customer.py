from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class CustomerType(StrEnum):
    BUSINESS = "BUSINESS"
    PERSON = "PERSON"


@dataclass(frozen=True)
class CustomerModel:
    id: str
    name: str
    customer_type: CustomerType
    phone: str
    email: str
    broker_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))