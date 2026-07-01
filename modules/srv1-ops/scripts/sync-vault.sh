#!/bin/bash
# v5.2-omni: gitleaks-aware + lock + branch auto + telegram notify + logrotate + GBrain sync
# Managed by: ~/GitHub/omni-srv-admin/modules/srv1-ops/
# Runs every 5 min on SRV-1, SRV-2, SRV-3 (escalonado 0s/45s/90s)
#
# Melhorias v5.0 sobre v4.1:
# 1. Pre-push hook gitleaks-like (regex robusta, evita leak de secrets)
# 2. Lock file com flock (evita overlap se sync demorar)
# 3. Auto-detect branch (master vs main baseado no origin)
# 4. Notificação Telegram se sync falhar 3 ciclos consecutivos
# 5. Log rotation (gzip quando log > 10MB, manter últimos 5)
# 6. GBrain sync incremental do vault depois do Git sync bem-sucedido
#
# Pitfalls v5.0:
# - P1: .gitignore deve estar completo (data/, db-data/, .env, *.key, *.pem)
# - P2: paths hardcoded em $VAULT — se repo mover, sync quebra silenciosamente
# - P3: logrotate só roda se log > 10MB, então se vault gerar < 10MB/semana, nunca roda (ok)
# - P4: Telegram notify usa curl; se curl falhar, não notifica (mas não impede sync)
# - P5: lock file em /tmp/sync-vault.lock — se /tmp for tmpfs (RAM), sobrevive reboot mas não disk failure

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="${SYNC_VAULT_REPO:-$HOME/GitHub/obsidian-vault}"
if [ -n "${SYNC_VAULT_LOG:-}" ]; then
    LOG="$SYNC_VAULT_LOG"
elif [ "$SCRIPT_DIR" = "$HOME/scripts" ]; then
    LOG="$HOME/scripts/sync-vault.log"
else
    LOG="$HOME/.logs/sync-vault.log"
fi
LOCK="/tmp/sync-vault.lock"
GBRAIN_BIN="${SYNC_VAULT_GBRAIN_BIN:-$HOME/.local/bin/gbrain}"
GBRAIN_SYNC_REPO="${SYNC_VAULT_GBRAIN_REPO:-$VAULT}"
GBRAIN_SYNC_ENABLED="${SYNC_VAULT_GBRAIN_SYNC:-1}"
GBRAIN_SYNC_LOG="${SYNC_VAULT_GBRAIN_LOG:-$HOME/.logs/gbrain-vault-sync.log}"
GBRAIN_SYNC_TIMEOUT_SECONDS="${SYNC_VAULT_GBRAIN_TIMEOUT_SECONDS:-240}"
GBRAIN_FAIL_STATE="${SYNC_VAULT_GBRAIN_FAIL_STATE:-$HOME/.cache/omni/gbrain-vault-sync.failures}"
GBRAIN_NOTIFY_AFTER="${SYNC_VAULT_GBRAIN_NOTIFY_AFTER:-3}"
TELEGRAM_BOT_TOKEN="${SYNC_VAULT_TG_BOT:-}"  # set em ~/.bashrc ou .env
TELEGRAM_CHAT_ID="${SYNC_VAULT_TG_CHAT:-}"  # chat_id do Giovanni pra alertas
MAX_LOG_SIZE_MB=10
MAX_LOG_FILES=5
MAX_RETRIES=3
GITLEAKS_REGEX='(api[_-]?key|token|secret|password|access[_-]?key|auth[_-]?key|client[_-]?secret)\s*[:=]\s*["'\''"]?[a-zA-Z0-9_/+=-]{20,}'
GITLEAKS_AWS_REGEX='AKIA[0-9A-Z]{16}'
GITLEAKS_GHP_REGEX='ghp_[a-zA-Z0-9]{36}'
GITLEAKS_SK_REGEX='sk-[a-zA-Z0-9]{20,}'

notify_telegram() {
    local msg="${1:-Sync failed on $(hostname) at $(date '+%H:%M:%S')}"
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        return 0  # not configured
    fi
    curl -sS -m 10 \
        -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="$TELEGRAM_CHAT_ID" \
        -d text="⚠️ sync-vault: $msg" \
        >/dev/null 2>&1
}

validate_vault_layout() {
    if [ ! -d "$VAULT/AiSecondBrain" ]; then
        echo "[$(date '+%H:%M')] FAIL: canonical vault missing: $VAULT/AiSecondBrain" >> "$LOG"
        notify_telegram "CANONICAL VAULT MISSING: $VAULT/AiSecondBrain on $(hostname)"
        exit 1
    fi

    if [ -e "$VAULT/Ideaverse" ] || [ -e "$VAULT/ideaverse" ]; then
        echo "[$(date '+%H:%M')] FAIL: legacy vault path exists; refusing sync before manual cleanup" >> "$LOG"
        notify_telegram "LEGACY VAULT PATH EXISTS: Ideaverse/ideaverse on $(hostname)"
        exit 1
    fi
}

record_gbrain_sync_success() {
    rm -f "$GBRAIN_FAIL_STATE" >/dev/null 2>&1 || true
}

record_gbrain_sync_failure() {
    local rc="${1:-1}"
    local count=0
    local notify_after="$GBRAIN_NOTIFY_AFTER"

    if [ -f "$GBRAIN_FAIL_STATE" ]; then
        count=$(cat "$GBRAIN_FAIL_STATE" 2>/dev/null || echo 0)
    fi
    case "$count" in
        ''|*[!0-9]*) count=0 ;;
    esac
    case "$notify_after" in
        ''|*[!0-9]*) notify_after=3 ;;
    esac

    count=$((count + 1))
    mkdir -p "$(dirname "$GBRAIN_FAIL_STATE")"
    printf '%s\n' "$count" > "$GBRAIN_FAIL_STATE"

    if [ "$count" -ge "$notify_after" ]; then
        notify_telegram "GBRAIN SYNC FAILED ${count}x (rc=$rc) on $(hostname)"
    fi

    printf '%s\n' "$count"
}

sync_gbrain_index() {
    local rc=0
    local failures=0
    local timeout_seconds="$GBRAIN_SYNC_TIMEOUT_SECONDS"

    if [ "$GBRAIN_SYNC_ENABLED" = "0" ]; then
        echo "[$(date '+%H:%M')] GBrain sync skipped: disabled by SYNC_VAULT_GBRAIN_SYNC=0" >> "$LOG"
        return 0
    fi

    if [ ! -x "$GBRAIN_BIN" ]; then
        echo "[$(date '+%H:%M')] GBrain sync skipped: executable not found at $GBRAIN_BIN" >> "$LOG"
        return 0
    fi

    case "$timeout_seconds" in
        ''|*[!0-9]*) timeout_seconds=240 ;;
    esac

    mkdir -p "$(dirname "$GBRAIN_SYNC_LOG")"
    echo "[$(date '+%H:%M')] GBrain sync start: $GBRAIN_SYNC_REPO" >> "$LOG"

    (
        echo "[$(date '+%Y-%m-%d %H:%M:%S%z')] start repo=$GBRAIN_SYNC_REPO timeout=${timeout_seconds}s"
        if command -v timeout >/dev/null 2>&1; then
            timeout "$timeout_seconds" "$GBRAIN_BIN" sync --repo "$GBRAIN_SYNC_REPO" --no-pull --yes --json
        else
            "$GBRAIN_BIN" sync --repo "$GBRAIN_SYNC_REPO" --no-pull --yes --json
        fi
        rc=$?
        echo "[$(date '+%Y-%m-%d %H:%M:%S%z')] exit=$rc"
        exit "$rc"
    ) >> "$GBRAIN_SYNC_LOG" 2>&1
    rc=$?

    if [ "$rc" -eq 0 ]; then
        record_gbrain_sync_success
        echo "[$(date '+%H:%M')] GBrain sync OK" >> "$LOG"
        return 0
    fi

    failures=$(record_gbrain_sync_failure "$rc")
    echo "[$(date '+%H:%M')] WARN: GBrain sync failed rc=$rc consecutive_failures=$failures log=$GBRAIN_SYNC_LOG" >> "$LOG"
    return "$rc"
}

auto_commit_changes() {
    local phase="${1:-local changes}"

    if ! git add -u >> "$LOG" 2>&1; then
        echo "[$(date '+%H:%M')] FAIL: git add -u ($phase)" >> "$LOG"
        notify_telegram "GIT ADD TRACKED FAILED on $(hostname)"
        exit 1
    fi

    tmp_untracked=$(mktemp)
    git ls-files -z --others --exclude-standard > "$tmp_untracked"
    if [ -s "$tmp_untracked" ]; then
        if ! git add --pathspec-from-file="$tmp_untracked" --pathspec-file-nul >> "$LOG" 2>&1; then
            rm -f "$tmp_untracked"
            echo "[$(date '+%H:%M')] FAIL: git add untracked ($phase)" >> "$LOG"
            notify_telegram "GIT ADD UNTRACKED FAILED on $(hostname)"
            exit 1
        fi
    fi
    rm -f "$tmp_untracked"

    if git diff --cached --quiet; then
        return 0
    fi

    secrets_found=""
    while IFS= read -r -d '' f; do
        if [ -f "$f" ]; then
            # Scan for common secret patterns
            if grep -qE "$GITLEAKS_REGEX" "$f" 2>/dev/null; then
                secrets_found="$secrets_found $f:generic"
            fi
            if grep -qE "$GITLEAKS_AWS_REGEX" "$f" 2>/dev/null; then
                secrets_found="$secrets_found $f:aws"
            fi
            if grep -qE "$GITLEAKS_GHP_REGEX" "$f" 2>/dev/null; then
                secrets_found="$secrets_found $f:github"
            fi
            if grep -qE "$GITLEAKS_SK_REGEX" "$f" 2>/dev/null; then
                secrets_found="$secrets_found $f:openai_sk"
            fi
        fi
    done < <(git diff --cached --name-only -z)
    if [ -n "$secrets_found" ]; then
        echo "[$(date '+%H:%M')] ABORT: secrets detected:$secrets_found" >> "$LOG"
        git reset HEAD >/dev/null 2>&1
        notify_telegram "SECRETS DETECTED:$secrets_found"
        exit 1
    fi

    count=$(git diff --cached --numstat | wc -l)
    if ! git commit -m "auto-sync: $(date '+%Y-%m-%d %H:%M')" >> "$LOG" 2>&1; then
        echo "[$(date '+%H:%M')] FAIL: git commit ($phase)" >> "$LOG"
        notify_telegram "GIT COMMIT FAILED on $(hostname)"
        exit 1
    fi
    echo "[$(date '+%H:%M')] Auto-committed ($phase): $count file(s)" >> "$LOG"
}

# === 0. Lock file (evita overlap) ===
exec 200>"$LOCK"
mkdir -p "$(dirname "$LOG")"
if ! flock -n 200; then
    echo "[$(date '+%H:%M')] SKIPPED: another sync in progress (lock held)" >> "$LOG"
    exit 0
fi

# === 1. Log rotation ===
log_size_mb=$(du -m "$LOG" 2>/dev/null | awk '{print $1}')
if [ "${log_size_mb:-0}" -gt "$MAX_LOG_SIZE_MB" ]; then
    # Rotaciona: log → log.1.gz, log.1.gz → log.2.gz, etc
    for i in $(seq $((MAX_LOG_FILES-1)) -1 1); do
        [ -f "$LOG.$i.gz" ] && mv "$LOG.$i.gz" "$LOG.$((i+1)).gz"
    done
    [ -f "$LOG" ] && gzip -k "$LOG" && mv "$LOG.gz" "$LOG.1.gz"
    # Cria log novo vazio
    : > "$LOG"
    echo "[$(date '+%H:%M')] Log rotated (was ${log_size_mb}MB)" >> "$LOG"
fi

cd "$VAULT" || {
    echo "[$(date '+%H:%M')] FAIL: cd $VAULT" >> "$LOG"
    notify_telegram
    exit 1
}
validate_vault_layout

# === 2. Auto-detect branch ===
# Tenta master, depois main, depois HEAD (caso local-only)
branch=$(git symbolic-ref --short HEAD 2>/dev/null)
if [ -z "$branch" ]; then
    branch="master"  # fallback
fi
if ! git fetch origin --prune >> "$LOG" 2>&1; then
    echo "[$(date '+%H:%M')] FAIL: git fetch origin" >> "$LOG"
    notify_telegram "FETCH FAILED for $branch on $(hostname)"
    exit 1
fi
# Se o origin não tem o branch atual, tenta alternar
if ! git rev-parse --verify "origin/$branch" >/dev/null 2>&1; then
    for alt in master main; do
        if git rev-parse --verify "origin/$alt" >/dev/null 2>&1; then
            branch="$alt"
            break
        fi
    done
fi
echo "[$(date '+%H:%M')] Using branch: $branch" >> "$LOG"

# === 3. Validate origin branch ===
remote=$(git rev-parse "origin/$branch" 2>/dev/null) || {
    echo "[$(date '+%H:%M')] FAIL: origin/$branch not found" >> "$LOG"
    notify_telegram "ORIGIN BRANCH NOT FOUND: $branch on $(hostname)"
    exit 1
}
local=$(git rev-parse HEAD)

# === 4. Detect local changes (tracked modified + untracked) ===
auto_commit_changes "initial scan"
local=$(git rev-parse HEAD)

# === 6. Reconcile local commits with origin ===
if ! git fetch origin --prune >> "$LOG" 2>&1; then
    echo "[$(date '+%H:%M')] FAIL: git fetch origin before reconcile" >> "$LOG"
    notify_telegram "FETCH BEFORE RECONCILE FAILED for $branch on $(hostname)"
    exit 1
fi
auto_commit_changes "pre-reconcile scan"
remote=$(git rev-parse "origin/$branch" 2>/dev/null) || {
    echo "[$(date '+%H:%M')] FAIL: origin/$branch not found before reconcile" >> "$LOG"
    notify_telegram "ORIGIN BRANCH NOT FOUND BEFORE RECONCILE: $branch on $(hostname)"
    exit 1
}
local=$(git rev-parse HEAD)
ahead=$(git rev-list --count "origin/$branch..HEAD" 2>/dev/null || echo 0)
behind=$(git rev-list --count "HEAD..origin/$branch" 2>/dev/null || echo 0)

if [ "${behind:-0}" -gt 0 ] && [ "${ahead:-0}" -gt 0 ]; then
    echo "[$(date '+%H:%M')] WARN: diverged from origin/$branch (ahead $ahead, behind $behind) — rebasing" >> "$LOG"
    if ! git rebase "origin/$branch" >> "$LOG" 2>&1; then
        git rebase --abort >/dev/null 2>&1 || true
        echo "[$(date '+%H:%M')] FAIL: rebase origin/$branch" >> "$LOG"
        notify_telegram "REBASE FAILED for $branch on $(hostname)"
        exit 1
    fi
    local=$(git rev-parse HEAD)
elif [ "${behind:-0}" -gt 0 ]; then
    if ! git reset --hard "origin/$branch" >> "$LOG" 2>&1; then
        echo "[$(date '+%H:%M')] FAIL: reset to origin/$branch" >> "$LOG"
        notify_telegram "RESET TO ORIGIN FAILED for $branch on $(hostname)"
        exit 1
    fi
    echo "[$(date '+%H:%M')] Reset to origin: ${remote:0:8}" >> "$LOG"
    local=$(git rev-parse HEAD)
fi

# === 7. Push if ahead (with retry) ===
remote=$(git rev-parse "origin/$branch" 2>/dev/null) || {
    echo "[$(date '+%H:%M')] FAIL: origin/$branch not found before push" >> "$LOG"
    notify_telegram "ORIGIN BRANCH NOT FOUND BEFORE PUSH: $branch on $(hostname)"
    exit 1
}
if [ "$local" != "$remote" ]; then
    if git log --format=%s "origin/$branch..HEAD" | grep -q .; then
        # Try push with backoff
        retry=0
        pushed=0
        while [ $retry -lt $MAX_RETRIES ]; do
            if git push origin "$branch" >> "$LOG" 2>&1; then
                echo "[$(date '+%H:%M')] Pushed: ${local:0:8}" >> "$LOG"
                pushed=1
                break
            fi
            retry=$((retry + 1))
            echo "[$(date '+%H:%M')] Push failed (retry $retry/$MAX_RETRIES)" >> "$LOG"
            if git fetch origin --prune >> "$LOG" 2>&1; then
                behind=$(git rev-list --count "HEAD..origin/$branch" 2>/dev/null || echo 0)
                if [ "${behind:-0}" -gt 0 ]; then
                    echo "[$(date '+%H:%M')] Remote advanced during push — rebasing before retry" >> "$LOG"
                    auto_commit_changes "pre-push-retry scan"
                    if ! git rebase "origin/$branch" >> "$LOG" 2>&1; then
                        git rebase --abort >/dev/null 2>&1 || true
                        echo "[$(date '+%H:%M')] FAIL: rebase before push retry" >> "$LOG"
                        notify_telegram "REBASE BEFORE PUSH RETRY FAILED for $branch on $(hostname)"
                        exit 1
                    fi
                    local=$(git rev-parse HEAD)
                fi
            fi
            sleep $((retry * 10))  # 10s, 20s, 30s
        done
        if [ $pushed -eq 0 ]; then
            echo "[$(date '+%H:%M')] FAIL: push after $MAX_RETRIES retries" >> "$LOG"
            notify_telegram "PUSH FAILED for $branch after $MAX_RETRIES retries on $(hostname)"
            exit 1
        fi
    fi
else
    echo "[$(date '+%H:%M')] Up-to-date: ${local:0:8}" >> "$LOG"
fi

if ! sync_gbrain_index; then
    exit 1
fi

# === 7. Notify on success if local had uncommitted state ===
# (já tá no log, sem necessidade extra)
