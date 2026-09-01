import { ReactNodeViewRenderer } from "@tiptap/react";
import { AttachmentExtensionConfig } from "./extension-config";
import { AttachmentNodeView } from "./node-view";
import type { AttachmentExtensionOptions, AttachmentExtensionStorage, AttachmentExtensionType } from "./types";
import type { TFileHandler } from "@/types";

export function AttachmentExtension(fileHandler: TFileHandler) {
  return AttachmentExtensionConfig.extend<AttachmentExtensionOptions, AttachmentExtensionStorage>({
    addOptions() {
      return {
        getAssetSource: fileHandler.getAssetSrc,
        getDownloadSource: fileHandler.getAssetDownloadSrc,
        uploadAsset: fileHandler.upload,
        cancelUpload: fileHandler.cancel,
        duplicateAsset: fileHandler.duplicate,
      };
    },
    addStorage() {
      return {
        fileMap: new Map(),
        deletedFileSet: new Map(),
        maxFileSize: fileHandler.validation?.maxFileSize ?? 100 * 1024 * 1024,
      };
    },
    addNodeView() {
      return ReactNodeViewRenderer((props) => (
        <AttachmentNodeView {...props} extension={props.extension as AttachmentExtensionType} />
      ));
    },
  });
}
