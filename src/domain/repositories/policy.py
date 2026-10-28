from abc import ABC, abstractmethod

from domain.models.policy import PolicyModel


class PolicyRepository(ABC):
    @abstractmethod
    def list_for_brokers(
        self,
        broker_ids: list[str],
        customer_id: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[PolicyModel], int]:
        raise NotImplementedError