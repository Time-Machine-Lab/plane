## MODIFIED Requirements

### Requirement: Work-item reads

The MCP server SHALL provide tools to list, search, and retrieve work items, including their current sanitized descriptions, and to list their comments and authorized attachment metadata using existing Plane external API contracts.

#### Scenario: Work items are listed with pagination

- **WHEN** a client lists work items for an accessible project
- **THEN** the result contains a bounded item set and the available pagination metadata

#### Scenario: Work item is retrieved

- **WHEN** a client requests an accessible work item by a supported identifier
- **THEN** the result contains its current core fields, sanitized description, and canonical identifiers without unrelated sensitive data

#### Scenario: Work-item context is inaccessible

- **WHEN** a client requests a work item, comments, or attachments outside the token user's authorized workspace or project
- **THEN** the server returns a not-found or authorization error and does not expose cross-workspace content or attachment access

## ADDED Requirements

### Requirement: Attachment reads

The MCP server SHALL provide a bounded read-only tool for listing authorized work-item attachment metadata and current download access without embedding attachment file bytes in MCP results.

#### Scenario: Attachments are listed

- **WHEN** an authenticated client lists attachments for an accessible work item
- **THEN** the result contains a bounded set of attachment identifiers, names, media types, sizes when known, and current authorized download access

#### Scenario: Work item has no attachments

- **WHEN** an authenticated client lists attachments for an accessible work item with no attachments
- **THEN** the tool returns an empty bounded result without error

#### Scenario: Download access expires

- **WHEN** previously returned attachment download access is no longer valid
- **THEN** the client can call the attachment listing tool again to obtain current authorized access without changing the work item

#### Scenario: Tool catalog is listed

- **WHEN** a client requests `tools/list`
- **THEN** the attachment tool is marked read-only and no tool for deleting or administrating attachments is advertised
