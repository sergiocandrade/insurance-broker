from abc import ABC, abstractmethod

from domain.models.customer import CustomerModel


class CustomerRepository(ABC):
    @abstractmethod
    def get_customer_by_id(self, customer_id: str) -> CustomerModel | None:
        raise NotImplementedError

    @abstractmethod
    def belongs_to_broker(self, customer_id: str, broker_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_by_broker(self, broker_id: str, offset: int, limit: int) -> tuple[list[CustomerModel], int]:
        raise NotImplementedError

    @abstractmethod
    def list_by_brokers(self, broker_ids: list[str], offset: int, limit: int) -> tuple[list[CustomerModel], int]:
        raise NotImplementedError