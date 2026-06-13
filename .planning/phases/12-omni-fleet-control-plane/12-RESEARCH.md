---
phase: 12
name: omni-fleet-control-plane
created: 2026-06-13
status: complete
---

# Phase 12 — Research

## Research Questions

1. O que precisa existir antes de K3s/Podman para o `omni-srv-admin` operar a
   frota com segurança?
2. Como modelar server/node, inventário, DB central e PgBouncer sem criar
   acoplamento prematuro com Kubernetes?
3. Quais contratos mínimos permitem versões, licenças, auditoria e integração
   futura com containers?
4. Como registrar slash commands de forma agent-native sem criar scripts soltos?

## Local Evidence

- `README.md` já posiciona o repo como ferramenta para inventariar hosts,
  gerenciar backups, remote mounts e serviços.
- `inventory/hosts/atius-srv-1.yaml`, `atius-srv-2.yaml` e `atius-srv-3.yaml`
  já existem e devem continuar canônicos.
- O vault tem histórico de `omni-srv-admin` como centro operacional, incluindo
  fleet docs, remote manager, fleet-backup e Podman cutover.
- Futuros milestones de container/orquestração dependem de decisões de
  inventário, capacidade, secrets, backup e controle de mudanças que pertencem
  a um control plane anterior.
- CLI-Anything está local em `/home/ubuntu/GitHub/Programs/CLI-Anything`.
  Referências relevantes: `README.md`, `codex-skill/SKILL.md`,
  `opencode-commands/cli-anything.md` e `cli-anything-plugin/HARNESS.md`.
  O padrão é gerar CLIs `cli-anything-<software>`, com `--json`, REPL, testes e
  slash commands `/cli-anything*`.

## Official Research

### PostgreSQL dump/restore

PostgreSQL recomenda `pg_dump` e `pg_restore` para backups lógicos e migração de
dados. Formatos custom/directory são adequados para restore seletivo e
portabilidade operacional. A documentação alerta para revisar warnings e tratar
restore de fontes não confiáveis como risco de execução de código SQL.

Sources:
- `https://www.postgresql.org/docs/current/backup-dump.html`
- `https://www.postgresql.org/docs/current/app-pgdump.html`

### PgBouncer

PgBouncer é configurado por seções `[databases]` e `[pgbouncer]`; clientes se
conectam ao PgBouncer, tipicamente em porta como `6432`, em vez de falar direto
com PostgreSQL. Parâmetros relevantes para o design: `pool_mode`,
`listen_port`, `auth_type`, `auth_file`, `admin_users`, `stats_users`,
`max_client_conn`, `default_pool_size`, `query_wait_timeout` e
`server_connect_timeout`.

Source:
- `https://www.pgbouncer.org/config.html`

## Proposed Architecture

```text
omni CLI / API
  -> Fleet Control Plane server
  -> PgBouncer
  -> PostgreSQL

Fleet nodes
  -> local agent
  -> heartbeat/status
  -> program inventory
  -> update plan executor
  -> PgBouncer
  -> PostgreSQL

Future Podman/K3s
  -> consumes inventory/status/program/version/audit contracts
```

## Server Responsibilities

- Own migrations and DB schema.
- Run PostgreSQL and PgBouncer.
- Expose control plane API/CLI commands.
- Import and validate `inventory/hosts/*.yaml`.
- Receive heartbeat/status from nodes.
- Generate update plans.
- Store license metadata and secret references only.
- Store audit events.

## Node Responsibilities

- Install as a lightweight agent.
- Report heartbeat and health.
- Report installed programs and versions.
- Execute approved update plans only.
- Never log secrets.
- Connect to DB through PgBouncer only.

## Initial Data Model

| Table | Purpose |
|---|---|
| `hosts` | Canonical host projection from inventory: name, role, IPs, OS, arch, tags |
| `nodes` | Runtime node state: install mode, agent version, heartbeat, health |
| `programs` | Installed program registry by host: name, install type, version, source |
| `versions` | Desired/current version state and update policy |
| `update_plans` | Proposed changes, approval status, execution result |
| `licenses` | License metadata, status, expiry, scope and `secret_ref` |
| `audit_events` | Actor, host, action, target, result, timestamp, metadata |
| `ops_scopes` | Per-host ops areas such as `srv1-ops`, `srv2-ops`, `srv3-ops` |
| `config_items` | DB-backed runtime parameters/configs with `secret_ref` for sensitive values |
| `slash_commands` | CLI-Anything slash-command registry |
| `slash_command_bindings` | Command-to-host/scope apply policy |

## Risks

- **DB availability:** nodes must degrade gracefully if PostgreSQL/PgBouncer is
  unavailable.
- **Pooler misconfiguration:** bypassing PgBouncer can exhaust PostgreSQL or
  split operational paths.
- **Inventory drift:** DB cannot become an unreviewed second source of truth.
- **Secret leakage:** license metadata and update logs must never include raw
  tokens or serials.
- **Agent blast radius:** node agents must be minimal and human-gated for
  destructive updates.
- **Premature orchestration coupling:** M004 must define contracts, not install
  Kubernetes.
- **Slash command drift:** ad-hoc slash commands can diverge from DB state unless
  every command is registered and validated through the control-plane schema.

## Conclusion

M004 should ship the control plane contract first. The minimum valuable output is
a clear server/node model, schema/migration plan, PgBouncer rule, heartbeat,
program registry, DB-backed ops/config state, CLI-Anything slash-command
registry, version/update plan flow, license handling rule and audit contract.
Future container/orchestration milestones can then use this foundation rather
than duplicating fleet state.
