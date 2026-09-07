# Disposition matrix — proc_d27e0eaeee4b

| Finding / artifact | Classificação | Disposição | Evidência |
|---|---|---|---|
| Runner exit `1` | Harness FAIL | Preservado; não promovido a PASS | `proc-d27-notification.txt` |
| Auth-only rc `0` | Auth PASS com side effect | Preservado | `proc-d27-auth-result.json`, TLS journal |
| Sessão `c6/:1` | Operational PASS | Adopted como prova de sessão | `proc-d27-proof-final.json`, `proc-d27-remote-state-c6.json` |
| TLS 1.3 + SSL | Security PASS | Adopted | `proc-d27-historical-tls-journal.log` |
| ABNT2 `0x00000416` | Keyboard PASS | Adopted | TLS journal e proof |
| Probe rc 0/output vazio | Invalid probe | Reproduzida como stdin suprimido por `ssh -n` | `proc-d27-probe-reproduction.json`, `proc-d27-harness-excerpt.txt` |
| Segunda conexão | Denied by session limit | Não invalida a sessão criada pelo auth-only | TLS journal |
| Framebuffer `c6` | Desktop proof | Adopted com state/journal | `proc-d27-desktop-c6.png`, `proc-d27-visual-observation.md` |
| Primeiro cleanup verifier | Verifier error pós-mutação | Superseded por journal/state posterior | `proc-d27-c6-cleanup-journal.log` |
| Sessão/processos atuais | Current PASS | `c6` ausente, Xvnc/watchdogs/setup `0` | `proc-d27-current-state.json` |
| Source versionado | Sem antipattern throwaway | Nenhum source patch necessário | search zero |
| Runtime final | Current authority | Sem alteração | apply `233823`, verify `234149`, manifest `aa1883d1…` |
