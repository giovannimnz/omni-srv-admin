#!/usr/bin/env python3
"""Fail-closed, read-only validation gate for Phase 54.

Evidence is untrusted input.  The runner derives status from fresh,
runner-observed checks and recomputed artifact lineage; an evidence document
cannot authorize its own progression.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any, Iterable


SCHEMA_EVIDENCE = "phase54.evidence.v1"
SCHEMA_GATE = "phase54.gate.v1"
DEFAULT_MAX_AGE_SECONDS = 900
PLAN_IDS = tuple(f"54-{number:02d}" for number in range(1, 11))
STAGE_IDS = {"preflight", "stability", "preview", "approval", "apply", "sync"}
STAGES_BY_PLAN: dict[str, frozenset[str | None]] = {
    "54-01": frozenset({None}),
    "54-02": frozenset({None, "preflight"}),
    "54-03": frozenset({None}),
    "54-04": frozenset({"preview", "approval", "apply"}),
    "54-05": frozenset({"preview", "approval", "apply"}),
    "54-06": frozenset({"preview", "approval", "apply"}),
    "54-07": frozenset({"preview", "approval", "apply"}),
    "54-08": frozenset({None}),
    "54-09": frozenset({"stability", "preview", "approval"}),
    "54-10": frozenset({"preflight", "apply", "sync"}),
}
BASE_REQUIRED_CHECK_IDS: dict[str, tuple[str, ...]] = {
    "54-01": (
        "workstream_config_routing",
        "focused_pytest",
        "syntax_compile",
        "adversarial_matrix",
        "secret_scan",
        "graphify_preflight",
    ),
    "54-02": (
        "live_inventory",
        "backup_restore_staging",
        "public_ip_baseline",
        "dns_edge_baseline",
    ),
    "54-03": ("builder_receipt", "builder_targets", "vcn_architecture"),
    "54-04": ("target_network", "drg_bidirectional", "security_bidirectional"),
    "54-05": ("vnic_private_ip", "host_k3s_dual_path", "public_ip_binding"),
    "54-06": ("freeipa_authority", "resolver_forwarding", "service_matrix"),
    "54-07": ("edge_transaction", "s23_unchanged", "s20_target"),
    "54-08": ("device_receipts", "s20_handshake", "dual_ssh_paths"),
    "54-09": ("stable_readbacks", "retirement_targets", "retirement_approval"),
    "54-10": ("retirement_readback", "full_matrix", "knowledge_receipts"),
}
STAGE_REQUIRED_CHECK_IDS = {
    "preflight": ("stage_preflight",),
    "stability": ("stage_stability",),
    "preview": ("operation_plan_preview",),
    "approval": ("typed_approval",),
    "apply": ("apply_receipt",),
    "sync": ("knowledge_sync",),
}
EDGE_TARGET_MAP = {
    "horistic_wireguard": {"from": "10.100.100.4", "to": "10.100.100.31"},
    "s23_lan": {
        "from": "192.168.1.10",
        "to": "192.168.1.10",
        "mac": "64:1B:2F:C2:DC:A3",
    },
    "s23_wireguard": {"from": "10.100.100.10", "to": "10.100.100.10"},
    "s20_lan": {
        "from": "192.168.1.9",
        "to": "192.168.1.11",
        "mac": "30:AB:6A:3C:96:D1",
    },
    "s20_wireguard": {"from": "10.100.100.9", "to": "10.100.100.11"},
}
EXPECTED_BUILDER_TARGETS = {
    "vcn": "10.31.0.0/16",
    "subnet": "10.31.1.0/24",
    "private_ip": "10.31.1.31",
}
LEGACY_FAILURE_STATES = {"BLOCK", "BLOCKED", "UNKNOWN", "PARTIAL"}
SENSITIVE_KEYS = {
    "authorization",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\b(?:token|password|secret)=[^\s<]+", re.IGNORECASE),
)
COMMAND_ID_PATTERN = re.compile(r"^phase54\.[a-z0-9][a-z0-9_.-]*$")
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")
HEX_40_PATTERN = re.compile(r"^[0-9a-f]{40}$")


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
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def required_check_ids(plan: str, stage: str | None) -> tuple[str, ...]:
    base = BASE_REQUIRED_CHECK_IDS.get(plan, ())
    stage_checks = STAGE_REQUIRED_CHECK_IDS.get(stage, ()) if stage is not None else ()
    return base + stage_checks


def result_check(check_id: str, expected: Any, observed: Any, passed: bool) -> dict[str, Any]:
    return {
        "id": check_id,
        "required": True,
        "expected": expected,
        "observed": observed,
        "result": "PASS" if passed else "BLOCK",
    }


def _path_from_evidence(raw_path: Any, evidence_dir: pathlib.Path) -> pathlib.Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = pathlib.Path(raw_path)
    if candidate.is_absolute():
        return candidate
    cwd_candidate = pathlib.Path.cwd() / candidate
    if cwd_candidate.exists():
        return cwd_candidate
    return evidence_dir / candidate


def _freshness(
    generated_at: Any,
    expires_at: Any,
    max_age_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    generated = parse_timestamp(generated_at)
    if generated is None:
        return False
    age = (current - generated).total_seconds()
    if age < -60 or age > max_age_seconds:
        return False
    if expires_at is None:
        return True
    expiry = parse_timestamp(expires_at)
    return bool(expiry and expiry > current)


def _contains_secret(value: Any, key: str | None = None) -> bool:
    if key and key.lower() in SENSITIVE_KEYS:
        return True
    if isinstance(value, dict):
        return any(_contains_secret(item, str(item_key)) for item_key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS)
    return False


def _hash_entries_valid(
    entries: Iterable[tuple[Any, Any]],
    evidence_dir: pathlib.Path,
) -> bool:
    for raw_path, expected_hash in entries:
        path = _path_from_evidence(raw_path, evidence_dir)
        if (
            path is None
            or not isinstance(expected_hash, str)
            or not HEX_64_PATTERN.fullmatch(expected_hash)
            or sha256_file(path) != expected_hash
        ):
            return False
    return True


def _artifacts_valid(evidence_json: dict[str, Any], evidence_dir: pathlib.Path) -> bool:
    artifacts = evidence_json.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return False
    entries: list[tuple[Any, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            return False
        entries.append((artifact.get("path"), artifact.get("sha256")))
    return _hash_entries_valid(entries, evidence_dir)


def _observed_check_valid(item: Any, evidence_dir: pathlib.Path) -> bool:
    if not isinstance(item, dict):
        return False
    required_fields = {
        "id",
        "required",
        "adapter",
        "command_id",
        "arguments",
        "redacted",
        "started_at",
        "finished_at",
        "timeout_seconds",
        "exit_code",
        "observed",
        "expected",
        "result",
        "artifact_hashes",
    }
    if not required_fields.issubset(item):
        return False
    if item.get("required") is not True or item.get("redacted") is not True:
        return False
    if not isinstance(item.get("adapter"), str) or not item["adapter"]:
        return False
    if not isinstance(item.get("arguments"), list) or _contains_secret(item["arguments"]):
        return False
    command_id = item.get("command_id")
    if not isinstance(command_id, str) or not COMMAND_ID_PATTERN.fullmatch(command_id):
        return False
    started = parse_timestamp(item.get("started_at"))
    finished = parse_timestamp(item.get("finished_at"))
    timeout = item.get("timeout_seconds")
    if (
        started is None
        or finished is None
        or not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or timeout <= 0
        or finished < started
        or (finished - started).total_seconds() > timeout
    ):
        return False
    if item.get("exit_code") != 0:
        return False
    if item.get("result") != "PASS" or item.get("observed") != item.get("expected"):
        return False
    hashes = item.get("artifact_hashes")
    if not isinstance(hashes, dict):
        return False
    return _hash_entries_valid(hashes.items(), evidence_dir)


def _previous_gate_valid(
    evidence_json: dict[str, Any],
    plan: str,
    evidence_dir: pathlib.Path,
    max_age_seconds: int,
) -> bool:
    if plan == "54-01":
        return True
    lineage = evidence_json.get("previous_gate")
    if not isinstance(lineage, dict):
        return False
    expected_plan = f"54-{int(plan[-2:]) - 1:02d}"
    gate_path = _path_from_evidence(lineage.get("gate_path"), evidence_dir)
    prior_evidence_path = _path_from_evidence(lineage.get("evidence_path"), evidence_dir)
    if gate_path is None or prior_evidence_path is None:
        return False
    gate_hash = sha256_file(gate_path)
    prior_evidence_hash = sha256_file(prior_evidence_path)
    prior_gate = read_json(gate_path)
    if (
        gate_hash != lineage.get("gate_sha256")
        or prior_evidence_hash != lineage.get("evidence_sha256")
        or prior_gate is None
    ):
        return False
    return bool(
        lineage.get("plan") == expected_plan
        and prior_gate.get("schema") == SCHEMA_GATE
        and prior_gate.get("plan") == expected_plan
        and prior_gate.get("status") == "PASS"
        and prior_gate.get("evidence_sha256") == prior_evidence_hash
        and _freshness(prior_gate.get("finished_at"), None, max_age_seconds)
    )


def _operation_lineage_valid(
    evidence_json: dict[str, Any],
    plan: str,
    stage: str | None,
    evidence_dir: pathlib.Path,
) -> bool:
    if stage not in {"preview", "approval", "apply"}:
        return True
    operation = evidence_json.get("operation")
    if not isinstance(operation, dict):
        return False
    operation_path = _path_from_evidence(operation.get("operation_plan_path"), evidence_dir)
    operation_hash = sha256_file(operation_path) if operation_path else None
    if (
        operation_hash is None
        or operation_hash != operation.get("operation_plan_sha256")
        or not HEX_64_PATTERN.fullmatch(operation_hash)
    ):
        return False
    operation_json = read_json(operation_path)
    input_hashes = operation.get("input_hashes")
    if (
        operation_json is None
        or operation_json.get("plan") != plan
        or not isinstance(input_hashes, dict)
        or operation_json.get("input_hashes") != input_hashes
        or not _hash_entries_valid(input_hashes.items(), evidence_dir)
    ):
        return False
    if stage == "preview":
        return True
    approval_path = _path_from_evidence(operation.get("approval_path"), evidence_dir)
    approval_hash = sha256_file(approval_path) if approval_path else None
    approval = read_json(approval_path) if approval_path else None
    typed = f"APPROVE {plan} {operation_hash}"
    if (
        approval is None
        or approval_hash != operation.get("approval_sha256")
        or approval.get("plan") != plan
        or approval.get("operation_plan_sha256") != operation_hash
        or approval.get("approval_typed") != typed
        or operation.get("approval_typed") != typed
        or approval.get("approval_expires_at") != operation.get("approval_expires_at")
        or not _freshness(utc_now(), operation.get("approval_expires_at"), DEFAULT_MAX_AGE_SECONDS)
    ):
        return False
    if stage == "approval":
        return True
    anti_drift_path = _path_from_evidence(
        operation.get("anti_drift_readback_path"),
        evidence_dir,
    )
    anti_drift_hash = sha256_file(anti_drift_path) if anti_drift_path else None
    receipt_id = operation.get("opc_request_id") or operation.get("command_receipt_id")
    return bool(
        anti_drift_hash
        and anti_drift_hash == operation.get("anti_drift_readback_sha256")
        and isinstance(receipt_id, str)
        and receipt_id
        and operation.get("receipt_state") == "PASS"
        and isinstance(operation.get("rollback_transaction_sha256"), str)
        and HEX_64_PATTERN.fullmatch(operation["rollback_transaction_sha256"])
    )


def _builder_valid(
    evidence_json: dict[str, Any],
    evidence_dir: pathlib.Path,
) -> bool:
    builder = evidence_json.get("builder")
    if not isinstance(builder, dict):
        return False
    receipt_path = _path_from_evidence(builder.get("receipt_path"), evidence_dir)
    receipt_hash = sha256_file(receipt_path) if receipt_path else None
    receipt = read_json(receipt_path) if receipt_path else None
    targets = builder.get("targets")
    if (
        builder.get("owner") != "oci-admin"
        or builder.get("validated") is not True
        or not isinstance(builder.get("commit"), str)
        or not HEX_40_PATTERN.fullmatch(builder["commit"])
        or receipt_hash != builder.get("receipt_sha256")
        or receipt is None
        or targets != EXPECTED_BUILDER_TARGETS
    ):
        return False
    serialized_targets = json.dumps(targets, sort_keys=True)
    return bool("10.21" not in serialized_targets and receipt == {
        "owner": builder["owner"],
        "validated": builder["validated"],
        "commit": builder["commit"],
        "targets": targets,
    })


def _public_ip_valid(evidence_json: dict[str, Any]) -> bool:
    public_ip = evidence_json.get("public_ip")
    if not isinstance(public_ip, dict):
        return False
    forbidden_operations = {"release", "delete", "recreate"}
    return bool(
        public_ip.get("address") == "163.176.232.119"
        and public_ip.get("ocid")
        and public_ip.get("ocid") == public_ip.get("baseline_ocid")
        and public_ip.get("private_ip_ocid")
        and public_ip.get("private_ip_ocid") == public_ip.get("baseline_private_ip_ocid")
        and public_ip.get("label") == "horistic-srv-1"
        and public_ip.get("state") in {"RESERVED", "ASSIGNED"}
        and public_ip.get("operation") not in forbidden_operations
    )


def _gate_status(checks: Iterable[dict[str, Any]]) -> str:
    return "PASS" if all(item.get("result") == "PASS" for item in checks) else "BLOCK"


def evaluate_evidence(
    evidence_path: pathlib.Path,
    plan: str,
    stage: str | None,
    max_age_seconds: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    checks: list[dict[str, Any]] = []
    evidence_hash = sha256_file(evidence_path)
    checks.append(
        result_check(
            "evidence_exists",
            "non-empty evidence file",
            str(evidence_path),
            evidence_hash is not None,
        )
    )
    evidence_json = read_json(evidence_path) if evidence_hash else None
    checks.append(
        result_check(
            "evidence_machine_readable",
            SCHEMA_EVIDENCE,
            evidence_json.get("schema") if evidence_json else None,
            bool(evidence_json and evidence_json.get("schema") == SCHEMA_EVIDENCE),
        )
    )
    expected_ids = required_check_ids(plan, stage)
    plan_valid = plan in PLAN_IDS and bool(evidence_json and evidence_json.get("plan") == plan)
    checks.append(
        result_check(
            "plan_id",
            plan,
            evidence_json.get("plan") if evidence_json else None,
            plan_valid,
        )
    )
    stage_valid = bool(
        plan in STAGES_BY_PLAN
        and stage in STAGES_BY_PLAN[plan]
        and stage not in (STAGE_IDS - STAGES_BY_PLAN[plan])
        and evidence_json
        and evidence_json.get("stage") == stage
    )
    checks.append(
        result_check(
            "stage",
            sorted(item for item in STAGES_BY_PLAN.get(plan, ()) if item is not None)
            or [None],
            stage,
            stage_valid,
        )
    )
    fresh = bool(
        evidence_json
        and _freshness(
            evidence_json.get("generated_at"),
            evidence_json.get("expires_at"),
            max_age_seconds,
        )
    )
    checks.append(
        result_check(
            "freshness",
            f"generated within {max_age_seconds}s and unexpired",
            evidence_json.get("generated_at") if evidence_json else None,
            fresh,
        )
    )
    claimed_status = evidence_json.get("status") if evidence_json else None
    legacy_ok = claimed_status not in LEGACY_FAILURE_STATES
    checks.append(
        result_check(
            "legacy_status",
            "legacy BLOCK/BLOCKED/UNKNOWN/PARTIAL absent",
            claimed_status,
            legacy_ok,
        )
    )
    redaction_ok = bool(
        evidence_json
        and evidence_json.get("redacted") is True
        and not _contains_secret(evidence_json)
    )
    checks.append(
        result_check(
            "redaction",
            "redacted evidence with no secret material",
            evidence_json.get("redacted") if evidence_json else None,
            redaction_ok,
        )
    )
    raw_observed_checks = evidence_json.get("checks") if evidence_json else None
    observed_by_id: dict[str, dict[str, Any]] = {}
    duplicates = False
    if isinstance(raw_observed_checks, list):
        for item in raw_observed_checks:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            if item["id"] in observed_by_id:
                duplicates = True
            observed_by_id[item["id"]] = item
    complete = bool(expected_ids and not duplicates and set(expected_ids) <= set(observed_by_id))
    checks.append(
        result_check(
            "required_checks_complete",
            list(expected_ids),
            sorted(observed_by_id),
            complete,
        )
    )
    evidence_dir = evidence_path.parent
    observed_valid = bool(
        complete
        and all(_observed_check_valid(observed_by_id[item], evidence_dir) for item in expected_ids)
    )
    checks.append(
        result_check(
            "observed_checks",
            "all required checks are runner-observed PASS",
            {item: observed_by_id[item].get("result") for item in expected_ids if item in observed_by_id},
            observed_valid,
        )
    )
    artifact_valid = bool(evidence_json and _artifacts_valid(evidence_json, evidence_dir))
    checks.append(
        result_check(
            "artifact_hashes",
            "all artifacts exist and SHA-256 hashes match",
            len(evidence_json.get("artifacts", [])) if evidence_json else 0,
            artifact_valid,
        )
    )
    previous_valid = bool(
        evidence_json
        and _previous_gate_valid(evidence_json, plan, evidence_dir, max_age_seconds)
    )
    checks.append(
        result_check(
            "previous_gate_lineage",
            "immediate predecessor gate is fresh and hash-valid",
            evidence_json.get("previous_gate") if evidence_json else None,
            previous_valid,
        )
    )
    operation_valid = bool(
        evidence_json and _operation_lineage_valid(evidence_json, plan, stage, evidence_dir)
    )
    checks.append(
        result_check(
            "operation_lineage",
            "operation/input/approval/anti-drift hashes match stage",
            stage,
            operation_valid,
        )
    )
    if plan == "54-03":
        builder_valid = bool(evidence_json and _builder_valid(evidence_json, evidence_dir))
        checks.append(
            result_check(
                "builder_targets",
                EXPECTED_BUILDER_TARGETS,
                evidence_json.get("builder", {}).get("targets") if evidence_json else None,
                builder_valid,
            )
        )
    if plan in {"54-02", "54-05", "54-10"}:
        public_ip_valid = bool(evidence_json and _public_ip_valid(evidence_json))
        checks.append(
            result_check(
                "public_ip_identity",
                "same public/private OCIDs, label and terminal state",
                evidence_json.get("public_ip") if evidence_json else None,
                public_ip_valid,
            )
        )
    if plan in {"54-07", "54-08", "54-10"}:
        observed_map = evidence_json.get("target_map") if evidence_json else None
        checks.append(
            result_check(
                "edge_target_map",
                EDGE_TARGET_MAP,
                observed_map,
                observed_map == EDGE_TARGET_MAP,
            )
        )
    if plan == "54-10":
        residuals = evidence_json.get("operational_10_21") if evidence_json else None
        checks.append(
            result_check(
                "zero_operational_10_21",
                [],
                residuals,
                residuals == [],
            )
        )
    return checks, evidence_json, evidence_hash


def _write_gate(path: pathlib.Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def run(args: argparse.Namespace) -> int:
    evidence = pathlib.Path(args.evidence).resolve()
    gate = pathlib.Path(args.gate).resolve()
    max_age_seconds = int(getattr(args, "max_age_seconds", DEFAULT_MAX_AGE_SECONDS))
    stage = getattr(args, "stage", None)
    checks, evidence_json, evidence_hash = evaluate_evidence(
        evidence,
        args.plan,
        stage,
        max_age_seconds,
    )
    status = _gate_status(checks)
    receipt = {
        "schema": SCHEMA_GATE,
        "phase": 54,
        "plan": args.plan,
        "stage": stage,
        "mode": "read-only",
        "status": status,
        "started_at": getattr(args, "started_at", utc_now()),
        "finished_at": utc_now(),
        "required_check_ids": list(required_check_ids(args.plan, stage)),
        "checks": checks,
        "evidence_sha256": evidence_hash,
        "next_wave_gate": f"PASS:{args.plan}" if status == "PASS" else None,
        "mutations_attempted": bool(
            evidence_json.get("mutations_attempted", False)
        )
        if evidence_json
        else False,
        "redacted": bool(getattr(args, "redact", False)),
    }
    _write_gate(gate, receipt)
    print(
        json.dumps(
            {
                "status": status,
                "plan": args.plan,
                "stage": stage,
                "gate": str(gate),
                "evidence_sha256": evidence_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 2


def assert_gate(args: argparse.Namespace) -> int:
    evidence = pathlib.Path(args.evidence).resolve()
    gate_path = pathlib.Path(args.gate).resolve()
    max_age_seconds = int(getattr(args, "max_age_seconds", DEFAULT_MAX_AGE_SECONDS))
    stage = getattr(args, "stage", None)
    gate_json = read_json(gate_path)
    evidence_hash = sha256_file(evidence)
    checks, _, _ = evaluate_evidence(evidence, args.plan, stage, max_age_seconds)
    derived_status = _gate_status(checks)
    gate_valid = bool(
        gate_json
        and gate_json.get("schema") == SCHEMA_GATE
        and gate_json.get("phase") == 54
        and gate_json.get("plan") == args.plan
        and gate_json.get("stage") == stage
        and gate_json.get("status") == "PASS"
        and gate_json.get("evidence_sha256") == evidence_hash
        and gate_json.get("required_check_ids") == list(required_check_ids(args.plan, stage))
        and isinstance(gate_json.get("checks"), list)
        and gate_json["checks"]
        and all(item.get("result") == "PASS" for item in gate_json["checks"])
        and _freshness(gate_json.get("finished_at"), None, max_age_seconds)
        and derived_status == "PASS"
    )
    status = "PASS" if gate_valid else "BLOCK"
    print(
        json.dumps(
            {
                "status": status,
                "plan": args.plan,
                "stage": stage,
                "gate": str(gate_path),
                "evidence_sha256": evidence_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if gate_valid else 2


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--plan", required=True)
    parser.add_argument("--stage")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    final_parser = subparsers.add_parser("final")
    _add_common_arguments(final_parser)
    final_parser.add_argument("--redact", action="store_true")
    assert_parser = subparsers.add_parser("assert-gate")
    _add_common_arguments(assert_parser)
    args = parser.parse_args()
    args.started_at = utc_now()
    if args.mode == "assert-gate":
        return assert_gate(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
