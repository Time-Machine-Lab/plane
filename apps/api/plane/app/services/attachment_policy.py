# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Authoritative server-side policy shared by Page and work-item uploads."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.conf import settings


EXTENSION_MIME_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".canvas": "application/json",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
}

SCRIPT_CAPABLE = frozenset({"text/html", "application/xhtml+xml", "text/javascript", "application/javascript", "image/svg+xml", "text/xml", "application/xml"})
DANGEROUS_EXTENSIONS = frozenset({".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".sh", ".msi", ".jar", ".scr", ".vbs"})


@dataclass(frozen=True)
class AttachmentDecision:
    mime_type: str
    presentation: str


class AttachmentPolicyError(ValueError):
    code = "unsupported"


def resolve_attachment_type(name: str, declared_type: Optional[str] = None) -> AttachmentDecision:
    filename = Path(name or "unnamed").name
    extension = Path(filename).suffix.lower()
    declared = (declared_type or "").split(";", 1)[0].strip().lower()
    if extension in DANGEROUS_EXTENSIONS:
        error = AttachmentPolicyError("Executable attachments are not supported")
        error.code = "dangerous"
        raise error
    mime_type = EXTENSION_MIME_TYPES.get(extension) or declared
    if not mime_type or mime_type == "application/octet-stream":
        # Keep the existing allow-list for recognized document/image formats,
        # but never let generic octet-stream bypass it.
        if declared not in settings.ATTACHMENT_MIME_TYPES or declared == "application/octet-stream":
            raise AttachmentPolicyError("Unable to determine a supported file type")
        mime_type = declared
    if mime_type not in settings.ATTACHMENT_MIME_TYPES and mime_type not in {"text/html", "application/json"}:
        raise AttachmentPolicyError("Unsupported file type")
    if extension == ".canvas":
        presentation = "json-canvas"
    elif mime_type == "text/html":
        presentation = "interactive-html"
    elif mime_type.startswith("image/"):
        presentation = "image"
    elif mime_type == "text/plain":
        presentation = "text"
    elif mime_type == "text/markdown":
        presentation = "markdown"
    elif mime_type == "application/pdf":
        presentation = "pdf"
    elif mime_type == "video/mp4":
        presentation = "video"
    elif mime_type == "audio/mpeg":
        presentation = "audio"
    elif mime_type in SCRIPT_CAPABLE:
        presentation = "download"
    else:
        presentation = "download"
    return AttachmentDecision(mime_type=mime_type, presentation=presentation)


def validate_attachment(name: str, size: int, declared_type: Optional[str] = None, limit: Optional[int] = None) -> AttachmentDecision:
    try:
        size = int(size)
    except (TypeError, ValueError) as error:
        raise AttachmentPolicyError("File size must be an integer") from error
    max_size = int(limit or getattr(settings, "FILE_SIZE_LIMIT", 104857600))
    if size <= 0:
        error = AttachmentPolicyError("File must not be empty")
        error.code = "empty"
        raise error
    if size > max_size:
        error = AttachmentPolicyError(f"File exceeds the {max_size} byte limit")
        error.code = "oversized"
        raise error
    return resolve_attachment_type(name, declared_type)


def get_active_storage_profile():
    """Return the verified instance write target, or ``None`` for legacy storage."""
    from plane.license.models import StorageProfile

    return StorageProfile.objects.filter(status=StorageProfile.Status.ACTIVE).order_by("-updated_at").first()
