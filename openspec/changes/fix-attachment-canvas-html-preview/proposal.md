## Why

Production users cannot reliably upload `.canvas` files because browser drag/paste events may expose an empty or generic MIME type, causing the client allow-list to discard the file before the upload request. HTML attachments also require an extra click before users can see their content, even though the existing isolated preview is already available.

## What Changes

- Recognize supported attachment files by extension when browser MIME metadata is empty or generic, including `.canvas`.
- Preserve the server-resolved canonical MIME type for `.canvas` uploads.
- Render HTML attachments inline by default in the existing opaque-origin sandboxed preview surface.
- Keep Download, View source, and a usable fallback when bounded HTML source cannot be loaded.
- Keep preview security restrictions unchanged: no Plane-origin access, network access, forms, popups, or top-level navigation.

## Capabilities

### New Capabilities

- `attachment-upload-preview-fixes`: Reliable extension fallback for attachment insertion and default safe HTML preview behavior.

### Modified Capabilities

## Impact

- `packages/editor`: drag/paste attachment filtering and attachment node view.
- `apps/web`: Page attachment preview surface.
- No database, storage-profile, API contract, or migration changes.
- Runtime change requires deployment of the affected web services and independent test-environment verification.
