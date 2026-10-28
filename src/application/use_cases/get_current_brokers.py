from domain.models.broker import BrokerModel
from domain.services.authentication import AuthenticationEngine
from domain.services.broker import BrokerService
from domain.services.user import UserService


class GetCurrentBrokersUseCase:
    def __init__(
        self,
        authentication_engine: AuthenticationEngine,
        broker_service: BrokerService,
        user_service: UserService,
    ) -> None:
        self.authentication_engine = authentication_engine
        self.broker_service = broker_service
        self.user_service = user_service

    def execute(self, access_token: str) -> list[BrokerModel]:
        external_id = self.authentication_engine.get_authenticated_user_id(access_token=access_token)
        user = self.user_service.get_info(external_id=external_id)
        return self.broker_service.list_brokers_for_user(user_id=user.id)