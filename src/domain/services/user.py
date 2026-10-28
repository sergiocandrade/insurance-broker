from datetime import UTC, datetime

from domain.exceptions.user import UserAlreadyRegistredException, UserNotFoundException, UserNotPreRegistredException
from domain.models.user import UserModel, UserStatus
from domain.repositories.user import UserRepository


class UserService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def fetch_pending_user_by_email(self, email: str) -> UserModel:
        user = self.user_repository.fetch_user_by_email(email=email)
        if user is None:
            raise UserNotPreRegistredException()
        if user.status != UserStatus.PENDING:
            raise UserAlreadyRegistredException()
        return user
    
    def activate_user(self, user: UserModel, external_id: str) -> UserModel:
        
        if user.status != UserStatus.PENDING:
            raise UserNotPreRegistredException()

        user.external_id = external_id
        user.status = UserStatus.REGISTERED
        user.activated_at = datetime.now(UTC)
        self.user_repository.update(user=user)
        return user

    def get_info(self, external_id: str) -> UserModel:
        user = self.user_repository.get_by_external_id(external_id=external_id)
        if user is None:
            raise UserNotFoundException("user_profile_not_found", "User profile not found")
        return user
