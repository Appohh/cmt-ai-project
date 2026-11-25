"""Application configuration helpers reading environment variables dynamically."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
if _ROOT_ENV.is_file():
    load_dotenv(_ROOT_ENV)
load_dotenv()

_DEFAULT_SECRET_KEY = "test-secret-key-for-integration-tests"
_DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"


def get_secret_key() -> str:
    """Return the HS256 JWT signing secret from environment or local dev default."""
    return os.getenv("SECRET_KEY") or _DEFAULT_SECRET_KEY


def get_access_token_expire_minutes() -> int:
    """Return JWT access token lifetime in minutes."""
    raw = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    try:
        value = int(raw)
        return value if value > 0 else 60
    except ValueError:
        return 60


def get_upload_dir() -> Path:
    """Return the directory where sanitized submission PDFs are stored."""
    raw = os.getenv("UPLOAD_DIR")
    if raw:
        return Path(raw)
    return _DEFAULT_UPLOAD_DIR


def get_frontend_base_url() -> str:
    """Return the frontend origin used when generating copyable invitation links."""
    return os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


def get_ai_provider() -> str:
    """Return the configured AI matching provider mode (local, ollama, or openai)."""
    return os.getenv("AI_PROVIDER", "local").strip().lower()


def utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Normalize naive datetimes from SQLite/MySQL drivers to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
