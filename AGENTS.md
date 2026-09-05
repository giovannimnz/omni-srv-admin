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
