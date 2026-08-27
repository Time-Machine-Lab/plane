# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64
import json

import pytest

from plane.utils.content_validator import validate_html_content


def _scene(version=1, elements=None, files=None):
    value = {"version": version, "elements": elements or [], "appState": {}}
    if files is not None:
        value["files"] = files
    return base64.b64encode(json.dumps(value).encode()).decode()


def _canvas(scene=None, preview="", extra=""):
    return (
        '<canvas-component data-canvas-id="c4d18686-95cf-4f3b-aab7-c2b595f454ae" '
        'data-title="Architecture" data-scene-version="1" '
        f'data-scene="{scene or _scene()}" data-preview="{preview}" '
        f'data-preview-width="720" data-preview-height="405" {extra}></canvas-component>'
    )


@pytest.mark.unit
def test_valid_canvas_is_preserved():
    is_valid, error, cleaned = validate_html_content(_canvas())
    assert is_valid is True
    assert error is None
    assert "canvas-component" in cleaned
    assert "data-scene=" in cleaned


@pytest.mark.unit
@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        (_canvas(scene="%%%"), "invalid"),
        (_canvas(scene=_scene(version=2)), "version"),
        (_canvas(scene=_scene(files={"asset": {"dataURL": "data:image/png;base64,AA=="}})), "files"),
        (_canvas(scene=_scene(elements=[{"id": "one", "type": "image", "fileId": "asset"}])), "files"),
        (_canvas(preview=base64.b64encode(b"not-png").decode()), "preview"),
    ],
)
def test_invalid_canvas_is_rejected(content, expected_error):
    is_valid, error, cleaned = validate_html_content(content)
    assert is_valid is False
    assert expected_error in error.lower()
    assert cleaned is None


@pytest.mark.unit
def test_canvas_executable_attributes_are_removed():
    is_valid, error, cleaned = validate_html_content(_canvas(extra='onclick="alert(1)" data-unsafe="bad"'))
    assert is_valid is True
    assert error is None
    assert "onclick" not in cleaned
    assert "data-unsafe" not in cleaned


@pytest.mark.unit
def test_oversized_canvas_scene_is_rejected():
    oversized_scene = base64.b64encode(b"x" * (4 * 1024 * 1024 + 1)).decode()
    is_valid, error, cleaned = validate_html_content(_canvas(scene=oversized_scene))
    assert is_valid is False
    assert "size limit" in error.lower()
    assert cleaned is None


@pytest.mark.unit
def test_oversized_canvas_title_is_rejected():
    is_valid, error, cleaned = validate_html_content(_canvas().replace("Architecture", "x" * 121))
    assert is_valid is False
    assert "title" in error.lower()
    assert cleaned is None
