# Legacy Hermes and historical boundary

Read this reference only when old Hermes skills, legacy scripts, historical
transcripts or Phase 18 handoffs appear during XRDP/ABNT2 work.

## Evidence only — do not execute

- `~/.hermes/skills/devops/abnt2-keyboard-fix/`
- `~/.hermes/skills/devops/abnt2-keyboard-investigation/`
- `modules/srv1-ops/legacy-scripts/fix-abnt2.sh`
- `modules/xrdp-abnt2/docs/original-*.md`
- historical Phase 18 RDP handoffs and pre-August closure notes

These artifacts preserve chronology. Their discovery metadata and bodies may
still route to superseded commands even when a banner says deprecated.

## Mandatory translations

| Legacy advice | Current contract |
|---|---|
| Fixed `DISPLAY=:10` | Detect the active session; do not assume a display. |
| Loose scripts, xbindkeys or custom services | Use the canonical module and CLI. |
| Direct `sed`, `tee`, `nano` or copy into `/etc` | Use the transactional installer. |
| `systemctl restart xrdp*` | Prohibited by default; requires explicit approval. |
| Implicit `apt install` | Preflight, then explicit `--install-packages` only when needed. |
| `dpkg-reconfigure`, `udevadm trigger`, `pkill` | Not part of the canonical flow. |
| Hotkey success proves root cause | Invalid inference; require logs/maps and falsification. |
| `setxkbmap -query` alone proves success | Require hashes, XRDP map and timer health. |
| Historical IP/user/display/hash | Resolve inventory and live state again. |

Never copy secrets or Xauthority material from a historical transcript. If a
legacy file conflicts with the canonical module, runbook, CLI or current
inventory, the current sources win.
