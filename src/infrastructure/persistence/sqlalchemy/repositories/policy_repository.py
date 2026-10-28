from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.models.policy import PolicyModel as DomainPolicyModel
from infrastructure.persistence.exceptions import PersistenceError
from infrastructure.persistence.sqlalchemy.models import CustomerModel, PolicyModel


class SqlAlchemyPolicyRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def list_for_brokers(
        self,
        broker_ids: list[str],
        customer_id: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[DomainPolicyModel], int]:
        try:
            with self.session_factory() as session:
                conditions = [CustomerModel.broker_id.in_(broker_ids)]
                if customer_id is not None:
                    conditions.append(PolicyModel.customer_id == customer_id)

                query = select(PolicyModel).join(
                    CustomerModel,
                    CustomerModel.id == PolicyModel.customer_id,
                ).where(*conditions)
                total = session.scalar(
                    select(func.count()).select_from(query.subquery()),
                ) or 0
                records = session.scalars(
                    query.order_by(PolicyModel.policy_number, PolicyModel.id)
                    .offset(offset)
                    .limit(limit),
                ).all()
                policies = [
                    DomainPolicyModel(
                        id=record.id,
                        customer_id=record.customer_id,
                        amount=record.amount,
                        insurance_product_id=record.insurance_product_id,
                        policy_number=record.policy_number,
                        start_date=record.start_date,
                        end_date=record.end_date,
                        status=record.status,
                        created_at=(
                            record.created_at.replace(tzinfo=UTC)
                            if record.created_at.tzinfo is None
                            else record.created_at.astimezone(UTC)
                        ),
                    )
                    for record in records
                ]
                return policies, total
        except SQLAlchemyError:
            raise PersistenceError("Unable to load policies") from None