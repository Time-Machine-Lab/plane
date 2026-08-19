---
name: plane
description: Use whenever a user wants to connect, set up, diagnose, read, or operate a Plane workspace through the Plane MCP server, including users who cannot configure tokens or terminal environments themselves.
---

# Plane

Use Plane through the configured `plane` MCP server. Do not construct Plane API requests or use browser automation when the MCP tools cover the request.

## Start a Plane workflow

1. Read the default profile described in [connection.md](references/connection.md).
2. When the user asks to connect or the profile/MCP entry is missing, perform the Agent-managed setup in [connection.md](references/connection.md). Ask only for the missing workspace URL or API token; never ask the user to run a command or configure their operating system.
3. If this task has not already established connection state, call `plane_status` with the profile's `workspace_slug`.
4. Confirm the returned user and workspace match the request before any mutation.
5. Use the smallest relevant Plane MCP tool. Keep `workspace_slug` explicit unless the connection already supplies the same default.
6. If status or a tool reports configuration, network, TLS, authentication, workspace, or discovery trouble, stop mutations and run the matching doctor entry point from [connection.md](references/connection.md).

## Agent-managed connection

- A user may explicitly provide a dedicated, revocable API token in conversation for this first-release flow. Briefly disclose that it becomes part of conversation context and is stored as a plain-text MCP header in the local Agent client configuration; do not repeat the value.
- Detect the Agent host and operating system yourself. For Codex, invoke the matching Windows or POSIX setup adapter and provide the token through masked stdin or a process-scoped environment facility, never in a command argument.
- Pass the explicit replacement option when the user supplied the current URL and token; that request authorizes replacing only the existing `plane` MCP entry. Preserve every unrelated client setting.
- Run doctor after setup. If the host cannot refresh MCP tools in the current task, tell the user to open a new task; do not require a terminal command or application relaunch.
- If a non-Codex host exposes a native remote MCP configuration API, register `<origin>/mcp` with a static Bearer authorization header through that API. If it exposes no writable MCP configuration surface, report that the host needs an adapter rather than shifting setup to the user.

## Credential safety

- Authentication comes from the user-level MCP connection, never from model-generated Plane tool arguments.
- Never repeat, print, summarize, or place a token in command arguments, Plane comments, work items, generated documentation, repository files, or the non-secret Skill profile.
- Treat the user-provided token as sensitive even though this flow accepts it in conversation. Redact setup, doctor, and error output, and recommend a dedicated least-privilege token that can be revoked independently.
- Store the token only in the current Agent client's user-level MCP authentication configuration. Do not additionally write it to shell profiles, project files, or environment configuration.

## Extension routing

Keep this core Skill limited to connection handling and safe Plane tool selection. Put organization-specific assignment, lifecycle, approval, deployment, and acceptance practices in a separately maintained team Skill. Put project-specific rules in the nearest applicable `AGENTS.md`.

Updating this Skill must not edit a team Skill, a project `AGENTS.md`, or user-owned workflow guidance.
