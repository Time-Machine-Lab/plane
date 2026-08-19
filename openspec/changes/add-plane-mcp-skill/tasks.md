## 1. Plane Core Skill

- [x] 1.1 Add the distributable `.codex/skills/plane` structure with complete `SKILL.md`, minimal references, and Windows/POSIX script entry points.
- [x] 1.2 Document the supported Skill installation source and the dependency on an available `add-plane-mcp-server` endpoint.

## 2. Setup Workflow

- [x] 2.1 Implement PowerShell and POSIX preflight checks for Codex MCP support and the existing `plane` server entry.
- [x] 2.2 Implement masked API-token or approved environment-value handling without writing the token to Skill or repository files.
- [x] 2.3 Parse and normalize the Plane workspace URL, validate identity and workspace access, and store only the non-secret default profile.
- [x] 2.4 Register the remote `/mcp` entry idempotently, preserve unrelated Codex configuration, and report restart or new-task requirements.

## 3. Doctor Workflow

- [x] 3.1 Implement PowerShell and POSIX doctor checks for local configuration, MCP reachability, authentication, workspace access, and tool availability.
- [x] 3.2 Ensure doctor output is actionable, machine-readable where useful, and redacts all credential values.

## 4. Skill Guidance And Extension Boundaries

- [x] 4.1 Add profile loading, `plane_status` verification, MCP-first tool selection, and failure routing to the core Skill.
- [x] 4.2 Add credential-safety rules and guidance for separate team Skills and project `AGENTS.md` without embedding organization-specific workflows.
- [x] 4.3 Verify core Skill updates do not overwrite separately maintained team or project guidance.

## 5. Verification

- [x] 5.1 Add focused setup, idempotency, configuration-preservation, URL parsing, redaction, and doctor fixtures for Windows and POSIX behavior.
- [x] 5.2 Confirm the independently deployed and accepted Plane MCP test endpoint from `add-plane-mcp-server`; do not duplicate the Plane deployment for this Skill-only change.
- [x] 5.3 Have an independent Tester install the Skill in an isolated Codex profile, execute the required setup and guidance scenarios, and record pass/fail evidence in `verification.md`.
