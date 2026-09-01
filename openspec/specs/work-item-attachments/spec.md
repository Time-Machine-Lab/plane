# work-item-attachments Specification

## Purpose

TBD - created by archiving change add-object-storage-backed-attachments. Update Purpose after archive.

## Requirements

### Requirement: Upload the shared safe attachment set from work-item detail

The system SHALL allow an authorized work-item user to upload one file at a time using the shared attachment policy and active instance upload limit.

#### Scenario: Upload common text and document formats

- **WHEN** an authorized user selects an allowed TXT, Markdown, HTML, PDF, JSON Canvas, Word, Excel, PowerPoint, or other allowlisted document within the configured limit
- **THEN** the work-item detail creates, directly uploads, finalizes, and lists the attachment

#### Scenario: Upload supported media

- **WHEN** an authorized user selects an allowlisted image, MP4, MP3, or other allowlisted audio/video file within the configured limit
- **THEN** the work-item detail creates, directly uploads, finalizes, and lists the attachment without requiring server-side transcoding

#### Scenario: Resolve a text MIME fallback

- **WHEN** browser or signature detection returns no MIME type for an allowlisted `.txt`, Markdown, `.html`, `.htm`, or `.canvas` file
- **THEN** the system uses the authoritative allowlisted extension mapping instead of rejecting the file solely because the detected type is empty

#### Scenario: Reject a dangerous or unknown file

- **WHEN** a selected file has a denied executable extension or no accepted MIME/extension mapping
- **THEN** the system rejects it before issuing a signed upload and leaves the work-item attachment list unchanged

#### Scenario: Reject an oversized work-item attachment

- **WHEN** the selected file exceeds the God Mode per-file limit
- **THEN** the system rejects it before upload and displays the effective limit

### Requirement: Show accurate attachment upload state and errors

The system SHALL show progress and stable actionable failures for work-item attachment uploads instead of collapsing unrelated failures into one generic message.

#### Scenario: Upload is in progress

- **WHEN** the browser is transferring an attachment directly to object storage
- **THEN** the work-item detail displays the filename, size, and current progress without listing the asset as completed

#### Scenario: Storage is unavailable

- **WHEN** the active storage profile cannot issue or complete the upload
- **THEN** the UI reports storage unavailability, clears the transient progress state, and does not add a completed attachment

#### Scenario: File validation fails

- **WHEN** the API rejects an empty, oversized, dangerous, or unsupported file
- **THEN** the UI identifies the applicable reason and does not present the attachment as uploaded

#### Scenario: Finalization verification fails

- **WHEN** the uploaded object is missing or does not match the accepted upload intent
- **THEN** the UI reports that upload verification failed and the attachment remains unavailable until a successful retry creates or completes a valid upload

### Requirement: Preserve existing work-item attachment behavior

The system SHALL retain authorized listing, download, deletion, count, and activity behavior for existing and newly profiled work-item attachments.

#### Scenario: List legacy and new attachments together

- **WHEN** a work item contains attachments from the legacy store and an activated object-storage profile
- **THEN** the detail view lists both sets consistently while each access operation resolves its own storage profile

#### Scenario: Download an attachment

- **WHEN** an authorized user selects an existing or new work-item attachment
- **THEN** the system checks current work-item access and issues a short-lived attachment download with the sanitized original filename

#### Scenario: Delete an attachment

- **WHEN** an authorized user deletes an attachment under existing work-item rules
- **THEN** the asset follows the existing soft-delete and activity behavior through its recorded storage profile and the visible attachment count updates

#### Scenario: Upload succeeds

- **WHEN** a new work-item attachment is finalized successfully
- **THEN** the attachment list, count, and existing attachment activity behavior update once without duplicate entries

### Requirement: Isolate work-item attachments by entity permissions

The system MUST scope attachment operations to the active workspace, project, work item, and authorized actor.

#### Scenario: Request another project's attachment

- **WHEN** a user supplies an attachment identifier that belongs to another project or work item
- **THEN** the system denies the request without rebinding the asset, revealing its metadata, or issuing signed access

#### Scenario: User loses work-item access

- **WHEN** a user who previously received attachment metadata no longer has access to the bound work item
- **THEN** subsequent preview, download, delete, restore, or finalize requests are denied even if the asset identifier is known

#### Scenario: Signed access expires

- **WHEN** a previously authorized object-store URL expires
- **THEN** the user must request new access and pass current work-item authorization again
