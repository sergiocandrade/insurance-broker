import unittest
from unittest.mock import Mock

from application.use_cases.activate_user import ActivateUserUseCase
from domain.exceptions.authentication import AuthenticationError
from domain.exceptions.user import UserNotPreRegistredException
from domain.models.user import UserModel, UserStatus
from domain.repositories.user import UserRepository
from domain.services.authentication import AuthenticationEngine, SignUpResult
from domain.services.broker import BrokerService
from domain.services.user import UserService
from infrastructure.persistence.exceptions import PersistenceError


class ActivateUserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=UserRepository)
        self.repository.fetch_user_by_email.return_value = UserModel(
            id="local-user-id", email="user@example.com", external_id="provisioned-id", status=UserStatus.PENDING,
        )
        self.authentication = Mock(spec=AuthenticationEngine)
        self.authentication.sign_up.return_value = SignUpResult(user_id="new-cognito-sub", user_confirmed=False)
        self.broker_service = Mock(spec=BrokerService)
        self.broker_service.list_brokers_for_user.return_value = []
        self.use_case = ActivateUserUseCase(self.authentication, UserService(self.repository), self.broker_service)

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

    def test_unprovisioned_user_does_not_create_cognito_account(self) -> None:
        self.repository.fetch_user_by_email.return_value = None

        with self.assertRaises(UserNotPreRegistredException):
            self.use_case.execute(email="user@example.com", password="test-password")

        self.authentication.sign_up.assert_not_called()
        self.repository.update.assert_not_called()

    def test_cognito_failure_does_not_update_local_user(self) -> None:
        self.authentication.sign_up.side_effect = AuthenticationError("service_error", "Cognito failed")

        with self.assertRaises(AuthenticationError):
            self.use_case.execute(email="user@example.com", password="test-password")

        self.repository.update.assert_not_called()

    def test_persistence_failure_is_not_reported_as_success(self) -> None:
        self.repository.update.side_effect = PersistenceError("Activation failed")

        with self.assertRaises(PersistenceError):
            self.use_case.execute(email="user@example.com", password="test-password")
