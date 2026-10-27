import base64
import hashlib
import hmac
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from domain.exceptions.authentication import AuthenticationError
from domain.services.authentication import (
    AuthenticationChallenge,
    AuthenticationEngine,
    AuthenticationResult,
    AuthenticationTokens,
)


class CognitoAuthenticationEngine(AuthenticationEngine):
    def __init__(self, region: str, client_id: str, client_secret: str) -> None:
        self.region = region
        self.client_id = client_id
        self.client_secret = client_secret

    def _secret_hash(self, username: str) -> str:
        digest = hmac.new(
            self.client_secret.encode("utf-8"),
            (username + self.client_id).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("ascii")

    def sign_in(self, username: str, password: str) -> AuthenticationResult:
        auth_parameters = {
            "USERNAME": username,
            "PASSWORD": password,
            "SECRET_HASH": self._secret_hash(username),
        }

        try:
            client = boto3.client("cognito-idp", region_name=self.region)
            result = client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters=auth_parameters,
            )
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"NotAuthorizedException", "UserNotFoundException"}:
                raise AuthenticationError("invalid_credentials", "Invalid username or password") from None
            if code in {"UserNotConfirmedException", "PasswordResetRequiredException"}:
                raise AuthenticationError(
                    "account_action_required", "Account verification or password reset required",
                ) from None
            if code in {"TooManyRequestsException", "LimitExceededException"}:
                raise AuthenticationError("throttled", "Too many sign-in attempts") from None
            raise AuthenticationError("service_error", f"Authentication service error {error}") from None
        except BotoCoreError:
            raise AuthenticationError("service_unavailable", "Authentication service unavailable") from None

        return self._authentication_result(result)

    def complete_new_password(
        self,
        username: str,
        new_password: str,
        session: str,
        required_attributes: dict[str, str],
    ) -> AuthenticationResult:
        challenge_responses = {
            "USERNAME": username,
            "NEW_PASSWORD": new_password,
            "SECRET_HASH": self._secret_hash(username),
        }
        challenge_responses.update({
            f"userAttributes.{name}": value
            for name, value in required_attributes.items()
        })

        try:
            client = boto3.client("cognito-idp", region_name=self.region)
            result = client.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName="NEW_PASSWORD_REQUIRED",
                Session=session,
                ChallengeResponses=challenge_responses,
            )
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"NotAuthorizedException", "UserNotFoundException"}:
                raise AuthenticationError(
                    "invalid_credentials", "Invalid or expired authentication session",
                ) from None
            if code in {"InvalidPasswordException", "PasswordHistoryPolicyViolationException"}:
                raise AuthenticationError("invalid_password", "Password does not meet the password policy") from None
            if code == "InvalidParameterException":
                raise AuthenticationError("invalid_challenge", "Invalid challenge response or required attributes") from None
            if code in {"TooManyRequestsException", "LimitExceededException"}:
                raise AuthenticationError("throttled", "Too many authentication attempts") from None
            raise AuthenticationError("service_error", "Authentication service error") from None
        except BotoCoreError:
            raise AuthenticationError("service_unavailable", "Authentication service unavailable") from None

        return self._authentication_result(result)

    @staticmethod
    def _authentication_result(result: dict[str, Any]) -> AuthenticationResult:
        if "AuthenticationResult" in result:
            tokens = result["AuthenticationResult"]
            return AuthenticationTokens(
                access_token=tokens["AccessToken"],
                id_token=tokens["IdToken"],
                refresh_token=tokens.get("RefreshToken"),
                token_type=tokens["TokenType"],
                expires_in=tokens["ExpiresIn"],
            )

        return AuthenticationChallenge(
            challenge_name=result["ChallengeName"],
            challenge_parameters=result.get("ChallengeParameters", {}),
            session=result["Session"],
        )