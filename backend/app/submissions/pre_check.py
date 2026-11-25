"""C4 PrePaperCheckComponent: PDF upload validation and author metadata stripping."""

from __future__ import annotations

import io
import re

from app.core.logging import log_action
from app.core.security import validate_pdf_upload

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - fallback if pypdf is unavailable
    PdfReader = None  # type: ignore[assignment]
    PdfWriter = None  # type: ignore[assignment]

_METADATA_FIELD_PARENS = re.compile(
    rb"/(?:Author|Creator|Producer|Subject|Keywords)\s*\((?:\\.|[^()])*\)"
)
_METADATA_FIELD_HEX = re.compile(
    rb"/(?:Author|Creator|Producer|Subject|Keywords)\s*<[^>]*>"
)
_XMP_PACKET = re.compile(rb"<x:xmpmeta[\s\S]*?</x:xmpmeta>", re.IGNORECASE)


def _scrub_raw_pdf_metadata(raw_bytes: bytes) -> bytes:
    """Remove common PDF Info dictionary author/creator tags and XMP packets."""
    cleaned = _METADATA_FIELD_PARENS.sub(b"", raw_bytes)
    cleaned = _METADATA_FIELD_HEX.sub(b"", cleaned)
    cleaned = _XMP_PACKET.sub(b"", cleaned)
    return cleaned


def strip_pdf_metadata(file_bytes: bytes) -> bytes:
    """Strip identifying author metadata from a PDF while preserving valid PDF output."""
    if not file_bytes.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF byte stream")

    if PdfReader is not None and PdfWriter is not None:
        try:
            reader = PdfReader(io.BytesIO(file_bytes), strict=False)
            if len(reader.pages) > 0:
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                writer.add_metadata({})
                out = io.BytesIO()
                writer.write(out)
                rewritten = out.getvalue()
                if rewritten.startswith(b"%PDF-"):
                    return _scrub_raw_pdf_metadata(rewritten)
        except Exception:
            pass

    return _scrub_raw_pdf_metadata(file_bytes)


def check_and_sanitize_pdf(filename: str, content_type: str, file_bytes: bytes) -> bytes:
    """Validate uploaded PDF security constraints and strip author metadata."""
    validate_pdf_upload(filename=filename, content_type=content_type, file_bytes=file_bytes)
    sanitized = strip_pdf_metadata(file_bytes)
    log_action(
        "pre_paper_check.validated",
        details={"filename": filename, "original_bytes": len(file_bytes), "sanitized_bytes": len(sanitized)},
    )
    return sanitized
