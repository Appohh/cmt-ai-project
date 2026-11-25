"""Schemas for UserComponent profile management and Admin overview."""

from __future__ import annotations

from sqlmodel import SQLModel

from app.auth.schemas import UserPublic


class ProfileUpdateRequest(SQLModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    affiliation: str | None = None
    expertise: str | None = None


class PasswordChangeRequest(SQLModel):
    current_password: str
    new_password: str


class UpdateUserRolesRequest(SQLModel):
    roles: list[str]


class AdminCounts(SQLModel):
    users: int
    reviewers: int
    conferences: int
    open_invites: int
    submissions: int
    accepted_submissions: int
    completed_reviews: int
    total_reviews: int
    missing_reviews: int


class AdminOverviewResponse(SQLModel):
    database_connected: bool
    counts: AdminCounts
    users: list[UserPublic]
