/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import {
  EMPTY_CANVAS_PREVIEW,
  ECanvasAttributeNames,
  convertHTMLDocumentToAllFormats,
  encodeCanvasScene,
  getAllDocumentFormatsFromDocumentEditorBinaryData,
  getBinaryDataFromDocumentEditorHTMLString,
  getCanvasSceneFingerprint,
  isCurrentCanvasSaveRevision,
  shouldRenderCanvasPreview,
} from "@plane/editor";
import type { TCanvasScene } from "@plane/editor";

const encodedScene = (label: string): string => {
  const result = encodeCanvasScene({
    version: 1,
    elements: [{ id: label, type: "rectangle", x: 1, y: 2 }],
    appState: { viewBackgroundColor: "#ffffff" },
  });
  if (!result.ok) throw new Error(result.code);
  return result.value;
};

const canvasHTML = (id: string, title: string, version = 1, preview = EMPTY_CANVAS_PREVIEW): string =>
  `<canvas-component data-canvas-id="${id}" data-title="${title}" data-scene-version="${version}" data-scene="${encodedScene(
    title
  )}" data-preview="${preview}" data-preview-width="720" data-preview-height="405"></canvas-component>`;

const getCanvasNodes = (contentJSON: object) => {
  const json = contentJSON as { content: Array<{ type: string; attrs?: Record<string, unknown> }> };
  return json.content.filter((node) => node.type === "canvas-component");
};

describe("Canvas document round trips", () => {
  it("commits only the latest revision after rapid changes and an immediate close flush", () => {
    const firstDebouncedRevision = 1;
    const secondPendingRevision = 2;
    const closeFlushRevision = secondPendingRevision;

    expect(isCurrentCanvasSaveRevision(firstDebouncedRevision, secondPendingRevision)).toBe(false);
    expect(isCurrentCanvasSaveRevision(closeFlushRevision, secondPendingRevision)).toBe(true);
  });

  it("deduplicates semantically identical scene snapshots", () => {
    const first: TCanvasScene = {
      version: 1,
      elements: [{ id: "shape", type: "rectangle", x: 1, y: 2 }],
      appState: { gridSize: 20, viewBackgroundColor: "#ffffff" },
    };
    const reordered: TCanvasScene = {
      appState: { viewBackgroundColor: "#ffffff", gridSize: 20 },
      elements: [{ y: 2, x: 1, type: "rectangle", id: "shape" }],
      version: 1,
    };
    const moved: TCanvasScene = {
      ...first,
      elements: [{ id: "shape", type: "rectangle", x: 2, y: 2 }],
    };

    expect(getCanvasSceneFingerprint(first)).toBe(getCanvasSceneFingerprint(reordered));
    expect(getCanvasSceneFingerprint(moved)).not.toBe(getCanvasSceneFingerprint(first));
  });

  it("hides a valid preview when the scene version is unsupported", () => {
    const preview = `data:image/png;base64,${EMPTY_CANVAS_PREVIEW}`;

    expect(shouldRenderCanvasPreview(preview, "unsupported-version")).toBe(false);
    expect(shouldRenderCanvasPreview(preview)).toBe(true);
  });

  it("preserves Canvas attributes through HTML, JSON, and Yjs binary", () => {
    const html = `<p>Before</p>${canvasHTML("c4d18686-95cf-4f3b-aab7-c2b595f454ae", "Architecture")}<p>After</p>`;
    const binary = getBinaryDataFromDocumentEditorHTMLString(html);
    const formats = getAllDocumentFormatsFromDocumentEditorBinaryData(binary, false);
    const [canvas] = getCanvasNodes(formats.contentJSON);
    expect(canvas?.attrs).toEqual({
      [ECanvasAttributeNames.ID]: "c4d18686-95cf-4f3b-aab7-c2b595f454ae",
      [ECanvasAttributeNames.TITLE]: "Architecture",
      [ECanvasAttributeNames.SCENE_VERSION]: 1,
      [ECanvasAttributeNames.SCENE]: encodedScene("Architecture"),
      [ECanvasAttributeNames.PREVIEW]: EMPTY_CANVAS_PREVIEW,
      [ECanvasAttributeNames.PREVIEW_WIDTH]: 720,
      [ECanvasAttributeNames.PREVIEW_HEIGHT]: 405,
    });
    expect(formats.contentHTML).toContain('data-canvas-id="c4d18686-95cf-4f3b-aab7-c2b595f454ae"');
    expect(formats.contentHTML).toContain(">After</p>");
  });

  it("keeps multiple Canvas blocks independent", () => {
    const html = `${canvasHTML("c4d18686-95cf-4f3b-aab7-c2b595f454ae", "One")}${canvasHTML(
      "53e6560f-c425-4754-ab24-b23541be526f",
      "Two"
    )}`;
    const binary = getBinaryDataFromDocumentEditorHTMLString(html);
    const formats = getAllDocumentFormatsFromDocumentEditorBinaryData(binary, false);
    const canvases = getCanvasNodes(formats.contentJSON);
    expect(canvases).toHaveLength(2);
    expect(canvases.map((node) => node.attrs?.[ECanvasAttributeNames.ID])).toEqual([
      "c4d18686-95cf-4f3b-aab7-c2b595f454ae",
      "53e6560f-c425-4754-ab24-b23541be526f",
    ]);
    expect(canvases.map((node) => node.attrs?.[ECanvasAttributeNames.SCENE])).toEqual([
      encodedScene("One"),
      encodedScene("Two"),
    ]);
  });

  it("preserves Canvas placement and attributes through HTML-based duplicate and version restore paths", () => {
    const originalHTML = `<p>First</p>${canvasHTML(
      "c4d18686-95cf-4f3b-aab7-c2b595f454ae",
      "Architecture"
    )}<p>Middle</p>${canvasHTML("53e6560f-c425-4754-ab24-b23541be526f", "Workflow")}<p>Last</p>`;
    const firstPass = convertHTMLDocumentToAllFormats({ document_html: originalHTML, variant: "document" });
    const restored = convertHTMLDocumentToAllFormats({
      document_html: firstPass.description_html,
      variant: "document",
    });

    expect(restored.description_json).toEqual(firstPass.description_json);
    expect(restored.description_html).toEqual(firstPass.description_html);
    expect(restored.description_binary).toBeTypeOf("string");
    expect(restored.description_html.indexOf("First")).toBeLessThan(restored.description_html.indexOf("Architecture"));
    expect(restored.description_html.indexOf("Architecture")).toBeLessThan(restored.description_html.indexOf("Middle"));
    expect(restored.description_html.indexOf("Middle")).toBeLessThan(restored.description_html.indexOf("Workflow"));
    expect(restored.description_html.indexOf("Workflow")).toBeLessThan(restored.description_html.indexOf("Last"));
  });

  it("preserves unsupported versions for a future client", () => {
    const binary = getBinaryDataFromDocumentEditorHTMLString(
      canvasHTML("c4d18686-95cf-4f3b-aab7-c2b595f454ae", "Future", 2)
    );
    const rendered = getAllDocumentFormatsFromDocumentEditorBinaryData(binary, false).contentHTML;
    expect(rendered).toContain('data-scene-version="2"');
    expect(rendered).toContain('data-title="Future"');
  });

  it("retains the Canvas schema when interactive editing is disabled", () => {
    const binary = getBinaryDataFromDocumentEditorHTMLString(
      canvasHTML("c4d18686-95cf-4f3b-aab7-c2b595f454ae", "Disabled")
    );
    const formats = getAllDocumentFormatsFromDocumentEditorBinaryData(binary, false);
    expect(getCanvasNodes(formats.contentJSON)).toHaveLength(1);
    expect(formats.contentHTML).toContain('data-title="Disabled"');
  });
});
