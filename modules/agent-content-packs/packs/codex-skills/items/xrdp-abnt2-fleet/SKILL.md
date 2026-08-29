---
name: xrdp-abnt2-fleet
description: Deploy, validate, and recover the ATIUS XRDP ABNT2 keyboard guard across SRV-1, SRV-2, SRV-3, and Horistic without disrupting active RDP sessions.
---

# XRDP ABNT2 Fleet

Use for keyboard-layout, extended-key, clipboard-adjacent XRDP session issues on
Atius Ubuntu desktop hosts.

## Read first

- `modules/xrdp-abnt2/README.md`
- `docs/operations/ubuntu-arm64-xrdp-desktop-standard.md`
- `cli/omni/xrdp_abnt2.py`

## Contract

- Target hosts are `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and
  `horistic-srv`.
- The live XRDP 0.9.24 map uses xfree86/base indexes: Up `Key98`, Left
  `Key100`, Right `Key102`, Down `Key104`, Delete `Key107`, Print `Key111`,
  ABNT_C1 `Key123`. Do not validate them against evdev offsets.
- Use `sudo -n python3 cli/omni/xrdp_abnt2.py install --user "$USER" --yes`.
  It creates a per-host backup and must not restart `xrdp` or `xrdp-sesman`.
- The `xrdp-abnt2-reconcile.timer` is the persistent drift guard. It reapplies
  files only; validate it is enabled and active after deployment.
- Do not use the packaged `omni` command until its installed asset path is
  proven. The checkout entrypoint is canonical for a live rollout.

## Procedure

1. Capture hostname, active XRDP sessions, `validate`, `diff`, current hashes,
   and timer state through SSH. Use both documented private/public fallback
   paths before declaring a host unreachable.
2. Confirm the reviewed repository and run syntax plus focused tests.
3. Run the installer on one host at a time. Record the backup path it prints.
4. Verify `validate`, `diff`, keymap SHA-256 parity, and timer enabled/active.
5. Require a new Microsoft RDP session to test arrows, Delete, Print Screen,
   `/`, `?`, AltGr symbols and clipboard. SSH cannot prove client input.
6. Record sanitized evidence in Obsidian and GBrain; never include secrets.

## Guardrails

- Never restart XRDP for this task unless the operator explicitly authorizes it.
- Never manually edit `/etc/xrdp/km-*.ini`; repair from the canonical module.
- Preserve and report backups before writing.
- Treat Landscape as optional inventory evidence; it is not a substitute for
  host-level file/hash/session validation.
