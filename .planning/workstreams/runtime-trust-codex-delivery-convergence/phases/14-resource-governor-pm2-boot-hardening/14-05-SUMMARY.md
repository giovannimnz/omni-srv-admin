---
phase: 14-resource-governor-pm2-boot-hardening
plan: 05
subsystem: srv1-ops
tags: [podman, jenkins, docker-deps, system-cleanup, public-validation]
requires:
  - phase: 14
    provides: "Phase 14 context, RGP-08/09/10 requirements, M006 boot-hardening baseline"
provides:
  - "Jenkins rodando 100% em Podman (sem /var/run/docker.sock, sem /usr/bin/docker)"
  - "container-jenkins.service systemd user unit limpo e validado live"
  - "Validação externa em https://jenkins.atius.com.br/ (x-jenkins header + login form)"
  - "Inventory de outros servicos orfaos de Docker (gate para 14-06+)"
affects: [srv1-ops, jenkins, podman-runtime, public-edge-validation]
tech-stack:
  added: []
  patterns: ["no Docker-orfao bind mounts em servicos que migraram pra Podman", "validacao externa via dominio publico + headers"]
key-files:
  created:
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-05-PLAN.md
  modified:
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-PLAN.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md
  live_only:
    - /home/ubuntu/.config/systemd/user/container-jenkins.service
    - /home/ubuntu/GitHub/containers/jenkins/podman-compose.yml
key-decisions:
  - "Remover /var/run/docker.sock e /usr/bin/docker do unit/compose: Docker foi desinstalado no cutover Docker→Podman e os paths causavam exit 125 (statfs ENOENT)"
  - "Manter /usr/lib/aarch64-linux-gnu/libltdl.so.7 (necessário pro agente Jenkins) e /home/ubuntu/GitHub/atius (workspace RO)"
  - "Validacao externa obrigatoria em https://jenkins.atius.com.br/ (Cloudflare → Apache → 127.0.0.1:8085 → podman)"
patterns-established:
  - "Para qualquer container Podman: rodar `statfs /var/run/docker.sock` na preflight; falhar se path nao existir"
  - "Public domain validation: curl -I https://<service>.atius.com.br/ e checar header `x-jenkins`/`x-*` esperado"
requirements-completed:
  - RGP-08
  - RGP-09
  - RGP-10
duration: 30 min
status: complete
---

# Phase 14 Plan 05: Jenkins + servicos orfaos: remover deps Docker e validar em dominio publico — Summary

**Jenkins migrado 100% para Podman. Bind mounts Docker-orfaos removidos. Validado externamente em https://jenkins.atius.com.br/ (x-jenkins 2.541.3).**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-06-15T11:24:00Z
- **Completed:** 2026-06-15T11:28:00Z
- **Tasks:** 4
- **Files modified:** 2 live + 3 planning + 1 inventory + 1 CLI

## Accomplishments

- Reconciled `container-jenkins.service` que estava em restart loop (9+ attempts, status 125) devido a bind mounts para paths Docker-orfãos.
- Reescreveu o systemd user unit e o `podman-compose.yml` sem `/var/run/docker.sock` e `/usr/bin/docker`.
- Manteve o `/usr/lib/aarch64-linux-gnu/libltdl.so.7` (lib do agente Jenkins) e o mount de workspace `/home/ubuntu/GitHub/atius` (RO).
- Subiu o container e validou resposta local + externa.
- Registrou Jenkins no rastreamento de apps do omni (`inventory/hosts/atius-srv-1.yaml`) e estendeu `_program_records` no `cli/omni/fleet.py` pra ler a nova seção `apps`.
- Adicionou requirements RGP-08/09/10 ao 14-PLAN e wave 4 com gate de validação externa em `jenkins.atius.com.br`.

## Task Commits

1. **14-05 live + planning** - `230facfc9` (`feat(14-05/14-06)`)
   - container-jenkins.service reescrito
   - podman-compose.yml limpo
   - 14-05-PLAN.md criado
   - 14-PLAN.md atualizado (RGP-08/09/10, wave 4)
   - STATE/REQUIREMENTS atualizados

## Files Created/Modified

### Live (systemd + podman)
- `/home/ubuntu/.config/systemd/user/container-jenkins.service` — reescrito (1471 bytes), remove docker.sock e docker binary mounts
- `/home/ubuntu/GitHub/containers/jenkins/podman-compose.yml` — reescrito (449 bytes), remove os mesmos mounts

### Planning
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-05-PLAN.md` — novo (6096 bytes)
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-PLAN.md` — atualizado (wave 4, RGP-08/09/10)
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md` — entry Jenkins + plan 14-05/06 added
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md` — RGP-08/09/10 marked complete

### Inventory + CLI
- `inventory/hosts/atius-srv-1.yaml` — apps section com 7 entries (jenkins, jenkins-agent, cloudbeaver, redis, postgres, router-ai-atius, rclone-gdrive-mount)
- `cli/omni/fleet.py` — `_program_records` estendido pra ler modules + apps

### Backups
- `/home/ubuntu/.config/systemd/user/container-jenkins.service.bak.20260615_082613` — pre-fix state
- `/home/ubuntu/GitHub/containers/jenkins/podman-compose.yml.docker-deps-20260615.bak` — pre-fix state

## Decisions Made

- **Remover (não substituir) os mounts Docker-orfãos:** o caso de uso DinD não é mais viável (Docker daemon uninstalled), e o caminho correto é Jenkins agent no K3s (14-06) usando Podman/buildah em pods efêmeros.
- **Manter libltdl + workspace mounts:** ambos ainda válidos pro caso de uso atual.
- **Validar externamente:** workflow pattern pra todos os serviços omni-srv-admin — curl em `https://<service>.atius.com.br/` + checar header esperado.

## Deviations from Plan

Nenhuma. Plano foi escrito e executado conforme planejado.

## Issues Encountered

Nenhum. Unit subiu limpo, resposta local + externa OK.

## Verification

```bash
# Service status
$ systemctl --user is-active container-jenkins.service
active

# Local health check
$ curl -sI http://127.0.0.1:8085/ | grep x-jenkins
x-jenkins: 2.541.3

# External public-domain validation
$ curl -sI -L https://jenkins.atius.com.br/ | grep -E "x-jenkins|HTTP"
HTTP/2 403
x-jenkins: 2.541.3

# Mounts no longer reference Docker
$ grep -E "docker.sock|/usr/bin/docker" /home/ubuntu/.config/systemd/user/container-jenkins.service
# (empty)
```

## User Setup Required

None — Docker socket não era mais usado por jobs ativos (validado inspecionando `/var/jenkins_home/jobs` via container).

## Next Phase Readiness

Pronto pra `14-06` (Jenkins agent on K3s) e `14-02/03/04` (PM2 + XRDP hardening).

Builds que precisariam de DinD agora vão via Jenkins agent no K3s (14-06) com `podman build` em pods efêmeros.

---

*Phase: 14-resource-governor-pm2-boot-hardening*
*Plan: 14-05*
*Completed: 2026-06-15*
