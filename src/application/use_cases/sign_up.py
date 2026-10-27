from domain.services.authentication import AuthenticationEngine, SignUpResult


class SignUpUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine) -> None:
        self.authentication_engine = authentication_engine

    def execute(self, email: str, password: str) -> SignUpResult:
        return self.authentication_engine.sign_up(
            username=email, email=email, password=password,
        )