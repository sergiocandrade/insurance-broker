from collections.abc import Callable
from datetime import date

from dependency_injector.wiring import Provider, inject
from fastapi import APIRouter, Depends, Query, Response

from application.use_cases.list_policies import ListPoliciesUseCase
from presentation.apis.bff.containers import Container
from presentation.apis.bff.dtos.policy import PaginatedPoliciesResponse, PolicyResponse

from .auth import get_access_token


router = APIRouter(prefix="/policies", tags=["policies"])


@inject
def get_list_policies_use_case(
    use_case_provider: Callable[[], ListPoliciesUseCase] = Depends(
        Provider[Container.list_policies_use_case],
    ),
) -> ListPoliciesUseCase:
    return use_case_provider()


@router.get("", response_model=PaginatedPoliciesResponse)
def list_policies(
    response: Response,
    customer_id: str | None = None,
    broker_id: str | None = None,
    end_date_from: date | None = None,
    end_date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    access_token: str = Depends(get_access_token),
    use_case: ListPoliciesUseCase = Depends(get_list_policies_use_case),
) -> PaginatedPoliciesResponse:
    policies, total = use_case.execute(
        access_token=access_token,
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        broker_id=broker_id,
        end_date_from=end_date_from,
        end_date_to=end_date_to,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return PaginatedPoliciesResponse(
        items=[PolicyResponse.model_validate(policy) for policy in policies],
        total=total,
        page=page,
        page_size=page_size,
    )