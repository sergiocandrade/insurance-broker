from abc import ABC, abstractmethod

from domain.models.user import UserModel


class UserRepository(ABC):
    @abstractmethod
    def get_by_external_id(self, external_id: str) -> UserModel | None:
        raise NotImplementedError

    @abstractmethod
    def add(self, user: UserModel) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_email_confirmed(self, email: str) -> None:
        raise NotImplementedError