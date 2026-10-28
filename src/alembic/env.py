from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

config = context.config
cmd_url = context.get_x_argument(as_dictionary=True).get("db_url")
config_url = context.config.get_main_option("sqlalchemy.url")
db_url = cmd_url or config_url

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from infrastructure.persistence.sqlalchemy.models import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    if not db_url:
        raise ValueError(
            "No DB URL configured. Provide -x db_url=... or set sqlalchemy.url in alembic.ini"
        )

    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not db_url:
        raise ValueError(
            "No DB URL configured. Provide -x db_url=... or set sqlalchemy.url in alembic.ini"
        )

    connectable = create_engine(db_url)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
