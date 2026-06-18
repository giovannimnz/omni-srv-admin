phase: 20
plan: 20-01
title: "Podman Networking Standardization — fleet-wide containers.conf + netavark + aardvark"
date: 2026-06-17
status: complete
---

# Phase 20 — Plan 20-01 SUMMARY

## Origem

Phase surgiu do cutover **plane-app v1.2.1 → v1.3.1** no SRV-1 em 2026-06-16. Durante o cutover, descobri 3 bugs latentes que afetavam todos os 3 servers:

1. Aardvark-dns 1.4.0 self-lookup NXDOMAIN (rootless bug)
2. `systemd-resolved` ausente no SRV-2 (mailcow Exited 45h por isso)
3. `containers.conf` drift entre servers (default_network errado, sem netavark)

Em vez de consertar pontualmente, o trabalho virou uma **padronização fleet-wide** consolidada em skill + módulo omni-srv-admin.

## Mudanças aplicadas (resumo)

### SRV-1 (10.1.1.1) — production

- ✅ `containers.conf.d/99-netavark.conf` criado
- ✅ `srv1-podman-v2` network criada (10.10.11.0/24, dns=true, netavark)
- ✅ 6 services + 1 pod migrados de CNI → netavark
- ✅ plane-app v1.3.1 rodando (13 containers, network `atius` 10.89.1.0/24 com extra_hosts)
- ✅ https://plane.atius.com.br/ → HTTP 200

### SRV-2 (10.1.1.2) — development

- ✅ `containers.conf` corrigido (`default_network=podman → srv2-podman`)
- ✅ `containers.conf.d/99-netavark.conf` criado
- ✅ Network `podman` (10.10.200.0/24) legada removida
- ✅ `systemd-resolved` instalado (fix mailcow Exited 45h)
- ✅ `podman-compose` 1.6.0 reinstalado

### SRV-3 (10.1.1.7) — sandbox

- ✅ `srv3-podman` recriada com `dns_enabled=true`
- ✅ `containers.conf.d/99-netavark.conf` criado
- ✅ k3s cluster validado (3/3 Ready)
- ✅ `podman-compose` 1.0.6 (apt) mantido (funcional, divergência menor)

## Materialização

| Output | Path | Tamanho |
|--------|------|---------|
| Skill | `~/.hermes/skills/devops/podman-fleet-standardize/` | 12 files |
| Módulo | `~/GitHub/omni-srv-admin/modules/fleet/podman-network/` | 12 files |
| CLI | `omni podman-network {drift,apply,smoke,standard}` | 4 subcommands |
| Doc | `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` | v1.2.0 |
| README | `omni-srv-admin/README.md` TL;DR | 3 novos comandos |

## Validação final

```
$ omni podman-network drift
=== Podman Fleet Standard Drift Check ===
default_network = srv<N>-podman: PASS
default_subnet = 10.10.<N>.0/24: PASS
99-netavark.conf = netavark: PASS
srv<N>-podman has dns=true (accepts -v2): PASS
systemd-resolve dir non-empty (>=3): PASS
systemd-resolved active: PASS
=== 6/6 PASS on SRV-1, SRV-2, SRV-3 ===
```

## Issues remanescentes (não-bloqueantes)

- SRV-1: `srv1-podman` (CNI legada) preservada (0 containers, não interfere)
- SRV-2: `atius-shared` (CNI legada) preservada, mailcow não usa
- SRV-2: binários CNI `/usr/lib/cni/` presentes (coexiste com netavark, suportado)
- SRV-3: `podman-compose` 1.0.6 vs 1.6.0 (funcional, divergência menor)

## Commits

- `c0543a9de feat(podman-network): fleet-wide podman networking standard + skill` (16 files, 1741 insertions)
- `5077660c7 chore(state): record session continuity (resumed via gsd-resume-work 2026-06-17)`

## Backups

- `~/backups/plane-app-2026-06-16/` (5 files)
- `~/backups/podman-fleet-standardize-2026-06-16/` (2 srv-containers + srv1-systemd-units/)

## Cross-refs

- `20-01-PLAN.md` (planejamento original)
- `vault/60-LOGS/2026-06-16-plane-app-podman-v131-cutover.md` (cutover origem)
- `vault/60-LOGS/2026-06-16-fleet-podman-network-standardize.md` (drift + materialização log)
- `omni-srv-admin/modules/fleet/podman-network/` (módulo canônico)
- `~/.hermes/skills/devops/podman-fleet-standardize/` (skill canônica)
- `docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` v1.2.0 (cross-ref)

## Status

✅ **Plan 20-01 DONE.** Phase 20 fechada. M008-b ship completa. Operator next steps unchanged: G18-1 (apt upgrade esm-apps+infra) + G18-2 (Microsoft RDP login validação) + Landscape SaaS UI confirmation.
