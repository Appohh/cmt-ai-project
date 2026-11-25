"""Authentication and user account service functions."""

from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.auth.schemas import UserPublic
from app.core.security import hash_password
from app.models.models import Role, User, UserRole


def register_user(
    name: str,
    email: str,
    affiliation: str,
    password: str,
    role: str = "author",
) -> dict:
    """Register a new user account with normalized email and hashed credentials."""
    if not name or not name.strip():
        raise ValueError("Name is required")
    if not email or "@" not in email:
        raise ValueError("Valid email is required")
    if not password:
        raise ValueError("Password is required")

    normalized_email = email.strip().lower()
    hashed = hash_password(password)
    return {
        "name": name.strip(),
        "email": normalized_email,
        "affiliation": affiliation.strip() if affiliation else None,
        "role": role,
        "password_hash": hashed,
    }


def get_user_roles(session: Session, user_id: uuid.UUID) -> list[Role]:
    """Load all roles assigned to the given user."""
    rows = session.exec(select(UserRole).where(UserRole.user_id == user_id)).all()
    return [row.role for row in rows]


def build_user_public(user: User, roles: list[Role]) -> UserPublic:
    """Serialize a User and its roles into a safe public response schema."""
    return UserPublic(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        affiliation=user.affiliation,
        expertise=user.expertise,
        roles=sorted(role.value for role in roles),
    )
