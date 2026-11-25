"""AuthComponent HTTP endpoints: register, login, logout (JTI revocation), and me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.auth.service import build_user_public, get_user_roles
from app.core.database import SessionDep
from app.core.logging import log_action
from app.core.security import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
    hash_password,
    revoke_token,
    verify_password,
)
from app.models.models import Role, User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(user: User, roles: list[Role]) -> TokenResponse:
    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "roles": [role.value for role in roles],
        }
    )
    return TokenResponse(access_token=token, user=build_user_public(user, roles))


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def register(payload: RegisterRequest, session: SessionDep):
    """Create a new user account with the default author role and return a JWT."""
    normalized_email = payload.email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid email is required")
    if not payload.first_name.strip() or not payload.last_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="First name and last name are required",
        )
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    existing = session.exec(select(User).where(User.email == normalized_email)).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        affiliation=payload.affiliation.strip() if payload.affiliation else None,
        expertise=payload.expertise.strip() if payload.expertise else None,
    )
    session.add(user)
    session.flush()

    default_role = UserRole(user_id=user.id, role=Role.author)
    session.add(default_role)
    session.commit()
    session.refresh(user)

    log_action("auth.register", actor_id=user.id, details={"email": user.email})
    return _issue_token(user, [Role.author])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDep):
    """Authenticate credentials and issue a signed HS256 Bearer token."""
    normalized_email = payload.email.strip().lower()
    user = session.exec(select(User).where(User.email == normalized_email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        log_action("auth.login_failed", details={"email": normalized_email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    roles = get_user_roles(session, user.id)
    if not roles:
        roles = [Role.author]

    log_action("auth.login", actor_id=user.id)
    return _issue_token(user, roles)


@router.post("/logout")
def logout(auth: AuthenticatedUser = Depends(get_current_user)):
    """Revoke the caller's active JWT jti immediately on the server."""
    jti = auth.token_payload.get("jti")
    exp = auth.token_payload.get("exp")
    if jti:
        revoke_token(str(jti), exp)
    log_action("auth.logout", actor_id=auth.user.id)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserPublic)
def me(auth: AuthenticatedUser = Depends(get_current_user)):
    """Return the authenticated user's profile and active roles."""
    return build_user_public(auth.user, auth.roles)
