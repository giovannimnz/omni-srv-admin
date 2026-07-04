#!/usr/bin/env bash
set -euo pipefail

PROJECT="${1:-}"
shift || true

if [[ -z "$PROJECT" ]]; then
  echo "usage: deploy.sh <project> [repo-path] [--dry-run]" >&2
  exit 2
fi

DRY_RUN=0
REPO_PATH=""
for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=1
      ;;
    *)
      if [[ -z "$REPO_PATH" ]]; then
        REPO_PATH="$arg"
      else
        echo "unexpected argument: $arg" >&2
        exit 2
      fi
      ;;
  esac
done

ROOT="${FORK_SYNC_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PROJECT_DIR="$ROOT/projects/$PROJECT"
SYNC_YAML="$PROJECT_DIR/sync.yaml"
DEPLOY_YAML="$PROJECT_DIR/deploy.yaml"
OMNI_CLI_DIR="${OMNI_CLI_DIR:-/home/ubuntu/GitHub/omni-srv-admin/cli}"

if [[ ! -f "$SYNC_YAML" || ! -f "$DEPLOY_YAML" ]]; then
  echo "missing sync/deploy config for project: $PROJECT" >&2
  exit 3
fi

eval "$(
  python3 - "$SYNC_YAML" "$DEPLOY_YAML" <<'PY'
import shlex
import sys
import yaml
sync_path, deploy_path = sys.argv[1:]
with open(sync_path, "r", encoding="utf-8") as fh:
    sync = yaml.safe_load(fh) or {}
with open(deploy_path, "r", encoding="utf-8") as fh:
    deploy = yaml.safe_load(fh) or {}
values = {
    "CFG_FORK": sync.get("fork", ""),
    "CFG_FORK_REPO": sync.get("fork_repo", ""),
    "CFG_IMAGE": deploy.get("image", ""),
    "CFG_HEALTH_ENDPOINT": deploy.get("health_endpoint", ""),
    "CFG_RESOURCE_PROFILE": deploy.get("resource_profile", "builds"),
    "CFG_BUILD_WRAPPER": deploy.get("build_wrapper", ""),
    "CFG_CONTAINER_NAME": deploy.get("container_name", ""),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(str(value or ''))}")
PY
)"

if [[ -z "$REPO_PATH" ]]; then
  REPO_PATH="$CFG_FORK"
fi
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

if [[ -z "$CFG_IMAGE" ]]; then
  echo "deploy image is empty in $DEPLOY_YAML" >&2
  exit 3
fi

VERSION="${FORK_SYNC_DEPLOY_VERSION:-}"
if [[ -z "$VERSION" && -s "$REPO_PATH/VERSION" ]]; then
  VERSION="$(tr -d '[:space:]' < "$REPO_PATH/VERSION")"
fi
if [[ -z "$VERSION" ]]; then
  echo "VERSION is empty; set FORK_SYNC_DEPLOY_VERSION or write $REPO_PATH/VERSION" >&2
  exit 3
fi
VERSION="${VERSION#v}"
IMAGE_TAG="v${VERSION}"
IMAGE_VERSION_REF="${CFG_IMAGE}:${IMAGE_TAG}"
IMAGE_LATEST_REF="${CFG_IMAGE}:latest"

BUILD_WRAPPER="$REPO_PATH/$CFG_BUILD_WRAPPER"
if [[ -z "$CFG_BUILD_WRAPPER" || ! -x "$BUILD_WRAPPER" ]]; then
  echo "build wrapper not executable: $BUILD_WRAPPER" >&2
  exit 3
fi

run_builds() {
  local -a cmd=("$@")
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY profile=%s ' "$CFG_RESOURCE_PROFILE"
    printf '%q ' "${cmd[@]}"
    printf '\n'
    return 0
  fi
  PYTHONPATH="$OMNI_CLI_DIR" python3 -m omni srv1-ops resources run "$CFG_RESOURCE_PROFILE" -- "${cmd[@]}"
}

run_plain() {
  local -a cmd=("$@")
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'DRY '
    printf '%q ' "${cmd[@]}"
    printf '\n'
    return 0
  fi
  "${cmd[@]}"
}

echo "project=$PROJECT"
echo "repo_path=$REPO_PATH"
echo "image_version=$IMAGE_VERSION_REF"
echo "image_latest=$IMAGE_LATEST_REF"
echo "resource_profile=$CFG_RESOURCE_PROFILE"

run_builds \
  "$BUILD_WRAPPER" build \
  --build-arg TARGETOS=linux \
  --build-arg TARGETARCH=arm64 \
  -f "$REPO_PATH/Dockerfile" \
  -t "$IMAGE_VERSION_REF" \
  -t "$IMAGE_LATEST_REF" \
  "$REPO_PATH"

run_builds podman push "$IMAGE_VERSION_REF"
run_builds podman push "$IMAGE_LATEST_REF"

run_plain podman image inspect "$IMAGE_VERSION_REF" --format 'built_image={{.Id}} os={{.Os}} arch={{.Architecture}} size={{.Size}}'

if [[ "$DRY_RUN" -eq 0 ]]; then
  (
    cd "$REPO_PATH"
    "$BUILD_WRAPPER" prod-restart
  )
fi

if [[ -n "$CFG_HEALTH_ENDPOINT" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY curl -fsS $CFG_HEALTH_ENDPOINT"
  else
    curl -fsS "$CFG_HEALTH_ENDPOINT" >/tmp/fork-sync-deploy-health.json
    echo "health_endpoint=$CFG_HEALTH_ENDPOINT"
    echo "health_output=/tmp/fork-sync-deploy-health.json"
  fi
fi

echo "status=success"
