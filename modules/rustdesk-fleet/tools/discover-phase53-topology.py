#!/usr/bin/env python3
"""Validate bounded read-only Phase 53 topology observations.

The caller supplies results from allowlisted OCI inventory and host route
readbacks either through ``--observation`` or the dedicated environment
transport. This program has no provider, host, plan, approval, or shell
capability. It emits only semantic check identifiers and digests.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


CONTRACT_RELATIVE_PATH = Path(
    "modules/rustdesk-fleet/contracts/phase53-topology.json"
)
OBSERVATION_ENV = "PHASE53_TOPOLOGY_OBSERVATION_JSON"
MAX_JSON_BYTES = 65_536
EXPECTED_CONTRACT_KEYS = {
    "schema_version",
    "workstream",
    "contract_id",
    "decisions",
    "edge",
    "backend",
    "drg",
    "return_path",
    "stale_operation_plan",
    "future_handoff",
    "receipt_policy",
}
EXPECTED_OBSERVATION_KEYS = {
    "schema_version",
    "observed_at",
    "sources",
    "edge",
    "backend",
    "drg",
    "return_path",
    "stale_operation_plan",
    "future_handoff",
}
EXPECTED_SOURCES = {
    "oci-admin:public-ip-inventory",
    "oci-admin:peering.drg_status",
    "host-readback:ip-route",
}
EXPECTED_CHECKS = [
    "backend-private-address",
    "backend-public-vnic-separation",
    "drg-attachments",
    "drg-route-tables",
    "edge-public-ip-binding",
    "future-handoff-disabled",
    "operation-plan-rejected",
    "return-path",
]


class TopologyBlocked(RuntimeError):
    """The current read-only observation does not match the strict contract."""


class DuplicateKeyError(ValueError):
    """A JSON document contains an ambiguous duplicate key."""


def _reject_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise DuplicateKeyError(f"duplicate-json-key:{key}")
        result[key] = value
    return result


def _parse_json(raw: str, *, reason: str) -> dict[str, Any]:
    if not raw or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
        raise TopologyBlocked(reason)
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, DuplicateKeyError, UnicodeError) as exc:
        raise TopologyBlocked(reason) from exc
    if not isinstance(payload, dict):
        raise TopologyBlocked(reason)
    return payload


def _load_json_file(path: Path, *, reason: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise TopologyBlocked(reason)
        return _parse_json(path.read_text(encoding="utf-8"), reason=reason)
    except TopologyBlocked:
        raise
    except (OSError, UnicodeError) as exc:
        raise TopologyBlocked(reason) from exc


def _canonical_digest(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 32:
        raise TopologyBlocked("observation-timestamp-invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TopologyBlocked("observation-timestamp-invalid") from exc
    if parsed.tzinfo is None:
        raise TopologyBlocked("observation-timestamp-invalid")
    return value


def _validate_contract(contract: Mapping[str, Any]) -> None:
    if set(contract) != EXPECTED_CONTRACT_KEYS:
        raise TopologyBlocked("topology-contract-invalid")
    if (
        contract.get("schema_version") != 1
        or contract.get("workstream") != "rustdesk-fleet"
        or contract.get("contract_id") != "phase53-topology-d06-d16-d17-v1"
        or contract.get("decisions") != ["D-06", "D-16", "D-17"]
    ):
        raise TopologyBlocked("topology-contract-invalid")
    if contract.get("stale_operation_plan") != {
        "path": (
            "modules/rustdesk-fleet/evidence/phase53/"
            "edge-forwarder-operation-plan.json"
        ),
        "accepted_as_authority": False,
        "hash_reuse_allowed": False,
    }:
        raise TopologyBlocked("topology-contract-invalid")
    if contract.get("future_handoff") != {
        "private_ipv4": "10.31.1.31",
        "executable": False,
    }:
        raise TopologyBlocked("topology-contract-invalid")
    if contract.get("receipt_policy") != {
        "authorizes_live": False,
        "committed_authority": False,
        "mutation_performed": False,
        "secret_material_present": False,
        "raw_provider_identifiers_allowed": False,
        "operation_plan_material_allowed": False,
    }:
        raise TopologyBlocked("topology-contract-invalid")


def _semantic_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "edge": observation["edge"],
        "backend": observation["backend"],
        "drg": observation["drg"],
        "return_path": observation["return_path"],
        "stale_operation_plan": observation["stale_operation_plan"],
        "future_handoff": observation["future_handoff"],
    }


def validate_observation(
    contract: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a value-free PASS receipt or raise a stable blocker."""

    _validate_contract(contract)
    if (
        not isinstance(observation, Mapping)
        or set(observation) != EXPECTED_OBSERVATION_KEYS
        or observation.get("schema_version") != 1
    ):
        raise TopologyBlocked("observation-schema-invalid")
    observed_at = _validate_timestamp(observation.get("observed_at"))
    sources = observation.get("sources")
    if (
        not isinstance(sources, Sequence)
        or isinstance(sources, (str, bytes))
        or set(sources) != EXPECTED_SOURCES
        or len(sources) != len(EXPECTED_SOURCES)
    ):
        raise TopologyBlocked("read-only-source-set-invalid")

    expected_edge = contract["edge"]
    observed_edge = observation.get("edge")
    if not isinstance(observed_edge, Mapping) or observed_edge != expected_edge:
        raise TopologyBlocked("edge-public-ip-binding-drift")

    expected_backend = contract["backend"]
    observed_backend = observation.get("backend")
    if not isinstance(observed_backend, Mapping):
        raise TopologyBlocked("backend-private-address-drift")
    if (
        observed_backend.get("host") != expected_backend["host"]
        or observed_backend.get("profile") != expected_backend["profile"]
        or observed_backend.get("private_ipv4") != expected_backend["private_ipv4"]
    ):
        raise TopologyBlocked("backend-private-address-drift")
    if (
        observed_backend.get("public_ip_on_private_address") is not None
        or observed_backend.get("separate_public_vnic")
        != expected_backend["separate_public_vnic"]
    ):
        raise TopologyBlocked("backend-public-ip-confusion")
    if observed_backend != expected_backend:
        raise TopologyBlocked("backend-private-address-drift")

    expected_drg = contract["drg"]
    observed_drg = observation.get("drg")
    if not isinstance(observed_drg, Mapping):
        raise TopologyBlocked("drg-attachment-drift")
    if (
        observed_drg.get("edge_attachment_state")
        != expected_drg["edge_attachment_state"]
        or observed_drg.get("backend_attachment_state")
        != expected_drg["backend_attachment_state"]
    ):
        raise TopologyBlocked("drg-attachment-drift")
    if (
        observed_drg.get("edge_route") != expected_drg["edge_route"]
        or observed_drg.get("backend_route") != expected_drg["backend_route"]
        or observed_drg != expected_drg
    ):
        raise TopologyBlocked("drg-route-drift")

    if observation.get("return_path") != contract["return_path"]:
        raise TopologyBlocked("return-path-drift")
    if observation.get("stale_operation_plan") != contract["stale_operation_plan"]:
        raise TopologyBlocked("stale-operation-plan-reuse")
    if observation.get("future_handoff") != contract["future_handoff"]:
        raise TopologyBlocked("future-handoff-executable")

    semantic = _semantic_observation(observation)
    return {
        "schema_version": 1,
        "workstream": "rustdesk-fleet",
        "contract_id": contract["contract_id"],
        "status": "PASS",
        "observed_at": observed_at,
        "generated_at": _utc_now(),
        "source_methods": sorted(sources),
        "checks": EXPECTED_CHECKS,
        "contract_digest": _canonical_digest(contract),
        "semantic_observation_digest": _canonical_digest(semantic),
        "operation_plan_rejected": True,
        "operation_plan_material_present": False,
        "future_handoff_executable": False,
        "authorizes_live": False,
        "committed_authority": False,
        "mutation_performed": False,
        "secret_material_present": False,
    }


def _blocked_receipt(
    *,
    blocker: str,
    contract: Mapping[str, Any] | None,
    observation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    observed_at = None
    if isinstance(observation, Mapping) and isinstance(
        observation.get("observed_at"), str
    ):
        observed_at = observation["observed_at"]
    contract_id = "phase53-topology-d06-d16-d17-v1"
    contract_digest = None
    if isinstance(contract, Mapping):
        contract_id = str(contract.get("contract_id", contract_id))
        contract_digest = _canonical_digest(contract)
    return {
        "schema_version": 1,
        "workstream": "rustdesk-fleet",
        "contract_id": contract_id,
        "status": "BLOCKED",
        "blocker": blocker,
        "observed_at": observed_at,
        "generated_at": _utc_now(),
        "contract_digest": contract_digest,
        "checks": [],
        "operation_plan_rejected": True,
        "operation_plan_material_present": False,
        "future_handoff_executable": False,
        "authorizes_live": False,
        "committed_authority": False,
        "mutation_performed": False,
        "secret_material_present": False,
    }


def _load_observation(path: Path | None) -> dict[str, Any]:
    if path is not None:
        return _load_json_file(path, reason="current-read-only-observation-invalid")
    raw = os.environ.get(OBSERVATION_ENV)
    if raw is None:
        raise TopologyBlocked("current-read-only-observation-required")
    return _parse_json(raw, reason="current-read-only-observation-invalid")


def _write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(raw, encoding="utf-8")
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate current read-only Phase 53 topology observations"
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--observation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    contract: dict[str, Any] | None = None
    observation: dict[str, Any] | None = None
    try:
        contract = _load_json_file(
            repo / CONTRACT_RELATIVE_PATH,
            reason="topology-contract-invalid",
        )
        observation = _load_observation(args.observation)
        receipt = validate_observation(contract, observation)
        exit_code = 0
    except TopologyBlocked as exc:
        receipt = _blocked_receipt(
            blocker=str(exc),
            contract=contract,
            observation=observation,
        )
        exit_code = 2

    _write_receipt(args.output, receipt)
    if args.json:
        print(json.dumps(receipt, sort_keys=True))
    else:
        print(receipt["status"])
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
