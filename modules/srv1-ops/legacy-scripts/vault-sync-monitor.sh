#!/bin/bash
# Monitor de sincronização do vault Obsidian em 3 servidores
# Intervalo: 5 minutos | Duração: 60 minutos

VAULT_DIR="$HOME/GitHub/obsidian-vault/AiSecondBrain"
LOG_FILE="$HOME/scripts/vault-sync-monitor.log"
SRV3="10.1.1.7"
MAX_MINUTES=60
INTERVAL=300  # 5 min

echo "=== Monitor iniciado $(date) ===" | tee -a $LOG_FILE

elapsed=0
while [ $elapsed -lt $MAX_MINUTES ]; do
    ts=$(date "+%H:%M")
    
    # GitHub (origin)
    # GitHub (origin) via git ls-remote
    github_sha=$(timeout 10 git ls-remote https://github.com/giovannimnz/obsidian-vault.git master 2>/dev/null | cut -f1 | cut -c1-8)
    
    # SRV-1 (local)
    srv1_sha=$(cd $VAULT_DIR && git log -1 --format="%H" 2>/dev/null | cut -c1-8)
    srv1_branch=$(cd $VAULT_DIR && git rev-parse --abbrev-ref HEAD 2>/dev/null)
    
    # SRV-3
    srv3_sha=$(ssh $SRV3 "cd $VAULT_DIR && git log -1 --format='%H'" 2>/dev/null | cut -c1-8)
    
    status="[$ts] GitHub:$github_sha | SRV-1:$srv1_sha | SRV-3:$srv3_sha"
    
    if [ "$github_sha" = "$srv1_sha" ] && [ "$github_sha" = "$srv3_sha" ]; then
        echo "✅ $status" | tee -a $LOG_FILE
    else
        echo "⚠️  DESSINCRONIZADOS — $status" | tee -a $LOG_FILE
        # Auto-fix: pull no SRV-1
        cd $VAULT_DIR && git pull --no-rebase origin master >> $LOG_FILE 2>&1
        # Auto-fix: reset no SRV-3
        ssh $SRV3 "cd $VAULT_DIR && git fetch origin && git reset --hard origin/master" >> $LOG_FILE 2>&1
        # Push se SRV-1 avançou
        cd $VAULT_DIR && git push origin master >> $LOG_FILE 2>&1
        echo "   → Auto-sync executado" | tee -a $LOG_FILE
    fi
    
    elapsed=$((elapsed + 5))
    if [ $elapsed -lt $MAX_MINUTES ]; then
        sleep $INTERVAL
    fi
done

echo "=== Monitor terminado $(date) ===" | tee -a $LOG_FILE
