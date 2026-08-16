#!/usr/bin/env bash
# Canonical implementation is generated for the 2026-07-31 rollout.
# Execute the sealed copy recorded by the rollout evidence after reviewing paths.
# This repo entry intentionally stays declarative; runtime mutation is owned by
# docs/evidence/atius-sso/2026-07-31-url-standard-rollout.json and its sealed
# cutover script/checksum.
set -Eeuo pipefail
printf 'Use the sealed rollout artifact referenced by docs/evidence/atius-sso/2026-07-31-url-standard-rollout.json\n' >&2
exit 2
