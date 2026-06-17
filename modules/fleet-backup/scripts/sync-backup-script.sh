#!/bin/bash
# ============================================================================
# sync-backup-script.sh
# ----------------------------------------------------------------------------
# Replica o backup-srv1-to-gdrive.sh (master em SRV-1) pros outros servers.
# Idempotente: scp -p preserva perms e mtime.
#
# Roda do SRV-1. Não tenta rodar em SRV-2/3 — master é sempre o SRV-1.
# ============================================================================
set -uo pipefail
IFS=$'\n\t'

REPO="${OMNI_SRV_ADMIN:-$HOME/GitHub/omni-srv-admin}"
MASTER_SCRIPT="$REPO/modules/srv1-ops/scripts/backup-srv1-to-gdrive.sh"

if [ ! -f "$MASTER_SCRIPT" ]; then
  echo "FAIL: master script não existe em $MASTER_SCRIPT" >&2
  exit 1
fi

# Alvos: SRV-2 e SRV-3 via alias VPN
SRV_HOSTS=("atius-srv-2-vpn:2" "atius-srv-3-vpn:3")

for entry in "${SRV_HOSTS[@]}"; do
  IFS=':' read -r srv srv_num <<< "$entry"
  echo "=== Sync para SRV-$srv_num ($srv) ==="
  scp -p -o ConnectTimeout=10 "$MASTER_SCRIPT" "ubuntu@${srv}:backup-srv${srv_num}-to-gdrive.sh"
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$srv" \
    "chmod +x ~/backup-srv${srv_num}-to-gdrive.sh && head -3 ~/backup-srv${srv_num}-to-gdrive.sh"
  echo ""
done

echo "Sync completo. Teste:"
echo "  ssh atius-srv-2-vpn 'bash ~/backup-srv2-to-gdrive.sh 2>&1 | head -5'"
