from domain.exceptions.broker import BrokerNotFoundException
from domain.models.customer import CustomerModel
from domain.models.policy import PolicyModel
from domain.services.authentication import AuthenticationEngine
from domain.services.broker import BrokerService
from domain.services.customer import CustomerService
from domain.services.policy import PolicyService
from domain.services.user import UserService


class GetCustomerDetailsUseCase:
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

    def execute(self, access_token: str, customer_id: str) -> tuple[CustomerModel, list[PolicyModel]]:
        external_id = self.authentication_engine.get_authenticated_user_id(access_token=access_token)
        user = self.user_service.get_info(external_id=external_id)
        customer = self.customer_service.get_customer_by_id(customer_id=customer_id)
        broker_ids = {
            broker.id for broker in self.broker_service.list_brokers_for_user(user_id=user.id)
        }
        if customer.broker_id not in broker_ids:
            raise BrokerNotFoundException()

        policies, _ = self.policy_service.list_for_brokers(
            broker_ids=[customer.broker_id],
            customer_id=customer.id,
            offset=0,
            limit=None,
        )
        return customer, policies