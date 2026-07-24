from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "modules/fleet-control-plane/scripts/phase54_network_gate.py"
SPEC = importlib.util.spec_from_file_location("phase54_network_gate", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def _ts(offset_seconds: int = 0) -> str:
    value = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return value.isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _args(root: Path, plan: str = "54-01", stage: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        mode="final",
        plan=plan,
        stage=stage,
        evidence=str(root / f"{plan}-EVIDENCE.json"),
        gate=str(root / f"{plan}-GATE.json"),
        redact=True,
        max_age_seconds=900,
        started_at=_ts(),
    )


def _observed_check(check_id: str) -> dict[str, object]:
    return {
        "id": check_id,
        "required": True,
        "adapter": "local",
        "command_id": f"phase54.{check_id}",
        "arguments": ["<redacted>"],
        "redacted": True,
        "started_at": _ts(-2),
        "finished_at": _ts(-1),
        "timeout_seconds": 60,
        "exit_code": 0,
        "observed": "PASS",
        "expected": "PASS",
        "result": "PASS",
        "artifact_hashes": {},
    }


def _write_previous_gate(root: Path, plan: str) -> dict[str, str]:
    predecessor = f"54-{int(plan[-2:]) - 1:02d}"
    previous_evidence = root / f"{predecessor}-EVIDENCE.json"
    previous_evidence.write_text('{"observed":"PASS"}\n', encoding="utf-8")
    previous_gate = root / f"{predecessor}-GATE.json"
    previous_gate.write_text(
        json.dumps(
            {
                "schema": "phase54.gate.v1",
                "phase": 54,
                "plan": predecessor,
                "stage": None,
                "status": "PASS",
                "finished_at": _ts(-30),
                "evidence_sha256": _sha(previous_evidence),
                "required_check_ids": ["fixture"],
                "checks": [{"id": "fixture", "required": True, "result": "PASS"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "plan": predecessor,
        "evidence_path": str(previous_evidence),
        "evidence_sha256": _sha(previous_evidence),
        "gate_path": str(previous_gate),
        "gate_sha256": _sha(previous_gate),
    }


def _write_operation_lineage(root: Path, plan: str) -> dict[str, object]:
    input_path = root / f"{plan}-INPUT.json"
    input_path.write_text('{"target":"10.31.1.31"}\n', encoding="utf-8")
    operation_path = root / f"{plan}-OPERATION-PLAN.json"
    operation_path.write_text(
        json.dumps({"plan": plan, "input_hashes": {str(input_path): _sha(input_path)}}) + "\n",
        encoding="utf-8",
    )
    approval_path = root / f"{plan}-APPROVAL.json"
    operation_hash = _sha(operation_path)
    approval_path.write_text(
        json.dumps(
            {
                "plan": plan,
                "operation_plan_sha256": operation_hash,
                "approval_typed": f"APPROVE {plan} {operation_hash}",
                "approval_expires_at": _ts(600),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    anti_drift_path = root / f"{plan}-ANTI-DRIFT.json"
    anti_drift_path.write_text('{"status":"PASS"}\n', encoding="utf-8")
    return {
        "operation_plan_path": str(operation_path),
        "operation_plan_sha256": operation_hash,
        "input_hashes": {str(input_path): _sha(input_path)},
        "approval_path": str(approval_path),
        "approval_sha256": _sha(approval_path),
        "approval_typed": f"APPROVE {plan} {operation_hash}",
        "approval_expires_at": _ts(600),
        "anti_drift_readback_path": str(anti_drift_path),
        "anti_drift_readback_sha256": _sha(anti_drift_path),
        "opc_request_id": "ocid-request-fixture",
        "receipt_state": "PASS",
        "rollback_transaction_sha256": "a" * 64,
    }


def _write_evidence(
    root: Path,
    plan: str = "54-01",
    stage: str | None = None,
) -> tuple[argparse.Namespace, dict[str, object]]:
    args = _args(root, plan, stage)
    artifact = root / "runner-proof.txt"
    artifact.write_text("runner observed proof\n", encoding="utf-8")
    evidence: dict[str, object] = {
        "schema": "phase54.evidence.v1",
        "plan": plan,
        "stage": stage,
        "status": "PASS",
        "generated_at": _ts(-5),
        "expires_at": _ts(600),
        "redacted": True,
        "mutations_attempted": False,
        "checks": [_observed_check(item) for item in gate.required_check_ids(plan, stage)],
        "artifacts": [{"path": str(artifact), "sha256": _sha(artifact)}],
    }
    if plan != "54-01":
        evidence["previous_gate"] = _write_previous_gate(root, plan)
    if stage in {"preview", "approval", "apply"}:
        evidence["operation"] = _write_operation_lineage(root, plan)
    if plan == "54-03":
        receipt = root / "builder-receipt.json"
        receipt.write_text(
            json.dumps(
                {
                    "owner": "oci-admin",
                    "validated": True,
                    "commit": "b" * 40,
                    "targets": {
                        "vcn": "10.31.0.0/16",
                        "subnet": "10.31.1.0/24",
                        "private_ip": "10.31.1.31",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        evidence["builder"] = {
            "owner": "oci-admin",
            "validated": True,
            "commit": "b" * 40,
            "receipt_path": str(receipt),
            "receipt_sha256": _sha(receipt),
            "targets": {
                "vcn": "10.31.0.0/16",
                "subnet": "10.31.1.0/24",
                "private_ip": "10.31.1.31",
            },
        }
    if plan in {"54-02", "54-05", "54-10"}:
        evidence["public_ip"] = {
            "address": "163.176.232.119",
            "ocid": "ocid1.publicip.fixture",
            "baseline_ocid": "ocid1.publicip.fixture",
            "private_ip_ocid": "ocid1.privateip.fixture",
            "baseline_private_ip_ocid": "ocid1.privateip.fixture",
            "label": "horistic-srv-1",
            "state": "ASSIGNED",
            "operation": "read",
        }
    if plan in {"54-07", "54-08", "54-10"}:
        evidence["target_map"] = gate.EDGE_TARGET_MAP
    if plan == "54-10":
        evidence["operational_10_21"] = []
    Path(args.evidence).write_text(json.dumps(evidence) + "\n", encoding="utf-8")
    return args, evidence


def _receipt(args: argparse.Namespace) -> dict[str, object]:
    return json.loads(Path(args.gate).read_text(encoding="utf-8"))


def _check(receipt: dict[str, object], check_id: str) -> dict[str, object]:
    return next(item for item in receipt["checks"] if item["id"] == check_id)


def _assert_blocked(args: argparse.Namespace, check_id: str) -> None:
    assert gate.run(args) != 0
    receipt = _receipt(args)
    assert receipt["status"] == "BLOCK"
    assert _check(receipt, check_id)["result"] == "BLOCK"


def test_complete_runner_observed_required_checks_pass(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)

    assert gate.run(args) == 0
    receipt = _receipt(args)
    assert receipt["status"] == "PASS"
    assert receipt["required_check_ids"] == list(gate.required_check_ids("54-01", None))
    assert all(item["result"] == "PASS" for item in receipt["checks"])


def test_claimed_pass_missing_required_probe_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["checks"].pop()
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "required_checks_complete")


def test_required_probe_unknown_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["checks"][0]["observed"] = "UNKNOWN"
    evidence["checks"][0]["result"] = "UNKNOWN"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "observed_checks")


def test_required_probe_timeout_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["checks"][0]["timeout_seconds"] = 0
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "observed_checks")


def test_required_probe_nonzero_exit_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["checks"][0]["exit_code"] = 1
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "observed_checks")


def test_legacy_blocked_status_is_canonical_block(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["status"] = "BLOCKED"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "legacy_status")


def test_stale_evidence_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["generated_at"] = _ts(-3600)
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "freshness")


def test_tampered_artifact_hash_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    Path(evidence["artifacts"][0]["path"]).write_text("tampered\n", encoding="utf-8")

    _assert_blocked(args, "artifact_hashes")


def test_wrong_evidence_plan_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["plan"] = "54-02"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "plan_id")


def test_unknown_stage_blocks(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)
    args.stage = "invented"

    _assert_blocked(args, "stage")


def test_builder_wrong_target_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-03")
    evidence["builder"]["targets"]["private_ip"] = "10.21.1.21"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "builder_targets")


def test_public_ip_ocid_drift_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-05", "apply")
    evidence["public_ip"]["ocid"] = "ocid1.publicip.drifted"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "public_ip_identity")


def test_s23_mutation_and_wrong_s20_mac_block(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-07", "apply")
    evidence["target_map"]["s23_wireguard"]["to"] = "10.100.100.9"
    evidence["target_map"]["s20_lan"]["mac"] = "00:00:00:00:00:00"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "edge_target_map")


def test_final_operational_10_21_residual_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-10", "sync")
    evidence["operational_10_21"] = ["route 10.21.0.0/16"]
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "zero_operational_10_21")


def test_expired_approval_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-05", "apply")
    evidence["operation"]["approval_expires_at"] = _ts(-1)
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "operation_lineage")


def test_assert_gate_accepts_fresh_hash_valid_receipt(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)
    assert gate.run(args) == 0

    assert gate.assert_gate(args) == 0


def test_assert_gate_rejects_missing_receipt(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)

    assert gate.assert_gate(args) != 0


def test_assert_gate_rejects_malformed_receipt(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)
    Path(args.gate).write_text("{", encoding="utf-8")

    assert gate.assert_gate(args) != 0


def test_assert_gate_rejects_stale_receipt(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)
    assert gate.run(args) == 0
    receipt = _receipt(args)
    receipt["finished_at"] = _ts(-3600)
    Path(args.gate).write_text(json.dumps(receipt), encoding="utf-8")

    assert gate.assert_gate(args) != 0


def test_assert_gate_rejects_tampered_evidence(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    assert gate.run(args) == 0
    evidence["checks"][0]["observed"] = "tampered"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    assert gate.assert_gate(args) != 0


def test_assert_gate_rejects_other_plan_receipt(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)
    assert gate.run(args) == 0
    receipt = _receipt(args)
    receipt["plan"] = "54-02"
    Path(args.gate).write_text(json.dumps(receipt), encoding="utf-8")

    assert gate.assert_gate(args) != 0
