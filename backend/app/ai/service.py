"""AI-assisted reviewer matching and topic tag generation (SEC-05 + NFR-04)."""

from __future__ import annotations

from typing import Any

from app.ai.providers import get_matching_provider

_SAFE_SUBMISSION_KEYS = {"id", "title", "abstract", "topics"}
_SAFE_CANDIDATE_KEYS = {"reviewer_id", "expertise", "past_topics"}


def _strip_submission_pii(submission: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in submission.items() if k in _SAFE_SUBMISSION_KEYS}


def _strip_candidate_pii(candidate: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in candidate.items() if k in _SAFE_CANDIDATE_KEYS}


def recommend_reviewers(
    submission: dict,
    candidate_reviewers: list[dict],
) -> list[dict]:
    """Generate ranked reviewer recommendations requiring explicit human confirmation."""
    safe_submission = _strip_submission_pii(submission)
    safe_candidates = [_strip_candidate_pii(c) for c in candidate_reviewers]

    _provider_name, provider = get_matching_provider()
    scored = provider.score_candidates(safe_submission, safe_candidates)
    scored.sort(key=lambda item: float(item["score"]), reverse=True)

    return [
        {
            "reviewer_id": item["reviewer_id"],
            "score": float(item["score"]),
            "status": "recommended",
            "confirmed": False,
        }
        for item in scored
    ]


def generate_topic_tags(
    text: str,
    max_tags: int = 4,
    provider_override: str | None = None,
) -> tuple[str, list[str]]:
    """Generate concise academic topic tags from PII-free text via LLMProviderComponent."""
    clean_text = (text or "").strip()
    if not clean_text:
        return "local", []

    provider_name, provider = get_matching_provider(override_provider=provider_override)
    tags = provider.generate_tags(clean_text, max_tags=max_tags)
    if getattr(provider, "last_fallback_used", False):
        provider_name = f"{provider_name} → local fallback"
    return provider_name, tags


def generate_bulk_topic_tags(
    items: list[dict[str, str]],
    max_tags: int = 4,
    provider_override: str | None = None,
) -> tuple[str, dict[str, list[str]]]:
    """Generate topic tags for multiple PII-free items in a single batched AI call."""
    safe_items = [
        {"id": str(item["id"]), "text": str(item["text"]).strip()}
        for item in items
        if str(item.get("text", "")).strip()
    ]
    if not safe_items:
        return "local", {}

    provider_name, provider = get_matching_provider(override_provider=provider_override)
    tag_map = provider.generate_bulk_tags(safe_items, max_tags=max_tags)
    if getattr(provider, "last_fallback_used", False):
        provider_name = f"{provider_name} → local fallback"
    return provider_name, tag_map
