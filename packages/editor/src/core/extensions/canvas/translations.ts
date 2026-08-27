/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TEditorTranslation } from "@/types/editor";

const ENGLISH_CANVAS_TRANSLATIONS: Record<string, string> = {
  "canvas.action.close": "Close canvas",
  "canvas.action.delete": "Delete canvas",
  "canvas.action.duplicate": "Duplicate canvas",
  "canvas.action.open": "Open canvas",
  "canvas.aria.block": "Canvas block: {title}",
  "canvas.aria.editor": "Canvas editor: {title}",
  "canvas.aria.open": "Open canvas: {title}",
  "canvas.aria.preview_size": "Canvas preview size",
  "canvas.aria.title": "Canvas title",
  "canvas.collaborator": "Another collaborator",
  "canvas.error.oversized": "Canvas is too large to save",
  "canvas.error.unsupported_file": "Images and file attachments are not supported yet",
  "canvas.error.unsupported_version": "This canvas was created by a newer version of Plane",
  "canvas.locked": "{user} is editing this canvas.",
  "canvas.preview_unavailable": "Preview unavailable",
  "canvas.size.compact": "Compact preview",
  "canvas.size.standard": "Standard preview",
  "canvas.size.wide": "Wide preview",
  "canvas.slash.description": "Insert a drawing canvas",
  "canvas.slash.title": "Canvas",
  "canvas.status.failed": "Save failed",
  "canvas.status.loading": "Loading canvas",
  "canvas.status.saved": "Saved",
  "canvas.status.saving": "Saving",
  "canvas.untitled": "Untitled canvas",
};

export const getCanvasTranslation = (
  translate: TEditorTranslation | undefined,
  key: string,
  params?: Record<string, unknown>
): string => {
  if (translate) return translate(key, params);
  const value = ENGLISH_CANVAS_TRANSLATIONS[key] ?? key;
  return Object.entries(params ?? {}).reduce(
    (result, [param, replacement]) => result.replaceAll(`{${param}}`, String(replacement)),
    value
  );
};
