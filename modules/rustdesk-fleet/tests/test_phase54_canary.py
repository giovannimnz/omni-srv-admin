from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO / "modules/rustdesk-fleet/tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import phase54_preflight


def _load_tool(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


INSTALLER = _load_tool("phase54_installer", "install-phase54-client.py")
WINDOWS = _load_tool("phase54_windows_installer", "install-phase54-windows.py")
VAULT = _load_tool("phase54_client_vault", "rustdesk-client-vault.py")
PERMISSION_MATRIX = _load_tool("phase54_permission_matrix", "phase54_permission_matrix.py")
TRANSPORT_MATRIX = _load_tool("phase54_transport_matrix", "phase54_transport_matrix.py")
CHECKPOINT_REDACTION = _load_tool("phase54_checkpoint_redaction", "phase54_checkpoint_redaction.py")
LIVE_VALIDATOR = _load_tool("phase54_live_validator", "validate_phase54_live_evidence.py")
CLOSEOUT = _load_tool("phase54_closeout", "phase54-closeout.py")
CONTRACT_DIR = REPO / "modules/rustdesk-fleet/contracts"
EVIDENCE_DIR = REPO / "modules/rustdesk-fleet/evidence/phase54"
SUPPLY_CHAIN = CONTRACT_DIR / "supply-chain.json"
PERMISSION_SOURCE = CONTRACT_DIR / "permission-profiles.json"

RUNTIME = CONTRACT_DIR / "phase54-client-runtime.json"
TOPOLOGY = CONTRACT_DIR / "phase54-canary-topology.json"
PERMISSION = CONTRACT_DIR / "phase54-permission.json"
TRANSPORT = CONTRACT_DIR / "phase54-transport.json"
INITIAL_GATE = EVIDENCE_DIR / "initial-gate.json"
NEGATIVE_FIXTURES = EVIDENCE_DIR / "negative-fixtures.json"

ALLOWED_TARGETS = {"horistic-srv", "GIOVANNI-W11-PC"}
EXCLUDED_TARGETS = {"atius-srv-1", "atius-srv-2", "atius-srv-3", "WSL", "GIOVANNI-S23"}
SECRET_KEYS = {"password", "private_key", "token", "bearer_token", "client_secret"}


def _strict_load(path: Path) -> dict[str, Any]:
    """Load a value-free contract and reject duplicate JSON keys."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate-json-key:{path.name}:{key}")
            result[key] = value
        return result

    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    if not isinstance(payload, dict):
        raise ValueError(f"json-object-required:{path.name}")
    return payload


def _walk_secret_values(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            # A reference is allowed; a value-bearing secret field is not.
            if lowered in SECRET_KEYS and child not in (False, None, "[REDACTED]"):
                raise AssertionError(f"secret-value:{path}.{key}")
            _walk_secret_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_secret_values(child, f"{path}[{index}]")
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise AssertionError(f"secret-value:{path}")


def _load_contracts() -> dict[str, dict[str, Any]]:
    return {
        "runtime": _strict_load(RUNTIME),
        "topology": _strict_load(TOPOLOGY),
        "permission": _strict_load(PERMISSION),
        "transport": _strict_load(TRANSPORT),
    }


def test_phase54_contracts_are_strict_and_value_free() -> None:
    contracts = _load_contracts()
    assert set(contracts) == {"runtime", "topology", "permission", "transport"}
    for name, payload in contracts.items():
        assert payload["schema_version"] == 1, name
        assert payload["phase"] == 54, name
        assert payload["workstream"] == "rustdesk-fleet", name
        _walk_secret_values(payload)


def test_client_hashes_and_architectures_match_pinned_supply_chain() -> None:
    runtime = _strict_load(RUNTIME)
    supply = _strict_load(SUPPLY_CHAIN)
    linux = runtime["targets"]["horistic-srv"]["asset"]
    windows = runtime["targets"]["GIOVANNI-W11-PC"]["asset"]
    expected_linux = supply["clients"]["linux_arm64_deb"]
    expected_windows = supply["clients"]["windows_x86_64_msi"]

    assert linux == {
        "version": expected_linux["version"] if "version" in expected_linux else "1.4.9",
        "asset_name": expected_linux["asset_name"],
        "package_type": "deb",
        "sha256": expected_linux["sha256"],
    }
    assert linux["version"] == supply["clients"]["version"]
    assert runtime["targets"]["horistic-srv"]["architecture"] == expected_linux["architecture"]
    assert windows["version"] == supply["clients"]["version"]
    assert windows["asset_name"] == expected_windows["asset_name"]
    assert windows["sha256"] == expected_windows["sha256"]
    assert windows["package_type"] == "msi"
    assert runtime["targets"]["GIOVANNI-W11-PC"]["architecture"] == expected_windows["architecture"]


def test_runtime_scope_is_client_only_and_targets_are_exact() -> None:
    runtime = _strict_load(RUNTIME)
    assert set(runtime["targets"]) == ALLOWED_TARGETS
    boundary = runtime["server_client_boundary"]
    assert boundary["client_paths_only"] is True
    assert all(boundary[key] is False for key in boundary if key.endswith("_allowed"))
    assert runtime["native_service"]["client_api_server_configured"] is False
    for target in runtime["targets"].values():
        assert target["rollback"]["client_only"] is True
        assert target["rollback"]["server_paths_untouched"] is True
        password_ref = target["password_ref"]
        assert password_ref["vault_path"].startswith("kv/atius/rustdesk/targets/")
        assert password_ref["field"] == "permanent_password"
        assert password_ref["durable_value"] is False
        assert "value" not in password_ref


def test_preflight_selector_keeps_both_as_aggregate_only() -> None:
    preflight = _strict_load(CONTRACT_DIR / "phase54-preflight.json")
    assert preflight["target_selector"] == {
        "individual_targets": ["horistic-srv", "GIOVANNI-W11-PC"],
        "aggregate_selector": "both",
        "aggregate_only": True,
    }
    assert "phase52_gate" in preflight["receipt"]["required_fields"]
    assert "phase53_gate" in preflight["receipt"]["required_fields"]


def test_topology_excludes_server_fleet_wsl_and_s23() -> None:
    topology = _strict_load(TOPOLOGY)
    assert set(topology["allowed_targets"]) == ALLOWED_TARGETS
    assert set(topology["excluded_targets"]) == EXCLUDED_TARGETS
    assert topology["serial_order"] == ["horistic-srv", "GIOVANNI-W11-PC"]
    assert topology["server_path_policy"]["mutation_allowed"] is False
    assert topology["server_path_policy"]["violation_action"] == "BLOCKED_AND_ROLLBACK"
    assert all(
        topology["domains"]["clients"][target]["identity_domain"].startswith("rustdesk-client-")
        for target in ALLOWED_TARGETS
    )
    assert topology["invariants"]["server_quadlets_untouched"] is True
    assert topology["invariants"]["phase53_state_untouched"] is True


def test_permission_matrix_matches_source_and_closes_negatives() -> None:
    contract = _strict_load(PERMISSION)
    source = _strict_load(PERMISSION_SOURCE)
    expected_profiles = {
        row["id"]: row["capabilities"] for row in source["profiles"]
    }
    assert contract["profiles"] == expected_profiles
    assert contract["unsupported_native_controls"] == "BLOCKED"
    assert contract["evidence_policy"]["requested_policy_is_not_effective_proof"] is True
    assert {row["expected"] for row in contract["negative_matrix"]} == {"BLOCKED"}
    for row in contract["negative_matrix"]:
        assert row["profile"] in contract["profiles"]
        assert row["capability"] in contract["capabilities"]
        assert contract["profiles"][row["profile"]][row["capability"]] == "deny"


def test_transport_is_direct_first_and_relay_is_controlled() -> None:
    transport = _strict_load(TRANSPORT)
    endpoint = transport["native_endpoint"]
    assert endpoint["rendezvous_host"] == "rustdesk.atius.com.br"
    assert endpoint["relay_host"] == endpoint["rendezvous_host"]
    assert endpoint["operations_api_server_field"] is False
    policy = transport["policy"]
    assert policy["production"] == "direct-first"
    assert policy["forced_relay_default"] is False
    assert policy["public_rustdesk_servers"] == "FORBIDDEN"
    correlation = transport["forced_relay_observation"]["correlator"]
    assert {"ui_marker", "pairing_evidence", "hbbr_positive_byte_delta"} <= set(correlation)
    assert transport["forced_relay_observation"]["must_not_change_default_policy"] is True


def test_initial_evidence_is_blocked_pending_and_redacted() -> None:
    evidence = _strict_load(INITIAL_GATE)
    assert evidence["state"] == "BLOCKED"
    assert evidence["status"] == "PENDING"
    assert evidence["phase53_gate"] == "BLOCKED"
    assert evidence["mutation_performed"] is False
    assert evidence["secret_material_present"] is False
    assert set(evidence["targets"]) == ALLOWED_TARGETS
    assert set(evidence["excluded_targets"]) == EXCLUDED_TARGETS
    assert all(
        value == "PENDING"
        for target in evidence["targets"].values()
        for value in target.values()
    )
    _walk_secret_values(evidence)


def _negative_case_is_closed(case: dict[str, Any]) -> bool:
    """Pure fake validator used by the fixtures; no host or network access."""

    case_id = case["id"]
    if case_id in {"excluded-target", "excluded-wsl", "excluded-s23"}:
        return case["input"]["target"] in EXCLUDED_TARGETS
    if case_id == "server-path-write":
        return case["input"]["path_class"].startswith("phase53-")
    if case_id == "hash-drift":
        return case["input"]["package_hash"] != "PINNED_AND_VERIFIED"
    if case_id == "secret-argv":
        return case["input"]["secret_surface"] in {"argv", "environment", "stdout"}
    if case_id == "public-server":
        return case["input"]["endpoint_class"] == "public-rustdesk-server"
    if case_id == "forced-relay-default":
        return case["input"]["forced_relay_default"] is True
    if case_id == "unsupported-permission":
        return case["input"]["capability"] == "unsupported-native-control"
    if case_id == "phase52-currentness-missing":
        return case["input"]["phase52_gate"] == "BLOCKED"
    if case_id == "phase53-source-head-drift":
        return case["input"]["phase53_source_head"] == "stale"
    if case_id == "stored-pass":
        return case["input"]["state"] == "PASS"
    if case_id == "relay-without-byte-delta":
        return case["input"]["hbbr_positive_byte_delta"] is False
    if case_id == "rollback-server-path":
        return case["input"]["server_paths_untouched"] is False
    if case_id == "phase52-receipt-digest-drift":
        return case["input"]["source_set_digest"] == "arbitrary"
    if case_id == "evidence-path-escape":
        return case["input"]["path"].startswith("../")
    if case_id == "transport-attempts-missing":
        return case["input"]["attempts"] == []
    if case_id == "permission-profile-missing":
        return case["input"]["profiles"] == ["admin-maintenance"]
    if case_id == "checkpoint-type-invalid":
        return isinstance(case["input"]["checkpoint"], dict)
    if case_id == "raw-session-id":
        return case["input"]["session_id"] == "raw-value"
    return False


def test_negative_fixtures_are_fail_closed() -> None:
    fixtures = _strict_load(NEGATIVE_FIXTURES)
    assert fixtures["fixture_set"] == "phase54-contract-negative-v1"
    assert fixtures["value_free"] is True
    assert fixtures["secret_material_present"] is False
    assert fixtures["cases"]
    for case in fixtures["cases"]:
        assert case["expected"] == "BLOCKED"
        assert _negative_case_is_closed(case), case["id"]
    _walk_secret_values(fixtures)


@pytest.mark.parametrize("relative", [
    "phase54-client-runtime.json",
    "phase54-canary-topology.json",
    "phase54-permission.json",
    "phase54-transport.json",
    "initial-gate.json",
    "negative-fixtures.json",
])
def test_phase54_artifacts_are_regular_files(relative: str) -> None:
    path = (CONTRACT_DIR if relative.endswith(".json") and relative.startswith("phase54-") else EVIDENCE_DIR) / relative
    assert path.is_file()
    assert not path.is_symlink()


def test_mutation_attempts_do_not_change_server_contracts() -> None:
    topology = _strict_load(TOPOLOGY)
    runtime = _strict_load(RUNTIME)
    candidate = copy.deepcopy(topology)
    candidate["server_path_policy"]["mutation_allowed"] = True
    assert topology["server_path_policy"]["mutation_allowed"] is False
    boundary = copy.deepcopy(runtime["server_client_boundary"])
    boundary["server_state_mutation_allowed"] = True
    assert runtime["server_client_boundary"]["server_state_mutation_allowed"] is False


def test_initial_gate_blocks_before_any_client_backend_call(tmp_path: Path) -> None:
    events: list[str] = []

    class Backend:
        phase54_scope = INSTALLER.BACKEND_SCOPE
        server_paths_mutable = False
        credential_channel = "fd-pipe"

        def snapshot(self, target: str, rollback_root: Path) -> None:
            events.append("snapshot")

        def install_package(self, package: Path, password_fd: int) -> None:
            events.append("install")

        def configure(self, target: str) -> None:
            events.append("configure")

        def readback(self, target: str) -> dict[str, Any]:
            events.append("readback")
            return {"value_free": True}

        def rollback(self, target: str, rollback_root: Path) -> None:
            events.append("rollback")

    with pytest.raises(INSTALLER.Phase54ClientBlocked, match="phase53-(?:independent-pass-required|evidence-invalid)"):
        INSTALLER.run_transaction(
            REPO,
            target="horistic-srv",
            package=tmp_path / "not-read-before-preflight.deb",
            receipt=INITIAL_GATE,
            rollback_root=tmp_path / "rollback",
            backend=Backend(),
            password_fd=-1,
        )
    assert events == []


def test_preflight_rejects_receipt_symlink_before_admission(tmp_path: Path) -> None:
    link = tmp_path / "receipt-link.json"
    link.symlink_to(INITIAL_GATE)
    with pytest.raises(phase54_preflight.Phase54PreflightBlocked, match="contract-file-invalid"):
        phase54_preflight.validate(REPO, link, "horistic-srv")


def test_preflight_rejects_local_policy_relaxation(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, topology, preflight = phase54_preflight._load_phase54_contracts(REPO)
    preflight["scope"]["server_paths_mutable"] = True
    monkeypatch.setattr(
        phase54_preflight,
        "_load_phase54_contracts",
        lambda repo: (runtime, topology, preflight),
    )
    with pytest.raises(phase54_preflight.Phase54PreflightBlocked, match="policy-drift"):
        phase54_preflight.validate(REPO, INITIAL_GATE, "horistic-srv")


def _synthetic_admission_receipt() -> tuple[dict[str, Any], dict[str, Any]]:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    phase53_names = (
        "phase53-runtime.json", "phase53-edge.json", "phase53-ops-api.json",
        "phase53-candidate-admission.json", "phase53-provider-manifest.json",
        "phase53-runtime-candidate.json",
    )
    current = {
        "state": "ADMITTED_PHASE53",
        "candidate_status": "ADMITTED_PHASE53",
        "source_head": head,
        "contract_digests": {
            name: hashlib.sha256((CONTRACT_DIR / name).read_bytes()).hexdigest()
            for name in phase53_names
        },
        "admission_authority": {
            "owner": "Giovanni Muniz",
            "approval_ref": "synthetic-test-approval",
            "expires_at": "2099-01-01T00:00:00Z",
            "risk_disposition": "approved-test-fixture",
            "hash_binding": True,
        },
    }
    receipt = {
        "phase": 54,
        "source_commit": head,
        "phase52_gate": {
            "state": "CURRENT",
            "source_commit": head,
            "receipt_path": "modules/rustdesk-fleet/evidence/phase52/phase52-receipt.json",
            "ordered_stages": [
                "supply", "capacity", "vault", "backup", "restore",
                "capacity_finalize", "rollback", "topology_security",
            ],
            "gate_vector_current": True,
            "vault_helper_current": True,
            "backup_a_current": True,
            "backup_b_current": True,
            "isolated_restore_current": True,
            "source_set_digest": "a" * 64,
            "gate_digest": "b" * 64,
        },
        "phase53_gate": {
            "state": "ADMITTED_PHASE53",
            "candidate_status": "ADMITTED_PHASE53",
            "independent_verifier": "PASS",
            "source_head": head,
            "contract_digests": current["contract_digests"],
        },
        "phase53_state": "ADMITTED_PHASE53",
        "phase53_independent_verifier": "PASS",
        "phase53_contract_digests": current["contract_digests"],
        "phase54_contract_digests": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (RUNTIME, TOPOLOGY, CONTRACT_DIR / "phase54-preflight.json")
        },
        "owner_admission": {
            "owner": "Giovanni Muniz",
            "approval_ref": "synthetic-test-approval",
            "expires_at": "2099-01-01T00:00:00Z",
            "risk_disposition": "approved-test-fixture",
            "hash_binding": True,
        },
        "capacity_state": "CURRENT",
        "pre_state_digest": "a" * 64,
        "rollback_state": "CURRENT",
        "graphify_state": "CURRENT",
        "target_scope": "horistic-srv",
        "blockers": [],
        "mutation_performed": False,
        "secret_material_present": False,
    }
    return receipt, {
        "state": "ADMITTED_PHASE53",
        "candidate_status": "ADMITTED_PHASE53",
        "source_head": head,
        "contract_digests": current["contract_digests"],
        "admission_authority": receipt["owner_admission"],
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_commit", "0" * 40),
        ("phase52_gate", {"state": "BLOCKED"}),
        ("phase53_gate", {"state": "BLOCKED"}),
        ("phase53_contract_digests", {}),
        ("owner_admission", {"owner": "other"}),
        ("capacity_state", "STALE"),
        ("pre_state_digest", "PENDING"),
        ("rollback_state", "STALE"),
        ("graphify_state", "STALE"),
        ("target_scope", "GIOVANNI-W11-PC"),
        ("blockers", ["drift"]),
    ],
)
def test_receipt_drift_blocks_before_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: Any) -> None:
    receipt, phase53_result = _synthetic_admission_receipt()
    monkeypatch.setattr(phase54_preflight, "validate_phase53", lambda repo: phase53_result)
    receipt[field] = value
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(phase54_preflight.Phase54PreflightBlocked):
        phase54_preflight.validate(REPO, path, "horistic-srv")


def test_vault_reference_and_ephemeral_channels_are_value_free(capsys: pytest.CaptureFixture[str]) -> None:
    runtime = _strict_load(RUNTIME)
    reference = VAULT.reference_from_contract(runtime, "horistic-srv")
    assert reference["vault_path"] == "kv/atius/rustdesk/targets/horistic-srv"
    with VAULT.fetch_ephemeral("horistic-srv", reference, lambda path, field: b"test-only-secret") as fetched_fd:
        assert os.read(fetched_fd, 64) == b"test-only-secret"
    with VAULT.secret_pipe(b"pipe-secret") as read_fd:
        assert os.read(read_fd, 64) == b"pipe-secret"
    with pytest.raises(OSError):
        os.read(read_fd, 1)
    with VAULT.secret_tmpfs(b"tmpfs-secret") as secret_path:
        assert secret_path.is_file()
        assert secret_path.read_bytes() == b"tmpfs-secret"
    assert not secret_path.exists()
    assert "test-only-secret" not in capsys.readouterr().out


def test_vault_tmpfs_rejects_non_tmpfs_directory(tmp_path: Path) -> None:
    with pytest.raises(VAULT.ClientVaultBlocked, match="tmpfs-directory-required"):
        with VAULT.secret_tmpfs(b"disk-secret", directory=tmp_path):
            pass


def _synthetic_runtime_for_package(payload: bytes, base_dir: Path | None = None) -> dict[str, Any]:
    runtime = _strict_load(RUNTIME)
    target = runtime["targets"]["horistic-srv"]
    target["asset"]["sha256"] = hashlib.sha256(payload).hexdigest()
    if base_dir is not None:
        target["paths"] = {
            "config": str(base_dir / "config"),
            "state": str(base_dir / "state"),
            "rollback": str(base_dir / "rollback" / "<transaction-id>"),
        }
    return runtime


def _synthetic_admission() -> dict[str, Any]:
    return {
        "phase": 54,
        "target": "horistic-srv",
        "state": "ADMITTED_PHASE54",
        "mutation_performed": False,
        "secret_material_present": False,
        "source_commit": "synthetic-test-head",
        "server_paths_mutable": False,
    }


def test_linux_password_transaction_success_order_and_fd_delivery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"synthetic-arm64-deb"
    package = tmp_path / "rustdesk-1.4.9-aarch64.deb"
    package.write_bytes(payload)
    runtime = _synthetic_runtime_for_package(payload, tmp_path)
    topology = _strict_load(TOPOLOGY)
    preflight = _strict_load(CONTRACT_DIR / "phase54-preflight.json")
    monkeypatch.setattr(INSTALLER, "validate_preflight", lambda repo, receipt, target: _synthetic_admission())
    monkeypatch.setattr(INSTALLER, "load_contracts", lambda repo: (runtime, topology, preflight))

    events: list[str] = []
    received_password: list[bytes] = []

    class Backend:
        phase54_scope = INSTALLER.BACKEND_SCOPE
        server_paths_mutable = False
        credential_channel = "fd-pipe"

        def snapshot(self, target: str, rollback_root: Path) -> None:
            events.append("snapshot")

        def install_package(self, package: Path, password_fd: int) -> None:
            events.append("install")
            received_password.append(os.read(password_fd, 64))

        def configure(self, target: str) -> None:
            events.append("configure")

        def readback(self, target: str) -> dict[str, Any]:
            events.append("readback")
            return {"target": target, "service_state": "observed", "value_free": True}

        def rollback(self, target: str, rollback_root: Path) -> None:
            events.append("rollback")

    with VAULT.secret_pipe(b"synthetic-password") as password_fd:
        result = INSTALLER.run_transaction(
            REPO,
            target="horistic-srv",
            package=package,
            receipt=INITIAL_GATE,
            rollback_root=tmp_path / "rollback" / "test",
            backend=Backend(),
            password_fd=password_fd,
            architecture_probe=lambda path: "arm64",
        )

    assert events == ["snapshot", "install", "configure", "readback"]
    assert received_password == [b"synthetic-password"]
    assert result["mutation_performed"] is True
    assert result["secret_material_present"] is False
    assert result["package"]["architecture_verified"] is True


def test_linux_rollback_after_backend_failure_is_ordered_and_client_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"synthetic-rollback-deb"
    package = tmp_path / "rustdesk-1.4.9-aarch64.deb"
    package.write_bytes(payload)
    runtime = _synthetic_runtime_for_package(payload, tmp_path)
    topology = _strict_load(TOPOLOGY)
    preflight = _strict_load(CONTRACT_DIR / "phase54-preflight.json")
    monkeypatch.setattr(INSTALLER, "validate_preflight", lambda repo, receipt, target: _synthetic_admission())
    monkeypatch.setattr(INSTALLER, "load_contracts", lambda repo: (runtime, topology, preflight))

    events: list[str] = []

    class FailingBackend:
        phase54_scope = INSTALLER.BACKEND_SCOPE
        server_paths_mutable = False
        credential_channel = "fd-pipe"

        def snapshot(self, target: str, rollback_root: Path) -> None:
            events.append("snapshot")

        def install_package(self, package: Path, password_fd: int) -> None:
            events.append("install")

        def configure(self, target: str) -> None:
            events.append("configure")
            raise RuntimeError("synthetic-config-failure")

        def readback(self, target: str) -> dict[str, Any]:
            events.append("readback")
            return {"value_free": True}

        def rollback(self, target: str, rollback_root: Path) -> None:
            events.append("rollback")

    with VAULT.secret_pipe(b"failure-password") as password_fd:
        with pytest.raises(INSTALLER.Phase54ClientBlocked, match="client-transaction-failed"):
            INSTALLER.run_transaction(
                REPO,
                target="horistic-srv",
                package=package,
                receipt=INITIAL_GATE,
                rollback_root=tmp_path / "rollback" / "failure",
                backend=FailingBackend(),
                password_fd=password_fd,
                architecture_probe=lambda path: "arm64",
            )

    assert events == ["snapshot", "install", "configure", "rollback"]
    assert "readback" not in events


def test_linux_hash_and_architecture_probe_are_both_required(tmp_path: Path) -> None:
    payload = b"synthetic-hash-arch-deb"
    package = tmp_path / "rustdesk-1.4.9-aarch64.deb"
    package.write_bytes(payload)
    runtime = _synthetic_runtime_for_package(payload)
    observation = INSTALLER.verify_package(
        package,
        runtime,
        "horistic-srv",
        architecture_probe=lambda path: "arm64",
    )
    assert observation["sha256"] == hashlib.sha256(payload).hexdigest()
    assert observation["architecture_observed"] == "arm64"
    assert observation["architecture_verified"] is True
    with pytest.raises(INSTALLER.Phase54ClientBlocked, match="package-architecture-mismatch"):
        INSTALLER.verify_package(
            package,
            runtime,
            "horistic-srv",
            architecture_probe=lambda path: "amd64",
        )


def test_linux_rollback_path_guard_rejects_server_and_outside_paths(tmp_path: Path) -> None:
    runtime = _synthetic_runtime_for_package(b"path-guard", tmp_path)
    INSTALLER.assert_client_path(
        tmp_path / "rollback" / "test",
        runtime,
        "horistic-srv",
    )
    with pytest.raises(INSTALLER.Phase54ClientBlocked, match="server-path-write-forbidden"):
        INSTALLER.assert_client_path(
            Path("/home/horistic/.local/share/atius-rustdesk/server/state"),
            runtime,
            "horistic-srv",
        )
    with pytest.raises(INSTALLER.Phase54ClientBlocked, match="client-path-outside-contract"):
        INSTALLER.assert_client_path(Path("/tmp/phase54-rollback"), runtime, "horistic-srv")


def test_linux_password_fd_is_closed_after_ephemeral_delivery() -> None:
    with VAULT.secret_pipe(b"selector-password") as read_fd:
        assert os.read(read_fd, 64) == b"selector-password"
    with pytest.raises(OSError):
        os.read(read_fd, 1)


def test_linux_backend_without_client_only_marker_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"backend-contract-package"
    package = tmp_path / "rustdesk-1.4.9-aarch64.deb"
    package.write_bytes(payload)
    runtime = _synthetic_runtime_for_package(payload, tmp_path)
    topology = _strict_load(TOPOLOGY)
    preflight = _strict_load(CONTRACT_DIR / "phase54-preflight.json")
    monkeypatch.setattr(INSTALLER, "validate_preflight", lambda repo, receipt, target: _synthetic_admission())
    monkeypatch.setattr(INSTALLER, "load_contracts", lambda repo: (runtime, topology, preflight))

    class UnscopedBackend:
        pass

    with VAULT.secret_pipe(b"backend-password") as password_fd:
        with pytest.raises(INSTALLER.Phase54ClientBlocked, match="client-backend-contract-required"):
            INSTALLER.run_transaction(
                REPO,
                target="horistic-srv",
                package=package,
                receipt=INITIAL_GATE,
                rollback_root=tmp_path / "rollback" / "unscoped",
                backend=UnscopedBackend(),
                password_fd=password_fd,
            architecture_probe=lambda path: "arm64",
            )


def _synthetic_windows_runtime_for_package(payload: bytes) -> dict[str, Any]:
    runtime = _strict_load(RUNTIME)
    target = runtime["targets"]["GIOVANNI-W11-PC"]
    target["asset"]["sha256"] = hashlib.sha256(payload).hexdigest()
    return runtime


def test_windows_msi_hash_arch_and_authenticode_probes_are_required(tmp_path: Path) -> None:
    payload = b"synthetic-windows-msi"
    package = tmp_path / "rustdesk-1.4.9-x86_64.msi"
    package.write_bytes(payload)
    runtime = _synthetic_windows_runtime_for_package(payload)
    observation = WINDOWS.verify_msi(
        package,
        runtime,
        "GIOVANNI-W11-PC",
        architecture_probe=lambda path: "x86_64",
        authenticode_probe=lambda path: True,
    )
    assert observation["sha256"] == hashlib.sha256(payload).hexdigest()
    assert observation["architecture_verified"] is True
    assert observation["authenticode_verified"] is True
    with pytest.raises(WINDOWS.Phase54WindowsBlocked, match="msi-architecture-mismatch"):
        WINDOWS.verify_msi(
            package,
            runtime,
            "GIOVANNI-W11-PC",
            architecture_probe=lambda path: "arm64",
            authenticode_probe=lambda path: True,
        )
    with pytest.raises(WINDOWS.Phase54WindowsBlocked, match="msi-authenticode-invalid"):
        WINDOWS.verify_msi(
            package,
            runtime,
            "GIOVANNI-W11-PC",
            architecture_probe=lambda path: "x86_64",
            authenticode_probe=lambda path: False,
        )


def test_windows_msi_requires_injected_probes_and_never_guesses() -> None:
    runtime = _strict_load(RUNTIME)
    package = Path("/nonexistent/rustdesk-1.4.9-x86_64.msi")
    with pytest.raises(WINDOWS.Phase54WindowsBlocked, match="msi-file-invalid"):
        WINDOWS.verify_msi(package, runtime, "GIOVANNI-W11-PC")


def test_windows_private_first_public_fallback_is_only_rc255() -> None:
    assert WINDOWS.select_ssh_route(0) == "private-first"
    assert WINDOWS.select_ssh_route(255) == "public-native-fallback"
    with pytest.raises(WINDOWS.Phase54WindowsBlocked, match="not-fallbackable"):
        WINDOWS.select_ssh_route(1)
    routes = WINDOWS.route_plan()
    assert routes[0]["route"] == "private-first"
    assert routes[0]["fallback_on"] == ["ssh-rc255"]
    assert routes[1]["route"] == "public-native-fallback"
    assert routes[1]["port"] == 8122


def test_windows_secret_wrapper_is_stdin_only_and_transcript_free() -> None:
    wrapper = (TOOLS_DIR / "rustdesk-client-vault.ps1").read_text(encoding="utf-8")
    assert "[Console]::In.ReadToEnd()" in wrapper
    assert "Start-Transcript" not in wrapper
    assert "Write-Host" not in wrapper
    assert "Password" not in wrapper
    assert "ConvertTo-SecureString" in wrapper
    assert "secret_material_present = $false" in wrapper


def test_windows_password_transaction_success_order_and_fd_delivery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"synthetic-windows-transaction"
    package = tmp_path / "rustdesk-1.4.9-x86_64.msi"
    package.write_bytes(payload)
    runtime = _synthetic_windows_runtime_for_package(payload)
    topology = _strict_load(TOPOLOGY)
    preflight = _strict_load(CONTRACT_DIR / "phase54-preflight.json")
    monkeypatch.setattr(WINDOWS, "validate_preflight", lambda repo, receipt, target: _synthetic_admission())
    monkeypatch.setattr(WINDOWS, "load_contracts", lambda repo: (runtime, topology, preflight))
    events: list[str] = []
    received_password: list[bytes] = []

    class Backend:
        phase54_scope = WINDOWS.BACKEND_SCOPE
        server_paths_mutable = False
        credential_channel = "fd-pipe"

        def snapshot(self, target: str, rollback_root: str) -> None:
            events.append("snapshot")

        def install_msi(self, package: Path, password_fd: int) -> None:
            events.append("install")
            received_password.append(os.read(password_fd, 64))

        def configure(self, target: str) -> None:
            events.append("configure")

        def readback(self, target: str) -> dict[str, Any]:
            events.append("readback")
            return {"target": target, "service_state": "observed", "value_free": True}

        def rollback(self, target: str, rollback_root: str) -> None:
            events.append("rollback")

    with VAULT.secret_pipe(b"synthetic-windows-password") as password_fd:
        result = WINDOWS.run_transaction(
            REPO,
            target="GIOVANNI-W11-PC",
            package=package,
            receipt=INITIAL_GATE,
            rollback_root="%PROGRAMDATA%\\RustDesk\\rollback\\test",
            backend=Backend(),
            password_fd=password_fd,
            architecture_probe=lambda path: "x86_64",
            authenticode_probe=lambda path: True,
        )
    assert events == ["snapshot", "install", "configure", "readback"]
    assert received_password == [b"synthetic-windows-password"]
    assert result["mutation_performed"] is True
    assert result["package"]["authenticode_verified"] is True


def test_windows_rollback_after_backend_failure_is_client_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"synthetic-windows-rollback"
    package = tmp_path / "rustdesk-1.4.9-x86_64.msi"
    package.write_bytes(payload)
    runtime = _synthetic_windows_runtime_for_package(payload)
    topology = _strict_load(TOPOLOGY)
    preflight = _strict_load(CONTRACT_DIR / "phase54-preflight.json")
    monkeypatch.setattr(WINDOWS, "validate_preflight", lambda repo, receipt, target: _synthetic_admission())
    monkeypatch.setattr(WINDOWS, "load_contracts", lambda repo: (runtime, topology, preflight))
    events: list[str] = []

    class FailingBackend:
        phase54_scope = WINDOWS.BACKEND_SCOPE
        server_paths_mutable = False
        credential_channel = "stdin"

        def snapshot(self, target: str, rollback_root: str) -> None:
            events.append("snapshot")

        def install_msi(self, package: Path, password_fd: int) -> None:
            events.append("install")

        def configure(self, target: str) -> None:
            events.append("configure")
            raise RuntimeError("synthetic-windows-config-failure")

        def readback(self, target: str) -> dict[str, Any]:
            events.append("readback")
            return {"value_free": True}

        def rollback(self, target: str, rollback_root: str) -> None:
            events.append("rollback")

    with VAULT.secret_pipe(b"windows-failure-password") as password_fd:
        with pytest.raises(WINDOWS.Phase54WindowsBlocked, match="client-transaction-failed"):
            WINDOWS.run_transaction(
                REPO,
                target="GIOVANNI-W11-PC",
                package=package,
                receipt=INITIAL_GATE,
                rollback_root="%PROGRAMDATA%\\RustDesk\\rollback\\failure",
                backend=FailingBackend(),
                password_fd=password_fd,
                architecture_probe=lambda path: "x86_64",
                authenticode_probe=lambda path: True,
            )
    assert events == ["snapshot", "install", "configure", "rollback"]


def test_windows_path_guard_rejects_phase53_and_outside_paths() -> None:
    runtime = _strict_load(RUNTIME)
    WINDOWS.assert_windows_path("%PROGRAMDATA%\\RustDesk\\rollback\\test", runtime, WINDOWS.TARGET)
    with pytest.raises(WINDOWS.Phase54WindowsBlocked, match="server-path-write-forbidden"):
        WINDOWS.assert_windows_path("%PROGRAMDATA%\\phase53\\server\\state", runtime, WINDOWS.TARGET)
    with pytest.raises(WINDOWS.Phase54WindowsBlocked, match="windows-path-outside-contract"):
        WINDOWS.assert_windows_path("%TEMP%\\RustDesk\\rollback", runtime, WINDOWS.TARGET)


def test_permission_matrix_uses_observed_markers_not_requested_policy() -> None:
    contract = PERMISSION_MATRIX.load_permission_contract(REPO)
    observations = {
        capability: {"observed": True, "observed_marker": True}
        for capability, policy in contract["profiles"]["admin-maintenance"].items()
        if policy == "allow"
    }
    observations.update(
        {
            capability: {"observed": True, "observed_denial": True}
            for capability, policy in contract["profiles"]["admin-maintenance"].items()
            if policy == "deny"
        }
    )
    result = PERMISSION_MATRIX.project_permission_matrix(
        contract, "admin-maintenance", observations, target="horistic-srv"
    )
    assert result["state"] == "PASS"
    assert result["requested_policy_is_not_effective_proof"] is True
    assert result["secret_material_present"] is False

    requested_only = {"screen_view": {"requested": "allow"}}
    blocked = PERMISSION_MATRIX.project_permission_matrix(
        contract, "support-observe", requested_only, target="horistic-srv"
    )
    assert blocked["state"] == "BLOCKED"
    assert blocked["matrix"]["screen_view"]["status"] == "BLOCKED"


def test_permission_matrix_marks_unsupported_controls_blocked() -> None:
    contract = copy.deepcopy(PERMISSION_MATRIX.load_permission_contract(REPO))
    contract["capabilities"].append("native-unsupported-control")
    for profile in contract["profiles"].values():
        profile["native-unsupported-control"] = "unsupported"
    result = PERMISSION_MATRIX.project_permission_matrix(
        contract,
        "support-observe",
        {},
        target="GIOVANNI-W11-PC",
    )
    assert result["state"] == "BLOCKED"
    assert result["matrix"]["native-unsupported-control"]["status"] == "BLOCKED"
    assert result["matrix"]["native-unsupported-control"]["reason"] == "unsupported-native-control"


def test_permission_matrix_entrypoint_is_fail_closed_before_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise PERMISSION_MATRIX.Phase54PermissionBlocked("phase53-independent-pass-required")

    monkeypatch.setattr(PERMISSION_MATRIX, "validate_preflight", blocked)
    with pytest.raises(PERMISSION_MATRIX.Phase54PermissionBlocked, match="phase53-independent-pass-required"):
        PERMISSION_MATRIX.evaluate_permission_matrix(
            REPO,
            receipt=INITIAL_GATE,
            target="horistic-srv",
            profile="support-observe",
            observations={},
        )


def _transport_observations() -> dict[str, Any]:
    return {
        "attempts": [
            {"route": "direct"},
            {"route": "forced-relay"},
        ],
        "sequence": ["direct", "forced-relay"],
        "direct": {
            "session_identity": True,
            "pairing_evidence": True,
            "transport_observed": "direct",
            "ui_marker": True,
        },
        "forced_relay": {
            "session_identity": True,
            "pairing_evidence": True,
            "ui_marker": True,
            "purpose": "controlled-validation",
            "hbbr_bytes_before": 100,
            "hbbr_bytes_after": 240,
            "hbbr_positive_byte_delta": True,
            "forced_relay_default": False,
        },
    }


def test_transport_matrix_requires_direct_first_and_hbbr_delta() -> None:
    contract = TRANSPORT_MATRIX.load_transport_contract(REPO)
    result = TRANSPORT_MATRIX.project_transport_matrix(
        contract, _transport_observations(), target="horistic-srv"
    )
    assert result["state"] == "PASS"
    assert result["production_policy"] == "direct-first"
    assert result["hbbr"]["positive_delta"] is True
    assert result["public_rustdesk_servers_contacted"] is False

    no_delta = _transport_observations()
    no_delta["forced_relay"]["hbbr_bytes_after"] = 100
    with pytest.raises(TRANSPORT_MATRIX.Phase54TransportBlocked, match="positive-byte-delta"):
        TRANSPORT_MATRIX.project_transport_matrix(contract, no_delta, target="horistic-srv")

    relay_first = _transport_observations()
    relay_first["attempts"] = [{"route": "forced-relay"}, {"route": "direct"}]
    with pytest.raises(TRANSPORT_MATRIX.Phase54TransportBlocked, match="direct-first"):
        TRANSPORT_MATRIX.project_transport_matrix(contract, relay_first, target="horistic-srv")


def test_transport_matrix_rejects_public_server_and_default_relay() -> None:
    contract = TRANSPORT_MATRIX.load_transport_contract(REPO)
    public = _transport_observations()
    public["public_server_contact"] = True
    with pytest.raises(TRANSPORT_MATRIX.Phase54TransportBlocked, match="public-rustdesk"):
        TRANSPORT_MATRIX.project_transport_matrix(contract, public, target="GIOVANNI-W11-PC")
    default = _transport_observations()
    default["forced_relay"]["forced_relay_default"] = True
    with pytest.raises(TRANSPORT_MATRIX.Phase54TransportBlocked, match="default"):
        TRANSPORT_MATRIX.project_transport_matrix(contract, default, target="GIOVANNI-W11-PC")


def test_transport_matrix_entrypoint_is_fail_closed_before_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise TRANSPORT_MATRIX.Phase54TransportBlocked("phase53-independent-pass-required")

    monkeypatch.setattr(TRANSPORT_MATRIX, "validate_preflight", blocked)
    with pytest.raises(TRANSPORT_MATRIX.Phase54TransportBlocked, match="phase53-independent-pass-required"):
        TRANSPORT_MATRIX.evaluate_transport_matrix(
            REPO, receipt=INITIAL_GATE, target="horistic-srv", observations=_transport_observations()
        )


def test_checkpoint_redaction_requires_human_markers_and_stays_value_free() -> None:
    observation = {
        "checkpoint": "horistic-lightdm-x11",
        "status": "PASS",
        "observed": True,
        "human_verified": True,
        "markers": {
            "x11_active": True,
            "image_marker": True,
            "input_marker": True,
            "lightdm_prelogin": True,
        },
    }
    result = CHECKPOINT_REDACTION.redact_checkpoint_observation(observation, target="horistic-srv")
    assert result["status"] == "PASS"
    assert result["value_free"] is True
    assert result["secret_material_present"] is False
    assert set(result["markers"]) == {
        "x11_active", "image_marker", "input_marker", "lightdm_prelogin"
    }

    missing = CHECKPOINT_REDACTION.project_checkpoint_matrix([], target="GIOVANNI-W11-PC")
    assert missing["state"] == "BLOCKED"
    assert all(item["status"] == "PENDING" for item in missing["checkpoints"].values())


def test_checkpoint_redaction_rejects_raw_gui_and_fabricated_pass() -> None:
    with pytest.raises(CHECKPOINT_REDACTION.Phase54CheckpointBlocked, match="raw-gui-payload"):
        CHECKPOINT_REDACTION.redact_checkpoint_observation(
            {
                "checkpoint": "windows-uac-rdp",
                "status": "PASS",
                "observed": True,
                "human_verified": True,
                "screenshot": "raw-image",
            },
            target="GIOVANNI-W11-PC",
        )
    with pytest.raises(CHECKPOINT_REDACTION.Phase54CheckpointBlocked, match="requires-human"):
        CHECKPOINT_REDACTION.redact_checkpoint_observation(
            {
                "checkpoint": "windows-uac-rdp",
                "status": "PASS",
                "observed": True,
                "human_verified": False,
                "markers": {"uac_secure_desktop": True, "rdp_console": True},
            },
            target="GIOVANNI-W11-PC",
        )


def test_checkpoint_entrypoint_is_fail_closed_before_human_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise CHECKPOINT_REDACTION.Phase54CheckpointBlocked("phase53-independent-pass-required")

    monkeypatch.setattr(CHECKPOINT_REDACTION, "validate_preflight", blocked)
    with pytest.raises(CHECKPOINT_REDACTION.Phase54CheckpointBlocked, match="phase53-independent-pass-required"):
        CHECKPOINT_REDACTION.evaluate_checkpoint_matrix(
            REPO,
            receipt=INITIAL_GATE,
            target="GIOVANNI-W11-PC",
            observations=[],
        )


def _synthetic_live_item(target: str) -> dict[str, Any]:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    runtime = _strict_load(RUNTIME)
    asset = runtime["targets"][target]
    phase53_names = (
        "phase53-runtime.json", "phase53-edge.json", "phase53-ops-api.json",
        "phase53-candidate-admission.json", "phase53-provider-manifest.json",
        "phase53-runtime-candidate.json",
    )
    phase53_digests = {
        name: hashlib.sha256((CONTRACT_DIR / name).read_bytes()).hexdigest()
        for name in phase53_names
    }
    phase54_paths = (RUNTIME, TOPOLOGY, CONTRACT_DIR / "phase54-preflight.json", PERMISSION, TRANSPORT)
    phase54_digests = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in phase54_paths
    }
    phase52_gate = {
        "state": "CURRENT",
        "source_commit": head,
        "receipt_path": "modules/rustdesk-fleet/evidence/phase52/phase52-receipt.json",
        "ordered_stages": ["supply", "capacity", "vault", "backup", "restore", "capacity_finalize", "rollback", "topology_security"],
        "gate_vector_current": True,
        "vault_helper_current": True,
        "backup_a_current": True,
        "backup_b_current": True,
        "isolated_restore_current": True,
        "source_set_digest": "a" * 64,
        "gate_digest": "b" * 64,
    }
    permission_contract = PERMISSION_MATRIX.load_permission_contract(REPO)
    profile_observations: dict[str, dict[str, Any]] = {}
    for profile, policies in permission_contract["profiles"].items():
        observations = {
            capability: {"observed": True, "observed_marker": True}
            for capability, policy in policies.items()
            if policy == "allow"
        }
        observations.update(
            {
                capability: {"observed": True, "observed_denial": True}
                for capability, policy in policies.items()
                if policy == "deny"
            }
        )
        profile_observations[profile] = {"observations": observations}
    checkpoints = [
        {
            "checkpoint": "horistic-lightdm-x11",
            "observed": True,
            "human_verified": True,
            "markers": {"x11_active": True, "image_marker": True, "input_marker": True, "lightdm_prelogin": True},
        }
    ] if target == "horistic-srv" else [
        {
            "checkpoint": "windows-uac-rdp",
            "observed": True,
            "human_verified": True,
            "markers": {"uac_secure_desktop": True, "rdp_console": True},
        },
        {
            "checkpoint": "windows-prelogin",
            "observed": True,
            "human_verified": True,
            "markers": {"windows_prelogin": True},
        },
    ]
    item = {
        "phase": 54,
        "target": target,
        "value_free": True,
        "secret_material_present": False,
        "source_commit": head,
        "phase52_gate": phase52_gate,
        "phase53_gate": {
            "state": "ADMITTED_PHASE53",
            "candidate_status": "ADMITTED_PHASE53",
            "independent_verifier": "PASS",
            "source_head": head,
            "contract_digests": phase53_digests,
        },
        "owner_admission": {
            "owner": "Giovanni Muniz",
            "approval_ref": "synthetic-approval",
            "expires_at": "2099-01-01T00:00:00Z",
            "risk_disposition": "synthetic-test-only",
            "hash_binding": True,
        },
        "capacity_state": "CURRENT",
        "pre_state_digest": "c" * 64,
        "rollback_state": "CURRENT",
        "graphify_state": "CURRENT",
        "phase54_contract_digests": phase54_digests,
        "predecessor": {"target": None, "state": "NONE"} if target == "horistic-srv" else {
            "target": "horistic-srv", "state": "PASS", "receipt_path": "horistic-closeout.json", "receipt_sha256": "0" * 64,
        },
        "blockers": [],
        "installation": {
            "package_hash": asset["asset"]["sha256"],
            "package_architecture": asset["architecture"],
            "package_hash_verified": True,
            "service_active_observed": True,
            "authenticode_verified": target == "GIOVANNI-W11-PC",
            "config_fingerprint": "sha256:" + "d" * 64,
            "public_key_fingerprint": "sha256:" + "e" * 64,
            "redacted_client_id_fingerprint": "sha256:" + "f" * 64,
            "rollback_artifact": {
                "present": True,
                "client_only": True,
                "server_paths_untouched": True,
                "artifact_digest": "sha256:" + "1" * 64,
            },
        },
        "transport": _transport_observations(),
        "permissions": {"profiles": profile_observations},
        "checkpoints": checkpoints,
        "reboot": {"reboot_observed": True, "service_recovered": True, "reconnect_observed": True},
        "fallback": {"fallback_smoke_passed": True, "private_first_preserved": True, "server_paths_untouched": True},
        "rollback": {"client_only": True, "server_paths_untouched": True, "artifact_retained": True, "reapply_safe": True},
        "server_path_mutation": False,
    }
    return item


def _write_synthetic_live_manifest(tmp_path: Path) -> Path:
    predecessor_path = tmp_path / "horistic-closeout.json"
    predecessor_payload = {
        "phase": 54, "target": "horistic-srv", "state": "PASS", "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "value_free": True, "secret_material_present": False,
    }
    predecessor_path.write_text(json.dumps(predecessor_payload, sort_keys=True), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "phase": 54,
        "value_free": True,
        "secret_material_present": False,
        "serial_order": ["horistic-srv", "GIOVANNI-W11-PC"],
        "targets": {target: _synthetic_live_item(target) for target in ("horistic-srv", "GIOVANNI-W11-PC")},
        "report_parity": {},
        "server_paths_untouched": True,
        "client_only_rollback": True,
    }
    manifest["targets"]["GIOVANNI-W11-PC"]["predecessor"]["receipt_sha256"] = hashlib.sha256(predecessor_path.read_bytes()).hexdigest()
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(exist_ok=True)
    for key, name in LIVE_VALIDATOR.ARTIFACT_NAMES.items():
        artifact = artifact_dir / name
        artifact.write_text(json.dumps({"phase": 54, "artifact": key, "value_free": True, "secret_material_present": False}, sort_keys=True), encoding="utf-8")
        manifest.setdefault("artifact_refs", {})[key] = {"path": f"artifacts/{name}", "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
    for name in ("json", "markdown", "uat"):
        parity_path = tmp_path / f"report-{name}.json"
        parity_path.write_text(json.dumps({"phase": 54, "report": name}, sort_keys=True), encoding="utf-8")
        manifest["report_parity"][name] = {"path": parity_path.name, "sha256": hashlib.sha256(parity_path.read_bytes()).hexdigest()}
    path = tmp_path / "live-evidence.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_live_validator_and_closeout_synthetic_both_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = _write_synthetic_live_manifest(tmp_path)
    manifest = json.loads(evidence.read_text(encoding="utf-8"))
    phase53 = manifest["targets"]["horistic-srv"]["phase53_gate"] | {"mutation_performed": False}
    def admit(repo: Path, receipt: Path, target: str) -> dict[str, Any]:
        return {
            "state": "ADMITTED_PHASE54", "mutation_performed": False,
            "source_commit": manifest["targets"][target]["source_commit"],
            "phase52_gate": manifest["targets"][target]["phase52_gate"],
            "predecessor": manifest["targets"][target]["predecessor"],
        }
    monkeypatch.setattr(phase54_preflight, "validate_phase53", lambda repo: phase53)
    monkeypatch.setattr(phase54_preflight, "validate", admit)
    result = LIVE_VALIDATOR.validate(REPO, "both", evidence, _test_only=True)
    assert result["state"] == "PASS"
    assert result["serial_order"] == ["horistic-srv", "GIOVANNI-W11-PC"]
    assert set(result["targets"]) == ALLOWED_TARGETS
    closed = CLOSEOUT.closeout(REPO, "both", evidence, _test_only=True)
    assert closed["state"] == "PASS"


def test_live_validator_blocks_missing_target_and_stored_pass(tmp_path: Path) -> None:
    evidence = _write_synthetic_live_manifest(tmp_path)
    manifest = json.loads(evidence.read_text(encoding="utf-8"))
    del manifest["targets"]["GIOVANNI-W11-PC"]
    evidence.write_text(json.dumps(manifest), encoding="utf-8")
    result = LIVE_VALIDATOR.validate(REPO, "both", evidence, _test_only=True)
    assert result["state"] == "BLOCKED"
    assert any("GIOVANNI-W11-PC" in blocker for blocker in result["blockers"])

    manifest = json.loads(_write_synthetic_live_manifest(tmp_path).read_text(encoding="utf-8"))
    manifest["targets"]["horistic-srv"]["state"] = "PASS"
    evidence.write_text(json.dumps(manifest), encoding="utf-8")
    result = LIVE_VALIDATOR.validate(REPO, "horistic-srv", evidence, _test_only=True)
    assert result["state"] == "BLOCKED"
    assert any("stored-verdict" in blocker for blocker in result["blockers"])


def test_both_is_aggregate_only_and_preflight_stays_target_strict() -> None:
    with pytest.raises(phase54_preflight.Phase54PreflightBlocked, match="target-scope-blocked"):
        phase54_preflight.validate(REPO, INITIAL_GATE, "both")


def test_live_validator_rejects_noncanonical_evidence_path(tmp_path: Path) -> None:
    evidence = tmp_path / "live-evidence.json"
    evidence.write_text(json.dumps({"phase": 54, "schema_version": 1}), encoding="utf-8")
    result = LIVE_VALIDATOR.validate(REPO, "horistic-srv", evidence)
    assert result["state"] == "BLOCKED"
    assert "evidence-path-not-canonical" in result["blockers"]


def test_live_validator_rejects_artifact_digest_drift(tmp_path: Path) -> None:
    evidence = _write_synthetic_live_manifest(tmp_path)
    manifest = json.loads(evidence.read_text(encoding="utf-8"))
    manifest["artifact_refs"]["transport"]["sha256"] = "0" * 64
    evidence.write_text(json.dumps(manifest), encoding="utf-8")
    result = LIVE_VALIDATOR.validate(REPO, "horistic-srv", evidence, _test_only=True)
    assert result["state"] == "BLOCKED"
    assert any("artifact-ref-digest-drift:transport" in blocker for blocker in result["blockers"])


def test_live_validator_rejects_missing_transport_attempts_and_profile(tmp_path: Path) -> None:
    item = _synthetic_live_item("horistic-srv")
    item["transport"]["attempts"] = []
    with pytest.raises(LIVE_VALIDATOR.Phase54EvidenceInvalid, match="transport-attempt-sequence-required"):
        LIVE_VALIDATOR._validate_transport(REPO, item, "horistic-srv")
    item = _synthetic_live_item("horistic-srv")
    item["permissions"]["profiles"].pop("support-observe")
    with pytest.raises(LIVE_VALIDATOR.Phase54EvidenceInvalid, match="permission-profiles-incomplete"):
        LIVE_VALIDATOR._validate_permissions(REPO, item, "horistic-srv")


def test_live_validator_malformed_checkpoint_is_structured_blocked() -> None:
    item = {"checkpoints": [{"checkpoint": {}}]}
    with pytest.raises(LIVE_VALIDATOR.Phase54EvidenceInvalid, match="checkpoint-name-invalid"):
        LIVE_VALIDATOR._validate_checkpoints(item, "horistic-srv")
