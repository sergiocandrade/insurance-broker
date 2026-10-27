from domain.services.authentication import AuthenticationEngine, SignUpResult
from domain.services.user import UserService


class SignUpUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine, user_service: UserService) -> None:
        self.authentication_engine = authentication_engine
        self.user_service = user_service

    def execute(self, email: str, password: str) -> SignUpResult:
        result = self.authentication_engine.sign_up(
            username=email, email=email, password=password,
        )
        self.user_service.add(email=email, external_id=result.user_id)
        return result