# VERSIONS — fork-sync

## 1.2.0 (2026-06-04)

### Adicionado
- **Release notes PT-BR** (`core/release_notes.py`) — `release generate|list|preview`
  - Busca release do upstream via `gh api` (body, assets, autor)
  - Parseia estrutura: `##` e `###` headings (Highlights, Bug Fixes, Under the Hood, etc)
  - Sub-headings (h3) viram prefixo do bullet (ex: `**Confiabilidade da sessão ACP** — ...`)
  - Traduz prosa pra PT-BR via `deep-translator` (GoogleTranslator) com cache em `.translate-cache/`
  - Adiciona seções canônicas PT-BR: Destaques, Correções de Bugs, Nos Bastidores, O Que Mudou, Contribuidores, Binários e Artefatos
  - Footer com links upstream/fork/tag/data/atribuição fork-sync
  - Suporte a `--changed-files` (arquivos divergentes do fork)
  - `--save-local` salva em `manuals/<projeto>/releases/<tag>.md`
- `bin/create-release.sh` refatorado: delega ao `fork-sync release generate --json` (era inline)
- Doc `docs/RELEASE-NOTES.md` (módulo, comandos, configuração, limitações)

### Mudanças (breaking)
- `bin/create-release.sh` não copia mais body upstream cru em inglês — usa o novo gerador PT-BR
  com fallback se `fork-sync` não estiver instalado

### Mantido (backward compat)
- v1.1.0 — auto-discovery, manuais, logrotate, PM2
- v1.0.0 — CLI base, scripts bash, 8 projetos

---

## 1.1.0 (2026-06-04)

### Adicionado
- **Auto-discovery** (`core/discovery.py`) — `discover check|heal` localiza forks/upstreams sumidos via `gh search`
  - Heurísticas: match exato (0.9), mesmo owner (0.85), próprio fork giovannimnz (0.7-0.95), penaliza archived
  - Auto-heal procura em `~/GitHub/forks/`, `~/docker/Atius/`, `~/GitHub/`
- **Manuais de atualização** (`core/manuals.py`) — `manuals generate|list|show|update|record-sync`
  - Versão por projeto em `manuals/<projeto>.md` com frontmatter YAML
  - Auto-gera a partir do `sync.yaml`
  - `record-sync` adiciona entrada no histórico
- **Rotação de logs** (`core/logrotate.py`) — gzip + retenção configurável
  - `FORK_SYNC_LOG_RETENTION_DAYS` (default 30)
  - `FORK_SYNC_KEEP_PER_PROJECT` (default 5)
  - Idempotente, seguro (nunca remove log do dia)
- **Serviço PM2** — 4 processos com `cron_restart`:
  - `fork-sync-scheduler` (REPL long-lived)
  - `fork-sync-doctor` (cron `0 7 * * *`)
  - `fork-sync-logrotate` (cron `0 3 * * *`)
  - `fork-sync-daily` (cron `0 8 * * *`)
  - `cli/scripts/pm2-setup.sh` para install/remove/status/logs
- **Doctor** — diagnóstico global de paths, deps (git, gh, jq, bash), gh auth, PM2, disco de logs
- 8 manuais gerados automaticamente (um por projeto)
- Doc `docs/PM2-SERVICE.md` (serviço PM2 + cron)

### Mantido (backward compat)
- v1.0.0 — CLI Python base, scripts bash legados, 8 projetos

---

## 1.0.0 (2026-06-04)

### Adicionado
- CLI Python unificado (`fork-sync`) com Click + prompt_toolkit
- Suporte a 8 forks configurados (aionui, atius-router, atius-router-docs, hermes-agent, hermes-os, gsd-2, bruno, get-shit-done)
- Saída JSON estruturada (`--json` global) para integração com agentes
- REPL interativo (`fork-sync repl`) com tab-completion, inspirado em CLI-Anything (HKUDS)
- Comandos: `projects {list,show,add,remove}`, `sync`, `detect`, `deploy`, `logs`, `repl`, `version`
- Documentação completa em PT-BR (README, SECRETS.md, CONTRIBUTING.md)
- Templates prontos: `basic.yaml`, `docker.yaml`, `submodule.yaml`, `deploy.yaml`
- Suporte declarativo a submodules via `.gitmodules` por projeto
- Política explícita de secrets (SECRETS.md) — zero credenciais no repo

### Mantido (backward compat)
- Scripts bash legados (`bin/sync.sh`, `bin/deploy.sh`, `bin/detect-release.sh`)
- Estrutura `projects/<name>/sync.yaml` da v1
- Cron entries e Telegram notifications

### Inspirado em
- [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) — framework CLI agent-native
- [Click](https://palletsprojects.com/p/click/) — Python CLI framework
- [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/) — REPL

---

## 0.x (legado)

- `bin/sync.sh` original — motor bash com sync diário + Telegram + cron
- Skill `fork-sync-engine` (Hermes internal) documenta o setup v1
