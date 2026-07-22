from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "modules/rustdesk-fleet/tools/validate_phase52.py"
CONTRACT_PATH = REPO / "modules/rustdesk-fleet/contracts/supply-chain.json"
OBSERVATION_PATH = REPO / "modules/rustdesk-fleet/evidence/phase52/supply-observation.json"
MUTATIONS_PATH = REPO / "modules/rustdesk-fleet/tests/fixtures/invalid/phase52-supply-mutations.json"

SPEC = importlib.util.spec_from_file_location("validate_phase52", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def _contract() -> dict:
    return validator.load_json_strict(CONTRACT_PATH)


def _categories(result) -> set[str]:
    return {item.category for item in result.findings}


def test_supply_contract_exact_pins() -> None:
    payload = _contract()
    result = validator.validate_supply_contract(payload)
    assert result.id == "P52-SUPPLY-001"
    assert result.status == "PASS"
    assert payload["server"]["version"] == payload["server"]["tag"] == "1.1.15"
    assert payload["server"]["commit"] == "9bae9f2f39d92c4b4ba2e28e089da5071897b22e"
    assert payload["server"]["classic_image"]["multiarch_digest"] == (
        "sha256:10818ec05b179039c6660f4d8e74b303f0db2858bbad2b18e24992ea22d54cd6"
    )
    assert payload["server"]["classic_image"]["linux_arm64_digest"] == (
        "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
    )
    assert payload["server"]["release_zip"]["sha256"] == (
        "4998dd6d32431f9aaf5841663339793bc154d7152313e128832d6b610580abe4"
    )
    assert payload["clients"]["version"] == payload["clients"]["tag"] == "1.4.9"
    assert payload["clients"]["commit"] == "6c578292e8ebbbec708b76986ba8c4bc7c509747"
    assert payload["clients"]["linux_arm64_deb"]["sha256"] == (
        "ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0"
    )
    assert payload["clients"]["windows_x86_64_msi"]["sha256"] == (
        "c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa"
    )


def test_supply_contract_represents_d01_d02_without_admission() -> None:
    payload = _contract()
    candidates = payload["server"]["candidates"]
    assert [item["host"] for item in candidates] == [
        "atius-srv-2",
        "atius-srv-3",
        "horistic-srv",
    ]
    assert all(item["selected"] is False for item in candidates)
    assert all(item["linux_arm64_digest"] == payload["server"]["classic_image"]["linux_arm64_digest"] for item in candidates)
    horistic = candidates[-1]
    assert horistic["client_colocation_if_selected"] is True
    assert horistic["server_identity_domain"] != horistic["future_client_identity_domain"]
    assert payload["policy"]["candidate_admission_performed"] is False


@pytest.mark.parametrize(
    ("path", "value", "category"),
    [
        (("server", "tag"), "latest", "mutable-reference"),
        (("server", "commit"), "0" * 40, "server-commit-drift"),
        (("server", "classic_image", "multiarch_digest"), "sha256:" + "0" * 64, "multiarch-digest-drift"),
        (("server", "classic_image", "linux_arm64_digest"), "sha256:" + "1" * 64, "arm64-digest-drift"),
        (("server", "release_zip", "sha256"), "2" * 64, "release-zip-checksum-drift"),
        (("clients", "linux_arm64_deb", "sha256"), "3" * 64, "linux-deb-checksum-drift"),
        (("clients", "windows_x86_64_msi", "sha256"), "4" * 64, "windows-msi-checksum-drift"),
        (("server", "classic_image", "architecture"), "amd64", "server-architecture-drift"),
        (("clients", "linux_arm64_deb", "architecture"), "amd64", "linux-client-architecture-drift"),
        (("policy", "automatic_pin_refresh"), True, "automatic-pin-refresh"),
        (("policy", "build_on_target"), True, "target-build-enabled"),
    ],
)
def test_supply_rejects_mutation(path: tuple[str, ...], value: object, category: str) -> None:
    payload = copy.deepcopy(_contract())
    target = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    result = validator.validate_supply_contract(payload)
    assert result.status == "FAIL"
    assert category in _categories(result)


def test_supply_contract_rejects_missing_extra_key_and_bool_as_int() -> None:
    missing = copy.deepcopy(_contract())
    missing["server"].pop("commit")
    assert "contract-shape" in _categories(validator.validate_supply_contract(missing))

    extra = copy.deepcopy(_contract())
    extra["unexpected"] = True
    assert "contract-shape" in _categories(validator.validate_supply_contract(extra))

    bool_size = copy.deepcopy(_contract())
    bool_size["server"]["release_zip"]["size_bytes"] = True
    assert "invalid-byte-size" in _categories(validator.validate_supply_contract(bool_size))


def test_supply_contract_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        validator.load_json_strict(path)


@pytest.mark.parametrize(
    ("artifact_path", "expected_architecture", "expected_checksum"),
    [
        (("server", "release_zip"), "linux-arm64v8", "4998dd6d32431f9aaf5841663339793bc154d7152313e128832d6b610580abe4"),
        (("clients", "linux_arm64_deb"), "arm64", "ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0"),
        (("clients", "windows_x86_64_msi"), "x86_64", "c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa"),
    ],
)
def test_supply_architecture_and_checksum_matrix(
    artifact_path: tuple[str, ...], expected_architecture: str, expected_checksum: str
) -> None:
    payload = _contract()
    artifact = payload
    for part in artifact_path:
        artifact = artifact[part]
    assert artifact["architecture"] == expected_architecture
    assert artifact["sha256"] == expected_checksum


def test_windows_msi_is_stage_only() -> None:
    payload = _contract()
    msi = payload["clients"]["windows_x86_64_msi"]
    assert msi["install_phase"] == 54
    assert msi["phase52_action"] == "verify-and-stage"
    assert payload["policy"]["windows_install_performed"] is False
    assert validator.validate_supply_contract(payload).status == "PASS"


def test_supply_status_precedence_and_exit_codes() -> None:
    passed = validator.CheckResult("A", "PASS")
    blocked = validator.CheckResult("B", "BLOCKED")
    failed = validator.CheckResult("C", "FAIL")
    assert validator.derive_overall_status([passed]) == "PASS"
    assert validator.derive_overall_status([passed, blocked]) == "BLOCKED"
    assert validator.derive_overall_status([blocked, failed]) == "FAIL"
    assert validator.exit_code_for_status("PASS") == 0
    assert validator.exit_code_for_status("FAIL") == 1
    assert validator.exit_code_for_status("BLOCKED") == 2


def test_supply_observation_matches_contract() -> None:
    contract = _contract()
    observation = validator.load_json_strict(OBSERVATION_PATH)
    result = validator.validate_supply_observation(observation, contract, repo=REPO)
    assert result.id == "P52-SUPPLY-001"
    assert result.status == "PASS"
    assert observation["status"] == "PASS"
    assert observation["windows_install_performed"] is False
    assert observation["secret_material_present"] is False
    assert observation["candidate_admission_performed"] is False
    assert observation["server"]["commit"] == contract["server"]["commit"]
    assert observation["clients"]["commit"] == contract["clients"]["commit"]
    assert observation["classic_image"]["multiarch_digest"] == contract["server"]["classic_image"]["multiarch_digest"]
    assert observation["classic_image"]["linux_arm64_digest"] == contract["server"]["classic_image"]["linux_arm64_digest"]


def test_supply_observation_is_derived_not_trusted() -> None:
    contract = _contract()
    observation = validator.load_json_strict(OBSERVATION_PATH)
    observation["status"] = "FAIL"
    result = validator.validate_supply_observation(observation, contract, repo=REPO)
    assert result.status == "FAIL"
    assert "stored-verdict-drift" in _categories(result)


def test_supply_observation_rejects_stale_timestamp() -> None:
    contract = _contract()
    observation = validator.load_json_strict(OBSERVATION_PATH)
    observation["observed_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=contract["policy"]["observation_ttl_seconds"] + 1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = validator.validate_supply_observation(observation, contract, repo=REPO)
    assert result.status == "BLOCKED"
    assert "stale-observation" in _categories(result)


def test_supply_observation_rejects_missing_cached_asset(tmp_path: Path) -> None:
    contract = _contract()
    observation = validator.load_json_strict(OBSERVATION_PATH)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    for artifact in observation["artifacts"]:
        source = Path(artifact["cache_path"])
        target = cache_root / source.name
        shutil.copy2(source, target)
        artifact["cache_path"] = str(target)
    Path(observation["artifacts"][0]["cache_path"]).unlink()
    result = validator.validate_supply_observation(
        observation, contract, repo=REPO, allowed_cache_root=cache_root
    )
    assert result.status == "BLOCKED"
    assert "cached-asset-missing" in _categories(result)


def _apply_catalog_mutation(payload: dict, mutation: dict) -> None:
    target = payload
    path = mutation["path"]
    for part in path[:-1]:
        target = target[part]
    if mutation["operation"] == "delete":
        del target[path[-1]]
    else:
        target[path[-1]] = mutation["value"]


def test_supply_mutation_catalog_exercises_every_negative() -> None:
    catalog = validator.load_json_strict(MUTATIONS_PATH)
    ids = [item["id"] for item in catalog["mutations"]]
    assert len(ids) == len(set(ids)) >= 11
    assert {
        "mutable-reference",
        "changed-server-commit",
        "wrong-multiarch-digest",
        "wrong-arm64-child-digest",
        "wrong-server-zip-checksum",
        "wrong-linux-deb-checksum",
        "wrong-windows-msi-checksum",
        "wrong-server-architecture",
        "wrong-client-architecture",
        "missing-official-asset",
        "phase52-windows-install-attempt",
    }.issubset(ids)
    for mutation in catalog["mutations"]:
        payload = copy.deepcopy(_contract())
        _apply_catalog_mutation(payload, mutation)
        result = validator.validate_supply_contract(payload)
        assert result.status in {"FAIL", "BLOCKED"}, mutation["id"]
        assert mutation["expected_category"] in _categories(result), mutation["id"]


def test_supply_quarantines_unexpected_bytes(tmp_path: Path) -> None:
    destination = tmp_path / "artifact.bin"
    destination.write_bytes(b"unexpected")
    quarantine = validator.verify_or_quarantine_file(destination, "0" * 64)
    assert quarantine is not None
    assert quarantine.parent == tmp_path / "quarantine"
    assert not destination.exists()
    assert quarantine.read_bytes() == b"unexpected"


def test_supply_cli_exposes_no_install_or_pin_refresh() -> None:
    options = {action.dest for action in validator.build_parser()._actions}
    assert not {"install", "update_pins", "admit_candidate"} & options
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    assert "podman build" not in source
    assert "docker build" not in source
    assert "msiexec" not in source
