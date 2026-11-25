"""Review assignment, conflict-of-interest, and scoring service functions."""

from __future__ import annotations

import uuid

from app.models.models import InvitationStatus


class ConflictOfInterestError(Exception):
    """Raised when assigning a reviewer with a conflict of interest."""


def assign_reviewer(
    submission: dict,
    reviewer_id: int | str | uuid.UUID,
    reviewer_email: str | None = None,
) -> dict:
    """Assign a reviewer to a submission after checking for conflicts of interest."""
    reviewer_str = str(reviewer_id)
    if submission.get("author_id") is not None and str(submission["author_id"]) == reviewer_str:
        raise ConflictOfInterestError("Primary author cannot be assigned to review their own paper")

    normalized_email = reviewer_email.strip().lower() if reviewer_email else None
    for co_author in submission.get("co_authors", []):
        if co_author.get("id") is not None and str(co_author["id"]) == reviewer_str:
            raise ConflictOfInterestError("Co-author cannot be assigned to review their own paper")
        if co_author.get("user_id") is not None and str(co_author["user_id"]) == reviewer_str:
            raise ConflictOfInterestError("Co-author cannot be assigned to review their own paper")
        if normalized_email and co_author.get("email"):
            if str(co_author["email"]).strip().lower() == normalized_email:
                raise ConflictOfInterestError(
                    "Co-author cannot be assigned to review their own paper"
                )

    return {
        "submission_id": submission.get("id"),
        "reviewer_id": reviewer_id,
        "status": InvitationStatus.invited.value,
    }


def calculate_average_score(reviews: list[dict]) -> float:
    """Calculate the mean numeric score across a non-empty list of reviews."""
    if not reviews:
        raise ValueError("Cannot calculate average score from an empty review list")

    scores = [float(item["score"]) for item in reviews if item.get("score") is not None]
    if not scores:
        raise ValueError("No numeric review scores available")

    return sum(scores) / len(scores)
