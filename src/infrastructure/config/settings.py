from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True)

    AWS_REGION: str 

    COGNITO_CLIENT_ID: str = Field(min_length=1)
    COGNITO_CLIENT_SECRET: SecretStr = Field(min_length=1)


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True)

    DATABASE_URL: SecretStr = Field(min_length=1)
