from domain.entities.user import User
from domain.repositories.user import UserRepository
from domain.services.authentication import AuthenticationEngine, SignUpResult


class SignUpUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine, user_repository: UserRepository) -> None:
        self.authentication_engine = authentication_engine
        self.user_repository = user_repository

    def execute(self, email: str, password: str) -> SignUpResult:
        result = self.authentication_engine.sign_up(
            username=email, email=email, password=password,
        )
        self.user_repository.add(User(id=result.user_id, email=email, external_id=result.user_id))
        return result