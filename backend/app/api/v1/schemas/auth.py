from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import settings


class _AuthCredentialsBase(BaseModel):
    email: EmailStr = Field(max_length=320)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip() if isinstance(value, str) else value


class SignupCredentialsRequest(_AuthCredentialsBase):
    password: str = Field(
        min_length=settings.auth_signup_password_min_length,
        max_length=settings.auth_password_max_length,
    )

    @field_validator("password")
    @classmethod
    def reject_control_only_password(cls, value: str) -> str:
        if all(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("Password cannot contain only control characters.")
        return value


class LoginCredentialsRequest(_AuthCredentialsBase):
    password: str = Field(min_length=1, max_length=settings.auth_password_max_length)


# Temporary import compatibility for consumers that still refer to the old name.
AuthCredentialsRequest = LoginCredentialsRequest


class AuthUserResponse(BaseModel):
    id: str
    email: Optional[str] = None


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: Optional[AuthUserResponse] = None
    message: Optional[str] = None


__all__ = [
    "AuthCredentialsRequest",
    "LoginCredentialsRequest",
    "SignupCredentialsRequest",
    "AuthUserResponse",
    "AuthSessionResponse",
]
