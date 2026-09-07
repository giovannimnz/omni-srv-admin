# Reconciliation — proc_d7b3cd5a26de

Data da reconciliação: 2026-09-06
Classificação: `pre-workload-launcher-failure`
Subtype: `missing-pythonpath`
Current actionable: nenhum

## Proveniência

- Processo: `proc_d7b3cd5a26de`
- Host: `atius-srv-4`
- Comando tentou executar `python3 -m omni srv1-ops resources run ...`.
- Output: `/usr/bin/python3: No module named omni`.
- Runner: `exit 1`.

## Boundary da falha

A falha ocorreu no Python externo antes de importar a CLI e antes de iniciar o resource governor ou `oci-arm64-host-setup.sh`.

Provas atuais:

- `python3 -c 'import omni'` fora do source root: exit `1`.
- `PYTHONPATH="$ROOT/cli:$ROOT/modules/fork-sync/cli" python3 -c 'import omni'`: PASS.
- O package contém `cli/omni/__main__.py`.
- Nenhum run/receipt específico foi criado pelo processo falho.
- Zero processo residual de setup/governor.

## Relação com o relaunch

A falha foi detectada na própria sessão e o launcher foi imediatamente corrigido:

- Relaunch: `proc_8df4807a96c0`.
- Correção: `PYTHONPATH="$ROOT/cli"` antes de `python3 -m omni`.
- O relaunch entrou no orchestrator e avançou oito steps; depois encontrou um bug independente `npm EEXIST`. Não é correto atribuir PASS integral ao relaunch.
- A cadeia de fixes/retomadas posterior convergiu nos runs autoritativos:
  - apply `20260906T233823+0000-1549801`: PASS;
  - verify-only `20260906T234149+0000-1558144`: PASS.

## Estado atual

- Runtime manifest: `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`.
- Failed units system/user: `0/0`.
- Setup/governor processes residuais: `0`.
- Backup operacional atual: checksums e restore inventory PASS.
- Graphify: fresh/current no commit `511901f`, receipt `status=ok`.

## Decisão

Preservar `proc_d7b3cd5a26de` como falha histórica pré-workload do launcher, superseded pela correção de ambiente e pelos runs finais. Não reexecutar `--apply --resume`, porque não há drift ou current actionable. Entrypoints source-based devem sempre exportar o CLI path em `PYTHONPATH` antes de `python3 -m omni`.
