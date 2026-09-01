## ADDED Requirements

### Requirement: Extension fallback for attachment insertion

The editor MUST accept a file for attachment insertion when its MIME type is empty or generic if its filename has a supported attachment extension, including `.canvas`.

#### Scenario: Paste a Canvas file with generic browser MIME

- **WHEN** a user pastes or drops a `.canvas` file whose `File.type` is empty or `application/octet-stream`
- **THEN** the editor inserts an attachment node and starts the normal upload flow
- **AND** the upload metadata resolves the canonical type as `application/json`

### Requirement: Default inline HTML preview

An uploaded HTML attachment MUST render its bounded source in the existing isolated interactive preview without requiring an initial Open action.

#### Scenario: Open a Page containing an HTML attachment

- **WHEN** the authorized HTML source is available within the preview limit
- **THEN** the attachment displays an interactive sandboxed iframe immediately
- **AND** Download and View source actions remain available

### Requirement: Safe fallback

HTML preview failures MUST leave an actionable fallback.

#### Scenario: HTML source is unavailable or too large

- **WHEN** the preview endpoint cannot return bounded source
- **THEN** the attachment shows the unavailable state and an authorized Download action when available
- **AND** no unsandboxed HTML is injected into the parent document
