from domain.services.authentication import AuthenticationEngine


class ConfirmSignUpUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine) -> None:
        self.authentication_engine = authentication_engine

    def execute(self, email: str, code: str) -> None:
        self.authentication_engine.confirm_sign_up(username=email, code=code)