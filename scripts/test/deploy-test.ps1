<#
.SYNOPSIS
Deploys the current Plane change to the persistent test environment.

.PARAMETER Services
Runtime services to deploy. The default, auto, derives services from changes relative to BaseRef.

.PARAMETER BaseRef
Git ref used to find committed changes for automatic service selection. Defaults to origin/preview.

.PARAMETER SkipChecks
Skips the lightweight package whitespace preflight. CI remains the owner of lint, types, builds, and tests.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet("auto", "all", "web", "admin", "space", "api", "worker", "beat-worker", "live", "mcp", "proxy", "fixtures")]
    [string[]]$Services = @("auto"),

    [string]$ConfigPath,

    [ValidateNotNullOrEmpty()]
    [string]$BaseRef = "origin/preview",

    [switch]$SkipChecks,
    [switch]$KeepPackage,

    [ValidateRange(60, 7200)]
    [int]$TimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $ConfigPath) {
    $ConfigPath = Join-Path $PSScriptRoot "../../.secrets/plane-test.env"
}

function Get-PythonCommand {
    foreach ($candidate in @("python", "py")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) { return $candidate }
    }
    throw "Python 3.12 or newer is required"
}

function Test-PlaneReady {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/instances/" -Method Get -TimeoutSec 5 -UseBasicParsing
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Ensure-TestTunnel {
    param(
        [Parameter(Mandatory)][string]$Python,
        [Parameter(Mandatory)][string]$Helper,
        [Parameter(Mandatory)][string]$Config,
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$RuntimeRoot
    )

    if (Test-PlaneReady) { return }

    $logsRoot = Join-Path $RuntimeRoot "logs"
    $sshRoot = Join-Path $RuntimeRoot "ssh"
    New-Item -ItemType Directory -Path $logsRoot, $sshRoot -Force | Out-Null
    $stdoutPath = Join-Path $logsRoot "ssh-tunnel.stdout.log"
    $stderrPath = Join-Path $logsRoot "ssh-tunnel.stderr.log"
    $pidPath = Join-Path $sshRoot "tunnel.pid"
    $process = Start-Process -FilePath $Python -ArgumentList @(
        $Helper, "tunnel", "--config", $Config, "--bind-host", "127.0.0.1", "--local-port", "8000",
        "--runtime-root", $RuntimeRoot
    ) -WorkingDirectory $RepoRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath -PassThru
    Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ascii

    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($process.HasExited) {
            throw "SSH tunnel exited before Plane became reachable. See $stdoutPath and $stderrPath"
        }
        if (Test-PlaneReady) { return }
        Start-Sleep -Seconds 2
    }
    throw "Timed out waiting for Plane through the SSH tunnel. See $stdoutPath and $stderrPath"
}

function Get-ComparisonBase {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$BaseRef
    )

    $resolvedBase = & git -C $RepoRoot rev-parse --verify --quiet "$BaseRef^{commit}"
    if ($LASTEXITCODE -ne 0 -or -not $resolvedBase) {
        throw "Could not resolve deployment comparison base '$BaseRef'. Fetch it or specify -BaseRef."
    }
    $mergeBase = & git -C $RepoRoot merge-base HEAD $resolvedBase
    if ($LASTEXITCODE -ne 0 -or -not $mergeBase) {
        throw "Could not find a merge base between HEAD and '$BaseRef'."
    }
    return ([string]$mergeBase).Trim()
}

function Get-ChangedPaths {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$ComparisonBase
    )

    $committed = & git -C $RepoRoot diff --name-only "$ComparisonBase..HEAD"
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect committed changes" }
    $workingTree = & git -C $RepoRoot diff --name-only HEAD
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect working tree changes" }
    $untracked = & git -C $RepoRoot ls-files --others --exclude-standard
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect untracked changes" }
    $paths = @($committed) + @($workingTree) + @($untracked)
    return $paths | Where-Object { $_ } | Sort-Object -Unique
}

function Resolve-AutoServices {
    param([Parameter(Mandatory)][string[]]$Paths)

    $selected = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $hasSharedPackageChange = $false
    foreach ($path in $Paths) {
        $normalized = $path.Replace("\", "/")
        switch -Regex ($normalized) {
            '^apps/api/' { [void]$selected.Add("api"); continue }
            '^apps/web/' { [void]$selected.Add("web"); continue }
            '^apps/admin/' { [void]$selected.Add("admin"); continue }
            '^apps/space/' { [void]$selected.Add("space"); continue }
            '^apps/live/' { [void]$selected.Add("live"); continue }
            '^apps/mcp/' { [void]$selected.Add("mcp"); continue }
            '^apps/proxy/' { [void]$selected.Add("proxy"); continue }
            '^scripts/test/' { [void]$selected.Add("fixtures"); continue }
            '^packages/codemods/' { continue }
            '^packages/' { $hasSharedPackageChange = $true; continue }
            '^(docker-compose\.yml|pnpm-lock\.yaml|pnpm-workspace\.yaml|package\.json|turbo\.json)$' {
                [void]$selected.Add("all")
                continue
            }
        }
    }
    if ($selected.Contains("all")) { return @("all") }
    if ($hasSharedPackageChange) {
        throw "Automatic service selection cannot safely infer consumers of shared package changes. Specify only the affected runtime services with -Services."
    }
    if ($selected.Count -eq 0) {
        throw "Automatic service selection found no runtime changes. Specify -Services explicitly if deployment is intentional."
    }
    return @($selected | Sort-Object)
}

function Invoke-PackagePreflight {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [AllowNull()][string]$ComparisonBase
    )

    Push-Location $RepoRoot
    try {
        if ($ComparisonBase) {
            & git diff --check "$ComparisonBase..HEAD"
            if ($LASTEXITCODE -ne 0) { throw "Committed change whitespace check failed" }
        }
        & git diff --check HEAD
        if ($LASTEXITCODE -ne 0) { throw "Working tree whitespace check failed" }
    }
    finally { Pop-Location }
}

function Get-TransportPython {
    param(
        [Parameter(Mandatory)][string]$SystemPython,
        [Parameter(Mandatory)][string]$RuntimeRoot
    )

    $toolRoot = Join-Path $RuntimeRoot "tools"
    $venvRoot = Join-Path $toolRoot "venv"
    $venvPython = Join-Path $venvRoot "Scripts/python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null
        & $SystemPython -m venv $venvRoot
        if ($LASTEXITCODE -ne 0) { throw "Could not create private transport virtual environment" }
    }
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $venvPython -c "import paramiko; raise SystemExit(0 if paramiko.__version__ == '4.0.0' else 1)" 2>$null
        $paramikoProbeExitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $previousErrorPreference }
    if ($paramikoProbeExitCode -ne 0) {
        & $venvPython -m pip install --disable-pip-version-check --quiet "paramiko==4.0.0"
        if ($LASTEXITCODE -ne 0) { throw "Could not install Paramiko in the private tool environment" }
    }
    return $venvPython
}

function Assert-PrivateConfig {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$Path
    )

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $secretsPrefix = (Join-Path $RepoRoot ".secrets").TrimEnd("\") + "\"
    if (-not $resolved.StartsWith($secretsPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Private configuration must be inside the repository's ignored .secrets directory"
    }
    $repoPrefix = $RepoRoot.TrimEnd("\") + "\"
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
$runtimeRoot = Join-Path $repoRoot ".runtime/test"
$helper = Join-Path $PSScriptRoot "test_env_transport.py"
$remoteScript = Join-Path $PSScriptRoot "remote-deploy.sh"
$systemPython = Get-PythonCommand

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "Private test configuration was not found: $ConfigPath"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is not available on PATH" }
$ConfigPath = Assert-PrivateConfig -RepoRoot $repoRoot -Path $ConfigPath
& $systemPython $helper validate --config $ConfigPath
if ($LASTEXITCODE -ne 0) { throw "Private test configuration validation failed" }

$selectedServices = @($Services | Select-Object -Unique)
$comparisonBase = $null
if ($selectedServices -contains "auto") {
    if ($selectedServices.Count -ne 1) { throw "Use -Services auto by itself" }
    $comparisonBase = Get-ComparisonBase -RepoRoot $repoRoot -BaseRef $BaseRef
    $selectedServices = Resolve-AutoServices -Paths (Get-ChangedPaths -RepoRoot $repoRoot -ComparisonBase $comparisonBase)
}
if ($selectedServices -contains "all" -and $selectedServices.Count -ne 1) { throw "Use -Services all by itself" }

$commit = (& git -C $repoRoot rev-parse --short=12 HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not determine the current commit" }
$release = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $commit
$releaseRoot = Join-Path $runtimeRoot "packages/$release"
$archive = Join-Path $releaseRoot "$release.tar.gz"
$manifest = Join-Path $releaseRoot "$release.manifest.json"
$serviceCsv = $selectedServices -join ","

Write-Host "Selected services: $serviceCsv"
Write-Host "Release: $release"

if (-not $SkipChecks -and $PSCmdlet.ShouldProcess($serviceCsv, "Run pre-deployment checks")) {
    Invoke-PackagePreflight -RepoRoot $repoRoot -ComparisonBase $comparisonBase
}

if ($WhatIfPreference) {
    & $systemPython $helper package --repo $repoRoot --output $archive --manifest $manifest --dry-run
    if ($LASTEXITCODE -ne 0) { throw "Package dry run failed with exit code $LASTEXITCODE" }
    Write-Host "Would deploy to the dedicated Plane test root using the private configuration at $ConfigPath"
    exit 0
}

& $systemPython $helper prepare --config $ConfigPath
if ($LASTEXITCODE -ne 0) { throw "Could not prepare stable private test identities" }
& $systemPython $helper validate --config $ConfigPath
if ($LASTEXITCODE -ne 0) { throw "Prepared private test configuration validation failed" }

New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
try {
    & $systemPython $helper package --repo $repoRoot --output $archive --manifest $manifest
    if ($LASTEXITCODE -ne 0) { throw "Packaging failed with exit code $LASTEXITCODE" }

    $transportPython = Get-TransportPython -SystemPython $systemPython -RuntimeRoot $runtimeRoot
    if ($PSCmdlet.ShouldProcess($serviceCsv, "Upload and deploy release $release to the Plane test environment")) {
        & $transportPython $helper deploy --config $ConfigPath --archive $archive --remote-script $remoteScript `
            --release $release --services $serviceCsv --runtime-root $runtimeRoot --timeout $TimeoutSeconds
        if ($LASTEXITCODE -ne 0) { throw "Deployment failed with exit code $LASTEXITCODE" }
        Ensure-TestTunnel -Python $transportPython -Helper $helper -Config $ConfigPath -RepoRoot $repoRoot `
            -RuntimeRoot $runtimeRoot
        Write-Host "Test Plane: http://localhost:8000"
    }
}
finally {
    if (-not $KeepPackage -and (Test-Path -LiteralPath $releaseRoot)) {
        Remove-Item -LiteralPath $releaseRoot -Recurse -Force
    }
}
