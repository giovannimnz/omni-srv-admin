# Reconciliation — proc_e1efd523449b

Data: 2026-09-06
Classificação: `historical-harness-failure`
Current actionable: nenhum

## Proveniência

- Processo: `proc_e1efd523449b`
- Alvo: `atius-srv-4`
- Backup: `/home/ubuntu/.backups/srv4-full-setup-parity-pre-20260906T041902+0000`
- Notificação tardia: runner `exit 1`
- Evidence copiada: `restore-drill.env` e `git-bundle-verify-final.log`

## Artifact readback

- `SHA256SUMS`: `15/15 PASS`
- `root_compare_rc=0`
- `user_compare_rc=0`
- `git_bundle_rc=0`
- `restore-drill.env`: `result=PASS`
- Restore dirs residuais: nenhum

## Causa do runner exit 1

O harness comparou contagem de members do tar com contagem de paths extraídos:

- root: `323` members versus `329` paths;
- user: `76.710` members versus `76.714` paths.

Essas métricas não são equivalentes quando a extração materializa diretórios implícitos. O compare byte/metadata independente e o bundle verify passaram.

## Estado atual

- Runtime manifest: `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`.
- Apply: `20260906T233823+0000-1549801`, PASS.
- Verify-only: `20260906T234149+0000-1558144`, PASS.
- Failed units system/user: `0/0`.
- Backup preapply atual: checksummed PASS e operacionalmente supersede o backup histórico.

## Decisão

Preservar a falha do runner como evidência histórica. Não reabrir runtime nem substituir o backup atual. Corrigir futuros restore drills para comparar manifests normalizados ou conteúdo/metadata, não contagens heterogêneas.
