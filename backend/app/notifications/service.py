"""Notification service stub ready for future SMTP or email provider integration."""

from __future__ import annotations

from app.core.logging import log_action


def send_invitation_notification(
    email: str,
    conference_name: str,
    role: str,
    invite_link: str,  # noqa: ARG001 - kept in signature for future SMTP templates
) -> dict:
    """Log an invitation dispatch event; in-app copyable links deliver tokens in MVP."""
    log_action(
        "notification.invitation_queued",
        details={"email": email, "conference": conference_name, "role": role},
    )
    return {"delivered": False, "mode": "in_app_link"}


def send_decision_notification(
    email: str,
    paper_title: str,
    status: str,
) -> dict:
    """Log an editorial decision event; automated email delivery is a Should-Have."""
    log_action(
        "notification.decision_logged",
        details={"email": email, "paper_title": paper_title, "status": status},
    )
    return {"delivered": False, "mode": "logged_only"}
