[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet("auto", "all", "web", "admin", "space", "api", "worker", "beat-worker", "live", "proxy")]
    [string[]]$Services = @("auto"),

    [string]$ConfigPath,

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

function Get-ChangedPaths {
    param([Parameter(Mandatory)][string]$RepoRoot)

    $tracked = & git -C $RepoRoot diff --name-only HEAD
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect tracked changes" }
    $untracked = & git -C $RepoRoot ls-files --others --exclude-standard
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect untracked changes" }
    return @($tracked) + @($untracked) | Where-Object { $_ }
}

function Resolve-AutoServices {
    param([Parameter(Mandatory)][string[]]$Paths)

    $selected = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($path in $Paths) {
        $normalized = $path.Replace("\", "/")
        switch -Regex ($normalized) {
            '^apps/api/' { [void]$selected.Add("api"); continue }
            '^apps/web/' { [void]$selected.Add("web"); continue }
            '^apps/admin/' { [void]$selected.Add("admin"); continue }
            '^apps/space/' { [void]$selected.Add("space"); continue }
            '^apps/live/' { [void]$selected.Add("live"); continue }
            '^apps/proxy/' { [void]$selected.Add("proxy"); continue }
            '^packages/' {
                foreach ($service in @("web", "admin", "space", "live")) { [void]$selected.Add($service) }
                continue
            }
            '^(docker-compose\.yml|pnpm-lock\.yaml|pnpm-workspace\.yaml|package\.json|turbo\.json)$' {
                [void]$selected.Add("all")
                continue
            }
        }
    }
    if ($selected.Count -eq 0) {
        throw "Automatic service selection found no runtime changes. Specify -Services explicitly if deployment is intentional."
    }
    if ($selected.Contains("all")) { return @("all") }
    return @($selected | Sort-Object)
}

function Invoke-RequiredCheck {
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string[]]$SelectedServices
    )

    Push-Location $RepoRoot
    try {
        $frontendApps = @($SelectedServices | Where-Object { $_ -in @("web", "admin", "space") })
        if ($SelectedServices -contains "all") { $frontendApps = @("web", "admin", "space") }
        foreach ($app in $frontendApps) {
            & pnpm turbo run check:types --filter=$app
            if ($LASTEXITCODE -ne 0) { throw "Type check failed for $app with exit code $LASTEXITCODE" }
        }
        if ($SelectedServices -contains "live" -or $SelectedServices -contains "all") {
            & pnpm --filter=live test
            if ($LASTEXITCODE -ne 0) { throw "Live tests failed with exit code $LASTEXITCODE" }
        }
        if ($SelectedServices -contains "api" -or $SelectedServices -contains "worker" -or $SelectedServices -contains "beat-worker" -or $SelectedServices -contains "all") {
            & python -m compileall -q apps/api/plane
            if ($LASTEXITCODE -ne 0) { throw "Python compile check failed with exit code $LASTEXITCODE" }
        }
    }
    finally { Pop-Location }
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
if (-not $SkipChecks -and -not (Get-Command pnpm -ErrorAction SilentlyContinue)) { throw "pnpm is not available on PATH" }

$selectedServices = @($Services | Select-Object -Unique)
if ($selectedServices -contains "auto") {
    if ($selectedServices.Count -ne 1) { throw "Use -Services auto by itself" }
    $selectedServices = Resolve-AutoServices -Paths (Get-ChangedPaths -RepoRoot $repoRoot)
}
if ($selectedServices -contains "all" -and $selectedServices.Count -ne 1) { throw "Use -Services all by itself" }

$commit = (& git -C $repoRoot rev-parse --short=12 HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not determine the current commit" }
$release = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $commit
$runtimeRoot = Join-Path ([System.IO.Path]::GetTempPath()) "plane-test-deploy/$release"
$archive = Join-Path $runtimeRoot "$release.tar.gz"
$manifest = Join-Path $runtimeRoot "$release.manifest.json"
$serviceCsv = $selectedServices -join ","

Write-Host "Selected services: $serviceCsv"
Write-Host "Release: $release"

if (-not $SkipChecks -and $PSCmdlet.ShouldProcess($serviceCsv, "Run pre-deployment checks")) {
    Invoke-RequiredCheck -RepoRoot $repoRoot -SelectedServices $selectedServices
}

if ($WhatIfPreference) {
    & $systemPython $helper package --repo $repoRoot --output $archive --manifest $manifest --dry-run
    if ($LASTEXITCODE -ne 0) { throw "Package dry run failed with exit code $LASTEXITCODE" }
    Write-Host "Would deploy to the dedicated Plane test root using the private configuration at $ConfigPath"
    exit 0
}

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
try {
    & $systemPython $helper package --repo $repoRoot --output $archive --manifest $manifest
    if ($LASTEXITCODE -ne 0) { throw "Packaging failed with exit code $LASTEXITCODE" }

    $transportPython = Get-TransportPython -SystemPython $systemPython
    if ($PSCmdlet.ShouldProcess($serviceCsv, "Upload and deploy release $release to the Plane test environment")) {
        & $transportPython $helper deploy --config $ConfigPath --archive $archive --remote-script $remoteScript `
            --release $release --services $serviceCsv --timeout $TimeoutSeconds
        if ($LASTEXITCODE -ne 0) { throw "Deployment failed with exit code $LASTEXITCODE" }
    }
}
finally {
    if (-not $KeepPackage -and (Test-Path -LiteralPath $runtimeRoot)) {
        Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
    }
}
