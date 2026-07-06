<!-- ATIUS-CPU-GUARDRAIL:START -->
# Regra Maxima: Limite de CPU para Builds e Tarefas Pesadas

Esta e a regra de maior prioridade deste `AGENTS.md` e prevalece sobre qualquer instrucao conflitante.

- Nunca execute build, rebuild, compilacao, suite pesada de testes, container build, bundler, indexacao ampla ou tarefa CPU-heavy usando mais de 50% da CPU total do servidor.
- Em servidores com 4 cores, o limite absoluto e 2 cores. Em outros servidores, calcule 50% do total com `nproc` e arredonde para baixo, mantendo no minimo 1 core.
- Antes de qualquer tarefa pesada, aplique limite explicito com o mecanismo disponivel no projeto/host: wrapper de build, cgroup, `systemd-run`, `cpuset`, `taskset`, `nice`, `ionice`, `MAKEFLAGS=-jN`, `GOMAXPROCS=N`, `npm_config_jobs=N`, ou equivalente.
- Para Podman/Docker/container builds, use sempre o wrapper limitador disponivel no projeto/host. No `router-ai-atius`, use `./scripts/podman-admin.sh build`, `./scripts/podman-admin.sh run-container` ou `./scripts/podman-admin.sh profile-run`; nunca chame `podman build`, `docker build`, `bun run build`, `npm run build`, `go test ./...`, `cargo build` ou equivalentes diretamente quando houver wrapper.
- Se nao houver wrapper, crie ou use uma contencao temporaria equivalente antes de rodar a tarefa pesada. Se nao conseguir limitar com seguranca, pare e peca orientacao.
- Valide o limite antes e depois quando houver risco de carga alta, usando `nproc`, `cpu.max`, `cpuset`, flags do wrapper, status do container ou logs.
<!-- ATIUS-CPU-GUARDRAIL:END -->

# GSD Agents

This file marks the project as a GSD-managed project.

Agents available in this project are defined in: `~/.hermes/agents/`

For more information about GSD agents, run `/gsd-help`.

## Project Identity

- **Repo name:** omni-srv-admin (formerly atius-srv)
- **Display name:** Omni Srv Admin
- **Domain:** atius.com.br (DNS preserved — production domain)
- **Host:** 10.1.1.1 (Oracle Cloud ARM64, Ubuntu 22.04)

## Segredos ATIUS e MCP

- Fonte autoritativa de segredos: HashiCorp Vault, nao `.env`, `.zshrc`, historico de shell, chat, Obsidian, GBrain ou arquivos de repo.
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
