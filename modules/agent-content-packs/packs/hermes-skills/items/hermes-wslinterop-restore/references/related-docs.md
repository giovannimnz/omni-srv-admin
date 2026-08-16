# Related Docs

This skill is backed by the following authoritative notes for this host:

- Obsidian: `runbooks/hermes-wslinterop-restore.md`
- GBrain: `runbooks/hermes-wslinterop-restore`
- Umbrella skill: `hermes-windows-wsl`

## What the linked docs contain

- root-cause classification: WSL runtime fault, not native Windows 11 profile issue
- live symptoms (`Exec format error`, stale cache fallback, missing `/proc/sys/fs/binfmt_misc/WSLInterop`)
- immediate repair command
- persistent systemd self-heal (`wslinterop-restore.service`)
- validation sequence for `powershell.exe`, `cmd.exe`, `wsl-sync-windows-env --refresh`, and `zsh -lic`
- persistence proof by deleting and restoring the `WSLInterop` binfmt entry

## Cross-reference policy

When this skill changes materially, update both linked docs.
When the docs discover a new failure mode or caveat, patch this skill.
