import base64
import hashlib
import hmac
from dataclasses import asdict
from datetime import UTC, datetime
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi.testclient import TestClient
from pydantic import ValidationError

from application.use_cases import sign_in as sign_in_module
from application.use_cases.complete_new_password import CompleteNewPasswordUseCase
from application.use_cases.get_current_user import GetCurrentUserUseCase
from application.use_cases.sign_up import SignUpUseCase
from application.use_cases.reset_password import ConfirmPasswordResetUseCase, RequestPasswordResetUseCase
from domain.exceptions.authentication import AuthenticationError
from infrastructure.persistence.exceptions import PersistenceError
from domain.models.user import UserModel as DomainUserModel, UserStatus
from domain.models.waiting_list import WaitingListEntryModel
from domain.repositories.user import UserRepository
from domain.repositories.waiting_list import WaitingListRepository
from domain.services.authentication import AuthenticationChallenge, AuthenticationEngine, SignUpResult
from domain.services.user import UserService
from infrastructure.authentication import cognito as cognito_module
from infrastructure.config.settings import Settings
from presentation.apis.bff.main import app


class SignUpResultTests(unittest.TestCase):
    def test_signup_result_contains_only_identity_and_confirmation_status(self) -> None:
        result = SignUpResult(user_id="user-id", user_confirmed=True)

        self.assertEqual(asdict(result), {"user_id": "user-id", "user_confirmed": True})

    def test_admin_signup_returns_result_without_delivery_fields(self) -> None:
        with patch.object(cognito_module.boto3, "client") as client_factory:
            cognito = client_factory.return_value
            cognito.admin_create_user.return_value = {"User": {"Username": "user-id"}}
            engine = cognito_module.CognitoAuthenticationEngine(
                region="us-east-1", client_id="test-client", client_secret="test-secret", user_pool_id="test-pool",
            )

            result = engine.sign_up(username="user@example.com", email="user@example.com", password="test-password")

        self.assertEqual(asdict(result), {"user_id": "user-id", "user_confirmed": True})
        cognito.admin_set_user_password.assert_called_once_with(
            UserPoolId="test-pool", Username="user@example.com", Password="test-password", Permanent=True,
        )

    def test_signup_endpoint_returns_only_result_fields(self) -> None:
        use_case = Mock(spec=SignUpUseCase)
        use_case.execute.return_value = WaitingListEntryModel(
            id="entry-id", email="user@example.com", phone="+5511999999999", region="SP",
            insurance_categories=("Pessoas",), created_at=datetime(2026, 10, 29, tzinfo=UTC),
        )

        with app.state.container.sign_up_use_case.override(use_case), TestClient(app) as client:
            response = client.post("/auth/sign-up", json={
                "email": "user@example.com", "phone": "+5511999999999", "region": "SP",
                "insurance_categories": ["Pessoas"],
            })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"id": "entry-id", "created_at": "2026-10-29T00:00:00Z"})

    def test_signup_response_schema_matches_result_fields(self) -> None:
        schema = app.openapi()["components"]["schemas"]["SignUpResponse"]

        self.assertEqual(set(schema["properties"]), {"id", "created_at"})


class SettingsTests(unittest.TestCase):
    def test_settings_load_environment_and_hide_secret(self) -> None:
        with patch.dict("os.environ", {
            "AWS_REGION": "us-east-1",
            "AWS_DEFAULT_REGION": "us-west-2",
            "COGNITO_CLIENT_ID": "test-client",
            "COGNITO_CLIENT_SECRET": "private-client-secret",
            "COGNITO_USER_POOL_ID": "us-east-1_testpool",
        }, clear=True):
            settings = Settings()

        self.assertEqual(settings.AWS_REGION, "us-east-1")
        self.assertEqual(settings.COGNITO_CLIENT_ID, "test-client")
        self.assertEqual(settings.COGNITO_USER_POOL_ID, "us-east-1_testpool")
        self.assertEqual(settings.COGNITO_CLIENT_SECRET.get_secret_value(), "private-client-secret")
        self.assertNotIn("private-client-secret", repr(settings))

    def test_empty_region_uses_default_region(self) -> None:
        with patch.dict("os.environ", {
            "AWS_REGION": "", "AWS_DEFAULT_REGION": "us-west-2",
            "COGNITO_CLIENT_ID": "test-client",
            "COGNITO_CLIENT_SECRET": "test-secret",
            "COGNITO_USER_POOL_ID": "us-east-1_testpool",
        }, clear=True):
            settings = Settings()

        self.assertEqual(settings.AWS_REGION, "us-west-2")

    def test_all_settings_are_required_and_nonempty(self) -> None:
        environment = {
            "AWS_REGION": "us-east-1",
            "COGNITO_CLIENT_ID": "test-client",
            "COGNITO_CLIENT_SECRET": "test-secret",
            "COGNITO_USER_POOL_ID": "us-east-1_testpool",
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
            "AWS_REGION", "COGNITO_CLIENT_ID", "COGNITO_CLIENT_SECRET", "COGNITO_USER_POOL_ID",
        })
        with patch.dict("os.environ", {
            "aws_region": "us-east-1",
            "cognito_client_id": "test-client",
            "cognito_client_secret": "test-secret",
        }, clear=True):
            with self.assertRaises(ValidationError):
                Settings()


class SignInUseCaseTests(unittest.TestCase):
    def test_current_user_returns_domain_model_through_service(self) -> None:
        engine = Mock(spec=AuthenticationEngine)
        engine.get_authenticated_user_id.return_value = "cognito-sub"
        repository = Mock(spec=UserRepository)
        user = DomainUserModel(
            id="local-id", email="user@example.com", external_id="cognito-sub",
            status=UserStatus.REGISTERED, created_at=datetime(2026, 10, 27, tzinfo=UTC),
        )
        repository.get_by_external_id.return_value = user
        service = UserService(user_repository=repository)
        use_case = GetCurrentUserUseCase(authentication_engine=engine, user_service=service)

        with patch.object(service, "get_info", wraps=service.get_info) as get_info:
            result = use_case.execute(access_token="test-access-token")
            get_info.assert_called_once_with(external_id="cognito-sub")

        self.assertIs(type(result), DomainUserModel)
        self.assertEqual(result.id, "local-id")
        self.assertEqual(result.email, "user@example.com")
        self.assertEqual(result.status, UserStatus.REGISTERED)
        repository.get_by_external_id.assert_called_once_with(external_id="cognito-sub")

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
    def test_broker_activation_router_is_removed(self) -> None:
        with TestClient(app) as client:
            response = client.post("/brokers/pending-broker/activate")

        self.assertEqual(response.status_code, 404)
        paths = app.openapi()["paths"]
        self.assertFalse(any(path.startswith("/brokers") for path in paths))
        self.assertIn("/auth/sign-in", paths)
        self.assertFalse(hasattr(app.state.container, "activate_broker_use_case"))

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
                "COGNITO_USER_POOL_ID": "us-east-1_testpool",
            },
            clear=True,
        )
        environment.start()
        self.addCleanup(environment.stop)
        client_patch = patch.object(cognito_module.boto3, "client")
        self.client_factory = client_patch.start()
        self.addCleanup(client_patch.stop)
        self.cognito = self.client_factory.return_value
        self.user_repository = Mock(spec=UserRepository)
        app.state.container.user_repository.override(self.user_repository)
        self.addCleanup(app.state.container.user_repository.reset_override)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.credentials = {"username": "test-user", "password": "test-password"}
        self.new_password_credentials = {
            "username": "test-user",
            "new_password": "new-test-password",
            "session": "challenge-session",
        }
        self.sign_up_body = {
            "email": "user@example.com", "phone": "+55 11 99999-9999", "region": "São Paulo",
            "insurance_categories": ["Pessoas", "Viagem"],
        }
        self.logged_user = DomainUserModel(
            id="local-user-id", email="user@example.com", external_id="cognito-user-sub",
            status=UserStatus.REGISTERED, name="Example User",
            created_at=datetime(2026, 10, 27, tzinfo=UTC),
        )
        self.cognito.get_user.return_value = {
            "UserAttributes": [{"Name": "sub", "Value": "cognito-user-sub"}],
        }
        self.user_repository.get_by_external_id.return_value = self.logged_user

    def test_current_user_returns_authenticated_profile(self) -> None:
        response = self.client.get("/auth/me", headers={"Authorization": "Bearer test-access-token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"name": "Example User", "email": "user@example.com"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.cognito.get_user.assert_called_once_with(AccessToken="test-access-token")
        self.user_repository.get_by_external_id.assert_called_once_with(external_id="cognito-user-sub")
        self.assertNotIn("test-access-token", response.text)

    def test_current_user_requires_bearer_token(self) -> None:
        for headers in ({}, {"Authorization": "Basic invalid"}, {"Authorization": "Bearer "}):
            with self.subTest(headers=headers):
                response = self.client.get("/auth/me", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        self.client_factory.assert_not_called()
        self.user_repository.get_by_external_id.assert_not_called()

    def test_current_user_cognito_errors_are_sanitized(self) -> None:
        for code, expected_status in (
            ("NotAuthorizedException", 401), ("UserNotFoundException", 401),
            ("ForbiddenException", 403), ("TooManyRequestsException", 429), ("InternalErrorException", 502),
        ):
            with self.subTest(code=code):
                self.cognito.get_user.side_effect = ClientError(
                    {"Error": {"Code": code, "Message": "private AWS details"}}, "GetUser",
                )
                response = self.client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("private AWS details", response.text)
                if expected_status == 401:
                    self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        self.user_repository.get_by_external_id.assert_not_called()

    def test_current_user_requires_cognito_sub(self) -> None:
        self.cognito.get_user.return_value = {"UserAttributes": [{"Name": "email", "Value": "user@example.com"}]}

        response = self.client.get("/auth/me", headers={"Authorization": "Bearer test-access-token"})

        self.assertEqual(response.status_code, 502)
        self.user_repository.get_by_external_id.assert_not_called()

    def test_current_user_profile_not_found(self) -> None:
        self.user_repository.get_by_external_id.return_value = None

        response = self.client.get("/auth/me", headers={"Authorization": "Bearer test-access-token"})

        self.assertEqual(response.status_code, 404)

    def test_current_user_database_error_is_sanitized(self) -> None:
        self.user_repository.get_by_external_id.side_effect = PersistenceError("private database details")

        response = self.client.get("/auth/me", headers={"Authorization": "Bearer test-access-token"})

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database details", response.text)

    def test_current_user_cognito_unavailable(self) -> None:
        self.cognito.get_user.side_effect = EndpointConnectionError(endpoint_url="https://cognito.example.com")

        response = self.client.get("/auth/me", headers={"Authorization": "Bearer test-access-token"})

        self.assertEqual(response.status_code, 503)
        self.user_repository.get_by_external_id.assert_not_called()

    def test_current_user_service_can_be_overridden(self) -> None:
        service = Mock(spec=UserService)
        service.get_info.return_value = DomainUserModel(
            id=self.logged_user.id,
            email=self.logged_user.email,
            external_id=self.logged_user.external_id,
            status=self.logged_user.status,
            name=self.logged_user.name,
            created_at=self.logged_user.created_at,
        )

        with app.state.container.user_service.override(service):
            response = self.client.get("/auth/me", headers={"Authorization": "Bearer test-access-token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], self.logged_user.name)
        self.assertNotIn("id", response.json())
        service.get_info.assert_called_once_with(external_id="cognito-user-sub")
        self.user_repository.get_by_external_id.assert_not_called()

    def test_current_user_use_case_can_be_overridden(self) -> None:
        use_case = Mock(spec=GetCurrentUserUseCase)
        use_case.execute.return_value = self.logged_user
        with app.state.container.get_current_user_use_case.override(use_case):
            response = self.client.get("/auth/me", headers={"Authorization": "Bearer test-access-token"})
        self.assertEqual(response.status_code, 200)
        use_case.execute.assert_called_once_with(access_token="test-access-token")
        self.client_factory.assert_not_called()

    def test_sign_up_saves_waiting_list_entry(self) -> None:
        waiting_list_repository = Mock(spec=WaitingListRepository)
        waiting_list_repository.exists_by_email.return_value = False

        with app.state.container.waiting_list_repository.override(waiting_list_repository):
            response = self.client.post("/auth/sign-up", json=self.sign_up_body)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.json()), {"id", "created_at"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        entry = waiting_list_repository.add.call_args.args[0]
        self.assertEqual(entry.id, response.json()["id"])
        self.assertEqual(entry.email, "user@example.com")
        self.assertEqual(entry.phone, "+55 11 99999-9999")
        self.assertEqual(entry.region, "São Paulo")
        self.assertEqual(entry.insurance_categories, ("Pessoas", "Viagem"))
        self.client_factory.assert_not_called()

    def test_sign_up_rejects_duplicate_email(self) -> None:
        waiting_list_repository = Mock(spec=WaitingListRepository)
        waiting_list_repository.exists_by_email.return_value = True

        with app.state.container.waiting_list_repository.override(waiting_list_repository):
            response = self.client.post("/auth/sign-up", json=self.sign_up_body)

        self.assertEqual(response.status_code, 409)
        waiting_list_repository.add.assert_not_called()

    def test_sign_up_validates_required_fields(self) -> None:
        for field in self.sign_up_body:
            with self.subTest(field=field):
                body = {key: value for key, value in self.sign_up_body.items() if key != field}
                response = self.client.post("/auth/sign-up", json=body)
                self.assertEqual(response.status_code, 422)
        for field, value in (
            ("email", "not-an-email"), ("phone", "abc"), ("region", ""),
            ("insurance_categories", []), ("insurance_categories", [" "]),
        ):
            with self.subTest(field=field, value=value):
                response = self.client.post("/auth/sign-up", json={**self.sign_up_body, field: value})
                self.assertEqual(response.status_code, 422)
        self.client_factory.assert_not_called()

    def test_sign_up_accepts_comma_separated_categories(self) -> None:
        waiting_list_repository = Mock(spec=WaitingListRepository)
        waiting_list_repository.exists_by_email.return_value = False

        with app.state.container.waiting_list_repository.override(waiting_list_repository):
            response = self.client.post("/auth/sign-up", json={
                **self.sign_up_body, "insurance_categories": "Pessoas, Viagem,",
            })

        self.assertEqual(response.status_code, 201)
        entry = waiting_list_repository.add.call_args.args[0]
        self.assertEqual(entry.insurance_categories, ("Pessoas", "Viagem"))

    def test_sign_up_use_case_can_be_overridden(self) -> None:
        use_case = Mock(spec=SignUpUseCase)
        use_case.execute.return_value = WaitingListEntryModel(
            id="entry-id", email="user@example.com", phone="+55 11 99999-9999", region="São Paulo",
            insurance_categories=("Pessoas", "Viagem"),
        )
        with app.state.container.sign_up_use_case.override(use_case):
            response = self.client.post("/auth/sign-up", json=self.sign_up_body)
        self.assertEqual(response.status_code, 201)
        use_case.execute.assert_called_once_with(
            email="user@example.com", phone="+55 11 99999-9999", region="São Paulo",
            insurance_categories=["Pessoas", "Viagem"],
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
            COGNITO_USER_POOL_ID="us-west-2_overridepool",
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