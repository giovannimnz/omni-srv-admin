# Reconciliação — proc_1a7a5a507eb3

Data da reconciliação: 2026-09-07
Evento histórico: 2026-09-06
Classificação do workload: `operational-pass`
Classificação do launcher: `post-workload-cleanup-skipped-after-exec`
Current actionable: resolvido

## Proveniência

- Processo: `proc_1a7a5a507eb3`
- PID histórico: `3113609`
- Host: `atius-srv-4`
- Session authority: mensagens `301273`–`301279` da sessão `20260904_200755_1d1861`.
- Script: `proc-1a7-lifecycle.sh`
- SHA-256: `de6c09d738bc5312b8281be6944219a46e74e4f06992aceaf494cfd5ce8d7bc4`
- Runner: exit `0`.

## Workload

O lifecycle test criou um display Xvfb temporário `:97`, iniciou os watchers de teclado e painel, derrubou o display e aguardou sua saída autônoma.

Resultado original:

- `keyboard_alive=0`;
- `panel_alive=0`;
- `elapsed_max_sec=10`;
- `watchdog_display_lifecycle=PASS`;
- exit `0`.

A `trap cleanup EXIT` dentro do payload encerrou os PIDs temporários restantes e removeu o workdir `omni-watchdog-lifecycle-*`.

## Source e runtime


O source canônico gera ambos os scripts com o guard:

`xdpyinfo >/dev/null 2>&1 || exit 0`

Validação:

- teste focado `test_xrdp_watchers_exit_when_their_display_disappears`: `1 passed`;
- `dark-themectl.sh` e lifecycle script passam `bash -n`;
- keyboard gerado e instalado: SHA `22dafbef4c1e5ee88466a81090eeac309d4a9493943dcd27afb9065d6a38522e`;
- panel gerado e instalado: SHA `e72c1057cd4e0ef434b9bb777dc59ebd6ab6e90dc898c220d5e5933524bd99ba`;
- ambos instalados em modo `0755` e contêm exatamente um display-exit guard.

## Falha de cleanup externo

O launcher remoto continha:

`exec /tmp/srv4-watchdog-lifecycle.sh; rc=$?; rm -f ...`

Quando `exec` teve sucesso, ele substituiu o shell remoto. `rc=$?`, `rm -f` e `exit $rc` ficaram inalcançáveis. O workload passou, mas `/tmp/srv4-watchdog-lifecycle.sh` permaneceu.

Os dois scripts testados também deixaram lockfiles vazios específicos de `:97`. Isso é compatível com `exec 9>lock`; os processos já haviam terminado e nenhum processo mantinha os arquivos abertos.

## Cleanup aplicado

Antes de remover qualquer resíduo:

- launcher copiado para `/home/ubuntu/.backups/proc-1a7-lifecycle-residue-20260907T032441+0000`;
- SHA-256 do source e backup: `de6c09d738bc5312b8281be6944219a46e74e4f06992aceaf494cfd5ce8d7bc4`;
- dois lockfiles copiados para `/home/ubuntu/.backups/proc-1a7-lock-residue-20260907T032624+0000`;
- ambos os backups passaram `sha256sum -c`.

Depois:

- launcher remoto: ausente;
- keyboard/panel lockfiles `:97`: ausentes;
- workdirs do lifecycle: `0`;
- `Xvfb :97`: `0`;
- keyboard watchers: `0`;
- panel watchers: `0`;
- setup processes: `0`.

O primeiro comando de cleanup retornou `1` depois de remover corretamente o launcher porque o probe inline de `test_dirs` perdeu aspas. O readback separado corrigiu o probe e confirmou todos os resíduos ausentes. Não se classifica isso como falha da remoção.

## Estado final

- `xrdp` e `xrdp-sesman`: active;
- failed units system/user: `0/0`;
- runtime manifest: `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- full apply final `233823`: PASS;
- verify final `234149`: PASS;
- backups operacionais atual e histórico: PASS.

## Decisão

Preservar o lifecycle como PASS operacional. Preservar a falha de cleanup externo como finding real do launcher throwaway, corrigido nesta reconciliação. Nenhum source versionado contém esse launcher; não há source patch no repo. Futuros launchers remotos devem usar `trap EXIT` sem `exec`, ou executar o payload, capturar rc, limpar e então sair.
