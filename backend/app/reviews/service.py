"""Review assignment and scoring service stubs."""


class ConflictOfInterestError(Exception):
    """Raised when assigning a reviewer with a conflict of interest."""


def assign_reviewer(submission: dict, reviewer_id: int) -> dict:
    """Assign a reviewer to a submission after checking for conflicts of interest."""
    raise NotImplementedError("TDD stub: implement to pass unit test")


def calculate_average_score(reviews: list[dict]) -> float:
    """Calculate the mean numeric score across a non-empty list of reviews."""
    raise NotImplementedError("TDD stub: implement to pass unit test")
