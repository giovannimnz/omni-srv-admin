---
phase: 12
name: omni-fleet-control-plane
created: 2026-06-13
method: self-discuss + repo/vault research + official-doc research
generator: gsd-discuss-phase adapted to Codex
status: locked
---

# Phase 12 — Omni Fleet Control Plane

## Objective

Planejar a fundação do Omni Fleet Control Plane no repo
`/home/ubuntu/GitHub/omni-srv-admin`. Esta phase cria a base operacional para
administrar `ATIUS-SRV-1`, `ATIUS-SRV-2` e `ATIUS-SRV-3`: inventário,
instalação `server`/`node`, PostgreSQL central via PgBouncer, heartbeat,
registry de programas, ops scopes por servidor, parâmetros/configs no DB,
controle de versões, licenças, auditoria, slash commands via CLI-Anything e
contrato futuro para Podman/K3s.

## Locked Decisions

### D-01: M004 define a base operacional

**Decisão:** `Omni Fleet Control Plane` é `M004 / Phase 12`.

**Rationale:** O Fleet Control Plane fornece inventário, estado, auditoria,
licenças e update plans. K3s/Podman devem consumir essa base em vez de criar uma
segunda fonte de verdade.

### D-02: Branch de trabalho do milestone

**Decisão:** A branch recomendada e usada para esta reorganização é
`codex/omni-fleet-control-plane-m004`.

### D-03: Repo canônico

**Decisão:** `omni-srv-admin` é o repo operacional e canônico. `omni-spec-driven`
fica fora deste plano.

### D-04: Modos de instalação

**Decisão:** O control plane deve suportar instalação como `server` ou `node`.

- `server`: roda API/CLI administrativa, PostgreSQL, PgBouncer, migrations,
  scheduler e registry central.
- `node`: roda agent mínimo, heartbeat, coleta local, execução controlada de
  update plans e reporte de estado.

### D-05: Inventário é fonte de verdade para identidade

**Decisão:** `inventory/hosts/*.yaml` permanece como source-of-truth versionado
para hosts, rede e papéis. O banco central armazena estado operacional, ops
scopes, parâmetros, configs, registry de comandos, cache de consulta, auditoria
e histórico, mas não substitui o inventário versionado para identidade dos
hosts.

### D-06: PostgreSQL central migrável

**Decisão:** O server terá PostgreSQL central com migrations versionadas e
procedimento de dump/restore. A migração deve funcionar entre hosts ARM64 e
futuras versões suportadas, usando formatos portáveis quando aplicável.

### D-07: PgBouncer obrigatório para clientes

**Decisão:** Nodes, CLI remota e futuros serviços devem conectar no banco via
PgBouncer. Acesso direto ao PostgreSQL fica restrito ao host `server`, migrations
e manutenção explícita.

### D-08: Licenças sem secrets em git/log/vault

**Decisão:** Licenças podem ter metadata versionável, mas tokens, chaves,
serials sensíveis e credenciais devem ficar fora de git, logs, `.planning` e
vault. O banco pode guardar apenas `secret_ref` ou metadata não sensível.

### D-09: Auditoria antes de automação destrutiva

**Decisão:** Toda ação relevante deve gerar audit event com ator, host, ação,
alvo, resultado, timestamp e metadata mínima. Update plans devem ser gerados e
aprovados antes de execução.

### D-10: Podman/K3s ficam como integração futura

**Decisão:** M004 define contracts para Podman/K3s consumirem inventário,
status, programs, versions e audit events. Instalar K3s, migrar workloads ou
trocar Portainer é escopo de outro milestone/branch.

### D-11: `DbOmniFleet` é o DB do `omni-srv-admin`

**Decisão:** Não criar banco paralelo para `omni-srv-admin`. O banco live é
`DbOmniFleet` e passa a ser o DB canônico do `omni-srv-admin` para runtime
state, ops scopes, parâmetros, configs e slash-command registry. As tabelas
usam prefixo `Tb` com CamelCase quoted, por exemplo `TbHosts`,
`TbUpdatePlans` e `TbSlashCommands`.

### D-12: Ops por servidor com config no DB

**Decisão:** Cada host terá um ops scope (`srv1-ops`, `srv2-ops`, `srv3-ops`).
Diretórios `modules/*-ops` guardam scripts, templates, bootstrap e exports.
Parâmetros e configs mutáveis devem ser resolvidos do PostgreSQL via PgBouncer.

### D-13: Slash commands via CLI-Anything

**Decisão:** Slash commands agent-facing devem ser registrados no DB e seguir a
convenção CLI-Anything/`clianything`. O alvo futuro para cobrir operações do
repo é `cli-anything-omni-srv-admin`; comandos ad hoc são temporários até
entrarem em `TbSlashCommands`.

### D-14: Execução distribuída é local ao host alvo

**Decisão:** Um servidor pode solicitar trabalho para outro via
`DbOmniFleet`/PgBouncer, mas não aplica remotamente por SSH. O host alvo roda
`omni-fleet-agent`, reclama apenas seus próprios update plans aprovados,
executa comandos allowlisted localmente e grava resultado/auditoria no DB.

### D-15: Monitoramento cross-server é requisito central do Omni

**Decisão:** Cada SRV deve conseguir enxergar os demais pela visão central do
Fleet Control Plane. O agent publica load, CPU, memória, disco, I/O, PSI e
service health em `TbNodeTelemetry`; `TbNodeResourcePolicies` define limites
iniciais para decisões de controller ativo e load-balancing.

## Canonical References

- `README.md` — repo como centro operacional de hosts, backups, mounts e
  serviços.
- `inventory/hosts/atius-srv-1.yaml` — host SRV-1.
- `inventory/hosts/atius-srv-2.yaml` — host SRV-2.
- `inventory/hosts/atius-srv-3.yaml` — host SRV-3.
- `docs/fleet/inventory-model.md` — modelo de inventário existente.
- `docs/operations/atius-fleet-specs.md` — recursos e limites dos servidores.
- `docs/operations/Atius-Spec-Servers.md` — regra operacional de capacidade.
- `modules/fleet-backup/` — módulo multi-host existente a integrar.
- `modules/fleet-control-plane/migrations/0003_agent_executor_monitoring.sql`
  — fila de execução, allowlist, telemetria e resource policies.
- PostgreSQL docs: `https://www.postgresql.org/docs/current/backup-dump.html`
- PostgreSQL pg_dump docs:
  `https://www.postgresql.org/docs/current/app-pgdump.html`
- PgBouncer docs: `https://www.pgbouncer.org/config.html`
- Vault: `60-LOGS/64-Worklogs-Agrupados/2026-06-06-omni-srv-admin-fleet-docs-remote-manager.md`

## Deferred Ideas

- Migração de workloads Docker/Podman para K3s.
- UI web/dashboard para o control plane.
- Compra/renovação automatizada de licenças.
- Longhorn, OCI CSI ou GitOps.
- Secret manager definitivo se exigir infraestrutura externa.
