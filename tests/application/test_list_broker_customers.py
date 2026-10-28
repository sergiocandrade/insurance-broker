from datetime import UTC, datetime
import unittest
from unittest.mock import Mock

from application.use_cases.list_broker_customers import ListBrokerCustomersUseCase
from domain.exceptions.broker import BrokerNotFoundException
from domain.models.broker import BrokerModel, BrokerStatus
from domain.models.customer import CustomerModel, CustomerType
from domain.models.user import UserModel, UserStatus
from domain.services.authentication import AuthenticationEngine
from domain.services.broker import BrokerService
from domain.services.customer import CustomerService
from domain.services.policy import PolicyService
from domain.services.user import UserService


class ListBrokerCustomersUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authentication = Mock(spec=AuthenticationEngine)
        self.authentication.get_authenticated_user_id.return_value = "external-user-id"
        self.broker_service = Mock(spec=BrokerService)
        self.broker_service.list_brokers_for_user.return_value = [
            BrokerModel(id="broker-id", status=BrokerStatus.ACTIVE, created_at=datetime.now(UTC)),
        ]
        self.customer_service = Mock(spec=CustomerService)
        self.customer_service.list_by_brokers.return_value = (
            [CustomerModel(
                id="customer-id", name="Customer", customer_type=CustomerType.PERSON,
                phone="+5511999999999", email="customer@example.com", broker_id="broker-id",
            )],
            1,
        )
        self.policy_service = Mock(spec=PolicyService)
        self.policy_service.list_for_customers.return_value = []
        self.user_service = Mock(spec=UserService)
        self.user_service.get_info.return_value = UserModel(
            id="local-user-id", email="user@example.com", external_id="external-user-id",
            status=UserStatus.REGISTERED,
        )
        self.use_case = ListBrokerCustomersUseCase(
            self.authentication, self.broker_service, self.customer_service,
            self.policy_service, self.user_service,
        )

    def test_lists_page_for_authenticated_broker_member(self) -> None:
        customers, total = self.use_case.execute(
            access_token="token", broker_id="broker-id", page=3, page_size=10,
        )

        self.assertEqual(len(customers), 1)
        self.assertEqual(total, 1)
        self.customer_service.list_by_brokers.assert_called_once_with(
            broker_ids=["broker-id"], offset=20, limit=10,
        )

    def test_rejects_user_who_is_not_a_broker_member(self) -> None:
        self.broker_service.list_brokers_for_user.return_value = []

        with self.assertRaises(BrokerNotFoundException):
            self.use_case.execute(access_token="token", broker_id="other-broker", page=1, page_size=20)

        self.customer_service.list_by_brokers.assert_not_called()

    def test_without_broker_filter_lists_all_accessible_brokers(self) -> None:
        self.use_case.execute(access_token="token", broker_id=None, page=1, page_size=20)

        self.customer_service.list_by_brokers.assert_called_once_with(
            broker_ids=["broker-id"], offset=0, limit=20,
        )