# Omni Srv Admin Auto-Update

Controle de versão e rollout automático do próprio `omni-srv-admin` na fleet.

## Source of Truth

- observação por host: `TbVersion`
- desired/current por programa: `TbVersions`
- fila de execução: `TbUpdatePlans`
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
- install:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File modules/fleet-control-plane/windows/Install-OmniFleetAgentTask.ps1
```

## Guardrails

- backup sempre criado antes do update
- worktree sujo é preservado via `git stash --include-untracked`
- o stash não é reaplicado automaticamente
- target operacional = branch do manifesto + tag/release desejada
