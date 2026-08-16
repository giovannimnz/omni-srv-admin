#!/usr/bin/env python3
"""Derive a value-free Phase 54 verdict from supplied evidence.

This validator is deliberately offline.  It reads repository contracts and a
value-free evidence manifest, but never contacts a host, Vault, Graphify,
RustDesk, SSH or a package manager.  A missing, stale, secret-bearing or
incomplete observation is a BLOCKED result; no stored PASS field is trusted.
The ``both`` selector is an aggregate convenience and is never accepted by
the per-target preflight or installers.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

try:
    from phase54_checkpoint_redaction import (
        Phase54CheckpointBlocked,
        _expected_markers,
        expected_checkpoints,
        redact_checkpoint_observation,
    )
    from phase54_permission_matrix import (
        Phase54PermissionBlocked,
        load_permission_contract,
        project_permission_matrix,
    )
    import phase54_preflight as PREFLIGHT
    from phase54_preflight import ALLOWED_TARGETS, PHASE52_STAGES, PREFLIGHT_RECEIPTS
    from phase54_transport_matrix import (
        Phase54TransportBlocked,
        load_transport_contract,
        project_transport_matrix,
    )
    from phase54_preflight import Phase54PreflightBlocked
except ImportError:  # pragma: no cover - direct invocation from another cwd
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from phase54_checkpoint_redaction import (  # type: ignore
        Phase54CheckpointBlocked,
        _expected_markers,
        expected_checkpoints,
        redact_checkpoint_observation,
    )
    from phase54_permission_matrix import (  # type: ignore
        Phase54PermissionBlocked,
        load_permission_contract,
        project_permission_matrix,
    )
    import phase54_preflight as PREFLIGHT  # type: ignore
    from phase54_preflight import ALLOWED_TARGETS, PHASE52_STAGES, PREFLIGHT_RECEIPTS  # type: ignore
    from phase54_transport_matrix import (  # type: ignore
        Phase54TransportBlocked,
        load_transport_contract,
        project_transport_matrix,
    )
    from phase54_preflight import Phase54PreflightBlocked  # type: ignore


class Phase54EvidenceInvalid(RuntimeError):
    """Raised internally for malformed or incomplete evidence."""


REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_RELATIVE = Path("modules/rustdesk-fleet/evidence/phase54/live-evidence.json")
RUNTIME_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-client-runtime.json")
TOPOLOGY_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-canary-topology.json")
PREFLIGHT_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-preflight.json")
SERIAL_ORDER = ("horistic-srv", "GIOVANNI-W11-PC")
ARTIFACT_RELATIVE = Path("modules/rustdesk-fleet/evidence/phase54")
ARTIFACT_NAMES = {
    "horistic-install": "horistic-install.json",
    "windows-install": "windows-install.json",
    "horistic-session": "horistic-session.json",
    "windows-session": "windows-session.json",
    "permissions": "permissions.json",
    "transport": "transport.json",
    "reboot": "reboot.json",
    "fallbacks": "fallbacks.json",
    "rollback": "rollback.json",
    "gate-report": "gate-report.json",
}
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_DIGEST = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_SECRET_KEYS = {
    "password",
    "private_key",
    "bearer_token",
    "client_secret",
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
_RAW_KEYS = {
    "raw_client_id",
    "raw_gui_payload",
    "screenshot",
    "screen_capture",
    "clipboard_text",
    "session_id",
    "client_id",
    "id",
    "raw_id",
    "payload",
}
_STORED_VERDICT_KEYS = {"verdict", "overall_status"}


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise Phase54EvidenceInvalid(f"duplicate-json-key:{path.name}:{key}")
            result[key] = value
        return result

    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_size <= 0 or info.st_size > 8 * 1024 * 1024:
            raise Phase54EvidenceInvalid(f"evidence-file-invalid:{path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except Phase54EvidenceInvalid:
        raise
    except FileNotFoundError as exc:
        raise Phase54EvidenceInvalid(f"evidence-missing:{path.name}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase54EvidenceInvalid(f"evidence-json-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise Phase54EvidenceInvalid("evidence-object-required")
    return payload


def _scan_value_free(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in _SECRET_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54EvidenceInvalid(f"secret-surface:{path}.{key}")
            if lowered in _RAW_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54EvidenceInvalid(f"raw-observation:{path}.{key}")
            if lowered in _STORED_VERDICT_KEYS and isinstance(child, str) and child in {"PASS", "ADMITTED_PHASE54"}:
                raise Phase54EvidenceInvalid(f"stored-verdict:{path}.{key}")
            if lowered in {"state", "status", "verdict", "overall_status"} and child == "PASS" and not path.endswith(".predecessor"):
                raise Phase54EvidenceInvalid(f"stored-verdict:{path}.{key}")
            _scan_value_free(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_value_free(child, f"{path}[{index}]")
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise Phase54EvidenceInvalid(f"secret-surface:{path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _head(repo: Path) -> str:
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
    if completed.returncode != 0 or not _HEX40.fullmatch(completed.stdout.strip()):
        raise Phase54EvidenceInvalid("source-head-unavailable")
    return completed.stdout.strip()


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise Phase54EvidenceInvalid(f"{field}-digest-invalid")
    return value


def _require(value: Any, field: str) -> Any:
    if value is None:
        raise Phase54EvidenceInvalid(f"required-field:{field}")
    return value


def _contract_digests(repo: Path) -> dict[str, str]:
    names = (
        RUNTIME_RELATIVE,
        TOPOLOGY_RELATIVE,
        PREFLIGHT_RELATIVE,
        Path("modules/rustdesk-fleet/contracts/phase54-permission.json"),
        Path("modules/rustdesk-fleet/contracts/phase54-transport.json"),
    )
    return {path.name: _sha256(repo / path) for path in names}


def _phase53_contract_digests(repo: Path) -> dict[str, str]:
    names = (
        "phase53-runtime.json",
        "phase53-edge.json",
        "phase53-ops-api.json",
        "phase53-candidate-admission.json",
        "phase53-provider-manifest.json",
        "phase53-runtime-candidate.json",
    )
    return {
        name: _sha256(repo / "modules/rustdesk-fleet/contracts" / name)
        for name in names
    }


def _validate_phase52_gate(gate: Any, head: str) -> None:
    if not isinstance(gate, Mapping):
        raise Phase54EvidenceInvalid("phase52-currentness-required")
    expected = {
        "state": "CURRENT",
        "ordered_stages": list(PHASE52_STAGES),
        "gate_vector_current": True,
        "vault_helper_current": True,
        "backup_a_current": True,
        "backup_b_current": True,
        "isolated_restore_current": True,
    }
    for key, value in expected.items():
        if gate.get(key) != value:
            raise Phase54EvidenceInvalid(f"phase52-gate-{key}-not-current")
    if gate.get("source_commit") != head:
        raise Phase54EvidenceInvalid("phase52-source-head-drift")
    receipt_path = gate.get("receipt_path")
    if not isinstance(receipt_path, str) or not receipt_path.startswith("modules/rustdesk-fleet/evidence/phase52/"):
        raise Phase54EvidenceInvalid("phase52-receipt-path-invalid")
    if not _HEX64.fullmatch(str(gate.get("source_set_digest", ""))) or not _HEX64.fullmatch(str(gate.get("gate_digest", ""))):
        raise Phase54EvidenceInvalid("phase52-recomputed-digest-required")


def _validate_phase53_gate(repo: Path, gate: Any, head: str) -> None:
    if not isinstance(gate, Mapping):
        raise Phase54EvidenceInvalid("phase53-independent-pass-required")
    if gate.get("state") != "ADMITTED_PHASE53" or gate.get("candidate_status") != "ADMITTED_PHASE53":
        raise Phase54EvidenceInvalid("phase53-independent-pass-required")
    if gate.get("independent_verifier") != "PASS":
        raise Phase54EvidenceInvalid("phase53-independent-verifier-required")
    if gate.get("source_head") != head:
        raise Phase54EvidenceInvalid("phase53-source-head-drift")
    if gate.get("contract_digests") != _phase53_contract_digests(repo):
        raise Phase54EvidenceInvalid("phase53-contract-digest-drift")


def _validate_owner(owner: Any) -> None:
    if not isinstance(owner, Mapping):
        raise Phase54EvidenceInvalid("owner-bound-admission-required")
    if (
        owner.get("owner") != "Giovanni Muniz"
        or owner.get("hash_binding") is not True
        or not isinstance(owner.get("approval_ref"), str)
        or not owner.get("approval_ref")
        or not isinstance(owner.get("expires_at"), str)
        or not owner.get("expires_at").endswith("Z")
        or not isinstance(owner.get("risk_disposition"), str)
        or not owner.get("risk_disposition")
    ):
        raise Phase54EvidenceInvalid("owner-approval-fields-required")
    try:
        expiry = datetime.fromisoformat(owner["expires_at"].replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise Phase54EvidenceInvalid("owner-expiry-invalid") from exc
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise Phase54EvidenceInvalid("owner-admission-expired")


def _validate_admission(repo: Path, item: Mapping[str, Any], head: str, phase53_result: Mapping[str, Any] | None = None, admission: Mapping[str, Any] | None = None) -> None:
    if item.get("source_commit") != head:
        raise Phase54EvidenceInvalid("source-commit-drift")
    _validate_phase52_gate(item.get("phase52_gate"), head)
    _validate_phase53_gate(repo, item.get("phase53_gate"), head)
    if phase53_result is not None:
        if phase53_result.get("state") != "ADMITTED_PHASE53" or phase53_result.get("candidate_status") != "ADMITTED_PHASE53" or phase53_result.get("mutation_performed") is not False:
            raise Phase54EvidenceInvalid("phase53-independent-pass-required")
        if item.get("phase53_gate") != {
            "state": "ADMITTED_PHASE53",
            "candidate_status": "ADMITTED_PHASE53",
            "independent_verifier": "PASS",
            "source_head": head,
            "contract_digests": phase53_result.get("contract_digests"),
        }:
            raise Phase54EvidenceInvalid("phase53-gate-attestation-drift")
    if admission is not None:
        if admission.get("state") != "ADMITTED_PHASE54" or admission.get("mutation_performed") is not False:
            raise Phase54EvidenceInvalid("phase54-admission-not-current")
        if admission.get("source_commit") != head:
            raise Phase54EvidenceInvalid("phase54-admission-source-head-drift")
        if "phase52_gate" not in admission or item.get("phase52_gate") != admission.get("phase52_gate"):
            raise Phase54EvidenceInvalid("phase52-gate-attestation-drift")
        if "predecessor" not in admission or item.get("predecessor") != admission.get("predecessor"):
            raise Phase54EvidenceInvalid("predecessor-attestation-drift")
    _validate_owner(item.get("owner_admission"))
    for key in ("capacity_state", "rollback_state", "graphify_state"):
        if item.get(key) != "CURRENT":
            raise Phase54EvidenceInvalid(f"{key}-not-current")
    _digest(_require(item.get("pre_state_digest"), "pre_state_digest"), "pre_state_digest")
    if item.get("phase54_contract_digests") != _contract_digests(repo):
        raise Phase54EvidenceInvalid("phase54-contract-digest-drift")
    if item.get("blockers") not in ([], {}):
        raise Phase54EvidenceInvalid("preflight-blockers-present")


def _validate_installation(repo: Path, item: Mapping[str, Any], target: str) -> None:
    runtime = _strict_json(repo / RUNTIME_RELATIVE)
    target_contract = runtime.get("targets", {}).get(target)
    if not isinstance(target_contract, Mapping):
        raise Phase54EvidenceInvalid("target-runtime-contract-missing")
    installation = item.get("installation")
    if not isinstance(installation, Mapping):
        raise Phase54EvidenceInvalid("installation-evidence-required")
    asset = target_contract.get("asset", {})
    if installation.get("package_hash") != asset.get("sha256"):
        raise Phase54EvidenceInvalid("package-hash-drift")
    if installation.get("package_architecture") != target_contract.get("architecture"):
        raise Phase54EvidenceInvalid("package-architecture-drift")
    if installation.get("package_hash_verified") is not True or installation.get("service_active_observed") is not True:
        raise Phase54EvidenceInvalid("package-or-service-observation-missing")
    if target == "GIOVANNI-W11-PC" and installation.get("authenticode_verified") is not True:
        raise Phase54EvidenceInvalid("authenticode-observation-missing")
    for key in ("config_fingerprint", "public_key_fingerprint", "redacted_client_id_fingerprint"):
        _digest(_require(installation.get(key), f"installation.{key}"), f"installation.{key}")
    rollback = installation.get("rollback_artifact")
    if (
        not isinstance(rollback, Mapping)
        or rollback.get("present") is not True
        or rollback.get("client_only") is not True
        or rollback.get("server_paths_untouched") is not True
    ):
        raise Phase54EvidenceInvalid("installation-rollback-artifact-invalid")
    _digest(_require(rollback.get("artifact_digest"), "installation.rollback_artifact.artifact_digest"), "installation.rollback_artifact.artifact_digest")


def _validate_transport(repo: Path, item: Mapping[str, Any], target: str) -> None:
    try:
        contract = load_transport_contract(repo)
        observations = item.get("transport")
        if not isinstance(observations, Mapping):
            raise Phase54TransportBlocked("transport-evidence-required")
        attempts = observations.get("attempts")
        sequence = observations.get("sequence")
        if not isinstance(attempts, list) or not attempts or not isinstance(sequence, list) or sequence != ["direct", "forced-relay"]:
            raise Phase54TransportBlocked("transport-attempt-sequence-required")
        if [row.get("route") for row in attempts if isinstance(row, Mapping)] != ["direct", "forced-relay"]:
            raise Phase54TransportBlocked("transport-direct-first-required")
        project_transport_matrix(contract, observations, target=target, require_forced_relay=True)
    except (Phase54TransportBlocked, OSError, ValueError, TypeError) as exc:
        raise Phase54EvidenceInvalid(f"transport-{exc}") from exc


def _validate_permissions(repo: Path, item: Mapping[str, Any], target: str) -> None:
    permissions = item.get("permissions")
    if not isinstance(permissions, Mapping) or not isinstance(permissions.get("profiles"), Mapping):
        raise Phase54EvidenceInvalid("permission-evidence-required")
    try:
        contract = load_permission_contract(repo)
        profiles = permissions["profiles"]
        if set(profiles) != {"admin-maintenance", "support-observe"}:
            raise Phase54PermissionBlocked("permission-profiles-incomplete")
        for profile in ("admin-maintenance", "support-observe"):
            row = profiles.get(profile)
            if not isinstance(row, Mapping) or not isinstance(row.get("observations"), Mapping):
                raise Phase54PermissionBlocked(f"permission-profile-missing:{profile}")
            result = project_permission_matrix(contract, profile, row["observations"], target=target)
            if result.get("state") != "PASS":
                raise Phase54PermissionBlocked(f"permission-negative-or-missing:{profile}")
    except (Phase54PermissionBlocked, OSError, ValueError, TypeError) as exc:
        raise Phase54EvidenceInvalid(f"permission-{exc}") from exc


def _validate_checkpoints(item: Mapping[str, Any], target: str) -> None:
    raw = item.get("checkpoints")
    if not isinstance(raw, list):
        raise Phase54EvidenceInvalid("checkpoint-evidence-required")
    seen: set[str] = set()
    for observation in raw:
        if not isinstance(observation, Mapping):
            raise Phase54EvidenceInvalid("checkpoint-observation-invalid")
        checkpoint = observation.get("checkpoint")
        if not isinstance(checkpoint, str) or not checkpoint:
            raise Phase54EvidenceInvalid("checkpoint-name-invalid")
        if checkpoint in seen:
            raise Phase54EvidenceInvalid("checkpoint-duplicate")
        seen.add(checkpoint)
        markers = observation.get("markers")
        try:
            required = _expected_markers(checkpoint)
        except (Phase54CheckpointBlocked, TypeError, ValueError) as exc:
            raise Phase54EvidenceInvalid(f"checkpoint-{exc}") from exc
        if not isinstance(markers, Mapping) or not all(markers.get(key) is True for key in required):
            raise Phase54EvidenceInvalid("checkpoint-marker-missing")
        normalized = dict(observation)
        normalized["status"] = "PASS"
        try:
            result = redact_checkpoint_observation(normalized, target=target)
        except (Phase54CheckpointBlocked, TypeError, ValueError) as exc:
            raise Phase54EvidenceInvalid(f"checkpoint-{exc}") from exc
        if result.get("status") != "PASS" or result.get("human_verified") is not True:
            raise Phase54EvidenceInvalid("human-checkpoint-required")
    if seen != set(expected_checkpoints(target)):
        raise Phase54EvidenceInvalid("checkpoint-set-incomplete")


def _validate_recovery(item: Mapping[str, Any]) -> None:
    reboot = item.get("reboot")
    fallback = item.get("fallback")
    rollback = item.get("rollback")
    if not isinstance(reboot, Mapping) or not all(
        reboot.get(key) is True
        for key in ("reboot_observed", "service_recovered", "reconnect_observed")
    ):
        raise Phase54EvidenceInvalid("reboot-recovery-incomplete")
    if not isinstance(fallback, Mapping) or not all(
        fallback.get(key) is True
        for key in ("fallback_smoke_passed", "private_first_preserved", "server_paths_untouched")
    ):
        raise Phase54EvidenceInvalid("fallback-regression-incomplete")
    if not isinstance(rollback, Mapping) or not all(
        rollback.get(key) is True
        for key in ("client_only", "server_paths_untouched", "artifact_retained", "reapply_safe")
    ):
        raise Phase54EvidenceInvalid("rollback-regression-incomplete")
    if item.get("server_path_mutation") is not False or item.get("secret_material_present") is not False:
        raise Phase54EvidenceInvalid("boundary-or-secret-invariant-drift")


def _artifact_path(repo: Path, evidence_path: Path, value: str, *, test_only: bool) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise Phase54EvidenceInvalid("artifact-path-invalid")
    if test_only:
        root = evidence_path.parent.resolve(strict=True)
        candidate = (root / value).resolve(strict=True)
    else:
        expected_root = (repo / ARTIFACT_RELATIVE).resolve(strict=True)
        if not value.startswith(ARTIFACT_RELATIVE.as_posix() + "/"):
            raise Phase54EvidenceInvalid("artifact-path-invalid")
        candidate = (repo / value).resolve(strict=True)
        try:
            candidate.relative_to(expected_root)
        except ValueError as exc:
            raise Phase54EvidenceInvalid("artifact-path-escape") from exc
    try:
        candidate.relative_to(root if test_only else expected_root)
    except ValueError as exc:
        raise Phase54EvidenceInvalid("artifact-path-escape") from exc
    original = root / value if test_only else repo / value
    if original.is_symlink() or not candidate.is_file():
        raise Phase54EvidenceInvalid("artifact-file-invalid")
    return candidate


def _validate_artifact_refs(repo: Path, manifest: Mapping[str, Any], evidence_path: Path, *, test_only: bool) -> None:
    refs = manifest.get("artifact_refs")
    if not isinstance(refs, Mapping) or set(refs) != set(ARTIFACT_NAMES):
        raise Phase54EvidenceInvalid("canonical-artifact-refs-required")
    for key, expected_name in ARTIFACT_NAMES.items():
        row = refs.get(key)
        if not isinstance(row, Mapping):
            raise Phase54EvidenceInvalid(f"artifact-ref-invalid:{key}")
        path_value = row.get("path")
        if not isinstance(path_value, str) or Path(path_value).name != expected_name:
            raise Phase54EvidenceInvalid(f"artifact-ref-name-invalid:{key}")
        digest = row.get("sha256")
        if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            raise Phase54EvidenceInvalid(f"artifact-ref-digest-invalid:{key}")
        artifact = _artifact_path(repo, evidence_path, path_value, test_only=test_only)
        if _sha256(artifact) != digest:
            raise Phase54EvidenceInvalid(f"artifact-ref-digest-drift:{key}")
        payload = _strict_json(artifact)
        _scan_value_free(payload, f"artifact.{key}")
        if payload.get("phase") != 54 or payload.get("value_free") is not True or payload.get("secret_material_present") is not False:
            raise Phase54EvidenceInvalid(f"artifact-contract-invalid:{key}")


def _canonical_predecessor(repo: Path, item: Mapping[str, Any], target: str, evidence_path: Path, *, test_only: bool) -> dict[str, Any]:
    predecessor = item.get("predecessor")
    if target == "horistic-srv":
        if predecessor != {"target": None, "state": "NONE"}:
            raise Phase54EvidenceInvalid("predecessor-invalid")
        return {"target": None, "state": "NONE"}
    if not isinstance(predecessor, Mapping) or predecessor.get("target") != "horistic-srv" or predecessor.get("state") != "PASS":
        raise Phase54EvidenceInvalid("horistic-predecessor-required")
    path_value = predecessor.get("receipt_path")
    if test_only:
        candidate = _artifact_path(repo=repo, evidence_path=evidence_path, value=str(path_value), test_only=True)
    else:
        candidate = _artifact_path(repo=repo, evidence_path=evidence_path, value=str(path_value), test_only=False)
    digest = predecessor.get("receipt_sha256")
    if not isinstance(digest, str) or not _HEX64.fullmatch(digest) or _sha256(candidate) != digest:
        raise Phase54EvidenceInvalid("horistic-predecessor-digest-drift")
    return dict(predecessor)


def _canonical_admission(repo: Path, item: Mapping[str, Any], target: str, head: str, evidence_path: Path, *, test_only: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_rel = PREFLIGHT_RECEIPTS[target]
    receipt_path = repo / receipt_rel if not test_only else evidence_path.parent / receipt_rel.name
    try:
        phase53_result = PREFLIGHT.validate_phase53(repo)
        admission = PREFLIGHT.validate(repo, receipt_path, target)
    except Exception as exc:
        raise Phase54EvidenceInvalid(f"canonical-preflight-blocked:{exc}") from exc
    if not isinstance(phase53_result, Mapping) or phase53_result.get("state") != "ADMITTED_PHASE53" or phase53_result.get("candidate_status") != "ADMITTED_PHASE53" or phase53_result.get("mutation_performed") is not False:
        raise Phase54EvidenceInvalid("phase53-independent-pass-required")
    if not isinstance(admission, Mapping) or admission.get("state") != "ADMITTED_PHASE54" or admission.get("mutation_performed") is not False or admission.get("source_commit") != head:
        raise Phase54EvidenceInvalid("phase54-admission-not-current")
    return dict(phase53_result), dict(admission)


def _validate_target(repo: Path, item: Any, target: str, head: str, evidence_path: Path, *, test_only: bool) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise Phase54EvidenceInvalid("target-evidence-object-required")
    if item.get("phase") != 54 or item.get("target") != target:
        raise Phase54EvidenceInvalid("target-identity-drift")
    if item.get("value_free") is not True or item.get("secret_material_present") is not False:
        raise Phase54EvidenceInvalid("value-free-invariant-drift")
    phase53_result, admission = _canonical_admission(repo, item, target, head, evidence_path, test_only=test_only)
    _canonical_predecessor(repo, item, target, evidence_path, test_only=test_only)
    _validate_admission(repo, item, head, phase53_result, admission)
    _validate_installation(repo, item, target)
    _validate_transport(repo, item, target)
    _validate_permissions(repo, item, target)
    _validate_checkpoints(item, target)
    _validate_recovery(item)
    return {
        "schema_version": 1,
        "phase": 54,
        "target": target,
        "state": "PASS",
        "value_free": True,
        "secret_material_present": False,
        "source_commit": head,
        "mutation_performed": True,
        "blockers": [],
    }


def _blocked(target: str, blocker: str, *, source_commit: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "phase": 54,
        "target": target,
        "state": "BLOCKED",
        "value_free": True,
        "secret_material_present": False,
        "mutation_performed": False,
        "blockers": [blocker],
    }
    if source_commit is not None:
        result["source_commit"] = source_commit
    return result


def _load_manifest(repo: Path, evidence_path: Path | None, *, test_only: bool) -> tuple[dict[str, Any], Path]:
    path = evidence_path or (repo / EVIDENCE_RELATIVE)
    if not test_only:
        canonical = (repo / EVIDENCE_RELATIVE).absolute()
        try:
            if path.absolute() != canonical or path.is_symlink():
                raise Phase54EvidenceInvalid("evidence-path-not-canonical")
        except (OSError, ValueError) as exc:
            raise Phase54EvidenceInvalid("evidence-path-not-canonical") from exc
        path = repo / EVIDENCE_RELATIVE
    return _strict_json(path), path


def validate(repo: Path = REPO_ROOT, target: str = "both", evidence_path: Path | None = None, *, _test_only: bool = False) -> dict[str, Any]:
    """Return a derived target or aggregate verdict without performing I/O beyond reads."""

    repo = repo.resolve(strict=True)
    if target not in (*ALLOWED_TARGETS, "both"):
        return _blocked(target, "target-scope-blocked")
    try:
        manifest, manifest_path = _load_manifest(repo, evidence_path, test_only=_test_only)
        _scan_value_free(manifest)
        if manifest.get("schema_version") != 1 or manifest.get("phase") != 54:
            raise Phase54EvidenceInvalid("manifest-identity-invalid")
        targets = manifest.get("targets")
        if not isinstance(targets, Mapping):
            raise Phase54EvidenceInvalid("target-map-required")
        if set(targets) - set(ALLOWED_TARGETS):
            raise Phase54EvidenceInvalid("target-scope-blocked")
        if manifest.get("serial_order", list(SERIAL_ORDER)) != list(SERIAL_ORDER):
            raise Phase54EvidenceInvalid("serial-order-drift")
        _validate_artifact_refs(repo, manifest, manifest_path, test_only=_test_only)
        head = _head(repo)
        selected = SERIAL_ORDER if target == "both" else (target,)
        results: dict[str, dict[str, Any]] = {}
        if target == "GIOVANNI-W11-PC":
            try:
                _validate_target(repo, targets.get("horistic-srv"), "horistic-srv", head, manifest_path, test_only=_test_only)
            except (Phase54EvidenceInvalid, Phase54PreflightBlocked, Phase54CheckpointBlocked, Phase54TransportBlocked, Phase54PermissionBlocked, OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
                return _blocked(target, f"horistic-predecessor-blocked:{exc}", source_commit=head)
        for name in selected:
            try:
                results[name] = _validate_target(repo, targets.get(name), name, head, manifest_path, test_only=_test_only)
            except (Phase54EvidenceInvalid, Phase54PreflightBlocked, Phase54CheckpointBlocked, Phase54TransportBlocked, Phase54PermissionBlocked, OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
                results[name] = _blocked(name, str(exc), source_commit=head)
        state = "PASS" if all(item["state"] == "PASS" for item in results.values()) else "BLOCKED"
        blockers = [f"{name}:{blocker}" for name, result in results.items() for blocker in result.get("blockers", [])]
        output: dict[str, Any] = {
            "schema_version": 1,
            "phase": 54,
            "target": target,
            "state": state,
            "value_free": True,
            "secret_material_present": False,
            "source_commit": head,
            "serial_order": list(SERIAL_ORDER),
            "targets": results,
            "blockers": blockers,
            "mutation_performed": any(item.get("mutation_performed") is True for item in results.values()),
        }
        return output
    except (Phase54EvidenceInvalid, Phase54PreflightBlocked, Phase54CheckpointBlocked, Phase54TransportBlocked, Phase54PermissionBlocked, OSError, UnicodeError, json.JSONDecodeError, subprocess.SubprocessError, TypeError, KeyError) as exc:
        return _blocked(target, str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 54 value-free live evidence validator")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--target", required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = validate(args.repo, args.target, args.evidence)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
