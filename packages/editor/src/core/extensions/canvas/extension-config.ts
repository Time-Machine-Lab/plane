/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { mergeAttributes, Node } from "@tiptap/core";
import type { MarkdownSerializerState } from "@tiptap/pm/markdown";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { CORE_EXTENSIONS } from "@/constants/extension";
import { ECanvasAttributeNames } from "./types";
import type { CanvasExtensionType, TCanvasAttributes } from "./types";
import { getDefaultCanvasAttributes } from "./utils";

const escapeAttribute = (value: string): string =>
  value.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

export const CanvasExtensionConfig: CanvasExtensionType = Node.create({
  name: CORE_EXTENSIONS.CANVAS,
  group: "block",
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    const defaults = getDefaultCanvasAttributes("00000000-0000-4000-8000-000000000000");
    return Object.values(ECanvasAttributeNames).reduce(
      (attributes, name) => {
        attributes[name] = { default: defaults[name] };
        return attributes;
      },
      {} as Record<ECanvasAttributeNames, { default: TCanvasAttributes[ECanvasAttributeNames] }>
    );
  },

  addStorage() {
    return {
      pendingOpenCanvasId: null,
      markdown: {
        serialize(state: MarkdownSerializerState, node: ProseMirrorNode) {
          const attrs = node.attrs as TCanvasAttributes;
          const renderedAttributes = Object.values(ECanvasAttributeNames)
            .map((name) => `${name}="${escapeAttribute(String(attrs[name] ?? ""))}"`)
            .join(" ");
          state.write(`<canvas-component ${renderedAttributes}></canvas-component>`);
          state.closeBlock(node);
        },
      },
    };
  },

  parseHTML() {
    return [{ tag: "canvas-component" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["canvas-component", mergeAttributes(HTMLAttributes)];
  },
});
