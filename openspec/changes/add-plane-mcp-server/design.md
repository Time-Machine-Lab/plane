## Context

Plane already has API-token-authenticated external endpoints under `/api/v1`, with membership and role checks performed by the API. MCP-capable AI clients need a standard Streamable HTTP endpoint and a smaller, task-oriented tool surface, but the MCP layer must not become a second implementation of Plane business rules or a direct database consumer.

The change crosses a new runtime module, the existing API contract, edge routing, deployment assets, and API-token security. It therefore needs an explicit protocol and deployment boundary.

## Goals / Non-Goals

**Goals:**

- Expose a same-origin `/mcp` endpoint usable by Codex, Matika, and other remote MCP clients.
- Reuse an existing Plane API token and the corresponding user's current authorization.
- Provide a focused, discoverable tool catalog for common workspace operations.
- Keep tool handlers thin by translating calls to `/api/v1` and returning normalized MCP results.
- Allow the MCP runtime to be deployed, disabled, and rolled back independently from the Django API.

**Non-Goals:**

- OAuth, new token scopes, new account types, or a separate Plane permission model.
- Direct database access from the MCP runtime.
- Complete parity with every Plane UI action.
- Destructive workspace administration or autonomous event-driven agents.
- Storing a user's API token in Plane MCP configuration or tool arguments.

## Decisions

### Add a dedicated thin MCP runtime

Create `apps/mcp` as a small TypeScript service using the official MCP SDK and Streamable HTTP transport. The edge proxy exposes it as `/mcp` on the Plane origin.

This keeps protocol dependencies and MCP lifecycle behavior outside Django while preserving a single public Plane address. Embedding protocol handling in Django was considered, but it would couple MCP transport evolution to the API process. A user-installed local-only MCP server was also considered, but it would not provide a common endpoint for hosted agents such as Matika.

### Authenticate with the existing Plane API token

The MCP endpoint accepts `Authorization: Bearer <plane-api-token>`. It never accepts the token as a tool parameter and never includes it in tool results or logs. The runtime forwards the credential to Plane API requests as `X-Api-Key`.

The MCP runtime performs no independent role calculation. `/api/v1` remains authoritative for workspace membership, project roles, and object ownership. A token that is invalid, expired, inactive, or unauthorized receives a stable MCP error derived from the API response.

### Keep workspace context explicit and stateless

Workspace tools accept an optional `workspace_slug`. When omitted, the runtime uses an optional `X-Plane-Workspace` connection header configured by the client. If neither value is present, the tool returns a validation error before calling Plane.

An explicit tool argument takes precedence over the default header, but it does not grant access: the Plane API still validates the token user against the requested workspace. The runtime stores no per-user connection state.

### Translate tools to existing external API contracts

Tool handlers use a typed Plane API client configured with the internal or public Plane API base URL, bounded timeouts, and redacted structured logging. Handlers validate MCP input, issue one or more existing `/api/v1` requests, and normalize the result; they do not reproduce serializers, permissions, or domain mutations.

If an intended tool cannot be implemented safely with an existing external API contract, implementation adds or adjusts that contract in `apps/api/plane/api` with OpenAPI and contract coverage rather than bypassing it.

### Start with a non-destructive tool catalog

The initial catalog contains connection status, project reads, work-item reads and writes, comments, and supporting states, labels, cycles, modules, and member reads. It does not expose delete, invitation, member-management, workspace-settings, token-management, export, archive, or restore operations.

Tool schemas use stable IDs and slugs, reject unknown fields, and return compact structured data plus canonical Plane URLs where available. List tools preserve API pagination metadata instead of silently loading an unbounded result set.

### Use existing deployment and verification boundaries

Local, test, and supported self-hosted deployment assets start the MCP service and route `/mcp` only when enabled. Health checks distinguish process availability from authenticated `plane_status` behavior. The implementation is verified through the repository's single deployment workflow and independent scenario acceptance.

## Risks / Trade-offs

- **New runtime increases deployment surface** -> Keep the service stateless and thin, use existing Node service patterns, and route it behind the existing proxy.
- **External API gaps could encourage duplicated business logic** -> Require tool handlers to use `/api/v1`; add missing external contracts explicitly when needed.
- **A human user's token attributes AI changes to that user** -> Document a dedicated Plane account as the recommended operational practice without requiring a new account model.
- **Prompt or log leakage could expose tokens** -> Credentials remain transport headers, sensitive headers are redacted, and error payloads exclude request headers.
- **Large tool responses can consume model context** -> Require pagination, compact projections, and bounded defaults.
- **MCP clients vary in header and workspace configuration support** -> Support both a default workspace header and explicit per-tool workspace input.

## Migration Plan

1. Add the MCP runtime and focused contract coverage without exposing a public route by default.
2. Add proxy and deployment configuration behind an enablement setting.
3. Deploy through `scripts/test/deploy-test.ps1` and have an independent Tester verify the OpenSpec scenarios with persistent API-token accounts.
4. Enable `/mcp` for the target environment after successful acceptance.

Rollback disables or removes the `/mcp` route and stops the MCP runtime. Existing `/api/v1` behavior and data remain unchanged because the change introduces no database migration.

## Open Questions

- Confirm the exact official MCP SDK version during implementation based on the repository's supported Node runtime and current Streamable HTTP API.
- Confirm which existing member endpoint provides the smallest authorized member projection; omit `list_members` from the first release if the external contract is not suitable.
