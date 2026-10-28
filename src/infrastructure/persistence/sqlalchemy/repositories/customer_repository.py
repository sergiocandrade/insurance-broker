from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.models.customer import CustomerModel as DomainCustomerModel
from infrastructure.persistence.exceptions import PersistenceError
from infrastructure.persistence.sqlalchemy.models import CustomerModel


class SqlAlchemyCustomerRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get_customer_by_id(self, customer_id: str) -> DomainCustomerModel | None:
        try:
            with self.session_factory() as session:
                record = session.execute(
                    select(CustomerModel).where(CustomerModel.id == customer_id),
                ).scalar_one_or_none()
                return self._to_domain(record) if record is not None else None
        except SQLAlchemyError:
            raise PersistenceError("Unable to load customer") from None

    def belongs_to_broker(self, customer_id: str, broker_id: str) -> bool:
        try:
            with self.session_factory() as session:
                customer = session.scalar(
                    select(CustomerModel.id)
                    .where(CustomerModel.id == customer_id, CustomerModel.broker_id == broker_id)
                    .limit(1),
                )
                return customer is not None
        except SQLAlchemyError:
            raise PersistenceError("Unable to verify customer broker access") from None

    def list_by_broker(self, broker_id: str, offset: int, limit: int) -> tuple[list[DomainCustomerModel], int]:
        return self.list_by_brokers(broker_ids=[broker_id], offset=offset, limit=limit)

    def list_by_brokers(
        self,
        broker_ids: list[str],
        offset: int,
        limit: int,
    ) -> tuple[list[DomainCustomerModel], int]:
        try:
            with self.session_factory() as session:
                conditions = CustomerModel.broker_id.in_(broker_ids)
                total = session.scalar(select(func.count()).select_from(CustomerModel).where(conditions)) or 0
                records = session.scalars(
                    select(CustomerModel)
                    .where(conditions)
                    .order_by(CustomerModel.name, CustomerModel.id)
                    .offset(offset)
                    .limit(limit),
                ).all()
                customers = [self._to_domain(record) for record in records]
                return customers, total
        except SQLAlchemyError:
            raise PersistenceError("Unable to load broker customers") from None

    @staticmethod
    def _to_domain(record: CustomerModel) -> DomainCustomerModel:
        created_at = (
            record.created_at.replace(tzinfo=UTC)
            if record.created_at.tzinfo is None
            else record.created_at.astimezone(UTC)
        )
        return DomainCustomerModel(
            id=record.id,
            name=record.name,
            customer_type=record.customer_type,
            phone=record.phone,
            email=record.email,
            broker_id=record.broker_id,
            created_at=created_at,
        )