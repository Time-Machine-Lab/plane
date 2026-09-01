## 1. Storage Profiles And Routing

- [ ] 1.1 Add the instance storage-profile model, encrypted write-only credentials, verification and lifecycle fields, audit metadata, and a nullable storage-profile reference on `FileAsset`, with migrations that leave existing assets on the legacy environment-backed store.
- [ ] 1.2 Refactor the object-storage adapter to resolve each operation through either an asset's immutable profile or the legacy environment configuration, including reads, copies, restores, and deletes.
- [ ] 1.3 Implement verified-profile activation, location versioning, credential rotation, rollback to legacy writes, active-profile health reporting, and refusal to remove profiles still referenced by assets.
- [ ] 1.4 Add bounded cleanup for expired upload intents and connection-probe objects without affecting finalized assets.

## 2. Direct Upload And Private Delivery

- [ ] 2.1 Define the authoritative backend attachment policy, extension and MIME resolution, dangerous-type denylist, preview classifications, typed validation errors, and configurable 100 MB default limit.
- [ ] 2.2 Implement shared Page and work-item upload-intent endpoints that validate entity permissions and file policy, bind pending assets to the selected profile, and issue short-lived size-constrained presigned uploads.
- [ ] 2.3 Implement authoritative upload finalization that checks the bound object and expected size before making an asset available, with stable errors for missing or mismatched objects.
- [ ] 2.4 Implement authorized preview and download intents that resolve the recorded profile, use short-lived signed access, enforce inline and attachment dispositions, and never expose storage credentials or object keys.
- [ ] 2.5 Apply Page- or work-item-level authorization and entity binding to upload, finalize, preview, download, duplicate, restore, and delete operations, including private Page and cross-project denial paths.

## 3. God Mode Object Storage

- [ ] 3.1 Add administrator APIs for creating and updating draft profiles, deriving Aliyun OSS protocol settings, accepting an optional advanced Endpoint override, returning masked secret state, setting the per-file limit, reporting verification health, activating a verified version, and returning sanitized failures.
- [ ] 3.2 Add a God Mode object-storage route whose normal Aliyun OSS form contains only AccessKey ID, write-only AccessKey Secret, Bucket, Region, and upload limit, with Endpoint under advanced settings plus draft, active, and rollback status controls.
- [ ] 3.3 Implement the browser-based connection probe so God Mode uploads a bounded test object through the presigned path and the API verifies, reads, deletes, and records the result before activation.
- [ ] 3.4 On browser probe failure, show the Plane origin and minimal Aliyun OSS CORS guidance without exposing CORS, signing, addressing, expiry, prefix, STS, CNAME, internal-endpoint, or encryption fields in the normal form.
- [ ] 3.5 Add localized administrator labels, validation feedback, masked-secret behavior, loading states, and accessible confirmation for activation and rollback.

## 4. Shared Attachment Client And Work Items

- [ ] 4.1 Update shared types, constants, services, and file helpers with the common attachment policy, extension fallbacks for empty or generic MIME values, preview metadata, typed API errors, and storage-aware asset contracts.
- [ ] 4.2 Implement a reusable direct-upload client with progress, cancellation, retry, upload finalization, and signed preview or download resolution without persisting signed URLs.
- [ ] 4.3 Migrate work-item detail attachments to the shared client and policy while preserving existing list, count, activity, download, and soft-delete behavior for both legacy and profiled assets.
- [ ] 4.4 Show distinct work-item errors for empty, oversized, dangerous, unsupported, unavailable-storage, transfer, and finalization failures, and add the required localized strings.

## 5. Page Attachment Editing And Lifecycle

- [ ] 5.1 Add the editor attachment node schema, commands, serialization, stable dimensions, disabled-feature fallback, and metadata fields for block ID, asset ID, sanitized name, canonical type, size, and presentation kind.
- [ ] 5.2 Implement Page attachment insertion through the block UI and file picker, and complete drag and paste handling for one or multiple files while preserving order and enforcing edit permissions.
- [ ] 5.3 Connect uploading, progress, cancellation, retry, ready, failed, unavailable, and removal states to the Page file handler without producing duplicate finalized assets.
- [ ] 5.4 Extend Page asset collection and the navigation assets pane to list image and non-image assets with location, state, metadata, and authorized download actions.
- [ ] 5.5 Preserve attachment nodes and asset lifecycle through realtime persistence, reload, version display and restore, duplication, undo and soft-restore, export fallback, and rollout disablement across editor, web, API, and live boundaries.

## 6. Page Preview Surfaces

- [ ] 6.1 Build a shared accessible Page attachment card and bounded preview shell with stable responsive dimensions, keyboard-operable controls, download fallback, and neutral unavailable states.
- [ ] 6.2 Add bounded UTF-8 TXT and safe Markdown preview, enforcing the independent text read limit and preventing raw HTML or script execution.
- [ ] 6.3 Add native browser PDF, MP4 video, and MP3 audio previews with controls where applicable, signed access, codec or viewer failure handling, and no transcoding or generated media.
- [ ] 6.4 Implement explicitly launched interactive HTML preview using bounded authorized source, an opaque-origin `sandbox="allow-scripts"` iframe, a non-overridable restrictive CSP, default network denial, blocked privileged capabilities, Plane-controlled external-link confirmation, stop, source, and download fallbacks, and no signed URL exposure to attachment code.
- [ ] 6.5 Review JSON Canvas renderer options for license, maintenance, bundle size, React compatibility, untrusted-input behavior, and implicit network access, then record and implement the smallest acceptable approach.
- [ ] 6.6 Implement bounded JSON Canvas 1.0 parsing and a read-only pan-and-zoom renderer for text, group, link, and edge content, with safe unresolved file placeholders and download-only fallback for malformed, unsupported, or excessive data.
- [ ] 6.7 Render every other allowed file as a metadata and authorized-download card, and force non-HTML script-capable content to download-only behavior.

## 7. Deployment And Independent Verification

- [ ] 7.1 Deploy the affected runtime services with `scripts/test/deploy-test.ps1` after implementation is complete.
- [ ] 7.2 Have the primary Agent create a fresh Tester sub-agent that did not participate in implementation to verify the compact Aliyun OSS form, derived Endpoint and protocol behavior, browser CORS probe, direct upload and finalization, Page previews and downloads including a self-contained interactive HTML artifact, work-item attachments, private permissions, and legacy-asset reads in the deployed test environment without modifying product code.
- [ ] 7.3 If verification fails, fix only the affected implementation scope, redeploy the affected services, and have the same Tester recheck the failure and necessary adjacent behavior before declaring the change complete.
