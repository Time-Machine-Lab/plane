## ADDED Requirements

### Requirement: Insert independent Canvas blocks

The system SHALL allow a user with Page edit permission to insert one or more independently identified Canvas blocks from the Page block insertion experience.

#### Scenario: Insert a new Canvas block

- **WHEN** an authorized editor selects the Canvas slash command or block action
- **THEN** the system inserts a Canvas block with a unique identifier and default title and opens it for editing

#### Scenario: Keep multiple canvases independent

- **WHEN** a Page contains multiple Canvas blocks and the user changes one of them
- **THEN** the other Canvas blocks retain their own titles, scenes, previews, and identifiers unchanged

#### Scenario: Prevent insertion without edit permission

- **WHEN** a user views a Page without edit permission
- **THEN** the system does not offer or execute the Canvas insertion command

### Requirement: Preview Canvas content inside the Page

The system SHALL render each Canvas block as a stable document preview with its title and an action to open the canvas without making the inline block an interactive drawing surface.

#### Scenario: Display a saved Canvas

- **WHEN** a Page renders a Canvas block with a valid saved preview
- **THEN** the document displays the title and preview without disrupting surrounding Page content or scrolling

#### Scenario: Resize the document preview

- **WHEN** an authorized editor selects a supported Canvas preview size
- **THEN** the system changes the block display size without changing the canvas scene coordinates or content

#### Scenario: Display an unavailable preview

- **WHEN** the preview is missing, malformed, or cannot be decoded
- **THEN** the system displays the Canvas title and a neutral unavailable state while preserving the stored scene

### Requirement: Edit Canvas content in a focused overlay

The system SHALL open Canvas content in a full-screen editor that provides selection, shapes, connectors, lines, freehand drawing, text, styling, pan, zoom, undo, and redo.

#### Scenario: Open an editable Canvas

- **WHEN** a user with Page edit permission opens a Canvas block that is not being edited by another connected user
- **THEN** the system opens the full-screen editor with the saved scene and enables the supported drawing controls

#### Scenario: Open a Canvas from a read-only Page

- **WHEN** a user without Page edit permission opens a Canvas block
- **THEN** the system opens the canvas in view-only mode without mutation controls

#### Scenario: Close after editing

- **WHEN** an editor closes the Canvas overlay after making valid changes
- **THEN** the system flushes pending changes, returns to the same Page context, and refreshes the document preview

### Requirement: Save versioned Canvas snapshots safely

The system SHALL persist a versioned Canvas scene and bounded preview through the existing Page document transaction and SHALL exclude embedded file payloads from the first-release scene format.

#### Scenario: Autosave a valid scene

- **WHEN** an authorized editor changes a Canvas and pauses editing
- **THEN** the system debounces the update, saves the scene and regenerated preview in one document update, and indicates when the save is complete

#### Scenario: Recover the latest saved Canvas

- **WHEN** a user reloads the Page or recovers it from the existing offline document cache
- **THEN** the Canvas opens with the latest successfully persisted scene snapshot

#### Scenario: Reject an oversized scene

- **WHEN** a Canvas update exceeds the configured scene or preview size limit
- **THEN** the system rejects that update, preserves the last valid snapshot, and presents an actionable size error

#### Scenario: Reject unsupported embedded files

- **WHEN** a first-release Canvas scene contains an imported image or other file payload
- **THEN** the system prevents the unsupported payload from being saved and explains that the content type is not supported

#### Scenario: Handle save failure

- **WHEN** the Page document cannot persist a pending Canvas update
- **THEN** the system shows a retryable failure state and does not report the Canvas as saved

### Requirement: Reduce accidental concurrent overwrite

The system SHALL use connected Page collaboration awareness to make one active Canvas editor visible to other clients without representing that awareness as an authorization decision.

#### Scenario: Another user is editing the Canvas

- **WHEN** a connected collaborator is already editing the same Canvas block
- **THEN** the system opens that Canvas for other collaborators in view-only mode and indicates that it is currently being edited

#### Scenario: Active editor leaves

- **WHEN** the active Canvas editor closes the overlay or disconnects
- **THEN** the advisory edit state clears and another authorized collaborator can enter edit mode

#### Scenario: Awareness is unavailable

- **WHEN** collaboration awareness is unavailable or two clients bypass the advisory state
- **THEN** Page permissions remain authoritative and persisted Canvas snapshots use last-writer-wins behavior

### Requirement: Preserve Canvas content across Page lifecycle operations

The system SHALL preserve supported Canvas blocks through serialization, Yjs persistence, Page duplication, Page version display, and Page version restoration.

#### Scenario: Duplicate a Page containing canvases

- **WHEN** an authorized user duplicates a Page containing one or more valid Canvas blocks
- **THEN** the duplicated Page contains corresponding canvases with their titles, scenes, and previews available

#### Scenario: View a historical Page version

- **WHEN** a historical Page version contains a Canvas block
- **THEN** the version viewer displays that Canvas title and preview in read-only form

#### Scenario: Restore a historical Page version

- **WHEN** an authorized user restores a Page version containing Canvas blocks
- **THEN** the active Page restores the Canvas titles, scenes, previews, and block placement from that version

#### Scenario: Canvas editing is disabled after rollout

- **WHEN** stored Canvas content is rendered while Canvas insertion or interactive editing is disabled
- **THEN** the system preserves the node and displays a non-editable fallback instead of dropping its stored content

### Requirement: Export a portable Canvas representation

The system SHALL represent each valid Canvas block by its title and stored preview in supported Page exports without requiring the interactive Excalidraw runtime.

#### Scenario: Export a Page to PDF with assets

- **WHEN** a user exports a Page containing valid Canvas blocks to PDF and includes assets
- **THEN** each Canvas appears as a bounded preview with its title in the exported document

#### Scenario: Export a Page to Markdown with assets

- **WHEN** a user exports a Page containing valid Canvas blocks to Markdown and includes assets
- **THEN** each Canvas appears with its title and a self-contained preview image representation

#### Scenario: Export without assets

- **WHEN** a user exports a Page containing Canvas blocks with the no-assets option
- **THEN** the export omits Canvas preview images but retains a textual Canvas title placeholder

#### Scenario: Export malformed Canvas data

- **WHEN** a Canvas scene or preview is malformed during export
- **THEN** the export completes for the remaining Page content and substitutes a title-based unavailable placeholder for that Canvas

### Requirement: Validate Canvas document data

The system MUST treat Canvas attributes as untrusted document content and SHALL validate the custom element, named attributes, encoded payloads, scene version, decoded size, and preview dimensions at applicable client and server boundaries.

#### Scenario: Sanitize supported Canvas HTML

- **WHEN** the API receives a valid `canvas-component` with supported attributes
- **THEN** sanitization preserves the required Canvas data without allowing executable markup or arbitrary attributes

#### Scenario: Reject unsafe Canvas HTML

- **WHEN** Canvas content includes an unsupported attribute, executable markup, unsafe URL, or invalid encoded payload
- **THEN** the system removes or rejects the unsafe data and does not execute it

#### Scenario: Encounter a future scene version

- **WHEN** a client cannot interpret the stored Canvas scene version
- **THEN** the system preserves the raw node, prevents destructive editing, and displays an unsupported-version fallback

### Requirement: Provide accessible and responsive Canvas controls

The system SHALL provide named controls, keyboard access, visible focus, theme-compatible rendering, and layouts that remain usable at supported Page viewport sizes.

#### Scenario: Navigate the Canvas block by keyboard

- **WHEN** a keyboard user focuses a Canvas block
- **THEN** the user can open it, identify its title and state, and leave the overlay without requiring pointer input

#### Scenario: Render on a narrow viewport

- **WHEN** a Page containing a Canvas block is displayed at a supported narrow viewport
- **THEN** the preview, title, and open action remain readable without overlapping surrounding content
