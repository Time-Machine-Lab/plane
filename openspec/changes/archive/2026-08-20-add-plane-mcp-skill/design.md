## Context

The dependent `add-plane-mcp-server` change provides a remote `/mcp` endpoint and atomic Plane tools. Codex can already act as an MCP client, so the remaining user problem is installing a reusable Plane Skill, configuring that client safely, validating a Plane workspace connection, and leaving a stable place for future operating guidance.

The solution should remain a Skill rather than creating a separately published npm installer or CLI product. Setup logic can live in explicit Skill scripts, while `SKILL.md` stays focused on routing and tool-use guidance.

## Goals / Non-Goals

**Goals:**

- Make a standard Codex Skill installation the only new client-side product surface.
- Configure and diagnose a remote Plane MCP connection using a workspace URL and existing API token.
- Let users complete the connection by giving the Agent only a workspace URL and dedicated API token; the Agent performs every local setup action.
- Keep the token out of repository files, Skill content, generated output, command arguments, and Plane work items while explicitly accepting that it enters conversation context and user-level client configuration in this first release.
- Provide minimal baseline guidance and clear extension boundaries for future team practices.
- Make setup idempotent and preserve unrelated Codex MCP and Skill configuration.

**Non-Goals:**

- A `plane-ai` npm package, globally installed CLI, or custom MCP client.
- OAuth, a secure-secret UI, or automatic Plane account and token creation.
- Installers for every AI platform in the first release.
- A comprehensive team workflow library or automatic Skill self-modification.
- Editing a team's separate Skill or project `AGENTS.md` during updates.

## Decisions

### Ship one Codex Skill with explicit scripts

Maintain the distributable source under `.codex/skills/plane` with `SKILL.md`, minimal references, and Windows/POSIX setup and doctor scripts. Users install it through a supported Skill installer, repository source, or future Skill marketplace; no custom package manager entry point is introduced.

The Skill may invoke its scripts when setup or diagnosis is needed. Scripts do not run automatically during Skill installation and make no changes until the user explicitly starts setup.

### Let the Agent own connection setup

The Skill asks only for missing workspace URL or token values. Once the user supplies them, the Agent detects its host environment, invokes the matching setup adapter itself, validates the connection, and reports the result. The user is never instructed to open a terminal, choose an operating-system launcher, configure an environment variable, or type a command.

The Windows and POSIX scripts remain implementation adapters that the Agent may invoke. Operating-system differences are internal to the Skill rather than user-facing connection paths.

### Persist the first-release credential in Codex MCP configuration

Setup registers one remote server named `plane` pointing to `<plane-origin>/mcp`. For Codex, it writes a static `Authorization: Bearer <token>` header to the user-level MCP entry, which is a supported remote MCP configuration form. This avoids relying on an environment variable inherited by a newly launched process and removes the need for a separate connector or application relaunch workflow.

This is an intentional first-release trade-off. The token is visible to the conversation and stored as plain text in the user's Codex configuration, so the Skill tells the user to use a dedicated, least-privilege, revocable token and never repeats the value in output. OAuth or a platform-owned secure-secret field should replace this storage mode later without changing the user-facing URL-first flow.

### Store only non-secret connection profile data

Setup parses a workspace URL into the Plane origin and workspace slug and stores only those non-secret values in a user-level Plane Skill profile. The Skill reads that profile at the start of a Plane workflow and passes the workspace slug explicitly to MCP tools.

The first release supports one default profile. Multiple Plane instances or named profiles are deferred until there is a demonstrated need.

### Validate before mutating client configuration

Before registering MCP, setup validates the normalized Plane origin, token identity, and workspace access against the deployed MCP/API contracts. Remote origins require HTTPS; HTTP is accepted only for loopback addresses used by local development or an SSH tunnel. Invalid URLs, tokens, certificates, or inaccessible workspaces leave existing Codex configuration unchanged.

Repeated setup is idempotent. If a `plane` MCP entry already matches, setup validates it without duplicating it. When the user explicitly supplies the current URL and token, that request authorizes replacing only a differing `plane` entry; unrelated entries remain unchanged.

### Keep the core Skill small and independently upgradeable

The base Skill contains triggering guidance, profile loading, `plane_status` verification, safe tool-selection rules, and error routing to doctor. It does not embed current team-specific lifecycle rules.

Future team practices live in a separately owned team Skill, while project-specific behavior remains in project `AGENTS.md`. Updating the core Plane Skill must not overwrite either layer.

## Risks / Trade-offs

- **A Skill cannot install itself** -> Publish clear installation instructions through the supported Skill installer or repository source; once installed, setup is self-contained.
- **The first-release token is present in conversation and local client configuration** -> Require an explicit user-supplied token, recommend a dedicated revocable credential, redact every output path, and document rotation as the recovery boundary.
- **Codex MCP configuration formats can evolve** -> Prefer the Codex MCP command surface and keep any structured config editing isolated and covered by fixtures.
- **Skill updates could overwrite local modifications** -> Treat the core Skill as vendor-owned and direct team customization to a separate Skill or project `AGENTS.md`.
- **A running task may not refresh its MCP tool catalog** -> Complete and verify configuration automatically, then report whether the host requires a new task; never ask the user to run setup commands.
- **Other Agent platforms use different MCP configuration stores** -> Keep the user-facing contract platform-neutral and the current implementation Codex-specific; add host adapters later without changing the connection request.
- **The Skill depends on a deployed MCP server** -> Declare the dependency on `add-plane-mcp-server` and make doctor distinguish missing server, invalid token, inaccessible workspace, and local configuration failures.

## Migration Plan

1. Implement and verify `add-plane-mcp-server` first.
2. Add the Plane Skill source and script fixtures without changing existing user configuration.
3. Install the Skill into an isolated Tester profile and have an Agent-managed setup run against the deployed MCP test endpoint.
4. Publish or document the supported Skill installation source after acceptance.

Rollback removes the installed core Skill and its `plane` MCP client entry. It does not revoke the Plane API token automatically; the user can revoke that token in Plane when access must be terminated.

## Open Questions

- Confirm the supported Codex Skill distribution channel for the first release: repository URL through the Skill installer or an internal marketplace entry.
- Define the migration path from static Codex headers to OAuth or a platform-owned secure-secret field before supporting broader distribution.
