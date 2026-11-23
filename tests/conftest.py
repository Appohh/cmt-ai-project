from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def conference_deadlines() -> dict[str, datetime]:
    """Return valid chronological conference deadlines in UTC."""
    base = datetime(2026, 12, 1, 23, 59, tzinfo=timezone.utc)
    return {
        "submission_deadline": base,
        "review_deadline": base + timedelta(days=14),
        "notification_deadline": base + timedelta(days=28),
    }


@pytest.fixture
def sample_submission() -> dict:
    """Return a sample paper submission containing author and co-author PII."""
    return {
        "id": 101,
        "title": "Automated Reviewer Matching in Academic Conferences",
        "abstract": "We study privacy-preserving reviewer recommendations using topic models.",
        "author_id": 42,
        "author_name": "Ada Lovelace",
        "author_email": "ada.lovelace@example.com",
        "affiliation": "TU Delft",
        "co_authors": [
            {
                "id": 43,
                "name": "Grace Hopper",
                "email": "grace.hopper@example.com",
                "affiliation": "Yale University",
            }
        ],
    }


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    """Return a minimal valid PDF byte payload starting with %PDF-1.4 header."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        b"%%EOF\n"
    )
