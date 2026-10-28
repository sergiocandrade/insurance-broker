from domain.exceptions.broker import BrokerNotFoundException
from domain.exceptions.customer import CustomerNotFoundException
from domain.models.policy import PolicyModel
from domain.services.authentication import AuthenticationEngine
from domain.services.broker import BrokerService
from domain.services.customer import CustomerService
from domain.services.policy import PolicyService
from domain.services.user import UserService


class ListPoliciesUseCase:
    def __init__(
        self,
        authentication_engine: AuthenticationEngine,
        broker_service: BrokerService,
        customer_service: CustomerService,
        policy_service: PolicyService,
        user_service: UserService,
    ) -> None:
        self.authentication_engine = authentication_engine
        self.broker_service = broker_service
        self.customer_service = customer_service
        self.policy_service = policy_service
        self.user_service = user_service

    def execute(
        self,
        access_token: str,
        page: int,
        page_size: int,
        customer_id: str | None = None,
        broker_id: str | None = None,
    ) -> tuple[list[PolicyModel], int]:
        external_id = self.authentication_engine.get_authenticated_user_id(access_token=access_token)
        user = self.user_service.get_info(external_id=external_id)
        accessible_broker_ids = [
            broker.id for broker in self.broker_service.list_brokers_for_user(user_id=user.id)
        ]

        if broker_id is not None:
            if broker_id not in accessible_broker_ids:
                raise BrokerNotFoundException()
            accessible_broker_ids = [broker_id]
                
        if customer_id is not None:
            customer = self.customer_service.get_customer_by_id(customer_id=customer_id)
            
            if not customer.broker_id in accessible_broker_ids:
                raise CustomerNotFoundException()

            if broker_id is not None:
                if customer.broker_id != broker_id:
                    raise BrokerNotFoundException()


        return self.policy_service.list_for_brokers(
            broker_ids=accessible_broker_ids,
            customer_id=customer_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )