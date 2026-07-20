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
