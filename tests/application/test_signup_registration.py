import unittest
from unittest.mock import Mock, call

from application.use_cases.sign_up import SignUpUseCase
from domain.exceptions.authentication import AuthenticationError
from infrastructure.persistence.exceptions import PersistenceError
from domain.models.user import UserModel, UserStatus
from domain.repositories.user import UserRepository
from domain.services.authentication import AuthenticationEngine, SignUpResult
from domain.services.user import UserService


class SignupRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=UserRepository)
        self.repository.fetch_user_by_email.return_value = UserModel(
            id="local-user-id", email="user@example.com", external_id="provisioned-id", status=UserStatus.PENDING,
        )
        self.authentication = Mock(spec=AuthenticationEngine)
        self.authentication.sign_up.return_value = SignUpResult(user_id="new-cognito-sub", user_confirmed=False)
        self.use_case = SignUpUseCase(self.authentication, UserService(self.repository))

    def test_existing_user_is_registered_after_cognito_confirmation(self) -> None:
        operations = Mock()
        operations.attach_mock(self.repository, "repository")
        operations.attach_mock(self.authentication, "authentication")

        result = self.use_case.execute(email="user@example.com", password="test-password")

        self.assertEqual(operations.mock_calls, [
            call.repository.fetch_user_by_email(email="user@example.com"),
            call.authentication.sign_up(username="user@example.com", email="user@example.com", password="test-password"),
            call.authentication.auto_confirm_email(username="user@example.com", account_confirmed=False),
            call.repository.activate_user(user_id="local-user-id", external_id="new-cognito-sub"),
        ])
        self.assertEqual(result.user_id, "new-cognito-sub")
        self.assertTrue(result.user_confirmed)
        self.repository.add.assert_not_called()

    def test_unprovisioned_registration_does_not_create_cognito_account(self) -> None:
        self.repository.fetch_user_by_email.return_value = None

        with self.assertRaises(AuthenticationError) as error:
            self.use_case.execute(email="user@example.com", password="test-password")

        self.assertEqual(error.exception.reason, "registration_not_provisioned")
        self.authentication.sign_up.assert_not_called()
        self.repository.activate_user.assert_not_called()

    def test_cognito_signup_failure_does_not_update_local_registration(self) -> None:
        self.authentication.sign_up.side_effect = AuthenticationError("service_error", "Cognito failed")

        with self.assertRaises(AuthenticationError):
            self.use_case.execute(email="user@example.com", password="test-password")

        self.authentication.auto_confirm_email.assert_not_called()
        self.repository.activate_user.assert_not_called()

    def test_confirmation_failure_does_not_update_local_registration(self) -> None:
        self.authentication.auto_confirm_email.side_effect = AuthenticationError("service_error", "Confirmation failed")

        with self.assertRaises(AuthenticationError):
            self.use_case.execute(email="user@example.com", password="test-password")

        self.repository.activate_user.assert_not_called()

    def test_registration_persistence_failure_is_not_reported_as_success(self) -> None:
        self.repository.activate_user.side_effect = PersistenceError("Registration failed")

        with self.assertRaises(PersistenceError):
            self.use_case.execute(email="user@example.com", password="test-password")

    def test_activate_user_persists_without_mutating_immutable_model(self) -> None:
        user = self.repository.fetch_user_by_email.return_value

        UserService(self.repository).activate_user(user=user, external_id="new-cognito-sub")

        self.repository.activate_user.assert_called_once_with(user_id="local-user-id", external_id="new-cognito-sub")
        self.assertEqual(user.status, UserStatus.PENDING)
        self.assertEqual(user.external_id, "provisioned-id")

    def test_activate_user_rejects_non_pending_user(self) -> None:
        user = UserModel(
            id="local-user-id", email="user@example.com", external_id="existing-sub", status=UserStatus.REGISTERED,
        )

        with self.assertRaises(AuthenticationError) as error:
            UserService(self.repository).activate_user(user=user, external_id="new-cognito-sub")

        self.assertEqual(error.exception.reason, "registration_not_pending")
        self.repository.activate_user.assert_not_called()