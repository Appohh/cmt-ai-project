"""Schemas for AIReviewMatchComponent, AI Topic Tags, and LLMProviderComponent."""

from __future__ import annotations

import uuid
from typing import Literal

from sqlmodel import SQLModel


class ReviewerRecommendationPublic(SQLModel):
    reviewer_id: str
    score: float
    status: str = "recommended"
    confirmed: bool = False
    name: str | None = None
    affiliation: str | None = None
    expertise: str | None = None
    topic_tags: list[str] = []
    active_reviews: int = 0
    already_assigned: bool = False


class AIMatchResponse(SQLModel):
    submission_id: uuid.UUID
    provider: str
    recommendations: list[ReviewerRecommendationPublic]


class AIProviderStatusResponse(SQLModel):
    active_provider: str
    available_providers: list[str]
    ollama_base_url: str
    ollama_model: str
    ollama_reachable: bool
    gemini_model: str
    gemini_configured: bool
    openai_model: str
    openai_configured: bool


class AIProviderUpdateRequest(SQLModel):
    provider: Literal["local", "ollama", "gemini", "openai"] | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None


class EntityTagsResponse(SQLModel):
    entity_type: str
    entity_id: uuid.UUID
    provider: str
    tags: list[str]


class BulkTagsResponse(SQLModel):
    conference_id: uuid.UUID
    provider: str
    submissions_tagged: int
    reviewers_tagged: int
