# OCI Snapshots — workflow versionado para hosts gerenciados

**Escopo:** hosts do inventário cujo `platform.provider` é `oracle-oci`
(SRV-1, SRV-2, SRV-3, horistic-srv). Source of truth: este doc + o
módulo `cli/omni/oci.py`. Adicionar/atualizar aqui sempre que o
schema ou o gate mudarem.

## Contexto

M005 fechou com 4 follow-ups. O mais operacional era **rollback
formal**: se uma operação em produção quebrar um node do cluster K3s,
o caminho atual é "reinstalar e re-aderir manualmente" — horas de
trabalho. Com snapshots OCI versionados, o mesmo cenário vira
"clonar do snapshot, validar K3s rejoins, done".

Este doc cobre o workflow versionado: `preflight` (gateado, antes de
operações de risco), `routine` (semanal, via timer) e `restore drill`
(simula restore sem custo para validar o caminho).

## Pré-requisitos

| Componente | Status atual (2026-06-18) |
|---|---|
| `oci` CLI (Python OCI SDK + wrapper) | **não instalado** nos 4 hosts |
| `~/.oci/config` com API key + tenancy/user OCID | **não configurado** |
| `python3` + `click` + `pyyaml` | ✅ OK (já roda o `omni` CLI) |
| `omni srv oci ...` subcomandos | ✅ OK (registrados em `cli.py`) |
| `inventory/hosts/<srv>.yaml` com bloco `oci:` | ✅ OK (preenchido em dry-run) |
| TbConfigItems (DbOmniFleet) | ⚠️ mirror implementado, skip se `fleet-db.env` ausente |
| systemD user timer (rotina semanal) | ❌ a registrar quando OCI live estiver disponível |

> Blocker explícito: o host atual (SRV-1) **não tem** `oci` CLI nem
> `~/.oci/config`. Os comandos em modo `--plan` / `--dry-run`
> continuam funcionando e geram o snapshot como `pending-...` no
> inventário + arquivo de estado local. Para a transição live é
> preciso provisionar um OCI user com `Allow group <grp> to manage
> instance-family in compartment ATIUS`.

## Comandos

### `omni srv oci status`

Mostra o último snapshot registrado e o `routine_schedule` de cada
host `oracle-oci` no inventário.

```bash
omni srv oci status
omni srv oci status --host atius-srv-1 --json
```

### `omni srv oci snapshot preflight`

Cria um snapshot OCI **gated** antes de operações de risco
(upgrade, cutover, migração etc). Comportamento:

- **Default**: pede confirmação interativa (`--gate/--no-gate`).
- **`--plan`**: NÃO chama a API; imprime o comando OCI que seria
  executado, registra `pending-...` no inventário e no arquivo de
  estado local. Útil para revisar o plano antes de aplicar.
- **Sem `--plan`**: tenta chamar a API; se faltar `oci` CLI,
  `~/.oci/config`, ou os OCIDs da instance/compartment, cai em
  `dry-run` e grava `pending-...` da mesma forma.
- **`--stop`/`--no-stop`**: default `--stop` (snapshot
  application-consistent); em produção, **não** usar `--no-stop`
  para PM2 daemons (crash-consistent pode levar a K3s rejoins
  demorados).
- **`--json`**: saída em JSON.

```bash
# Plano (sem chamada real):
omni srv oci snapshot preflight --host atius-srv-1 --plan --json

# Real (após provisionar oci CLI + config):
omni srv oci snapshot preflight \
  --host atius-srv-1 \
  --instance-ocid ocid1.instance.oc1.iad.aaaaaaa... \
  --compartment-ocid ocid1.tenancy.oc1..aaaaaaa...
```

Após `--plan` ou dry-run, o inventário e o arquivo de estado ficam:

```yaml
# inventory/hosts/atius-srv-1.yaml
oci:
  last_snapshot_id: "pending-be427934-..."  # ou ocid1.image.oc1... real
  last_snapshot_at: "2026-06-18T01:38:07Z"
```

```json
# ~/.local/state/omni/oci-last-snapshot.json
{
  "host": "atius-srv-1",
  "snapshot_id": "pending-be427934-...",
  "snapshot_at": "2026-06-18T01:38:07Z",
  "display_name": "omni-srv-admin-preflight-atius-srv-1-2026-06-18T01:38:07Z",
  "status": "dry-run",
  "mode": "preflight",
  "stop": true
}
```

### `omni srv oci snapshot routine`

Cria um snapshot OCI **non-interactive** (chamado pelo systemd
timer semanal). Comportamento:

- Sem gate interativo.
- Registra `pending-...` no inventário (com `routine_schedule`)
  + log em `~/.logs/oci/routine-snapshots.jsonl` (jsonl).
- DB mirror: skip quando `oci` CLI ausente ou `/etc/omni-srv-admin/fleet-db.env` não existe.

```bash
omni srv oci snapshot routine --host atius-srv-1
omni srv oci snapshot routine --host atius-srv-1 --schedule "weekly Sun 04:00 BRT"
```

### `omni srv oci restore drill`

Simula o restore de um snapshot OCI, **sem chamadas à OCI API**
quando `--dry-run`. Útil para validar o caminho de rollback
periodicamente sem custo.

- Lê `oci.last_snapshot_id` do inventário por default; aceita
  `--snapshot-id` para override.
- Rejeita `--no-dry-run` com `pending-...` (proteção: restore real
  exige ID OCI real).
- Em dry-run, registra o plano em
  `~/.logs/oci/restore-drills/restore-drill-YYYYMMDDTHHMMSSZ.log`.
- Quando o `oci` CLI estiver disponível e um ID real for passado,
  chama `oci compute instance launch` com `sourceDetails: image`,
  aguarda RUNNING, valida `kubectl get nodes` (TODO após K3s
  healthcheck job) e destrói a instance por default
  (`--keep-instance` para reter).

```bash
# Plano (sem chamada real) usando o last_snapshot_id do inventário:
omni srv oci restore drill --host atius-srv-1 --dry-run

# Plano com ID OCI real explícito:
omni srv oci restore drill --host atius-srv-1 \
  --snapshot-id ocid1.image.oc1.iad.aaaaaaa... \
  --compartment-ocid ocid1.tenancy.oc1..aaaaaaa... \
  --availability-domain iad:US-ASHBURN-AD-1 \
  --subnet-ocid ocid1.subnet.oc1.iad.aaaaaaa... \
  --dry-run
```

## Custos

| Item | Estimativa | Notas |
|---|---|---|
| Block storage (snapshot 200GB) | ~$0.025/GB/mês | Custom image em OCI cobra o tamanho da boot volume do parent |
| SRV-1 (250GB) | ~$6.25/mês | snapshot 4× ao mês × 90 dias = $25 / quarter |
| SRV-2 (250GB) | ~$6.25/mês | idem |
| SRV-3 (250GB) | ~$6.25/mês | idem |
| horistic-srv (200GB) | ~$5/mês | idem |
| **Total estimado** | **~$24/mês** | vs. horas de rollback manual |

Política de retenção atual: manter 4 snapshots semanais, apagar
mais antigos. Implementar via `omni srv oci prune` (TODO em
próxima iteração, fora de escopo da Phase 15).

## Riscos & mitigações

| Risco | Mitigação |
|---|---|
| Snapshot durante IO pesado = crash-consistent (não application) | `--stop` default; `pm2 save` antes em PM2 daemons; para K3s: drain + cordon antes |
| Quorum etcd durante restore drill | Gate explícito; drill só em janela de manutenção |
| `pending-...` vaza para inventory como se fosse ID real | `restore drill --no-dry-run` rejeita `pending-` com erro explícito |
| Substring match em `notes.vault_project` (`omni-srv-adminoci:`) | `oci.py:_update_inventory_oci_block` ancorado em `^oci:\s*$` (regex), corrigido em Phase 15 |
| Custo de retenção | prune job + monitoring (TODO) |
| OCI quota / API throttling | `preflight` exibe o comando antes de aplicar; `oci_cli_available()` reporta se o CLI está instalado |

## Pendências para fechar (OCI live)

1. Instalar `oci` CLI (`pip install oci-cli` ou `bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"`).
2. Provisionar API key + `~/.oci/config` com tenancy, user, fingerprint, region.
3. Setar OCIDs da instance (SRV-1/2/3/horistic-srv) e compartment em
   `~/.config/omni-srv-admin/oci-defaults.env` (TODO: módulo
   `cli/omni/oci_config.py`).
4. Registrar systemD user timer `~/.config/systemd/user/oci-snapshot-routine.timer` para rodar `omni srv oci snapshot routine --host atius-srv-1` semanalmente.
5. Smoke test live: rodar `preflight` em SRV-1 com `--no-gate`; verificar `oci_last_snapshot.json` tem `ocid1.image.oc1...` real; rodar `restore drill --no-dry-run --snapshot-id <real>` em janela de manutenção; validar K3s join + destroy.
6. Configurar IAM policy mínima:
   ```
   Allow group atius-fleet-admins to manage instance-family in compartment ATIUS
   Allow group atius-fleet-admins to manage virtual-network-family in compartment ATIUS
   ```
7. Implementar `omni srv oci prune` (delete older than N snapshots).

## Estado do inventário (2026-06-18)

Todos os 4 hosts `oracle-oci` estão com bloco `oci:` preenchido e
`routine_schedule: "weekly Sun 04:00 BRT"`. O `last_snapshot_id` é
`pending-...` (UUID v4) porque não houve chamada real à OCI API.
Após o item 5 acima, esses valores viram OCIDs reais.

```text
host                   last_snapshot_id                                   last_snapshot_at       schedule
atius-srv-1            pending-250f32ed-...-a08aa298a94c                  2026-06-18T01:38:21Z   weekly Sun 04:00 BRT
atius-srv-2            pending-ef73658b-...-0d939692c21e                  2026-06-18T01:38:21Z   weekly Sun 04:00 BRT
atius-srv-3            pending-5c217b32-...-c2130e9d2d49                  2026-06-18T01:38:21Z   weekly Sun 04:00 BRT
horistic-srv           pending-6f7baf00-...-9b49fa463c0a                  2026-06-18T01:38:21Z   weekly Sun 04:00 BRT
oci CLI: no  oci config: no
```

## Verificação rápida

```bash
# Sanity (sem oci CLI, dry-run):
omni srv oci status
omni srv oci snapshot preflight --host atius-srv-1 --plan --no-gate --json
omni srv oci snapshot routine --host atius-srv-1
omni srv oci restore drill --host atius-srv-1 --dry-run

# Estado local:
cat ~/.local/state/omni/oci-last-snapshot.json
ls -la ~/.logs/oci/
```

## Arquivos relacionados

- `cli/omni/oci.py` — implementação (Click group `oci` + sub-grupos `snapshot` e `restore`)
- `cli/omni/tests/test_oci.py` — testes do módulo (smoke + state machine)
- `cli/omni/cli.py` — registra `oci_group` como sub-grupo de `srv`
- `inventory/hosts/{atius-srv-1,atius-srv-2,atius-srv-3,horistic-srv}.yaml` — bloco `oci:` populado
- `.planning/phases/15-m005-oci-snapshots/15-PLAN.md` — plano original
- `.planning/phases/15-m005-oci-snapshots/15-SUMMARY.md` — fechamento da fase
- `docs/operations/13-OCI-ROLLBACK-PATH-2026-06-14.md` — runbook original do M005 que motivou esta fase
