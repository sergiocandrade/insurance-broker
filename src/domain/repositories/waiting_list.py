from abc import ABC, abstractmethod

from domain.models.waiting_list import WaitingListEntryModel


class WaitingListRepository(ABC):
    @abstractmethod
    def exists_by_email(self, email: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def add(self, entry: WaitingListEntryModel) -> None:
        raise NotImplementedError
