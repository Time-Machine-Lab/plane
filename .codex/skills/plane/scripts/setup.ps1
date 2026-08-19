[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceUrl,
    [string]$WorkspaceSlug,
    [switch]$NonInteractive,
    [switch]$Replace,
    [switch]$Json
)

. (Join-Path $PSScriptRoot "lib/plane.ps1")

$tokenForRedaction = [Environment]::GetEnvironmentVariable("PLANE_API_TOKEN", "Process")
try {
    $result = Invoke-PlaneSetup -WorkspaceUrl $WorkspaceUrl -WorkspaceSlug $WorkspaceSlug -NonInteractive:$NonInteractive -Replace:$Replace
    if ($Json) {
        $result | ConvertTo-Json -Depth 6 -Compress
    }
    else {
        Write-Host "Plane MCP is configured for $($result.origin)/$($result.workspace_slug)."
        Write-Host "MCP entry: $($result.mcp_configuration); token persisted: no."
        Write-Host $result.restart_note
    }
}
catch {
    $tokenForRedaction = [Environment]::GetEnvironmentVariable("PLANE_API_TOKEN", "Process")
    $message = Protect-PlaneText -Text $_.Exception.Message -Token $tokenForRedaction
    if ($Json) {
        [pscustomobject]@{ status = "error"; error = $message } | ConvertTo-Json -Compress
    }
    else {
        Write-Error $message
    }
    exit 1
}
