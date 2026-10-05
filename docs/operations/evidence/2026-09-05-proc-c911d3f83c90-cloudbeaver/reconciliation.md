# Reconciliação — `proc_c911d3f83c90`

## Classificação

```text
operational-pass-not-review
subtype: superseded-by-current-hardened-runtime
```

O processo histórico passou no escopo executado. Não é review independente e não aprovava exposição de rede.

## Processo histórico

| Campo | Valor |
|---|---|
| Session | `20260904_200755_1d1861` |
| Start observado | `2026-09-05T00:57:20-03:00` |
| Exit observado | `2026-09-05T01:00:24-03:00` |
| Duração tracker | `183s` |
| Exit | `0` |
| Marker | `CLOUDBEAVER_RECOVERY_OK` |
| Imagem | `docker.io/dbeaver/cloudbeaver:26.1.0` |
| Checks históricos | local `200`, público `200`, mount correto, serviço ativo, soak 30s |

Os `curl: (56) Recv failure` iniciais ocorreram durante o startup; o loop aguardou readiness e terminou em `200`.

## Disposition matrix

| Claim | Disposição atual | Evidência |
|---|---|---|
| Pull da imagem 26.1.0 concluiu | histórico PASS | `process-notification.json` |
| Serviço iniciou | histórico PASS, superseded | marker histórico + `current-runtime.json` |
| Workspace persistente preservado | PASS | mount live + `workspace-metadata.json` + restore do backup |
| Local HTTP saudável | PASS | `/status` `200`, `health=ok`, versão 26.1.0 |
| Edge público saudável | PASS | `https://db.atius.com.br/` `200` |
| Runtime era seguro na rede | fora do escopo histórico; drift atual corrigido | before externo `200`; after SRV-3/SRV-4 curl `7/000` |
| Source e inventário estavam atuais | FAIL atual corrigido | TDD RED/GREEN + source/live parity |
| Monitor periódico existia | FAIL atual corrigido | dois starts manuais + natural timer tick PASS |
| DbOmniFleet estava atual | FAIL atual corrigido targeted | `registry-isolation.json`, targeted readback |

## Current proof

- Unit `active/running`, `Result=success`, exit `0`, zero restarts.
- Imagem upstream pinada e workspace montado RW.
- Listener único `127.0.0.1:8978`.
- Local e edge público `200`.
- Exposição direta `137.131.190.161:8978` bloqueada de SRV-3 e SRV-4.
- Positive control `443` alcançável dos mesmos hosts.
- Cloudflare: `db.atius.com.br` único/proxied; alias antigo ausente.
- Monitor read-only a cada cinco minutos; natural tick `success`.
- TDD `5 passed`; inventory `14/14 ok`.
- Full suite governada: `156 passed, 2 failed`. Ambos os failures estão na lane
  dirty preexistente de backup/rclone, sem overlap com os paths ou contratos
  CloudBeaver; preservados em `full-suite.log` e classificados em
  `full-suite-disposition.md`.
- Source e runtime byte-equal.
- Failed units system/user: `0/0`.
- Lifecycle final: stop canônico `Result=success`, status `143` aceito,
  container/listener ausentes; start restaurou `9` arquivos/`1` DB candidate,
  zero restarts e monitor natural `success`.
- Checkpoint Graphify pré-seal: `14.473/21.163`, fresh/current; query exata
  `22/20`. O final seal externo registra a build pós-documentação.
- GBrain body e timeline: import targeted `1/1`, `6` chunks, sem embedding e
  readback do heading/process ID PASS.

## False-starts preservados

1. Validator de stop confundiu SIGTERM `143` com stop incompleto; rollback PASS.
2. `reset-failed` de unit ainda não carregada abortou o harness; rollback PASS.
3. `podman inspect` sob `NoNewPrivileges=true` falhou com `cannot clone`; rollback PASS.

O core cutover foi separado do monitor para impedir que falha auxiliar reabra a exposição pública.

## Backup e rollback

- Backup: `/home/ubuntu/.backups/cloudbeaver-loopback-cutover-20260905T204000-0300`.
- Manifest final: `21/21`.
- Restore test: `9` arquivos, `1` DB candidate.
- Registry rollback test: transaction apply/restore/`ROLLBACK` PASS.
- Registry rollback: `registry/rollback-cloudbeaver-registry.sql`.
- Rollback integral da unit antiga reabre `8978`; break-glass somente.

## Limites

- O historical PASS não é promovido a review `GO`.
- O processo original não testou acesso direto ao public IP.
- Bloqueio externo é observational proof com dois origins e positive control; a garantia primária é o bind host loopback-only comprovado em unit carregada e `ss`.
- O `graph.html` rastreado é histórico: Graphify recusou regenerá-lo porque o
  grafo excede `5.000` nodes. A prova usa `graph.json`, `GRAPH_REPORT.md`, status
  e query exata.
- Nenhum commit/push foi feito nesta reconciliação.
