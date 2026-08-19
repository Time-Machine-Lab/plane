# Plane connection

## Dependency

Setup requires a deployed Plane instance that includes the accepted `add-plane-mcp-server` change and exposes Streamable HTTP at `<origin>/mcp`. The Skill does not install or deploy that service.

## Install the Skill

The distributable source is `.codex/skills/plane` in this repository. Install it from the repository path with Codex's `skill-installer`, or copy that directory unchanged to `$CODEX_HOME/skills/plane`. Restart Codex or open a new task after installation so the Skill is discovered.

Windows setup requires PowerShell 7. POSIX setup requires a POSIX shell, Python 3, and curl.

Installing the Skill does not change MCP configuration. Run setup explicitly:

```powershell
./scripts/setup.ps1 -WorkspaceUrl "https://plane.example.com/my-workspace"
```

```sh
./scripts/setup.sh --workspace-url "https://plane.example.com/my-workspace"
```

The URL must use HTTPS. Its first path segment is the workspace slug. For an origin-only URL, also pass `-WorkspaceSlug` or `--workspace-slug`.

Setup uses an existing `PLANE_API_TOKEN` environment value or reads it with a masked terminal prompt. It never persists the token. If the prompt is used, configure the same variable through your approved secret manager or process-launch environment before starting Codex. Do not put the token on a command line, in chat, in a shell profile, or in a repository file.

Setup stores only `origin` and `workspace_slug` at `$CODEX_HOME/plane/profile.json` (or the corresponding default `~/.codex/plane/profile.json`). It registers `plane` through:

```text
codex mcp add plane --url <origin>/mcp --bearer-token-env-var PLANE_API_TOKEN
```

An identical entry is reused. A different entry is not replaced without confirmation; non-interactive callers must pass the explicit replacement flag.

## Diagnose

Run doctor from a terminal that already has `PLANE_API_TOKEN`:

```powershell
./scripts/doctor.ps1
./scripts/doctor.ps1 -Json
```

```sh
./scripts/doctor.sh
./scripts/doctor.sh --json
```

Doctor checks local profile and MCP configuration, reachability/TLS, API-token authentication, workspace access, and a read-only `plane_status` probe through Codex's built-in MCP client. Use the JSON form for automation. Output is redacted.

After setup or an environment change, open a new Codex task. Restart the Codex desktop app if it was launched before `PLANE_API_TOKEN` became available to its environment.
