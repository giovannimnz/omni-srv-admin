from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "modules/rustdesk-fleet/tools/validate_phase51.py"
CONTRACT_PATH = REPO / "modules/rustdesk-fleet/contracts/scope.json"
INVALID_DIR = REPO / "modules/rustdesk-fleet/tests/fixtures/invalid"
PRODUCT_PATH = REPO / "modules/rustdesk-fleet/contracts/product-decision.json"
PERMISSION_PATH = REPO / "modules/rustdesk-fleet/contracts/permission-profiles.json"
THREAT_PATH = REPO / "modules/rustdesk-fleet/contracts/threat-model.json"

SPEC = importlib.util.spec_from_file_location("validate_phase51", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def _statuses(payload: dict) -> dict[str, str]:
    return {result.id: result.status for result in validator.validate_scope(payload)}


def _canonical_scope() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_scope_contract() -> None:
    statuses = _statuses(_canonical_scope())
    assert statuses == {
        "P51-SCOPE-001": "PASS",
        "P51-LEGACY-001": "PASS",
        "P51-TRANSPORT-001": "PASS",
    }


@pytest.mark.parametrize(
    ("fixture", "failed_check"),
    [
        ("excluded-host.json", "P51-SCOPE-001"),
        ("forced-relay-default.json", "P51-TRANSPORT-001"),
    ],
)
def test_scope_transport_static_negatives(fixture: str, failed_check: str) -> None:
    payload = validator.load_json_strict(INVALID_DIR / fixture)
    statuses = _statuses(payload)
    assert statuses[failed_check] == "FAIL"


def test_legacy_missing_tool_fails(tmp_path: Path) -> None:
    payload = _canonical_scope()
    payload["preserved_access_tools"] = payload["preserved_access_tools"][:-1]
    path = tmp_path / "missing-legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    statuses = _statuses(validator.load_json_strict(path))
    assert statuses["P51-LEGACY-001"] == "FAIL"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["included_hosts"].append("srv2"),
        lambda payload: payload["included_hosts"].append("WSL"),
        lambda payload: payload["excluded_hosts"].append("atius-srv-1"),
    ],
)
def test_scope_rejects_alias_overlap_and_extra(mutation) -> None:
    payload = _canonical_scope()
    mutation(payload)
    assert _statuses(payload)["P51-SCOPE-001"] == "FAIL"


def test_scope_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        validator.load_json_strict(path)


def test_scope_rejects_path_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="outside repository"):
        validator.validate_repo_path(repo, outside)


def test_product_decision_contract_starts_blocked() -> None:
    payload = validator.load_json_strict(PRODUCT_PATH)
    derived = validator.derive_product_decision(payload)
    result = validator.validate_product_decision(payload)
    assert derived == {"decision": "BLOCKED", "required_edition": None}
    assert result.id == "P51-PRODUCT-001"
    assert result.status == "BLOCKED"


def test_product_decision_truth_table() -> None:
    payload = validator.load_json_strict(PRODUCT_PATH)

    for control in payload["enterprise_controls"]:
        control.update(mandatory=False, review_status="reviewed", accepted_absence=True)
    payload["declared_decision"] = "GO"
    payload["derived_decision"] = "GO"
    payload["required_edition"] = "oss"
    assert validator.derive_product_decision(payload) == {
        "decision": "GO",
        "required_edition": "oss",
    }
    assert validator.validate_product_decision(payload).status == "PASS"

    payload["enterprise_controls"][0]["mandatory"] = True
    payload["enterprise_controls"][0]["accepted_absence"] = False
    payload["declared_decision"] = "NO-GO"
    payload["derived_decision"] = "NO-GO"
    payload["required_edition"] = "pro"
    assert validator.derive_product_decision(payload) == {
        "decision": "NO-GO",
        "required_edition": "pro",
    }
    assert validator.validate_product_decision(payload).status == "PASS"

    payload["declared_decision"] = "GO"
    payload["required_edition"] = "oss"
    assert validator.validate_product_decision(payload).status == "FAIL"


def test_permission_profiles_contract() -> None:
    payload = validator.load_json_strict(PERMISSION_PATH)
    assert validator.validate_permission_profiles(payload).status == "PASS"
    profiles = {profile["id"]: profile["capabilities"] for profile in payload["profiles"]}
    assert profiles["support-observe"]["screen_view"] == "allow"
    assert set(profiles["support-observe"].values()) == {"allow", "deny"}
    assert sum(value == "allow" for value in profiles["support-observe"].values()) == 1
    for capability in ("file_transfer", "audio", "tcp_tunnel", "privacy_mode", "recording"):
        assert profiles["admin-maintenance"][capability] == "deny"


def test_permission_profiles_reject_support_terminal() -> None:
    payload = validator.load_json_strict(PERMISSION_PATH)
    next(profile for profile in payload["profiles"] if profile["id"] == "support-observe")[
        "capabilities"
    ]["terminal"] = "allow"
    assert validator.validate_permission_profiles(payload).status == "FAIL"


def test_threat_contract_has_complete_stride_and_asvs_mapping() -> None:
    payload = validator.load_json_strict(THREAT_PATH)
    result = validator.validate_threat_model(payload)
    assert result.id == "P51-THREAT-001"
    assert result.status == "PASS"
    assert {item["id"] for item in payload["threats"]} == {f"T-{number:02d}" for number in range(1, 13)}
    assert set(payload["risk_based_l2_subset"]) == {
        "v5.0.0-16.1.1",
        "v5.0.0-16.2.5",
        "v5.0.0-16.3.3",
        "v5.0.0-16.4.2",
        "v5.0.0-16.5.1",
        "v5.0.0-16.5.3",
    }


def test_threat_contract_unresolved_high_is_blocked() -> None:
    payload = validator.load_json_strict(THREAT_PATH)
    payload["threats"][0]["status"] = "open"
    payload["threats"][0]["disposition"] = "pending"
    assert validator.validate_threat_model(payload).status == "BLOCKED"
