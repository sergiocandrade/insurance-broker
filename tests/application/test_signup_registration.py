import unittest
from unittest.mock import Mock

from application.use_cases.sign_up import SignUpUseCase
from domain.exceptions.user import UserNotPreRegistredException
from domain.exceptions.waiting_list import WaitingListEntryAlreadyExistsException
from infrastructure.persistence.exceptions import PersistenceError
from domain.models.user import UserModel, UserStatus
from domain.repositories.user import UserRepository
from domain.repositories.waiting_list import WaitingListRepository
from domain.services.user import UserService
from domain.services.waiting_list import WaitingListService


class SignupRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = Mock(spec=UserRepository)
        self.repository.fetch_user_by_email.return_value = UserModel(
            id="local-user-id", email="user@example.com", external_id="provisioned-id", status=UserStatus.PENDING,
        )
        self.waiting_list_repository = Mock(spec=WaitingListRepository)
        self.waiting_list_repository.exists_by_email.return_value = False
        self.use_case = SignUpUseCase(WaitingListService(self.waiting_list_repository))

    def execute(self):
        return self.use_case.execute(
            email="user@example.com", phone="+55 11 99999-9999", region="São Paulo",
            insurance_categories=["Pessoas", "Viagem", "Pessoas"],
        )

    def test_sign_up_saves_entry_in_waiting_list(self) -> None:
        entry = self.execute()

        self.waiting_list_repository.add.assert_called_once_with(entry)
        self.assertEqual(entry.email, "user@example.com")
        self.assertEqual(entry.phone, "+55 11 99999-9999")
        self.assertEqual(entry.region, "São Paulo")
        self.assertEqual(entry.insurance_categories, ("Pessoas", "Viagem"))
        self.assertIsNotNone(entry.created_at)

    def test_duplicate_email_is_rejected(self) -> None:
        self.waiting_list_repository.exists_by_email.return_value = True

        with self.assertRaises(WaitingListEntryAlreadyExistsException):
            self.execute()

        self.waiting_list_repository.add.assert_not_called()

    def test_persistence_failure_is_not_reported_as_success(self) -> None:
        self.waiting_list_repository.add.side_effect = PersistenceError("Save failed")

        with self.assertRaises(PersistenceError):
            self.execute()

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