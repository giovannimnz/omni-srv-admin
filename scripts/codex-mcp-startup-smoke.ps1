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
  $results.Add((Test-ProfileFile "knowledge-mcp"))

  $reachable = Test-NetConnection -ComputerName "10.11.1.11" -Port 27124 -InformationLevel Quiet
  if ($reachable) {
    $results.Add((New-SmokeResult "knowledge-mcp" "obsidian-rest-reachability" "ok" "10.11.1.11:27124 reachable"))
  } else {
    $results.Add((New-SmokeResult "knowledge-mcp" "obsidian-rest-reachability" "unreachable" "10.11.1.11:27124 not reachable" "Check WireGuard/VPN before enabling Obsidian MCP."))
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
