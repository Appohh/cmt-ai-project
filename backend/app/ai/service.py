"""AI-assisted reviewer matching service (SEC-05 PII stripping + NFR-04 human-in-the-loop)."""

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
