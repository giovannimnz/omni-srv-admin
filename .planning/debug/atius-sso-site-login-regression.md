---
status: resolved
trigger: "Os cinco sites Atius deixaram de concluir o SSO; VPN e logout mudavam o hostname visível para sso.atius.com.br. Validar dois ciclos completos por site com screenshots."
created: 2026-07-30
updated: 2026-07-30
---

## Symptoms

- expected: cada site permanece em `https://<site>.atius.com.br`; acesso anônimo termina em `/login`; login entra no app; logout retorna ao `/login` do mesmo host.
- actual: `vpn.atius.com.br` redirecionava entrada, `/login` e logout para `sso.atius.com.br`; AdGuard concluía logout no control plane central; o relatório anterior marcou PASS sem dois ciclos completos de logout e relogin.
- errors: regressão de contrato e evidência incompleta, sem erro único de aplicação.
- timeline: detectado pelo usuário em 2026-07-30 após rollout SSO dos cinco sites.
- reproduction: abrir contexto anônimo em `/`, autenticar, encerrar sessão e observar a URL final.

## Current Focus

- hypothesis: implementações divergentes misturaram control plane central visível e facades locais; testes antigos validavam apenas primeiro redirect/login e até exigiam o host central na VPN.
- test: comparar redirects anônimos, source/live, logout e dois ciclos headless completos por host.
- expecting: todos os quatro estágios de cada ciclo mantêm o hostname do app e logout termina em `/login` limpo.
- next_action: aplicar sources testados, reiniciar VPN/AdGuard e executar 2 ciclos E2E por host.
- reasoning_checkpoint:
  hypothesis: "VPN expunha diretamente buildSsoLoginUrl/buildSsoLogoutUrl; AdGuard devolvia centralLogoutBridgeUrl; admin edges já tinham facade local, mas sem cobertura E2E suficiente."
  confirming_evidence:
    - "VPN `/`, `/login` e `/logout` terminavam em `https://sso.atius.com.br/login`."
    - "phase09-sso-contract.mjs exigia explicitamente hostname `sso.atius.com.br`, cristalizando a regressão."
    - "AdGuard POST `/logout` retornava `centralLogoutBridgeUrl`."
    - "Grafana, Portainer e Docker redirecionavam anonimamente para `/login` no próprio host."
  falsification_test: "a hipótese falha se build/source corrigidos ainda trocarem host ou se o login real não emitir sessão válida."
  fix_rationale: "uma facade local por app mantém a URL pública estável enquanto usa o backend Atius server-side; logout apaga cookies e retorna ao `/login` local."
  blind_spots: "logout nativo de cada vendor pode usar rotas próprias; o contrato canônico validado usa a facade app-local `/logout` ou `/api/auth/logout`."
- tdd_checkpoint:
  red: "contratos antigos exigiam central host na VPN/AdGuard."
  green: "VPN contract+typecheck PASS; AdGuard 20/20 PASS; admin-edge source/config PASS."
  refactor: "pendente de E2E browser e closeout."

## Evidence

- timestamp: 2026-07-30T18:05:00-03:00
  result: "Graphify fresco no commit 79844a3; 13841 nodes, 19832 edges, commit_stale=false."
- timestamp: 2026-07-30T18:06:00-03:00
  result: "Baseline público: Grafana/Portainer/Docker locais em `/login`; VPN no host central; AdGuard GET root sem HTML retornou 401 e browser document apontou para login local."
- timestamp: 2026-07-30T18:13:00-03:00
  result: "Backup verificado em `/home/ubuntu/backups/atius-sso-recovery-20260730-181233`, 14 arquivos com SHA-256."
- timestamp: 2026-07-30T18:23:00-03:00
  result: "VPN contract e typecheck PASS; AdGuard 20 testes PASS; admin edge source/config PASS."
- timestamp: 2026-07-30T18:34:00-03:00
  result: "Next.js production build PASS dentro de `omni-builds.slice`; compilação 50s."

## Eliminated

- hypothesis: "todos os cinco serviços estavam indisponíveis."
  reason: "gateways, Apache e upstreams responderam; o defeito principal é ciclo de auth/URL, não outage total de processo."
- hypothesis: "repo/live drift no admin-edge ou AdGuard causou a regressão."
  reason: "hashes source/live eram idênticos antes da correção."

## Resolution

- root_cause: "VPN expunha o control plane central; `/login` era protegido pelo próprio `AuthGuard`; AdGuard exigia metadados opcionais omitidos pelo edge/browser mesmo com CSRF one-shot válido; a evidência anterior não cobria dois ciclos completos."
- fix: "VPN ganhou facade local `/login`/`/logout`; AdGuard preservou CSRF e passou a aceitar ausência de metadados opcionais quando não há origem estrangeira explícita; harness E2E valida URL visível por site."
- verification: "PASS em 5 sites, 10 ciclos, 40 screenshots. Combined report em `docs/evidence/atius-sso/2026-07-30-host-local-lifecycle-per-site/combined-report.json`."
- files_changed: "VPN frontend, AdGuard gateway/tests, admin-edge E2E harness, docs domain/operations/evidence, Obsidian incident/logs."

## Final Evidence

- `docs/evidence/atius-sso/2026-07-30-host-local-lifecycle-per-site/combined-report.json`
- `docs/evidence/atius-sso/2026-07-30-host-local-lifecycle-per-site/SHA256SUMS`
- `docs/evidence/atius-sso/2026-07-30-host-local-lifecycle-per-site/README.md`
- `docs/operations/atius-sso-host-local-lifecycle.md`
- `docs/domain/atius-sso-lifecycle-matrix.md`

## Final Validation

- Browser E2E: `grafana`, `portainer`, `docker`, `vpn`, `adguard` -> 2/2 cycles each.
- Screenshots: 40.
- Services: `atius-admin-edge-gateway.service`, `adguard-portal-gateway.service`, `vpn-frontend.service`, `apache2.service` -> active.
- Unit/contracts: AdGuard `21/21 PASS`; VPN `phase09-sso-contract: PASS`; VPN `tsc --noEmit: PASS`.
- Graphify: `13841 nodes`, `19832 edges`, `commit_stale=false`.
