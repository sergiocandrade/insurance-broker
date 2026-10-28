from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.models.user import UserModel as DomainUserModel, UserStatus
from infrastructure.persistence.exceptions import PersistenceError
from domain.repositories.user import UserRepository
from domain.models.broker import BrokerStatus
from infrastructure.persistence.sqlalchemy.models import BrokerModel, UserBrokerModel
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

    def activate_user(
        self,
        user_id: str,
        external_id: str,
        activated_at: datetime | None = None,
    ) -> None:
        try:
            with self.session_factory.begin() as session:
                record = session.execute(
                    select(UserModel).where(UserModel.id == user_id).with_for_update(),
                ).scalar_one_or_none()
                if record is None:
                    return None

                
                record.external_id = external_id
                record.status = UserStatus.REGISTERED
                activation_time = activated_at or datetime.now(UTC)
                record.activated_at = activation_time.astimezone(UTC).replace(tzinfo=None)
                session.execute(
                    update(BrokerModel)
                    .where(BrokerModel.id.in_(broker_ids))
                    .values(status=BrokerStatus.ACTIVE, activated_at=record.activated_at),
                )
        except SQLAlchemyError:
            raise PersistenceError("Unable to activate user and associated brokers") from None
