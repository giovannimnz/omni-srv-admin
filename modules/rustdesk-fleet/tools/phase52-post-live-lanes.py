#!/usr/bin/env python3
"""Fail-closed producer for the Phase 52 post-live evidence lanes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


FREEZE = "6bb2e0abad5cad3eb1ff750bcb92130c06ee0f6c"
INTERVAL_START = "63affd2d14547efdcb21c727170e4dcf0e643944"
INTERVAL_END = "bf3f5062c9abcbacfd4256074d8c7eb59085240b"
EXPECTED_XFAILS = {
    "modules.rustdesk-fleet.tests.test_phase53_primary_edge::test_future_implementation_symbol_is_red_only_for_owner_plan[evidence/phase53/deploy-transaction.json-53-05]",
    "modules.rustdesk-fleet.tests.test_phase53_primary_edge::test_future_implementation_symbol_is_red_only_for_owner_plan[tools/validate_phase53.py-53-06]",
}
LEGACY_NODES = {
    "test_preflight_candidate_binds_gate_a_and_managed_sources",
    "test_finalize_requires_two_distinct_pass_reviews_on_exact_hash_set",
    "test_finalize_requires_exact_offline_check_schema_and_counts[<lambda>0]",
    "test_finalize_requires_exact_offline_check_schema_and_counts[<lambda>1]",
    "test_finalize_requires_exact_offline_check_schema_and_counts[<lambda>2]",
    "test_finalize_requires_exact_offline_check_schema_and_counts[<lambda>3]",
    "test_finalize_rejects_stale_source_and_execute_live_never_reaches_network",
    "test_cli_without_explicit_execute_live_is_local_only",
    "test_remote_bootstrap_recomputes_canonical_hash_and_private_digest_ephemerally",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"git failed: {' '.join(args)}")
    return completed.stdout


def is_phase53_execution_path(path: str) -> bool:
    return (
        path.startswith(".planning/workstreams/rustdesk-fleet/phases/53-")
        or path.startswith("modules/rustdesk-fleet/nftables/")
        or path.startswith("modules/rustdesk-fleet/systemd/")
        or path.startswith("modules/rustdesk-fleet/tools/apply-phase53")
        or path.startswith("modules/rustdesk-fleet/tools/probe-phase53")
        or path == "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py"
    )


def cases(path: Path) -> list[ET.Element]:
    return list(ET.parse(path).getroot().iter("testcase"))


def lane_current(path: Path) -> dict[str, object]:
    rows = cases(path)
    failures = [row for row in rows if row.find("failure") is not None or row.find("error") is not None]
    xfails = [
        f"{row.get('classname', '')}::{row.get('name', '')}".strip(":")
        for row in rows
        if row.find("skipped") is not None
        and row.find("skipped").get("type") == "pytest.xfail"
    ]
    regular_skips = [
        row for row in rows if row.find("skipped") is not None and row.find("skipped").get("type") != "pytest.xfail"
    ]
    if failures or set(xfails) != EXPECTED_XFAILS or regular_skips:
        raise SystemExit("current lane is not strict PASS")
    return {
        "junit": path.name,
        "sha256": sha(path),
        "test_count": len(rows),
        "failure_count": 0,
        "error_count": 0,
        "regular_skip_count": 0,
        "xfail_count": len(xfails),
        "xfail_nodeids": sorted(xfails),
        "frozen_verifier": "PASS",
    }


def lane_legacy(path: Path) -> dict[str, object]:
    rows = cases(path)
    names = {row.get("name", "") for row in rows}
    if names != LEGACY_NODES or len(rows) != 9:
        raise SystemExit("legacy lane node set drift")
    failures = [row.find("failure") for row in rows]
    if any(item is None for item in failures) or any(row.find("error") is not None for row in rows):
        raise SystemExit("legacy lane outcome drift")
    drift = sum("gate-a-managed-source-drift" in (item.text or "") for item in failures if item is not None)
    cli = next(row for row in rows if row.get("name") == "test_cli_without_explicit_execute_live_is_local_only")
    cli_text = cli.find("failure").text or ""
    if drift != 8 or "assert 2 == 0" not in cli_text or "AssertionError: network attempted" in cli_text:
        raise SystemExit("legacy lane classification drift")
    return {
        "junit": path.name,
        "sha256": sha(path),
        "test_count": 9,
        "failure_count": 9,
        "error_count": 0,
        "skip_count": 0,
        "gate_a_managed_source_drift_count": drift,
        "cli_local_only_case_count": 1,
        "network_attempted": False,
        "expected_failure": True,
        "historical_evidence_rewritten": False,
    }


def lane_timeout(paths: list[Path]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for path in paths:
        items = cases(path)
        if len(items) != 1 or items[0].find("failure") is not None or items[0].find("error") is not None or items[0].find("skipped") is not None:
            raise SystemExit(f"timeout lane failed: {path.name}")
        rows.append({"junit": path.name, "sha256": sha(path), "test_count": 1, "failure_count": 0, "error_count": 0, "skip_count": 0})
    return {
        "test_nodeid": "modules/fleet-backup/tests/test_phase52_backup_b.py::Phase52BackupBTests::test_cat_failure_and_timeout_block_and_cleanup_snapshots",
        "consecutive_pass_count": len(rows),
        "runs": rows,
    }


def interval_audit(repo: Path) -> dict[str, object]:
    commits = git(repo, "rev-list", "--first-parent", "--reverse", f"{INTERVAL_START}^..{INTERVAL_END}").splitlines()
    if commits[0] != INTERVAL_START or commits[-1] != INTERVAL_END or len(commits) != 16:
        raise SystemExit("Phase 53 interval drift")
    rows = []
    for commit in commits:
        paths = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines()
        if not paths or any(not path.startswith("modules/rustdesk-fleet/") for path in paths):
            raise SystemExit("unexpected Phase 53 interval path")
        rows.append({"commit": commit, "paths": paths, "path_count": len(paths)})
    later = []
    for commit in git(repo, "rev-list", "--first-parent", f"{FREEZE}..HEAD").splitlines():
        paths = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines()
        if any(is_phase53_execution_path(path) for path in paths):
            later.append(commit)
    if later:
        raise SystemExit("later Phase 53 execution/path commit detected")
    dirty = git(repo, "diff", "--name-only").splitlines()
    if any(is_phase53_execution_path(path) for path in dirty):
        raise SystemExit("dirty Phase 53 path detected")
    return {
        "schema": "phase52-phase53-interval-audit-v1",
        "status": "PASS",
        "read_only": True,
        "mutation_performed": False,
        "source_freeze_commit": FREEZE,
        "interval_head": INTERVAL_END,
        "implementation_start": INTERVAL_START,
        "phase53_execution_frozen": True,
        "new_phase53_execution_count": 0,
        "later_phase53_path_commits": [],
        "first_parent_interval_count": len(commits),
        "first_parent_interval": rows,
        "authority": {"live_authority": False, "replay_authorized": False, "vault_write_authorized": False},
        "secret_material_present": False,
    }


def retained_audit(repo: Path) -> dict[str, object]:
    paths = {
        "supply_observation": repo / "modules/rustdesk-fleet/evidence/phase52/supply-observation.json",
        "capacity_horistic_srv": repo / "modules/rustdesk-fleet/evidence/phase52/capacity-horistic-srv.json",
        "integrated_gate": repo / "modules/rustdesk-fleet/evidence/phase52/integrated-gate.json",
        "gate_b_transaction": repo / "modules/rustdesk-fleet/evidence/phase52/gate-b-transaction.json",
    }
    integrated = json.loads(paths["integrated_gate"].read_text(encoding="utf-8"))
    expected_hashes = {
        "supply_observation": "c699e7aa45efe965ac8092c4ddfbd3416e1170d68afcf4eb70d8ed25a44054db",
        "capacity_horistic_srv": "69997872cbe0b9e2f886cc67b8c0379499628a068cc1e9d6996f60b8df39622e",
        "integrated_gate": "8a70bced3cfa4f0d588707720bc20ebef0ed4e14b0143aca9c5cc154f50eb00a",
        "gate_b_transaction": "d4eeb2da7956c177595d41f6170cdc7ee50a0b6eab3b7bb0054800212d173001",
    }
    actual_hashes = {key: sha(path) for key, path in paths.items()}
    if actual_hashes != expected_hashes:
        raise SystemExit("retained evidence hash drift")
    if integrated.get("selected_candidate") != "horistic-srv":
        raise SystemExit("retained candidate drift")
    checks = integrated.get("checks", [])
    if len(checks) != 11 or any(item.get("status") != "PASS" for item in checks):
        raise SystemExit("retained integrated gate is not 11/11 PASS")
    gate_b = json.loads(paths["gate_b_transaction"].read_text(encoding="utf-8"))
    if (
        integrated.get("public_listener_created") is not False
        or integrated.get("secret_material_present") is not False
        or integrated.get("windows_install_performed") is not False
        or gate_b.get("network_listener_created") is not False
        or gate_b.get("secret_material_present") is not False
        or gate_b.get("windows_install_performed") is not False
        or gate_b.get("live_write_performed") is not True
    ):
        raise SystemExit("retained authority or mutation accounting drift")
    return {
        "schema": "phase52-retained-evidence-audit-v1",
        "status": "PASS",
        "historical_evidence": True,
        "fresh_operational_replay": False,
        "read_only": True,
        "mutation_performed": False,
        "selected_candidate": "horistic-srv",
        "retained_integrated_gate_check_count": 11,
        "retained_integrated_gate_status": "PASS",
        "retained_input_sha256": actual_hashes,
        "historical_live_write_performed": True,
        "current_live_authority": False,
        "current_network_listener_created": False,
        "current_secret_material_present": False,
        "authority": {"live_authority": False, "replay_authorized": False, "vault_write_authorized": False, "listener_created": False},
        "secret_material_present": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("all", "audits", "lanes"), default="all")
    args = parser.parse_args()
    repo = args.repo.resolve()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.mode in {"all", "lanes"}:
        current = lane_current(out / "pytest-current-junit.xml")
        legacy = lane_legacy(out / "pytest-gateb-drift-junit.xml")
        timeout = lane_timeout([out / f"pytest-backup-timeout-{n}.xml" for n in (1, 2, 3)])
    else:
        current = legacy = timeout = None
    fixture = repo / "modules/fleet-backup/tests/test_phase52_backup_b.py"
    verdict = {
        "schema": "phase52-pytest-lanes-v1",
        "status": "PASS",
        "current_lane": current,
        "legacy_gateb_drift_lane": legacy,
        "backup_timeout_lane": {
            **(timeout or {}),
            "fixture_delta": {
                "path": str(fixture.relative_to(repo)),
                "old_sha256": "54669ede1d8848958e63018907dcd2505479d28f4d8b01298c9fd17843279633",
                "new_sha256": sha(fixture),
                "change": "fake rclone timeout branch uses exec sleep 3",
                "production_scripts_changed": False,
            },
        },
        "authority": {"live_authority": False, "replay_authorized": False, "vault_write_authorized": False},
        "secret_material_present": False,
    }
    if args.mode in {"all", "lanes"}:
        (out / "pytest-lanes-verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.mode in {"all", "audits"}:
        (out / "phase53-interval-audit.json").write_text(json.dumps(interval_audit(repo), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out / "retained-phase52-audit.json").write_text(json.dumps(retained_audit(repo), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "mode": args.mode, "current": current["test_count"] if current else None, "legacy": legacy["failure_count"] if legacy else None, "timeout_runs": timeout["consecutive_pass_count"] if timeout else None}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
