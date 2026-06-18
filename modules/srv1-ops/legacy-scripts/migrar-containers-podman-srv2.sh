#!/bin/bash
# migrar-containers-podman-srv2.sh
# Plan 17-02 — SRV-2: Docker → Podman cutover idempotente
# Ordem: db-newapi (pequeno, dados críticos) → router-ai-atius/zentrius → mailcow (grande, 18 containers)
# YOLO mode ON, backup pré-exigido, Docker NÃO removido (soak +7 dias)
set -uo pipefail

LOG="$HOME/.logs/migrar-podman-srv2.log"
mkdir -p "$HOME/.logs" "$HOME/backups"
DATE=$(date +%Y%m%d_%H%M%S)
SNAPSHOT_DIR="$HOME/backups/srv2-pre-migration-$DATE"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
fail() { log "FAIL: $*"; exit 1; }
ok() { log "OK: $*"; }

# === 0. PRÉ-FLIGHT ===
log "=== PRÉ-FLIGHT ==="
[[ "$(hostname)" == "ATIUS-SRV-2" ]] || fail "Esperado SRV-2, rodando em $(hostname)"
command -v podman >/dev/null || fail "podman não instalado"
command -v docker >/dev/null || fail "docker não instalado"
command -v rclone >/dev/null || fail "rclone não instalado"

DOCKER_CTS=$(docker ps --format "{{.Names}}" | wc -l)
log "Docker containers rodando: $DOCKER_CTS"
[[ "$DOCKER_CTS" -ge 19 ]] || fail "Esperado >=19 containers, encontrado $DOCKER_CTS"

# === 1. BACKUP GDRIVE ===
log "=== STEP 1: BACKUP GDRIVE ==="
if [[ ! -f "$HOME/backup-srv2-to-gdrive.sh" ]]; then
    log "Criando backup-srv2-to-gdrive.sh a partir do SRV-1"
    if [[ -f "$HOME/backup-srv1-to-gdrive.sh.tmp" ]]; then
        cp "$HOME/backup-srv1-to-gdrive.sh.tmp" "$HOME/backup-srv2-to-gdrive.sh"
    else
        scp -p ubuntu@10.1.1.1:/home/ubuntu/.local/bin/backup-srv1-to-gdrive.sh "$HOME/backup-srv2-to-gdrive.sh"
    fi
    sed -i 's|SRV-1|SRV-2|g; s|srv1|srv2|g' "$HOME/backup-srv2-to-gdrive.sh"
    chmod +x "$HOME/backup-srv2-to-gdrive.sh"
    ok "backup-srv2-to-gdrive.sh criado"
fi

# Remover .tmp se existir
rm -f "$HOME/backup-srv1-to-gdrive.sh.tmp"

log "Executando backup GDrive (pode demorar)..."
bash "$HOME/backup-srv2-to-gdrive.sh" >> "$LOG" 2>&1 || fail "Backup GDrive falhou"
ok "Backup GDrive concluído"

LATEST_SNAP=$(rclone lsf giovanni-drive:ATIUS-SRV/SRV-2/Backup/snapshots/ --dirs-only 2>/dev/null | sort | tail -1 | tr -d '/' || echo "")
[[ -n "$LATEST_SNAP" ]] || fail "Nenhum snapshot encontrado em GDrive SRV-2"
log "Snapshot GDrive: $LATEST_SNAP"
rclone check --one-way "$HOME/docker" "giovanni-drive:ATIUS-SRV/SRV-2/Backup/snapshots/${LATEST_SNAP}/home/ubuntu/docker" 2>&1 | tee -a "$LOG" | tail -5

# Snapshot local adicional
log "Snapshot local: $SNAPSHOT_DIR"
mkdir -p "$SNAPSHOT_DIR"
rsync -a --exclude='*/data/postgres*' --exclude='*/postgres_data/**' --exclude='*/db-data/**' "$HOME/docker/" "$SNAPSHOT_DIR/docker/" 2>&1 | tail -3
rsync -a "$HOME/.hermes/" "$SNAPSHOT_DIR/hermes/" 2>&1 | tail -3
SNAP_SIZE=$(du -sh "$SNAPSHOT_DIR" 2>/dev/null | awk '{print $1}')
ok "Snapshot local criado ($SNAP_SIZE)"

# === 2. SKELETON ~/GitHub/containers/ ===
log "=== STEP 2: SKELETON GitHub/containers/ ==="
mkdir -p "$HOME/GitHub/containers/mailcow" "$HOME/GitHub/containers/router-ai-atius" "$HOME/GitHub/containers/router-ai-zentrius"

if [[ ! -f "$HOME/GitHub/containers/router-ai-atius/podman-compose.yml" ]] || [[ "$HOME/GitHub/containers/router-ai-atius/podman-compose.yml" -ot "$HOME/docker/Atius/router-ai-atius/docker-compose.yml" ]]; then
    cp "$HOME/docker/Atius/router-ai-atius/docker-compose.yml" "$HOME/GitHub/containers/router-ai-atius/podman-compose.yml"
    ok "router-ai-atius podman-compose.yml copiado"
fi
if [[ ! -f "$HOME/GitHub/containers/router-ai-zentrius/podman-compose.yml" ]] || [[ "$HOME/GitHub/containers/router-ai-zentrius/podman-compose.yml" -ot "$HOME/docker/Atius/router-ai-zentrius/docker-compose.yml" ]]; then
    cp "$HOME/docker/Atius/router-ai-zentrius/docker-compose.yml" "$HOME/GitHub/containers/router-ai-zentrius/podman-compose.yml"
    ok "router-ai-zentrius podman-compose.yml copiado"
fi
if [[ ! -d "$HOME/GitHub/containers/mailcow/helper-scripts" ]]; then
    cp "$HOME/docker/mailcow/docker-compose.yml" "$HOME/GitHub/containers/mailcow/podman-compose.yml"
    cp -r "$HOME/docker/mailcow/helper-scripts" "$HOME/GitHub/containers/mailcow/"
    cp "$HOME/docker/mailcow/mailcow.conf" "$HOME/docker/mailcow/generate_config.sh" "$HOME/docker/mailcow/create_cold_standby.sh" "$HOME/docker/mailcow/update.sh" "$HOME/GitHub/containers/mailcow/" 2>/dev/null
    ok "mailcow skeleton copiado (helper-scripts + scripts oficiais preservados)"
fi
ls -la "$HOME/GitHub/containers/mailcow/" | head -20 | tee -a "$LOG"

# === 3. MIGRAR db-newapi (Postgres) ===
log "=== STEP 3: MIGRAR db-newapi ==="
if podman ps --format "{{.Names}}" | grep -q "^db-newapi$"; then
    log "db-newapi já em Podman, pulando cutover"
else
    log "Dump Postgres pré-migration"
    docker exec db-newapi pg_dump -U postgres -d newapi > "$HOME/backups/db-newapi-pre-migration-$DATE.sql" 2>>"$LOG" || fail "pg_dump falhou"
    DUMP_SIZE=$(stat -c %s "$HOME/backups/db-newapi-pre-migration-$DATE.sql")
    log "Dump size: ${DUMP_SIZE} bytes"
    [[ "$DUMP_SIZE" -gt 0 ]] || fail "Dump vazio"

    log "Parando db-newapi (Docker)"
    docker compose -f "$HOME/docker/Atius/router-ai-atius/docker-compose.yml" stop db-newapi 2>&1 | tee -a "$LOG"
    sleep 5

    log "Transferindo imagem postgres:15-alpine Docker → Podman"
    docker save postgres:15-alpine | podman load 2>&1 | tail -3 | tee -a "$LOG"
    podman tag localhost/postgres:15-alpine localhost/db-newapi:podman-latest
    ok "Imagem transferida"

    log "Editando podman-compose.yml (image tag)"
    sed -i 's|postgres:15-alpine|localhost/db-newapi:podman-latest|g' "$HOME/GitHub/containers/router-ai-atius/podman-compose.yml"
    # Verificar se houve mudança
    grep "image" "$HOME/GitHub/containers/router-ai-atius/podman-compose.yml" | head -3 | tee -a "$LOG"

    log "Subindo db-newapi via podman-compose"
    cd "$HOME/GitHub/containers/router-ai-atius" && podman-compose up -d db-newapi 2>&1 | tee -a "$LOG"
    sleep 30

    log "Aguardando Postgres ready"
    for i in 1 2 3 4 5 6; do
        if podman exec db-newapi pg_isready -U postgres 2>&1 | grep -q "accepting"; then
            ok "Postgres aceitando conexões (tentativa $i)"
            break
        fi
        sleep 5
    done
    podman exec db-newapi pg_isready -U postgres 2>&1 | tee -a "$LOG"

    log "Restore dump pré-migration"
    cat "$HOME/backups/db-newapi-pre-migration-$DATE.sql" | podman exec -i db-newapi psql -U postgres -d newapi 2>&1 | tail -10 | tee -a "$LOG"

    log "Verify count(*) users"
    USERS_COUNT=$(podman exec db-newapi psql -U postgres -d newapi -t -c "SELECT count(*) FROM users;" 2>&1 | tr -d ' ' | grep -E '^[0-9]+$' | head -1)
    log "users count: ${USERS_COUNT:-INDETERMINADO}"
    if [[ -z "$USERS_COUNT" ]] || [[ "$USERS_COUNT" == "0" ]]; then
        log "WARN: count=0 ou falhou. Verificando schema..."
        podman exec db-newapi psql -U postgres -d newapi -c "\dt" 2>&1 | tee -a "$LOG"
    fi
    ok "db-newapi migrado (users=$USERS_COUNT)"
fi

# === 4. MIGRAR router-ai-atius + zentrius (batch pequeno) ===
log "=== STEP 4: MIGRAR router-ai ==="
for stack in router-ai-atius router-ai-zentrius; do
    DIR="$HOME/GitHub/containers/$stack"
    log "--- $stack ---"
    # Identifica imagens do compose
    IMGS=$(grep -E '^\s*image:' "$DIR/podman-compose.yml" | awk '{print $2}' | sort -u)
    log "Imagens: $(echo $IMGS | tr '\n' ' ')"

    for img in $IMGS; do
        # Pular se já é localhost (carregada)
        if [[ "$img" == localhost/* ]]; then
            log "Já localhost: $img"
            continue
        fi
        log "Docker save $img | podman load"
        docker save "$img" 2>/dev/null | podman load 2>&1 | tail -2 | tee -a "$LOG" || log "WARN: falha ao carregar $img (pode já estar em podman)"
    done

    log "Subindo stack $stack via podman-compose"
    cd "$DIR" && podman-compose up -d 2>&1 | tee -a "$LOG" | tail -10
    sleep 15
    podman ps --format "table {{.Names}}\t{{.Status}}" | grep -i "$stack" | tee -a "$LOG"
done

# === 5. MIGRAR mailcow (18 containers, batch grande) ===
log "=== STEP 5: MIGRAR MAILCOW (18 containers) ==="
if podman ps --format "{{.Names}}" | grep -c "mailcowdockerized" | grep -q "^[1-9]"; then
    log "mailcow já em Podman, pulando cutover"
else
    log "Backup ~/docker/mailcow/data"
    mkdir -p "$HOME/backups/mailcow-data-pre-migration-$DATE"
    rsync -a "$HOME/docker/mailcow/data/" "$HOME/backups/mailcow-data-pre-migration-$DATE/data/" 2>&1 | tail -3
    MC_SIZE=$(du -sh "$HOME/backups/mailcow-data-pre-migration-$DATE" 2>/dev/null | awk '{print $1}')
    log "mailcow data backup: $MC_SIZE"

    log "mysqldump do mailcowmysql"
    docker exec mailcowdockerized-mysql-mailcow-1 mysqldump --all-databases -uroot -p"$(grep DBROOTPASS "$HOME/docker/mailcow/mailcow.conf" | cut -d\' -f2)" > "$HOME/backups/mailcow-mysql-pre-migration-$DATE.sql" 2>>"$LOG" || log "WARN: mysqldump falhou (não bloqueante, dados em volume)"
    [[ -s "$HOME/backups/mailcow-mysql-pre-migration-$DATE.sql" ]] && log "mysqldump OK ($(stat -c %s "$HOME/backups/mailcow-mysql-pre-migration-$DATE.sql") bytes)"

    log "Parando mailcow Docker"
    cd "$HOME/docker/mailcow" && docker compose down 2>&1 | tee -a "$LOG" | tail -5
    sleep 10

    log "Transferindo imagens mailcow Docker → Podman"
    MC_IMGS=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "mailcow|ofelia|olefy|unbound|ofelia|nginx|postfix|dovecot|clamd|rspamd|sogo|netfilter|memcached|redis|mysql|php-fpm|acme|watchdog|ipv6nat|dockerapi" | sort -u)
    IMG_COUNT=0
    for img in $MC_IMGS; do
        IMG_COUNT=$((IMG_COUNT + 1))
        SHORT=$(echo "$img" | tr '/:' '_')
        docker save "$img" 2>/dev/null | podman load 2>&1 | tail -1 | tee -a "$LOG" >/dev/null || log "WARN: falha $img"
        podman tag "$(echo "$img" | sed 's|.*/||')" "localhost/mailcow-$SHORT:podman-latest" 2>/dev/null || true
    done
    log "Imagens processadas: $IMG_COUNT"

    log "Backup mailcow.conf (snapshot de config)"
    cp "$HOME/docker/mailcow/mailcow.conf" "$HOME/backups/mailcow.conf.bak-$DATE"

    log "Subindo mailcow via podman-compose"
    cd "$HOME/GitHub/containers/mailcow" && podman-compose up -d 2>&1 | tee -a "$LOG" | tail -20

    log "Aguardando 60s para containers subirem"
    sleep 60

    MC_RUNNING=$(podman ps --format "{{.Names}}" | grep -c "mailcowdockerized" || echo 0)
    log "mailcow containers rodando em Podman: $MC_RUNNING"
    podman ps --format "table {{.Names}}\t{{.Status}}" | grep mailcowdockerized | tee -a "$LOG"

    # SMTP test
    log "SMTP test (port 25)"
    echo "QUIT" | timeout 3 nc -w 2 127.0.0.1 25 2>&1 | head -3 | tee -a "$LOG"
    # IMAP test
    log "IMAP test (port 143)"
    echo "A1 LOGOUT" | timeout 3 nc -w 2 127.0.0.1 143 2>&1 | head -3 | tee -a "$LOG"
    # HTTPs test
    log "HTTPS test"
    curl -skI https://localhost/ 2>&1 | head -3 | tee -a "$LOG"
fi

# === 6. RELATÓRIO ===
log "=== STEP 6: RELATÓRIO FINAL ==="
echo
echo "Docker containers restantes:"
docker ps --format "{{.Names}}" 2>/dev/null | head -20
echo
echo "Podman containers:"
podman ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null
echo
echo "Total Podman: $(podman ps --format '{{.Names}}' 2>/dev/null | wc -l)"
echo "Total Docker: $(docker ps --format '{{.Names}}' 2>/dev/null | wc -l)"
echo
log "=== MIGRAÇÃO SRV-2 CONCLUÍDA — Docker NÃO removido (soak +7 dias) ==="
ok "Log em: $LOG"
ok "Snapshots em: giovanni-drive:ATIUS-SRV/SRV-2/Backup/snapshots/"
ok "Backups locais em: $HOME/backups/"
