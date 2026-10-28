from datetime import date, datetime, UTC
from decimal import Decimal
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from application.use_cases.list_policies import ListPoliciesUseCase
from domain.exceptions.broker import BrokerNotFoundException
from domain.models.policy import PolicyModel
from presentation.apis.bff.main import app


class PoliciesApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_returns_paginated_policies_with_optional_filters(self) -> None:
        use_case = Mock(spec=ListPoliciesUseCase)
        use_case.execute.return_value = (
            [PolicyModel(
                id="policy-id", customer_id="customer-id", amount=Decimal("125.50"),
                insurance_product_id="product-id", policy_number="POL-001",
                start_date=date(2026, 1, 1), end_date=date(2027, 1, 1),
                status="ACTIVE", created_at=datetime(2026, 10, 28, tzinfo=UTC),
            )],
            7,
        )
        with app.state.container.list_policies_use_case.override(use_case):
            response = self.client.get(
                "/policies?broker_id=broker-id&customer_id=customer-id&page=2&page_size=5",
                headers={"Authorization": "Bearer token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 7)
        self.assertEqual(response.json()["page"], 2)
        self.assertEqual(response.json()["page_size"], 5)
        self.assertEqual(response.json()["items"][0]["policy_number"], "POL-001")
        use_case.execute.assert_called_once_with(
            access_token="token", page=2, page_size=5,
            customer_id="customer-id", broker_id="broker-id",
        )

    def test_requires_authentication_and_valid_pagination(self) -> None:
        self.assertEqual(self.client.get("/policies").status_code, 401)
        use_case = Mock(spec=ListPoliciesUseCase)
        with app.state.container.list_policies_use_case.override(use_case):
            response = self.client.get(
                "/policies?page=0", headers={"Authorization": "Bearer token"},
            )
        self.assertEqual(response.status_code, 422)
        use_case.execute.assert_not_called()

    def test_denies_access_to_another_broker(self) -> None:
        use_case = Mock(spec=ListPoliciesUseCase)
        use_case.execute.side_effect = BrokerNotFoundException()
        with app.state.container.list_policies_use_case.override(use_case):
            response = self.client.get(
                "/policies?broker_id=other-broker",
                headers={"Authorization": "Bearer token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Access to this broker is denied"})