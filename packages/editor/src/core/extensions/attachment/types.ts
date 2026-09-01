import type { Node } from "@tiptap/core";
import type { TFileHandler } from "@/types";

export type TAttachmentPresentation = "text" | "markdown" | "pdf" | "video" | "audio" | "canvas" | "html" | "download";

export type TAttachmentAttributes = {
  id: string;
  assetId: string | null;
  src: string | null;
  name: string;
  mimeType: string;
  size: number;
  presentation: TAttachmentPresentation;
  status: "pending" | "uploading" | "ready" | "failed" | "duplicating";
};

export type InsertAttachmentProps = { file?: File; pos?: number; event: "insert" | "drop" };

export type AttachmentExtensionOptions = {
  getAssetSource: TFileHandler["getAssetSrc"];
  getDownloadSource: TFileHandler["getAssetDownloadSrc"];
  uploadAsset?: TFileHandler["upload"];
  cancelUpload: TFileHandler["cancel"];
  duplicateAsset?: TFileHandler["duplicate"];
};

export type AttachmentExtensionStorage = {
  fileMap: Map<string, File>;
  deletedFileSet: Map<string, boolean>;
  maxFileSize: number;
};

export type AttachmentExtensionType = Node<AttachmentExtensionOptions, AttachmentExtensionStorage>;
