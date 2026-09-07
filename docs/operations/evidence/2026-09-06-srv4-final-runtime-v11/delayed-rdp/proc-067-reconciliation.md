# Reconciliação — proc_06700dd17aab

Data da reconciliação: 2026-09-06
Classificação: `historical-rdp-harness-false-negative`
Subtype: `auth-only-session-side-effect-plus-invalid-embedded-probe`
Current actionable: nenhum

## Proveniência

- Processo: `proc_06700dd17aab`
- PID histórico: `3003432`
- Launcher: `python3 /tmp/srv4-rdp-first-login.py`
- Target: `10.100.100.18:3389`
- Runner: `exit 1`
- Session authority: mensagens `301104`–`301137` da sessão `20260904_200755_1d1861`.

## Separação dos eixos

### 1. Autenticação

O primeiro `xfreerdp +auth-only` retornou `0` e emitiu `Authentication only, exit status 0`. A credencial veio do Vault e foi enviada apenas por stdin; nenhum valor foi preservado.

No XRDP/Xvnc deste host, `+auth-only` teve efeito lateral inesperado: criou uma sessão real `c5`, display `:1.0`. A reprodução atual repetiu esse comportamento com sessão `c7`, TLS 1.3 e ABNT2. A sessão atual foi terminada seletivamente após captura de evidência; XRDP não foi reiniciado.

### 2. Sessão desktop histórica

O journal histórico prova que a primeira conexão:

- recebeu acesso para `ubuntu`;
- iniciou `Xvnc` em `:1.0`;
- abriu sessão PAM;
- registrou `Session started successfully for user ubuntu on display 1`;
- aplicou keylayout `0x00000416` e `br(abnt2)`.

A coleta remota posterior do mesmo login registrou `Xvnc`, `lxsession`, `lxpanel` e `pcmanfm` na sessão `c5`, display `:1.0`, oito pastas XDG, dark theme e `light-locker` desabilitado.

### 3. Probe embutida

A probe original enviava Python multi-line dentro de um único argumento SSH. A reprodução byte-equivalente retorna `SyntaxError: '(' was never closed`, stdout vazio e rc `1`.

O harness só atualizava `remote_state` quando a probe retornava `0`. Por isso o erro de sintaxe virou `{}` e foi relatado incorretamente como `session did not reach desktop`.

### 4. Segunda conexão e screenshot negativa

Depois de `+auth-only` já ter ocupado a única sessão permitida por `MaxSessions=1`, o harness abriu outro cliente RDP. O segundo login foi negado pelo limite de sessões. A captura local `proc-067-historical-client-negative.png` mostra `login failed for user ubuntu` e área preta.

Esse arquivo é artifact negativo da segunda conexão. Não é prova do estado do primeiro desktop e não deve ser apresentado como screenshot de aceitação.

### 5. Framebuffer remoto

A captura direta posterior do display histórico `:1` mostra desktop escuro, painel inferior, atalhos Trash/Obsidian, launchers e indicador `BR(ABNT...)`, sem mensagem de erro visível. O estado de processos associa esse framebuffer à sessão `c5`.

A reprodução atual criou `c7/:1` por `+auth-only`, negociou TLS 1.3, aplicou ABNT2, iniciou sessão e gerou novo framebuffer escuro. `c7` foi encerrada seletivamente; o pós-cleanup registra `Xvnc=0`.

## Gap TLS encontrado e corrigido

O login histórico de 06:14 UTC selecionou RDP sem TLS porque cert/key ainda não existiam. Esse era um finding real separado do false negative do harness.

A cadeia posterior emitiu o leaf ATIUS, instalou cert/key e incorporou verificação ao setup. Estado atual:

- `security_layer=negotiate`, `crypt_level=high`;
- cert/key presentes, public keys correspondentes;
- SANs incluem FQDN, aliases e IPs do SRV-4;
- journal atual registra `selected [SSL]` e `TLSv1.3 / TLS_AES_256_GCM_SHA384`;
- `xrdp` e `xrdp-sesman` active/enabled;
- porta `3389` acessível somente em `10.100.100.18`, bloqueada no OCI private/public;
- oito pastas XDG e dark theme presentes.

## Autoridade final

- runtime manifest `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`;
- full apply `20260906T233823+0000-1549801`: `17/17 PASS`;
- verify-only `20260906T234149+0000-1558144`: `17/17 PASS`;
- failed units system/user `0/0`;
- setup processes `0`;
- sessão de teste atual ausente e `Xvnc=0`;
- backups atual e histórico: PASS.

## Decisão

Preservar `proc_06700dd17aab` como false negative histórico do harness, não como falha do XRDP. Preservar a screenshot local como artifact negativo e usar somente os framebuffers remotos, states e journals associados para provar desktop. O gap TLS descoberto foi corrigido e validado. Nenhum current actionable.

Futuros harnesses devem usar uma única conexão XRDP, copiar probes como arquivos sintaticamente validados, capturar stderr separado e encerrar apenas a sessão de teste identificada.
