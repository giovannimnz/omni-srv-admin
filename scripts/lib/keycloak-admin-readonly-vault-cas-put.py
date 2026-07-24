#!/usr/bin/env python3
"""Remote-only Vault KV v2 CAS=0 writer.

The secret JSON arrives on stdin. Only the created version is written to stdout.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys


EXPECTED_PATH = "kv/atius/keycloak/admin-readonly"
EXPECTED_FIELDS = sorted(
    (
        "KEYCLOAK_BASE_URL",
        "KEYCLOAK_READONLY_CLIENT_ID",
        "KEYCLOAK_READONLY_CLIENT_SECRET",
        "KEYCLOAK_REALM",
    )
)


def main() -> None:
    if os.geteuid() != 0 or len(sys.argv) != 4 or sys.argv[1] != EXPECTED_PATH:
        raise SystemExit("exact root Vault target is required")
    try:
        cas = int(sys.argv[2])
        expected_version = int(sys.argv[3])
    except ValueError:
        raise SystemExit("Vault CAS/version must be integers") from None
    if (cas, expected_version) not in ((0, 1), (1, 2)):
        raise SystemExit("only initial CAS=0/version=1 and drill CAS=1/version=2 are allowed")
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict) or sorted(payload) != EXPECTED_FIELDS:
        raise SystemExit("Vault payload field set mismatch")
    if not all(isinstance(value, str) and value for value in payload.values()):
        raise SystemExit("Vault payload contains an empty/non-string value")
    init = json.loads(pathlib.Path("/root/hashicorp-vault-atius/init.json").read_text())
    token = init.get("root_token")
    if not isinstance(token, str) or not token:
        raise SystemExit("Vault runtime token unavailable")
    result = subprocess.run(
        [
            "podman",
            "exec",
            "-i",
            "-e",
            "VAULT_ADDR=https://127.0.0.1:8200",
            "-e",
            "VAULT_SKIP_VERIFY=true",
            "-e",
            f"VAULT_TOKEN={token}",
            "hashicorp-vault-atius",
            "vault",
            "kv",
            "put",
            "-format=json",
            f"-cas={cas}",
            EXPECTED_PATH,
            "@/dev/stdin",
        ],
        input=json.dumps(payload, separators=(",", ":")).encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit("Vault CAS=0 create failed")
    response = json.loads(result.stdout)
    version = response.get("data", {}).get("version")
    if version != expected_version:
        raise SystemExit("Vault CAS create did not return the exact expected version")
    json.dump({"version": version}, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
