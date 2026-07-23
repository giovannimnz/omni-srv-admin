---
phase: 15
padded: 15
slug: m005-oci-snapshots
name: M005 OCI Snapshots
date: 2026-06-18
status: complete
wave: 1
depends_on: []
autonomous: true
requirements_addressed:
  - OCI-01
  - OCI-02
  - OCI-03
---

# Phase 15: M005 OCI Snapshots — Summary

## TL;DR

CLI `omni srv oci {status, snapshot preflight, snapshot routine, restore drill}`
implementado, registrado no `cli.py`, validado em dry-run nos 4 hosts
oracle-oci (SRV-1/2/3 + horistic-srv). Bug pré-existente no updater
de inventário corrigido. Inventário de todos os hosts tem bloco
`oci:` com `pending-...` ID (estado offline, sem OCI live) +
`routine_schedule`. Test suite: 12/12 verde (suite completa do
`cli/`: 28/28). Doc canônico em `docs/operations/oci-snapshots.md`.

**Live OCI bloqueado** (sem `oci` CLI + `~/.oci/config` no host).
A fase fecha o que é possível fechar agora e deixa a transição
live documentada como 7 itens na seção "Pendências" do doc.

## Tasks — status

| # | Task | Status | Evidence |
|---|---|---|---|
| 1 | `omni srv oci snapshot preflight` (gated, --plan, --stop, --gate) | ✅ | `cli/omni/oci.py:379-558` |
| 1 | `omni srv oci snapshot routine` (non-interactive, --schedule) | ✅ | `cli/omni/oci.py:561-673` |
| 2 | Inventário `inventory/hosts/<srv>.yaml` com `last_snapshot_id` + `last_snapshot_at` + `routine_schedule` | ✅ | diff em todos os 4 hosts |
| 2 | Mirror `TbConfigItems` (DbOmniFleet) | ✅ code, ⚠️ skip live (sem `fleet-db.env` + sem `oci` CLI) | `cli/omni/oci.py:_mirror_to_fleet_db` |
| 3 | `omni srv oci restore drill [--dry-run]` | ✅ | `cli/omni/oci.py:686-826`; rejeita `--no-dry-run` com `pending-` |
| 4 | Doc `docs/operations/oci-snapshots.md` | ✅ | novo arquivo (9880 bytes) |
| 4 | `15-SUMMARY.md` | ✅ | este arquivo |
| 5 | 1 drill real SRV-1 (live OCI) | ❌ blocked (sem OCI CLI) | doc tem runbook; TODO para próxima janela |
| 6 | Test suite | ✅ | `cli/omni/tests/test_oci.py` 12 testes; suite `cli/` 28/28 |

## Verificação executada (2026-06-18, SRV-1)

```text
$ omni srv oci status
atius-srv-1            pending-250f32ed-...-a08aa298a94c    2026-06-18T01:38:21Z   weekly Sun 04:00 BRT
atius-srv-2            pending-ef73658b-...-0d939692c21e    2026-06-18T01:38:21Z   weekly Sun 04:00 BRT
atius-srv-3            pending-5c217b32-...-c2130e9d2d49    2026-06-18T01:38:21Z   weekly Sun 04:00 BRT
horistic-srv           pending-6f7baf00-...-9b49fa463c0a    2026-06-18T01:38:21Z   weekly Sun 04:00 BRT
oci CLI: no  oci config: no

$ omni srv oci snapshot preflight --host atius-srv-1 --plan --no-gate --json
{
  "status": "dry-run",
  "snapshot_id": "pending-...",
  "oci_cmd": ["oci", "compute", "image", "create", "--compartment-id", "<COMPARTMENT_OCID_REQUIRED>", ...],
  "inventory": {"status": "dry-run", "would_write_lines": ["oci:", "  last_snapshot_id: \"pending-...\"", ...]}
}

$ omni srv oci snapshot routine --host atius-srv-1
host         : atius-srv-1
snapshot_id  : pending-...
status       : dry-run (missing oci CLI)

$ omni srv oci restore drill --host atius-srv-1 --dry-run
host             : atius-srv-1
snapshot_id      : pending-...
display_name     : omni-drill-atius-srv-1-2026-06-18T01:38:48Z
status           : dry-run (missing oci CLI)
drill_log        : /home/ubuntu/.logs/oci/restore-drills/restore-drill-20260618T013848Z.log

$ omni srv oci restore drill --host atius-srv-1 --no-dry-run
Error: host atius-srv-1 com snapshot pending (pending-...) — restore real exige ID OCI real.
       Use --dry-run para validar o plano ou passe --snapshot-id=ocid1.image.oc1...
```

Estado local:
```text
$ ls ~/.local/state/omni/ ~/.logs/oci/
/home/ubuntu/.local/state/omni/oci-last-snapshot.json
/home/ubuntu/.logs/oci/restore-drills/restore-drill-20260618T013848Z.log
```

## Desvios do plano original

### Bug pré-existente corrigido

`_update_inventory_oci_block` em `oci.py` usava `"oci:" in text` para
achar o bloco a atualizar. Substring match pegava o `oci` em
`notes.vault_project: "...omni-srv-admin"` e colava o bloco no fim
dessa string, **quebrando o YAML** e perdendo a chave `notes:` inteira
no SRV-1. Sintoma: `yaml.scanner.ScannerError: mapping values are not
allowed here ... line 197, column 66: ... ROJETOS-ATIVOS/omni-srv-adminoci:`.

Fix: anchor com `re.match(r"^oci:\s*$", line)` (linha começando com
`oci:` e nada mais). Validei re-rodando `preflight` + `routine` em
todos os 4 hosts, o YAML permanece parseável e o bloco `oci:` fica
em um único lugar.

### Drill: rejeição explícita de `--no-dry-run` com `pending-`

A versão inicial rejeitava `--dry-run` (default) com `pending-` com
erro genérico "snapshot ID inválido". Achei confuso: o user
frequentement quer validar o **plano** de restore com o último
snapshot que está offline. Refatorei:
- `--dry-run` (default) + `pending-` → plano + log (status dry-run)
- `--no-dry-run` + `pending-` → erro explícito: precisa de OCID real
- `--no-dry-run` + ID real → tenta API; sem `oci` CLI cai em
  dry-run com a mesma mensagem
- `--dry-run` + ID real → plano + log

### Pendência de prune

POLICY "keep 4 weekly, delete older" não foi implementada.
`omni srv oci prune` é TODO para M008-ext ou próximo ciclo. Doc
de OCI snapshots tem o item na seção "Pendências para fechar".

## Decisões de arquitetura

1. **Failure mode de OCI ausente = dry-run explícito, não crash.** O
   módulo nunca quebra a CLI por falta de `oci` CLI/config; cai em
   dry-run, gera `pending-...` e log. Operador pode rodar em qualquer
   máquina que tenha `omni` instalado.
2. **Mirror DbOmniFleet best-effort.** `_mirror_to_fleet_db` é
   skip se `fleet-db.env` ausente ou `psql` não disponível, sem
   falhar o preflight.
3. **Inventário é o source of truth local.** Mesmo quando o mirror DB
   não acontece, o inventário YAML fica populado, e `omni srv oci
   status` funciona offline.
4. **Gate explícito em restore drill, não em snapshot.** Snapshot
   preflight é idempotente e barato; restore drill tem custo (cria
   instance OCI). Gate é a recusa de `--no-dry-run` com `pending-`.

## Estado do repo após a fase

```text
 M cli/omni/cli.py                            # registra oci_group
 M cli/omni.egg-info/PKG-INFO
 M cli/omni.egg-info/SOURCES.txt
 M inventory/hosts/atius-srv-1.yaml           # bloco oci: pending-250f32ed
 M inventory/hosts/atius-srv-2.yaml           # bloco oci: pending-ef73658b
 M inventory/hosts/atius-srv-3.yaml           # bloco oci: pending-5c217b32
 M inventory/hosts/horistic-srv.yaml          # bloco oci: pending-6f7baf00
?? cli/omni/oci.py                            # módulo novo (885 linhas)
?? cli/omni/tests/test_oci.py                 # 12 testes
?? docs/operations/oci-snapshots.md           # runbook
```

## Riscos remanescentes

| Risco | Mitigação | Owner |
|---|---|---|
| `oci` CLI não instalado em 4 hosts | `docs/operations/oci-snapshots.md` "Pendências" item 1 | operator (próxima janela) |
| `~/.oci/config` ausente | mesma lista, item 2 | operator |
| `pending-...` aceito como se fosse ID real por engano | `_restore_drill` rejeita com erro explícito; testes cobrem | covered |
| Sem prune job → custo de retenção cresce | TODO `omni srv oci prune`; custo estimado ~$24/mês total, aceitável | next phase |
| IAM policy permissiva demais | TODO no doc (item 6): policy mínima `instance-family` + `virtual-network-family` | operator |

## Next phase readiness

Phase 16 (Cloudflare Access) e Phase 17 (Observability) podem rodar
em paralelo — não dependem de Phase 15 fechar live. Phase 18 (Ubuntu
Pro ESM Apps) está gated em G18-1 (apt upgrade) independente desta.

Para fechar o follow-up OCI live:
1. Operator agenda janela de manutenção (~30min por host).
2. Provisiona OCI user + API key em todos os 4 hosts.
3. Roda `omni srv oci snapshot preflight --host <h> --no-gate` em
   cada um — vira ID real no inventário.
4. Roda `omni srv oci restore drill --host <h> --no-dry-run` em
   SRV-1 só (mais barato), valida K3s join + destroy.
5. Registra systemD user timer para `routine` semanal.
6. Atualiza este SUMMARY com SHA final + drill logs.

## Referências

- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/15-m005-oci-snapshots/15-PLAN.md` — plano original
- `docs/operations/oci-snapshots.md` — source of truth operacional
- `docs/operations/13-OCI-ROLLBACK-PATH-2026-06-14.md` — runbook M005 que motivou
- `cli/omni/oci.py` — implementação
- `cli/omni/tests/test_oci.py` — suite de testes
- `cli/omni/cli.py` — registro do sub-grupo `oci` em `srv`
