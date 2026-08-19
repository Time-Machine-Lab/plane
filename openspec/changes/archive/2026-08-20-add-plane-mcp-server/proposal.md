## Why

External AI clients need a stable, structured way to read and operate a Plane workspace with an existing Plane account. Plane already exposes API-token-authenticated `/api/v1` capabilities, but AI clients currently lack a standard MCP endpoint that discovers and invokes those capabilities as tools.

## What Changes

- Add a thin MCP server runtime exposed from the Plane origin at `/mcp` using the Streamable HTTP transport.
- Authenticate MCP requests with an existing Plane API token and preserve the token user's current workspace and project permissions.
- Expose a focused initial tool catalog for connection status, projects, work items, comments, states, labels, cycles, modules, and members.
- Translate MCP tool calls into existing Plane `/api/v1` requests rather than accessing Plane data directly.
- Normalize tool validation, pagination, authorization failures, API failures, and response payloads for AI clients.
- Route and deploy the MCP runtime with Plane while allowing it to be disabled or rolled back independently.
- Exclude OAuth, new permission models, account provisioning, destructive administration tools, and autonomous event-triggered agents from this change.

## Capabilities

### New Capabilities

- `plane-mcp-access`: Remote MCP connection, API-token authentication, workspace context, status checks, and failure behavior.
- `plane-mcp-tools`: Discoverable Plane tool definitions and execution against the existing external API.

### Modified Capabilities

None.

## Impact

- Adds a deployable runtime under `apps/mcp` and a same-origin `/mcp` proxy route.
- Adds MCP SDK/runtime dependencies and deployment configuration for local, test, and supported self-hosted stacks.
- Reuses `apps/api/plane/api` contracts and the existing `X-Api-Key` authentication and membership authorization behavior; no database migration is expected.
- Requires focused MCP protocol, API mapping, authorization-isolation, and error-contract coverage.
- Applicable standards: `docs/spec/general-development.md`, `docs/spec/backend-development.md`, `docs/spec/module-structure.md`, `docs/spec/testing-quality.md`, and `docs/spec/test-environment.md`.
- Existing `/api/v1` consumers remain compatible; disabling the new MCP route restores the previous deployment behavior.
