# Disposition matrix — proc_06700dd17aab

| Finding / artifact | Classificação | Disposição | Evidência |
|---|---|---|---|
| Runner terminou exit 1 com `remote_state={}` | Harness false negative | Preservado; não usado como verdict do XRDP | `proc-067-notification.txt` |
| `xfreerdp +auth-only` retornou 0 | Auth PASS com side effect | Preservado; não encadear segunda conexão | `proc-067-historical-auth-result.json` |
| `+auth-only` abriu `c5/:1` | Sessão real histórica | Adopted como prova de login | `proc-067-historical-journal.log`, `proc-067-historical-remote-state.json` |
| Probe SSH retornou stdout vazio | Probe inválida | Reproduzida como SyntaxError; não confundir com desktop ausente | `proc-067-historical-probe-reproduction.json`, `proc-067-invalid-probe-excerpt.txt` |
| Segunda conexão mostrou `login failed` | Artifact negativo esperado | Preservado, explicitamente sem autoridade de desktop | `proc-067-historical-client-negative.png` |
| Framebuffer remoto histórico | Desktop proof | Adopted com state de processos | `proc-067-historical-remote-desktop.png`, `proc-067-historical-remote-state.json` |
| Login histórico selecionou RDP sem TLS | Finding real | Corrigido posteriormente | `proc-067-historical-journal.log` |
| Reprodução atual `c7/:1` | Current TLS desktop proof | Adopted; sessão terminada seletivamente | `proc-067-current-journal.log`, `proc-067-current-session-c7.txt`, `proc-067-current-tls-desktop.png` |
| Ingress XRDP | Current PASS | WG aberto; OCI private/public não abertos | `proc-067-current-ingress.json` |
| Resíduo da sessão de teste | Current PASS | `c7` ausente, `Xvnc=0`, serviços ativos | `proc-067-current-post-cleanup-state.json` |
| Runtime final | Current authority | Sem alteração | full apply `233823`, verify `234149`, manifest `aa1883d1…` |
