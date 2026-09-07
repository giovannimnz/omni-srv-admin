# Disposition matrix — proc_1a7a5a507eb3

| Finding / artifact | Classificação | Disposição | Evidência |
|---|---|---|---|
| `keyboard_alive=0 panel_alive=0` | Operational PASS | Preservado | `proc-1a7-notification.txt`, `proc-1a7-lifecycle.sh` |
| Watchers encerram após display morrer | Current source/runtime PASS | Teste focado e byte parity | `proc-1a7-focused-test.log`, `proc-1a7-source-runtime-parity.json` |
| Workdir temporário do payload | Cleanup PASS | `trap EXIT` removeu; readback zero | `proc-1a7-post-cleanup-state.json` |
| Launcher remoto em `/tmp` | Post-workload cleanup skipped | Backup checksummed e removido | backup `proc-1a7-lifecycle-residue-*` |
| Dois lockfiles vazios `:97` | Test residue | Sem holders; backup checksummed e removidos | backup `proc-1a7-lock-residue-*` |
| Probe inline de `test_dirs` perdeu aspas | Cleanup verifier error | Superseded por state collector estruturado | `proc-1a7-post-cleanup-state.json` |
| Source versionado | Sem launcher defeituoso | Nenhum patch necessário | search zero; source commit `a99d9a8` |
| Runtime final | Current authority | Sem alteração | manifest `aa1883d1…`, XRDP active, health `0/0` |
