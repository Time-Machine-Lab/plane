[CmdletBinding()]
param([switch]$Json)

. (Join-Path $PSScriptRoot "lib/plane.ps1")

$result = Invoke-PlaneDoctor
if ($Json) {
    $result | ConvertTo-Json -Depth 8 -Compress
}
else {
    foreach ($check in $result.checks) {
        Write-Host ("[{0}] {1}: {2}" -f $check.status.ToUpperInvariant(), $check.name, $check.detail)
    }
    Write-Host "Plane doctor result: $($result.status)."
}
if ($result.status -ne "healthy") {
    exit 1
}
