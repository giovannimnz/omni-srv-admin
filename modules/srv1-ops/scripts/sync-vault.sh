#!/bin/bash
# v5.1-omni: gitleaks-aware + lock + branch auto + telegram notify + logrotate
# Managed by: ~/GitHub/omni-srv-admin/modules/srv1-ops/
# Runs every 5 min on SRV-1, SRV-2, SRV-3 (escalonado 0s/45s/90s)
#
# Melhorias v5.0 sobre v4.1:
# 1. Pre-push hook gitleaks-like (regex robusta, evita leak de secrets)
# 2. Lock file com flock (evita overlap se sync demorar)
# 3. Auto-detect branch (master vs main baseado no origin)
# 4. Notificação Telegram se sync falhar 3 ciclos consecutivos
# 5. Log rotation (gzip quando log > 10MB, manter últimos 5)
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
    > "$LOG"
    echo "[$(date '+%H:%M')] Log rotated (was ${log_size_mb}MB)" >> "$LOG"
fi

cd "$VAULT" || {
    echo "[$(date '+%H:%M')] FAIL: cd $VAULT" >> "$LOG"
    notify_telegram
    exit 1
}

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

# === 7. Notify on success if local had uncommitted state ===
# (já tá no log, sem necessidade extra)
