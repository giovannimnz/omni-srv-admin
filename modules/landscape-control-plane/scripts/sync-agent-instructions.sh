#!/usr/bin/env bash
# ==============================================================================
# Script: sync-agent-instructions.sh
# Purpose: Synchronize canonical AI agent instructions, skills, Landscape directives,
#          and install recurring systemd auto-sync timer across all fleet hosts.
# Managed: Omni Landscape Control Plane
# ==============================================================================
set -euo pipefail

LANDSCAPE_DIRECTIVE_BLOCK='## Canonical Fleet Operations & Landscape Control-Plane Directive

- **Regra Mandatória para Múltiplos Servidores / Frota:** SEMPRE que qualquer operação, atualização, diagnóstico, instalação de pacotes APT, sincronização de arquivos, verificação ou execução envolver mais de um servidor (`atius-srv-1`, `atius-srv-2`, `atius-srv-3`, `atius-srv-4`, `horistic-srv`), NUNCA execute loops manuais seriais de SSH se a operação puder ser executada via **Landscape Control-Plane**.
- **Comando Canônico de Execução Simultânea:**
  ```bash
  omni landscape run <script-id> --hosts all --wait --yes
  ```
  - Executa simultaneamente em todos os 5 nós da frota via Landscape Server self-hosted (`atius-srv-3`).
  - Coleta e agrega status (`undelivered`, `in-progress`, `delivered`, `succeeded`), stdout, stderr e exit codes em tempo real.
  - Para subconjunto de hosts, use `--hosts atius-srv-1,atius-srv-2...` ou `--query <custom-query>`.
- **Scripts Versionados e Manifesto:**
  - Diretório: `/home/ubuntu/GitHub/omni-srv-admin/modules/landscape-control-plane/scripts/`
  - Manifesto: `/home/ubuntu/GitHub/omni-srv-admin/modules/landscape-control-plane/scripts/manifest.json`
  - Para novo script: salve no diretório, adicione ao `manifest.json`, sincronize com `omni landscape scripts push <script-id> --yes` e dispare com `omni landscape run <script-id> --hosts all --wait --yes`.
- **Comandos de Suporte e Inventário:**
  - Listar computadores registrados: `omni landscape computers`
  - Status da integração: `omni landscape status`
  - Listar scripts cadastrados: `omni landscape scripts list`
  - Consultar atividades: `omni landscape activities`
- **Gatilhos de Acionamento Automático:**
  - Palavras-chave: `em todos os servidores`, `nos servidores 1 a 4`, `na frota`, `fleet-wide`, `multi-host`, `multi-servidor`, `todos os hosts`, `atualizar servidores`, `instalar em todos`, `status da frota`, `diagnóstico em massa`.
  - Skill canônica associada: `atius-fleet-landscape-ops` (`~/.gemini/config/skills/atius-fleet-landscape-ops/SKILL.md`).
- **Conectividade OCI DRG:** Todo tráfego Landscape trafega pela rota direta privada OCI DRG (`10.13.1.13 landscape.atius.com.br`) com latência sub-milissegundo (~0.6 ms) sem custos de egress.'

# ─── 1. Cria script daemon autônomo de sincronização ──────────────────────────
cat << 'RUNTIMESYNC' > /usr/local/bin/omni-fleet-runtime-sync.sh
#!/usr/bin/env bash
# Omni Fleet AI Runtime & Skills Auto-Sync
set -euo pipefail

CANONICAL_HOST="10.11.1.11"
LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

for TARGET_USER in ubuntu horistic; do
    if ! id "${TARGET_USER}" >/dev/null 2>&1; then
        continue
    fi
    TARGET_HOME="$(eval echo ~${TARGET_USER})"
    GEMINI_CONFIG="${TARGET_HOME}/.gemini/config"
    AGENTS_MD="${GEMINI_CONFIG}/AGENTS.md"
    SKILLS_DIR="${GEMINI_CONFIG}/skills"

    mkdir -p "${GEMINI_CONFIG}" "${SKILLS_DIR}"

    # Sincroniza AGENTS.md e skills se não for o host canônico srv-1
    if [ "${LOCAL_IP}" != "${CANONICAL_HOST}" ] && [ "$(hostname)" != "atius-srv-1" ]; then
        if su -s /bin/bash "${TARGET_USER}" -c "scp -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=accept-new ubuntu@${CANONICAL_HOST}:~/.gemini/config/AGENTS.md ${AGENTS_MD}.tmp" 2>/dev/null; then
            mv "${AGENTS_MD}.tmp" "${AGENTS_MD}"
            chown "${TARGET_USER}:${TARGET_USER}" "${AGENTS_MD}"
        fi

        LOCAL_COUNT="$(find "${SKILLS_DIR}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
        if [ "${LOCAL_COUNT}" -lt 315 ]; then
            if su -s /bin/bash "${TARGET_USER}" -c "scp -o ConnectTimeout=20 -o BatchMode=yes -o StrictHostKeyChecking=accept-new ubuntu@${CANONICAL_HOST}:~/.gemini/config/fleet-skills.tar.gz /tmp/fleet-skills.tar.gz" 2>/dev/null; then
                tar -xzf /tmp/fleet-skills.tar.gz -C "${GEMINI_CONFIG}/"
                rm -f /tmp/fleet-skills.tar.gz
                chown -R "${TARGET_USER}:${TARGET_USER}" "${SKILLS_DIR}"
            fi
        fi
    fi

    # Symlinks canônicos — AGENTS.md atende todos os runtimes (Antigravity, Codex, Claude)
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

    # Remove redundâncias: se tem AGENTS.md não precisa de GEMINI.md/CLAUDE.md/CODEX.md
    rm -f \
        "${TARGET_HOME}/GEMINI.md" \
        "${TARGET_HOME}/CLAUDE.md" \
        "${TARGET_HOME}/CODEX.md" \
        "${TARGET_HOME}/.codex/CODEX.md" \
        "${TARGET_HOME}/.claude/CLAUDE.md" \
        "${TARGET_HOME}/.gemini/GEMINI.md" \
        "${TARGET_HOME}/.gemini/config/GEMINI.md"

    # .agents/AGENTS.md include
    AGENTS_SUB_DIR="${TARGET_HOME}/.agents"
    if [ -d "${AGENTS_SUB_DIR}" ]; then
        AGENTS_SUB_FILE="${AGENTS_SUB_DIR}/AGENTS.md"
        if [ ! -f "${AGENTS_SUB_FILE}" ] || ! grep -q "@${AGENTS_MD}" "${AGENTS_SUB_FILE}"; then
            echo "@${AGENTS_MD}" | cat - "${AGENTS_SUB_FILE}" 2>/dev/null > "${AGENTS_SUB_FILE}.tmp" || echo "@${AGENTS_MD}" > "${AGENTS_SUB_FILE}.tmp"
            mv "${AGENTS_SUB_FILE}.tmp" "${AGENTS_SUB_FILE}"
        fi
    fi

    # Sincronizar repositório omni-srv-admin se presente
    REPO_DIR="${TARGET_HOME}/GitHub/omni-srv-admin"
    if [ -d "${REPO_DIR}/.git" ]; then
        su -s /bin/bash "${TARGET_USER}" -c "cd '${REPO_DIR}' && git pull --ff-only origin main" 2>/dev/null || true
    fi

    chown -R "${TARGET_USER}:${TARGET_USER}" "${GEMINI_CONFIG}" 2>/dev/null || true
done
RUNTIMESYNC
chmod +x /usr/local/bin/omni-fleet-runtime-sync.sh

# ─── 2. Configura e ativa systemd service & timer ──────────────────────────────
cat << 'SERVICE' > /etc/systemd/system/omni-fleet-runtime-sync.service
[Unit]
Description=Omni Fleet AI Runtime and Skills Synchronization
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/omni-fleet-runtime-sync.sh
Nice=19
IOSchedulingClass=best-effort
IOSchedulingPriority=7

[Install]
WantedBy=multi-user.target
SERVICE

cat << 'TIMER' > /etc/systemd/system/omni-fleet-runtime-sync.timer
[Unit]
Description=Run Omni Fleet AI Runtime and Skills Synchronization every 2 hours
After=network.target

[Timer]
OnBootSec=5min
OnUnitActiveSec=2h
Persistent=true

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload
systemctl enable --now omni-fleet-runtime-sync.timer

# ─── 3. Execução imediata no host atual ───────────────────────────────────────
/usr/local/bin/omni-fleet-runtime-sync.sh

echo "[SUCCESS] Instruction and skills auto-sync timer active on $(hostname)"
