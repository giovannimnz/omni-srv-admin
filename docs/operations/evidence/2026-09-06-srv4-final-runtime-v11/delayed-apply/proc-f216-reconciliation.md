# Reconciliação — proc_f2166f90095c

Data da reconciliação: 2026-09-07
Evento histórico: 2026-09-06
Classificação: `historical-full-apply-operational-pass`
Estado atual: `superseded-by-sealed-444`
Current actionable: nenhum

## Proveniência

- Processo: `proc_f2166f90095c`
- PID histórico: `3169543`
- Launch authority: mensagem `300323` da sessão `20260904_200755_1d1861`.
- Poll/completion authority: mensagens `300325`, `300332` e notification tardia.
- Receipt-set authority: mensagens `300333` e `300348`.
- Run: `20260906T071332+0000-1040769`.
- Mode: `apply --resume` sob `omni-builds.slice`.
- Raw setup log: 24831 bytes, SHA-256 `86f71514cead1061df595131552c468535597549a2e7c3c84ca772f3d34a7ef2`.
- COMPLETE: 98 bytes, SHA-256 `55048ad20830cd0a060fd53da87b8cf26df4654afa719961cbd196799ac14192`.

## Execução

O run preserva 17 steps na ordem canônica:

1. `preflight`
2. `packages`
3. `ubuntu-pro`
4. `identity-network`
5. `podman`
6. `desktop-xrdp`
7. `landscape`
8. `fleet-agent`
9. `toolchains`
10. `desktop-apps`
11. `agents`
12. `gsd-graphify`
13. `agent-content`
14. `obsidian`
15. `resource-governor`
16. `desktop-theme`
17. `final-verify`

Resultado:

- START `17`;
- DONE `17`;
- SKIP `0`;
- FAIL markers `0`;
- `COMPLETE=PASS`;
- completed at `2026-09-06T07:15:09+00:00`.

O run não apenas reutilizou receipts antigos. Mudança no orchestrator invalidou os receipts anteriores e os 17 steps rodaram novamente.

## Receipt set contemporâneo

Logo após completion, o state compartilhado `completed/apply` continha 17 receipts. Todos tinham:

- `status=PASS`;
- `run_id=20260906T071332+0000-1040769`;
- `source_sha256=539594a1de03ee6a6ee5cdb75619630a5adfcecbd47865b15e5ffe86a8519278`.

O diretório de receipts é mutável e seus arquivos foram sobrescritos por runs posteriores. O packet preserva a transcrição estruturada do readback contemporâneo sem afirmar que os arquivos atuais ainda pertencem ao run.

## Source boundary

A promoção `proc_8eca51e24f34` completou imediatamente antes do launch:

- package `418/418`;
- manifest `d6fad21c664e48913cc537e0e43ac8d31db72a7299a7c369a2006f97580d0eed`;
- orchestrator `539594a1de03ee6a6ee5cdb75619630a5adfcecbd47865b15e5ffe86a8519278`.

O launcher leu o canonical path recém-promovido. O receipt-set contemporâneo vincula todos os 17 steps ao orchestrator `539594…`.

Limite: essa versão do orchestrator ainda não copiava `source-manifest.sealed.json` para o run. O manifest `d6fad…` é contexto externo forte, não run-local seal. Por isso o run é operational PASS, não source seal.

A reconstrução do package 418 foi exercitada separadamente em `../delayed-source/proc-8eca-reconstructed-restore-drill.json`: `418/418 PASS`.

## Warnings históricos

### Portal color-scheme sem DISPLAY

Três ocorrências de:

`WARN Portal color-scheme nao validado sem DISPLAY/gdbus/timeout`

Classificação: `deferred-to-session-proof`.

Não bloquearam o dark-theme validator. Apply/verify finais também preservam esse warning headless, enquanto o framebuffer RDP posterior prova o desktop LXDE escuro. Não é tratado como erro nem descrito como removido.

### Referências `.claude` do GSD installer

O installer de Codex e Hermes reportou duas vezes:

`Found 300 unreplaced .claude path reference(s) in 93 file(s)`

Classificação: `accepted-installer-warning`.

O warning permanece visível também nos runs finais. O contrato operacional aceito passa em:

- Codex profile `full`;
- Hermes profile `full`;
- Codex GSD Core `1.13.0`;
- Hermes GSD Core `1.13.0`;
- `gsd-tools.cjs check auto-mode` rc `0` nos dois runtimes;
- Graphify `0.9.23`.

Não há evidência de falha funcional causada por esse warning neste run. Também não se afirma que ele desapareceu.

## Autoridade atual

O run foi superseded por uma source de 444 files:

- manifest `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- orchestrator `59ee6d177edbcaf28af6cdf67325eae581dfafa4bc37204597fcafa0ad25a898`;
- apply final `20260906T233823+0000-1549801`: `17/17 PASS`, run-local seal `aa1883…`;
- verify final `20260906T234149+0000-1558144`: `17/17 PASS`, run-local seal `aa1883…`.

Readback atual:

- repo remoto clean;
- failed units system/user `0/0`;
- setup processes `0`;
- GSD `1.13.0/full` nos dois runtimes;
- Graphify `0.9.23`;
- backups atual e histórico PASS.

## Decisão

Preservar `proc_f2166f90095c` como full apply operacional histórico PASS, ligado ao orchestrator `539594…` e ao contexto de source 418. Não promover o process a source seal ou current authority.

Nenhum current actionable. Não rerodar apply/verify.
