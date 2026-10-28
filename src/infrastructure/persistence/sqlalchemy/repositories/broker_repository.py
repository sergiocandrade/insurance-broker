from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.models.broker import BrokerModel as DomainBrokerModel, BrokerStatus
from domain.exceptions.broker import BrokerAccessDeniedError, BrokerNotFoundError
from infrastructure.persistence.exceptions import PersistenceError
from domain.repositories.broker import BrokerRepository
from infrastructure.persistence.sqlalchemy.models import BrokerModel, UserBrokerModel


class SqlAlchemyBrokerRepository(BrokerRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

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

    def activate(self, broker_id: str, user_id: str) -> DomainBrokerModel:
        try:
            with self.session_factory.begin() as session:
                record = session.execute(
                    select(BrokerModel)
                    .join(UserBrokerModel, UserBrokerModel.broker_id == BrokerModel.id)
                    .where(BrokerModel.id == broker_id, UserBrokerModel.user_id == user_id)
                    .with_for_update(),
                ).scalar_one_or_none()
                if record is None:
                    existing_id = session.scalar(select(BrokerModel.id).where(BrokerModel.id == broker_id))
                    if existing_id is None:
                        raise BrokerNotFoundError("Broker not found")
                    raise BrokerAccessDeniedError("You are not a member of this broker")
                record.status = BrokerStatus.ACTIVE
                record.activated_at = datetime.now(UTC).replace(tzinfo=None)
                return DomainBrokerModel(
                    id=record.id,
                    status=record.status,
                    created_at=record.created_at.replace(tzinfo=UTC),
                    activated_at=record.activated_at.replace(tzinfo=UTC),
                )
        except SQLAlchemyError:
            raise PersistenceError("Unable to activate broker") from None