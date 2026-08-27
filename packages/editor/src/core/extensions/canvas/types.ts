/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Node as TiptapNode } from "@tiptap/core";
import type { HocuspocusProvider } from "@hocuspocus/provider";
import type { TEditorTranslation } from "@/types/editor";

export const CANVAS_SCENE_VERSION = 1 as const;
export const MAX_CANVAS_SCENE_BYTES = 4 * 1024 * 1024;
export const MAX_CANVAS_PREVIEW_BYTES = 1536 * 1024;
export const MAX_CANVAS_PREVIEW_DIMENSION = 2048;
export const MAX_CANVAS_TITLE_LENGTH = 120;
export const CANVAS_SAVE_DEBOUNCE_MS = 800;

export enum ECanvasAttributeNames {
  ID = "data-canvas-id",
  TITLE = "data-title",
  SCENE_VERSION = "data-scene-version",
  SCENE = "data-scene",
  PREVIEW = "data-preview",
  PREVIEW_WIDTH = "data-preview-width",
  PREVIEW_HEIGHT = "data-preview-height",
}

export type TCanvasPreviewSize = "compact" | "standard" | "wide";
export type TCanvasSaveStatus = "idle" | "saving" | "saved" | "failed" | "oversized" | "unsupported-file";

export type TCanvasElement = Record<string, unknown> & {
  id: string;
  type: string;
};

export type TCanvasAppState = {
  gridSize?: number | null;
  viewBackgroundColor?: string;
};

export type TCanvasScene = {
  version: typeof CANVAS_SCENE_VERSION;
  elements: TCanvasElement[];
  appState: TCanvasAppState;
};

export type TCanvasAttributes = {
  [ECanvasAttributeNames.ID]: string;
  [ECanvasAttributeNames.TITLE]: string;
  [ECanvasAttributeNames.SCENE_VERSION]: number;
  [ECanvasAttributeNames.SCENE]: string;
  [ECanvasAttributeNames.PREVIEW]: string;
  [ECanvasAttributeNames.PREVIEW_WIDTH]: number;
  [ECanvasAttributeNames.PREVIEW_HEIGHT]: number;
};

export type TCanvasValidationErrorCode =
  | "invalid-encoding"
  | "invalid-scene"
  | "oversized"
  | "unsupported-file"
  | "unsupported-version"
  | "invalid-preview";

export type TCanvasValidationResult<T> = { ok: true; value: T } | { ok: false; code: TCanvasValidationErrorCode };

export type TCanvasUpdate = Partial<
  Pick<
    TCanvasAttributes,
    | ECanvasAttributeNames.TITLE
    | ECanvasAttributeNames.SCENE_VERSION
    | ECanvasAttributeNames.SCENE
    | ECanvasAttributeNames.PREVIEW
    | ECanvasAttributeNames.PREVIEW_WIDTH
    | ECanvasAttributeNames.PREVIEW_HEIGHT
  >
>;

export type CanvasExtensionOptions = {
  isEditable: boolean;
  translate?: TEditorTranslation;
  userName?: string;
  provider?: HocuspocusProvider;
};

export type CanvasExtensionStorage = {
  pendingOpenCanvasId: string | null;
};

export type CanvasExtensionType = TiptapNode<CanvasExtensionOptions, CanvasExtensionStorage>;

export type TInsertCanvasProps = {
  id?: string;
  pos?: number;
  title?: string;
};

export type TCanvasAwarenessState = {
  canvasId: string;
  userName?: string;
};
