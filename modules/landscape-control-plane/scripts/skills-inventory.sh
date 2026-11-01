#!/usr/bin/env bash
# ==============================================================================
# Script: skills-inventory.sh
# Purpose: Read-only inventory of AI skills count, atius-vault-access propagation,
#          symlink health, and Landscape directive presence across the fleet.
# Managed: Omni Landscape Control Plane
# Version: 1.0.0
# ==============================================================================
set -euo pipefail

HOST="$(hostname -s 2>/dev/null || hostname)"
TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== SKILLS INVENTORY FOR HOST: ${HOST} ==="
echo "host: ${HOST}"
echo "timestamp_utc: ${TIMESTAMP_UTC}"

JSON_USERS=""

for TARGET_USER in ubuntu horistic muniz; do
    if ! id "${TARGET_USER}" >/dev/null 2>&1; then
        continue
    fi
    TARGET_HOME="$(eval echo ~${TARGET_USER})"
    GEMINI_SKILLS="${TARGET_HOME}/.gemini/config/skills"
    AGENTS_SKILLS="${TARGET_HOME}/.agents/skills"
    AGENTS_MD="${TARGET_HOME}/.gemini/config/AGENTS.md"

    GEMINI_SKILLS_COUNT=0
    if [ -d "${GEMINI_SKILLS}" ]; then
        GEMINI_SKILLS_COUNT="$(find "${GEMINI_SKILLS}/" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
    fi

    AGENTS_SKILLS_COUNT=0
    if [ -d "${AGENTS_SKILLS}" ]; then
        AGENTS_SKILLS_COUNT="$(find "${AGENTS_SKILLS}/" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
    fi

    VAULT_SKILL_STATUS="missing"
    VAULT_SKILL_MD="${GEMINI_SKILLS}/atius-vault-access/SKILL.md"
    if [ -f "${VAULT_SKILL_MD}" ]; then
        if [ -s "${VAULT_SKILL_MD}" ] && grep -qi "atius-vault-access" "${VAULT_SKILL_MD}"; then
            VAULT_SKILL_STATUS="present_valid"
        else
            VAULT_SKILL_STATUS="present_corrupted"
        fi
    fi

    SYMLINK_STATUS="missing"
    if [ -L "${AGENTS_SKILLS}" ]; then
        TARGET="$(readlink -f "${AGENTS_SKILLS}" 2>/dev/null || echo "unresolved")"
        if [ "${TARGET}" = "${GEMINI_SKILLS}" ]; then
            SYMLINK_STATUS="valid_symlink"
        else
            SYMLINK_STATUS="symlink_to:${TARGET}"
        fi
    elif [ -d "${AGENTS_SKILLS}" ]; then
        SYMLINK_STATUS="physical_directory"
    fi

    HAS_LANDSCAPE_DIRECTIVE=false
    if [ -f "${AGENTS_MD}" ]; then
        if grep -q "Canonical Fleet Operations & Landscape Control-Plane Directive" "${AGENTS_MD}"; then
            HAS_LANDSCAPE_DIRECTIVE=true
        fi
    fi

    echo ""
    echo "user: ${TARGET_USER}"
    echo "  gemini_skills_count: ${GEMINI_SKILLS_COUNT}"
    echo "  agents_skills_count: ${AGENTS_SKILLS_COUNT}"
    echo "  agents_skills_symlink: ${SYMLINK_STATUS}"
    echo "  atius_vault_access: ${VAULT_SKILL_STATUS}"
    echo "  landscape_directive: ${HAS_LANDSCAPE_DIRECTIVE}"

    USER_JSON=$(cat << UJSON
    "${TARGET_USER}": {
      "gemini_skills_count": ${GEMINI_SKILLS_COUNT},
      "agents_skills_count": ${AGENTS_SKILLS_COUNT},
      "agents_skills_symlink": "${SYMLINK_STATUS}",
      "atius_vault_access": "${VAULT_SKILL_STATUS}",
      "landscape_directive": ${HAS_LANDSCAPE_DIRECTIVE}
    }
UJSON
)
    if [ -z "${JSON_USERS}" ]; then
        JSON_USERS="${USER_JSON}"
    else
        JSON_USERS="${JSON_USERS},
${USER_JSON}"
    fi
done

TIMER_STATUS="inactive_or_missing"
if command -v systemctl >/dev/null 2>&1; then
    if systemctl is-active --quiet omni-fleet-runtime-sync.timer 2>/dev/null; then
        TIMER_STATUS="active"
    fi
fi
echo ""
echo "service_timer: ${TIMER_STATUS}"

echo ""
echo "=== JSON SUMMARY ==="
cat << JSONEOF
{
  "host": "${HOST}",
  "timestamp_utc": "${TIMESTAMP_UTC}",
  "service_timer": "${TIMER_STATUS}",
  "users": {
${JSON_USERS}
  }
}
JSONEOF
echo "=== END INVENTORY ==="
