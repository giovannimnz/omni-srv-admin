---
project: atius-router-docs
version: 2
created: 2026-06-04
last_updated: 2026-06-07
generator: fork-sync manuals generate
---

# Manual de Atualização — atius-router-docs

> Documento vivo. Cada sync/deploy/incidente relevante deve atualizar este manual.
> Versionado no git junto com `sync.yaml`. CLI regenera com `fork-sync manuals regen atius-router-docs`.

## 1. Visão Geral

- **Projeto:** `atius-router-docs`
- **Display name:** `Atius Router Docs`
- **Estratégia de merge:** `theirs`
- **Deploy:** systemd user (não container)
- **Runtime:** `atius-router-docs.service` na porta 3003

### Phase 09 — Mudanças Estruturais

A partir da Phase 09 (docs-convergence-main-repo), o source canônico da docs
mudou de `/home/ubuntu/docker/Atius/atius-router-docs` (standalone checkout)
para o submodule `docs/atius-router-docs/` dentro de `router-ai-atius`.

Ver ADR em `router-ai-atius/21.03-Decisoes-Arquitetura/2026-06-07-docs-convergence-submodule.md`.

## 2. Upstreams

| # | Nome | URL | Role |
|---|------|-----|------|
| 1 | `Atius Router Docs` | https://github.com/giovannimnz/new-api-docs-v1 | primary (submodule) |

## 3. Estratégia de Sync — Passo a Passo

1. **Estratégia:** `theirs`
2. Conflitos são resolvidos a favor do upstream (rebrand fica em `protected_paths`)
3. O sync opera dentro do submodule `router-ai-atius/docs/atius-router-docs/`
4. Após sync/bump, o submodule reference deve ser commitado em `router-ai-atius`

## 4. Paths Protegidos (rebrand)

Estes paths são preservados em conflito (nunca sobrescritos pelo upstream):

- `public/assets/atius-logo.svg`
- `public/assets/newapi.svg`
- `src/lib/layout.shared.tsx`
- `src/app/[lang]/layout.tsx`
- `src/app/[lang]/(home)/page.tsx`
- `src/app/[lang]/(home)/page.client.tsx`
- `src/lib/metadata.ts`
- `src/components/search.tsx`
- `src/app/layout.tsx`
- `next.config.mjs`
- `tsconfig.json`
- `Dockerfile`
- `public/favicon.ico`
- `.github/workflows/scheduled-build.yml`
- `.github/workflows/translate.yml`

## 5. Como Adaptar o Fork (Rebrand)

Documentar aqui as customizações que diferenciam este fork do upstream:

- **Identidade visual:** logos, cores, naming
- **Funcionalidades extras:** patches próprios
- **Configurações locais:** endpoints, paths
- **i18n:** traduções adicionadas

Para cada item, referenciar o path em `protected_paths` e dar contexto de POR QUE
essa customização existe (issue, ticket, decisão arquitetural).

Exemplo:
- `web/default/public/logo.png` — Logo do Atius, não usar o do new-api upstream
- `i18n/locales/pt-BR.yaml` — Tradução PT-BR adicionada manualmente

Se adicionar rebrand:
1. Adicionar path em `protected_paths` no `sync.yaml`
2. Documentar aqui com justificativa
3. Incrementar `version:` no frontmatter deste manual

## 6. Como Reagir a Breaking Changes do Upstream

1. **Verificar release notes do upstream:**
   ```bash
   gh release list --repo <UPSTREAM_URL>
   ```
2. **Comparar últimos N commits:**
   ```bash
   git fetch upstream
   git log --oneline upstream/<branch> -20
   ```
3. **Rodar sync em dry-run:**
   ```bash
   fork-sync sync <PROJETO> --dry-run
   ```
4. **Aplicar mudanças de rebrand (se necessário):**
   - Editar paths protegidos
   - Atualizar este manual (incrementar `version:` no frontmatter)
5. **Sync real:**
   ```bash
   fork-sync sync <PROJETO>
   ```
6. **Build + Deploy manual:**
   ```bash
   cd /home/ubuntu/docker/Atius/router-ai-atius/docs/atius-router-docs
   bun install && bun run build
   systemctl --user restart atius-router-docs.service
   ```
7. **Validar:**
   ```bash
   curl -I http://127.0.0.1:3003/pt/
   curl -I http://127.0.0.1:3003/en/
   ```

## 7. Runtime e Deploy

### Bootstrap do submodule

```bash
cd /home/ubuntu/docker/Atius/router-ai-atius
git submodule update --init --recursive
```

### Build

```bash
cd /home/ubuntu/docker/Atius/router-ai-atius/docs/atius-router-docs
bun install
bun run build
```

### Deploy

```bash
# Restart service
systemctl --user daemon-reload
systemctl --user restart atius-router-docs.service

# Check status
systemctl --user status --no-pager atius-router-docs.service

# Health check
curl -I http://127.0.0.1:3003/pt/
```

### Rollback

Se o cutover falhar, o checkout standalone legado ainda existe até cutover final:

```bash
# Parar service com submodule
systemctl --user stop atius-router-docs.service

# Restaurar service para path legado
sed -i 's|WorkingDirectory=/home/ubuntu/docker/Atius/router-ai-atius/docs/atius-router-docs|WorkingDirectory=/home/ubuntu/docker/Atius/atius-router-docs|' \
  ~/.config/systemd/user/atius-router-docs.service
systemctl --user daemon-reload
systemctl --user start atius-router-docs.service

# Verificar rotas
curl -I http://127.0.0.1:3003/pt/
```

## 8. Troubleshooting Específico

### Service não sobe
- Verificar se submodule foi inicializado: `git submodule update --init --recursive` na raiz do router-ai-atius
- Verificar se `node_modules` existe: `ls docs/atius-router-docs/node_modules`
- Logs: `journalctl --user -u atius-router-docs.service -n 50 --no-pager`

### Logo SVG não carrega
- Verificar `/var/www/atius/atius-logo.svg` (Apache serve assets locais)
- Verificar `public/assets/atius-logo.svg` dentro do submodule
- Dar cache-bust: `curl -I https://router.atius.com.br/assets/atius-logo.svg?v=YYYYMMDD-N`

### Build falha
- Verificar espaço em disco: `df -h /`
- Se `no space left on device`: limpar Podman images (`podman system prune -f`) e/ou docker cache
- Bun lock desatualizado: `rm -f bun.lock && bun install`

## 9. Remote Separado — Decisão de Governança

**Decisão (Phase 09):** O remote `giovannimnz/new-api-docs-v1` continua como remote
do submodule. O checkout standalone `/home/ubuntu/docker/Atius/atius-router-docs`
será mantido como mirror transitório até o fim do milestone v2.15, depois removido.

**Critério de remoção do standalone:**
1. Sync via fork-sync funcionando no submodule por ≥2 ciclos consecutivos
2. Build + deploy via systemd validado em produção
3. Nenhuma referência funcional ao path legado em scripts ou automações

## 10. Smoke Checks Pré-Deploy

Antes de qualquer build/deploy, verificar:

```bash
# 1. Submodule inicializado
ls /home/ubuntu/docker/Atius/router-ai-atius/docs/atius-router-docs/package.json

# 2. Node modules instalados
ls /home/ubuntu/docker/Atius/router-ai-atius/docs/atius-router-docs/node_modules/.package-lock.json

# 3. Build anterior válido (opcional, fallback)
ls /home/ubuntu/docker/Atius/router-ai-atius/docs/atius-router-docs/.next/BUILD_ID
```

## 11. Cache-Bust de Assets

Após trocar a logo ou qualquer asset estático:

```bash
# 1. Copiar asset para /var/www/atius/
sudo cp docs/atius-router-docs/public/assets/atius-logo.svg /var/www/atius/atius-logo.svg

# 2. Atualizar cache-bust no layout.shared.tsx
#    v=YYYYMMDD-N

# 3. Purge Cloudflare (se aplicável)
curl -X POST https://api.cloudflare.com/client/v4/zones/{ZONE}/purge_cache \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"files": ["https://router.atius.com.br/assets/atius-logo.svg"]}'

# 4. Validar
curl -I https://router.atius.com.br/assets/atius-logo.svg
```

## 12. Histórico de Versões do Manual

| Versão | Data | Mudança |
|--------|------|---------|
| 1 | 2026-06-04 | Geração inicial via `fork-sync manuals generate` |
| 2 | 2026-06-07 | Phase 09: docs migrados para submodule, swap container → systemd, adicionada governança do remote separado |

---

_Mantenha este manual sincronizado com `sync.yaml`. Se mudar a estratégia, regenere:_
```bash
fork-sync manuals regenerate atius-router-docs
```
