import { mergeAttributes, Node } from "@tiptap/core";
import { v4 as uuidv4 } from "uuid";
import { CORE_EXTENSIONS } from "@/constants/extension";
import type {
  AttachmentExtensionOptions,
  AttachmentExtensionStorage,
  TAttachmentAttributes,
  InsertAttachmentProps,
} from "./types";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    [CORE_EXTENSIONS.ATTACHMENT]: {
      insertAttachment: (props: InsertAttachmentProps) => ReturnType;
    };
  }
}

export const AttachmentExtensionConfig = Node.create<AttachmentExtensionOptions, AttachmentExtensionStorage>({
  name: CORE_EXTENSIONS.ATTACHMENT,
  group: "block",
  atom: true,

  addAttributes() {
    return {
      id: { default: "" },
      assetId: { default: null },
      src: { default: null },
      name: { default: "Attachment" },
      mimeType: { default: "application/octet-stream" },
      size: { default: 0 },
      presentation: { default: "download" },
      status: { default: "pending" },
    };
  },

  parseHTML() {
    return [{ tag: "attachment-component" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["attachment-component", mergeAttributes(HTMLAttributes)];
  },

  addCommands() {
    return {
      insertAttachment:
        (props: InsertAttachmentProps) =>
        ({ commands }) => {
          const id = uuidv4();
          if (props.file) this.storage.fileMap.set(id, props.file);
          const attrs: Partial<TAttachmentAttributes> = props.file
            ? {
                id,
                name: props.file.name,
                mimeType: props.file.type || "application/octet-stream",
                size: props.file.size,
              }
            : { id };
          return props.pos !== undefined
            ? commands.insertContentAt(props.pos, { type: this.name, attrs })
            : commands.insertContent({ type: this.name, attrs });
        },
    };
  },
});
