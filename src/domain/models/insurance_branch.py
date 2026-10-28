from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.models.insurance_category import InsuranceCategoryModel


@dataclass(frozen=True)
class InsuranceBranchModel:
    id: str
    category_id: str
    name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    insurance_category: InsuranceCategoryModel | None = None