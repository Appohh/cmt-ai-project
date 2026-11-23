"""Authentication and user account service stubs."""


def register_user(
    name: str,
    email: str,
    affiliation: str,
    password: str,
    role: str = "author",
) -> dict:
    """Register a new user account with normalized email and hashed credentials."""
    raise NotImplementedError("TDD stub: implement to pass unit test")
