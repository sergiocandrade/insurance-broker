from domain.models.customer import CustomerModel
from domain.exceptions.customer import CustomerNotFoundException
from domain.repositories.customer import CustomerRepository


class CustomerService:
    def __init__(self, customer_repository: CustomerRepository) -> None:
        self.customer_repository = customer_repository

    def get_customer_by_id(self, customer_id: str) -> CustomerModel:
        customer = self.customer_repository.get_customer_by_id(customer_id=customer_id)
        if customer is None:
            raise CustomerNotFoundException()
        return customer

    def belongs_to_broker(self, customer_id: str, broker_id: str) -> bool:
        return self.customer_repository.belongs_to_broker(customer_id=customer_id, broker_id=broker_id)

    def list_by_broker(self, broker_id: str, offset: int, limit: int) -> tuple[list[CustomerModel], int]:
        return self.customer_repository.list_by_broker(broker_id=broker_id, offset=offset, limit=limit)

    def list_by_brokers(self, broker_ids: list[str], offset: int, limit: int) -> tuple[list[CustomerModel], int]:
        return self.customer_repository.list_by_brokers(broker_ids=broker_ids, offset=offset, limit=limit)