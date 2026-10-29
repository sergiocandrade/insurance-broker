import json
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.exceptions.waiting_list import WaitingListEntryAlreadyExistsException
from domain.models.waiting_list import WaitingListEntryModel
from domain.repositories.waiting_list import WaitingListRepository
from infrastructure.persistence.exceptions import PersistenceError
from infrastructure.persistence.sqlalchemy.models import WaitingListModel


class SqlAlchemyWaitingListRepository(WaitingListRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def exists_by_email(self, email: str) -> bool:
        try:
            with self.session_factory() as session:
                return session.scalar(
                    select(WaitingListModel.id).where(WaitingListModel.email == email).limit(1),
                ) is not None
        except SQLAlchemyError:
            raise PersistenceError("Unable to load waiting list entry") from None

    def add(self, entry: WaitingListEntryModel) -> None:
        try:
            with self.session_factory.begin() as session:
                session.add(WaitingListModel(
                    id=entry.id,
                    email=entry.email,
                    phone=entry.phone,
                    region=entry.region,
                    insurance_categories=json.dumps(list(entry.insurance_categories), ensure_ascii=False),
                    created_at=entry.created_at.astimezone(UTC).replace(tzinfo=None),
                ))
        except IntegrityError:
            raise WaitingListEntryAlreadyExistsException() from None
        except SQLAlchemyError:
            raise PersistenceError("Unable to save waiting list entry") from None
