from collections.abc import Callable
from typing import Literal

from dependency_injector.wiring import Provider, inject
from fastapi import APIRouter, Depends, Query, Response

from application.use_cases.get_customer_details import GetCustomerDetailsUseCase
from application.use_cases.list_broker_customers import ListBrokerCustomersUseCase
from presentation.apis.bff.containers import Container
from presentation.apis.bff.dtos.customer import (
    CustomerDetailsResponse,
    CustomerResponse,
    PaginatedCustomerDetailsResponse,
    PaginatedCustomerSummaryResponse,
    PaginatedCustomersResponse,
    CustomerSummaryResponse,
)
from presentation.apis.bff.dtos.policy import PolicyResponse

from .auth import get_access_token


router = APIRouter(prefix="/customers", tags=["customers"])


@inject
def get_list_broker_customers_use_case(
    use_case_provider: Callable[[], ListBrokerCustomersUseCase] = Depends(
        Provider[Container.list_broker_customers_use_case],
    ),
) -> ListBrokerCustomersUseCase:
    return use_case_provider()


@inject
def get_customer_details_use_case(
    use_case_provider: Callable[[], GetCustomerDetailsUseCase] = Depends(
        Provider[Container.get_customer_details_use_case],
    ),
) -> GetCustomerDetailsUseCase:
    return use_case_provider()


@router.get("/{customer_id}", response_model=CustomerDetailsResponse)
def get_customer_details(
    customer_id: str,
    response: Response,
    access_token: str = Depends(get_access_token),
    use_case: GetCustomerDetailsUseCase = Depends(get_customer_details_use_case),
) -> CustomerDetailsResponse:
    customer, policies = use_case.execute(access_token=access_token, customer_id=customer_id)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return CustomerDetailsResponse(
        **CustomerResponse.model_validate(customer).model_dump(),
        policies=[PolicyResponse.model_validate(policy) for policy in policies],
    )


@router.get(
    "",
    response_model=PaginatedCustomerSummaryResponse | PaginatedCustomerDetailsResponse,
)
def list_customers(
    response: Response,
    broker_id: str | None = Query(default=None),
    view: Literal["summary", "detailed"] = Query(default="summary"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    access_token: str = Depends(get_access_token),
    use_case: ListBrokerCustomersUseCase = Depends(get_list_broker_customers_use_case),
) -> PaginatedCustomerSummaryResponse | PaginatedCustomerDetailsResponse:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if view == "detailed":
        customers, policies, total = use_case.execute_with_policies(
            access_token=access_token,
            broker_id=broker_id,
            page=page,
            page_size=page_size,
        )
        policies_by_customer_id = {customer.id: [] for customer in customers}
        for policy in policies:
            policies_by_customer_id[policy.customer_id].append(
                PolicyResponse.model_validate(policy),
            )
        return PaginatedCustomerDetailsResponse(
            items=[
                CustomerDetailsResponse(
                    **CustomerResponse.model_validate(customer).model_dump(),
                    policies=policies_by_customer_id[customer.id],
                )
                for customer in customers
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    customers, total = use_case.execute(
        access_token=access_token,
        broker_id=broker_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedCustomerSummaryResponse(
        items=[CustomerSummaryResponse.model_validate(customer) for customer in customers],
        total=total,
        page=page,
        page_size=page_size,
    )