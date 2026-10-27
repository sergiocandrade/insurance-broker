from abc import ABC, abstractmethod

from domain.entities.user import User


class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> None:
        raise NotImplementedError