from abc import ABC, abstractmethod

from domain.models.broker import BrokerModel


class BrokerRepository(ABC):
    @abstractmethod
    def list_brokers_for_user(self, user_id: str) -> list[BrokerModel]:
        raise NotImplementedError

    @abstractmethod
    def activate(self, broker_id: str, user_id: str) -> BrokerModel:
        raise NotImplementedError