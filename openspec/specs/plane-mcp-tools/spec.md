## Purpose

Define Plane's initial MCP tool catalog, supported project and work-item operations, excluded destructive operations, and stable validation and error behavior.

## Requirements

### Requirement: Discoverable initial tool catalog

The MCP server SHALL advertise a focused initial catalog covering connection status, project access, work-item access, comments, and supporting project metadata.

#### Scenario: Client lists tools

- **WHEN** an authenticated or unauthenticated MCP client requests the server tool catalog according to the MCP protocol
- **THEN** the server returns stable tool names, descriptions, and input schemas for the supported initial catalog without exposing credentials

### Requirement: Project and metadata reads

The MCP server SHALL provide authorized tools to list and retrieve projects and to list the states, labels, cycles, modules, and suitable member data required to interpret or edit work items.

#### Scenario: Authorized project context is read

- **WHEN** the token user calls a project or metadata read tool for an accessible workspace and project
- **THEN** the server returns a compact structured result derived from `/api/v1`

#### Scenario: Project belongs to another workspace

- **WHEN** a client supplies a project identifier that does not belong to the requested workspace
- **THEN** the server returns a not-found or authorization error and does not return cross-workspace data

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

### Requirement: Work-item writes

The MCP server SHALL provide tools to create and update work items using only fields allowed by the tool schema and the existing Plane API.

#### Scenario: Work item is created

- **WHEN** an authorized user calls `create_work_item` with valid project, title, and optional supported fields
- **THEN** Plane creates one work item attributed to the token user and the tool returns its identifiers and current state

#### Scenario: Work item is updated

- **WHEN** an authorized user calls `update_work_item` with a valid work-item identifier and supported changes
- **THEN** Plane applies those changes through `/api/v1` and the tool returns the updated work item

#### Scenario: Unknown write field is supplied

- **WHEN** a create or update call contains a field outside the declared tool schema
- **THEN** the MCP server rejects the call as invalid and does not issue a partial mutation

### Requirement: Comment operations

The MCP server SHALL provide tools to list and add work-item comments through the existing Plane API.

#### Scenario: Comment is added

- **WHEN** an authorized user calls `add_comment` with a valid work item and non-empty supported comment content
- **THEN** Plane creates one comment attributed to the token user and the tool returns the created comment metadata

#### Scenario: Invalid comment is rejected

- **WHEN** a comment request is empty, malformed, or targets an inaccessible work item
- **THEN** the server returns a validation, not-found, or authorization error without creating a comment

### Requirement: Destructive and administrative operations are excluded

The initial MCP tool catalog MUST NOT expose tools for deletion, member administration, workspace settings, API-token management, export, archive, restore, or other destructive administration.

#### Scenario: Client lists the initial tools

- **WHEN** a client requests `tools/list`
- **THEN** no destructive or administrative tool named by this requirement is present

### Requirement: Stable validation and error mapping

Every Plane MCP tool SHALL validate its input before upstream calls and SHALL map Plane API validation, authentication, authorization, not-found, conflict, throttling, and unexpected failures to stable MCP errors.

#### Scenario: Input validation fails

- **WHEN** required input is missing or malformed
- **THEN** the tool returns a validation error describing the invalid field and does not call Plane

#### Scenario: Plane API throttles the token

- **WHEN** the Plane API returns a rate-limit response for the token
- **THEN** the MCP tool returns a throttling error and preserves available retry information without exposing credentials
