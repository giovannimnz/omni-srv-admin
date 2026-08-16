# Atius SSO live total regression — final stable closeout — 2026-07-31

## Veredito

- Live five-site SSO lifecycle: `PASS_HOST_LOCAL_SSO_VISUAL`.
- Evidence scope: `full`.
- Proof scope: `hostLocalLifecycle=true`, `centralOidcFlow=false`.
- Sites: `grafana`, `portainer`, `docker`, `vpn`, `adguard`.
- Cycles: `10` (`5 sites × 2`).
- Original lifecycle screenshots: `40`.
- Final-stable PNG evidence: `45` (`40 lifecycle + 5 vision comparison sheets`).
- Final-stable file count: `48`.
- Commit/push: none.

## Final stable evidence

- Final-stable pack: `/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-live-total-regression-final-stable-082114`.
- Final-stable report: `report.json`, sha256 `02dd1aa786469700d8b6f6c3fa8267bf95732170033436fd99ae537585500759`.
- Final-stable vision manifest: `vision-comparison-sheets-SHA256SUMS`, sha256 `29610a84df1b8832ed2bf1e809d8d7475ab0f316a7542c3f3e65ca2efef91ed3`.
- Final-stable verdict in report: `PASS`, `evidenceScope=full`, `completeFleetEvidence=true`.
- Final-stable vision review: `5/5` sites PASS, both cycles PASS, zero material divergences.
- Reference UI: `/home/ubuntu/GitHub/Prints/sso-ssh-base-model.png`.

## Causas confirmadas

1. Cookie collision.
   - Browsers with stale host-only `auth-token` could send duplicate cookie names with the valid `.atius.com.br` token.
   - The old gateway path validated only one cookie value, so result depended on browser ordering.
   - VPN code also trusted cookie presence before server-side session validation in some paths.

2. K3s/private firewall regression.
   - The private K3s fabric needed explicit allow rules for `10.11/10.12/10.13/10.21` on TCP `6443,2379,2380,10250,10257,10259` and UDP `8472`.
   - Missing/old guard state blocked VXLAN/private cluster paths and made Grafana visually broken even after authentication.

3. Grafana datasource/readiness drift.
   - Grafana must query Prometheus through the chart-compatible short service name `http://omni-monitoring-prometheus.monitoring:9090/`.
   - FQDN probes with the Grafana container resolver fail even while the runtime short name succeeds; final health checks use the same resolver path the app uses.

4. E2E runner false-positive / CLI bug.
   - The lifecycle runner treated `--evidence-dir` as a positional path and wrote to a literal `./--evidence-dir` directory.
   - Previous PASS could miss visual usability regressions, empty Grafana dashboards, and Portainer screenshots before card counters stabilized.

5. UI typography drift.
   - App-local `/login` pages had heavier labels and destination text than the canonical `sso.atius.com.br/login` source.
   - Final computed style parity is exact for the relevant fields: `Destino seguro` `11px/400/16.5px`, destination host `14px/400/20px`, labels `14px/500/20px`.

## Fixes applied live

- `atius-admin-edge-gateway.service`
  - validates all duplicate `auth-token` candidates, up to four values;
  - preserves `auth_unavailable` and `forbidden` failure reasons instead of collapsing everything to `invalid_auth`;
  - login typography aligned to the canonical Atius SSO reference;
  - live file is byte-exact with repo source.

- `adguard-portal-gateway.service`
  - same duplicate-cookie validation hardening;
  - login typography aligned to the canonical Atius SSO reference;
  - live file is byte-exact with repo source.

- `vpn-frontend.service`
  - rebuilt under `omni-builds.slice` and restarted with `BUILD_ID=wRHd_fNEJck2D1TsdEsPq`;
  - login success clears host-only legacy cookies;
  - session/API/proxy/logout paths no longer rely on first-cookie-only behavior;
  - login typography aligned to the canonical Atius SSO reference.

- `atius-k3s-firewall.service`
  - aligned on SRV-1, SRV-2, SRV-3 and Horistic;
  - accepts K3s private TCP `6443,2379,2380,10250,10257,10259` and UDP `8472` from `10.11.0.0/16`, `10.12.0.0/16`, `10.13.0.0/16`, `10.21.0.0/16`;
  - preserves public deny guard for those K3s ports.

- Grafana Helm release `omni-monitoring`
  - final deployed revision observed: `10`;
  - `root_url=https://grafana.atius.com.br/`;
  - Grafana pinned to `atius-srv-3`, Prometheus to `atius-srv-1`, Alertmanager to `atius-srv-2`;
  - datasource URL explicitly pinned to `http://omni-monitoring-prometheus.monitoring:9090/`.

- `validate-atius-sites-sso-lifecycle.mjs`
  - fixed `--evidence-dir <path>` and `--evidence-dir=<path>` handling;
  - rejects fleet PASS for subset unless `E2E_ALLOW_SUBSET_PASS=1`, and then emits only `PASS_SUBSET`;
  - Grafana authenticated state now requires useful visible panels;
  - Portainer/Docker authenticated state now enters `#!/1/kubernetes/dashboard` and waits for final Kubernetes counters.

- `/home/ubuntu/GitHub/atius-sso/`
  - standalone gateways mirrored with duplicate-cookie hardening and canonical typography;
  - source manifest hashes refreshed.

## Browser E2E results — final stable

- `grafana.atius.com.br`: 2 cycles PASS; authenticated dashboard has multiple useful panels; logout returns `https://grafana.atius.com.br/login`.
- `portainer.atius.com.br`: 2 cycles PASS; authenticated dashboard is Kubernetes `atius-k3s` with final counters; logout returns `https://portainer.atius.com.br/login`.
- `docker.atius.com.br`: 2 cycles PASS; authenticated dashboard is Kubernetes `atius-k3s` with final counters; logout returns `https://docker.atius.com.br/login`.
- `vpn.atius.com.br`: 2 cycles PASS; authenticated dashboard shows WireGuard operational data; logout returns `https://vpn.atius.com.br/login`.
- `adguard.atius.com.br`: 2 cycles PASS; authenticated dashboard shows AdGuard metrics/data; logout returns `https://adguard.atius.com.br/login`.

## Vision review — final stable

- Grafana: `2/2` cycles PASS; no material divergences; one panel with `Sem dados` is non-blocking because the dashboard has multiple populated panels.
- Portainer: `2/2` cycles PASS; `atius-k3s` dashboard visible with `10 Namespaces`, `26 Applications`, `34 Services`, `0 Ingresses`, `51 ConfigMaps`, `38 Secrets`, `10 Volumes`.
- Docker: `2/2` cycles PASS; same Portainer Kubernetes dashboard through `docker.atius.com.br`.
- VPN: `2/2` cycles PASS; WireGuard operational dashboard with peers and traffic data.
- AdGuard: `2/2` cycles PASS; dashboard/métricas úteis; no loading/error/blank page.

## Gates

- Omni admin-edge tests: `7/7` PASS.
- VPN SSO contract: PASS.
- VPN typecheck: PASS.
- VPN Next build: PASS under `omni-builds.slice`; `BUILD_ID=wRHd_fNEJck2D1TsdEsPq`.
- Standalone tests: `46/46` unit/contracts + `8/8` admin-edge + `24/24` adguard PASS.
- Standalone lint: `repository_lint=PASS files=117`.
- Standalone source manifest: `source_manifest=PASS files=23`.
- Standalone secret scan: `secret_scan=PASS`.
- `git diff --check`: PASS for modified scoped paths.
- Live services: `atius-k3s-firewall`, `k3s`, `atius-admin-edge-gateway`, `adguard-portal-gateway`, `vpn-frontend`, `apache2` active/enabled.
- K3s nodes: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `horistic-srv` Ready.
- Grafana datasource probe histórico naquele closeout: `5/5` curls from Grafana container to `http://omni-monitoring-prometheus.monitoring:9090/-/ready` PASS. Não representa disponibilidade atual após o `DiskPressure` posterior.
- Backup manifests: PASS.

## Rollback

- Base backup root: `/home/ubuntu/backups/atius-sso-live-total-regression-20260731-052218`.
- Typography backup root: `/home/ubuntu/backups/atius-sso-login-typography-20260731-074035`.
- Grafana datasource/root-url Helm backups:
  - `/home/ubuntu/backups/atius-sso-live-total-regression-20260731-052218/helm-grafana-datasource-fqdn-20260731-081804`;
  - `/home/ubuntu/backups/atius-sso-live-total-regression-20260731-052218/helm-grafana-datasource-shortname-20260731-082019`.
- Gateway rollback:
  - restore `/opt/atius/atius-admin-edge-gateway.js` from backup;
  - restore `/opt/atius/adguard-portal-gateway.js` from backup;
  - restart `atius-admin-edge-gateway.service adguard-portal-gateway.service`.
- VPN rollback:
  - restore prior source/build from repo/backup if needed;
  - rebuild under `omni-builds.slice` if source rollback is used;
  - restart `vpn-frontend.service`.
- Firewall rollback:
  - restore `/usr/local/sbin/atius-k3s-firewall.sh` and `/etc/systemd/system/atius-k3s-firewall.service` from backup;
  - `systemctl daemon-reload && systemctl restart atius-k3s-firewall.service`.
- Grafana Helm rollback:
  - use Helm release rollback or re-apply the backed-up values from the Helm backup directory;
  - verify Grafana remains on `atius-srv-3` and Prometheus remains on `atius-srv-1` before accepting rollback.
- K3s disaster rollback:
  - etcd snapshot `pre-atius-sso-total-recovery-*` exists on SRV-3 and was verified ready/size/hash during recovery.

## Caveat

This verifies host-local Atius SSO lifecycle and visual usability. It does not prove a central OIDC Authorization Code + PKCE flow for the five app-local sites; the current deployed five-site flow remains host-local form + shared `auth-token` session validation.

## Final indexing

- GBrain slug: `atius-sso-live-total-regression-final-stable-2026-07-31/index`.
- GBrain import: `--no-embed` PASS; readback PASS; `9193` bytes.
- Graphify `omni-srv-admin`: `13993` nodes, `20023` edges, `0` hyperedges, `stale=false`, `commit_stale=false`, source commit `79844a3`.
- Graphify `vpn-atius`: `16451` nodes, `19062` edges, `0` hyperedges, `stale=false`, `commit_stale=false`, source commit `ae29eb7`.
- Graphify `atius-sso`: `994` nodes, `1103` edges, `0` hyperedges, `stale=false`.
- Graphify governor: `omni-builds.slice`, `CPUWeight=100`, `CPUQuotaPerSecUSec=800ms`.
- Graphify query checks:
  - `omni-srv-admin :: validate-atius-sites-sso-lifecycle` → `31` nodes, `58` edges.
  - `omni-srv-admin :: atius-admin-edge-gateway` → `60` nodes, `112` edges.
  - `vpn-atius :: phase09-sso-contract` → `15` nodes, `14` edges.
  - `vpn-atius :: adguard-portal-gateway` → `31` nodes, `28` edges.
  - `atius-sso :: atius-admin-edge-gateway` → `5` nodes, `4` edges.
  - `atius-sso :: adguard-portal-gateway` → `8` nodes, `8` edges.
  - `atius-sso :: source-manifest` → `3` nodes, `2` edges.

## Reabertura visual v2 — referência SSH live — 2026-07-31 10:00 BRT

O closeout `final-stable-082114` foi reaberto após Giovanni rejeitar a aparência do Grafana. O PASS anterior era insuficiente: media somente a tipografia crítica e aceitava um renderer aproximado com logo de `72px`, emojis como ícones e card/espaçamentos diferentes do componente live em `https://ssh.atius.com.br/sso?return_to=https%3A%2F%2Fssh.atius.com.br%2Fcompute`.

### Correções visuais finais

- `atius-admin-edge-gateway.service`: Grafana, Portainer e Docker passaram a usar o renderer canônico completo.
- `adguard-portal-gateway.service`: AdGuard passou a usar o mesmo renderer.
- `vpn-frontend.service`: VPN alinhada ao mesmo card, espaçamentos, fontes, ícones SVG e botão.
- ATS central/SSH: favicon legado HRSTC removido; `/mono-atius-horizontal.svg` virou favicon Atius canônico.
- Grafana/Portainer/Docker/AdGuard: `/_atius/favicon.svg` serve a geometria exata da marca ATS.
- VPN: `/atius-mark.svg` é byte-exato com `/mono-atius-horizontal.svg`.
- SSO central: bootstrap do `AuthProvider` não muda mais o botão para `Entrando...`; o submit continua protegido por guard lógico e o spinner aparece somente após submit real.
- Lifecycle, cookies, redirects, logout e hostnames app-local foram preservados.

### Paridade computada final

- Páginas: SSH referência, SSO central, Grafana, Portainer, Docker, VPN e AdGuard — `7/7` PASS.
- Card: `448 × 454.25px`, `border-radius: 12px`.
- Logo: `44 × 44px`.
- `Destino seguro`: `11px / 400 / 16.5px`, tracking normal.
- Hostname: `14px / 400 / 20px`.
- Labels: `14px / 500 / 20px`.
- Inputs: `44px`, raio `10px`, `14px / 400 / 20px`.
- Botão: `44px`, raio `10px`, `14px / 500 / 20px`.
- Fundo: mesmo gradient `135deg` da referência.
- Emojis no renderer ativo: zero.
- Botão após `3s`: `Entrar com Atius SSO`, habilitado e sem spinner em `7/7` páginas.
- Vision final: SSO central + cinco apps `6/6` PASS contra SSH; nenhuma divergência material.

### Lifecycle app-local pós-correção visual

- Pack: `/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-visual-reference-v2-lifecycle-20260731-093627`.
- Resultado: `5/5` sites, `10/10` ciclos, `40/40` screenshots, nenhum failure artifact.
- Grafana: dois ciclos com dashboard `/d/vkQ0UHxik/coredns` e painéis úteis.
- Portainer/Docker: dois ciclos com dashboard Kubernetes e sete contadores finais.
- VPN e AdGuard: dois ciclos com aplicação autenticada pronta.
- Auth cookie emitido e removido em todos os dez ciclos.
- Unit governada: `atius-sso-visual-v2-lifecycle.service`, `Result=success`, `ExecMainStatus=0`, zero swap.

### Builds e regressões

- Admin-edge: `8/8` PASS.
- AdGuard live source: `25/25` PASS.
- VPN: contract, typecheck, lint e Next production build PASS; live `BUILD_ID=TyT674tPqvnHnsQM1RTQ_`.
- ATS central: SSO allowlist/bootstrap `64/64`, typecheck e Next production build PASS; live `BUILD_ID=atius-1785502082536`.
- Standalone `atius-sso`: `34/34` gateways PASS, lint PASS, secret scan PASS, provenance `29` files PASS.
- Builds executados serialmente em `omni-builds.slice` com CPU quota efetiva e throttling observado.

#### Reconciliação do wrapper `proc_7af4368e4884`

- O `exit code 1` não veio do Next build. A unit transitória `atius-vpn-sso-visual-build-v2.service` terminou em `09:23:41 BRT` com `Result=success`, `ExecMainStatus=0`, `26.199s` de CPU, `771.4M` de memória pico e `0B` de swap.
- O log do workload fecha limpo: compile PASS, TypeScript PASS, páginas estáticas `11/11` e rota `/login` presente.
- A falha ocorreu depois, no shell pai zsh: o wrapper tentou atribuir o readback a `status`, parâmetro especial read-only do zsh. O erro abortou somente a linha de resumo do harness.
- Reproduction gate: `zsh -fc 'status=0'` retorna `1`; `zsh -fc 'exec_status=0'` e `bash -lc 'status=0'` retornam `0`.
- O artifact de `09:23` foi superseded por outro build em `09:35:23`, `BUILD_ID=TyT674tPqvnHnsQM1RTQ_`. `vpn-frontend.service` entrou `active/running` em `09:35:34`, `Result=success`, `ExecMainStatus=0`; `/login` e o build manifest públicos retornam `200`.
- O visual-v2 posterior de `09:41:50` permanece a única autoridade: `PASS_HOST_LOCAL_SSO_VISUAL`, `hostLocalLifecycle=true`, `centralOidcFlow=false`.
- Classificação: `POST_WORKLOAD_ZSH_HARNESS_FAILURE_BUILD_SUCCEEDED_SUPERSEDED_BY_LATER_SUCCESSFUL_BUILD_AND_RUNTIME`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-proc-7af4368e4884-vpn-build-wrapper-reconciliation.json`.

#### Reconciliação do build ATS `proc_e8fd6e44b09b`

- O processo terminou normalmente com `exit code 0`. A unit `atius-central-sso-visual-build-v2.service`, invocation `b1d1ae24a8ac4304b428b1359b483442`, fechou em `09:28:34 BRT` com `Result=success`, `ExecMainStatus=0`, runtime `1min 26.304s`, CPU `1min 8.341s`, memória pico `546.3M` e swap `0B`.
- O Next build compilou sem erro explícito; `ats-build.log` tem `9.984` bytes e SHA-256 `180e69a28cc7cd0f316123c6144b0db90f6891d255b72daf2a6a3618122c4066`.
- O artifact foi promovido em `09:28:50`, servido por `atius-web` com `BUILD_ID=atius-1785500828844`, central SSO `200` e favicon byte-exato. O lifecycle posterior de `09:36–09:41` passou `5/5`, `10/10` ciclos e `40/40` screenshots.
- Um patch posterior corrigiu o flash visual de bootstrap do botão central. Por isso, e não por falha do primeiro build, `proc_125b2c12a64b`, unit `atius-central-sso-bootstrap-visual-fix.service`, invocation `c97a77f5169f482095680f2fe16aa601`, passou `success/status=0` em `43.700s`, CPU `33.527s`, pico `784.8M`, swap `0B`, e foi promovido como `BUILD_ID=atius-1785502082536`.
- O runtime atual continua `atius-web=online`; login e build manifest públicos retornam `200`. Screenshot central de `09:51:59` e computed styles `7/7` de `09:55:23` validam o artifact posterior.
- Rollback preservado e estruturalmente válido, sem restore: `/home/ubuntu/GitHub/Atius-Capital/ats/frontend/.next.rollback-sso-visual-v2-20260731-092707`, `198` arquivos, `5.389.961` bytes, build anterior `atius-1785038139458`.
- Classificação: `SUCCESSFUL_ATS_BUILD_PROMOTED_AND_VALIDATED_THEN_SUPERSEDED_BY_LATER_SUCCESSFUL_SOURCE_CHANGE_BUILD_AND_RUNTIME`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-proc-e8fd6e44b09b-ats-build-reconciliation.json`.
- A autoridade visual permanece `PASS_HOST_LOCAL_SSO_VISUAL`, `hostLocalLifecycle=true`, `centralOidcFlow=false`.
- Backup pré-closeout: `/home/ubuntu/backups/proc-e8fd6e44b09b-closeout-20260731-142537`, `8` arquivos, `171.591` bytes, checksum PASS.
- Backup pós-closeout: `/home/ubuntu/backups/proc-e8fd6e44b09b-final-20260731-144543`, `10` arquivos, `186.332` bytes, checksum PASS.

#### Reconciliação do build VPN `proc_f11177028401`

- O alerta tardio entregou o comando e output completos. A unit governada `atius-vpn-sso-visual-build-v2-final.service`, invocation `adb667ff581045d59aaa3cd4ea3ebe2e`, terminou `success/status=0`: runtime `34.903s`, CPU `26.394s`, memória pico `818.5M` e swap `0B`.
- `vpn-build-final.log` confirma compile PASS, TypeScript, páginas estáticas `11/11` e rota `/login`; SHA-256 `bfdbac00cd84034ca3b144b7268e44885fa0302a9f1f84150ffcba3922a19f79`.
- O artifact `5i44myr1IPLzVZISp62Km` foi promovido e servido: `vpn-frontend.service=active`, health local `200`, front local/público `307`, listeners somente em `127.0.0.1:8000/3100` e asset Atius byte-exato.
- Isso prova sucesso de build/promoção/runtime, não autoridade visual final. O smoke computed-style posterior encontrou drift real no VPN: botão herdando `400/21px`, card `16px` mais baixo e spacing label/control divergente.
- Um patch real em `src/app/login/page.tsx` às `09:33:42` fixou spacing de `8px`, inputs `14px/400/20px` e botão `14px/500/20px`. O processo de paridade `proc_8c81b41b836e`, unit `atius-vpn-sso-visual-build-v2-parity.service`, invocation `7aadef3753084c6baa24e2ce527a4886`, terminou `success/status=0`: runtime `34.413s`, CPU `26.505s`, pico `829.5M`, swap `0B`; foi promovido como `TyT674tPqvnHnsQM1RTQ_` às `09:35`.
- O artifact `09:35` passou computed-style `5/5` e o visual-v2 de `09:41`. A fonte primária tardia identifica esse lifecycle como `proc_9badcb5bf73d`, unit `atius-sso-visual-v2-lifecycle.service`, invocation `ca41da73483d46149d8e3aeed8f316a2`, `success/status=0`, runtime `5min 23.511s`, CPU `42.228s`, pico `488.3M`, swap `0B`: VPN `2/2` ciclos e `8/8` screenshots; fleet `5/5`, `10/10`, `40/40`.
- Classificação: `SUCCESSFUL_VPN_BUILD_PROMOTED_AND_RUNTIME_VALIDATED_THEN_SUPERSEDED_BY_LATER_SUCCESSFUL_SOURCE_PARITY_BUILD_RUNTIME_AND_VISUAL_V2`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-proc-f11177028401-vpn-build-reconciliation.json`.
- A única autoridade visual operacional continua `PASS_HOST_LOCAL_SSO_VISUAL`, `hostLocalLifecycle=true`, `centralOidcFlow=false`.
- Backup pré-closeout: `/home/ubuntu/backups/proc-f11177028401-closeout-20260731-145027`, `9` arquivos, `189.575` bytes, checksum PASS.

### Evidência e hashes

- Evidence visual: `/home/ubuntu/GitHub/omni-srv-admin/docs/evidence/atius-sso/2026-07-31-visual-reference-v2`.
- Lifecycle report sha256: `e1940214d684af276d91412c4a69087d6d0d076f15397fe44b6e56aa61c3208b`.
- Computed styles sha256: `512bc9cec3b2f41d2116695d08d1bcd6659cb9034d36f5a82e565bb5a4f5d256`.
- Contact sheet final sha256: `63432ad3374e02bac83426e8efd95173d61800be88bb72d074a71ebdc6cd09ff`.
- Favicon Atius sha256: `2318a298cbe6cef688d98750ae4f8efe957726cb68ad467934d171ae4f4e1089`.
- Final checksum manifest: `docs/evidence/atius-sso/2026-07-31-visual-reference-v2/final-SHA256SUMS` — PASS.
- Backup verificado: `/home/ubuntu/backups/atius-sso-visual-reference-v2-20260731-084646`, `216` arquivos, `5,684,393` bytes, checksum e restore smoke PASS.

### Veredito v2

`PASS_HOST_LOCAL_SSO_VISUAL`.

Escopo real: identidade visual canônica + lifecycle host-local dos cinco apps. O fluxo live continua usando `/v1/token/generate`; esta entrega não prova OIDC Authorization Code + PKCE central (`centralOidcFlow=false`). Nenhum commit ou push foi feito.

### Indexação e referência SSH final

- GBrain slug: `atius-sso-visual-v2-2026-07-31/index`; import `--no-embed` e readback Markdown PASS (`5,663` bytes).
- Graphify `omni-srv-admin`: `14,006` nodes, `20,038` edges, `stale=false`, `commit_stale=false`.
- Graphify `vpn-atius`: `16,451` nodes, `19,062` edges, `stale=false`, `commit_stale=false`.
- Graphify `Atius-Capital/ats`: `31,914` nodes, `48,384` edges, `stale=false`, `commit_stale=false`.
- Graphify `atius-sso`: `1,009` nodes, `1,115` edges, `stale=false`.
- Rebuild serial governado: `Result=success`, `ExecMainStatus=0`, `8m43s`, memória pico `2.4G`, swap `0B`.
- Backup Graphify: `/home/ubuntu/backups/atius-sso-visual-v2-graphify-20260731-100320`, `40` arquivos, `186,245,556` bytes, checksum PASS.
- Referência SSH pós-fix: login chegou a `https://ssh.atius.com.br/compute`; UI mostrou cinco destinos; logout pelo controle visível `Sair` concluiu em `https://sso.atius.com.br/login`; `/v1/auth/me=401` e zero `auth-token` após estabilização.
- Evidence SSH: `docs/evidence/atius-sso/2026-07-31-visual-reference-v2/ssh-reference-lifecycle-final.json`.

### Classificação de runner assíncrono tardio

- O processo `proc_77b801b17517` terminou depois do closeout, mas seu pack foi gerado às `05:28 BRT`, antes da correção visual v2.
- Pack histórico: `docs/evidence/atius-sso/2026-07-31-live-total-regression-before-fix-052355`.
- Seu `PASS` continua válido somente como baseline funcional host-local daquela hora.
- Marker: `BASELINE-NOT-AUTHORITATIVE.md`.
- O pack não comprova card/logo/ícones/espaçamentos/favicon v2 e não substitui a certificação `09:41 BRT`.
- Ponteiro autoritativo preservado em `docs/evidence/atius-sso/2026-07-31-visual-reference-v2/latest-lifecycle-path.txt`.
- Baseline report sha256: `76040921a1c70bb0fc296969b7f88492ecf3054ede2ccb2e384a38376da419c1`.
- Visual v2 report sha256: `e1940214d684af276d91412c4a69087d6d0d076f15397fe44b6e56aa61c3208b`.
- Backup pré-classificação: `/home/ubuntu/backups/atius-sso-late-baseline-classification-20260731-102844`, checksum PASS.

### Finding de segurança pós-closeout

- A reconciliação do fan-out assíncrono antigo não invalidou a UI v2, mas revelou exposição direta da ATS API em `0.0.0.0:8015`.
- O incidente é separado do SSO visual: `OPEN/HIGH`, com `189` requests públicos diretos identificados nos logs e reachability confirmada a partir do `horistic-srv`.
- Remediação proposta: bind `127.0.0.1`, restart controlado do `atius-api`, health/API/SSO regression e probe externo bloqueado.
- A mutação não foi aplicada porque exige gate explícito de produção.
- Registro autoritativo: `AiSecondBrain/61-Incidents/2026-07-31-atius-api-porta-8015-exposta.md`.
- Backups verificados: `/home/ubuntu/backups/atius-api-public-8015-incident-20260731-104527` e `/home/ubuntu/backups/atius-api-8015-docs-20260731-104954`.
- Evidence machine-readable: `docs/evidence/atius-sso/2026-07-31-atius-api-public-8015-incident.json`.
- Primeiro seal Graphify pós-finding: `success/status=0`; Omni `14011/20042`, vault `37565/63222`, zero swap do workload e throttling comprovado.

### Classificação do processo readiness tardio

- `proc_397b5f569f20`: `OBSOLETE_HARNESS_PROCESS_FAILURE`.
- Exit `1` veio de `MODULE_NOT_FOUND` para `/tmp/atius-sso-app-readiness-diagnostic.mjs`, antes de qualquer probe do produto.
- Isso não é regressão de Grafana, Portainer, Docker, VPN, AdGuard ou do SSO central.
- O script atual apareceu depois e passa sintaxe; isso não altera a classificação do processo que falhou.
- Estado atual read-only: cinco `/login=200`, API `healthy`, zero runner.
- Autoridade preservada: pack visual-v2 `09:41 BRT`; nenhum rerun do harness obsoleto.
- Evidence: `docs/evidence/atius-sso/2026-07-31-obsolete-readiness-harness-process.json`.

### Reconciliação do processo posterior

- `proc_3c0b08ba1c60` executou o script materializado e terminou `exit 0`; a coleta pertence à janela histórica `05:37–05:38 BRT`.
- Não é PASS automático: o harness não falha por `failures[]`, console errors, painel sem dados ou spinner persistente.
- Grafana autenticou, mas registrou datasource `500`, WebSocket `403` e painéis vazios; Docker/Portainer ficou pronto apesar do locale fallback `404`.
- O WebSocket Grafana teve `101` em execuções posteriores e esse finding não revoga a certificação visual-v2.
- Evidence: `docs/evidence/atius-sso/2026-07-31-readiness-diagnostic-0537-reconciliation.json`.

### Reproducer histórico da colisão de cookie

- `proc_3a60256f5a48` terminou `exit 0` com evidence às `05:50 BRT`, antes do primeiro deploy/restart do hardening às `06:20 BRT`.
- A prova reproduziu a causa descrita neste closeout: cookie canônico `.atius.com.br` válido + cookie host-only homônimo inválido fazia a raiz Grafana voltar para `/login`.
- O relogin antigo recuperava o dashboard, mas deixava ambos coexistindo.
- Runtime atual: source/live byte-exact, valida até quatro candidatos e remove o host-only legado no relogin; testes das duas ordens passam (`8/8`).
- Essa evidence fortalece a causalidade pré-fix e não revoga `PASS_HOST_LOCAL_SSO_VISUAL` posterior.
- Evidence: `docs/evidence/atius-sso/2026-07-31-duplicate-cookie-pre-fix-reproducer.json`.

### Reconciliação do wrapper K3s interrompido

- `proc_604529af8f88` iniciou às `05:53:19 BRT` e completou o backup de config/unit/manifests antes de entrar no restart síncrono do K3s.
- Backup: `/home/ubuntu/backups/atius-sso-live-total-regression-20260731-052218/k3s-srv1`; `14` arquivos, `19.318` bytes, checksum PASS, restore-readiness PASS para o escopo registrado. Não inclui datastore/etcd.
- Às `06:03:39 BRT`, a sessão chamou `process.kill` para liberar o wrapper preso enquanto a investigação de firewall/etcd continuava. O resultado persistido é `completion_reason=killed` e `termination_source=process.kill`; logo, `143/SIGTERM` não foi timeout, OOM nem dano ao backup.
- O wrapper morreu antes dos probes e nunca produziu `k3s_restart_verify=PASS`; esse marcador não pode ser retroativamente atribuído ao run.
- A allowlist privada em iptables concluiu às `06:04:41 BRT`. Após tentativas intermediárias com exit `1`, o K3s atual começou às `06:05:52` e ficou `active/running` às `06:06:10`.
- Readback independente: node `Ready=True`, K3s result `success`, config/unit/manifests byte-exact com o backup. Não houve repetição do restart.
- O `DiskPressure` começou apenas às `10:13:14 BRT`; Prometheus/Loki `Pending` são uma degradação posterior e não evidência de dano pelo SIGTERM.
- Evidence: `docs/evidence/atius-sso/2026-07-31-k3s-restart-wrapper-sigterm-reconciliation.json`.
- GBrain: `atius-sso-k3s-restart-wrapper-sigterm-2026-07-31/index`, import `--no-embed` + readback PASS; Graphify adiado enquanto `DiskPressure=True`.

### Reconciliação do fan-out VXLAN tardio

- `deleg_68a11ed4` executou diagnóstico read-only entre `07:01:49` e `07:09:25 BRT`; nenhum comando mutante aparece no transcript do subagente.
- A sessão principal executou, em paralelo, o rollout do guard de firewall nos peers entre `07:05:04` e `07:05:13 BRT`. Assim, o PASS cross-node do fan-out às aproximadamente `07:07 BRT` é **pós-rollout**, não baseline independente.
- Naquele instante, Grafana `10.42.2.5` resolveu CoreDNS e alcançou Prometheus pelo service e pelo pod; isso prova recuperação da malha depois do alinhamento do firewall.
- Readback atual mantém VXLAN/DNS cross-node saudável para endpoints existentes: Grafana `10.42.2.9` alcança CoreDNS no SRV-2 e Alertmanager `10.42.1.34`.
- Prometheus/Loki atuais têm zero endpoints por scheduling/storage no SRV-1; esse estado posterior não revoga o proof de rede e também não permite declarar observabilidade saudável.
- Firewall live: script/unit byte-exact e service `active/enabled` nos quatro nodes. Débitos persistentes: os dois artefatos ainda estão `untracked`; o watchdog não verifica os guards remotos; os backups `07:05` não têm manifesto de checksum.
- Evidence: `docs/evidence/atius-sso/2026-07-31-vxlan-async-post-firewall-reconciliation.json`.
- GBrain: `atius-sso-vxlan-async-post-firewall-reconciliation-2026-07-31/index`, import `--no-embed` e readback PASS; Graphify adiado por `DiskPressure`.

### Reconciliação dos diagnósticos tipográfico e visual assíncronos

- `deleg_fcbee331` operou read-only de `07:35:58` a `07:45:58 BRT`. O transcript registra `29` API calls, coleta live/source concluída e zero tool calls mutantes; o status `timeout` veio do budget de `600s` antes da emissão do resumo final, não de falha de browser, API ou produto.
- `deleg_115bbf83` operou de `07:35:59` a `07:45:59 BRT` como reviewer read-only. Registrou `37` API calls e `58` tool calls no transcript, capturou os seis `/login`, screenshots, computed styles, contact sheet e pixel metrics, e expirou durante a síntese final sem emitir score/summary.
- Os únicos writes do reviewer foram três scripts efêmeros em `/tmp`; houve zero mutações de produto, runtime ou repo. `vision_analyze` `503` e navegação `file://` `400` foram falhas auxiliares posteriores à captura, não falhas dos seis sites.
- A evidence pré-fix durável mostra a divergência real: referência central em `11px/400/16.5px`, hostname `14px/400/20px` e labels `14px/500/20px`; Grafana/Portainer/Docker/AdGuard em `10px`, hostname `16px/600` e labels `14px/650`; VPN em título `10px`, hostname/labels `600`.
- Um coletor concorrente de autoria não comprovada materializou o pack inicial às `07:37:17 BRT`. O segundo pack `/tmp`, de `07:38:49–07:41:32`, pertence a `deleg_115bbf83`, provado por transcript, paths, timestamps e hashes. Ele foi preservado em `docs/evidence/atius-sso/2026-07-31-login-typography-before-fix/ui-review-deleg-115bbf83`.
- O transcript original não foi copiado ao repo porque contém string histórica com formato de credencial devolvida por busca ampla; a evidence versionável mantém path, tamanho, SHA-256 e conclusões redigidas. Secret scan do pack preservado: PASS.
- Como o subagente não emitiu score, o review de seis pilares foi reconstruído no closeout e não atribuído ao reviewer: Copywriting `4`, Visuals `2`, Color `3`, Typography `2`, Spacing `2`, Experience Design `3`; total histórico `16/24`.
- A correção entrou depois dessa janela. Runtime atual: admin-edge e AdGuard source/live byte-exact, services ativos desde `09:26`; VPN ativa desde `09:35`. Gates atuais: Omni `8/8`, VPN contract `1/1`, AdGuard no repo VPN `25/25`, standalone Bun `34/34`.
- Os diagnósticos históricos fortalecem a causa raiz — renderers separados com tipografia, escala e spacing divergentes — e não revogam o pack visual-v2 de `09:41 BRT`: computed-style `7/7`, vision `6/6`, lifecycle `5/5`, `10/10` ciclos e `40/40` screenshots.
- Classificação principal: `HISTORICAL_PRE_FIX_READ_ONLY_DIAGNOSIS_SUPERSEDED_BY_VISUAL_V2`; review: `HISTORICAL_PRE_FIX_UI_REVIEW_RECONSTRUCTED_POST_TIMEOUT_SUPERSEDED_BY_VISUAL_V2`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-typography-timeout-pre-fix-reconciliation.json` e `docs/evidence/atius-sso/2026-07-31-login-typography-before-fix/ui-review-deleg-115bbf83/UI-REVIEW-HISTORICAL.md`.
- Risco ainda aberto: owners/packs seguem `untracked` ou staged/modificados em Omni, VPN, standalone e ATS; live está correto, mas um rebuild/deploy a partir de source incompleto pode reintroduzir drift até persistência Git coordenada.
- GBrain: `atius-sso-typography-timeout-pre-fix-reconciliation-2026-07-31/index`, import `--no-embed` e readback PASS após atualização.
- Graphify continua `DEFERRED_DISKPRESSURE`: `DiskPressure=True`, root `90%`, `20G` livres e zero runners.

### Incidente operacional posterior

- `DiskPressure=True` começou às `10:13 BRT`, depois do diagnóstico e da certificação visual.
- Prometheus e Loki estão `Pending` por taint `NoSchedule`, `nodeSelector` e PV local presos ao SRV-1.
- O shell Grafana continua saudável, mas o datasource está indisponível; isso exige incidente próprio e não altera o escopo de `PASS_HOST_LOCAL_SSO_VISUAL`.
- Incidente: `AiSecondBrain/61-Incidents/2026-07-31-srv1-diskpressure-prometheus-loki-pending.md`.
