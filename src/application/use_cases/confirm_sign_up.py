from domain.services.authentication import AuthenticationEngine
from domain.services.user import UserService


class ConfirmSignUpUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine, user_service: UserService) -> None:
        self.authentication_engine = authentication_engine
        self.user_service = user_service

    def execute(self, email: str, code: str) -> None:
        self.authentication_engine.confirm_sign_up(username=email, code=code)
        self.user_service.mark_email_confirmed(email=email)