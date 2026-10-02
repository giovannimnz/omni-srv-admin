#!/bin/bash
# omni::agy-sessions-list — lista sessões Antigravity CLI no host
# Risk: read-only
# Version: 1.0.0
set -euo pipefail

HOST=$(hostname)
BRAIN="${HOME}/.gemini/antigravity-cli/brain"
DB="${HOME}/.gemini/antigravity-cli/conversation_summaries.db"

echo "=== HOST: ${HOST} ==="
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo ""

if [ ! -d "${BRAIN}" ]; then
    echo "Brain dir not found: ${BRAIN}"
    echo "Antigravity CLI possivelmente nao instalado neste host."
    exit 0
fi

# Tenta SQLite primeiro (mais rico)
if command -v sqlite3 &>/dev/null && [ -f "${DB}" ]; then
    echo "--- Sessoes Principais (via SQLite) ---"
    sqlite3 "${DB}" << 'SQLEOF'
.mode column
.headers on
SELECT
    substr(last_modified_time, 1, 16) AS modified,
    substr(conversation_id, 1, 8) || '...' AS id_short,
    step_count AS steps,
    substr(title, 1, 50) AS title,
    substr(workspace_uris, 1, 60) AS workspace
FROM conversation_summaries
WHERE nesting_depth = 0
ORDER BY last_modified_time DESC
LIMIT 15;
SQLEOF

    echo ""
    echo "--- Total de sessoes (incluindo subagentes) ---"
    sqlite3 "${DB}" "SELECT COUNT(*) || ' sessoes totais, ' || SUM(CASE WHEN nesting_depth=0 THEN 1 ELSE 0 END) || ' principais' FROM conversation_summaries;"

else
    echo "SQLite indisponivel — escaneando brain dir..."
    if command -v python3 &>/dev/null; then
        python3 << 'PYEOF'
import os, json, re, datetime

brains = os.path.expanduser("~/.gemini/antigravity-cli/brain")
sessions = []
for entry in os.scandir(brains):
    if not entry.is_dir():
        continue
    t = os.path.join(entry.path, ".system_generated/logs/transcript.jsonl")
    if not os.path.exists(t):
        continue
    mtime = os.path.getmtime(t)
    prompts = []
    try:
        with open(t) as f:
            for line in f:
                d = json.loads(line)
                if d.get("type") == "USER_INPUT":
                    raw = re.sub(r"<[^>]+>", "", d.get("content","")).strip()
                    if raw:
                        prompts.append(raw)
    except Exception:
        pass
    sessions.append((mtime, entry.name, prompts))
sessions.sort(reverse=True)
print(f"{'Data/Hora':<17} {'ID (8 chars)':<12} {'Turnos':>6}  {'Primeiro Prompt'}")
print("-" * 80)
for mtime, cid, p in sessions[:15]:
    dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    first = (p[0][:60] if p else "N/A").replace("\n"," ")
    print(f"{dt:<17} {cid[:8]+'...':<12} {len(p):>6}  {first}")
PYEOF
    else
        echo "Python3 indisponivel. Liste manualmente em: ${BRAIN}"
    fi
fi

echo ""
echo "--- Cache last_conversations (agy -c mapping) ---"
CACHE="${HOME}/.gemini/antigravity-cli/cache/last_conversations.json"
if [ -f "${CACHE}" ]; then
    cat "${CACHE}"
else
    echo "(cache nao encontrado)"
fi

echo ""
echo "=== FIM: ${HOST} ==="
