/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import {
  CANVAS_SCENE_VERSION,
  ECanvasAttributeNames,
  MAX_CANVAS_PREVIEW_BYTES,
  MAX_CANVAS_PREVIEW_DIMENSION,
  MAX_CANVAS_SCENE_BYTES,
  MAX_CANVAS_TITLE_LENGTH,
} from "./types";
import type {
  TCanvasAttributes,
  TCanvasPreviewSize,
  TCanvasScene,
  TCanvasValidationErrorCode,
  TCanvasValidationResult,
} from "./types";

const BASE64_PATTERN = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;
const PNG_SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10];
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const CANVAS_PREVIEW_SIZES: Record<TCanvasPreviewSize, { width: number; height: number }> = {
  compact: { width: 480, height: 270 },
  standard: { width: 720, height: 405 },
  wide: { width: 960, height: 540 },
};

export const EMPTY_CANVAS_SCENE: TCanvasScene = {
  version: CANVAS_SCENE_VERSION,
  elements: [],
  appState: {},
};

export const EMPTY_CANVAS_PREVIEW =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XxP2AAAAAElFTkSuQmCC";

export const normalizeCanvasTitle = (title: string, fallback: string): string =>
  (title.trim() || fallback).slice(0, MAX_CANVAS_TITLE_LENGTH);

export const isCurrentCanvasSaveRevision = (revision: number, currentRevision: number): boolean =>
  revision === currentRevision;

const sortCanvasValue = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(sortCanvasValue);
  if (!value || typeof value !== "object") return value;
  return Object.keys(value as Record<string, unknown>)
    .sort()
    .reduce<Record<string, unknown>>((result, key) => {
      result[key] = sortCanvasValue((value as Record<string, unknown>)[key]);
      return result;
    }, {});
};

export const getCanvasSceneFingerprint = (scene: TCanvasScene): string => JSON.stringify(sortCanvasValue(scene));

export const shouldRenderCanvasPreview = (
  preview: string | null,
  validationError?: TCanvasValidationErrorCode
): preview is string => preview !== null && validationError !== "unsupported-version";

const bytesToBase64 = (bytes: Uint8Array): string => {
  if (typeof Buffer !== "undefined") return Buffer.from(bytes).toString("base64");
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
};

const base64ToBytes = (value: string): TCanvasValidationResult<Uint8Array> => {
  if (!value || !BASE64_PATTERN.test(value)) return { ok: false, code: "invalid-encoding" };
  try {
    if (typeof Buffer !== "undefined") return { ok: true, value: Uint8Array.from(Buffer.from(value, "base64")) };
    const binary = atob(value);
    return { ok: true, value: Uint8Array.from(binary, (character) => character.charCodeAt(0)) };
  } catch {
    return { ok: false, code: "invalid-encoding" };
  }
};

export const encodeCanvasScene = (scene: TCanvasScene): TCanvasValidationResult<string> => {
  const bytes = new TextEncoder().encode(JSON.stringify(scene));
  if (bytes.byteLength > MAX_CANVAS_SCENE_BYTES) return { ok: false, code: "oversized" };
  return { ok: true, value: bytesToBase64(bytes) };
};

const isCanvasScene = (value: unknown): value is TCanvasScene => {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  if (candidate.version !== CANVAS_SCENE_VERSION || !Array.isArray(candidate.elements)) return false;
  if (!candidate.appState || typeof candidate.appState !== "object" || Array.isArray(candidate.appState)) return false;
  return candidate.elements.every(
    (element) =>
      !!element &&
      typeof element === "object" &&
      typeof (element as Record<string, unknown>).id === "string" &&
      typeof (element as Record<string, unknown>).type === "string"
  );
};

export const decodeCanvasScene = (encoded: string, declaredVersion?: number): TCanvasValidationResult<TCanvasScene> => {
  if (declaredVersion !== undefined && declaredVersion !== CANVAS_SCENE_VERSION)
    return { ok: false, code: "unsupported-version" };
  const decoded = base64ToBytes(encoded);
  if (!decoded.ok) return decoded;
  if (decoded.value.byteLength > MAX_CANVAS_SCENE_BYTES) return { ok: false, code: "oversized" };
  try {
    const value: unknown = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(decoded.value));
    if (!value || typeof value !== "object") return { ok: false, code: "invalid-scene" };
    const record = value as Record<string, unknown>;
    if (record.version !== CANVAS_SCENE_VERSION) return { ok: false, code: "unsupported-version" };
    if ("files" in record && record.files && Object.keys(record.files as object).length > 0)
      return { ok: false, code: "unsupported-file" };
    if (!isCanvasScene(value)) return { ok: false, code: "invalid-scene" };
    const hasFileElements = value.elements.some((element) => typeof element.fileId === "string");
    if (hasFileElements) return { ok: false, code: "unsupported-file" };
    return { ok: true, value };
  } catch {
    return { ok: false, code: "invalid-scene" };
  }
};

export const validateCanvasPreview = (
  preview: string,
  width: number,
  height: number
): TCanvasValidationResult<string> => {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0)
    return { ok: false, code: "invalid-preview" };
  if (width > MAX_CANVAS_PREVIEW_DIMENSION || height > MAX_CANVAS_PREVIEW_DIMENSION)
    return { ok: false, code: "invalid-preview" };
  const decoded = base64ToBytes(preview);
  if (!decoded.ok) return { ok: false, code: "invalid-preview" };
  if (decoded.value.byteLength > MAX_CANVAS_PREVIEW_BYTES) return { ok: false, code: "oversized" };
  if (!PNG_SIGNATURE.every((value, index) => decoded.value[index] === value))
    return { ok: false, code: "invalid-preview" };
  return { ok: true, value: preview };
};

export const getCanvasPreviewDataUri = (attrs: TCanvasAttributes): string | null => {
  const result = validateCanvasPreview(
    attrs[ECanvasAttributeNames.PREVIEW],
    Number(attrs[ECanvasAttributeNames.PREVIEW_WIDTH]),
    Number(attrs[ECanvasAttributeNames.PREVIEW_HEIGHT])
  );
  return result.ok ? `data:image/png;base64,${result.value}` : null;
};

export const getCanvasPreviewSize = (width: number): TCanvasPreviewSize => {
  if (width <= CANVAS_PREVIEW_SIZES.compact.width) return "compact";
  if (width >= CANVAS_PREVIEW_SIZES.wide.width) return "wide";
  return "standard";
};

export const isValidCanvasId = (value: string): boolean => UUID_PATTERN.test(value);

export const getDefaultCanvasAttributes = (id: string, title = ""): TCanvasAttributes => {
  const encoded = encodeCanvasScene(EMPTY_CANVAS_SCENE);
  if (!encoded.ok) throw new Error("The empty Canvas scene could not be encoded.");
  return {
    [ECanvasAttributeNames.ID]: id,
    [ECanvasAttributeNames.TITLE]: normalizeCanvasTitle(title, ""),
    [ECanvasAttributeNames.SCENE_VERSION]: CANVAS_SCENE_VERSION,
    [ECanvasAttributeNames.SCENE]: encoded.value,
    [ECanvasAttributeNames.PREVIEW]: "",
    [ECanvasAttributeNames.PREVIEW_WIDTH]: CANVAS_PREVIEW_SIZES.standard.width,
    [ECanvasAttributeNames.PREVIEW_HEIGHT]: CANVAS_PREVIEW_SIZES.standard.height,
  };
};

export const validateCanvasAttributes = (attrs: TCanvasAttributes): TCanvasValidationResult<TCanvasAttributes> => {
  if (!isValidCanvasId(attrs[ECanvasAttributeNames.ID])) return { ok: false, code: "invalid-scene" };
  const scene = decodeCanvasScene(
    attrs[ECanvasAttributeNames.SCENE],
    Number(attrs[ECanvasAttributeNames.SCENE_VERSION])
  );
  if (!scene.ok) return scene;
  const preview = attrs[ECanvasAttributeNames.PREVIEW];
  if (preview) {
    const previewResult = validateCanvasPreview(
      preview,
      Number(attrs[ECanvasAttributeNames.PREVIEW_WIDTH]),
      Number(attrs[ECanvasAttributeNames.PREVIEW_HEIGHT])
    );
    if (!previewResult.ok) return previewResult;
  }
  return { ok: true, value: attrs };
};
