---
name: hermes-yolo-three-env
description: "Use when auditing, fixing, or documenting YOLO/full-auto behavior across Giovanni's three shell environments on Windows: PowerShell 7/cmd.exe, MSYS2 Zsh, and local WSL Ubuntu, while respecting the fact that only two Hermes Agent installations exist."
version: 1.0.0
author: Hermes Agent
platforms: [windows, linux]
---

# Hermes YOLO across 3 environments on Giovanni's Windows host

## Topology

There are 3 shell environments but only 2 Hermes installations:

1. PowerShell 7 / cmd.exe
   - same Windows Hermes install
   - Hermes home: `C:\Users\muniz\AppData\Local\hermes`

2. MSYS2 Zsh via PowerShell 7 wrapper / Windows Terminal profile
   - same Windows Hermes install as item 1
   - bootstrap file: `C:\Users\muniz\.config\shell\common-env.sh`

3. WSL Ubuntu-24.04
   - separate WSL Hermes install
   - Hermes home: `/home/muniz/.hermes`

## YOLO correctness model

YOLO is layered. "Full permissions" is not one switch.

### Layer 1 — Hermes config
Both Hermes installs must keep:

```yaml
approvals:
  mode: off
  timeout: 60
  cron_mode: deny
```

Important: `approvals.mode` must be the string `off`, not boolean `false`.

### Layer 2 — shell/runtime env
Set these in every environment that launches Hermes:

```bash
HERMES_YOLO_MODE=1
HERMES_ACCEPT_HOOKS=true
```

### Layer 3 — environment-specific bootstrap points

#### PowerShell 7 / Windows PowerShell
Set in both profile files:
- `C:\Users\muniz\Documents\PowerShell\Microsoft.PowerShell_profile.ps1`
- `C:\Users\muniz\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`

#### cmd.exe
Persist in both:
- User env vars in `HKCU\Environment`
- `HKCU\Software\Microsoft\Command Processor\AutoRun`

#### MSYS2 Zsh
Set through:
- `C:\Users\muniz\.config\shell\common-env.sh`
- active `C:\Users\muniz\.zshrc` already sources `common.zsh`, which sources `common-env.sh`

#### WSL
Set through:
- `/home/muniz/.hermes/.env`
- `/mnt/c/Users/muniz/.config/shell/common-env.sh`
- `/home/muniz/.zshrc`
- `/home/muniz/.profile`
- `/home/muniz/.bashrc` should source `common-env.sh` too for interactive non-login bash

## Verification

### Windows Hermes config
```bash
python - <<'PY'
from pathlib import Path
import yaml
obj=yaml.safe_load(Path(r'C:/Users/muniz/AppData/Local/hermes/config.yaml').read_text())
print(obj.get('approvals'))
PY
```

### WSL Hermes config
```bash
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -lc "python3 -c 'from pathlib import Path; import yaml; obj=yaml.safe_load(Path(\"/home/muniz/.hermes/config.yaml\").read_text()); print(obj.get(\"approvals\"))'"
```

### PowerShell 7
```bash
powershell.exe -NoLogo -Command '$env:HERMES_YOLO_MODE; $env:HERMES_ACCEPT_HOOKS'
```

### cmd.exe
```bash
cmd.exe /c "echo %HERMES_YOLO_MODE% & echo %HERMES_ACCEPT_HOOKS%"
```

### MSYS2 zsh
```bash
C:\msys64\usr\bin\zsh.exe -ic 'printf "YOLO=%s\nHOOKS=%s\nHERMES_HOME=%s\n" "$HERMES_YOLO_MODE" "$HERMES_ACCEPT_HOOKS" "$HERMES_HOME"'
```

### WSL zsh / bash
```bash
wsl.exe -d Ubuntu-24.04 -u muniz -- zsh -ic 'printf "YOLO=%s\nHOOKS=%s\nHERMES_HOME=%s\n" "$HERMES_YOLO_MODE" "$HERMES_ACCEPT_HOOKS" "$HERMES_HOME"'
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -ic 'printf "YOLO=%s\nHOOKS=%s\nHERMES_HOME=%s\n" "$HERMES_YOLO_MODE" "$HERMES_ACCEPT_HOOKS" "$HERMES_HOME"'
```

## Notes
- YOLO removes Hermes approval prompts; it does not create OS privileges out of thin air.
- Windows PowerShell 7 + cmd.exe and MSYS2 Zsh share the same Windows Hermes install.
- WSL is a distinct Hermes runtime and must keep its own `HERMES_HOME`.
