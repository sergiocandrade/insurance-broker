from datetime import datetime
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.exceptions.customer import CustomerNotFoundException
from domain.services.customer import CustomerService
from infrastructure.persistence.sqlalchemy.models import Base, BrokerModel, CustomerModel
from infrastructure.persistence.sqlalchemy.repositories.customer_repository import SqlAlchemyCustomerRepository


class CustomerRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.sessions.begin() as session:
            session.add_all([BrokerModel(id="broker-a"), BrokerModel(id="broker-b")])
        with self.sessions.begin() as session:
            session.add_all([
                CustomerModel(
                    id=f"customer-{index}", name=f"Customer {index}", customer_type="PERSON",
                    phone=f"+55119999999{index:02d}", email=f"customer{index}@example.com", broker_id="broker-a",
                )
                for index in range(1, 5)
            ])
            session.add(CustomerModel(
                id="other-customer", name="Other Customer", customer_type="BUSINESS",
                phone="+5521999999999", email="other@example.com", broker_id="broker-b",
            ))
        self.repository = SqlAlchemyCustomerRepository(self.sessions)

    def test_get_by_id_returns_customer(self) -> None:
        customer = CustomerService(self.repository).get_customer_by_id("customer-1")

        self.assertEqual(customer.id, "customer-1")
        self.assertEqual(customer.broker_id, "broker-a")

    def test_get_by_id_raises_not_found_for_unknown_customer(self) -> None:
        with self.assertRaises(CustomerNotFoundException):
            CustomerService(self.repository).get_customer_by_id("missing-customer")

    def test_paginates_customers_for_only_the_requested_broker(self) -> None:
        customers, total = self.repository.list_by_broker("broker-a", offset=1, limit=2)

        self.assertEqual(total, 4)
        self.assertEqual([customer.id for customer in customers], ["customer-2", "customer-3"])
        self.assertTrue(all(customer.broker_id == "broker-a" for customer in customers))

    def test_lists_customers_for_multiple_brokers(self) -> None:
        customers, total = self.repository.list_by_brokers(["broker-a", "broker-b"], offset=0, limit=20)

        self.assertEqual(total, 5)
        self.assertEqual({customer.broker_id for customer in customers}, {"broker-a", "broker-b"})

    def test_unknown_broker_has_empty_result(self) -> None:
        customers, total = self.repository.list_by_broker("missing-broker", offset=0, limit=20)

        self.assertEqual(customers, [])
        self.assertEqual(total, 0)

    def test_belongs_to_broker_checks_both_customer_and_broker(self) -> None:
        self.assertTrue(self.repository.belongs_to_broker("customer-1", "broker-a"))
        self.assertFalse(self.repository.belongs_to_broker("customer-1", "broker-b"))
        self.assertFalse(self.repository.belongs_to_broker("missing-customer", "broker-a"))