## Context

Plane Pages use a Tiptap/ProseMirror document synchronized through Yjs. The realtime service persists the full Yjs binary and derives JSON and sanitized HTML for API consumers, versions, duplication fallback, and exports. Custom atom nodes such as images and work-item embeds already establish the extension pattern, but the Page duplicate flow rebuilds a new binary document from HTML and version restore currently restores HTML content. Canvas data stored only in an auxiliary Yjs shared type would therefore be lost on those paths.

The first release needs an embedded drawing experience without creating a standalone whiteboard domain or real-time collaboration protocol. It also needs to remain maintainable alongside upstream Plane and safe for self-hosted distribution.

## Goals / Non-Goals

**Goals:**

- Add an independently identifiable Canvas atom block to Page documents.
- Offer a stable preview in the document and a lazy-loaded full-screen Excalidraw editor.
- Preserve canvas content through Yjs persistence, offline recovery, Page duplication, and Page version restore without a database migration.
- Respect Page authorization and reduce accidental same-canvas overwrite through collaborative awareness.
- Produce useful PDF and Markdown representations and safe fallback rendering.
- Bound document growth and preserve older or temporarily disabled Canvas nodes.

**Non-Goals:**

- Fine-grained CRDT synchronization of Excalidraw elements or simultaneous editing of one Canvas block.
- Canvas-specific API endpoints, database models, or a top-level Canvas route.
- Imported images, attachments, video, templates, comments, AI generation, semantic nodes, or automatic layout.
- Pixel-identical rendering of the interactive editor in document previews and exported files.

## Decisions

### 1. Model Canvas as a versioned Page atom node

Add a block-level, selectable atom node rendered as `canvas-component`. Its stable attributes are:

- `data-canvas-id`: UUID that distinguishes multiple canvases in one Page.
- `data-title`: user-facing title.
- `data-scene-version`: integer format version.
- `data-scene`: UTF-8 Excalidraw scene JSON encoded as base64.
- `data-preview`: base64-encoded, size-bounded PNG preview payload without a URL prefix.
- `data-preview-width` and `data-preview-height`: preview aspect-ratio metadata.

The scene contains elements and the persisted subset of application state, but no Excalidraw file payloads. The node configuration is registered in both the interactive editor extension set and the property-free schema used by Yjs/HTML conversion. The API sanitizer explicitly allows only the Canvas tag and named attributes.

This keeps the scene in the same canonical Page lifecycle as surrounding content. The alternative of a sibling Yjs map was rejected for the MVP because current HTML-based duplicate and restore paths would discard it. A separate Canvas model was rejected because it would add authorization, lifecycle, versioning, duplication, and cleanup contracts before they are needed.

### 2. Use Excalidraw behind an editor-owned adapter

Add `@excalidraw/excalidraw` through the workspace catalog and isolate it behind Canvas types and an adapter owned by `packages/editor`. The package is loaded dynamically only when the full-screen editor opens. The adapter owns conversion between the versioned Plane scene payload and Excalidraw types, preview generation, and future format migrations.

Excalidraw is selected because its MIT license is compatible with Plane distribution and its embeddable React editor covers freehand drawing and connected structural diagrams. React Flow was not selected because it is optimized for semantic node graphs rather than a general whiteboard. tldraw was not selected because current production use requires an additional license.

### 3. Keep the document block passive and edit in a full-screen overlay

The Page node view displays the title, preview, status/fallback state, and an open action. It does not mount an interactive infinite canvas inside the scrolling document. Opening the block launches a full-screen overlay with a stable toolbar and a clear close action. This avoids gesture conflicts between Page text selection, block dragging, scrolling, canvas panning, and zooming.

New blocks open immediately after insertion. Editable Pages open in edit mode; read-only Pages open a view-only canvas. The document preview supports a small set of fixed display sizes without changing the scene coordinate system.

### 4. Save snapshots through normal ProseMirror/Yjs transactions

Canvas changes are debounced and converted into a single node-attribute update containing the scene and regenerated preview. Pending changes are flushed before a normal close. A save failure leaves the last acknowledged snapshot intact, keeps the overlay open when possible, and presents a retryable error. The UI exposes saving, saved, and failed states.

The implementation enforces decoded per-scene and per-preview limits below the existing 10 MB Page limit. It rejects unsupported scene versions, file payloads, and oversized updates before committing them to the document. Preview generation uses a bounded resolution and excludes editor chrome.

Updating one serialized node is intentionally last-writer-wins. Fine-grained element merging is deferred until a future design can introduce an independent Canvas Yjs document or adapter.

### 5. Use Yjs awareness as an advisory same-canvas edit lock

When an editable client opens a Canvas block, it publishes the active Canvas ID through the existing provider awareness state. Other connected clients render that Canvas in view-only mode and identify that it is being edited. Disconnecting or closing clears the awareness state. Because awareness is ephemeral and not an authorization boundary, the persisted node update remains last-writer-wins if two clients bypass the advisory lock.

Server-side Page permissions remain authoritative. Canvas does not add an endpoint or trust the awareness state to grant edit rights.

### 6. Treat preview as the portable representation

Interactive rendering uses the scene snapshot. Non-interactive consumers use the stored PNG preview:

- Page display and version display show the preview and title.
- Browser PDF conversion replaces `canvas-component` with a bounded image and caption.
- Server PDF rendering decodes and validates the preview before passing it to the PDF image renderer.
- Markdown export emits the title and a data-URI PNG image so the existing single-file export stays self-contained.
- The existing "no assets" export option omits the preview but retains a textual Canvas title placeholder.

Malformed or unavailable previews never prevent the rest of the Page from rendering or exporting; consumers fall back to the title and a neutral unavailable state.

### 7. Keep schema support present when the feature is disabled

Add `canvas` to the editor extension controls. Feature flagging or rollback disables insertion and interactive editing but retains the property-free Canvas schema and fallback node renderer. This prevents a disabled release from silently dropping stored Canvas elements during conversion or subsequent Page edits. Existing Pages need no migration.

## Risks / Trade-offs

- [Serialized snapshots cause larger Yjs updates and Page payloads] -> Debounce saves, bound scene and preview sizes, exclude embedded files, and generate low-resolution previews.
- [Two users can bypass the advisory lock and overwrite one another] -> Display awareness-based edit ownership, keep last-writer-wins behavior explicit, and defer same-canvas collaboration to a separate design.
- [Base64 adds storage overhead] -> Keep previews bounded and prefer lifecycle correctness over a new asset/entity system in the MVP.
- [Excalidraw API or scene types change] -> Pin the catalog version and isolate all library-specific types and migrations behind the Canvas adapter.
- [Invalid custom HTML could reach API or export boundaries] -> Allowlist exact tags/attributes, validate decoded payloads and dimensions, and never inject scene JSON as executable markup.
- [An older deployment cannot interpret Canvas nodes] -> Roll out schema and sanitizer support before enabling insertion, and roll back by disabling insertion while retaining schema/fallback support.
- [Full-screen editing may be uncomfortable on small screens] -> Provide view-only preview everywhere and ensure the overlay and core controls remain usable at supported mobile widths; advanced mobile drawing ergonomics remain outside the MVP.

## Migration Plan

1. Add the dependency, schema, serializer/sanitizer support, and fallback renderers while Canvas insertion remains disabled.
2. Add the Page node view, full-screen editor, persistence, awareness, and export handling.
3. Enable Canvas insertion after affected editor, API, Live, and export checks pass.
4. Roll back by disabling insertion and interactive editing while leaving schema parsing and fallback rendering deployed.

No database migration or content backfill is required.

## Open Questions

None for the MVP. Real-time same-canvas editing and externalized Canvas storage require a separate proposal if pursued.
