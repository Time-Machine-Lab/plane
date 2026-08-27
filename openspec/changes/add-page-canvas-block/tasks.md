## 1. Canvas Data Contract and Dependency

- [ ] 1.1 Add the pinned MIT-licensed `@excalidraw/excalidraw` dependency to the workspace catalog and `@plane/editor` package.
- [ ] 1.2 Define the versioned Canvas scene, preview, size, status, command, and extension types with decoded payload limits below the Page content limit.
- [ ] 1.3 Implement Canvas scene encode/decode, schema-version validation, unsupported-file rejection, preview validation, and safe fallback helpers.

## 2. Editor Schema and Commands

- [ ] 2.1 Add the `canvas-component` atom schema with the specified allowlisted attributes and register it in interactive and property-free editor extension sets.
- [ ] 2.2 Add Canvas insertion, update, preview-size, open, duplicate-block, and delete-block commands while preserving the schema when Canvas editing is disabled.
- [ ] 2.3 Add the Canvas slash-command and block-menu entry with edit-permission and extension-flag handling.
- [ ] 2.4 Add focused editor round-trip coverage for Canvas HTML, JSON, Yjs binary, multiple independent blocks, unsupported versions, and disabled-extension fallback behavior.

## 3. Page Canvas Experience

- [ ] 3.1 Build the passive Canvas node view with title, bounded preview, supported display sizes, open action, loading state, and unavailable fallback.
- [ ] 3.2 Build a dynamically loaded full-screen Excalidraw adapter with the supported drawing, selection, styling, pan, zoom, undo, and redo controls.
- [ ] 3.3 Implement Canvas title editing, read-only viewing, close behavior, return-to-document focus, and immediate opening after insertion.
- [ ] 3.4 Implement debounced scene saves, bounded PNG preview generation, pending-save flush on close, and visible saving, saved, failed, oversized, and unsupported-file states.
- [ ] 3.5 Publish and consume active Canvas IDs through existing Yjs awareness so a Canvas edited by another connected user opens in advisory view-only mode.
- [ ] 3.6 Complete keyboard, focus, accessible naming, theme, standard Page width, full-width Page, and supported narrow-viewport behavior.

## 4. Persistence, Security, and Lifecycle

- [ ] 4.1 Extend API rich-text sanitization to preserve valid Canvas elements and exact attributes while removing unsupported or executable content.
- [ ] 4.2 Confirm Page save, offline recovery, duplication, version display, and HTML-based version restore preserve Canvas IDs, titles, scenes, previews, and placement; fix only the affected lifecycle paths where round trips fail.
- [ ] 4.3 Add focused API sanitizer and size-validation tests for valid, malformed, oversized, future-version, and unsafe Canvas payloads.

## 5. Export and Localization

- [ ] 5.1 Extend browser PDF and Markdown conversion to render Canvas title and preview, honor no-assets mode, and fall back without aborting the remaining Page export.
- [ ] 5.2 Extend Live server-side PDF rendering to validate and render Canvas previews with title-based fallback, including focused renderer coverage.
- [ ] 5.3 Add all Canvas commands, statuses, errors, fallback, locking, and accessibility strings through the repository translation workflow and verify locale key synchronization.

## 6. Development Checks

- [ ] 6.1 Run focused type and lint checks for `@plane/editor` and directly affected web, API, Live, and i18n modules, resolving only Canvas-related failures.
- [ ] 6.2 Run the focused editor serialization, API sanitizer, export, and Live PDF tests that cover the Canvas risk boundaries.
- [ ] 6.3 Exercise the Page Canvas flow locally in editable and read-only Pages, including multiple blocks, reload, duplicate, version restore, export, save failure, narrow viewport, and advisory locking.

## 7. Independent Verification

- [ ] 7.1 Have the primary Agent create a new Tester sub-agent that did not participate in implementation to independently verify the requirement goal, directly affected Page Canvas behavior, and necessary Page editor/export regression without modifying product code.
- [ ] 7.2 If verification fails, fix the focused implementation scope and have the same Tester recheck only the failure and necessary adjacent behavior before completion.
