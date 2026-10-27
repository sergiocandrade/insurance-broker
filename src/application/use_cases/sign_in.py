from domain.services.authentication import AuthenticationEngine, AuthenticationResult


class SignInUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine) -> None:
        self.authentication_engine = authentication_engine

    def execute(self, username: str, password: str) -> AuthenticationResult:
        return self.authentication_engine.sign_in(username=username, password=password)