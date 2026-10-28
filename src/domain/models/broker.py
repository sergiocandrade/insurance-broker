from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BrokerStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"


@dataclass()
class BrokerModel:
    id: str
    status: BrokerStatus
    created_at: datetime
    activated_at: datetime | None = None