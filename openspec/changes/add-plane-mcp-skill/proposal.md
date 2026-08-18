## Why

An MCP server provides Plane tools, but users still need a simple way to connect Codex and a durable place to evolve team operating practices. A repository-managed Plane Skill can perform setup and diagnosis while keeping workflow guidance separate from the server's atomic tools.

## What Changes

- Add a Plane Skill that detects whether the Plane MCP server is configured and reachable from Codex.
- Bundle explicit setup and doctor scripts for Windows and POSIX environments; do not introduce a separate `plane-ai` npm installer.
- Accept a Plane workspace URL and API token during setup, derive the Plane origin and workspace slug, validate access, and register the remote `/mcp` server with Codex.
- Keep secrets out of Skill content, repository files, prompts, and Plane comments; reference supported client-side secret or environment configuration instead.
- Add lightweight baseline guidance that checks `plane_status`, selects MCP tools, and routes connection failures to the doctor workflow.
- Define extension boundaries for a stable Plane core Skill, separately maintained team workflow Skills, and project-specific `AGENTS.md` rules.
- Exclude a full team workflow library, automatic self-modification, non-Codex client installers, and a standalone CLI product from this change.
- Depend on the MCP endpoint and tool contracts introduced by `add-plane-mcp-server`.

## Capabilities

### New Capabilities

- `plane-mcp-skill-setup`: Skill installation prerequisites, MCP configuration, connection validation, diagnosis, and reconnection behavior.
- `plane-mcp-skill-guidance`: Minimal Plane tool-use guidance and safe extension points for team and project operating rules.

### Modified Capabilities

None.

## Impact

- Adds a distributable Skill and setup/doctor scripts under the repository AI-tooling boundary; no product database or runtime migration is expected.
- Reads and updates Codex MCP configuration without overwriting unrelated servers and requires idempotent setup behavior.
- Requires Windows and POSIX script coverage plus acceptance against a deployed Plane MCP endpoint.
- Applicable standards: `docs/spec/general-development.md`, `docs/spec/module-structure.md`, and the OpenSpec workflow requirements in `docs/spec/README.md`.
- The change is additive and can be rolled back by removing the Skill and its Plane MCP client entry; server-side MCP availability is unaffected.
