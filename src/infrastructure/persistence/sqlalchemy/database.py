from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError

from infrastructure.persistence.exceptions import PersistenceError
from infrastructure.config.settings import DatabaseSettings
from infrastructure.persistence.sqlalchemy.models import Base


def create_database_engine(database_url: str) -> Engine:
    try:
        return create_engine(database_url, pool_pre_ping=True, hide_parameters=True)
    except (SQLAlchemyError, ValueError):
        raise PersistenceError("Unable to configure user database") from None


if __name__ == "__main__":
    settings = DatabaseSettings()
    engine = create_database_engine(settings.DATABASE_URL.get_secret_value())
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()