from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AuthCredentialsRequest(BaseModel):
    email: str
    password: str


class AuthUserResponse(BaseModel):
    id: str
    email: Optional[str] = None


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: Optional[AuthUserResponse] = None
    message: Optional[str] = None


__all__ = [
    "AuthCredentialsRequest",
    "AuthUserResponse",
    "AuthSessionResponse",
]
