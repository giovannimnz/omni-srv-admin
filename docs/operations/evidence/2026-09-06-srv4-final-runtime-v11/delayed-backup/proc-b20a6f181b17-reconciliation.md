# Reconciliation — proc_b20a6f181b17

Data da reconciliação: 2026-09-06
Classificação: `post-workload-harness-failure`
Subtype: `localized-checksum-token-mismatch`
Current actionable: nenhum

## Proveniência

- Processo: `proc_b20a6f181b17`
- Comando: `/tmp/srv4-verify-existing-backup.sh` no `atius-srv-4`
- Backup: `/home/ubuntu/.backups/srv4-full-setup-parity-pre-20260906T041902+0000`
- Runner: `exit 1`
- Output tardio: `CHECKSUM_ENTRIES=13`, `CHECKSUM_FAILURES=13`, `ROOT_COMPARE=0`, `USER_COMPARE=0`, `BUNDLE=0`, `RESTORE=PASS`.

## Workload readback atual

- `SHA256SUMS`: 15 rows, `sha256sum -c` exit 0, 15/15 `OK`.
- `restore-drill.env`:
  - `root_compare_rc=0`;
  - `user_compare_rc=0`;
  - `git_bundle_rc=0`;
  - `result=PASS`.
- `git bundle verify`: exit 0.
- Restore scratch residual: nenhum.

## Causa do wrapper exit 1

O script executou:

`failures=$(grep -vc 'SUCESSO$' /tmp/srv4-backup-readback.log || true)`

O `sha256sum -c` do host emitiu `: OK`, não `: SUCESSO`. Logo, o wrapper contou todas as 13 linhas como falha, embora o próprio `sha256sum` tivesse retornado 0 e todos os compares/bundle tivessem passado. O teste final `[ "$failures" -eq 0 ]` causou o runner `exit 1`.

## Estado atual

- Runtime manifest: `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`.
- Apply: `20260906T233823+0000-1549801`, PASS.
- Verify-only: `20260906T234149+0000-1558144`, PASS.
- Failed units system/user: `0/0`.
- Backup operacional atual: checksums PASS e `RESTORE-INVENTORY.json status=PASS`.
- Graphify: fresh/current no commit `4cb0695`, receipt `status=ok`.

## Decisão

Preservar o runner exit 1 como falha histórica do harness, não do backup. Não reabrir runtime, restore ou backup. Futuros scripts devem confiar no exit code de `sha256sum -c`, ou fixar `LC_ALL=C` e parsear o token canônico `: OK`; nunca depender de palavra localizada.
