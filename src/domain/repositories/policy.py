from abc import ABC, abstractmethod
from datetime import date

from domain.models.policy import PolicyModel


class PolicyRepository(ABC):
    @abstractmethod
    def list_for_brokers(
        self,
        broker_ids: list[str],
        customer_id: str | None,
        offset: int,
        limit: int | None,
        customer_ids: list[str] | None = None,
        end_date_from: date | None = None,
        end_date_to: date | None = None,
    ) -> tuple[list[PolicyModel], int]:
        raise NotImplementedError