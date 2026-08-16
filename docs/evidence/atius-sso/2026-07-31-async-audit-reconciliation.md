# 2026-07-31 — Reconciliação da auditoria async SSO

Status: `LIVE_PARTIAL_NONCOMPLIANT`.

## Resultado

- Control plane central: disponível.
- Grafana/Portainer/Docker: host-local shell e gateway disponíveis.
- AdGuard: correto; documento anônimo recebe `302 /login`, API anônima recebe `401`.
- VPN: regressão de contrato confirmada; login local chama `/api/auth/login` → `/v1/token/generate` e não prova OIDC central.

## Evidence antiga

Os packs de 2026-07-30 são históricos. O harness permitia runs filtrados por `E2E_TARGETS` emitirem `PASS` pelo tamanho do subconjunto. Isso não prova um run único da frota e não prova Authorization Code + PKCE.

## Harden aplicado

`modules/atius-admin-edge-sso/scripts/validate-atius-sites-sso-lifecycle.mjs` agora:

- reserva `PASS` para os cinco sites;
- exige `E2E_ALLOW_SUBSET_PASS=1` para filtro;
- rotula sucesso filtrado como `PASS_SUBSET`;
- registra escopo e limites no report.

Helper: `modules/atius-admin-edge-sso/scripts/sso-lifecycle-evidence-scope.mjs`.

Validação targeted: Node syntax, helper parity e `git diff --check` PASS. No repo standalone, o teste de regressão e o gate completo passaram `74/74`.

Nenhuma produção foi alterada. Backup pré-edição: `/home/ubuntu/backups/atius-sso-async-audit-reconcile-20260731-044632`.

## Reconciliação tardia do fan-out completo — 10:49 BRT

- O fan-out foi executado entre `05:18` e `05:28 BRT`, antes da correção visual v2 e da certificação final.
- Os timeouts de VPN, AdGuard, forensics e harness não invalidam o closeout posterior; os transcripts foram lidos e comparados com source/runtime atuais.
- O harness atual cobre geometria, logo, SVGs, favicon, tipografia, estados intermediários, conteúdo autenticado e screenshots; o falso PASS visual descrito pelo subagente corresponde ao harness antigo.
- A auditoria revelou um incidente separado de segurança: `atius-api` escuta em `0.0.0.0:8015` e a porta está exposta diretamente.
- Probe externo do `horistic-srv` alcançou `137.131.190.161:8015` e `10.11.1.11:8015`.
- Logs PM2 contêm `189` requests públicos diretos com `Host: ...:8015`, incluindo scanners e traversal probes.
- Remediação proposta: `API_HOST=127.0.0.1`, restart controlado e regressão completa; bloqueada por gate explícito de produção.
- Incidente: `AiSecondBrain/61-Incidents/2026-07-31-atius-api-porta-8015-exposta.md`.
- Backups: `/home/ubuntu/backups/atius-api-public-8015-incident-20260731-104527` e `/home/ubuntu/backups/atius-api-8015-docs-20260731-104954`, checksums PASS.
- O `pm2 save` usado para materializar o backup alterou somente o dump persistente; pre/post sanitizados têm os mesmos `19` apps e o runtime `atius-api` permaneceu no mesmo PID/listener.
- Debts secundários: Grafana/Portainer têm drift entre `sites-enabled` e `sites-available`; logout admin-edge host-local não comprova POST+CSRF central.
- O veredito visual permanece `PASS_HOST_LOCAL_SSO_VISUAL`; o incidente de rede fica `OPEN/HIGH` e fora do escopo visual.
- Evidence machine-readable: `docs/evidence/atius-sso/2026-07-31-atius-api-public-8015-incident.json`.
- Primeiro seal Graphify: `success/status=0`, `4m17s`, CPU limitada a `20%` do host, `nr_throttled=770`, pico `1.7G`, swap pico `0B`.
- Graphify pós-seal: Omni `14011/20042`; vault `37565/63222`; query do incidente no vault `14` nodes e `13` edges.

## Processo tardio `proc_397b5f569f20`

- Classificação: `OBSOLETE_HARNESS_PROCESS_FAILURE`.
- O comando `node /tmp/atius-sso-app-readiness-diagnostic.mjs` terminou em `MODULE_NOT_FOUND` antes de executar qualquer probe do produto.
- O arquivo temporário atual foi materializado posteriormente (`mtime 05:37:02 BRT`) e passa `node --check`; ele não transforma a falha anterior em regressão do produto.
- Readback atual: cinco `/login=200`, API central `healthy`, zero diagnostic/lifecycle runner.
- Não reabrir nem redisparar `proc_397b5f569f20`; o pack visual-v2 posterior permanece autoritativo.
- Evidence: `docs/evidence/atius-sso/2026-07-31-obsolete-readiness-harness-process.json`.

## Processo posterior `proc_3c0b08ba1c60`

- O mesmo comando terminou `exit 0` em outro processo e materializou evidence às `05:38 BRT`.
- `exit 0` significa coletor completo, não PASS irrestrito: o script registra `failures[]` e console, mas não possui asserts sobre esses arrays, erros de painel, séries carregadas ou spinners.
- Grafana autenticou e renderizou `12` painéis, mas na janela `05:37` houve `3` requests de datasource Prometheus com `500`, `8` WebSockets `403`, painéis sem dados e um erro de plugin visível aos `15s`.
- Docker/Portainer autenticou, exibiu `1` environment card e zerou os spinners até `15s`; o locale `en-US` deu `404`, com fallback e sem degradação visual observada.
- O WebSocket foi corrigido depois: o access log contém `10` upgrades `101` a partir de `07:23 BRT`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-readiness-diagnostic-0537-reconciliation.json`.

## Reproducer histórico `proc_3a60256f5a48`

- O processo `node /tmp/atius-sso-duplicate-cookie-proof.mjs` terminou `exit 0` e materializou evidence às `05:50 BRT`.
- O browser autenticou inicialmente com o cookie canônico `.atius.com.br`, depois recebeu intencionalmente um `auth-token` host-only inválido para `grafana.atius.com.br`.
- Com os dois cookies, a raiz voltou para `/login`: reprodução causal do bug de precedência de cookie antigo.
- O relogin recuperou o dashboard, mas a evidence pré-fix ainda mostrava os dois cookies coexistindo.
- O primeiro restart com hardening ocorreu às `06:20 BRT`; o runtime atual iniciou às `09:26 BRT`, antes do relatório visual-v2 das `09:41 BRT`.
- Source/live atual é byte-exact (`da122770...`), valida até quatro candidatos em qualquer ordem e expira o host-only legado após relogin.
- Testes focados atuais: `8/8` PASS, incluindo as duas ordens `valid→stale` e `stale→valid`.
- Classificação: `HISTORICAL_PRE_FIX_DUPLICATE_COOKIE_REPRODUCER`; não é regressão atual.
- Evidence: `docs/evidence/atius-sso/2026-07-31-duplicate-cookie-pre-fix-reproducer.json`.

## Wrapper K3s interrompido `proc_604529af8f88`

- O processo foi iniciado em background às `05:53:19 BRT`, com timeout configurado de `900s`, para preservar config/unit/manifests, reiniciar o K3s e verificar node/monitoring.
- O backup terminou antes do restart: `/home/ubuntu/backups/atius-sso-live-total-regression-20260731-052218/k3s-srv1`, `14` arquivos, `19.318` bytes, zero arquivo vazio/parcial e `SHA256SUMS` PASS.
- Escopo exato: `config.yaml`, `k3s.service` e manifests. Não é snapshot de datastore/etcd nem backup full-cluster.
- Às `06:03:39 BRT`, o wrapper ainda estava bloqueado em `systemctl restart k3s` e recebeu kill explícito pela própria sessão: `completion_reason=killed`, `termination_source=process.kill`. O `exit 143/SIGTERM` não veio do timeout, OOM ou corrupção.
- Por isso, o wrapper original não alcançou o loop `attempt=...` nem imprimiu `k3s_restart_verify=PASS`; a validação teve de ser refeita fora dele.
- A recuperação não foi causada pelo kill: a allowlist privada K3s em iptables terminou às `06:04:41 BRT`; houve tentativas intermediárias com exit `1`; o processo atual iniciou às `06:05:52` e entrou `active/running` às `06:06:10 BRT`.
- Readback independente às `12:17 BRT`: K3s `active/running`, result `success`, node `Ready=True`; config/unit/manifests continuam byte-exact com o backup.
- O restart não resolveu o incidente posterior de storage: `DiskPressure=True`, Prometheus/Loki `Pending` e endpoint Prometheus vazio continuam separados e abertos.
- Classificação: `INTERRUPTED_WRAPPER_AFTER_VERIFIED_BACKUP_WITH_LIVE_RECOVERY`; dano encontrado: nenhum.
- Evidence: `docs/evidence/atius-sso/2026-07-31-k3s-restart-wrapper-sigterm-reconciliation.json`.
- GBrain: `atius-sso-k3s-restart-wrapper-sigterm-2026-07-31/index`, import `--no-embed` e readback PASS; Graphify `DEFERRED_DISKPRESSURE`.

## Fan-out VXLAN tardio `deleg_68a11ed4`

- O subagente operou read-only entre `07:01:49` e `07:09:25 BRT`; o transcript não contém install, restart, alteração de iptables ou write live.
- A janela não foi independente do ambiente: em paralelo, a sessão principal alinhou o guard de firewall em SRV-2, SRV-3 e Horistic entre `07:05:04` e `07:05:13 BRT`, com backup host-local, install do script/unit, `daemon-reload`, `enable --now` e restart somente de `atius-k3s-firewall.service`. K3s não foi reiniciado nesse rollout.
- Por isso, os probes de aproximadamente `07:07 BRT` são evidence **pós-rollout**: Grafana `10.42.2.5` resolveu via CoreDNS `10.43.0.10`/`10.42.1.4` e recebeu `Prometheus Server is Ready.` do service `10.43.122.246:9090` e do pod `10.42.0.24:9090`.
- Esses probes não provam que o VXLAN já estava saudável antes do rollout e não representam disponibilidade atual do Prometheus.
- Readback atual `12:34 BRT`: rotas/FDB Flannel coerentes nos quatro nodes; Grafana atual `10.42.2.9` alcança CoreDNS service/pod e Alertmanager `10.42.1.34`; portanto o dataplane cross-node continua saudável para endpoints existentes.
- Prometheus e Loki têm zero endpoints porque continuam `Pending` por `DiskPressure`, taint, `nodeSelector` e PV `local-path` presos ao SRV-1. Ausência atual desses workloads não é evidência de regressão VXLAN.
- Script/unit live estão byte-exact nos quatro nodes (`b4f01c...` / `67f4e9...`) e os services estão `active/enabled`. A recomendação de instalação nos peers foi cumprida pelo rollout concorrente.
- Readback de ordem: ACCEPT privado precede DROP público para UDP `8472` e TCP K3s nos quatro nodes. SRV-2/Horistic mantêm regras ACCEPT duplicadas; a ordem é segura e a limpeza fica adiada para manutenção explícita.
- Débitos ainda abertos: script e unit continuam `untracked` no repo; o watchdog versionado só verifica o firewall local e não cobre SRV-2/SRV-3/Horistic remotamente; os backups host-local do rollout existem e são legíveis, mas não têm `SHA256SUMS`, portanto não recebem claim retroativo de checksum PASS.
- Evidence: `docs/evidence/atius-sso/2026-07-31-vxlan-async-post-firewall-reconciliation.json`.
- Classificação: `READ_ONLY_OBSERVER_POST_CONCURRENT_FIREWALL_ROLLOUT_WITH_CURRENT_VXLAN_HEALTH_AND_LATER_STORAGE_DEGRADATION`.
- GBrain: `atius-sso-vxlan-async-post-firewall-reconciliation-2026-07-31/index`, import `--no-embed` e readback PASS; Graphify `DEFERRED_DISKPRESSURE`.
- Backup documental: `/home/ubuntu/backups/deleg-68a11ed4-closeout-20260731-123605`, `7` arquivos, `136.266` bytes, checksum PASS. O incidente alterado também tem preimage no backup válido `k3s-proc-604529-closeout-20260731-121903`.

## Diagnósticos tipográfico e visual tardios

- O subagente executou somente leitura entre `07:35:58` e `07:45:58 BRT`; o `timeout` de `600s` encerrou a tarefa depois do último probe bem-sucedido às `07:45:52`, sem summary final e sem mutação.
- O transcript provou runtime/source pré-fix com `DESTINO SEGURO` em `10px`, hostname `600` e labels `650` nos gateways; a VPN ainda usava `text-[10px]` e `font-semibold`.
- O pack computed-style durável foi materializado por coletor concorrente de autoria não comprovada às `07:37:17 BRT`.
- `deleg_115bbf83` executou o review visual read-only em paralelo de `07:35:59` a `07:45:59 BRT`: `37` API calls, `58` tool calls no transcript, zero mutações de produto/runtime/repo e três writes efêmeros de scripts em `/tmp`. O pack `/tmp` de `07:38:49–07:41:32` pertence a esse reviewer e não ao debugger.
- O reviewer completou screenshots, computed styles, contact sheet e pixel metrics, mas expirou durante a síntese após falhas auxiliares `vision 503` e `file:// 400`. Nenhuma dessas falhas atingiu os seis `/login`.
- O score de seis pilares foi reconstruído depois do timeout, não emitido pelo subagente: `4/2/3/2/2/3`, total `16/24`. Pack seguro: `docs/evidence/atius-sso/2026-07-31-login-typography-before-fix/ui-review-deleg-115bbf83`; transcript original mantido fora do repo por conter string histórica credential-like em output de busca ampla.
- A matriz pré-fix é causal, não current state. O runtime pós-fix entrou `09:26–09:35 BRT` e o pack visual-v2 autoritativo terminou `09:41 BRT` com `7/7`, `6/6`, `5/5`, `10/10` e `40/40`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-typography-timeout-pre-fix-reconciliation.json`.
- Review histórico: `docs/evidence/atius-sso/2026-07-31-login-typography-before-fix/ui-review-deleg-115bbf83/UI-REVIEW-HISTORICAL.md`.
- Classificação: `HISTORICAL_PRE_FIX_READ_ONLY_DIAGNOSIS_SUPERSEDED_BY_VISUAL_V2`.
- O risco residual é persistência Git/source-runtime, não regressão visual demonstrada: arquivos relevantes ainda estão `untracked`, staged ou modificados nos quatro repos.
- Backup documental: `/home/ubuntu/backups/deleg-fcbee331-closeout-20260731-130848`, `8` arquivos, `156.474` bytes, checksum PASS.
- GBrain: `atius-sso-typography-timeout-pre-fix-reconciliation-2026-07-31/index`, import `--no-embed` e readback PASS.
- Graphify permanece adiado por `DiskPressure=True`; zero runners.

## Processo tardio `proc_7af4368e4884`

- O registro do process manager já havia expirado, mas o comando/output completos foram recuperados da sessão Hermes `@session:default/20260730_034546_71412d`.
- `systemd-run` terminou o Next build de `09:23` com sucesso/status `0`; o log materializado confirma compile, TypeScript, geração `11/11` e `/login`.
- O `exit 1` foi emitido pelo wrapper pós-workload quando o zsh recusou `status=$(...)`, pois `status` é parâmetro especial read-only. Não é falha de build, produto ou runtime.
- O artifact foi substituído pelo build atual de `09:35:23`; o runtime system-level está `active/running` desde `09:35:34`, e os endpoints públicos do login e build manifest respondem `200`.
- Visual-v2 de `09:41` continua autoritativo e inalterado: `PASS_HOST_LOCAL_SSO_VISUAL`, `centralOidcFlow=false`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-proc-7af4368e4884-vpn-build-wrapper-reconciliation.json`.

## Reconciliação do processo ATS `proc_e8fd6e44b09b`

- O alerta tardio trouxe o comando e output completos; a limitação histórica de payload parcial foi superseded pela fonte primária, sem reconstrução ou output inventado.
- `proc_e8fd6e44b09b` terminou `exit 0`. A unit governada fechou `success/status=0`, zero swap; o log do Next build compilou sem erro explícito.
- O artifact `atius-1785500828844` foi promovido, respondeu `200`, passou smoke e foi coberto pelo lifecycle visual posterior `5/5`, `10/10`, `40/40`.
- O build foi substituído somente após patch de source no bootstrap visual. O processo posterior `proc_125b2c12a64b`, unit `atius-central-sso-bootstrap-visual-fix.service`, invocation `c97a77f5169f482095680f2fe16aa601`, passou `success/status=0` em `43.700s`, pico `784.8M`, swap `0B`, materializou `atius-1785502082536` e permanece servido por `atius-web=online`.
- Rollback pré-build permanece preservado e estruturalmente válido; nenhum restore foi executado.
- Classificação: `SUCCESSFUL_ATS_BUILD_PROMOTED_AND_VALIDATED_THEN_SUPERSEDED_BY_LATER_SUCCESSFUL_SOURCE_CHANGE_BUILD_AND_RUNTIME`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-proc-e8fd6e44b09b-ats-build-reconciliation.json`.
- A autoridade operacional continua `PASS_HOST_LOCAL_SSO_VISUAL`, `hostLocalLifecycle=true`, `centralOidcFlow=false`.
- Backups verificados: `/home/ubuntu/backups/proc-e8fd6e44b09b-closeout-20260731-142537` e `/home/ubuntu/backups/proc-e8fd6e44b09b-final-20260731-144543`.

## Reconciliação do processo VPN `proc_f11177028401`

- A notificação tardia completa tornou a fonte primária disponível: processo `exit 0`; unit `atius-vpn-sso-visual-build-v2-final.service`, invocation `adb667ff581045d59aaa3cd4ea3ebe2e`, `success/status=0`, runtime `34.903s`, pico `818.5M`, swap `0B`.
- O artifact `5i44myr1IPLzVZISp62Km` foi promovido e validado em runtime. Health local `200`, front local/público `307`, listeners loopback e asset Atius byte-exato.
- O artifact não virou autoridade visual: a comparação computed-style posterior detectou drift de tipografia/spacing no VPN.
- Patch de source às `09:33:42` corrigiu spacing label/control e tipografia explícita; `proc_8c81b41b836e`, unit `atius-vpn-sso-visual-build-v2-parity.service`, invocation `7aadef3753084c6baa24e2ce527a4886`, passou `success/status=0` em `34.413s`, pico `829.5M`, swap `0B`, e materializou `TyT674tPqvnHnsQM1RTQ_`. O lifecycle visual autoritativo foi `proc_9badcb5bf73d`, invocation `ca41da73483d46149d8e3aeed8f316a2`, `success/status=0`, `5min 23.511s`, pico `488.3M`, swap `0B`, com `5/5` sites, `10/10` ciclos e `40/40` screenshots.
- Classificação: `SUCCESSFUL_VPN_BUILD_PROMOTED_AND_RUNTIME_VALIDATED_THEN_SUPERSEDED_BY_LATER_SUCCESSFUL_SOURCE_PARITY_BUILD_RUNTIME_AND_VISUAL_V2`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-proc-f11177028401-vpn-build-reconciliation.json`.
- Autoridade operacional única: `PASS_HOST_LOCAL_SSO_VISUAL`, `hostLocalLifecycle=true`, `centralOidcFlow=false`.
- Backup pré-closeout: `/home/ubuntu/backups/proc-f11177028401-closeout-20260731-145027`, checksum PASS.

## Incidente atual de observabilidade

- Às `10:13:14 BRT`, horas depois do run acima, o `atius-srv-1` entrou em `DiskPressure=True` com root em `90%`.
- Prometheus e Loki ficaram `Pending`: ambos têm `nodeSelector` e PV local presos ao SRV-1, agora tainted com `NoSchedule`.
- O Grafana continua autenticável/saudável no shell, mas o datasource Prometheus está indisponível.
- Este incidente operacional é separado do contrato visual SSO e não explica os `500` das `05:37`.
- Incidente: `AiSecondBrain/61-Incidents/2026-07-31-srv1-diskpressure-prometheus-loki-pending.md`.
- Evidence: `docs/evidence/atius-sso/2026-07-31-srv1-diskpressure-monitoring-incident.json`.