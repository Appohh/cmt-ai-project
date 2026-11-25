"""Schemas for ConferenceComponent and Invitation endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlmodel import SQLModel


class ConferencePublic(SQLModel):
    id: uuid.UUID
    name: str
    description: str | None
    submission_deadline: datetime
    review_deadline: datetime
    notification_deadline: datetime


class ConferenceCreate(SQLModel):
    name: str
    description: str | None = None
    submission_deadline: datetime
    review_deadline: datetime
    notification_deadline: datetime


class ChairReviewBrief(SQLModel):
    review_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_name: str
    status: str
    score: int | None = None
    confidence: int | None = None
    comments: str | None = None


class ChairSubmissionItem(SQLModel):
    id: uuid.UUID
    title: str
    abstract: str
    author_id: uuid.UUID
    author_name: str
    co_author_names: list[str]
    status: str
    average_score: float | None = None
    topic_tags: list[str] = []
    reviews: list[ChairReviewBrief]


class ChairProgressSummary(SQLModel):
    completed_reviews: int
    total_reviews: int
    missing_reviews: int
    unassigned_papers: int


class ChairSubmissionsResponse(SQLModel):
    conference_id: uuid.UUID
    summary: ChairProgressSummary
    submissions: list[ChairSubmissionItem]


class CommitteeMemberPublic(SQLModel):
    id: uuid.UUID
    name: str
    email: str
    affiliation: str | None = None
    expertise: str | None = None
    topic_tags: list[str] = []
    roles: list[str]
    completed_reviews: int
    total_assigned: int


class InvitationPublic(SQLModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime


class ConferenceCommitteeResponse(SQLModel):
    members: list[CommitteeMemberPublic]
    invitations: list[InvitationPublic]


class InvitationCreate(SQLModel):
    email: str
    role: Literal["reviewer", "guest"] = "reviewer"


class InvitationCreatedResponse(SQLModel):
    invitation: InvitationPublic
    raw_token: str
    invite_link: str


class InvitationAcceptRequest(SQLModel):
    token: str


class InvitationAcceptResponse(SQLModel):
    status: str
    role_granted: str
    conference_id: uuid.UUID
    roles: list[str]
