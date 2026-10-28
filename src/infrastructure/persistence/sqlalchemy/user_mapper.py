from datetime import UTC

from domain.models.user import UserModel as DomainUserModel, UserStatus
from infrastructure.persistence.sqlalchemy.models.user_model import UserModel as SqlAlchemyUserModel


class UserMapper:
    @staticmethod
    def to_domain(model: SqlAlchemyUserModel) -> DomainUserModel:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        else:
            created_at = created_at.astimezone(UTC)
        return DomainUserModel(
            id=model.id,
            email=model.email,
            external_id=model.external_id,
            status=UserStatus(model.status),
            created_at=created_at,
        )

    @staticmethod
    def to_model(user: DomainUserModel) -> SqlAlchemyUserModel:
        return SqlAlchemyUserModel(
            id=user.id,
            email=user.email,
            external_id=user.external_id,
            status=user.status,
            created_at=user.created_at.astimezone(UTC).replace(tzinfo=None),
        )