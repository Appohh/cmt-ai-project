"""Paper submission and double-blind anonymization service functions."""

from __future__ import annotations

from datetime import datetime

from app.core.config import ensure_utc
from app.core.security import validate_pdf_upload
from app.models.models import SubmissionStatus

_ANONYMIZATION_FORBIDDEN_KEYS = {
    "author_id",
    "author_name",
    "author_email",
    "author",
    "affiliation",
    "author_affiliation",
    "co_authors",
    "first_name",
    "last_name",
    "email",
}


class DeadlinePassedError(Exception):
    """Raised when a submission action is attempted after the conference deadline."""


def submit_paper(
    title: str,
    abstract: str,
    co_authors: list[dict],
    pdf_bytes: bytes,
    submitted_at: datetime,
    submission_deadline: datetime,
) -> dict:
    """Submit a paper before the submission deadline."""
    if ensure_utc(submitted_at) > ensure_utc(submission_deadline):
        raise DeadlinePassedError("Submission deadline has already passed")

    if not title or not title.strip():
        raise ValueError("Paper title is required")
    if not abstract or not abstract.strip():
        raise ValueError("Paper abstract is required")

    validate_pdf_upload("paper.pdf", "application/pdf", pdf_bytes)

    return {
        "title": title.strip(),
        "abstract": abstract.strip(),
        "co_authors": list(co_authors),
        "status": SubmissionStatus.submitted.value,
        "submitted_at": ensure_utc(submitted_at),
    }


def anonymize_submission_for_reviewer(submission: dict) -> dict:
    """Strip author and co-author identifying metadata for double-blind review."""
    return {
        key: value
        for key, value in submission.items()
        if key not in _ANONYMIZATION_FORBIDDEN_KEYS
    }
