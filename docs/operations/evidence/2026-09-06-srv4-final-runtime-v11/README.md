# ATIUS-SRV-4 final runtime v11

Data: 2026-09-06
Status: PASS

## Authority

- Source manifest stable final: `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`
- Source file count: `444/444`
- Full apply final: `20260906T233823+0000-1549801`, `17/17 PASS`
- Verify-only final: `20260906T234149+0000-1558144`, `17/17 PASS`
- O package documental anterior `d54b2a07…`/`220508`/`220854` foi
  superseded somente pelo alinhamento final `.gitignore`/`.graphifyignore`.
- O apply/verify funcional anterior (`20260906T211445`/`20260906T211836`,
  manifest `22bc6ba2…`) permanece histórico válido e foi superseded somente pelo
  package que sincronizou a documentação/skill final.
- Runtime review: `VERDICT=GO`, `P0/P1/P2/P3=0/0/0/0`

## Runtime

- Repo runtime `main=f851a03=origin/main`, clean.
- Node `24.20.0`, npm `11.19.0`, Bun `1.4.2`, Codex `0.153.4`.
- Rust `1.98.1`, cargo-binstall binary equal to SRV-1, Zellij `0.45.1`.
- Hermes `0.21.0` at `01ae7a5668ce0fa2efca524a4567cacdd0786c95`.
- GSD Core `1.13.0/full`; Graphify `0.9.23` with OpenAI `2.24.0`.
- Graphify backend and both stream patches active; real API smoke returned valid JSON.
- MCP tool counts: GBrain `115`, Obsidian `16`, OCI Admin `12`.
- System/user failed units: `0/0`.

## Network and desktop

- OCI private `10.14.1.14`; reserved public `164.152.48.22`; WireGuard `10.100.100.18`.
- `atius-srv-4.atius.internal` forward/reverse resolution passed.
- XRDP/LightDM/LXDE, ATIUS TLS, ABNT2, dark theme and eight XDG folders passed.
- Nine SRV-1-only units are `not-found` on SRV-4.

## Backup and rollback

- Preapply backup: `/home/ubuntu/.backups/srv4-final-runtime-preapply-20260906T205141+0000`.
- Five archives + `ABSENT-PATHS.txt`; six checksum rows; restore inventory PASS.
- Previous setup sources preserved under `~/.local/share/omni-setup-source.pre-*`.

## Review convergence

- `reviews/setup-v10-go.txt`
- `reviews/setup-post-v10-go.txt`
- `reviews/ops-v10-go.txt`
- `reviews/ops-p3-go.txt`
- `reviews/reset-hotfix-go.txt`
- `reviews/runtime-v11-go.txt`
- `reviews/server-analysis-hotfix-go.txt`
- `reviews/aa-runtime-final-go.txt`
- `reviews/proc-b20-reconciliation-go.txt`
- `reviews/proc-d7-reconciliation-go.txt`

## Cleanup

Validation artifacts were inventoried before deletion. `16/16` reproducible items, `5.634.420.094` bytes, zero remaining. SRV-1 disk changed from `100% / 1.1G free` to `97% / 6.4G free`. Runtime, worktree, backups, review manifests and logs were preserved.

## Seal note

The first evidence checksum command used repo-prefixed paths while verifying
from inside this directory and failed before producing a valid seal. The final
`SHA256SUMS` uses paths relative to this evidence root; `SHA256SUMS.check` is
the successful readback authority.

## Resultado assíncrono tardio

- O processo histórico `proc_e1efd523449b` notificou `exit 1` depois do
  runtime final já estar selado.
- O backup antigo
  `/home/ubuntu/.backups/srv4-full-setup-parity-pre-20260906T041902+0000`
  permaneceu íntegro: `SHA256SUMS` `15/15 PASS`, root/user compare `rc=0`,
  `git bundle verify rc=0` e `restore-drill.env result=PASS`.
- A falha foi do harness: ele comparou quantidade de members do tar com
  quantidade de paths extraídos, métricas não equivalentes quando existem
  diretórios implícitos. Classificação: `historical-harness-failure`.
- O backup preapply atual permaneceu checksummed e supersede esse backup antigo
  como rollback operacional. Nenhum current actionable foi reaberto.
- Evidência preservada em `delayed-backup/`.
- O processo posterior `proc_b20a6f181b17` confirmou o mesmo backup com
  `ROOT_COMPARE=0`, `USER_COMPARE=0`, `BUNDLE=0` e `RESTORE=PASS`, mas o
  wrapper retornou `exit 1` porque procurou o token localizado `SUCESSO$`
  enquanto `sha256sum -c` emitiu `OK`. Classificação:
  `post-workload-harness-failure/localized-checksum-token-mismatch`.
- Readback atual: 15/15 checksums `OK`; nenhum current actionable.
- Reconciliação: `delayed-backup/proc-b20a6f181b17-reconciliation.md`.
- `proc_d7b3cd5a26de` falhou antes do workload com `No module named omni`:
  o launcher source-based não exportou `PYTHONPATH=$ROOT/cli`.
- A sessão detectou a falha e relançou como `proc_8df4807a96c0` com o ambiente
  correto; esse relaunch avançou oito steps e depois encontrou o bug independente
  `npm EEXIST`, corrigido nas retomadas seguintes.
- Apply `20260906T233823+0000-1549801` e verify-only
  `20260906T234149+0000-1558144` são a autoridade final. Classificação:
  `pre-workload-launcher-failure/missing-pythonpath`, superseded, sem current
  actionable.
- Reconciliação: `delayed-backup/proc-d7b3cd5a26de-reconciliation.md`.

## Graphify final

- Governed named unit: `srv4-final-graphify-192557.service`, result success.
- Stable final: `13.729` nodes, `21.421` edges, fresh/current no HEAD observado.
- Exact queries encontraram o evidence pack, runbook, setup e offload.
- O segundo rebuild retornou `No code-graph topology changes detected`; hashes
  dos outputs foram idênticos. O status final fica em `/tmp` para evitar um
  ciclo de self-mutation no corpus versionado.
