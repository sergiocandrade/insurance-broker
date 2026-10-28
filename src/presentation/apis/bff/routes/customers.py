from collections.abc import Callable

from dependency_injector.wiring import Provider, inject
from fastapi import APIRouter, Depends, Query, Response

from application.use_cases.list_broker_customers import ListBrokerCustomersUseCase
from presentation.apis.bff.containers import Container
from presentation.apis.bff.dtos.customer import CustomerResponse, PaginatedCustomersResponse

from .auth import get_access_token


router = APIRouter(prefix="/customers", tags=["customers"])


@inject
def get_list_broker_customers_use_case(
    use_case_provider: Callable[[], ListBrokerCustomersUseCase] = Depends(
        Provider[Container.list_broker_customers_use_case],
    ),
) -> ListBrokerCustomersUseCase:
    return use_case_provider()


@router.get("", response_model=PaginatedCustomersResponse)
def list_customers(
    response: Response,
    broker_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    access_token: str = Depends(get_access_token),
    use_case: ListBrokerCustomersUseCase = Depends(get_list_broker_customers_use_case),
) -> PaginatedCustomersResponse:
    customers, total = use_case.execute(
        access_token=access_token,
        broker_id=broker_id,
        page=page,
        page_size=page_size,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return PaginatedCustomersResponse(
        items=[CustomerResponse.model_validate(customer) for customer in customers],
        total=total,
        page=page,
        page_size=page_size,
    )