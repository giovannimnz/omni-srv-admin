from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "modules/fleet-control-plane/scripts/phase54_network_gate.py"
SPEC = importlib.util.spec_from_file_location("phase54_network_gate", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def _args(root: Path, plan: str) -> argparse.Namespace:
    return argparse.Namespace(
        mode="final",
        plan=plan,
        evidence=str(root / f"{plan}-EVIDENCE.json"),
        gate=str(root / f"{plan}-GATE.json"),
        redact=True,
        started_at="2026-07-23T00:00:00Z",
    )


def _write_inputs(root: Path, plan: str, target_map: dict | None) -> None:
    evidence = {"status": "PASS", "mutations_attempted": False}
    if target_map is not None:
        evidence["target_map"] = target_map
    (root / f"{plan}-EVIDENCE.json").write_text(
        json.dumps(evidence),
        encoding="utf-8",
    )
    rollback = {
        "status": "PASS",
        "host_backups": {
            "status": "PASS",
            "horistic": {
                "checksum_status": "PASS",
                "restore_staging_status": "PASS",
            },
            "srv1": {
                "checksum_status": "PASS",
                "restore_staging_status": "PASS",
            },
        },
    }
    (root / "rollback-receipt.json").write_text(
        json.dumps(rollback),
        encoding="utf-8",
    )


def test_edge_gate_requires_exact_horistic_s23_s20_target_map(tmp_path: Path) -> None:
    args = _args(tmp_path, "54-05")
    _write_inputs(tmp_path, args.plan, gate.EDGE_TARGET_MAP)

    assert gate.run(args) == 0
    receipt = json.loads(Path(args.gate).read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS"
    assert next(item for item in receipt["checks"] if item["id"] == "edge_target_map")["result"] == "PASS"


def test_edge_gate_blocks_when_horistic_wireguard_target_is_missing(tmp_path: Path) -> None:
    args = _args(tmp_path, "54-05")
    incomplete = dict(gate.EDGE_TARGET_MAP)
    incomplete.pop("horistic_wireguard")
    _write_inputs(tmp_path, args.plan, incomplete)

    assert gate.run(args) == 2
    receipt = json.loads(Path(args.gate).read_text(encoding="utf-8"))
    assert receipt["status"] == "BLOCK"
    assert next(item for item in receipt["checks"] if item["id"] == "edge_target_map")["result"] == "BLOCK"


def test_non_edge_plan_does_not_require_edge_target_map(tmp_path: Path) -> None:
    args = _args(tmp_path, "54-04")
    _write_inputs(tmp_path, args.plan, None)

    assert gate.run(args) == 0
    receipt = json.loads(Path(args.gate).read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS"
    assert all(item["id"] != "edge_target_map" for item in receipt["checks"])
