#!/usr/bin/env bash
# ==============================================================================
# Script: sync-agent-instructions.sh
# Purpose: Synchronize canonical AI agent instructions, skills, agents, and modular rules
#          across all fleet hosts via multilateral Any-to-All Git state machine,
#          and install recurring systemd auto-sync timer (15 min) across all fleet hosts.
# Managed: Omni Landscape Control Plane
# Version: 2.1.0
# ==============================================================================
set -euo pipefail
export GIT_TERMINAL_PROMPT=0
export GCM_INTERACTIVE=never

# ─── 1. Cria script daemon autônomo de sincronização ──────────────────────────
cat << 'RUNTIMESYNC' > /usr/local/bin/omni-fleet-runtime-sync.sh
#!/usr/bin/env bash
# Omni Fleet AI Runtime & Skills Auto-Sync v2.1.0 (Multilateral Any-to-All)
set -euo pipefail

export GIT_TERMINAL_PROMPT=0
export GCM_INTERACTIVE=never

# Trava de exclusão mútua contra concorrência entre timer systemd e Landscape
LOCK_FILE="/var/lock/omni-fleet-runtime-sync.lock"
exec 200>"${LOCK_FILE}"
if ! flock -n 200; then
    echo "[WARN] Another sync worker instance is already running (${LOCK_FILE}). Skipping this cycle."
    exit 0
fi

HOST_NAME="$(hostname -s 2>/dev/null || hostname)"
REMOTE_REPO_URL="https://github.com/giovannimnz/omni-agent-runtime.git"

for TARGET_USER in ubuntu horistic muniz; do
    if ! id "${TARGET_USER}" >/dev/null 2>&1; then
        continue
    fi
    TARGET_HOME="$(eval echo ~${TARGET_USER})"
    RUNTIME_REPO="${TARGET_HOME}/.local/share/omni-agent-runtime"
    GEMINI_CONFIG="${TARGET_HOME}/.gemini/config"
    AGENTS_DIR="${TARGET_HOME}/.agents"
    AGENTS_MD="${GEMINI_CONFIG}/AGENTS.md"

    mkdir -p "${TARGET_HOME}/.local/share" "${GEMINI_CONFIG}" "${AGENTS_DIR}"

    # A. Bootstrap/Clonagem do Repositório Canônico se não existir
    if [ ! -d "${RUNTIME_REPO}/.git" ]; then
        if su -s /bin/bash "${TARGET_USER}" -c "git clone --quiet '${REMOTE_REPO_URL}' '${RUNTIME_REPO}'" 2>/dev/null; then
            echo "[INFO] Cloned omni-agent-runtime for ${TARGET_USER}"
        else
            # Inicialização local se clone remoto falhar (offline/sem acesso ainda)
            mkdir -p "${RUNTIME_REPO}/skills" "${RUNTIME_REPO}/agents" "${RUNTIME_REPO}/rules/core" "${RUNTIME_REPO}/rules/platform-linux"
            if [ -d "${GEMINI_CONFIG}/skills" ] && [ ! -L "${GEMINI_CONFIG}/skills" ]; then
                cp -rn "${GEMINI_CONFIG}/skills/"* "${RUNTIME_REPO}/skills/" 2>/dev/null || true
            fi
            if [ -d "${GEMINI_CONFIG}/agents" ] && [ ! -L "${GEMINI_CONFIG}/agents" ]; then
                cp -rn "${GEMINI_CONFIG}/agents/"* "${RUNTIME_REPO}/agents/" 2>/dev/null || true
            fi
            # V2 FIX: Chown imediato para evitar Permission Denied no git init executado pelo TARGET_USER
            chown -R "${TARGET_USER}:${TARGET_USER}" "${RUNTIME_REPO}"
            su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git init -b main --quiet && git config user.name 'Omni Runtime Sync' && git config user.email 'runtime-sync@atius.com.br' && git remote add origin '${REMOTE_REPO_URL}' 2>/dev/null || true"
            if [ -n "$(su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git status --porcelain" 2>/dev/null)" ]; then
                su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git add -A && git commit -m 'init(${HOST_NAME}): bootstrap local runtime' --quiet" 2>/dev/null || true
            fi
        fi
    fi

    # B. Máquina de Estados Git Multilateral Any-to-All
    if [ -d "${RUNTIME_REPO}/.git" ]; then
        # 0. Self-Heal: Abortar rebase pendente de execuções anteriores interrompidas
        if [ -d "${RUNTIME_REPO}/.git/rebase-merge" ] || [ -d "${RUNTIME_REPO}/.git/rebase-apply" ]; then
            echo "[WARN] Dirty rebase detected in ${RUNTIME_REPO}. Executing self-heal git rebase --abort..."
            su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git rebase --abort" 2>/dev/null || true
            rm -rf "${RUNTIME_REPO}/.git/rebase-merge" "${RUNTIME_REPO}/.git/rebase-apply" 2>/dev/null || true
        fi

        # 1. Commit de alterações locais
        DIRTY="$(su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git status --porcelain" 2>/dev/null || true)"
        if [ -n "${DIRTY}" ]; then
            COMMIT_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
            su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git add -A && git commit -m 'sync(${HOST_NAME}): ${COMMIT_TS}' --quiet" 2>/dev/null || true
        fi

        # 2. Fetch e Rebase contra origin main
        HAS_ORIGIN="$(su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git remote" 2>/dev/null | grep -E '^origin$' || true)"
        if [ -n "${HAS_ORIGIN}" ]; then
            if su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git fetch origin main --quiet" 2>/dev/null; then
                if su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git pull --rebase origin main --quiet" 2>/dev/null; then
                    # 3. Push de commits pendentes (Safe parsing & retry com quarentena)
                    UNPUSHED_RAW="$(su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git rev-list origin/main..HEAD --count 2>/dev/null" 2>/dev/null || echo 0)"
                    UNPUSHED="${UNPUSHED_RAW//[[:space:]]/}"
                    if [[ "${UNPUSHED:-0}" =~ ^[0-9]+$ ]] && [ "${UNPUSHED:-0}" -gt 0 ]; then
                        if ! su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git push origin main --quiet" 2>/dev/null; then
                            echo "[WARN] Push rejected for ${TARGET_USER}. Retrying with fast rebase..."
                            if su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git pull --rebase origin main --quiet" 2>/dev/null; then
                                su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git push origin main --quiet" 2>/dev/null || echo "[WARN] Push retry failed for ${TARGET_USER}."
                            else
                                # Conflito no retry rebase: contingência idêntica ao rebase primário
                                su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git rebase --abort" 2>/dev/null || true
                                CONFLICT_BRANCH="conflict-${HOST_NAME}-$(date +%s)"
                                su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git branch '${CONFLICT_BRANCH}' && git reset --hard origin/main" 2>/dev/null || true
                                echo "[WARN] Retry rebase conflict in ${HOST_NAME} (${TARGET_USER}) quarantined to branch: ${CONFLICT_BRANCH}"
                            fi
                        fi
                    fi
                else
                    # CONFLITO DETECTADO: Quarentena não-bloqueante
                    su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git rebase --abort" 2>/dev/null || true
                    CONFLICT_BRANCH="conflict-${HOST_NAME}-$(date +%s)"
                    su -s /bin/bash "${TARGET_USER}" -c "cd '${RUNTIME_REPO}' && git branch '${CONFLICT_BRANCH}' && git reset --hard origin/main" 2>/dev/null || true
                    echo "[WARN] Conflict in ${HOST_NAME} quarantined to branch: ${CONFLICT_BRANCH}"
                fi
            fi
        fi
    fi

    # C. Padronização de Symlinks (skills e agents)
    # Skills
    if [ -e "${GEMINI_CONFIG}/skills" ] && [ ! -L "${GEMINI_CONFIG}/skills" ]; then
        rm -rf "${GEMINI_CONFIG}/skills"
    fi
    ln -sfn "${RUNTIME_REPO}/skills" "${GEMINI_CONFIG}/skills"

    if [ -e "${AGENTS_DIR}/skills" ] && [ ! -L "${AGENTS_DIR}/skills" ]; then
        rm -rf "${AGENTS_DIR}/skills"
    fi
    ln -sfn "${RUNTIME_REPO}/skills" "${AGENTS_DIR}/skills"

    # Agents
    if [ -d "${RUNTIME_REPO}/agents" ]; then
        if [ -e "${GEMINI_CONFIG}/agents" ] && [ ! -L "${GEMINI_CONFIG}/agents" ]; then
            rm -rf "${GEMINI_CONFIG}/agents"
        fi
        ln -sfn "${RUNTIME_REPO}/agents" "${GEMINI_CONFIG}/agents"

        if [ -e "${AGENTS_DIR}/agents" ] && [ ! -L "${AGENTS_DIR}/agents" ]; then
            rm -rf "${AGENTS_DIR}/agents"
        fi
        ln -sfn "${RUNTIME_REPO}/agents" "${AGENTS_DIR}/agents"
    fi

    # D. Compilação Modular de AGENTS.md (core + platform-linux)
    RULES_CORE="${RUNTIME_REPO}/rules/core"
    RULES_LINUX="${RUNTIME_REPO}/rules/platform-linux"
    if [ -d "${RULES_CORE}" ]; then
        COMPILED_TMP="${AGENTS_MD}.tmp"
        > "${COMPILED_TMP}"
        for rf in "${RULES_CORE}"/*.md; do
            if [ -f "${rf}" ]; then
                cat "${rf}" >> "${COMPILED_TMP}"
                echo -e "\n" >> "${COMPILED_TMP}"
            fi
        done
        if [ -d "${RULES_LINUX}" ]; then
            for rf in "${RULES_LINUX}"/*.md; do
                if [ -f "${rf}" ]; then
                    cat "${rf}" >> "${COMPILED_TMP}"
                    echo -e "\n" >> "${COMPILED_TMP}"
                fi
            done
        fi
        # V1 FIX: Valida se o arquivo compilado não está vazio antes de sobrescrever AGENTS.md
        if [ -s "${COMPILED_TMP}" ]; then
            mv "${COMPILED_TMP}" "${AGENTS_MD}"
            chown "${TARGET_USER}:${TARGET_USER}" "${AGENTS_MD}"
        else
            rm -f "${COMPILED_TMP}"
            echo "[WARN] Compiled rules empty for ${TARGET_USER}. Preserving existing AGENTS.md"
        fi
    fi

    # E. Symlinks Canônicos de AGENTS.md (Antigravity, Codex, Claude)
    LINKS=(
        "${TARGET_HOME}/AGENTS.md"
        "${TARGET_HOME}/.codex/AGENTS.md"
        "${TARGET_HOME}/.gemini/AGENTS.md"
        "${TARGET_HOME}/.claude/AGENTS.md"
    )

    for link in "${LINKS[@]}"; do
        parent_dir="$(dirname "${link}")"
        if [ -d "${parent_dir}" ] || [ "${parent_dir}" = "${TARGET_HOME}" ]; then
            mkdir -p "${parent_dir}"
            rm -f "${link}"
            ln -sf "${AGENTS_MD}" "${link}"
        fi
    done

    # Remove redundâncias legadas
    rm -f \
        "${TARGET_HOME}/GEMINI.md" \
        "${TARGET_HOME}/CLAUDE.md" \
        "${TARGET_HOME}/CODEX.md" \
        "${TARGET_HOME}/.codex/CODEX.md" \
        "${TARGET_HOME}/.claude/CLAUDE.md" \
        "${TARGET_HOME}/.gemini/GEMINI.md" \
        "${TARGET_HOME}/.gemini/config/GEMINI.md"

    # .agents/AGENTS.md include
    if [ -d "${AGENTS_DIR}" ]; then
        AGENTS_SUB_FILE="${AGENTS_DIR}/AGENTS.md"
        if [ ! -f "${AGENTS_SUB_FILE}" ] || ! grep -q "@${AGENTS_MD}" "${AGENTS_SUB_FILE}"; then
            echo "@${AGENTS_MD}" | cat - "${AGENTS_SUB_FILE}" 2>/dev/null > "${AGENTS_SUB_FILE}.tmp" || echo "@${AGENTS_MD}" > "${AGENTS_SUB_FILE}.tmp"
            mv "${AGENTS_SUB_FILE}.tmp" "${AGENTS_SUB_FILE}"
        fi
    fi

    # F. Sincronizar repositório omni-srv-admin APENAS se permitido por política (R6)
    if [ "${HOST_NAME}" != "horistic-srv" ] && [ "${HOST_NAME}" != "aln-srv" ] && [ "${TARGET_USER}" != "horistic" ]; then
        REPO_DIR="${TARGET_HOME}/GitHub/omni-srv-admin"
        if [ -d "${REPO_DIR}/.git" ]; then
            su -s /bin/bash "${TARGET_USER}" -c "cd '${REPO_DIR}' && git pull --ff-only origin main" 2>/dev/null || true
        fi
    fi

    chown -R "${TARGET_USER}:${TARGET_USER}" "${RUNTIME_REPO}" 2>/dev/null || true
    chown -R "${TARGET_USER}:${TARGET_USER}" "${GEMINI_CONFIG}" 2>/dev/null || true
    chown -R "${TARGET_USER}:${TARGET_USER}" "${AGENTS_DIR}" 2>/dev/null || true
done
RUNTIMESYNC
chmod +x /usr/local/bin/omni-fleet-runtime-sync.sh

# ─── 2. Configura e ativa systemd service & timer (15 minutos) ─────────────────
cat << 'SERVICE' > /etc/systemd/system/omni-fleet-runtime-sync.service
[Unit]
Description=Omni Fleet AI Runtime and Skills Synchronization
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/omni-fleet-runtime-sync.sh
Environment="GIT_TERMINAL_PROMPT=0"
Environment="GCM_INTERACTIVE=never"
Nice=19
IOSchedulingClass=best-effort
IOSchedulingPriority=7
CPUQuota=20%

[Install]
WantedBy=multi-user.target
SERVICE

cat << 'TIMER' > /etc/systemd/system/omni-fleet-runtime-sync.timer
[Unit]
Description=Run Omni Fleet AI Runtime and Skills Synchronization every 15 minutes
After=network.target

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
TIMER

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
    systemctl enable --now omni-fleet-runtime-sync.timer || true
fi

# ─── 3. Execução imediata no host atual ───────────────────────────────────────
/usr/local/bin/omni-fleet-runtime-sync.sh

echo "[SUCCESS] Any-to-All instruction and skills auto-sync timer (15m) active on $(hostname)"
