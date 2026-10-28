from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.models.user import UserModel as DomainUserModel, UserStatus
from infrastructure.persistence.exceptions import PersistenceError
from domain.repositories.user import UserRepository
from infrastructure.persistence.sqlalchemy.models.user_model import UserModel
from infrastructure.persistence.sqlalchemy.user_mapper import UserMapper


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get_by_external_id(self, external_id: str) -> DomainUserModel | None:
        try:
            with self.session_factory() as session:
                record = session.execute(
                    select(UserModel).where(UserModel.external_id == external_id),
                ).scalar_one_or_none()
                if record is None:
                    return None
                return UserMapper.to_domain(record)
        except SQLAlchemyError as e:
            raise PersistenceError(f"Unable to load user profile {external_id}: {e}") from None

    def add(self, user: DomainUserModel) -> None:
        try:
            with self.session_factory.begin() as session:
                session.add(UserMapper.to_model(user))
        except SQLAlchemyError:
            raise PersistenceError("Unable to save user profile") from None

    def mark_email_confirmed(self, email: str) -> None:
        try:
            with self.session_factory.begin() as session:
                result = session.execute(
                    update(UserModel)
                    .where(UserModel.email == email, UserModel.status == UserStatus.REGISTERED)
                    .values(status=UserStatus.EMAIL_CONFIRMED)
                )
                if result.rowcount == 0:
                    user_id = session.scalar(select(UserModel.id).where(UserModel.email == email))
                    if user_id is None:
                        raise PersistenceError("User profile not found")
        except SQLAlchemyError:
            raise PersistenceError("Unable to update user registration status") from None