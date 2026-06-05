#!/usr/bin/env bash
# model-history-tracker — hook do comando /model
# Uso: source this in cli.py antes de processar /model, ou append em ~/.bashrc.
# Persiste o modelo *anterior* sempre que o user muda.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HIST="$HERMES_HOME/state/model_history.json"
CONFIG="$HERMES_HOME/config.yaml"

track_model_change() {
  local new_model="$1"
  local new_provider="${2:-}"
  mkdir -p "$(dirname "$HIST")"
  [[ -f "$HIST" ]] || echo '{"current":"","previous":""}' > "$HIST"

  local cur_model cur_prov
  cur_model=$(awk '/^  default:/{print $2; exit}' "$CONFIG" 2>/dev/null || echo "")
  cur_prov=$(awk '/^model:/{f=1; next} f && /provider:/{print $2; exit}' "$CONFIG" 2>/dev/null || echo "")

  if [[ -z "$cur_model" || "$cur_model" == "$new_model" ]]; then
    return 0
  fi

  # Move current → previous, new → current
  python3 - "$HIST" "$cur_model" "$cur_prov" "$new_model" "$new_provider" <<'PY'
import json, sys
path, prev_m, prev_p, cur_m, cur_p = sys.argv[1:6]
json.dump({"current": cur_m, "current_provider": cur_p,
           "previous": prev_m, "previous_provider": prev_p},
          open(path, "w"), indent=2)
PY
  echo "📌 Histórico: $cur_model → $new_model"
}
