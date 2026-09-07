# Reconciliação — proc_8eca51e24f34

Data da reconciliação: 2026-09-07
Evento histórico: 2026-09-06
Classificação: `historical-source-promotion-operational-pass`
Estado atual: `superseded-by-sealed-444`
Current actionable: nenhum

## Proveniência

- Processo: `proc_8eca51e24f34`
- PID histórico: `3167182`
- Session authority: `20260904_200755_1d1861`
- Build receipt: mensagem `300314`.
- Promotion launch: mensagens `300316` e `300317`.
- Promotion completion: mensagem `300319` e notification tardia.
- Immediate apply: mensagens `300322`, `300323`, `300332`.
- Receipt-set readback: mensagens `300333` e `300348`.
- Cleanup ENOSPC: mensagens `302214`–`302219`.

## Package promovido

O package foi construído a partir do worktree no HEAD histórico `f851a0353e7ed3f03e736b571270ff7baaf8c357`:

- 418 files declarados;
- 588930127 bytes de source;
- manifest SHA-256 `d6fad21c664e48913cc537e0e43ac8d31db72a7299a7c369a2006f97580d0eed`;
- orchestrator SHA-256 `539594a1de03ee6a6ee5cdb75619630a5adfcecbd47865b15e5ffe86a8519278`;
- archive SHA-256 `b30eb57049b854c44b99686f0a63a57a8e40616221387fc2ac827a792e12412f`;
- archive size 392104728 bytes.

O promoter verificou o archive local, copiou por SCP, verificou o archive remoto, extraiu para diretório novo e validou os 418 entries por SHA-256 e bytes. Resultado remoto: `418`, `bad=0`.

A promoção foi atômica no nível do path:

1. o canonical source anterior foi movido para `omni-setup-source.pre-20260906T071252+0000`;
2. o tree validado foi movido para `~/.local/share/omni-setup-source`;
3. o archive remoto foi removido;
4. o orchestrator recebeu mode 0755;
5. o repo remoto permaneceu clean.

## Apply imediato

Logo após a promoção, o run `20260906T071332+0000-1040769` executou `17/17` steps, zero skip e `COMPLETE=PASS`.

O readback contemporâneo registrou 17 receipts em `completed/apply`, todos:

- `status=PASS`;
- `run_id=20260906T071332+0000-1040769`;
- `source_sha256=539594a1de03ee6a6ee5cdb75619630a5adfcecbd47865b15e5ffe86a8519278`.

Esses receipts foram sobrescritos por runs posteriores no diretório compartilhado, mas sua leitura contemporânea está preservada na session authority. O run dir ainda preserva `17 START`, `17 DONE`, `COMPLETE=PASS` e log SHA-256 `86f71514cead1061df595131552c468535597549a2e7c3c84ca772f3d34a7ef2`.

Limite de autoridade: esse run antecede a cópia de `source-manifest.sealed.json` para cada run. Portanto ele é operational PASS vinculado ao orchestrator exato, não um current source seal.

## Linhagem 418 posterior

O inventário por `source_manifest_entries=418` encontrou oito runs posteriores:

- 6 com `COMPLETE=PASS`;
- 2 com `FAILED` no step `agents`;
- todos sem run-local source seal.

Esses runs provam uma linhagem com 418 entries. Não são todos atribuídos ao manifest `d6fad…`, porque o backing tree recebeu mudanças in-place e variantes 418 foram promovidas depois.

## Archive e backup histórico

O archive remoto foi removido pelo próprio promoter. O archive local permaneceu em `/tmp` após o outer `exec` e foi removido deliberadamente no cleanup ENOSPC posterior.

O receipt checksummed `/home/ubuntu/.backups/srv4-staging-temp-cleanup-20260906T073423-0300/receipt.env` registra:

- `/tmp/srv4-setup-source-seal.tgz`;
- 392104728 bytes;
- cleanup de staging reproduzível;
- SHA-256 do receipt `484f8c86067c3ba03c2bb217e936e67dfe1a0377dd4f0f69e9f51cd41e5f6366`.

O archive original não está disponível hoje.

## Restore drill reconstruído

O backup `/home/ubuntu/.backups/omni-setup-source-pre-final-20260906T092728+0000` ainda contém:

- o manifest exato `d6fad…`;
- os 418 paths declarados;
- 417/418 entries byte-equal ao manifest;
- o orchestrator alterado posteriormente;
- o preimage exato `oci-arm64-host-setup.sh.pre-self-hosts-1788679602`, hash `539594…`;
- extras de runtime, como `__pycache__`, fora do manifest.

O restore drill não alterou o backup. Criou uma árvore temporária normalizada usando:

- 417 entries declarados do backing tree;
- 1 orchestrator do preimage exato;
- somente paths declarados no manifest.

Resultado:

- restored `418/418`;
- bad `0`;
- missing `0`;
- extra `0`;
- modes/bytes/SHA-256: PASS;
- árvore temporária removida;
- backup original intacto.

Conclusão de restore: não existe direct archive restore nem direct tree restore, mas o snapshot é deterministicamente reconstruível e esse processo foi exercitado.

## Supersession

A primeira autoridade posterior explicitamente identificada tem 421 entries:

- apply `20260906T103837+0000-1165560`: `17/17 PASS`;
- verify `20260906T104148+0000-1174121`: `17/17 PASS`.

A autoridade final é a source de 444 files:

- manifest `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- orchestrator `59ee6d177edbcaf28af6cdf67325eae581dfafa4bc37204597fcafa0ad25a898`;
- apply `20260906T233823+0000-1549801`: `17/17 PASS`, run-local seal `aa1883…`;
- verify `20260906T234149+0000-1558144`: `17/17 PASS`, run-local seal `aa1883…`.

## Estado atual

- canonical source: 444 files, manifest `aa1883…`;
- canonical repo remoto: clean;
- archive local/remoto `srv4-setup-source-seal.tgz`: ausente;
- setup processes: `0`;
- failed units system/user: `0/0`;
- backups atual e histórico: PASS.

## Decisão

Preservar `proc_8eca51e24f34` como promoção operacional histórica válida, seguida de apply integral válido no orchestrator `539594…`. Não promovê-la à autoridade atual e não atribuir toda a linhagem 418 ao manifest `d6fad…`.

A ausência do archive direto está fechada pelo receipt de cleanup e pelo restore drill reconstruído `418/418`. Nenhum current actionable; não rerodar apply/verify.
