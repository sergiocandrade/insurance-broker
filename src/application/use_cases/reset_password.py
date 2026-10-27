from domain.services.authentication import AuthenticationEngine


class RequestPasswordResetUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine) -> None:
        self.authentication_engine = authentication_engine

    def execute(self, username: str) -> None:
        self.authentication_engine.request_password_reset(username=username)


class ConfirmPasswordResetUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine) -> None:
        self.authentication_engine = authentication_engine

    def execute(self, username: str, code: str, new_password: str) -> None:
        self.authentication_engine.confirm_password_reset(
            username=username, code=code, new_password=new_password,
        )