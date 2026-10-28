from domain.exceptions.broker import BrokerNotFoundException
from domain.models.customer import CustomerModel
from domain.services.authentication import AuthenticationEngine
from domain.services.broker import BrokerService
from domain.services.customer import CustomerService
from domain.services.user import UserService


class ListBrokerCustomersUseCase:
    def __init__(
        self,
        authentication_engine: AuthenticationEngine,
        broker_service: BrokerService,
        customer_service: CustomerService,
        user_service: UserService,
    ) -> None:
        self.authentication_engine = authentication_engine
        self.broker_service = broker_service
        self.customer_service = customer_service
        self.user_service = user_service

    def execute(
        self,
        access_token: str,
        broker_id: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[CustomerModel], int]:
        external_id = self.authentication_engine.get_authenticated_user_id(access_token=access_token)
        user = self.user_service.get_info(external_id=external_id)
        broker_ids = [broker.id for broker in self.broker_service.list_brokers_for_user(user_id=user.id)]
        if broker_id is not None:
            if broker_id not in broker_ids:
                raise BrokerNotFoundException()
            broker_ids = [broker_id]

        return self.customer_service.list_by_brokers(
            broker_ids=broker_ids,
            offset=(page - 1) * page_size,
            limit=page_size,
        )