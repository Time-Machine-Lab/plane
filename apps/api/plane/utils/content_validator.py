# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import base64
import binascii
import json
import nh3
from plane.utils.exception_logger import log_exception
from bs4 import BeautifulSoup
from collections import defaultdict
import logging
from uuid import UUID

logger = logging.getLogger("plane.api")

# Maximum allowed size for binary data (10MB)
MAX_SIZE = 10 * 1024 * 1024
MAX_CANVAS_SCENE_SIZE = 4 * 1024 * 1024
MAX_CANVAS_PREVIEW_SIZE = 1536 * 1024
MAX_CANVAS_PREVIEW_DIMENSION = 2048
MAX_CANVAS_TITLE_LENGTH = 120
CANVAS_SCENE_VERSION = 1
CANVAS_ATTRIBUTES = {
    "data-canvas-id",
    "data-title",
    "data-scene-version",
    "data-scene",
    "data-preview",
    "data-preview-width",
    "data-preview-height",
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Suspicious patterns for binary data content
SUSPICIOUS_BINARY_PATTERNS = [
    "<html",
    "<!doctype",
    "<script",
    "javascript:",
    "data:",
    "<iframe",
]


def validate_binary_data(data):
    """
    Validate that binary data appears to be a valid document format
    and doesn't contain malicious content.

    Args:
        data (bytes or str): The binary data to validate, or base64-encoded string

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not data:
        return True, None  # Empty is OK

    # Handle base64-encoded strings by decoding them first
    if isinstance(data, str):
        try:
            binary_data = base64.b64decode(data)
        except Exception:
            return False, "Invalid base64 encoding"
    else:
        binary_data = data

    # Size check - 10MB limit
    if len(binary_data) > MAX_SIZE:
        return False, "Binary data exceeds maximum size limit (10MB)"

    # Basic format validation
    if len(binary_data) < 4:
        return False, "Binary data too short to be valid document format"

    # Check for suspicious text patterns (HTML/JS)
    try:
        decoded_text = binary_data.decode("utf-8", errors="ignore")[:200]
        if any(pattern in decoded_text.lower() for pattern in SUSPICIOUS_BINARY_PATTERNS):
            return False, "Binary data contains suspicious content patterns"
    except Exception:
        pass  # Binary data might not be decodable as text, which is fine

    return True, None


# Combine custom components and editor-specific nodes into a single set of tags
CUSTOM_TAGS = {
    # editor node/tag names
    "mention-component",
    "label",
    "input",
    "image-component",
    "canvas-component",
}
ALLOWED_TAGS = nh3.ALLOWED_TAGS | CUSTOM_TAGS

# Merge nh3 defaults with all attributes used across our custom components
ATTRIBUTES = {
    "*": {
        "class",
        "id",
        "title",
        "role",
        "aria-label",
        "aria-hidden",
        "style",
        "start",
        "type",
        "xmlns",
        # common editor data-* attributes seen in stored HTML
        # (wildcards like data-* are NOT supported by nh3; we add known keys
        # here and dynamically include all data-* seen in the input below)
        "data-tight",
        "data-node-type",
        "data-type",
        "data-checked",
        "data-background-color",
        "data-text-color",
        "data-name",
        "data-id",
        # callout attributes
        "data-icon-name",
        "data-icon-color",
        "data-background",
        "data-emoji-unicode",
        "data-emoji-url",
        "data-logo-in-use",
        "data-block-type",
    },
    "a": {"href", "target"},
    # editor node/tag attributes
    "image-component": {
        "id",
        "width",
        "height",
        "aspectRatio",
        "aspectratio",
        "src",
        "alignment",
        "status",
    },
    "canvas-component": CANVAS_ATTRIBUTES,
    "img": {
        "width",
        "height",
        "aspectRatio",
        "aspectratio",
        "alignment",
        "src",
        "alt",
        "title",
    },
    "mention-component": {"id", "entity_identifier", "entity_name"},
    "th": {
        "colspan",
        "rowspan",
        "colwidth",
        "background",
        "style",
    },
    "td": {
        "colspan",
        "rowspan",
        "colwidth",
        "background",
        "textColor",
        "textcolor",
        "style",
    },
    "tr": {"background", "textColor", "textcolor", "style"},
    "pre": {"language"},
    "code": {"language", "spellcheck"},
    "input": {"type", "checked"},
}

SAFE_PROTOCOLS = {"http", "https", "mailto", "tel"}


def _decode_canvas_base64(value: str, max_size: int):
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return None
    if len(decoded) > max_size:
        return None
    return decoded


def _validate_canvas_component(component):
    attrs = component.attrs
    if not CANVAS_ATTRIBUTES.issubset(attrs.keys()):
        return False, "Canvas component is missing required attributes"
    if not isinstance(attrs["data-title"], str) or len(attrs["data-title"]) > MAX_CANVAS_TITLE_LENGTH:
        return False, "Canvas title exceeds the size limit"

    try:
        UUID(attrs["data-canvas-id"])
        scene_version = int(attrs["data-scene-version"])
        preview_width = int(attrs["data-preview-width"])
        preview_height = int(attrs["data-preview-height"])
    except (TypeError, ValueError, AttributeError):
        return False, "Canvas component has invalid metadata"

    if scene_version != CANVAS_SCENE_VERSION:
        return False, "Canvas scene version is not supported"
    if (
        preview_width <= 0
        or preview_height <= 0
        or preview_width > MAX_CANVAS_PREVIEW_DIMENSION
        or preview_height > MAX_CANVAS_PREVIEW_DIMENSION
    ):
        return False, "Canvas preview dimensions are invalid"

    scene_bytes = _decode_canvas_base64(attrs["data-scene"], MAX_CANVAS_SCENE_SIZE)
    if scene_bytes is None:
        return False, "Canvas scene is invalid or exceeds the size limit"
    try:
        scene = json.loads(scene_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "Canvas scene is malformed"

    if not isinstance(scene, dict) or scene.get("version") != CANVAS_SCENE_VERSION:
        return False, "Canvas scene version is not supported"
    if not isinstance(scene.get("elements"), list) or not isinstance(scene.get("appState"), dict):
        return False, "Canvas scene is malformed"
    if scene.get("files"):
        return False, "Canvas embedded files are not supported"
    if any(not isinstance(element, dict) or element.get("fileId") for element in scene["elements"]):
        return False, "Canvas embedded files are not supported"

    preview = attrs["data-preview"]
    if preview:
        preview_bytes = _decode_canvas_base64(preview, MAX_CANVAS_PREVIEW_SIZE)
        if preview_bytes is None or not preview_bytes.startswith(PNG_SIGNATURE):
            return False, "Canvas preview is invalid or exceeds the size limit"

    return True, None


def _compute_html_sanitization_diff(before_html: str, after_html: str):
    """
    Compute a coarse diff between original and sanitized HTML.

    Returns a dict with:
    - removed_tags: mapping[tag] -> removed_count
    - removed_attributes: mapping[tag] -> sorted list of attribute names removed
    """
    try:

        def collect(soup):
            tag_counts = defaultdict(int)
            attrs_by_tag = defaultdict(set)
            for el in soup.find_all(True):
                tag_name = (el.name or "").lower()
                if not tag_name:
                    continue
                tag_counts[tag_name] += 1
                for attr_name in list(el.attrs.keys()):
                    if isinstance(attr_name, str) and attr_name:
                        attrs_by_tag[tag_name].add(attr_name.lower())
            return tag_counts, attrs_by_tag

        soup_before = BeautifulSoup(before_html or "", "html.parser")
        soup_after = BeautifulSoup(after_html or "", "html.parser")

        counts_before, attrs_before = collect(soup_before)
        counts_after, attrs_after = collect(soup_after)

        removed_tags = {}
        for tag, cnt_before in counts_before.items():
            cnt_after = counts_after.get(tag, 0)
            if cnt_after < cnt_before:
                removed = cnt_before - cnt_after
                removed_tags[tag] = removed

        removed_attributes = {}
        for tag, before_set in attrs_before.items():
            after_set = attrs_after.get(tag, set())
            removed = before_set - after_set
            if removed:
                removed_attributes[tag] = sorted(list(removed))

        return {"removed_tags": removed_tags, "removed_attributes": removed_attributes}
    except Exception:
        # Best-effort only; if diffing fails we don't block the request
        return {"removed_tags": {}, "removed_attributes": {}}


def validate_html_content(html_content: str):
    """
    Sanitize HTML content using nh3.
    Returns a tuple: (is_valid, error_message, clean_html)
    """
    if not html_content:
        return True, None, None

    # Size check - 10MB limit (consistent with binary validation)
    if len(html_content.encode("utf-8")) > MAX_SIZE:
        return False, "HTML content exceeds maximum size limit (10MB)", None

    try:
        clean_html = nh3.clean(
            html_content,
            tags=ALLOWED_TAGS,
            attributes=ATTRIBUTES,
            url_schemes=SAFE_PROTOCOLS,
        )
        clean_soup = BeautifulSoup(clean_html, "html.parser")
        for canvas_component in clean_soup.find_all("canvas-component"):
            is_canvas_valid, canvas_error = _validate_canvas_component(canvas_component)
            if not is_canvas_valid:
                return False, canvas_error, None
        # Report removals to logger (Sentry) if anything was stripped
        diff = _compute_html_sanitization_diff(html_content, clean_html)
        if diff.get("removed_tags") or diff.get("removed_attributes"):
            try:
                import json

                summary = json.dumps(diff)
            except Exception:
                summary = str(diff)
            logger.warning(f"HTML sanitization removals: {summary}")
        return True, None, clean_html
    except Exception as e:
        log_exception(e)
        return False, "Failed to sanitize HTML", None


def has_alphanumeric(value):
    """
    Check whether a string contains at least one alphanumeric character.

    `str.isalnum()` is Unicode-aware, so letters and digits from any script
    (Latin, CJK, Arabic, Cyrillic, etc.) all count. This mirrors the frontend
    HAS_ALPHANUMERIC_REGEX (/[\\p{L}\\p{N}]/u) check and is used to reject
    symbol-only names such as "-_________-".

    Args:
        value (str): The string to check.

    Returns:
        bool: True if the value contains at least one letter or digit.
    """
    return any(char.isalnum() for char in (value or ""))
