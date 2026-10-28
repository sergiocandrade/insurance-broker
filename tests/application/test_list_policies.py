from datetime import UTC, date, datetime
from decimal import Decimal
import unittest
from unittest.mock import Mock

from application.use_cases.list_policies import ListPoliciesUseCase
from domain.exceptions.broker import BrokerNotFoundException
from domain.models.broker import BrokerModel, BrokerStatus
from domain.models.policy import PolicyModel
from domain.models.user import UserModel, UserStatus
from domain.services.authentication import AuthenticationEngine
from domain.services.broker import BrokerService
from domain.services.customer import CustomerService
from domain.services.policy import PolicyService
from domain.services.user import UserService


class ListPoliciesUseCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authentication = Mock(spec=AuthenticationEngine)
        self.authentication.get_authenticated_user_id.return_value = "external-user"
        self.broker_service = Mock(spec=BrokerService)
        self.broker_service.list_brokers_for_user.return_value = [
            BrokerModel(id="broker-a", status=BrokerStatus.ACTIVE, created_at=datetime.now(UTC)),
            BrokerModel(id="broker-b", status=BrokerStatus.ACTIVE, created_at=datetime.now(UTC)),
        ]
        self.policy_service = Mock(spec=PolicyService)
        self.policy_service.list_for_brokers.return_value = ([], 0)
        self.customer_service = Mock(spec=CustomerService)
        self.customer_service.belongs_to_broker.return_value = True
        self.user_service = Mock(spec=UserService)
        self.user_service.get_info.return_value = UserModel(
            id="user-id", email="user@example.com", external_id="external-user", status=UserStatus.REGISTERED,
        )
        self.use_case = ListPoliciesUseCase(
            self.authentication, self.broker_service, self.customer_service,
            self.policy_service, self.user_service,
        )

    def test_filters_with_accessible_broker_and_customer(self) -> None:
        policy = PolicyModel(
            id="policy-id", customer_id="customer-id", amount=Decimal("125.00"),
            insurance_product_id="product-id", policy_number="POL-001",
            start_date=datetime(2026, 1, 1).date(), end_date=datetime(2027, 1, 1).date(),
        )
        self.policy_service.list_for_brokers.return_value = ([policy], 1)

        policies, total = self.use_case.execute(
            access_token="token", broker_id="broker-b", customer_id="customer-id", page=2, page_size=5,
        )

        self.assertEqual(policies, [policy])
        self.assertEqual(total, 1)
        self.policy_service.list_for_brokers.assert_called_once_with(
            broker_ids=["broker-b"], customer_id="customer-id", offset=5, limit=5,
        )
        self.customer_service.belongs_to_broker.assert_called_once_with(
            customer_id="customer-id", broker_id="broker-b",
        )

    def test_rejects_customer_that_does_not_belong_to_filtered_broker(self) -> None:
        self.customer_service.belongs_to_broker.return_value = False

        with self.assertRaises(BrokerNotFoundException):
            self.use_case.execute(
                access_token="token", broker_id="broker-a", customer_id="customer-from-broker-b",
                page=1, page_size=20,
            )

        self.policy_service.list_for_brokers.assert_not_called()

    def test_rejects_broker_outside_current_users_access(self) -> None:
        with self.assertRaises(BrokerNotFoundException):
            self.use_case.execute(access_token="token", broker_id="other-broker", page=1, page_size=20)

        self.policy_service.list_for_brokers.assert_not_called()

    def test_without_broker_filter_uses_all_accessible_brokers(self) -> None:
        self.use_case.execute(access_token="token", page=1, page_size=20)

        self.policy_service.list_for_brokers.assert_called_once_with(
            broker_ids=["broker-a", "broker-b"], customer_id=None, offset=0, limit=20,
            end_date_from=None, end_date_to=None,
        )

    def test_filters_by_end_date_range(self) -> None:
        self.use_case.execute(
            access_token="token",
            page=1,
            page_size=20,
            end_date_from=date(2027, 1, 1),
            end_date_to=date(2027, 12, 31),
        )

        self.policy_service.list_for_brokers.assert_called_once_with(
            broker_ids=["broker-a", "broker-b"],
            customer_id=None,
            offset=0,
            limit=20,
            end_date_from=date(2027, 1, 1),
            end_date_to=date(2027, 12, 31),
        )