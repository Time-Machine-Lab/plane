## 1. Data Model And Shared Contracts

- [ ] 1.1 Add Mutica connection, external agent, immutable work-item delegation, and delivery-attempt models with workspace/project ownership, one-active-delegation constraints, safe status enums, and additive migrations.
- [ ] 1.2 Seed or register the Mutica integration provider and wire model exports without changing existing integration, member, assignee, or token records.
- [ ] 1.3 Add typed connection, agent, delegation, and event contracts in the appropriate shared packages and expose only stable public exports.

## 2. Workspace Connection And Service Identity

- [ ] 2.1 Implement workspace-admin connection endpoints that validate the existing Mutica endpoint, signing secret, and default assistant with the repository's URL/SSRF protections and return secrets only through explicit one-time provisioning responses.
- [ ] 2.2 Provision a dedicated Mutica bot, workspace membership, current-project memberships, and workspace-bound bot service token transactionally when a connection is enabled.
- [ ] 2.3 Keep the Mutica service identity synchronized into newly created projects in the connected workspace with the minimum role required for MCP work-item reads and writes.
- [ ] 2.4 Enforce the `APIToken.workspace` boundary for service tokens during external API authentication and confirm personal-token APIs cannot list, mutate, or delete Mutica service credentials.
- [ ] 2.5 Implement connection verification, service-token rotation, disable, and disconnect behavior with immediate old-token revocation, redacted diagnostics, and retained delegation history.

## 3. Delegation API And Delivery

- [ ] 3.1 Implement authorized work-item delegation, retry, reassign, clear, current-state, and history endpoints that keep Mutica delegation independent from `IssueAssignee` and schedule delivery only after commit.
- [ ] 3.2 Implement conditional delegation transitions for `dispatching`, `handed_off`, `failed`, and `superseded` so stale attempts and responses cannot replace the current delegation.
- [ ] 3.3 Implement the versioned thin Mutica event serializer with stable Plane/Mutica identifiers, HMAC signature and timestamp headers, idempotent delegation/delivery identifiers, and no comments, attachment bodies, expiring links, or service credentials.
- [ ] 3.4 Implement bounded asynchronous delivery and retry behavior using the existing pinned outbound-request safety pattern, safe failure categories, and secret/response redaction.
- [ ] 3.5 Add non-sensitive work-item activity records for delegation, retry outcome, reassignment, and clear actions without creating Mutica execution or completion activities.

## 4. Plane MCP Context Reads

- [ ] 4.1 Extend `get_work_item` to return the current sanitized description within the existing response-size and authorization boundaries.
- [ ] 4.2 Add a paginated read-only attachment tool that maps the existing attachment API to bounded metadata and current authorized download access without returning file bytes.
- [ ] 4.3 Update MCP tool projections, schemas, tool catalog, error mapping, and credential redaction while preserving all existing tool inputs and result fields.

## 5. Web Experience

- [ ] 5.1 Add a workspace-admin **Connect Mutica** settings experience for endpoint verification, default assistant details, one-time service-token provisioning, rotation, connection status, and disconnect with complete loading, error, and disabled states.
- [ ] 5.2 Add an optional Mutica delegation control to work-item creation that submits only after the work item is persisted and remains unavailable when the connection or permissions are invalid.
- [ ] 5.3 Add a separate Mutica property to work-item details showing the default assistant and `dispatching`, `handed off`, or actionable `failed` feedback, with retry, reassign, and clear actions for authorized users.
- [ ] 5.4 Render delegation activity using existing work-item activity patterns and add synchronized locale keys through the repository translation workflow.

## 6. Focused Development Checks

- [ ] 6.1 Add focused backend unit or contract coverage for admin-only connection, service-token workspace isolation and revocation, project membership synchronization, delegation authorization, active-attempt races, signed event redaction, retries, and disconnect behavior using an offline Mutica endpoint stub.
- [ ] 6.2 Add focused MCP coverage for description projection, attachment pagination/access, cross-workspace rejection, result bounds, tool annotations, and regression of the existing catalog.
- [ ] 6.3 Run the smallest relevant API, MCP, web type/lint, and i18n synchronization checks for the files changed and resolve introduced failures without expanding to unrelated repository checks.

## 7. Independent Verification

- [ ] 7.1 Have the primary Agent create a fresh Tester sub-agent that did not participate in implementation to verify the connection boundary, non-human workspace credential, delegation/assignee separation, observable handoff outcomes, authoritative MCP context access, and necessary adjacent regressions without modifying product code.
- [ ] 7.2 If verification fails, fix only the affected implementation scope and have the same Tester recheck the failure and necessary adjacent behavior; do not use a real Mutica endpoint or deploy a test environment unless the core requirement cannot be validated with the local stub and the user authorizes the external call.
