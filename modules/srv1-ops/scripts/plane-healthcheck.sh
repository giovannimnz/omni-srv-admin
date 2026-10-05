#!/usr/bin/env bash
set -euo pipefail

unit="plane-podman.service"
local_root="http://127.0.0.1:8090/"
local_setup="http://127.0.0.1:8090/setup/"
local_api="http://127.0.0.1:8090/api/v1/users/me/"
local_spaces="http://127.0.0.1:8090/spaces/"
public_root="https://plane.atius.com.br/"
public_setup="https://plane.atius.com.br/setup/"
public_api="https://plane.atius.com.br/api/v1/users/me/"
public_spaces="https://plane.atius.com.br/spaces/"

unit_state="$(systemctl --user show plane-podman.service \
  -p ActiveState -p SubState -p Result -p ExecMainStatus -p ExecStart)"
printf '%s\n' "$unit_state" | grep -Fqx 'ActiveState=active'
printf '%s\n' "$unit_state" | grep -Fqx 'SubState=exited'
printf '%s\n' "$unit_state" | grep -Fqx 'Result=success'
printf '%s\n' "$unit_state" | grep -Fqx 'ExecMainStatus=0'
exec_start="$(printf '%s\n' "$unit_state" | sed -n 's/^ExecStart=//p')"
[[ "$exec_start" == *"/home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/plane-stack-up.sh"* ]]

mapfile -t listeners < <(ss -H -ltn '( sport = :8080 or sport = :8090 )' \
  | awk '{print $4}' | sort)
expected_listeners=(
  "127.0.0.1:8080"
  "127.0.0.1:8090"
)
[[ "${#listeners[@]}" -eq "${#expected_listeners[@]}" ]]
for index in "${!expected_listeners[@]}"; do
  [[ "${listeners[$index]}" == "${expected_listeners[$index]}" ]]
done

probe() {
  local url="$1" expected="$2"
  local code
  code="$(curl --silent --show-error --location --output /dev/null \
    --write-out '%{http_code}' --max-time 15 "$url")"
  [[ "$code" == "$expected" ]]
}

probe "$local_root" 200
probe "$local_setup" 200
probe "$local_api" 401
probe "$local_spaces" 200
probe "$public_root" 200
probe "$public_setup" 200
probe "$public_api" 401
probe "$public_spaces" 200

printf '{"unit":"%s","listeners":["%s","%s"],"local":{"root":200,"setup":200,"api":401,"spaces":200},"public":{"root":200,"setup":200,"api":401,"spaces":200}}\n' \
  "$unit" "${listeners[0]}" "${listeners[1]}"
