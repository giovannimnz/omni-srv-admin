#!/bin/bash
# Fix Shared_smb — verifica e remonta //10.1.1.2/Shared se necessario
# Uso: ~/scripts/fix-shared_smb.sh

set -e

MOUNT_POINT="$HOME/Shared_smb"
REMOTE="//10.1.1.2/Shared"

echo "[fix-shared_smb] Verificando mount..."

# 1. Testa se mountpoint esta acessivel
if timeout 5 ls "$MOUNT_POINT" > /dev/null 2>&1; then
    echo "[fix-shared_smb] Mount OK — conteudo acessivel"
    echo "[fix-shared_smb] $(ls "$MOUNT_POINT" 2>/dev/null | wc -l) itens no diretorio"
else
    echo "[fix-shared_smb] Mount invalido — remountando..."

    # 2. Desmonta se existir (pode falhar se nao montado, ok)
    sudo umount -l "$MOUNT_POINT" 2>/dev/null || true

    # 3. Remonta
    sudo mount -t cifs "$REMOTE" "$MOUNT_POINT" \
        -o credentials="$HOME/.smbcredentials",uid=ubuntu,gid=ubuntu,file_mode=0755,dir_mode=0755,_netdev,x-systemd.automount

    # 4. Verifica
    if timeout 5 ls "$MOUNT_POINT" > /dev/null 2>&1; then
        echo "[fix-shared_smb] Mount refeito com sucesso"
    else
        echo "[fix-shared_smb] ERRO: nao foi possivel remontar"
        exit 1
    fi
fi

# 5. Mostra espacos livre
df -h "$MOUNT_POINT" 2>/dev/null | tail -1

echo "[fix-shared_smb] OK"
