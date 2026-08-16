#!/usr/bin/env python3
"""Read-only, shared admission validator for Phase 54 client mutations.

This module is intentionally boring: it validates the current Phase 53
evidence, the source commit, and an owner-bound value-free receipt before a
backend can be injected.  It never talks to a host, Vault, a package manager,
or Graphify and it never writes an artifact.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
from typing import Any, Callable


class Phase54PreflightBlocked(RuntimeError):
    """Raised for every missing, stale, or malformed admission input."""


REPO_ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-preflight.json")
RUNTIME_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-client-runtime.json")
TOPOLOGY_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-canary-topology.json")
EVIDENCE_RELATIVE = Path("modules/rustdesk-fleet/evidence/phase54")
PREFLIGHT_RECEIPTS = {
    "horistic-srv": EVIDENCE_RELATIVE / "preflight-horistic-srv.json",
    "GIOVANNI-W11-PC": EVIDENCE_RELATIVE / "preflight-giovanni-w11-pc.json",
}
P52_RECEIPT_ROOT = Path("modules/rustdesk-fleet/evidence/phase52")
ALLOWED_TARGETS = {"horistic-srv", "GIOVANNI-W11-PC"}
PHASE52_STAGES = (
    "supply",
    "capacity",
    "vault",
    "backup",
    "restore",
    "capacity_finalize",
    "rollback",
    "topology_security",
)
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SECRET_KEYS = {
    "password",
    "private_key",
    "bearer_token",
    "client_secret",
    "raw_client_id",
    "raw_gui_payload",
    "authorization",
    "authorization_header",
    "api_token",
    "token",
    "credential",
    "credentials",
    "id",
    "raw_id",
    "client_id",
    "session_id",
    "payload",
    "screenshot",
    "screen_capture",
    "gui_payload",
    "secret",
}


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise Phase54PreflightBlocked(f"duplicate-json-key:{path.name}:{key}")
            result[key] = value
        return result

    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_size <= 0 or info.st_size > 4 * 1024 * 1024:
            raise Phase54PreflightBlocked(f"contract-file-invalid:{path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except Phase54PreflightBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase54PreflightBlocked(f"contract-json-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise Phase54PreflightBlocked(f"contract-object-required:{path.name}")
    return payload


def _value_free(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in _SECRET_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54PreflightBlocked(f"secret-surface:{path}.{key}")
            _value_free(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _value_free(child, f"{path}[{index}]")
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise Phase54PreflightBlocked(f"secret-surface:{path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _head(repo: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise Phase54PreflightBlocked("source-head-unavailable") from exc
    if completed.returncode != 0:
        raise Phase54PreflightBlocked("source-head-unavailable")
    head = completed.stdout.strip()
    if not _HEX40.fullmatch(head):
        raise Phase54PreflightBlocked("source-head-invalid")
    return head


def _canonical_path(repo: Path, candidate: Path, *, root: Path = EVIDENCE_RELATIVE) -> Path:
    """Resolve a path only when it stays inside the repository evidence root."""

    repo = repo.resolve(strict=True)
    root_path = (repo / root).resolve(strict=True)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root_path)
    except (OSError, ValueError) as exc:
        raise Phase54PreflightBlocked("evidence-path-escape") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise Phase54PreflightBlocked("evidence-file-invalid")
    return resolved


def _load_phase53_validator(repo: Path) -> Callable[[Path], dict[str, Any]]:
    path = repo / "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py"
    if path.is_symlink() or not path.is_file():
        raise Phase54PreflightBlocked("phase53-validator-missing")
    spec = importlib.util.spec_from_file_location("rustdesk_phase53_validator", path)
    if spec is None or spec.loader is None:
        raise Phase54PreflightBlocked("phase53-validator-load-failed")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - defensive import boundary
        raise Phase54PreflightBlocked("phase53-validator-load-failed") from exc
    validate = getattr(module, "validate", None)
    if not callable(validate):
        raise Phase54PreflightBlocked("phase53-validator-invalid")
    return validate


def validate_phase53(repo: Path) -> dict[str, Any]:
    """Return the current validator result; exposed for hermetic unit tests."""

    validator = _load_phase53_validator(repo)
    try:
        result = validator(repo)
    except Exception as exc:
        raise Phase54PreflightBlocked("phase53-evidence-invalid") from exc
    if not isinstance(result, dict):
        raise Phase54PreflightBlocked("phase53-validator-result-invalid")
    return result


def _current(value: Any) -> bool:
    if isinstance(value, str):
        return value == "CURRENT"
    if isinstance(value, dict):
        return value.get("state") == "CURRENT" or value.get("status") == "CURRENT"
    return False


def _target_scope_matches(scope: Any, target: str) -> bool:
    if scope == target:
        return True
    if isinstance(scope, list):
        return scope == [target]
    if isinstance(scope, dict):
        if scope == {"target": target}:
            return True
        return scope.get("allowed_targets") == [target]
    return False


def _load_phase52_report_validator(repo: Path) -> Callable[[Path], dict[str, Any]]:
    path = repo / "modules/rustdesk-fleet/tools/validate_phase52.py"
    if path.is_symlink() or not path.is_file():
        raise Phase54PreflightBlocked("phase52-validator-missing")
    spec = importlib.util.spec_from_file_location("rustdesk_phase52_validator", path)
    if spec is None or spec.loader is None:
        raise Phase54PreflightBlocked("phase52-validator-load-failed")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - defensive import boundary
        raise Phase54PreflightBlocked("phase52-validator-load-failed") from exc
    build_report = getattr(module, "build_phase52_report", None)
    if not callable(build_report):
        raise Phase54PreflightBlocked("phase52-validator-invalid")
    return build_report


def validate_phase52_current(repo: Path) -> dict[str, Any]:
    """Run the canonical read-only Phase 52 report builder.

    This function is intentionally the only production authority for the P52
    predecessor. Tests may replace it in an isolated fixture, but the normal
    path always loads the repository's canonical validator.
    """

    builder = _load_phase52_report_validator(repo)
    try:
        result = builder(repo)
    except Exception as exc:
        raise Phase54PreflightBlocked("phase52-evidence-invalid") from exc
    if not isinstance(result, dict):
        raise Phase54PreflightBlocked("phase52-validator-result-invalid")
    if result.get("overall_status") != "PASS" or result.get("phase53_advance_status") != "READY":
        raise Phase54PreflightBlocked("phase52-current-pass-required")
    if not isinstance(result.get("selected_candidate"), str) or not result.get("selected_candidate"):
        raise Phase54PreflightBlocked("phase52-selected-candidate-required")
    return result


def _digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_phase52_receipt(repo: Path, gate: Any, current_head: str) -> dict[str, Any]:
    """Validate the canonical P52 per-stage receipt and recomputed digests."""

    if not isinstance(gate, dict):
        raise Phase54PreflightBlocked("phase52-receipt-required")
    if any(key in gate for key in ("gate_vector_digest", "evidence_digest")):
        raise Phase54PreflightBlocked("phase52-arbitrary-digest-fields-forbidden")
    receipt_path_value = gate.get("receipt_path")
    if not isinstance(receipt_path_value, str) or not receipt_path_value.startswith(P52_RECEIPT_ROOT.as_posix() + "/"):
        raise Phase54PreflightBlocked("phase52-receipt-path-invalid")
    receipt_path = _canonical_path(repo, repo / receipt_path_value, root=P52_RECEIPT_ROOT)
    if gate.get("source_commit") != current_head:
        raise Phase54PreflightBlocked("phase52-source-head-drift")
    observed_at = gate.get("observed_at")
    ttl_seconds = gate.get("ttl_seconds")
    if gate.get("observed") is not True or not isinstance(observed_at, str) or not observed_at.endswith("Z") or type(ttl_seconds) is not int or not 0 < ttl_seconds <= 86400:
        raise Phase54PreflightBlocked("phase52-observation-ttl-invalid")
    try:
        observed_dt = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise Phase54PreflightBlocked("phase52-observed-at-invalid") from exc
    if observed_dt.tzinfo is None or (datetime.now(timezone.utc) - observed_dt).total_seconds() > ttl_seconds:
        raise Phase54PreflightBlocked("phase52-receipt-stale")
    if gate.get("read_only") is not True or gate.get("mutation_performed") is not False:
        raise Phase54PreflightBlocked("phase52-read-only-invariant-drift")
    for key in ("vault_helper_current", "backup_a_current", "backup_b_current", "isolated_restore_current"):
        if gate.get(key) is not True:
            raise Phase54PreflightBlocked(f"phase52-{key}-not-current")
    stages = gate.get("stages")
    if not isinstance(stages, dict) or list(stages) != list(PHASE52_STAGES):
        raise Phase54PreflightBlocked("phase52-stage-vector-invalid")
    source_set: list[dict[str, str]] = []
    for stage in PHASE52_STAGES:
        row = stages.get(stage)
        if not isinstance(row, dict) or row.get("status") != "PASS" or row.get("observed") is not True or row.get("read_only") is not True or row.get("mutation_performed") is not False:
            raise Phase54PreflightBlocked(f"phase52-stage-not-pass:{stage}")
        path_value = row.get("path")
        if not isinstance(path_value, str) or not path_value.startswith(P52_RECEIPT_ROOT.as_posix() + "/"):
            raise Phase54PreflightBlocked(f"phase52-stage-path-invalid:{stage}")
        path = _canonical_path(repo, repo / path_value, root=P52_RECEIPT_ROOT)
        digest = _sha256(path)
        if row.get("sha256") != digest:
            raise Phase54PreflightBlocked(f"phase52-stage-digest-drift:{stage}")
        stage_payload = _strict_json(path)
        _value_free(stage_payload)
        if stage_payload.get("phase") != 52 or stage_payload.get("source_commit") != current_head or stage_payload.get("observed") is not True or stage_payload.get("read_only") is not True or stage_payload.get("mutation_performed") is not False:
            raise Phase54PreflightBlocked(f"phase52-stage-schema-invalid:{stage}")
        source_set.append({"stage": stage, "path": path_value, "sha256": digest})
    source_set_digest = _digest_json(source_set)
    if gate.get("source_set_digest") != source_set_digest:
        raise Phase54PreflightBlocked("phase52-source-set-digest-drift")
    gate_digest = _digest_json({
        "source_commit": current_head,
        "source_set_digest": source_set_digest,
        "observed_at": observed_at,
        "ttl_seconds": ttl_seconds,
        "stages": {stage: stages[stage]["status"] for stage in PHASE52_STAGES},
    })
    if gate.get("gate_digest") != gate_digest:
        raise Phase54PreflightBlocked("phase52-gate-digest-drift")
    try:
        payload = _strict_json(receipt_path)
    except Phase54PreflightBlocked:
        raise
    _value_free(payload)
    if payload.get("phase") != 52 or payload.get("source_commit") != current_head or payload.get("observed") is not True or payload.get("read_only") is not True or payload.get("mutation_performed") is not False or payload.get("source_set_digest") != source_set_digest or payload.get("gate_digest") != gate_digest:
        raise Phase54PreflightBlocked("phase52-canonical-receipt-invalid")
    return {"receipt_path": receipt_path.relative_to(repo).as_posix(), "gate_digest": gate_digest}


def _phase52_gate_matches(gate: Any, current_head: str | None = None) -> bool:
    """Require a current, value-free Phase 52 readiness attestation.

    Phase 54 intentionally does not re-run Phase 52 or inspect Vault/GDrive.
    The receipt must carry the current gate vector and its non-secret
    readiness flags; missing or partial attestations remain fail-closed.
    """

    expected = {
        "state": "CURRENT",
        "ordered_stages": list(PHASE52_STAGES),
        "gate_vector_current": True,
        "vault_helper_current": True,
        "backup_a_current": True,
        "backup_b_current": True,
        "isolated_restore_current": True,
    }
    if not isinstance(gate, dict) or not all(gate.get(key) == value for key, value in expected.items()):
        return False
    return current_head is None or gate.get("source_commit") == current_head


def _phase53_gate_matches(gate: Any, result: dict[str, Any], current_head: str) -> bool:
    if not isinstance(gate, dict):
        return False
    return gate == {
        "state": "ADMITTED_PHASE53",
        "candidate_status": "ADMITTED_PHASE53",
        "independent_verifier": "PASS",
        "source_head": current_head,
        "contract_digests": result.get("contract_digests"),
    }


def _load_phase54_contracts(repo: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    runtime = _strict_json(repo / RUNTIME_RELATIVE)
    topology = _strict_json(repo / TOPOLOGY_RELATIVE)
    preflight = _strict_json(repo / PREFLIGHT_RELATIVE)
    for payload in (runtime, topology, preflight):
        _value_free(payload)
        if payload.get("phase") != 54 or payload.get("workstream") != "rustdesk-fleet":
            raise Phase54PreflightBlocked("phase54-contract-identity-drift")
    return runtime, topology, preflight


def _validate_phase54_policy(runtime: dict[str, Any], topology: dict[str, Any], preflight: dict[str, Any]) -> None:
    """Reject local contract relaxation before any receipt can admit a write."""

    scope = preflight.get("scope")
    selector = preflight.get("target_selector")
    required = preflight.get("required_inputs")
    fail_closed = preflight.get("fail_closed")
    if (
        preflight.get("status_before_admission") != "BLOCKED"
        or not isinstance(scope, dict)
        or selector != {
            "individual_targets": ["horistic-srv", "GIOVANNI-W11-PC"],
            "aggregate_selector": "both",
            "aggregate_only": True,
        }
        or set(scope.get("allowed_targets", [])) != ALLOWED_TARGETS
        or scope.get("server_paths_mutable") is not False
        or scope.get("client_paths_only") is not True
        or scope.get("serial_mutation_required") is not True
        or not isinstance(required, dict)
        or required.get("phase52") != {
            "state": "CURRENT",
            "current_source_commit": True,
            "observed": True,
            "ttl_seconds_max": 86400,
            "read_only": True,
            "mutation_performed": False,
            "recomputed_digests": True,
            "receipt_root": "modules/rustdesk-fleet/evidence/phase52",
            "ordered_stages": list(PHASE52_STAGES),
            "gate_vector_current": True,
            "vault_helper_current": True,
            "backup_a_current": True,
            "backup_b_current": True,
            "isolated_restore_current": True,
        }
        or required.get("phase53") != {
            "state": "ADMITTED_PHASE53",
            "independent_verifier": "PASS",
            "current_source_commit": True,
            "owner_bound_admission": True,
        }
        or required.get("owner") != {
            "name": "Giovanni Muniz",
            "approval_ref_required": True,
            "expires_at_required": True,
            "hash_binding_required": True,
            "risk_disposition_required": True,
        }
        or required.get("fresh_state") != {
            "capacity": "CURRENT",
            "target_pre_state": "CURRENT",
            "rollback_readiness": "CURRENT",
            "source_and_contracts": "CURRENT",
            "graphify": "CURRENT",
        }
        or required.get("client_authority") != {
            "package_hashes": "PINNED_AND_VERIFIED",
            "vault_refs_only": True,
            "credential_channel": "EPHEMERAL_FD_PIPE_OR_TMPFS",
            "human_checkpoints": ["horistic-lightdm-x11", "windows-uac-rdp", "windows-prelogin"],
        }
        or fail_closed != {
            "missing_or_stale_input": "BLOCKED",
            "phase53_not_current_pass": "BLOCKED",
            "owner_or_hash_drift": "BLOCKED",
            "server_path_write_attempt": "BLOCKED_AND_ROLLBACK",
            "secret_or_raw_id_in_evidence": "BLOCKED_AND_REDACT",
            "mutation_performed_until_all_inputs_pass": False,
        }
        or preflight.get("evidence_manifest") != {
            "canonical_path": "modules/rustdesk-fleet/evidence/phase54/live-evidence.json",
            "artifact_refs": [
                "horistic-install", "windows-install", "horistic-session", "windows-session",
                "permissions", "transport", "reboot", "fallbacks", "rollback", "gate-report",
            ],
            "sha256_required": True,
            "path_escape": "BLOCKED",
            "test_only_injection": "UNIT_TESTS_ONLY",
        }
    ):
        raise Phase54PreflightBlocked("phase54-preflight-policy-drift")

    boundary = runtime.get("server_client_boundary")
    native = runtime.get("native_service")
    if (
        not isinstance(boundary, dict)
        or boundary.get("client_paths_only") is not True
        or any(boundary.get(key) is not False for key in boundary if key.endswith("_allowed"))
        or not isinstance(native, dict)
        or native.get("client_api_server_configured") is not False
        or native.get("public_rustdesk_servers_forbidden") is not True
    ):
        raise Phase54PreflightBlocked("phase54-runtime-boundary-drift")
    if (
        set(topology.get("allowed_targets", [])) != ALLOWED_TARGETS
        or set(topology.get("excluded_targets", [])) != {"atius-srv-1", "atius-srv-2", "atius-srv-3", "GIOVANNI-S23", "WSL"}
        or topology.get("serial_order") != ["horistic-srv", "GIOVANNI-W11-PC"]
        or topology.get("server_path_policy", {}).get("mutation_allowed") is not False
        or topology.get("invariants", {}).get("server_quadlets_untouched") is not True
        or topology.get("invariants", {}).get("phase53_state_untouched") is not True
    ):
        raise Phase54PreflightBlocked("phase54-topology-boundary-drift")


def validate(repo: Path, receipt_path: Path, target: str) -> dict[str, Any]:
    """Validate all Phase 54 admission inputs without performing mutation."""

    repo = repo.resolve(strict=True)
    if target not in ALLOWED_TARGETS:
        raise Phase54PreflightBlocked("target-scope-blocked")
    runtime, topology, preflight = _load_phase54_contracts(repo)
    _validate_phase54_policy(runtime, topology, preflight)
    phase54_contract_digests = {
        PREFLIGHT_RELATIVE.name: _sha256(repo / PREFLIGHT_RELATIVE),
        RUNTIME_RELATIVE.name: _sha256(repo / RUNTIME_RELATIVE),
        TOPOLOGY_RELATIVE.name: _sha256(repo / TOPOLOGY_RELATIVE),
    }
    allowed = set(preflight.get("scope", {}).get("allowed_targets", []))
    if target not in allowed or target not in set(topology.get("allowed_targets", [])):
        raise Phase54PreflightBlocked("target-scope-blocked")
    scope_policy = preflight.get("scope", {})
    if scope_policy.get("server_paths_mutable") is not False or scope_policy.get("client_paths_only") is not True:
        raise Phase54PreflightBlocked("server-client-boundary-invalid")

    # Keep the caller's path intact so `_strict_json` can reject symlinks
    # instead of resolving one into an apparently regular file.
    receipt = _strict_json(receipt_path)
    _value_free(receipt)
    if receipt.get("phase") != 54 or receipt.get("mutation_performed") is not False:
        raise Phase54PreflightBlocked("preflight-receipt-identity-invalid")
    if receipt.get("secret_material_present") is not False:
        raise Phase54PreflightBlocked("secret-material-flag-invalid")
    phase53 = validate_phase53(repo)
    if (
        phase53.get("state") != "ADMITTED_PHASE53"
        or phase53.get("candidate_status") != "ADMITTED_PHASE53"
        or phase53.get("mutation_performed") is not False
    ):
        raise Phase54PreflightBlocked("phase53-independent-pass-required")
    for key in ("source_commit", "phase52_gate", "phase53_gate", "phase53_state", "phase53_independent_verifier", "owner_admission", "capacity_state", "pre_state_digest", "rollback_state", "graphify_state", "target_scope", "blockers", "predecessor", "phase53_contract_digests", "phase54_contract_digests"):
        if key not in receipt:
            raise Phase54PreflightBlocked(f"receipt-field-required:{key}")

    current_head = _head(repo)
    if receipt.get("source_commit") != current_head or phase53.get("source_head") != current_head:
        raise Phase54PreflightBlocked("source-commit-drift")
    current_digests = phase53.get("contract_digests")
    recorded_digests = receipt.get("phase53_contract_digests")
    if not isinstance(current_digests, dict) or recorded_digests != current_digests:
        raise Phase54PreflightBlocked("phase53-contract-digest-drift")
    if receipt.get("phase54_contract_digests") != phase54_contract_digests:
        raise Phase54PreflightBlocked("phase54-contract-digest-drift")
    if receipt.get("phase53_state") != "ADMITTED_PHASE53":
        raise Phase54PreflightBlocked("phase53-independent-pass-required")
    if receipt.get("phase53_independent_verifier") != "PASS":
        raise Phase54PreflightBlocked("phase53-independent-verifier-required")
    phase52_gate = receipt.get("phase52_gate")
    phase52_receipt = _validate_phase52_receipt(repo, phase52_gate, current_head)
    validate_phase52_current(repo)
    if not _phase53_gate_matches(receipt.get("phase53_gate"), phase53, current_head):
        raise Phase54PreflightBlocked("phase53-gate-attestation-drift")

    owner = receipt.get("owner_admission")
    if not isinstance(owner, dict):
        raise Phase54PreflightBlocked("owner-bound-admission-required")
    if (
        owner.get("owner") != "Giovanni Muniz"
        or owner.get("hash_binding") is not True
        or not isinstance(owner.get("approval_ref"), str)
        or not owner.get("approval_ref")
        or not isinstance(owner.get("expires_at"), str)
        or not owner.get("expires_at")
        or not isinstance(owner.get("risk_disposition"), str)
        or not owner.get("risk_disposition")
    ):
        raise Phase54PreflightBlocked("owner-approval-fields-required")
    phase53_authority = phase53.get("admission_authority")
    if not isinstance(phase53_authority, dict) or owner != phase53_authority:
        raise Phase54PreflightBlocked("owner-admission-binding-drift")
    try:
        if not owner["expires_at"].endswith("Z"):
            raise ValueError("canonical-utc-required")
        expiry = datetime.fromisoformat(owner["expires_at"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise Phase54PreflightBlocked("owner-expiry-invalid") from exc
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise Phase54PreflightBlocked("owner-admission-expired")

    for state_key in ("capacity_state", "rollback_state", "graphify_state"):
        if not _current(receipt[state_key]):
            raise Phase54PreflightBlocked(f"{state_key}-not-current")
    pre_state_digest = receipt["pre_state_digest"]
    if not isinstance(pre_state_digest, str) or not _HEX64.fullmatch(pre_state_digest):
        raise Phase54PreflightBlocked("pre_state_digest-not-current")
    if not _target_scope_matches(receipt["target_scope"], target):
        raise Phase54PreflightBlocked("receipt-target-scope-drift")
    if receipt["blockers"] not in ([], {}):
        raise Phase54PreflightBlocked("preflight-blockers-present")

    predecessor = receipt.get("predecessor")
    if target == "horistic-srv":
        if predecessor != {"target": None, "state": "NONE"}:
            raise Phase54PreflightBlocked("predecessor-invalid")
    else:
        if not isinstance(predecessor, dict) or predecessor.get("target") != "horistic-srv" or predecessor.get("state") != "PASS":
            raise Phase54PreflightBlocked("horistic-predecessor-required")
        predecessor_path_value = predecessor.get("receipt_path")
        if not isinstance(predecessor_path_value, str):
            raise Phase54PreflightBlocked("horistic-predecessor-receipt-required")
        predecessor_path = _canonical_path(repo, repo / predecessor_path_value)
        if _sha256(predecessor_path) != predecessor.get("receipt_sha256"):
            raise Phase54PreflightBlocked("horistic-predecessor-digest-drift")
        predecessor_payload = _strict_json(predecessor_path)
        if predecessor_payload.get("target") != "horistic-srv" or predecessor_payload.get("state") != "PASS" or predecessor_payload.get("source_commit") != current_head:
            raise Phase54PreflightBlocked("horistic-predecessor-not-current")

    target_contract = runtime.get("targets", {}).get(target)
    if not isinstance(target_contract, dict):
        raise Phase54PreflightBlocked("target-runtime-contract-missing")
    return {
        "schema_version": 1,
        "phase": 54,
        "target": target,
        "state": "ADMITTED_PHASE54",
        "mutation_performed": False,
        "secret_material_present": False,
        "source_commit": current_head,
        "phase53_contract_digests": dict(sorted(current_digests.items())),
        "phase54_contract_digests": dict(sorted(phase54_contract_digests.items())),
        "phase52_gate": dict(phase52_gate),
        "phase52_receipt": phase52_receipt,
        "predecessor": dict(predecessor) if isinstance(predecessor, dict) else predecessor,
        "runtime_contract_sha256": phase54_contract_digests[RUNTIME_RELATIVE.name],
        "target_platform": target_contract.get("platform"),
        "server_paths_mutable": topology["server_path_policy"]["mutation_allowed"],
    }
