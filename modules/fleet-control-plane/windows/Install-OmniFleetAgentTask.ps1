param(
  [string]$RepoDir = "$env:USERPROFILE\Documents\GitHub\omni-srv-admin",
  [string]$HostId = "giovanni-w11-pc",
  [string]$TaskName = "OmniFleetAgent",
  [int]$Minutes = 30
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $RepoDir "modules\fleet-control-plane\windows\Invoke-OmniFleetAgent.ps1"
if (-not (Test-Path $scriptPath)) {
  throw "missing script: $scriptPath"
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
$pythonExe = $null
if ($pythonCmd) {
  $pythonExe = $pythonCmd.Source
  if ($pythonExe -match '\.(bat|cmd)$') {
    $resolved = & $pythonExe -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $resolved) {
      $pythonExe = ($resolved | Select-Object -Last 1).Trim()
    }
  }
}
if (-not $pythonExe) {
  throw "python executable not found for scheduled task"
}

$launcherDir = Join-Path $env:LOCALAPPDATA "omni-srv-admin"
New-Item -ItemType Directory -Force -Path $launcherDir | Out-Null
$launcherPath = Join-Path $launcherDir "OmniFleetAgent.cmd"
@"
@echo off
set REPO_DIR=$RepoDir
set HOST_ID=$HostId
set PYTHON_EXE=$pythonExe
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$scriptPath" -RepoDir "%REPO_DIR%" -HostId "%HOST_ID%" -PythonExe "%PYTHON_EXE%"
exit /b %ERRORLEVEL%
"@ | Set-Content -Path $launcherPath -Encoding ASCII

schtasks /Create /F /TN $TaskName /SC MINUTE /MO $Minutes /TR $launcherPath | Out-Null
schtasks /Run /TN $TaskName | Out-Null
schtasks /Query /TN $TaskName /V /FO LIST
