from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.models.customer import CustomerType
from presentation.apis.bff.dtos.policy import PolicyResponse


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


class CustomerDetailsResponse(CustomerResponse):
    policies: list[PolicyResponse]


class CustomerSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    customer_type: CustomerType


class PaginatedCustomerSummaryResponse(BaseModel):
    items: list[CustomerSummaryResponse]
    total: int
    page: int
    page_size: int


class PaginatedCustomerDetailsResponse(BaseModel):
    items: list[CustomerDetailsResponse]
    total: int
    page: int
    page_size: int