---
phase: 12
padded: 12
slug: omni-fleet-control-plane
name: Fleet Control Plane Foundation
date: 2026-06-13
status: ready
wave: 1
depends_on: []
autonomous: false
files_modified:
  - .planning/ROADMAP.md
  - .planning/REQUIREMENTS.md
  - .planning/STATE.md
  - .planning/config.json
  - .planning/phases/12-omni-fleet-control-plane/12-CONTEXT.md
  - .planning/phases/12-omni-fleet-control-plane/12-RESEARCH.md
  - .planning/phases/12-omni-fleet-control-plane/12-01-PLAN.md
requirements_addressed:
  - FCP-01
  - FCP-02
  - FCP-03
  - FCP-04
  - FCP-05
  - FCP-06
  - FCP-07
  - FCP-08
  - FCP-09
  - FCP-10
---

# Phase 12 — Master Plan

## Goal

Criar a fundação planejada do Omni Fleet Control Plane para que o
`omni-srv-admin` controle a frota antes de instalar K3s/Portainer: modo
`server`/`node`, inventário como fonte de verdade, PostgreSQL central via
PgBouncer, heartbeat/status, registry de programas, version/update plans,
licenças sem secrets e auditoria.

## Scope

Esta phase é de planejamento e contrato. Ela não instala K3s, não migra
workloads, não muda Portainer e não executa alterações destrutivas nos hosts.

## Architecture

```text
M004 Fleet Control Plane
  server:
    - PostgreSQL
    - PgBouncer
    - migrations
    - inventory importer
    - scheduler/update planner
    - audit registry

  node:
    - agent
    - heartbeat/status
    - program/version reporter
    - approved update executor

M005 K3s/Portainer
  - consumes M004 inventory/state/audit contracts
```

## Plans

| ID | Name | Status | Notes |
|---|---|---|---|
| 12-01 | Fleet Control Plane Foundation | ready | Planning contract and implementation checklist |

## Hard Gates

- No raw secrets, license keys or tokens in git, logs, `.planning` or vault.
- PgBouncer is mandatory for node/client DB access.
- Inventory remains source-of-truth; DB stores operational state/projections.
- Destructive update execution must require an approved update plan.
- K3s/Podman work stays deferred to M005+.

## Acceptance

- `FCP-01..FCP-10` exist in `.planning/REQUIREMENTS.md`.
- ROADMAP shows `M004 / Phase 12` as Fleet Control Plane and `M005 / Phase 13`
  as K3s HA Cluster + Portainer.
- Phase artifacts exist under `.planning/phases/12-omni-fleet-control-plane/`.
- K3s artifacts are renumbered under `.planning/phases/13-k3s-ha-portainer-oci/`.
- STATE/config point to M004 Phase 12 as active and M005 Phase 13 as planned.
