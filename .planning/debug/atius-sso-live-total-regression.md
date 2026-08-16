---
status: resolved
trigger: "Ainda nada de funcionar o login dos sites via sso, agora piorou que parou foi tudo; corrigir e testar grafana, portainer, docker, vpn e adguard em dois ciclos completos, mantendo hostname app-local /login e comparando visualmente com o modelo SSH."
created: 2026-07-31T05:16:48-03:00
updated: 2026-07-31T10:00:17-03:00
resolution: PASS_HOST_LOCAL_SSO_VISUAL_REFERENCE_V2
---

# Atius SSO live total regression

## Sintomas

- Giovanni reportou falha geral do login SSO e rejeitou o PASS anterior porque faltava login real, logout real, repetição, screenshot e análise visual.
- Contrato: cada app mantém `https://<site>.atius.com.br`; acesso anônimo e pós-logout terminam em `/login`; UI segue o modelo `/home/ubuntu/GitHub/Prints/sso-ssh-base-model.png`.
- Revisões intermediárias reabriram o incidente por falso PASS visual: Grafana autenticado vazio e Portainer/Docker capturados antes dos contadores finais.

## Root causes

1. Duplicate cookie collision:
   - browsers podiam manter `auth-token` host-only legado junto com o token válido `.atius.com.br`;
   - gateways antigos validavam só um valor de cookie;
   - VPN tinha caminhos que tratavam presença de cookie como sessão.
2. K3s private firewall drift:
   - peers privados `10.11/10.12/10.13/10.21` precisavam allow explícito para portas K3s e VXLAN;
   - o drift quebrava tráfego cross-node e deixava Grafana visualmente autenticado, mas sem dados.
3. Harness bugs:
   - `--evidence-dir` virava path literal `./--evidence-dir`;
   - Portainer/Docker eram capturados antes do dashboard Kubernetes estabilizar;
   - Grafana aceitava UI autenticada sem exigir painéis úteis.
4. UI typography drift:
   - app-local `/login` tinha labels/destination com peso/tamanho diferentes da referência Atius SSO.
5. Grafana datasource/readiness probe drift:
   - FQDN no container Grafana falha com o resolver; o runtime correto usa o nome curto `omni-monitoring-prometheus.monitoring`.

## Fixes

- Admin-edge gateway: multiple `auth-token` candidate validation + reason-preserving failures + tipografia canônica.
- AdGuard gateway: mesmo hardening + tipografia canônica.
- VPN frontend: build/restart com host-only cookie cleanup, validação server-side nos paths de sessão/API/logout/proxy e tipografia canônica.
- K3s firewall guard: alinhado em SRV-1/SRV-2/SRV-3/Horistic para liberar cluster privado e manter deny público.
- Grafana Helm: revision final `10`, `root_url=https://grafana.atius.com.br/`, datasource `http://omni-monitoring-prometheus.monitoring:9090/`.
- E2E runner: evidence-dir corrigido, subset só `PASS_SUBSET`, Grafana exige painéis úteis, Portainer/Docker entram no dashboard `atius-k3s` e aguardam contadores finais.
- Standalone `/home/ubuntu/GitHub/atius-sso`: gateways espelhados; manifest atualizado.

## Evidência final estável

- Pack final-stable: `/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-live-total-regression-final-stable-082114`.
- Report sha256: `02dd1aa786469700d8b6f6c3fa8267bf95732170033436fd99ae537585500759`.
- Vision manifest sha256: `29610a84df1b8832ed2bf1e809d8d7475ab0f316a7542c3f3e65ca2efef91ed3`.
- Repo closeout: `/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-live-total-regression-final-closeout.md`.
- Backup base: `/home/ubuntu/backups/atius-sso-live-total-regression-20260731-052218`.
- Backup tipografia: `/home/ubuntu/backups/atius-sso-login-typography-20260731-074035`.

## Verification

- Browser E2E final-stable: `5` sites, `10` cycles, `40` lifecycle screenshots, final `PASS`, `evidenceScope=full`, `completeFleetEvidence=true`.
- Vision final-stable: `5/5` comparison sheets PASS; both cycles PASS for all sites; zero material divergences.
- Computed style parity: canonical labels/destination weights and sizes matched after deploy.
- Logout: all five return to `https://<site>.atius.com.br/login`.
- Services: `atius-k3s-firewall`, `k3s`, `atius-admin-edge-gateway`, `adguard-portal-gateway`, `vpn-frontend`, `apache2` active/enabled.
- K3s: four nodes Ready; Grafana on SRV-3, Prometheus on SRV-1, Alertmanager on SRV-2.
- Grafana datasource: `5/5` curls from Grafana container to `http://omni-monitoring-prometheus.monitoring:9090/-/ready` PASS.
- Tests: admin-edge `7/7`, VPN contract/typecheck PASS, standalone `46+8+24` PASS.
- Standalone lint/source/security: PASS.
- Backup SHA manifests: PASS.

## Caveat

Verdict is `PASS_HOST_LOCAL_SSO_VISUAL`. `centralOidcFlow=false` remains explicit: this run did not prove Authorization Code + PKCE for the five app-local sites.

## Reabertura visual v2

- Trigger: Grafana ainda não reproduzia a aparência live do SSH; favicon Atius ausente na guia.
- Root cause: o fix anterior validava só três tokens tipográficos e mantinha renderer aproximado de `72px` com emojis e geometria divergente.
- Referência autoritativa: `https://ssh.atius.com.br/sso?return_to=https%3A%2F%2Fssh.atius.com.br%2Fcompute` + source ATS.
- Correção: renderer completo source-exact em admin-edge, AdGuard e VPN; favicon Atius em central, SSH e apps; flash `Entrando...` removido do bootstrap central.
- Computed styles: `7/7` páginas PASS; card `448×454.25`, logo `44×44`, zero emoji, botão estável sem spinner.
- Vision: SSO central + cinco apps `6/6` PASS contra SSH.
- Lifecycle: `5/5` sites, `10/10` ciclos, `40/40` screenshots, nenhuma falha.
- Evidence: `docs/evidence/atius-sso/2026-07-31-visual-reference-v2` e `docs/evidence/atius-sso/2026-07-31-visual-reference-v2-lifecycle-20260731-093627`.
- Veredito preservado: `PASS_HOST_LOCAL_SSO_VISUAL`; `centralOidcFlow=false`.
