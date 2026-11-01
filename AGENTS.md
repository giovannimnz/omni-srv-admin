# GSD Agents

This file marks the project as a GSD-managed project.

Agents available in this project are defined in: `~/.hermes/agents/`

For more information about GSD agents, run `/gsd-help`.

## Project Identity

- **Repo name:** omni-srv-admin (formerly atius-srv)
- **Display name:** Omni Srv Admin
- **Domain:** atius.com.br (DNS preserved — production domain)
- **Host:** 10.11.1.11 primary private/DRG service path, `10.100.100.1` reserve fallback (Oracle Cloud ARM64, Ubuntu 22.04)

## SSH Reachability Fallback

- Falha no caminho privado direto de W11, WSL, S23 ou Horistic deve ser seguida imediatamente pela rota SSH pública nativa, sem dependencia de WireGuard.
- W11: `ssh muniz@10.100.100.8` -> `ssh -p 8122 muniz@ssh-giovanni-w11-pc.atius.com.br`.
- WSL: `ssh -p 8022 muniz@10.100.100.8` -> `ssh -p 8222 muniz@ssh-giovanni-wsl-pc.atius.com.br`.
- S23: `ssh -p 8022 termux@10.100.100.10` -> `ssh -p 8322 termux@ssh-giovanni-s23.atius.com.br`.
- S23 LAN/BE3: backend `192.168.1.10:8022`; NAT
  `GIOVANNI-S23-SSH` TCP externo `8322` -> `192.168.1.10:8022`.
  O endpoint WireGuard configurado no hub e `10.100.100.10:8022`; em
  2026-07-23 ainda estava sem handshake do handset.
- S20 LAN/BE3: reserva `192.168.1.9`, MAC `30:AB:6A:3C:96:D1`; o hub
  reserva `10.100.100.9/32`, tambem sem handshake do handset em 2026-07-23.
  Os slots `8422` (Termux) e `8522` (Ubuntu PRoot) sao apenas reservados:
  nao publicar nem tratar como fallback ate provar listener, usuario,
  fingerprint, NAT, relay, DNS e browser end to end.
- Correcao 2026-07-23: com backup nativo do BE3, as quatro regras Casa
  passaram a restringir `Remote Host` ao egress real do relay
  `137.131.190.161`. Probes externos no SRV-3 validaram W11 `8122` e WSL
  `8222`; no browser headless, W11/WSL chegaram a `connected`, enquanto S23
  chegou ao launcher/WebSocket e ficou `disconnected`. S23 `8322` ainda
  fechava antes do KEX e continua pendente. No RDP, o fluxo headless chegou
  ao formulario canonico autenticado; WebSocket/NLA/desktop nao foram
  executados porque a credencial Microsoft correta nao existe no Vault.
- Horistic: `ssh horistic@10.21.1.21` -> `ssh -p 22 horistic@ssh-horistic-srv.atius.com.br`.
- Preserve a evidencia de ambos os probes antes de declarar indisponibilidade. `ssh.atius.com.br/ssh-*` e interface de browser, nao hostname OpenSSH.

## CPU Guardrail

- Builds, rebuilds, compiles, heavy test suites, container builds, bundlers, broad indexers, and any CPU-heavy task must never exceed 20% of total host CPU on `atius-srv-1`, `atius-srv-2`, `atius-srv-3`, and `horistic-srv`.
- The canonical host-level source is `modules/srv1-ops/configs/resource-governor.env` with `RG_PROFILE_BUILDS_CPU_TOTAL_PCT=20` and `RG_PROFILE_BUILDS_CPU_QUOTA=20%`.
- Always route build commands through the local guard/wrapper when available. Do not run raw `docker build`, `podman build`, `npm run build`, `bun run build`, `pnpm build`, `go test ./...`, `cargo build`, or equivalent heavy commands outside the `builds` profile.
- If a wrapper is missing, create temporary containment with `omni srv1-ops resources run builds -- ...`, cgroup/systemd-run quota, `nice`, and `ionice` before running the task. If containment cannot be verified, stop before starting the build.

## K3s Resource Unit

- Managed k3s workloads use `1 pod = 500m CPU = 0.5 host CPU/vCPU` as the resource-management unit.
- For normal one-container pods, set both `resources.requests.cpu` and `resources.limits.cpu` to `500m`.
- If a pod has multiple containers, split the pod budget explicitly so the total pod CPU stays at or below `500m`; Kubernetes accounts CPU per container, so this must be checked in the manifest.
- Two replicas/pods at this standard equal `1000m`, i.e. one full CPU core of the host.

## XRDP ABNT2 Fleet

- Toda auditoria, diagnostico, reconcile, recovery, packaging ou closeout de
  teclado ABNT2 em XRDP deve usar `$xrdp-abnt2-fleet`.
- Fonte versionada: `modules/agent-content-packs/packs/codex-skills/items/xrdp-abnt2-fleet/SKILL.md`.
- A skill resolve os hosts pelo inventory, preserva sessoes/dirty worktrees,
  proibe restart XRDP por default e exige UAT fisica em nova sessao Microsoft
  RDP antes de `complete`.
- Skills/scripts Hermes antigos e `modules/srv1-ops/legacy-scripts/fix-abnt2.sh`
  sao evidencia historica, nao entrypoints operacionais.

## Canonical Fleet Operations & Landscape Control-Plane Directive

- **Regra Mandatória para Múltiplos Servidores / Frota:** SEMPRE que qualquer operação, atualização, diagnóstico, instalação de pacotes APT, sincronização de arquivos, verificação ou execução envolver mais de um servidor (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`), NUNCA execute loops manuais seriais de SSH se a operação puder ser executada via **Landscape Control-Plane**.
- **Comando Canônico de Execução Simultânea:**
  ```bash
  omni landscape run <script-id> --hosts all --wait --yes
  ```
  - Executa simultaneamente em todos os 5 nós da frota via Landscape Server self-hosted (`atius-srv-3`).
  - Coleta e agrega status (`undelivered`, `in-progress`, `delivered`, `succeeded`), stdout, stderr e exit codes em tempo real.
  - Para subconjunto de hosts, use `--hosts atius-srv-1,atius-srv-2...` ou `--query <custom-query>`.
- **Scripts Versionados e Manifesto:**
  - Diretório: `/home/ubuntu/GitHub/omni-srv-admin/modules/landscape-control-plane/scripts/`
  - Manifesto: `/home/ubuntu/GitHub/omni-srv-admin/modules/landscape-control-plane/scripts/manifest.json`
  - Para novo script: salve no diretório, adicione ao `manifest.json`, sincronize com `omni landscape scripts push <script-id> --yes` e dispare com `omni landscape run <script-id> --hosts all --wait --yes`.
- **Comandos de Suporte e Inventário:**
  - Listar computadores registrados: `omni landscape computers`
  - Status da integração: `omni landscape status`
  - Listar scripts cadastrados: `omni landscape scripts list`
  - Consultar atividades: `omni landscape activities`
- **Gatilhos de Acionamento Automático:**
  - Palavras-chave: `em todos os servidores`, `nos servidores 1 a 4`, `na frota`, `fleet-wide`, `multi-host`, `multi-servidor`, `todos os hosts`, `atualizar servidores`, `instalar em todos`, `status da frota`, `diagnóstico em massa`.
  - Skill canônica associada: `atius-fleet-landscape-ops` (`~/.gemini/config/skills/atius-fleet-landscape-ops/SKILL.md`).
- **Conectividade OCI DRG:** Todo tráfego Landscape trafega pela rota direta privada OCI DRG (`10.13.1.13 landscape.atius.com.br`) com latência sub-milissegundo (~0.6 ms) sem custos de egress.
- **Arquitetura & Hospedagem:**
  - **Servidor Self-Hosted:** Host `atius-srv-3` (`10.13.1.13`), container LXC `landscape` (`10.65.172.253`).
  - **Ingress Edge / Reverse Proxy:** Host `atius-srv-1` (`10.11.1.11`), Apache TLS com certificados Let's Encrypt em paridade dual-domain: `https://landscape.atius.com.br/` e `https://landscape.atius.io/`.
  - **Client Endpoint:** `http://landscape.atius.com.br/ping` e `http://landscape.atius.io/ping` (HTTP puro obrigatório para comunicação do `landscape-client`; não redirecionar para HTTPS).
- **Interfaces & Rotas Web:**
  - **Classic UI (Padrão):** `/login` (reescrita canônica transparente no Apache do `atius-srv-1` com retorno aos segredos em `/account/standalone/secrets`).
  - **Modern Dashboard:** `/new_dashboard/overview` — interface SPA moderna (React/Vite) servida estaticamente pelo container.
  - **Skin & Tema Dark:** Template clássico customizado em `/opt/canonical/landscape/canonical/landscape/ui/skin/hokan/page.pt` (container LXC) com `<style id="atius-classic-dark">`, cobrindo overrides para formulários, cards e modal `.cookie-policy` (evitando texto branco em fundo branco).
- **Documentação de Governança:** `docs/fleet/landscape-omni-governance.md`, `docs/fleet/landscape-omni-cli.md` e `docs/operations/LANDSCAPE-DRG-AND-FLEET-ROLLOUT.md`.

## Segredos ATIUS e MCP

- Fonte autoritativa de segredos: HashiCorp Vault, nao `.env`, `.zshrc`, historico de shell, chat, Obsidian, GBrain ou arquivos do repo.
- Vault endpoint: `https://10.13.1.13:8202` em `atius-srv-3`.
- Helper Windows: `C:\Users\muniz\.local\bin\atius-vault-env.cmd`.
- Helper Linux onde instalado: `~/.local/bin/atius-vault-env <profile>`.
- Backend no host Vault `atius-srv-3`: `sudo /usr/local/sbin/atius-vault-export-env <profile>`.
- Arquivos de runtime como `.env`, `.zshrc`, `environment.d` e variaveis de ambiente do SO/usuario sao cache de hidratacao; o Vault continua sendo a fonte de verdade.
- Acesso Cloudflare: profile Vault `cloudflare`, path `kv/atius/cloudflare/api`, registro Landscape `atius-cloudflare-api`.
- O profile Cloudflare exporta `CF_ACCOUNT_ID`, `CF_ACCOUNT_NAME`, `CF_AUTH_EMAIL`, `CF_GLOBAL_API_KEY`, `CF_ZONE_ID_ATIUS` e `CF_ZONE_ID_ZENTRIUS`.
- Para REST direto da Cloudflare, carregar `cloudflare` do Vault e autenticar com `X-Auth-Email` + `X-Auth-Key`; nunca colar ou logar a chave.
- No Windows, usar `codex-cloud-ops` para trabalho Cloudflare via MCP; ele carrega o profile Vault no processo filho do Codex e injeta `cloudflare-api` sem persistir o segredo no ambiente do usuario.
- Helpers Linux que usam SSH para o host Vault precisam ser stdin-safe (`ssh -n` ou equivalente) para automacoes poderem chama-los dentro de scripts.
- `horistic-srv` usa uma chave SSH restrita para `ubuntu@atius-srv-3`, forcada para `/home/ubuntu/.local/bin/atius-vault-export-ssh`, apenas para export do Vault.
- Se uma credencial ainda existir so em documentacao, `.env` ou `.zshrc`, usar isso apenas como evidencia de migracao; mover o segredo operacional para o HashiCorp Vault antes de tratar como estavel.
- Nunca gravar valores de segredos em AGENTS.md, Markdown, logs, commits, Obsidian, GBrain ou chat. Documentar apenas paths do Vault, profiles, nomes de variaveis e evidencias de validacao.
- Endpoints MCP canonicos do Codex:
  - `gbrain_http`: `https://mcp.atius.com.br/gbrain`
  - `obsidian_http`: `https://mcp.atius.com.br/obsidian`
  - `oci_admin_http`: `https://mcp.atius.com.br/oci-admin`
- Os tres MCPs usam `Authorization: Bearer $ATIUS_MCP_TOKEN`; carregar `ATIUS_MCP_TOKEN` do profile Vault `atius-mcp` (`kv/atius/atius-mcp/api`).
- O nome client-side do OCI Admin e `oci_admin_http`; a identidade MCP continua `serverInfo.name=oci-admin`. O alias client-side `oci_admin` e aposentado.
- O backend OCI Admin usa OCI/DRG `10.13.1.13:8090`; `10.100.100.3` e somente reserve/fallback.
- O MCP do Obsidian e sessionful: depois de `initialize`, preservar `Mcp-Session-Id`, enviar `notifications/initialized`, e so entao chamar `tools/list` ou tools.
- Material de browser-login/access-key fica no Vault path `kv/atius/browser-login/access-keys` e no registro Landscape `atius-browser-login-access-keys`. O Vault armazena e entrega o material; o navegador so reconhece a chave quando o perfil do browser, OS/hardware authenticator, provider/extensao, certificado cliente ou autenticador virtual CDP/Playwright estiver provisionado para o relying party.

<!-- codex-policy:parallel-headless:start -->
## Paralelismo e automacao de browser

- Autorizacao permanente: Codex pode usar multiplos subagentes quando houver trabalho paralelo util, sem pedir confirmacao por tarefa.
- Pesquisa e validacao podem ocorrer em paralelo, mas mutacoes devem ser coordenadas com apenas um writer por arquivo ou escopo sobreposto.
- Toda automacao de browser deve executar em modo headless, incluindo Chrome, Chromium, Chrome DevTools, Playwright, Selenium, Puppeteer ou ferramenta equivalente.
- Nao abrir browser visivel nem usar sessoes XRDP/noVNC para automacao, salvo override especifico do usuario para a tarefa.
- Preservar evidencia headless adequada, como output de comandos, traces, screenshots, snapshots ou artefatos de teste.

<!-- codex-policy:parallel-headless:end -->


## Diretriz Canônica Permanente: Sistema Universal de Busca Inteligente Multi-Tier para Nomes, Strings e Documentos

- **Mandato Universal e Permanente:** Em todo e qualquer projeto, serviço, API, CLI, banco de dados ou interface frontend do ecossistema ATIUS onde houver cadastro, consulta ou filtro de nomes de pessoas, strings de texto livre ou documentos (CPF, RG, RENACH, CNPJ), é OBRIGATÓRIA a aplicação deste motor multi-tier. É expressamente proibido usar `LIKE %termo%` ingênuo sensível a acentos ou comparações estritas `==`.
- **Accent-Folding Simétrico Bidirecional:** A busca DEVE normalizar texto com decomposição Unicode NFD e remoção de marcas diacríticas `[\u0300-\u036f]`. Digitar `lívia` DEVE encontrar `Livia Nascimento` e `Lívia Nascimento`; digitar `livia` DEVE encontrar `Lívia Nascimento` e `Livia Nascimento`.
- **Hierarquia Estrita de Priorização (9 Tiers):**
  1. **Tier 1 (Score 1.00):** Correspondência exata literal (mesmo case e acentos).
  2. **Tier 2 (Score 0.99):** Correspondência exata case-insensitive.
  3. **Tier 3 (Score 0.98):** Correspondência exata normalizada (desconsiderando acentos).
  4. **Tier 4 (Score 0.97):** Multi-Token Match (todas as palavras da consulta constam no nome cadastrado).
  5. **Tier 5 (Score 0.96):** Substring literal contínua.
  6. **Tier 6 (Score 0.94):** Substring normalizada contínua.
  7. **Tier 7 (Score 0.93):** Token individual exato (qualquer palavra do nome idêntica ao termo).
  8. **Tier 8 (Score 0.90):** Prefixo de token (`liv` prefixo de `Livia`).
  9. **Tier 9 (Score 0.70 a 0.88):** Similaridade Fuzzy / Proporção de Letras (`SequenceMatcher` / Levenshtein) para tolerância a pequenos erros de digitação (typos).
- **Busca Numérica por Documentos:** Dígitos limpos (>= 3 caracteres) consultam CPF, RG, RENACH e CNPJ com scores `0.99` (exato) e `0.95` (parcial).
- **Frontend / UX (/impeccable):** Filtro local instantâneo com micro-debounce (30ms a 50ms), fallback debounced (300ms) para API remota, empty state legível com termo buscado e botão de 1 clique para limpar busca, badge dinâmico de contagem de resultados.
- **Consultas em Banco de Dados:** SQL deve buscar tanto termos originais quanto desacentuados (`name ILIKE :term OR unaccent(name) ILIKE :term_unaccent`) com ranqueamento `ORDER BY CASE ...`.
- **Implementação de Referência:** Módulos `app.core.search` (Python) e `app/static/js/app.js` (JavaScript) no repositório `XDriver-App`.
- **Registro Canônico de Arquitetura:** Documentado no GBrain (fato #613) e no Obsidian (`AiSecondBrain/Operations/Diretriz-Canonica-Busca-Inteligente-Nomes-Strings.md`).


## Teamwork Defaults (Permanente)

- Ao invocar `/teamwork`: NÃO fazer entrevista de calibração de rotina. Usar [skip-interview] / defaults abaixo.
- Quando for necessário relatório/documento: perguntar ao usuário destino via `ask_question` com timeout de 2 minutos. Sem resposta em 2 min, padrão = salvar em `.planning/` E `docs/` do repo (+ resumo inline).
- Restrições padrão: sem SSH/Landscape na frota, sem imprimir segredos, somente-leitura exceto arquivos de relatório. Verificação padrão: rubrica por tópico com evidências rastreáveis. Idioma: PT-BR, caveman full.
