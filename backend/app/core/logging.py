"""C4 LoggingComponent: structured audit logging with sensitive field redaction."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

_REDACTED_KEYS = {
    "password",
    "password_hash",
    "token",
    "raw_token",
    "access_token",
    "secret",
    "authorization",
}

logger = logging.getLogger("cmt.audit")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): ("[REDACTED]" if str(k).lower() in _REDACTED_KEYS else _sanitize_value(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def log_action(
    event: str,
    actor_id: Any = None,
    target_id: Any = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Emit a structured JSON audit log entry with sensitive credentials redacted."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor_id": str(actor_id) if actor_id is not None else None,
        "target_id": str(target_id) if target_id is not None else None,
        "details": _sanitize_value(details or {}),
    }
    logger.info(json.dumps(record, default=str))
