from datetime import UTC

from domain.models.broker import BrokerModel as DomainBrokerModel, BrokerStatus
from infrastructure.persistence.sqlalchemy.models.user_model import BrokerModel as SqlAlchemyBrokerModel


class BrokerMapper:
    @staticmethod
    def to_domain(model: SqlAlchemyBrokerModel) -> DomainBrokerModel:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        else:
            created_at = created_at.astimezone(UTC)
        return DomainBrokerModel(
            id=model.id,
            email=model.email,
            external_id=model.external_id,
            status=BrokerStatus(model.status),
            created_at=created_at,
        )

    @staticmethod
    def to_model(broker: DomainBrokerModel) -> SqlAlchemyBrokerModel:
        return SqlAlchemyBrokerModel(
            id=broker.id,
            email=broker.email,
            external_id=broker.external_id,
            status=broker.status,
            created_at=broker.created_at.astimezone(UTC).replace(tzinfo=None),
        )