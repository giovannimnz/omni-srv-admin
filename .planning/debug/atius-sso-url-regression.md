---
status: resolved
trigger: "Giovanni informa que nada funciona no login SSO após a padronização de URL; exige manter cada hostname app-local, usar /login, testar dois ciclos reais de login/logout em absolutamente todos os sites, capturar screenshots e analisar visualmente contra sso-ssh-base-model.png."
created: 2026-07-31T17:12:27-03:00
updated: 2026-07-31T20:36:00-03:00
---

# Atius SSO regressão pós-padronização de URL

## Symptoms

- expected: cada site permanece em `https://<site>.atius.com.br`; acesso anônimo termina em `/login`; login real entra no app; logout visível termina em `/login` do mesmo host; o ciclo repete duas vezes.
- actual: usuário reporta indisponibilidade total dos logins após o URL-standard e invalida o PASS anterior.
- reference: `/home/ubuntu/Imagens/Prints/sso-ssh-base-model.png`.
- scope: `sso`, `ssh`, `rdp`, `oci`, `talk`, `admin.talk`, `grafana`, `portainer`, `docker`, `vpn`, `adguard`, `remote`.

## Current Focus

- hypothesis: o URL-standard alterou somente aliases/redirects, mas não validou lifecycle; alguns hosts têm upstream indisponível ou raiz fora do facade, e os hosts ATS-owned podem ter regressão no POST de login/cookie/destino após a mudança de middleware.
- test: executar baseline HTTP e browser real pré-fix; localizar a primeira fronteira de falha por host; comparar source/live/histórico antes de qualquer correção.
- expecting: distinguir falha de redirect, login POST, cookie, autorização, upstream, logout e readiness visual, sem aceitar `/login=200` como PASS.
- next_action: executar lifecycle real existente nos cinco hosts já suportados e ampliar o harness aos demais hosts.
- reasoning_checkpoint:
  hypothesis: "O relatório 12/12 anterior é false positive funcional porque o harness URL-standard nunca digitou credenciais nem clicou logout."
  confirming_evidence:
    - "`2026-07-31-url-standard-headless-contract.mjs` somente abre `/login`, `/sso` e legado; não autentica."
    - "Baseline live: AdGuard root=401, Talk/Admin Talk root=503 e Remote root=404, apesar de todos os `/login` retornarem 200."
    - "O harness lifecycle real cobre apenas Grafana, Portainer, Docker, VPN e AdGuard."
  falsification_test: "A hipótese falha se dois ciclos reais atuais passarem em todo o fleet e as imagens mostrarem apps autenticados/saída real."
  fix_rationale: "Nenhuma mutação de produto antes de capturar a primeira falha real; backup byte-exact já concluído."
  blind_spots: "SSO central pode ter semântica própria; Talk/Admin Talk e Remote podem estar sem upstream por incidente não-SSO; SSH/RDP exigem markers próprios."

## Evidence

- timestamp: 2026-07-31T17:08:01-03:00
  result: "Graphify fresh no commit 79844a3: 14013 nodes, 20044 edges, commit_stale=false."
- timestamp: 2026-07-31T17:10:00-03:00
  result: "HTTP matrix: app-local `/login`=200 em 12 hosts; roots divergentes: AdGuard 401, Talk/Admin Talk 503, Remote 404."
- timestamp: 2026-07-31T17:12:27-03:00
  result: "Backup `/home/ubuntu/backups/atius-sso-url-regression-pre-20260731-171227`: 91 arquivos, restore drill byte-exact PASS."

## Eliminated

- hypothesis: "Apache e todos os gateways estão parados."
  reason: "Apache, VPN, admin-edge, Casa SSH/RDP e MT5 proxy estão active; o defeito não é outage total desses processos."
- hypothesis: "O PASS URL-standard provou o login/logout real."
  reason: "O código do harness não contém preenchimento de credenciais, submit, marker autenticado ou click de logout."

## Resolution

- root_cause:
  - URL-only e readiness genérica permitiam falso PASS sem login/logout real.
  - Grafana autenticava com painel TCP sem dados porque não havia tráfego DNS
    TCP contínuo e o dashboard de `3h` comprimira as primeiras amostras reais.
  - Remote aceitava o shell SSO antes do primeiro framebuffer noVNC.
  - RDP podia completar navegação same-origin enquanto o locator de login era
    desmontado, produzindo falso FAIL do harness.
  - Remote amplificava `/v1/auth/me` em rajadas sem cache/coalescência.
- fix:
  - harness fleet com dois ciclos completos, cookies limpos, ready markers por
    app, visual contract e `PASS_SUBSET` não canônico;
  - Grafana bloqueia qualquer painel sem dados/erro e usa janela operacional
    `15m` para exibir séries reais;
  - canário systemd `coredns-tcp-canary.timer` gera uma query DNS-over-TCP real
    a cada `30s`;
  - Remote exige framebuffer não branco/preto por análise de pixels;
  - RDP tolera detach somente quando URL same-origin e UI autenticada passam;
  - proxy Remote usa cache positivo curto e coalescência por sessão.
- verification:
  - canonical pack `docs/evidence/atius-sso/2026-07-31-full-fleet-final-strict-20260731-202636/`;
  - `12/12` sites, `24/24` ciclos, `96` screenshots, zero failure artifacts;
  - independent vision review `12/12 PASS`;
  - Remote: dois framebuffers com aproximadamente `421` cores e `4.31%`
    de pixels não pretos;
  - Grafana: 12 painéis com dados nos dois ciclos, incluindo TCP;
  - Apache `Syntax OK`; canary active/enabled, `Result=success`.
- files_changed:
  - `modules/atius-admin-edge-sso/scripts/validate-atius-sites-sso-lifecycle.mjs`;
  - `modules/mt5-remote-auth/scripts/mt5-remote-auth-proxy.js`;
  - `modules/mt5-remote-auth/scripts/mt5-remote-auth-proxy.test.js`;
  - `modules/k3s-ha-portainer-oci/monitoring/scripts/coredns-tcp-canary.sh`;
  - `modules/k3s-ha-portainer-oci/systemd/coredns-tcp-canary.{service,timer}`;
  - owner docs and evidence package.
