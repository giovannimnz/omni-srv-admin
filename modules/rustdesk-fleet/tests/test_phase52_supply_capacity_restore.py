from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "modules/rustdesk-fleet/tools/validate_phase52.py"
CONTRACT_PATH = REPO / "modules/rustdesk-fleet/contracts/supply-chain.json"
OBSERVATION_PATH = REPO / "modules/rustdesk-fleet/evidence/phase52/supply-observation.json"
MUTATIONS_PATH = REPO / "modules/rustdesk-fleet/tests/fixtures/invalid/phase52-supply-mutations.json"
CAPACITY_POLICY_PATH = REPO / "modules/rustdesk-fleet/contracts/capacity-policy.json"
PLACEMENT_PATH = REPO / "modules/rustdesk-fleet/contracts/placement-decision.json"
CAPACITY_MUTATIONS_PATH = (
    REPO / "modules/rustdesk-fleet/tests/fixtures/invalid/phase52-capacity-placement-mutations.json"
)
CAPACITY_PROPOSAL_PATH = REPO / "modules/rustdesk-fleet/evidence/phase52/capacity-proposal.json"
CAPACITY_SUMMARY_PATH = REPO / "modules/rustdesk-fleet/evidence/phase52/capacity-summary.json"
OPERATIONAL_DECISIONS_PATH = (
    REPO
    / ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-OPERATIONAL-DECISIONS.md"
)
SECRET_ROLES_PATH = REPO / "modules/rustdesk-fleet/contracts/secret-roles.json"
VAULT_HELPER_PATH = REPO / "modules/rustdesk-fleet/tools/rustdesk-vault-hydrate"

SPEC = importlib.util.spec_from_file_location("validate_phase52", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def _contract() -> dict:
    return validator.load_json_strict(CONTRACT_PATH)


def _capacity_policy() -> dict:
    return validator.load_json_strict(CAPACITY_POLICY_PATH)


def _placement() -> dict:
    return validator.load_json_strict(PLACEMENT_PATH)


def _categories(result) -> set[str]:
    return {item.category for item in result.findings}


def _secret_roles() -> dict:
    return validator.load_json_strict(SECRET_ROLES_PATH)


def _write_fake_vault_provider(path: Path, values: dict[str, str]) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "request = json.load(sys.stdin)\n"
        f"values = {values!r}\n"
        "json.dump({'request_count': len(request['references']), 'values': values}, sys.stdout)\n",
        encoding="utf-8",
    )
    path.chmod(0o700)


def _run_vault_helper(
    tmp_path: Path,
    mode: str,
    values: dict[str, str],
    *,
    runtime_dir: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    provider = tmp_path / "fake-vault-provider"
    _write_fake_vault_provider(provider, values)
    read_fd, write_fd = os.pipe()
    env = {
        "PATH": os.environ["PATH"],
        "RUSTDESK_VAULT_PROVIDER": str(provider),
        "RUSTDESK_VAULT_RESULT_FD": str(write_fd),
    }
    command = [
        str(VAULT_HELPER_PATH),
        mode,
        "--contract",
        str(SECRET_ROLES_PATH),
    ]
    if runtime_dir is not None:
        command.extend(["--runtime-dir", str(runtime_dir)])
    completed = subprocess.run(
        command,
        cwd=REPO,
        env=env,
        pass_fds=(write_fd,),
        text=True,
        capture_output=True,
        check=False,
    )
    os.close(write_fd)
    with os.fdopen(read_fd, encoding="utf-8") as handle:
        safe_output = handle.read()
    return completed, json.loads(safe_output) if safe_output else {}


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


def _raw_sample(*, used: int, total: int = 100_000, inode_used: int = 10, observed_at: str | None = None) -> dict:
    return {
        "observed_at": observed_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "hostname": "atius-srv-2",
        "architecture": "aarch64",
        "filesystem_source": "/dev/vda1",
        "mount_point": "/",
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": total - used,
        "inode_total": 100,
        "inode_used": inode_used,
        "inode_available": 100 - inode_used,
        "podman_graphroot": "/home/ubuntu/.local/share/containers/storage",
        "podman_version": "4.9.3",
        "resource_wrapper": "omni srv1-ops resources run builds",
        "resource_profile": "builds",
        "command_version": "phase52-capacity-v1",
        "read_only": True,
        "mutation_performed": False,
    }


def _candidate(host: str, *, evaluated: bool, status: str = "PENDING") -> dict:
    row = {
        "candidate": host,
        "evaluated": evaluated,
        "supply_status": status,
        "capacity_status": status,
        "vault_status": status,
        "backup_status": status,
        "restore_status": status,
        "capacity_finalize_status": status,
        "rollback_status": status,
        "topology_security_status": status,
        "evidence_ids": [f"P52-EV-{host.upper()}"],
        "verdict": "PENDING",
    }
    if host == "horistic-srv":
        row.update(
            {
                "client_colocation": True,
                "server_client_resource_domains": {"server": "horistic-server", "client": "horistic-client"},
                "server_client_evidence_domains": {"server": "ev-server", "client": "ev-client"},
                "server_client_rollback_domains": {"server": "rb-server", "client": "rb-client"},
                "phase53_review_required": True,
                "phase54_review_required": True,
                "phase57_review_required": True,
            }
        )
    return row


def test_capacity_policy_materializes_approved_d04_d05_d06() -> None:
    policy = _capacity_policy()
    assert validator.validate_capacity_policy(policy).status == "PASS"
    assert policy["pre_disk_pct_max"] == 78
    assert policy["post_disk_pct_max"] == policy["inode_pct_max"] == 80
    reservations = policy["reservations"]
    assert reservations["combined_daily_log_budget_bytes"] == 134_217_728
    assert reservations["log_retention_days"] == 30
    assert reservations["log_reserve_30d_bytes"] == 4_026_531_840
    assert reservations["state_growth_budget_bytes"] == 4_294_967_296
    assert reservations["backup_a_bytes"] == reservations["backup_b_bytes"] == 4_294_967_296
    assert policy["backup_a_retention"]["destination"] == "candidate-local"
    assert policy["backup_b_retention"]["destination"] == "modules/fleet-backup:gdrive"
    assert policy["remediation_policy"] == "none"
    assert policy["approval"]["accountable"] == "Giovanni Muniz"
    assert policy["approval"]["approved_at"] == "2026-07-22T00:51:46Z"


@pytest.mark.parametrize(
    ("used", "total", "limit", "expected"),
    [
        (77_999, 100_000, 78, True),
        (78_000, 100_000, 78, True),
        (78_001, 100_000, 78, False),
        (79_999, 100_000, 80, True),
        (80_000, 100_000, 80, True),
        (80_001, 100_000, 80, False),
        (True, 100_000, 80, False),
        (80_000.0, 100_000, 80, False),
        (-1, 100_000, 80, False),
        (1, 0, 80, False),
    ],
)
def test_capacity_integer_boundary(used: object, total: object, limit: object, expected: bool) -> None:
    assert validator.pct_at_most(used, total, limit) is expected


def test_capacity_checked_add_rejects_bool_negative_and_overflow() -> None:
    assert validator.checked_add_bytes(1, 2, 3) == 6
    for values in ((True, 1), (-1, 1), ((2**63) - 1, 1)):
        with pytest.raises(ValueError):
            validator.checked_add_bytes(*values)


@pytest.mark.parametrize(
    ("mutation", "category"),
    [
        (("reservations", "backup_a_bytes", 0), "invalid-reservation"),
        (("reservations", "backup_b_bytes", -1), "invalid-reservation"),
        (("reservations", "state_growth_budget_bytes", True), "invalid-reservation"),
        (("reservations", "log_reserve_30d_bytes", 2**63), "invalid-reservation"),
        (("remediation_policy", None, "cleanup"), "remediation-authority-drift"),
    ],
)
def test_capacity_policy_rejects_invalid_approved_inputs(mutation: tuple, category: str) -> None:
    policy = copy.deepcopy(_capacity_policy())
    parent, child, value = mutation
    if child is None:
        policy[parent] = value
    else:
        policy[parent][child] = value
    result = validator.validate_capacity_policy(policy)
    assert result.status in {"FAIL", "BLOCKED"}
    assert category in _categories(result)


def test_capacity_observation_rejects_stale_mount_mismatch_and_rounded_only() -> None:
    policy = _capacity_policy()
    stale = _raw_sample(
        used=1,
        observed_at=(datetime.now(timezone.utc) - timedelta(seconds=policy["observation_max_age_seconds"] + 1))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    )
    assert "stale-observation" in _categories(validator.validate_capacity_observation(stale, policy))

    rounded = _raw_sample(used=1)
    rounded.pop("used_bytes")
    rounded["disk_percent"] = "1%"
    assert "raw-counter-shape" in _categories(validator.validate_capacity_observation(rounded, policy))

    mismatch = _raw_sample(used=1)
    mismatch["capacity_finalize"] = {
        **_raw_sample(used=2),
        "mount_point": "/different",
        "actual_backup_a_bytes": 1,
        "actual_backup_b_bytes": 1,
        "materialized_reservations": {
            "loaded_image_bytes": 1,
            "preserved_oci_archive_bytes": 1,
            "peak_import_workspace_bytes": 1,
            "backup_a_bytes": 1,
            "backup_b_bytes": 1,
        },
    }
    result = validator.validate_capacity_observation(mismatch, policy)
    assert "finalize-mount-mismatch" in _categories(result)


def test_capacity_derivation_uses_all_reservations_and_inode_boundary() -> None:
    policy = _capacity_policy()
    required = sum(
        policy["reservations"][key]
        for key in (
            "loaded_image_bytes",
            "preserved_oci_archive_bytes",
            "peak_import_workspace_bytes",
            "backup_a_bytes",
            "backup_b_bytes",
            "log_reserve_30d_bytes",
            "state_growth_budget_bytes",
        )
    )
    total = required * 5
    at_boundary = _raw_sample(used=total * 78 // 100, total=total, inode_used=80)
    result = validator.derive_candidate_capacity(at_boundary, policy)
    assert result["required_incremental_bytes"] == required
    assert result["pre_disk_ok"] is True
    assert result["inode_ok"] is True
    assert result["status"] in {"PASS", "NO-GO"}

    above_inode = _raw_sample(used=1, total=total, inode_used=81)
    assert validator.derive_candidate_capacity(above_inode, policy)["inode_ok"] is False


def test_capacity_finalize_reconciles_actuals_and_remaining_reservations() -> None:
    policy = _capacity_policy()
    sample = _raw_sample(used=1, total=100_000_000_000)
    sample["capacity_finalize"] = {
        **_raw_sample(used=2, total=100_000_000_000),
        "actual_backup_a_bytes": policy["reservations"]["backup_a_bytes"],
        "actual_backup_b_bytes": policy["reservations"]["backup_b_bytes"],
        "materialized_reservations": {
            "loaded_image_bytes": policy["reservations"]["loaded_image_bytes"],
            "preserved_oci_archive_bytes": policy["reservations"]["preserved_oci_archive_bytes"],
            "peak_import_workspace_bytes": policy["reservations"]["peak_import_workspace_bytes"],
            "backup_a_bytes": policy["reservations"]["backup_a_bytes"],
            "backup_b_bytes": policy["reservations"]["backup_b_bytes"],
        },
    }
    derived = validator.derive_candidate_capacity(sample, policy)
    assert derived["capacity_finalize_status"] == "PASS"
    assert derived["still_unmaterialized_reservations"] == (
        policy["reservations"]["log_reserve_30d_bytes"]
        + policy["reservations"]["state_growth_budget_bytes"]
    )

    sample["capacity_finalize"]["actual_backup_a_bytes"] += 1
    assert validator.derive_candidate_capacity(sample, policy)["capacity_finalize_status"] == "NO-GO"


def test_placement_derives_strict_serial_chain_and_recomputes_stored_verdict() -> None:
    placement = _placement()
    assert validator.validate_placement_decision(placement).status == "BLOCKED"

    srv2 = _candidate("atius-srv-2", evaluated=True, status="PASS")
    srv2["verdict"] = "PASS"
    selected_srv2 = {**placement, "candidates": [srv2, _candidate("atius-srv-3", evaluated=False), _candidate("horistic-srv", evaluated=False)], "selected_candidate": "atius-srv-2", "overall_status": "PASS"}
    assert validator.derive_placement(selected_srv2)["selected_candidate"] == "atius-srv-2"
    assert validator.validate_placement_decision(selected_srv2).status == "PASS"

    drift = copy.deepcopy(selected_srv2)
    drift["selected_candidate"] = "atius-srv-3"
    result = validator.validate_placement_decision(drift)
    assert result.status == "FAIL"
    assert "stored-verdict-drift" in _categories(result)


def test_placement_rejects_order_bypass_partial_vector_and_windows_evidence() -> None:
    placement = _placement()
    bypass = copy.deepcopy(placement)
    bypass["candidates"][1] = _candidate("atius-srv-3", evaluated=True, status="PASS")
    result = validator.validate_placement_decision(bypass)
    assert result.status in {"FAIL", "BLOCKED"}
    assert "candidate-order-bypass" in _categories(result)

    partial = copy.deepcopy(placement)
    partial["candidates"][0] = _candidate("atius-srv-2", evaluated=True, status="PASS")
    partial["candidates"][0]["vault_status"] = "PENDING"
    assert validator.derive_placement(partial)["selected_candidate"] is None

    windows = copy.deepcopy(placement)
    windows["windows_install_performed"] = True
    windows["windows_access_proven"] = True
    assert "windows-phase-boundary" in _categories(validator.validate_placement_decision(windows))


def test_horistic_selection_requires_two_prior_nogos_and_separate_domains() -> None:
    placement = _placement()
    rows = []
    for host in ("atius-srv-2", "atius-srv-3"):
        row = _candidate(host, evaluated=True, status="NO-GO")
        row["verdict"] = "NO-GO"
        rows.append(row)
    horistic = _candidate("horistic-srv", evaluated=True, status="PASS")
    horistic["verdict"] = "PASS"
    selected = {**placement, "candidates": [*rows, horistic], "selected_candidate": "horistic-srv", "overall_status": "PASS"}
    assert validator.validate_placement_decision(selected).status == "PASS"

    conflated = copy.deepcopy(selected)
    conflated["candidates"][2]["server_client_resource_domains"]["client"] = "horistic-server"
    result = validator.validate_placement_decision(conflated)
    assert result.status == "FAIL"
    assert "horistic-colocation-contract" in _categories(result)


def test_capacity_placement_mutation_catalog_is_complete() -> None:
    catalog = validator.load_json_strict(CAPACITY_MUTATIONS_PATH)
    ids = {item["id"] for item in catalog["mutations"]}
    assert {
        "reservation-omitted",
        "reservation-zero",
        "reservation-negative",
        "reservation-overflow",
        "stale-observation",
        "different-mount",
        "rounded-only",
        "order-bypass",
        "missing-horistic-colocation",
        "missing-horistic-reviews",
    }.issubset(ids)


def test_capacity_accepts_reserved_filesystem_blocks() -> None:
    policy = _capacity_policy()
    sample = _raw_sample(used=10, total=100)
    sample["available_bytes"] = 80
    result = validator.validate_capacity_observation(sample, policy)
    assert "byte-counter-reconciliation" not in _categories(result)


def test_capacity_proposal_binds_exact_accountable_approval_and_two_samples() -> None:
    proposal = validator.load_json_strict(CAPACITY_PROPOSAL_PATH)
    policy = _capacity_policy()
    result = validator.validate_capacity_proposal(proposal, policy, REPO)
    assert result.id == "P52-CAPACITY-001"
    assert result.status == "BLOCKED"
    assert proposal["approval"]["status"] == "approved"
    assert proposal["approval"]["accountable"] == "Giovanni Muniz"
    assert proposal["approval"]["approved_at"] == "2026-07-22T00:51:46Z"
    assert [item["candidate"] for item in proposal["candidates"]] == list(validator.CANDIDATES)
    assert all(len(item["samples"]) == 2 for item in proposal["candidates"])
    assert proposal["mutation_performed"] is False
    assert proposal["remediation_policy"] == "none"
    assert proposal["selected_candidate"] is None


def test_capacity_proposal_rejects_approval_digest_or_stored_verdict_drift() -> None:
    proposal = validator.load_json_strict(CAPACITY_PROPOSAL_PATH)
    policy = _capacity_policy()
    digest_drift = copy.deepcopy(proposal)
    digest_drift["approval"]["source_sha256"] = "0" * 64
    result = validator.validate_capacity_proposal(digest_drift, policy, REPO)
    assert result.status == "BLOCKED"
    assert "approval-source-drift" in _categories(result)

    verdict_drift = copy.deepcopy(proposal)
    verdict_drift["candidates"][0]["capacity_verdict"] = "PASS"
    result = validator.validate_capacity_proposal(verdict_drift, policy, REPO)
    assert result.status in {"FAIL", "BLOCKED"}
    assert "stored-verdict-drift" in _categories(result)


def test_capacity_proposal_cli_is_validation_only() -> None:
    parser = validator.build_parser()
    options = {action.dest for action in parser._actions}
    assert not {"cleanup", "remediate", "admit_candidate", "install"} & options


@pytest.mark.parametrize(
    "action",
    [
        "cleanup",
        "remediation",
        "reclamation",
        "prune",
        "delete",
        "move",
        "compress",
        "vacuum",
        "glob",
        "symlink",
        *validator.BOUNDED_FULL_GATE_WRITES,
    ],
)
@pytest.mark.parametrize("candidate", validator.CANDIDATES)
def test_zero_cleanup_rejects_every_non_read_only_action(candidate: str, action: str) -> None:
    with pytest.raises(ValueError, match="read-only capacity preflight"):
        validator.enforce_zero_cleanup(candidate, action)


def test_zero_cleanup_allows_only_capacity_probe_before_command_construction() -> None:
    assert validator.enforce_zero_cleanup("atius-srv-2", "capacity-sample") is None
    command = validator.build_capacity_probe_command("atius-srv-2")
    assert isinstance(command, list)
    assert command[:2] == ["ssh", "-n"]
    assert "BatchMode=yes" in command
    assert "ConnectTimeout=10" in command
    assert "atius-srv-2-direct" in command
    assert not any(token in command for token in ("rm", "mv", "find", "tar", "gzip", "podman"))


def test_capacity_routing_requires_persisted_predecessor_nogo(tmp_path: Path) -> None:
    policy = _capacity_policy()
    decision_digest = validator._sha256_file(OPERATIONAL_DECISIONS_PATH)
    supply_digest = validator._sha256_file(OBSERVATION_PATH)
    total = 100_000_000_000
    no_go = [_raw_sample(used=79_000_000_000, total=total), _raw_sample(used=79_000_000_000, total=total)]
    eligible = [_raw_sample(used=10_000_000_000, total=total), _raw_sample(used=10_000_000_000, total=total)]
    for sample in no_go + eligible:
        sample["hostname"] = "fixture"

    with pytest.raises(ValueError, match="persisted predecessor NO-GO"):
        validator.evaluate_capacity_chain(
            {"atius-srv-3": no_go},
            policy,
            decision_source_digest=decision_digest,
            supply_digest=supply_digest,
            persisted_predecessors=set(),
        )

    chain = validator.evaluate_capacity_chain(
        {
            "atius-srv-2": no_go,
            "atius-srv-3": no_go,
            "horistic-srv": eligible,
        },
        policy,
        decision_source_digest=decision_digest,
        supply_digest=supply_digest,
        persisted_predecessors={"atius-srv-2", "atius-srv-3"},
    )
    assert chain["attempt_order"] == list(validator.CANDIDATES)
    assert [item["preliminary_verdict"] for item in chain["attempts"]] == [
        "NO-GO",
        "NO-GO",
        "PRELIMINARY_ELIGIBLE",
    ]
    assert chain["capacity_eligible_candidate"] == "horistic-srv"
    assert chain["selected_candidate"] is None
    assert chain["overall_status"] == "BLOCKED"
    assert chain["mutation_performed"] is False


def test_capacity_live_parser_remains_blocked_and_exposes_no_mutation_action() -> None:
    parser = validator.build_parser()
    only = next(action for action in parser._actions if action.dest == "only")
    assert "capacity-live" in only.choices
    assert not {"cleanup", "remediate", "write", "load", "install"} & {
        action.dest for action in parser._actions
    }


def test_capacity_live_evidence_is_serial_current_and_not_placement() -> None:
    chain = validator.load_json_strict(CAPACITY_SUMMARY_PATH)
    placement = _placement()
    result = validator.validate_capacity_live_summary(chain, _capacity_policy(), placement, REPO)
    assert result.id == "P52-CAPACITY-LIVE-001"
    assert result.status == "BLOCKED"
    assert chain["attempt_order"] == list(validator.CANDIDATES)
    assert [item["predecessor_status"] for item in chain["attempts"]] == [
        "NOT_APPLICABLE",
        "NO-GO",
        "NO-GO",
    ]
    assert [item["preliminary_verdict"] for item in chain["attempts"]] == [
        "NO-GO",
        "NO-GO",
        "PRELIMINARY_ELIGIBLE",
    ]
    assert chain["capacity_eligible_candidate"] == "horistic-srv"
    assert chain["selected_candidate"] is None
    assert chain["mutation_performed"] is False
    assert placement["selected_candidate"] is None
    assert [row["capacity_status"] for row in placement["candidates"]] == ["NO-GO", "NO-GO", "PASS"]
    assert all(row["vault_status"] == "PENDING" for row in placement["candidates"])
    horistic = chain["attempts"][2]["horistic_colocation"]
    assert horistic["phase52_review_status"] == "PASS"
    assert horistic["phase53_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    assert horistic["phase54_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    assert horistic["phase57_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    assert horistic["independent_dr_claimed"] is False


def test_vault_metadata_accepts_only_the_six_approved_references() -> None:
    payload = _secret_roles()
    result = validator.validate_vault_metadata(payload)
    assert result.id == "P52-VAULT-001"
    assert result.status == "PASS"
    refs = validator.approved_vault_references(payload)
    assert refs == [
        ("kv/atius/rustdesk/server", "private_key"),
        ("kv/atius/rustdesk/server", "public_key"),
        ("kv/atius/rustdesk/targets/atius-srv-1", "permanent_password"),
        ("kv/atius/rustdesk/targets/atius-srv-2", "permanent_password"),
        ("kv/atius/rustdesk/targets/atius-srv-3", "permanent_password"),
        ("kv/atius/rustdesk/targets/horistic-srv", "permanent_password"),
        ("kv/atius/rustdesk/targets/giovanni-w11-pc", "permanent_password"),
    ]

    unknown = copy.deepcopy(payload)
    unknown["target_password_roles"][0]["vault_path"] = "kv/atius/rustdesk/targets/unknown"
    blocked = validator.validate_vault_metadata(unknown)
    assert blocked.status == "BLOCKED"
    assert "unknown-vault-reference" in _categories(blocked)


def test_vault_helper_hydrates_tmpfs_without_disclosure(tmp_path: Path) -> None:
    sentinel_private = f"private-{secrets.token_urlsafe(32)}"
    sentinel_public = f"public-{secrets.token_urlsafe(32)}"
    passwords = [f"password-{secrets.token_urlsafe(24)}" for _ in range(5)]
    values = {
        "kv/atius/rustdesk/server#private_key": sentinel_private,
        "kv/atius/rustdesk/server#public_key": sentinel_public,
        **{
            f"kv/atius/rustdesk/targets/{host}#permanent_password": password
            for host, password in zip(
                ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv", "giovanni-w11-pc"),
                passwords,
                strict=True,
            )
        },
    }
    runtime_dir = Path("/dev/shm") / f"rustdesk-vault-test-{secrets.token_hex(8)}"
    completed, result = _run_vault_helper(
        tmp_path, "hydrate-server-identity", values, runtime_dir=runtime_dir
    )
    try:
        assert completed.returncode == 0
        assert completed.stdout == completed.stderr == ""
        assert result["status"] == "PASS"
        assert result["secret_material_present"] is False
        assert result["runtime_tmpfs"] is True
        assert result["runtime_mode"] == "0700"
        assert result["file_modes"] == {"id_ed25519": "0600", "id_ed25519.pub": "0600"}
        assert result["public_key_fingerprint"].startswith("sha256:")
        assert runtime_dir.stat().st_mode & 0o777 == 0o700
        assert (runtime_dir / "id_ed25519").read_text(encoding="utf-8") == sentinel_private
        assert (runtime_dir / "id_ed25519.pub").read_text(encoding="utf-8") == sentinel_public
        combined = completed.stdout + completed.stderr + json.dumps(result, sort_keys=True)
        assert all(secret not in combined for secret in [sentinel_private, sentinel_public, *passwords])
        assert all(secret not in " ".join(completed.args) for secret in values.values())
    finally:
        subprocess.run(
            [str(VAULT_HELPER_PATH), "cleanup", "--runtime-dir", str(runtime_dir)],
            cwd=REPO,
            env={"PATH": os.environ["PATH"]},
            text=True,
            capture_output=True,
            check=False,
        )
    assert not runtime_dir.exists()


def test_secret_password_distinctness_is_aggregate_and_non_reusable(tmp_path: Path) -> None:
    passwords = [f"password-{secrets.token_urlsafe(24)}" for _ in range(5)]
    values = {
        "kv/atius/rustdesk/server#private_key": f"private-{secrets.token_urlsafe(24)}",
        "kv/atius/rustdesk/server#public_key": f"public-{secrets.token_urlsafe(24)}",
        **{
            f"kv/atius/rustdesk/targets/{host}#permanent_password": password
            for host, password in zip(
                ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv", "giovanni-w11-pc"),
                passwords,
                strict=True,
            )
        },
    }
    first, first_result = _run_vault_helper(tmp_path, "verify-password-distinctness", values)
    second, second_result = _run_vault_helper(tmp_path, "verify-password-distinctness", values)
    assert first.returncode == second.returncode == 0
    assert first.stdout == first.stderr == second.stdout == second.stderr == ""
    assert first_result == second_result == {
        "count": 5,
        "secret_material_present": False,
        "status": "PASS",
        "unique": 5,
    }
    serialized = json.dumps(first_result, sort_keys=True) + json.dumps(second_result, sort_keys=True)
    assert all(password not in serialized for password in passwords)
    assert "hmac" not in serialized.lower()

    duplicate_values = dict(values)
    duplicate_values["kv/atius/rustdesk/targets/giovanni-w11-pc#permanent_password"] = passwords[0]
    duplicate, duplicate_result = _run_vault_helper(
        tmp_path, "verify-password-distinctness", duplicate_values
    )
    assert duplicate.returncode == 2
    assert duplicate_result == {
        "count": 5,
        "secret_material_present": False,
        "status": "BLOCKED",
        "unique": 4,
    }


def test_vault_runtime_and_cleanup_fail_closed_off_tmpfs(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "rustdesk-not-tmpfs"
    runtime_dir.mkdir(mode=0o700)
    (runtime_dir / "id_ed25519").write_text("synthetic-private", encoding="utf-8")
    (runtime_dir / "id_ed25519.pub").write_text("synthetic-public", encoding="utf-8")
    (runtime_dir / "id_ed25519").chmod(0o600)
    (runtime_dir / "id_ed25519.pub").chmod(0o600)
    result = validator.validate_hydration_runtime(runtime_dir)
    assert result["status"] == "BLOCKED"
    assert result["runtime_tmpfs"] is False

    completed = subprocess.run(
        [str(VAULT_HELPER_PATH), "cleanup", "--runtime-dir", str(runtime_dir)],
        cwd=REPO,
        env={"PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == completed.stderr == ""
    assert runtime_dir.exists()
