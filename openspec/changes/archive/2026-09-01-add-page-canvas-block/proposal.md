## Why

Plane Pages can describe work in rich text but cannot express spatial ideas such as architecture diagrams, flows, sketches, and relationship maps without leaving the page or uploading a static image. An embedded canvas block lets users create and revisit those visuals in the context of the surrounding document while preserving the existing Page editing model.

## What Changes

- Add a Canvas block that can be inserted into a Page from the slash-command and block insertion interfaces.
- Render each Canvas block as a titled preview in the document and open a focused full-screen editor for drawing and editing.
- Provide essential drawing controls through an embedded Excalidraw editor, including shapes, connectors, freehand drawing, text, selection, styling, zoom, undo, and redo.
- Persist a versioned canvas scene snapshot and lightweight preview with the Page document so the block survives reload, offline recovery, page duplication, and page-version restore.
- Respect Page edit and read-only permissions, and prevent accidental overwrite when another collaborator is already editing the same Canvas block without introducing real-time canvas co-editing.
- Represent Canvas blocks predictably in Page PDF and Markdown exports using their title and preview.
- Add validation, content-size handling, and graceful fallback behavior for invalid, oversized, or unsupported canvas data.
- Add the MIT-licensed Excalidraw package as an editor dependency and load it only when a Canvas block is opened.
- Keep existing Pages and documents compatible; no existing content requires migration.

### Non-goals

- Real-time multi-user editing, cursors, or fine-grained conflict merging inside one Canvas block.
- Element-level comments, AI-generated diagrams, templates, or links between canvas elements and Plane work items.
- Images, videos, or arbitrary file attachments inside the first Canvas release.
- A standalone top-level whiteboard product outside Pages.
- A specialized semantic workflow or architecture modeling engine with automatic layout.

## Capabilities

### New Capabilities

- `page-canvas-block`: Insert, edit, view, persist, copy, restore, and export an embedded Page canvas while preserving Page permissions and document compatibility.

### Modified Capabilities

None.

## Impact

- `packages/editor`: Canvas schema, React node view, commands, slash-menu entry, serialization, read-only rendering, and editor public types.
- `apps/web`: Full-screen canvas experience, Page-specific handlers, collaboration awareness, preview/export conversion, error states, and localized user-facing text.
- `apps/api`: Rich-text sanitizer support and validation for the Canvas custom element and attributes; no database schema or public API change is planned.
- `apps/live`: Canvas schema awareness during Yjs conversion and Canvas preview handling in server-side PDF export.
- `packages/i18n`: Canvas labels, commands, statuses, errors, and accessibility text across supported locales.
- External dependency: `@excalidraw/excalidraw` under the MIT license, added through the workspace catalog.
- Applicable standards: `docs/spec/general-development.md`, `docs/spec/frontend-development.md`, `docs/spec/shared-packages-development.md`, `docs/spec/backend-development.md`, `docs/spec/realtime-development.md`, and `docs/spec/testing-quality.md`.
- Compatibility and rollout: existing Page documents remain valid because Canvas is additive. Disabling or rolling back the UI must retain a safe non-editable fallback for stored Canvas nodes rather than dropping their content.
