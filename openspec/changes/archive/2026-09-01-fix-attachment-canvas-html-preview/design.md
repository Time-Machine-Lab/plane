## Context

The browser `File.type` value is not dependable for `.canvas` files. The existing server policy already maps the extension to `application/json` and classifies it as `json-canvas`, so the client must allow insertion based on a normalized filename extension before metadata detection runs.

HTML source is fetched through the authorized preview endpoint. The existing iframe uses `srcDoc`, `sandbox="allow-scripts"`, restrictive CSP, and a parent message bridge for explicitly confirmed external links. Defaulting the launch state to true exposes the same controlled surface without weakening the security boundary.

## Decisions

- Add a small shared predicate in the editor drop plugin that accepts image MIME types, attachment MIME types, or known attachment extensions (`txt`, `md`, `markdown`, `pdf`, `html`, `htm`, `canvas`, `mp4`, `mp3`, and existing generic fallback cases).
- Continue sending the original `File` to the upload service; `getFileMetaDataForUpload` remains authoritative for extension fallback and returns `application/json` for `.canvas`.
- Initialize HTML preview state as active in both PageAttachmentPreview and the editor attachment node view. The node view keeps source controls available while the iframe is active and keeps Download in the attachment metadata row.
- If source loading fails or exceeds the bounded preview limit, render the existing download fallback instead of an empty iframe.
- When constructing a direct-to-object-storage multipart payload, use the signed `Content-Type` for the file part. This keeps browser-reported generic MIME values (notably `.canvas`) aligned with the server's signed POST policy.

## Compatibility and Security

- Existing image, text, PDF, audio, video, and download-only behavior is unchanged.
- No signed URL is persisted or exposed to `srcDoc`; HTML is fetched as bounded source and rendered in an opaque-origin sandbox.
- No backend or schema changes are needed.
