# Omni Srv Admin Auto-Update

Controle de versão e rollout automático do próprio `omni-srv-admin` na fleet.

## Source of Truth

- observação por host: `TbVersion`
- desired/current por programa: `TbVersions`
- fila de execução: `TbUpdatePlans`
- endpoint de fila: PgBouncer `10.11.1.11:6432` (`10.100.100.1:6432` reserve)
- manifesto versionado:

```text
modules/fleet-control-plane/configs/omni-version-matrix.json
```

## Hosts alvo

- `atius-srv-1`
- `atius-srv-2`
- `atius-srv-3`
- `giovanni-w11-pc`

## Comandos

Tabela de controle:

```bash
PYTHONPATH=cli python3 -m omni fleet version-table
PYTHONPATH=cli python3 -m omni fleet version-table --db --json
```

Coleta local do checkout:

```bash
PYTHONPATH=cli python3 -m omni fleet agent collect-version --host atius-srv-1 --db --json
python -m omni fleet agent collect-version --host giovanni-w11-pc --db --json
```

Fila de rollout:

```bash
PYTHONPATH=cli python3 -m omni fleet queue-self-update --db --approve
PYTHONPATH=cli python3 -m omni fleet queue-self-update --version v0.1.0 --host atius-srv-3 --db --approve
```

Fila PKI trust-client no Windows:

```bash
python -m omni fleet trust-pki install-trust --host giovanni-w11-pc --source db --db --json
```

Esse plano entra na mesma `TbUpdatePlans` consumida pelo `OmniFleetAgent`. Para
`giovanni-w11-pc`, o PKI roda como `trust-client`: instala a root CA em
`Cert:\CurrentUser\Root`, a issuing CA em `Cert:\CurrentUser\CA`, e valida a
CA interna de servicos; certificados leaf dos peers nao viram root CA.

Execução local de um ciclo:

```bash
PYTHONPATH=cli python3 -m omni fleet agent cycle --host atius-srv-3 --apply --json
python -m omni fleet agent cycle --host giovanni-w11-pc --apply --json
```

## Trigger automático

Linux (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`)

- service: `omni-fleet-agent.service`
- install:

```bash
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-1
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-2
modules/fleet-control-plane/scripts/install-omni-fleet-agent.sh atius-srv-3
```

Windows (`giovanni-w11-pc`)

- Scheduled Task: `OmniFleetAgent`
- DB queue endpoint expected by the local cache:
  `C:\Users\muniz\.config\omni-srv-admin\fleet-db.env -> PGHOST=10.100.100.1`
- install:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File modules/fleet-control-plane/windows/Install-OmniFleetAgentTask.ps1
```

2026-07-10 validation: the task is installed and enabled. After SRV-1's
`omni-pg-access-guard` was updated to allow OCI private peers (`10.12/10.13/10.21`)
and reserve `wg100`, Windows was promoted to `10.11.1.11:6432` after direct
reachability from `10.100.100.8` passed. The trust-client
`install-ca` plan `22097c7e-cf44-4841-9133-33517578f21f` finished as
`succeeded`, and `python -m omni fleet agent cycle --host giovanni-w11-pc
--apply --json` returned `status=idle` with telemetry `healthy`.

## Guardrails

- backup sempre criado antes do update
- worktree sujo é preservado via `git stash --include-untracked`
- o stash não é reaplicado automaticamente
- target operacional = branch do manifesto + tag/release desejada
