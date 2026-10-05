#!/usr/bin/env bash
set -euo pipefail

compose_dir="/home/ubuntu/GitHub/containers/plane-app"
compose_file="$compose_dir/podman-compose.yaml"
env_file="$compose_dir/.env"
compose_bin="/home/ubuntu/.local/bin/podman-compose"
podman_bin="/usr/bin/podman"
migrator="plane-app_migrator_1"
api_url="http://127.0.0.1:8090/api/v1/users/me/"
setup_url="http://127.0.0.1:8090/setup/"
root_url="http://127.0.0.1:8090/"
spaces_url="http://127.0.0.1:8090/spaces/"

cd "$compose_dir"
"$compose_bin" --podman-path "$podman_bin" --env-file "$env_file" \
  -f "$compose_file" up -d

migrator_state="missing"
for _ in $(seq 1 300); do
  migrator_state="$($podman_bin inspect "$migrator" \
    --format '{{.State.Status}}:{{.State.ExitCode}}' 2>/dev/null || printf missing)"
  case "$migrator_state" in
    exited:0) break ;;
    exited:*) printf 'MIGRATOR_FAILED state=%s\n' "$migrator_state" >&2; exit 3 ;;
  esac
  sleep 4
done
[[ "$migrator_state" == "exited:0" ]] || {
  printf 'MIGRATOR_TIMEOUT state=%s\n' "$migrator_state" >&2
  exit 4
}

api_code=000
setup_code=000
root_code=000
spaces_code=000
for _ in $(seq 1 120); do
  api_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --max-time 5 "$api_url" 2>/dev/null || true)"
  setup_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --max-time 5 "$setup_url" 2>/dev/null || true)"
  root_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --max-time 5 "$root_url" 2>/dev/null || true)"
  spaces_code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --max-time 5 "$spaces_url" 2>/dev/null || true)"
  if [[ "$api_code" == "401" && "$setup_code" == "200" && "$root_code" == "200" && "$spaces_code" == "200" ]]; then
    break
  fi
  sleep 3
done

[[ "$api_code" == "401" && "$setup_code" == "200" && "$root_code" == "200" && "$spaces_code" == "200" ]] || {
  printf 'PLANE_API_NOT_READY migrator=%s api=%s setup=%s root=%s spaces=%s\n' \
    "$migrator_state" "$api_code" "$setup_code" "$root_code" "$spaces_code" >&2
  exit 5
}

all_count="$($podman_bin ps -a --format '{{.Names}}' | grep -c '^plane-app_')"
running_count="$($podman_bin ps --format '{{.Names}}' | grep -c '^plane-app_')"
[[ "$all_count" == "12" && "$running_count" == "11" ]] || {
  printf 'PLANE_CONTAINER_COUNT_MISMATCH all=%s running=%s\n' "$all_count" "$running_count" >&2
  exit 6
}

printf 'PLANE_READY_OK migrator=%s api=%s setup=%s root=%s spaces=%s all=%s running=%s\n' \
  "$migrator_state" "$api_code" "$setup_code" "$root_code" "$spaces_code" "$all_count" "$running_count"
