from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "modules/rustdesk-fleet/contracts/phase52-post-live-successor.json"
VERIFIER_PATH = ROOT / "modules/rustdesk-fleet/tools/verify-phase52-post-live.py"
SCANNER_PATH = ROOT / "scripts/sso-secret-hygiene-scan.sh"
ANCHOR = "phase52_post_live_successor_v1"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("phase52_post_live_successor", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _strict_json(path: Path) -> dict:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def test_phase52_post_live_successor_v1_anchor_is_static_and_runtime_bound() -> None:
    assert ANCHOR in CONTRACT_PATH.read_text(encoding="utf-8")
    assert ANCHOR in VERIFIER_PATH.read_text(encoding="utf-8")
    assert ANCHOR in Path(__file__).read_text(encoding="utf-8")
    verifier = _load_verifier()
    contract = _strict_json(CONTRACT_PATH)
    assert verifier.PHASE52_POST_LIVE_SUCCESSOR_V1 == ANCHOR
    assert contract["schema_anchor"] == verifier.PHASE52_POST_LIVE_SUCCESSOR_V1


def test_contract_binds_exact_history_hashes_and_no_live_authority() -> None:
    contract = _strict_json(CONTRACT_PATH)
    assert contract["history"] == [
        {
            "commit": "443305b5059decfd1b2d8bdc1d8700f3e7232fb4",
            "path": "modules/rustdesk-fleet/evidence/ledger.json",
            "old_sha256": "fdf9c1fb071d6ea8c72280c165ba9793199420fd7dea7ba3cc039fff8581b047",
            "new_sha256": "06681c7706b934feb22fd781ed45ed12fa684d5d056d3f10e751d1bd60eb69cd",
        },
        {
            "commit": "257ba51180f67cc748421f68542d7d465cfe1087",
            "path": "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py",
            "old_sha256": "e1c5ccf280f86ea0874c96cb60e3410e7db25650fab7545196f561bdd4917454",
            "new_sha256": "679150a75e038f06131c01700b91b2661f1e9317e07e97489139eab9f45da6f4",
        },
        {
            "commit": "8683e1742b4297217fd56bbca082233260f799b5",
            "path": "modules/rustdesk-fleet/tools/validate_phase52.py",
            "old_sha256": "a58155d77b367289ac021ad5d28d0db47a3b090574cbed4055ba9d94e1c9ef5a",
            "new_sha256": "523f7026d1be334aa53a2b725ebf3560008dbe108cf79dbe50223c6e3f4fed52",
        },
    ]
    assert contract["authority"] == {
        "live_authority": False,
        "replay_authorized": False,
        "vault_write_authorized": False,
    }


def test_exact_git_objects_ancestry_and_ledger_successor_pass() -> None:
    verifier = _load_verifier()
    contract = _strict_json(CONTRACT_PATH)
    result = verifier.verify_historical_successor(ROOT, contract)
    assert result["status"] == "PASS"
    assert result["history_count"] == 3
    assert result["path_count"] == 3
    assert result["ancestry"]["first_is_ancestor_of_second"] is True
    assert result["ancestry"]["second_is_direct_parent_of_third"] is True
    assert result["ledger"]["requirement_count"] == 36
    assert result["ledger"]["promoted_requirement_ids"] == [
        "SCP-04",
        "SRV-01",
        "SRV-05",
        "SRV-07",
    ]


@pytest.mark.parametrize("mutation", ["fourth-path", "substituted-commit", "amended-hash"])
def test_history_mutations_are_rejected(mutation: str) -> None:
    verifier = _load_verifier()
    contract = _strict_json(CONTRACT_PATH)
    if mutation == "fourth-path":
        contract["history"].append(copy.deepcopy(contract["history"][0]))
        contract["history"][-1]["path"] = "unexpected"
    elif mutation == "substituted-commit":
        contract["history"][1]["commit"] = contract["history"][0]["commit"]
    else:
        contract["history"][2]["new_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        verifier.verify_historical_successor(ROOT, contract)


def test_ledger_successor_rejects_duplicate_extra_and_non_phase52_change() -> None:
    verifier = _load_verifier()
    old = verifier.git_json(ROOT, "443305b5059decfd1b2d8bdc1d8700f3e7232fb4^", "modules/rustdesk-fleet/evidence/ledger.json")
    new = verifier.git_json(ROOT, "443305b5059decfd1b2d8bdc1d8700f3e7232fb4", "modules/rustdesk-fleet/evidence/ledger.json")
    assert verifier.validate_ledger_successor(old, new)["status"] == "PASS"
    duplicate = copy.deepcopy(new)
    duplicate["requirements"].append(copy.deepcopy(duplicate["requirements"][0]))
    with pytest.raises(ValueError):
        verifier.validate_ledger_successor(old, duplicate)
    changed = copy.deepcopy(new)
    changed["requirements"][0]["status"] = "pending"
    with pytest.raises(ValueError):
        verifier.validate_ledger_successor(old, changed)


def test_source_freeze_detects_byte_drift(tmp_path: Path) -> None:
    verifier = _load_verifier()
    source = tmp_path / "source"
    source.write_text("frozen\n", encoding="utf-8")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert verifier.validate_source_freeze(tmp_path, {"source": expected})["status"] == "PASS"
    source.write_text("drifted\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source-freeze"):
        verifier.validate_source_freeze(tmp_path, {"source": expected})


def test_independent_review_quorum_requires_distinct_identity_and_same_hash() -> None:
    verifier = _load_verifier()
    expected = "a" * 64
    reviews = [
        {
            "schema_anchor": ANCHOR,
            "reviewer_id": "fresh-reviewer-1",
            "checkout_mode": "read-only",
            "verdict": "PASS",
            "hash_set_sha256": expected,
            "unresolved_high_count": 0,
            "secret_material_present": False,
        },
        {
            "schema_anchor": ANCHOR,
            "reviewer_id": "fresh-reviewer-2",
            "checkout_mode": "read-only",
            "verdict": "PASS",
            "hash_set_sha256": expected,
            "unresolved_high_count": 0,
            "secret_material_present": False,
        },
    ]
    assert verifier.validate_independent_reviews(reviews, expected)["status"] == "PASS"
    reviews[1]["reviewer_id"] = reviews[0]["reviewer_id"]
    with pytest.raises(ValueError, match="independent"):
        verifier.validate_independent_reviews(reviews, expected)


def test_cli_exposes_only_offline_read_only_surfaces() -> None:
    allowed = {
        "attest",
        "verify-attestation",
        "reconcile-phase53",
        "refresh-read-only",
        "project-current",
        "verify-junit",
        "record-secret-hygiene",
        "verify-closeout-inputs",
        "verify-closeout",
    }
    verifier = _load_verifier()
    parser = verifier.build_parser()
    assert verifier.ALLOWED_COMMANDS == allowed
    parser.parse_args(["attest", "--repo", ".", "--out", "attestation.json"])
    for forbidden in (
        "execute",
        "execute-live",
        "live",
        "resume",
        "status",
        "transaction",
        "write",
        "delete",
        "cleanup",
    ):
        with pytest.raises(SystemExit):
            parser.parse_args([forbidden])


def test_scanner_consumes_all_explicit_scopes_and_redacts_findings(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "clean.txt").write_text("clean\n", encoding="utf-8")
    (second / "clean.txt").write_text("clean\n", encoding="utf-8")
    clean = subprocess.run(
        ["bash", str(SCANNER_PATH), str(first), str(second)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert clean.returncode == 0
    assert "Scanned 2 files" in clean.stdout
    (second / "bad.txt").write_text('PASSWORD="super-secret-sentinel"\n', encoding="utf-8")
    failed = subprocess.run(
        ["bash", str(SCANNER_PATH), str(first), str(second)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert failed.returncode == 1
    assert "super-secret-sentinel" not in failed.stdout + failed.stderr
    assert "password-value" in failed.stdout
    assert str(second / "bad.txt") in failed.stdout


def test_scanner_fails_when_any_explicit_target_is_missing(tmp_path: Path) -> None:
    present = tmp_path / "present"
    present.write_text("clean\n", encoding="utf-8")
    completed = subprocess.run(
        ["bash", str(SCANNER_PATH), str(present), str(tmp_path / "missing")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "missing explicit target" in completed.stderr.lower()


def test_scanner_retains_legacy_targets_for_zero_argument_invocation() -> None:
    text = SCANNER_PATH.read_text(encoding="utf-8")
    assert 'if (( "$#" > 0 )); then' in text
    assert "legacy_targets=(" in text
    assert "modules/mt5-remote-auth" in text
