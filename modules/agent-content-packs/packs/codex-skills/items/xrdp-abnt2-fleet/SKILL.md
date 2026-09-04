---
name: xrdp-abnt2-fleet
description: Audit, diagnose, safely reconcile, validate, and document ATIUS XRDP ABNT2 keyboard drift on inventory-managed Ubuntu desktop hosts without disrupting active RDP sessions. Use for layout/keymap drift, guard packaging, and fleet closeout; not for XRDP authentication, display rendering, or unrelated Windows keyboard configuration.
---

# ATIUS XRDP ABNT2 Fleet

Use this as the single agent-facing workflow for the `xrdp-abnt2` module. The
repository module and CLI remain the executable source of truth; do not create
parallel repair scripts inside this skill.

## Scope and routing

Resolve targets from `inventory/hosts/*.yaml`. A host is in scope when it
declares `platform.desktop: lxde-xrdp` and module `xrdp-abnt2`. State the exact
included and excluded hosts before live work; never hard-code the historical
four-host rollout as the current fleet.

Use this skill for read-only fleet audit, keyboard/layout diagnosis, authorized
serial reconcile, rollback verification, wheel/asset parity, and GSD/GitHub/
knowledge closeout. Do not use it for XRDP authentication, TLS/trust, blank
framebuffer/display, desktop theme, RustDesk, or unrelated Windows keyboard
configuration. Route those to their owning runbook or skill.

## Canonical sources

From the current `omni-srv-admin` checkout, read in this order:

1. `modules/xrdp-abnt2/README.md` — desired state and installed files.
2. `docs/operations/ubuntu-arm64-xrdp-desktop-standard.md` — fleet operation,
   evidence and UAT.
3. `cli/omni/xrdp_abnt2.py` — actual install/validate/diff behavior.
4. `inventory/hosts/*.yaml` — current target membership and users.
5. `.planning/debug/xrdp-keyboard-fleet-drift.md` — historical RCA only.

Planning, transcripts, old Hermes skills and legacy scripts never override
these sources. If any appear, read `references/legacy-hermes-boundary.md`.

## Modes

- `audit`: live read-only status, hashes, logs, sessions and repository state.
- `diagnose`: audit plus evidence-led root cause and eliminated hypotheses.
- `reconcile`: authorized, backed-up, one-host-at-a-time installation.
- `recover`: verify automatic rollback/readback after a failed install; there
  is no public operator-requested rollback command, so do not improvise one.
- `package`: validate wheel assets, content-pack manifest and installed skill.
- `closeout`: GSD/Graphify, tests, PR/merge and knowledge records when the user
  requested those external mutations.

## Non-negotiable invariants

- XRDP `0.9.24` consumes `xfree86/base` indexes: Up `Key98`, Left `Key100`,
  Right `Key102`, Down `Key104`, Insert `Key106`, Delete `Key107`, Print Screen
  `Key111`, ABNT_C1 `Key123`. Do not validate against live evdev offsets.
- If the XRDP version changes, verify translation against installed/upstream
  source before carrying this mapping forward.
- Never edit `/etc/xrdp/km-*.ini`, `xrdp.ini` or `startwm.sh` manually.
- Never restart `xrdp` or `xrdp-sesman` without task-specific approval.
- Use `--install-packages` only after preflight proves packages missing;
  package installation is outside transactional rollback.
- Preserve dirty checkouts and active sessions. Stop at the first failed host.
- Do not expose credentials, cookies, Xauthority data or Vault values.

## Audit and diagnosis

1. Run Graphify status/query before choosing repo files; rebuild when stale.
2. Consult GBrain/Obsidian when history can affect the diagnosis.
3. Per host, capture hostname/user, inventory membership, repo SHA/dirty state,
   XRDP/TigerVNC versions, active sessions, `status`, `validate`, `diff`, hashes,
   timer/service properties, APT hook, backups and relevant logs.
4. For Horistic, probe private then public SSH before declaring it unreachable.
5. Treat mtimes and temporal proximity as evidence, not causality.

Use the reviewed checkout entrypoints:

```bash
python3 cli/omni/xrdp_abnt2.py status --user "$USER"
python3 cli/omni/xrdp_abnt2.py validate --user "$USER"
python3 cli/omni/xrdp_abnt2.py diff --user "$USER"
```

## Reconcile

1. Confirm the exact commit and focused tests. Route heavy tests/builds through
   the host resource governor at no more than 20% total host CPU.
2. Inventory active sessions and record the pre-state.
3. Run one host at a time:

```bash
sudo -n python3 cli/omni/xrdp_abnt2.py install --user "$USER" --yes
```

4. Record the printed backup. If prerequisites are missing, stop and review
   them before explicitly repeating with `--install-packages`.
5. If a host fails, prove rollback of files, mode, uid/gid and the prior states
   of `xrdp`, `xrdp-sesman`, reconcile service and timer before continuing.

## Health gate

Every changed host must satisfy all of these:

- `validate=PASS` and `diff=CLEAN` from the reviewed source;
- managed keymaps match the current canonical asset hash;
- `xrdp`, `xrdp-sesman` and reconcile timer enabled/active;
- reconciler `Result=success`, `ExecMainStatus=0`, and nonzero execution time;
- next trigger finite in realtime or monotonic; reject empty, `0`, `n/a`, and
  `infinity`;
- APT/DPKG hook and session watchdog point to canonical assets;
- no unapproved restart and pre-existing sessions remain present.

Enabled/active alone is never sufficient.

## Package and skill parity

- Prove wheel assets before trusting the installed `omni` executable.
- Validate the source skill with `skill-creator/scripts/quick_validate.py`.
- Update every changed file/hash/byte count and the aggregate item hash in the
  Codex content-pack manifest.
- Run `modules/agent-content-packs/scripts/agent-content-validate-all.sh` and a
  dry-run; compare source and installed skill trees by hash after local install.
- `agent-content sync --apply` for `ssh-linux` is intentionally fail-closed.
  Never bypass it; improve remote transaction separately if needed.

Landscape is optional inventory/activity evidence only. Use the self-hosted
profile only after it is resolved from Vault; never treat the historical SaaS
profile as authority or replace host-level evidence.

## Closeout

When authorized: run focused tests/content-pack validation/`git diff --check`;
obtain independent review; refresh Graphify; commit, PR, review, merge and
post-merge readback; then write sanitized Obsidian/GBrain records containing
observations, inference, backups, hosts, validation, residual risks and next
gate.

## Completion states

- `code-and-runtime-pass-awaiting-rdp-uat`: machine gates pass, but one or more
  hosts lack a new physical Microsoft RDP keyboard test.
- `complete`: every machine gate and physical UAT passed for every target.
- `blocked`: an explicit external dependency prevents safe progress.

Physical UAT must use a new Microsoft RDP session per host and cover arrows,
Insert, Delete, Print Screen, `/`, `?`, `°`, `¿`, accents/cedilla, AltGr and
clipboard. SSH, hashes, `setxkbmap`, or headless FreeRDP cannot replace it.
