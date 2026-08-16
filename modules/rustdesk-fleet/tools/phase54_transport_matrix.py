#!/usr/bin/env python3
"""Hermetic Phase 54 transport/fallback matrix validator.

Only caller-supplied, value-free observations are accepted.  No network
probe, SSH route, RustDesk endpoint, or relay is contacted by this module.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

try:
    from phase54_preflight import Phase54PreflightBlocked, validate as _validate_preflight
except ImportError:  # pragma: no cover - direct invocation from another cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from phase54_preflight import Phase54PreflightBlocked, validate as _validate_preflight


class Phase54TransportBlocked(RuntimeError):
    """Raised when transport evidence is missing, unsafe, or contradictory."""


REPO_ROOT = Path(__file__).resolve().parents[3]
TRANSPORT_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-transport.json")
RUNTIME_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-client-runtime.json")
ALLOWED_TARGETS = {"horistic-srv", "GIOVANNI-W11-PC"}
_SECRET_KEYS = {
    "password", "private_key", "bearer_token", "client_secret", "token",
    "authorization", "authorization_header", "api_token", "secret",
    "raw_gui_payload", "raw_client_id",
}
_RAW_OBSERVATION_KEYS = {"id", "session_id", "fingerprint", "payload", "text", "value"}
_MARKER_FIELDS = {"session_identity", "pairing_evidence", "ui_marker", "transport_observed"}


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise Phase54TransportBlocked(f"duplicate-json-key:{path.name}:{key}")
            result[key] = value
        return result

    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_size <= 0 or info.st_size > 4 * 1024 * 1024:
            raise Phase54TransportBlocked(f"contract-file-invalid:{path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except Phase54TransportBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase54TransportBlocked(f"contract-json-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise Phase54TransportBlocked(f"contract-object-required:{path.name}")
    return payload


def _reject_secret_surface(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered in _SECRET_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54TransportBlocked(f"secret-surface:{path}.{key_text}")
            if lowered in _RAW_OBSERVATION_KEYS and child not in (False, None, "[REDACTED]"):
                raise Phase54TransportBlocked(f"raw-observation:{path}.{key_text}")
            if key_text in _MARKER_FIELDS and isinstance(child, str) and child not in {"direct", "forced-relay"}:
                raise Phase54TransportBlocked(f"raw-observation-marker:{path}.{key_text}")
            _reject_secret_surface(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_surface(child, f"{path}[{index}]")
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise Phase54TransportBlocked(f"secret-surface:{path}")


def load_transport_contract(repo: Path = REPO_ROOT) -> dict[str, Any]:
    repo = repo.resolve(strict=True)
    contract = _strict_json(repo / TRANSPORT_RELATIVE)
    _reject_secret_surface(contract)
    if contract.get("phase") != 54 or contract.get("workstream") != "rustdesk-fleet":
        raise Phase54TransportBlocked("transport-contract-identity-drift")
    endpoint = contract.get("native_endpoint")
    policy = contract.get("policy")
    direct = contract.get("direct_observation")
    relay = contract.get("forced_relay_observation")
    if (
        not isinstance(endpoint, Mapping)
        or endpoint.get("operations_api_server_field") is not False
        or not isinstance(policy, Mapping)
        or policy.get("production") != "direct-first"
        or policy.get("forced_relay_default") is not False
        or policy.get("forced_relay_allowed") is not True
        or policy.get("public_rustdesk_servers") != "FORBIDDEN"
        or policy.get("wan_retry_to_convert_failure") != "FORBIDDEN"
        or not isinstance(direct, Mapping)
        or direct.get("required") is not True
        or not isinstance(relay, Mapping)
        or relay.get("must_be_controlled") is not True
        or relay.get("must_not_change_default_policy") is not True
    ):
        raise Phase54TransportBlocked("transport-policy-drift")
    return contract


def validate_preflight(repo: Path, receipt: Path, target: str) -> dict[str, Any]:
    try:
        return _validate_preflight(repo, receipt, target)
    except Phase54PreflightBlocked as exc:
        raise Phase54TransportBlocked(str(exc)) from exc


def _marker(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, Mapping) and value.get("observed") is True


def _route_name(value: Any) -> str:
    if value in {"direct", "forced-relay"}:
        return str(value)
    if value == "relay":
        return "forced-relay"
    return ""


def _check_direct(observation: Mapping[str, Any]) -> None:
    if not isinstance(observation, Mapping):
        raise Phase54TransportBlocked("direct-observation-required")
    if observation.get("transport_observed") not in ("direct", {"observed": True}):
        raise Phase54TransportBlocked("direct-transport-marker-required")
    if not _marker(observation.get("session_identity")):
        raise Phase54TransportBlocked("direct-session-identity-required")
    if not _marker(observation.get("pairing_evidence")):
        raise Phase54TransportBlocked("direct-pairing-evidence-required")
    if not _marker(observation.get("ui_marker")):
        raise Phase54TransportBlocked("direct-ui-marker-required")


def _check_relay(observation: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(observation, Mapping):
        raise Phase54TransportBlocked("forced-relay-observation-required")
    purpose = observation.get("purpose")
    if purpose not in set(policy.get("forced_relay_purposes", [])):
        raise Phase54TransportBlocked("forced-relay-purpose-not-controlled")
    if observation.get("forced_relay_default") is True or observation.get("default_policy_changed") is True:
        raise Phase54TransportBlocked("forced-relay-default-forbidden")
    if "transport_observed" in observation and observation.get("transport_observed") != "forced-relay":
        raise Phase54TransportBlocked("forced-relay-transport-marker-invalid")
    if not _marker(observation.get("session_identity")):
        raise Phase54TransportBlocked("relay-session-identity-required")
    if not _marker(observation.get("pairing_evidence")):
        raise Phase54TransportBlocked("relay-pairing-evidence-required")
    if not _marker(observation.get("ui_marker")):
        raise Phase54TransportBlocked("relay-ui-marker-required")
    before = observation.get("hbbr_bytes_before")
    after = observation.get("hbbr_bytes_after")
    if type(before) is not int or type(after) is not int or before < 0 or after < 0:
        raise Phase54TransportBlocked("hbbr-byte-counters-required")
    delta = after - before
    if delta <= 0:
        raise Phase54TransportBlocked("hbbr-positive-byte-delta-required")
    if "hbbr_positive_byte_delta" in observation and observation["hbbr_positive_byte_delta"] is not True:
        raise Phase54TransportBlocked("hbbr-byte-delta-claim-invalid")
    return {"before": before, "after": after, "positive_delta": True}


def project_transport_matrix(
    contract: Mapping[str, Any],
    observations: Mapping[str, Any],
    *,
    target: str,
    require_forced_relay: bool = True,
) -> dict[str, Any]:
    """Validate direct-first and controlled relay observations without I/O."""

    if target not in ALLOWED_TARGETS:
        raise Phase54TransportBlocked("target-scope-blocked")
    if not isinstance(observations, Mapping):
        raise Phase54TransportBlocked("transport-observations-object-required")
    _reject_secret_surface(observations)
    if (
        contract.get("phase") != 54
        or contract.get("workstream") != "rustdesk-fleet"
        or not isinstance(contract.get("policy"), Mapping)
        or contract["policy"].get("production") != "direct-first"
        or contract["policy"].get("forced_relay_default") is not False
        or contract["policy"].get("public_rustdesk_servers") != "FORBIDDEN"
        or contract["policy"].get("wan_retry_to_convert_failure") != "FORBIDDEN"
    ):
        raise Phase54TransportBlocked("transport-policy-drift")
    policy = contract.get("policy")
    if not isinstance(policy, Mapping):
        raise Phase54TransportBlocked("transport-policy-invalid")
    if observations.get("public_server_contact") is True or observations.get("endpoint_class") == "public-rustdesk-server":
        raise Phase54TransportBlocked("public-rustdesk-server-forbidden")
    if observations.get("wan_retry") is True or observations.get("wan_retry_to_convert_failure") is True:
        raise Phase54TransportBlocked("wan-retry-forbidden")
    if observations.get("forced_relay_default") is True or observations.get("default_policy_changed") is True:
        raise Phase54TransportBlocked("forced-relay-default-forbidden")

    attempts = observations.get("attempts")
    if attempts is not None:
        if not isinstance(attempts, list) or not attempts:
            raise Phase54TransportBlocked("direct-first-attempts-required")
        routes = [_route_name(item.get("route")) if isinstance(item, Mapping) else "" for item in attempts]
        if routes[0] != "direct":
            raise Phase54TransportBlocked("direct-first-order-required")
        if any(route not in {"direct", "forced-relay"} for route in routes):
            raise Phase54TransportBlocked("transport-route-invalid")

    direct = observations.get("direct", observations.get("direct_observation"))
    _check_direct(direct)
    relay_result: dict[str, Any] | None = None
    if require_forced_relay:
        relay = observations.get("forced_relay", observations.get("forced_relay_observation"))
        relay_result = _check_relay(relay, policy)

    sequence = observations.get("sequence")
    if sequence is not None:
        expected = ["direct", "forced-relay"] if require_forced_relay else ["direct"]
        normalized = [_route_name(item) if isinstance(item, str) else _route_name(item.get("route")) for item in sequence] if isinstance(sequence, list) else []
        if normalized[: len(expected)] != expected:
            raise Phase54TransportBlocked("transport-sequence-invalid")

    result: dict[str, Any] = {
        "schema_version": 1,
        "phase": 54,
        "target": target,
        "state": "PASS",
        "value_free": True,
        "secret_material_present": False,
        "production_policy": "direct-first",
        "direct": {"observed": True, "status": "PASS"},
        "forced_relay": {"observed": relay_result is not None, "status": "PASS" if relay_result is not None else "PENDING"},
        "hbbr": relay_result or {"status": "PENDING"},
        "public_rustdesk_servers_contacted": False,
        "forced_relay_default": False,
    }
    return result


def evaluate_transport_matrix(
    repo: Path,
    *,
    receipt: Path,
    target: str,
    observations: Mapping[str, Any],
    require_forced_relay: bool = True,
) -> dict[str, Any]:
    admission = validate_preflight(repo, receipt, target)
    contract = load_transport_contract(repo)
    result = project_transport_matrix(
        contract, observations, target=target, require_forced_relay=require_forced_relay,
    )
    result["admission_state"] = admission["state"]
    return result


validate_transport_matrix = evaluate_transport_matrix
validate_fallback_observation = project_transport_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 54 transport matrix (fixture-only)")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args()
    try:
        observations = _strict_json(args.observations)
        result = evaluate_transport_matrix(
            args.repo, receipt=args.receipt, target=args.target,
            observations=observations,
        )
    except (Phase54TransportBlocked, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "value_free": True}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
