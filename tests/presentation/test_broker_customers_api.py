from datetime import UTC, datetime
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from application.use_cases.list_broker_customers import ListBrokerCustomersUseCase
from domain.models.customer import CustomerModel, CustomerType
from presentation.apis.bff.main import app


class BrokerCustomersApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_returns_paginated_customers_for_broker(self) -> None:
        use_case = Mock(spec=ListBrokerCustomersUseCase)
        use_case.execute.return_value = (
            [CustomerModel(
                id="customer-id", name="Customer", customer_type=CustomerType.PERSON,
                phone="+5511999999999", email="customer@example.com", broker_id="broker-id",
                created_at=datetime(2026, 10, 28, tzinfo=UTC),
            )],
            12,
        )
        with app.state.container.list_broker_customers_use_case.override(use_case):
            response = self.client.get(
                "/brokers/broker-id/customers?page=2&page_size=5",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 12)
        self.assertEqual(response.json()["page"], 2)
        self.assertEqual(response.json()["page_size"], 5)
        self.assertEqual(response.json()["items"][0]["id"], "customer-id")
        use_case.execute.assert_called_once_with(
            access_token="test-token", broker_id="broker-id", page=2, page_size=5,
        )

    def test_requires_authentication_and_valid_pagination(self) -> None:
        response = self.client.get("/brokers/broker-id/customers")
        self.assertEqual(response.status_code, 401)

        use_case = Mock(spec=ListBrokerCustomersUseCase)
        with app.state.container.list_broker_customers_use_case.override(use_case):
            response = self.client.get(
                "/brokers/broker-id/customers?page=0",
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(response.status_code, 422)
        use_case.execute.assert_not_called()

    def test_lists_customers_with_broker_query_filter(self) -> None:
        use_case = Mock(spec=ListBrokerCustomersUseCase)
        use_case.execute.return_value = ([], 0)
        with app.state.container.list_broker_customers_use_case.override(use_case):
            response = self.client.get(
                "/customers?broker_id=broker-id&page=3&page_size=10",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": [], "total": 0, "page": 3, "page_size": 10})
        use_case.execute.assert_called_once_with(
            access_token="test-token", broker_id="broker-id", page=3, page_size=10,
        )

    def test_customer_list_broker_filter_is_optional(self) -> None:
        use_case = Mock(spec=ListBrokerCustomersUseCase)
        use_case.execute.return_value = ([], 0)
        with app.state.container.list_broker_customers_use_case.override(use_case):
            response = self.client.get("/customers", headers={"Authorization": "Bearer test-token"})

        self.assertEqual(response.status_code, 200)
        use_case.execute.assert_called_once_with(
            access_token="test-token", broker_id=None, page=1, page_size=20,
        )

    def test_customer_list_defaults_to_summary_view(self) -> None:
        use_case = Mock(spec=ListBrokerCustomersUseCase)
        use_case.execute.return_value = (
            [CustomerModel(
                id="customer-id", name="Customer", customer_type=CustomerType.PERSON,
                phone="+5511999999999", email="customer@example.com", broker_id="broker-id",
                created_at=datetime(2026, 10, 28, tzinfo=UTC),
            )],
            1,
        )
        with app.state.container.list_broker_customers_use_case.override(use_case):
            response = self.client.get("/customers", headers={"Authorization": "Bearer test-token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0], {
            "id": "customer-id", "name": "Customer", "customer_type": "PERSON",
        })

    def test_customer_list_detailed_view_includes_policies(self) -> None:
        use_case = Mock(spec=ListBrokerCustomersUseCase)
        customer = CustomerModel(
            id="customer-id", name="Customer", customer_type=CustomerType.PERSON,
            phone="+5511999999999", email="customer@example.com", broker_id="broker-id",
            created_at=datetime(2026, 10, 28, tzinfo=UTC),
        )
        use_case.execute_with_policies.return_value = ([customer], [], 1)
        with app.state.container.list_broker_customers_use_case.override(use_case):
            response = self.client.get(
                "/customers?view=detailed",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["id"], "customer-id")
        self.assertEqual(item["phone"], "+5511999999999")
        self.assertEqual(item["policies"], [])
        use_case.execute_with_policies.assert_called_once_with(
            access_token="test-token", broker_id=None, page=1, page_size=20,
        )