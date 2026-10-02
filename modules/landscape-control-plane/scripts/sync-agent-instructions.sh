#!/usr/bin/env bash
# ==============================================================================
# Script: sync-agent-instructions.sh
# Purpose: Synchronize canonical AI agent instructions and Landscape directives
#          across all fleet hosts via Landscape ExecuteScript.
# Managed: Omni Landscape Control Plane
# ==============================================================================
set -euo pipefail

# Determine target non-root user
if id horistic >/dev/null 2>&1; then
    TARGET_USER="horistic"
    TARGET_HOME="/home/horistic"
elif id ubuntu >/dev/null 2>&1; then
    TARGET_USER="ubuntu"
    TARGET_HOME="/home/ubuntu"
else
    echo "[!] Neither horistic nor ubuntu user found"
    exit 1
fi

echo "[*] Target user: ${TARGET_USER} (${TARGET_HOME})"

GEMINI_CONFIG_DIR="${TARGET_HOME}/.gemini/config"
AGENTS_MD="${GEMINI_CONFIG_DIR}/AGENTS.md"

mkdir -p "${GEMINI_CONFIG_DIR}"

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

# Inject or replace directive in AGENTS.md
if [ -f "${AGENTS_MD}" ]; then
    if grep -q "Canonical Fleet Operations & Landscape Control-Plane Directive" "${AGENTS_MD}"; then
        echo "[*] Landscape directive already present in ${AGENTS_MD}"
    else
        echo "[*] Injecting Landscape directive into ${AGENTS_MD}..."
        # Inject right before CPU Guardrail or at the end
        if grep -q "## CPU Guardrail" "${AGENTS_MD}"; then
            python3 -c "
with open('${AGENTS_MD}', 'r') as f:
    content = f.read()

directive = '''${LANDSCAPE_DIRECTIVE_BLOCK}

'''
if '## CPU Guardrail' in content:
    content = content.replace('## CPU Guardrail', directive + '## CPU Guardrail', 1)
else:
    content += '\n\n' + directive

with open('${AGENTS_MD}', 'w') as f:
    f.write(content)
"
            echo "[OK] Injected before CPU Guardrail"
        else
            printf "\n\n%s\n" "${LANDSCAPE_DIRECTIVE_BLOCK}" >> "${AGENTS_MD}"
            echo "[OK] Appended to AGENTS.md"
        fi
    fi
else
    echo "[!] ${AGENTS_MD} not found, creating from template..."
    printf "# Antigravity Global Runtime\n\n%s\n" "${LANDSCAPE_DIRECTIVE_BLOCK}" > "${AGENTS_MD}"
fi

# Ensure canonical symlinks
LINKS=(
    "${TARGET_HOME}/AGENTS.md"
    "${TARGET_HOME}/GEMINI.md"
    "${TARGET_HOME}/CLAUDE.md"
    "${TARGET_HOME}/CODEX.md"
    "${TARGET_HOME}/.codex/AGENTS.md"
    "${TARGET_HOME}/.codex/CODEX.md"
    "${TARGET_HOME}/.claude/CLAUDE.md"
    "${TARGET_HOME}/.gemini/AGENTS.md"
    "${TARGET_HOME}/.gemini/GEMINI.md"
    "${TARGET_HOME}/.gemini/config/GEMINI.md"
)

for link in "${LINKS[@]}"; do
    parent_dir="$(dirname "${link}")"
    if [ -d "${parent_dir}" ] || [ "${parent_dir}" = "${TARGET_HOME}" ]; then
        mkdir -p "${parent_dir}"
        rm -f "${link}"
        ln -sf "${AGENTS_MD}" "${link}"
        echo "  [LINK] ${link} -> ${AGENTS_MD}"
    fi
done

# Ensure .agents/AGENTS.md has include
AGENTS_SUB_DIR="${TARGET_HOME}/.agents"
if [ -d "${AGENTS_SUB_DIR}" ]; then
    AGENTS_SUB_FILE="${AGENTS_SUB_DIR}/AGENTS.md"
    if [ ! -f "${AGENTS_SUB_FILE}" ] || ! grep -q "@${AGENTS_MD}" "${AGENTS_SUB_FILE}"; then
        echo "@${AGENTS_MD}" | cat - "${AGENTS_SUB_FILE}" 2>/dev/null > "${AGENTS_SUB_FILE}.tmp" || echo "@${AGENTS_MD}" > "${AGENTS_SUB_FILE}.tmp"
        mv "${AGENTS_SUB_FILE}.tmp" "${AGENTS_SUB_FILE}"
        echo "  [UPDATE] Prepended @${AGENTS_MD} to ${AGENTS_SUB_FILE}"
    fi
fi

# Fix ownership
chown -R "${TARGET_USER}:${TARGET_USER}" "${GEMINI_CONFIG_DIR}" 2>/dev/null || true
chown -h "${TARGET_USER}:${TARGET_USER}" "${TARGET_HOME}/AGENTS.md" "${TARGET_HOME}/GEMINI.md" "${TARGET_HOME}/CLAUDE.md" "${TARGET_HOME}/CODEX.md" 2>/dev/null || true

echo "[SUCCESS] Instruction sync complete on $(hostname)"
