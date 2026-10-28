from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.models.insurance_branch import InsuranceBranchModel


@dataclass(frozen=True)
class InsuranceProductModel:
    id: str
    branch_id: str
    name: str
    product_code: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    insurance_branch: InsuranceBranchModel | None = None