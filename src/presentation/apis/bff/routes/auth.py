from collections.abc import Callable

from dependency_injector.wiring import Provider, inject
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from application.use_cases.complete_new_password import CompleteNewPasswordUseCase
from application.use_cases.get_current_user import GetCurrentUserUseCase
from application.use_cases.get_current_brokers import GetCurrentBrokersUseCase
from application.use_cases.reset_password import ConfirmPasswordResetUseCase, RequestPasswordResetUseCase
from application.use_cases.sign_in import SignInUseCase
from application.use_cases.sign_up import SignUpUseCase
from presentation.apis.bff.containers import Container
from domain.services.authentication import AuthenticationResult, AuthenticationTokens
from presentation.apis.bff.dtos.auth import (
    ConfirmPasswordResetRequest,
    CurrentUserResponse,
    NewPasswordRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    SignInChallenge,
    SignInRequest,
    SignInTokens,
    SignUpRequest,
    SignUpResponse,
)
from presentation.apis.bff.dtos.broker import BrokerResponse


router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="A Cognito access token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@inject
def get_current_user_use_case(
    use_case_provider: Callable[[], GetCurrentUserUseCase] = Depends(Provider[Container.get_current_user_use_case]),
) -> GetCurrentUserUseCase:
    return use_case_provider()


@inject
def get_current_brokers_use_case(
    use_case_provider: Callable[[], GetCurrentBrokersUseCase] = Depends(
        Provider[Container.get_current_brokers_use_case],
    ),
) -> GetCurrentBrokersUseCase:
    return use_case_provider()


@inject
def get_sign_in_use_case(
    use_case_provider: Callable[[], SignInUseCase] = Depends(Provider[Container.sign_in_use_case]),
) -> SignInUseCase:
    return use_case_provider()


@inject
def get_sign_up_use_case(
    use_case_provider: Callable[[], SignUpUseCase] = Depends(Provider[Container.sign_up_use_case]),
) -> SignUpUseCase:
    return use_case_provider()


@inject
def get_complete_new_password_use_case(
    use_case_provider: Callable[[], CompleteNewPasswordUseCase] = Depends(
        Provider[Container.complete_new_password_use_case],
    ),
) -> CompleteNewPasswordUseCase:
    return use_case_provider()


@inject
def get_request_password_reset_use_case(
    use_case_provider: Callable[[], RequestPasswordResetUseCase] = Depends(
        Provider[Container.request_password_reset_use_case],
    ),
) -> RequestPasswordResetUseCase:
    return use_case_provider()


@inject
def get_confirm_password_reset_use_case(
    use_case_provider: Callable[[], ConfirmPasswordResetUseCase] = Depends(
        Provider[Container.confirm_password_reset_use_case],
    ),
) -> ConfirmPasswordResetUseCase:
    return use_case_provider()


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(
    response: Response,
    access_token: str = Depends(get_access_token),
    use_case: GetCurrentUserUseCase = Depends(get_current_user_use_case),
) -> CurrentUserResponse:
    user = use_case.execute(access_token=access_token)

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return CurrentUserResponse.model_validate(user)


@router.get("/me/brokers", response_model=list[BrokerResponse])
def get_current_brokers(
    response: Response,
    access_token: str = Depends(get_access_token),
    use_case: GetCurrentBrokersUseCase = Depends(get_current_brokers_use_case),
) -> list[BrokerResponse]:
    brokers = use_case.execute(access_token=access_token)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return [BrokerResponse.model_validate(broker) for broker in brokers]


@router.post("/sign-up", response_model=SignUpResponse, status_code=201)
def sign_up(
    credentials: SignUpRequest,
    response: Response,
    use_case: SignUpUseCase = Depends(get_sign_up_use_case),
) -> SignUpResponse:
    result = use_case.execute(
        email=str(credentials.email),
        password=credentials.password.get_secret_value(),
    )

    response.headers["Cache-Control"] = "no-store"
    return SignUpResponse(
        user_id=result.user_id,
        user_confirmed=result.user_confirmed,
    )


@router.post("/sign-in", response_model=SignInTokens | SignInChallenge)
def sign_in(
    credentials: SignInRequest,
    response: Response,
    use_case: SignInUseCase = Depends(get_sign_in_use_case),
) -> SignInTokens | SignInChallenge:
    result = use_case.execute(
        username=credentials.username,
        password=credentials.password.get_secret_value(),
    )

    return authentication_response(result, response)


@router.post("/new-password", response_model=SignInTokens | SignInChallenge)
def complete_new_password(
    credentials: NewPasswordRequest,
    response: Response,
    use_case: CompleteNewPasswordUseCase = Depends(get_complete_new_password_use_case),
) -> SignInTokens | SignInChallenge:
    result = use_case.execute(
        username=credentials.username,
        new_password=credentials.new_password.get_secret_value(),
        session=credentials.session.get_secret_value(),
        required_attributes=credentials.required_attributes,
    )

    return authentication_response(result, response)


@router.post("/reset-password", response_model=PasswordResetResponse, status_code=202)
def request_password_reset(
    credentials: PasswordResetRequest,
    response: Response,
    use_case: RequestPasswordResetUseCase = Depends(get_request_password_reset_use_case),
) -> PasswordResetResponse:
    use_case.execute(username=credentials.username)

    response.headers["Cache-Control"] = "no-store"
    return PasswordResetResponse(
        message="If the account is eligible, a password reset code has been sent.",
    )


@router.post("/reset-password/confirm", response_model=PasswordResetResponse)
def confirm_password_reset(
    credentials: ConfirmPasswordResetRequest,
    response: Response,
    use_case: ConfirmPasswordResetUseCase = Depends(get_confirm_password_reset_use_case),
) -> PasswordResetResponse:
    use_case.execute(
        username=credentials.username,
        code=credentials.code.get_secret_value(),
        new_password=credentials.new_password.get_secret_value(),
    )

    response.headers["Cache-Control"] = "no-store"
    return PasswordResetResponse(message="Password reset successfully. Sign in with your new password.")


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