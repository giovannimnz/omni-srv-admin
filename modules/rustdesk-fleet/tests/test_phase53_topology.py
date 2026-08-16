from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[3]
CONTRACT_PATH = REPO / "modules/rustdesk-fleet/contracts/phase53-topology.json"
DISCOVERY_PATH = REPO / "modules/rustdesk-fleet/tools/discover-phase53-topology.py"
STALE_PLAN_PATH = (
    "modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json"
)


def _module() -> Any:
    assert DISCOVERY_PATH.is_file(), DISCOVERY_PATH
    spec = importlib.util.spec_from_file_location(
        "phase53_topology_discovery", DISCOVERY_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _contract() -> dict[str, Any]:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _valid_observation() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "observed_at": "2026-07-26T07:00:00Z",
        "sources": [
            "oci-admin:public-ip-inventory",
            "oci-admin:peering.drg_status",
            "host-readback:ip-route",
        ],
        "edge": {
            "host": "atius-srv-1",
            "profile": "atius1",
            "public_ip": {
                "address": "137.131.140.20",
                "allocation": "RESERVED",
                "state": "ASSIGNED",
            },
            "public_vnic": {
                "private_ipv4": "10.0.0.238",
                "owner_host": "atius-srv-1",
            },
            "route_vnic": {
                "private_ipv4": "10.11.1.11",
                "owner_host": "atius-srv-1",
            },
        },
        "backend": {
            "host": "horistic-srv",
            "profile": "horistic",
            "private_ipv4": "10.21.1.21",
            "public_ip_on_private_address": None,
            "separate_public_vnic": {
                "private_ipv4": "10.0.0.65",
                "public_ipv4": "163.176.232.119",
                "owner_host": "horistic-srv",
            },
        },
        "drg": {
            "edge_attachment_state": "attached_to_central",
            "backend_attachment_state": "attached_to_central",
            "edge_route": {
                "destination_cidr": "10.21.0.0/16",
                "target": "central-drg",
            },
            "backend_route": {
                "destination_cidr": "10.11.0.0/16",
                "target": "central-drg",
            },
        },
        "return_path": {
            "edge_to_backend": {
                "destination": "10.21.1.21",
                "via": "10.11.1.1",
                "device": "enp1s0",
                "source": "10.11.1.11",
            },
            "backend_to_edge": {
                "destination": "10.11.1.11",
                "via": "10.21.1.1",
                "device": "enp1s0",
                "source": "10.21.1.21",
            },
            "snat_source": "10.11.1.11",
            "backend_ingress_source": "10.11.1.11",
        },
        "stale_operation_plan": {
            "path": STALE_PLAN_PATH,
            "accepted_as_authority": False,
            "hash_reuse_allowed": False,
        },
        "future_handoff": {
            "private_ipv4": "10.31.1.31",
            "executable": False,
        },
    }


def _assert_blocked(observation: dict[str, Any], reason: str) -> None:
    module = _module()
    with pytest.raises(module.TopologyBlocked, match=reason):
        module.validate_observation(_contract(), observation)


def test_contract_models_exact_dual_vnic_topology() -> None:
    contract = _contract()
    assert contract["schema_version"] == 1
    assert contract["workstream"] == "rustdesk-fleet"
    assert contract["contract_id"] == "phase53-topology-d06-d16-d17-v1"
    assert contract["decisions"] == ["D-06", "D-16", "D-17"]
    assert contract["edge"] == {
        "host": "atius-srv-1",
        "profile": "atius1",
        "public_ip": {
            "address": "137.131.140.20",
            "allocation": "RESERVED",
            "state": "ASSIGNED",
        },
        "public_vnic": {
            "private_ipv4": "10.0.0.238",
            "owner_host": "atius-srv-1",
        },
        "route_vnic": {
            "private_ipv4": "10.11.1.11",
            "owner_host": "atius-srv-1",
        },
    }
    assert contract["backend"]["private_ipv4"] == "10.21.1.21"
    assert contract["backend"]["public_ip_on_private_address"] is None
    assert contract["backend"]["separate_public_vnic"] == {
        "private_ipv4": "10.0.0.65",
        "public_ipv4": "163.176.232.119",
        "owner_host": "horistic-srv",
    }
    assert contract["return_path"]["snat_source"] == "10.11.1.11"
    assert contract["return_path"]["backend_ingress_source"] == "10.11.1.11"
    assert contract["future_handoff"] == {
        "private_ipv4": "10.31.1.31",
        "executable": False,
    }
    assert contract["stale_operation_plan"]["accepted_as_authority"] is False
    assert contract["stale_operation_plan"]["hash_reuse_allowed"] is False


def test_valid_current_topology_passes_with_non_authorizing_receipt() -> None:
    receipt = _module().validate_observation(_contract(), _valid_observation())
    assert receipt["status"] == "PASS"
    assert receipt["authorizes_live"] is False
    assert receipt["committed_authority"] is False
    assert receipt["mutation_performed"] is False
    assert receipt["secret_material_present"] is False
    assert receipt["operation_plan_rejected"] is True
    assert receipt["future_handoff_executable"] is False
    assert receipt["checks"] == [
        "backend-private-address",
        "backend-public-vnic-separation",
        "drg-attachments",
        "drg-route-tables",
        "edge-public-ip-binding",
        "future-handoff-disabled",
        "operation-plan-rejected",
        "return-path",
    ]
    serialized = json.dumps(receipt, sort_keys=True)
    assert "ocid1." not in serialized
    assert "typed_confirmation" not in serialized
    assert "canonical_input_sha256" not in serialized
    assert "137.131.140.20" not in serialized
    assert "163.176.232.119" not in serialized


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (
            lambda item: item["edge"]["public_ip"].update(
                {"address": "137.131.140.21"}
            ),
            "edge-public-ip-binding-drift",
        ),
        (
            lambda item: item["edge"]["public_ip"].update({"state": "AVAILABLE"}),
            "edge-public-ip-binding-drift",
        ),
        (
            lambda item: item["edge"]["public_vnic"].update(
                {"private_ipv4": "10.0.0.239"}
            ),
            "edge-public-ip-binding-drift",
        ),
        (
            lambda item: item["edge"]["public_vnic"].update(
                {"owner_host": "horistic-srv"}
            ),
            "edge-public-ip-binding-drift",
        ),
        (
            lambda item: item["backend"].update(
                {"public_ip_on_private_address": "163.176.232.119"}
            ),
            "backend-public-ip-confusion",
        ),
        (
            lambda item: item["backend"]["separate_public_vnic"].update(
                {"private_ipv4": "10.21.1.21"}
            ),
            "backend-public-ip-confusion",
        ),
        (
            lambda item: item["drg"].update({"edge_route": None}),
            "drg-route-drift",
        ),
        (
            lambda item: item["return_path"]["backend_to_edge"].update(
                {"destination": "10.0.0.238"}
            ),
            "return-path-drift",
        ),
        (
            lambda item: item["return_path"].update(
                {"snat_source": "10.0.0.238"}
            ),
            "return-path-drift",
        ),
        (
            lambda item: item["stale_operation_plan"].update(
                {"accepted_as_authority": True}
            ),
            "stale-operation-plan-reuse",
        ),
        (
            lambda item: item["stale_operation_plan"].update(
                {"hash_reuse_allowed": True}
            ),
            "stale-operation-plan-reuse",
        ),
        (
            lambda item: item["future_handoff"].update({"executable": True}),
            "future-handoff-executable",
        ),
    ],
)
def test_topology_drift_blocks(
    mutator: Any,
    reason: str,
) -> None:
    observation = copy.deepcopy(_valid_observation())
    mutator(observation)
    _assert_blocked(observation, reason)


def test_discovery_source_exposes_no_provider_mutation_capability() -> None:
    source = DISCOVERY_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "oci_execute",
        "oci_plan(",
        "oci_plan_control",
        "oci_plan_multi",
        "subprocess.run",
        "subprocess.Popen",
        "os.system",
        "paramiko",
    ):
        assert forbidden not in source
    assert "PHASE53_TOPOLOGY_OBSERVATION_JSON" in source
    assert "--observation" in source


def test_cli_writes_pass_receipt_from_bounded_read_only_observation(
    tmp_path: Path,
) -> None:
    observation_path = tmp_path / "observation.json"
    output_path = tmp_path / "receipt.json"
    observation_path.write_text(
        json.dumps(_valid_observation(), sort_keys=True), encoding="utf-8"
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(DISCOVERY_PATH),
            "--repo",
            str(REPO),
            "--observation",
            str(observation_path),
            "--output",
            str(output_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 0, completed.stderr
    stdout = json.loads(completed.stdout)
    receipt = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout == receipt
    assert receipt["status"] == "PASS"


def test_cli_writes_blocked_receipt_and_nonzero_on_drift(tmp_path: Path) -> None:
    observation = _valid_observation()
    observation["drg"]["backend_attachment_state"] = "detached"
    observation_path = tmp_path / "observation.json"
    output_path = tmp_path / "receipt.json"
    observation_path.write_text(json.dumps(observation), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(DISCOVERY_PATH),
            "--repo",
            str(REPO),
            "--observation",
            str(observation_path),
            "--output",
            str(output_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 2
    receipt = json.loads(output_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "BLOCKED"
    assert receipt["blocker"] == "drg-attachment-drift"
    assert receipt["authorizes_live"] is False
    assert receipt["committed_authority"] is False
    assert receipt["mutation_performed"] is False


def test_cli_blocks_without_a_current_observation(tmp_path: Path) -> None:
    output_path = tmp_path / "receipt.json"
    env = dict(os.environ)
    env.pop("PHASE53_TOPOLOGY_OBSERVATION_JSON", None)
    completed = subprocess.run(
        [
            sys.executable,
            str(DISCOVERY_PATH),
            "--repo",
            str(REPO),
            "--output",
            str(output_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**env, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 2
    receipt = json.loads(output_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "BLOCKED"
    assert receipt["blocker"] == "current-read-only-observation-required"
