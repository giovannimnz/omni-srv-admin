# Landscape / Omni Parity for CVE, USN and Package Governance

**Date:** 2026-06-25  
**Scope:** Phase 32 parity between Landscape self-hosted and Omni Fleet.

## Decision

Landscape self-hosted provides the Ubuntu machine-management UI and package activity surface.

Omni Fleet provides governance, audit, desired-state profiles, security snapshots and approved update-plan execution.

No CVE/USN fix is applied automatically from reporting. `pro fix` is allowed only as `--dry-run` for inspection or as part of an explicitly approved update plan.

## Parity Matrix

| Capability | Landscape self-hosted | Omni Fleet | Decision |
|---|---|---|---|
| Registered Ubuntu machines | Primary UI/API for the five managed hosts | Inventory/source-of-truth projection | Both are used; Omni owns reviewed identity |
| Package alerts | Landscape package upgrade/alert UI | `TbPrograms`, `TbVersions`, collector cache | Landscape is operator UI; Omni records audit/governance state |
| CVE/USN visibility | Landscape package/security evidence where available | `omni fleet security report` from Ubuntu Pro Client | Omni centralizes snapshots for policy decisions |
| Repository profiles | Landscape repository profiles where useful | `TbRepositoryProfiles`, desired-state rules | Omni owns policy; Landscape can execute machine-side activities |
| Update execution | Landscape activities/scripts | `TbUpdatePlans` + local agent | High-risk changes need explicit gate |
| Workload operations | Not a K3s controller | Not a workload UI | K3s/Portainer own workloads |

## Omni Commands

Read-only local security report:

```bash
PYTHONPATH=cli python3 -m omni fleet security report --host atius-srv-1 --json
```

Optional DB snapshot through PgBouncer:

```bash
PYTHONPATH=cli python3 -m omni fleet security report --host atius-srv-1 --db --json
```

Parity matrix:

```bash
PYTHONPATH=cli python3 -m omni fleet landscape-parity --json
```

## Ubuntu Pro Inputs

The Omni security report is based on read-only Ubuntu Pro Client commands:

```bash
pro status --format json
pro security-status --format json
pro cves --format json
```

Manual investigation for one CVE/USN can use:

```bash
pro fix --dry-run CVE-YYYY-NNNN
pro fix --dry-run USN-NNNN-N
```

Do not run `pro fix` without an explicit approval gate.

## Storage

Local cache:

```text
~/.logs/fleet/security/<host>.json
```

DB table:

```text
TbSecurityFindings
```

The table stores normalized fields and redacted evidence. It must not store Ubuntu Pro tokens, Landscape API secrets or package-manager credentials.
