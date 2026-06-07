#!/bin/bash
# qBittorrent Post-Processing Script
# Move completed torrents to GDrive (SRV-1/streaming-service/)
# Uso: Chamado pelo qBittorrent ao completar torrent
# Parâmetros: %I (hash) | %F (path) | %C (categoria)
#
# Regras:
#  - Torrent normal: move para GDrive após completar download
#  - Private tracker (tag "private"): mantém seed até ratio 4.0x

QBT_API="http://127.0.0.1:6889"
COOKIES="/tmp/qbt_cookies.txt"
LOG="/home/ubuntu/.logs/qbt-postprocess.log"
QBT_USER="admin"
QBT_PASS="adminadmin"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"; }

login() {
  curl -s -c "$COOKIES" -b "$COOKIES" -X POST "${QBT_API}/api/v2/auth/login" \
    -d "username=${QBT_USER}&password=${QBT_PASS}" | grep -q "Ok."
}

move_to_gdrive() {
  local src="$1"; local cat="$2"; local dest="giovanni-drive:/SRV-1/streaming-service/${cat}"
  log "Movendo: ${src} -> ${dest}"
  rclone move "${src}" "${dest}/" --drive-shared-with-me -v --log-file /home/ubuntu/.logs/rclone-move.log
  [ $? -eq 0 ] && log "OK: ${src} -> ${dest}" || log "ERRO: move falhou"
}

[ $# -lt 2 ] && { echo "Uso: $0 <hash> <path> [cat]"; exit 1; }
HASH="$1"; TORRENT_PATH="$2"; CAT="${3:-}"; log "=== Torrent: $HASH | $TORRENT_PATH | cat=${CAT}"

login || { log "ERRO login"; exit 1; }

# Verificar tags
TAGS=$(curl -s -b "$COOKIES" "${QBT_API}/api/v2/torrents/info?hash=${HASH}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].get('tags','') if d else '')")

if echo "$TAGS" | grep -qi "private"; then
  log "Tag 'private' detectada — seeding até 4.0x ratio"
  curl -s -b "$COOKIES" -X POST "${QBT_API}/api/v2/torrents/setShareLimits" \
    -d "hashes=${HASH}&ratioLimit=400&inactiveSeedingTimeLimit=-1"
  log "Ratio 4.0x configurado"
  exit 0
fi

# Mover para GDrive
[ -z "$CAT" ] && CAT=$(echo "$TORRENT_PATH" | grep -oE 'filmes|series|cursos|outros' | head -1)
[ -n "$CAT" ] && [ -d "$TORRENT_PATH" ] && move_to_gdrive "$TORRENT_PATH" "$CAT" || log "Pula: sem categoria ou path inválido"
exit 0
