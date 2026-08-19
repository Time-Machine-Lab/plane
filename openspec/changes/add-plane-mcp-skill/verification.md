# Verification

- Tester: accept_plane_skill_with_token
- Deployment: current accepted `add-plane-mcp-server` test deployment
- Verdict: pass

| Journey                                            | Result | Evidence                                                                                                                                                                                                                                                                                                              |
| -------------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Isolated Skill installation                        | pass   | The current Skill was copied unchanged into fresh isolated Codex homes. Installation created no Plane profile or MCP entry.                                                                                                                                                                                           |
| Valid and idempotent setup                         | pass   | A temporary ordinary API token belonging to the persistent Member test identity completed identity, workspace, and MCP validation. Consecutive identical setup calls reported `added` then `reused`; the second call left the Codex configuration hash unchanged.                                                     |
| Secret-safe profile and configuration preservation | pass   | The stored profile contained only `origin` and `workspace_slug`, neither profile nor Codex configuration contained the token, and a pre-existing unrelated MCP entry remained available after both setup calls.                                                                                                       |
| Doctor connection diagnosis                        | pass   | The final doctor completed in bounded time with overall status `healthy`. Codex capability, profile, MCP configuration, endpoint reachability, authentication, workspace authorization, and `tools:tool_availability` all reported `pass`; the deterministic `plane_status` probe confirmed the configured workspace. |
| MCP connection and fixed project read              | pass   | An official MCP SDK client called `plane_status`, confirmed the authenticated identity and workspace, listed projects, and located the fixed test project. The final read-only retest passed after the doctor fix.                                                                                                    |
| MCP work-item and comment workflow                 | pass   | Through Plane MCP tools, the Tester created one `[AI-TEST]` work item, read it back, updated its title and description, read back the updated result, added one `[AI-TEST]` comment, and listed comments to confirm it. The item remains because the initial MCP catalog intentionally has no delete tool.            |
| Missing-token mutation protection                  | pass   | With the token removed from the process environment, `plane_status` returned the stable authentication category and the client performed no business mutation.                                                                                                                                                        |

## Failures

- None.

## Environment notes

- Password sign-in returned HTTP 500 during acceptance. With implementation-owner approval, a constrained remote Django ORM operation was used only to create and revoke temporary Member API tokens; all Plane business reads and writes used MCP tools.
- Every temporary acceptance token was revoked, and final scoped checks found zero remaining acceptance tokens. The isolated Codex homes, temporary scripts, and Tester-owned tunnels were removed after each verification run.

## Residual risks

- The `[AI-TEST]` work item and comment created during acceptance remain in the persistent test project because the initial MCP tool catalog intentionally exposes no delete capability.

## Guided connection amendment

- Tester: `tester_guided_connection`
- Verification method: static and offline local verification; no deployment or live Plane credential was required
- Verdict: pass after focused rework

| Goal                          | Result | Evidence                                                                                                                                                                                                                  |
| ----------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Operating-system entry points | pass   | Windows includes `connect.cmd` and `connect.ps1`; macOS/POSIX includes `connect.command` and `connect.sh`, with both POSIX launchers recorded as executable mode `100755` and LF line endings.                            |
| Derived token-management link | pass   | Both implementations derive `<origin>/settings/profile/api-tokens/` from the normalized workspace origin without adding the token to the URL.                                                                             |
| Masked setup reuse            | pass   | Guided flows delegate to the existing setup functions, preserving masked token input, validation-before-configuration, and idempotent MCP registration.                                                                   |
| Process-scoped relaunch       | pass   | Windows and POSIX child-process checks confirmed that a launched Codex process inherits `PLANE_API_TOKEN` without writing it to the profile or long-lived environment configuration.                                      |
| Relaunch fallback             | pass   | Missing executables display a visible retry/select/quit prompt. Immediate POSIX child failure is detected and returns to the same connector process, preserving the process-scoped token until the user explicitly quits. |
| Focused regression            | pass   | `node --test .codex/skills/plane/tests/plane-skill.test.mjs` completed 21 tests with 21 passes; PowerShell/POSIX syntax, `git diff --check`, and strict OpenSpec validation also passed.                                  |

### Rework resolved during independent verification

- Corrected the POSIX launcher Git modes from non-executable to `100755`.
- Replaced the non-actionable relaunch warning with interactive executable discovery and retry.
- Removed stderr suppression that hid the POSIX selection prompt.
- Added immediate POSIX child-exit detection so failed launches do not report success.

## Agent-managed connection revision

- Tester: `tester_agent_managed_connection`
- Verification method: isolated local Codex profile plus focused offline Windows/POSIX checks; no real token or external Plane instance
- Verdict: pass

| Goal                           | Result | Evidence                                                                                                                                                                         |
| ------------------------------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent-owned setup              | pass   | Skill guidance accepts a workspace URL and dedicated token, requires the Agent to perform setup, and includes no user-facing operating-system launcher or terminal-command step. |
| Codex credential configuration | pass   | In an isolated user profile, setup replaced the `plane` entry, stored a static Bearer header in user-level `config.toml`, and reused the identical entry on the second run.      |
| Configuration containment      | pass   | An unrelated MCP entry remained unchanged, the Plane profile contained no credential, and no repository or generated output contained the token.                                 |
| Diagnosis and redaction        | pass   | Doctor loaded the saved header credential, returned `healthy`, and emitted neither the token nor a complete authorization header.                                                |
| Focused regression             | pass   | The 18-case offline suite, PowerShell/POSIX/Python syntax checks, Skill validation, strict OpenSpec validation, and `git diff --check` passed.                                   |

### Residual risks

- The real Codex user-configuration path was exercised on Windows. POSIX behavior was verified through the shared offline suite rather than a native macOS/Linux Codex installation.
- Plain-text token storage in the Agent client's user configuration is intentional for this first release and is disclosed in the Skill; use a dedicated, revocable token.
