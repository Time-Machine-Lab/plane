/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { CommandProps } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { ReactNodeViewRenderer } from "@tiptap/react";
import { v4 as uuidv4 } from "uuid";
import { CORE_EXTENSIONS } from "@/constants/extension";
import { insertEmptyParagraphAtNodeBoundaries } from "@/helpers/insert-empty-paragraph-at-node-boundary";
import { CanvasNodeView } from "./node-view";
import { CanvasExtensionConfig } from "./extension-config";
import { getCanvasTranslation } from "./translations";
import { ECanvasAttributeNames } from "./types";
import type {
  CanvasExtensionOptions,
  CanvasExtensionStorage,
  TCanvasAttributes,
  TCanvasPreviewSize,
  TCanvasUpdate,
  TInsertCanvasProps,
} from "./types";
import { CANVAS_PREVIEW_SIZES, getDefaultCanvasAttributes, normalizeCanvasTitle } from "./utils";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.CANVAS]: {
      deleteCanvasBlock: (canvasId: string) => ReturnType;
      duplicateCanvasBlock: (canvasId: string) => ReturnType;
      insertCanvas: (props?: TInsertCanvasProps) => ReturnType;
      openCanvas: (canvasId: string) => ReturnType;
      setCanvasPreviewSize: (canvasId: string, size: TCanvasPreviewSize) => ReturnType;
      updateCanvas: (canvasId: string, update: TCanvasUpdate) => ReturnType;
    };
  }
}

const findCanvasNode = (
  document: ProseMirrorNode,
  canvasId: string
): { node: ProseMirrorNode; position: number } | null => {
  let result: { node: ProseMirrorNode; position: number } | null = null;
  document.descendants((node, position) => {
    if (node.type.name === CORE_EXTENSIONS.CANVAS && node.attrs[ECanvasAttributeNames.ID] === canvasId) {
      result = { node, position };
      return false;
    }
    return result === null;
  });
  return result;
};

const updateCanvasNode = (
  canvasId: string,
  update: TCanvasUpdate,
  fallbackTitle: string,
  { state, dispatch }: Pick<CommandProps, "state" | "dispatch">
): boolean => {
  const match = findCanvasNode(state.doc, canvasId);
  if (!match) return false;
  const boundedUpdate = { ...update };
  if (typeof boundedUpdate[ECanvasAttributeNames.TITLE] === "string") {
    boundedUpdate[ECanvasAttributeNames.TITLE] = normalizeCanvasTitle(
      boundedUpdate[ECanvasAttributeNames.TITLE],
      fallbackTitle
    );
  }
  if (dispatch) dispatch(state.tr.setNodeMarkup(match.position, undefined, { ...match.node.attrs, ...boundedUpdate }));
  return true;
};

export const CanvasExtension = (options: CanvasExtensionOptions) =>
  CanvasExtensionConfig.extend<CanvasExtensionOptions, CanvasExtensionStorage>({
    selectable: true,
    draggable: options.isEditable,

    addOptions() {
      return options;
    },

    addCommands() {
      return {
        insertCanvas:
          (props = {}) =>
          ({ commands }) => {
            if (!this.options.isEditable) return false;
            const id = props.id ?? uuidv4();
            const content = {
              type: this.name,
              attrs: getDefaultCanvasAttributes(
                id,
                props.title ?? getCanvasTranslation(this.options.translate, "canvas.untitled")
              ),
            };
            const inserted =
              props.pos === undefined ? commands.insertContent(content) : commands.insertContentAt(props.pos, content);
            if (inserted) this.storage.pendingOpenCanvasId = id;
            return inserted;
          },
        updateCanvas: (canvasId, update) => (props) => {
          if (!this.options.isEditable) return false;
          return updateCanvasNode(
            canvasId,
            update,
            getCanvasTranslation(this.options.translate, "canvas.untitled"),
            props
          );
        },
        setCanvasPreviewSize: (canvasId, size) => (props) => {
          if (!this.options.isEditable) return false;
          const dimensions = CANVAS_PREVIEW_SIZES[size];
          return updateCanvasNode(
            canvasId,
            {
              [ECanvasAttributeNames.PREVIEW_WIDTH]: dimensions.width,
              [ECanvasAttributeNames.PREVIEW_HEIGHT]: dimensions.height,
            },
            getCanvasTranslation(this.options.translate, "canvas.untitled"),
            props
          );
        },
        openCanvas: (canvasId) => () => {
          if (typeof window === "undefined") return false;
          window.dispatchEvent(new CustomEvent("plane:canvas-open", { detail: { canvasId } }));
          return true;
        },
        duplicateCanvasBlock:
          (canvasId) =>
          ({ state, dispatch }) => {
            if (!this.options.isEditable) return false;
            const match = findCanvasNode(state.doc, canvasId);
            if (!match) return false;
            const duplicateAttributes: TCanvasAttributes = {
              ...(match.node.attrs as TCanvasAttributes),
              [ECanvasAttributeNames.ID]: uuidv4(),
            };
            if (dispatch)
              dispatch(state.tr.insert(match.position + match.node.nodeSize, this.type.create(duplicateAttributes)));
            return true;
          },
        deleteCanvasBlock:
          (canvasId) =>
          ({ state, dispatch }) => {
            if (!this.options.isEditable) return false;
            const match = findCanvasNode(state.doc, canvasId);
            if (!match) return false;
            if (dispatch) dispatch(state.tr.delete(match.position, match.position + match.node.nodeSize));
            return true;
          },
      };
    },

    addKeyboardShortcuts() {
      return {
        ArrowDown: insertEmptyParagraphAtNodeBoundaries("down", this.name),
        ArrowUp: insertEmptyParagraphAtNodeBoundaries("up", this.name),
      };
    },

    addNodeView() {
      return ReactNodeViewRenderer((props) => (
        <CanvasNodeView
          {...props}
          isEditable={this.options.isEditable}
          provider={this.options.provider}
          userName={this.options.userName}
          translate={this.options.translate}
        />
      ));
    },
  });
