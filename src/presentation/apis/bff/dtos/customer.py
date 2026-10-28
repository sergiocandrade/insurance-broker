from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.models.customer import CustomerType


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    customer_type: CustomerType
    phone: str
    email: str
    broker_id: str
    created_at: datetime


class PaginatedCustomersResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int