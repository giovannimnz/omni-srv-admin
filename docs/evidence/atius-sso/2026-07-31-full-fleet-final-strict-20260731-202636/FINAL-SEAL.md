# Final seal — Atius SSO fleet

- Veredito: `PASS_HOST_LOCAL_SSO_VISUAL_FLEET`.
- Fleet: `12/12` hosts.
- Lifecycle: `24/24` ciclos completos.
- Screenshots: `96/96` estados obrigatórios.
- Vision: `12/12 PASS`.
- `completeFleetEvidence=true`.
- Hostname: app-local preservado em login, aplicação e logout.
- URL humana: `https://<app>.atius.com.br/login`.
- `/sso`: compatibilidade controlada, não URL humana.
- Grafana: 12 painéis com dados nos dois ciclos, inclusive TCP.
- Remote: desktop real renderizado nos dois ciclos; canvas preto rejeitado pelo harness.
- Logout: controle real clicado e retorno app-local `/login` nos dois ciclos.
- Secrets na evidência: zero findings.
- Auditor documental: `8/8` surfaces, `20/20` checks.
- GBrain: slug canônico
  `aisecondbrain/30-recursos/atius/sso-atius-guia-canonico` atualizado e
  readback com o marker deste fleet.
- Graphify final pós-hardening: rebuild user-owned governado `success/status=0`;
  `14.148` nodes, `20.204` edges, `stale=false`, `commit_stale=false`,
  `DiskPressure=False`, artifacts source/dest byte-exact e zero arquivos
  root-owned.
- O update final exigiu `--force` porque a remoção deliberada do diretório
  default contaminado reduziu o grafo em exatamente `1` node e `1` edge; o
  owner canônico 2026-07-30 permaneceu preservado e o snapshot pré-force teve
  restore drill PASS.
- Graphify queries: `waitForRemoteFramebuffer` `33/42`,
  `coredns-tcp-canary` `2/1`, `mt5-remote-auth-proxy` `69/123`,
  `atius-sso-url-regression` `7/6` (nodes/edges).
- Reconciliação tardia do processo `proc_9db50fade3fc`: o listener `3200`
  era um smoke Next órfão com cwd `.rollback-smoke-url-standard (deleted)`,
  fora de PM2/systemd/Apache. O runtime VPN canônico permaneceu no PID do
  `vpn-frontend.service`, porta `3100`, e não foi reiniciado.
- Pós-cleanup: porta `3200` liberada, zero processos com cwd deletado,
  Apache `Syntax OK`, VPN pública `200`, lifecycle VPN `2/2 PASS_SUBSET`,
  `8` screenshots e vision PASS. Evidência separada:
  `../2026-07-31-vpn-post-orphan-cleanup-20260731-205753/`.
- Harness endurecido para honrar `E2E_OUTPUT_DIR`; regression test `2/2`
  provou isolamento da saída e ausência de recriação do diretório default.
- GBrain: guia canônico reimportado no mesmo slug; readback confirmou
  `E2E_OUTPUT_DIR` e o path da evidência pós-cleanup.
- Commit/push: nenhum.

Owner documental: `docs/domain/atius-sso-lifecycle-matrix.md`.
Revisão visual: `VISUAL-REVIEW.md`.
Resultado estruturado: `report.json` e `verification.json`.
Integridade: `SHA256SUMS`.
