Set-StrictMode -Version Latest

$script:PlaneMcpName = "plane"
$script:PlaneTokenVariable = "PLANE_API_TOKEN"
$script:PlaneMcpProtocolVersion = "2025-03-26"

function Protect-PlaneText {
    param(
        [AllowNull()]
        [string]$Text,
        [AllowNull()]
        [string]$Token
    )

    if ($null -eq $Text) {
        return ""
    }

    $redacted = $Text
    if (-not [string]::IsNullOrWhiteSpace($Token)) {
        $redacted = $redacted.Replace($Token, "[REDACTED]")
    }
    $redacted = [regex]::Replace($redacted, '(?i)(Authorization\s*:\s*Bearer\s+)[^\s,;]+', '$1[REDACTED]')
    $redacted = [regex]::Replace($redacted, '(?i)(X-Api-Key\s*:\s*)[^\s,;]+', '$1[REDACTED]')
    return $redacted
}

function Assert-PlaneApiTokenSafe {
    param([Parameter(Mandatory = $true)][string]$Token)

    $hasControlCharacter = $false
    foreach ($character in $Token.ToCharArray()) {
        if ([char]::IsControl($character)) {
            $hasControlCharacter = $true
            break
        }
    }
    if ($hasControlCharacter -or $Token.IndexOf([char]34) -ge 0 -or $Token.IndexOf([char]92) -ge 0) {
        throw "Plane API token contains unsafe characters."
    }
}

function Get-PlaneCodexHome {
    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        return [System.IO.Path]::GetFullPath($env:CODEX_HOME)
    }
    return Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)) ".codex"
}

function Get-PlaneProfilePath {
    if (-not [string]::IsNullOrWhiteSpace($env:PLANE_PROFILE_PATH)) {
        return [System.IO.Path]::GetFullPath($env:PLANE_PROFILE_PATH)
    }
    return Join-Path (Get-PlaneCodexHome) "plane/profile.json"
}

function Get-PlaneCodexConfigPath {
    return Join-Path (Get-PlaneCodexHome) "config.toml"
}

function ConvertTo-PlaneConnectionProfile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceUrl,
        [string]$WorkspaceSlug
    )

    $uri = $null
    if (-not [Uri]::TryCreate($WorkspaceUrl, [UriKind]::Absolute, [ref]$uri)) {
        throw "Workspace URL is not an absolute URL."
    }
    $isLoopbackHttp = $uri.Scheme -eq "http" -and $uri.IsLoopback
    if ($uri.Scheme -ne "https" -and -not $isLoopbackHttp) {
        throw "Workspace URL must use HTTPS unless it targets a loopback address."
    }
    if (-not [string]::IsNullOrEmpty($uri.UserInfo)) {
        throw "Workspace URL must not contain user information."
    }
    if (-not [string]::IsNullOrEmpty($uri.Query) -or -not [string]::IsNullOrEmpty($uri.Fragment)) {
        throw "Workspace URL must not contain a query string or fragment."
    }

    $segments = @($uri.AbsolutePath.Trim("/").Split("/", [StringSplitOptions]::RemoveEmptyEntries))
    $slug = $WorkspaceSlug
    if ([string]::IsNullOrWhiteSpace($slug) -and $segments.Count -gt 0) {
        $slug = [Uri]::UnescapeDataString($segments[0])
    }
    if ([string]::IsNullOrWhiteSpace($slug)) {
        throw "Workspace slug is missing. Add it to the URL path or pass WorkspaceSlug."
    }
    if ($slug -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]*$') {
        throw "Workspace slug contains unsupported characters."
    }
    if ($slug.ToLowerInvariant() -in @("api", "mcp", "god-mode", "spaces")) {
        throw "Workspace slug cannot be a reserved Plane path."
    }
    if (-not [string]::IsNullOrWhiteSpace($WorkspaceSlug) -and $segments.Count -gt 0) {
        $pathSlug = [Uri]::UnescapeDataString($segments[0])
        if ($pathSlug -ne $slug) {
            throw "Workspace slug does not match the workspace URL path."
        }
    }

    $origin = $uri.GetLeftPart([UriPartial]::Authority).TrimEnd("/")
    return [pscustomobject]@{
        origin         = $origin
        workspace_slug = $slug
        mcp_url        = "$origin/mcp"
    }
}

function Get-PlaneApiToken {
    param([switch]$NonInteractive)

    $existing = [Environment]::GetEnvironmentVariable($script:PlaneTokenVariable, "Process")
    if (-not [string]::IsNullOrWhiteSpace($existing)) {
        Assert-PlaneApiTokenSafe -Token $existing
        return [pscustomobject]@{ Value = $existing; Source = "environment" }
    }
    if ($NonInteractive) {
        throw "$script:PlaneTokenVariable is not available in this process."
    }

    $secure = Read-Host "Plane API token" -AsSecureString
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Plane API token is empty."
    }
    Assert-PlaneApiTokenSafe -Token $value
    [Environment]::SetEnvironmentVariable($script:PlaneTokenVariable, $value, "Process")
    return [pscustomobject]@{ Value = $value; Source = "masked_prompt" }
}

function Invoke-PlaneCodex {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $standardErrorPath = Join-Path ([IO.Path]::GetTempPath()) ("plane-codex-stderr-{0}.txt" -f [Guid]::NewGuid().ToString("N"))
    try {
        $standardOutput = @(& codex @Arguments 2> $standardErrorPath)
        $exitCode = $LASTEXITCODE
        $output = $standardOutput -join [Environment]::NewLine
        $standardError = if (Test-Path -LiteralPath $standardErrorPath) {
            Get-Content -Raw -LiteralPath $standardErrorPath -ErrorAction SilentlyContinue
        }
        else {
            ""
        }
        if ($exitCode -ne 0 -and -not [string]::IsNullOrWhiteSpace($standardError)) {
            $output = @($output, $standardError.TrimEnd()) -join [Environment]::NewLine
        }
        return [pscustomobject]@{
            ExitCode = $exitCode
            Output   = $output
        }
    }
    finally {
        Remove-Item -LiteralPath $standardErrorPath -Force -ErrorAction SilentlyContinue
    }
}

function Assert-PlaneCodexPreflight {
    if ($null -eq (Get-Command codex -ErrorAction SilentlyContinue)) {
        throw "Codex CLI is not installed or is not available on PATH."
    }
    $help = Invoke-PlaneCodex -Arguments @("mcp", "add", "--help")
    if ($help.ExitCode -ne 0 -or $help.Output -notmatch '--url') {
        throw "This Codex CLI does not support remote HTTP MCP servers."
    }
}

function Get-PlaneMcpConfig {
    $result = Invoke-PlaneCodex -Arguments @("mcp", "get", $script:PlaneMcpName, "--json")
    if ($result.ExitCode -ne 0) {
        return $null
    }
    try {
        return $result.Output | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Codex returned invalid JSON for the plane MCP entry."
    }
}

function Get-PlaneTokenFromMcpConfig {
    param([AllowNull()]$Config)

    if ($null -eq $Config -or $null -eq $Config.transport -or $null -eq $Config.transport.http_headers) {
        return $null
    }
    $authorization = $Config.transport.http_headers.PSObject.Properties |
        Where-Object { $_.Name -ieq "Authorization" } |
        Select-Object -First 1
    if ($null -eq $authorization -or [string]$authorization.Value -notmatch '^Bearer\s+(.+)$') {
        return $null
    }
    $token = $Matches[1]
    Assert-PlaneApiTokenSafe -Token $token
    return $token
}

function Test-PlaneMcpConfigMatch {
    param(
        [AllowNull()]$Config,
        [Parameter(Mandatory = $true)][string]$McpUrl,
        [Parameter(Mandatory = $true)][string]$Token
    )

    if ($null -eq $Config -or $null -eq $Config.transport) {
        return $false
    }
    $configuredToken = Get-PlaneTokenFromMcpConfig -Config $Config
    return (
        $Config.enabled -ne $false -and
        $Config.transport.type -eq "streamable_http" -and
        $Config.transport.url.TrimEnd("/") -eq $McpUrl.TrimEnd("/") -and
        $configuredToken -ceq $Token
    )
}

function Set-PlaneMcpStaticToken {
    param([Parameter(Mandatory = $true)][string]$Token)

    Assert-PlaneApiTokenSafe -Token $Token
    $path = Get-PlaneCodexConfigPath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Codex did not create its user-level configuration file."
    }
    $content = Get-Content -Raw -LiteralPath $path
    if ($content -notmatch '(?m)^\[mcp_servers\.plane\]\s*$') {
        throw "Codex did not create the plane MCP configuration table."
    }
    if ($content -match '(?m)^\[mcp_servers\.plane\.http_headers\]\s*$') {
        throw "The plane MCP authorization table already exists unexpectedly."
    }

    $newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
    $prefix = if ($content.EndsWith("`n")) { $content } else { "$content$newline" }
    $updated = "$prefix$newline[mcp_servers.plane.http_headers]$newline" +
        "Authorization = `"Bearer $Token`"$newline"
    $directory = Split-Path -Parent $path
    $temporary = Join-Path $directory ("config.{0}.tmp" -f [Guid]::NewGuid().ToString("N"))
    try {
        [IO.File]::WriteAllText($temporary, $updated, [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Invoke-PlaneHttpRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][ValidateSet("ApiKey", "Bearer")][string]$Authentication,
        [Parameter(Mandatory = $true)][string]$Token,
        [ValidateSet("Get", "Post")][string]$Method = "Get",
        [string]$Body = "{}"
    )

    Assert-PlaneApiTokenSafe -Token $Token
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(15)
    $httpMethod = if ($Method -eq "Post") { [System.Net.Http.HttpMethod]::Post } else { [System.Net.Http.HttpMethod]::Get }
    $request = [System.Net.Http.HttpRequestMessage]::new($httpMethod, $Url)
    if ($Authentication -eq "ApiKey") {
        $request.Headers.Add("X-Api-Key", $Token)
        $request.Headers.Accept.ParseAdd("application/json")
    }
    else {
        $request.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $Token)
        $request.Headers.Accept.ParseAdd("text/event-stream")
        $request.Headers.Accept.ParseAdd("application/json")
        $request.Headers.Add("MCP-Protocol-Version", $script:PlaneMcpProtocolVersion)
    }
    if ($Method -eq "Post") {
        $request.Content = [System.Net.Http.StringContent]::new($Body, [Text.Encoding]::UTF8, "application/json")
    }
    try {
        $response = $client.Send($request)
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        return [pscustomobject]@{ Status = [int]$response.StatusCode; Body = $body }
    }
    catch [System.Net.Http.HttpRequestException] {
        throw "Network, DNS, or TLS connection failed."
    }
    catch [System.Threading.Tasks.TaskCanceledException] {
        throw "Network request timed out."
    }
    finally {
        $request.Dispose()
        $client.Dispose()
        $handler.Dispose()
    }
}

function Get-PlaneUserLabel {
    param([Parameter(Mandatory = $true)][string]$Json)

    try {
        $user = $Json | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Plane returned invalid identity JSON."
    }
    foreach ($property in @("display_name", "name", "email", "id")) {
        if ($null -ne $user.PSObject.Properties[$property] -and -not [string]::IsNullOrWhiteSpace([string]$user.$property)) {
            return [string]$user.$property
        }
    }
    return "authenticated user"
}

function Test-PlaneConnection {
    param(
        [Parameter(Mandatory = $true)]$Profile,
        [Parameter(Mandatory = $true)][string]$Token
    )

    $identity = Invoke-PlaneHttpRequest -Url "$($Profile.origin)/api/v1/users/me/" -Authentication ApiKey -Token $Token
    if ($identity.Status -in @(401, 403)) {
        throw "Plane rejected the API token."
    }
    if ($identity.Status -ne 200) {
        throw "Plane identity validation failed with HTTP $($identity.Status)."
    }

    $encodedSlug = [Uri]::EscapeDataString($Profile.workspace_slug)
    $workspace = Invoke-PlaneHttpRequest -Url "$($Profile.origin)/api/v1/workspaces/$encodedSlug/projects/?per_page=1" -Authentication ApiKey -Token $Token
    if ($workspace.Status -in @(401, 403, 404)) {
        throw "The authenticated user cannot access the requested workspace."
    }
    if ($workspace.Status -ne 200) {
        throw "Workspace validation failed with HTTP $($workspace.Status)."
    }

    $mcp = Invoke-PlaneHttpRequest -Url $Profile.mcp_url -Authentication Bearer -Token $Token -Method Post
    if ($mcp.Status -in @(401, 403)) {
        throw "The MCP endpoint rejected the API token."
    }
    if ($mcp.Status -eq 404 -or $mcp.Status -ge 500) {
        throw "The Plane MCP endpoint is not available."
    }
    if ($mcp.Status -notin @(200, 400, 422)) {
        throw "The Plane MCP endpoint returned unexpected HTTP $($mcp.Status)."
    }

    $userLabel = Get-PlaneUserLabel -Json $identity.Body
    return [pscustomobject]@{ User = Protect-PlaneText -Text $userLabel -Token $Token }
}

function Save-PlaneProfile {
    param([Parameter(Mandatory = $true)]$Profile)

    $path = Get-PlaneProfilePath
    $directory = Split-Path -Parent $path
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $temporary = Join-Path $directory ("profile.{0}.tmp" -f [Guid]::NewGuid().ToString("N"))
    try {
        [pscustomobject]@{
            origin         = $Profile.origin
            workspace_slug = $Profile.workspace_slug
        } | ConvertTo-Json | Set-Content -LiteralPath $temporary -Encoding utf8NoBOM
        Move-Item -LiteralPath $temporary -Destination $path -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
    return $path
}

function Get-PlaneProfile {
    $path = Get-PlaneProfilePath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Plane profile is missing. Run setup first."
    }
    try {
        $profile = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Plane profile is invalid. Run setup again."
    }
    $normalized = ConvertTo-PlaneConnectionProfile -WorkspaceUrl "$($profile.origin)/$($profile.workspace_slug)" -WorkspaceSlug $profile.workspace_slug
    if ($normalized.origin -ne $profile.origin -or $normalized.workspace_slug -ne $profile.workspace_slug) {
        throw "Plane profile is not normalized. Run setup again."
    }
    return $normalized
}

function Invoke-PlaneSetup {
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceUrl,
        [string]$WorkspaceSlug,
        [switch]$NonInteractive,
        [switch]$Replace
    )

    Assert-PlaneCodexPreflight
    $profile = ConvertTo-PlaneConnectionProfile -WorkspaceUrl $WorkspaceUrl -WorkspaceSlug $WorkspaceSlug
    $token = Get-PlaneApiToken -NonInteractive:$NonInteractive
    $validation = Test-PlaneConnection -Profile $profile -Token $token.Value

    $existing = Get-PlaneMcpConfig
    $configurationChanged = $false
    if (Test-PlaneMcpConfigMatch -Config $existing -McpUrl $profile.mcp_url -Token $token.Value) {
        $configurationState = "reused"
    }
    else {
        if ($null -ne $existing -and -not $Replace) {
            if ($NonInteractive) {
                throw "A different plane MCP entry exists. Re-run with the explicit replacement flag."
            }
            $answer = Read-Host "A different plane MCP entry exists. Replace it? [y/N]"
            if ($answer -notmatch '^(?i:y|yes)$') {
                throw "The existing plane MCP entry was not changed."
            }
        }
        if ($null -ne $existing) {
            $removed = Invoke-PlaneCodex -Arguments @("mcp", "remove", $script:PlaneMcpName)
            if ($removed.ExitCode -ne 0) {
                throw "Codex could not remove the existing plane MCP entry."
            }
        }
        $added = Invoke-PlaneCodex -Arguments @(
            "mcp", "add", $script:PlaneMcpName,
            "--url", $profile.mcp_url
        )
        if ($added.ExitCode -ne 0) {
            throw (Protect-PlaneText -Text "Codex could not add the plane MCP entry: $($added.Output)" -Token $token.Value)
        }
        try {
            Set-PlaneMcpStaticToken -Token $token.Value
        }
        catch {
            throw (Protect-PlaneText -Text "Codex could not store the plane MCP credential: $($_.Exception.Message)" -Token $token.Value)
        }
        $configurationChanged = $true
        $configurationState = if ($null -eq $existing) { "added" } else { "replaced" }
    }

    $profilePath = Save-PlaneProfile -Profile $profile
    return [pscustomobject]@{
        status                = "configured"
        origin                = $profile.origin
        workspace_slug        = $profile.workspace_slug
        authenticated_user    = $validation.User
        mcp_configuration     = $configurationState
        configuration_changed = $configurationChanged
        token_source          = $token.Source
        token_persisted       = $true
        token_storage         = "codex_user_mcp_config"
        profile_path          = $profilePath
        new_task_required     = $true
        restart_note          = "Open a new Codex task if this task does not refresh the Plane MCP tool catalog. No terminal command or application relaunch is required."
    }
}

function Add-PlaneDoctorCheck {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Checks,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][ValidateSet("pass", "fail", "skipped")][string]$Status,
        [Parameter(Mandatory = $true)][string]$Category,
        [Parameter(Mandatory = $true)][string]$Detail
    )
    $Checks.Add([pscustomobject]@{ name = $Name; status = $Status; category = $Category; detail = $Detail })
}

function Invoke-PlaneStatusProbe {
    param(
        [Parameter(Mandatory = $true)]$Profile,
        [Parameter(Mandatory = $true)][string]$Token
    )

    try {
        $payload = [ordered]@{
            jsonrpc = "2.0"
            id      = "plane-doctor-status"
            method  = "tools/call"
            params  = [ordered]@{
                name      = "plane_status"
                arguments = [ordered]@{ workspace_slug = $Profile.workspace_slug }
            }
        } | ConvertTo-Json -Depth 6 -Compress
        $response = Invoke-PlaneHttpRequest -Url $Profile.mcp_url -Authentication Bearer -Token $Token -Method Post -Body $payload
        if ($response.Status -in @(401, 403)) {
            return [pscustomobject]@{ Success = $false; Detail = "The Plane MCP endpoint rejected the credential." }
        }
        if ($response.Status -ne 200) {
            return [pscustomobject]@{ Success = $false; Detail = "The plane_status MCP request returned HTTP $($response.Status)." }
        }

        $message = $response.Body | ConvertFrom-Json -ErrorAction Stop
        if ($null -ne $message.PSObject.Properties["error"]) {
            return [pscustomobject]@{ Success = $false; Detail = "The Plane MCP endpoint returned a JSON-RPC error." }
        }
        $resultProperty = $message.PSObject.Properties["result"]
        if ($null -eq $resultProperty) {
            return [pscustomobject]@{ Success = $false; Detail = "The Plane MCP endpoint returned an invalid plane_status result." }
        }
        $result = $resultProperty.Value
        $isErrorProperty = $result.PSObject.Properties["isError"]
        if ($null -ne $isErrorProperty -and $isErrorProperty.Value -eq $true) {
            $errorCode = [string]$result.structuredContent.error.code
            if ($errorCode -notmatch '^[a-z_]+$') { $errorCode = "tool_error" }
            return [pscustomobject]@{ Success = $false; Detail = "plane_status returned a $errorCode error." }
        }
        $structuredContentProperty = $result.PSObject.Properties["structuredContent"]
        if ($null -eq $structuredContentProperty) {
            return [pscustomobject]@{ Success = $false; Detail = "The Plane MCP endpoint returned an invalid plane_status result." }
        }
        $status = $structuredContentProperty.Value
        if ($status.available -ne $true -or [string]$status.workspace -ne [string]$Profile.workspace_slug) {
            return [pscustomobject]@{ Success = $false; Detail = "plane_status did not confirm the configured workspace." }
        }
        return [pscustomobject]@{ Success = $true; Detail = "plane_status confirmed the configured workspace." }
    }
    catch {
        return [pscustomobject]@{ Success = $false; Detail = "The deterministic plane_status MCP probe failed." }
    }
}

function Invoke-PlaneDoctor {
    $checks = [System.Collections.Generic.List[object]]::new()
    $token = $null
    $config = $null
    $profile = $null
    $user = $null

    try {
        Assert-PlaneCodexPreflight
        Add-PlaneDoctorCheck $checks "codex" "pass" "local_configuration" "Codex remote MCP support is available."
    }
    catch {
        Add-PlaneDoctorCheck $checks "codex" "fail" "local_configuration" (Protect-PlaneText $_.Exception.Message $token)
    }

    try {
        $profile = Get-PlaneProfile
        Add-PlaneDoctorCheck $checks "profile" "pass" "local_configuration" "The non-secret Plane profile is valid."
    }
    catch {
        Add-PlaneDoctorCheck $checks "profile" "fail" "local_configuration" (Protect-PlaneText $_.Exception.Message $token)
    }

    if ($null -ne $profile) {
        try {
            $config = Get-PlaneMcpConfig
            $token = Get-PlaneTokenFromMcpConfig -Config $config
            if ([string]::IsNullOrWhiteSpace($token) -or -not (Test-PlaneMcpConfigMatch $config $profile.mcp_url $token)) {
                throw "The plane MCP entry is missing or does not match the profile."
            }
            Add-PlaneDoctorCheck $checks "mcp_configuration" "pass" "local_configuration" "The plane MCP entry matches the profile."
        }
        catch {
            Add-PlaneDoctorCheck $checks "mcp_configuration" "fail" "local_configuration" (Protect-PlaneText $_.Exception.Message $token)
        }
    }
    else {
        Add-PlaneDoctorCheck $checks "mcp_configuration" "skipped" "local_configuration" "Skipped because the profile is unavailable."
    }

    if ([string]::IsNullOrWhiteSpace($token)) {
        Add-PlaneDoctorCheck $checks "authentication" "fail" "authentication" "The plane MCP entry does not contain a Bearer credential."
    }
    elseif ($null -ne $profile) {
        try {
            $mcp = Invoke-PlaneHttpRequest $profile.mcp_url Bearer $token Post
            if ($mcp.Status -in @(401, 403)) {
                throw "The Plane MCP endpoint rejected the credential."
            }
            if ($mcp.Status -notin @(200, 400, 422)) {
                throw "The Plane MCP endpoint is unavailable or returned HTTP $($mcp.Status)."
            }
            Add-PlaneDoctorCheck $checks "reachability" "pass" "reachability_tls" "The Plane MCP endpoint is reachable over TLS."
        }
        catch {
            Add-PlaneDoctorCheck $checks "reachability" "fail" "reachability_tls" (Protect-PlaneText $_.Exception.Message $token)
        }

        try {
            $identity = Invoke-PlaneHttpRequest "$($profile.origin)/api/v1/users/me/" ApiKey $token
            if ($identity.Status -in @(401, 403)) { throw "Plane rejected the API token." }
            if ($identity.Status -ne 200) { throw "Identity check returned HTTP $($identity.Status)." }
            $user = Protect-PlaneText -Text (Get-PlaneUserLabel $identity.Body) -Token $token
            Add-PlaneDoctorCheck $checks "authentication" "pass" "authentication" "Plane accepted the configured API token."
        }
        catch {
            Add-PlaneDoctorCheck $checks "authentication" "fail" "authentication" (Protect-PlaneText $_.Exception.Message $token)
        }

        if ($null -ne $user) {
            try {
                $encodedSlug = [Uri]::EscapeDataString($profile.workspace_slug)
                $workspace = Invoke-PlaneHttpRequest "$($profile.origin)/api/v1/workspaces/$encodedSlug/projects/?per_page=1" ApiKey $token
                if ($workspace.Status -in @(401, 403, 404)) { throw "The user cannot access the configured workspace." }
                if ($workspace.Status -ne 200) { throw "Workspace check returned HTTP $($workspace.Status)." }
                Add-PlaneDoctorCheck $checks "workspace" "pass" "workspace_authorization" "The authenticated user can access the configured workspace."
            }
            catch {
                Add-PlaneDoctorCheck $checks "workspace" "fail" "workspace_authorization" (Protect-PlaneText $_.Exception.Message $token)
            }
        }
        else {
            Add-PlaneDoctorCheck $checks "workspace" "skipped" "workspace_authorization" "Skipped because authentication failed."
        }
    }
    else {
        Add-PlaneDoctorCheck $checks "reachability" "skipped" "reachability_tls" "Skipped because connection inputs are unavailable."
        Add-PlaneDoctorCheck $checks "workspace" "skipped" "workspace_authorization" "Skipped because connection inputs are unavailable."
    }

    $canProbe = $null -ne $profile -and -not [string]::IsNullOrWhiteSpace($token) -and -not ($checks | Where-Object { $_.status -eq "fail" })
    if ($canProbe) {
        $probe = Invoke-PlaneStatusProbe $profile $token
        if ($probe.Success) {
            Add-PlaneDoctorCheck $checks "tools" "pass" "tool_availability" (Protect-PlaneText $probe.Detail $token)
        }
        else {
            Add-PlaneDoctorCheck $checks "tools" "fail" "tool_availability" (Protect-PlaneText $probe.Detail $token)
        }
    }
    else {
        Add-PlaneDoctorCheck $checks "tools" "skipped" "tool_availability" "Skipped until earlier failures are resolved."
    }

    $healthy = -not ($checks | Where-Object { $_.status -eq "fail" })
    return [pscustomobject]@{
        status             = if ($healthy) { "healthy" } else { "unhealthy" }
        origin             = if ($null -ne $profile) { $profile.origin } else { $null }
        workspace_slug     = if ($null -ne $profile) { $profile.workspace_slug } else { $null }
        authenticated_user = $user
        checks             = $checks.ToArray()
    }
}
