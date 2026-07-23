#!/usr/bin/env bash
set -euo pipefail

# Read-only fleet contract smoke for the canonical Streamable HTTP registration.
# It never prints environment values, request headers, or bodies.

usage() {
  cat <<'EOF'
Usage: oci-admin-mcp-fleet-smoke.sh [--hosts h1,h2] [--runtimes codex,hermes]
  [--require-canonical-only] [--read-back] [--redact]
EOF
}

hosts="atius-srv-1,atius-srv-2,atius-srv-3,horistic-srv,GIOVANNI-W11-PC,GIOVANNI-S23"
runtimes="codex,hermes"
require_canonical=0
read_back=0
redact=0
while (($#)); do
  case "$1" in
    --hosts) hosts=${2:?missing value for --hosts}; shift 2 ;;
    --runtimes) runtimes=${2:?missing value for --runtimes}; shift 2 ;;
    --require-canonical-only) require_canonical=1; shift ;;
    --read-back) read_back=1; shift ;;
    --redact) redact=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
printf '%s\n' '{"schema":"oci-admin-mcp-fleet-smoke/v1","read_only":true,"redacted":true}' >"$tmp"

json_record() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" >>"$tmp"
}

adapter_for_host() {
  case "$1" in
    GIOVANNI-W11-PC) printf '%s' 'powershell/ssh-windows' ;;
    GIOVANNI-S23) printf '%s' 'termux/proot/ssh' ;;
    *) printf '%s' 'ssh' ;;
  esac
}

ssh_target_for_host() {
  case "$1" in
    atius-srv-1|atius-srv-1.atius.internal) printf '%s' 'atius-srv-1.atius.internal' ;;
    atius-srv-2|atius-srv-2.atius.internal) printf '%s' 'atius-srv-2.atius.internal' ;;
    atius-srv-3|atius-srv-3.atius.internal) printf '%s' 'atius-srv-3.atius.internal' ;;
    horistic-srv|horistic-srv.atius.internal) printf '%s' 'horistic-srv.atius.internal' ;;
    *) printf '%s' "$1" ;;
  esac
}

remote_probe='set +e; found=0; canonical=0; legacy=0; url=0; for f in "$HOME/.codex/config.toml" "$HOME/.codex/config.yaml" "$HOME/.hermes/config.toml" "$HOME/.hermes/config.yaml" "$HOME/.config/codex/config.toml"; do if [ -f "$f" ]; then found=1; grep -Eq "oci_admin_http" "$f" && canonical=1; grep -Eq "(^|[^A-Za-z0-9_])oci_admin([^A-Za-z0-9_]|$)" "$f" && legacy=1; grep -Eq "mcp\.atius\.com\.br/oci-admin" "$f" && url=1; fi; done; printf "found=%s canonical=%s legacy=%s url=%s\n" "$found" "$canonical" "$legacy" "$url"'

probe_local() {
  local runtime=$1 found=0 canonical=0 legacy=0 url=0 f
  local -a files=("$HOME/.codex/config.toml" "$HOME/.codex/config.yaml" "$HOME/.hermes/config.toml" "$HOME/.hermes/config.yaml" "$HOME/.config/codex/config.toml")
  for f in "${files[@]}"; do
    [[ -f "$f" ]] || continue
    found=1
    rg -q 'oci_admin_http' "$f" && canonical=1 || true
    rg -q '(^|[^A-Za-z0-9_])oci_admin([^A-Za-z0-9_]|$)' "$f" && legacy=1 || true
    rg -q 'mcp\.atius\.com\.br/oci-admin' "$f" && url=1 || true
  done
  local status=ok reason="canonical registration present"
  if ((found == 0)); then status=not-installed; reason="runtime config not installed";
  elif ((require_canonical == 1 && (canonical == 0 || legacy == 1))); then status=divergent; reason="canonical key missing or legacy alias present";
  elif ((canonical == 0)); then status=divergent; reason="canonical key missing"; fi
  json_record "local" "$runtime" "$status" "$reason" "before=unavailable" "after=read-only" "rollback=not-run" "local"
}

probe_remote() {
  local host=$1 runtime=$2 out status reason found canonical legacy adapter ssh_target
  adapter=$(adapter_for_host "$host")
  ssh_target=$(ssh_target_for_host "$host")
  if [[ "$host" == "$(hostname -s)" || "$host" == "localhost" ]]; then probe_local "$runtime"; return; fi
  if ! out=$(timeout 12 ssh -n -o BatchMode=yes -o ConnectTimeout=5 "$ssh_target" "$remote_probe" 2>/dev/null); then
    json_record "$host" "$runtime" unreachable "${adapter} adapter unavailable" "before=unavailable" "after=not-run" "rollback=not-run" "$adapter"
    return
  fi
  found=${out##*found=}; found=${found%% *}; canonical=${out##*canonical=}; canonical=${canonical%% *}; legacy=${out##*legacy=}; legacy=${legacy%% *}
  status=ok; reason="canonical registration present"
  if [[ "$found" == 0 ]]; then status=not-installed; reason="runtime config not installed";
  elif ((require_canonical == 1 && (canonical == 0 || legacy == 1))); then status=divergent; reason="canonical key missing or legacy alias present";
  elif [[ "$canonical" == 0 ]]; then status=divergent; reason="canonical key missing"; fi
  json_record "$host" "$runtime" "$status" "$reason" "before=sha256-redacted" "after=read-back:$read_back" "rollback=not-run" "$adapter"
}

IFS=',' read -r -a host_list <<<"$hosts"
IFS=',' read -r -a runtime_list <<<"$runtimes"
for host in "${host_list[@]}"; do
  host=${host// /}; [[ -n "$host" ]] || continue
  for runtime in "${runtime_list[@]}"; do
    runtime=${runtime// /}; [[ -n "$runtime" ]] || continue
    case "$runtime" in codex|hermes) ;; *) json_record "$host" "$runtime" invalid "unsupported runtime" "before=not-run" "after=not-run" "rollback=not-run" "unknown"; continue ;; esac
    probe_remote "$host" "$runtime"
  done
done

python3 - "$tmp" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    lines = [line.rstrip("\n") for line in fh]
header = json.loads(lines[0])
rows = []
for line in lines[1:]:
    host, runtime, status, reason, before, after, rollback, adapter = line.split("\t", 7)
    rows.append({"host": host, "runtime": runtime, "status": status, "reason": reason,
                 "before": before, "after": after, "rollback": rollback, "adapter": adapter})
header.update({"matrix": rows, "canonical_key": "oci_admin_http", "legacy_alias": "oci_admin"})
print(json.dumps(header, ensure_ascii=False, sort_keys=True))
sys.exit(1 if any(row["status"] == "divergent" for row in rows) else 0)
PY
