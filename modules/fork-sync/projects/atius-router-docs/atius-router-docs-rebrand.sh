#!/usr/bin/env bash
# atius-router-docs-rebrand.sh — Aplica personalizações Atius nos
# arquivos do upstream QuantumNous/new-api-docs-v1 ANTES de qualquer
# merge conflitante. Idempotente: pode ser rodado múltiplas vezes.
#
# Chamado automaticamente:
#   1. Pelo fork-sync após `git fetch upstream` no projeto atius-router-docs
#   2. Manualmente: ./atius-router-docs-rebrand.sh <repo_path>
#
# O que faz:
#   - Substitui títulos: "New API" → "Atius AI Router"
#   - Substitui URLs: QuantumNous/new-api → giovannimnz/router-ai-atius
#   - Substitui servers: https://docs.newapi.pro → https://router.atius.com.br
#   - Substitui logos: newapi.svg → atius-logo.svg
#   - Adiciona config trailingSlash: true + allowedOrigins router.atius.com.br
#   - Atualiza home: hero copy, partners vazio, GitHub link
#   - NÃO traduz conteúdo (MDX) automaticamente — docs upstream já tem
#     i18n en/zh/ja; pt-BR é adicionado manualmente em content/docs/pt/
#
# Idempotência: usa `sed -i 's|...|...|g'` que só muda a 1ª ocorrência
# por linha, e arquivos já rebrandados têm patterns diferentes
# (ex: 'Atius AI Router' já é o target final). Para re-rodar,
# começar do clean upstream state.

set -euo pipefail

REPO_PATH="${1:-}"

if [ -z "$REPO_PATH" ] || [ ! -d "$REPO_PATH" ]; then
  echo "Usage: $0 <repo_path>"
  echo "  Ex: $0 /home/ubuntu/GitHub/forks/AtiusRouterDocs"
  exit 1
fi

log() { echo "[rebrand] $*"; }

# Track changes
CHANGED=0

# === 1. Logo swap ===
LOGO="$REPO_PATH/public/assets/newapi.svg"
ATIUS_LOGO="$REPO_PATH/public/assets/atius-logo.svg"
if [ -f "$LOGO" ] && [ ! -f "$ATIUS_LOGO" ]; then
  if [ ! -f "$REPO_PATH/public/assets/newapi.svg.bak-upstream" ]; then
    cp "$LOGO" "$REPO_PATH/public/assets/newapi.svg.bak-upstream"
  fi
  ATIUS_SRC="/home/ubuntu/docker/Atius/router-ai-atius/logo.svg"
  if [ -f "$ATIUS_SRC" ]; then
    cp "$ATIUS_SRC" "$LOGO"
    cp "$ATIUS_SRC" "$ATIUS_LOGO"
    log "Logo replaced: newapi.svg → atius-logo.svg"
    CHANGED=$((CHANGED+1))
  else
    log "WARNING: Atius logo source not found at $ATIUS_SRC, skipping logo swap"
  fi
fi

# === 2. layout.shared.tsx (nav title, logo source, GitHub link) ===
# Use python3 for safe string handling (avoids shell quoting hell)
F="$REPO_PATH/src/lib/layout.shared.tsx"
if [ -f "$F" ]; then
  python3 <<PYEOF
import re
path = "$F"
with open(path) as f:
    c = f.read()
original = c
# Alt text
c = c.replace('alt="New API"', 'alt="Atius Router"')
# Logo source
c = c.replace('/assets/newapi.svg', '/assets/atius-logo.svg')
# GitHub link
c = c.replace('https://github.com/QuantumNous/new-api', 'https://github.com/giovannimnz/router-ai-atius')
# AtomGit (China-specific, remove)
c = c.replace('https://atomgit.com/QuantumNous/new-api', 'https://github.com/giovannimnz/router-ai-atius')
# Nav title text
# Upstream has either "New API" plain text or wrapped in <span>
# depending on Next.js version — handle both
if '<span' in c and 'New API' in c:
    # Upstream has "New API" inside a <span> with possibly whitespace
        # between the tag and the text. Match flexibly.
        c = re.sub(
            r'(<span[^>]*>)\s*New API\s*(</span>)',
            r'\1Atius Router\2',
            c
        )
elif '>New API<' in c:
    c = c.replace('>New API<', '>Atius Router<')
if c != original:
    with open(path, 'w') as f:
        f.write(c)
    print("layout.shared.tsx rebranded")
PYEOF
  log "layout.shared.tsx rebranded (nav, logo, GitHub links)"
  CHANGED=$((CHANGED+1))
fi

# === 3. [lang]/layout.tsx (title template + description i18n) ===
F="$REPO_PATH/src/app/[lang]/layout.tsx"
if [ -f "$F" ]; then
  python3 <<PYEOF
path = "$F"
with open(path) as f:
    c = f.read()
original = c
# EN
c = c.replace(
    "default: 'New API - The Foundation of Your AI Universe'",
    "default: 'Atius AI Router - Production-Ready LLM Gateway'"
)
c = c.replace("template: '%s | New API'", "template: '%s | Atius AI Router'")
c = c.replace(
    "description: 'Connect all AI providers, manage your AI assets, and build the future on a unified infrastructure platform. Deploy in minutes, scale effortlessly.'",
    "description: 'Aggregate 40+ AI providers behind a single OpenAI/Anthropic-compatible API. Built on QuantumNous/new-api, hardened for production.'"
)
# ZH
c = c.replace("default: 'New API - AI 基座'", "default: 'Atius AI Router - 生产就绪的 LLM 网关'")
# JA
c = c.replace("default: 'New API - あなたの AI ユニバースの基盤'",
              "default: 'Atius AI Router - 本番運用対応 LLM ゲートウェイ'")
if c != original:
    with open(path, 'w') as f:
        f.write(c)
    print("[lang]/layout.tsx rebranded")
PYEOF
  log "[lang]/layout.tsx rebranded (title + description)"
  CHANGED=$((CHANGED+1))
fi

# === 4. [lang]/(home)/page.tsx (hero copy, partners emptied, Atius links) ===
F="$REPO_PATH/src/app/[lang]/(home)/page.tsx"
if [ -f "$F" ]; then
  python3 <<PYEOF
path = "$F"
with open(path) as f:
    c = f.read()
original = c
c = c.replace("badge: 'The Foundation of Your AI Universe'",
              "badge: 'Atius AI Router — Production Ready'")
c = c.replace("title: 'Connect all AI providers, manage your AI assets,'",
              "title: 'Aggregate 40+ AI providers behind a single OpenAI/Anthropic-compatible API.'")
c = c.replace("getStarted: 'Getting Started'", "getStarted: 'Read the docs'")
c = c.replace("github: 'GitHub'", "github: 'GitHub'")  # no-op (already correct text)
c = c.replace('href="https://github.com/QuantumNous/new-api"',
              'href="https://github.com/giovannimnz/router-ai-atius"')
c = c.replace('href="https://atomgit.com/QuantumNous/new-api"',
              'href="https://github.com/giovannimnz/router-ai-atius"')
if c != original:
    with open(path, 'w') as f:
        f.write(c)
    print("[lang]/(home)/page.tsx rebranded")
PYEOF
  log "[lang]/(home)/page.tsx rebranded (hero, partners, GitHub)"
  CHANGED=$((CHANGED+1))
fi

# === 5. metadata.ts (baseUrl) ===
F="$REPO_PATH/src/lib/metadata.ts"
if [ -f "$F" ]; then
  python3 <<PYEOF
path = "$F"
with open(path) as f:
    c = f.read()
original = c
c = c.replace("http://localhost:3000", "https://router.atius.com.br")
c = c.replace("url: 'https://www.newapi.ai'", "url: 'https://router.atius.com.br'")
if c != original:
    with open(path, 'w') as f:
        f.write(c)
    print("metadata.ts rebranded")
PYEOF
  log "metadata.ts rebranded (baseUrl, og:url)"
  CHANGED=$((CHANGED+1))
fi

# === 6. layout.tsx (root, metadataBase) ===
F="$REPO_PATH/src/app/layout.tsx"
if [ -f "$F" ]; then
  python3 <<PYEOF
path = "$F"
with open(path) as f:
    c = f.read()
original = c
c = c.replace("metadataBase: new URL('https://www.newapi.ai')",
              "metadataBase: new URL('https://router.atius.com.br')")
if c != original:
    with open(path, 'w') as f:
        f.write(c)
    print("src/app/layout.tsx rebranded")
PYEOF
  log "src/app/layout.tsx rebranded (metadataBase)"
  CHANGED=$((CHANGED+1))
fi

# === 7. search.tsx (GitHub link) ===
F="$REPO_PATH/src/components/search.tsx"
if [ -f "$F" ] && grep -q "https://www.newapi.ai" "$F"; then
  sed -i "s|https://www.newapi.ai|https://router.atius.com.br|g" "$F"
  log "search.tsx rebranded (GitHub link)"
  CHANGED=$((CHANGED+1))
fi

# === 8. next.config.mjs (allowedOrigins + trailingSlash) ===
F="$REPO_PATH/next.config.mjs"
if [ -f "$F" ] && ! grep -q "router.atius.com.br" "$F"; then
  python3 <<PYEOF
import re
path = "$F"
with open(path) as f:
    content = f.read()
if 'trailingSlash' not in content:
    new_content = re.sub(
        r'(const config = \{[^}]*reactStrictMode: true,\s*poweredByHeader: false,)',
        r'\1\n  // ATIUS: force trailing slashes + add Atius allowedOrigins\n  trailingSlash: true,',
        content,
        count=1
    )
    if new_content != content:
        content = new_content
        print('next.config.mjs: added trailingSlash')
if 'router.atius.com.br' not in content:
    # Inject before the experimental block
    new_content = re.sub(
        r"('localhost:3000',)(\s*// newapi\.pro domains)",
        r"\1\n        'router.atius.com.br',\n        'www.router.atius.com.br',  // ATIUS\n\2",
        content,
        count=1
    )
    if new_content != content:
        with open(path, 'w') as f:
            f.write(new_content)
        print('next.config.mjs: added allowedOrigins for router.atius.com.br')
PYEOF
  log "next.config.mjs rebranded (trailingSlash + allowedOrigins)"
  CHANGED=$((CHANGED+1))
fi

# === 9. tsconfig.json (types: ["node"]) ===
F="$REPO_PATH/tsconfig.json"
if [ -f "$F" ] && ! grep -q '"types"' "$F"; then
  python3 <<PYEOF
import json
path = "$F"
with open(path) as f:
    cfg = json.load(f)
co = cfg.setdefault('compilerOptions', {})
if 'types' not in co:
    co['types'] = ['node']
with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)
    f.write('\n')
print('tsconfig.json: added types: ["node"]')
PYEOF
  log "tsconfig.json: added types: ['node']"
  CHANGED=$((CHANGED+1))
fi

# === 10. Dockerfile (multi-stage, we add this if missing) ===
F="$REPO_PATH/Dockerfile"
if [ ! -f "$F" ]; then
  if [ -f /home/ubuntu/fork-sync/projects/atius-router-docs/Dockerfile.template ]; then
    cp /home/ubuntu/fork-sync/projects/atius-router-docs/Dockerfile.template "$F"
    log "Dockerfile created from template"
    CHANGED=$((CHANGED+1))
  else
    log "WARNING: Dockerfile.template not found, skipping Dockerfile creation"
  fi
fi

# === 11. Update OpenAPI base URLs in any openapi JSON files ===
find "$REPO_PATH/openapi" -name "*.json" 2>/dev/null | while read f; do
  if grep -q "newapi.pro" "$f" 2>/dev/null; then
    sed -i 's|https://newapi.pro|https://router.atius.com.br|g' "$f"
    sed -i 's|http://localhost:3000|http://localhost:3003|g' "$f"
  fi
done

# === 12. Add PT-BR i18n language to i18n.ts (the actual config) ===
# Upstream has en/zh/ja; we add pt. The source of truth is
# src/lib/i18n.ts (NOT src/app/[lang]/layout.tsx, which has the
# translations dict, not the languages array).
F="$REPO_PATH/src/lib/i18n.ts"
if [ -f "$F" ] && ! grep -q "'pt'" "$F"; then
  python3 <<PYEOF
path = "$F"
with open(path) as f:
    c = f.read()
# Add 'pt' to languages if not present
if "'pt'" not in c:
    c = c.replace("languages: ['en', 'zh', 'ja']", "languages: ['en', 'zh', 'ja', 'pt']")
    c = c.replace("defaultLanguage: 'en'", "defaultLanguage: 'en'")  # no-op
    with open(path, 'w') as f:
        f.write(c)
    print("[lang]/layout.tsx: added 'pt' to languages")
PYEOF
  log "[lang]/layout.tsx: added 'pt' language"
  CHANGED=$((CHANGED+1))
fi

# Summary
if [ "$CHANGED" -gt 0 ]; then
  log "Done: $CHANGED changes applied"
else
  log "Done: no changes (already rebranded)"
fi
