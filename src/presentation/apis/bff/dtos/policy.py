from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from domain.models.customer import CustomerType


class PolicyCustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    customer_type: CustomerType
    phone: str
    email: str
    broker_id: str
    created_at: datetime


class InsuranceCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime


class InsurerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime


class InsuranceBranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
    insurance_category: InsuranceCategoryResponse


class InsuranceProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    product_code: str
    created_at: datetime
    insurance_branch: InsuranceBranchResponse


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    customer: PolicyCustomerResponse
    amount: Decimal
    insurance_product: InsuranceProductResponse
    policy_number: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime
    insurer: InsurerResponse | None


class PaginatedPoliciesResponse(BaseModel):
    items: list[PolicyResponse]
    total: int
    page: int
    page_size: int