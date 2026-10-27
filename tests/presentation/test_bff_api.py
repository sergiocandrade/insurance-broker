import base64
import hashlib
import hmac
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi.testclient import TestClient
from pydantic import ValidationError

from application.use_cases import sign_in as sign_in_module
from application.use_cases.complete_new_password import CompleteNewPasswordUseCase
from application.use_cases.confirm_sign_up import ConfirmSignUpUseCase
from application.use_cases.sign_up import SignUpUseCase
from application.use_cases.reset_password import ConfirmPasswordResetUseCase, RequestPasswordResetUseCase
from domain.exceptions.authentication import AuthenticationError
from domain.services.authentication import AuthenticationChallenge, AuthenticationEngine, SignUpResult
from infrastructure.authentication import cognito as cognito_module
from infrastructure.config.settings import Settings
from presentation.apis.bff.main import app


class SettingsTests(unittest.TestCase):
    def test_settings_load_environment_and_hide_secret(self) -> None:
        with patch.dict("os.environ", {
            "AWS_REGION": "us-east-1",
            "AWS_DEFAULT_REGION": "us-west-2",
            "COGNITO_CLIENT_ID": "test-client",
            "COGNITO_CLIENT_SECRET": "private-client-secret",
        }, clear=True):
            settings = Settings()

        self.assertEqual(settings.AWS_REGION, "us-east-1")
        self.assertEqual(settings.COGNITO_CLIENT_ID, "test-client")
        self.assertEqual(settings.COGNITO_CLIENT_SECRET.get_secret_value(), "private-client-secret")
        self.assertNotIn("private-client-secret", repr(settings))

    def test_empty_region_uses_default_region(self) -> None:
        with patch.dict("os.environ", {
            "AWS_REGION": "", "AWS_DEFAULT_REGION": "us-west-2",
            "COGNITO_CLIENT_ID": "test-client",
            "COGNITO_CLIENT_SECRET": "test-secret",
        }, clear=True):
            settings = Settings()

        self.assertEqual(settings.AWS_REGION, "us-west-2")

    def test_all_settings_are_required_and_nonempty(self) -> None:
        environment = {
            "AWS_REGION": "us-east-1",
            "COGNITO_CLIENT_ID": "test-client",
            "COGNITO_CLIENT_SECRET": "test-secret",
        }
        for field in environment:
            for value in (None, ""):
                with self.subTest(field=field, value=value):
                    invalid_environment = environment.copy()
                    if value is None:
                        del invalid_environment[field]
                    else:
                        invalid_environment[field] = value
                    with patch.dict("os.environ", invalid_environment, clear=True):
                        with self.assertRaises(ValidationError) as error:
                            Settings()
                    self.assertEqual(error.exception.errors()[0]["loc"], (field,))

    def test_settings_fields_are_uppercase(self) -> None:
        self.assertEqual(set(Settings.model_fields), {
            "AWS_REGION", "COGNITO_CLIENT_ID", "COGNITO_CLIENT_SECRET",
        })
        with patch.dict("os.environ", {
            "aws_region": "us-east-1",
            "cognito_client_id": "test-client",
            "cognito_client_secret": "test-secret",
        }, clear=True):
            with self.assertRaises(ValidationError):
                Settings()


class SignInUseCaseTests(unittest.TestCase):
    def test_confirm_sign_up_use_case_uses_email_as_username(self) -> None:
        engine = Mock(spec=AuthenticationEngine)
        use_case = ConfirmSignUpUseCase(authentication_engine=engine)

        use_case.execute(email="user@example.com", code="123456")

        engine.confirm_sign_up.assert_called_once_with(username="user@example.com", code="123456")

    def test_sign_up_use_case_uses_email_as_username(self) -> None:
        engine = Mock(spec=AuthenticationEngine)
        engine.sign_up.return_value = SignUpResult(user_id="user-id", user_confirmed=False)
        use_case = SignUpUseCase(authentication_engine=engine)

        result = use_case.execute(email="user@example.com", password="test-password")

        self.assertIs(result, engine.sign_up.return_value)
        engine.sign_up.assert_called_once_with(
            username="user@example.com", email="user@example.com", password="test-password",
        )

    def test_use_case_delegates_to_domain_engine(self) -> None:
        engine = Mock(spec=AuthenticationEngine)
        engine.sign_in.return_value = AuthenticationChallenge(
            challenge_name="SMS_MFA", challenge_parameters={}, session="test-session",
        )
        use_case = sign_in_module.SignInUseCase(authentication_engine=engine)

        result = use_case.execute(username="test-user", password="test-password")

        self.assertIs(result, engine.sign_in.return_value)
        engine.sign_in.assert_called_once_with(username="test-user", password="test-password")

    def test_use_case_propagates_domain_error(self) -> None:
        engine = Mock(spec=AuthenticationEngine)
        error = AuthenticationError("invalid_credentials", "Invalid username or password")
        engine.sign_in.side_effect = error
        use_case = sign_in_module.SignInUseCase(authentication_engine=engine)

        with self.assertRaises(AuthenticationError) as raised:
            use_case.execute(username="test-user", password="test-password")

        self.assertIs(raised.exception, error)


class BffApiTests(unittest.TestCase):
    def test_health(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class SignInTests(unittest.TestCase):
    def setUp(self) -> None:
        app.state.container.reset_singletons()
        self.addCleanup(app.state.container.reset_singletons)
        environment = patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "COGNITO_CLIENT_ID": "test-client",
                "COGNITO_CLIENT_SECRET": "test-secret",
            },
            clear=True,
        )
        environment.start()
        self.addCleanup(environment.stop)
        client_patch = patch.object(cognito_module.boto3, "client")
        self.client_factory = client_patch.start()
        self.addCleanup(client_patch.stop)
        self.cognito = self.client_factory.return_value
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.credentials = {"username": "test-user", "password": "test-password"}
        self.new_password_credentials = {
            "username": "test-user",
            "new_password": "new-test-password",
            "session": "challenge-session",
        }

    def test_confirm_sign_up_sends_email_code_and_secret_hash(self) -> None:
        response = self.client.post("/auth/sign-up/confirm", json={
            "email": "user@example.com", "code": "123456",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "message": "Sign-up confirmed successfully. You can now sign in.",
        })
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        expected_hash = base64.b64encode(hmac.new(
            b"test-secret", b"user@example.comtest-client", hashlib.sha256,
        ).digest()).decode("ascii")
        self.cognito.confirm_sign_up.assert_called_once_with(
            ClientId="test-client", Username="user@example.com", ConfirmationCode="123456",
            SecretHash=expected_hash, ForceAliasCreation=False,
        )

    def test_confirm_sign_up_errors_are_sanitized(self) -> None:
        for code, expected_status in (
            ("CodeMismatchException", 400), ("ExpiredCodeException", 400),
            ("UserNotFoundException", 400), ("NotAuthorizedException", 400),
            ("InvalidParameterException", 400), ("AliasExistsException", 409),
            ("ForbiddenException", 403), ("TooManyRequestsException", 429),
            ("LimitExceededException", 429), ("TooManyFailedAttemptsException", 429),
            ("InternalErrorException", 502),
        ):
            with self.subTest(code=code):
                self.cognito.confirm_sign_up.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "private AWS details"}}, "ConfirmSignUp",
                )
                response = self.client.post("/auth/sign-up/confirm", json={
                    "email": "user@example.com", "code": "123456",
                })
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("private AWS details", response.text)

    def test_confirm_sign_up_validates_email_and_code(self) -> None:
        for body in (
            {}, {"email": "user@example.com"}, {"code": "123456"},
            {"email": "not-an-email", "code": "123456"},
            {"email": "user@example.com", "code": ""},
        ):
            with self.subTest(body=body):
                response = self.client.post("/auth/sign-up/confirm", json=body)
                self.assertEqual(response.status_code, 422)
        self.client_factory.assert_not_called()

    def test_confirm_sign_up_service_unavailable(self) -> None:
        self.cognito.confirm_sign_up.side_effect = EndpointConnectionError(endpoint_url="https://cognito.example.com")
        response = self.client.post("/auth/sign-up/confirm", json={
            "email": "user@example.com", "code": "123456",
        })
        self.assertEqual(response.status_code, 503)

    def test_confirm_sign_up_missing_configuration(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post("/auth/sign-up/confirm", json={
                "email": "user@example.com", "code": "123456",
            })
        self.assertEqual(response.status_code, 503)
        self.client_factory.assert_not_called()

    def test_confirm_sign_up_use_case_can_be_overridden(self) -> None:
        use_case = Mock(spec=ConfirmSignUpUseCase)
        with app.state.container.confirm_sign_up_use_case.override(use_case):
            response = self.client.post("/auth/sign-up/confirm", json={
                "email": "user@example.com", "code": "123456",
            })
        self.assertEqual(response.status_code, 200)
        use_case.execute.assert_called_once_with(email="user@example.com", code="123456")
        self.client_factory.assert_not_called()

    def test_sign_up_creates_user_and_returns_confirmation_details(self) -> None:
        self.cognito.sign_up.return_value = {
            "UserSub": "user-id", "UserConfirmed": False,
            "CodeDeliveryDetails": {"Destination": "u***@example.com", "DeliveryMedium": "EMAIL"},
        }
        response = self.client.post("/auth/sign-up", json={
            "email": "user@example.com", "password": "test-password",
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {
            "user_id": "user-id", "user_confirmed": False,
            "confirmation_destination": "u***@example.com", "confirmation_delivery_medium": "EMAIL",
        })
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        expected_hash = base64.b64encode(hmac.new(
            b"test-secret", b"user@example.comtest-client", hashlib.sha256,
        ).digest()).decode("ascii")
        self.cognito.sign_up.assert_called_once_with(
            ClientId="test-client", Username="user@example.com", Password="test-password",
            SecretHash=expected_hash, UserAttributes=[{"Name": "email", "Value": "user@example.com"}],
        )
        self.assertNotIn("test-password", response.text)

    def test_sign_up_supports_auto_confirmed_users(self) -> None:
        self.cognito.sign_up.return_value = {"UserSub": "user-id", "UserConfirmed": True}
        response = self.client.post("/auth/sign-up", json={
            "email": "user@example.com", "password": "test-password",
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["user_confirmed"])
        self.assertIsNone(response.json()["confirmation_destination"])

    def test_sign_up_errors_are_sanitized(self) -> None:
        for code, expected_status in (
            ("UsernameExistsException", 409), ("InvalidPasswordException", 400),
            ("InvalidParameterException", 400), ("NotAuthorizedException", 403),
            ("ForbiddenException", 403), ("TooManyRequestsException", 429),
            ("LimitExceededException", 429), ("InternalErrorException", 502),
        ):
            with self.subTest(code=code):
                self.cognito.sign_up.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "private AWS details"}}, "SignUp",
                )
                response = self.client.post("/auth/sign-up", json={
                    "email": "user@example.com", "password": "test-password",
                })
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("private AWS details", response.text)

    def test_sign_up_validates_required_fields(self) -> None:
        valid = {"email": "user@example.com", "password": "test-password"}
        for field in valid:
            with self.subTest(field=field):
                response = self.client.post("/auth/sign-up", json={**valid, field: ""})
                self.assertEqual(response.status_code, 422)
        response = self.client.post("/auth/sign-up", json={**valid, "email": "not-an-email"})
        self.assertEqual(response.status_code, 422)
        self.client_factory.assert_not_called()

    def test_sign_up_service_unavailable(self) -> None:
        self.cognito.sign_up.side_effect = EndpointConnectionError(endpoint_url="https://cognito.example.com")
        response = self.client.post("/auth/sign-up", json={
            "email": "user@example.com", "password": "test-password",
        })
        self.assertEqual(response.status_code, 503)

    def test_sign_up_missing_configuration(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post("/auth/sign-up", json={
                "email": "user@example.com", "password": "test-password",
            })
        self.assertEqual(response.status_code, 503)
        self.client_factory.assert_not_called()

    def test_sign_up_use_case_can_be_overridden(self) -> None:
        use_case = Mock(spec=SignUpUseCase)
        use_case.execute.return_value = SignUpResult(user_id="user-id", user_confirmed=False)
        with app.state.container.sign_up_use_case.override(use_case):
            response = self.client.post("/auth/sign-up", json={
                "username": "test-user", "email": "user@example.com", "password": "test-password",
            })
        self.assertEqual(response.status_code, 201)
        use_case.execute.assert_called_once_with(
            email="user@example.com", password="test-password",
        )
        self.client_factory.assert_not_called()

    def test_email_verification_endpoints_are_removed(self) -> None:
        for path in ("/auth/verify-email", "/auth/verify-email/request"):
            with self.subTest(path=path):
                response = self.client.post(path, json={"code": "123456"})
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(path, app.openapi()["paths"])
        self.client_factory.assert_not_called()

    def test_new_password_returns_tokens_and_sends_challenge(self) -> None:
        self.cognito.respond_to_auth_challenge.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access-token", "IdToken": "id-token",
                "RefreshToken": "refresh-token", "TokenType": "Bearer", "ExpiresIn": 3600,
            },
        }
        response = self.client.post("/auth/new-password", json={
            **self.new_password_credentials,
            "required_attributes": {"name": "Test User"},
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "access-token")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        expected_hash = base64.b64encode(hmac.new(
            b"test-secret", b"test-usertest-client", hashlib.sha256,
        ).digest()).decode("ascii")
        self.cognito.respond_to_auth_challenge.assert_called_once_with(
            ClientId="test-client", ChallengeName="NEW_PASSWORD_REQUIRED",
            Session="challenge-session",
            ChallengeResponses={
                "USERNAME": "test-user", "NEW_PASSWORD": "new-test-password",
                "SECRET_HASH": expected_hash, "userAttributes.name": "Test User",
            },
        )

    def test_new_password_returns_next_challenge(self) -> None:
        self.cognito.respond_to_auth_challenge.return_value = {
            "ChallengeName": "SMS_MFA", "Session": "next-session",
        }
        response = self.client.post("/auth/new-password", json=self.new_password_credentials)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "challenge_name": "SMS_MFA", "challenge_parameters": {}, "session": "next-session",
        })

    def test_new_password_errors_are_sanitized(self) -> None:
        for code, expected_status in (
            ("NotAuthorizedException", 401),
            ("InvalidPasswordException", 400),
            ("PasswordHistoryPolicyViolationException", 400),
            ("InvalidParameterException", 400),
            ("TooManyRequestsException", 429),
            ("InternalErrorException", 502),
        ):
            with self.subTest(code=code):
                self.cognito.respond_to_auth_challenge.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "private AWS details"}},
                    "RespondToAuthChallenge",
                )
                response = self.client.post("/auth/new-password", json=self.new_password_credentials)
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("private AWS details", response.text)

    def test_new_password_requires_session_and_password(self) -> None:
        for field in ("session", "new_password"):
            with self.subTest(field=field):
                response = self.client.post("/auth/new-password", json={
                    **self.new_password_credentials, field: "",
                })
                self.assertEqual(response.status_code, 422)
        self.client_factory.assert_not_called()

    def test_new_password_use_case_can_be_overridden(self) -> None:
        use_case = Mock(spec=CompleteNewPasswordUseCase)
        use_case.execute.return_value = AuthenticationChallenge(
            challenge_name="SMS_MFA", challenge_parameters={}, session="next-session",
        )
        with app.state.container.complete_new_password_use_case.override(use_case):
            response = self.client.post("/auth/new-password", json=self.new_password_credentials)
        self.assertEqual(response.status_code, 200)
        use_case.execute.assert_called_once_with(
            username="test-user", new_password="new-test-password",
            session="challenge-session", required_attributes={},
        )
        self.client_factory.assert_not_called()

    def test_reset_password_requests_code(self) -> None:
        response = self.client.post("/auth/reset-password", json={"username": "test-user"})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {
            "message": "If the account is eligible, a password reset code has been sent.",
        })
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        expected_hash = base64.b64encode(hmac.new(
            b"test-secret", b"test-usertest-client", hashlib.sha256,
        ).digest()).decode("ascii")
        self.cognito.forgot_password.assert_called_once_with(
            ClientId="test-client", Username="test-user", SecretHash=expected_hash,
        )

    def test_reset_password_does_not_reveal_account_existence(self) -> None:
        expected = self.client.post("/auth/reset-password", json={"username": "test-user"})
        for code in ("UserNotFoundException", "NotAuthorizedException", "InvalidParameterException"):
            with self.subTest(code=code):
                self.cognito.forgot_password.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "private AWS details"}}, "ForgotPassword",
                )
                response = self.client.post("/auth/reset-password", json={"username": "test-user"})
                self.assertEqual(response.status_code, expected.status_code)
                self.assertEqual(response.json(), expected.json())

    def test_reset_password_confirm_sends_code_and_new_password(self) -> None:
        response = self.client.post("/auth/reset-password/confirm", json={
            "username": "test-user", "code": "123456", "new_password": "new-test-password",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "message": "Password reset successfully. Sign in with your new password.",
        })
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        expected_hash = base64.b64encode(hmac.new(
            b"test-secret", b"test-usertest-client", hashlib.sha256,
        ).digest()).decode("ascii")
        self.cognito.confirm_forgot_password.assert_called_once_with(
            ClientId="test-client", Username="test-user", ConfirmationCode="123456",
            Password="new-test-password", SecretHash=expected_hash,
        )

    def test_reset_password_confirm_errors_are_sanitized(self) -> None:
        for code, expected_status in (
            ("CodeMismatchException", 400), ("ExpiredCodeException", 400),
            ("UserNotFoundException", 400), ("NotAuthorizedException", 400),
            ("InvalidParameterException", 400), ("InvalidPasswordException", 400),
            ("PasswordHistoryPolicyViolationException", 400),
            ("TooManyRequestsException", 429), ("TooManyFailedAttemptsException", 429),
            ("InternalErrorException", 502),
        ):
            with self.subTest(code=code):
                self.cognito.confirm_forgot_password.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "private AWS details"}},
                    "ConfirmForgotPassword",
                )
                response = self.client.post("/auth/reset-password/confirm", json={
                    "username": "test-user", "code": "123456", "new_password": "new-password",
                })
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("private AWS details", response.text)

    def test_reset_password_request_errors_are_sanitized(self) -> None:
        for code, expected_status in (
            ("TooManyRequestsException", 429), ("LimitExceededException", 429),
            ("CodeDeliveryFailureException", 502), ("InternalErrorException", 502),
        ):
            with self.subTest(code=code):
                self.cognito.forgot_password.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "private AWS details"}}, "ForgotPassword",
                )
                response = self.client.post("/auth/reset-password", json={"username": "test-user"})
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("private AWS details", response.text)

    def test_reset_password_validates_input(self) -> None:
        for path, body in (
            ("/auth/reset-password", {"username": ""}),
            ("/auth/reset-password/confirm", {"username": "test-user", "new_password": "new-password"}),
            ("/auth/reset-password/confirm", {"username": "test-user", "code": "123456", "new_password": ""}),
        ):
            with self.subTest(path=path, body=body):
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 422)
        self.client_factory.assert_not_called()

    def test_reset_password_service_unavailable(self) -> None:
        for path, body, method in (
            ("/auth/reset-password", {"username": "test-user"}, self.cognito.forgot_password),
            ("/auth/reset-password/confirm", {
                "username": "test-user", "code": "123456", "new_password": "new-password",
            }, self.cognito.confirm_forgot_password),
        ):
            with self.subTest(path=path):
                method.side_effect = EndpointConnectionError(endpoint_url="https://cognito.example.com")
                response = self.client.post(path, json=body)
                self.assertEqual(response.status_code, 503)

    def test_reset_password_missing_configuration(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            for path, body in (
                ("/auth/reset-password", {"username": "test-user"}),
                ("/auth/reset-password/confirm", {
                    "username": "test-user", "code": "123456", "new_password": "new-password",
                }),
            ):
                with self.subTest(path=path):
                    response = self.client.post(path, json=body)
                    self.assertEqual(response.status_code, 503)
        self.client_factory.assert_not_called()

    def test_reset_password_use_cases_can_be_overridden(self) -> None:
        request_use_case = Mock(spec=RequestPasswordResetUseCase)
        confirm_use_case = Mock(spec=ConfirmPasswordResetUseCase)
        with app.state.container.request_password_reset_use_case.override(request_use_case):
            response = self.client.post("/auth/reset-password", json={"username": "test-user"})
        self.assertEqual(response.status_code, 202)
        request_use_case.execute.assert_called_once_with(username="test-user")

        with app.state.container.confirm_password_reset_use_case.override(confirm_use_case):
            response = self.client.post("/auth/reset-password/confirm", json={
                "username": "test-user", "code": "123456", "new_password": "new-password",
            })
        self.assertEqual(response.status_code, 200)
        confirm_use_case.execute.assert_called_once_with(
            username="test-user", code="123456", new_password="new-password",
        )
        self.client_factory.assert_not_called()

    def test_sign_in_delegates_to_use_case(self) -> None:
        use_case = Mock(spec=sign_in_module.SignInUseCase)
        use_case.execute.return_value = AuthenticationChallenge(
            challenge_name="SMS_MFA", challenge_parameters={}, session="challenge-session",
        )
        with app.state.container.sign_in_use_case.override(use_case):
            response = self.client.post("/auth/sign-in", json=self.credentials)

        self.assertEqual(response.status_code, 200)
        use_case.execute.assert_called_once_with(
            username="test-user", password="test-password",
        )
        self.client_factory.assert_not_called()

    def test_authentication_engine_can_be_overridden(self) -> None:
        engine = Mock(spec=AuthenticationEngine)
        engine.sign_in.return_value = AuthenticationChallenge(
            challenge_name="SMS_MFA", challenge_parameters={}, session="test-session",
        )

        with app.state.container.authentication_engine.override(engine):
            response = self.client.post("/auth/sign-in", json=self.credentials)

        self.assertEqual(response.status_code, 200)
        engine.sign_in.assert_called_once_with(username="test-user", password="test-password")
        self.client_factory.assert_not_called()

    def test_settings_can_be_overridden(self) -> None:
        settings = Settings(
            AWS_REGION="us-west-2",
            COGNITO_CLIENT_ID="override-client",
            COGNITO_CLIENT_SECRET="override-secret",
        )
        self.cognito.initiate_auth.return_value = {
            "ChallengeName": "SMS_MFA", "Session": "challenge-session",
        }

        with app.state.container.settings.override(settings):
            response = self.client.post("/auth/sign-in", json=self.credentials)

        self.assertEqual(response.status_code, 200)
        self.client_factory.assert_called_once_with("cognito-idp", region_name="us-west-2")
        arguments = self.cognito.initiate_auth.call_args.kwargs
        self.assertEqual(arguments["ClientId"], "override-client")
        expected_hash = base64.b64encode(hmac.new(
            b"override-secret", b"test-useroverride-client", hashlib.sha256,
        ).digest()).decode("ascii")
        self.assertEqual(arguments["AuthParameters"]["SECRET_HASH"], expected_hash)

    def test_sign_in_returns_tokens(self) -> None:
        self.cognito.initiate_auth.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access-token",
                "IdToken": "id-token",
                "RefreshToken": "refresh-token",
                "TokenType": "Bearer",
                "ExpiresIn": 3600,
            }
        }

        response = self.client.post("/auth/sign-in", json=self.credentials)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "access_token": "access-token",
            "id_token": "id-token",
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        })
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.client_factory.assert_called_once_with("cognito-idp", region_name="us-east-1")
        self.cognito.initiate_auth.assert_called_once_with(
            ClientId="test-client",
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": "test-user",
                "PASSWORD": "test-password",
                "SECRET_HASH": base64.b64encode(hmac.new(
                    b"test-secret", b"test-usertest-client", hashlib.sha256,
                ).digest()).decode("ascii"),
            },
        )

    def test_sign_in_includes_secret_hash(self) -> None:
        self.cognito.initiate_auth.return_value = {
            "ChallengeName": "SMS_MFA", "Session": "challenge-session",
        }
        with patch.dict("os.environ", {"COGNITO_CLIENT_SECRET": "test-secret"}):
            response = self.client.post("/auth/sign-in", json=self.credentials)

        self.assertEqual(response.status_code, 200)
        parameters = self.cognito.initiate_auth.call_args.kwargs["AuthParameters"]
        expected = base64.b64encode(hmac.new(
            b"test-secret", b"test-usertest-client", hashlib.sha256,
        ).digest()).decode("ascii")
        self.assertEqual(parameters["SECRET_HASH"], expected)

    def test_sign_in_returns_mfa_challenge(self) -> None:
        self.cognito.initiate_auth.return_value = {
            "ChallengeName": "SMS_MFA",
            "ChallengeParameters": {"CODE_DELIVERY_DELIVERY_MEDIUM": "SMS"},
            "Session": "challenge-session",
        }

        response = self.client.post("/auth/sign-in", json=self.credentials)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "challenge_name": "SMS_MFA",
            "challenge_parameters": {"CODE_DELIVERY_DELIVERY_MEDIUM": "SMS"},
            "session": "challenge-session",
        })

    def test_cognito_errors_are_sanitized(self) -> None:
        for code, expected_status in (
            ("NotAuthorizedException", 401),
            ("UserNotFoundException", 401),
            ("UserNotConfirmedException", 403),
            ("PasswordResetRequiredException", 403),
            ("TooManyRequestsException", 429),
            ("InternalErrorException", 502),
        ):
            with self.subTest(code=code):
                self.cognito.initiate_auth.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "private AWS details"}},
                    "InitiateAuth",
                )

                response = self.client.post("/auth/sign-in", json=self.credentials)

                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("private AWS details", response.text)

    def test_connection_error_returns_service_unavailable(self) -> None:
        self.cognito.initiate_auth.side_effect = EndpointConnectionError(
            endpoint_url="https://cognito-idp.us-east-1.amazonaws.com",
        )
        response = self.client.post("/auth/sign-in", json=self.credentials)
        self.assertEqual(response.status_code, 503)

    def test_missing_configuration_does_not_call_cognito(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post("/auth/sign-in", json=self.credentials)
        self.assertEqual(response.status_code, 503)
        self.client_factory.assert_not_called()

    def test_empty_password_is_rejected(self) -> None:
        response = self.client.post(
            "/auth/sign-in", json={"username": "test-user", "password": ""},
        )
        self.assertEqual(response.status_code, 422)
        self.client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()