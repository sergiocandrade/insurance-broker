from datetime import UTC

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.models.broker import BrokerModel as DomainBrokerModel
from domain.exceptions.domain import NotFoundException
from infrastructure.persistence.exceptions import PersistenceError
from domain.repositories.broker import BrokerRepository
from infrastructure.persistence.sqlalchemy.models import BrokerModel, UserBrokerModel


class SqlAlchemyBrokerRepository(BrokerRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def update(self, broker: DomainBrokerModel) -> None:
        try:
            with self.session_factory.begin() as session:
                record = session.execute(
                    select(BrokerModel).where(BrokerModel.id == broker.id).with_for_update(),
                ).scalar_one_or_none()
                if record is None:
                    raise NotFoundException("Broker")

                record.status = broker.status
                record.activated_at = broker.activated_at
        except SQLAlchemyError:
            raise PersistenceError("Unable to update broker") from None

    def list_brokers_for_user(self, user_id: str) -> list[DomainBrokerModel]:
        try:
            with self.session_factory() as session:
                records = session.scalars(
                    select(BrokerModel)
                    .join(UserBrokerModel, UserBrokerModel.broker_id == BrokerModel.id)
                    .where(UserBrokerModel.user_id == user_id)
                    .order_by(BrokerModel.id),
                ).all()
                return [
                    DomainBrokerModel(
                        id=record.id,
                        status=record.status,
                        created_at=record.created_at.replace(tzinfo=UTC),
                        activated_at=(
                            record.activated_at.replace(tzinfo=UTC)
                            if record.activated_at is not None
                            else None
                        ),
                    )
                    for record in records
                ]
        except SQLAlchemyError:
            raise PersistenceError("Unable to load user brokers") from None
