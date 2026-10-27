from domain.services.authentication import AuthenticationEngine, AuthenticationResult


class CompleteNewPasswordUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine) -> None:
        self.authentication_engine = authentication_engine

    def execute(
        self,
        username: str,
        new_password: str,
        session: str,
        required_attributes: dict[str, str],
    ) -> AuthenticationResult:
        return self.authentication_engine.complete_new_password(
            username=username,
            new_password=new_password,
            session=session,
            required_attributes=required_attributes,
        )