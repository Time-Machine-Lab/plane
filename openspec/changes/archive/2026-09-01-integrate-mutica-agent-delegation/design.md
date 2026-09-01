## Context

Plane currently models work-item responsibility through project-member assignees and intentionally removes bot users from normal member pickers. It also has `Integration`, `WorkspaceIntegration`, bot users, and API tokens with service/workspace fields, but the user-facing token endpoint creates only personal tokens and API authorization still executes as the token's user. Plane MCP can read and update work items and comments, but its work-item projection omits the description and it has no attachment tool.

Mutica is already deployed outside Plane. A Plane workspace administrator needs to connect that existing environment once, expose one default Mutica assistant to workspace members, and give Mutica a non-human Plane identity. Plane owns only a reliable handoff; Mutica owns task creation, discussion, execution, and subsequent Plane updates through MCP.

## Goals / Non-Goals

**Goals:**

- Establish one workspace-scoped Mutica connection and default assistant without per-member setup.
- Give Mutica a revocable non-human Plane service identity that cannot cross workspace boundaries.
- Keep Mutica delegation separate from human assignees and preserve handoff history.
- Make outbound handoff signed, idempotent, retryable, and observable without modeling Mutica execution.
- Let Mutica pull the authoritative description, comments, and attachment access through Plane MCP.
- Preserve compatibility for workspaces that never connect Mutica and for all existing assignee behavior.

**Non-Goals:**

- Deploying or administering Mutica or creating Mutica agents.
- Mirroring Mutica queue, discussion, execution, or completion state.
- Issuing an instance-wide credential or using a workspace member's personal token.
- Embedding file bodies or a complete mutable task snapshot in the delegation event.
- Adding destructive or administrative MCP tools.

## Decisions

### 1. Treat setup as a workspace connection, not an installation

The web UI will say **Connect Mutica**. An administrator supplies the existing Mutica delivery endpoint, a shared signing secret, and the external identifier and display metadata for the default assistant. Plane verifies the endpoint with an SSRF-safe, non-destructive handshake before enabling delegation.

The first release uses explicit connection values rather than requiring a Mutica OAuth or installation API that is outside this repository. A future automated registration flow can populate the same connection contract.

### 2. Reuse the integration actor pattern and create a dedicated service identity

A Mutica connection will use the existing `Integration` and `WorkspaceIntegration` ownership pattern. Plane creates a bot user such as `Mutica Integration`, workspace/project memberships that cover the connected workspace, and an `APIToken` marked as a bot service token and bound to that workspace. The raw token is returned only during connection or rotation so it can be provisioned into Mutica; it is never listed with personal tokens or written to logs, activities, or connection metadata.

API authentication continues to execute as the service user, preserving existing permission checks and audit attribution. The authentication boundary must additionally reject a workspace-bound service token when the requested workspace differs from the token workspace. Disconnecting or rotating the connection revokes the prior token immediately.

Alternative considered: use the connecting administrator's personal token. This was rejected because access and attribution would depend on that person's employment and role, and the token could carry unrelated access.

Alternative considered: create an instance-wide integration token. This was rejected because it breaks tenant isolation and creates an unnecessarily large credential blast radius.

### 3. Store assistant identity separately from Plane users and human assignees

A Mutica assistant is an external agent record owned by the workspace integration, not a selectable Plane member. The initial connection creates one enabled default assistant, while the data model can support more assistants later without changing delegation records.

The work item receives a separate Mutica delegation property. Existing `IssueAssignee` data, filters, analytics, and notification behavior remain unchanged.

### 4. Persist immutable delegation attempts and one active delegation

Each delegation attempt records the work item, Mutica agent, initiating user, correlation identifier, status, timestamps, delivery attempts, and a safe failure category. At most one non-superseded delegation is active for a work item. Reassigning or clearing the property supersedes the old record rather than rewriting it, preserving history and preventing a delayed response for an old attempt from becoming current.

The user-visible handoff state is intentionally small:

```text
dispatching -> handed_off
           -> failed

dispatching/handed_off/failed -> superseded (on reassignment or clear)
```

Plane sets `dispatching` when it commits the delegation. It sets `handed_off` only after the Mutica endpoint durably accepts that `delegation_id` with a successful response. A transport success that does not represent durable acceptance must be labeled as notification delivery rather than agent acceptance. Plane never infers execution from API-token usage.

Mutica execution state is represented only through the work item's ordinary Plane state when the agent chooses to update it through MCP.

### 5. Send a thin signed event and let Mutica pull authoritative context

After the database transaction commits, a background task sends a signed event with a stable contract:

- event type and schema version;
- delivery ID and delegation ID;
- Plane origin and canonical work-item URL;
- workspace slug, project ID, and work-item ID;
- external Mutica agent ID;
- delegation timestamp.

The event contains no service token, comments, attachment bodies, or expiring download URLs. Mutica uses the separately provisioned Plane service token and MCP to read the latest task context. This avoids stale duplicated payloads and keeps retry messages small.

The delivery ID and delegation ID are idempotency keys. Retries use bounded exponential backoff. Response bodies and secrets are redacted; failure categories remain actionable without exposing credentials. Existing URL safety utilities and pinned outbound requests protect against private-network and DNS-rebinding targets.

Alternative considered: send the complete task, all comments, and all files in the event. This was rejected because updates during retries would produce ambiguous snapshots, comments can be large, and files or signed links can exceed delivery limits or expire.

### 6. Keep delegation controls within existing work-item interaction patterns

Workspace settings expose connection, verification, rotation, and disconnect actions only to workspace administrators. Work-item creation and details expose **Delegate to Mutica** only when the connection and default assistant are enabled and the current user can edit the work item.

Creation persists the work item first and then creates the delegation so Mutica never receives an incomplete draft identifier. The detail property shows the assistant identity plus `dispatching`, `handed off`, or actionable `failed` feedback. Activity history records delegation, retry outcome, reassignment, and clear actions, but does not create execution activities.

### 7. Extend MCP with bounded description and attachment reads

`get_work_item` will include the current sanitized description representation within existing response-size limits. A new read-only attachment tool will list bounded metadata including attachment identifier, name, media type, size when known, and authorized download access. The tool will not embed file bytes in MCP results.

Attachment access continues to use Plane's workspace/project/work-item authorization and produces a current authorized download URL or equivalent download endpoint. Comments continue through the existing paginated tool. Mutica can therefore assemble full context without a special Mutica-only content API.

## Risks / Trade-offs

- **A shared workspace service identity cannot attribute ordinary Plane edits to an individual Mutica sub-agent.** -> The delegation record retains the selected external agent ID; if future agents require distinct permissions or audit identities, issue separate service identities without changing the delegation contract.
- **Workspace-wide project access gives Mutica broader visibility than a single delegated item.** -> Show this scope during connection, bind the token to one workspace, use a dedicated bot, and allow immediate rotation or disconnect. Object-scoped tokens can be considered separately if required.
- **Mutica can accept a handoff but fail before an agent begins work.** -> `handed_off` explicitly means durable transfer to Mutica, not execution; normal Plane workflow state remains authoritative for progress.
- **Retries or delayed responses can race with reassignment.** -> Use immutable delegation IDs, conditional state transitions, and an active-delegation constraint so stale attempts cannot overwrite the current property.
- **Attachment download links can expire.** -> Return current authorized access on demand through MCP rather than persisting links in delegation records or events.
- **Connection secrets and service tokens are high-value credentials.** -> Minimize display, redact all logs, encrypt stored Mutica secrets, enforce workspace scope, and revoke old credentials on rotation/disconnect.
- **The external Mutica contract may evolve.** -> Version the event payload and keep provider-specific transport behind the integration boundary.

## Migration Plan

1. Add new nullable/independent Mutica connection, agent, and delegation tables and seed the Mutica integration provider without changing existing work-item or assignee rows.
2. Deploy API and worker support with delegation disabled until a workspace explicitly connects Mutica.
3. Deploy the MCP description and attachment read additions while preserving existing tool inputs and result fields.
4. Deploy web connection and delegation controls after the API contracts are available.
5. On rollback, disable new delegation, revoke affected service tokens, and retain delegation history. The additive schema can remain until a later cleanup migration.

No real Mutica endpoint is required for automated or independent verification; use a local or offline endpoint stub unless the user separately authorizes a real third-party call.

## Open Questions

No blocking product questions remain. The concrete Mutica endpoint path and handshake field names can be finalized against Mutica's receiving contract during implementation without changing Plane's ownership, identity, state, or security decisions above.
