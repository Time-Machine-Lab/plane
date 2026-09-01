## ADDED Requirements

### Requirement: Insert file attachments into editable Pages

The system SHALL allow a user with Page edit permission to insert allowed files as durable Page content attachments through the block insertion experience, file picker, drag, or paste.

#### Scenario: Insert a supported attachment

- **WHEN** an authorized Page editor selects or drops a non-empty allowed file within the instance size limit
- **THEN** the system inserts a stable uploading block, uploads the file to the selected object-storage profile, finalizes it, and replaces the block with an attachment bound to the returned asset ID

#### Scenario: Upload multiple dropped files

- **WHEN** an authorized editor drops multiple allowed files into a Page
- **THEN** the system inserts and processes one stable attachment block for each file without changing their source order

#### Scenario: Prevent insertion on a read-only Page

- **WHEN** a user without Page edit permission views or interacts with the Page editor
- **THEN** attachment insertion controls are unavailable and upload commands do not execute

#### Scenario: Cancel or retry an upload

- **WHEN** an attachment upload is in progress or has failed before finalization
- **THEN** the block offers the applicable cancel or retry action without creating duplicate available assets

#### Scenario: Reject a file before upload

- **WHEN** the selected file is empty, oversized, dangerous, or not in the safe attachment policy
- **THEN** the system keeps it out of the Page document's ready state and explains the specific validation failure

### Requirement: Preview supported Page attachment types

The system SHALL render supported Page attachments inline and SHALL retain a download fallback for every uploaded attachment.

#### Scenario: Preview plain text

- **WHEN** a ready attachment is valid UTF-8 TXT within the text preview limit
- **THEN** the Page displays a bounded read-only text preview with filename, size, and download action

#### Scenario: Preview Markdown safely

- **WHEN** a ready attachment is Markdown within the text preview limit
- **THEN** the Page renders its supported Markdown without executing raw HTML or scripts and retains the download action

#### Scenario: Preview PDF

- **WHEN** a ready attachment is a supported PDF
- **THEN** the Page displays the browser PDF viewer in a bounded surface and provides a download fallback

#### Scenario: Play MP4 video

- **WHEN** a ready attachment is MP4 with a codec supported by the browser
- **THEN** the Page displays native video controls and streams the authorized object without transcoding

#### Scenario: Play MP3 audio

- **WHEN** a ready attachment is MP3 supported by the browser
- **THEN** the Page displays native audio controls and streams the authorized object without waveform or format conversion

#### Scenario: Browser cannot preview supported media

- **WHEN** the browser cannot render the PDF or decode the MP4 or MP3 content
- **THEN** the attachment remains identifiable and downloadable and the Page displays a non-destructive preview-unavailable state

#### Scenario: Display a download-only attachment

- **WHEN** a ready attachment is allowed but has no inline preview contract, including supported Office documents or archives
- **THEN** the Page displays a metadata card with filename, type, size, and authorized download action

### Requirement: Preview interactive HTML in an isolated sandbox

The system SHALL allow a user to explicitly launch a bounded `.html` or `.htm` attachment with in-document interaction while treating its markup, styles, and scripts as untrusted content isolated from Plane.

#### Scenario: Launch an interactive HTML attachment

- **WHEN** an authorized user explicitly starts preview for an allowed HTML attachment within the HTML preview limit
- **THEN** the Page runs its supported inline scripts in an opaque-origin iframe with only the script sandbox capability so in-document controls such as buttons, filters, and dialogs can operate

#### Scenario: Attempt to access Plane privileges

- **WHEN** attachment code attempts to inspect the parent document, read Plane cookies or storage, submit a form, open a popup, trigger a download, or navigate the top-level application
- **THEN** the sandbox blocks the capability without granting the attachment same-origin or authenticated Plane access

#### Scenario: Depend on an external resource

- **WHEN** an HTML attachment references an external script, style, image, font, frame, media object, or network endpoint
- **THEN** the default preview policy blocks the external request, preserves any self-contained content and interactions that can still run, and retains source and download fallbacks

#### Scenario: Request an external link

- **WHEN** a user activates a link inside an HTML preview that targets content outside the artifact
- **THEN** the attachment cannot navigate Plane or open the destination directly and the system may offer a Plane-controlled confirmation before opening the validated destination outside the preview

#### Scenario: Reject unsafe or excessive HTML preview

- **WHEN** an HTML attachment is too large, cannot be decoded, violates the supported preview contract, or fails while running
- **THEN** the system stops or refuses interactive execution while preserving bounded source viewing and authorized original-file download

#### Scenario: Keep the signed object location private from HTML

- **WHEN** the parent obtains authorized HTML preview bytes from object storage
- **THEN** it supplies content to the isolated renderer without using the signed object URL as the attachment document location or exposing that URL through a frame bridge

### Requirement: Preview JSON Canvas 1.0 safely

The system SHALL provide a bounded read-only preview for a valid JSON Canvas 1.0 `.canvas` attachment without treating it as an editable Plane Canvas block.

#### Scenario: Preview standard canvas content

- **WHEN** a `.canvas` attachment is valid UTF-8 JSON Canvas 1.0 within the preview byte, node, edge, and coordinate bounds
- **THEN** the Page displays its text nodes, groups, link labels, and edges in a read-only pan-and-zoom surface

#### Scenario: Encounter a local file reference

- **WHEN** a JSON Canvas file node references a local or vault-relative file that was not explicitly mapped to an authorized Plane asset
- **THEN** the preview displays an unresolved file reference with its safe path label and does not read the user's filesystem or guess a storage URL

#### Scenario: Encounter an external link node

- **WHEN** a JSON Canvas contains an external link node
- **THEN** the preview displays a safely validated link action without automatically fetching or embedding the remote page

#### Scenario: Reject malformed or unsupported canvas data

- **WHEN** a `.canvas` file is malformed, uses an unsupported format version, or exceeds a preview resource bound
- **THEN** the system refuses to parse it inline, preserves the uploaded file, and displays a normal download card with an actionable preview-unavailable reason

#### Scenario: Upload a non-JSON file named canvas

- **WHEN** a file has a `.canvas` extension but fails JSON Canvas structural validation
- **THEN** the system does not execute or render its contents and exposes it only through the authorized download fallback

### Requirement: Track Page assets consistently

The system SHALL include ready image and non-image attachment nodes in the Page asset inventory with stable metadata and authorized actions.

#### Scenario: Open the Page assets pane

- **WHEN** a Page contains ready images and file attachments
- **THEN** the assets pane lists each item with an appropriate preview or file icon, filename, type or size metadata, location action, and authorized download action

#### Scenario: Attachment is unavailable

- **WHEN** an attachment node refers to a missing, unfinalized, deleted, or inaccessible asset
- **THEN** the Page and assets pane show a neutral unavailable state without exposing provider details or breaking the rest of the document

### Requirement: Preserve Page attachments across document lifecycle

The system SHALL preserve supported attachment nodes and their independent asset lifecycle across realtime persistence, reload, version display and restore, duplication, export, and feature rollback.

#### Scenario: Reload a Page containing attachments

- **WHEN** a Page with finalized attachment nodes is reloaded or recovered from collaboration persistence
- **THEN** each node retains its asset ID, metadata, presentation kind, placement, and authorized preview or download behavior

#### Scenario: View or restore a historical version

- **WHEN** a Page version contains attachment nodes
- **THEN** version display renders safe read-only attachment fallbacks and version restoration preserves the nodes and restorable assets from that version

#### Scenario: Duplicate a Page with attachments

- **WHEN** an authorized user duplicates a Page containing finalized attachments
- **THEN** the duplicate receives independent asset records and object keys in the source assets' storage profiles while preserving node order and presentation

#### Scenario: Export a Page with attachments

- **WHEN** a supported Page export encounters an attachment node
- **THEN** the export includes a bounded supported representation or filename, type, and size fallback and continues even when an attachment preview is unavailable

#### Scenario: Disable attachment insertion after rollout

- **WHEN** insertion or previews are disabled while stored attachment nodes still exist
- **THEN** the editor retains those nodes and displays a read-only metadata/download fallback instead of dropping document content

#### Scenario: Remove and undo an attachment node

- **WHEN** an authorized editor removes an attachment and then restores it through supported undo or version behavior within the asset retention window
- **THEN** the asset follows the existing soft-delete and restore lifecycle without immediate irreversible byte loss

### Requirement: Authorize Page attachment operations with Page access

The system MUST apply the bound Page's effective access rules to upload, finalize, preview, download, duplicate, restore, and delete operations.

#### Scenario: Owner accesses a private Page attachment

- **WHEN** the private Page owner requests an attachment operation permitted by their Page role
- **THEN** the operation proceeds using the asset's bound workspace, project, Page, and storage profile

#### Scenario: Project member requests another user's private Page attachment

- **WHEN** a project member lacks access to the private Page but supplies a valid asset UUID
- **THEN** the system denies the operation without issuing signed access or revealing asset metadata

#### Scenario: Asset identifier belongs to another Page or project

- **WHEN** a user submits an asset identifier outside the requested Page's active workspace/project relationship
- **THEN** the system rejects the operation and does not rebind or disclose the asset

### Requirement: Provide accessible and stable attachment controls

The system SHALL keep Page attachment blocks operable and readable with keyboard, assistive technology, supported themes, and narrow Page viewports.

#### Scenario: Operate an attachment by keyboard

- **WHEN** a keyboard user focuses an attachment block
- **THEN** the user can identify its filename and state and invoke available preview, play, retry, cancel, or download actions without pointer input

#### Scenario: Render on a narrow viewport

- **WHEN** an attachment preview or card is displayed on a supported narrow viewport
- **THEN** controls and text remain contained, the media surface keeps stable responsive dimensions, and surrounding Page content is not occluded
