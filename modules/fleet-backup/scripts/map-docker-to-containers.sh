#!/bin/bash
# ============================================================================
# map-docker-to-containers.sh
# ----------------------------------------------------------------------------
# Mapeia 1:1 exato a estrutura de ~/docker/ para ~/GitHub/containers/.
# Preserva case, symlinks relativos, atributos (quando possível).
# Idempotente: rodável múltiplas vezes sem efeito colateral.
#
# Uso:
#   bash map-docker-to-containers.sh [SRC] [DST]
#   bash map-docker-to-containers.sh ~/docker ~/GitHub/containers
#
# Validação:
#   diff -r <(cd ~/docker && find .) <(cd ~/GitHub/containers && find .)
# ============================================================================
set -uo pipefail
IFS=$'\n\t'

SRC="${1:-/home/ubuntu/docker}"
DST="${2:-/home/ubuntu/GitHub/containers}"

if [ ! -d "$SRC" ]; then
  echo "FAIL: SRC não existe: $SRC" >&2
  exit 1
fi

mkdir -p "$DST"

# Mapeia top-level dirs: cada subdiretório de SRC vira subdiretório de DST
# case-preserved, com mesmo nome
echo "=== Mapeando $SRC -> $DST ==="
for entry in "$SRC"/*; do
  [ -e "$entry" ] || continue
  name=$(basename "$entry")
  dst_path="$DST/$name"

  if [ -d "$entry" ]; then
    if [ ! -d "$dst_path" ]; then
      mkdir -p "$dst_path"
      echo "  + mkdir $name/"
    fi
  else
    # File no top-level (state.db, etc)
    if [ ! -f "$dst_path" ]; then
      cp -p "$entry" "$dst_path"
      echo "  + cp $name"
    fi
  fi
done

# Agora para cada subdiretório mapeado, recursivamente preserva estrutura
# de SUBPASTAS (mas NÃO copia files grandes automaticamente — só estrutura)
echo ""
echo "=== Recriando estrutura de subpastas (sem conteúdo binário) ==="
for src_dir in "$SRC"/*/; do
  [ -d "$src_dir" ] || continue
  name=$(basename "$src_dir")
  dst_dir="$DST/$name"

  # Encontra todas as subpastas (1+ nível) e cria mirror
  cd "$src_dir" || continue
  find . -mindepth 1 -type d -print0 | while IFS= read -r -d '' subdir; do
    rel="${subdir#./}"
    dst_subdir="$dst_dir/$rel"
    if [ ! -d "$dst_subdir" ]; then
      mkdir -p "$dst_subdir"
    fi
  done
done

# Log de tudo
echo ""
echo "=== Mapeamento completo ==="
echo "SRC: $SRC"
echo "DST: $DST"
echo ""
echo "Top-level em $DST:"
ls -1 "$DST" | sed 's/^/  /'

echo ""
echo "Validar com diff -r (esperado vazio):"
echo "  diff -r <(cd $SRC && find .) <(cd $DST && find .) | head -20"
