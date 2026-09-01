/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// extensions
import type { ImageExtensionStorage } from "@/extensions/image";
import type { AttachmentExtensionStorage } from "@/extensions/attachment";

export type ExtensionFileSetStorageKey =
  | Extract<keyof ImageExtensionStorage, "deletedImageSet">
  | Extract<keyof AttachmentExtensionStorage, "deletedFileSet">;
