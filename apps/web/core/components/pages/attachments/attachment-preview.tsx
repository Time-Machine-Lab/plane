/* oxlint-disable jsx-a11y/media-has-caption -- Plane cannot synthesize caption tracks for user-provided media. */
import { useEffect, useMemo, useState, type ReactNode } from "react";

export type PageAttachmentPreviewProps = {
  name: string;
  mimeType?: string | null;
  sourceUrl?: string;
  downloadUrl?: string;
  size?: number;
};

const MAX_TEXT_BYTES = 256 * 1024;
const MAX_CANVAS_NODES = 500;

const isolatedHtml = (value: string) => {
  const csp =
    "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none';\">";
  return /<head[\s>]/i.test(value) ? value.replace(/<head([^>]*)>/i, `<head$1>${csp}`) : `${csp}${value}`;
};

export function PageAttachmentPreview({
  name,
  mimeType = "application/octet-stream",
  sourceUrl,
  downloadUrl,
  size = 0,
}: PageAttachmentPreviewProps) {
  const [text, setText] = useState<string>();
  const [htmlLaunched, setHtmlLaunched] = useState(true);
  const [error, setError] = useState<string>();
  const isText = mimeType === "text/plain" || mimeType === "text/markdown";
  const isHtml = mimeType === "text/html" || mimeType === "application/xhtml+xml" || /\.html?$/i.test(name);
  const isCanvas = mimeType === "application/canvas" || /\.canvas$/i.test(name);

  useEffect(() => {
    if ((!isText && !isCanvas && !isHtml) || !sourceUrl || size > MAX_TEXT_BYTES) return;
    const controller = new AbortController();
    const loadPreview = async () => {
      try {
        const response = await fetch(sourceUrl, { signal: controller.signal });
        if (!response.ok) throw new Error("Unable to load preview");
        const value = await response.text();
        if (new TextEncoder().encode(value).byteLength > MAX_TEXT_BYTES) throw new Error("Preview is too large");
        setText(value);
      } catch (cause) {
        if ((cause as Error).name !== "AbortError") setError("Preview unavailable");
      }
    };
    void loadPreview();
    return () => controller.abort();
  }, [isCanvas, isHtml, isText, size, sourceUrl]);

  const canvas = useMemo(() => {
    if (!text || !isCanvas) return null;
    try {
      const document = JSON.parse(text) as {
        nodes?: Array<{ type?: string; text?: string; x?: number; y?: number; width?: number; height?: number }>;
      };
      if (!Array.isArray(document.nodes) || document.nodes.length > MAX_CANVAS_NODES) return null;
      return document.nodes
        .filter((node) => node.type === "text")
        .map((node) => (
          <div
            key={`${node.x ?? 0}:${node.y ?? 0}:${node.width ?? 240}:${node.height ?? 24}:${node.text ?? ""}`}
            className="text-sm absolute whitespace-pre-wrap"
            style={{ left: node.x ?? 0, top: node.y ?? 0, width: node.width ?? 240, minHeight: node.height ?? 24 }}
          >
            {node.text ?? ""}
          </div>
        ));
    } catch {
      return null;
    }
  }, [isCanvas, text]);

  if (error) return <AttachmentFallback name={name} downloadUrl={downloadUrl} message={error} />;
  if (isHtml && text !== undefined && htmlLaunched) {
    return (
      <div>
        <div className="relative h-[min(70vh,640px)] min-h-64 overflow-hidden rounded border border-subtle">
          <iframe
            title={name}
            srcDoc={isolatedHtml(text)}
            sandbox="allow-scripts"
            referrerPolicy="no-referrer"
            className="h-full w-full"
          />
        </div>
        <div className="mt-2 flex items-center gap-3">
          {downloadUrl && (
            <a href={downloadUrl} download={name} className="text-sm text-link-primary">
              Download
            </a>
          )}
          <button type="button" onClick={() => setHtmlLaunched(false)} className="text-sm text-link-primary">
            Stop
          </button>
        </div>
      </div>
    );
  }
  if (isHtml && text !== undefined)
    return (
      <AttachmentFallback
        name={name}
        downloadUrl={downloadUrl}
        message="Interactive HTML preview"
        action={
          <button type="button" onClick={() => setHtmlLaunched(true)} className="text-link-primary">
            Open preview
          </button>
        }
      />
    );
  if (isHtml)
    return (
      <AttachmentFallback
        name={name}
        downloadUrl={downloadUrl}
        message={sourceUrl ? "Interactive HTML preview" : "Preview unavailable"}
      />
    );
  if (isText && text !== undefined)
    return <pre className="text-sm max-h-96 overflow-auto rounded bg-layer-2 p-3 whitespace-pre-wrap">{text}</pre>;
  if (isCanvas && canvas)
    return (
      <div className="relative h-96 overflow-auto rounded border border-subtle bg-layer-2">
        <div className="relative min-h-full min-w-full" style={{ width: 1600, height: 1000 }}>
          {canvas}
        </div>
      </div>
    );
  if (sourceUrl && mimeType.startsWith("image/"))
    return <img src={sourceUrl} alt={name} className="max-h-[70vh] max-w-full rounded object-contain" />;
  if (sourceUrl && mimeType === "application/pdf")
    return (
      <iframe
        title={name}
        src={sourceUrl}
        sandbox="allow-same-origin"
        className="h-[min(70vh,640px)] min-h-96 w-full rounded border border-subtle"
      />
    );
  if (sourceUrl && mimeType.startsWith("video/"))
    return <video src={sourceUrl} controls className="max-h-[70vh] max-w-full" />;
  if (sourceUrl && mimeType.startsWith("audio/")) return <audio src={sourceUrl} controls className="w-full" />;
  return <AttachmentFallback name={name} downloadUrl={downloadUrl} message="Preview unavailable" />;
}

function AttachmentFallback({
  name,
  downloadUrl,
  message,
  action,
}: {
  name: string;
  downloadUrl?: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded border border-subtle bg-layer-1 p-3">
      <div className="min-w-0">
        <div className="text-sm truncate font-medium">{name}</div>
        <div className="text-xs text-tertiary">{message}</div>
      </div>
      {action ??
        (downloadUrl ? (
          <a href={downloadUrl} download={name} className="text-link-primary">
            Download
          </a>
        ) : null)}
    </div>
  );
}
