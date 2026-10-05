#!/usr/bin/env bash
# omni-fleet-sync.sh v2.0.0 - Governed Parallel Git Synchronization & Policy Enforcement Engine
# Managed by omni-srv-admin fleet governance. CPU <= 20%, flock protected, non-destructive.

set -eo pipefail

LOCK_FILE="/tmp/omni-fleet-sync.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync already running, skipping."; exit 0; }

USER_HOME="${HOME:-/home/$(id -un)}"
GITHUB_DIR="$USER_HOME/GitHub"
POLICY_FILE="/etc/omni/fleet-repositories.json"
if [ ! -f "$POLICY_FILE" ]; then
    POLICY_FILE="$GITHUB_DIR/omni-srv-admin/inventory/fleet-repositories.json"
fi
TARGET_REPO="${1:-all}"
CONCURRENCY_LIMIT=3

# 1. Resolve Host Identity
get_host_id() {
    local h
    h=$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo "unknown")
    case "$h" in
        atius-srv-1*) echo "atius-srv-1" ;;
        atius-srv-2*) echo "atius-srv-2" ;;
        atius-srv-3*) echo "atius-srv-3" ;;
        atius-srv-4*) echo "atius-srv-4" ;;
        horistic*)    echo "horistic-srv" ;;
        aln-srv*)     echo "aln-srv" ;;
        *wsl*|*W11*|*w11*|*GIOVANNI*) echo "giovanni-w11-wsl" ;;
        *) echo "$h" ;;
    esac
}

HOST_ID=$(get_host_id)

# 2. Policy Enforcement & Authorization Check
# Returns:
#   0: ALLOWED
#   1: FORBIDDEN (must purge / reject)
#   2: NOT TARGETED (skip sync)
check_policy() {
    local rname="$1"
    local hid="$2"

    if [ ! -f "$POLICY_FILE" ]; then
        if [[ "$hid" =~ ^(horistic-srv|aln-srv)$ ]] && [[ "$rname" =~ ^(oci-admin|omni-srv-admin)$ ]]; then
            return 1 # Explicitly forbidden on partner hosts
        fi
        return 0
    fi

    python3 -c "
import json, sys
rname = sys.argv[1]
hid = sys.argv[2]
pfile = sys.argv[3]

try:
    with open(pfile, 'r') as f:
        policy = json.load(f)
    repos = policy.get('repositories', {})
    info = repos.get(rname)
    if not info:
        for k, v in repos.items():
            if rname in v.get('aliases', []):
                info = v
                break
    if not info:
        sys.exit(0) # Unlisted repo: allowed by default

    forbidden = info.get('forbidden_hosts', [])
    if hid in forbidden:
        sys.exit(1) # Explicitly forbidden!

    allowed = info.get('allowed_hosts', [])
    if 'all' in allowed or hid in allowed:
        sys.exit(0) # Allowed!

    sys.exit(2) # Not allowed on this host
except Exception:
    sys.exit(0)
" "$rname" "$hid" "$POLICY_FILE"
}

# 3. Dynamic Repository Discovery
discover_repos() {
    local found=()
    if [ -d "$GITHUB_DIR" ]; then
        for d in "$GITHUB_DIR"/*; do
            if [ -d "$d/.git" ]; then
                found+=("$(basename "$d")")
            fi
        done
    fi
    echo "${found[@]}"
}

# 4. Sync Individual Repository
sync_repo() {
    local repo_name="$1"
    local repo_dir="$GITHUB_DIR/$repo_name"

    # Policy Enforcement Check
    local policy_status=0
    check_policy "$repo_name" "$HOST_ID" || policy_status=$?

    if [ "$policy_status" -eq 1 ]; then
        echo "[POLICY VIOLATION] Repositório '$repo_name' é PROIBIDO no host '$HOST_ID'!"
        if [ -d "$repo_dir" ]; then
            echo "[POLICY ENFORCE] Removendo repositório proibido '$repo_name' de $GITHUB_DIR..."
            rm -rf "$repo_dir"
            echo "[POLICY OK] '$repo_name' expurgado com sucesso deste nó."
        fi
        return 0
    elif [ "$policy_status" -eq 2 ]; then
        echo "[POLICY SKIP] Repositório '$repo_name' não está alocado para o host '$HOST_ID'. Pulando."
        return 0
    fi

    if [ ! -d "$repo_dir/.git" ]; then
        if [ "$TARGET_REPO" = "$repo_name" ] || [ "$repo_name" = "oci-admin" ] || [ "$repo_name" = "omni-srv-admin" ]; then
            echo "[INFO] Repositório '$repo_name' ausente em $GITHUB_DIR, mas autorizado para '$HOST_ID'. Clonando..."
            mkdir -p "$GITHUB_DIR"
            if git clone "https://github.com/giovannimnz/$repo_name.git" "$repo_dir" 2>&1; then
                echo "[OK] '$repo_name' provisionado e clonado com sucesso em $repo_dir."
                return 0
            else
                echo "[WARN] Falha ao clonar '$repo_name'."
                return 1
            fi
        fi
        return 0
    fi

    cd "$repo_dir"
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    if [ "$branch" = "HEAD" ] || [ -z "$branch" ]; then
        branch="main"
    fi

    # Fetch remote prune with CPU quota containment
    if ! git fetch origin --prune 2>/dev/null; then
        echo "[WARN] git fetch falhou para $repo_name."
        return 1
    fi

    local local_sha remote_sha
    local_sha=$(git rev-parse HEAD 2>/dev/null || echo "")
    remote_sha=$(git rev-parse "origin/$branch" 2>/dev/null || echo "")

    if [ -z "$remote_sha" ]; then
        return 0
    fi

    if [ "$local_sha" = "$remote_sha" ]; then
        echo "[OK] $repo_name atualizado (${local_sha:0:8}) no branch $branch."
        return 0
    fi

    local behind ahead
    behind=$(git rev-list "HEAD..origin/$branch" --count 2>/dev/null || echo "0")
    ahead=$(git rev-list "origin/$branch..HEAD" --count 2>/dev/null || echo "0")

    echo "[INFO] $repo_name status: behind $behind, ahead $ahead"

    if [ "$behind" -gt 0 ] && [ "$ahead" -eq 0 ]; then
        if git diff-index --quiet HEAD -- 2>/dev/null; then
            echo "[INFO] Fast-forwarding $repo_name para origin/$branch..."
            git pull --ff-only origin "$branch" 2>&1 || git reset --hard "origin/$branch"
            echo "[OK] $repo_name atualizado com sucesso."
        else
            echo "[INFO] $repo_name tem edicoes locais pendentes. Preservando com autostash..."
            git stash push -u -m "auto-sync-stash-$(date +%s)" 2>/dev/null || true
            git pull --ff-only origin "$branch" 2>&1 || git reset --hard "origin/$branch"
            git stash pop 2>/dev/null || true
            echo "[OK] $repo_name atualizado com alteracoes locais preservadas."
        fi
    elif [ "$behind" -gt 0 ] && [ "$ahead" -gt 0 ]; then
        echo "[INFO] $repo_name divergiu (ahead $ahead, behind $behind). Mesclando origin/$branch..."
        git merge "origin/$branch" --no-edit -m "merge: auto-sync fleet merge from origin/$branch" || {
            echo "[ERR] Conflito de merge em $repo_name! Abortando para evitar corrupcao."
            git merge --abort 2>/dev/null || true
            return 1
        }
        echo "[OK] Divergencia mesclada com sucesso em $repo_name."
    elif [ "$behind" -eq 0 ] && [ "$ahead" -gt 0 ]; then
        echo "[OK] $repo_name adiante do remoto por $ahead commit(s). Commits locais preservados."
    fi
}

# 5. Parallel Worker Execution
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] Iniciando Omni Fleet Sync no host: $HOST_ID (Alvo: $TARGET_REPO)"

if [ "$TARGET_REPO" != "all" ]; then
    sync_repo "$TARGET_REPO" || true
else
    # Discover all repositories in ~/GitHub
    REPOS=($(discover_repos))
    echo "[INFO] Repositorios descobertos em $GITHUB_DIR: ${REPOS[*]}"

    # Run in parallel with concurrency cap
    pids=()
    for repo in "${REPOS[@]}"; do
        (
            sync_repo "$repo"
        ) &
        pids+=($!)

        if [ ${#pids[@]} -ge $CONCURRENCY_LIMIT ]; then
            wait -n 2>/dev/null || wait "${pids[0]}"
            new_pids=()
            for pid in "${pids[@]}"; do
                if kill -0 "$pid" 2>/dev/null; then
                    new_pids+=("$pid")
                fi
            done
            pids=("${new_pids[@]}")
        fi
    done

    # Wait for all remaining jobs
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [OK] Omni Fleet Sync concluido com sucesso no host $HOST_ID."
