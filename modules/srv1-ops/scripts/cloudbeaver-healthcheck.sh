#!/usr/bin/env bash
set -euo pipefail

unit="container-cloudbeaver.service"
expected_image="docker.io/dbeaver/cloudbeaver:26.1.0"
expected_mount="/home/ubuntu/GitHub/containers/cloudbeaver/workspace_recent:/opt/cloudbeaver/workspace:rw"
expected_listener="127.0.0.1:8978"
local_url="http://127.0.0.1:8978/status"
public_url="https://db.atius.com.br/"

tmp_local="$(mktemp)"
tmp_public="$(mktemp)"
trap 'rm -f "$tmp_local" "$tmp_public"' EXIT

unit_state="$(systemctl --user show container-cloudbeaver.service \
  -p ActiveState -p SubState -p Result -p NRestarts -p ExecStart)"
printf '%s\n' "$unit_state" | grep -Fqx 'ActiveState=active'
printf '%s\n' "$unit_state" | grep -Fqx 'SubState=running'
printf '%s\n' "$unit_state" | grep -Fqx 'Result=success'
printf '%s\n' "$unit_state" | grep -Fqx 'NRestarts=0'
exec_start="$(printf '%s\n' "$unit_state" | sed -n 's/^ExecStart=//p')"
[[ "$exec_start" == *"$expected_image"* ]]
[[ "$exec_start" == *"$expected_mount"* ]]
[[ "$exec_start" == *"--network srv1-podman-v2"* ]]
[[ "$exec_start" == *"-p 127.0.0.1:8978:8978"* ]]

listener_lines="$(ss -H -ltn 'sport = :8978')"
[[ "$(printf '%s\n' "$listener_lines" | sed '/^[[:space:]]*$/d' | wc -l)" -eq 1 ]]
listener_address="$(printf '%s\n' "$listener_lines" | awk 'NR == 1 {print $4}')"
[[ "$listener_address" == "$expected_listener" ]]

curl --fail --silent --show-error --max-time 10 "$local_url" --output "$tmp_local"
python3 - "$tmp_local" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
assert payload.get("health") == "ok", payload
assert str(payload.get("product.version", "")).startswith("26.1.0"), payload
PY

curl --fail --silent --show-error --location --max-time 15 "$public_url" --output "$tmp_public"
grep -qi '<title>CloudBeaver Community' "$tmp_public"

printf '{"unit":"%s","image":"%s","listener":"%s","local":"ok","public":"ok","restarts":0}\n' \
  "$unit" "$expected_image" "$listener_address"
