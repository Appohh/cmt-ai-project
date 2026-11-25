"""Public schemas and request payloads for AuthComponent."""

from __future__ import annotations

import uuid
from sqlmodel import SQLModel


class UserPublic(SQLModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    affiliation: str | None = None
    expertise: str | None = None
    roles: list[str]


class RegisterRequest(SQLModel):
    first_name: str
    last_name: str
    email: str
    password: str
    affiliation: str | None = None
    expertise: str | None = None


class LoginRequest(SQLModel):
    email: str
    password: str


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
