from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "modules/fleet-control-plane/scripts/phase54_network_gate.py"
SPEC = importlib.util.spec_from_file_location("phase54_network_gate", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def _fixture_remote_transport(
    spec: gate.ProbeSpec,
    context: gate.ProbeContext,
) -> dict[str, object]:
    result = {
        "id": spec.check_id,
        "required": True,
        "adapter": "fixture-remote-transport",
        "command_id": f"phase54.{spec.check_id}",
        "started_at": _ts(-2),
        "finished_at": _ts(-1),
        "exit_code": 0,
        "result": "PASS",
        "artifact_hashes": {
            "transport-observation": hashlib.sha256(spec.check_id.encode()).hexdigest()
        },
    }
    if spec.check_id == "full_matrix":
        result["normalized"] = {
            "evidence_sha256": _sha(context.evidence),
            "operational_10_21": [],
            "residual_live": {
                "present": False,
                "count": 0,
                "sha256": gate.sha256_json([]),
            },
            "live_readback_sha256": "f" * 64,
        }
    return result


def _fixture_remote_block(
    spec: gate.ProbeSpec,
    context: gate.ProbeContext,
) -> dict[str, object]:
    del context
    return {
        "id": spec.check_id,
        "required": True,
        "adapter": "fixture-owner-failure",
        "command_id": f"phase54.{spec.check_id}",
        "exit_code": 2,
        "result": "BLOCK",
        "artifact_hashes": {},
    }


def _ts(offset_seconds: int = 0) -> str:
    value = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return value.isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _args(
    root: Path, plan: str = "54-01", stage: str | None = None
) -> argparse.Namespace:
    return argparse.Namespace(
        mode="final",
        plan=plan,
        stage=stage,
        evidence=str(root / f"{plan}-EVIDENCE.json"),
        gate=str(root / f"{plan}-GATE.json"),
        redact=True,
        max_age_seconds=900,
        started_at=_ts(),
        local_transport=_fixture_remote_transport,
        remote_transport=_fixture_remote_transport,
        adapter_validator=lambda plan: True,
        pin_validator=lambda lineage, evidence, receipt, runner_hash: True,
    )


def _write_review_gate(
    root: Path,
    *,
    scope_root: Path = REPO,
) -> tuple[Path, Path]:
    scope = [
        {
            "path": path,
            "sha256": _sha(scope_root / path),
        }
        for path in gate.REVIEW_SCOPE_PATHS
    ]
    evidence_path = root / gate.REVIEW_EVIDENCE_NAME
    review_evidence = {
        "schema": gate.SCHEMA_REVIEW_EVIDENCE,
        "phase": 54,
        "status": "PASS",
        "planner_identity": "planner-agent",
        "reviewer_identity": "independent-plan-checker",
        "started_at": _ts(-30),
        "finished_at": _ts(-20),
        "expires_at": _ts(600),
        "scope": scope,
        "blockers": [],
        "warnings": [],
        "redacted": True,
    }
    evidence_path.write_text(
        json.dumps(review_evidence, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    gate_path = root / gate.REVIEW_GATE_NAME
    review_gate = {
        "schema": gate.SCHEMA_REVIEW_GATE,
        "phase": 54,
        "status": "PASS",
        "planner_identity": review_evidence["planner_identity"],
        "reviewer_identity": review_evidence["reviewer_identity"],
        "started_at": _ts(-15),
        "finished_at": _ts(-10),
        "expires_at": _ts(600),
        "evidence_path": str(evidence_path),
        "evidence_sha256": _sha(evidence_path),
        "scope_sha256": gate.sha256_json(scope),
        "blockers": [],
        "warnings": [],
        "redacted": True,
    }
    gate_path.write_text(
        json.dumps(review_gate, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence_path, gate_path


def _write_previous_gate(root: Path, plan: str) -> dict[str, object]:
    predecessor = f"54-{int(plan[-2:]) - 1:02d}"
    predecessor_stage = gate.TERMINAL_STAGE_BY_PLAN[predecessor]
    previous_args, _ = _write_evidence(root, predecessor, predecessor_stage)
    assert gate.run(previous_args) == 0
    previous_evidence = Path(previous_args.evidence)
    previous_gate = Path(previous_args.gate)
    previous_evidence_json = json.loads(previous_evidence.read_text(encoding="utf-8"))
    previous_chain = (
        previous_evidence_json.get("previous_gate", {}).get("chain_sha256")
        if isinstance(previous_evidence_json.get("previous_gate"), dict)
        else None
    )
    evidence_sha = _sha(previous_evidence)
    gate_sha = _sha(previous_gate)
    lineage: dict[str, object] = {
        "plan": predecessor,
        "stage": predecessor_stage,
        "evidence_path": str(previous_evidence),
        "evidence_sha256": evidence_sha,
        "gate_path": str(previous_gate),
        "gate_sha256": gate_sha,
        "chain_sha256": gate.sha256_json(
            {
                "plan": predecessor,
                "stage": predecessor_stage,
                "evidence_sha256": evidence_sha,
                "gate_sha256": gate_sha,
                "previous_chain_sha256": previous_chain,
            }
        ),
    }
    lineage.update(
        {
            "pin_state": "commit-pinned",
            "source_commit": "c" * 40,
            "atomic_commit_required": False,
        }
    )
    return lineage


def _write_operation_lineage(root: Path, plan: str) -> dict[str, object]:
    contract = gate.OPERATION_CONTRACTS[plan]
    input_path = root / f"{plan}-INPUT.json"
    input_path.write_text('{"target":"10.31.1.31"}\n', encoding="utf-8")
    input_hashes = {str(input_path): _sha(input_path)}
    operations = [sorted(contract["operations"])[0]]
    rollback_path = root / contract["rollback"]
    rollback_path.write_text(
        json.dumps(
            {
                "schema": gate.SCHEMA_ROLLBACK_RECEIPT,
                "owner": contract["owner"],
                "plan": plan,
                "stage": "preview",
                "status": "READY",
                "operations": operations,
                "input_hashes": input_hashes,
                "created_at": _ts(-10),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    operation_path = root / contract["filename"]
    operation_path.write_text(
        json.dumps(
            {
                "schema": gate.SCHEMA_OPERATION_PLAN,
                "owner": contract["owner"],
                "plan": plan,
                "stage": "preview",
                "operations": operations,
                "input_hashes": input_hashes,
                "created_at": _ts(-10),
                "expires_at": _ts(600),
                "rollback_receipt_path": str(rollback_path),
                "rollback_receipt_sha256": _sha(rollback_path),
                "public_ip_binding": {
                    "public_ip_ocid": "ocid1.publicip.fixture",
                    "address": "163.176.232.119",
                    "private_ip_address": "10.31.1.31",
                    "private_ip_ocid": "ocid1.privateip.target",
                    "vnic_ocid": "ocid1.vnic.target",
                    "subnet_ocid": "ocid1.subnet.target",
                    "vcn_ocid": "ocid1.vcn.target",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    approval_path = root / f"{plan}-APPROVAL.json"
    operation_hash = _sha(operation_path)
    approval_expires_at = _ts(600)
    approval_path.write_text(
        json.dumps(
            {
                "schema": gate.SCHEMA_APPROVAL,
                "owner": "human-approval",
                "plan": plan,
                "stage": "approval",
                "actor": "fixture-operator",
                "operation_plan_sha256": operation_hash,
                "approval_typed": f"APPROVE {plan} {operation_hash}",
                "approved_at": _ts(-5),
                "approval_expires_at": approval_expires_at,
                "input_hashes": input_hashes,
                "anti_drift_sha256": gate.sha256_json(input_hashes),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    anti_drift_path = root / f"{plan}-ANTI-DRIFT.json"
    anti_drift_path.write_text(
        json.dumps(
            {
                "schema": "phase54.anti-drift.v1",
                "plan": plan,
                "operation_plan_sha256": operation_hash,
                "input_hashes": input_hashes,
                "status": "PASS",
                "generated_at": _ts(-2),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    apply_path = root / f"{plan}-APPLY-RECEIPT.json"
    apply_path.write_text(
        json.dumps(
            {
                "schema": gate.SCHEMA_APPLY_RECEIPT,
                "owner": contract["owner"],
                "plan": plan,
                "stage": "apply",
                "status": "PASS",
                "operation_plan_sha256": operation_hash,
                "approval_sha256": _sha(approval_path),
                "anti_drift_sha256": _sha(anti_drift_path),
                "rollback_receipt_sha256": _sha(rollback_path),
                "operations": operations,
                "request_ids": ["fixture-request-id"],
                "started_at": _ts(-2),
                "finished_at": _ts(-1),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "operation_plan_path": str(operation_path),
        "operation_plan_sha256": operation_hash,
        "input_hashes": input_hashes,
        "approval_path": str(approval_path),
        "approval_sha256": _sha(approval_path),
        "approval_typed": f"APPROVE {plan} {operation_hash}",
        "approval_expires_at": approval_expires_at,
        "anti_drift_readback_path": str(anti_drift_path),
        "anti_drift_readback_sha256": _sha(anti_drift_path),
        "apply_receipt_path": str(apply_path),
        "apply_receipt_sha256": _sha(apply_path),
    }


def _write_backup_evidence(root: Path) -> dict[str, object]:
    pre_existing: list[dict[str, object]] = []
    for owner in ("srv1", "srv3", "be3"):
        receipt_path = root / f"54-02-{owner.upper()}-BACKUP-RECEIPT.json"
        receipt = {
            "schema": gate.SCHEMA_BACKUP_RECEIPT,
            "classification": "pre-existing-evidence",
            "approval_claimed": False,
            "remote_path": f"/var/backups/phase54/{owner}.tgz",
            "remote_sha256": (
                "a" if owner == "srv1" else "b" if owner == "srv3" else "c"
            )
            * 64,
            "owner": owner,
            "mode": "read-only-proof",
        }
        if owner == "be3":
            receipt.update(
                {
                    "source_branch": "codex/phase54-be3-readonly-evidence-20260726",
                    "source_commit": "24f2562af086625b0678c4573f1c03a77270fc22",
                    "source_evidence_path": "modules/home-router-be3/evidence/phase54/be3-lan-readonly-20260726-final-v13.json",
                    "source_evidence_sha256": "dbb8311dd341a8f9dd71f0da1ea13760aa53cae711525faa170c7d54d15de00c",
                    "metadata_path": "modules/home-router-be3/evidence/phase54/be3-native-export-20260726-final-v11.json",
                    "metadata_sha256": "5d93a2d45323249f4bf4ddc0530f5a03d5c054640ec53a909d8d5d09d02a9aa3",
                    "remote_path": "/home/ubuntu/.local/state/home-router-be3/backups/phase54/be3-native-20260726T052404Z.bin",
                    "remote_sha256": "866adbef8a1434622f0b4028ddaf5b5bd76afaeafc246e7a576b675c889cb781",
                    "size": 32864,
                    "file_mode": "0600",
                    "apply": "NOT RUN",
                    "restore": "NOT RUN",
                }
            )
        receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        pre_existing.append(
            {
                "receipt_path": str(receipt_path),
                "receipt_sha256": _sha(receipt_path),
                "classification": "pre-existing-evidence",
                "approval_claimed": False,
            }
        )
    return {
        "retroactive_approval": False,
        "pre_existing": pre_existing,
        "pending_writes": ["oci_boot_backup"],
    }


def _write_public_ip(
    root: Path,
    plan: str,
    operation_lineage: dict[str, object] | None,
) -> dict[str, object]:
    if plan == "54-02":
        binding = {
            "public_ip_ocid": "ocid1.publicip.fixture",
            "address": "163.176.232.119",
            "private_ip_address": gate.BASELINE_PUBLIC_BINDING,
            "private_ip_ocid": "ocid1.privateip.primary",
            "vnic_ocid": "ocid1.vnic.primary",
            "subnet_ocid": "ocid1.subnet.primary",
        }
        return {
            "address": "163.176.232.119",
            "ocid": binding["public_ip_ocid"],
            "baseline_ocid": binding["public_ip_ocid"],
            "binding": binding["private_ip_address"],
            "private_ip_address": binding["private_ip_address"],
            "private_ip_ocid": binding["private_ip_ocid"],
            "baseline_private_ip_ocid": binding["private_ip_ocid"],
            "vnic_ocid": binding["vnic_ocid"],
            "subnet_ocid": binding["subnet_ocid"],
            "label": "horistic-srv-1",
            "state": "ASSIGNED",
            "lifetime": "RESERVED",
            "scope": "REGION",
            "operation": "read",
            "current_binding_sha256": gate.sha256_json(binding),
        }
    if operation_lineage is None:
        canonical_evidence = json.loads(
            (root / "54-05-EVIDENCE.json").read_text(encoding="utf-8")
        )
        operation_lineage = canonical_evidence["operation"]
    operation_path = Path(operation_lineage["operation_plan_path"])
    operation_hash = operation_lineage["operation_plan_sha256"]
    binding = {
        "public_ip_ocid": "ocid1.publicip.fixture",
        "address": "163.176.232.119",
        "private_ip_address": "10.31.1.31",
        "private_ip_ocid": "ocid1.privateip.target",
        "vnic_ocid": "ocid1.vnic.target",
        "subnet_ocid": "ocid1.subnet.target",
        "vcn_ocid": "ocid1.vcn.target",
    }
    readback_path = root / "54-05-PUBLIC-IP-READBACK.json"
    if plan == "54-05":
        readback_path.write_text(
            json.dumps(
                {
                    "schema": gate.SCHEMA_PUBLIC_IP_READBACK,
                    "status": "PASS",
                    "approved_operation_plan_sha256": operation_hash,
                    "binding": binding,
                    "binding_sha256": gate.sha256_json(binding),
                }
            )
            + "\n",
            encoding="utf-8",
        )
    result = {
        "address": binding["address"],
        "ocid": binding["public_ip_ocid"],
        "baseline_ocid": binding["public_ip_ocid"],
        "private_ip_address": binding["private_ip_address"],
        "private_ip_ocid": binding["private_ip_ocid"],
        "vnic_ocid": binding["vnic_ocid"],
        "subnet_ocid": binding["subnet_ocid"],
        "vcn_ocid": binding["vcn_ocid"],
        "label": "horistic-srv-1",
        "state": "ASSIGNED",
        "operation": "read",
        "approved_operation_plan_path": str(operation_path),
        "approved_operation_plan_sha256": operation_hash,
        "binding_readback_path": str(readback_path),
        "binding_readback_sha256": _sha(readback_path),
        "current_binding_sha256": gate.sha256_json(binding),
    }
    if plan == "54-10":
        evidence_path = root / "54-05-EVIDENCE.json"
        gate_path = root / "54-05-GATE.json"
        result["cutover_anchor"] = {
            "evidence_path": str(evidence_path),
            "evidence_sha256": _sha(evidence_path),
            "gate_path": str(gate_path),
            "gate_sha256": _sha(gate_path),
            "operation_path": str(operation_path),
            "operation_sha256": operation_hash,
            "approval_path": operation_lineage["approval_path"],
            "approval_sha256": operation_lineage["approval_sha256"],
            "apply_path": operation_lineage["apply_receipt_path"],
            "apply_sha256": operation_lineage["apply_receipt_sha256"],
        }
    return result


def _write_s20_retirement(root: Path, decision: str = "retire") -> dict[str, str]:
    receipt_path = root / "54-08-S20-RETIREMENT-RECEIPT.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema": gate.SCHEMA_S20_RETIREMENT_RECEIPT,
                "plan": "54-08",
                "decision": decision,
                "old_peer": "10.100.100.9",
                "peer_present": decision != "retire",
                "allowed_ip_present": decision != "retire",
                "new_peer": "10.100.100.11",
                "new_peer_handshake": "PASS",
                "status": "PASS",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {"receipt_path": str(receipt_path), "receipt_sha256": _sha(receipt_path)}


def _write_stability_gate(root: Path) -> dict[str, str]:
    args, _ = _write_evidence(root, "54-09", "stability")
    assert gate.run(args) == 0
    source_evidence = Path(args.evidence)
    source_gate = Path(args.gate)
    stability_evidence = root / "54-09-STABILITY-EVIDENCE.json"
    stability_gate = root / "54-09-STABILITY-GATE.json"
    source_evidence.rename(stability_evidence)
    source_gate.rename(stability_gate)
    return {
        "evidence_path": str(stability_evidence),
        "evidence_sha256": _sha(stability_evidence),
        "gate_path": str(stability_gate),
        "gate_sha256": _sha(stability_gate),
    }


def _write_knowledge_freeze(root: Path) -> dict[str, str]:
    semantic_names = (
        "54-CONTEXT.md",
        "54-RESEARCH.md",
        "54-VALIDATION.md",
        "54-VALIDATION-CONTRACT.md",
        "54-10-SUMMARY.md",
    )
    artifact_hashes: dict[str, str] = {}
    for name in semantic_names:
        path = root / name
        path.write_text(f"frozen semantic artifact {name}\n", encoding="utf-8")
        artifact_hashes[str(path)] = _sha(path)
    receipt = root / "54-10-KNOWLEDGE-RECEIPTS.json"
    receipt.write_text('{"status":"PASS","read_only":true}\n', encoding="utf-8")
    freeze_path = root / "54-10-KNOWLEDGE-FREEZE.json"
    freeze_path.write_text(
        json.dumps(
            {
                "schema": gate.SCHEMA_KNOWLEDGE_FREEZE,
                "plan": "54-10",
                "status": "FROZEN",
                "mutations_after_freeze": False,
                "graphify": {
                    "stale": False,
                    "commit_stale": False,
                    "relevant_nodes": True,
                    "query": "phase54_network_gate",
                },
                "artifact_hashes": artifact_hashes,
                "receipt_hashes": {str(receipt): _sha(receipt)},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {"path": str(freeze_path), "sha256": _sha(freeze_path)}


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
        "production_mutations_attempted": False,
        "check_inputs": {
            item: {"artifact_hashes": {}}
            for item in gate.required_check_ids(plan, stage)
        },
        "artifacts": [{"path": str(artifact), "sha256": _sha(artifact)}],
    }
    stability_gate = (
        _write_stability_gate(root) if plan == "54-09" and stage == "preview" else None
    )
    if plan != "54-01":
        evidence["previous_gate"] = _write_previous_gate(root, plan)
    if plan == "54-02":
        _write_review_gate(root)
    operation_lineage = None
    if stage in gate.OPERATION_STAGES_BY_PLAN.get(plan, frozenset()):
        operation_lineage = _write_operation_lineage(root, plan)
        evidence["operation"] = operation_lineage
    if plan == "54-02":
        evidence["backups"] = _write_backup_evidence(root)
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
        evidence["public_ip"] = _write_public_ip(root, plan, operation_lineage)
    if plan in {"54-07", "54-08", "54-10"}:
        evidence["target_map"] = json.loads(json.dumps(gate.EDGE_TARGET_MAP))
    if plan == "54-10":
        evidence["knowledge_freeze"] = _write_knowledge_freeze(root)
    if plan == "54-09" and stage == "stability":
        evidence["stability"] = {
            "readings": [
                {"observed_at": _ts(-901), "sha256": "1" * 64},
                {"observed_at": _ts(), "sha256": "2" * 64},
            ]
        }
    if stability_gate is not None:
        evidence["stability_gate"] = stability_gate
    if plan == "54-08" and stage == "sync":
        evidence["s20_retirement"] = _write_s20_retirement(root)
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


def test_assert_review_gate_accepts_exact_current_independent_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_path, gate_path = _write_review_gate(tmp_path)
    args = argparse.Namespace(
        evidence=str(evidence_path),
        gate=str(gate_path),
        max_age_seconds=900,
        scope_root=REPO,
    )

    assert gate.assert_review_gate(args) == 0
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(MODULE_PATH),
            "assert-review-gate",
            "--evidence",
            str(evidence_path),
            "--gate",
            str(gate_path),
        ],
    )
    assert gate.main() == 0
    assert len(gate.REVIEW_SCOPE_PATHS) == 14
    assert tuple(Path(path).name for path in gate.REVIEW_SCOPE_PATHS) == (
        "54-CONTEXT.md",
        "54-RESEARCH.md",
        "54-VALIDATION.md",
        "54-VALIDATION-CONTRACT.md",
        *(f"54-{number:02d}-PLAN.md" for number in range(1, 11)),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "drift",
        "malformed",
        "stale",
        "expired",
        "self-review",
        "finding",
        "non-pass",
        "missing-scope",
        "extra-scope",
    ),
)
def test_assert_review_gate_rejects_adversarial_review_artifacts(
    tmp_path: Path,
    mutation: str,
) -> None:
    evidence_path, gate_path = _write_review_gate(tmp_path)
    review_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    review_gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if mutation == "drift":
        review_evidence["scope"][0]["sha256"] = "0" * 64
    elif mutation == "malformed":
        review_evidence["unknown"] = "not-allowed"
    elif mutation == "stale":
        review_evidence["started_at"] = _ts(-4000)
        review_evidence["finished_at"] = _ts(-3900)
        review_gate["started_at"] = _ts(-3800)
        review_gate["finished_at"] = _ts(-3700)
    elif mutation == "expired":
        review_evidence["expires_at"] = _ts(-1)
        review_gate["expires_at"] = _ts(-1)
    elif mutation == "self-review":
        review_evidence["reviewer_identity"] = review_evidence["planner_identity"]
        review_gate["reviewer_identity"] = review_evidence["planner_identity"]
    elif mutation == "finding":
        review_evidence["warnings"] = ["unresolved warning"]
        review_gate["warnings"] = ["unresolved warning"]
    elif mutation == "non-pass":
        review_evidence["status"] = "UNKNOWN"
        review_gate["status"] = "UNKNOWN"
    elif mutation == "missing-scope":
        review_evidence["scope"].pop()
    else:
        review_evidence["scope"].append({"path": "unknown.md", "sha256": "0" * 64})
    evidence_path.write_text(
        json.dumps(review_evidence, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    review_gate["evidence_sha256"] = _sha(evidence_path)
    review_gate["scope_sha256"] = gate.sha256_json(review_evidence["scope"])
    gate_path.write_text(
        json.dumps(review_gate, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        evidence=str(evidence_path),
        gate=str(gate_path),
        max_age_seconds=900,
        scope_root=REPO,
    )

    assert gate.assert_review_gate(args) != 0


def test_54_02_final_requires_independent_review_gate(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path, "54-02", "preflight")
    assert gate.run(args) == 0
    observed = _check(_receipt(args), "observed_checks")["observed"]
    review_check = next(
        item for item in observed if item["id"] == "independent_review_gate"
    )
    assert review_check["adapter"] == "runner-contract"
    assert review_check["result"] == "PASS"
    (tmp_path / gate.REVIEW_GATE_NAME).unlink()

    _assert_blocked(args, "observed_checks")


def test_probe_registry_covers_every_required_tuple_with_physical_or_derived_specs() -> (
    None
):
    expected = {
        (plan, stage, check_id)
        for plan, stages in gate.STAGES_BY_PLAN.items()
        for stage in stages
        for check_id in gate.required_check_ids(plan, stage)
    }
    assert set(gate.PROBE_REGISTRY) == expected
    assert all(
        spec.kind in {"local", "remote-owner", "runner-contract"}
        for spec in gate.PROBE_REGISTRY.values()
    )
    assert all(
        spec.argv
        for spec in gate.PROBE_REGISTRY.values()
        if spec.kind == "remote-owner"
    )
    assert all(
        not spec.argv
        for spec in gate.PROBE_REGISTRY.values()
        if spec.kind == "runner-contract"
    )


def test_physical_owner_adapter_coverage_is_exact_for_every_remote_plan() -> None:
    for plan in gate.PLAN_IDS[1:]:
        assert gate._adapter_coverage_valid(plan), plan


def test_final_blocks_before_owner_adapter_coverage_is_ready(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path, "54-02", "preflight")
    args.adapter_validator = lambda plan: False
    assert gate.run(args) != 0
    assert _check(_receipt(args), "adapter_coverage")["result"] == "BLOCK"


def test_real_local_probe_executor_integration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_local_command(
        argv: list[str],
        *,
        timeout: int = 25,
    ) -> tuple[int, bytes, bytes]:
        del timeout
        calls.append(argv)
        if argv[1:2] == ["status"]:
            return 0, b'{"commit_stale":false,"stale":false}', b""
        if argv[1:2] == ["query"]:
            return 0, b'{"matches":["Phase54 network gate adapter workstream"]}', b""
        if argv[1:2] == ["init-plan-phase"]:
            return 0, b"true\n", b""
        if "pytest" in argv:
            return 0, b"3 passed in 1.00s\n", b""
        raise AssertionError(argv)

    monkeypatch.setattr(gate, "_run_local_command", fake_local_command)
    for check_id in gate.BASE_REQUIRED_CHECK_IDS["54-01"]:
        assert gate.run_local_probe(check_id) == 0
    assert any(argv[1:2] == ["init-plan-phase"] for argv in calls)
    assert any(argv[1:2] == ["status"] for argv in calls)
    assert any(argv[1:2] == ["query"] for argv in calls)
    selectors = [argv[-1] for argv in calls if "pytest" in argv]
    assert any("probe_registry" in selector for selector in selectors)
    assert any("manually_fabricated" in selector for selector in selectors)


@pytest.mark.parametrize("failure", ("stale", "commit-stale", "irrelevant-query"))
def test_graphify_probe_blocks_stale_or_irrelevant_results(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    def fixture_command(
        argv: list[str],
        *,
        timeout: int = 25,
    ) -> tuple[int, bytes, bytes]:
        del timeout
        if argv[1:2] == ["status"]:
            return (
                0,
                json.dumps(
                    {
                        "stale": failure == "stale",
                        "commit_stale": failure == "commit-stale",
                    }
                ).encode(),
                b"",
            )
        return (
            0,
            (
                b'{"matches":["unrelated node"]}'
                if failure == "irrelevant-query"
                else b'{"matches":["Phase54 network gate adapter workstream"]}'
            ),
            b"",
        )

    monkeypatch.setattr(gate, "_run_local_command", fixture_command)
    assert not gate._graphify_probe(Path("/repo/scripts/graphify-sync.sh"))


def test_run_fixed_argv_uses_exact_safe_subprocess_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class Completed:
        returncode = 0
        stdout = json.dumps(
            {
                "schema": "phase54.check-observation.v1",
                "probe_id": "fixed",
                "status": "PASS",
                "read_only": True,
                "mutation_performed": False,
                "secret_material_present": False,
                "request_id": "fixed-request",
                "observed_sha256": "a" * 64,
            }
        ).encode()
        stderr = b""

    def fake_run(argv: list[str], **kwargs: object) -> Completed:
        calls.append((argv, kwargs))
        return Completed()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    monkeypatch.setenv("HOME", "/fixture/home")
    monkeypatch.setenv("CODEX_HOME", "/fixture/codex")
    spec = gate.ProbeSpec("54-01", None, "fixed", "local", ("/usr/bin/fixed", "probe"))
    context = gate.ProbeContext(
        "54-01", None, tmp_path / "evidence.json", tmp_path, 900
    )
    assert gate.run_fixed_argv(spec, context)["result"] == "PASS"
    argv, kwargs = calls[0]
    assert argv == ["/usr/bin/fixed", "probe"]
    assert kwargs["shell"] is False
    assert kwargs["stdin"] is gate.subprocess.DEVNULL
    assert "ATIUS_MCP_TOKEN" not in kwargs["env"]
    assert kwargs["env"]["HOME"] == "/fixture/home"
    assert kwargs["env"]["CODEX_HOME"] == "/fixture/codex"


@pytest.mark.parametrize(
    "missing",
    (
        "read_only",
        "mutation_performed",
        "secret_material_present",
        "request_id",
        "observed_sha256",
    ),
)
def test_run_fixed_argv_rejects_incomplete_read_only_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    payload = {
        "schema": "phase54.check-observation.v1",
        "probe_id": "fixed",
        "status": "PASS",
        "read_only": True,
        "mutation_performed": False,
        "secret_material_present": False,
        "request_id": "fixed-request",
        "observed_sha256": "a" * 64,
    }
    payload.pop(missing)

    class Completed:
        returncode = 0
        stdout = json.dumps(payload).encode()
        stderr = b""

    monkeypatch.setattr(gate.subprocess, "run", lambda *args, **kwargs: Completed())
    spec = gate.ProbeSpec("54-01", None, "fixed", "local", ("/usr/bin/fixed",))
    context = gate.ProbeContext(
        "54-01", None, tmp_path / "evidence.json", tmp_path, 900
    )
    assert gate.run_fixed_argv(spec, context)["result"] == "BLOCK"


@pytest.mark.parametrize(
    "mutation",
    ("missing-normalized", "wrong-target", "wrong-evidence-hash", "secret-field"),
)
def test_remote_normalized_semantics_are_fixed_hash_bound_and_secret_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    evidence_path = tmp_path / "54-03-EVIDENCE.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schema": gate.SCHEMA_EVIDENCE,
                "plan": "54-03",
                "stage": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    evidence_sha = _sha(evidence_path)
    payload: dict[str, object] = {
        "schema": "phase54.check-observation.v1",
        "probe_id": "builder_targets",
        "status": "PASS",
        "read_only": True,
        "mutation_performed": False,
        "secret_material_present": False,
        "request_id": "oci-builder-targets",
        "observed_sha256": "a" * 64,
        "evidence_sha256": evidence_sha,
        "normalized": {
            "evidence_sha256": evidence_sha,
            "operation": "peering.address_plan",
            "semantic": {
                "applies_live_oci_writes": False,
                "target_contains_10_21": False,
                "target": {
                    "vcn": "10.31.0.0/16",
                    "subnet": "10.31.1.0/24",
                    "private_ip": "10.31.1.31",
                },
            },
        },
    }
    if mutation == "missing-normalized":
        payload.pop("normalized")
    elif mutation == "wrong-target":
        payload["normalized"]["semantic"]["target"]["private_ip"] = "10.21.1.21"
    elif mutation == "wrong-evidence-hash":
        payload["normalized"]["evidence_sha256"] = "0" * 64
    else:
        payload["normalized"]["token"] = "must-not-appear"

    class Completed:
        returncode = 0
        stdout = json.dumps(payload).encode()
        stderr = b""

    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> Completed:
        del kwargs
        calls.append(argv)
        return Completed()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    spec = gate.ProbeSpec(
        "54-03",
        None,
        "builder_targets",
        "remote-owner",
        ("/usr/bin/python3", "/repo/phase54_probe_adapters.py", "probe"),
    )
    context = gate.ProbeContext("54-03", None, evidence_path, tmp_path, 900)
    assert gate.run_fixed_argv(spec, context)["result"] == "BLOCK"
    assert calls[0][-2:] == ["--evidence", str(evidence_path.resolve())]


def test_claimed_pass_missing_required_probe_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["check_inputs"].pop(next(iter(evidence["check_inputs"])))
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "required_checks_complete")


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "adapter",
        "argv",
        "command",
        "command_id",
        "host",
        "tool",
        "result",
        "observed",
        "exit_code",
    ),
)
def test_check_inputs_reject_executor_control_fields(
    tmp_path: Path,
    forbidden_field: str,
) -> None:
    args, evidence = _write_evidence(tmp_path)
    check_id = next(iter(evidence["check_inputs"]))
    evidence["check_inputs"][check_id][forbidden_field] = "PASS"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "required_checks_complete")


@pytest.mark.parametrize(
    "payload",
    (";touch /tmp/pwn", "$(touch /tmp/pwn)", "line1\nline2", "-oProxyCommand=bad"),
)
def test_check_inputs_reject_injection_payloads(tmp_path: Path, payload: str) -> None:
    args, evidence = _write_evidence(tmp_path)
    check_id = next(iter(evidence["check_inputs"]))
    evidence["check_inputs"][check_id]["argv"] = payload
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "required_checks_complete")


def test_manually_fabricated_happy_path_blocks_without_runner_success(
    tmp_path: Path,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    args.remote_transport = _fixture_remote_block
    evidence["fabricated_receipt"] = {
        "schema": "phase54.check-observation.v1",
        "status": "PASS",
    }
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


def test_unredacted_secret_material_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["note"] = "Authorization: Bearer leaked-fixture"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "redaction")


def test_wrong_evidence_plan_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path)
    evidence["plan"] = "54-02"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "plan_id")


def test_unknown_stage_blocks(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)
    args.stage = "invented"

    _assert_blocked(args, "stage")


def test_plan_contract_uses_canonical_evidence_and_literal_tokens() -> None:
    phase_dir = (
        REPO
        / ".planning/workstreams/network-horistic-readdress/phases"
        / "54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re"
    )
    final_call = re.compile(
        r"phase54_network_gate\.py final --plan (54-\d{2})"
        r"(?:(?!phase54_network_gate\.py).)*?"
        r"--evidence ([^\s<]+)"
    )
    for plan_path in sorted(phase_dir.glob("54-??-PLAN.md")):
        text = plan_path.read_text(encoding="utf-8")
        calls = final_call.findall(text)
        assert calls, plan_path
        for plan, evidence_path in calls:
            assert Path(evidence_path).name == f"{plan}-EVIDENCE.json", (
                plan_path,
                plan,
                evidence_path,
            )
        assert "APROVAR" not in text
        assert "APPROVE BACKUP" not in text
        assert "APPROVE RETIREMENT" not in text

    for plan in ("54-02", "54-04", "54-05", "54-06", "54-07", "54-08", "54-09"):
        text = (phase_dir / f"{plan}-PLAN.md").read_text(encoding="utf-8")
        assert f"APPROVE {plan} &lt;sha256-completo&gt;" in text
    assert "--plan 54-09 --stage apply" in (phase_dir / "54-09-PLAN.md").read_text(
        encoding="utf-8"
    )
    assert "--plan 54-10 --stage apply" not in (phase_dir / "54-10-PLAN.md").read_text(
        encoding="utf-8"
    )
    for plan in ("54-02", "54-08", "54-09"):
        text = (phase_dir / f"{plan}-PLAN.md").read_text(encoding="utf-8")
        assert text.count("<task ") <= 3
    for plan in gate.PLAN_IDS:
        text = (phase_dir / f"{plan}-PLAN.md").read_text(encoding="utf-8")
        if plan != "54-01":
            assert f"adapters-ready --plan {plan} --smoke" in text
        assert "<adapter_gate>" not in text
        frontmatter = text.split("---", 2)[1]
        files_section = frontmatter.split("files_modified:", 1)[1].split(
            "autonomous:", 1
        )[0]
        assert files_section.count("\n  - ") <= 9
        if plan == "54-01":
            assert (
                "modules/fleet-control-plane/scripts/phase54_probe_adapters.py"
                in files_section
            )
            assert (
                "modules/fleet-control-plane/tests/test_phase54_probe_adapters.py"
                in files_section
            )
        else:
            assert (
                "modules/fleet-control-plane/scripts/phase54_probe_adapters.py"
                not in files_section
            )
            assert (
                "modules/fleet-control-plane/tests/test_phase54_probe_adapters.py"
                not in files_section
            )
    plan02 = (phase_dir / "54-02-PLAN.md").read_text(encoding="utf-8")
    plan02_frontmatter = plan02.split("---", 2)[1]
    plan02_files = plan02_frontmatter.split("files_modified:", 1)[1].split(
        "autonomous:", 1
    )[0]
    assert plan02_files.count("\n  - ") == 7
    task1 = plan02.split("<name>Task 1:", 1)[1].split("</task>", 1)[0]
    task1_files = task1.split("<files>", 1)[1].split("</files>", 1)[0]
    task1_read_first = task1.split("<read_first>", 1)[1].split("</read_first>", 1)[0]
    must_haves = plan02_frontmatter.split("must_haves:", 1)[1]
    for owner in ("SRV1", "SRV3", "BE3"):
        receipt = f"54-02-{owner}-BACKUP-RECEIPT.json"
        assert receipt not in plan02_files
        assert receipt not in task1_files
        assert receipt in task1_read_first
        assert receipt in must_haves
    produced = plan02.split("## Artifacts this phase produces", 1)[1].split(
        "## Pre-existing evidence", 1
    )[0]
    assert "BACKUP-RECEIPT.json" not in produced
    assert "commit-pinned e estritamente read-only" in task1
    assert "nunca criá-los, reemiti-los" in task1
    assert "54-02-BACKUP-RECEIPTS.json" not in plan02
    for review_artifact in (
        gate.REVIEW_EVIDENCE_NAME,
        gate.REVIEW_GATE_NAME,
    ):
        assert review_artifact not in plan02_files
        assert review_artifact not in task1_files
        assert review_artifact in task1_read_first
        assert review_artifact in must_haves
    plan03 = (phase_dir / "54-03-PLAN.md").read_text(encoding="utf-8")
    task2 = plan03.split("<name>Task 2:", 1)[1].split("</task>", 1)[0]
    assert "54-03-GATE.json" in task2.split("</files>", 1)[0]

    predecessor_contracts = {
        "54-02": ("54-01", None),
        "54-04": ("54-03", None),
        "54-05": ("54-04", "apply"),
        "54-06": ("54-05", "apply"),
        "54-07": ("54-06", "apply"),
        "54-08": ("54-07", "apply"),
        "54-09": ("54-08", "sync"),
        "54-10": ("54-09", "apply"),
    }
    for plan, (predecessor, terminal_stage) in predecessor_contracts.items():
        text = (phase_dir / f"{plan}-PLAN.md").read_text(encoding="utf-8")
        first_verify = text.split("<verify><automated>", 1)[1].split("</automated>", 1)[
            0
        ]
        commands = [item.strip() for item in first_verify.split("&amp;&amp;")]
        if plan == "54-02":
            assert "phase54_network_gate.py assert-review-gate " in commands[0]
            assert gate.REVIEW_EVIDENCE_NAME in commands[0]
            assert gate.REVIEW_GATE_NAME in commands[0]
            first_command = commands[1]
        else:
            first_command = commands[0]
        assert (
            f"phase54_network_gate.py assert-gate --plan {predecessor} "
        ) in first_command
        assert f"{predecessor}-EVIDENCE.json" in first_command
        assert f"{predecessor}-GATE.json" in first_command
        if terminal_stage is None:
            assert "--stage" not in first_command
        else:
            assert f"--stage {terminal_stage}" in first_command


def test_stage_contracts_cover_backup_device_retirement_and_read_only_sync(
    tmp_path: Path,
) -> None:
    expected = {
        "54-02": {"preflight", "preview", "approval", "apply"},
        "54-08": {"preview", "approval", "apply", "sync"},
        "54-09": {"stability", "preview", "approval", "apply"},
        "54-10": {"preflight", "sync"},
    }
    for plan, stages in expected.items():
        assert gate.STAGES_BY_PLAN[plan] == frozenset(stages)
        for stage in stages:
            args, _ = _write_evidence(tmp_path, plan, stage)
            assert gate.run(args) == 0, (plan, stage, _receipt(args))

    args, _ = _write_evidence(tmp_path, "54-10", "preflight")
    args.stage = "apply"
    _assert_blocked(args, "stage")


def test_54_09_preview_requires_exact_stability_gate_hash(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-09", "preview")
    assert gate.run(args) == 0
    evidence["stability_gate"]["gate_sha256"] = "0" * 64
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")
    _assert_blocked(args, "observed_checks")


@pytest.mark.parametrize("mutation", ("manifest-hash", "graph-stale", "receipt-hash"))
def test_54_10_preflight_requires_frozen_semantic_manifest(
    tmp_path: Path,
    mutation: str,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-10", "preflight")
    assert gate.run(args) == 0
    freeze_path = Path(evidence["knowledge_freeze"]["path"])
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if mutation == "manifest-hash":
        first = next(iter(freeze["artifact_hashes"]))
        freeze["artifact_hashes"][first] = "0" * 64
    elif mutation == "graph-stale":
        freeze["graphify"]["stale"] = True
    else:
        first = next(iter(freeze["receipt_hashes"]))
        freeze["receipt_hashes"][first] = "0" * 64
    freeze_path.write_text(json.dumps(freeze) + "\n", encoding="utf-8")
    evidence["knowledge_freeze"]["sha256"] = _sha(freeze_path)
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")
    _assert_blocked(args, "observed_checks")


def test_raw_operation_plan_is_not_canonical_evidence(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-04", "preview")
    operation_path = Path(evidence["operation"]["operation_plan_path"])
    args.evidence = str(operation_path)

    _assert_blocked(args, "evidence_machine_readable")


@pytest.mark.parametrize("mutation", ("stage", "name", "hash"))
def test_predecessor_wrong_stage_name_or_hash_blocks(
    tmp_path: Path,
    mutation: str,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    lineage = evidence["previous_gate"]
    if mutation == "stage":
        lineage["stage"] = "preview"
    elif mutation == "name":
        wrong = tmp_path / "renamed-gate.json"
        Path(lineage["gate_path"]).rename(wrong)
        lineage["gate_path"] = str(wrong)
        lineage["gate_sha256"] = _sha(wrong)
    else:
        lineage["gate_sha256"] = "0" * 64
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "previous_gate_lineage")


def test_predecessor_depth_guard_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    assert not gate._previous_gate_valid(
        evidence,
        "54-02",
        tmp_path,
        900,
        visited=frozenset(),
        depth=gate.MAX_PREDECESSOR_DEPTH,
        remote_transport=_fixture_remote_transport,
        pin_validator=lambda lineage, evidence_path, gate_path, runner_hash: True,
    )


def test_immediate_predecessor_requires_commit_pin_even_for_54_01(
    tmp_path: Path,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    lineage = evidence["previous_gate"]
    assert lineage["pin_state"] == "commit-pinned"
    assert lineage["source_commit"] == "c" * 40
    assert lineage["atomic_commit_required"] is False
    assert gate.run(args) == 0

    lineage.update(
        {
            "pin_state": "bootstrap-uncommitted",
            "source_commit": None,
            "atomic_commit_required": True,
        }
    )
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")
    _assert_blocked(args, "previous_gate_lineage")


def test_successors_require_immediate_predecessor_commit_pin(
    tmp_path: Path,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-03")
    lineage = evidence["previous_gate"]
    lineage.update(
        {
            "pin_state": "bootstrap-uncommitted",
            "source_commit": None,
            "atomic_commit_required": True,
        }
    )
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")
    _assert_blocked(args, "previous_gate_lineage")


def test_sync_requires_hash_bound_apply_receipt(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-08", "sync")
    evidence["operation"].pop("apply_receipt_path")
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "operation_lineage")


def test_non_literal_approval_tokens_block(tmp_path: Path) -> None:
    for index, token_template in enumerate(
        (
            "APROVAR 54-05 {hash}",
            "APPROVE BACKUP 54-05 {hash}",
            "APPROVE RETIREMENT 54-05 {hash}",
        )
    ):
        root = tmp_path / str(index)
        root.mkdir()
        args, evidence = _write_evidence(root, "54-05", "approval")
        operation = evidence["operation"]
        operation_hash = operation["operation_plan_sha256"]
        approval_path = Path(operation["approval_path"])
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        typed = token_template.format(hash=operation_hash)
        approval["approval_typed"] = typed
        approval_path.write_text(json.dumps(approval) + "\n", encoding="utf-8")
        operation["approval_typed"] = typed
        operation["approval_sha256"] = _sha(approval_path)
        Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

        _assert_blocked(args, "operation_lineage")


def test_pre_existing_backup_cannot_claim_retroactive_approval(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    evidence["backups"]["retroactive_approval"] = True
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "backup_evidence_classification")


def test_existing_srv_backups_cannot_be_reclassified_as_pending_writes(
    tmp_path: Path,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    evidence["backups"]["pending_writes"].append("srv1_existing_backup")
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "backup_evidence_classification")


def test_backup_receipt_name_and_schema_are_exact(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    srv1 = evidence["backups"]["pre_existing"][0]
    receipt_path = Path(srv1["receipt_path"])
    wrong_path = receipt_path.with_name("srv1-backup-receipt.json")
    receipt_path.rename(wrong_path)
    srv1["receipt_path"] = str(wrong_path)
    srv1["receipt_sha256"] = _sha(wrong_path)
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "backup_evidence_classification")


def test_backup_receipt_wrong_schema_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    srv3 = evidence["backups"]["pre_existing"][1]
    receipt_path = Path(srv3["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["schema"] = "phase54.backup-receipt.v0"
    receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    srv3["receipt_sha256"] = _sha(receipt_path)
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "backup_evidence_classification")


def test_be3_backup_receipt_exact_external_receipt_is_required(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    be3 = evidence["backups"]["pre_existing"][2]
    receipt_path = Path(be3["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["source_commit"] = "0" * 40
    receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    be3["receipt_sha256"] = _sha(receipt_path)
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "backup_evidence_classification")


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


@pytest.mark.parametrize("mutation", ("public-ocid", "binding"))
def test_public_ip_54_02_normalized_baseline_is_exact(
    tmp_path: Path,
    mutation: str,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-02", "preflight")
    public = evidence["public_ip"]
    semantic = {
        "reserved_public_ips": [
            {
                "public_ip_ocid": public["ocid"],
                "label": "horistic-srv-1",
                "address": "163.176.232.119",
                "private_ip_ocid": public["private_ip_ocid"],
                "lifecycle_state": "ASSIGNED",
                "lifetime": "RESERVED",
            }
        ],
        "private_ips": [
            {
                "private_ip_ocid": public["private_ip_ocid"],
                "address": gate.BASELINE_PUBLIC_BINDING,
                "vnic_ocid": public["vnic_ocid"],
                "subnet_ocid": public["subnet_ocid"],
            },
            {
                "private_ip_ocid": "ocid1.privateip.secondary",
                "address": "10.21.1.21",
                "vnic_ocid": "ocid1.vnic.secondary",
                "subnet_ocid": "ocid1.subnet.secondary",
            },
        ],
    }
    evidence_sha = _sha(Path(args.evidence))
    normalized = {
        "evidence_sha256": evidence_sha,
        "operation": "inventory.get",
        "semantic": semantic,
    }
    payload = {
        "evidence_sha256": evidence_sha,
        "normalized": normalized,
    }
    spec = gate.ProbeSpec(
        "54-02",
        "preflight",
        "public_ip_baseline",
        "remote-owner",
        (),
    )
    context = gate.ProbeContext(
        "54-02",
        "preflight",
        Path(args.evidence),
        tmp_path,
        900,
    )
    assert gate._normalized_probe_valid(spec, context, payload)
    if mutation == "public-ocid":
        semantic["reserved_public_ips"][0]["public_ip_ocid"] = "ocid1.publicip.wrong"
    else:
        semantic["private_ips"][0]["address"] = "10.21.1.21"
    assert not gate._normalized_probe_valid(spec, context, payload)


def _dns_baseline_normalized(evidence_sha: str) -> dict[str, object]:
    authority = {
        "server": "10.89.53.10",
        "a_aa": True,
        "ptr_aa": False,
        "soa_aa": True,
        "ns_aa": True,
        "aa": False,
        "nxdomain": True,
        "a_address": None,
        "ptr_owner": None,
        "soa": True,
        "ns": True,
    }
    resolver_matrix = {
        "10.11.1.11": {
            "a": True,
            "ptr": True,
            "soa": True,
            "ns": True,
            "nxdomain": True,
        },
        "127.0.0.2": {
            "a": True,
            "ptr": True,
            "soa": False,
            "ns": False,
            "nxdomain": False,
        },
    }
    resolvers = {
        "servers": ["10.11.1.11", "127.0.0.2"],
        "nxdomain_count": 1,
        "soa_count": 1,
        "ns_count": 1,
        "a_ptr_complete": True,
        "a_address": "10.21.1.21",
        "ptr_owner": "21.1.21.10.in-addr.arpa",
        "soa": False,
        "ns": False,
        "matrix": resolver_matrix,
    }
    material = {
        "expected_address": "10.21.1.21",
        "expected_reverse": "21.1.21.10.in-addr.arpa",
        "authority": authority,
        "resolvers": resolvers,
    }
    return {
        "evidence_sha256": evidence_sha,
        **material,
        "ttl_min": 300,
        "baseline_gap": {
            "schema": "phase54.dns-baseline-gap.v1",
            "authority_missing": ["A", "PTR"],
            "resolver_missing": {
                "10.11.1.11": [],
                "127.0.0.2": ["NS", "NXDOMAIN", "SOA"],
            },
            "observed_sha256": gate.sha256_json(material),
        },
    }


@pytest.mark.parametrize(
    "mutation",
    ("missing-gap", "tampered-a", "resolver-missing-mismatch"),
)
def test_dns_54_02_requires_explicit_hash_bound_baseline_gap(
    tmp_path: Path,
    mutation: str,
) -> None:
    args, _ = _write_evidence(tmp_path, "54-02", "preflight")
    evidence_sha = _sha(Path(args.evidence))
    normalized = _dns_baseline_normalized(evidence_sha)
    payload = {"evidence_sha256": evidence_sha, "normalized": normalized}
    context = gate.ProbeContext(
        "54-02",
        "preflight",
        Path(args.evidence),
        tmp_path,
        900,
    )
    spec = gate.ProbeSpec(
        "54-02",
        "preflight",
        "dns_edge_baseline",
        "remote-owner",
        (),
    )
    assert gate._normalized_probe_valid(spec, context, payload)
    if mutation == "missing-gap":
        normalized.pop("baseline_gap")
    elif mutation == "tampered-a":
        normalized["resolvers"]["a_address"] = "10.21.1.99"
    else:
        normalized["baseline_gap"]["resolver_missing"]["127.0.0.2"] = [
            "SOA",
            "NS",
            "NXDOMAIN",
        ]
    assert not gate._normalized_probe_valid(spec, context, payload)

    strict_spec = gate.ProbeSpec(
        "54-06",
        "preview",
        "freeipa_authority",
        "remote-owner",
        (),
    )
    assert not gate._normalized_probe_valid(
        strict_spec,
        gate.ProbeContext(
            "54-06",
            "preview",
            Path(args.evidence),
            tmp_path,
            900,
        ),
        payload,
    )


def _dns_strict_normalized(evidence_sha: str) -> dict[str, object]:
    expected_address = "10.21.1.21"
    expected_reverse = "21.1.21.10.in-addr.arpa"
    authority = {
        "server": "10.89.53.10",
        "a_aa": True,
        "ptr_aa": True,
        "soa_aa": True,
        "ns_aa": True,
        "aa": True,
        "nxdomain": True,
        "a_address": expected_address,
        "ptr_owner": expected_reverse,
        "soa": True,
        "ns": True,
    }
    matrix = {
        server: {
            "a": True,
            "ptr": True,
            "soa": True,
            "ns": True,
            "nxdomain": True,
        }
        for server in ("10.11.1.11", "127.0.0.2")
    }
    resolvers = {
        "servers": ["10.11.1.11", "127.0.0.2"],
        "nxdomain_count": 2,
        "soa_count": 2,
        "ns_count": 2,
        "a_ptr_complete": True,
        "a_address": expected_address,
        "ptr_owner": expected_reverse,
        "soa": True,
        "ns": True,
        "matrix": matrix,
    }
    return {
        "evidence_sha256": evidence_sha,
        "expected_address": expected_address,
        "expected_reverse": expected_reverse,
        "authority": authority,
        "resolvers": resolvers,
        "ttl_min": 300,
    }


@pytest.mark.parametrize(
    "mutation",
    (
        "authority-ptr-owner",
        "authority-ptr-aa",
        "resolver-ptr-owner",
        "resolver-soa-summary",
        "resolver-ns-count",
        "resolver-matrix-cell",
        "resolver-matrix-shape",
    ),
)
def test_dns_54_06_strict_normalized_contract_rejects_tampering(
    tmp_path: Path,
    mutation: str,
) -> None:
    args, _ = _write_evidence(tmp_path, "54-02", "preflight")
    evidence_sha = _sha(Path(args.evidence))
    normalized = _dns_strict_normalized(evidence_sha)
    payload = {"evidence_sha256": evidence_sha, "normalized": normalized}
    context = gate.ProbeContext(
        "54-06",
        "preview",
        Path(args.evidence),
        tmp_path,
        900,
    )
    spec = gate.ProbeSpec(
        "54-06",
        "preview",
        "freeipa_authority",
        "remote-owner",
        (),
    )
    assert gate._normalized_probe_valid(spec, context, payload)

    if mutation == "authority-ptr-owner":
        normalized["authority"]["ptr_owner"] = "wrong.in-addr.arpa"
    elif mutation == "authority-ptr-aa":
        normalized["authority"]["ptr_aa"] = False
    elif mutation == "resolver-ptr-owner":
        normalized["resolvers"]["ptr_owner"] = "wrong.in-addr.arpa"
    elif mutation == "resolver-soa-summary":
        normalized["resolvers"]["soa"] = False
    elif mutation == "resolver-ns-count":
        normalized["resolvers"]["ns_count"] = 1
    elif mutation == "resolver-matrix-cell":
        normalized["resolvers"]["matrix"]["127.0.0.2"]["ns"] = False
    else:
        normalized["resolvers"]["matrix"]["127.0.0.2"].pop("nxdomain")

    assert not gate._normalized_probe_valid(spec, context, payload)


def test_public_ip_target_cannot_reuse_old_private_binding(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-05", "apply")
    evidence["public_ip"]["private_ip_address"] = "10.21.1.21"
    evidence["public_ip"]["private_ip_ocid"] = "ocid1.privateip.old"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "public_ip_identity")


def test_public_ip_target_ids_must_match_approved_operation_and_readback(
    tmp_path: Path,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-05", "apply")
    evidence["public_ip"]["vnic_ocid"] = "ocid1.vnic.unapproved"
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "public_ip_identity")


def test_public_ip_readback_hash_tamper_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-10", "preflight")
    readback_path = Path(evidence["public_ip"]["binding_readback_path"])
    readback_path.write_text('{"tampered":true}\n', encoding="utf-8")

    _assert_blocked(args, "public_ip_identity")


@pytest.mark.parametrize(
    "artifact",
    ("evidence", "gate", "operation", "approval", "apply"),
)
def test_public_ip_54_10_requires_every_exact_54_05_anchor_hash(
    tmp_path: Path,
    artifact: str,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-10", "preflight")
    evidence["public_ip"]["cutover_anchor"][f"{artifact}_sha256"] = "0" * 64
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
    evidence["operational_10_21"] = []
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    def residual_transport(
        spec: gate.ProbeSpec,
        context: gate.ProbeContext,
    ) -> dict[str, object]:
        result = _fixture_remote_transport(spec, context)
        if spec.check_id == "full_matrix":
            result["normalized"]["operational_10_21"] = ["route 10.21.0.0/16"]
            result["normalized"]["residual_live"] = {
                "present": True,
                "count": 1,
                "sha256": gate.sha256_json(["route 10.21.0.0/16"]),
            }
        return result

    args.remote_transport = residual_transport
    _assert_blocked(args, "zero_operational_10_21")


def test_self_asserted_empty_residual_without_live_normalized_inventory_blocks(
    tmp_path: Path,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-10", "sync")
    evidence["operational_10_21"] = []
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    def missing_inventory_transport(
        spec: gate.ProbeSpec,
        context: gate.ProbeContext,
    ) -> dict[str, object]:
        result = _fixture_remote_transport(spec, context)
        if spec.check_id == "full_matrix":
            result.pop("normalized")
        return result

    args.remote_transport = missing_inventory_transport
    _assert_blocked(args, "zero_operational_10_21")


def test_s20_old_peer_or_allowed_ip_present_blocks_sync(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-08", "sync")
    receipt_path = Path(evidence["s20_retirement"]["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["peer_present"] = True
    receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    evidence["s20_retirement"]["receipt_sha256"] = _sha(receipt_path)
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "s20_old_peer_absent")


def test_s20_defer_decision_cannot_complete_sync(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-08", "sync")
    evidence["s20_retirement"] = _write_s20_retirement(tmp_path, "defer")
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "s20_old_peer_absent")


def test_plan_54_10_sync_blocks_any_production_write_signal(tmp_path: Path) -> None:
    for mutation in (
        {"mutations_attempted": True},
        {"production_mutations_attempted": True},
        {"apply_receipts": [{"id": "write-receipt"}]},
        {"writes": [{"target": "production"}]},
        {"operation": {"stage": "apply"}},
        {"apply": True},
        {"apply_operation": {"target": "production"}},
        {"write_operations": [{"target": "knowledge"}]},
        {"write_receipts": [{"id": "knowledge-write"}]},
    ):
        root = tmp_path / str(len(list(tmp_path.iterdir())))
        root.mkdir()
        args, evidence = _write_evidence(root, "54-10", "sync")
        evidence.update(mutation)
        Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

        _assert_blocked(args, "sync_read_only")


def test_expired_approval_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-05", "apply")
    evidence["operation"]["approval_expires_at"] = _ts(-1)
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "operation_lineage")


def test_strict_operation_schema_rejects_invented_rollback_and_receipt_state(
    tmp_path: Path,
) -> None:
    args, evidence = _write_evidence(tmp_path, "54-05", "apply")
    operation = evidence["operation"]
    operation.pop("apply_receipt_path")
    operation.pop("apply_receipt_sha256")
    operation["receipt_state"] = "PASS"
    operation["rollback_transaction_sha256"] = "a" * 64
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    _assert_blocked(args, "operation_lineage")


def test_tampered_operation_input_hash_blocks(tmp_path: Path) -> None:
    args, evidence = _write_evidence(tmp_path, "54-05", "apply")
    input_path = next(iter(evidence["operation"]["input_hashes"]))
    Path(input_path).write_text('{"target":"10.21.1.21"}\n', encoding="utf-8")

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
    evidence["check_inputs"]["focused_pytest"]["artifact_hashes"] = {
        "tampered": "a" * 64
    }
    Path(args.evidence).write_text(json.dumps(evidence), encoding="utf-8")

    assert gate.assert_gate(args) != 0


def test_assert_gate_rejects_other_plan_receipt(tmp_path: Path) -> None:
    args, _ = _write_evidence(tmp_path)
    assert gate.run(args) == 0
    receipt = _receipt(args)
    receipt["plan"] = "54-02"
    Path(args.gate).write_text(json.dumps(receipt), encoding="utf-8")

    assert gate.assert_gate(args) != 0
