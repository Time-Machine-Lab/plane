[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet("web", "admin", "space")]
    [string[]]$Apps = @("web"),

    [string]$ConfigPath,

    [switch]$SkipChecks,
    [switch]$SkipInstall,
    [switch]$NoBrowser,
    [switch]$Wait,

    [ValidateRange(10, 1800)]
    [int]$TimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $PSScriptRoot "../../.secrets/plane-test.env"
}

function Read-DotEnv {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Private test configuration was not found: $Path"
    }

    $values = @{}
    $lineNumber = 0
    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding utf8) {
        $lineNumber++
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $separator = $line.IndexOf("=")
        if ($separator -lt 1) { throw "Invalid configuration line $lineNumber in $Path" }
        $key = $line.Substring(0, $separator).Trim()
        $value = $line.Substring($separator + 1).Trim()
        if ($value.Length -ge 2 -and (($value[0] -eq '"' -and $value[-1] -eq '"') -or ($value[0] -eq "'" -and $value[-1] -eq "'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$key] = $value
    }
    return $values
}

function Test-HttpReady {
    param([Parameter(Mandatory)][string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -Method Head -TimeoutSec 5 -UseBasicParsing
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][System.Diagnostics.Process]$Process,
        [Parameter(Mandatory)][int]$Timeout
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($Timeout)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) {
            throw "Local app process exited before becoming ready: $Url (exit $($Process.ExitCode))"
        }
        if (Test-HttpReady -Url $Url) { return }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for local app: $Url"
}

function Get-PythonCommand {
    foreach ($candidate in @("python", "py")) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) { return $candidate }
    }
    throw "Python 3.12 or newer is required for the SSH tunnel"
}

function Get-TransportPython {
    param([Parameter(Mandatory)][string]$SystemPython)

    & $SystemPython -c "import paramiko" 2>$null
    if ($LASTEXITCODE -eq 0) { return $SystemPython }

    $toolRoot = Join-Path $env:LOCALAPPDATA "PlaneTestTools"
    $venvRoot = Join-Path $toolRoot "venv"
    $venvPython = Join-Path $venvRoot "Scripts/python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null
        & $SystemPython -m venv $venvRoot
        if ($LASTEXITCODE -ne 0) { throw "Could not create private transport virtual environment" }
    }
    & $venvPython -m pip install --disable-pip-version-check --quiet "paramiko==4.0.0"
    if ($LASTEXITCODE -ne 0) { throw "Could not install Paramiko in the private tool environment" }
    return $venvPython
}

function Assert-PrivateConfig {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$Path
    )

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $repoPrefix = $RepoRoot.TrimEnd("\") + "\"
    if (-not $resolved.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Private configuration must be inside the repository's ignored .secrets directory"
    }
    $relative = $resolved.Substring($repoPrefix.Length).Replace("\", "/")
    & git -C $RepoRoot check-ignore --quiet -- $relative
    if ($LASTEXITCODE -ne 0) { throw "Private configuration is not ignored by Git: $relative" }
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & git -C $RepoRoot ls-files --error-unmatch -- $relative 2>$null | Out-Null
        $trackedExitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previousErrorPreference }
    if ($trackedExitCode -eq 0) { throw "Private configuration is tracked by Git: $relative" }
    return $resolved
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is not available on PATH" }
$ConfigPath = Assert-PrivateConfig -RepoRoot $repoRoot -Path $ConfigPath
$config = Read-DotEnv -Path $ConfigPath
$portKey = if ($config.ContainsKey("PLANE_TEST_HTTP_PORT")) { "PLANE_TEST_HTTP_PORT" } else { "PLANE_TEST_PUBLIC_PORT" }
$remotePort = 0
if (-not $config.ContainsKey($portKey) -or -not [int]::TryParse($config[$portKey], [ref]$remotePort) -or $remotePort -lt 1 -or $remotePort -gt 65535) {
    throw "PLANE_TEST_HTTP_PORT (or PLANE_TEST_PUBLIC_PORT) must be between 1 and 65535"
}
if (-not $config.ContainsKey("PLANE_TEST_SSH_HOST_KEY_SHA256") -or $config["PLANE_TEST_SSH_HOST_KEY_SHA256"] -notmatch '^SHA256:[A-Za-z0-9+/]{43}$') {
    throw "PLANE_TEST_SSH_HOST_KEY_SHA256 must contain the verified OpenSSH SHA256 fingerprint"
}
if (-not $config.ContainsKey("PLANE_TEST_BASE_URL") -or -not $config["PLANE_TEST_BASE_URL"]) {
    if (-not $config.ContainsKey("PLANE_TEST_HOST") -or -not $config.ContainsKey($portKey)) {
        throw "PLANE_TEST_BASE_URL, or PLANE_TEST_HOST plus PLANE_TEST_HTTP_PORT, is required in $ConfigPath"
    }
    $config["PLANE_TEST_BASE_URL"] = "http://$($config['PLANE_TEST_HOST']):$($config[$portKey])"
}
$remoteBaseUrl = $config["PLANE_TEST_BASE_URL"].TrimEnd("/")
if (-not [Uri]::IsWellFormedUriString($remoteBaseUrl, [UriKind]::Absolute)) {
    throw "PLANE_TEST_BASE_URL must be an absolute URL"
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js is not available on PATH" }
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) { throw "pnpm is not available on PATH" }

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "node_modules") -PathType Container)) {
    if ($SkipInstall) { throw "node_modules is missing and -SkipInstall was supplied" }
    if ($PSCmdlet.ShouldProcess($repoRoot, "Install locked pnpm dependencies")) {
        Push-Location $repoRoot
        try {
            & pnpm install --frozen-lockfile
            if ($LASTEXITCODE -ne 0) { throw "pnpm install failed with exit code $LASTEXITCODE" }
        }
        finally { Pop-Location }
    }
}

if (-not $SkipChecks) {
    foreach ($app in $Apps) {
        if ($PSCmdlet.ShouldProcess($app, "Run TypeScript check")) {
            Push-Location $repoRoot
            try {
                & pnpm turbo run check:types --filter=$app
                if ($LASTEXITCODE -ne 0) { throw "Type check failed for $app with exit code $LASTEXITCODE" }
            }
            finally { Pop-Location }
        }
    }
}

$runtimeRoot = Join-Path ([System.IO.Path]::GetTempPath()) "plane-local-apps"
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$started = @()
$localApiUrl = "http://localhost:8000"

if (-not (Test-HttpReady -Url "$localApiUrl/")) {
    if ($PSCmdlet.ShouldProcess("localhost:8000", "Start SSH tunnel to the remote Plane proxy")) {
        $systemPython = Get-PythonCommand
        $transportPython = Get-TransportPython -SystemPython $systemPython
        $helper = Join-Path $PSScriptRoot "test_env_transport.py"
        $tunnelStdout = Join-Path $runtimeRoot "ssh-tunnel.stdout.log"
        $tunnelStderr = Join-Path $runtimeRoot "ssh-tunnel.stderr.log"
        $tunnelProcess = Start-Process -FilePath $transportPython -ArgumentList @(
            $helper, "tunnel", "--config", $ConfigPath, "--bind-host", "127.0.0.1", "--local-port", "8000"
        ) -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $tunnelStdout `
            -RedirectStandardError $tunnelStderr -PassThru
        $started += $tunnelProcess
        try {
            Wait-HttpReady -Url "$localApiUrl/" -Process $tunnelProcess -Timeout $TimeoutSeconds
        }
        catch {
            Write-Error "$_`nTunnel logs: $tunnelStdout and $tunnelStderr"
            throw
        }
        Write-Host "Remote Plane API tunnel is ready: $localApiUrl"
    }
    else {
        Write-Host "Would start an SSH tunnel at $localApiUrl"
    }
}
else {
    Write-Host "A service is already reachable at $localApiUrl; reusing it as the Plane API endpoint."
}

$env:VITE_API_BASE_URL = $localApiUrl
$env:VITE_WEB_BASE_URL = "http://localhost:3000"
$env:VITE_ADMIN_BASE_URL = "http://localhost:3001"
$env:VITE_ADMIN_BASE_PATH = "/god-mode"
$env:VITE_SPACE_BASE_URL = "http://localhost:3002"
$env:VITE_SPACE_BASE_PATH = "/spaces"
$env:VITE_LIVE_BASE_URL = $localApiUrl
$env:VITE_LIVE_BASE_PATH = "/live"

$appSettings = @{
    web = @{ Port = 3000; Url = "http://localhost:3000/" }
    admin = @{ Port = 3001; Url = "http://localhost:3001/god-mode/" }
    space = @{ Port = 3002; Url = "http://localhost:3002/spaces/" }
}
foreach ($app in $Apps) {
    $settings = $appSettings[$app]
    $url = $settings.Url
    if (Test-HttpReady -Url $url) {
        Write-Host "$app is already reachable at $url"
        if (-not $NoBrowser -and $PSCmdlet.ShouldProcess($url, "Open browser")) { Start-Process $url }
        continue
    }

    if (-not $PSCmdlet.ShouldProcess($app, "Start local development server on port $($settings.Port)")) {
        Write-Host "Would start $app at $url with API $localApiUrl"
        continue
    }

    $stdoutPath = Join-Path $runtimeRoot "$app.stdout.log"
    $stderrPath = Join-Path $runtimeRoot "$app.stderr.log"
    $command = "pnpm --filter=$app dev"
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList @("/d", "/s", "/c", $command) `
        -WorkingDirectory $repoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath -PassThru
    $started += $process
    try {
        Wait-HttpReady -Url $url -Process $process -Timeout $TimeoutSeconds
    }
    catch {
        Write-Error "$_`nLogs: $stdoutPath and $stderrPath"
        throw
    }
    Write-Host "$app is ready: $url"
    Write-Host "Logs: $stdoutPath and $stderrPath"
    if (-not $NoBrowser) { Start-Process $url }
}

if ($Wait -and $started.Count -gt 0) {
    Write-Host "Press Ctrl+C to stop the local app processes."
    try {
        while (($started | Where-Object { -not $_.HasExited }).Count -gt 0) { Start-Sleep -Seconds 1 }
    }
    finally {
        foreach ($process in $started) {
            if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
        }
    }
}
