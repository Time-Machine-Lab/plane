## Context

The dependent `add-plane-mcp-server` change provides a remote `/mcp` endpoint and atomic Plane tools. Codex can already act as an MCP client, so the remaining user problem is installing a reusable Plane Skill, configuring that client safely, validating a Plane workspace connection, and leaving a stable place for future operating guidance.

The solution should remain a Skill rather than creating a separately published npm installer or CLI product. Setup logic can live in explicit Skill scripts, while `SKILL.md` stays focused on routing and tool-use guidance.

## Goals / Non-Goals

**Goals:**

- Make a standard Codex Skill installation the only new client-side product surface.
- Configure and diagnose a remote Plane MCP connection using a workspace URL and existing API token.
- Keep the token out of prompts, repository files, Skill content, and Plane work items.
- Provide minimal baseline guidance and clear extension boundaries for future team practices.
- Make setup idempotent and preserve unrelated Codex MCP and Skill configuration.

**Non-Goals:**

- A `plane-ai` npm package, globally installed CLI, or custom MCP client.
- OAuth or automatic Plane account and token creation.
- Installers for every AI platform in the first release.
- A comprehensive team workflow library or automatic Skill self-modification.
- Editing a team's separate Skill or project `AGENTS.md` during updates.

## Decisions

### Ship one Codex Skill with explicit scripts

Maintain the distributable source under `.codex/skills/plane` with `SKILL.md`, minimal references, and Windows/POSIX setup and doctor scripts. Users install it through a supported Skill installer, repository source, or future Skill marketplace; no custom package manager entry point is introduced.

The Skill may invoke its scripts when setup or diagnosis is needed. Scripts do not run automatically during Skill installation and make no changes until the user explicitly starts setup.

### Use Codex's built-in remote MCP client

Setup registers one remote server named `plane` pointing to `<plane-origin>/mcp`. It uses Codex's supported MCP configuration command where possible and otherwise performs a structured, narrowly scoped update that preserves unrelated configuration.

The connection references `PLANE_API_TOKEN` as the Bearer-token environment variable. Setup collects the token only through masked terminal input or validates an already configured environment value; the Skill never asks the user to paste it into chat. Because a running desktop or terminal process may not observe a newly persisted environment value, successful setup explicitly reports when Codex must be restarted or a new task opened.

### Store only non-secret connection profile data

Setup parses a workspace URL into the Plane origin and workspace slug and stores only those non-secret values in a user-level Plane Skill profile. The Skill reads that profile at the start of a Plane workflow and passes the workspace slug explicitly to MCP tools.

The first release supports one default profile. Multiple Plane instances or named profiles are deferred until there is a demonstrated need.

### Validate before mutating client configuration

Before registering MCP, setup validates the normalized HTTPS Plane origin, token identity, and workspace access against the deployed MCP/API contracts. Invalid URLs, tokens, certificates, or inaccessible workspaces leave existing Codex configuration unchanged.

Repeated setup is idempotent. If a `plane` MCP entry already matches, setup validates it without duplicating it. If it differs, the user receives a clear replacement decision and unrelated entries remain unchanged.

### Keep the core Skill small and independently upgradeable

The base Skill contains triggering guidance, profile loading, `plane_status` verification, safe tool-selection rules, and error routing to doctor. It does not embed current team-specific lifecycle rules.

Future team practices live in a separately owned team Skill, while project-specific behavior remains in project `AGENTS.md`. Updating the core Plane Skill must not overwrite either layer.

## Risks / Trade-offs

- **A Skill cannot install itself** -> Publish clear installation instructions through the supported Skill installer or repository source; once installed, setup is self-contained.
- **Environment-variable persistence differs across operating systems** -> Provide dedicated PowerShell and POSIX paths, validate the effective value, and report restart requirements explicitly.
- **Codex MCP configuration formats can evolve** -> Prefer the Codex MCP command surface and keep any structured config editing isolated and covered by fixtures.
- **Skill updates could overwrite local modifications** -> Treat the core Skill as vendor-owned and direct team customization to a separate Skill or project `AGENTS.md`.
- **A user may paste a token into chat despite instructions** -> Setup and error text consistently route token entry to masked scripts and warn against chat-based entry.
- **The Skill depends on a deployed MCP server** -> Declare the dependency on `add-plane-mcp-server` and make doctor distinguish missing server, invalid token, inaccessible workspace, and local configuration failures.

## Migration Plan

1. Implement and verify `add-plane-mcp-server` first.
2. Add the Plane Skill source and script fixtures without changing existing user configuration.
3. Install the Skill into an isolated Tester profile and run setup against the deployed MCP test endpoint.
4. Publish or document the supported Skill installation source after acceptance.

Rollback removes the installed core Skill and its `plane` MCP client entry. It does not revoke the Plane API token automatically; the user can revoke that token in Plane when access must be terminated.

## Open Questions

- Confirm the supported Codex Skill distribution channel for the first release: repository URL through the Skill installer or an internal marketplace entry.
- Confirm the operating-system-specific approved mechanism for persisting `PLANE_API_TOKEN`; if no safe common mechanism is approved, setup will require users to configure the environment value themselves and will only validate it.
