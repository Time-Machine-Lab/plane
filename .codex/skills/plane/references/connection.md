# Plane connection

## Dependency

Setup requires a deployed Plane instance that includes the accepted `add-plane-mcp-server` change and exposes Streamable HTTP at `<origin>/mcp`. The Skill does not install or deploy that service.

## Install the Skill

The distributable source is `.codex/skills/plane` in this repository. Install it from the repository path with Codex's `skill-installer`, or copy that directory unchanged to `$CODEX_HOME/skills/plane`. Restart Codex or open a new task after installation so the Skill is discovered.

The Codex adapter requires PowerShell 7 on Windows. The POSIX adapter requires a POSIX shell, Python 3, and curl.

## Agent-managed setup

The user supplies a workspace URL and a dedicated, revocable Plane API token. The Agent performs every remaining action:

1. Detect the current Agent host and operating system.
2. Normalize the workspace URL and derive `<origin>/mcp` plus the workspace slug.
3. Invoke the matching setup adapter itself, supplying the token through masked stdin or a process-scoped environment facility rather than a command argument.
4. Validate the identity, workspace access, and MCP endpoint before changing client configuration.
5. Register or replace only the `plane` MCP entry and run doctor.

Remote URLs must use HTTPS. HTTP is accepted only for loopback addresses (`localhost`, `127.0.0.1`, or `::1`) so local development and an SSH tunnel can be tested without sending the API token over an untrusted network. The first path segment is the workspace slug. For an origin-only URL, also pass `-WorkspaceSlug` or `--workspace-slug`.

For Codex, setup creates a user-level remote MCP entry with a static `Authorization: Bearer <token>` header. This is the deliberately chosen first-release trade-off: the token is present in conversation context and stored as plain text in local Codex configuration. Use a dedicated least-privilege token and revoke or rotate it if the conversation or client profile is exposed.

The non-secret profile at `$CODEX_HOME/plane/profile.json` (or `~/.codex/plane/profile.json`) still stores only `origin` and `workspace_slug`. Setup must never print the token, put it in a command argument, or write it to the repository, profile, generated documentation, Plane content, shell startup files, or long-lived environment configuration.

The Windows adapter is `scripts/setup.ps1`; the POSIX adapter is `scripts/setup.sh`. These are internal Skill resources for the Agent, not commands the user must run.

An identical URL and credential are reused. Supplying a current workspace URL and token authorizes the Agent to pass the explicit replacement option for the `plane` entry only; unrelated MCP and Codex configuration must remain unchanged.

## Diagnose

The Agent invokes `scripts/doctor.ps1` on Windows or `scripts/doctor.sh` on POSIX. Doctor reads the configured Bearer credential internally and checks the local profile, MCP configuration, reachability/TLS, API-token authentication, workspace access, and a read-only `plane_status` probe. Output is redacted.

If the current task does not refresh its MCP catalog after setup, the Agent tells the user to open a new task. No terminal command, environment configuration, or application relaunch is required.
