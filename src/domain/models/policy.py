from dataclasses import dataclass
from datetime import date
from datetime import UTC, datetime
from decimal import Decimal
from dataclasses import field

from domain.models.insurance_product import InsuranceProductModel
from domain.models.insurer import InsurerModel


@dataclass(frozen=True)
class PolicyModel:
    id: str
    customer_id: str
    amount: Decimal
    insurance_product_id: str
    policy_number: str
    start_date: date
    end_date: date
    insurer_id: str | None = None
    status: str = "PENDING"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    insurance_product: InsuranceProductModel | None = None
    insurer: InsurerModel | None = None