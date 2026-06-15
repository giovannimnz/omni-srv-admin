---
phase: 13
slug: k3s-ha-portainer-oci
date: 2026-06-15
status: context-updated-for-no-cost-release-gates
branch: docs/m005-gate-review-20260614
mode: gsd-discuss-phase-text
---

# Phase 13 Context - M005 No-Cost Release Gates

## Domain

M005 entrega o cluster K3s HA com Portainer, observability, watchdog e edge
admin em `ATIUS-SRV-1`, `ATIUS-SRV-2` e `ATIUS-SRV-3`.

O cluster live baseline ja passou. Esta rodada decide como fechar os gates
restantes sem custo recorrente novo e sem introduzir dependencias pagas.

## Locked Decisions

### Rollback sem snapshot OCI

Decisao: remover `OCI snapshot IDs` como gate obrigatorio do M005.

Novo gate:

- `GDrive backup bundle + checksum + restore drill validado`.

Racional:

- snapshots OCI geram custo de storage;
- a conta ja possui 5TB no GDrive;
- o milestone aceita restore operacional mais lento, desde que o caminho seja
  documentado, verificavel e testado por checksum/runbook.

Limite aceito:

- GDrive substitui snapshot OCI como rollback/offsite backup;
- GDrive nao substitui snapshot instantaneo da VM;
- restore de host destruido passa a ser rebuild + download + restore, nao
  rollback de volume OCI.

### Storage M005

Decisao: aceitar `local-path` + backup GDrive + restore drill para M005.

Escopo aceito:

- Portainer, Grafana, Prometheus e Alertmanager continuam em PVC `local-path`
  no SRV-1 neste milestone;
- backup offsite deve ir para GDrive com `SHA256SUMS`;
- restore drill deve validar checksums e descrever a reidratacao de etcd/PVCs.

Fora do M005:

- Longhorn/RWX/replicacao real de storage;
- GDrive montado como storage live/PVC;
- Prometheus HA real.

### Tailscale PTP fallback

Decisao: criar Tailscale como segunda camada PTP operacional entre os 3 SRVs.

Escopo M005:

- instalar/validar Tailscale em SRV-1/SRV-2/SRV-3;
- aplicar ACL restrita para os 3 nodes e o usuario/admin;
- validar SSH/Fleet/PgBouncer/admin debugging pelo caminho Tailscale;
- documentar Tailscale como fallback de gestao quando WireGuard cair.

Pre-flight evidence:

- SRV-1: `100.76.56.62`, online;
- SRV-2: `100.93.43.113`, online;
- SRV-3: `100.72.102.57`, online;
- bidirectional `tailscale ping` passed across all three hosts on 2026-06-15.

Limite aceito:

- nao trocar K3s/flannel/etcd automaticamente para Tailscale neste milestone;
- WireGuard continua dependencia do cluster K3s em M005;
- Tailscale fecha o gate como fallback operacional, nao como HA completo do
  transporte do cluster.

### Edge auth

Decisao: usar Cloudflare Access se estiver disponivel sem custo na conta.

Escopo M005:

- configurar Access para `portainer.atius.com.br`, `docker.atius.com.br`,
  `grafana.atius.com.br` e `jenkins.atius.com.br`;
- manter Apache Basic Auth como fallback ate Access estar validado;
- nunca registrar tokens/API keys em git, `.planning`, logs ou vault.

Implementacao preferida:

- usar API/CLI Cloudflare com credenciais carregadas do `.zshrc`, sem imprimir
  valores sensiveis;
- usar navegador apenas se a API nao tiver acesso suficiente.

Secret handling locked:

- `set +x` before loading credentials;
- no `env`, `printenv`, `set`, `echo $TOKEN` or verbose curl output containing
  credentials;
- prefer protected temporary header/config files under `/dev/shm` over putting
  long-lived API keys directly in process arguments;
- run value-based secret leak checks before committing any doc updates.

### Jenkins hotfix

Decisao: corrigir Jenkins para Podman socket/CLI, nao `/var/run/docker.sock`.

Estado atual:

- `https://jenkins.atius.com.br/` retorna 503;
- Apache proxy aponta para `127.0.0.1:8085`;
- `container-jenkins.service` falha porque `/var/run/docker.sock` nao existe.

Escopo M005:

- recuperar UI Jenkins primeiro;
- trocar dependencia de Docker socket por Podman socket/CLI ou remover socket
  temporariamente se a UI for o primeiro passo necessario;
- validar `http://127.0.0.1:8085/login` e o dominio publico protegido por
  Cloudflare Access/Basic Auth.

Futuro:

- Jenkins agents no K3s ficam como arquitetura posterior ao hotfix.

### Ubuntu Pro / ESM Apps

Decisao: adicionar gate para habilitar e validar Ubuntu Pro ESM Apps nos 3 SRVs.

Escopo M005:

- verificar `pro status` em SRV-1/SRV-2/SRV-3;
- se anexado mas `esm-apps` estiver disabled, executar `sudo pro enable esm-apps`;
- se nao estiver anexado, usar token Ubuntu Pro fora de git/log/vault;
- validar `esm-apps` e `esm-infra` como `enabled` ou registrar excecao explicita.

Pre-flight evidence:

- SRV-1: attached, `esm-apps` enabled, `esm-infra` enabled;
- SRV-2: attached, `esm-apps` enabled, `esm-infra` enabled;
- SRV-3: `attached=false`; no Ubuntu Pro token was found in `.zshrc`,
  `.bashrc`, `.profile` or shallow `~/.config` scan by variable name.

Safe attach rule:

- SRV-3 attach must use `pro attach --token-stdin` or equivalent non-logged
  stdin/secret-file flow;
- if no token/attach path is available, the gate stays blocked.

Fonte oficial:

- Ubuntu Pro attach: `https://documentation.ubuntu.com/pro/attach-tutorial/`
- ESM Apps/Infra enable: `https://documentation.ubuntu.com/pro-client/en/latest/howtoguides/enable_esm_infra/`
- ESM overview: `https://ubuntu.com/security/esm`

## Canonical Refs

- `.planning/ROADMAP.md`
- `.planning/MILESTONES.md`
- `.planning/STATE.md`
- `.planning/phases/13-k3s-ha-portainer-oci/13-GATE-REVIEW-2026-06-14.md`
- `.planning/phases/13-k3s-ha-portainer-oci/13-RESTORE-DRILL-2026-06-14.md`
- `.planning/phases/13-k3s-ha-portainer-oci/13-FALLBACK-PTP-2026-06-14.md`
- `.planning/phases/13-k3s-ha-portainer-oci/13-OCI-ROLLBACK-PATH-2026-06-14.md`
- `.planning/phases/13-k3s-ha-portainer-oci/13-OBSERVABILITY-WATCHDOG-2026-06-14.md`
- `modules/k3s-ha-portainer-oci/README.md`
- `modules/k3s-ha-portainer-oci/scripts/backup-local-path-pvcs.sh`
- `modules/fleet-backup/README.md`
- `modules/srv1-ops/README.md`

## Deferred Ideas

- Jenkins agents on K3s.
- Longhorn or other replicated RWX/HA storage.
- K3s transport redesign away from mandatory WireGuard.
- OCI private API VIP/LB.
