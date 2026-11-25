"""Schemas for ReviewComponent endpoints (strictly double-blind for reviewers)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field
from sqlmodel import SQLModel


class AssignReviewerRequest(SQLModel):
    reviewer_id: uuid.UUID


class ReviewRespondRequest(SQLModel):
    status: Literal["accepted", "declined"]


class ReviewSubmitRequest(SQLModel):
    score: int = Field(ge=1, le=5)
    confidence: int = Field(ge=1, le=5)
    comments: str


class ReviewAssignmentPublic(SQLModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    conference_id: uuid.UUID
    conference_name: str
    title: str
    abstract: str
    review_deadline: datetime
    status: str
    score: int | None = None
    confidence: int | None = None
    comments: str | None = None
    can_review: bool = False


class BlindSubmissionPublic(SQLModel):
    id: uuid.UUID
    conference_id: uuid.UUID
    title: str
    abstract: str
    status: str
    review_id: uuid.UUID
    review_status: str
    score: int | None = None
    confidence: int | None = None
    comments: str | None = None
