from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from domain.models.user import UserStatus


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    external_id: str | None
    status: UserStatus
    created_at: datetime


class SignInRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=256)


class SignUpRequest(BaseModel):
    email: EmailStr = Field(max_length=128)
    password: SecretStr = Field(min_length=1, max_length=256)


class SignUpResponse(BaseModel):
    user_id: str
    user_confirmed: bool
    # confirmation_destination: str | None = None  # Removed for new implementation
    # confirmation_delivery_medium: str | None = None  # Removed for new implementation


class ConfirmSignUpRequest(BaseModel):
    email: EmailStr = Field(max_length=128)
    code: SecretStr = Field(min_length=1, max_length=2048)


class ConfirmSignUpResponse(BaseModel):
    message: str


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