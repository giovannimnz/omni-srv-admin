---
phase: 8
name: rebrand-fork-sync-submodule
created: 2026-06-04
method: inline (CLI Agent — no Claude Code subagents; applied per gsd-discuss-phase P7 + P14 fallback)
generator: gsd-discuss-phase (adapted to Hermes CLI Agent)
status: locked
---

# Phase 8 — Rebrand + fork-sync como submodule

## Objective

Transformar o repositório local `omni-srv-admin` (era `atius-srv`) em uma
administração de servidor **vendor-neutral / multi-tenant** com o `fork-sync`
embutido como submodule nativo em `modules/fork-sync/`. O repositório
`giovannimnz/atius-srv` no GitHub é renomeado para `giovannimnz/omni-srv-admin`,
o rebrand textual (de "Atius Server" para "Omni Srv Admin") é aplicado em
superfície, e o fork-sync vira submodule vivo (linkado em
`https://github.com/giovannimnz/fork-sync.git`, branch `main`). O repo
`giovannimnz/fork-sync` recebe uma tag final `v1.2.1-omni-archived` e é
descontinuado (conteúdo migrado, GitHub archive).

## Locked Decisions

### D-01: Rebrand textual — escopo abrangente

**Decisão:** Atualizar todas as referências a "Atius Server" / `atius-srv` em:
- `README.md` (201 linhas — escopo total)
- `AGENTS.md`
- `.planning/PROJECT.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `STATE.md`
- `docs/ARCHITECTURE.md`, `CONFIGURATION.md`, `DEVELOPMENT.md`,
  `GETTING-STARTED.md`, `TESTING.md`, `CLOUDFLARE.md`,
  `SERVER-AUDIT-20260506.md`
- `domain-infrastructure/CLAUDE.md`
- `RECOVERY_LOG.md`
- `vscode-profile/.github/memory-bank/{progress,tasks/_index,activeContext}.md`
  + `tasks/TASK010-migracao-infra-pm2-postgres-atius.md`
- `vscode-profile/.github/mcp-config/linux/mcp.json`
- `vscode-profile/.github/vscode-settings/settings.json`
- `.gitignore` (paths `atius-*`)

**NÃO atualizar:** comentários em arquivos `.sh` (bin/setup.sh — só atualiza
header), `.planning/phases/*/PLAN.md` históricos (preservados como histórico
do projeto), `.planning/research/*.md`, e o `git log` (imutável).

**Rationale:** Decisão em cascata P5 (timeout — best-judgment default):
opção 1 do `clarify` (mais abrangente) foi escolhida por ser proporcional,
reversível (`git revert` em caso de erro) e consistente com o nome do
repositório. O custo de rebranding parcial (com "Atius" residual) é maior
do que o trabalho de fazer tudo de uma vez.

**Reversibilidade:** `git revert` do commit de rebrand. Estimativa: **75
matches rastreados** em 19 arquivos (medido via
`git grep -c "Atius Server\|atius-srv" -- ':!*.com.br'`), ou ~95 com
untracked (medido via `grep -rcI`). Substituição: `Atius Server` → `Omni
Srv Admin`, `atius-srv` → `omni-srv-admin`, `ATIUS-SRV-1` → `OMNI-SRV-1`
(em paths/scripts apenas onde fizer sentido), `atius.com.br` (DNS) é
**preservado** — é domínio de produção, não é rebrand.

### D-02: Repo GitHub renomeado

**Decisão:** `gh repo rename giovannimnz/atius-srv omni-srv-admin --yes` (CLI
confirmou escolha). Atualizar `git remote set-url origin
https://github.com/giovannimnz/omni-srv-admin.git`. GitHub provê redirect
automático de `atius-srv` → `omni-srv-admin` por 90+ dias, mas o remote
local é atualizado imediatamente.

**Rationale:** GitHub redirects funcionam mas poluem o ecossistema com URLs
que apontam pra um nome morto. Atualizar o remote local é trivial e evita
confusão em logs/scripts futuros.

**Pré-condição:** gh CLI autenticado (verificado: `giovannimnz` logado).

### D-03: fork-sync vira submodule em `modules/fork-sync/`

**Decisão:** Path `modules/fork-sync/`, branch `main`, URL
`https://github.com/giovannimnz/fork-sync.git` (CLI confirmou). Modo:
`git submodule add` normal — link vivo, atualizável, com workflow padrão de
`git submodule update --init --recursive`.

**Rationale:** Submodule é o padrão da indústria pra componentes versionados
de forma independente. O fork-sync evolui em ritmo próprio (sync.yaml,
projetos, bin/cli) e o omni-srv-admin só precisa consumi-lo.

**Ajustes pós-add:**
- `.gitignore` do omni-srv-admin ganha `modules/fork-sync/logs/` e
  `modules/fork-sync/.translate-cache/` (voláteis)
- `modules/fork-sync/cli/fork_sync.egg-info/` removido do tracking (artefato
  de build)
- `modules/fork-sync/.gitignore` já existe (verificado) — verificar que
  `scripts/` está gitignored (README menciona isso)

### D-04: Descontinuação do repo `giovannimnz/fork-sync`

**Decisão:** Após o submodule ser adicionado com sucesso, o repo
`giovannimnz/fork-sync` no GitHub recebe:
1. Tag final `v1.2.1-omni-archived` apontando pro commit HEAD atual
2. Release notes apontando pro submodule em
   `giovannimnz/omni-srv-admin/modules/fork-sync/`
3. `gh repo archive giovannimnz/fork-sync --yes` (read-only no GitHub)

**Rationale:** CLI confirmou "Mata o repo giovannimnz/fork-sync no GitHub
depois de migrar conteúdo + tag final v1.2.x". Archive (read-only) preserva
histórico, issues, PRs, releases — melhor que `delete` que perde tudo.

**Conteúdo a preservar antes de archivar:** o estado atual do fork-sync
(working tree dirty: `manuals/hermes-os.md` + `projects/hermes-os/sync.yaml`
modificados) deve ser commitado no fork-sync **antes** do submodule add, pra
que o `v1.2.1-omni-archived` capture o estado completo.

### D-05: `domain-infrastructure/` permanece como diretório mergeado (não submodule)

**Decisão:** Não tocar em `domain-infrastructure/` — é diretório mergeado
(commit `2b244ac`) com 3 subpastas vazias (`configs/`, `docker/`,
`scripts/` com `.gitkeep`) e `CLAUDE.md`. Apenas rebranding textual em
`CLAUDE.md`.

**Rationale:** O usuário falou "implemente o fork-sync como submodule" —
específico ao fork-sync. `domain-infrastructure` é plano de phases 3-7
(FreeIPA/Keycloak/Samba). Se virar submodule, vira dependência externa
desnecessária.

### D-06: Push policy — o que pode ser executado automaticamente

**Decisão (refinamento da memory rule "WRITE-REMOTO"):**

| Operação | Auth | Rationale |
|---|---|---|
| `git commit` local (qualquer branch) | Auto | Local-only, user revisa diff |
| `gh repo rename giovannimnz/atius-srv omni-srv-admin` | Soft-gate (clarify já confirmou) | Renomeação destrutiva, mas já aprovada |
| `git push origin main` (omni-srv-admin) | Auto após rebrand commit + cleanup do working tree | Fork do user, rollback trivial |
| `gh repo archive giovannimnz/fork-sync` | Hard-gate — pedir confirmação explícita antes | Destrutiva, irreversível sem gh API admin |
| `git tag -a v1.2.1-omni-archived` no fork-sync | Auto (parte do commit pre-archive) | Tag local, sem side-effect upstream |
| `git push fork-sync v1.2.1-omni-archived` | Hard-gate — pedir confirmação explícita | Push remoto, requer owner do repo |
| `gh release create v1.2.1-omni-archived` no fork-sync | Hard-gate — pedir confirmação explícita | Cria release visível publicamente |
| `git push --force` qualquer | **PROIBIDO** | Sempre merge, nunca force |
| `git push` do omni-srv-admin pro upstream QuantumNous | **N/A** — omni-srv-admin é do user | Não é fork |

**Push policy registrado em PLAN.md `§ Push policy`.**

### D-07: Vault Obsidian — onde registrar

**Decisão:** Criar/atualizar notas no vault
`~/GitHub/obsidian-vault/ideaverse/`:

1. **NOVO:** `20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin/omni-srv-admin.md`
   — nota canônica do projeto (escopo, módulos, links)
2. **NOVO:** `20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin/fork-sync-submodule.md`
   — nota do submodule (path, versionamento, comandos)
3. **MOVER:** `20-PROJETOS/21-PROJETOS-ATIVOS/atius/` → arquivar
   (`22-PROJETOS-ARQUIVADOS/atius-2026-06-04/`) — referencia histórica
4. **ATUALIZAR:** `21.03-Decisoes-Arquitetura/2026-06-04-omni-srv-rebrand.md`
   — decisão arquitetural registrada
5. **NOVO:** `60-LOGS/2026-06-04-omni-srv-admin-rebrand-phase8.md` — log
   de execução da phase
6. **ATUALIZAR:** `91-Diarios/2026-06-04.md` — daily note com entrada da phase

**Rationale:** Memory rule "REGRA DE OURO: consultar e atualizar Obsidian
sempre". Sem nota no vault, a decisão morre no commit. Daily note + decisão
+ log + nota do projeto é o padrão de coverage.

## Gray Areas (não decididas — defaults aplicados)

### G-01: Ordem de execução (rebrand antes ou depois do submodule?)
**Default (P5):** Rebrand **depois** do submodule add. Razão: o rebrand
afeta ~95 ocorrências e o working tree já está dirty. Adicionar submodule
depois garante que o commit do rebrand inclui o `.gitmodules` + path
canonical.

### G-02: Tag versionada do omni-srv-admin
**Default (P5):** Sem tag no omni-srv-admin nesta phase. Razão: o repo não
se versiona por tag (não tem release pipeline). O commit de rebrand
carrega SHA próprio.

### G-03: Branch strategy pós-rebrand
**Default (P5):** Continuar em `main` direto. Não criar `feat/rebrand`
porque o rebrand é contínuo (um commit), não uma feature isolada.

### G-04: Manuais PT-BR do fork-sync (`manuals/hermes-os.md` modified)
**Default (P5):** Commitar no fork-sync **antes** do submodule add (parte
do D-04). Razão: o dirty working tree do fork-sync tem que virar commit
limpo antes de virar submodule.

### G-05: Script `setup.sh` — atualizar referência ao repo?
**Default (P5):** Sim. `setup.sh` linha 4-5 tem referências ao nome
`atius-srv`. Atualizar pra `omni-srv-admin`. Trivial, sem impacto funcional.

## Out of Scope

- Implementar phases 3-7 do roadmap (FreeIPA, Keycloak, Samba) — essas são
  phases futuras independentes
- Refatorar `.planning/` (STATE.md, REQUIREMENTS.md são gerados via
  `gsd-sdk query state.record-session`) — apenas rebranding textual
- Atualizar vault para outras línguas — vault é PT-BR canônico
- Mover/deixar de usar `domain-infrastructure/` — D-05

## Open Questions (para `gsd-plan-phase` resolver via research)

- **O-01:** O GitHub `gh repo rename` afeta redirects? (Sim, 90+ dias
  automáticos, mas vale documentar em DEVELOPMENT.md)
- **O-02:** `git submodule add` com URL HTTPS + gh credential helper —
  funciona no shell atual? (Verificar com `git config --get credential.helper`)
- **O-03:** O egg-info `cli/fork_sync.egg-info/` é regenerado pelo
  `setup.py`? Se sim, removê-lo do index git no fork-sync antes de virar
  submodule.

## Reference

- Memory: `WRITE-REMOTO refined 2026-06-04` (hard-gate SÓ QuantumNous,
  fork push livre APÓS audit) — refine pra D-06
- Memory: `REGRA DE OURO: Obsidian sempre`
- Memory: `Sync: rsync SEM --delete` — não se aplica (não é sync de
  filesystem, é git submodule)
- Vault: `60-LOGS/2026-06-04-fork-sync-cli-rebuild.md` (contexto da
  origem do fork-sync)
- Vault: `21.03-Decisoes-Arquitetura/2026-06-04-fork-sync-cli-python.md`
  (decisão técnica do fork-sync que será preservada)
- Repo: `giovannimnz/omni-srv-admin` (renamed from atius-srv) on main,
  SHA `8a281a6` + 2 ahead
- Repo: `giovannimnz/fork-sync` on main, SHA `5c46125`, working tree dirty
