#!/usr/bin/env python3
"""Hermetic Phase 54 permission-matrix validator.

This module only evaluates value-free observations supplied by a caller.  It
does not open a RustDesk session, inspect a host, or write evidence.  The
public ``evaluate_permission_matrix`` entry point first invokes the shared
Phase 54 preflight; callers that only need the pure projection can use
``project_permission_matrix`` with an already validated admission object.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

try:
    from phase54_preflight import Phase54PreflightBlocked, validate as _validate_preflight
except ImportError:  # pragma: no cover - direct import from an arbitrary cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from phase54_preflight import Phase54PreflightBlocked, validate as _validate_preflight


class Phase54PermissionBlocked(RuntimeError):
    """Raised when a permission observation cannot be admitted safely."""


REPO_ROOT = Path(__file__).resolve().parents[3]
PERMISSION_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-permission.json")
SOURCE_RELATIVE = Path("modules/rustdesk-fleet/contracts/permission-profiles.json")
ALLOWED_TARGETS = {"horistic-srv", "GIOVANNI-W11-PC"}
STATUSES = {"PASS", "BLOCKED", "PENDING"}
_SECRET_KEYS = {
    "password", "private_key", "bearer_token", "client_secret", "token",
    "authorization", "authorization_header", "api_token", "secret",
    "raw_gui_payload", "raw_client_id",
}
_RAW_OBSERVATION_KEYS = {"id", "session_id", "fingerprint", "payload", "text", "value"}


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise Phase54PermissionBlocked(f"duplicate-json-key:{path.name}:{key}")
            result[key] = value
        return result

    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_size <= 0 or info.st_size > 4 * 1024 * 1024:
            raise Phase54PermissionBlocked(f"contract-file-invalid:{path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except Phase54PermissionBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase54PermissionBlocked(f"contract-json-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise Phase54PermissionBlocked(f"contract-object-required:{path.name}")
    return payload


def _reject_secret_surface(value: Any, path: str = "root", *, raw_observation: bool = False) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered in _SECRET_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54PermissionBlocked(f"secret-surface:{path}.{key_text}")
            if raw_observation and lowered in _RAW_OBSERVATION_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54PermissionBlocked(f"raw-observation:{path}.{key_text}")
            _reject_secret_surface(child, f"{path}.{key_text}", raw_observation=raw_observation)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_surface(child, f"{path}[{index}]", raw_observation=raw_observation)
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise Phase54PermissionBlocked(f"secret-surface:{path}")


def load_permission_contract(repo: Path = REPO_ROOT) -> dict[str, Any]:
    """Load and cross-check the explicit permission profiles."""

    repo = repo.resolve(strict=True)
    contract = _strict_json(repo / PERMISSION_RELATIVE)
    source = _strict_json(repo / SOURCE_RELATIVE)
    for payload in (contract, source):
        _reject_secret_surface(payload)
    if (
        contract.get("phase") != 54
        or contract.get("workstream") != "rustdesk-fleet"
        or contract.get("enforcement_model") != "observed-effective-capability-or-blocked"
        or contract.get("unsupported_native_controls") != "BLOCKED"
    ):
        raise Phase54PermissionBlocked("permission-contract-identity-drift")
    profiles = {row.get("id"): row.get("capabilities") for row in source.get("profiles", [])}
    if not profiles or contract.get("profiles") != profiles:
        raise Phase54PermissionBlocked("permission-profiles-drift")
    capabilities = contract.get("capabilities")
    if not isinstance(capabilities, list) or set(capabilities) != {
        capability for profile in profiles.values() for capability in profile
    }:
        raise Phase54PermissionBlocked("permission-capability-set-drift")
    return contract


def validate_preflight(repo: Path, receipt: Path, target: str) -> dict[str, Any]:
    """Use the one shared fail-closed Phase 54 admission gate."""

    try:
        return _validate_preflight(repo, receipt, target)
    except Phase54PreflightBlocked as exc:
        raise Phase54PermissionBlocked(str(exc)) from exc


def _bool(value: Any) -> bool:
    return type(value) is bool


def _observation_marker(observation: Mapping[str, Any]) -> bool:
    """Return a marker only for explicit, observed, value-free evidence."""

    if observation.get("observed") is not True:
        return False
    if observation.get("observed_marker") is True:
        return True
    # A named marker is acceptable only as a boolean; a requested policy or a
    # free-form string is never effective proof.
    markers = observation.get("markers")
    return isinstance(markers, Mapping) and any(value is True for value in markers.values())


def _denial_marker(observation: Mapping[str, Any]) -> bool:
    if observation.get("observed_denial") is True:
        return True
    markers = observation.get("markers")
    return isinstance(markers, Mapping) and markers.get("denied") is True


def project_permission_matrix(
    contract: Mapping[str, Any],
    profile: str,
    observations: Mapping[str, Any],
    *,
    target: str,
) -> dict[str, Any]:
    """Project injected observations into a redacted effective matrix.

    ``contract`` and ``observations`` are copied into no output except for
    booleans and fixed enum labels.  In particular, ``requested`` fields are
    ignored and cannot produce a PASS verdict.
    """

    if target not in ALLOWED_TARGETS:
        raise Phase54PermissionBlocked("target-scope-blocked")
    if (
        contract.get("phase") != 54
        or contract.get("workstream") != "rustdesk-fleet"
        or contract.get("enforcement_model") != "observed-effective-capability-or-blocked"
        or contract.get("unsupported_native_controls") != "BLOCKED"
    ):
        raise Phase54PermissionBlocked("permission-policy-drift")
    if not isinstance(observations, Mapping):
        raise Phase54PermissionBlocked("permission-observations-object-required")
    _reject_secret_surface(observations, raw_observation=True)
    profiles = contract.get("profiles")
    capabilities = contract.get("capabilities")
    if not isinstance(profiles, Mapping) or profile not in profiles:
        raise Phase54PermissionBlocked("permission-profile-unsupported")
    if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
        raise Phase54PermissionBlocked("permission-capabilities-invalid")
    desired = profiles[profile]
    if not isinstance(desired, Mapping):
        raise Phase54PermissionBlocked("permission-profile-invalid")

    matrix: dict[str, dict[str, Any]] = {}
    overall = "PASS"
    for capability in capabilities:
        requested = desired.get(capability)
        raw = observations.get(capability)
        item = raw if isinstance(raw, Mapping) else {}
        if requested == "allow":
            observed = _observation_marker(item)
            status = "PASS" if observed else "BLOCKED"
            reason = "observed-allow" if observed else "observed-marker-required"
        elif requested == "deny":
            observed = _denial_marker(item)
            status = "PASS" if observed else "BLOCKED"
            reason = "observed-denial" if observed else "observed-denial-required"
        else:
            observed = False
            status = "BLOCKED"
            reason = "unsupported-native-control"
        if status != "PASS":
            overall = "BLOCKED"
        matrix[capability] = {
            "requested_policy": requested if requested in {"allow", "deny"} else "unsupported",
            "observed": observed,
            "status": status,
            "reason": reason,
        }

    return {
        "schema_version": 1,
        "phase": 54,
        "target": target,
        "profile": profile,
        "state": overall,
        "value_free": True,
        "secret_material_present": False,
        "requested_policy_is_not_effective_proof": True,
        "matrix": matrix,
    }


def evaluate_permission_matrix(
    repo: Path,
    *,
    receipt: Path,
    target: str,
    profile: str,
    observations: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed on admission, then evaluate only injected observations."""

    admission = validate_preflight(repo, receipt, target)
    contract = load_permission_contract(repo)
    result = project_permission_matrix(contract, profile, observations, target=target)
    result["admission_state"] = admission["state"]
    return result


# Names used by callers that describe this as a capability matrix.
validate_permission_matrix = evaluate_permission_matrix
build_permission_matrix = evaluate_permission_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 54 permission matrix (fixture-only)")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args()
    try:
        observations = _strict_json(args.observations)
        result = evaluate_permission_matrix(
            args.repo, receipt=args.receipt, target=args.target,
            profile=args.profile, observations=observations,
        )
    except (Phase54PermissionBlocked, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "value_free": True}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
