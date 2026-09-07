# Reconciliação — proc_4ba8d1574e50

Data da reconciliação: 2026-09-07
Evento histórico: 2026-09-06
Classificação: `historical-full-apply-operational-pass-with-stale-external-manifest`
Estado atual: `superseded-by-sealed-444`
Current actionable: nenhum

## Proveniência

- Processo: `proc_4ba8d1574e50`
- PID histórico: `3209677`
- Launch authority: mensagem `300382` da sessão `20260904_200755_1d1861`.
- Poll/completion authority: mensagens `300383`, `300396` e notification tardia.
- Receipt-set authority: mensagem `300397`.
- Run: `20260906T072705+0000-1053677`.
- Mode: `apply --resume` sob `omni-builds.slice`.
- Raw setup log: 24831 bytes, SHA-256 `0808c770345afe80a8a8e6b9620d2e441bab5ec001a9db0351355f5eb2fb5535`.
- COMPLETE: 98 bytes, SHA-256 `20c49b047fb44e3c9bc7fd5146e1ca04754388b7f77cea18eeaad94234099ce7`.

## Execução

O run preserva os 17 steps canônicos:

`preflight`, `packages`, `ubuntu-pro`, `identity-network`, `podman`, `desktop-xrdp`, `landscape`, `fleet-agent`, `toolchains`, `desktop-apps`, `agents`, `gsd-graphify`, `agent-content`, `obsidian`, `resource-governor`, `desktop-theme`, `final-verify`.

Resultado:

- START `17`;
- DONE `17`;
- SKIP `0`;
- FAIL markers `0`;
- `COMPLETE=PASS`;
- completed at `2026-09-06T07:28:35+00:00`.

## Receipt set contemporâneo

Após completion, o readback do state compartilhado reportou:

- 17 receipts;
- 17 PASS;
- 17 vinculados ao mesmo source SHA;
- run único `20260906T072705+0000-1053677`;
- `source_sha256=54ba94542747d8d51072c2b5afe6012f81dfe8a2cc6e5ef8234a4278782318fb`.

O diretório `completed/apply` é mutável e os receipts foram sobrescritos por runs posteriores. O packet preserva uma transcrição estruturada do readback, não uma alegação de imutabilidade atual.

## Source boundary: manifest stale

Antes do launch, o orchestrator foi substituído in-place:

- anterior/declarado no manifest: `539594a1de03ee6a6ee5cdb75619630a5adfcecbd47865b15e5ffe86a8519278`;
- executado/receipts: `54ba94542747d8d51072c2b5afe6012f81dfe8a2cc6e5ef8234a4278782318fb`.

A mudança adicionou:

- verificação de self-FQDN para `10.14.1.14`;
- `apply_host_identity()` idempotente;
- reconciliação de `/etc/hosts` antes de `netplan generate`.

O diff exato está em `proc-4ba-orchestrator-diff.txt`.

A cópia versionável teve somente trailing whitespace removido para passar o
gate Git. O raw byte-exato e seu SHA estão registrados em
`proc-4ba-provenance.json` e preservados no backup pre-commit.

O manifest externo `d6fad21c664e48913cc537e0e43ac8d31db72a7299a7c369a2006f97580d0eed` ainda declarava 418 files e o orchestrator antigo `539594…`. Portanto:

- ele é contexto histórico stale;
- não representa a closure exata executada pelo run;
- não pode ser promovido a source seal do run;
- o orchestrator executado `54ba94…` é exato por receipt binding e preimage;
- a closure completa do restante do source não foi selada.

O run também antecede `source-manifest.sealed.json` dentro de cada run. Classificação correta: operational PASS no orchestrator exato, source closure unsealed.

## Efeito da correção self-FQDN

O readback contemporâneo após completion confirmou:

- `getent atius-srv-4.atius.internal = 10.14.1.14`;
- DNS authority = `10.14.1.14`;
- `/etc/hosts` contém `10.14.1.14 atius-srv-4.atius.internal atius-srv-4`;
- failed units `0/0`;
- upgradable packages `0`.

O self-FQDN gap foi resolvido pelo run.

## Warnings históricos

### Portal sem DISPLAY

Três ocorrências de `WARN Portal color-scheme nao validado sem DISPLAY/gdbus/timeout`.

Classificação: `deferred-to-session-proof`. Dark-theme validation passou; o framebuffer RDP posterior prova desktop LXDE escuro. Warning preservado, não descrito como removido.

### Referências `.claude`

Duas ocorrências de `Found 300 unreplaced .claude path reference(s) in 93 file(s)`.

Classificação: `accepted-installer-warning`. O warning também aparece nos installers finais. O contrato atual passa em GSD `1.13.0/full`, `check auto-mode` rc `0` em Codex/Hermes e Graphify `0.9.23`.

## Autoridade atual

Source atual:

- 444 files;
- manifest `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- orchestrator `59ee6d177edbcaf28af6cdf67325eae581dfafa4bc37204597fcafa0ad25a898`.

Runs finais:

- apply `20260906T233823+0000-1549801`: `17/17 PASS`, run-local seal `aa1883…`;
- verify-only `20260906T234149+0000-1558144`: `17/17 PASS`, run-local seal `aa1883…`.

Estado atual:

- repo remoto clean;
- failed units `0/0`;
- setup processes `0`;
- GSD `1.13.0/full` em Codex/Hermes;
- Graphify `0.9.23`;
- backups atual e histórico PASS.

## Decisão

Preservar `proc_4ba8d1574e50` como full apply operacional histórico PASS no orchestrator exato `54ba94…`, responsável por fechar o self-FQDN.

Não atribuir o run ao manifest `d6fad…`, porque esse manifest estava stale no orchestrator entry. Não promover o run a source seal/current authority.

Nenhum current actionable. Não rerodar apply/verify.
