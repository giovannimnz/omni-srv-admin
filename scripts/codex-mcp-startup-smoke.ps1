[CmdletBinding()]
param(
  [ValidateSet("baseline", "knowledge-mcp", "browser-mcp", "oci-mcp", "cloud-ops-mcp", "lab-mcp", "all")]
  [string] $Profile = "baseline"
)

$ErrorActionPreference = "Continue"

$CodexHome = "C:\Users\muniz\.codex"
$LocalVaultEnv = "C:\Users\muniz\.local\bin\atius-vault-env.ps1"

function New-SmokeResult {
  param(
    [string] $Profile,
    [string] $Check,
    [ValidateSet("ok", "disabled", "missing-env", "unreachable", "slow-start")]
    [string] $Status,
    [string] $Detail,
    [string] $Next = ""
  )

  [pscustomobject]@{
    profile = $Profile
    check = $Check
    status = $Status
    detail = $Detail
    next = $Next
  }
}

function Test-EnvPresent {
  param([string] $Name)

  foreach ($scope in @("Process", "User", "Machine")) {
    $value = [Environment]::GetEnvironmentVariable($Name, $scope)
    if ($value) {
      return $true
    }
  }
  return $false
}

function Get-EnvValue {
  param([string] $Name)

  foreach ($scope in @("Process", "User", "Machine")) {
    $value = [Environment]::GetEnvironmentVariable($Name, $scope)
    if ($value) {
      return $value
    }
  }
  return $null
}

function Get-VaultExportNames {
  param([string] $VaultProfile)

  if (-not (Test-Path -LiteralPath $LocalVaultEnv)) {
    return @()
  }

  $output = & $LocalVaultEnv $VaultProfile 2>$null
  if ($LASTEXITCODE -ne 0) {
    return @()
  }

  $names = @()
  foreach ($line in $output) {
    if ($line -match '^export\s+([A-Za-z_][A-Za-z0-9_]*)=') {
      $names += $matches[1]
    }
  }
  return $names
}

function Invoke-CurlRequest {
  param(
    [ValidateSet("GET", "POST")]
    [string] $Method,
    [string] $Uri,
    [hashtable] $Headers = @{},
    [string] $Body = ""
  )

  $headerFile = New-TemporaryFile
  $bodyFile = New-TemporaryFile
  $requestBodyFile = $null

  try {
    $curlArgs = @("-sS", "-D", $headerFile.FullName, "-o", $bodyFile.FullName, "-X", $Method, $Uri)

    foreach ($key in $Headers.Keys) {
      $curlArgs += @("-H", "${key}: $($Headers[$key])")
    }

    if ($Body) {
      $requestBodyFile = New-TemporaryFile
      Set-Content -LiteralPath $requestBodyFile.FullName -Value $Body -NoNewline
      $curlArgs += @("-H", "Content-Type: application/json", "--data-binary", "@$($requestBodyFile.FullName)")
    }

    & curl.exe @curlArgs | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "curl exited with code $LASTEXITCODE"
    }

    $headerLines = Get-Content -LiteralPath $headerFile.FullName
    $statusLine = ($headerLines | Where-Object { $_ -match '^HTTP/' } | Select-Object -Last 1)
    if (-not $statusLine) {
      throw "missing HTTP status line"
    }

    $statusCode = [int](($statusLine -split '\s+')[1])
    $parsedHeaders = @{}
    foreach ($line in $headerLines) {
      if ($line -match '^(?<name>[^:]+):\s*(?<value>.*)$') {
        $parsedHeaders[$matches.name] = $matches.value.Trim()
      }
    }

    [pscustomobject]@{
      StatusCode = $statusCode
      Headers = $parsedHeaders
      Body = (Get-Content -LiteralPath $bodyFile.FullName -Raw)
    }
  } finally {
    Remove-Item -LiteralPath $headerFile.FullName, $bodyFile.FullName -Force -ErrorAction SilentlyContinue
    if ($requestBodyFile) {
      Remove-Item -LiteralPath $requestBodyFile.FullName -Force -ErrorAction SilentlyContinue
    }
  }
}

function Test-ProfileFile {
  param([string] $Name)

  $path = Join-Path $CodexHome "$Name.config.toml"
  if (Test-Path -LiteralPath $path) {
    return New-SmokeResult $Name "profile-file" "ok" $path
  }
  return New-SmokeResult $Name "profile-file" "disabled" "missing $path"
}

function Invoke-BaselineSmoke {
  $results = [System.Collections.Generic.List[object]]::new()

  $doctor = & codex doctor --json 2>&1
  if ($LASTEXITCODE -ne 0) {
    $results.Add((New-SmokeResult "baseline" "codex-doctor" "slow-start" "codex doctor failed or timed out" "Run codex doctor --json manually and inspect stderr."))
  } else {
    try {
      $parsed = $doctor | ConvertFrom-Json
      $status = if ($parsed.overallStatus -eq "ok") { "ok" } else { "slow-start" }
      $servers = $parsed.checks."config.load".details."mcp servers"
      $results.Add((New-SmokeResult "baseline" "codex-doctor" $status "overall=$($parsed.overallStatus); configured_mcp_servers=$servers"))
    } catch {
      $results.Add((New-SmokeResult "baseline" "codex-doctor" "slow-start" "doctor returned non-json output"))
    }
  }

  $list = & codex mcp list 2>&1
  if ($LASTEXITCODE -ne 0) {
    $results.Add((New-SmokeResult "baseline" "codex-mcp-list" "slow-start" "codex mcp list failed" "Run codex mcp list manually."))
  } else {
    $text = ($list -join "`n")
    $forbidden = @(
      "memory",
      "filesystem",
      "sequentialthinking",
      "chrome-devtools",
      "playwright-desktop",
      "playwright-mobile",
      "obsidian_rest",
      "cloudflare-api",
      "oci-api-",
      "oci-compute-"
    ) | Where-Object { $text -match [regex]::Escape($_) }

    if ($forbidden.Count -gt 0) {
      $results.Add((New-SmokeResult "baseline" "codex-mcp-list" "slow-start" "optional MCPs still in default: $($forbidden -join ', ')" "Move optional MCPs out of C:\Users\muniz\.codex\config.toml."))
    } else {
      $results.Add((New-SmokeResult "baseline" "codex-mcp-list" "ok" "default list excludes heavy optional MCPs"))
    }
  }

  return $results
}

function Invoke-KnowledgeSmoke {
  $results = [System.Collections.Generic.List[object]]::new()
  $profileResult = Test-ProfileFile "knowledge-mcp"
  $results.Add($profileResult)

  if ($profileResult.status -eq "ok") {
    $profileText = Get-Content -LiteralPath $profileResult.detail -Raw
    $hasNewNames = $profileText -match '\[mcp_servers\.gbrain_http\]' -and $profileText -match '\[mcp_servers\.obsidian_http\]'
    $hasRetiredNames = $profileText -match '\[mcp_servers\.obsidian_rest\]' -or $profileText -match '\[mcp_servers\.http_gbrain\]' -or $profileText -match '\[mcp_servers\.http_obsidian\]'
    $hasHardcodedBearer = $profileText -match 'Authorization\s*=\s*"Bearer\s+'

    if ($hasNewNames -and -not $hasRetiredNames -and -not $hasHardcodedBearer) {
      $results.Add((New-SmokeResult "knowledge-mcp" "profile-contract" "ok" "profile uses gbrain_http/obsidian_http without hardcoded bearer"))
    } else {
      $results.Add((New-SmokeResult "knowledge-mcp" "profile-contract" "slow-start" "profile drift: expected gbrain_http + obsidian_http via ATIUS_MCP_TOKEN, no hardcoded bearer" "Rewrite C:\\Users\\muniz\\.codex\\knowledge-mcp.config.toml to the current ATIUS MCP standard."))
    }
  }

  $token = Get-EnvValue "ATIUS_MCP_TOKEN"
  if ($token) {
    $results.Add((New-SmokeResult "knowledge-mcp" "ATIUS_MCP_TOKEN" "ok" "present in environment"))
  } else {
    $vaultNames = Get-VaultExportNames "atius-mcp"
    if ($vaultNames -contains "ATIUS_MCP_TOKEN") {
      $results.Add((New-SmokeResult "knowledge-mcp" "ATIUS_MCP_TOKEN" "missing-env" "not loaded in process; available via atius-vault-env" "Restart Codex Desktop or load atius-vault-env atius-mcp before running MCP smokes."))
    } else {
      $results.Add((New-SmokeResult "knowledge-mcp" "ATIUS_MCP_TOKEN" "missing-env" "not loaded and not exported by vault wrapper"))
    }
    return $results
  }

  $headers = @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/json, text/event-stream"
  }

  $initializeBody = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"codex-mcp-startup-smoke","version":"1.0"}}}'

  try {
    $gbrainHealth = Invoke-CurlRequest -Method GET -Uri "https://mcp.atius.com.br/gbrain/health"
    if ($gbrainHealth.StatusCode -eq 404) {
      $results.Add((New-SmokeResult "knowledge-mcp" "gbrain-health" "ok" "status=404; public edge reachable; /health not exposed on current edge"))
    } else {
      $healthStatus = if ($gbrainHealth.StatusCode -ge 200 -and $gbrainHealth.StatusCode -lt 300) { "ok" } else { "slow-start" }
      $healthNext = if ($healthStatus -eq "ok") { "" } else { "Expected 2xx or the known 404-not-exposed behavior from the public GBrain health endpoint." }
      $results.Add((New-SmokeResult "knowledge-mcp" "gbrain-health" $healthStatus "status=$([int]$gbrainHealth.StatusCode); public edge reachable" $healthNext))
    }
  } catch {
    $results.Add((New-SmokeResult "knowledge-mcp" "gbrain-health" "unreachable" $_.Exception.Message "Check public DNS/edge routing to mcp.atius.com.br."))
  }

  try {
    $gbrainInit = Invoke-CurlRequest -Method POST -Uri "https://mcp.atius.com.br/gbrain" -Headers $headers -Body $initializeBody
    $gbrainStatus = if ($gbrainInit.StatusCode -ge 200 -and $gbrainInit.StatusCode -lt 300) { "ok" } else { "slow-start" }
    $gbrainNext = if ($gbrainStatus -eq "ok") { "" } else { "Expected 2xx from MCP initialize on /gbrain." }
    $results.Add((New-SmokeResult "knowledge-mcp" "gbrain-initialize" $gbrainStatus "status=$([int]$gbrainInit.StatusCode); MCP initialize probe returned" $gbrainNext))
  } catch {
    $results.Add((New-SmokeResult "knowledge-mcp" "gbrain-initialize" "unreachable" $_.Exception.Message "Check ATIUS_MCP_TOKEN or the GBrain MCP edge."))
  }

  try {
    $obsidianInit = Invoke-CurlRequest -Method POST -Uri "https://mcp.atius.com.br/obsidian" -Headers $headers -Body $initializeBody
    $sessionId = $obsidianInit.Headers["Mcp-Session-Id"]
    if ($sessionId) {
      $notifyHeaders = @{
        "Authorization" = "Bearer $token"
        "Accept" = "application/json, text/event-stream"
        "Mcp-Session-Id" = $sessionId
      }
      $notifyBody = '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
      Invoke-CurlRequest -Method POST -Uri "https://mcp.atius.com.br/obsidian" -Headers $notifyHeaders -Body $notifyBody | Out-Null
    }
    $detail = if ($sessionId) {
      "status=$([int]$obsidianInit.StatusCode); MCP initialize succeeded; session header present"
    } else {
      "status=$([int]$obsidianInit.StatusCode); MCP initialize succeeded; session header missing"
    }
    $obsidianStatus = if ($obsidianInit.StatusCode -ge 200 -and $obsidianInit.StatusCode -lt 300 -and $sessionId) { "ok" } else { "slow-start" }
    $obsidianNext = if ($obsidianStatus -eq "ok") { "" } else { "Expected 2xx plus Mcp-Session-Id from MCP initialize on /obsidian." }
    $results.Add((New-SmokeResult "knowledge-mcp" "obsidian-initialize" $obsidianStatus $detail $obsidianNext))
  } catch {
    $results.Add((New-SmokeResult "knowledge-mcp" "obsidian-initialize" "unreachable" $_.Exception.Message "Check ATIUS_MCP_TOKEN, Obsidian plugin state, or MCP session negotiation."))
  }

  return $results
}

function Invoke-BrowserSmoke {
  $results = [System.Collections.Generic.List[object]]::new()
  $results.Add((Test-ProfileFile "browser-mcp"))

  $chrome = "C:\Users\muniz\AppData\Local\ms-playwright\chromium-1223\chrome-win64\chrome.exe"
  if (Test-Path -LiteralPath $chrome) {
    $results.Add((New-SmokeResult "browser-mcp" "chrome-executable" "ok" $chrome))
  } else {
    $results.Add((New-SmokeResult "browser-mcp" "chrome-executable" "unreachable" "missing $chrome" "Install/refresh Playwright Chromium."))
  }

  $npx = Get-Command npx -ErrorAction SilentlyContinue
  if ($npx) {
    $results.Add((New-SmokeResult "browser-mcp" "npx" "ok" $npx.Source))
  } else {
    $results.Add((New-SmokeResult "browser-mcp" "npx" "unreachable" "npx not found in PATH"))
  }

  return $results
}

function Invoke-OciSmoke {
  $results = [System.Collections.Generic.List[object]]::new()
  $results.Add((Test-ProfileFile "oci-mcp"))

  $uv = Get-Command uv -ErrorAction SilentlyContinue
  if ($uv) {
    $results.Add((New-SmokeResult "oci-mcp" "uv" "ok" $uv.Source))
  } else {
    $results.Add((New-SmokeResult "oci-mcp" "uv" "unreachable" "uv not found in PATH"))
  }

  foreach ($path in @(
    "C:\Users\muniz\Documents\GitHub\oracle-oci-mcp\src\oci-api-mcp-server",
    "C:\Users\muniz\Documents\GitHub\oracle-oci-mcp\src\oci-compute-mcp-server",
    "C:\Users\muniz\.oci\config"
  )) {
    if (Test-Path -LiteralPath $path) {
      $results.Add((New-SmokeResult "oci-mcp" "path" "ok" $path))
    } else {
      $results.Add((New-SmokeResult "oci-mcp" "path" "unreachable" "missing $path"))
    }
  }

  return $results
}

function Invoke-CloudOpsSmoke {
  $results = [System.Collections.Generic.List[object]]::new()
  $results.Add((Test-ProfileFile "cloud-ops-mcp"))

  if (Test-EnvPresent "CF_GLOBAL_API_KEY") {
    $results.Add((New-SmokeResult "cloud-ops-mcp" "CF_GLOBAL_API_KEY" "ok" "present in environment"))
  } else {
    $vaultNames = Get-VaultExportNames "cloudflare"
    if ($vaultNames -contains "CF_GLOBAL_API_KEY") {
      $results.Add((New-SmokeResult "cloud-ops-mcp" "CF_GLOBAL_API_KEY" "missing-env" "not loaded in process; available via atius-vault-env" "Use codex-cloud-ops or load atius-vault-env cloudflare in the launcher process before enabling Cloudflare MCP."))
    } else {
      $results.Add((New-SmokeResult "cloud-ops-mcp" "CF_GLOBAL_API_KEY" "missing-env" "not loaded and not exported by vault wrapper"))
    }
  }

  return $results
}

function Invoke-LabSmoke {
  $results = [System.Collections.Generic.List[object]]::new()
  $results.Add((Test-ProfileFile "lab-mcp"))

  $npx = Get-Command npx -ErrorAction SilentlyContinue
  if ($npx) {
    $results.Add((New-SmokeResult "lab-mcp" "npx" "ok" $npx.Source))
  } else {
    $results.Add((New-SmokeResult "lab-mcp" "npx" "unreachable" "npx not found in PATH"))
  }

  return $results
}

$profiles = if ($Profile -eq "all") {
  @("baseline", "knowledge-mcp", "browser-mcp", "oci-mcp", "cloud-ops-mcp", "lab-mcp")
} else {
  @($Profile)
}

$allResults = [System.Collections.Generic.List[object]]::new()
foreach ($target in $profiles) {
  switch ($target) {
    "baseline" { (Invoke-BaselineSmoke) | ForEach-Object { $allResults.Add($_) } }
    "knowledge-mcp" { (Invoke-KnowledgeSmoke) | ForEach-Object { $allResults.Add($_) } }
    "browser-mcp" { (Invoke-BrowserSmoke) | ForEach-Object { $allResults.Add($_) } }
    "oci-mcp" { (Invoke-OciSmoke) | ForEach-Object { $allResults.Add($_) } }
    "cloud-ops-mcp" { (Invoke-CloudOpsSmoke) | ForEach-Object { $allResults.Add($_) } }
    "lab-mcp" { (Invoke-LabSmoke) | ForEach-Object { $allResults.Add($_) } }
  }
}

$allResults | ConvertTo-Json -Depth 4

$blocked = $allResults | Where-Object { $_.status -in @("missing-env", "unreachable", "slow-start") }
if ($blocked) {
  exit 1
}
