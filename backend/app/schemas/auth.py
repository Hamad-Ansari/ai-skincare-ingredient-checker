"""Authentication request and response schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _normalize_email(value: EmailStr) -> str:
    return str(value).strip().casefold()


class RegisterRequest(BaseModel):
    """New-account payload; password is accepted only over an HTTPS deployment."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_address(cls, value: EmailStr) -> str:
        return _normalize_email(value)

    @field_validator("password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password must contain a non-whitespace character")
        if len(value.encode("utf-8")) > 1024:
            raise ValueError("Password is too long")
        return value


class LoginRequest(BaseModel):
    """Login credentials."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_address(cls, value: EmailStr) -> str:
        return _normalize_email(value)


class AuthUserRead(BaseModel):
    """Public current-user fields; never contains password or token material."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str | None
    email_verified_at: datetime
    created_at: datetime


class CsrfTokenResponse(BaseModel):
    csrf_token: str
    expires_in_seconds: int


class RegistrationResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    message: str = "If the address is available, verification instructions will be sent."
    dev_verification_token: str | None = None


class AuthMessageResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    message: str
    dev_token: str | None = None


class LoginResponse(BaseModel):
    user: AuthUserRead
    csrf_token: str
    csrf_expires_in_seconds: int


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_address(cls, value: EmailStr) -> str:
        return _normalize_email(value)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_address(cls, value: EmailStr) -> str:
        return _normalize_email(value)


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password must contain a non-whitespace character")
        if len(value.encode("utf-8")) > 1024:
            raise ValueError("Password is too long")
        return value


class AccountDeletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128)
