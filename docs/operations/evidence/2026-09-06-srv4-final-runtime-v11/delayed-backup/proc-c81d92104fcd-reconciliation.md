# Reconciliation — proc_c81d92104fcd

Data da reconciliação: 2026-09-06
Classificação: `pre-step-orchestrator-initialization-failure`
Subtype: `setup-log-process-substitution-race`
Current actionable: nenhum

## Proveniência

- Processo: `proc_c81d92104fcd`
- PID histórico: `2956808`
- Host: `atius-srv-4`
- Run dir: `20260906T060022+0000-973861`
- Runner: `exit 1`
- Log histórico: `proc-c81d92104fcd-setup.log`, 145 bytes.
- Session authority: messages `300021`, `300026`, `300027` e `300028` da sessão `20260904_200755_1d1861`.

## Boundary da falha

O outer resource governor iniciou em `omni-builds.slice`, validou o doctor e lançou o script. O orchestrator criou o run dir, mas falhou durante a inicialização do logging antes de qualquer step:

- `setup.log` contém apenas o erro de `chmod`;
- `FAILED` ausente;
- `COMPLETE` ausente;
- receipts próprios do run: `0`;
- nenhum `START step=` foi emitido.

Os oito receipts então existentes pertenciam ao run anterior `20260906T055159+0000-956775`; não são atribuídos a este processo.

## Causa

O script histórico fazia:

1. `exec > >(tee -a "$LOG_FILE") 2>&1`;
2. `chmod 600 "$LOG_FILE"`.

A process substitution inicializa `tee` de forma assíncrona. O shell podia executar `chmod` antes de `tee` criar o arquivo, produzindo `No such file or directory` sob `set -e`.

## Correção incorporada

A ordem final é determinística:

1. `touch "$LOG_FILE"`;
2. `chmod 600 "$LOG_FILE"`;
3. `exec > >(tee -a "$LOG_FILE") 2>&1`.

Provas atuais:

- teste de ordem no `test_oci_arm64_host_setup.py`;
- test focado `12/12 PASS` com warnings-as-errors;
- source local, package instalado e commit de `oci-arm64-host-setup.sh` são byte-equal;
- runs finais posteriores produziram logs completos e status PASS.

## Autoridade final

- apply `20260906T233823+0000-1549801`: PASS;
- verify-only `20260906T234149+0000-1558144`: PASS;
- runtime manifest `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- failed units system/user `0/0`;
- setup/governor processes residuais `0`.

## Decisão

Preservar `proc_c81d92104fcd` como failure histórico de inicialização pré-step. O bug foi corrigido e coberto por teste. Não reexecutar `--apply --resume`; não há drift ou current actionable. Não atribuir receipts herdados ao run falho.
