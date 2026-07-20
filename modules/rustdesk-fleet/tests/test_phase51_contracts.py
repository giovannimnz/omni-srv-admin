from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
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
SECRET_ROLES_PATH = REPO / "modules/rustdesk-fleet/contracts/secret-roles.json"
UNSCOPED_COMMAND_PATH = INVALID_DIR / "unscoped-gsd-command.md"
PHASE48_BASELINE_PATH = REPO / "modules/rustdesk-fleet/evidence/phase48-baseline.json"
PHASE48_DRIFT_PATH = INVALID_DIR / "phase48-drift.json"
PHASE48_ROOT = (
    REPO
    / ".planning/workstreams/runtime-trust-codex-delivery-convergence/phases/48-codex-oauth-wayland-acp-convergence"
)
REQUIREMENTS_PATH = REPO / ".planning/workstreams/rustdesk-fleet/REQUIREMENTS.md"
LEDGER_PATH = REPO / "modules/rustdesk-fleet/evidence/ledger.json"
BUNDLE_PATH = REPO / "modules/rustdesk-fleet/tests/fixtures/valid/minimal-contracts/bundle.json"
PHASE51_DIR = (
    REPO
    / ".planning/workstreams/rustdesk-fleet/phases/51-contract-threat-model-and-workstream-isolation"
)
REVIEW_PATH = PHASE51_DIR / "51-OPERATIONAL-REVIEW.md"

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
        "P51-WS-001": "PASS",
    }


def test_workstream_scope_contract() -> None:
    payload = _canonical_scope()
    result = validator.validate_workstream_policy(payload)
    assert result.id == "P51-WS-001"
    assert result.status == "PASS"
    assert payload["gsd_lifecycle"]["required_flag"] == "--ws"
    assert payload["gsd_lifecycle"]["required_workstream"] == "rustdesk-fleet"
    assert payload["shared_writers"] == {
        "mode": "serialized-single-writer",
        "paths": [
            ".planning/PROJECT.md",
            ".planning/MILESTONES.md",
            ".planning/graphs/graph.json",
            ".planning/graphs/GRAPH_REPORT.md",
            ".planning/graphs/manifest.json",
        ],
    }
    assert payload["transition_gates"] == {
        "precheck_ids": ["P51-WS-001"],
        "postcheck_ids": ["P51-P48-001"],
    }


def test_workstream_commands_are_checked_independently() -> None:
    text = UNSCOPED_COMMAND_PATH.read_text(encoding="utf-8")
    commands = validator.extract_executable_gsd_commands(text, source_kind="markdown")
    assert len(commands) == 2
    results = validator.validate_workstream_commands(commands)
    assert [result.status for result in results] == ["PASS", "FAIL"]
    assert results[1].findings[0].category == "missing-explicit-workstream"


def test_workstream_rejects_wrong_scope_and_accepts_read_only_query() -> None:
    payload = _canonical_scope()
    verbs = payload["gsd_lifecycle"]["mutating_verbs"]
    wrong = validator.validate_workstream_commands(
        ["node gsd-tools.cjs state begin-phase --ws another-lane 51"],
        mutating_verbs=verbs,
    )
    assert wrong[0].status == "FAIL"
    assert wrong[0].findings[0].category == "wrong-explicit-workstream"

    read_only = validator.validate_workstream_commands(
        [
            "node gsd-tools.cjs query state.json --ws "
            "runtime-trust-codex-delivery-convergence --pick current_phase"
        ],
        mutating_verbs=verbs,
    )
    assert read_only[0].status == "PASS"


def test_workstream_prose_is_not_an_executable_command() -> None:
    text = "Every lifecycle command must use --ws rustdesk-fleet."
    assert validator.extract_executable_gsd_commands(text, source_kind="markdown") == []


def test_workstream_or_chain_and_duplicate_scope_fail_independently() -> None:
    commands = validator.extract_executable_gsd_commands(
        "node gsd-tools.cjs state begin-phase --ws rustdesk-fleet 51 || "
        "node gsd-tools.cjs state advance-plan 51\n",
        source_kind="script",
    )
    assert [result.status for result in validator.validate_workstream_commands(commands)] == ["PASS", "FAIL"]
    duplicate = validator.validate_workstream_commands(
        ["node gsd-tools.cjs state begin-phase --ws rustdesk-fleet --ws rustdesk-fleet 51"]
    )
    assert duplicate[0].status == "FAIL"


def test_phase48_integrity_contract() -> None:
    payload = validator.load_json_strict(PHASE48_BASELINE_PATH)
    result = validator.validate_phase48_baseline(payload, REPO)
    assert result.id == "P51-P48-001"
    assert result.status == "PASS"
    assert payload["file_count"] == 9
    assert len(payload["files"]) == 9
    assert payload["allowed_exclusions"] == ["__pycache__", "*.pyc", "*.swp", "*~"]
    assert payload["rebaseline_policy"] == "explicit-serialized-review-only"


@pytest.mark.parametrize(
    "relative_path",
    [
        "48-01-PLAN.md",
        "48-01-ROUTER-EVIDENCE.md",
        "48-02-PLAN.md",
        "48-CONTEXT.md",
        "48-EXECUTION-CHECKPOINT-2026-07-12.md",
        "48-PATTERNS.md",
        "48-RESEARCH.md",
        "48-VALIDATION.md",
        "tools/verify-router-evidence.py",
    ],
)
def test_phase48_old_blob_to_migrated_hash(relative_path: str) -> None:
    payload = validator.load_json_strict(PHASE48_BASELINE_PATH)
    row = next(item for item in payload["files"] if item["workstream_path"].endswith(relative_path))
    assert validator.resolve_legacy_blob(REPO, payload["source_head"], row["legacy_git_path"]) == row[
        "legacy_blob_id"
    ]
    assert validator._sha256_file(REPO / row["workstream_path"]) == row["workstream_sha256"]


def test_phase48_drift_is_blocked_on_disposable_copy(tmp_path: Path) -> None:
    payload = validator.load_json_strict(PHASE48_BASELINE_PATH)
    descriptor = validator.load_json_strict(PHASE48_DRIFT_PATH)
    copied_root = tmp_path / "phase48"
    shutil.copytree(PHASE48_ROOT, copied_root)
    target = copied_root / descriptor["target"]
    target.write_bytes(target.read_bytes() + b"\n")
    result = validator.validate_phase48_baseline(payload, REPO, workstream_root=copied_root)
    assert result.status == "BLOCKED"
    assert {finding.category for finding in result.findings} == {"workstream-sha256-drift"}


@pytest.mark.parametrize("mutation", ["zero", "missing", "extra"])
def test_phase48_rejects_incomplete_or_extra_rows(mutation: str) -> None:
    payload = validator.load_json_strict(PHASE48_BASELINE_PATH)
    if mutation == "zero":
        payload["files"] = []
        payload["file_count"] = 0
    elif mutation == "missing":
        payload["files"].pop()
    else:
        payload["files"].append(dict(payload["files"][0]))
    assert validator.validate_phase48_baseline(payload, REPO).status == "BLOCKED"


def test_phase48_validator_has_no_rebaseline_cli_option() -> None:
    options = {action.dest for action in validator.build_parser()._actions}
    assert "rebaseline" not in options


def test_requirement_ledger_contract() -> None:
    canonical = validator.parse_canonical_requirements(REQUIREMENTS_PATH)
    payload = validator.load_json_strict(LEDGER_PATH)
    result = validator.validate_ledger(payload, canonical, REPO)
    assert result.id == "P51-LEDGER-001"
    assert result.status == "PASS"
    assert len(canonical) == payload["requirement_count"] == 36
    assert [row["requirement_id"] for row in payload["requirements"]] == list(canonical)
    assert len({evidence_id for row in payload["requirements"] for evidence_id in row["evidence_ids"]}) == 36
    assert {row["status"] for row in payload["requirements"]} == {"pending"}


@pytest.mark.parametrize("mutation", ["missing", "orphan", "duplicate"])
def test_requirement_ledger_rejects_id_drift(mutation: str) -> None:
    canonical = validator.parse_canonical_requirements(REQUIREMENTS_PATH)
    payload = validator.load_json_strict(LEDGER_PATH)
    if mutation == "missing":
        payload["requirements"].pop()
    elif mutation == "orphan":
        payload["requirements"][-1]["requirement_id"] = "ORPHAN-99"
    else:
        payload["requirements"][-1]["requirement_id"] = payload["requirements"][0]["requirement_id"]
    assert validator.validate_ledger(payload, canonical, REPO).status == "BLOCKED"


@pytest.mark.parametrize(
    ("path", "digest", "verified_at", "category"),
    [
        (".planning/workstreams/rustdesk-fleet/phases/51/SUMMARY.md", "a" * 64, "2026-07-20T05:00:00Z", "summary-only-evidence"),
        ("../outside.json", "a" * 64, "2026-07-20T05:00:00Z", "evidence-path-outside-scope"),
        ("modules/rustdesk-fleet/evidence/current.json", "short", "2026-07-20T05:00:00Z", "evidence-digest-shape"),
        ("modules/rustdesk-fleet/evidence/current.json", "a" * 64, "2026-07-19T05:00:00Z", "evidence-currentness"),
    ],
)
def test_requirement_ledger_rejects_invalid_pass_evidence(
    path: str, digest: str, verified_at: str, category: str
) -> None:
    canonical = validator.parse_canonical_requirements(REQUIREMENTS_PATH)
    payload = validator.load_json_strict(LEDGER_PATH)
    row = payload["requirements"][0]
    row.update(status="pass", last_verified_at="2026-07-20T05:00:00Z")
    payload["evidence_catalog"][row["evidence_ids"][0]] = {
        "path": path,
        "sha256": digest,
        "input_digest": "b" * 64,
        "observed_at": verified_at,
    }
    result = validator.validate_ledger(payload, canonical, REPO)
    assert result.status == "BLOCKED"
    assert category in {finding.category for finding in result.findings}


def test_complete_fixture_bundle_materializes_all_contracts(tmp_path: Path) -> None:
    bundle = validator.load_json_strict(BUNDLE_PATH)
    written = validator.materialize_fixture_bundle(bundle, tmp_path)
    assert set(written) == {
        "scope",
        "product_decision",
        "threat_model",
        "permission_profiles",
        "secret_roles",
        "ledger",
        "phase48_baseline",
        "operational_review",
    }
    assert len(validator.load_json_strict(written["ledger"])["requirements"]) == 36
    assert len(validator.load_json_strict(written["phase48_baseline"])["files"]) == 9
    assert validator.load_json_strict(written["operational_review"])["status"] == "BLOCKED"


def test_structural_static_fixtures_match_plan01_failures() -> None:
    missing = validator.load_structural_fixture(INVALID_DIR / "missing-legacy-tool.json", REPO)
    duplicate = validator.load_structural_fixture(INVALID_DIR / "duplicate-secret-ref.json", REPO)
    assert _statuses(missing)["P51-LEGACY-001"] == "FAIL"
    assert validator.validate_secret_roles(duplicate).status == "FAIL"


def test_summary_only_static_fixture_cannot_close_requirement() -> None:
    canonical = validator.parse_canonical_requirements(REQUIREMENTS_PATH)
    payload = validator.load_structural_fixture(INVALID_DIR / "summary-only-ledger.json", REPO)
    result = validator.validate_ledger(payload, canonical, REPO)
    assert result.status == "BLOCKED"
    assert "summary-only-evidence" in {finding.category for finding in result.findings}


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


def test_product_decision_contract_records_oss_acceptance() -> None:
    payload = validator.load_json_strict(PRODUCT_PATH)
    derived = validator.derive_product_decision(payload)
    result = validator.validate_product_decision(payload)
    assert derived == {"decision": "GO", "required_edition": "oss"}
    assert result.id == "P51-PRODUCT-001"
    assert result.status == "PASS"
    assert all(
        control == {
            "id": control["id"],
            "mandatory": False,
            "source": "accountable-operational-review",
            "review_status": "reviewed",
            "accepted_absence": True,
        }
        for control in payload["enterprise_controls"]
    )
    assert payload["custom_ops_api"] == {
        "status": "approved-to-plan-and-implement",
        "kind": "atius-ops-api",
        "rustdesk_native_api": False,
        "configure_client_api_server": False,
        "rustdesk_api_port_21114": "closed",
        "phase": 53,
        "requirement_id": "OPS-01",
    }


def test_product_decision_rejects_native_api_confusion() -> None:
    payload = validator.load_json_strict(PRODUCT_PATH)
    payload["custom_ops_api"]["rustdesk_native_api"] = True
    assert validator.validate_product_decision(payload).status == "FAIL"


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


def test_secret_role_contract() -> None:
    payload = validator.load_json_strict(SECRET_ROLES_PATH)
    result = validator.validate_secret_roles(payload)
    assert result.id == "P51-SECRET-001"
    assert result.status == "BLOCKED"
    roles = payload["target_password_roles"]
    assert [item["host"] for item in roles] == list(validator.EXPECTED_INCLUDED_HOSTS)
    assert len({item["role"] for item in roles}) == 5
    assert len({item["vault_path"] for item in roles}) == 5
    assert {item["approval_status"] for item in roles} == {"pending"}
    assert payload["value_distinctness_phase"] == 52


def test_secret_role_contract_passes_only_after_accountable_approval() -> None:
    payload = validator.load_json_strict(SECRET_ROLES_PATH)
    payload["server_identity"]["approval_status"] = "approved"
    for role in payload["target_password_roles"]:
        role["approval_status"] = "approved"
    payload["recovery_authority"]["approval_status"] = "approved"
    assert validator.validate_secret_roles(payload).status == "PASS"


def test_secret_role_contract_rejects_duplicate_reference() -> None:
    payload = validator.load_json_strict(SECRET_ROLES_PATH)
    payload["target_password_roles"][1]["vault_path"] = payload["target_password_roles"][0][
        "vault_path"
    ]
    assert validator.validate_secret_roles(payload).status == "FAIL"


@pytest.mark.parametrize(
    ("category", "sentinel_factory"),
    [
        ("private-key-header", lambda: "-----BEGIN " + "PRIVATE KEY-----"),
        ("bearer-token", lambda: "Bearer " + ("Ab9_" * 12)),
        ("secret-assignment", lambda: "password=" + ("Xy7!" * 8)),
        ("uri-credential", lambda: "https://operator:" + ("Qz8" * 8) + "@example.invalid"),
        ("high-entropy", lambda: "".join(chr(65 + (index * 7) % 26) for index in range(72))),
        ("argv-transcript", lambda: "argv: rustdesk --password " + ("Uv4" * 8)),
        ("screenshot-redaction", lambda: "screenshot_redaction_status=failed"),
    ],
)
def test_redact_scanner_reports_metadata_only(category: str, sentinel_factory) -> None:
    sentinel = sentinel_factory()
    findings = validator.scan_secret_material({"sample": sentinel}, path="runtime.json")
    assert category in {item.category for item in findings}
    serialized = json.dumps(
        [
            {"category": item.category, "path": item.path, "location": item.location}
            for item in findings
        ],
        sort_keys=True,
    )
    assert sentinel not in serialized


def test_phase51_validator_never_reads_vault() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    forbidden = (
        "-".join(("atius", "vault", "env")),
        " ".join(("vault", "read")),
        " ".join(("vault", "kv", "get")),
        "hv" + "ac",
        "/".join(("hashicorp", "vault")),
    )
    assert not any(token in source for token in forbidden)


def test_operational_review_blocks_without_human_fields() -> None:
    review = validator.load_operational_review(REVIEW_PATH)
    manifest = validator.build_review_input_manifest(REPO, validator.git_head(REPO))
    result = validator.validate_operational_review(review, REPO, manifest)
    assert result.id == "P51-REPORT-001"
    assert result.status == "BLOCKED"
    categories = {finding.category for finding in result.findings}
    assert {"operator-review-pending", "vault-owner-review-pending"}.issubset(categories)


def test_report_contains_exact_check_set() -> None:
    report = validator.build_report(REPO, generated_at="2026-07-20T05:00:00Z")
    assert [check["id"] for check in report["checks"]] == list(validator.CHECK_ORDER)
    assert len(report["checks"]) == 11
    assert report["overall_status"] == "BLOCKED"
    assert report["secret_material_present"] is False


def test_report_exit_precedence() -> None:
    passed = validator.CheckResult("A", "PASS")
    blocked = validator.CheckResult("B", "BLOCKED")
    failed = validator.CheckResult("C", "FAIL")
    assert validator.derive_overall_status([passed]) == "PASS"
    assert validator.derive_overall_status([passed, blocked]) == "BLOCKED"
    assert validator.derive_overall_status([blocked, failed]) == "FAIL"
    assert validator.exit_code_for_status("PASS") == 0
    assert validator.exit_code_for_status("BLOCKED") == 2
    assert validator.exit_code_for_status("FAIL") == 1


def test_report_currentness_detects_changed_input(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text('{"schema_version": 1}\n', encoding="utf-8")
    report = {"inputs": validator.collect_input_digests(tmp_path, [source])}
    assert validator.validate_report_currentness(report, tmp_path).status == "PASS"
    source.write_text('{"schema_version": 2}\n', encoding="utf-8")
    result = validator.validate_report_currentness(report, tmp_path)
    assert result.status == "BLOCKED"
    assert {finding.category for finding in result.findings} == {"stale-input-digest"}


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True
    )
    return completed.stdout.strip()


def _review_source_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Phase 51 Test")
    _git(repo, "config", "user.email", "phase51@example.invalid")
    (repo / "input.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    _git(repo, "add", "input.json")
    _git(repo, "commit", "-qm", "input baseline")
    source_head = _git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(validator, "PRE_REPORT_INPUTS", ("input.json",))
    monkeypatch.setattr(validator, "POST_REVIEW_ALLOWED_PATHS", ("review.md",))
    monkeypatch.setattr(validator, "REVIEW_NORMATIVE_PATHS", ("validator.py",))
    return repo, source_head


def test_review_source_survives_allowed_attestation_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, source_head = _review_source_repo(tmp_path, monkeypatch)
    manifest = validator.build_review_input_manifest(repo, source_head)
    (repo / "review.md").write_text("approved\n", encoding="utf-8")
    _git(repo, "add", "review.md")
    _git(repo, "commit", "-qm", "record attestation")

    assert validator.validate_review_source(repo, source_head, manifest) == []


def test_review_source_rejects_committed_or_worktree_input_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, source_head = _review_source_repo(tmp_path, monkeypatch)
    manifest = validator.build_review_input_manifest(repo, source_head)
    (repo / "input.json").write_text('{"schema_version": 2}\n', encoding="utf-8")
    assert "reviewed-input-drift" in validator.validate_review_source(repo, source_head, manifest)

    _git(repo, "add", "input.json")
    _git(repo, "commit", "-qm", "drift reviewed input")
    categories = validator.validate_review_source(repo, source_head, manifest)
    assert {"post-review-scope-drift", "reviewed-input-drift"}.issubset(categories)


def test_review_source_rejects_unrelated_post_review_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, source_head = _review_source_repo(tmp_path, monkeypatch)
    manifest = validator.build_review_input_manifest(repo, source_head)
    (repo / "validator.py").write_text("VERSION = 2\n", encoding="utf-8")
    assert "uncommitted-review-authority-drift" in validator.validate_review_source(
        repo, source_head, manifest
    )
    _git(repo, "add", "validator.py")
    _git(repo, "commit", "-qm", "change validator")
    assert "post-review-scope-drift" in validator.validate_review_source(
        repo, source_head, manifest
    )


def test_post_review_allowlist_excludes_normative_roadmap() -> None:
    assert ".planning/workstreams/rustdesk-fleet/ROADMAP.md" not in validator.POST_REVIEW_ALLOWED_PATHS


@pytest.mark.parametrize(
    "value",
    [
        "2026-02-30T12:00:00Z",
        "2026-07-20T24:00:00Z",
        "2026-07-20T05:00:00+00:00",
        "not-a-timestamp",
        None,
    ],
)
def test_utc_timestamp_validation_is_semantic(value: object) -> None:
    assert validator.is_utc_timestamp(value) is False


def test_utc_timestamp_validation_accepts_canonical_utc() -> None:
    assert validator.is_utc_timestamp("2026-07-20T05:00:00Z") is True


def test_json_markdown_parity_and_atomic_outputs(tmp_path: Path) -> None:
    report = validator.build_report(REPO, generated_at="2026-07-20T05:00:00Z")
    markdown = validator.render_markdown(report)
    assert report["source_head"] in markdown
    assert report["generated_at"] in markdown
    for item in report["inputs"]:
        assert item["path"] in markdown and item["sha256"] in markdown
    for check in report["checks"]:
        assert check["id"] in markdown and check["status"] in markdown

    json_path = tmp_path / "51-CONTRACT-VALIDATION.json"
    markdown_path = tmp_path / "51-CONTRACT-VALIDATION.md"
    nyquist = tmp_path / "51-VALIDATION.md"
    nyquist.write_text("immutable strategy\n", encoding="utf-8")
    validator.write_reports_atomically(report, json_path, markdown_path, tmp_path)
    assert validator.load_json_strict(json_path) == report
    assert markdown_path.read_text(encoding="utf-8") == markdown
    assert nyquist.read_text(encoding="utf-8") == "immutable strategy\n"
