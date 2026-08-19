import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const testDir = dirname(fileURLToPath(import.meta.url));
const skillDir = resolve(testDir, "..");
const repoDir = resolve(skillDir, "../../..");
const psLibrary = join(skillDir, "scripts", "lib", "plane.ps1");
const shLibrary = join(skillDir, "scripts", "lib", "plane.sh");
const helper = join(skillDir, "scripts", "lib", "plane_helper.py");
const fixtures = join(testDir, "fixtures");

function powerShell(script, env = {}) {
  const result = spawnSync("pwsh", ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script], {
    cwd: repoDir,
    encoding: "utf8",
    env: { ...process.env, ...env },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout.trim();
}

function bash(script, env = {}) {
  const temporary = mkdtempSync(join(tmpdir(), "plane-bash-test-"));
  const scriptPath = join(temporary, "test.sh");
  try {
    writeFileSync(scriptPath, `#!/bin/sh\ncd ${quoteShell(posixPath(repoDir))}\n${script}\n`, "utf8");
    const result = spawnSync("bash", [posixPath(scriptPath)], {
      cwd: repoDir,
      encoding: "utf8",
      env: { ...process.env, ...env },
    });
    assert.equal(result.status, 0, result.stderr || result.stdout);
    return result.stdout.trim();
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}

function posixPath(path) {
  const normalized = path.replaceAll("\\", "/");
  const drivePath = /^([A-Za-z]):\/(.*)$/.exec(normalized);
  if (drivePath) {
    return `/mnt/${drivePath[1].toLowerCase()}/${drivePath[2]}`;
  }
  return normalized;
}

function quotePowerShell(value) {
  return `'${value.replaceAll("'", "''")}'`;
}

function quoteShell(value) {
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}

test("PowerShell and POSIX normalize the same workspace URL", () => {
  const psOutput = powerShell(`
    . ${quotePowerShell(psLibrary)}
    ConvertTo-PlaneConnectionProfile -WorkspaceUrl 'https://plane.example.com/acme/projects/123' | ConvertTo-Json -Compress
  `);
  assert.deepEqual(JSON.parse(psOutput), {
    origin: "https://plane.example.com",
    workspace_slug: "acme",
    mcp_url: "https://plane.example.com/mcp",
  });

  const shOutput = execFileSync(
    "python",
    [helper, "normalize-url", "--url", "https://plane.example.com/acme/projects/123"],
    {
      encoding: "utf8",
    }
  ).trim();
  assert.deepEqual(shOutput.split(/\r?\n/), ["https://plane.example.com", "acme", "https://plane.example.com/mcp"]);
});

test("PowerShell and POSIX reject insecure workspace URLs", () => {
  const psResult = spawnSync(
    "pwsh",
    [
      "-NoProfile",
      "-NonInteractive",
      "-Command",
      `
    . ${quotePowerShell(psLibrary)}
    ConvertTo-PlaneConnectionProfile -WorkspaceUrl 'http://plane.example.com/acme'
  `,
    ],
    { cwd: repoDir, encoding: "utf8" }
  );
  assert.notEqual(psResult.status, 0);
  assert.match(psResult.stderr, /must use HTTPS/);

  const pyResult = spawnSync("python", [helper, "normalize-url", "--url", "http://plane.example.com/acme"], {
    encoding: "utf8",
  });
  assert.notEqual(pyResult.status, 0);
  assert.match(pyResult.stderr, /must use HTTPS/);
});

test("PowerShell and POSIX redact credential values and headers", () => {
  const token = "plane-secret-token";
  const input = `failed ${token} Authorization: Bearer ${token} X-Api-Key: ${token}`;
  const psOutput = powerShell(`
    . ${quotePowerShell(psLibrary)}
    Protect-PlaneText -Text ${quotePowerShell(input)} -Token ${quotePowerShell(token)}
  `);
  assert.doesNotMatch(psOutput, /plane-secret-token/);
  assert.match(psOutput, /\[REDACTED\]/);

  const pyResult = spawnSync("python", [helper, "redact"], {
    encoding: "utf8",
    input,
    env: { ...process.env, PLANE_API_TOKEN: token },
  });
  assert.equal(pyResult.status, 0, pyResult.stderr);
  assert.doesNotMatch(pyResult.stdout, /plane-secret-token/);
  assert.match(pyResult.stdout, /\[REDACTED\]/);
});

test("unsafe environment tokens are rejected without disclosure", () => {
  const injectedToken = "secret-token\r\nX-Injected: yes";
  const psOutput = powerShell(
    `
    . ${quotePowerShell(psLibrary)}
    try {
      Get-PlaneApiToken -NonInteractive | Out-Null
      throw 'unsafe token was accepted'
    }
    catch {
      if ($_.Exception.Message -eq 'unsafe token was accepted') { throw }
      $_.Exception.Message
    }
  `,
    { PLANE_API_TOKEN: injectedToken }
  );
  assert.match(psOutput, /unsafe characters/);
  assert.doesNotMatch(psOutput, /secret-token|X-Injected/);

  const pyResult = spawnSync("python", [helper, "validate-token"], {
    encoding: "utf8",
    env: { ...process.env, PLANE_API_TOKEN: injectedToken },
  });
  assert.notEqual(pyResult.status, 0);
  assert.match(pyResult.stderr, /unsafe characters/);
  assert.doesNotMatch(pyResult.stderr, /secret-token|X-Injected/);

  const shOutput = bash(`
    PLANE_SCRIPT_ROOT=${quoteShell(posixPath(join(skillDir, "scripts")))}
    PLANE_API_TOKEN=${quoteShell('unsafe"token\\fragment')}
    export PLANE_SCRIPT_ROOT PLANE_API_TOKEN
    . ${quoteShell(posixPath(shLibrary))}
    error_file=$(mktemp)
    curl_marker=$(mktemp)
    rm -f "$curl_marker"
    if plane_get_token 2>"$error_file"; then exit 99; fi
    curl() { : >"$curl_marker"; }
    if plane_http_request get api_key https://plane.example.com/api /tmp/plane-token-body 2>>"$error_file"; then exit 98; fi
    if [ -e "$curl_marker" ]; then exit 97; fi
    cat "$error_file"
    rm -f "$error_file" /tmp/plane-token-body
  `);
  assert.match(shOutput, /unsafe characters/);
  assert.doesNotMatch(shOutput, /unsafe"token|fragment/);
});

test("MCP reachability probes use bounded POST requests", () => {
  const psSource = readFileSync(psLibrary, "utf8");
  assert.match(psSource, /HttpMethod\]::Post/);
  assert.match(psSource, /FromSeconds\(15\)/);
  assert.match(psSource, /-Method Post/);

  const shSource = readFileSync(shLibrary, "utf8");
  assert.match(shSource, /--connect-timeout 5 --max-time 15/);
  assert.match(shSource, /plane_http_request post bearer/);
  assert.match(shSource, /--request POST/);
});

test("PowerShell setup adds only the plane MCP entry and writes a non-secret profile", () => {
  const temporary = mkdtempSync(join(tmpdir(), "plane-skill-ps-add-"));
  const callLog = join(temporary, "calls.jsonl");
  try {
    const output = powerShell(
      `
      . ${quotePowerShell(psLibrary)}
      function Assert-PlaneCodexPreflight {}
      function Test-PlaneConnection { param($Profile, $Token) [pscustomobject]@{ User = 'tester' } }
      function Get-PlaneMcpConfig { return $null }
      function Invoke-PlaneCodex {
        param([string[]]$Arguments)
        Add-Content -LiteralPath ${quotePowerShell(callLog)} -Value ($Arguments | ConvertTo-Json -Compress)
        [pscustomobject]@{ ExitCode = 0; Output = '' }
      }
      Invoke-PlaneSetup -WorkspaceUrl 'https://plane.example.com/acme' -NonInteractive | ConvertTo-Json -Compress
    `,
      { CODEX_HOME: temporary, PLANE_API_TOKEN: "plane-secret-token" }
    );
    const result = JSON.parse(output);
    assert.equal(result.mcp_configuration, "added");
    const calls = readFileSync(callLog, "utf8");
    assert.match(
      calls,
      /"mcp","add","plane","--url","https:\/\/plane\.example\.com\/mcp","--bearer-token-env-var","PLANE_API_TOKEN"/
    );
    assert.doesNotMatch(calls, /plane-secret-token/);
    const profile = readFileSync(join(temporary, "plane", "profile.json"), "utf8");
    assert.deepEqual(JSON.parse(profile), { origin: "https://plane.example.com", workspace_slug: "acme" });
    assert.doesNotMatch(profile, /token/i);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});

test("PowerShell setup reuses a matching entry without mutating Codex configuration", () => {
  const temporary = mkdtempSync(join(tmpdir(), "plane-skill-ps-reuse-"));
  try {
    const output = powerShell(
      `
      . ${quotePowerShell(psLibrary)}
      function Assert-PlaneCodexPreflight {}
      function Test-PlaneConnection { param($Profile, $Token) [pscustomobject]@{ User = 'tester' } }
      function Get-PlaneMcpConfig { Get-Content -Raw ${quotePowerShell(join(fixtures, "mcp-match.json"))} | ConvertFrom-Json }
      function Invoke-PlaneCodex { throw 'configuration mutation was not expected' }
      Invoke-PlaneSetup -WorkspaceUrl 'https://plane.example.com/acme' -NonInteractive | ConvertTo-Json -Compress
    `,
      { CODEX_HOME: temporary, PLANE_API_TOKEN: "plane-secret-token" }
    );
    assert.equal(JSON.parse(output).mcp_configuration, "reused");
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});

test("PowerShell replacement is scoped to the plane entry", () => {
  const temporary = mkdtempSync(join(tmpdir(), "plane-skill-ps-replace-"));
  const callLog = join(temporary, "calls.txt");
  try {
    powerShell(
      `
      . ${quotePowerShell(psLibrary)}
      function Assert-PlaneCodexPreflight {}
      function Test-PlaneConnection { param($Profile, $Token) [pscustomobject]@{ User = 'tester' } }
      function Get-PlaneMcpConfig { Get-Content -Raw ${quotePowerShell(join(fixtures, "mcp-conflict.json"))} | ConvertFrom-Json }
      function Invoke-PlaneCodex {
        param([string[]]$Arguments)
        Add-Content -LiteralPath ${quotePowerShell(callLog)} -Value ($Arguments -join ' ')
        [pscustomobject]@{ ExitCode = 0; Output = '' }
      }
      Invoke-PlaneSetup -WorkspaceUrl 'https://plane.example.com/acme' -NonInteractive -Replace | Out-Null
    `,
      { CODEX_HOME: temporary, PLANE_API_TOKEN: "plane-secret-token" }
    );
    assert.deepEqual(readFileSync(callLog, "utf8").trim().split(/\r?\n/), [
      "mcp remove plane",
      "mcp add plane --url https://plane.example.com/mcp --bearer-token-env-var PLANE_API_TOKEN",
    ]);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});

test("POSIX setup adds the plane entry and is idempotent", () => {
  const temporary = mkdtempSync(join(tmpdir(), "plane-skill-sh-"));
  const callLog = join(temporary, "calls.txt");
  const common = `
    PLANE_SCRIPT_ROOT=${quoteShell(posixPath(join(skillDir, "scripts")))}
    export PLANE_SCRIPT_ROOT CODEX_HOME=${quoteShell(posixPath(temporary))} PLANE_API_TOKEN=plane-secret-token
    . ${quoteShell(posixPath(shLibrary))}
    plane_assert_preflight() { :; }
    plane_validate_connection() { printf '%s\\n' tester; }
  `;
  try {
    const first = bash(`${common}
      plane_codex() {
        printf '%s\\n' "$*" >>${quoteShell(posixPath(callLog))}
        if [ "$#" -eq 4 ]; then return 1; fi
        return 0
      }
      plane_setup_main --workspace-url https://plane.example.com/acme --non-interactive --json
    `);
    assert.equal(JSON.parse(first).mcp_configuration, "added");
    const firstCalls = readFileSync(callLog, "utf8");
    assert.match(
      firstCalls,
      /mcp add plane --url https:\/\/plane\.example\.com\/mcp --bearer-token-env-var PLANE_API_TOKEN/
    );
    assert.doesNotMatch(firstCalls, /plane-secret-token/);

    const matchingFixture = posixPath(join(fixtures, "mcp-match.json"));
    const second = bash(`${common}
      plane_codex() {
        cat ${quoteShell(matchingFixture)} || { printf '%s\\n' 'fixture read failed' >&2; return 2; }
      }
      plane_setup_main --workspace-url https://plane.example.com/acme --non-interactive --json
    `);
    assert.equal(JSON.parse(second).mcp_configuration, "reused");
    const profile = readFileSync(join(temporary, "plane", "profile.json"), "utf8");
    assert.doesNotMatch(profile, /token/i);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});

test("PowerShell doctor reports every diagnostic category and redacts probe detail", () => {
  const temporary = mkdtempSync(join(tmpdir(), "plane-skill-ps-doctor-"));
  try {
    execFileSync("python", [
      helper,
      "profile-write",
      "--path",
      join(temporary, "plane", "profile.json"),
      "--origin",
      "https://plane.example.com",
      "--slug",
      "acme",
    ]);
    const output = powerShell(
      `
      . ${quotePowerShell(psLibrary)}
      function Assert-PlaneCodexPreflight {}
      function Get-PlaneMcpConfig { Get-Content -Raw ${quotePowerShell(join(fixtures, "mcp-match.json"))} | ConvertFrom-Json }
      function Invoke-PlaneHttpRequest {
        param($Url, $Authentication, $Token, $Method)
        if ($Url -match 'users/me') { return [pscustomobject]@{ Status = 200; Body = '{"display_name":"Plane Test User"}' } }
        return [pscustomobject]@{ Status = 200; Body = '{}' }
      }
      function Invoke-PlaneStatusProbe { param($WorkspaceSlug) [pscustomobject]@{ Success = $true; Detail = 'ok plane-secret-token' } }
      Invoke-PlaneDoctor | ConvertTo-Json -Depth 8 -Compress
    `,
      { CODEX_HOME: temporary, PLANE_API_TOKEN: "plane-secret-token" }
    );
    const result = JSON.parse(output);
    assert.equal(result.status, "healthy");
    assert.deepEqual(
      new Set(result.checks.map((item) => item.category)),
      new Set([
        "local_configuration",
        "reachability_tls",
        "authentication",
        "workspace_authorization",
        "tool_availability",
      ])
    );
    assert.doesNotMatch(output, /plane-secret-token/);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});

test("POSIX doctor reports every diagnostic category", () => {
  const temporary = mkdtempSync(join(tmpdir(), "plane-skill-sh-doctor-"));
  try {
    execFileSync("python", [
      helper,
      "profile-write",
      "--path",
      join(temporary, "plane", "profile.json"),
      "--origin",
      "https://plane.example.com",
      "--slug",
      "acme",
    ]);
    const output = bash(`
      PLANE_SCRIPT_ROOT=${quoteShell(posixPath(join(skillDir, "scripts")))}
      export PLANE_SCRIPT_ROOT CODEX_HOME=${quoteShell(posixPath(temporary))} PLANE_API_TOKEN=plane-secret-token
      . ${quoteShell(posixPath(shLibrary))}
      plane_helper_real() { python3 ${quoteShell(posixPath(helper))} "$@"; }
      plane_helper() {
        if [ "$1" = user-label ]; then printf '%s\\n' 'Plane Test User'; return 0; fi
        plane_helper_real "$@"
      }
      plane_assert_preflight() { :; }
      plane_codex() { cat ${quoteShell(posixPath(join(fixtures, "mcp-match.json")))}; }
      plane_http_request() {
        case "$3" in
          *users/me*) cp ${quoteShell(posixPath(join(fixtures, "user.json")))} "$4" || return 1 ;;
          *) printf '%s\\n' '{}' >"$4" ;;
        esac
        printf '%s' 200
      }
      plane_status_probe() { cp ${quoteShell(posixPath(join(fixtures, "probe-success.json")))} "$4"; }
      plane_doctor_main --json
    `);
    const result = JSON.parse(output);
    assert.equal(result.status, "healthy");
    assert.deepEqual(
      new Set(result.checks.map((item) => item.category)),
      new Set([
        "local_configuration",
        "reachability_tls",
        "authentication",
        "workspace_authorization",
        "tool_availability",
      ])
    );
    assert.doesNotMatch(output, /plane-secret-token/);
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
});
