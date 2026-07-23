from __future__ import annotations

import copy
import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
import secrets
import signal
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import time
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
FULL_GATE_SUMMARY_PATH = REPO / "modules/rustdesk-fleet/evidence/phase52/full-gate-summary.json"
INTEGRATED_GATE_PATH = REPO / "modules/rustdesk-fleet/evidence/phase52/integrated-gate.json"
LEDGER_PATH = REPO / "modules/rustdesk-fleet/evidence/ledger.json"
PHASE52_DIR = (
    REPO
    / ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement"
)
PHASE52_REPORT_JSON_PATH = PHASE52_DIR / "52-GATE-REPORT.json"
PHASE52_REPORT_MD_PATH = PHASE52_DIR / "52-GATE-REPORT.md"
PHASE53_TOPOLOGY_REVIEW_PATH = PHASE52_DIR / "52-PHASE53-TOPOLOGY-REVIEW.md"
OPERATIONAL_DECISIONS_PATH = (
    REPO
    / ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-OPERATIONAL-DECISIONS.md"
)
SECRET_ROLES_PATH = REPO / "modules/rustdesk-fleet/contracts/secret-roles.json"
VAULT_HELPER_PATH = REPO / "modules/rustdesk-fleet/tools/rustdesk-vault-hydrate"
VAULT_PROVIDER_PATH = REPO / "modules/rustdesk-fleet/tools/rustdesk-vault-provider"
VAULT_PROVIDER_INSTALLER_PATH = (
    REPO / "modules/rustdesk-fleet/tools/install-rustdesk-vault-provider.sh"
)
VAULT_CONTROL_CONTRACT_PATH = (
    REPO / "modules/rustdesk-fleet/contracts/phase52-vault-control-plane.json"
)
VAULT_CONTROL_BACKEND_PATH = (
    REPO / "modules/rustdesk-fleet/tools/atius-vault-export-rustdesk-phase52"
)
VAULT_CONTROL_DISPATCHER_PATH = (
    REPO / "modules/rustdesk-fleet/tools/atius-vault-export-ssh-phase52"
)
VAULT_CONTROL_WRITER_PATH = (
    REPO / "modules/rustdesk-fleet/tools/atius-vault-phase52-write"
)
VAULT_CONTROL_INSTALLER_PATH = (
    REPO / "modules/rustdesk-fleet/tools/install-phase52-vault-control-plane.sh"
)
LIVE_DRILL_PATH = REPO / "modules/rustdesk-fleet/tools/phase52-horistic-live-drill.py"
LIVE_DRILL_CONTRACT_PATH = (
    REPO / "modules/rustdesk-fleet/contracts/phase52-live-drill-contract.json"
)
RECOVERY_PATH = REPO / "modules/rustdesk-fleet/tools/phase52_recovery.py"
VAULT_CLIENT_PATH = REPO / "modules/rustdesk-fleet/tools/atius-vault-phase52-client"
VAULT_RESTORE_MUTATIONS_PATH = (
    REPO / "modules/rustdesk-fleet/tests/fixtures/invalid/phase52-vault-restore-mutations.json"
)

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


def test_post_live_successor_boundary_is_non_authorizing() -> None:
    result = validator.validate_post_live_successor_boundary(REPO)
    assert result.status == "PASS"
    assert validator.PHASE52_POST_LIVE_SUCCESSOR_V1 == "phase52_post_live_successor_v1"


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


def _approved_values() -> dict[str, str]:
    return {
        "kv/atius/rustdesk/server#private_key": "fixture-private-value",
        "kv/atius/rustdesk/server#public_key": "fixture-public-value",
        **{
            f"kv/atius/rustdesk/targets/{host}#permanent_password": f"fixture-password-{index}"
            for index, host in enumerate(
                ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv", "giovanni-w11-pc"),
                start=1,
            )
        },
    }


def _write_fake_exact_vault_backend(path: Path, values: dict[str, str]) -> None:
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


def _create_sqlite_source(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True)
    database = path / "db_v2.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE peers (id TEXT PRIMARY KEY, note TEXT NOT NULL)")
        connection.execute("INSERT INTO peers VALUES (?, ?)", ("fixture-peer", "non-secret-state"))
    database.chmod(0o600)
    return database


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
    result = validator.validate_supply_observation(
        observation,
        contract,
        repo=REPO,
        now=datetime(2026, 7, 22, 3, 30, tzinfo=timezone.utc),
    )
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
    result = validator.validate_supply_observation(
        observation,
        contract,
        repo=REPO,
        now=datetime(2026, 7, 22, 3, 30, tzinfo=timezone.utc),
    )
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
    assert validator.validate_placement_decision(placement).status == "PASS"
    assert placement["selected_candidate"] == "horistic-srv"

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
    assert placement["selected_candidate"] == "horistic-srv"
    assert [row["capacity_status"] for row in placement["candidates"]] == ["NO-GO", "NO-GO", "PASS"]
    assert [row["vault_status"] for row in placement["candidates"]] == [
        "SKIPPED_DUE_TO_GATE",
        "SKIPPED_DUE_TO_GATE",
        "PASS",
    ]
    assert validator.load_json_strict(FULL_GATE_SUMMARY_PATH)["overall_status"] == "PASS"
    horistic = chain["attempts"][2]["horistic_colocation"]
    assert horistic["phase52_review_status"] == "PASS"
    assert horistic["phase53_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    assert horistic["phase54_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    assert horistic["phase57_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    assert horistic["independent_dr_claimed"] is False


def test_capacity_live_stale_boundary_is_blocked_while_tamper_remains_fail() -> None:
    chain = validator.load_json_strict(CAPACITY_SUMMARY_PATH)
    policy = _capacity_policy()
    placement = _placement()
    earliest_observation = min(
        datetime.fromisoformat(sample["observed_at"].replace("Z", "+00:00"))
        for attempt in chain["attempts"]
        for sample in attempt["samples"]
    )
    boundary = earliest_observation + timedelta(seconds=policy["observation_max_age_seconds"])

    current = validator.validate_capacity_live_summary(chain, policy, placement, REPO, now=boundary)
    assert current.status == "BLOCKED"
    assert "stale-observation" not in _categories(current)

    expired_at = boundary + timedelta(seconds=1)
    expired = validator.validate_capacity_live_summary(chain, policy, placement, REPO, now=expired_at)
    assert expired.status == "BLOCKED"
    assert "stale-observation" in _categories(expired)
    assert "stored-verdict-drift" not in _categories(expired)

    tampered = copy.deepcopy(chain)
    tampered["attempts"][2]["calculations"][0]["headroom_ok"] = False
    tampered_result = validator.validate_capacity_live_summary(tampered, policy, placement, REPO, now=expired_at)
    assert tampered_result.status == "FAIL"
    assert "stored-verdict-drift" in _categories(tampered_result)


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


def test_full_gate_readiness_is_remote_home_aware(tmp_path: Path) -> None:
    remote_home = tmp_path / "home" / "horistic"
    remote_home.mkdir(parents=True)
    completed = subprocess.run(
        [sys.executable, "-c", validator.REMOTE_FULL_GATE_READINESS_SCRIPT],
        env={"HOME": str(remote_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["home"] == str(remote_home)
    assert payload["paths"]["vault_helper"]["exists"] is False
    assert payload["paths"]["rustdesk_vault_provider"]["exists"] is False
    assert "/home/ubuntu" not in validator.REMOTE_FULL_GATE_READINESS_SCRIPT
    assert payload["vault_provider"] == {
        "status": "BLOCKED",
        "blocker": "rustdesk-vault-provider-missing",
        "secret_material_present": False,
    }


def test_versioned_vault_provider_rejects_non_exact_references_without_backend_call(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "backend-called"
    backend = tmp_path / "backend"
    backend.write_text(
        "#!/bin/sh\n"
        f"touch {marker}\n"
        "exit 99\n",
        encoding="utf-8",
    )
    backend.chmod(0o700)
    request = {
        "references": [
            {"vault_path": path, "field": field}
            for path, field in validator.APPROVED_VAULT_REFERENCES
        ]
    }
    request["references"].append(
        {"vault_path": "kv/atius/rustdesk/targets/not-approved", "field": "permanent_password"}
    )
    completed = subprocess.run(
        [str(VAULT_PROVIDER_PATH)],
        input=json.dumps(request),
        env={
            "HOME": str(tmp_path),
            "PATH": os.environ["PATH"],
            "ATIUS_RUSTDESK_VAULT_BACKEND": str(backend),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == completed.stderr == ""
    assert not marker.exists()


def test_versioned_vault_provider_exact_protocol_and_safe_self_check(tmp_path: Path) -> None:
    values = _approved_values()
    backend = tmp_path / "atius-rustdesk-vault-export"
    _write_fake_exact_vault_backend(backend, values)
    request = {
        "references": [
            {"vault_path": path, "field": field}
            for path, field in validator.APPROVED_VAULT_REFERENCES
        ]
    }
    env = {
        "HOME": str(tmp_path),
        "PATH": os.environ["PATH"],
        "ATIUS_RUSTDESK_VAULT_BACKEND": str(backend),
    }
    completed = subprocess.run(
        [str(VAULT_PROVIDER_PATH)],
        input=json.dumps(request),
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {"request_count": 7, "values": values}

    checked = subprocess.run(
        [str(VAULT_PROVIDER_PATH), "--self-check"],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert checked.stderr == ""
    safe_result = json.loads(checked.stdout)
    assert safe_result == {
        "status": "PASS",
        "blocker": "none",
        "reference_count": 7,
        "secret_material_present": False,
    }
    assert all(value not in checked.stdout for value in values.values())


def test_versioned_vault_provider_and_installer_fail_closed_without_backend(tmp_path: Path) -> None:
    target_home = tmp_path / "home" / "horistic"
    target_bin = target_home / ".local" / "bin"
    target_bin.mkdir(parents=True)
    existing = target_bin / "rustdesk-vault-provider"
    existing.write_text("previous-provider\n", encoding="utf-8")
    existing.chmod(0o755)

    installed = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(target_home)],
        env={"HOME": str(target_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(installed.stdout)["status"] == "PASS"
    assert existing.stat().st_mode & 0o777 == 0o700
    assert (target_bin / "atius-vault-phase52-client").stat().st_mode & 0o777 == 0o700
    state_dir = target_home / ".local/state/atius-rustdesk-vault-provider"
    assert (state_dir / "install-state").stat().st_mode & 0o777 == 0o600
    assert (state_dir / "provider.pre-phase52").stat().st_mode & 0o777 == 0o600

    blocked = subprocess.run(
        [str(existing), "--self-check"],
        env={"HOME": str(target_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=False,
    )
    assert blocked.returncode == 2
    assert blocked.stderr == ""
    assert json.loads(blocked.stdout)["blocker"] == "rustdesk-vault-backend-failed"

    rolled_back = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--rollback", "--home", str(target_home)],
        env={"HOME": str(target_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(rolled_back.stdout)["status"] == "PASS"
    assert existing.read_text(encoding="utf-8") == "previous-provider\n"
    assert existing.stat().st_mode & 0o777 == 0o755
    assert not (target_bin / "atius-vault-phase52-client").exists()
    assert not (state_dir / "install-state").exists()
    assert not (state_dir / "provider.pre-phase52").exists()


def test_vault_provider_bounds_pathological_input_and_backend_output(tmp_path: Path) -> None:
    base_env = {"HOME": str(tmp_path), "PATH": os.environ["PATH"]}
    pathological_requests = (
        b"{" + (b" " * (16 * 1024)) + b"}",
        b"\xff\xfe\xfd",
        (b"[" * 2_000) + b"0" + (b"]" * 2_000),
    )
    for payload in pathological_requests:
        completed = subprocess.run(
            [str(VAULT_PROVIDER_PATH)],
            input=payload,
            env=base_env,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 2
        assert completed.stdout == completed.stderr == b""

    backend = tmp_path / "oversized-backend"
    backend.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdin.buffer.read()\n"
        "sys.stdout.buffer.write(b'x' * (64 * 1024 + 1))\n",
        encoding="utf-8",
    )
    backend.chmod(0o700)
    checked = subprocess.run(
        [str(VAULT_PROVIDER_PATH), "--self-check"],
        env={**base_env, "ATIUS_RUSTDESK_VAULT_BACKEND": str(backend)},
        capture_output=True,
        check=False,
    )
    assert checked.returncode == 2
    assert checked.stderr == b""
    assert json.loads(checked.stdout)["blocker"] == "rustdesk-vault-backend-output-too-large"


def test_vault_provider_rejects_invalid_backend_unicode_without_traceback(tmp_path: Path) -> None:
    backend = tmp_path / "invalid-unicode-backend"
    backend.write_bytes(b"#!/bin/sh\nprintf '\\377\\376\\375'\n")
    backend.chmod(0o700)
    completed = subprocess.run(
        [str(VAULT_PROVIDER_PATH), "--self-check"],
        env={
            "HOME": str(tmp_path),
            "PATH": os.environ["PATH"],
            "ATIUS_RUSTDESK_VAULT_BACKEND": str(backend),
        },
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stderr == b""
    assert json.loads(completed.stdout)["status"] == "BLOCKED"


def test_vault_provider_installer_rejects_symlink_parent_and_drift(tmp_path: Path) -> None:
    symlink_home = tmp_path / "symlink-home"
    symlink_home.mkdir()
    escaped = tmp_path / "escaped"
    escaped.mkdir()
    (symlink_home / ".local").symlink_to(escaped, target_is_directory=True)
    rejected = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(symlink_home)],
        env={"HOME": str(symlink_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode == 2
    assert not any(escaped.iterdir())

    owner_home = tmp_path / "owner-home"
    owner_home.mkdir()
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_id = fake_bin / "id"
    fake_id.write_text("#!/bin/sh\necho 424242\n", encoding="utf-8")
    fake_id.chmod(0o700)
    owner_rejected = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(owner_home)],
        env={"HOME": str(owner_home), "PATH": f"{fake_bin}:/usr/bin:/bin"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert owner_rejected.returncode == 2
    assert "target home owner mismatch" in owner_rejected.stderr

    target_home = tmp_path / "drift-home"
    target_home.mkdir()
    installed = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(target_home)],
        env={"HOME": str(target_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(installed.stdout)["status"] == "PASS"
    target = target_home / ".local/bin/rustdesk-vault-provider"
    target.write_text("drifted-provider\n", encoding="utf-8")
    target.chmod(0o700)
    rollback = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--rollback", "--home", str(target_home)],
        env={"HOME": str(target_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=False,
    )
    assert rollback.returncode == 2
    assert "installed provider drift" in rollback.stderr
    assert (target_home / ".local/state/atius-rustdesk-vault-provider/install-state").is_file()


def test_vault_provider_installer_dry_run_is_zero_write_and_modes_fail_closed(
    tmp_path: Path,
) -> None:
    dry_home = tmp_path / "dry-home"
    dry_home.mkdir()
    before = list(dry_home.rglob("*"))
    completed = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--dry-run", "--home", str(dry_home)],
        env={"HOME": str(dry_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(completed.stdout)["dry_run"] is True
    assert list(dry_home.rglob("*")) == before == []

    writable_home = tmp_path / "writable-home"
    writable_home.mkdir(mode=0o775)
    writable_home.chmod(0o775)
    rejected = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(writable_home)],
        env={"HOME": str(writable_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode == 2
    assert "group/world writable" in rejected.stderr
    assert list(writable_home.rglob("*")) == []

    state_mode_home = tmp_path / "state-mode-home"
    (state_mode_home / ".local/state").mkdir(parents=True, mode=0o755)
    (state_mode_home / ".local/state").chmod(0o755)
    rejected_state = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(state_mode_home)],
        env={"HOME": str(state_mode_home), "PATH": os.environ["PATH"]},
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected_state.returncode == 2
    assert "state directory mode drift" in rejected_state.stderr


def test_vault_provider_installer_recovers_interrupted_install_and_rollback(
    tmp_path: Path,
) -> None:
    stage_home = tmp_path / "stage-crash-home"
    stage_home.mkdir()
    stage_env = {"HOME": str(stage_home), "PATH": os.environ["PATH"]}
    interrupted_stage = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(stage_home)],
        env={**stage_env, "ATIUS_RUSTDESK_INSTALLER_TEST_INTERRUPT_AFTER": "stage"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert interrupted_stage.returncode == 75
    stage_state = stage_home / ".local/state/atius-rustdesk-vault-provider"
    assert (stage_state / "provider.transaction").is_file()
    assert not (stage_state / "transaction-journal").exists()
    completed_after_stage = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(stage_home)],
        env=stage_env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(completed_after_stage.stdout)["status"] == "PASS"
    assert not (stage_state / "provider.transaction").exists()

    target_home = tmp_path / "crash-home"
    target = target_home / ".local/bin/rustdesk-vault-provider"
    target.parent.mkdir(parents=True)
    target.write_text("baseline-provider\n", encoding="utf-8")
    target.chmod(0o755)
    env = {"HOME": str(target_home), "PATH": os.environ["PATH"]}

    interrupted_install = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(target_home)],
        env={**env, "ATIUS_RUSTDESK_INSTALLER_TEST_INTERRUPT_AFTER": "journal"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert interrupted_install.returncode == 75
    state_dir = target_home / ".local/state/atius-rustdesk-vault-provider"
    assert (state_dir / "transaction-journal").is_file()
    assert (state_dir / "provider.transaction").is_file()

    recovered_install = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(target_home)],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(recovered_install.stdout)["recovered"] is True
    assert (state_dir / "install-state").is_file()
    assert not (state_dir / "transaction-journal").exists()

    interrupted_rollback = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--rollback", "--home", str(target_home)],
        env={**env, "ATIUS_RUSTDESK_INSTALLER_TEST_INTERRUPT_AFTER": "target"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert interrupted_rollback.returncode == 75
    assert target.read_text(encoding="utf-8") == "baseline-provider\n"
    assert (state_dir / "transaction-journal").is_file()

    recovered_rollback = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--rollback", "--home", str(target_home)],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(recovered_rollback.stdout)["recovered"] is True
    assert target.read_text(encoding="utf-8") == "baseline-provider\n"
    assert not (state_dir / "install-state").exists()
    assert not (state_dir / "provider.pre-phase52").exists()
    assert not (state_dir / "transaction-journal").exists()


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


def test_backup_restore_state_machine_positive_flow(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-state"
    database = _create_sqlite_source(source_dir)
    source_state = {
        "active": False,
        "public_listener": False,
        "image_digest": validator.ARM64_IMAGE_DIGEST,
        "architecture": "arm64",
    }
    assert validator.quiesce_source(source_state).status == "PASS"
    assert validator.verify_sqlite_integrity(database).status == "PASS"
    assert validator.verify_state_allowlist(source_dir).status == "PASS"

    backup_a = validator.create_verified_backup(
        source_dir, tmp_path / "backup-a.tar", source_state, label="A"
    )
    backup_b = validator.create_verified_backup(
        source_dir, tmp_path / "backup-b.tar", source_state, label="B"
    )
    assert backup_a["status"] == backup_b["status"] == "PASS"
    assert backup_a["archive_path"] != backup_b["archive_path"]
    assert backup_a["entries"] == backup_b["entries"] == ["db_v2.sqlite3"]
    assert backup_a["archive_mode"] == backup_b["archive_mode"] == "0600"
    assert len(backup_a["sha256"]) == len(backup_b["sha256"]) == 64
    assert validator.validate_recovery_backups(backup_a, backup_b).status == "PASS"

    restored = validator.restore_isolated(Path(backup_a["archive_path"]), tmp_path / "restores")
    restored_dir = Path(restored["runtime_dir"])
    assert restored["status"] == "PASS"
    assert restored_dir.name.startswith("rustdesk-restore-")
    assert validator.verify_sqlite_integrity(restored_dir / "db_v2.sqlite3").status == "PASS"

    public_key = tmp_path / "id_ed25519.pub"
    public_key.write_bytes(b"synthetic-public-identity")
    expected_fingerprint = "sha256:" + validator.hashlib.sha256(public_key.read_bytes()).hexdigest()
    assert validator.verify_public_fingerprint(public_key, expected_fingerprint).status == "PASS"
    assert validator.verify_no_public_listener({"public_listener": False}).status == "PASS"

    rollback = validator.cleanup_restore_runtime(
        restored_dir,
        {"service_active": False, "service_enabled": False, "public_listener": False},
        restore_verified=True,
    )
    assert rollback.id == "P52-ROLLBACK-001"
    assert rollback.status == "PASS"
    assert not restored_dir.exists()
    assert Path(backup_a["archive_path"]).exists()
    assert Path(backup_b["archive_path"]).exists()


def test_backup_excludes_identity_and_requires_quiesced_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-state"
    _create_sqlite_source(source_dir)
    (source_dir / "id_ed25519").write_text("synthetic-private-key", encoding="utf-8")
    result = validator.verify_state_allowlist(source_dir)
    assert result.status == "BLOCKED"
    assert "private-key-in-state" in _categories(result)

    active = {
        "active": True,
        "public_listener": False,
        "image_digest": validator.ARM64_IMAGE_DIGEST,
        "architecture": "arm64",
    }
    with pytest.raises(ValueError, match="quiesced"):
        validator.create_verified_backup(source_dir, tmp_path / "active.tar", active, label="A")
    assert not (tmp_path / "active.tar").exists()


def test_restore_blocks_missing_b_corrupt_archive_and_path_escape(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-state"
    _create_sqlite_source(source_dir)
    source_state = {
        "active": False,
        "public_listener": False,
        "image_digest": validator.ARM64_IMAGE_DIGEST,
        "architecture": "arm64",
    }
    backup_a = validator.create_verified_backup(
        source_dir, tmp_path / "backup-a.tar", source_state, label="A"
    )
    missing_b = validator.validate_recovery_backups(backup_a, None)
    assert missing_b.status == "BLOCKED"
    assert "missing-backup-b" in _categories(missing_b)

    corrupt = tmp_path / "corrupt.tar"
    corrupt.write_bytes(b"not-a-tar")
    corrupt.chmod(0o600)
    with pytest.raises(ValueError, match="archive"):
        validator.restore_isolated(corrupt, tmp_path / "corrupt-restores")

    escaping = tmp_path / "escaping.tar"
    payload = tmp_path / "payload"
    payload.write_text("state", encoding="utf-8")
    with tarfile.open(escaping, "w") as archive:
        archive.add(payload, arcname="../db_v2.sqlite3")
    escaping.chmod(0o600)
    with pytest.raises(ValueError, match="allowlist"):
        validator.restore_isolated(escaping, tmp_path / "escape-restores")


def test_restore_blocks_sqlite_fingerprint_network_and_early_cleanup(tmp_path: Path) -> None:
    corrupt_db = tmp_path / "db_v2.sqlite3"
    corrupt_db.write_bytes(b"not-sqlite")
    assert validator.verify_sqlite_integrity(corrupt_db).status == "BLOCKED"

    public_key = tmp_path / "id_ed25519.pub"
    public_key.write_bytes(b"synthetic-public-identity")
    mismatch = validator.verify_public_fingerprint(public_key, "sha256:" + "0" * 64)
    assert mismatch.status == "BLOCKED"
    assert validator.verify_no_public_listener({"public_listener": True}).status == "BLOCKED"

    restore_dir = tmp_path / "rustdesk-restore-early"
    restore_dir.mkdir()
    (restore_dir / ".phase52-disposable-restore").write_text("fixture", encoding="utf-8")
    blocked = validator.cleanup_restore_runtime(
        restore_dir,
        {"service_active": True, "service_enabled": False, "public_listener": False},
        restore_verified=False,
    )
    assert blocked.status == "BLOCKED"
    assert restore_dir.exists()


def test_rollback_cleanup_failure_remains_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    restore_dir = tmp_path / "rustdesk-restore-cleanup-failure"
    restore_dir.mkdir()
    marker = restore_dir / ".phase52-disposable-restore"
    marker.write_text("fixture", encoding="utf-8")
    marker.chmod(0o600)

    def refuse_cleanup(_path: Path) -> None:
        raise OSError("synthetic cleanup refusal")

    monkeypatch.setattr(validator.shutil, "rmtree", refuse_cleanup)
    result = validator.cleanup_restore_runtime(
        restore_dir,
        {"service_active": False, "service_enabled": False, "public_listener": False},
        restore_verified=True,
    )
    assert result.status == "BLOCKED"
    assert "cleanup-failure" in _categories(result)
    assert restore_dir.exists()


def test_full_candidate_gate_persists_nogo_before_return(tmp_path: Path) -> None:
    persisted: list[dict] = []
    callbacks = {
        "supply": lambda: "PASS",
        "capacity": lambda: "PASS",
        "vault": lambda: "PASS",
        "backup": lambda: "BLOCKED",
        "restore": lambda: "PASS",
        "capacity_finalize": lambda: "PASS",
        "rollback": lambda: "PASS",
        "topology_security": lambda: "PASS",
    }
    result = validator.run_full_candidate_gate(
        "horistic-srv", callbacks, lambda payload: persisted.append(copy.deepcopy(payload))
    )
    assert result["verdict"] == "NO-GO"
    assert result["stages"]["backup"]["status"] == "BLOCKED"
    assert result["stages"]["restore"]["status"] == "SKIPPED_DUE_TO_GATE"
    assert persisted[-1] == result
    assert persisted[-1]["persisted_before_fallback"] is True


def test_candidate_chain_reaches_horistic_without_disabling_live_write_guard() -> None:
    persisted: list[dict] = []
    calls: list[tuple[str, str]] = []

    def callbacks(candidate: str, failure: str | None) -> dict[str, object]:
        result: dict[str, object] = {}
        for stage in validator.FULL_CANDIDATE_STAGES:
            def invoke(stage_name: str = stage) -> dict[str, object]:
                calls.append((candidate, stage_name))
                return {
                    "status": "BLOCKED" if stage_name == failure else "PASS",
                    "input_digest": "a" * 64,
                    "evidence_ids": [f"fixture-{candidate}-{stage_name}"],
                    "findings": ["synthetic-stage-failure"] if stage_name == failure else [],
                    "mutation": {
                        "performed": False,
                        "classes": [],
                    },
                }

            result[stage] = invoke
        return result

    callbacks_by_candidate = {
        "atius-srv-2": callbacks("atius-srv-2", "capacity"),
        "atius-srv-3": callbacks("atius-srv-3", None),
        "horistic-srv": callbacks("horistic-srv", None),
    }

    def persist(payload: dict) -> None:
        if persisted:
            assert persisted[-1]["verdict"] == "NO-GO"
        persisted.append(copy.deepcopy(payload))

    summary = validator.run_candidate_chain(
        validator.CANDIDATES,
        callbacks_by_candidate,
        persist,
    )
    assert [row["candidate"] for row in persisted] == list(validator.CANDIDATES)
    assert persisted[0]["first_non_pass_stage"] == "capacity"
    assert persisted[1]["first_non_pass_stage"] == "vault"
    assert persisted[1]["stages"]["vault"]["findings"] == [
        "unauthorized-live-write-candidate"
    ]
    assert list(persisted[0]["stages"]) == list(validator.FULL_CANDIDATE_STAGES)
    assert summary["selected_candidate"] == "horistic-srv"
    assert summary["overall_status"] == "PASS"
    assert summary["authorized_live_write_candidate"] == "horistic-srv"
    assert all(
        row["authorized_live_write_candidate"] == "horistic-srv" for row in persisted
    )
    assert summary["windows_install_performed"] is False
    assert ("atius-srv-2", "rollback") not in calls
    assert ("atius-srv-3", "vault") not in calls
    assert ("atius-srv-3", "rollback") not in calls
    with pytest.raises(ValueError, match="authorized live write candidate is invalid"):
        validator.run_candidate_chain(
            validator.CANDIDATES,
            callbacks_by_candidate,
            lambda _: None,
            authorized_live_write_candidate="atius-srv-3",
        )


def test_persisted_full_gate_summary_requires_exact_horistic_authority(tmp_path: Path) -> None:
    def callbacks(candidate: str) -> dict[str, object]:
        return {
            stage: (
                lambda stage_name=stage: {
                    "status": (
                        "NO-GO"
                        if candidate == "atius-srv-2" and stage_name == "capacity"
                        else "BLOCKED"
                        if candidate == "horistic-srv" and stage_name == "vault"
                        else "PASS"
                    ),
                    "mutation": {"performed": False, "classes": []},
                }
            )
            for stage in validator.FULL_CANDIDATE_STAGES
        }

    evidence_root = tmp_path / "phase52"
    evidence_root.mkdir()

    def persist(payload: dict) -> None:
        name = validator.FULL_GATE_EVIDENCE_NAMES[payload["candidate"]]
        (evidence_root / name).write_text(json.dumps(payload), encoding="utf-8")

    summary = validator.run_candidate_chain(
        validator.CANDIDATES,
        {candidate: callbacks(candidate) for candidate in validator.CANDIDATES},
        persist,
    )
    placement = validator._update_placement_from_full_gate(_placement(), summary)
    baseline = validator.validate_full_candidate_summary(summary, placement, evidence_root)
    assert baseline.status == "BLOCKED"
    assert "authorized-live-write-candidate-drift" not in _categories(baseline)

    tampered = copy.deepcopy(summary)
    tampered["authorized_live_write_candidate"] = "atius-srv-3"
    result = validator.validate_full_candidate_summary(tampered, placement, evidence_root)
    assert result.status == "FAIL"
    assert "authorized-live-write-candidate-drift" in _categories(result)


def test_rollback_callback_is_not_run_after_capacity_nogo() -> None:
    rollback_calls: list[bool] = []
    callbacks = {
        "supply": lambda: {"status": "PASS"},
        "capacity": lambda: {"status": "NO-GO"},
        "vault": lambda: {"status": "PASS"},
        "backup": lambda: {"status": "PASS"},
        "restore": lambda: {"status": "PASS"},
        "capacity_finalize": lambda: {"status": "PASS"},
        "rollback": lambda: rollback_calls.append(True) or {"status": "PASS"},
        "topology_security": lambda: {"status": "PASS"},
    }
    result = validator.run_full_candidate_gate("horistic-srv", callbacks, lambda _: None)
    assert rollback_calls == []
    assert result["stages"]["rollback"]["status"] == "BLOCKED"
    assert result["stages"]["rollback"]["findings"] == [
        "rollback-requires-current-capacity-pass"
    ]
    assert result["stages"]["rollback"]["mutation"] == {"performed": False, "classes": []}


def test_full_candidate_gate_converts_stage_exception_to_blocked_and_runs_rollback() -> None:
    persisted: list[dict] = []
    rollback_calls: list[bool] = []

    def explode() -> dict[str, object]:
        raise RuntimeError("synthetic secret-capable failure")

    callbacks = {
        "supply": lambda: {"status": "PASS"},
        "capacity": lambda: {"status": "PASS"},
        "vault": explode,
        "backup": lambda: {"status": "PASS"},
        "restore": lambda: {"status": "PASS"},
        "capacity_finalize": lambda: {"status": "PASS"},
        "rollback": lambda: rollback_calls.append(True) or {"status": "PASS"},
        "topology_security": lambda: {"status": "PASS"},
    }
    result = validator.run_full_candidate_gate("horistic-srv", callbacks, persisted.append)
    assert result["stages"]["vault"]["status"] == "BLOCKED"
    assert result["stages"]["vault"]["findings"] == ["stage-exception"]
    assert rollback_calls == [True]
    assert result["verdict"] == "NO-GO"
    assert persisted == [result]


def test_backup_independence_contract_requires_distinct_generation_and_destination(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-state"
    _create_sqlite_source(source_dir)
    source_state = {
        "active": False,
        "public_listener": False,
        "image_digest": validator.ARM64_IMAGE_DIGEST,
        "architecture": "arm64",
    }
    backup_a = validator.create_verified_backup(
        source_dir, tmp_path / "backup-a.tar", source_state, label="A"
    )
    backup_b = validator.create_verified_backup(
        source_dir, tmp_path / "backup-b.tar", source_state, label="B"
    )
    assert backup_a["status"] == backup_b["status"] == "PASS"
    assert backup_a["archive_sha256"] != backup_b["archive_sha256"] or backup_a["generated_at"] != backup_b["generated_at"]
    assert backup_a["generation_id"] != backup_b["generation_id"]
    assert backup_a["destination_class"] == "candidate-local"
    assert backup_b["destination_class"] == "modules/fleet-backup:gdrive"
    assert backup_a["source_input_digest"] == backup_b["source_input_digest"]
    assert backup_a["verified_copy"] is backup_b["verified_copy"] is True
    assert validator.validate_recovery_backups(backup_a, backup_b).status == "PASS"

    conflated = copy.deepcopy(backup_b)
    conflated["generation_id"] = backup_a["generation_id"]
    assert validator.validate_recovery_backups(backup_a, conflated).status == "BLOCKED"


def test_candidate_write_authority_is_capacity_gated_and_exact() -> None:
    with pytest.raises(ValueError, match="capacity PASS"):
        validator.enforce_candidate_write(
            "horistic-srv", "state-only-backup-a", capacity_status="NO-GO", isolated=True
        )
    with pytest.raises(ValueError, match="forbidden"):
        validator.enforce_candidate_write(
            "atius-srv-2", "cleanup", capacity_status="PASS", isolated=True
        )
    with pytest.raises(ValueError, match="isolation"):
        validator.enforce_candidate_write(
            "horistic-srv", "state-only-backup-a", capacity_status="PASS", isolated=False
        )
    assert validator.enforce_candidate_write(
        "horistic-srv", "state-only-backup-a", capacity_status="PASS", isolated=True
    ) is None
    with pytest.raises(ValueError, match="unauthorized-live-write-candidate"):
        validator.enforce_candidate_write(
            "atius-srv-3", "state-only-backup-a", capacity_status="PASS", isolated=True
        )


def test_live_write_candidate_guard_blocks_callbacks_before_any_mutation() -> None:
    calls: list[str] = []

    def callback(stage: str) -> dict[str, object]:
        calls.append(stage)
        return {
            "status": "PASS",
            "mutation": {
                "performed": stage in validator.LIVE_WRITE_CAPABLE_STAGES,
                "classes": ["synthetic-write"] if stage in validator.LIVE_WRITE_CAPABLE_STAGES else [],
            },
        }

    callbacks = {
        stage: (lambda stage_name=stage: callback(stage_name))
        for stage in validator.FULL_CANDIDATE_STAGES
    }
    persisted: list[dict[str, object]] = []
    result = validator.run_full_candidate_gate(
        "atius-srv-2",
        callbacks,
        persisted.append,
        authorized_live_write_candidate=validator.AUTHORIZED_LIVE_WRITE_CANDIDATE,
    )
    assert calls == ["supply", "capacity"]
    assert result["stages"]["vault"]["status"] == "BLOCKED"
    assert result["stages"]["vault"]["findings"] == ["unauthorized-live-write-candidate"]
    assert result["stages"]["vault"]["mutation"] == {"performed": False, "classes": []}
    assert result["stages"]["rollback"]["status"] == "BLOCKED"
    assert result["stages"]["rollback"]["mutation"] == {"performed": False, "classes": []}
    assert result["authorized_live_write_candidate"] == "horistic-srv"
    assert persisted == [result]
    with pytest.raises(ValueError, match="authorized live write candidate is invalid"):
        validator.run_full_candidate_gate(
            "horistic-srv",
            callbacks,
            lambda _: None,
            authorized_live_write_candidate="atius-srv-3",
        )


def test_horistic_topology_contract_accepts_current_review_and_future_jit_gates() -> None:
    topology = validator.horistic_topology_evidence()
    assert topology["status"] == "PASS"
    assert topology["client_colocation"] is True
    assert topology["phase52_review_status"] == "PASS"
    assert topology["phase53_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    assert topology["phase54_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    assert topology["phase57_review"] == "REQUIRED_IMMEDIATELY_BEFORE_PHASE"
    for domains in (
        topology["server_client_resource_domains"],
        topology["server_client_evidence_domains"],
        topology["server_client_rollback_domains"],
    ):
        assert domains["server"] != domains["client"]


def test_vault_restore_mutation_catalog_is_complete_and_non_secret() -> None:
    catalog = validator.load_json_strict(VAULT_RESTORE_MUTATIONS_PATH)
    ids = {item["id"] for item in catalog["mutations"]}
    assert {
        "unknown-vault-reference",
        "duplicate-password-result",
        "secret-bearing-argv",
        "secret-bearing-output",
        "permissive-runtime",
        "non-tmpfs-runtime",
        "private-key-archive",
        "missing-backup-b",
        "corrupt-backup-b",
        "active-source",
        "wrong-database",
        "sqlite-integrity-failure",
        "fingerprint-mismatch",
        "public-listener",
        "restored-service-active",
        "cleanup-failure",
    }.issubset(ids)
    serialized = json.dumps(catalog, sort_keys=True)
    assert "BEGIN PRIVATE KEY" not in serialized
    assert "permanent_password_value" not in serialized


def test_report_builds_exact_pass_check_set_from_current_horistic_primary() -> None:
    report = validator.build_phase52_report(REPO, generated_at="2026-07-22T03:30:00Z")
    assert [item["id"] for item in report["checks"]] == list(validator.PHASE52_CHECK_ORDER)
    assert len(report["checks"]) == len(set(item["id"] for item in report["checks"])) == 11
    assert report["overall_status"] == "PASS"
    assert report["selected_candidate"] == "horistic-srv"
    assert report["phase53_advance_status"] == "READY"
    assert report["phase53_topology_review_status"] == "PASS"
    assert report["windows_install_performed"] is False
    assert report["windows_access_proven"] is False
    assert report["secret_material_present"] is False
    by_id = {item["id"]: item for item in report["checks"]}
    assert by_id["P52-SUPPLY-001"]["status"] == "PASS"
    assert all(item["status"] == "PASS" and item["findings"] == [] for item in report["checks"])
    assert by_id["P52-REPORT-001"]["status"] == "PASS"
    assert by_id["P51-WS-001"]["status"] == "PASS"
    assert by_id["P51-P48-001"]["status"] == "PASS"


def test_report_rejects_duplicate_stale_self_hash_secret_and_stored_verdict_drift() -> None:
    report = validator.build_phase52_report(REPO, generated_at="2026-07-22T03:30:00Z")

    duplicate = copy.deepcopy(report)
    duplicate["checks"].append(copy.deepcopy(duplicate["checks"][0]))
    result = validator.validate_phase52_report(duplicate, REPO)
    assert result.status == "FAIL"
    assert "report-check-set" in _categories(result)

    stale = copy.deepcopy(report)
    stale["inputs"][0]["sha256"] = "0" * 64
    result = validator.validate_phase52_report(stale, REPO)
    assert result.status == "BLOCKED"
    assert "stale-input-digest" in _categories(result)

    self_cycle = copy.deepcopy(report)
    self_cycle["inputs"].append(
        {"path": PHASE52_REPORT_JSON_PATH.relative_to(REPO).as_posix(), "sha256": "0" * 64}
    )
    result = validator.validate_phase52_report(self_cycle, REPO)
    assert result.status == "FAIL"
    assert "report-self-hash-cycle" in _categories(result)

    secret = copy.deepcopy(report)
    secret["secret_material_present"] = True
    result = validator.validate_phase52_report(secret, REPO)
    assert result.status == "FAIL"
    assert "secret-material" in _categories(result)

    verdict = copy.deepcopy(report)
    verdict["overall_status"] = "BLOCKED"
    result = validator.validate_phase52_report(verdict, REPO)
    assert result.status == "FAIL"
    assert "stored-verdict-drift" in _categories(result)


def test_report_outputs_are_atomic_parity_and_topology_is_ready(tmp_path: Path) -> None:
    report = validator.build_phase52_report(REPO, generated_at="2026-07-22T03:30:00Z")
    integrated = tmp_path / "integrated-gate.json"
    machine = tmp_path / "52-GATE-REPORT.json"
    markdown = tmp_path / "52-GATE-REPORT.md"
    topology = tmp_path / "52-PHASE53-TOPOLOGY-REVIEW.md"
    validator.write_phase52_outputs_atomically(
        report,
        integrated_path=integrated,
        json_path=machine,
        markdown_path=markdown,
        topology_path=topology,
        repo=REPO,
        allow_test_paths=True,
    )
    assert integrated.read_bytes() == machine.read_bytes()
    assert validator.validate_phase52_output_parity(report, integrated, machine, markdown).status == "PASS"
    topology_text = topology.read_text(encoding="utf-8")
    assert "**Status:** PASS" in topology_text
    assert "**Selected candidate:** `horistic-srv`" in topology_text
    assert "**Phase 53 advance status:** `READY`" in topology_text
    assert "Current blockers: none." in topology_text
    assert "Phase 54" in topology_text and "Phase 57" in topology_text
    assert "windows_install_performed=false" in topology_text


def test_pass_report_promotes_exact_phase52_ledger_rows() -> None:
    report = validator.build_phase52_report(REPO, generated_at="2026-07-22T03:30:00Z")
    ledger = validator.load_json_strict(LEDGER_PATH)
    updated, promoted = validator.update_phase52_ledger(ledger, report)
    assert promoted is True
    rows = {
        item["requirement_id"]: item
        for item in updated["requirements"]
        if item["requirement_id"] in validator.PHASE52_REQUIREMENTS
    }
    assert set(rows) == set(validator.PHASE52_REQUIREMENTS)
    assert all(item["status"] == "pass" and item["last_verified_at"] == report["generated_at"] for item in rows.values())


def test_report_cli_accepts_canonical_output_paths() -> None:
    parser = validator.build_parser()
    options = {action.dest for action in parser._actions}
    assert {"json_out", "markdown_out", "integrated_out", "topology_out"}.issubset(options)
    assert not {"install", "cleanup", "remediate", "publish"} & options


def test_gate_a_vault_control_plane_contract_is_exact_and_value_free() -> None:
    contract = validator.load_json_strict(VAULT_CONTROL_CONTRACT_PATH)
    assert contract["backend_protocol"] == "rustdesk-phase52-v1"
    assert contract["rclone_protocol"] == "rclone-giovanni-drive-phase52-v1"
    assert contract["rclone_binding"] == {
        "profile": "rclone-giovanni-drive-phase52",
        "vault_path": "kv/atius/fleet-backup/rclone/giovanni-drive",
        "field": "rclone_conf",
        "approved_remote": "giovanni-drive",
    }
    assert contract["horistic_key_policy"]["reuse_existing_key"] is True
    assert contract["horistic_key_policy"]["rotate_or_generate"] is False
    assert contract["srv3_backend"]["vault_writer"] == "/usr/local/sbin/atius-vault-phase52-write"
    assert contract["srv3_backend"]["vault_writer_scope"] == "local-root-only-stdin-cas0"
    assert "/usr/local/sbin/atius-vault-phase52-write" in contract["srv3_control_plane_scope"]
    serialized = json.dumps(contract, sort_keys=True)
    assert "fixture-token" not in serialized
    for path in (
        VAULT_CONTROL_BACKEND_PATH,
        VAULT_CONTROL_DISPATCHER_PATH,
        VAULT_CONTROL_WRITER_PATH,
        VAULT_CONTROL_INSTALLER_PATH,
    ):
        assert path.is_file()
        assert os.access(path, os.X_OK)


def test_gate_a_readiness_uses_ephemeral_vault_hydration_and_fetcher() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "rclone_vault_hydrator" in text
    assert "rclone_copy" in text
    assert "rclone_fetch" in text
    assert "runtime_tmpfs" in text
    assert "~/.config/rclone/rclone.conf" not in text


def test_gate_a_stage_check_uses_selected_candidate_not_expected_predecessor_nogo() -> None:
    stages = {
        name: {
            "status": "PASS",
            "evidence_ids": [f"P52-EV-HORISTIC-{name.upper()}"],
            "findings": [],
        }
        for name in validator.FULL_CANDIDATE_STAGES
    }
    predecessor_stages = copy.deepcopy(stages)
    predecessor_stages["capacity"] = {
        "status": "NO-GO",
        "evidence_ids": ["P52-EV-SRV2-CAPACITY"],
        "findings": ["capacity-threshold-exceeded"],
    }
    summary = {
        "selected_candidate": "horistic-srv",
        "attempts": [
            {"candidate": "atius-srv-2", "stages": predecessor_stages},
            {"candidate": "atius-srv-3", "stages": predecessor_stages},
            {"candidate": "horistic-srv", "stages": stages},
        ],
    }
    for stage in ("vault", "backup", "restore", "capacity", "rollback"):
        result = validator._stage_check(
            f"P52-GATE-A-{stage.upper()}", stage, summary, require_selected=True
        )
        assert result.status == "PASS"
        assert all("threshold" not in finding.category for finding in result.findings)


def test_gate_a_live_drill_declares_ordered_actions_and_offline_pinned_hbbs() -> None:
    assert LIVE_DRILL_PATH.is_file()
    text = LIVE_DRILL_PATH.read_text(encoding="utf-8")
    for action in (
        "preflight",
        "vault",
        "backup",
        "restore",
        "capacity-finalize",
        "rollback",
    ):
        assert action in text
    assert validator.ARM64_IMAGE_DIGEST in text
    recovery_text = RECOVERY_PATH.read_text(encoding="utf-8")
    assert "--network" in recovery_text and "none" in recovery_text
    assert "--publish" not in text + recovery_text and "-p " not in text + recovery_text


def test_gate_a_backend_rejects_duplicate_reordered_extra_oversized_and_legacy() -> None:
    expected = {
        "protocol": "rustdesk-phase52-v1",
        "references": [
            {"vault_path": path, "field": field}
            for path, field in validator.APPROVED_VAULT_REFERENCES
        ],
    }
    malformed = [
        b'{"protocol":"rustdesk-phase52-v1","protocol":"rustdesk-phase52-v1","references":[]}',
        json.dumps({**expected, "references": list(reversed(expected["references"]))}).encode(),
        json.dumps({**expected, "extra": False}).encode(),
        b"{" + b"x" * 16384 + b"}",
    ]
    for payload in malformed:
        completed = subprocess.run(
            [str(VAULT_CONTROL_BACKEND_PATH), "rustdesk-phase52-v1"],
            input=payload,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 2
        assert completed.stdout == b"" and completed.stderr == b""
    legacy = subprocess.run(
        [str(VAULT_CONTROL_BACKEND_PATH), "rustdesk-phase52"],
        input=b"{}",
        capture_output=True,
        check=False,
    )
    assert legacy.returncode == 64
    assert legacy.stdout == b"" and legacy.stderr == b""


def test_gate_a_control_plane_installer_dry_run_is_zero_write(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir(mode=0o700)
    ssh_dir = root / "home/ubuntu/.ssh"
    ssh_dir.mkdir(parents=True, mode=0o700)
    fixture_key = tmp_path / "fixture-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(fixture_key)],
        check=True,
    )
    public = fixture_key.with_suffix(".pub")
    key_type, key_blob, comment = public.read_text(encoding="utf-8").strip().split(maxsplit=2)
    authorized = ssh_dir / "authorized_keys"
    authorized.write_text(
        f'command="/home/ubuntu/.local/bin/atius-vault-export-ssh",no-agent-forwarding,no-X11-forwarding,no-pty,no-port-forwarding {key_type} {key_blob} {comment}\n',
        encoding="utf-8",
    )
    authorized.chmod(0o600)
    fingerprint = subprocess.run(
        ["ssh-keygen", "-lf", str(public), "-E", "sha256"],
        text=True, capture_output=True, check=True,
    ).stdout.split()[1]
    before = {path.relative_to(root): (path.stat().st_mode, path.read_bytes() if path.is_file() else b"") for path in root.rglob("*")}
    completed = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--install", "--dry-run", "--root", str(root),
         "--authorized-key-file", str(public), "--expected-fingerprint", fingerprint],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "PASS"
    assert payload["live_write_performed"] is False
    assert payload["key_rotation_performed"] is False
    assert payload["secret_material_present"] is False
    assert payload["replacement_count"] == 1
    assert payload["authorized_keys_mode"] == "0600"
    after = {path.relative_to(root): (path.stat().st_mode, path.read_bytes() if path.is_file() else b"") for path in root.rglob("*")}
    assert after == before


def test_gate_a_corrective_recovery_is_versioned_and_external_runners_are_forbidden() -> None:
    assert LIVE_DRILL_CONTRACT_PATH.is_file()
    assert RECOVERY_PATH.is_file()
    live_text = LIVE_DRILL_PATH.read_text(encoding="utf-8")
    assert "phase52_recovery" in live_text
    assert "runtime-contract" not in live_text
    assert "action_runners" not in live_text
    contract = validator.load_json_strict(LIVE_DRILL_CONTRACT_PATH)
    assert contract["external_action_runners_allowed"] is False
    assert contract["actions"] == [
        "preflight", "vault", "backup", "restore", "capacity-finalize", "rollback"
    ]


def test_gate_a_corrective_rollback_is_terminal_after_partial_failure(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("phase52_recovery_test", RECOVERY_PATH)
    assert spec and spec.loader
    recovery = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = recovery
    spec.loader.exec_module(recovery)
    state = recovery.initial_state("a" * 32)
    state["completed_actions"] = ["preflight", "vault"]
    state["active_action"] = "backup"
    state["cleanup_pending"] = ["disposable-source-runtime"]
    recovery.validate_transition("rollback", state)
    rolled = recovery.rollback_state(state)
    assert rolled["terminal"] is True
    assert rolled["completed_actions"][-1] == "rollback"
    assert rolled["cleanup_pending"] == []
    assert recovery.rollback_state(rolled) == rolled


def test_gate_a_corrective_vault_client_preserves_provider_api_and_internal_envelope() -> None:
    assert VAULT_CLIENT_PATH.is_file() and os.access(VAULT_CLIENT_PATH, os.X_OK)
    provider_text = VAULT_PROVIDER_PATH.read_text(encoding="utf-8")
    client_text = VAULT_CLIENT_PATH.read_text(encoding="utf-8")
    backend_text = VAULT_CONTROL_BACKEND_PATH.read_text(encoding="utf-8")
    assert 'set(payload) != {"references"}' in provider_text
    assert "atius-vault-phase52-client" in provider_text
    assert '"protocol"' in client_text and '"references"' in client_text
    assert "/usr/local/sbin/atius-vault" in backend_text
    assert "kv\", \"get\", \"-format=json" in backend_text
    assert "atius-vault-export-env" not in backend_text


def test_gate_a_corrective_streams_are_bounded_during_read_and_kill_process_groups() -> None:
    for path in (VAULT_CLIENT_PATH, VAULT_CONTROL_BACKEND_PATH):
        text = path.read_text(encoding="utf-8")
        assert "selectors" in text
        assert "start_new_session" in text
        assert "killpg" in text
        assert "subprocess.run" not in text


def test_gate_a_corrective_dispatcher_preserves_legacy_grammar() -> None:
    text = VAULT_CONTROL_DISPATCHER_PATH.read_text(encoding="utf-8")
    assert "atius-vault-env" in text
    assert "atius-vault-export-ssh" in text
    assert "rustdesk-phase52-v1" in text
    assert "rclone-giovanni-drive-phase52-v1" in text
    assert "eval" not in text


def test_gate_a_dispatcher_does_not_require_caller_execute_permission_on_root_backend() -> None:
    text = VAULT_CONTROL_DISPATCHER_PATH.read_text(encoding="utf-8")
    assert '[[ -x "$BACKEND" ]]' not in text
    assert '[[ -f "$BACKEND" && ! -L "$BACKEND" ]]' in text


def test_gate_a_dispatcher_uses_canonical_live_root_paths_for_exact_sudoers_match(
    tmp_path: Path,
) -> None:
    text = VAULT_CONTROL_DISPATCHER_PATH.read_text(encoding="utf-8")
    assert "phase52_managed_path" in text
    command = (
        'source "$1"; '
        'phase52_managed_path "$2" usr/local/sbin/atius-vault-export-rustdesk-phase52; '
        "printf '\\n'; "
        'phase52_managed_path "$2" home/ubuntu/.local/bin/atius-vault-export-ssh'
    )
    live = subprocess.run(
        ["bash", "-c", command, "bash", str(VAULT_CONTROL_DISPATCHER_PATH), "/"],
        text=True, capture_output=True, check=False,
    )
    assert live.returncode == 0, live.stderr
    assert live.stdout.splitlines() == [
        "/usr/local/sbin/atius-vault-export-rustdesk-phase52",
        "/home/ubuntu/.local/bin/atius-vault-export-ssh",
    ]
    fixture_root = tmp_path / "root"
    fixture_root.mkdir()
    fixture = subprocess.run(
        ["bash", "-c", command, "bash", str(VAULT_CONTROL_DISPATCHER_PATH), str(fixture_root)],
        text=True, capture_output=True, check=False,
    )
    assert fixture.returncode == 0, fixture.stderr
    assert fixture.stdout.splitlines() == [
        f"{fixture_root}/usr/local/sbin/atius-vault-export-rustdesk-phase52",
        f"{fixture_root}/home/ubuntu/.local/bin/atius-vault-export-ssh",
    ]


def test_gate_a_corrective_installer_preserves_identity_and_validates_sudoers() -> None:
    text = VAULT_CONTROL_INSTALLER_PATH.read_text(encoding="utf-8")
    for required in ("st_uid", "st_gid", "st_nlink", "visudo", "authorized-key-entry-not-unique"):
        assert required in text
    assert "symlink" in text.lower()
    assert "hardlink" in text.lower()


def test_gate_a_corrective_predecessor_mutation_is_rejected_even_when_selected_passes() -> None:
    record = {"status": "PASS", "evidence_ids": ["fixture"], "findings": [], "mutation": {"performed": False, "classes": []}}
    predecessor = copy.deepcopy(record)
    predecessor["status"] = "NO-GO"
    predecessor["mutation"] = {"performed": True, "classes": ["unexpected-write"]}
    summary = {
        "selected_candidate": "horistic-srv",
        "attempts": [
            {"candidate": "atius-srv-2", "stages": {"capacity": predecessor}},
            {"candidate": "horistic-srv", "stages": {"capacity": record}},
        ],
    }
    result = validator._stage_check("P52-CORRECTIVE", "capacity", summary, require_selected=True)
    assert result.status == "FAIL"
    assert "predecessor-mutation" in _categories(result)


def test_gate_a_corrective_topology_renderer_has_truthful_pass_branch() -> None:
    report = validator.build_phase52_report(REPO, generated_at="2026-07-22T03:30:00Z")
    report["selected_candidate"] = "horistic-srv"
    report["phase53_topology_review_status"] = "PASS"
    report["phase53_advance_status"] = "READY"
    report["overall_status"] = "PASS"
    for check in report["checks"]:
        check["status"] = "PASS"
        check["findings"] = []
    text = validator.render_phase53_topology_review(report)
    assert "No recoverable primary is selected" not in text
    assert "Phase 53 is blocked" not in text
    assert "Horistic" in text and "READY" in text


def test_gate_a_composed_provider_client_dispatch_transport_and_direct_backend(tmp_path: Path) -> None:
    profile_root = tmp_path / "profiles"
    profile_root.mkdir(mode=0o700)
    references = [
        {"vault_path": path, "field": field}
        for path, field in validator.APPROVED_VAULT_REFERENCES
    ]
    (profile_root / "rustdesk-phase52-v1.json").write_text(
        json.dumps({"protocol": "rustdesk-phase52-v1", "references": references}),
        encoding="utf-8",
    )
    (profile_root / "rustdesk-phase52-v1.json").chmod(0o600)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(mode=0o700)
    fake_vault = fake_bin / "atius-vault"
    fake_vault.write_text(
        "#!/usr/bin/env python3\n"
        "import json,sys\n"
        "path=sys.argv[-1]\n"
        "values={'private_key':'private-fixture','public_key':'public-fixture'} if path.endswith('/server') else {'permanent_password':'R'+path.rsplit('/',1)[-1].replace('-','')[:20].ljust(31,'x')}\n"
        "print(json.dumps({'data':{'data':values}}))\n",
        encoding="utf-8",
    )
    fake_vault.chmod(0o700)
    fake_ssh = fake_bin / "ssh"
    fake_ssh.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nprotocol=${!#}\nexec \"$FAKE_PHASE52_BACKEND\" \"$protocol\"\n",
        encoding="utf-8",
    )
    fake_ssh.chmod(0o700)
    completed = subprocess.run(
        [str(VAULT_PROVIDER_PATH), "--self-check"],
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "ATIUS_RUSTDESK_VAULT_BACKEND": str(VAULT_CLIENT_PATH),
            "ATIUS_PHASE52_PROFILE_ROOT": str(profile_root),
            "ATIUS_PHASE52_VAULT_BIN": str(fake_vault),
            "ATIUS_PHASE52_SSH_TARGET": "fixture-srv3",
            "FAKE_PHASE52_BACKEND": str(VAULT_CONTROL_BACKEND_PATH),
        },
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {
        "status": "PASS", "blocker": "none", "reference_count": 7,
        "secret_material_present": False,
    }
    assert "private-fixture" not in completed.stdout + completed.stderr
    assert "public-fixture" not in completed.stdout + completed.stderr


def test_gate_a_third_cycle_dispatcher_is_installed_root_owned_and_executable() -> None:
    text = VAULT_CONTROL_INSTALLER_PATH.read_text(encoding="utf-8")
    assert "dispatcher_install_mode=0o755" in text
    assert "control_plane_uid=0" in text and "control_plane_gid=0" in text
    assert "dispatcher-installed-identity-drift" in text


def test_gate_a_third_cycle_client_pins_existing_transport_identity_and_ssh_policy() -> None:
    text = VAULT_CLIENT_PATH.read_text(encoding="utf-8")
    assert 'SSH_TARGET = "ubuntu@atius-srv-3"' in text
    assert 'SSH_IDENTITY = "/home/horistic/.ssh/atius-vault-export-ed25519"' in text
    for option in (
        "IdentitiesOnly=yes", "IdentityAgent=none", "ProxyCommand=none",
        "ProxyJump=none", "ClearAllForwardings=yes",
    ):
        assert option in text
    assert "ATIUS_PHASE52_SSH_TARGET" not in text


def test_gate_a_third_cycle_dispatcher_legacy_grammar_is_exact_and_unbounded_by_count() -> None:
    text = VAULT_CONTROL_DISPATCHER_PATH.read_text(encoding="utf-8")
    assert "[A-Za-z0-9_.:-]+" in text
    assert "legacy_command_max_bytes=16384" in text
    assert "{0,7}" not in text
    assert "[a-z0-9][a-z0-9-]" not in text


def test_gate_a_third_cycle_control_plane_dry_run_proves_exact_key_replacement() -> None:
    text = VAULT_CONTROL_INSTALLER_PATH.read_text(encoding="utf-8")
    for proof in (
        "dry-run-authorized-key-proof-required", "old_forced_command",
        "old_options", "authorized_keys_uid", "authorized_keys_gid",
        "authorized_keys_mode", "replacement_count", "replacement_line_sha256",
    ):
        assert proof in text
    assert "authorized_key_fingerprint_verified" in text


def test_gate_a_third_cycle_control_plane_validates_parents_lock_fsync_and_drift() -> None:
    text = VAULT_CONTROL_INSTALLER_PATH.read_text(encoding="utf-8")
    for required in (
        "validate_parent_chain", "flock", "fsync_parent", "installed-target-drift",
        "control-plane-global.lock",
    ):
        assert required in text


def test_gate_a_third_cycle_provider_and_client_share_one_transaction_journal() -> None:
    text = VAULT_PROVIDER_INSTALLER_PATH.read_text(encoding="utf-8")
    assert "client_state_file" not in text
    assert "client_backup_file" not in text
    assert "provider_target_path" in text and "client_target_path" in text
    assert "provider_installed_sha256" in text and "client_installed_sha256" in text
    assert "transaction-journal" in text


def test_gate_a_third_cycle_all_bounded_process_failures_kill_the_process_group() -> None:
    for path in (VAULT_PROVIDER_PATH, VAULT_CLIENT_PATH, VAULT_CONTROL_BACKEND_PATH, RECOVERY_PATH):
        text = path.read_text(encoding="utf-8")
        assert "kill_process_group" in text
        assert "if process.poll() is None:" not in text


def test_gate_a_third_cycle_composed_path_uses_installed_dispatcher_fake_sudo_and_backend(tmp_path: Path) -> None:
    installer = VAULT_CONTROL_INSTALLER_PATH.read_text(encoding="utf-8")
    dispatcher = VAULT_CONTROL_DISPATCHER_PATH.read_text(encoding="utf-8")
    backend = VAULT_CONTROL_BACKEND_PATH.read_text(encoding="utf-8")
    assert "fixture_root_relative_runtime" in installer
    assert "root_prefix_from_self" in dispatcher
    assert "root_prefix_from_self" in backend
    assert "sudo -n --" in dispatcher
    assert "mode_as_uid_proof" in backend
    root = tmp_path / "root"
    ssh_dir = root / "home/ubuntu/.ssh"
    ssh_dir.mkdir(parents=True, mode=0o700)
    key = tmp_path / "fixture-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    public = key.with_suffix(".pub")
    key_type, blob, comment = public.read_text(encoding="utf-8").strip().split(maxsplit=2)
    authorized = ssh_dir / "authorized_keys"
    authorized.write_text(
        f'command="/home/ubuntu/.local/bin/atius-vault-export-ssh",no-agent-forwarding,no-X11-forwarding,no-pty,no-port-forwarding {key_type} {blob} {comment}\n', encoding="utf-8"
    )
    authorized.chmod(0o600)
    fingerprint = subprocess.run(["ssh-keygen", "-lf", str(public), "-E", "sha256"], text=True, capture_output=True, check=True).stdout.split()[1]
    legacy = root / "home/ubuntu/.local/bin/atius-vault-export-ssh"
    legacy.parent.mkdir(parents=True, mode=0o700)
    legacy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8"); legacy.chmod(0o755)
    installed = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--install", "--root", str(root),
         "--authorized-key-file", str(public), "--expected-fingerprint", fingerprint],
        text=True, capture_output=True, check=False,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    installed_dispatcher = root / "usr/local/sbin/atius-vault-export-ssh-phase52"
    installed_backend = root / "usr/local/sbin/atius-vault-export-rustdesk-phase52"
    assert stat.S_IMODE(installed_dispatcher.stat().st_mode) == 0o755
    assert stat.S_IMODE(installed_backend.stat().st_mode) == 0o700
    fake_vault = root / "usr/local/sbin/atius-vault"
    fake_vault.write_text(
        "#!/usr/bin/env python3\nimport json,sys\np=sys.argv[-1]\n"
        "v={'private_key':'private-fixture','public_key':'public-fixture'} if p.endswith('/server') else {'permanent_password':'R'+p.rsplit('/',1)[-1].replace('-','')[:20].ljust(31,'x')}\n"
        "print(json.dumps({'data':{'data':v}}))\n", encoding="utf-8",
    ); fake_vault.chmod(0o755)
    fake_bin = tmp_path / "bin"; fake_bin.mkdir(mode=0o700)
    sudo_log = tmp_path / "sudo.log"
    (fake_bin / "sudo").write_text(
        "#!/bin/sh\nprintf '%s %s\\n' \"$(id -u)\" \"$(stat -c %a \"$3\")\" > \"$FAKE_SUDO_LOG\"\nshift 2\nexec \"$@\"\n",
        encoding="utf-8",
    ); (fake_bin / "sudo").chmod(0o700)
    (fake_bin / "ssh").write_text(
        "#!/bin/sh\nprotocol=\"\"\nfor item in \"$@\"; do protocol=$item; done\nSSH_ORIGINAL_COMMAND=$protocol exec \"$FAKE_DISPATCHER\"\n",
        encoding="utf-8",
    ); (fake_bin / "ssh").chmod(0o700)
    completed = subprocess.run(
        [str(VAULT_PROVIDER_PATH), "--self-check"], text=True, capture_output=True, check=False,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}",
             "ATIUS_RUSTDESK_VAULT_BACKEND": str(VAULT_CLIENT_PATH),
             "FAKE_DISPATCHER": str(installed_dispatcher), "FAKE_SUDO_LOG": str(sudo_log)},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["status"] == "PASS"
    assert sudo_log.read_text(encoding="utf-8").split()[1] == "700"


def test_gate_a_third_cycle_controller_pins_remote_drill_recovery_and_contract_digests() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    for required in (
        "live_drill_sha256", "recovery_sha256", "live_drill_contract_sha256",
        "remote-managed-source-digest-drift", "--expected-managed-source-digests",
    ):
        assert required in text


def test_gate_a_third_cycle_action_results_have_exact_action_specific_proofs() -> None:
    recovery_text = RECOVERY_PATH.read_text(encoding="utf-8")
    live_text = LIVE_DRILL_PATH.read_text(encoding="utf-8")
    assert "ACTION_DETAIL_KEYS" in recovery_text
    assert "validate_action_result" in recovery_text
    assert "validate_action_result(action" in live_text
    for proof in ("image_running", "sqlite_ready", "remote_rehash_verified", "retained_rehash_verified"):
        assert proof in recovery_text + live_text


def test_gate_a_third_cycle_partial_failure_persists_and_emits_planned_mutation() -> None:
    text = LIVE_DRILL_PATH.read_text(encoding="utf-8")
    for required in (
        "planned_mutation", "planned_cleanup", "action_journal",
        "failure_mutation", "failure_cleanup_pending",
    ):
        assert required in text
    assert 'state["active_action"] = args.action' in text


def test_gate_a_third_cycle_hbbs_proves_liveness_readiness_and_container_absence() -> None:
    text = LIVE_DRILL_PATH.read_text(encoding="utf-8") + RECOVERY_PATH.read_text(encoding="utf-8")
    for required in (
        "container_running", "hbbs_liveness", "sqlite_readiness",
        "checked_stop_remove", "container_absent",
    ):
        assert required in text


def test_gate_a_third_cycle_rollback_journals_paths_inodes_and_rehashes_retained_backups() -> None:
    text = LIVE_DRILL_PATH.read_text(encoding="utf-8") + RECOVERY_PATH.read_text(encoding="utf-8")
    for required in (
        "artifact_journal", "st_dev", "st_ino", "retained_rehash_verified",
        "remote_delete_performed", "disposable_partial",
    ):
        assert required in text


def test_gate_a_third_cycle_capacity_finalize_uses_canonical_policy_derivation() -> None:
    text = LIVE_DRILL_PATH.read_text(encoding="utf-8")
    for required in (
        "capacity-policy.json", "derive_candidate_capacity", "inode_total",
        "mount_point", "materialized_reservations", "observed_at",
    ):
        assert required in text
    assert "snapshot-a.sqlite3" not in text and "snapshot-b.sqlite3" not in text


def test_gate_a_third_cycle_all_predecessor_stage_mutations_are_globally_rejected() -> None:
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "validate_all_predecessor_mutations" in text
    summary = {
        "selected_candidate": "horistic-srv",
        "attempts": [
            {"candidate": "atius-srv-2", "stages": {
                "supply": {"status": "PASS", "mutation": {"performed": True, "classes": ["unexpected"]}},
                "capacity": {"status": "NO-GO", "mutation": {"performed": False, "classes": []}},
            }},
            {"candidate": "horistic-srv", "stages": {
                "supply": {"status": "PASS", "mutation": {"performed": False, "classes": []}},
                "capacity": {"status": "PASS", "mutation": {"performed": False, "classes": []}},
            }},
        ],
    }
    assert validator.validate_all_predecessor_mutations(summary) == ["predecessor-mutation"]


def test_gate_a_third_cycle_action_history_must_be_an_exact_actions_prefix() -> None:
    spec = importlib.util.spec_from_file_location("phase52_recovery_prefix_test", RECOVERY_PATH)
    assert spec and spec.loader
    recovery = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = recovery
    spec.loader.exec_module(recovery)
    state = recovery.initial_state("b" * 32)
    state["completed_actions"] = ["preflight", "backup"]
    with pytest.raises(recovery.RecoveryBlocked, match="action-history-invalid"):
        recovery.validate_transition("restore", state)


def _load_phase52_live_drill() -> tuple[object, object]:
    recovery_spec = importlib.util.spec_from_file_location("phase52_recovery", RECOVERY_PATH)
    assert recovery_spec and recovery_spec.loader
    recovery = importlib.util.module_from_spec(recovery_spec)
    sys.modules[recovery_spec.name] = recovery
    recovery_spec.loader.exec_module(recovery)
    live_spec = importlib.util.spec_from_file_location("phase52_live_drill_fourth", LIVE_DRILL_PATH)
    assert live_spec and live_spec.loader
    live = importlib.util.module_from_spec(live_spec)
    sys.modules[live_spec.name] = live
    live_spec.loader.exec_module(live)
    return recovery, live


def test_gate_a_hbbs_readiness_waits_for_detached_container_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recovery, _ = _load_phase52_live_drill()
    probes = iter((False, False, True))
    monkeypatch.setattr(recovery, "hbbs_liveness", lambda _name, _state: next(probes))
    monkeypatch.setattr(recovery.time, "sleep", lambda _seconds: None)
    assert recovery.wait_hbbs_liveness("fixture", tmp_path, timeout_seconds=1.0)
    monkeypatch.setattr(recovery, "hbbs_liveness", lambda _name, _state: False)
    assert not recovery.wait_hbbs_liveness("fixture", tmp_path, timeout_seconds=0.0)


def test_gate_a_hbbs_sqlite_mode_is_normalized_only_after_exact_identity_checks(
    tmp_path: Path,
) -> None:
    recovery, _ = _load_phase52_live_drill()
    database = tmp_path / "db_v2.sqlite3"
    database.write_bytes(b"sqlite-fixture")
    database.chmod(0o644)
    recovery.normalize_hbbs_sqlite(database)
    assert stat.S_IMODE(database.stat().st_mode) == 0o600

    database.chmod(0o666)
    with pytest.raises(recovery.RecoveryBlocked, match="file-owner-mode-invalid"):
        recovery.normalize_hbbs_sqlite(database)

    database.chmod(0o600)
    hardlink = tmp_path / "db-hardlink"
    os.link(database, hardlink)
    with pytest.raises(recovery.RecoveryBlocked, match="file-owner-mode-invalid"):
        recovery.normalize_hbbs_sqlite(database)


def test_gate_a_fourth_cycle_managed_source_verifier_checks_every_pin(tmp_path: Path) -> None:
    recovery, live = _load_phase52_live_drill()
    with pytest.raises(recovery.RecoveryBlocked, match="remote-managed-source-digest-drift"):
        live.verify_managed_source_digests(
            json.dumps({"live_drill_sha256": "0" * 64}), dry_run=False
        )
    repo = LIVE_DRILL_PATH.resolve().parents[3]
    paths = {
        "live_drill_sha256": LIVE_DRILL_PATH,
        "recovery_sha256": RECOVERY_PATH,
        "live_drill_contract_sha256": LIVE_DRILL_CONTRACT_PATH,
        "validator_sha256": MODULE_PATH,
        "capacity_policy_sha256": CAPACITY_POLICY_PATH,
        "provider_sha256": VAULT_PROVIDER_PATH,
        "client_sha256": VAULT_CLIENT_PATH,
        "rclone_hydrate_sha256": repo / "modules/fleet-backup/scripts/atius-rclone-vault-hydrate",
        "rclone_copy_sha256": repo / "modules/fleet-backup/scripts/rclone-copy-verified-phase52.sh",
        "rclone_fetch_sha256": repo / "modules/fleet-backup/scripts/rclone-fetch-verified-phase52.sh",
    }
    exact = {key: __import__("hashlib").sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}
    live.verify_managed_source_digests(json.dumps(exact), dry_run=True)


def test_gate_a_fourth_cycle_action_specific_value_invariants_are_executable() -> None:
    recovery, _ = _load_phase52_live_drill()
    digest = "a" * 64
    tx = "b" * 32
    manifest = {
        "schema": recovery.BACKUP_SCHEMA,
        "transaction_id": tx,
        "label": "A",
        "generation_id": "c" * 32,
        "source_snapshot_sha256": digest,
        "archive_sha256": digest,
        "member_sha256": digest,
        "size_bytes": 10240,
        "entries": ["db_v2.sqlite3"],
        "mode": "0600",
        "secret_material_present": False,
        "destination_class": "candidate-local",
    }
    backup_b = {
        **manifest,
        "label": "B",
        "generation_id": "d" * 32,
        "destination_class": "modules/fleet-backup:gdrive",
        "remote_object": f"giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/phase52/backup-b/{tx}.tar",
        "local_sha256": digest,
        "remote_sha256": digest,
        "retention": {
            "retain_until": "phase57-pass-plus-30-days",
            "deletion_requires_new_explicit_approval": True,
        },
    }
    valid = {
        "preflight": {"image": recovery.IMMUTABLE_HBBS, "image_running": False, "network_mode": "none", "published_ports": []},
        "vault": {"reference_count": 7, "provider_api": "references-v1", "public_fingerprint": digest},
        "backup": {"backup_a": manifest, "backup_b": backup_b, "state_only": ["db_v2.sqlite3"], "remote_rehash_verified": True, "sqlite_ready": True},
        "restore": {"sqlite_integrity": "ok", "sqlite_ready": True, "public_fingerprint": digest, "image": recovery.IMMUTABLE_HBBS, "image_running": True, "network_mode": "none", "port_bindings": {}, "public_listener_delta": []},
        "capacity-finalize": {"capacity": {"status": "PASS", "capacity_finalize_status": "PASS", "pre_disk_ok": True, "inode_ok": True, "projected_post_ok": True, "headroom_ok": True}, "actual_backup_a_bytes": 10240, "actual_backup_b_bytes": 10240},
        "rollback": {"terminal": True, "retained_artifacts": list(recovery.RETAINED), "cleanup_pending": [], "retained_rehash_verified": True, "remote_rehash_verified": True, "remote_delete_performed": False},
    }
    for action, details in valid.items():
        recovery.validate_action_result(action, details)
        invalid = copy.deepcopy(details)
        key = next(iter(invalid))
        invalid[key] = None
        with pytest.raises(recovery.RecoveryBlocked, match="action-result-value-invalid"):
            recovery.validate_action_result(action, invalid)
    values = {
        "kv/atius/rustdesk/server#private_key": base64.b64encode(b"p" * 64).decode(),
        "kv/atius/rustdesk/server#public_key": base64.b64encode(b"u" * 32).decode(),
        **{
            f"kv/atius/rustdesk/targets/{host}#permanent_password": "R" + str(index) * 31
            for index, host in enumerate(
                ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv", "giovanni-w11-pc"),
                start=1,
            )
        },
    }
    assert len(recovery.validate_vault_values(values)) == 64
    invalid_values = dict(values)
    invalid_values["kv/atius/rustdesk/targets/atius-srv-2#permanent_password"] = invalid_values[
        "kv/atius/rustdesk/targets/atius-srv-1#permanent_password"
    ]
    with pytest.raises(recovery.RecoveryBlocked, match="vault-password-contract-invalid"):
        recovery.validate_vault_values(invalid_values)


def test_gate_a_fourth_cycle_capacity_import_executes_and_pre_manifest_inventory_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recovery, live = _load_phase52_live_drill()
    monkeypatch.setenv("HOME", str(tmp_path))
    transaction_id = "e" * 32
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    retained = tmp_path / ".local/share/atius-rustdesk-phase52" / transaction_id
    retained.mkdir(parents=True, mode=0o700)
    (retained / "backup-a.tar").write_bytes(b"a" * 10240)
    (retained / "backup-b.tar").write_bytes(b"b" * 10240)
    state = recovery.initial_state(transaction_id)
    live.journal_artifact(root, state, retained, disposable=False)
    with pytest.raises(recovery.RecoveryBlocked, match="capacity-finalize-nogo"):
        live.direct_action("capacity-finalize", root, state, False)
    with pytest.raises(recovery.RecoveryBlocked, match="rollback-artifact-journal-missing"):
        live.direct_action("rollback", root, state, False)
    assert (retained / "backup-a.tar").is_file()
    assert (retained / "backup-b.tar").is_file()


def test_gate_a_fourth_cycle_action_details_survive_candidate_evidence() -> None:
    details = {"remote_rehash_verified": True, "retained_rehash_verified": True}
    stage = validator._stage_record(
        "horistic-srv",
        "backup",
        {"status": "PASS", "action_details": details, "mutation": {"performed": False, "classes": []}},
    )
    attempt = {"candidate": "horistic-srv", "stages": {"backup": stage}}
    evidence = validator._candidate_evidence(attempt, "2026-07-22T09:00:00Z")
    assert evidence["stages"]["backup"]["action_details"] == details


def test_gate_a_fourth_cycle_mutation_journal_records_observed_writes_before_failure(
    tmp_path: Path
) -> None:
    recovery, live = _load_phase52_live_drill()
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    state = recovery.initial_state("f" * 32)
    live.observe_mutation(root, state, "ephemeral-vault-hydration", ["ephemeral-identity"])
    live.observe_mutation(root, state, "redacted-evidence-write", ["disposable-partial"])
    observed = live.observed_mutation(state)
    assert observed["performed"] is True
    assert observed["classes"] == ["ephemeral-vault-hydration", "redacted-evidence-write"]
    assert observed["cleanup_pending"] == ["ephemeral-identity", "disposable-partial"]
    assert [row["status"] for row in state["action_journal"]] == ["mutation-observed", "mutation-observed"]


def test_gate_a_fourth_cycle_predecessor_shape_is_exact() -> None:
    summary = {
        "selected_candidate": "horistic-srv",
        "attempts": [
            {"candidate": "atius-srv-2", "stages": {"capacity": {"status": "NO-GO"}}},
            {"candidate": "horistic-srv", "stages": {}},
        ],
    }
    assert validator.validate_all_predecessor_mutations(summary) == ["predecessor-mutation"]


def test_gate_a_fourth_cycle_backend_rejects_non_0600_profile(tmp_path: Path) -> None:
    profile_root = tmp_path / "profiles"
    profile_root.mkdir(mode=0o700)
    reference = {"vault_path": "kv/atius/rustdesk/server", "field": "public_key"}
    profile = profile_root / "rustdesk-phase52-v1.json"
    profile.write_text(json.dumps({"protocol": "rustdesk-phase52-v1", "references": [reference]}), encoding="utf-8")
    profile.chmod(0o640)
    fake_vault = tmp_path / "atius-vault"
    fake_vault.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    fake_vault.chmod(0o700)
    completed = subprocess.run(
        [str(VAULT_CONTROL_BACKEND_PATH), "rustdesk-phase52-v1"],
        input=json.dumps({"protocol": "rustdesk-phase52-v1", "references": [reference]}).encode(),
        capture_output=True,
        check=False,
        env={**os.environ, "ATIUS_PHASE52_PROFILE_ROOT": str(profile_root), "ATIUS_PHASE52_VAULT_BIN": str(fake_vault)},
    )
    assert completed.returncode == 2
    assert completed.stdout == completed.stderr == b""


def test_gate_a_fourth_cycle_requires_exact_legacy_forced_command_and_options(tmp_path: Path) -> None:
    root = tmp_path / "root"
    ssh_dir = root / "home/ubuntu/.ssh"
    ssh_dir.mkdir(parents=True, mode=0o700)
    key = tmp_path / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    public = key.with_suffix(".pub")
    key_type, blob, comment = public.read_text().strip().split(maxsplit=2)
    authorized = ssh_dir / "authorized_keys"
    authorized.write_text(f'command="/home/ubuntu/.local/bin/atius-vault-export-ssh",no-port-forwarding {key_type} {blob} {comment}\n')
    authorized.chmod(0o600)
    fingerprint = subprocess.run(["ssh-keygen", "-lf", str(public), "-E", "sha256"], text=True, capture_output=True, check=True).stdout.split()[1]
    completed = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--install", "--dry-run", "--root", str(root), "--authorized-key-file", str(public), "--expected-fingerprint", fingerprint],
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 2
    assert "legacy-authorized-key-policy-drift" in completed.stderr


@pytest.mark.parametrize("interruption", ["provider-target", "client-target"])
def test_gate_a_fourth_cycle_provider_client_recovers_after_either_target(
    tmp_path: Path, interruption: str
) -> None:
    home = tmp_path / interruption
    home.mkdir(mode=0o700)
    env = {**os.environ, "HOME": str(home), "ATIUS_RUSTDESK_INSTALLER_TEST_INTERRUPT_AFTER": interruption}
    interrupted = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(home)],
        env=env, text=True, capture_output=True, check=False,
    )
    assert interrupted.returncode == 75
    recovered = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(home)],
        env={**os.environ, "HOME": str(home)}, text=True, capture_output=True, check=False,
    )
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert (home / ".local/bin/rustdesk-vault-provider").read_bytes() == VAULT_PROVIDER_PATH.read_bytes()
    assert (home / ".local/bin/atius-vault-phase52-client").read_bytes() == VAULT_CLIENT_PATH.read_bytes()
    interrupted_rollback = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--rollback", "--home", str(home)],
        env=env, text=True, capture_output=True, check=False,
    )
    assert interrupted_rollback.returncode == 75
    recovered_rollback = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--rollback", "--home", str(home)],
        env={**os.environ, "HOME": str(home)}, text=True, capture_output=True, check=False,
    )
    assert recovered_rollback.returncode == 0, recovered_rollback.stdout + recovered_rollback.stderr
    assert not (home / ".local/bin/rustdesk-vault-provider").exists()
    assert not (home / ".local/bin/atius-vault-phase52-client").exists()


def test_gate_a_fourth_cycle_control_plane_rejects_lock_and_installed_identity_drift(
    tmp_path: Path
) -> None:
    root = tmp_path / "root"
    ssh_dir = root / "home/ubuntu/.ssh"
    ssh_dir.mkdir(parents=True, mode=0o700)
    key = tmp_path / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    public = key.with_suffix(".pub")
    key_type, blob, comment = public.read_text().strip().split(maxsplit=2)
    authorized = ssh_dir / "authorized_keys"
    authorized.write_text(
        f'command="/home/ubuntu/.local/bin/atius-vault-export-ssh",no-agent-forwarding,no-X11-forwarding,no-pty,no-port-forwarding {key_type} {blob} {comment}\n'
    )
    authorized.chmod(0o600)
    legacy = root / "home/ubuntu/.local/bin/atius-vault-export-ssh"
    legacy.parent.mkdir(parents=True, mode=0o700)
    legacy.write_text("#!/bin/sh\nexit 0\n"); legacy.chmod(0o755)
    fingerprint = subprocess.run(["ssh-keygen", "-lf", str(public), "-E", "sha256"], text=True, capture_output=True, check=True).stdout.split()[1]
    install = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--install", "--root", str(root), "--authorized-key-file", str(public), "--expected-fingerprint", fingerprint],
        text=True, capture_output=True, check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    lock = root / "var/lib/atius-vault-phase52/control-plane-global.lock"
    lock.chmod(0o644)
    rollback = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--rollback", "--root", str(root)],
        text=True, capture_output=True, check=False,
    )
    assert rollback.returncode == 2
    assert "control-plane-lock-identity-drift" in rollback.stderr
    lock.chmod(0o600)
    backend = root / "usr/local/sbin/atius-vault-export-rustdesk-phase52"
    backend.chmod(0o755)
    rollback = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--rollback", "--root", str(root)],
        text=True, capture_output=True, check=False,
    )
    assert rollback.returncode == 2
    assert "installed-target-identity-drift" in rollback.stderr
    backend.chmod(0o700)
    state_dir = root / "var/lib/atius-vault-phase52"
    state_dir.chmod(0o755)
    rollback = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--rollback", "--root", str(root)],
        text=True, capture_output=True, check=False,
    )
    assert rollback.returncode == 2
    assert "control-plane-state-identity-drift" in rollback.stderr
    state_dir.chmod(0o700)
    manifest = state_dir / "install-state.json"
    manifest_alias = state_dir / "install-state.alias"
    os.link(manifest, manifest_alias)
    rollback = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--rollback", "--root", str(root)],
        text=True, capture_output=True, check=False,
    )
    assert rollback.returncode == 2
    assert "control-plane-manifest-identity-drift" in rollback.stderr


def test_gate_a_fourth_cycle_controller_streaming_bound_kills_process_group(tmp_path: Path) -> None:
    script = tmp_path / "overflow.py"
    pid_file = tmp_path / "child.pid"
    script.write_text(
        "import pathlib,subprocess,sys,time\n"
        "child=subprocess.Popen(['sleep','60'])\n"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
        "sys.stdout.write('x'*200000); sys.stdout.flush(); time.sleep(60)\n",
        encoding="utf-8",
    )
    with pytest.raises((OverflowError, TimeoutError)):
        validator._run_bounded_text_command(
            [sys.executable, str(script), str(pid_file)], timeout=2, stdout_limit=1024, stderr_limit=1024
        )
    child_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        os.kill(child_pid, signal.SIGKILL)
        pytest.fail("bounded controller left a descendant alive")


def _phase52_control_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "root"
    ssh_dir = root / "home/ubuntu/.ssh"
    ssh_dir.mkdir(parents=True, mode=0o700)
    key = tmp_path / "transport"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    public = key.with_suffix(".pub")
    key_type, blob, comment = public.read_text().strip().split(maxsplit=2)
    authorized = ssh_dir / "authorized_keys"
    authorized.write_text(
        f'command="/home/ubuntu/.local/bin/atius-vault-export-ssh",no-agent-forwarding,no-X11-forwarding,no-pty,no-port-forwarding {key_type} {blob} {comment}\n'
    )
    authorized.chmod(0o600)
    legacy = root / "home/ubuntu/.local/bin/atius-vault-export-ssh"
    legacy.parent.mkdir(parents=True, mode=0o700)
    legacy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    legacy.chmod(0o755)
    fingerprint = subprocess.run(
        ["ssh-keygen", "-lf", str(public), "-E", "sha256"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.split()[1]
    return root, public, fingerprint


def _run_control_install(root: Path, public: Path, fingerprint: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(VAULT_CONTROL_INSTALLER_PATH), "--install", "--root", str(root),
            "--authorized-key-file", str(public), "--expected-fingerprint", fingerprint,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_gate_a_fifth_cycle_provider_recovery_rejects_installed_hash_with_wrong_mode(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    env = {**os.environ, "HOME": str(home)}
    interrupted = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(home)],
        env={**env, "ATIUS_RUSTDESK_INSTALLER_TEST_INTERRUPT_AFTER": "client-target"},
        text=True, capture_output=True, check=False,
    )
    assert interrupted.returncode == 75
    provider = home / ".local/bin/rustdesk-vault-provider"
    provider.chmod(0o600)
    recovered = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(home)],
        env=env, text=True, capture_output=True, check=False,
    )
    assert recovered.returncode == 2
    assert "provider install recovery mode drift" in recovered.stderr


def test_gate_a_fifth_cycle_requested_rollback_aborts_interrupted_install(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    env = {**os.environ, "HOME": str(home)}
    interrupted = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--install", "--home", str(home)],
        env={**env, "ATIUS_RUSTDESK_INSTALLER_TEST_INTERRUPT_AFTER": "provider-target"},
        text=True, capture_output=True, check=False,
    )
    assert interrupted.returncode == 75
    rollback = subprocess.run(
        [str(VAULT_PROVIDER_INSTALLER_PATH), "--rollback", "--home", str(home)],
        env=env, text=True, capture_output=True, check=False,
    )
    assert rollback.returncode == 0, rollback.stdout + rollback.stderr
    assert json.loads(rollback.stdout)["action"] == "rollback"
    assert not (home / ".local/bin/rustdesk-vault-provider").exists()
    assert not (home / ".local/bin/atius-vault-phase52-client").exists()


def test_gate_a_fifth_cycle_control_rollback_prevalidates_missing_target_without_partial_restore(
    tmp_path: Path,
) -> None:
    root, public, fingerprint = _phase52_control_fixture(tmp_path)
    installed = _run_control_install(root, public, fingerprint)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    backend = root / "usr/local/sbin/atius-vault-export-rustdesk-phase52"
    dispatcher = root / "usr/local/sbin/atius-vault-export-ssh-phase52"
    dispatcher_before = dispatcher.read_bytes()
    backend.unlink()
    rollback = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--rollback", "--root", str(root)],
        text=True, capture_output=True, check=False,
    )
    assert rollback.returncode == 2
    assert "installed-target-missing" in rollback.stderr
    assert dispatcher.read_bytes() == dispatcher_before


def test_gate_a_fifth_cycle_control_recovers_installing_manifest(tmp_path: Path) -> None:
    root, public, fingerprint = _phase52_control_fixture(tmp_path)
    installed = _run_control_install(root, public, fingerprint)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    manifest = root / "var/lib/atius-vault-phase52/install-state.json"
    payload = json.loads(manifest.read_text())
    payload["status"] = "installing"
    manifest.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    manifest.chmod(0o600)
    recovered = _run_control_install(root, public, fingerprint)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert json.loads(manifest.read_text())["status"] == "installed"


def test_gate_a_fifth_cycle_control_atomic_rejects_ancestor_symlink_before_mkdir(tmp_path: Path) -> None:
    root, public, fingerprint = _phase52_control_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    (root / "etc").symlink_to(outside, target_is_directory=True)
    installed = _run_control_install(root, public, fingerprint)
    assert installed.returncode == 2
    assert "parent-chain-drift" in installed.stderr
    assert list(outside.rglob("*")) == []


def test_gate_a_fifth_cycle_container_absence_is_exact_and_cleanup_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recovery, _ = _load_phase52_live_drill()
    responses = iter([(125, b"", b"transport-error")])
    monkeypatch.setattr(recovery, "bounded_process", lambda *args, **kwargs: next(responses))
    with pytest.raises(recovery.RecoveryBlocked, match="container-exists-check-failed"):
        recovery.checked_stop_remove("fixture")
    responses = iter([(1, b"", b"")])
    monkeypatch.setattr(recovery, "bounded_process", lambda *args, **kwargs: next(responses))
    recovery.checked_stop_remove("fixture")
    responses = iter([(0, b"", b""), (0, b"", b""), (0, b"", b""), (1, b"", b"")])
    monkeypatch.setattr(recovery, "bounded_process", lambda *args, **kwargs: next(responses))
    recovery.checked_stop_remove("fixture")


def test_gate_a_fifth_cycle_rollback_without_manifest_preserves_unresolved_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recovery, live = _load_phase52_live_drill()
    monkeypatch.setenv("HOME", str(tmp_path))
    transaction_id = "9" * 32
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    (root / "sqlite-a.work").write_bytes(b"partial")
    retained = tmp_path / ".local/share/atius-rustdesk-phase52" / transaction_id
    retained.mkdir(parents=True, mode=0o700)
    (retained / "backup-a.tar").write_bytes(b"partial")
    state = recovery.initial_state(transaction_id)
    live.journal_artifact(root, state, root / "sqlite-a.work", disposable=True)
    live.journal_artifact(root, state, retained, disposable=False)
    with pytest.raises(recovery.RecoveryBlocked, match="rollback-artifact-journal-missing"):
        live.direct_action("rollback", root, state, False)
    assert (root / "sqlite-a.work").is_file()
    assert (retained / "backup-a.tar").is_file()


def test_gate_a_fifth_cycle_dry_run_uses_live_action_schemas(tmp_path: Path) -> None:
    recovery, live = _load_phase52_live_drill()
    for action in recovery.ACTIONS:
        details, mutation = live.direct_action(action, tmp_path, recovery.initial_state("8" * 32), True)
        recovery.validate_action_result(action, details)
        recovery.validate_mutation(mutation)


def test_gate_a_fifth_cycle_mutation_semantics_reject_false_types_and_empty_classes() -> None:
    recovery, _ = _load_phase52_live_drill()
    invalid = (
        {"performed": "false", "classes": [], "cleanup_pending": [], "retained_artifacts": list(recovery.RETAINED)},
        {"performed": True, "classes": [], "cleanup_pending": [], "retained_artifacts": list(recovery.RETAINED)},
        {"performed": False, "classes": ["not-approved"], "cleanup_pending": [], "retained_artifacts": list(recovery.RETAINED)},
    )
    for mutation in invalid:
        with pytest.raises(recovery.RecoveryBlocked):
            recovery.validate_mutation(mutation)


def test_gate_a_fifth_cycle_controller_rejects_pass_with_invalid_action_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "schema": "phase52-live-drill-result-v2",
        "transaction_id": "7" * 32,
        "action": "preflight",
        "status": "PASS",
        "details": {"image": "lookalike"},
        "mutation": {"performed": False, "classes": [], "cleanup_pending": [], "retained_artifacts": ["backup-a", "backup-b-local", "backup-b-remote"]},
        "secret_material_present": False,
    }
    monkeypatch.setattr(
        validator,
        "_run_bounded_text_command",
        lambda *args, **kwargs: (0, json.dumps(payload), ""),
    )
    with pytest.raises(ValueError, match="live-drill action details invalid"):
        validator.run_live_drill_action("horistic-srv", "preflight", "/dev/shm/phase52-fixture")


def test_gate_a_fifth_cycle_managed_pins_include_installed_executables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recovery, live = _load_phase52_live_drill()
    home = tmp_path / "home"
    bin_dir = home / ".local/bin"
    bin_dir.mkdir(parents=True, mode=0o700)
    installed = {
        "provider_sha256": VAULT_PROVIDER_PATH,
        "client_sha256": VAULT_CLIENT_PATH,
        "rclone_hydrate_sha256": REPO / "modules/fleet-backup/scripts/atius-rclone-vault-hydrate",
        "rclone_copy_sha256": REPO / "modules/fleet-backup/scripts/rclone-copy-verified-phase52.sh",
        "rclone_fetch_sha256": REPO / "modules/fleet-backup/scripts/rclone-fetch-verified-phase52.sh",
    }
    names = {
        "provider_sha256": "rustdesk-vault-provider",
        "client_sha256": "atius-vault-phase52-client",
        "rclone_hydrate_sha256": "atius-rclone-vault-hydrate",
        "rclone_copy_sha256": "rclone-copy-verified-phase52",
        "rclone_fetch_sha256": "rclone-fetch-verified-phase52",
    }
    for key, source in installed.items():
        shutil.copy2(source, bin_dir / names[key])
        (bin_dir / names[key]).chmod(0o700)
    repo = LIVE_DRILL_PATH.resolve().parents[3]
    paths = {
        "live_drill_sha256": LIVE_DRILL_PATH,
        "recovery_sha256": RECOVERY_PATH,
        "live_drill_contract_sha256": LIVE_DRILL_CONTRACT_PATH,
        "validator_sha256": MODULE_PATH,
        "capacity_policy_sha256": CAPACITY_POLICY_PATH,
        "provider_sha256": VAULT_PROVIDER_PATH,
        "client_sha256": VAULT_CLIENT_PATH,
        "rclone_hydrate_sha256": repo / "modules/fleet-backup/scripts/atius-rclone-vault-hydrate",
        "rclone_copy_sha256": repo / "modules/fleet-backup/scripts/rclone-copy-verified-phase52.sh",
        "rclone_fetch_sha256": repo / "modules/fleet-backup/scripts/rclone-fetch-verified-phase52.sh",
    }
    exact = {key: __import__("hashlib").sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}
    monkeypatch.setenv("HOME", str(home))
    live.verify_managed_source_digests(json.dumps(exact), dry_run=False)
    (bin_dir / names["provider_sha256"]).write_text("drift\n")
    with pytest.raises(recovery.RecoveryBlocked, match="installed-managed-source-digest-drift"):
        live.verify_managed_source_digests(json.dumps(exact), dry_run=False)


def test_gate_a_sixth_cycle_remote_create_without_manifest_blocks_and_preserves_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recovery, live = _load_phase52_live_drill()
    monkeypatch.setenv("HOME", str(tmp_path))
    transaction_id = "1" * 32
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    retained = tmp_path / ".local/share/atius-rustdesk-phase52" / transaction_id
    retained.mkdir(parents=True, mode=0o700)
    (retained / "backup-b.tar").write_bytes(b"remote-copy-source")
    state = recovery.initial_state(transaction_id)
    live.journal_artifact(root, state, retained, disposable=False)
    state["observed_mutation"] = recovery.mutation(
        True, ["state-only-backup-b-remote-create"]
    )
    with pytest.raises(recovery.RecoveryBlocked, match="remote-object-inventory-missing"):
        live.direct_action("rollback", root, state, False)
    assert retained.is_dir()
    assert (retained / "backup-b.tar").is_file()
    destination = (
        "giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/"
        f"phase52/backup-b/{transaction_id}.tar"
    )
    intent = live.persist_remote_object_intent(
        retained, transaction_id, destination, "a" * 64, 10240, verified=False
    )
    assert intent == live.load_remote_object_intent(retained, transaction_id)
    assert intent["status"] == "copy-planned"
    with pytest.raises(recovery.RecoveryBlocked, match="remote-object-intent-unresolved"):
        live.direct_action("rollback", root, state, False)
    assert retained.is_dir()


def test_gate_a_sixth_cycle_terminal_rollback_emits_full_valid_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recovery, live = _load_phase52_live_drill()
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    state = recovery.initial_state("2" * 32)
    rollback_details = {
        "terminal": True,
        "retained_artifacts": [],
        "cleanup_pending": [],
        "retained_rehash_verified": False,
        "remote_rehash_verified": False,
        "remote_delete_performed": False,
    }
    state["facts"] = {"rollback": rollback_details}
    state["retained_artifacts"] = []
    state = recovery.rollback_state(state)
    live.atomic_state(root, state)
    monkeypatch.setattr(live, "tmpfs_owned", lambda _path: None)
    monkeypatch.setattr(live, "verify_managed_source_digests", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(LIVE_DRILL_PATH), "--action", "rollback", "--transaction-dir", str(root)],
    )
    assert live.main() == 0
    payload = json.loads(capsys.readouterr().out)
    recovery.validate_action_result("rollback", payload["details"])


def test_gate_a_sixth_cycle_mutation_false_rejects_observed_or_pending_work() -> None:
    recovery, _ = _load_phase52_live_drill()
    invalid = (
        recovery.mutation(False, []) | {"classes": ["redacted-evidence-write"]},
        recovery.mutation(False, []) | {"cleanup_pending": ["disposable-partial"]},
    )
    for mutation in invalid:
        with pytest.raises(recovery.RecoveryBlocked, match="mutation-false-contradiction"):
            recovery.validate_mutation(mutation)


def test_gate_a_sixth_cycle_installing_manifest_never_blesses_wrong_mode(
    tmp_path: Path,
) -> None:
    root, public, fingerprint = _phase52_control_fixture(tmp_path)
    installed = _run_control_install(root, public, fingerprint)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    manifest = root / "var/lib/atius-vault-phase52/install-state.json"
    payload = json.loads(manifest.read_text())
    payload["status"] = "installing"
    payload["targets"]["backend"]["installed_identity"] = None
    manifest.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    manifest.chmod(0o600)
    backend = root / "usr/local/sbin/atius-vault-export-rustdesk-phase52"
    backend.chmod(0o777)
    recovered = _run_control_install(root, public, fingerprint)
    assert recovered.returncode == 2
    assert "installed-target-identity-drift" in recovered.stderr
    assert stat.S_IMODE(backend.stat().st_mode) == 0o777


def test_gate_a_sixth_cycle_rollback_recovers_installing_manifest(
    tmp_path: Path,
) -> None:
    root, public, fingerprint = _phase52_control_fixture(tmp_path)
    installed = _run_control_install(root, public, fingerprint)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    manifest = root / "var/lib/atius-vault-phase52/install-state.json"
    payload = json.loads(manifest.read_text())
    payload["status"] = "installing"
    manifest.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    manifest.chmod(0o600)
    rollback = subprocess.run(
        [str(VAULT_CONTROL_INSTALLER_PATH), "--rollback", "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert rollback.returncode == 0, rollback.stdout + rollback.stderr
    assert not (root / "var/lib/atius-vault-phase52").exists()
    assert not (root / "usr/local/sbin/atius-vault-export-rustdesk-phase52").exists()
    assert "command=\"/home/ubuntu/.local/bin/atius-vault-export-ssh\"" in (
        root / "home/ubuntu/.ssh/authorized_keys"
    ).read_text()


def test_gate_a_sixth_cycle_partial_retained_cleanup_rejects_inode_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recovery, live = _load_phase52_live_drill()
    monkeypatch.setenv("HOME", str(tmp_path))
    transaction_id = "3" * 32
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    retained = tmp_path / ".local/share/atius-rustdesk-phase52" / transaction_id
    retained.mkdir(parents=True, mode=0o700)
    state = recovery.initial_state(transaction_id)
    live.journal_artifact(root, state, retained, disposable=False)
    retained.rename(retained.with_name(retained.name + ".original"))
    retained.mkdir(mode=0o700)
    (retained / "replacement").write_text("must-survive\n", encoding="utf-8")
    with pytest.raises(recovery.RecoveryBlocked, match="rollback-artifact-identity-drift"):
        live.direct_action("rollback", root, state, False)
    assert (retained / "replacement").read_text(encoding="utf-8") == "must-survive\n"


def _gate_a_seventh_rollback_fixture(
    tmp_path: Path,
) -> tuple[object, object, Path, dict[str, object], Path, dict[str, object]]:
    recovery, live = _load_phase52_live_drill()
    transaction_id = "4" * 32
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    retained = tmp_path / ".local/share/atius-rustdesk-phase52" / transaction_id
    retained.mkdir(parents=True, mode=0o700)
    archive_a = retained / "backup-a.tar"
    archive_b = retained / "backup-b.tar"
    member_payload = b"phase52-sqlite-state"
    snapshot = root / "fixture.sqlite3"
    snapshot.write_bytes(member_payload)
    snapshot.chmod(0o600)
    generated_a = recovery.state_archive(
        snapshot, archive_a, label="A", transaction_id=transaction_id
    )
    generated_b = recovery.state_archive(
        snapshot, archive_b, label="B", transaction_id=transaction_id
    )
    snapshot.unlink()
    digest_a = generated_a["archive_sha256"]
    digest_b = generated_b["archive_sha256"]
    dry_details, _ = recovery.dry_run_details("backup", root)
    manifest_a = copy.deepcopy(dry_details["backup_a"])
    manifest_b = copy.deepcopy(dry_details["backup_b"])
    member_digest = __import__("hashlib").sha256(member_payload).hexdigest()
    for manifest, generated in (
        (manifest_a, generated_a),
        (manifest_b, generated_b),
    ):
        manifest["transaction_id"] = transaction_id
        for field in (
            "generation_id", "source_snapshot_sha256", "member_sha256",
            "archive_sha256", "size_bytes",
        ):
            manifest[field] = generated[field]
    destination = (
        "giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/"
        f"phase52/backup-b/{transaction_id}.tar"
    )
    manifest_b.update(
        {
            "remote_object": destination,
            "local_sha256": digest_b,
            "remote_sha256": digest_b,
        }
    )
    manifests = {"A": manifest_a, "B": manifest_b}
    live.atomic_json(retained / "backup-manifests.json", manifests)
    live.persist_remote_object_intent(
        retained, transaction_id, destination, digest_b,
        archive_b.stat().st_size, verified=True,
    )
    state = recovery.initial_state(transaction_id)
    live.journal_artifact(root, state, retained, disposable=False)
    live.journal_artifact(root, state, archive_a, disposable=False)
    live.journal_artifact(root, state, archive_b, disposable=False)
    return recovery, live, root, state, retained, manifests


def test_gate_a_seventh_cycle_retained_tar_rehash_rejects_byte_identical_inode_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    archive = retained / "backup-a.tar"
    original = root / "backup-a.original"
    archive.rename(original)
    archive.write_bytes(original.read_bytes())
    archive.chmod(0o600)
    monkeypatch.setattr(
        recovery,
        "bounded_process",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("remote fetch reached")),
    )
    with pytest.raises(recovery.RecoveryBlocked, match="rollback-artifact-identity-drift"):
        live.direct_action("rollback", root, state, False)
    assert archive.read_bytes() == original.read_bytes()


def test_gate_a_seventh_cycle_manifest_reconciles_copy_verified_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    intent_path = retained / live.REMOTE_INTENT_FILE
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    intent["size_bytes"] += 1
    live.atomic_json(intent_path, intent)
    monkeypatch.setattr(
        recovery,
        "bounded_process",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("remote fetch reached")),
    )
    with pytest.raises(recovery.RecoveryBlocked, match="remote-object-intent-manifest-drift"):
        live.direct_action("rollback", root, state, False)


def test_gate_a_seventh_cycle_backup_manifest_schema_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    manifests["unexpected"] = {"accepted": False}
    live.atomic_json(retained / "backup-manifests.json", manifests)
    monkeypatch.setattr(
        recovery,
        "bounded_process",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("remote fetch reached")),
    )
    with pytest.raises(recovery.RecoveryBlocked, match="backup-manifest-schema-invalid"):
        live.direct_action("rollback", root, state, False)


def _gate_a_block_remote_fetch(
    recovery: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        recovery,
        "bounded_process",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("remote fetch reached")),
    )


def test_gate_a_eighth_cycle_tar_size_must_match_manifest_before_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    manifests["A"]["size_bytes"] += 1
    manifests["B"]["size_bytes"] += 1
    live.atomic_json(retained / "backup-manifests.json", manifests)
    intent_path = retained / live.REMOTE_INTENT_FILE
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    intent["size_bytes"] += 1
    live.atomic_json(intent_path, intent)
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="retained-backup-size-drift"):
        live.direct_action("rollback", root, state, False)


def test_gate_a_eighth_cycle_integer_schema_rejects_bool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    manifests["B"]["size_bytes"] = True
    live.atomic_json(retained / "backup-manifests.json", manifests)
    intent_path = retained / live.REMOTE_INTENT_FILE
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    intent["size_bytes"] = True
    live.atomic_json(intent_path, intent)
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="backup-manifest-schema-invalid"):
        live.direct_action("rollback", root, state, False)


def test_gate_a_eighth_cycle_json_loaders_reject_duplicate_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, _, _, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    manifest_path = retained / "backup-manifests.json"
    duplicate_manifest = (
        '{"A":' + json.dumps(manifests["A"], separators=(",", ":"))
        + ',"A":' + json.dumps(manifests["A"], separators=(",", ":"))
        + ',"B":' + json.dumps(manifests["B"], separators=(",", ":")) + '}\n'
    )
    manifest_path.write_text(duplicate_manifest, encoding="utf-8")
    manifest_path.chmod(0o600)
    with pytest.raises(recovery.RecoveryBlocked, match="backup-manifest-schema-invalid"):
        live.load_reconciled_backup_manifests(retained, "4" * 32)
    live.atomic_json(manifest_path, manifests)
    intent_path = retained / live.REMOTE_INTENT_FILE
    raw_intent = intent_path.read_text(encoding="utf-8").replace(
        '"status":"copy-verified"',
        '"status":"copy-planned","status":"copy-verified"',
    )
    intent_path.write_text(raw_intent, encoding="utf-8")
    intent_path.chmod(0o600)
    with pytest.raises(recovery.RecoveryBlocked, match="remote-object-inventory-invalid"):
        live.load_reconciled_backup_manifests(retained, "4" * 32)


def test_gate_a_eighth_cycle_retention_requires_exact_bool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    intent_path = retained / live.REMOTE_INTENT_FILE
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    intent["retention"]["deletion_requires_new_explicit_approval"] = 1
    live.atomic_json(intent_path, intent)
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="remote-object-inventory-invalid"):
        live.direct_action("rollback", root, state, False)


@pytest.mark.parametrize("variant", ["source-snapshot", "generation-id"])
def test_gate_a_eighth_cycle_backup_pair_invariants_are_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    if variant == "source-snapshot":
        manifests["B"]["source_snapshot_sha256"] = "f" * 64
        manifests["B"]["member_sha256"] = "f" * 64
    else:
        manifests["B"]["generation_id"] = manifests["A"]["generation_id"]
    live.atomic_json(retained / "backup-manifests.json", manifests)
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="backup-manifest-pair-drift"):
        live.direct_action("rollback", root, state, False)


def test_gate_a_eighth_cycle_retained_inventory_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    (retained / "unexpected.bin").write_bytes(b"not-allowed")
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="retained-inventory-drift"):
        live.direct_action("rollback", root, state, False)


@pytest.mark.parametrize("unexpected", [None, ".unexpected", "nested"])
def test_gate_a_ninth_cycle_missing_manifest_preserves_complete_local_backups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unexpected: str | None
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    (retained / "backup-manifests.json").unlink()
    (retained / live.REMOTE_INTENT_FILE).unlink()
    state["observed_mutation"] = recovery.mutation(
        True, ["state-only-backup-a", "state-only-backup-b-local"]
    )
    if unexpected == ".unexpected":
        (retained / unexpected).write_bytes(b"hidden")
    elif unexpected == "nested":
        (retained / unexpected).mkdir(mode=0o700)
    blocker = (
        "retained-local-backup-inventory-unresolved"
        if unexpected is None
        else "partial-retained-inventory-drift"
    )
    with pytest.raises(recovery.RecoveryBlocked, match=blocker):
        live.direct_action("rollback", root, state, False)
    assert retained.is_dir()
    assert (retained / "backup-a.tar").is_file()
    assert (retained / "backup-b.tar").is_file()
    if unexpected is not None:
        assert (retained / unexpected).exists()


@pytest.mark.parametrize("variant", ["archive-sha256", "size-bytes"])
def test_gate_a_ninth_cycle_backup_pair_requires_equal_archive_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    if variant == "archive-sha256":
        manifests["B"]["archive_sha256"] = "f" * 64
        manifests["B"]["local_sha256"] = "f" * 64
        manifests["B"]["remote_sha256"] = "f" * 64
    else:
        manifests["B"]["size_bytes"] += 1
    live.atomic_json(retained / "backup-manifests.json", manifests)
    live.persist_remote_object_intent(
        retained,
        "4" * 32,
        manifests["B"]["remote_object"],
        manifests["B"]["archive_sha256"],
        manifests["B"]["size_bytes"],
        verified=True,
    )
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="backup-manifest-pair-drift"):
        live.direct_action("rollback", root, state, False)


@pytest.mark.parametrize("generation_id", ["A" * 32, "g" * 32])
def test_gate_a_ninth_cycle_generation_id_is_lowercase_hex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, generation_id: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    manifests["B"]["generation_id"] = generation_id
    live.atomic_json(retained / "backup-manifests.json", manifests)
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="backup-manifest-schema-invalid"):
        live.direct_action("rollback", root, state, False)


def test_gate_a_ninth_cycle_retained_directory_mode_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    retained.chmod(0o755)
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="retained-identity-drift"):
        live.direct_action("rollback", root, state, False)


def _gate_a_malicious_tar(kind: str) -> tuple[bytes, str]:
    if kind == "blob":
        return b"not-a-tar" * 1024, "0" * 64
    payload = b"member-payload"
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:") as bundle:
        def add_regular(name: str, data: bytes = payload) -> None:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o600
            member.uid = member.gid = 0
            member.mtime = 0
            bundle.addfile(member, io.BytesIO(data))

        if kind == "path-traversal":
            add_regular("../db_v2.sqlite3")
        elif kind == "link":
            member = tarfile.TarInfo("db_v2.sqlite3")
            member.type = tarfile.SYMTYPE
            member.linkname = "../../outside"
            member.mode = 0o600
            bundle.addfile(member)
        elif kind == "duplicate":
            add_regular("db_v2.sqlite3")
            add_regular("db_v2.sqlite3")
        elif kind == "extra":
            add_regular("db_v2.sqlite3")
            add_regular("extra.sqlite3")
        else:
            raise AssertionError(kind)
    return stream.getvalue(), __import__("hashlib").sha256(payload).hexdigest()


@pytest.mark.parametrize("kind", ["blob", "path-traversal", "link", "duplicate", "extra"])
def test_gate_a_ninth_cycle_retained_tar_structure_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    tar_bytes, member_digest = _gate_a_malicious_tar(kind)
    archive_digest = __import__("hashlib").sha256(tar_bytes).hexdigest()
    for label in ("A", "B"):
        archive = retained / f"backup-{label.lower()}.tar"
        archive.write_bytes(tar_bytes)
        archive.chmod(0o600)
        manifests[label]["archive_sha256"] = archive_digest
        manifests[label]["size_bytes"] = len(tar_bytes)
        manifests[label]["source_snapshot_sha256"] = member_digest
        manifests[label]["member_sha256"] = member_digest
    manifests["B"]["local_sha256"] = archive_digest
    manifests["B"]["remote_sha256"] = archive_digest
    live.atomic_json(retained / "backup-manifests.json", manifests)
    live.persist_remote_object_intent(
        retained,
        "4" * 32,
        manifests["B"]["remote_object"],
        archive_digest,
        len(tar_bytes),
        verified=True,
    )
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="retained-tar-invalid"):
        live.direct_action("rollback", root, state, False)


@pytest.mark.parametrize(
    ("present", "classes"),
    [
        ({"A"}, []),
        ({"A"}, ["state-only-backup-a"]),
        ({"A", "B"}, ["state-only-backup-a"]),
        (set(), ["state-only-backup-a"]),
        ({"B"}, []),
        (set(), ["state-only-backup-b-local"]),
    ],
)
def test_gate_a_tenth_cycle_pre_manifest_crash_windows_preserve_and_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    present: set[str],
    classes: list[str],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    (retained / "backup-manifests.json").unlink()
    (retained / live.REMOTE_INTENT_FILE).unlink()
    for label in {"A", "B"} - present:
        (retained / f"backup-{label.lower()}.tar").unlink()
    state["observed_mutation"] = recovery.mutation(bool(classes), classes)

    with pytest.raises(
        recovery.RecoveryBlocked,
        match="retained-local-backup-inventory-unresolved",
    ):
        live.direct_action("rollback", root, state, False)

    assert retained.is_dir()
    assert {
        entry.name for entry in retained.iterdir()
    } == {f"backup-{label.lower()}.tar" for label in present}


def _gate_a_exact_tar_end(payload_size: int) -> int:
    return 512 + ((payload_size + 511) // 512) * 512 + 1024


def _gate_a_rechecksum_tar_header(raw: bytes) -> bytes:
    updated = bytearray(raw)
    updated[148:156] = b"        "
    updated[148:156] = f"{sum(updated[:512]):06o}\0 ".encode("ascii")
    return bytes(updated)


def _gate_a_tenth_tar_bytes(kind: str) -> tuple[bytes, str]:
    payload = b"phase52-canonical-member"
    stream = io.BytesIO()
    kwargs: dict[str, object] = {"fileobj": stream, "mode": "w:"}
    if kind in {"pax-global", "pax-member"}:
        kwargs["format"] = tarfile.PAX_FORMAT
        if kind == "pax-global":
            kwargs["pax_headers"] = {"comment": "forbidden"}
    elif kind in {"gnu-format", "gnu-longname"}:
        kwargs["format"] = tarfile.GNU_FORMAT
    else:
        kwargs["format"] = tarfile.USTAR_FORMAT
    with tarfile.open(**kwargs) as bundle:
        name = "x" * 120 if kind == "gnu-longname" else "db_v2.sqlite3"
        member = tarfile.TarInfo(name)
        member.size = len(payload)
        member.mode = 0o600
        member.uid = member.gid = 0
        member.mtime = 0
        if kind == "pax-member":
            member.pax_headers = {"comment": "forbidden"}
        bundle.addfile(member, io.BytesIO(payload))
    raw = stream.getvalue()
    canonical_end = _gate_a_exact_tar_end(len(payload))
    if kind == "truncated-end-blocks":
        raw = raw[: canonical_end - 512]
    elif kind == "trailing-zero-block":
        raw = raw[:canonical_end] + b"\0" * 512
    elif kind == "trailing-junk":
        raw = raw[:canonical_end] + b"junk"
    elif kind == "gnu-sparse":
        sparse = bytearray(raw[:canonical_end])
        sparse[156:157] = tarfile.GNUTYPE_SPARSE
        raw = _gate_a_rechecksum_tar_header(bytes(sparse))
    else:
        raw = raw[:canonical_end]
    return raw, __import__("hashlib").sha256(payload).hexdigest()


def _gate_a_tenth_metadata_tar(field: str) -> tuple[bytes, str]:
    payload = b"phase52-canonical-member"
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:", format=tarfile.USTAR_FORMAT) as bundle:
        member = tarfile.TarInfo("db_v2.sqlite3")
        member.size = len(payload)
        member.mode = 0o600
        member.uid = member.gid = 0
        member.mtime = 0
        if field in {"uid", "gid", "mtime", "devmajor", "devminor"}:
            setattr(member, field, 1)
        elif field == "mode":
            member.mode = 0o640
        elif field in {"uname", "gname"}:
            setattr(member, field, "root")
        elif field == "linkname":
            member.linkname = "unexpected"
        else:
            raise AssertionError(field)
        bundle.addfile(member, io.BytesIO(payload))
    raw = stream.getvalue()[: _gate_a_exact_tar_end(len(payload))]
    if field in {"devmajor", "devminor"}:
        updated = bytearray(raw)
        offset = 329 if field == "devmajor" else 337
        updated[offset : offset + 8] = b"0000001\0"
        raw = _gate_a_rechecksum_tar_header(bytes(updated))
    return raw, __import__("hashlib").sha256(payload).hexdigest()


def _gate_a_replace_retained_pair(
    live: object,
    retained: Path,
    manifests: dict[str, object],
    tar_bytes: bytes,
    member_digest: str,
) -> None:
    archive_digest = __import__("hashlib").sha256(tar_bytes).hexdigest()
    for label in ("A", "B"):
        archive = retained / f"backup-{label.lower()}.tar"
        archive.write_bytes(tar_bytes)
        archive.chmod(0o600)
        manifests[label]["archive_sha256"] = archive_digest
        manifests[label]["size_bytes"] = len(tar_bytes)
        manifests[label]["source_snapshot_sha256"] = member_digest
        manifests[label]["member_sha256"] = member_digest
    manifests["B"]["local_sha256"] = archive_digest
    manifests["B"]["remote_sha256"] = archive_digest
    live.atomic_json(retained / "backup-manifests.json", manifests)
    live.persist_remote_object_intent(
        retained,
        "4" * 32,
        manifests["B"]["remote_object"],
        archive_digest,
        len(tar_bytes),
        verified=True,
    )


@pytest.mark.parametrize(
    "kind",
    [
        "pax-global",
        "pax-member",
        "gnu-format",
        "gnu-longname",
        "gnu-sparse",
        "truncated-end-blocks",
        "trailing-zero-block",
        "trailing-junk",
    ],
)
def test_gate_a_tenth_cycle_retained_tar_requires_canonical_physical_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    tar_bytes, member_digest = _gate_a_tenth_tar_bytes(kind)
    _gate_a_replace_retained_pair(live, retained, manifests, tar_bytes, member_digest)
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="retained-tar-invalid"):
        live.direct_action("rollback", root, state, False)


@pytest.mark.parametrize(
    "field",
    ["mode", "uid", "gid", "uname", "gname", "mtime", "devmajor", "devminor", "linkname"],
)
def test_gate_a_tenth_cycle_retained_tar_metadata_is_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    tar_bytes, member_digest = _gate_a_tenth_metadata_tar(field)
    _gate_a_replace_retained_pair(live, retained, manifests, tar_bytes, member_digest)
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="retained-tar-invalid"):
        live.direct_action("rollback", root, state, False)


def test_gate_a_tenth_cycle_archive_hash_is_checked_before_tar_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    wrong_digest = "f" * 64
    for label in ("A", "B"):
        manifests[label]["archive_sha256"] = wrong_digest
    manifests["B"]["local_sha256"] = wrong_digest
    manifests["B"]["remote_sha256"] = wrong_digest
    live.atomic_json(retained / "backup-manifests.json", manifests)
    live.persist_remote_object_intent(
        retained,
        "4" * 32,
        manifests["B"]["remote_object"],
        wrong_digest,
        manifests["B"]["size_bytes"],
        verified=True,
    )
    monkeypatch.setattr(
        live,
        "validate_retained_tar",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("parser reached")),
    )
    _gate_a_block_remote_fetch(recovery, monkeypatch)
    with pytest.raises(recovery.RecoveryBlocked, match="retained-backup-drift"):
        live.direct_action("rollback", root, state, False)


@pytest.mark.parametrize(
    "classes",
    [
        ["state-only-backup-a"],
        ["state-only-backup-b-local"],
        ["state-only-backup-a", "state-only-backup-b-local"],
    ],
)
def test_gate_a_eleventh_cycle_declared_local_mutation_requires_retained_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, classes: list[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live = _load_phase52_live_drill()
    transaction_id = "6" * 32
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    retained = tmp_path / ".local/share/atius-rustdesk-phase52" / transaction_id
    state = recovery.initial_state(transaction_id)
    state["observed_mutation"] = recovery.mutation(True, classes)

    with pytest.raises(
        recovery.RecoveryBlocked,
        match="retained-local-backup-inventory-missing",
    ):
        live.direct_action("rollback", root, state, False)

    assert not retained.exists() and not retained.is_symlink()


@pytest.mark.parametrize("identity", ["regular", "symlink"])
def test_gate_a_eleventh_cycle_non_directory_retained_root_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identity: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live = _load_phase52_live_drill()
    transaction_id = "7" * 32
    root = tmp_path / "transaction"
    root.mkdir(mode=0o700)
    retained = tmp_path / ".local/share/atius-rustdesk-phase52" / transaction_id
    retained.parent.mkdir(parents=True, mode=0o700)
    if identity == "regular":
        retained.write_bytes(b"not-a-directory")
    else:
        target = tmp_path / "retained-target"
        target.mkdir(mode=0o700)
        retained.symlink_to(target, target_is_directory=True)
    state = recovery.initial_state(transaction_id)
    live.journal_artifact(root, state, retained, disposable=False)
    state["observed_mutation"] = recovery.mutation(
        True, ["state-only-backup-a"]
    )

    with pytest.raises(recovery.RecoveryBlocked, match="retained-identity-drift"):
        live.direct_action("rollback", root, state, False)

    assert retained.exists() or retained.is_symlink()


def _gate_a_restore_fetch_must_not_run(
    recovery: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        recovery,
        "bounded_process",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("restore fetch reached")),
    )


@pytest.mark.parametrize("variant", ["b-only", "wrong-transaction", "duplicate-key"])
def test_gate_a_twelfth_cycle_restore_rejects_unreconciled_manifest_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    manifest_path = retained / "backup-manifests.json"
    if variant == "b-only":
        live.atomic_json(manifest_path, {"B": manifests["B"]})
    elif variant == "wrong-transaction":
        manifests["A"]["transaction_id"] = "5" * 32
        live.atomic_json(manifest_path, manifests)
    else:
        manifest_path.write_text(
            '{"A":' + json.dumps(manifests["A"], separators=(",", ":"))
            + ',"A":' + json.dumps(manifests["A"], separators=(",", ":"))
            + ',"B":' + json.dumps(manifests["B"], separators=(",", ":")) + '}\n',
            encoding="utf-8",
        )
        manifest_path.chmod(0o600)
    _gate_a_restore_fetch_must_not_run(recovery, monkeypatch)

    with pytest.raises(recovery.RecoveryBlocked):
        live.direct_action("restore", root, state, False)


@pytest.mark.parametrize("variant", ["missing", "drift"])
def test_gate_a_twelfth_cycle_restore_reconciles_remote_intent_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    intent_path = retained / live.REMOTE_INTENT_FILE
    if variant == "missing":
        intent_path.unlink()
    else:
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        intent["status"] = "copy-planned"
        intent["verified_remote_sha256"] = None
        live.atomic_json(intent_path, intent)
    _gate_a_restore_fetch_must_not_run(recovery, monkeypatch)

    with pytest.raises(recovery.RecoveryBlocked):
        live.direct_action("restore", root, state, False)


def test_gate_a_twelfth_cycle_restore_rejects_retained_identity_drift_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, retained, _ = _gate_a_seventh_rollback_fixture(tmp_path)
    original = retained.with_name(retained.name + ".original")
    retained.rename(original)
    retained.symlink_to(original, target_is_directory=True)
    _gate_a_restore_fetch_must_not_run(recovery, monkeypatch)

    with pytest.raises(recovery.RecoveryBlocked):
        live.direct_action("restore", root, state, False)


@pytest.mark.parametrize("variant", ["missing", "mismatch"])
def test_gate_a_twelfth_cycle_restore_requires_matching_backup_facts_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, _, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    state["completed_actions"] = ["preflight", "vault", "backup"]
    if variant == "mismatch":
        facts = {
            "backup_a": copy.deepcopy(manifests["A"]),
            "backup_b": copy.deepcopy(manifests["B"]),
            "state_only": ["db_v2.sqlite3"],
            "remote_rehash_verified": True,
            "sqlite_ready": True,
        }
        facts["backup_b"]["archive_sha256"] = "f" * 64
        state.setdefault("facts", {})["backup"] = facts
    _gate_a_restore_fetch_must_not_run(recovery, monkeypatch)

    with pytest.raises(recovery.RecoveryBlocked):
        live.direct_action("restore", root, state, False)


def test_gate_a_twelfth_cycle_valid_reconciled_restore_reaches_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    recovery, live, root, state, _, manifests = _gate_a_seventh_rollback_fixture(tmp_path)
    state["completed_actions"] = ["preflight", "vault", "backup"]
    state.setdefault("facts", {})["backup"] = {
        "backup_a": copy.deepcopy(manifests["A"]),
        "backup_b": copy.deepcopy(manifests["B"]),
        "state_only": ["db_v2.sqlite3"],
        "remote_rehash_verified": True,
        "sqlite_ready": True,
    }
    _gate_a_restore_fetch_must_not_run(recovery, monkeypatch)

    with pytest.raises(AssertionError, match="restore fetch reached"):
        live.direct_action("restore", root, state, False)
