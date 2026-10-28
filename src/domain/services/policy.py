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
        limit: int | None,
        customer_ids: list[str] | None = None,
    ) -> tuple[list[PolicyModel], int]:
        return self.policy_repository.list_for_brokers(
            broker_ids=broker_ids,
            customer_id=customer_id,
            offset=offset,
            limit=limit,
            customer_ids=customer_ids,
        )

    def list_for_customers(
        self,
        broker_ids: list[str],
        customer_ids: list[str],
    ) -> list[PolicyModel]:
        policies, _ = self.list_for_brokers(
            broker_ids=broker_ids,
            customer_id=None,
            customer_ids=customer_ids,
            offset=0,
            limit=None,
        )
        return policies