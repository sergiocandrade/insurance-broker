from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints, field_validator


CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str


class SignInRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=256)


class SignUpRequest(BaseModel):
    email: EmailStr = Field(max_length=128)
    phone: str = Field(min_length=8, max_length=32, pattern=r"^\+?[0-9 ()-]+$")
    region: str = Field(min_length=1, max_length=128)
    insurance_categories: list[CategoryName] = Field(min_length=1, max_length=50)

    @field_validator("insurance_categories", mode="before")
    @classmethod
    def split_categories(cls, value: object) -> object:
        if isinstance(value, str):
            return [category for category in value.split(",") if category.strip()]
        return value


class SignUpResponse(BaseModel):
    id: str
    created_at: datetime


class NewPasswordRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=1, max_length=256)
    session: SecretStr = Field(min_length=1, max_length=2048)
    required_attributes: dict[str, str] = Field(default_factory=dict)


class PasswordResetRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)


class ConfirmPasswordResetRequest(PasswordResetRequest):
    code: SecretStr = Field(min_length=1, max_length=2048)
    new_password: SecretStr = Field(min_length=1, max_length=256)


class PasswordResetResponse(BaseModel):
    message: str


class SignInTokens(BaseModel):
    access_token: str
    id_token: str
    refresh_token: str | None = None
    token_type: str
    expires_in: int


class SignInChallenge(BaseModel):
    challenge_name: str
    challenge_parameters: dict[str, str]
    session: str