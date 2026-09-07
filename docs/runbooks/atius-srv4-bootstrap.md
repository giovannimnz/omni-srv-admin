# Bootstrap de novo servidor OCI ARM64

Este runbook transforma uma instância Ubuntu 24.04 ARM64 mínima no padrão
operacional ATIUS. Ele foi validado em `atius-srv-4`.

## Entry point versionado

O orchestrator canônico, resumível e fail-closed é
`modules/fleet/scripts/oci-arm64-host-setup.sh`.

O staging deve ser gerado pelo builder versionado
`modules/fleet/scripts/build-oci-arm64-host-setup-staging.py`, usando a
allowlist exata `modules/fleet/configs/oci-arm64-host-setup-files.txt`. Não
montar `SOURCE-MANIFEST.json` com harness ad hoc: o builder copia só arquivos
declarados, recusa symlink/path traversal, registra bytes/mode/SHA-256, cria o
archive tar determinístico e executa restore drill antes da promoção.

- `--dry-run`: lista ações sem escrever;
- `--verify-only`: executa todos os gates sem remediar;
- `--apply`: executa todos os passos idempotentes e preserva um receipt por
  step em `~/.local/state/omni/oci-arm64-host-setup/`;
- `--apply --resume`: recuperação de uma execução interrompida; nunca substitui
  o full apply sem resume usado como seal de fresh-host;
- cada receipt registra o SHA-256 de `SOURCE-MANIFEST.json`; mudança em qualquer
  artifact do staging invalida PASS antigo e força o novo contract a rodar;
- `agent-content` é aplicado item-scoped pelo orchestrator SRV-1. O target não
  recebe private key outbound apenas para executar self-SSH;
- OAuth de Codex/Hermes continua host-local e não é copiado.

Sequência de aceitação: `--dry-run` → `--apply` sem resume → `--verify-only`.
O verify-only é o gate pós-apply independente, não uma pré-condição para um host
ainda vazio.

## Ordem obrigatória

1. Confirmar que cloud-init e qualquer instalador de utilitários terminaram.
2. Pelo `oci_admin_http`, validar instance `RUNNING`, VNIC, IP privado/público,
   NSG/security list e a tabela de rota efetiva da subnet.
3. Para SSH público, a subnet precisa usar uma route table com
   `0.0.0.0/0 -> Internet Gateway`; não usar a VCN ingress route table como
   route table da subnet.
4. Confirmar TCP/22 antes de diagnosticar chave. Comparar fingerprints da
   chave privada local e da chave pública entregue por Vault, sem expor o
   material.
5. Criar `~/GitHub` e `~/GitHub/containers`; copiar o checkout limpo mais
   recente de `omni-srv-admin` ou clonar a origem verificada.
6. Instalar a baseline ARM64: Git, Python/venv/pipx, Podman rootless, rede,
   build tools, Rust estável, cargo-binstall e Zellij. Materializar
   `~/.config/environment.d/90-atius-developer-tools.conf` para que
   `~/.cargo/bin` e `~/.local/bin` existam também nas sessões XRDP e systemd
   do usuário.
   Configurar Podman com `srv4-podman` em `10.10.4.0/24`, netavark e
   `systemd-resolved`; habilitar linger e `podman.socket` para persistência
   user-level, sem iniciar stacks de aplicação.
   Antes do primeiro `apt-get update` do setup, instalar os keyrings/sources
   públicos versionados para ChatGPT e Google Chrome:
   `modules/fleet/configs/apt/keyrings/{chatgpt-archive-keyring.gpg,google-chrome.gpg}`
   e `modules/fleet/configs/apt/sources.list.d/{chatgpt.sources,google-chrome.sources}`.
   Host fresh sem esses sources não resolve `chatgpt` nem
   `google-chrome-stable` pelos repositórios Ubuntu padrão.
7. Instalar `omni` em pipx e executar a etapa de teclado pela skill
   `$xrdp-abnt2-fleet`, versionada em
   `modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`.
   Usar `--install-packages` somente no host novo e validar os três units XRDP
   e o timer de reconciliação conforme o procedimento canônico.
8. Fixar o teclado global em `br(abnt2)` e revalidar o guard XRDP; a sessão
   RDP usa os keymaps canônicos mesmo sem um desktop já aberto.
9. Instalar e registrar `landscape-client` no Landscape self-hosted
   `standalone` com os endpoints `message-system` HTTPS e `ping` HTTP. Nunca
   usar o profile SaaS legado para o self-hosted.
10. Hidratar o profile Vault `omni-fleet`, instalar `omni-fleet-agent` e
    registrar o inventário no DbOmniFleet; confirmar heartbeat, programas e
    versão antes de declarar o host incluído nos relatórios. `systemctl active`
    não basta: exigir cache local fresh em `~/.logs/fleet/{heartbeats,versions}`
    e readback fresh de `TbNodes`/`TbVersion` via PgBouncer. Adicionar o host a
    `modules/fleet-control-plane/configs/omni-version-matrix.json` e aos
    allowlists `omni.fleet.heartbeat`/`omni.self-update.linux`.
11. Registrar o host no inventário, documentar a evidência e atualizar GBrain
    e Obsidian com fatos sem segredos.
12. Instalar Node.js LTS atual, npm, Bun, Codex CLI e Hermes Agent. Configurar
    os MCPs HTTP `gbrain_http`, `obsidian_http` e `oci_admin_http` com token
    hidratado do profile Vault `atius-mcp`; não copiar `auth.json` de outro host.
13. Criar chave SSH dedicada do host para o exporter Vault forced-command e
    outra deploy key GitHub exclusiva para o clone do Obsidian. O SRV-4 usa
    sync pull-only e nunca auto-commita/pusha o vault.
    Instalar também `browser-default-reconciler` com
    `BROWSER_DESKTOP=google-chrome.desktop` e `CODEX_DESKTOP=chatgpt.desktop`;
    aceitar somente `.path`/`.timer` ativos, state `success` e handlers
    HTML/HTTP/HTTPS em Google Chrome + `x-scheme-handler/codex` em ChatGPT.
14. O hostname do sistema deve ser `atius-srv-4.atius.internal`; o DNS interno
    publica A/PTR em `10.14.1.14`; o DNS público publica
    `atius-srv-4.atius.com.br -> 164.152.48.22` como DNS-only.
    `/etc/hosts` deve mapear o FQDN e short hostname para `10.14.1.14`, não
    `127.0.1.1`, para que `getent` local não contradiga o DNS autoritativo.
15. `wg100` usa `10.100.100.18`. Não usar `10.100.100.14`, que já pertence ao
    peer histórico `GIOVANNI-UBUNTU-S23`.
16. Instalar o resource governor com
    `PYTHONPATH=cli:. python3 -m omni srv1-ops resources install --generic-host`.
    O flag é obrigatório fora do SRV-1: evita instalar o
    `inviolable-watchdog`, que contém checks e relaunch de apps exclusivos do
    host de produção. Depois, executar
    `modules/srv1-ops/scripts/install-build-cpu-guard.sh` e validar
    `resources doctor` + um build smoke dentro de `omni-builds.slice`.
17. Para Podman Compose, o padrão da frota é
    `~/.local/bin/podman-compose` 1.6.0. O package APT 1.0.6 pode ficar como
    fallback, validado com `PYTHONNOUSERSITE=1 /usr/bin/podman-compose --version`.
    Rodar compose config/run/down descartável e provar zero resíduos.
18. Smokes HTTP sob `pipefail` nunca usam `curl <body> | head`. Salvar body em
    arquivo temporário com `curl -o`, validar HTTP code/bytes com `-w` e só
    depois ler uma linha do arquivo. `curl | head` pode sair 23 num endpoint
    saudável porque o consumer fecha o pipe cedo.
19. Em hosts NetworkManager/Netplan, remover resolvers públicos concorrentes do
    profile ativo e manter somente `10.11.1.11`; o CoreDNS encaminha Internet.
    Validar `resolvectl query` para todos os peers. `dig @10.11.1.11` sozinho
    não prova que o resolver local evita NXDOMAIN races.
    Após publicar um host novo em `atius.internal`, validar também
    `resolvectl/getent` em SRV-1/2/3. Se `dig @10.11.1.11` responde mas o stub
    local não, instalar o drop-in versionado
    `modules/fleet/configs/systemd/resolved.conf.d/60-atius-internal.conf`,
    reiniciar `systemd-resolved`, limpar cache e revalidar Internet + todos os
    nomes `atius-srv-{1,2,3,4}.atius.internal`. Em SRV-2, remover qualquer linha
    `127.0.1.1` que carregue o próprio FQDN; o self lookup deve retornar
    `10.12.1.12`.
20. No primeiro login XRDP, desabilitar `light-locker.desktop` no XDG autostart.
    Preservar qualquer crash report antes de limpar o Apport e repetir o login
    no display `:1` até obter desktop limpo.
21. XRDP só fecha GREEN com o leaf ATIUS presente em
    `/etc/xrdp/atius-rdp/server.{crt,key}.pem`, chain válida contra a ATIUS RDP
    Fleet Root CA, `serverAuth`, key match, validade mínima de 30 dias e SANs
    para `164.152.48.22`, `10.14.1.14`, `10.100.100.18`, `atius-srv-4`, `srv4`
    e `atius-srv-4.atius.internal`. O journal precisa selecionar `SSL` e
    registrar TLS; fallback para protocolo RDP é FAIL mesmo que LXDE abra.
22. Assinar `C:\Users\muniz\Desktop\ATIUS-SRV-4.rdp` com o publisher ATIUS
    confiado e usar `10.100.100.18` como endereço padrão. O private key da CA
    permanece no Windows; o private key do leaf nasce e permanece no SRV-4.
23. Attach Ubuntu Pro por attach-config `0600` com `--no-auto-enable`, habilitar
    apenas ESM Apps/Infra e preservar o Landscape self-hosted `standalone`.
    O token fica em `kv/atius/ubuntu-pro/subscription`; caches temporários no
    target são removidos depois do attach.

O SRV-4 segue esse contrato como bootstrap próprio; isso não o torna
participante do rollout histórico da frota em 2026-08-29.

## Guardrails

- Nunca copiar `.ssh/private.pem`, Vault tokens, `.env`, caches ou dumps PM2
  entre hosts.
- Não promover K3s, Vault, Wayland, PM2 de produção ou containers de outro
  servidor sem que a função do novo host esteja explicitamente definida.
- A integração ao DRG central é cross-tenancy e exige OperationPlan, preview,
  confirmação tipada, readback e atualização das rotas dos dois lados. No
  SRV-4, o DRG está ativo e o inventário não deve voltar a `pending`.
- Depois de a rota DRG estar comprovada, adicionar `10.14.0.0/16` aos guards
  persistentes de serviços do SRV-1 (PgBouncer e Obsidian REST) e às rotas
  OCI-primary do host antes de declarar a malha privada green.
- RDP público não é baseline. Expor TCP/3389 somente por regra OCI específica
  e aprovada para a origem necessária.

## Evidência de conclusão

- SSH por chave canônica autenticado;
- TCP/22 e a route table efetiva comprovados;
- `podman info` rootless e smoke de container aprovados;
- `omni xrdp-abnt2 validate` aprovado;
- leaf XRDP ATIUS serial `100C`, fingerprint SHA-256
  `7B:26:6A:45:87:98:21:A7:59:9C:07:16:51:B9:1D:4A:ED:BB:C6:40:28:85:D1:D1:1F:AB:3C:A1:BE:CF:C6:02`,
  TLSv1.3 `TLS_AES_256_GCM_SHA384` e `.rdp` Windows assinado;
- `landscape-config --is-registered` e `landscape-client` ativos;
- `omni-fleet-agent` ativo, com heartbeat e relatórios DB para o host;
- heartbeat autônomo avança no `DbOmniFleet` sem restart da unit; a matrix de
  versão inclui `atius-srv-4` e `version-table --db` retorna sua linha;
- `~/GitHub/omni-srv-admin` limpo no commit registrado;
- inventário, GBrain e Obsidian atualizados.
- `hostname -f` retorna `atius-srv-4.atius.internal`;
- IP público reservado, A/PTR interno e A público têm readback independente;
- `wg show wg100` tem handshake recente e SSH em `10.100.100.18` autentica;
- `node`, `npm`, `bun`, `codex`, `hermes`, GSD e Graphify respondem;
- `hermes mcp test` e `codex mcp list` validam os três MCPs HTTP;
- clone Obsidian e timer pull-only estão limpos/ativos;
- login XRDP cria `Desktop/Documents/Downloads/...` e sessão LXDE no display `:1`.
- depois do logout, não ficam scopes `abandoned` nem watchers de teclado/painel;
  os watchers encerram em até 10 segundos após o display desaparecer.
- `resolvectl` e `getent` resolvem todos os peers `.atius.internal` usando
  somente o DNS `10.11.1.11`, e nomes públicos continuam funcionais.
- `resources doctor` retorna `doctor_ok: True`; um build smoke mostra
  `omni-builds.slice` e `cpu.max=80000 100000` em host com 4 vCPUs.
- O updater foi executado duas vezes sob `omni-builds.slice` porque o upstream
  avançou durante o closeout. Observação final em
  `2026-09-05T12:46:16Z`: upstream/local `9e23028e`, ahead/behind `0/0`, tree
  clean. Os HEADs grafted/orphan anteriores `b51c055a` e `bde6f6dc` ficaram
  preservados em `refs/hermes-update-backups/`.
- Backup final `~/.hermes/backups/pre-update-2026-09-05-124525.zip`: mode
  `0600`, `74.758.734` bytes, SHA-256
  `eb344bbdbaca885d883a445e5dd6d0296aba0879e8109594fbbdb3fe084174c2` e
  `unzip -t` PASS. Config/doctor rc 0, MCPs `115/16/12` e smoke
  `SRV4_HERMES_9E23028_OK` passaram. Production npm audit já estava em zero.
  OAuth continua pendente. O SHA é uma observação timestamped; upstream pode
  avançar depois sem representar regressão do host.
- Seal posterior de 2026-09-06: o orchestrator executou `17/17` steps em apply
  por três rodadas completas durante a convergência e `17/17` em verify-only.
  O seal final fixa Hermes no commit fleet-validado
  `01ae7a5668ce0fa2efca524a4567cacdd0786c95`, em vez de perseguir uma branch
  `main` móvel. GSD Core
  `1.13.0/full` passou `868/868` em Codex e Hermes; Bun `1.4.2`; ChatGPT
  `26.901.51231`; Ubuntu Pro attached com ESM Apps/Infra e Landscape
  self-hosted preservado. O login headless real criou display `:1`, LXDE,
  LXPanel, PCManFM e oito pastas XDG; o framebuffer dark não mostrou erros.
  O primeiro harness cliente reconectou sem uma segunda senha e capturou um
  diálogo de login failed, mas o login original já estava ativo. A conclusão
  usa o journal `Session started successfully`, processo/cgroup live e captura
  direta do framebuffer da sessão original. Dois scopes históricos
  `c3/c4` em estado abandoned e quatro watchers órfãos foram removidos; o
  gerador foi corrigido para os watchers encerrarem quando o display morre.
  O build guard também foi corrigido para tratar membership real em
  `omni-builds.slice` como autoridade suficiente. O requisito anterior de
  herdar `OMNI_BUILD_CPU_GUARD_ACTIVE=1` causava deadlock em
  `npm ci -> node-gyp -> make`, porque o child tentava adquirir o semaphore já
  retido pelo próprio ancestor. O regression test e o build real do Hermes
  Desktop passaram após o fix.
  O preflight do setup agora valida containment, ausência de symlink, bytes,
  mode e SHA-256 de cada artifact declarado em `SOURCE-MANIFEST.json`.
  Timezone Hermes é `America/Sao_Paulo`; `UTC-3` é inválido para `zoneinfo`.
- Processo operacional inicial `proc_ee218970f57e`: exit 0 e installer completo
  em `00:01:10–00:06:37Z`, classificado
  `operational-pass-not-review / superseded-by-newer-current-proof`. Script,
  log e journal foram preservados em
  `docs/operations/evidence/2026-09-05-proc-ee218970f57e-reconciliation/`.
  O installer `/tmp` continha `curl | bash`, não é canônico e foi removido só
  após hash local=remote; o log histórico permanece `0600`.
- `fleet-storage-audit.service/timer` ficam `not-found` no SRV-4 por design.
  A unit versionada executa `storage-audit all` e pertence ao orchestrator
  SRV-1; instalar a mesma timer no target duplicaria o fan-out e exigiria uma
  chave outbound que o SRV-4 não possui. A cobertura do SRV-4 é o audit
  explícito disparado pelo SRV-1, que passou em 3 s. Não confundir com os timers
  locais `resource-governor-doctor/audit`, que são parte do baseline do host.
- Processo histórico `proc_8f85e83756ca`: `repair --install-packages` aplicou o
  tema, mas saiu 1 após `AltGr/Electron preservado`; o `apply_all()` antigo
  herdava o status false de `[ RESTART_SESSION -eq 1 ]`. Classificação:
  `failed-probe-fixed-current-tree / historical-false-status-current-source-idempotence-pass`.
  Current source foi executado sem restart, chegou ao validator e passou.
  Duas execuções consecutivas produziram manifestos SHA/mode idênticos para 27
  outputs. Runtime durável: `~/.local/bin/dark-themectl`; clone permaneceu clean.
  Evidence: `docs/operations/evidence/2026-09-05-proc-8f85e83756ca-reconciliation/`.
- Processo histórico anterior `proc_09d9a470d8c0`: duplicate byte-equal da
  mesma false-exit class, backup próprio `20260905-011304` restore-tested.
  Nenhum novo patch/rerun foi necessário; classificação
  `failed-probe-fixed-current-tree / duplicate-historical-probe-superseded-by-current-proof`.
  Evidence: `docs/operations/evidence/2026-09-05-proc-09d9a470d8c0-reconciliation/`.
- `proc_9298dbc5399e` falhou exit 127 antes de qualquer installer: `npx` ainda
  não existia no PATH não interativo. Classificação
  `failed-probe-fixed-current-tree / failed-prerequisite-later-resolved-by-separate-install`.
- O retry `proc_61114807cf18` instalou GSD 1.12.0/full para Codex/Hermes e
  saiu 0, mas é `operational-pass-not-review`; suas versões Hermes/Graphify
  foram superseded e `codex_gsd=0` era uma contagem de path inválida.
- Current seal GSD:
  - Codex: 71/71 skills oficiais em `~/.agents/skills`, hashes relocados exatos,
    zero drift não-skill. O manifest 1.12.0 registra 71 paths incorretos em
    `~/.codex/skills`; bug reproduzido em install fresh isolado.
  - Hermes: o update posterior sobrescreveu `skills/gsd/**`; repair Hermes-only
    pinado em 1.12.0/full após backup/restore trouxe manifest `737/737` e
    restaurou `gsd-next`/`gsd-onboard`.
  - Backups pre/post repair: 765 e 829 arquivos, restore-tested.
  - Suite Omni pós-repair: `238/238`; ambos os smokes `check auto-mode` rc 0,
    repo SRV-4 clean e failed units `0/0`.
  - Evidence: `docs/operations/evidence/2026-09-05-gsd-srv4-current-proof/`,
    `...proc-9298dbc5399e-reconciliation/` e
    `...proc-61114807cf18-reconciliation/`.
- `proc_d6191acfa3eb`: installer histórico dos packages oficiais ChatGPT e
  Google Chrome ARM64, classificado `operational-pass-not-review /
  superseded-by-newer-current-proof-with-mime-and-harness-fixes`.
  - ChatGPT avançou de `26.901.41123` para `26.901.41600`; Chrome permanece
    `152.0.7977.82-1`.
  - Source/keyring hashes continuam byte-equal ao baseline SRV-1; `dpkg -V`,
    ELF ARM64, Chrome sandbox `4755 root:root`, launchers e APT health passam.
  - SRV-4 não possui Brave; Chrome oficial é o default aprovado para HTML,
    HTTP e HTTPS. `x-scheme-handler/codex` permanece ChatGPT.
  - Audit final: `22 PASS / 0 DRIFT / 2 N/A`; Chrome DOM smoke roda com
    HOME/XDG/DBus isolados. ChatGPT Xvfb isolado abriu window, criou 2
    renderers, estabilizou CPU e não alterou MIME real.
  - O startup real do ChatGPT reassumia `text/html`; `browser-default-reconciler`
    foi instalado como `.path` + `.timer`, sem DBus. Failure injection nos três
    handlers convergiu em 160 ms, preservou `x-scheme-handler/codex=chatgpt.desktop`
    e o tick seguinte do timer foi no-op com failed units `0/0`.
  - Primeiro deploy do guard ficou preservado como FAIL `218/CAPABILITIES`:
    `ProtectKernelModules=true` é incompatível com a user manager do host.
    Bisection isolou o directive; o deploy corrigido passou pela unit real.
  - Source/live parity passou; focused managed-apps `11/11` e suite Omni
    `242/242`. Snapshot pós-deploy com 15 arquivos passou restore byte/mode.
  - Evidence: `docs/operations/evidence/2026-09-05-proc-d6191acfa3eb-reconciliation/`.
- `proc_2459d1161e30`: sync histórico substituiu integralmente os roots Codex e
  Hermes por tar do SRV-1. Exit 0 foi classificado `operational-pass-not-review /
  superseded-by-current-item-scoped-agent-content-proof`.
  - Archives históricos passaram SHA e restore byte/mode: Codex 71 arquivos,
    Hermes 422. Contagens históricas 30/507 não são contrato de paridade.
  - Root replacement fica proibido; a autoridade atual é `agent-content-packs`
    por item, com preimage transacional e preservação de extras.
  - Manifest stale da skill bootstrap e targets SRV-4 ausentes no shared pack
    foram corrigidos e cobertos por testes.
  - Apply granular: Codex bootstrap, seis skills Hermes e NotebookLM nos dois
    runtimes. Quatro dry-runs finais noop: 11/19/10/20 arquivos.
  - Estado atual: 31 Codex e 449 Hermes skills, 9 preimages, zero rollback,
    Hermes GSD 737/737, critical discovery PASS, repo clean e failed units 0/0.
  - Focused agent-content `20/20`; suite Omni `243/243`.
  - Evidence: `docs/operations/evidence/2026-09-05-proc-2459d1161e30-reconciliation/`.
- `proc_44edf3223e02`: cleanup SRV-1 histórico classificado
  `operational-pass-not-review / historical-no-op-cleanup-superseded-by-current-governed-loop-fix`.
  - Run exato 23:53:51–23:54:05 BRT: zero deletes, pnpm 0/0,
    Podman 10.88→10.88GB, journal 0B, disco 13G→13G.
  - Finding posterior separado: 76 runs independentes depois do processo;
    `server-analysis.timer` repetia cleanup completo em disk critical sem cooldown.
  - Corrigido com lane build-hygiene, cooldown persistente 6h/state+lock 0600,
    warning inventory-only e zero auto-prune de volumes.
  - Dois ticks reais avançaram sem cleanup (`2605→2605`), weekly timer preservado;
    focused `30/30`, suite `247/247`, failed units `0/0`.
  - Evidence: `docs/operations/evidence/2026-09-05-proc-44edf3223e02-reconciliation/`.
- `proc_f7b5314f81e7`: exit 23 classificado como
  `post-workload-harness-failure / curl-write-error-after-head-closed-pipe`.
  - Installs e services estavam green antes do failure; Node Exporter e Cockpit
    retornam 200, Podman socket/linger ativos e Graphify 0.9.23.
  - Reproduzido `pipeline/curl/head = 23/23/0`; safe pattern com body em arquivo
    passa. Bootstrap foi corrigido e sincronizado item-scoped/post-noop.
  - Podman Compose alinhado ao user-local 1.6.0; APT 1.0.6 preservado via
    `PYTHONNOUSERSITE=1`; compose config/run/down smoke sem resíduos.
  - Security List pública só contém TCP/22; 9090/9100 timeout em SRV-1/2/3.
    NSG rule details indisponíveis: block é observational, não union seal.
  - Evidence: `docs/operations/evidence/2026-09-05-proc-f7b5314f81e7-reconciliation/`.
- `proc_2df37032fe87`: upgrade APT classificado
  `operational-pass-not-review / superseded-by-later-chatgpt-runtime-proof`.
  - ChatGPT 41123→41600 e procps/libproc2 `.2→.3`; apt check PASS,
    upgradable 0, reboot não requerido e payload MD5 mismatch 0.
  - `ps`/`pgrep`/`top` passam. Missing docs/manpages em `dpkg --verify` são
    policy nodoc/noman, não corrupção de payload.
  - Xvfb proof posterior ocorreu exatamente 15:16:24.123576 após o upgrade;
    window/renderers/app-server/cleanup passaram. A estimativa inicial 5h12 foi
    corrigida antes da documentação.
  - Evidence: `docs/operations/evidence/2026-09-05-proc-2df37032fe87-reconciliation/`.

## Seal final de 2026-09-06

- O staging canônico é gerado por
  `modules/fleet/scripts/build-oci-arm64-host-setup-staging.py` usando a
  allowlist `modules/fleet/configs/oci-arm64-host-setup-files.txt`; não há mais
  `SOURCE-MANIFEST.json` montado por harness ad hoc.
- Fresh-host APT instala keyrings/sources oficiais ARM64 de ChatGPT e Google
  Chrome antes do primeiro `apt-get update`; o step desktop instala e valida
  `browser-default-reconciler` para Chrome/ChatGPT.
- O DNS foi validado no caminho do cliente: SRV-1/2/3/4 resolvem
  `atius-srv-4.atius.internal` para `10.14.1.14` via `getent`; SRV-2 resolve o
  próprio FQDN para `10.12.1.12`, não `127.0.1.1`.
- `proc_6c7a69a68341` permanece `FAIL` histórico, classificado
  `post-workload-harness-failure / cleanup-permission-after-restore-success`.
  O backup atual passou 15/15 checksums, root/user compare 0/0, Git bundle 0 e
  deixou zero scratch residual. Evidence:
  `docs/operations/evidence/2026-09-06-proc-6c7a69a68341-reconciliation/`.
- Graphify não indexa mais os próprios outputs. O graph antigo continha 1.577
  nodes derivados; o rebuild removeu todos, removeu zero nodes reais e
  adicionou 107 nodes reais. O segundo rebuild retornou
  `No code-graph topology changes detected`.

## Seal runtime v11 — 2026-09-06

- Source package stable final: `444` artifacts; manifest
  `aa1883d1dfb95fda6978dc31d5499520d91b0c68d67d536bfe0914a8f86bd788`.
- Full apply sem resume: `20260906T233823+0000-1549801`, `17/17 PASS`.
- Verify-only independente: `20260906T234149+0000-1558144`, `17/17 PASS`.
- O package `d54b2a07…`/`220508`/`220854` permanece evidência histórica
  válida, superseded somente pela sincronização final dos ignores.
- O runtime funcional anterior `22bc6ba2…`/`20260906T211445`/`20260906T211836`
  permanece evidência histórica válida, superseded pelo package documental final.
- Backup preapply: `~/.backups/srv4-final-runtime-preapply-20260906T205141+0000`,
  cinco archives, seis checksums e restore inventory PASS.
- Source reviews convergiram em zero P0/P1/P2; runtime review independente
  retornou `VERDICT=GO`, zero findings.
- Graphify `0.9.23` usa `openai==2.24.0`, backend `atius-router-gpt`, patch de
  streaming em labeling e extraction e smoke API real com resposta JSON válida.
- Hermes respondeu `SRV4-HERMES-V11-OK`; MCPs descobriram `115/16/12` tools.
- O setup materializa Landscape, Fleet DB, XRDP leaf, Obsidian pull-only,
  Hermes/Graphify e agent-content a partir de profiles Vault específicos, sem
  copiar OAuth ou executar arquivos de secrets como shell.
- Generic-host rejeita todos os nove units SRV-1-only. O installer reseta apenas
  units realmente `failed`; `not-loaded` não é falha de instalação.
- Evidence: `docs/operations/evidence/2026-09-06-srv4-final-runtime-v11/`.
- Graphify stable final: `13.729` nodes, `21.421` edges, fresh/current.
  O segundo rebuild retornou `No code-graph topology changes detected`, os
  hashes ficaram idênticos e as queries do evidence, runbook, setup e offload
  passaram.
