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
    SignUpResult,
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

    def get_authenticated_user_id(self, access_token: str) -> str:
        try:
            client = boto3.client("cognito-idp", region_name=self.region)
            result = client.get_user(AccessToken=access_token)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"NotAuthorizedException", "UserNotFoundException"}:
                raise AuthenticationError("invalid_credentials", "Invalid or expired access token") from None
            if code == "ForbiddenException":
                raise AuthenticationError("access_forbidden", "Access is not permitted") from None
            if code in {"TooManyRequestsException", "LimitExceededException"}:
                raise AuthenticationError("throttled", "Too many authentication attempts") from None
            raise AuthenticationError("service_error", "Authentication service error") from None
        except BotoCoreError:
            raise AuthenticationError("service_unavailable", "Authentication service unavailable") from None

        for attribute in result.get("UserAttributes", []):
            if attribute.get("Name") == "sub":
                user_id = attribute.get("Value")
                if isinstance(user_id, str) and user_id:
                    return user_id
        raise AuthenticationError("service_error", "Authentication service returned no user identifier")

    def sign_up(self, username: str, email: str, password: str) -> SignUpResult:
        try:
            client = boto3.client("cognito-idp", region_name=self.region)
            result = client.sign_up(
                ClientId=self.client_id,
                SecretHash=self._secret_hash(username),
                Username=username,
                Password=password,
                UserAttributes=[
                    {
                        "Name": "email", 
                        "Value": email
                },
            ],
            )

            
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code == "UsernameExistsException":
                raise AuthenticationError("user_exists", "Username is already registered") from None
            if code == "InvalidPasswordException":
                raise AuthenticationError("invalid_password", "Password does not meet the password policy") from None
            if code == "InvalidParameterException":
                raise AuthenticationError("invalid_signup_details", "Invalid sign-up details") from None
            if code in {"NotAuthorizedException", "ForbiddenException"}:
                raise AuthenticationError("signup_not_allowed", "Sign-up is not permitted") from None
            if code in {"TooManyRequestsException", "LimitExceededException"}:
                raise AuthenticationError("throttled", "Too many sign-up attempts") from None
            raise AuthenticationError("service_error", "Authentication service error") from None
        except BotoCoreError as e:
            raise AuthenticationError("service_unavailable", "Authentication service unavailable") from None

        return SignUpResult(
            user_id=result["UserSub"],
            user_confirmed=result["UserConfirmed"],
        )

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

    def request_password_reset(self, username: str) -> None:
        try:
            client = boto3.client("cognito-idp", region_name=self.region)
            client.forgot_password(
                ClientId=self.client_id,
                Username=username,
                SecretHash=self._secret_hash(username),
            )
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"UserNotFoundException", "NotAuthorizedException", "InvalidParameterException"}:
                return
            raise self._password_reset_error(error) from None
        except BotoCoreError:
            raise AuthenticationError("service_unavailable", "Authentication service unavailable") from None

    def confirm_password_reset(self, username: str, code: str, new_password: str) -> None:
        try:
            client = boto3.client("cognito-idp", region_name=self.region)
            client.confirm_forgot_password(
                ClientId=self.client_id,
                Username=username,
                ConfirmationCode=code,
                Password=new_password,
                SecretHash=self._secret_hash(username),
            )
        except ClientError as error:
            raise self._password_reset_error(error) from None
        except BotoCoreError:
            raise AuthenticationError("service_unavailable", "Authentication service unavailable") from None

    @staticmethod
    def _password_reset_error(error: ClientError) -> AuthenticationError:
        code = error.response.get("Error", {}).get("Code")
        if code in {
            "CodeMismatchException", "ExpiredCodeException", "UserNotFoundException",
            "NotAuthorizedException", "InvalidParameterException",
        }:
            return AuthenticationError("invalid_reset_code", "Invalid or expired password reset code")
        if code in {"InvalidPasswordException", "PasswordHistoryPolicyViolationException"}:
            return AuthenticationError("invalid_password", "Password does not meet the password policy")
        if code in {"TooManyRequestsException", "LimitExceededException", "TooManyFailedAttemptsException"}:
            return AuthenticationError("throttled", "Too many password reset attempts")
        return AuthenticationError("service_error", "Authentication service error")

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