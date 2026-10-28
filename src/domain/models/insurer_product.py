from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class InsurerProductModel:
    insurer_id: str
    product_id: str
    created_at: datetime