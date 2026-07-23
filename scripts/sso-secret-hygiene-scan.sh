#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMNI_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ATS_ROOT="/home/ubuntu/GitHub/Atius-Capital/ats"
PHASE_DIR="${OMNI_ROOT}/.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/42-atius-wide-sso-login-on-sso-atius-com-br"

legacy_targets=(
  "${PHASE_DIR}"
  "${OMNI_ROOT}/scripts/sso-edge-smoke.sh"
  "${OMNI_ROOT}/scripts/sso-secret-hygiene-scan.sh"
  "${OMNI_ROOT}/scripts/keycloak-sso-client-check.sh"
  "${ATS_ROOT}/tests/backend/auth/test_sso_redirect_allowlist.test.js"
  "${ATS_ROOT}/tests/backend/auth/test_sso_oidc_bridge.test.js"
  "${ATS_ROOT}/tests/backend/auth/test_sso_auth_endpoints.runtime.test.js"
  "${ATS_ROOT}/tests/frontend/e2e/test_sso_global_logout.spec.ts"
  "${ATS_ROOT}/frontend/src/lib/sso"
  "${ATS_ROOT}/frontend/src/app/api/sso"
  "${ATS_ROOT}/frontend/src/middleware.ts"
  "${OMNI_ROOT}/modules/mt5-remote-auth"
  "${OMNI_ROOT}/docs/domain/atius-wide-sso.md"
  "/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-28-phase42-atius-wide-sso.md"
)

# Explicit scopes are fail-closed and value-free; legacy is zero-argument only.
if (( "$#" > 0 )); then
  targets=("$@")
  for target in "${targets[@]}"; do
    if [[ ! -e "${target}" ]]; then
      printf 'SSO hygiene scan blocked: missing explicit target: %s\n' "${target}" >&2
      exit 2
    fi
  done
else
  targets=("${legacy_targets[@]}")
fi

python3 - "${targets[@]}" <<'PY'
from __future__ import annotations

import pathlib
import re
import sys

raw_targets = [pathlib.Path(arg) for arg in sys.argv[1:]]

patterns = [
    ("private-key", re.compile(r"BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY")),
    ("bearer-token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}")),
    ("cookie-value", re.compile(r"\bauth-token=[A-Za-z0-9._-]{16,}")),
    (
        "client-secret-value",
        re.compile(r"(?i)\bclient[_-]?secret\b\s*[:=]\s*['\"](?!redacted\b|example\b|changeme\b)[^'\"]{6,}['\"]")
    ),
    (
        "jwt-secret-value",
        re.compile(r"(?i)\bJWT_SECRET\b\s*[:=]\s*['\"](?!redacted\b|example\b|changeme\b)[^'\"]{6,}['\"]")
    ),
    (
        "password-value",
        re.compile(r"(?i)\b(?:SSO_TEST_PASSWORD|ADMIN_TEST_PASSWORD|TEST_PASSWORD|PASSWORD|SENHA)\b\s*[:=]\s*['\"](?!redacted\b|example\b|changeme\b)[^'\"]{6,}['\"]")
    ),
]

files: list[pathlib.Path] = []
for target in raw_targets:
    if not target.exists():
        continue
    if target.is_dir():
        files.extend(path for path in target.rglob("*") if path.is_file())
    else:
        files.append(target)

findings = []
for path in sorted(set(files)):
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        continue
    for line_number, line in enumerate(lines, start=1):
        for category, regex in patterns:
            if regex.search(line):
                findings.append((path, line_number, category))

if findings:
    print("SSO hygiene scan failed. Redacted findings:")
    for path, line_number, category in findings:
        print(f"- {path}:{line_number} [{category}]")
    sys.exit(1)

print(f"SSO hygiene scan passed. Scanned {len(set(files))} files with redacted reporting.")
PY
