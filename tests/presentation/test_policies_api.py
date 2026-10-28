from datetime import date, datetime, UTC
from decimal import Decimal
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from application.use_cases.list_policies import ListPoliciesUseCase
from domain.exceptions.broker import BrokerNotFoundException
from domain.models.customer import CustomerModel, CustomerType
from domain.models.insurance_branch import InsuranceBranchModel
from domain.models.insurance_category import InsuranceCategoryModel
from domain.models.insurance_product import InsuranceProductModel
from domain.models.insurer import InsurerModel
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
                insurance_product_id="product-id", insurer_id="insurer-id", policy_number="POL-001",
                start_date=date(2026, 1, 1), end_date=date(2027, 1, 1),
                status="ACTIVE", created_at=datetime(2026, 10, 28, tzinfo=UTC),
                customer=CustomerModel(
                    id="customer-id", name="Customer Example", customer_type=CustomerType.PERSON,
                    phone="+5511999999999", email="customer@example.com", broker_id="broker-id",
                    created_at=datetime(2026, 10, 28, tzinfo=UTC),
                ),
                insurer=InsurerModel(
                    id="insurer-id", name="Example Insurer", created_at=datetime(2026, 10, 28, tzinfo=UTC),
                ),
                insurance_product=InsuranceProductModel(
                    id="product-id", branch_id="branch-id", name="Health Cover",
                    product_code="HLT-001", created_at=datetime(2026, 10, 28, tzinfo=UTC),
                    insurance_branch=InsuranceBranchModel(
                        id="branch-id", category_id="category-id", name="Individual",
                        created_at=datetime(2026, 10, 28, tzinfo=UTC),
                        insurance_category=InsuranceCategoryModel(
                            id="category-id", name="Health",
                            created_at=datetime(2026, 10, 28, tzinfo=UTC),
                        ),
                    ),
                ),
            )],
            7,
        )
        with app.state.container.list_policies_use_case.override(use_case):
            response = self.client.get(
                "/policies?broker_id=broker-id&customer_id=customer-id&end_date_from=2027-01-01&end_date_to=2027-12-31&page=2&page_size=5",
                headers={"Authorization": "Bearer token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 7)
        self.assertEqual(response.json()["page"], 2)
        self.assertEqual(response.json()["page_size"], 5)
        self.assertEqual(response.json()["items"][0]["policy_number"], "POL-001")
        self.assertEqual(response.json()["items"][0]["customer"]["id"], "customer-id")
        self.assertEqual(response.json()["items"][0]["customer"]["name"], "Customer Example")
        self.assertEqual(response.json()["items"][0]["customer"]["email"], "customer@example.com")
        self.assertEqual(response.json()["items"][0]["insurer"]["id"], "insurer-id")
        self.assertEqual(response.json()["items"][0]["insurer"]["name"], "Example Insurer")
        self.assertEqual(response.json()["items"][0]["insurance_product"]["id"], "product-id")
        self.assertEqual(response.json()["items"][0]["insurance_product"]["name"], "Health Cover")
        self.assertEqual(
            response.json()["items"][0]["insurance_product"]["insurance_branch"]["name"],
            "Individual",
        )
        self.assertEqual(
            response.json()["items"][0]["insurance_product"]["insurance_branch"]["insurance_category"]["name"],
            "Health",
        )
        self.assertNotIn("branch_id", response.json()["items"][0]["insurance_product"])
        self.assertNotIn("category_id", response.json()["items"][0]["insurance_product"]["insurance_branch"])
        self.assertNotIn("insurance_product_id", response.json()["items"][0])
        self.assertNotIn("insurer_id", response.json()["items"][0])
        self.assertNotIn("insurers", response.json()["items"][0]["insurance_product"])
        use_case.execute.assert_called_once_with(
            access_token="token", page=2, page_size=5,
            customer_id="customer-id", broker_id="broker-id",
            end_date_from=date(2027, 1, 1), end_date_to=date(2027, 12, 31),
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

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Broker not found"})