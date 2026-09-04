# Multi-host rollout plan

## Phase 1 — inventory

- [x] Create host YAML files.
- [x] Create `modules/fleet/` docs.
- [ ] Add `omni fleet list`.
- [ ] Add `omni fleet show <host>`.

## Phase 2 — read-only probes

- [ ] `omni fleet status <host>` via SSH.
- [ ] Detect OS, arch, shell, scheduler, package manager.
- [ ] Write logs to `~/.logs/fleet/`.

## Phase 3 — module compatibility matrix

- [ ] Mark modules as compatible with host classes.
- [ ] `srv1-ops`: SRV-1 only.
- [ ] `xrdp-abnt2`: OCI Ubuntu with XRDP only; operar por
  `$xrdp-abnt2-fleet` (`modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`).
- [ ] `remote-manager`: OCI Ubuntu + Desktop Ubuntu, later Termux partial.
- [ ] `backup`: OCI Ubuntu + Desktop Ubuntu + PRoot, Termux variant.

## Phase 4 — remote execution

- [ ] Implement `omni fleet run <host> <command> --read-only`.
- [ ] Implement `--sudo` only with explicit flag.
- [ ] Add command audit log.

## Phase 5 — support mode

- [ ] `omni fleet support init <label>`.
- [ ] Temporary host profile.
- [ ] Incident/worklog required.
- [ ] No saved secrets.

## Validation

Each phase must validate:
- host inventory parse OK
- no secrets in host YAMLs
- command output shape OK
- logs written under `~/.logs`
- vault note updated
