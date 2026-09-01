Work item: **TMLPLANE-8**

## Why

Plane Pages currently upload only editor images even though the shared asset pipeline and work-item detail already expose broader attachment concepts. Users need Pages and work items to accept common documents and media, keep uploaded bytes out of the Plane application server, and provide clear preview or download behavior through an administrator-configured object store.

## What Changes

- Add a streamlined God Mode object-storage configuration experience with an Aliyun OSS preset, encrypted AccessKey credentials, Bucket, Region, an optional advanced Endpoint override, connection verification, an administrator-configurable per-file limit defaulting to 100 MB, and an explicitly activated storage profile for new uploads.
- Route new user-uploaded assets directly from the browser to the active private S3-compatible object store by presigned upload, while Plane stores metadata and continues to authorize preview and download access.
- Preserve access to assets in the existing storage backend when a new profile is activated, record the storage profile used by each new asset, and leave byte migration to a later explicit migration operation.
- Add a Page attachment block with upload progress, retry, cancellation, removal, accessible fallback states, and Page-lifecycle preservation.
- Preview images, bounded UTF-8 text and Markdown, PDFs, MP4 video, MP3 audio, valid JSON Canvas 1.0 `.canvas` files, and explicitly launched interactive HTML inside Pages; use a normal attachment card and authorized download for all other allowed files or unsupported previews.
- Render JSON Canvas previews as read-only content. Text, links, groups, and edges are displayed; unresolved file references are represented safely without reading arbitrary local paths or automatically embedding third-party pages.
- Run allowed HTML interactions only inside an opaque-origin sandbox that can execute in-document scripts but cannot access Plane sessions, storage, or parent content; block forms, popups, downloads, top-level navigation, and external network access by default, and retain source and download fallbacks.
- Make work-item detail attachments use the same file-type resolution, safe allowlist, object-storage routing, size limit, and actionable error contract so currently rejected text, JSON Canvas, document, audio, and video uploads behave predictably.
- Enforce Page- and work-item-level authorization before issuing preview or download access, keep buckets private, and force executable or script-capable content other than the isolated HTML preview contract to download rather than render inline.

### Non-goals

- Migrating existing object bytes to the newly activated storage profile in this change.
- Video or audio transcoding, poster generation, waveform generation, adaptive streaming, or codec conversion.
- Editing imported JSON Canvas files, converting them into Plane Canvas blocks, or resolving their referenced local files from a user's device or Obsidian vault.
- Inline preview or server-side conversion for Word, Excel, PowerPoint, archives, or arbitrary proprietary formats.
- Full-fidelity website hosting for uploaded HTML, unrestricted external dependencies or navigation, and any HTML access to the Plane application origin, authenticated session, or privileged browser capabilities.
- Exposing provider-specific signing, addressing, object-prefix, STS, CNAME, internal-endpoint, or per-object encryption tuning in the first-release administrator form; the Aliyun OSS preset owns safe signing and addressing defaults.
- Allowing administrators to remove security restrictions by configuring arbitrary executable MIME types.
- Moving compiled application static assets such as JavaScript, CSS, or bundled product images into the user-upload object store.

## Capabilities

### New Capabilities

- `instance-object-storage`: Configure, verify, activate, version, and safely route user-uploaded assets across legacy and new private object-storage profiles.
- `page-content-attachments`: Upload, embed, preview, download, preserve, and authorize supported file attachments in Plane Pages.
- `work-item-attachments`: Reliably upload and download the supported attachment set from work-item detail with shared limits, storage routing, validation, and actionable failure feedback.

### Modified Capabilities

None.

## Impact

- `apps/admin`: new God Mode object-storage route with a compact Aliyun OSS form, optional advanced Endpoint override, connection and CORS diagnosis, activation status, masked-secret behavior, and upload-limit controls.
- `apps/api`: encrypted instance storage configuration, storage-profile routing, asset ownership metadata, presigned upload/preview/download endpoints, Page/work-item authorization, validation, and a forward-compatible migration path for existing `FileAsset` rows.
- `apps/web`: Page attachment insertion and rendering, shared preview/download surfaces, work-item attachment feedback, upload progress, and storage-aware services and stores.
- `packages/editor`: additive attachment schema, commands, node view, file drop/paste handling, asset metadata, serialization, duplication, restore, and disabled-extension fallback.
- `apps/live`: schema awareness and safe attachment representation for Page persistence, historical content, and supported exports where the editor node crosses the realtime boundary.
- `packages/types`, `packages/services`, `packages/constants`, `packages/utils`, and `packages/i18n`: shared storage, attachment, validation, preview, API, and localized error contracts.
- `deployments/*` and environment compatibility: existing environment-backed S3/MinIO configuration remains the legacy profile and rollback path; no existing object bytes are copied automatically.
- Dependencies and licensing: a JSON Canvas 1.0 read-only renderer may be added only after license, bundle, maintenance, and security review; converting the bounded standard subset through an existing Plane-owned rendering adapter remains an acceptable implementation choice.
- Security and compatibility: secrets never return from the API, private asset URLs are short-lived, content and filenames are untrusted, interactive HTML runs only after explicit user action in a restricted opaque-origin sandbox, old assets remain readable after activation, and stored attachment nodes survive feature disablement or rollback.
- Applicable standards: `docs/spec/general-development.md`, `docs/spec/frontend-development.md`, `docs/spec/backend-development.md`, `docs/spec/realtime-development.md`, `docs/spec/shared-packages-development.md`, `docs/spec/module-structure.md`, and `docs/spec/testing-quality.md`.
