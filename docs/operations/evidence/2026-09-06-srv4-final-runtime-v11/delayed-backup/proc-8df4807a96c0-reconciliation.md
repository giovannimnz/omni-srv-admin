# Reconciliation — proc_8df4807a96c0

Data da reconciliação: 2026-09-06
Classificação: `partial-workload-failure`
Subtype: `npm-prefix-symlink-collision`
Current actionable: nenhum

## Proveniência

- Processo: `proc_8df4807a96c0`
- PID histórico: `2933150`
- Host: `atius-srv-4`
- Run do orchestrator: `20260906T055159+0000-956775`
- Runner: `exit 1`
- Log histórico: `proc-8df4807a96c0-setup.log`
- Session authority: messages `300007`, `300010` e `300011` da sessão `20260904_200755_1d1861`.

## Workload executado

O launcher corrigido exportou `PYTHONPATH="$ROOT/cli"`, entrou no resource governor e iniciou o orchestrator. O run concluiu oito steps antes do failure:

1. `preflight`
2. `packages`
3. `ubuntu-pro`
4. `identity-network`
5. `podman`
6. `desktop-xrdp`
7. `landscape`
8. `fleet-agent`

O log então registrou `START step=toolchains mode=apply` e falhou com:

- `npm error code EEXIST`;
- path `/home/ubuntu/.local/bin/npm`;
- tentativa de instalar npm globalmente no mesmo prefix que já continha o symlink fornecido pelo Node bundle.

## Causa

O orchestrator histórico executava `npm install -g --prefix "$HOME/.local" "npm@$NPM_VERSION" "@openai/codex@$CODEX_VERSION"`. O prefixo já continha `~/.local/bin/npm`, portanto npm recusou sobrescrever o arquivo.

## Correção incorporada

O source final separa responsabilidades:

- `install_node()` instala/atualiza npm dentro de `~/.local/opt/node-$NODE_VERSION-linux-arm64`;
- `~/.local/bin/npm` aponta ao `build-cpu-guard-wrapper.sh`, que despacha para
  o npm do Node install root dentro do cgroup governado;
- `apply_toolchains()` instala apenas Codex no prefix `~/.local` quando há drift;
- `verify_toolchains()` valida Node/npm/Bun/Codex e demais toolchains.

Provas atuais:

- source local, package instalado e versão commitada de `oci-arm64-host-setup.sh` são byte-equal;
- `npm=11.19.0`;
- `codex-cli=0.153.4`;
- test focado `test_oci_arm64_host_setup.py`: `12/12 PASS` com warnings-as-errors.
- A cópia pública do log redige o identificador de conta Ubuntu Pro; o log raw
  permanece apenas no host e sua hash original está na proveniência.

## Cadeia posterior

O próprio run parcial não é promovido a PASS. A correção foi restaged e novas retomadas ocorreram. A autoridade final é:

- apply `20260906T233823+0000-1549801`: PASS;
- verify-only `20260906T234149+0000-1558144`: PASS;
- runtime manifest `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- failed units system/user `0/0`;
- setup/governor processes residuais `0`.

## Decisão

Preservar `proc_8df4807a96c0` como failure histórico parcial de workload. O bug foi corrigido no source/package/runtime final e coberto por teste. Não reexecutar `--apply --resume`: não há drift ou current actionable. Não atribuir os runs finais ao processo falho.
