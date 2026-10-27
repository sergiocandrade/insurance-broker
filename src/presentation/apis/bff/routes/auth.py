from collections.abc import Callable

from dependency_injector.wiring import Provider, inject
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, SecretStr, ValidationError

from application.use_cases.complete_new_password import CompleteNewPasswordUseCase
from application.use_cases.sign_in import SignInUseCase
from presentation.apis.bff.containers import Container
from domain.exceptions.authentication import AuthenticationError
from domain.services.authentication import AuthenticationResult, AuthenticationTokens


router = APIRouter(prefix="/auth", tags=["auth"])


class SignInRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=256)


class NewPasswordRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=1, max_length=256)
    session: SecretStr = Field(min_length=1, max_length=2048)
    required_attributes: dict[str, str] = Field(default_factory=dict)


class SignInTokens(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str | None = None
    token_type: str
    expires_in: int


class SignInChallenge(BaseModel):
    challenge_name: str
    challenge_parameters: dict[str, str]
    session: str


@inject
def get_sign_in_use_case(
    use_case_provider: Callable[[], SignInUseCase] = Depends(Provider[Container.sign_in_use_case]),
) -> SignInUseCase:
    try:
        return use_case_provider()
    except ValidationError:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from None


@inject
def get_complete_new_password_use_case(
    use_case_provider: Callable[[], CompleteNewPasswordUseCase] = Depends(
        Provider[Container.complete_new_password_use_case],
    ),
) -> CompleteNewPasswordUseCase:
    try:
        return use_case_provider()
    except ValidationError:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from None


def authentication_http_error(error: AuthenticationError) -> HTTPException:
    status_codes = {
        "invalid_credentials": 401,
        "account_action_required": 403,
        "invalid_password": 400,
        "invalid_challenge": 400,
        "throttled": 429,
        "service_error": 502,
        "service_unavailable": 503,
    }
    return HTTPException(status_code=status_codes[error.reason], detail=str(error))


@router.post("/sign-in", response_model=SignInTokens | SignInChallenge)
def sign_in(
    credentials: SignInRequest,
    response: Response,
    use_case: SignInUseCase = Depends(get_sign_in_use_case),
) -> SignInTokens | SignInChallenge:
    
    try:
        result = use_case.execute(
            username=credentials.username,
            password=credentials.password.get_secret_value(),
        )
    except AuthenticationError as error:
        raise authentication_http_error(error) from None

    return authentication_response(result, response)


@router.post("/new-password", response_model=SignInTokens | SignInChallenge)
def complete_new_password(
    credentials: NewPasswordRequest,
    response: Response,
    use_case: CompleteNewPasswordUseCase = Depends(get_complete_new_password_use_case),
) -> SignInTokens | SignInChallenge:
    try:
        result = use_case.execute(
            username=credentials.username,
            new_password=credentials.new_password.get_secret_value(),
            session=credentials.session.get_secret_value(),
            required_attributes=credentials.required_attributes,
        )
    except AuthenticationError as error:
        raise authentication_http_error(error) from None

    return authentication_response(result, response)


def authentication_response(
    result: AuthenticationResult, response: Response,
) -> SignInTokens | SignInChallenge:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    if isinstance(result, AuthenticationTokens):
        return SignInTokens(
            access_token=result.access_token,
            id_token=result.id_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        )

    return SignInChallenge(
        challenge_name=result.challenge_name,
        challenge_parameters=result.challenge_parameters,
        session=result.session,
    )