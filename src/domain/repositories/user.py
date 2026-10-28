from abc import ABC, abstractmethod
from datetime import datetime

from domain.models.user import UserModel


class UserRepository(ABC):
    @abstractmethod
    def fetch_user_by_email(self, email: str) -> UserModel | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_external_id(self, external_id: str) -> UserModel | None:
        raise NotImplementedError 

    @abstractmethod
    def update(self, user: UserModel) -> None:
        raise NotImplementedError

    @abstractmethod
    def activate_user(
        self,
        user_id: str,
        external_id: str,
        activated_at: datetime | None = None,
    ) -> None:
        raise NotImplementedError

   