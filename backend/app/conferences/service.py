"""Conference administration and invitation token service functions."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from app.core.config import ensure_utc


def create_conference(
    name: str,
    description: str,
    submission_deadline: datetime,
    review_deadline: datetime,
    notification_deadline: datetime,
) -> dict:
    """Create a conference after validating chronological deadline order."""
    if not name or not name.strip():
        raise ValueError("Conference name is required")

    sub_dl = ensure_utc(submission_deadline)
    rev_dl = ensure_utc(review_deadline)
    notif_dl = ensure_utc(notification_deadline)

    if not (sub_dl < rev_dl < notif_dl):
        raise ValueError(
            "Conference deadlines must follow submission_deadline < review_deadline < notification_deadline"
        )

    return {
        "name": name.strip(),
        "description": description.strip() if description else None,
        "submission_deadline": sub_dl,
        "review_deadline": rev_dl,
        "notification_deadline": notif_dl,
    }


def hash_invitation_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of an invitation token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_invitation_token() -> tuple[str, str]:
    """Generate a cryptographically random invitation token and its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_invitation_token(raw_token)
