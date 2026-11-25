"""Schemas for SubmissionComponent API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlmodel import SQLModel


class CoAuthorIn(SQLModel):
    name: str
    email: str
    affiliation: str | None = None


class CoAuthorPublic(SQLModel):
    id: uuid.UUID
    name: str
    email: str
    affiliation: str | None = None


class SubmissionPublic(SQLModel):
    id: uuid.UUID
    conference_id: uuid.UUID
    conference_name: str | None = None
    author_id: uuid.UUID
    title: str
    abstract: str
    status: str
    co_authors: list[CoAuthorPublic] = []
    decision_released: bool = False
    can_edit: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DecisionRequest(SQLModel):
    status: Literal["accepted", "rejected"]


class ReleasedReviewPublic(SQLModel):
    id: uuid.UUID
    score: int | None = None
    confidence: int | None = None
    comments: str | None = None
    reviewer_name: str | None = None


class SubmissionReviewsResponse(SQLModel):
    submission_id: uuid.UUID
    status: str
    average_score: float | None = None
    reviews: list[ReleasedReviewPublic]
