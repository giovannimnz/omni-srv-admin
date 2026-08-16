---
name: hermes-wslinterop-restore
description: 'Use when WSL shell startup prints the stale-cache interop warning or when powershell.exe/cmd.exe inside WSL fail with Exec format error because /proc/sys/fs/binfmt_misc/WSLInterop is missing.'
version: 1.0.0
author: Hermes Agent
platforms: [windows, linux]
metadata:
  hermes:
    tags: [hermes, windows, wsl, interop, binfmt_misc, troubleshooting, self-heal]
---

# Hermes WSLInterop Restore

Dedicated fix path for the specific WSL failure where Windows binary interop disappears inside Ubuntu WSL even though the Windows host itself is healthy.

## When to Use

Use this skill when one or more of these happen inside WSL:

- shell startup prints `wsl-sync-windows-env: Windows interop unavailable; using stale cache (OSError)`
- `powershell.exe` fails with `cannot execute binary file: Exec format error`
- `cmd.exe` fails with `cannot execute binary file: Exec format error`
- `/proc/sys/fs/binfmt_misc/status` exists but `/proc/sys/fs/binfmt_misc/WSLInterop` is missing
- `systemctl status systemd-binfmt` shows the WSL condition skipped the normal binfmt restore path

## Scope Classification

This is a WSL runtime problem, not a native Windows 11 shell-profile problem.

Do not burn time editing Windows PowerShell profiles first when:

- the Win32 executables are present in WSL PATH
- execution fails before the command body runs
- the missing object is `/proc/sys/fs/binfmt_misc/WSLInterop`

## Fast Diagnosis

Run these checks inside WSL:

```bash
ls /proc/sys/fs/binfmt_misc
cat /proc/sys/fs/binfmt_misc/status
ls -l /proc/sys/fs/binfmt_misc/WSLInterop
powershell.exe -NoProfile -Command 'Write-Output INTEROP_OK'
cmd.exe /c echo CMD_OK
systemctl status systemd-binfmt --no-pager -l || true
```

Interpretation:

- if `status` exists, `WSLInterop` is missing, and `powershell.exe`/`cmd.exe` fail with `Exec format error`, the root cause is confirmed
- if `systemd-binfmt` says `ConditionVirtualization=!wsl was not met`, normal systemd restoration is not going to save you here

## Immediate Live Repair

```bash
sudo sh -c "printf ':WSLInterop:M::MZ::/init:PF' > /proc/sys/fs/binfmt_misc/register"
```

Then re-test immediately:

```bash
powershell.exe -NoProfile -Command 'Write-Output INTEROP_OK'
cmd.exe /c echo CMD_OK
/home/muniz/.local/bin/wsl-sync-windows-env --refresh >/tmp/out 2>/tmp/err && wc -c /tmp/err
zsh -lic 'powershell.exe -NoProfile -Command "Write-Output ZSH_OK"'
```

Expected:

- `INTEROP_OK`
- `CMD_OK`
- refresh stderr size `0`
- zsh login path works again

## Persistent Self-Heal

If the entry disappeared once on this host, install a WSL-local self-heal because the normal binfmt unit may be skipped under WSL.

### Script

Create `/usr/local/sbin/ensure-wslinterop`:

```bash
sudo tee /usr/local/sbin/ensure-wslinterop >/dev/null <<'EOF'
#!/bin/sh
set -eu
if [ ! -e /proc/sys/fs/binfmt_misc/status ]; then
  exit 0
fi
if [ -e /proc/sys/fs/binfmt_misc/WSLInterop ]; then
  exit 0
fi
printf ':WSLInterop:M::MZ::/init:PF' > /proc/sys/fs/binfmt_misc/register
EOF
sudo chmod 0755 /usr/local/sbin/ensure-wslinterop
```

### systemd unit

Create `/etc/systemd/system/wslinterop-restore.service`:

```bash
sudo tee /etc/systemd/system/wslinterop-restore.service >/dev/null <<'EOF'
[Unit]
Description=Restore WSL Windows interop binfmt entry
DefaultDependencies=no
After=local-fs.target proc-sys-fs-binfmt_misc.mount systemd-modules-load.service
Before=multi-user.target
ConditionPathExists=/proc/sys/fs/binfmt_misc/register

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/ensure-wslinterop
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable wslinterop-restore.service
sudo systemctl restart wslinterop-restore.service
```

## Persistence Proof

Do not stop at `systemctl status`. Prove the self-heal:

```bash
sudo sh -c 'echo -1 > /proc/sys/fs/binfmt_misc/WSLInterop'
systemctl restart wslinterop-restore.service
cat /proc/sys/fs/binfmt_misc/WSLInterop
```

Expected restored entry:

```text
enabled
interpreter /init
flags: PF
offset 0
magic 4d5a
```

## Validation Checklist

Use this exact post-fix validation:

```bash
powershell.exe -NoProfile -Command 'Write-Output INTEROP_OK_FINAL'
cmd.exe /c echo CMD_OK_FINAL
/home/muniz/.local/bin/wsl-sync-windows-env --refresh >/tmp/wsl-sync-refresh.out 2>/tmp/wsl-sync-refresh.err
wc -c /tmp/wsl-sync-refresh.err
zsh -lic 'powershell.exe -NoProfile -Command "Write-Output ZSH_OK_FINAL"' >/tmp/zsh.out 2>/tmp/zsh.err
wc -c /tmp/zsh.err
cat /tmp/zsh.out
systemctl status wslinterop-restore.service --no-pager -l
```

Healthy result:

- interop commands run
- both stderr files are `0` bytes
- `wsl-sync-windows-env` imports fresh env again
- service is `active (exited)` and successful

## Common Mistakes

- treating it as a native Windows 11 profile issue before checking `/proc/sys/fs/binfmt_misc/WSLInterop`
- trusting `systemd=true` in `/etc/wsl.conf` as proof that binfmt restoration is already covered
- validating only `powershell.exe` and forgetting `zsh -lic ...` plus `wsl-sync-windows-env --refresh`
- stopping after the temporary register without installing a persistence path on a host that has already lost `WSLInterop`

## Related Assets

- Umbrella skill: `hermes-windows-wsl`
- Obsidian note: `runbooks/hermes-wslinterop-restore.md`
- GBrain page: `runbooks/hermes-wslinterop-restore`
- Skill reference file: `references/related-docs.md`

## See Also

- `skill_view(name="hermes-windows-wsl")`
- `skill_view(name="hermes-wslinterop-restore", file_path="references/related-docs.md")`
