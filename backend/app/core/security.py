"""Security services: Argon2 password hashing, RBAC, PDF validation, and HS256 JWT auth."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlmodel import select

from app.core.config import get_access_token_expire_minutes, get_secret_key
from app.core.database import SessionDep
from app.models.models import Role, User, UserRole

try:
    import jwt as pyjwt
except ImportError:  # pragma: no cover - fallback only if PyJWT is absent
    pyjwt = None  # type: ignore[assignment]

password_hasher = PasswordHash.recommended()
_bearer_scheme = HTTPBearer(auto_error=False)

# In-memory TTL blocklist for server-side JWT logout revocation (keyed by jti -> exp unix ts)
_REVOKED_JTIS: dict[str, float] = {}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "author": {
        "submit_paper",
        "edit_own_submission",
        "withdraw_own_submission",
        "view_own_submission",
        "view_released_reviews",
        "manage_own_profile",
    },
    "reviewer": {
        "accept_review_invitation",
        "decline_review_invitation",
        "view_assigned_submissions",
        "download_blind_pdf",
        "submit_review",
        "edit_own_review",
        "manage_own_profile",
    },
    "organizer": {
        "create_conference",
        "view_all_submissions",
        "invite_reviewer",
        "invite_guest",
        "assign_reviewer",
        "unassign_reviewer",
        "view_all_reviews",
        "record_final_decision",
        "run_ai_matching",
        "track_review_progress",
        "manage_own_profile",
    },
    "admin": {
        "access_admin_dashboard",
        "view_system_overview",
        "manage_users",
        "create_conference",
        "manage_own_profile",
    },
    "guest": {
        "view_conference_overview",
        "accept_invitation",
        "manage_own_profile",
    },
}

_DANGEROUS_PDF_PATTERN = re.compile(rb"/(JavaScript|JS|Launch)\b")


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using a salted Argon2 password hash."""
    if not isinstance(plain_password, str) or not plain_password:
        raise ValueError("Password must be a non-empty string")
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its stored hash."""
    if not plain_password or not password_hash:
        return False
    try:
        return password_hasher.verify(plain_password, password_hash)
    except Exception:
        return False


def normalize_role(role: str) -> str:
    """Normalize role aliases (e.g., 'administrator' -> 'admin')."""
    normalized = role.strip().lower()
    if normalized == "administrator":
        return "admin"
    return normalized


def check_permission(role: str, action: str) -> bool:
    """Return True if the given role is permitted to perform the requested action."""
    if not isinstance(role, str) or not isinstance(action, str):
        return False
    normalized = normalize_role(role)
    return action.strip() in ROLE_PERMISSIONS.get(normalized, set())


def validate_pdf_upload(
    filename: str,
    content_type: str,
    file_bytes: bytes,
    max_size_bytes: int = 10 * 1024 * 1024,
) -> bool:
    """Validate uploaded PDF extension, MIME type, magic bytes, payload safety, and size limit."""
    if not filename or not isinstance(filename, str):
        raise ValueError("Filename is required")
    if "\x00" in filename or ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError("Invalid filename path")
    if Path(filename).suffix.lower() != ".pdf":
        raise ValueError("Only .pdf files are permitted")

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime != "application/pdf":
        raise ValueError("Invalid content type; expected application/pdf")

    if not isinstance(file_bytes, (bytes, bytearray)):
        raise ValueError("File payload must be bytes")
    raw = bytes(file_bytes)
    if len(raw) == 0:
        raise ValueError("Uploaded PDF file is empty")
    if len(raw) > max_size_bytes:
        raise ValueError(f"PDF exceeds maximum allowed size of {max_size_bytes} bytes")

    if not raw.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF signature; file must start with %PDF-")

    if b"<script" in raw.lower() or _DANGEROUS_PDF_PATTERN.search(raw):
        raise ValueError("Potentially malicious active script payload detected in PDF")

    return True


def _prune_revoked_jtis() -> None:
    now_ts = time.time()
    expired = [jti for jti, exp_ts in _REVOKED_JTIS.items() if exp_ts < now_ts]
    for jti in expired:
        _REVOKED_JTIS.pop(jti, None)


def revoke_token(jti: str, exp: int | float | None = None) -> None:
    """Record a JWT ID (jti) as revoked until its expiration timestamp."""
    if not jti:
        return
    _prune_revoked_jtis()
    default_exp = time.time() + get_access_token_expire_minutes() * 60
    _REVOKED_JTIS[jti] = float(exp) if exp is not None else default_exp


def is_token_revoked(jti: str | None) -> bool:
    """Return True if the given JWT ID has been explicitly revoked."""
    if not jti:
        return False
    _prune_revoked_jtis()
    return jti in _REVOKED_JTIS


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed HS256 JWT access token with unique jti and expiration."""
    now = datetime.now(timezone.utc)
    delta = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=get_access_token_expire_minutes())
    )
    payload = dict(data)
    payload.setdefault("jti", str(uuid.uuid4()))
    payload["iat"] = int(now.timestamp())
    payload["exp"] = int((now + delta).timestamp())
    secret = get_secret_key()

    if pyjwt is not None:
        return pyjwt.encode(payload, secret, algorithm="HS256")

    header_b64 = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"
    sig = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an HS256 JWT access token, enforcing expiry and jti revocation."""
    if not token:
        raise ValueError("Missing token")
    secret = get_secret_key()

    if pyjwt is not None:
        try:
            payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        except Exception as exc:
            raise ValueError("Invalid or expired token") from exc
    else:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed JWT")
        header_b64, payload_b64, sig_b64 = parts
        try:
            header = json.loads(_b64url_decode(header_b64))
            if header.get("alg") != "HS256":
                raise ValueError("Unsupported JWT algorithm")
            signing_input = f"{header_b64}.{payload_b64}"
            expected_sig = hmac.new(
                secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256
            ).digest()
            actual_sig = _b64url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                raise ValueError("Invalid token signature")
            payload = json.loads(_b64url_decode(payload_b64))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Invalid token payload") from exc

        exp = payload.get("exp")
        if exp is None or float(exp) < time.time():
            raise ValueError("Token has expired")

    if is_token_revoked(payload.get("jti")):
        raise ValueError("Token has been revoked")
    return payload


@dataclass
class AuthenticatedUser:
    """Represents the authenticated principal and their database roles."""

    user: User
    roles: list[Role]
    token_payload: dict[str, Any]

    def has_role(self, role: Role | str) -> bool:
        target = normalize_role(role.value if isinstance(role, Role) else role)
        return any(normalize_role(r.value) == target for r in self.roles)


def get_current_user(
    session: SessionDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """FastAPI dependency that authenticates a Bearer JWT and loads the active user + roles."""
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise auth_error

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(str(payload.get("sub")))
    except Exception:
        raise auth_error

    user = session.get(User, user_id)
    if user is None:
        raise auth_error

    role_rows = session.exec(select(UserRole).where(UserRole.user_id == user.id)).all()
    roles = [row.role for row in role_rows]
    return AuthenticatedUser(user=user, roles=roles, token_payload=payload)


def require_roles(*allowed_roles: Role) -> Callable[..., AuthenticatedUser]:
    """Return a FastAPI dependency enforcing that the caller holds at least one allowed role."""

    def _dependency(auth: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not any(auth.has_role(role) for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )
        return auth

    return _dependency
