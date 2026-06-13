---
phase: 12
padded: 12
slug: omni-fleet-control-plane
name: Fleet Control Plane Foundation
date: 2026-06-13
status: live-implemented
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
  - FCP-11
  - FCP-12
  - FCP-13
  - FCP-14
  - FCP-15
---

# Phase 12 — Master Plan

## Goal

Criar a fundação planejada do Omni Fleet Control Plane para que o
`omni-srv-admin` controle a frota antes de instalar K3s/Portainer: modo
`server`/`node`, inventário como fonte de verdade, PostgreSQL central via
PgBouncer, heartbeat/status, registry de programas, version/update plans,
agent executor local allowlisted, monitoramento cross-server, ops scopes por
servidor, parâmetros/configs no DB, slash commands via CLI-Anything, licenças
sem secrets e auditoria.

## Scope

Esta phase criou o contrato e a fundação live: repo nos 3 hosts, DB central no
SRV-1, PgBouncer para clients/nodes e migrations de runtime state. Ela não
instala K3s, não migra workloads e não muda Portainer.

## Architecture

```text
M004 Fleet Control Plane
  server:
    - PostgreSQL
    - PgBouncer
    - migrations
    - inventory importer
    - ops/config registry
    - slash command registry
    - scheduler/update planner
    - fleet telemetry reader
    - audit registry

  node:
    - agent
    - heartbeat/status
    - program/version reporter
    - approved update executor
    - resource telemetry collector

Future Podman/K3s integration
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
- PostgreSQL is canonical for ops scopes, mutable configs, runtime parameters
  and slash-command registry.
- Slash commands use CLI-Anything conventions.
- Destructive update execution must require an approved update plan, command allowlist and local execution by the target host's agent.
- Every SRV must be able to monitor the others through central telemetry and local fallback cache.
- K3s/Podman work stays deferred to a separate milestone/branch.

## Acceptance

- `FCP-01..FCP-15` exist in `.planning/REQUIREMENTS.md`.
- ROADMAP shows `M004 / Phase 12` as Fleet Control Plane.
- Phase artifacts exist under `.planning/phases/12-omni-fleet-control-plane/`.
- STATE/config point to M004 Phase 12 as active.
