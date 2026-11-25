"""Schemas for AIReviewMatchComponent endpoints."""

from __future__ import annotations

import uuid
from sqlmodel import SQLModel


class ReviewerRecommendationPublic(SQLModel):
    reviewer_id: str
    score: float
    status: str = "recommended"
    confirmed: bool = False
    name: str | None = None
    affiliation: str | None = None
    expertise: str | None = None
    active_reviews: int = 0
    already_assigned: bool = False


class AIMatchResponse(SQLModel):
    submission_id: uuid.UUID
    provider: str
    recommendations: list[ReviewerRecommendationPublic]
