"""UserComponent HTTP endpoints: profile management and Admin overview."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.auth.schemas import UserPublic
from app.auth.service import build_user_public
from app.core.database import SessionDep
from app.core.logging import log_action
from app.core.security import (
    AuthenticatedUser,
    get_current_user,
    hash_password,
    normalize_role,
    require_roles,
    verify_password,
)
from app.models.models import (
    Conference,
    Invitation,
    InvitationStatus,
    Review,
    Role,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)
from app.users.schemas import (
    AdminCounts,
    AdminOverviewResponse,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    UpdateUserRolesRequest,
)

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserPublic)
def get_my_profile(auth: AuthenticatedUser = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return build_user_public(auth.user, auth.roles)


@router.patch("/users/me", response_model=UserPublic)
def update_my_profile(
    payload: ProfileUpdateRequest,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Update personal details (name, email, affiliation, expertise) for the caller."""
    user = auth.user

    if payload.first_name is not None:
        stripped = payload.first_name.strip()
        if not stripped:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="First name cannot be empty",
            )
        user.first_name = stripped

    if payload.last_name is not None:
        stripped = payload.last_name.strip()
        if not stripped:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Last name cannot be empty",
            )
        user.last_name = stripped

    if payload.email is not None:
        normalized_email = payload.email.strip().lower()
        if not normalized_email or "@" not in normalized_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valid email is required",
            )
        if normalized_email != user.email:
            conflict = session.exec(select(User).where(User.email == normalized_email)).first()
            if conflict is not None and conflict.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email is already registered to another account",
                )
            user.email = normalized_email

    if payload.affiliation is not None:
        user.affiliation = payload.affiliation.strip() or None

    if payload.expertise is not None:
        user.expertise = payload.expertise.strip() or None

    session.add(user)
    session.commit()
    session.refresh(user)

    log_action("users.profile_updated", actor_id=user.id)
    return build_user_public(user, auth.roles)


@router.post("/users/me/password")
def change_my_password(
    payload: PasswordChangeRequest,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(get_current_user),
):
    """Change the authenticated user's password after verifying the current password."""
    if not verify_password(payload.current_password, auth.user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long",
        )

    auth.user.password_hash = hash_password(payload.new_password)
    session.add(auth.user)
    session.commit()

    log_action("users.password_changed", actor_id=auth.user.id)
    return {"status": "password_updated"}


@router.get("/admin/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.admin)),
):
    """Return read-only system metrics and user directory for administrators."""
    users = session.exec(select(User).order_by(User.created_at)).all()
    role_rows = session.exec(select(UserRole)).all()
    roles_by_user: dict = {}
    for row in role_rows:
        roles_by_user.setdefault(row.user_id, []).append(row.role)

    conferences = session.exec(select(Conference)).all()
    invitations = session.exec(select(Invitation)).all()
    submissions = session.exec(select(Submission)).all()
    reviews = session.exec(select(Review)).all()

    reviewer_ids = {
        row.user_id for row in role_rows if row.role == Role.reviewer
    }
    open_invites = sum(1 for inv in invitations if inv.status == InvitationStatus.invited)
    accepted_submissions = sum(
        1 for sub in submissions if sub.status == SubmissionStatus.accepted
    )
    active_reviews = [r for r in reviews if r.status != InvitationStatus.declined]
    completed_reviews = sum(1 for r in active_reviews if r.score is not None)
    missing_reviews = len(active_reviews) - completed_reviews

    user_directory = [
        build_user_public(u, roles_by_user.get(u.id, [Role.author]))
        for u in users
    ]

    log_action("admin.overview_viewed", actor_id=auth.user.id)
    return AdminOverviewResponse(
        database_connected=True,
        counts=AdminCounts(
            users=len(users),
            reviewers=len(reviewer_ids),
            conferences=len(conferences),
            open_invites=open_invites,
            submissions=len(submissions),
            accepted_submissions=accepted_submissions,
            completed_reviews=completed_reviews,
            total_reviews=len(active_reviews),
            missing_reviews=missing_reviews,
        ),
        users=user_directory,
    )


@router.put("/admin/users/{user_id}/roles", response_model=UserPublic)
def update_user_roles(
    user_id: uuid.UUID,
    payload: UpdateUserRolesRequest,
    session: SessionDep,
    auth: AuthenticatedUser = Depends(require_roles(Role.admin)),
):
    """Update assigned roles for a user account (US-24 / FR-08)."""
    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    parsed_roles: list[Role] = []
    seen: set[Role] = set()
    for raw_role in payload.roles:
        try:
            role_enum = Role(normalize_role(raw_role))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{raw_role}'",
            ) from exc
        if role_enum not in seen:
            seen.add(role_enum)
            parsed_roles.append(role_enum)

    if not parsed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user must have at least one assigned role",
        )

    if target_user.id == auth.user.id and Role.admin not in parsed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own Admin role",
        )

    existing_rows = session.exec(
        select(UserRole).where(UserRole.user_id == target_user.id)
    ).all()
    for row in existing_rows:
        session.delete(row)
    session.flush()

    for role_enum in parsed_roles:
        session.add(UserRole(user_id=target_user.id, role=role_enum))
    session.commit()

    log_action(
        "admin.roles_updated",
        actor_id=auth.user.id,
        target_id=target_user.id,
        details={"roles": sorted(r.value for r in parsed_roles)},
    )
    return build_user_public(target_user, parsed_roles)
