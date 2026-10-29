from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, inspect, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from infrastructure.persistence.sqlalchemy.models import Base, UserModel
from infrastructure.persistence.sqlalchemy.user_mapper import UserMapper
from presentation.apis.bff.dtos.auth import CurrentUserResponse


class NullableUserExternalIdTests(unittest.TestCase):
    def test_user_without_external_id_persists_and_maps_to_domain(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            Base.metadata.create_all(engine)
            sessions = sessionmaker(bind=engine, expire_on_commit=False)
            with sessions.begin() as session:
                session.add(UserModel(
                    id="local-id", email="user@example.com", name="Example User", created_at=datetime(2026, 10, 27),
                ))
            with sessions() as session:
                record = session.get(UserModel, "local-id")
                self.assertIsNone(record.external_id)
                user = UserMapper.to_domain(record)
                self.assertIsNone(user.external_id)
                self.assertEqual(user.name, "Example User")
                self.assertIsNone(UserMapper.to_model(user).external_id)
                response = CurrentUserResponse.model_validate(user).model_dump()
                self.assertEqual(response, {"name": "Example User", "email": "user@example.com"})
        finally:
            engine.dispose()

    def test_mysql_schema_keeps_external_id_nullable_and_indexed(self) -> None:
        statement = str(CreateTable(UserModel.__table__).compile(dialect=mysql.dialect()))

        self.assertIn("external_id VARCHAR(36)", statement)
        self.assertNotIn("external_id VARCHAR(36) NOT NULL", statement)
        self.assertTrue(UserModel.__table__.c.external_id.nullable)
        index = next(index for index in UserModel.__table__.indexes if index.name == "ix_users_external_id")
        self.assertFalse(index.unique)

    def test_migration_preserves_rows_and_guards_downgrade_with_null_values(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = "sqlite+pysqlite:///" + directory + "/external_id.db"
            config = Config(str(Path(__file__).resolve().parents[2] / "src/alembic/alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "99068bc3191e")
            engine = create_engine(database_url)
            try:
                users = Table("users", MetaData(), autoload_with=engine)
                with engine.begin() as connection:
                    connection.execute(users.insert().values(
                        id="existing-user", email="existing@example.com", name="Existing User",
                        external_id="existing-cognito-sub", created_at=datetime(2026, 10, 27),
                    ))

                command.upgrade(config, "head")
                engine.dispose()

                columns = {column["name"]: column for column in inspect(engine).get_columns("users")}
                self.assertTrue(columns["external_id"]["nullable"])
                self.assertIn("ix_users_external_id", {index["name"] for index in inspect(engine).get_indexes("users")})
                with engine.begin() as connection:
                    connection.execute(users.insert().values(
                        id="new-user", email="new@example.com", name="New User",
                        external_id=None, created_at=datetime(2026, 10, 27),
                    ))

                with self.assertRaisesRegex(RuntimeError, "Populate all NULL"):
                    command.downgrade(config, "99068bc3191e")

                with engine.begin() as connection:
                    self.assertEqual(len(connection.execute(select(users.c.id)).all()), 2)
                    self.assertEqual(connection.execute(
                        select(users.c.external_id).where(users.c.id == "existing-user"),
                    ).scalar_one(), "existing-cognito-sub")
                    connection.execute(users.update().where(users.c.id == "new-user").values(external_id="new-cognito-sub"))

                command.downgrade(config, "99068bc3191e")
                engine.dispose()

                self.assertFalse(next(
                    column for column in inspect(engine).get_columns("users") if column["name"] == "external_id"
                )["nullable"])
                with engine.connect() as connection:
                    self.assertEqual(len(connection.execute(select(users.c.id)).all()), 2)
            finally:
                engine.dispose()