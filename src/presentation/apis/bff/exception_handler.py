from collections.abc import Iterator
from contextlib import contextmanager

from domain.exceptions.user import UserAlreadyRegistredException, UserNotFoundException, UserNotPreRegistredException
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from starlette.responses import Response
from pydantic import ValidationError

from application.usecase_exception import UseCaseException
from domain.exceptions.authentication import AuthenticationError
from domain.exceptions.broker import BrokerAccessDeniedError, BrokerNotFoundError
from domain.exceptions.domain import DomainException, NotFoundException
from infrastructure.persistence.exceptions import PersistenceError


AUTHENTICATION_STATUS_CODES = {
    "invalid_credentials": 401,
    "access_forbidden": 403,
    "user_profile_not_found": 404,
    "account_action_required": 403,
    "registration_not_provisioned": 403,
    "registration_not_pending": 403,
    "invalid_password": 400,
    "invalid_signup_details": 400,
    "invalid_signup_confirmation": 400,
    "user_exists": 409,
    "signup_not_allowed": 403,
    "invalid_challenge": 400,
    "invalid_reset_code": 400,
    "email_conflict": 409,
    "throttled": 429,
    "service_error": 502,
    "service_unavailable": 503,
}


PERSISTENCE_ERROR_DETAILS = {
    "get_current_user": "User profile service unavailable",
    "sign_up": "Registration succeeded in Cognito, but the user profile could not be saved. Contact support before retrying.",
    "confirm_sign_up": "Email confirmed in Cognito, but registration status could not be saved. Contact support before retrying.",
}


async def intercept_exception(request: Request, error: Exception) -> Response:
    route = request.scope.get("route")
    route_name = getattr(route, "name", "")
    configuration_detail = "Service is not configured"
    if "auth" in getattr(route, "tags", []):
        configuration_detail = (
            "User profile service is not configured"
            if route_name == "get_current_user" else "Authentication is not configured"
        )

    try:
        with handle_exceptions(
            persistence_detail=PERSISTENCE_ERROR_DETAILS.get(route_name, "Persistence service unavailable"),
            configuration_detail=configuration_detail,
        ):
            raise error
    except HTTPException as translated:
        return await http_exception_handler(request, translated)


def register_exception_handlers(app: FastAPI) -> None:
    for exception_type in (
        AuthenticationError,
        DomainException,
        UseCaseException,
        PersistenceError,
        BrokerNotFoundError,
        BrokerAccessDeniedError,
        UserNotPreRegistredException,
        UserAlreadyRegistredException,
        UserNotFoundException,
        ValidationError,
    ):
        app.add_exception_handler(exception_type, intercept_exception)


@contextmanager
def handle_exceptions(
    *,
    persistence_detail: str = "Persistence service unavailable",
    configuration_detail: str | None = None,
) -> Iterator[None]:

    try:
        yield
    except AuthenticationError as error:
        status_code = AUTHENTICATION_STATUS_CODES.get(error.reason, 500)
        if status_code < 500:
            detail = str(error)
        else:
            detail = {
                502: "Authentication service error",
                503: "Authentication service unavailable",
            }.get(status_code, "Authentication failed")
        headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
        raise HTTPException(status_code=status_code, detail=detail, headers=headers) from None
    except (NotFoundException, BrokerNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except (BrokerAccessDeniedError, UserNotPreRegistredException, UserAlreadyRegistredException) as error:
        raise HTTPException(status_code=403, detail=str(error)) from None
    except PersistenceError:
        raise HTTPException(status_code=503, detail=persistence_detail) from None
    except (DomainException, UseCaseException) as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    except ValidationError:
        if configuration_detail is None:
            raise

        raise HTTPException(status_code=500, detail=configuration_detail) from None