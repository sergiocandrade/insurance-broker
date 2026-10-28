from dataclasses import dataclass
from datetime import date
from datetime import UTC, datetime
from decimal import Decimal
from dataclasses import field


@dataclass(frozen=True)
class PolicyModel:
    id: str
    customer_id: str
    amount: Decimal
    insurance_product_id: str
    policy_number: str
    start_date: date
    end_date: date
    status: str = "PENDING"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))