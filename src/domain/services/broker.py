from datetime import UTC, datetime

from domain.exceptions.broker import BrokerAlreadyActiveException
from domain.models.broker import BrokerModel, BrokerStatus
from domain.repositories.broker import BrokerRepository


class BrokerService:
    def __init__(self, broker_repository: BrokerRepository) -> None:
        self.broker_repository = broker_repository

    def list_brokers_for_user(self, user_id: str) -> list[BrokerModel]:
        return self.broker_repository.list_brokers_for_user(user_id=user_id)


    def activate(self, broker: BrokerModel, user_id: str) -> BrokerModel:
        if broker.status == BrokerStatus.ACTIVE:
            raise BrokerAlreadyActiveException()

        broker.status = BrokerStatus.ACTIVE
        broker.activated_at = datetime.now(UTC)
        
        return self.broker_repository.activate(broker_id=broker.id, user_id=user_id)