"""Functional unit tests for core Conference Management Tool features."""

from datetime import timedelta

import pytest

from app.ai.service import recommend_reviewers
from app.auth.service import register_user
from app.conferences.service import create_conference
from app.reviews.service import calculate_average_score
from app.submissions.service import DeadlinePassedError, submit_paper


@pytest.mark.unit
def test_user_registration_creates_account() -> None:
    """US-01 / FR-01: User registration normalizes email and hides plaintext password."""
    account = register_user(
        name="Ada Lovelace",
        email="ADA@Example.COM",
        affiliation="TU Delft",
        password="StrongPassword123!",
    )

    assert account["name"] == "Ada Lovelace"
    assert account["email"] == "ada@example.com"
    assert account["affiliation"] == "TU Delft"
    assert account["role"] == "author"
    assert "password" not in account
    assert "StrongPassword123!" not in account.values()


@pytest.mark.unit
def test_conference_creation_validates_deadline_order(
    conference_deadlines: dict,
) -> None:
    """US-11 / FR-04 / NFR-03: Conference deadlines must be chronologically ordered."""
    conference = create_conference(
        name="CMT AI Symposium 2026",
        description="Annual conference on AI-assisted research workflows.",
        submission_deadline=conference_deadlines["submission_deadline"],
        review_deadline=conference_deadlines["review_deadline"],
        notification_deadline=conference_deadlines["notification_deadline"],
    )

    assert conference["name"] == "CMT AI Symposium 2026"

    with pytest.raises(ValueError):
        create_conference(
            name="Invalid Deadline Conference",
            description="Review deadline precedes submission deadline.",
            submission_deadline=conference_deadlines["submission_deadline"],
            review_deadline=conference_deadlines["submission_deadline"] - timedelta(days=1),
            notification_deadline=conference_deadlines["notification_deadline"],
        )


@pytest.mark.unit
def test_paper_submission_rejected_after_deadline(
    conference_deadlines: dict,
    valid_pdf_bytes: bytes,
) -> None:
    """US-03 / US-04 / FR-02 / NFR-03: Submissions after the deadline are rejected."""
    submission_deadline = conference_deadlines["submission_deadline"]
    late_timestamp = submission_deadline + timedelta(minutes=1)

    with pytest.raises(DeadlinePassedError):
        submit_paper(
            title="Late Research Submission",
            abstract="Paper submitted one minute after the configured deadline.",
            co_authors=[],
            pdf_bytes=valid_pdf_bytes,
            submitted_at=late_timestamp,
            submission_deadline=submission_deadline,
        )


@pytest.mark.unit
def test_review_average_score_calculation() -> None:
    """US-10 / US-15 / FR-03: Average score calculation returns exact mean and guards empty input."""
    reviews = [
        {"score": 4, "confidence": 5},
        {"score": 2, "confidence": 3},
        {"score": 3, "confidence": 4},
    ]

    average = calculate_average_score(reviews)
    assert average == pytest.approx(3.0)

    with pytest.raises(ValueError):
        calculate_average_score([])


@pytest.mark.unit
def test_ai_reviewer_matching_requires_human_confirmation() -> None:
    """US-21 / FR-06 / NFR-04: AI recommendations are ranked and unconfirmed by default."""
    submission_context = {
        "id": 101,
        "title": "Privacy-Preserving NLP for Peer Review",
        "abstract": "Applying topic extraction to match academic reviewers without leaking PII.",
        "topics": ["nlp", "privacy", "peer-review"],
    }
    candidate_reviewers = [
        {
            "reviewer_id": 1,
            "expertise": ["databases", "sql"],
            "past_topics": ["indexing"],
        },
        {
            "reviewer_id": 2,
            "expertise": ["nlp", "privacy", "peer-review"],
            "past_topics": ["nlp", "double-blind"],
        },
        {
            "reviewer_id": 3,
            "expertise": ["nlp", "machine-learning"],
            "past_topics": ["classification"],
        },
    ]

    recommendations = recommend_reviewers(submission_context, candidate_reviewers)

    assert len(recommendations) > 0
    scores = [item["score"] for item in recommendations]
    assert scores == sorted(scores, reverse=True)
    assert all(
        item["status"] == "recommended" and item["confirmed"] is False
        for item in recommendations
    )
