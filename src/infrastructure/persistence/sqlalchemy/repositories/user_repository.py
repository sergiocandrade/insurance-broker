from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.models.user import UserModel as DomainUserModel
from infrastructure.persistence.exceptions import PersistenceError
from domain.repositories.user import UserRepository
from infrastructure.persistence.sqlalchemy.models.user_model import UserModel
from infrastructure.persistence.sqlalchemy.user_mapper import UserMapper


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def fetch_user_by_email(self, email: str) -> DomainUserModel | None:
        try:
            with self.session_factory() as session:
                record = session.execute(
                    select(UserModel).where(UserModel.email == email),
                ).scalar_one_or_none()
                return UserMapper.to_domain(record) if record is not None else None
        except SQLAlchemyError:
            raise PersistenceError("Unable to load registration profile") from None    

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
    

    def update(self, user: DomainUserModel) -> None:
        try:
            with self.session_factory.begin() as session:
                record = session.execute(
                    select(UserModel).where(UserModel.id == user.id).with_for_update(),
                ).scalar_one_or_none()
                if record is None:
                    raise PersistenceError("User profile not found")
                record.email = user.email
                record.external_id = user.external_id
                record.status = user.status
                record.activated_at = user.activated_at
        except SQLAlchemyError:
            raise PersistenceError("Unable to update user profile") from None

