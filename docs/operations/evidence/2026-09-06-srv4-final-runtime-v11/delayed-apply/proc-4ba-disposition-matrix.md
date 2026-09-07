# Disposition matrix — proc_4ba8d1574e50

| Finding / artifact | Classificação | Disposição | Evidência |
|---|---|---|---|
| Runner exit `0` | Transport success | Preservado, não usado sozinho como approval | notification |
| Run `072705` | Historical full apply operational PASS | 17 START/DONE, zero skip/fail, COMPLETE PASS | setup log/run-state/COMPLETE |
| Receipt set | Contemporaneous operational evidence | 17/17 PASS, mesmo run e orchestrator `54ba94…`; files depois sobrescritos | contemporary receipts |
| Manifest `d6fad…` | Stale external context | Não atribuído como source seal do run | source boundary |
| Orchestrator `54ba94…` | Exact executed orchestrator | Adopted por deploy pre-launch + 17 receipts | source boundary/diff/message `300397` |
| Source closure | Unsealed | Não reconstruída como exact run source | ausência de run-local seal + stale manifest |
| Self-FQDN | Historical fixed behavior | `getent`/DNS/hosts convergiram em `10.14.1.14` | contemporaneous readback |
| Portal sem DISPLAY | Deferred-to-session-proof | Warning preservado; framebuffer posterior fecha visual | warning disposition/delayed-rdp |
| `.claude` references | Accepted installer warning | Warning preservado; GSD runtime contract passa | warning disposition/current authority |
| Source final 444 | Current authority | Supersedes o run sem apagar PASS histórico | current authority |
| Runtime atual | Current PASS | Repo clean, health `0/0`, setup `0` | current authority/live readback |
