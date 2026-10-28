from domain.models.policy import PolicyModel
from domain.repositories.policy import PolicyRepository


class PolicyService:
    def __init__(self, policy_repository: PolicyRepository) -> None:
        self.policy_repository = policy_repository

    def list_for_brokers(
        self,
        broker_ids: list[str],
        customer_id: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[PolicyModel], int]:
        return self.policy_repository.list_for_brokers(
            broker_ids=broker_ids,
            customer_id=customer_id,
            offset=offset,
            limit=limit,
        )