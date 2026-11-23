"""Conference administration service stubs."""

from datetime import datetime


def create_conference(
    name: str,
    description: str,
    submission_deadline: datetime,
    review_deadline: datetime,
    notification_deadline: datetime,
) -> dict:
    """Create a conference after validating chronological deadline order."""
    raise NotImplementedError("TDD stub: implement to pass unit test")
