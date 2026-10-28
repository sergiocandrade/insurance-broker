from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from domain.models.policy import PolicyModel as DomainPolicyModel
from domain.models.insurance_product import InsuranceProductModel as DomainInsuranceProductModel
from domain.models.insurance_branch import InsuranceBranchModel as DomainInsuranceBranchModel
from domain.models.insurance_category import InsuranceCategoryModel as DomainInsuranceCategoryModel
from domain.models.insurer import InsurerModel as DomainInsurerModel
from infrastructure.persistence.exceptions import PersistenceError
from infrastructure.persistence.sqlalchemy.models import (
    CustomerModel,
    InsuranceBranchModel,
    InsuranceCategoryModel,
    InsuranceProductModel,
    InsurerModel as SqlInsurerModel,
    PolicyModel,
)


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

                query = select(
                    PolicyModel, InsuranceProductModel, InsuranceBranchModel, InsuranceCategoryModel,
                    SqlInsurerModel,
                ).join(
                    CustomerModel,
                    CustomerModel.id == PolicyModel.customer_id,
                ).join(
                    InsuranceProductModel,
                    InsuranceProductModel.id == PolicyModel.insurance_product_id,
                ).join(
                    InsuranceBranchModel,
                    InsuranceBranchModel.id == InsuranceProductModel.branch_id,
                ).join(
                    InsuranceCategoryModel,
                    InsuranceCategoryModel.id == InsuranceBranchModel.category_id,
                ).outerjoin(
                    SqlInsurerModel,
                    SqlInsurerModel.id == PolicyModel.insurer_id,
                ).where(*conditions)
                total = session.scalar(
                    select(func.count()).select_from(query.subquery()),
                ) or 0
                records = session.execute(
                    query.order_by(PolicyModel.policy_number, PolicyModel.id)
                    .offset(offset)
                    .limit(limit),
                ).all()
                policies = [
                    DomainPolicyModel(
                        id=policy.id,
                        customer_id=policy.customer_id,
                        amount=policy.amount,
                        insurance_product_id=policy.insurance_product_id,
                        insurer_id=policy.insurer_id,
                        policy_number=policy.policy_number,
                        start_date=policy.start_date,
                        end_date=policy.end_date,
                        status=policy.status,
                        created_at=(
                            policy.created_at.replace(tzinfo=UTC)
                            if policy.created_at.tzinfo is None
                            else policy.created_at.astimezone(UTC)
                        ),
                        insurance_product=DomainInsuranceProductModel(
                            id=product.id,
                            branch_id=product.branch_id,
                            name=product.name,
                            product_code=product.product_code,
                            created_at=(
                                product.created_at.replace(tzinfo=UTC)
                                if product.created_at.tzinfo is None
                                else product.created_at.astimezone(UTC)
                            ),
                            insurance_branch=DomainInsuranceBranchModel(
                                id=branch.id,
                                category_id=branch.category_id,
                                name=branch.name,
                                created_at=(
                                    branch.created_at.replace(tzinfo=UTC)
                                    if branch.created_at.tzinfo is None
                                    else branch.created_at.astimezone(UTC)
                                ),
                                insurance_category=DomainInsuranceCategoryModel(
                                    id=category.id,
                                    name=category.name,
                                    created_at=(
                                        category.created_at.replace(tzinfo=UTC)
                                        if category.created_at.tzinfo is None
                                        else category.created_at.astimezone(UTC)
                                    ),
                                ),
                            ),
                        ),
                        insurer=(
                            DomainInsurerModel(
                                id=insurer.id,
                                name=insurer.name,
                                created_at=(
                                    insurer.created_at.replace(tzinfo=UTC)
                                    if insurer.created_at.tzinfo is None
                                    else insurer.created_at.astimezone(UTC)
                                ),
                            )
                            if insurer is not None
                            else None
                        ),
                    )
                    for policy, product, branch, category, insurer in records
                ]
                return policies, total
        except SQLAlchemyError:
            raise PersistenceError("Unable to load policies") from None