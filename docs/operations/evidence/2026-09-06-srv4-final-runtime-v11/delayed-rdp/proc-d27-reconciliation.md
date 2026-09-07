# Reconciliação — proc_d27e0eaeee4b

Data da reconciliação: 2026-09-07
Evento histórico: 2026-09-06
Classificação: `historical-rdp-harness-false-negative`
Subtype: `ssh-n-stdin-suppression-plus-auth-only-session-side-effect`
Runner: FAIL
Sessão TLS observada: PASS operacional
Current actionable: nenhum

## Proveniência

- Processo: `proc_d27e0eaeee4b`
- PID histórico: `3116616`
- Launcher: `python3 /tmp/srv4-rdp-tls-final.py`
- Target: `10.100.100.18:3389`
- Session authority: mensagens `301279`–`301289` e `300270`–`300290` da sessão `20260904_200755_1d1861`.
- Harness bruto: SHA-256 `7e6125f46731ea107ac60bc9ef2c35bab3596960e6e068155be7fad49a76454a`.
- Backup bruto restrito: `/home/ubuntu/.backups/proc-d27-rdp-harness-raw-20260907T005743-0300`.

## Eixo 1 — auth e criação da sessão

O primeiro `xfreerdp +auth-only` retornou `0` e emitiu `Authentication only, exit status 0`.

Nesse XRDP/Xvnc, `+auth-only` não foi side-effect-free. Criou a sessão real `c6`, display `:1.0`. O journal registra:

- `selected [SSL]`;
- TLS 1.3 com `TLS_AES_256_GCM_SHA384`;
- keylayout sobrescrito para `0x00000416` / `br(abnt2)`;
- access granted para `ubuntu`;
- `Starting session ... display :1.0`;
- `Session started successfully for user ubuntu on display 1`.

A segunda conexão iniciada pelo harness encontrou a sessão única já ocupada e foi negada por `MaxSessions=1`. Isso não invalida `c6`.

## Eixo 2 — probe inválida

`remote_state()` chamava:

`ssh -n ... python3 -`

mas tentava fornecer o programa remoto com `subprocess.run(..., input=script)`.

`ssh -n` redireciona stdin para `/dev/null`. O `python3 -` remoto recebeu EOF, não executou o payload, saiu `0` e produziu stdout/stderr vazios. O harness converteu isso em:

`{'probe_rc': 0, 'stderr': ''}`

A reprodução determinística sem abrir desktop confirmou:

- com `-n`: rc `0`, output vazio, payload não executado;
- sem `-n`: rc `0`, marker `PROBE_PAYLOAD_EXECUTED`, payload executado.

Logo, `desktop not ready` é false negative da observação.

## Eixo 3 — desktop pós-TLS

A sessão `c6` foi inspecionada fora do harness defeituoso:

- `Xvnc :1`;
- `/usr/bin/lxsession -s LXDE -e LXDE`;
- `lxpanel --profile LXDE`;
- `pcmanfm --desktop --profile LXDE`;
- oito pastas XDG;
- dark theme presente.

O framebuffer remoto `proc-d27-desktop-c6.png` mostra desktop escuro 1024×768, painel inferior, atalhos/launchers e indicador `BR(ABNT...)`, sem erro visual.

A imagem não prova TLS sozinha; journal e proof estruturado fornecem essa associação.

## Eixo 4 — cleanup

A primeira tentativa de cleanup terminou `c6`, mas o verificador posterior teve quoting inválido em `awk $4`. A mutação e a verificação são classificadas separadamente.

A autoridade posterior confirmou:

- `c6=absent`;
- `Xvnc=0`;
- watchers `0`;
- scopes abandonados `0`;
- artifacts remotos `/tmp/srv4-rdp-tls-final.{py,png}` ausentes;
- XRDP/sesman ativos;
- failed units `0/0`.

O state collector atual reproduziu esse estado sem abrir nova sessão.

## Source

Busca no source versionado não encontrou o antipattern `ssh -n ... python3 -` com payload stdin. O harness era throwaway sob `/tmp`; não há source patch no repo para esse arquivo.

O procedimento durável foi corrigido nas skills: probes remotas enviadas por stdin não usam `ssh -n`; preferir copiar script sintaticamente validado e invocá-lo por path.

## Autoridade final

- runtime manifest `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- full apply `20260906T233823+0000-1549801`: `17/17 PASS`;
- verify-only `20260906T234149+0000-1558144`: `17/17 PASS`;
- TLS cert/key presentes e correspondentes;
- `c6` ausente, Xvnc/watchdogs/setup processes `0`;
- XRDP/sesman active;
- failed units system/user `0/0`;
- backups atual e histórico: PASS.

## Decisão

Preservar `proc_d27e0eaeee4b` como runner FAIL por probe inválida. Preservar a sessão `c6` como evidência operacional separada de TLS/desktop PASS. Não promover o processo inteiro a PASS. Nenhum current actionable e nenhuma nova sessão necessária.
