# Reconciliation — proc_419dd742547f

Data da reconciliação: 2026-09-06
Classificação: `historical-full-verify-operational-pass`
Authority: operacional, não seal/review
Current actionable: nenhum

## Proveniência

- Processo: `proc_419dd742547f`
- PID histórico: `2998895`
- Host: `atius-srv-4`
- Run: `20260906T061314+0000-991532`
- Runner: `exit 0`
- Session authority: mensagem `300060` para launch e `300062` para completion, sessão `20260904_200755_1d1861`.
- Log histórico: `proc-419dd742547f-setup.log`.

## Escopo executado

O run executou uma verificação completa e separada após o primeiro apply resumido:

- `START=17`;
- `DONE=17`;
- `SKIP=0`;
- `COMPLETE` registra `status=PASS mode=verify-only`;
- `FAILED` ausente;
- observação Hermes do run: commit `245e48008fa814b3251f50755eb656bd9fb86cb1`.

## Contexto de source

Antes do run, o package de 265 arquivos foi construído e promovido com validação `bad=0`:

- manifest externo: `818cc5af6dd8fc3d8aafa405da8f66a59b8b222b1f1321c04c9ee5e58c6c1ca4`;
- source head declarado: `f851a0353e7ed3f03e736b571270ff7baaf8c357`;
- orchestrator declarado: `477d4fb1cf02a97ce6b67bff52dd17a2badbb2e6f30a21ac4dd3c6fe7adc537a`;
- evidence da construção/promoção: mensagens `299333` e `300058`.

O run não copiou `source-manifest.sealed.json` para seu próprio diretório. O manifest externo é contexto pré-run, não seal run-local.

O backup histórico que hoje contém esse manifest preserva o JSON, mas recebeu patches in-place posteriores no orchestrator:

- readback atual: 264/265 entries conferem;
- orchestrator atual no backup: `ba5dd2c78105bb70efb4db9abb4ac236f989e728b2c19df63d85edbdbb06110d`;
- não se atribui essa divergência posterior ao momento do run;
- o backing tree atual não permite reconstruir source closure exata do run.

## Limitação de autoridade

`exit 0` e `17/17` comprovam postconditions operacionais naquela execução. Não equivalem a:

- seal de source imutável;
- review independente;
- autoridade mais nova que os runs finais.

## Estado supersessor

A autoridade final é:

- full apply `20260906T233823+0000-1549801`: `17/17 PASS`;
- verify-only `20260906T234149+0000-1558144`: `17/17 PASS`;
- manifest run-local/final `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- failed units system/user `0/0`;
- setup/governor processes residuais `0`;
- backups atual e histórico: PASS.

## Decisão

Preservar `proc_419dd742547f` como verify-only operacional completo histórico. Não promovê-lo a seal ou review GO e não reexecutar o setup: os runs finais mais novos e selados supersedem essa evidência. Nenhum current actionable.
