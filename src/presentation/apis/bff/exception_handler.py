from collections.abc import Iterator
from contextlib import contextmanager

from domain.exceptions.user import UserNotFoundException
from domain.exceptions.domain import DomainException, NotFoundException, ForbiddenException
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from starlette.responses import Response

from application.usecase_exception import UseCaseException
from domain.exceptions.authentication import AuthenticationError
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
    "user_exists": 409,
    "signup_not_allowed": 403,
    "invalid_challenge": 400,
    "invalid_reset_code": 400,
    "throttled": 429,
    "service_error": 502,
    "service_unavailable": 503,
}


async def intercept_exception(request: Request, error: Exception) -> Response:
    try:
        with handle_exceptions():
            raise error
    except HTTPException as translated:
        return await http_exception_handler(request, translated)


def register_exception_handlers(app: FastAPI) -> None:
    for exception_type in (
        AuthenticationError,
        DomainException,
        UseCaseException,
        PersistenceError,
        ForbiddenException,
        UserNotFoundException,
    ):
        app.add_exception_handler(exception_type, intercept_exception)


@contextmanager
def handle_exceptions() -> Iterator[None]:
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
    except NotFoundException as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except ForbiddenException as error:
        raise HTTPException(status_code=403, detail=str(error)) from None
    except PersistenceError:
        raise HTTPException(status_code=503, detail="Persistence service unavailable") from None
    except (DomainException, UseCaseException) as error:
        raise HTTPException(status_code=400, detail=str(error)) from None