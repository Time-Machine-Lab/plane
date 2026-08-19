---
name: plane
description: Use when reading or operating a Plane workspace through the configured Plane MCP server, or when setting up or diagnosing that connection.
---

# Plane

Use Plane through the configured `plane` MCP server. Do not construct Plane API requests or use browser automation when the MCP tools cover the request.

## Start a Plane workflow

1. Read the non-secret default profile described in [connection.md](references/connection.md). Never read or request the API token in chat.
2. If this task has not already established connection state, call `plane_status` with the profile's `workspace_slug`.
3. Confirm the returned user and workspace match the request before any mutation.
4. Use the smallest relevant Plane MCP tool. Keep `workspace_slug` explicit unless the connection already supplies the same default.
5. If status or a tool reports configuration, network, TLS, authentication, workspace, or discovery trouble, stop mutations and run the matching doctor entry point from [connection.md](references/connection.md).

## Credential safety

- Authentication comes from the MCP connection's `PLANE_API_TOKEN` environment reference, never from model-generated tool arguments.
- Never ask for, print, copy, summarize, or store a token in chat, prompts, Plane comments, work items, documentation, repository files, or the Skill profile.
- When the token is absent, direct the user to the masked setup script. Do not accept a token pasted into the conversation.

## Extension routing

Keep this core Skill limited to connection handling and safe Plane tool selection. Put organization-specific assignment, lifecycle, approval, deployment, and acceptance practices in a separately maintained team Skill. Put project-specific rules in the nearest applicable `AGENTS.md`.

Updating this Skill must not edit a team Skill, a project `AGENTS.md`, or user-owned workflow guidance.
