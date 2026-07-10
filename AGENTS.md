# GSD Agents

This file marks the project as a GSD-managed project.

Agents available in this project are defined in: `~/.hermes/agents/`

For more information about GSD agents, run `/gsd-help`.

## Project Identity

- **Repo name:** omni-srv-admin (formerly atius-srv)
- **Display name:** Omni Srv Admin
- **Domain:** atius.com.br (DNS preserved — production domain)
- **Host:** 10.1.1.1 (Oracle Cloud ARM64, Ubuntu 22.04)

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

## Segredos ATIUS e MCP

- Fonte autoritativa de segredos: HashiCorp Vault, nao `.env`, `.zshrc`, historico de shell, chat, Obsidian, GBrain ou arquivos do repo.
- Vault endpoint: `https://10.1.1.3:8202` em `atius-srv-3`.
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
- Os dois MCPs usam `Authorization: Bearer $ATIUS_MCP_TOKEN`; carregar `ATIUS_MCP_TOKEN` do profile Vault `atius-mcp` (`kv/atius/atius-mcp/api`).
- O MCP do Obsidian e sessionful: depois de `initialize`, preservar `Mcp-Session-Id`, enviar `notifications/initialized`, e so entao chamar `tools/list` ou tools.
- Material de browser-login/access-key fica no Vault path `kv/atius/browser-login/access-keys` e no registro Landscape `atius-browser-login-access-keys`. O Vault armazena e entrega o material; o navegador so reconhece a chave quando o perfil do browser, OS/hardware authenticator, provider/extensao, certificado cliente ou autenticador virtual CDP/Playwright estiver provisionado para o relying party.
