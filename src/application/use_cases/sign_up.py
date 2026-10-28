from dataclasses import replace

from domain.exceptions.broker import BrokerAlreadyActiveException
from domain.services.authentication import AuthenticationEngine, SignUpResult
from domain.services.broker import BrokerService
from domain.services.user import UserService
from domain.models.broker import BrokerStatus


class SignUpUseCase:
    def __init__(
        self,
        authentication_engine: AuthenticationEngine,
        user_service: UserService,
        broker_service: BrokerService,
    ) -> None:
        self.authentication_engine = authentication_engine
        self.user_service = user_service
        self.broker_service = broker_service

    def execute(self, email: str, password: str) -> SignUpResult:

        user = self.user_service.fetch_pending_user_by_email(email=email)
        
        result = self.authentication_engine.sign_up(
            username=email, email=email, password=password,
        )

        self.user_service.activate_user(user=user, external_id=result.user_id)


        for broker in self.broker_service.list_brokers_for_user(user_id=user.id):
                try:
                    self.broker_service.activate(broker, user_id=user.id)
                except BrokerAlreadyActiveException:
                    pass
                
        return replace(result, user_confirmed=True)  # Removed delivery fields