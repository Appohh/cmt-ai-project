"""Security service stubs for authentication, RBAC, and file upload validation."""


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using a salted cryptographic password hash."""
    raise NotImplementedError("TDD stub: implement to pass unit test")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its stored hash."""
    raise NotImplementedError("TDD stub: implement to pass unit test")


def check_permission(role: str, action: str) -> bool:
    """Return True if the given role is permitted to perform the requested action."""
    raise NotImplementedError("TDD stub: implement to pass unit test")


def validate_pdf_upload(
    filename: str,
    content_type: str,
    file_bytes: bytes,
    max_size_bytes: int = 10 * 1024 * 1024,
) -> bool:
    """Validate uploaded PDF extension, MIME type, magic bytes, and size limit."""
    raise NotImplementedError("TDD stub: implement to pass unit test")
