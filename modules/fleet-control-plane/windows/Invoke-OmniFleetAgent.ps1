param(
  [string]$RepoDir = "$env:USERPROFILE\Documents\GitHub\omni-srv-admin",
  [string]$HostId = "giovanni-w11-pc",
  [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$python = $PythonExe
if (-not $python) {
  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd) {
    $python = $pythonCmd.Source
    if ($python -match '\.(bat|cmd)$') {
      $resolved = & $python -c "import sys; print(sys.executable)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $resolved) {
        $python = ($resolved | Select-Object -Last 1).Trim()
      }
    }
  }
}
if (-not $python) {
  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCmd) {
    $resolved = & $pyCmd.Source -3 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $resolved) {
      $python = ($resolved | Select-Object -Last 1).Trim()
    }
  }
}
if (-not $python) {
  throw "Python runtime not found"
}
$env:OMNI_SRV_ADMIN = $RepoDir
if ($env:PYTHONPATH) {
  $env:PYTHONPATH = "$RepoDir\cli;$env:PYTHONPATH"
} else {
  $env:PYTHONPATH = "$RepoDir\cli"
}

$localAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $env:USERPROFILE "AppData\Local" }
$tmpRoot = if ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
$logRoot = Join-Path $localAppData "omni-srv-admin\logs"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$logFile = Join-Path $logRoot "fleet-agent-cycle.log"

$args = @("-m", "omni.fleet_entry", "agent", "cycle", "--host", $HostId, "--apply", "--json")
$tmpOut = Join-Path $tmpRoot "omni-fleet-agent-$HostId-output.txt"
if (Test-Path $tmpOut) { Remove-Item $tmpOut -Force }
$previousNativePref = $PSNativeCommandUseErrorActionPreference
$PSNativeCommandUseErrorActionPreference = $false
& $python @args *> $tmpOut
$exitCode = $LASTEXITCODE
$PSNativeCommandUseErrorActionPreference = $previousNativePref
$timestamp = Get-Date -Format "s"
$content = if (Test-Path $tmpOut) { Get-Content $tmpOut -Raw } else { "" }
Add-Content -Path $logFile -Value ("[$timestamp] exit=$exitCode`n$content")
if ($exitCode -ne 0) {
  throw "Omni fleet agent cycle failed with exit code $exitCode"
}
exit 0
