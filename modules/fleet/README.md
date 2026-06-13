# fleet — multi-computer operations

## Goal

Manage Giovanni's computers and servers from `omni-srv-admin` without hardcoding SRV-1 assumptions into every automation.

## Scope

Supported categories:
- Oracle OCI servers: ATIUS-SRV-1/2/3
- Android Termux host: Giovanni-S23-Termux
- Android Ubuntu PRoot: Giovanni-S23-PRoot
- Personal workstation: Dell Inspiron 3520 Ubuntu 26.04
- Temporary authorized support hosts

## Rules

- Every managed host has a file in `inventory/hosts/<id>.yaml`.
- Host-specific scripts live in `modules/<host-or-domain>/`.
- Cross-host logic lives in `modules/fleet/` or a reusable domain module.
- Never run SRV-1 scripts on another host unless the host profile explicitly enables the module.
- Remote support requires explicit scope, backup, and audit log.

## Planned CLI

```bash
omni fleet list
omni fleet show atius-srv-1
omni fleet status --all
omni fleet validate-inventory
omni fleet install server --host atius-srv-1
omni fleet install node --host atius-srv-2
omni fleet heartbeat --host atius-srv-1 --json
omni fleet programs --host atius-srv-1 --json
omni fleet update-plan --host atius-srv-1 --program fork-sync --desired-version v4.1 --json
omni fleet ssh atius-srv-2
omni fleet run atius-srv-3 'df -h /'
omni fleet sync-module srv1-ops --target atius-srv-2 --dry-run
omni fleet backup-plan atius-srv-1
```

The control-plane commands above are safe M004 contracts. They render dry-run
plans and status payloads; live `--apply` execution remains blocked until the
human gates in `docs/fleet/control-plane.md` pass.

## Directory layout

```text
omni-srv-admin/
├── inventory/
│   ├── hosts/
│   │   ├── atius-srv-1.yaml
│   │   ├── atius-srv-2.yaml
│   │   ├── atius-srv-3.yaml
│   │   ├── giovanni-s23-termux.yaml
│   │   ├── giovanni-s23-proot.yaml
│   │   ├── dell-inspiron-3520.yaml
│   │   └── support-template.yaml
│   ├── groups/
│   └── remotes/
│       └── srv1-shared-smb.yaml
└── modules/fleet/
    ├── README.md
    ├── docs/
    ├── scripts/
    └── configs/
```

## Implementation phases

### Phase 1 — inventory only
- Host YAMLs.
- `omni fleet list/show`.
- No remote execution.

### Phase 2 — read-only remote probes
- SSH status checks.
- `df`, uptime, OS facts, service list.
- Output to `~/.logs/fleet/`.

### Phase 3 — module deployment
- Sync selected module to target.
- Dry-run first.
- Backup target files before overwrite.

### Phase 4 — controlled operations
- Install/update packages.
- Enable timers.
- Run backup/cleanup.
- All destructive operations require explicit flag.

## Host class differences

| Class | Scheduler | Paths | Notes |
|---|---|---|---|
| OCI Ubuntu | systemd user/system | `/home/ubuntu` | canonical server path |
| Termux | cronie + runsv | `/data/data/com.termux/files/home` | no systemd |
| PRoot Ubuntu | limited systemd | `/home/ubuntu` | do not assume services work |
| Desktop Ubuntu | systemd user | `/home/<user>` | personal data caution |
| Support host | unknown | scoped | temporary, audited |

## Links

- `../../inventory/hosts/`
- `../../inventory/remotes/`
- `../remote-manager/README.md`
- `../srv1-ops/README.md`
