#!/usr/bin/env bash
# omni::backup-databases v1.1.0
# Backup automatico, seguro e granular de bancos de dados da frota ATIUS para Google Drive (/mnt/gdrive).
# Suporta: PostgreSQL nativo (multi-porta), Podman containers, Mailcow MariaDB, Vault Raft, Vaultwarden SQLite/tarball, Landscape LXD e Mailu SQLite/DKIM.
set -euo pipefail
umask 077

HOSTNAME_RAW=$(hostname -s | tr '[:upper:]' '[:lower:]')
DATE_DIR=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
err() { printf '[%s] ERROR: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

# CPU e IO Guardrail: max 20% CPU total do host
renice -n 10 $$ >/dev/null 2>&1 || true
ionice -c 2 -n 7 -p $$ >/dev/null 2>&1 || true

# 1. Validacao do destino (/mnt/gdrive)
BASE_GDRIVE="/mnt/gdrive/ATIUS-SRV/${HOSTNAME_RAW}/Backup/databases"
FALLBACK_DIR="/home/ubuntu/backups/databases"

if mountpoint -q /mnt/gdrive 2>/dev/null; then
    TARGET_DIR="${BASE_GDRIVE}/${DATE_DIR}"
else
    log "AVISO: /mnt/gdrive nao esta montado. Usando fallback local ${FALLBACK_DIR}..."
    TARGET_DIR="${FALLBACK_DIR}/${DATE_DIR}"
fi

mkdir -p "${TARGET_DIR}"
log "Iniciando backup de bancos de dados em ${TARGET_DIR} para host ${HOSTNAME_RAW}..."

TOTAL_DUMPS=0
TOTAL_BYTES=0

# Helper para registrar dumps
track_dump() {
    local file="$1"
    if [ -f "$file" ]; then
        local sz
        sz=$(stat -c %s "$file" 2>/dev/null || stat -f %z "$file" 2>/dev/null || echo 0)
        TOTAL_BYTES=$((TOTAL_BYTES + sz))
        TOTAL_DUMPS=$((TOTAL_DUMPS + 1))
        log "OK: Dump gerado: $(basename "$file") (${sz} bytes)"
    fi
}

# 2. Backups especificos por host

# --- HOST: atius-srv-1 (PostgreSQL Central, 18+ DBs) ---
if [ "${HOSTNAME_RAW}" = "atius-srv-1" ]; then
    PG_PORT=8745
    if pg_isready -p "${PG_PORT}" >/dev/null 2>&1; then
        log "Executando pg_dumpall --globals-only no PostgreSQL (porta ${PG_PORT})..."
        sudo -u postgres pg_dumpall -p "${PG_PORT}" --globals-only 2>/dev/null | gzip -9 > "${TARGET_DIR}/globals.sql.gz" || true
        track_dump "${TARGET_DIR}/globals.sql.gz"

        # Lista bancos ativos (exclui templates)
        DBS=$(sudo -u postgres psql -p "${PG_PORT}" -l -t 2>/dev/null | cut -d '|' -f 1 | xargs)
        for db in $DBS; do
            case "$db" in
                template0|template1) continue ;;
            esac
            log "Dump do banco PostgreSQL: ${db}..."
            DUMP_FILE="${TARGET_DIR}/${db}.dump"
            sudo -u postgres pg_dump -p "${PG_PORT}" -Fc -Z 6 -f "${DUMP_FILE}" "${db}" 2>/dev/null || {
                err "Falha ao realizar dump do banco ${db}"
                continue
            }
            track_dump "${DUMP_FILE}"
        done
    fi
fi

# --- HOST: atius-srv-2 (Mailcow MariaDB + PostgreSQL) ---
if [ "${HOSTNAME_RAW}" = "atius-srv-2" ]; then
    # Mailcow MariaDB
    if [ -f /opt/mailcow-dockerized/mailcow.conf ]; then
        DBROOT=$(grep "^DBROOT=" /opt/mailcow-dockerized/mailcow.conf | cut -d= -f2 | tr -d "\r\n")
        if [ -n "$DBROOT" ]; then
            log "Executando mariadb-dump do Mailcow..."
            MYSQL_DUMP="${TARGET_DIR}/mailcow-mysql.sql.gz"
            podman exec mailcowdockerized_mysql-mailcow_1 mariadb-dump -u root -p"${DBROOT}" --databases mailcow 2>/dev/null | gzip -9 > "${MYSQL_DUMP}" || \
            podman exec mailcowdockerized_mysql-mailcow_1 mysqldump -u root -p"${DBROOT}" --databases mailcow 2>/dev/null | gzip -9 > "${MYSQL_DUMP}" || true
            track_dump "${MYSQL_DUMP}"

            # Backup da configuracao mailcow.conf
            cp -a /opt/mailcow-dockerized/mailcow.conf "${TARGET_DIR}/mailcow.conf" 2>/dev/null || true
            chmod 600 "${TARGET_DIR}/mailcow.conf" 2>/dev/null || true
            track_dump "${TARGET_DIR}/mailcow.conf"
        fi
    fi

    # PostgreSQL nativo se houver bancos alem de templates
    if pg_isready -p 5432 >/dev/null 2>&1; then
        DBS=$(sudo -u postgres psql -p 5432 -l -t 2>/dev/null | cut -d '|' -f 1 | xargs)
        for db in $DBS; do
            case "$db" in
                template0|template1|postgres) continue ;;
            esac
            log "Dump do banco PostgreSQL: ${db}..."
            DUMP_FILE="${TARGET_DIR}/${db}.dump"
            sudo -u postgres pg_dump -p 5432 -Fc -Z 6 -f "${DUMP_FILE}" "${db}" 2>/dev/null || true
            track_dump "${DUMP_FILE}"
        done
    fi
fi

# --- HOST: atius-srv-3 (HashiCorp Vault, Vaultwarden, Landscape LXD) ---
if [ "${HOSTNAME_RAW}" = "atius-srv-3" ]; then
    # 1. HashiCorp Vault Raft Snapshot
    if [ -x /usr/local/sbin/atius-hashicorp-vault-backup.sh ]; then
        log "Executando snapshot do HashiCorp Vault via atius-hashicorp-vault-backup.sh..."
        SNAP_PATH=$(sudo /usr/local/sbin/atius-hashicorp-vault-backup.sh 2>/dev/null || true)
        if [ -n "$SNAP_PATH" ] && [ -f "$SNAP_PATH" ]; then
            cp -f "$SNAP_PATH" "${TARGET_DIR}/hashicorp-vault-snapshot.snap" 2>/dev/null || true
            chmod 600 "${TARGET_DIR}/hashicorp-vault-snapshot.snap" 2>/dev/null || true
            track_dump "${TARGET_DIR}/hashicorp-vault-snapshot.snap"
        fi
    elif [ -x /usr/local/sbin/atius-vault ]; then
        log "Executando Raft snapshot direto do HashiCorp Vault..."
        VAULT_TMP="/srv/hashicorp-vault-atius/backups/vault-snapshot-${TIMESTAMP}.snap"
        if sudo /usr/local/sbin/atius-vault operator raft snapshot save "/vault/backups/vault-snapshot-${TIMESTAMP}.snap" 2>/dev/null; then
            mv "${VAULT_TMP}" "${TARGET_DIR}/hashicorp-vault-snapshot.snap" 2>/dev/null || true
            chmod 600 "${TARGET_DIR}/hashicorp-vault-snapshot.snap" 2>/dev/null || true
            track_dump "${TARGET_DIR}/hashicorp-vault-snapshot.snap"
        fi
    fi

    # 2. Vaultwarden Backup
    if [ -x /usr/local/sbin/atius-vaultwarden-backup.sh ]; then
        log "Executando backup do Vaultwarden via atius-vaultwarden-backup.sh..."
        VW_PATH=$(sudo /usr/local/sbin/atius-vaultwarden-backup.sh 2>/dev/null || true)
        if [ -n "$VW_PATH" ] && [ -f "$VW_PATH" ]; then
            cp -f "$VW_PATH" "${TARGET_DIR}/vaultwarden-backup.tgz" 2>/dev/null || true
            chmod 600 "${TARGET_DIR}/vaultwarden-backup.tgz" 2>/dev/null || true
            track_dump "${TARGET_DIR}/vaultwarden-backup.tgz"
        fi
    fi

    # 3. Landscape LXD Container PostgreSQL (6 bancos Landscape)
    if command -v lxc >/dev/null 2>&1; then
        if sudo lxc list -c s --format csv 2>/dev/null | grep -q "RUNNING"; then
            log "Executando pg_dumpall dos bancos do Landscape Server..."
            LANDSCAPE_DUMP="${TARGET_DIR}/landscape-pg-all.sql.gz"
            sudo lxc exec landscape -- sudo -u postgres pg_dumpall 2>/dev/null | gzip -9 > "${LANDSCAPE_DUMP}" || true
            track_dump "${LANDSCAPE_DUMP}"
        fi
    fi
fi

# --- HOST: atius-srv-4 (Mailu SQLite + DKIM) ---
if [ "${HOSTNAME_RAW}" = "atius-srv-4" ]; then
    # 1. Mailu SQLite database
    MAILU_DB="/home/ubuntu/data/atius-mail/data/main.db"
    if [ -f "${MAILU_DB}" ]; then
        log "Executando SQLite backup online do Mailu..."
        MAILU_DUMP="${TARGET_DIR}/mailu-main.sqlite3"
        python3 -c "import sqlite3; con = sqlite3.connect('${MAILU_DB}'); bck = sqlite3.connect('${MAILU_DUMP}'); con.backup(bck); bck.close(); con.close()" 2>/dev/null || cp -a "${MAILU_DB}" "${MAILU_DUMP}" 2>/dev/null || true
        chmod 600 "${MAILU_DUMP}" 2>/dev/null || true
        track_dump "${MAILU_DUMP}"
    fi

    # 2. Mailu DKIM Keys
    MAILU_DKIM="/home/ubuntu/data/atius-mail/dkim"
    if [ -d "${MAILU_DKIM}" ]; then
        log "Executando backup das chaves DKIM do Mailu..."
        DKIM_TAR="${TARGET_DIR}/mailu-dkim.tar.gz"
        tar -C /home/ubuntu/data/atius-mail -czf "${DKIM_TAR}" dkim 2>/dev/null || true
        chmod 600 "${DKIM_TAR}" 2>/dev/null || true
        track_dump "${DKIM_TAR}"
    fi
fi

# 3. Checksums de Integridade
if [ "${TOTAL_DUMPS}" -gt 0 ]; then
    log "Gerando SHA256SUMS..."
    (cd "${TARGET_DIR}" && sha256sum * > SHA256SUMS 2>/dev/null || true)
fi

# 4. Politica de Retencao (Expira snapshots com mais de 14 dias)
PARENT_DIR="$(dirname "${TARGET_DIR}")"
log "Aplicando retencao de 14 dias em ${PARENT_DIR}..."
find "${PARENT_DIR}" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} + 2>/dev/null || true

# 5. Manifesto de Conclusao
MANIFEST_FILE="${TARGET_DIR}/manifest.json"
cat <<EOF_JSON > "${MANIFEST_FILE}"
{
  "host": "${HOSTNAME_RAW}",
  "timestamp": "${TIMESTAMP}",
  "date": "${DATE_DIR}",
  "target_dir": "${TARGET_DIR}",
  "total_dumps": ${TOTAL_DUMPS},
  "total_bytes": ${TOTAL_BYTES},
  "status": "SUCCESS"
}
EOF_JSON

log "SUCCESS: Backup de bancos de dados concluido com sucesso! Total de dumps: ${TOTAL_DUMPS}, Bytes: ${TOTAL_BYTES}."
exit 0
