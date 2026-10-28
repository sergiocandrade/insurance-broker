from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    amount: Decimal
    insurance_product_id: str
    policy_number: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime


class PaginatedPoliciesResponse(BaseModel):
    items: list[PolicyResponse]
    total: int
    page: int
    page_size: int