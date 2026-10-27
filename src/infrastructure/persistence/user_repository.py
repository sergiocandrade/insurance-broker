from datetime import UTC

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.entities.user import User
from domain.exceptions.persistence import UserPersistenceError
from domain.repositories.user import UserRepository
from infrastructure.persistence.models import UserModel


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def add(self, user: User) -> None:
        try:
            with self.session_factory.begin() as session:
                session.add(UserModel(
                    id=user.id,
                    email=user.email,
                    external_id=user.external_id,
                    created_at=user.created_at.astimezone(UTC).replace(tzinfo=None),
                ))
        except SQLAlchemyError:
            raise UserPersistenceError("Unable to save user profile") from None