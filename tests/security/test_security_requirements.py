"""Security-focused unit tests covering authentication, RBAC, anonymity, COI, and uploads."""

import pytest

from app.core.security import (
    check_permission,
    hash_password,
    validate_pdf_upload,
    verify_password,
)
from app.reviews.service import ConflictOfInterestError, assign_reviewer
from app.submissions.service import anonymize_submission_for_reviewer


@pytest.mark.security
def test_password_hashing_and_verification() -> None:
    """SEC-01 / NFR-02: Passwords must be uniquely salted, hashed, and verifiable."""
    plain = "S3cur3!Passw0rd"
    h1 = hash_password(plain)
    h2 = hash_password(plain)

    assert h1 != plain
    assert h1 != h2
    assert verify_password(plain, h1) is True
    assert verify_password("WrongPassword", h1) is False


@pytest.mark.security
def test_rbac_prevents_unauthorized_role_actions() -> None:
    """US-20 / FR-05 / SEC-03: Strict RBAC blocks privileged actions for unauthorized roles."""
    assert check_permission("author", "record_final_decision") is False
    assert check_permission("reviewer", "view_other_reviews_before_release") is False
    assert check_permission("reviewer", "manage_users") is False
    assert check_permission("organizer", "record_final_decision") is True
    assert check_permission("administrator", "manage_users") is True


@pytest.mark.security
def test_double_blind_anonymization_strips_author_metadata(
    sample_submission: dict,
) -> None:
    """US-09 / NFR-01 / SEC-02: Double-blind view removes all author and co-author PII."""
    anonymized = anonymize_submission_for_reviewer(sample_submission)

    assert anonymized["title"] == sample_submission["title"]
    assert anonymized["abstract"] == sample_submission["abstract"]

    forbidden_keys = {
        "author_name",
        "author_email",
        "affiliation",
        "author_id",
        "co_authors",
    }
    assert forbidden_keys.isdisjoint(anonymized.keys())

    serialized_values = " ".join(str(value) for value in anonymized.values())
    pii_values = [
        sample_submission["author_name"],
        sample_submission["author_email"],
        sample_submission["affiliation"],
        sample_submission["co_authors"][0]["name"],
        sample_submission["co_authors"][0]["email"],
        sample_submission["co_authors"][0]["affiliation"],
    ]
    for pii in pii_values:
        assert pii not in serialized_values


@pytest.mark.security
def test_conflict_of_interest_blocks_self_review(sample_submission: dict) -> None:
    """NFR-01 / SEC-03: Authors and co-authors cannot be assigned to review their own paper."""
    with pytest.raises(ConflictOfInterestError):
        assign_reviewer(sample_submission, reviewer_id=sample_submission["author_id"])

    co_author_id = sample_submission["co_authors"][0]["id"]
    with pytest.raises(ConflictOfInterestError):
        assign_reviewer(sample_submission, reviewer_id=co_author_id)


@pytest.mark.security
def test_pdf_upload_validation_rejects_spoofed_and_oversized_files(
    valid_pdf_bytes: bytes,
) -> None:
    """SEC-04 / NFR-02: Uploaded PDFs must pass magic-bytes and maximum file size checks."""
    assert validate_pdf_upload("paper.pdf", "application/pdf", valid_pdf_bytes) is True

    with pytest.raises(ValueError):
        validate_pdf_upload(
            "malicious.pdf",
            "application/pdf",
            b"<script>alert(1)</script>",
        )

    oversized_pdf = b"%PDF-1.4\n" + (b"A" * (11 * 1024 * 1024))
    with pytest.raises(ValueError):
        validate_pdf_upload("oversized.pdf", "application/pdf", oversized_pdf)
