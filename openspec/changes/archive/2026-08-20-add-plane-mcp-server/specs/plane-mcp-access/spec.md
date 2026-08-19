## ADDED Requirements

### Requirement: Remote MCP endpoint

Plane SHALL expose an MCP Streamable HTTP endpoint at `/mcp` when the MCP runtime is enabled.

#### Scenario: MCP client initializes successfully

- **WHEN** an MCP client sends a valid initialization request to the enabled `/mcp` endpoint
- **THEN** the system returns a valid MCP initialization response advertising its supported server capabilities

#### Scenario: MCP runtime is disabled

- **WHEN** the MCP runtime is disabled for an environment
- **THEN** the Plane deployment does not advertise or route an operational `/mcp` endpoint

### Requirement: API-token authentication

The MCP server SHALL authenticate requests with a Plane API token supplied as a Bearer credential and SHALL execute Plane API requests as the token's user.

#### Scenario: Valid API token

- **WHEN** a client calls an MCP tool with a valid active Plane API token
- **THEN** the MCP server forwards the request to Plane using that token and returns the authorized result

#### Scenario: Invalid or expired API token

- **WHEN** a client calls the MCP server with a missing, invalid, inactive, or expired Plane API token
- **THEN** the MCP server rejects the call with an authentication error and does not invoke a Plane business operation

#### Scenario: Existing role denies an operation

- **WHEN** the token user lacks the Plane workspace or project role required by a requested tool operation
- **THEN** the MCP server returns an authorization error matching the Plane API decision and does not broaden the user's access

### Requirement: Workspace context

Workspace-scoped tools SHALL use an explicit workspace slug from the tool call or a configured default workspace header, without storing server-side user connection state.

#### Scenario: Explicit workspace is supplied

- **WHEN** a tool call includes `workspace_slug`
- **THEN** the MCP server uses that slug for the Plane API request and relies on Plane to validate access

#### Scenario: Default workspace is supplied by the connection

- **WHEN** a tool call omits `workspace_slug` and the connection supplies `X-Plane-Workspace`
- **THEN** the MCP server uses the header value as the workspace slug

#### Scenario: Workspace context is absent

- **WHEN** a workspace-scoped tool call supplies neither an explicit workspace slug nor a default workspace header
- **THEN** the MCP server returns a validation error without invoking the Plane API

### Requirement: Connection status

The MCP server SHALL provide a `plane_status` tool that verifies authentication and optional workspace access without mutating Plane data.

#### Scenario: Status succeeds

- **WHEN** an authenticated client calls `plane_status` with an accessible workspace context
- **THEN** the result identifies the authenticated Plane user, Plane origin, workspace, and connection availability without exposing credentials

#### Scenario: Workspace is inaccessible

- **WHEN** an authenticated client calls `plane_status` for a workspace the token user cannot access
- **THEN** the result is an authorization error and contains no workspace data

### Requirement: Credential confidentiality

The MCP runtime MUST keep Plane API tokens out of tool schemas, tool results, application logs, and user-facing errors.

#### Scenario: Tool call is logged

- **WHEN** the MCP runtime records a request, response, or failure
- **THEN** authorization and API-token header values are redacted and no token value is persisted

#### Scenario: Upstream failure occurs

- **WHEN** a Plane API request fails unexpectedly
- **THEN** the client receives a stable error without internal headers, credentials, absolute filesystem paths, or raw exception details
