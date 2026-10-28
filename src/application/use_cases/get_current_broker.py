from domain.models.broker import BrokerModel
from domain.services.authentication import AuthenticationEngine
from domain.services.broker import BrokerService


class GetCurrentBrokerUseCase:
    def __init__(self, authentication_engine: AuthenticationEngine, broker_service: BrokerService) -> None:
        self.authentication_engine = authentication_engine
        self.broker_service = broker_service

    def execute(self, access_token: str) -> BrokerModel:
        external_id = self.authentication_engine.get_authenticated_user_id(access_token=access_token)
        return self.broker_service.get_info(external_id=external_id)