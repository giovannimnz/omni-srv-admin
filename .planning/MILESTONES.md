# Milestone Branch Matrix

**Last updated:** 2026-06-15

Este arquivo deve existir em `main` e nas branches de planejamento para deixar
clara a ordem dos milestones e onde cada plano completo vive.

## Correct Order

| Milestone | Phase | Name | Canonical branch | Full artifacts | Status |
|---|---:|---|---|---|---|
| M004 | 12 | Omni Fleet Control Plane | `codex/omni-fleet-control-plane-m004` | `.planning/phases/12-omni-fleet-control-plane/` | Live implemented; repos, central DB, PgBouncer node path and DB-backed ops/config/slash registry validated |
| M005 | 13 | K3s HA Cluster + Portainer | `codex/k3s-portainer-oci-plan` | `.planning/phases/13-k3s-ha-portainer-oci/` | Execution checkpoint blocked before live mutation |
| M006 | 14 | SRV-1 Resource Governance + PM2 Hardening | `codex/phase14-resource-governor-14-01` | `.planning/phases/14-resource-governor-pm2-boot-hardening/` | In progress; 14-01 complete |

## Separation Rule

- Fleet branch contains the full M004/Phase 12 plan and only references K3s.
- K3s branch contains the full M005/Phase 13 plan and references Fleet as a prerequisite.
- `main` keeps the shared milestone/branch index and roadmap visibility; full plan artifacts should arrive via their canonical branches.

## Dependency

M004 comes before M005 because Fleet Control Plane defines the operational base:
inventory, server/node install contract, central PostgreSQL via PgBouncer,
per-host ops scopes, DB-backed configs/parameters, CLI-Anything slash-command
registry, program registry, versions/update plans, license metadata, audit logs
and the future contract consumed by Podman/K3s.

M005 must not be executed before:

- M004 live implementation remains healthy on SRV-1/SRV-2/SRV-3.
- SRV-1/SRV-2/SRV-3 are on Ubuntu 24.04.
- Preflight for `ATIUS-SRV-1`, `ATIUS-SRV-2`, `ATIUS-SRV-3` passes.
- OCI snapshots/backups, public-ingress closure in each OCI account and host firewall rules for `wg0` are confirmed.
- Cloudflare Tunnel token is supplied out-of-band.
- Portainer exposure target remains `portainer.atius.com.br`.
- PTP fallback mesh is designed and validated before production-ready.
