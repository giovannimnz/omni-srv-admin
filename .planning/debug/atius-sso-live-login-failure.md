---
status: resolved
trigger: "Giovanni informa que o login SSO dos cinco sites continua sem funcionar e que agora tudo parou; exige dois ciclos completos, 40 screenshots e análise visual contra o modelo SSH."
created: 2026-07-30T22:25:50-03:00
updated: 2026-07-30T23:34:00-03:00
---

## Symptoms

- expected: `grafana`, `portainer`, `docker`, `vpn` e `adguard` preservam o hostname app-local; acesso anônimo termina em `/login`; login real entra no app; logout retorna a `/login`; o ciclo repete duas vezes.
- actual: usuário informa que os logins continuam sem funcionar e que o estado piorou para indisponibilidade geral.
- errors: nenhum erro único fornecido; o PASS anterior foi explicitamente invalidado pelo usuário.
- timeline: terceira contestação em 2026-07-30, depois da promoção visual das 22:08 BRT.
- reproduction: abrir cada raiz em contexto anônimo, autenticar pelo formulário app-local, validar app, executar logout, validar retorno app-local e repetir.

## Current Focus

- hypothesis: o shell `/login` e os redirects anônimos podem estar saudáveis enquanto o POST real de login, emissão/escopo do `auth-token`, autorização do usuário ou upstream pós-login falha; o harness anterior pode ter produzido evidência que não representa a experiência atual do usuário.
- test: nova execução independente por site, sem reutilizar evidence pack anterior, com Vault, browser headless real, dois ciclos, URLs visíveis, cookie e screenshots.
- expecting: identificar a primeira fronteira real que falha por site: form submit, token issuance, session validation, authorization, upstream, logout ou visual.
- next_action: executar Grafana isoladamente e propagar o diagnóstico aos demais sites.
- reasoning_checkpoint:
  hypothesis: "Disponibilidade HTTP do shell não prova autenticação real; os cinco `/login` respondem, mas isso não resolve a contestação."
  confirming_evidence:
    - "Em 22:25 BRT os quatro serviços estavam active e os cinco `/login` retornavam o template Atius SSO."
    - "Grafana, Portainer, Docker e VPN redirecionavam a raiz para `/login`; AdGuard retornava 401 para curl sem Accept HTML, mas a regra browser permanece dependente do request."
    - "Source/live dos gateways admin-edge e AdGuard possuem hashes idênticos."
  falsification_test: "A hipótese falha se nova automação real, isolada e fresca passar dois ciclos em todos os sites e as imagens confirmarem o resultado."
  fix_rationale: "Nenhuma mutação até localizar a fronteira real; backup antes de qualquer correção."
  blind_spots: "Diferença entre browser do usuário e headless, Cloudflare, cookie antigo, logout nativo do vendor e credencial Vault."

## Evidence

- timestamp: 2026-07-30T22:25:50-03:00
  result: "Graphify FRESH: 13920 nodes, 19926 edges, 0 hyperedges, commit_stale=false."
- timestamp: 2026-07-30T22:29:00-03:00
  result: "Baseline HTTP atual: os cinco `/login` servem o template canônico; nenhum PASS de login foi inferido desse resultado."
- timestamp: 2026-07-30T22:32:59-03:00
  result: "Backup documental validado em /home/ubuntu/backups/atius-sso-reopen-docs-20260730-223259."

## Eliminated

- hypothesis: "Os processos gateway/Apache/Next estão todos parados."
  reason: "systemd e listeners confirmam os quatro serviços active e portas 8210/8198/3100 abertas."
- hypothesis: "O runtime dos gateways divergiu do source."
  reason: "hash source/live idêntico para admin-edge e AdGuard."

## Resolution

- root_cause:
  - "O ATS API usa `@fastify/rate-limit` global de 100 requests/minuto. Admin-edge e AdGuard chamavam `/v1/auth/me` por asset/request; a bateria drenava o budget e `/v1/token/generate` passava a retornar 429. Os adapters convertiam 429 em erro de credencial."
  - "O harness anterior navegava diretamente para `/logout`; não clicava no logout visível do app. Os ready markers também aceitavam Portainer/VPN antes da UI protegida terminar de carregar."
- fix:
  - "Cache positivo de sessão por token/origem por 30s e coalescing de requests nos gateways admin-edge e AdGuard."
  - "VPN preserva cache/coalescing e classifica indisponibilidade como 503; 401/403 continuam sendo inválidos."
  - "Admin edges receberam controle visível `Sair do Atius SSO`, integrado ao logout local `/logout`; o logout vendor do Portainer é interceptado para o mesmo contrato."
  - "Harness agora clica em controle visível e espera marcadores de UI pronta específicos por site."
- verification:
  - "Evidence pack definitivo: `docs/evidence/atius-sso/2026-07-30-rate-limit-real-ui-final/`."
  - "5 sites, 10 ciclos, 40 screenshots; auth-token emitido/limpo; nenhuma navegação visível para sso.atius.com.br."
  - "Vision final PASS para identidade visual e para os oito estados de cada site; Docker e VPN foram regenerados após a visão rejeitar estados intermediários."
  - "Admin bridge 4/4 PASS; AdGuard 22/22 PASS; VPN typecheck, build governado, contrato offline/live PASS; Apache Syntax OK; quatro serviços active."
  - "Logs pós-deploy: zero 429. Três timeouts Portainer posteriores aos ciclos ficaram registrados como incidente upstream separado."
- files_changed:
  - "modules/atius-admin-edge-sso/scripts/atius-admin-edge-gateway.js"
  - "modules/atius-admin-edge-sso/scripts/atius-admin-edge-gateway.test.mjs"
  - "modules/atius-admin-edge-sso/scripts/validate-atius-sites-sso-lifecycle.mjs"
  - "/home/ubuntu/GitHub/vpn-atius/home-proxy/modules/home-router-be3/scripts/adguard-portal-gateway.cjs"
  - "/home/ubuntu/GitHub/vpn-atius/home-proxy/modules/home-router-be3/test/dns-casa/adguard-portal-gateway.test.mjs"
  - "/home/ubuntu/GitHub/vpn-atius/web/frontend/src/lib/atius-sso.ts"
  - "/home/ubuntu/GitHub/vpn-atius/web/frontend/src/app/api/auth/login/route.ts"
  - "/home/ubuntu/GitHub/vpn-atius/web/frontend/src/app/api/auth/session/route.ts"
  - "/home/ubuntu/GitHub/vpn-atius/web/frontend/src/app/api/vpn/[...path]/route.ts"
  - "/home/ubuntu/GitHub/vpn-atius/web/frontend/tests/phase09-sso-contract.mjs"
