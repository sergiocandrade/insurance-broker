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


class AuthenticationEngine(ABC):
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