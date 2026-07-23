---
phase: 14
padded: 14
slug: resource-governor-pm2-boot-hardening
name: Validation Architecture
date: 2026-06-13
status: ready
---

# Phase 14: Validation Architecture

## Validation Layers

### Layer 1: Static

- `python3 -m py_compile` para CLI e scripts Python do governor.
- `bash -n` para scripts shell.
- `git diff --check`.
- `systemd-analyze verify --user` quando disponivel para units user
  versionadas.

### Layer 2: Read-Only Live

- `systemctl --user list-jobs`.
- `systemctl --user status ... --no-pager`.
- `systemctl --user show ...`.
- `systemctl cat pm2-ubuntu.service`.
- `pm2 jlist` e `pm2 ls`.
- `nc -z` para portas locais.
- Leitura de `/sys/fs/cgroup`.

### Layer 3: Low-Impact Apply

- `systemctl --user daemon-reload`.
- `systemctl --user enable --now` apenas para governor/inviolable units da fase
  depois de static/read-only OK.
- Execucao de `resource-governor-status.py`.

### Layer 4: Gated Live

Exige aprovacao explicita:

- `systemctl --user stop/restart/disable --now ats-pm2.service`.
- `systemctl --user stop/restart/disable --now horistic-pm2.service`.
- `systemctl restart pm2-ubuntu.service`.
- `pm2 kill`, `pm2 delete`, `pm2 resurrect`.
- Restart de `xrdp.service`.
- Reboot do host.

## Requirement Test Map

| Requirement | Validation |
|-------------|------------|
| RGP-01 | `systemctl --user list-jobs`, unit graph sem dependencia critica de `default.target` |
| RGP-02 | Comparar `resource-governor.env`, runtime override, `systemctl --user show omni-*.slice` e cgroups diretos |
| RGP-03 | `systemctl cat pm2-ubuntu.service`, user units PM2, grep por `/home/ubuntu/ecosystem.atius.js` |
| RGP-04 | Jobs PM2/default ausentes ou documentados como gated, PM2 apps online |
| RGP-05 | `inviolable-watchdog.sh` usa ecosystems reais, ignora nginx ausente, transient units para XRDP/SSHD |
| RGP-06 | Runbook classifica impacto de cleanup PM2/XRDP |
| RGP-07 | Docs/vault incluem rollback, backup e checklist pos-boot |

## Abort Criteria

- `atius-web`, `horistic-api`, `atius-api` ou `atius-webhook-signals` ficam
  offline apos acao da fase.
- Porta 3015, 8050, 8015 ou 8199 fecha sem motivo esperado.
- Sessao XRDP atual cai fora de janela aprovada.
- Aparece PM2 daemon novo nao documentado.
- `resource-governor-patcher.service` ou `resource-governor-watchdog.service`
  falha apos daemon-reload/start.
