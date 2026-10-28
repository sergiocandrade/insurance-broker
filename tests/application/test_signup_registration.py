import unittest
from unittest.mock import Mock

from application.use_cases.sign_up import SignUpUseCase
from domain.exceptions.authentication import AuthenticationError
from domain.exceptions.user import UserNotPreRegistredException
from infrastructure.persistence.exceptions import PersistenceError
from domain.models.user import UserModel, UserStatus
from domain.repositories.user import UserRepository
from domain.services.authentication import AuthenticationEngine, SignUpResult
from domain.services.user import UserService
from domain.services.broker import BrokerService


class SignupRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=UserRepository)
        self.repository.fetch_user_by_email.return_value = UserModel(
            id="local-user-id", email="user@example.com", external_id="provisioned-id", status=UserStatus.PENDING,
        )
        self.authentication = Mock(spec=AuthenticationEngine)
        self.authentication.sign_up.return_value = SignUpResult(user_id="new-cognito-sub", user_confirmed=False)
        self.broker_service = Mock(spec=BrokerService)
        self.broker_service.list_brokers_for_user.return_value = []
        self.use_case = SignUpUseCase(self.authentication, UserService(self.repository), self.broker_service)

    def test_existing_user_is_registered_and_brokers_are_loaded(self) -> None:
        result = self.use_case.execute(email="user@example.com", password="test-password")

        self.repository.fetch_user_by_email.assert_called_once_with(email="user@example.com")
        self.authentication.sign_up.assert_called_once_with(
            username="user@example.com", email="user@example.com", password="test-password",
        )
        self.repository.update.assert_called_once()
        self.broker_service.list_brokers_for_user.assert_called_once_with(user_id="local-user-id")
        self.assertEqual(result.user_id, "new-cognito-sub")
        self.assertTrue(result.user_confirmed)

    def test_unprovisioned_registration_does_not_create_cognito_account(self) -> None:
        self.repository.fetch_user_by_email.return_value = None

        with self.assertRaises(UserNotPreRegistredException):
            self.use_case.execute(email="user@example.com", password="test-password")

        self.authentication.sign_up.assert_not_called()
        self.repository.update.assert_not_called()

    def test_cognito_signup_failure_does_not_update_local_registration(self) -> None:
        self.authentication.sign_up.side_effect = AuthenticationError("service_error", "Cognito failed")

        with self.assertRaises(AuthenticationError):
            self.use_case.execute(email="user@example.com", password="test-password")

        self.repository.update.assert_not_called()

    def test_registration_persistence_failure_is_not_reported_as_success(self) -> None:
        self.repository.update.side_effect = PersistenceError("Registration failed")

        with self.assertRaises(PersistenceError):
            self.use_case.execute(email="user@example.com", password="test-password")

    def test_activate_user_updates_domain_model_and_repository(self) -> None:
        user = self.repository.fetch_user_by_email.return_value

        UserService(self.repository).activate_user(user=user, external_id="new-cognito-sub")

        self.repository.update.assert_called_once_with(user=user)
        self.assertEqual(user.status, UserStatus.REGISTERED)
        self.assertEqual(user.external_id, "new-cognito-sub")

    def test_activate_user_rejects_non_pending_user(self) -> None:
        user = UserModel(
            id="local-user-id", email="user@example.com", external_id="existing-sub", status=UserStatus.REGISTERED,
        )

        with self.assertRaises(UserNotPreRegistredException):
            UserService(self.repository).activate_user(user=user, external_id="new-cognito-sub")

        self.repository.update.assert_not_called()