from domain.models.user import UserModel
from domain.services.authentication import AuthenticationEngine
from domain.services.user import UserService


class GetCurrentUserUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine, user_service: UserService) -> None:
        self.authentication_engine = authentication_engine
        self.user_service = user_service

    def execute(self, access_token: str) -> UserModel:
        external_id = self.authentication_engine.get_authenticated_user_id(access_token=access_token)
        return self.user_service.get_info(external_id=external_id)