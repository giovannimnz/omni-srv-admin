# Runtime contracts de aplicações SRV-1

Fonte versionada das units e compose files sanitizados recuperados em 2026-09-05.

## Aplicações

- `cloudbeaver/`: CloudBeaver 26.1.0, workspace H2 fora do repo.
- `jenkins/`: Jenkins 2.541.3, JENKINS_HOME fora do repo, ATS montado read-only.
- `plane/`: Plane 1.3.1, `.env` e todos os volumes fora do repo.
- `rustdesk/`: runtime preflight `Pull=never`/tmpfs, bounded restart, edge nft
  público aprovado e guard de reapply atômico.

## Regras

- Nunca copiar `.env`, credentials, H2, JENKINS_HOME ou volumes para Git.
- Antes de aplicar: backup da unit, compose e dados; validar `SHA256SUMS` e restore test.
- Instalar unit com `install -m 644`, executar `systemd-analyze --user verify`, `systemctl --user daemon-reload`, então iniciar somente a unit alvo.
- Validar endpoint local antes do domínio público.
- CloudBeaver: HTTP 200 em `127.0.0.1:8978` e `db.atius.com.br`.
- Jenkins: HTTP 200 em `127.0.0.1:8085/login` e `jenkins.atius.com.br/login`.
- Plane: 13 containers, migrator `exit 0`, 162 migrations, root/API/setup `200/401/200`.
- Plane usa volumes `plane-app_*`; `pgdata` e `redisdata` sem prefixo pertencem ao Atius Router.
- RustDesk preserva o digest imutável ARM64 por tag local pinada, reidrata a
  identidade exclusivamente no tmpfs e publica somente `34100/TCP`,
  `34125/TCP+UDP` e `34126/TCP`; `21114-21119` ficam fechadas no VNIC público.
- O edge vive como system unit root porque nft é kernel-owned; `hbbs/hbbr` e o
  preflight continuam rootless no user manager. O guard de 1 minuto usa reload
  batch-validado/atômico e nunca faz flush incremental da policy live.
- O batch é montado por `rustdesk/apply-rustdesk-edge.sh`, com
  `set -euo pipefail`, source regular/root-owned/non-writable, `nft -c` antes
  do apply e transação única. Policy ausente/inválida falha antes de tocar a
  table live; o drill de source ausente preservou o hash da table.

Runbook: `docs/operations/srv1-service-recovery-2026-09-05.md`.
