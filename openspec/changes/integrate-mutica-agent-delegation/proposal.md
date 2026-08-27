## Why

Teams use Plane as the work-item board and an already deployed Mutica environment as the place where agents collaborate with people and execute delegated work. Plane needs a workspace-scoped way to hand a work item to a Mutica agent without requiring every member to configure personal credentials or making Plane responsible for the agent's execution lifecycle.

## What Changes

- Add a workspace-admin flow to connect an existing Mutica environment, bind one default workspace-wide Mutica assistant, verify delivery configuration, and disconnect or rotate the connection without deploying Mutica software.
- Provision a non-human, workspace-scoped Plane service identity and revocable service token for Mutica instead of using a member's personal API token.
- Add an independent Mutica delegation property and action to work items while preserving the existing human assignee model.
- Deliver a signed, idempotent delegation event containing stable Plane and Mutica identifiers; Mutica uses Plane MCP tools and the service token to pull authoritative work-item context.
- Track only the handoff states Plane can establish reliably: dispatching, handed off, and failed. Agent execution and completion continue to use the work item's normal Plane state and are updated by Mutica through Plane MCP.
- Allow reassignment to create a new delegation attempt while preserving prior handoff history and preventing stale responses from replacing the active delegation.
- Extend Plane MCP work-item reads to include the description and authorized attachment metadata or download access, complementing the existing comment tools so Mutica can retrieve the full task context.
- Revoke the service token and disable further delegation when the workspace disconnects Mutica.

### Non-goals

- Deploying, installing, creating, or configuring the Mutica runtime or its agents.
- Mirroring Mutica's discussion, queue, execution, or completion lifecycle inside Plane.
- Giving Mutica an instance-wide Plane credential or requiring each Plane member to configure a personal Mutica assistant or personal Plane token.
- Sending attachment file bodies inside the delegation event.
- Automatically closing or otherwise interpreting the work item's business state on Mutica's behalf.

## Capabilities

### New Capabilities

- `mutica-workspace-connection`: Connect an existing Mutica environment to one Plane workspace, manage its default assistant and delivery credentials, and provision a constrained Plane service identity for Mutica access.
- `mutica-work-item-delegation`: Delegate and reassign work items to the connected Mutica assistant with explicit authorization, idempotent delivery, visible handoff outcome, and preserved history.

### Modified Capabilities

- `plane-mcp-tools`: Expand authorized work-item context reads to return descriptions and expose attachment listing and access without adding destructive or administrative tools.

## Impact

- **Web app:** workspace integration settings, work-item creation/detail delegation controls, activity/history presentation, loading and error states.
- **API:** Mutica connection and delegation endpoints, authorization, service-identity lifecycle, outbound delivery orchestration, retry/idempotency behavior, and attachment access contracts.
- **Database:** new connection/agent/delegation records plus a migration; existing human assignee data and APIs remain compatible.
- **MCP:** bounded work-item description and attachment read support; existing tool names and behaviors remain compatible.
- **Shared packages:** typed service contracts, constants, state where justified, and localized user-facing strings.
- **Security:** workspace and project isolation, secret confidentiality, service-token rotation/revocation, signed delivery, SSRF-safe Mutica endpoints, and redacted logs are required.
- **Deployment and compatibility:** no third-party package or separate runtime is required, but the API, worker, web, and MCP services may be affected. Rollout must tolerate existing workspaces with no Mutica connection and must not change current assignee behavior.
- **Licensing:** no licensing or plan restriction is introduced by this proposal.
- **Applicable standards:** `docs/spec/general-development.md`, `docs/spec/frontend-development.md`, `docs/spec/backend-development.md`, `docs/spec/shared-packages-development.md`, `docs/spec/module-structure.md`, and `docs/spec/testing-quality.md`.
