/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
// plane imports
import type { ADDITIONAL_EXTENSIONS } from "@plane/utils";
import { CORE_EXTENSIONS } from "@plane/utils";
// extensions
import { getImageBlockId } from "@/extensions/custom-image/utils";
// plane editor imports
import { ADDITIONAL_ASSETS_META_DATA_RECORD } from "@/plane-editor/constants/assets";
// types
import type { TEditorAsset } from "@/types";

export type TAssetMetaDataRecord = (attrs: ProseMirrorNode["attrs"]) => TEditorAsset | undefined;

export const CORE_ASSETS_META_DATA_RECORD: Partial<
  Record<CORE_EXTENSIONS | ADDITIONAL_EXTENSIONS, TAssetMetaDataRecord>
> = {
  [CORE_EXTENSIONS.IMAGE]: (attrs) => {
    if (!attrs?.src) return;
    return {
      href: `#${getImageBlockId(attrs?.id ?? "")}`,
      id: attrs?.id,
      name: `image-${attrs?.id}`,
      size: 0,
      src: attrs?.src,
      type: CORE_EXTENSIONS.IMAGE,
    };
  },
  [CORE_EXTENSIONS.CUSTOM_IMAGE]: (attrs) => {
    if (!attrs?.src) return;
    return {
      href: `#${getImageBlockId(attrs?.id ?? "")}`,
      id: attrs?.id,
      name: `image-${attrs?.id}`,
      size: 0,
      src: attrs?.src,
      type: CORE_EXTENSIONS.CUSTOM_IMAGE,
    };
  },
  [CORE_EXTENSIONS.ATTACHMENT]: (attrs) => {
    if (!attrs?.assetId && !attrs?.src) return;
    return {
      href: `#attachment-${attrs?.id ?? attrs?.assetId}`,
      id: attrs?.id ?? attrs?.assetId,
      name: attrs?.name ?? "Attachment",
      src: attrs?.assetId ?? attrs?.src,
      mimeType: attrs?.mimeType,
      size: attrs?.size ?? 0,
      presentation: attrs?.presentation,
      type: "attachment-component",
    };
  },
  ...ADDITIONAL_ASSETS_META_DATA_RECORD,
};
