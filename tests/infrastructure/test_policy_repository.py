from datetime import date
from decimal import Decimal
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.persistence.sqlalchemy.models import (
    Base,
    BrokerModel,
    CustomerModel,
    InsuranceBranchModel,
    InsuranceCategoryModel,
    InsuranceProductModel,
    InsurerModel,
    InsurerProductModel,
    PolicyModel,
)
from infrastructure.persistence.sqlalchemy.repositories.policy_repository import SqlAlchemyPolicyRepository


class PolicyRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.add_policy_data()
        self.repository = SqlAlchemyPolicyRepository(self.sessions)

    def add_policy_data(self) -> None:
        with self.sessions.begin() as session:
            session.add_all([BrokerModel(id="broker-a"), BrokerModel(id="broker-b")])
            session.add_all([
                InsuranceCategoryModel(id="category-id", name="Category"),
                InsurerModel(id="insurer-id", name="Insurer"),
            ])
        with self.sessions.begin() as session:
            session.add_all([
                CustomerModel(
                    id="customer-a1", name="Customer A1", customer_type="PERSON",
                    phone="+551100000001", email="a1@example.com", broker_id="broker-a",
                ),
                CustomerModel(
                    id="customer-a2", name="Customer A2", customer_type="PERSON",
                    phone="+551100000002", email="a2@example.com", broker_id="broker-a",
                ),
                CustomerModel(
                    id="customer-b1", name="Customer B1", customer_type="PERSON",
                    phone="+552100000001", email="b1@example.com", broker_id="broker-b",
                ),
                InsuranceBranchModel(id="branch-id", category_id="category-id", name="Branch"),
            ])
        with self.sessions.begin() as session:
            session.add(InsuranceProductModel(
                id="product-id", branch_id="branch-id", name="Product", product_code="P-001",
            ))
        with self.sessions.begin() as session:
            session.add(InsurerProductModel(insurer_id="insurer-id", product_id="product-id"))
        with self.sessions.begin() as session:
            session.add_all([
                PolicyModel(
                    id=f"policy-{number}", customer_id=customer_id, amount=Decimal("100.00"),
                    insurance_product_id="product-id", insurer_id="insurer-id", policy_number=f"POL-{number:03}",
                    start_date=date(2026, 1, 1), end_date=date(2027, 1, 1),
                )
                for number, customer_id in ((1, "customer-a1"), (2, "customer-a1"),
                                            (3, "customer-a2"), (4, "customer-b1"))
            ])

    def test_paginates_within_broker_and_applies_customer_filter(self) -> None:
        policies, total = self.repository.list_for_brokers(
            broker_ids=["broker-a"], customer_id="customer-a1", offset=1, limit=1,
        )

        self.assertEqual(total, 2)
        self.assertEqual([policy.policy_number for policy in policies], ["POL-002"])
        self.assertEqual(policies[0].insurance_product.name, "Product")
        self.assertEqual(policies[0].insurance_product.product_code, "P-001")
        self.assertEqual(policies[0].insurance_product.insurance_branch.name, "Branch")
        self.assertEqual(
            policies[0].insurance_product.insurance_branch.insurance_category.name,
            "Category",
        )
        self.assertEqual(policies[0].insurer.id, "insurer-id")
        self.assertEqual(policies[0].insurer.name, "Insurer")

    def test_lists_across_accessible_brokers(self) -> None:
        policies, total = self.repository.list_for_brokers(
            broker_ids=["broker-a", "broker-b"], customer_id=None, offset=0, limit=10,
        )

        self.assertEqual(total, 4)
        self.assertEqual(len(policies), 4)

    def test_empty_broker_access_returns_no_policies(self) -> None:
        policies, total = self.repository.list_for_brokers(
            broker_ids=[], customer_id=None, offset=0, limit=10,
        )

        self.assertEqual(policies, [])
        self.assertEqual(total, 0)

    def test_filters_batch_query_by_customer_ids_and_accessible_brokers(self) -> None:
        policies, total = self.repository.list_for_brokers(
            broker_ids=["broker-a", "broker-b"],
            customer_id=None,
            customer_ids=["customer-a2", "customer-b1"],
            offset=0,
            limit=None,
        )

        self.assertEqual(total, 2)
        self.assertEqual(
            {policy.customer_id for policy in policies},
            {"customer-a2", "customer-b1"},
        )