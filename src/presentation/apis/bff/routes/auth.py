from collections.abc import Callable

from dependency_injector.wiring import Provider, inject
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import ValidationError

from application.use_cases.complete_new_password import CompleteNewPasswordUseCase
from application.use_cases.confirm_sign_up import ConfirmSignUpUseCase
from application.use_cases.reset_password import ConfirmPasswordResetUseCase, RequestPasswordResetUseCase
from application.use_cases.sign_in import SignInUseCase
from application.use_cases.sign_up import SignUpUseCase
from presentation.apis.bff.containers import Container
from domain.exceptions.authentication import AuthenticationError
from domain.services.authentication import AuthenticationResult, AuthenticationTokens
from presentation.apis.bff.dtos.auth import (
    ConfirmPasswordResetRequest,
    ConfirmSignUpRequest,
    ConfirmSignUpResponse,
    NewPasswordRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    SignInChallenge,
    SignInRequest,
    SignInTokens,
    SignUpRequest,
    SignUpResponse,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@inject
def get_sign_in_use_case(
    use_case_provider: Callable[[], SignInUseCase] = Depends(Provider[Container.sign_in_use_case]),
) -> SignInUseCase:
    try:
        return use_case_provider()
    except ValidationError:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from None


@inject
def get_sign_up_use_case(
    use_case_provider: Callable[[], SignUpUseCase] = Depends(Provider[Container.sign_up_use_case]),
) -> SignUpUseCase:
    try:
        return use_case_provider()
    except ValidationError:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from None


@inject
def get_confirm_sign_up_use_case(
    use_case_provider: Callable[[], ConfirmSignUpUseCase] = Depends(Provider[Container.confirm_sign_up_use_case]),
) -> ConfirmSignUpUseCase:
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


@inject
def get_request_password_reset_use_case(
    use_case_provider: Callable[[], RequestPasswordResetUseCase] = Depends(
        Provider[Container.request_password_reset_use_case],
    ),
) -> RequestPasswordResetUseCase:
    try:
        return use_case_provider()
    except ValidationError:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from None


@inject
def get_confirm_password_reset_use_case(
    use_case_provider: Callable[[], ConfirmPasswordResetUseCase] = Depends(
        Provider[Container.confirm_password_reset_use_case],
    ),
) -> ConfirmPasswordResetUseCase:
    try:
        return use_case_provider()
    except ValidationError:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from None


def authentication_http_error(error: AuthenticationError) -> HTTPException:
    status_codes = {
        "invalid_credentials": 401,
        "account_action_required": 403,
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
    return HTTPException(status_code=status_codes[error.reason], detail=str(error))


@router.post("/sign-up", response_model=SignUpResponse, status_code=201)
def sign_up(
    credentials: SignUpRequest,
    response: Response,
    use_case: SignUpUseCase = Depends(get_sign_up_use_case),
) -> SignUpResponse:
    try:
        result = use_case.execute(
            email=str(credentials.email),
            password=credentials.password.get_secret_value(),
        )
    except AuthenticationError as error:
        raise authentication_http_error(error) from None

    response.headers["Cache-Control"] = "no-store"
    return SignUpResponse(
        user_id=result.user_id,
        user_confirmed=result.user_confirmed,
        confirmation_destination=result.confirmation_destination,
        confirmation_delivery_medium=result.confirmation_delivery_medium,
    )


@router.post("/sign-up/confirm", response_model=ConfirmSignUpResponse)
def confirm_sign_up(
    credentials: ConfirmSignUpRequest,
    response: Response,
    use_case: ConfirmSignUpUseCase = Depends(get_confirm_sign_up_use_case),
) -> ConfirmSignUpResponse:
    try:
        use_case.execute(email=str(credentials.email), code=credentials.code.get_secret_value())
    except AuthenticationError as error:
        raise authentication_http_error(error) from None

    response.headers["Cache-Control"] = "no-store"
    return ConfirmSignUpResponse(message="Sign-up confirmed successfully. You can now sign in.")


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


@router.post("/reset-password", response_model=PasswordResetResponse, status_code=202)
def request_password_reset(
    credentials: PasswordResetRequest,
    response: Response,
    use_case: RequestPasswordResetUseCase = Depends(get_request_password_reset_use_case),
) -> PasswordResetResponse:
    try:
        use_case.execute(username=credentials.username)
    except AuthenticationError as error:
        raise authentication_http_error(error) from None

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
    try:
        use_case.execute(
            username=credentials.username,
            code=credentials.code.get_secret_value(),
            new_password=credentials.new_password.get_secret_value(),
        )
    except AuthenticationError as error:
        raise authentication_http_error(error) from None

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