from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, repr=False)
class AuthenticationTokens:
    access_token: str
    id_token: str
    refresh_token: str | None
    token_type: str
    expires_in: int


@dataclass(frozen=True, repr=False)
class AuthenticationChallenge:
    challenge_name: str
    challenge_parameters: dict[str, str]
    session: str


AuthenticationResult = AuthenticationTokens | AuthenticationChallenge


@dataclass(frozen=True)
class SignUpResult:
    user_id: str
    user_confirmed: bool
    confirmation_destination: str | None = None
    confirmation_delivery_medium: str | None = None


class AuthenticationEngine(ABC):
    @abstractmethod
    def get_authenticated_user_id(self, access_token: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def sign_up(self, username: str, email: str, password: str) -> SignUpResult:
        raise NotImplementedError

    @abstractmethod
    def confirm_sign_up(self, username: str, code: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def sign_in(self, username: str, password: str) -> AuthenticationResult:
        raise NotImplementedError

    @abstractmethod
    def complete_new_password(
        self,
        username: str,
        new_password: str,
        session: str,
        required_attributes: dict[str, str],
    ) -> AuthenticationResult:
        raise NotImplementedError

    @abstractmethod
    def request_password_reset(self, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def confirm_password_reset(self, username: str, code: str, new_password: str) -> None:
        raise NotImplementedError