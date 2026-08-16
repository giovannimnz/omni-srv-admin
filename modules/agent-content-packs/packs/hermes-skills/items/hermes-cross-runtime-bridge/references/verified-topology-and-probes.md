# Verified dual-runtime topology and probe recipes

This reference captures the concrete Giovanni Windows/WSL installation verified on 2026-07-19. Keep volatile counts and versions here rather than turning them into permanent invariants in `SKILL.md`.

## Verified topology

| Item | Windows native | WSL |
|---|---|---|
| Runtime home | `C:\Users\muniz\AppData\Local\hermes` | `/home/muniz/.hermes` |
| Native executable | `C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe` | `/home/muniz/.local/bin/hermes` |
| Source checkout | `C:\Users\muniz\AppData\Local\hermes\hermes-agent` | `/home/muniz/.hermes/hermes-agent` |
| Peer filesystem view | WSL appears at `\\wsl.localhost\Ubuntu-24.04\home\muniz\.hermes` | Windows appears at `/mnt/c/Users/muniz/AppData/Local/hermes` |
| Gateway ownership | Stopped by design | Authoritative active gateway |
| Default profile/model | Re-check live | `default` / `gpt-5.6-sol` when last verified |

The two skill copies initially installed at:

```text
C:\Users\muniz\AppData\Local\hermes\skills\devops\hermes-cross-runtime-bridge\SKILL.md
/home/muniz/.hermes/skills/devops/hermes-cross-runtime-bridge/SKILL.md
```

were byte-identical at installation time. Do not treat the old hash as a permanent invariant after either copy is improved.

## Exact native discovery

`hermes skills inspect NAME` resolves registry/source candidates and is not the correct proof that a local skill is installed. A local skill can be present and enabled while `skills inspect` says it was not found.

Use the installed-skill inventory instead:

```bash
# WSL
export HERMES_HOME=/home/muniz/.hermes
export COLUMNS=240
hermes skills list --source local --enabled-only | rg 'hermes-cross-runtime-bridge'
```

```powershell
# Windows
$env:HERMES_HOME='C:\Users\muniz\AppData\Local\hermes'
$env:COLUMNS='240'
$h='C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe'
$out = & $h skills list --source local --enabled-only 2>&1 | Out-String -Width 300
if ($out -notmatch 'hermes-cross-runtime-bridge') {
    throw 'local skill not discovered'
}
```

Force a wide output width before matching long names. Rich tables truncate names at narrow widths and can create false negatives.

## WSL to Windows identity probe

Always reset Windows `HERMES_HOME` inside the native PowerShell process. WSLInterop can otherwise pass `/home/muniz/.hermes` into Win32 and make a Windows executable inspect the WSL home.

```bash
WIN_PWSH='/mnt/c/Program Files/PowerShell/7/pwsh.exe'
"$WIN_PWSH" -NoProfile -Command '
  $env:HERMES_HOME="C:\Users\muniz\AppData\Local\hermes"
  Set-Location "C:\Users\muniz"
  $h="C:\Users\muniz\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe"
  & $h --version
  & $h config path
'
```

Require both paths in the output to be Windows-native.

## Windows to WSL identity probe

```powershell
$cmd = 'export HERMES_HOME=/home/muniz/.hermes; export PATH=/home/muniz/.local/bin:/home/muniz/.hermes/hermes-agent/venv/bin:$PATH; hermes --version; hermes config path'
wsl.exe -d Ubuntu-24.04 -u muniz -- bash -lc $cmd
```

Require `/home/muniz/.hermes/config.yaml` in the output.

## Content-equivalence proof

From WSL:

```bash
sha256sum \
  /home/muniz/.hermes/skills/devops/hermes-cross-runtime-bridge/SKILL.md \
  /mnt/c/Users/muniz/AppData/Local/hermes/skills/devops/hermes-cross-runtime-bridge/SKILL.md
```

Use this only when the goal is strict mirroring. If platform-specific divergence is intentional, compare and document the semantic difference instead.

## Session database safety

The Windows and WSL `state.db` files are independent. Query each with its native Hermes CLI. If a native CLI reports physical SQLite corruption, preserve DB/WAL/SHM and recover from a native-filesystem copy; do not repeatedly query or repair the live file over `/mnt/c` or UNC.
