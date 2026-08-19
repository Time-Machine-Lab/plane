## Why

An MCP server provides Plane tools, but users still need a simple way to connect Codex and a durable place to evolve team operating practices. A repository-managed Plane Skill can perform setup and diagnosis while keeping workflow guidance separate from the server's atomic tools.

## What Changes

- Add a Plane Skill that detects whether the Plane MCP server is configured and reachable from Codex.
- Bundle Agent-invoked setup and doctor adapters for Windows and POSIX environments; do not introduce a separate `plane-ai` npm installer.
- Let a user provide the Plane workspace URL and a dedicated, revocable API token directly to the Agent, then have the Agent derive the Plane origin and workspace slug, validate access, and register the remote `/mcp` server without asking the user to run commands.
- Persist the accepted token only in the current Agent client's user-level MCP authentication configuration so future tasks can connect without rebuilding a process environment. For Codex, use a static `Authorization` header in the user-level MCP entry.
- Keep secrets out of Skill content, repository files, generated documentation, Plane comments, command arguments, and setup output. Clearly disclose that this first-release flow places the token in conversation context and client configuration.
- Add lightweight baseline guidance that checks `plane_status`, selects MCP tools, and routes connection failures to the doctor workflow.
- Define extension boundaries for a stable Plane core Skill, separately maintained team workflow Skills, and project-specific `AGENTS.md` rules.
- Exclude OAuth, a platform-provided secure-secret input, a full team workflow library, automatic self-modification, non-Codex client adapters, and a standalone CLI product from this change.
- Depend on the MCP endpoint and tool contracts introduced by `add-plane-mcp-server`.

## Capabilities

### New Capabilities

- `plane-mcp-skill-setup`: Skill installation prerequisites, MCP configuration, connection validation, diagnosis, and reconnection behavior.
- `plane-mcp-skill-guidance`: Minimal Plane tool-use guidance and safe extension points for team and project operating rules.

### Modified Capabilities

None.

## Impact

- Adds a distributable Skill and setup/doctor scripts under the repository AI-tooling boundary; no product database or runtime migration is expected.
- Reads and updates Codex user-level MCP configuration, including one Plane authentication header, without overwriting unrelated servers and requires idempotent setup behavior.
- Requires Windows and POSIX adapter coverage, including offline Agent-managed connection checks, plus acceptance against a deployed Plane MCP endpoint where the core goal requires it.
- Applicable standards: `docs/spec/general-development.md`, `docs/spec/module-structure.md`, and the OpenSpec workflow requirements in `docs/spec/README.md`.
- The change is additive and can be rolled back by removing the Skill and its Plane MCP client entry; server-side MCP availability is unaffected.
