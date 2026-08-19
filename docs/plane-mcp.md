# Plane MCP Server

Plane can expose a Streamable HTTP MCP endpoint at `/mcp`. The MCP service is a stateless adapter over the existing
Plane external API; it does not access the database and does not introduce a separate permission model.

## Enablement

Self-hosted deployments keep the endpoint disabled by default. Set the following environment variable and restart the
`mcp` and `proxy` services:

```env
MCP_ENABLED=true
```

The standard container configuration uses `http://api:8000/api/v1` internally. These optional limits can be adjusted
without changing Plane API behavior:

```env
PLANE_API_BASE_URL=http://api:8000/api/v1
PLANE_API_TIMEOUT_MS=10000
PLANE_API_RESPONSE_LIMIT_BYTES=1048576
```

When enabled, MCP clients connect to `https://<plane-origin>/mcp`. The service health endpoint is available only inside
the deployment at `/health` on port `3100`.

## Authentication And Workspace Context

Create a Plane API token for the Plane account the AI should act as, then configure the MCP client to send it only as a
request header:

```http
Authorization: Bearer <plane-api-token>
```

Do not put the token in prompts, tool arguments, repository files, or Skill files. The MCP service forwards the token to
Plane `/api/v1` as `X-Api-Key`; existing workspace membership and project roles remain authoritative. A dedicated normal
Plane account is recommended when AI actions should have a distinct audit identity.

Workspace-scoped tools accept `workspace_slug`. A client may instead configure this connection header:

```http
X-Plane-Workspace: <workspace-slug>
```

An explicit tool argument takes precedence over the header. Neither option grants access to a workspace the Plane
account cannot access.

## Initial Tools

The initial catalog contains:

- `plane_status`, `list_projects`, and `get_project`
- `list_work_items`, `search_work_items`, `get_work_item`, `create_work_item`, and `update_work_item`
- `list_comments` and `add_comment`
- `list_states`, `list_labels`, `list_cycles`, `list_modules`, and `list_members`

List operations are bounded and preserve available Plane pagination metadata. The catalog intentionally excludes delete,
archive, restore, export, invitation, member administration, workspace settings, and API-token management operations.

## Disable Or Roll Back

Set `MCP_ENABLED=false` and restart the `mcp` service to make `/mcp` return not found. To remove the runtime entirely,
stop the `mcp` service and roll back the proxy image or configuration. No Plane data migration or API rollback is needed.
