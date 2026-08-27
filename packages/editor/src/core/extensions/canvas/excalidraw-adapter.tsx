/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo } from "react";
import { Excalidraw, exportToBlob } from "@excalidraw/excalidraw";
import type {
  AppState,
  BinaryFiles,
  ExcalidrawInitialDataState,
  ExcalidrawImperativeAPI,
} from "@excalidraw/excalidraw/types";
import type { ExcalidrawElement } from "@excalidraw/excalidraw/element/types";
// oxlint-disable-next-line import/no-unassigned-import -- Excalidraw's editor chrome requires its global stylesheet.
import "@excalidraw/excalidraw/index.css";
import type { TCanvasScene, TCanvasValidationErrorCode } from "./types";
import { EMPTY_CANVAS_PREVIEW } from "./utils";

type Props = {
  isReadOnly: boolean;
  onChange: (scene: TCanvasScene) => void;
  onInvalidChange: (code: TCanvasValidationErrorCode) => void;
  scene: TCanvasScene;
  theme: "dark" | "light";
};

const blobToBase64 = async (blob: Blob): Promise<string> => {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
};

export const renderCanvasPreview = async (scene: TCanvasScene, width: number, height: number): Promise<string> => {
  if (scene.elements.length === 0) return EMPTY_CANVAS_PREVIEW;
  const elements = scene.elements as unknown as readonly ExcalidrawElement[];
  const blob = await exportToBlob({
    elements,
    appState: {
      exportBackground: true,
      exportWithDarkMode: false,
      viewBackgroundColor: scene.appState.viewBackgroundColor ?? "#ffffff",
    },
    files: null,
    mimeType: "image/png",
    getDimensions: () => ({ width, height, scale: 1 }),
  });
  return blobToBase64(blob);
};

export function ExcalidrawAdapter(props: Props) {
  const { isReadOnly, onChange, onInvalidChange, scene, theme } = props;
  const initialData = useMemo<ExcalidrawInitialDataState>(
    () => ({
      elements: scene.elements as unknown as readonly ExcalidrawElement[],
      appState: {
        gridSize: scene.appState.gridSize ?? undefined,
        viewBackgroundColor: scene.appState.viewBackgroundColor ?? "#ffffff",
      },
      files: undefined,
      scrollToContent: true,
    }),
    [scene]
  );

  const handleChange = useCallback(
    (elements: readonly ExcalidrawElement[], appState: AppState, files: BinaryFiles) => {
      if (Object.keys(files).length > 0 || elements.some((element) => "fileId" in element && !!element.fileId)) {
        onInvalidChange("unsupported-file");
        return;
      }
      onChange({
        version: 1,
        elements: JSON.parse(JSON.stringify(elements)) as TCanvasScene["elements"],
        appState: {
          gridSize: appState.gridSize,
          viewBackgroundColor: appState.viewBackgroundColor,
        },
      });
    },
    [onChange, onInvalidChange]
  );

  return (
    <Excalidraw
      initialData={initialData}
      excalidrawAPI={(_api: ExcalidrawImperativeAPI) => undefined}
      onChange={handleChange}
      theme={theme}
      viewModeEnabled={isReadOnly}
      zenModeEnabled={false}
      UIOptions={{
        canvasActions: {
          changeViewBackgroundColor: !isReadOnly,
          clearCanvas: !isReadOnly,
          export: false,
          loadScene: false,
          saveAsImage: false,
          toggleTheme: false,
        },
      }}
    />
  );
}
