#!/usr/bin/env python3
"""Machine-readable validation gate for Phase 54.

The gate is intentionally fail-closed: missing evidence, unknown state,
missing rollback receipts, or a prior BLOCKED status can never produce PASS.
It performs no infrastructure mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

EDGE_TARGET_MAP = {
    "horistic_wireguard": {"from": "10.100.100.4", "to": "10.100.100.31"},
    "s23_wireguard": {"from": "10.100.100.9", "to": "10.100.100.10"},
    "s20_lan": {"from": "192.168.1.10", "to": "192.168.1.11"},
    "s20_wireguard": {"from": None, "to": "10.100.100.11"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def check(check_id: str, expected: str, observed: Any, result: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "expected": expected,
        "observed": observed,
        "result": result,
    }


def run(args: argparse.Namespace) -> int:
    evidence = pathlib.Path(args.evidence).resolve()
    gate = pathlib.Path(args.gate).resolve()
    checks: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    evidence_hash = sha256_file(evidence)
    checks.append(
        check(
            "evidence_exists",
            "evidence file exists and is non-empty",
            str(evidence),
            "PASS" if evidence_hash else "BLOCK",
        )
    )
    if evidence_hash:
        artifacts.append({"path": str(evidence), "sha256": evidence_hash, "redacted": True})

    evidence_json = read_json(evidence) if evidence_hash else None
    checks.append(
        check(
            "evidence_machine_readable",
            "JSON object with status PASS",
            evidence_json.get("status") if evidence_json else None,
            "PASS" if evidence_json and evidence_json.get("status") == "PASS" else "BLOCK",
        )
    )
    if args.plan in {"54-05", "54-06"}:
        observed_target_map = evidence_json.get("target_map") if evidence_json else None
        checks.append(
            check(
                "edge_target_map",
                "exact Horistic, S23 and S20 LAN/WireGuard migration map",
                observed_target_map,
                "PASS" if observed_target_map == EDGE_TARGET_MAP else "BLOCK",
            )
        )

    phase_root = evidence.parent
    rollback = phase_root / "rollback-receipt.json"
    rollback_json = read_json(rollback)
    rollback_ok = bool(rollback_json and rollback_json.get("status") == "PASS")
    checks.append(check("rollback_receipt", "rollback receipt status PASS", rollback_json and rollback_json.get("status"), "PASS" if rollback_ok else "BLOCK"))
    if rollback.is_file():
        artifacts.append({"path": str(rollback), "sha256": sha256_file(rollback), "redacted": True})

    backup_root = pathlib.Path("/var/backups/omni-srv-admin/phase54")
    local_backup_ok = backup_root.is_dir() and any(backup_root.iterdir())
    host_backups = rollback_json.get("host_backups", {}) if rollback_json else {}
    remote_backup_ok = bool(
        host_backups.get("status") == "PASS"
        and host_backups.get("horistic", {}).get("checksum_status") == "PASS"
        and host_backups.get("horistic", {}).get("restore_staging_status") == "PASS"
        and host_backups.get("srv1", {}).get("checksum_status") == "PASS"
        and host_backups.get("srv1", {}).get("restore_staging_status") == "PASS"
    )
    backup_ok = local_backup_ok or remote_backup_ok
    backup_observed: Any = str(backup_root)
    if not local_backup_ok:
        backup_observed = {
            "source": "rollback-receipt.json",
            "remote_host_backups": host_backups.get("status"),
            "horistic_restore": host_backups.get("horistic", {}).get("restore_staging_status"),
            "srv1_restore": host_backups.get("srv1", {}).get("restore_staging_status"),
        }
    checks.append(
        check(
            "backup_restore_staging",
            "local backup directory or verified remote host backup receipts PASS",
            backup_observed,
            "PASS" if backup_ok else "BLOCK",
        )
    )

    required_results = [item["result"] for item in checks]
    status = "PASS" if required_results and all(item == "PASS" for item in required_results) else "BLOCK"
    receipt = {
        "schema": "gsd.validation.v1",
        "phase": 54,
        "plan": args.plan,
        "mode": "read-only",
        "status": status,
        "started_at": args.started_at,
        "finished_at": utc_now(),
        "checks": checks,
        "artifacts": artifacts,
        "evidence_sha256": evidence_hash,
        "next_wave_gate": f"PASS:{args.plan}" if status == "PASS" else None,
        "mutations_attempted": bool(evidence_json.get("mutations_attempted", False)) if evidence_json else False,
    }
    gate.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=gate.parent, delete=False) as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, gate)
    print(json.dumps({"status": status, "plan": args.plan, "gate": str(gate), "evidence_sha256": evidence_hash}, ensure_ascii=False))
    return 0 if status == "PASS" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["final"])
    parser.add_argument("--plan", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--redact", action="store_true")
    args = parser.parse_args()
    args.started_at = utc_now()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
