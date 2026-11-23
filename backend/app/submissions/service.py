"""Paper submission and double-blind anonymization service stubs."""

from datetime import datetime


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
    raise NotImplementedError("TDD stub: implement to pass unit test")


def anonymize_submission_for_reviewer(submission: dict) -> dict:
    """Strip author and co-author identifying metadata for double-blind review."""
    raise NotImplementedError("TDD stub: implement to pass unit test")
