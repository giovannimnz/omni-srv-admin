#!/usr/bin/env bash
# ==============================================================================
# omni::antigravity-tarball-cleanup
# Purges legacy Antigravity manual tarball extractions, build artifacts and downloads.
# ==============================================================================
set -euo pipefail

echo "=== [$(hostname -f 2>/dev/null || hostname)] Antigravity Tarball Cleanup Starting ==="

PURGED_COUNT=0

# 1. Purge legacy standalone tarball extraction directory
for d in /home/*/.local/opt/antigravity /root/.local/opt/antigravity; do
  if [ -d "$d" ]; then
    echo "Removendo diretorio de extracao: $d"
    rm -rf "$d"
    PURGED_COUNT=$((PURGED_COUNT + 1))
  fi
done

# 2. Purge legacy standalone symlink
for f in /home/*/.local/bin/antigravity /root/.local/bin/antigravity; do
  if [ -L "$f" ] || [ -f "$f" ]; then
    echo "Removendo binario/symlink local: $f"
    rm -f "$f"
    PURGED_COUNT=$((PURGED_COUNT + 1))
  fi
done

# 3. Purge GitHub/Programs/Antigravity directories and tarballs
for p in /home/*/GitHub/Programs/Antigravity /home/*/GitHub/Programs/Antygravity; do
  if [ -d "$p" ]; then
    echo "Removendo pasta de programas: $p"
    rm -rf "$p"
    PURGED_COUNT=$((PURGED_COUNT + 1))
  fi
done

for t in /home/*/GitHub/Programs/Antigravity*.tar.gz /home/*/GitHub/Programs/antigravity*.tar.gz; do
  if [ -f "$t" ]; then
    echo "Removendo tarball em Programs: $t"
    rm -f "$t"
    PURGED_COUNT=$((PURGED_COUNT + 1))
  fi
done

# 4. Purge .tar.gz in ~/Downloads
for d in /home/*/Downloads /root/Downloads; do
  if [ -d "$d" ]; then
    for f in "$d"/*.tar.gz; do
      if [ -f "$f" ]; then
        echo "Removendo download tar.gz: $f"
        rm -f "$f"
        PURGED_COUNT=$((PURGED_COUNT + 1))
      fi
    done
  fi
done

# 5. Verify official APT package remains intact
ACTIVE_BIN="$(which antigravity 2>/dev/null || echo 'NONE')"
echo "Itens purgados: $PURGED_COUNT"
echo "Binario oficial ativo: $ACTIVE_BIN"
if [ "$ACTIVE_BIN" = "/usr/bin/antigravity" ]; then
  echo "STATUS: CONFORME (/usr/bin/antigravity ativo)"
else
  echo "ALERTA: /usr/bin/antigravity nao detectado como default!"
fi

echo "=== Cleanup Concluido com Sucesso ==="
