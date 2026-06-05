#!/usr/bin/env bash
# post-merge.sh — Hook chamado pelo merge-upstream.sh após cada merge.
#
# Para o projeto atius-router-docs: aplica o rebrand Atius nos
# arquivos que o upstream QuantumNous/new-api-docs-v1 introduz
# ou modifica (logos, titles, GitHub links, hero copy, etc).
#
# Idempotente — pode ser rodado múltiplas vezes sem duplicar mudanças.
# Os paths protegidos pelo sync.yaml (protected_paths) são preservados
# pelo checkout --ours do merge-upstream.sh; o rebrand re-aplica as
# mudanças Atius nos arquivos upstreamed (não protegidos) que o merge
# acabou de introduzir.
#
# Uso: post-merge.sh <repo_path> <upstream_version>
#   ex: post-merge.sh /home/ubuntu/GitHub/forks/AtiusRouterDocs v1.0.0

set -euo pipefail

REPO_PATH="${1:-}"
UPSTREAM_VERSION="${2:-unknown}"

if [ -z "$REPO_PATH" ] || [ ! -d "$REPO_PATH" ]; then
  echo "[post-merge] Usage: $0 <repo_path> <upstream_version>" >&2
  exit 1
fi

# Source the rebrand script (handles all Atius-specific substitutions)
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REBRAND="$SOURCE_DIR/projects/atius-router-docs/atius-router-docs-rebrand.sh"

if [ ! -f "$REBRAND" ]; then
  echo "[post-merge] ERROR: rebrand script not found at $REBRAND" >&2
  exit 1
fi

echo "[post-merge] Running Atius rebrand on $REPO_PATH (upstream: $UPSTREAM_VERSION)"
"$REBRAND" "$REPO_PATH"

# If the rebrand created/modified files, stage them
if git -C "$REPO_PATH" status --porcelain | grep -q .; then
  echo "[post-merge] Staging Atius rebrand changes"
  git -C "$REPO_PATH" add -A
fi
