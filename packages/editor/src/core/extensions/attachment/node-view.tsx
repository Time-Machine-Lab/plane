/* oxlint-disable jsx-a11y/media-has-caption -- Plane cannot synthesize caption tracks for user-provided media. */
import { NodeViewWrapper } from "@tiptap/react";
import type { NodeViewProps } from "@tiptap/react";
import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import type { AttachmentExtensionType, TAttachmentAttributes } from "./types";

type Props = Omit<NodeViewProps, "extension"> & { extension: AttachmentExtensionType };

export function AttachmentNodeView({ extension, node, updateAttributes, editor }: Props) {
  const attributes = node.attrs as TAttachmentAttributes;
  const { id, assetId, name, mimeType, size, status } = attributes;
  const [previewUrl, setPreviewUrl] = useState<string>();
  const [downloadUrl, setDownloadUrl] = useState<string>();
  const [textContent, setTextContent] = useState<string>();
  const [htmlLaunched, setHtmlLaunched] = useState(false);
  const [showHtmlSource, setShowHtmlSource] = useState(false);
  const [canvasScale, setCanvasScale] = useState(1);
  const inputRef = useRef<HTMLInputElement>(null);
  const htmlFrameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const file = extension.storage.fileMap.get(id);
    const uploadAsset = extension.options.uploadAsset;
    if (!assetId && status === "pending" && file && uploadAsset) {
      updateAttributes({ status: "uploading", name: file.name, mimeType: file.type || mimeType, size: file.size });
      const upload = async () => {
        try {
          const uploadedId = await uploadAsset(id, file);
          updateAttributes({ assetId: uploadedId, src: uploadedId, status: "ready" });
          extension.storage.fileMap.delete(id);
        } catch {
          updateAttributes({ status: "failed" });
        }
      };
      void upload();
    }
  }, [assetId, extension, id, mimeType, status, updateAttributes]);

  useEffect(() => {
    if (status !== "duplicating" || !assetId || !extension.options.duplicateAsset) return;
    extension.options
      .duplicateAsset(assetId)
      .then((newAssetId: string) => updateAttributes({ assetId: newAssetId, src: newAssetId, status: "ready" }))
      .catch(() => updateAttributes({ status: "failed" }));
  }, [assetId, extension.options, status, updateAttributes]);

  useEffect(() => {
    if (!assetId) return;
    editor.commands.updateAssetsList?.({
      asset: {
        id,
        href: `#attachment-${id}`,
        name,
        src: assetId,
        mimeType,
        size,
        presentation: attributes.presentation,
        type: "attachment-component",
      },
    });
    let disposed = false;
    const loadSources = async () => {
      try {
        const [previewSource, downloadSource] = await Promise.all([
          extension.options.getAssetSource(assetId),
          extension.options.getDownloadSource(assetId),
        ]);
        if (!disposed) {
          setPreviewUrl(previewSource);
          setDownloadUrl(downloadSource);
        }
      } catch {
        // The attachment card retains its metadata and unavailable fallback.
      }
    };
    void loadSources();
    return () => {
      disposed = true;
    };
  }, [assetId, attributes.presentation, editor.commands, id, mimeType, name, size, extension.options]);

  const isHtml = mimeType === "text/html" || /\.html?$/i.test(name);
  const isCanvas = mimeType === "application/canvas" || /\.canvas$/i.test(name);
  const isText = mimeType === "text/plain" || mimeType === "text/markdown";

  useEffect(() => {
    if (!previewUrl || (!isHtml && !isCanvas && !isText) || size > 256 * 1024) return;
    const controller = new AbortController();
    const loadText = async () => {
      try {
        const response = await fetch(previewUrl, { signal: controller.signal });
        if (!response.ok) throw new Error("Preview unavailable");
        const value = await response.text();
        if (new TextEncoder().encode(value).byteLength <= 256 * 1024) setTextContent(value);
      } catch {
        // Download remains available when the bounded preview cannot load.
      }
    };
    void loadText();
    return () => controller.abort();
  }, [isCanvas, isHtml, isText, previewUrl, size]);

  const canvasDocument = useMemo(() => {
    if (!isCanvas || !textContent) return null;
    try {
      const value = JSON.parse(textContent) as {
        nodes?: Array<{
          id?: string;
          type?: string;
          text?: string;
          url?: string;
          x?: number;
          y?: number;
          width?: number;
          height?: number;
        }>;
        edges?: Array<{ id?: string; fromNode?: string; toNode?: string }>;
      };
      if (!Array.isArray(value.nodes) || value.nodes.length > 500) return null;
      const nodes = value.nodes.slice(0, 500);
      const byId = new Map(nodes.map((item) => [item.id, item]));
      const edges = (value.edges ?? []).slice(0, 1000).map((edge) => {
        const from = byId.get(edge.fromNode);
        const to = byId.get(edge.toNode);
        if (!from || !to) return null;
        const edgeKey =
          edge.id ??
          `${edge.fromNode ?? "unknown"}:${edge.toNode ?? "unknown"}:${from.x ?? 0}:${from.y ?? 0}:${to.x ?? 0}:${to.y ?? 0}`;
        return (
          <line
            key={edgeKey}
            x1={(from.x ?? 0) + (from.width ?? 240) / 2}
            y1={(from.y ?? 0) + (from.height ?? 100) / 2}
            x2={(to.x ?? 0) + (to.width ?? 240) / 2}
            y2={(to.y ?? 0) + (to.height ?? 100) / 2}
            stroke="currentColor"
            strokeWidth="2"
            opacity="0.4"
          />
        );
      });
      const renderedNodes = nodes.map((item) => (
        <div
          key={item.id ?? `${item.type ?? "node"}:${item.x ?? 0}:${item.y ?? 0}:${item.text ?? item.url ?? ""}`}
          className="text-xs absolute overflow-hidden rounded border border-subtle bg-layer-1 p-2 whitespace-pre-wrap"
          style={{
            left: Math.max(0, item.x ?? 0),
            top: Math.max(0, item.y ?? 0),
            width: Math.min(600, Math.max(80, item.width ?? 240)),
            height: Math.min(400, Math.max(40, item.height ?? 100)),
          }}
        >
          {item.type === "file"
            ? "Unresolved file"
            : item.type === "link"
              ? (item.url ?? "Link")
              : (item.text ?? item.type ?? "Canvas node")}
        </div>
      ));
      return { edges, nodes: renderedNodes };
    } catch {
      return null;
    }
  }, [isCanvas, textContent]);

  const sandboxedHtml = useMemo(() => {
    if (!textContent) return "";
    const csp =
      "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none';\">";
    const bridge =
      '<script>document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("a[href]");if(a){e.preventDefault();parent.postMessage({type:"plane-attachment-link",href:a.href},"*")}},true);document.addEventListener("submit",function(e){e.preventDefault()},true);</script>';
    const guarded = `${csp}${bridge}`;
    return /<head[\s>]/i.test(textContent)
      ? textContent.replace(/<head([^>]*)>/i, `<head$1>${guarded}`)
      : `${guarded}${textContent}`;
  }, [textContent]);

  useEffect(() => {
    if (!htmlLaunched) return;
    const onMessage = (event: MessageEvent) => {
      if (event.source !== htmlFrameRef.current?.contentWindow || event.data?.type !== "plane-attachment-link") return;
      try {
        const url = new URL(String(event.data.href));
        if (!["http:", "https:"].includes(url.protocol)) return;
        if (window.confirm(`Open external link?\n${url.toString()}`))
          window.open(url.toString(), "_blank", "noopener,noreferrer");
      } catch {
        return;
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [htmlLaunched]);

  const canPreview =
    Boolean(previewUrl) &&
    (mimeType.startsWith("image/") ||
      mimeType === "application/pdf" ||
      mimeType.startsWith("video/") ||
      mimeType.startsWith("audio/"));
  const uploadProgress = editor.storage.utility?.assetsUploadStatus?.[id];
  const uploadSelectedFile = async (file: File) => {
    try {
      const uploadedId = await extension.options.uploadAsset?.(id, file);
      if (uploadedId) updateAttributes({ assetId: uploadedId, src: uploadedId, status: "ready" });
    } catch {
      updateAttributes({ status: "failed" });
    }
  };

  return (
    <NodeViewWrapper className="attachment-component my-2" data-attachment-id={assetId ?? id}>
      {!assetId && status === "pending" && editor.isEditable && !extension.storage.fileMap.has(id) && (
        <div className="rounded-md border border-dashed border-subtle p-3">
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            onChange={(event: ChangeEvent<HTMLInputElement>) => {
              const file = event.target.files?.[0];
              if (!file) return;
              extension.storage.fileMap.set(id, file);
              updateAttributes({
                name: file.name,
                mimeType: file.type || "application/octet-stream",
                size: file.size,
                status: "uploading",
              });
              void uploadSelectedFile(file);
            }}
          />
          <button type="button" className="text-sm text-link-primary" onClick={() => inputRef.current?.click()}>
            Choose attachment
          </button>
        </div>
      )}
      <div className="flex items-center gap-3 rounded-md border border-subtle bg-layer-1 p-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm truncate font-medium">{name}</div>
          <div className="text-xs text-tertiary">
            {mimeType} {size ? `(${Math.ceil(size / 1024)} KB)` : ""}
          </div>
          {status === "uploading" && (
            <div className="text-xs flex items-center gap-2 text-tertiary">
              <span>Uploading{typeof uploadProgress === "number" ? ` ${Math.round(uploadProgress)}%` : "..."}</span>
              <button
                type="button"
                onClick={() => {
                  extension.options.cancelUpload();
                  updateAttributes({ status: "failed" });
                }}
                className="text-link-primary"
              >
                Cancel
              </button>
            </div>
          )}
          {status === "failed" && (
            <div className="text-xs text-red-500 flex items-center gap-2">
              <span>Upload failed</span>
              {extension.storage.fileMap.has(id) && (
                <button
                  type="button"
                  onClick={() => updateAttributes({ status: "pending" })}
                  className="text-link-primary"
                >
                  Retry
                </button>
              )}
            </div>
          )}
        </div>
        {canPreview && mimeType.startsWith("image/") && (
          <img src={previewUrl} alt={name} className="max-h-32 max-w-32 rounded object-contain" />
        )}
        {canPreview && mimeType === "application/pdf" && (
          <iframe src={previewUrl} title={name} sandbox="allow-same-origin" className="h-32 w-48" />
        )}
        {canPreview && mimeType.startsWith("video/") && (
          <video src={previewUrl} controls className="max-h-32 max-w-48" />
        )}
        {canPreview && mimeType.startsWith("audio/") && <audio src={previewUrl} controls />}
        {downloadUrl && (
          <a href={downloadUrl} download={name} target="_blank" rel="noreferrer" className="text-sm text-link-primary">
            Download
          </a>
        )}
      </div>
      {isText && textContent && (
        <pre className="text-xs mt-2 max-h-80 overflow-auto rounded border border-subtle bg-layer-2 p-3 whitespace-pre-wrap">
          {textContent}
        </pre>
      )}
      {isCanvas && canvasDocument && (
        <div className="mt-2 rounded border border-subtle bg-layer-2">
          <div className="flex gap-1 border-b border-subtle p-1">
            <button
              type="button"
              onClick={() => setCanvasScale((value) => Math.max(0.25, value - 0.25))}
              aria-label="Zoom out"
            >
              -
            </button>
            <button type="button" onClick={() => setCanvasScale(1)} aria-label="Reset zoom">
              {Math.round(canvasScale * 100)}%
            </button>
            <button
              type="button"
              onClick={() => setCanvasScale((value) => Math.min(2, value + 0.25))}
              aria-label="Zoom in"
            >
              +
            </button>
          </div>
          <div className="relative h-80 overflow-auto">
            <div
              className="relative origin-top-left"
              style={{ width: 1600, height: 1000, transform: `scale(${canvasScale})` }}
            >
              <svg className="absolute inset-0 size-full" aria-hidden="true">
                {canvasDocument.edges}
              </svg>
              {canvasDocument.nodes}
            </div>
          </div>
        </div>
      )}
      {isHtml && textContent && !htmlLaunched && (
        <div className="mt-2 flex gap-3">
          <button type="button" onClick={() => setHtmlLaunched(true)} className="text-sm text-link-primary">
            Open interactive preview
          </button>
          <button
            type="button"
            onClick={() => setShowHtmlSource((value) => !value)}
            className="text-sm text-link-primary"
          >
            {showHtmlSource ? "Hide source" : "View source"}
          </button>
        </div>
      )}
      {isHtml && showHtmlSource && (
        <pre className="text-xs mt-2 max-h-64 overflow-auto rounded border border-subtle bg-layer-2 p-3 whitespace-pre-wrap">
          {textContent}
        </pre>
      )}
      {isHtml && htmlLaunched && (
        <div className="relative mt-2 h-96 overflow-hidden rounded border border-subtle">
          <iframe
            ref={htmlFrameRef}
            title={name}
            srcDoc={sandboxedHtml}
            sandbox="allow-scripts"
            referrerPolicy="no-referrer"
            className="h-full w-full"
          />
          <button
            type="button"
            onClick={() => setHtmlLaunched(false)}
            className="text-xs absolute top-2 right-2 rounded bg-layer-2 px-2 py-1"
          >
            Stop
          </button>
        </div>
      )}
      {!editor.isEditable && status === "pending" && <span className="sr-only">Attachment unavailable</span>}
    </NodeViewWrapper>
  );
}
