## Context

Plane already models uploaded bytes as `FileAsset` records and uses presigned S3 operations so the browser can upload directly to S3 or MinIO. Pages already provide a `PAGE_DESCRIPTION` file handler for images, and work-item detail already exposes a dedicated attachment list. The current implementation is incomplete for this change: the editor attachment insertion branch is empty, project description assets accept only image MIME types, file-type detection returns an empty type for common text formats, the global limit defaults to 5 MB, and the God Mode image page configures Unsplash rather than storage.

The requested rollout introduces a new active object store for future uploads without migrating existing bytes immediately. A mutable global endpoint is therefore insufficient: every asset must remain resolvable through the storage location that accepted it. The change also crosses instance administration, Django storage and permissions, shared asset contracts, the Page editor and realtime schema, work-item detail, deployment compatibility, and private content delivery.

JSON Canvas 1.0 `.canvas` files are UTF-8 JSON documents containing positioned text, file, link, group, and edge records. They are not Microsoft Office formats and are distinct from Plane's editable Excalidraw Canvas block. A single JSON Canvas file can reference vault-relative files that are not contained in the upload, so complete external-file resolution is impossible without a later bundle/import workflow.

HTML attachments can be self-contained interactive artifacts whose buttons, dialogs, filters, and other controls require JavaScript. Treating them as ordinary inline documents would execute untrusted code in a sensitive product surface, while stripping every script would defeat the requested interaction. The preview therefore needs a narrowly scoped execution exception rather than general website hosting.

## Goals / Non-Goals

**Goals:**

- Give instance administrators a safe God Mode workflow to configure, verify, activate, and rotate an S3-compatible object-storage profile and set a default 100 MB per-file limit.
- Send new user-uploaded bytes directly from the browser to the active private object store while Plane remains authoritative for metadata, permissions, lifecycle, and signed access.
- Keep existing assets readable from the environment-backed legacy store and make later byte migration possible without blocking this release.
- Add durable Page attachment nodes with inline preview for images, bounded text/Markdown, PDF, MP4, MP3, valid JSON Canvas 1.0 files, and explicitly launched sandboxed HTML interactions, plus download cards for the remaining safe attachment set.
- Make work-item attachments accept the same safe file policy and produce specific, actionable failures.
- Preserve Page attachments through collaboration, reload, version display/restore, duplication, export fallback, and feature rollback.

**Non-Goals:**

- Copying existing bytes into the new profile or deleting the legacy store.
- Importing or editing JSON Canvas as a Plane Canvas block, resolving local vault paths, or packaging related files.
- Office/archive preview, media transcoding, thumbnail/poster generation, adaptive streaming, or format conversion.
- Full-fidelity hosting of uploaded websites, unrestricted HTML network access or navigation, and granting uploaded HTML same-origin access to Plane or its authenticated session.
- Storing application build artifacts in the user-upload store.
- Making long-lived or public object URLs the authorization contract.

## Decisions

### 1. Persist immutable storage locations and bind every new asset to one

Introduce an instance-owned storage-profile model with a stable UUID, provider kind, effective endpoint, region, bucket, provider-owned addressing/signing behavior, encrypted credentials, lifecycle state, connection-test metadata, and audit fields. Add a nullable storage-profile reference to `FileAsset`.

- A null profile means the existing environment-backed legacy S3/MinIO configuration. Existing rows remain null; no byte backfill occurs.
- Exactly one verified profile can be the active write target. New uploads capture that profile when their pending asset row is created.
- Provider, effective endpoint, region, or bucket changes create a new profile rather than mutating an active location. Credentials for the same location can be rotated in place with secret-safe audit metadata.
- A retired profile remains available for read, copy, and delete while assets reference it. The API refuses destructive removal of referenced profiles.

This is preferred over writing new values into `InstanceConfiguration` alone because mutable global values would strand old keys after activation and would not support safe rollback or deferred migration.

The first-release God Mode form intentionally does not mirror every stored adapter field. For the Aliyun OSS preset, administrators provide AccessKey ID, AccessKey Secret, Bucket, Region, and the instance upload limit. Plane derives the public Endpoint from Region, fixes virtual-hosted addressing and the supported V4 signing behavior, applies short internal signing lifetimes and an internal object prefix, and exposes Endpoint only as an advanced override. STS roles, custom CNAME delivery, separate internal endpoints, and per-object encryption controls are deferred rather than presented as required setup.

### 2. Keep the legacy environment configuration as a first-class compatibility profile

The existing `AWS_*`, `USE_MINIO`, and related settings remain the implicit legacy profile and deployment fallback. Storage resolution accepts either an explicit database profile or the legacy profile, then creates the appropriate client through one storage adapter contract.

On rollback, administrators can disable the database-backed write target so new uploads return to the legacy profile. Explicitly profiled assets remain readable; rollback does not drop the profile model, attachment schema, or stored document nodes.

### 3. Verify configuration from the real browser upload path before activation

God Mode creates or updates a draft profile without making it active. A connection probe uses a unique, bounded test object:

1. The API validates and stores the masked draft configuration.
2. The API returns a presigned upload for a small generated probe object.
3. The God Mode browser uploads the probe, exercising actual origin and bucket CORS behavior.
4. The API verifies object metadata, reads the bounded probe, deletes it, and records the result.
5. Activation is available only after a successful current-version probe.

Failed probes leave the existing active profile unchanged and expose a sanitized diagnosis without returning credentials, canonical authorization headers, or full signed URLs in logs. CORS is not modeled as a set of Plane storage fields: when the browser stage fails, God Mode shows the Plane origin and the minimal OSS methods and headers that the administrator must allow. The alternative of a server-only bucket `HEAD` was rejected because it would not verify the browser-to-bucket upload path required by the product.

### 4. Use a two-phase direct-upload contract and verify completion

Page and work-item uploads share an upload-intent contract:

1. The browser submits entity context, sanitized filename, declared size, detected/browser MIME candidates, and extension.
2. The API validates entity authorization, storage availability, safe type policy, and the active upload limit before creating a pending `FileAsset` bound to the selected storage profile.
3. The API returns a short-lived presigned POST whose content-length condition matches the accepted size.
4. The browser uploads directly to object storage and reports progress without sending file bytes through Plane.
5. The browser calls finalize; the API performs `HEAD` against the asset's bound profile, verifies the object exists and the stored size matches the intent, records authoritative metadata, and marks the asset uploaded.

Abandoned pending rows and probe objects are removed by bounded cleanup. A failed finalize never exposes the asset as downloadable. This strengthens the existing patch-only completion flow, which trusts client completion without confirming the stored object.

### 5. Centralize a conservative attachment policy

Create one shared attachment policy represented consistently in TypeScript and Python. Client signature detection improves feedback but is never the authorization boundary. The API resolves common empty or generic browser types using an allowlisted extension mapping, including:

- `.txt` -> `text/plain`
- `.md`/`.markdown` -> `text/markdown`
- `.canvas` -> JSON Canvas candidate stored as `application/json` with explicit preview metadata
- `.html`/`.htm` -> `text/html` with an explicit isolated-interactive preview classification
- `.pdf` -> `application/pdf`
- `.mp4` -> `video/mp4`
- `.mp3` -> `audio/mpeg`

Known document, spreadsheet, presentation, image, audio, video, archive, JSON Canvas, and HTML types can be stored. Dangerous executable extensions remain denied. Unknown files are accepted only when an allowlisted extension maps them to a download-only type; arbitrary `application/octet-stream` does not bypass the policy. HTML is the only script-capable preview exception and uses the isolated contract below. SVG, JavaScript, XML, and other active or script-capable content is never executed inline and is always delivered as an attachment.

The instance upload limit defaults to 100 MB and applies before a presigned upload is issued. Preview readers impose smaller independent decoded limits; accepting a file for download does not imply that Plane will parse or render it.

### 6. Store Page attachment identity, never signed URLs, in the document

Add an additive `attachment-component` editor node containing a stable block ID, asset ID, name, canonical type, size, and presentation kind. Signed URLs and provider object keys are not serialized because they expire and are storage implementation details.

The node supports slash-command/file-picker insertion plus drag and paste insertion where the browser exposes a file. Images continue to use the established image node. Text, PDF, MP4, MP3, JSON Canvas, interactive HTML, and download-only files use the attachment node. Uploading, failed, canceled, unavailable, unsupported-preview, awaiting-launch, running, and ready states have stable dimensions and do not resize surrounding content unexpectedly.

The existing file handler remains responsible for upload, duplicate, soft-delete, restore, access URL resolution, and progress. The Page assets pane consumes the same editor asset metadata and lists both images and non-image attachments.

### 7. Keep previews bounded and authorization-aware, and isolate interactive HTML

The API exposes separate authorized preview and download intents. Both resolve the asset's profile only after validating its bound Page or work item. Preview uses an allowlisted inline disposition; download always uses attachment disposition and the original sanitized filename.

- Text reads at most 1 MB, decodes UTF-8, and displays plain text. Markdown uses the existing safe Markdown renderer without raw HTML execution.
- PDF uses the browser's native viewer from a short-lived signed response and always offers download fallback.
- MP4 and MP3 use native `<video controls>` and `<audio controls>` elements. Unsupported codecs, range failures, or browser playback errors fall back to download; Plane performs no conversion.
- JSON Canvas preview parses at most 10 MB, validates version 1.0 and bounded node/edge counts and coordinates, and renders a read-only pan/zoom surface. Text, groups, links, and edges render locally. Link nodes do not auto-fetch or embed remote pages. File nodes display a safe unresolved-reference placeholder unless a future explicit import maps them to authorized Plane assets.
- HTML preview reads at most 1 MB and never starts automatically. After an explicit user action, the parent fetches authorized bytes and supplies them to an opaque-origin iframe rather than navigating the iframe to an OSS signed URL. The iframe uses `sandbox="allow-scripts"` without same-origin, form, popup, download, or top-navigation grants. A fixed restrictive CSP allows bounded in-document inline script and style behavior but denies connections and external resources by default; the attachment cannot weaken this policy, access Plane cookies or storage, inspect the parent document, or receive provider credentials or signed URLs.
- In-document controls such as buttons, filters, and dialogs can work inside the HTML sandbox. External dependencies may degrade under the default network deny policy. External link requests are blocked inside the artifact and may be handed to a Plane-owned confirmation flow that opens them outside the preview only after an explicit user decision. The preview always offers bounded source viewing, stop or close, and original-file download fallbacks.
- All other allowed types render a metadata card with download.

The renderer may use a reviewed MIT JSON Canvas library or a Plane-owned adapter over existing canvas primitives. Before adding a dependency, implementation must confirm license, bundle impact, maintenance, React compatibility, untrusted-input behavior, and that no network fetch occurs implicitly. The behavior contract, rather than a specific library, is authoritative.

Implementation review selected a Plane-owned bounded renderer instead of a third-party JSON Canvas package. This adds no license, maintenance, or bundle dependency, uses ordinary React/HTML/SVG primitives, performs no implicit network requests, and parses only the bounded JSON Canvas fields required by this change.

### 8. Reuse Page and work-item permissions at every asset boundary

Upload, finalize, preview, download, duplicate, restore, and delete endpoints resolve the bound entity and apply its authoritative permission class. A project role alone is insufficient for a private Page asset. Work-item assets remain scoped to their workspace, project, work item, and permitted actor.

Presigned URLs are short-lived bearer capabilities and therefore can be used until expiry once issued. They are not persisted in Page content, API responses beyond the requesting operation, analytics, or logs. Buckets remain private; public-read ACLs are not part of the contract.

### 9. Preserve attachment nodes and bytes through Page lifecycle operations

The attachment schema is registered in interactive and property-free editor schemas so Yjs conversion, historical versions, and disabled-feature fallback do not discard nodes. Page duplication creates a new `FileAsset` and object key within the source asset's storage profile, preserving independent deletion semantics without requiring a cross-profile copy. Version restoration reuses the stored asset identity and restore behavior already used for editor images.

Exports represent download-only attachments by name, type, and size. Supported previews can provide a bounded static representation only where the existing exporter can do so safely; export failure or expired access never aborts the remaining Page export. Removing a node follows existing soft-delete/restore protection so undo and version restoration do not immediately destroy bytes.

### 10. Make errors stable and useful across Pages and work items

Define typed error codes for at least invalid type, dangerous extension, empty file, size limit, storage unavailable, upload expired, upload failed, verification mismatch, preview unsupported, preview too large, preview malformed, and permission denied. UI text is localized and includes the configured limit where relevant, while internal provider detail is logged with correlation and asset/profile IDs but without secrets or signed URLs.

The work-item attachment UI retains one-file-at-a-time behavior but no longer collapses every backend rejection into a generic message. Existing successfully uploaded attachments continue to list, download, and delete normally.

## Risks / Trade-offs

- [Changing storage credentials can make both old and new assets unavailable] -> Validate rotation against the same immutable location before replacing encrypted credentials and retain recoverable prior secret material only according to the existing secret-management policy.
- [Deferred migration leaves multiple storage systems operational] -> Bind every asset to a profile, prevent deletion of referenced profiles, surface profile health in God Mode, and design a later idempotent migration around the stable profile reference.
- [A copied signed URL bypasses Plane until it expires] -> Keep expirations short, issue URLs only after entity authorization, keep buckets private, and never serialize signed URLs into documents.
- [Direct upload metadata can lie about content] -> Use extension/MIME policy before upload, verify stored size and metadata on finalize, force risky types to attachment disposition, and execute only explicitly classified HTML through the isolated preview contract. Deep malware scanning remains a future integration.
- [Interactive HTML can attempt session theft, phishing, navigation, network exfiltration, or resource exhaustion] -> Require explicit launch, keep it in an opaque-origin sandbox with a non-overridable restrictive CSP and no privileged sandbox grants, deny external networking by default, bound source size, label the content as an attachment preview, provide a stop action, and ignore unrecognized frame messages.
- [Native PDF/media behavior differs across browsers] -> Provide a stable attachment card and download fallback for every preview.
- [Large text, HTML, or JSON Canvas input can exhaust browser resources] -> Enforce independent decoded byte, node, edge, coordinate, and rendering bounds and refuse or stop preview without refusing authorized download.
- [JSON Canvas file references appear incomplete] -> Render explicit unresolved placeholders and do not guess local or remote paths; bundled imports are deferred.
- [Page duplication across a retired profile depends on retained credentials] -> Retired profiles remain operational while referenced, and duplication copies within the source profile rather than silently switching location.
- [A new editor node could be dropped by older services] -> Deploy schema-aware API/Live/editor readers before enabling insertion and retain fallback schema support during rollback.
- [God Mode connection testing performs an external write] -> Use a namespaced minimal probe, require an explicit administrator action, delete it immediately, and keep tests against real third-party storage out of automated verification unless separately authorized.

## Migration Plan

1. Add storage profiles, a nullable `FileAsset` profile reference, encrypted configuration support, and unified storage resolution while all existing rows continue to resolve through legacy environment settings.
2. Deploy read/finalize authorization and direct-upload hardening before exposing profile activation or Page attachment insertion.
3. Add God Mode draft, browser probe, activation, health, credential rotation, and 100 MB limit controls. Keep legacy as the active write target until a new profile passes its probe.
4. Activate the chosen object-storage profile for new uploads only. Observe upload intent, finalize, provider, and cleanup failures without logging secrets.
5. Deploy the shared attachment policy and repair work-item attachment MIME resolution and errors.
6. Deploy attachment schema readers and fallback renderers across editor, API, and Live, then enable Page insertion and passive previews before enabling explicitly launched interactive HTML previews.
7. On rollback, disable Page attachment insertion and database-profile writes, return new uploads to legacy storage, and retain profile routing plus attachment schema readers so already-created assets and documents remain accessible.
8. Implement existing-byte migration only in a later change using idempotent copy, metadata verification, per-asset profile switch, retry, and rollback. Do not delete legacy bytes as part of this release.

## Open Questions

No blocking product decisions remain. The implementation must validate the user's actual Aliyun OSS endpoint, preset signing behavior, and CORS through the God Mode browser probe before activation; no provider credential or endpoint is recorded in OpenSpec.
