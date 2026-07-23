#!/usr/bin/env python3
"""Offline, non-authorizing verifier for the Phase 52 post-live successor."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PHASE52_POST_LIVE_SUCCESSOR_V1 = "phase52_post_live_successor_v1"
CONTRACT_PATH = Path("modules/rustdesk-fleet/contracts/phase52-post-live-successor.json")
LEDGER_PATH = Path("modules/rustdesk-fleet/evidence/ledger.json")
ATTESTATION_PATH = Path(
    "modules/rustdesk-fleet/evidence/phase52/post-live/successor-attestation.json"
)
SOURCE_PATHS = (
    "modules/rustdesk-fleet/contracts/phase52-post-live-successor.json",
    "modules/rustdesk-fleet/tools/verify-phase52-post-live.py",
    "modules/rustdesk-fleet/tools/validate_phase52.py",
    "modules/rustdesk-fleet/tests/test_phase52_post_live_successor.py",
    "modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py",
    "scripts/sso-secret-hygiene-scan.sh",
)
ANCHOR_PATHS = SOURCE_PATHS[:2] + (SOURCE_PATHS[3],)
PROMOTED_REQUIREMENTS = ("SCP-04", "SRV-01", "SRV-05", "SRV-07")
PROMOTED_AT = "2026-07-22T22:41:53Z"
HISTORY = (
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
)
AUTHORITY = {
    "live_authority": False,
    "replay_authorized": False,
    "vault_write_authorized": False,
}
ALLOWED_COMMANDS = {
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


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key rejected")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicates,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path.name}:{exc.lineno}") from None


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _repo_path(repo: Path, relative: str | Path, *, must_exist: bool = True) -> Path:
    root = repo.resolve()
    candidate = (root / relative).resolve(strict=False)
    if candidate != root and not candidate.is_relative_to(root):
        raise ValueError("path outside repository")
    if must_exist and not candidate.exists():
        raise ValueError(f"required path missing: {relative}")
    return candidate


def _git(repo: Path, *arguments: str, binary: bool = False) -> str | bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo.resolve()), *arguments],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("offline Git object verification failed")
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="strict").strip()


def git_json(repo: Path, revision: str, path: str) -> dict[str, Any]:
    payload = _git(repo, "show", f"{revision}:{path}", binary=True)
    assert isinstance(payload, bytes)
    try:
        value = json.loads(payload, object_pairs_hook=_reject_duplicates)
    except json.JSONDecodeError:
        raise ValueError("historical JSON object invalid") from None
    if not isinstance(value, dict):
        raise ValueError("historical JSON object must be an object")
    return value


def _git_blob(repo: Path, revision: str, path: str) -> bytes:
    payload = _git(repo, "show", f"{revision}:{path}", binary=True)
    assert isinstance(payload, bytes)
    return payload


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    expected_keys = {
        "authority",
        "history",
        "ledger_invariant",
        "review_quorum",
        "schema_anchor",
        "schema_version",
        "source_freeze",
        "successor_scope",
    }
    if set(contract) != expected_keys:
        raise ValueError("successor contract keys drift")
    if (
        contract.get("schema_version") != 1
        or contract.get("schema_anchor") != PHASE52_POST_LIVE_SUCCESSOR_V1
        or contract.get("authority") != AUTHORITY
        or contract.get("history") != list(HISTORY)
    ):
        raise ValueError("successor contract immutable fields drift")
    ledger = contract.get("ledger_invariant")
    if ledger != {
        "evidence_catalog_additions": [
            f"RDF-V19-{item}" for item in PROMOTED_REQUIREMENTS
        ],
        "new_last_verified_at": PROMOTED_AT,
        "new_status": "pass",
        "old_last_verified_at": None,
        "old_status": "pending",
        "promoted_requirement_ids": list(PROMOTED_REQUIREMENTS),
        "requirement_count": 36,
    }:
        raise ValueError("ledger invariant drift")
    freeze = contract.get("source_freeze")
    if freeze != {
        "paths": list(SOURCE_PATHS),
        "reviews_must_follow_source_commit": True,
    }:
        raise ValueError("source freeze contract drift")
    quorum = contract.get("review_quorum")
    if quorum != {
        "checkout_mode": "read-only",
        "minimum_reviewers": 2,
        "require_checkout_snapshots_equal": True,
        "require_distinct_reviewer_ids": True,
        "require_same_hash_set_sha256": True,
        "require_source_freeze_commit": True,
        "required_findings": [],
        "required_mutation_detected": False,
        "required_unresolved_high_count": 0,
        "required_verdict": "PASS",
    }:
        raise ValueError("review quorum contract drift")
    if contract.get("successor_scope") != {
        "phase53_reconciliation_is_read_only": True,
        "plans_09_10_may_refresh_observations_read_only": True,
        "protected_history_is_immutable": True,
    }:
        raise ValueError("successor scope drift")
    return {"status": "PASS", "schema_anchor": PHASE52_POST_LIVE_SUCCESSOR_V1}


def _rows_by_id(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = ledger.get("requirements")
    if not isinstance(rows, list) or len(rows) != 36:
        raise ValueError("ledger must contain exactly 36 rows")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("requirement_id"), str):
            raise ValueError("ledger row shape invalid")
        requirement_id = row["requirement_id"]
        if requirement_id in result:
            raise ValueError("ledger requirement IDs must be unique")
        result[requirement_id] = row
    return result


def validate_ledger_successor(
    old: dict[str, Any], new: dict[str, Any]
) -> dict[str, Any]:
    expected_top = {
        "schema_version",
        "milestone",
        "requirement_count",
        "evidence_catalog",
        "requirements",
    }
    if set(old) != expected_top or set(new) != expected_top:
        raise ValueError("ledger top-level shape drift")
    for key in ("schema_version", "milestone", "requirement_count"):
        if old[key] != new[key]:
            raise ValueError(f"ledger {key} changed")
    if old["requirement_count"] != 36:
        raise ValueError("ledger requirement_count must be 36")
    old_rows, new_rows = _rows_by_id(old), _rows_by_id(new)
    if set(old_rows) != set(new_rows):
        raise ValueError("ledger requirement ID set changed")
    for requirement_id in sorted(old_rows):
        before = old_rows[requirement_id]
        after = new_rows[requirement_id]
        if requirement_id not in PROMOTED_REQUIREMENTS:
            if before != after:
                raise ValueError("non-Phase52 ledger row changed")
            continue
        expected = copy.deepcopy(before)
        if (
            before.get("status") != "pending"
            or before.get("last_verified_at") is not None
        ):
            raise ValueError("Phase52 ledger predecessor state invalid")
        expected["status"] = "pass"
        expected["last_verified_at"] = PROMOTED_AT
        if after != expected:
            raise ValueError("Phase52 ledger promotion semantic drift")
    old_catalog, new_catalog = old["evidence_catalog"], new["evidence_catalog"]
    if not isinstance(old_catalog, dict) or not isinstance(new_catalog, dict):
        raise ValueError("ledger evidence catalog invalid")
    expected_additions = {f"RDF-V19-{item}" for item in PROMOTED_REQUIREMENTS}
    if set(new_catalog) - set(old_catalog) != expected_additions:
        raise ValueError("ledger evidence catalog additions drift")
    if set(old_catalog) - set(new_catalog):
        raise ValueError("ledger evidence catalog entry removed")
    for evidence_id, value in old_catalog.items():
        if new_catalog[evidence_id] != value:
            raise ValueError("existing ledger evidence catalog changed")
    for requirement_id in PROMOTED_REQUIREMENTS:
        evidence_id = f"RDF-V19-{requirement_id}"
        row = new_catalog.get(evidence_id)
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "sha256", "input_digest", "observed_at"}
            or row.get("path")
            != "modules/rustdesk-fleet/evidence/phase52/integrated-gate.json"
            or row.get("observed_at") != PROMOTED_AT
            or not _is_sha256(row.get("sha256"))
            or row.get("input_digest") != row.get("sha256")
        ):
            raise ValueError("new ledger evidence catalog entry invalid")
    return {
        "status": "PASS",
        "requirement_count": 36,
        "unique_requirement_count": 36,
        "promoted_requirement_ids": list(PROMOTED_REQUIREMENTS),
        "promotion_count": 4,
        "promoted_at": PROMOTED_AT,
        "unchanged_requirement_count": 32,
        "evidence_catalog_addition_count": 4,
    }


def verify_historical_successor(
    repo: Path, contract: dict[str, Any]
) -> dict[str, Any]:
    validate_contract(contract)
    rows = contract["history"]
    if len(rows) != 3 or len({row["commit"] for row in rows}) != 3:
        raise ValueError("history is cyclic, substituted, or has a fourth entry")
    if len({row["path"] for row in rows}) != 3:
        raise ValueError("history path set invalid")
    object_proofs: list[dict[str, str]] = []
    for row in rows:
        commit = row["commit"]
        parents = str(_git(repo, "show", "-s", "--format=%P", commit)).split()
        if not parents:
            raise ValueError("historical commit has no parent")
        before = _git_blob(repo, f"{commit}^", row["path"])
        after = _git_blob(repo, commit, row["path"])
        old_hash, new_hash = _sha256_bytes(before), _sha256_bytes(after)
        if old_hash != row["old_sha256"] or new_hash != row["new_sha256"]:
            raise ValueError("historical Git blob hash drift")
        object_proofs.append(
            {
                "commit": commit,
                "path": row["path"],
                "old_sha256": old_hash,
                "new_sha256": new_hash,
            }
        )
    ancestor = subprocess.run(
        ["git", "-C", str(repo.resolve()), "merge-base", "--is-ancestor", rows[0]["commit"], rows[1]["commit"]],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0
    third_parents = str(
        _git(repo, "show", "-s", "--format=%P", rows[2]["commit"])
    ).split()
    direct = third_parents == [rows[1]["commit"]]
    if not ancestor or not direct:
        raise ValueError("historical ancestry invalid or amended")
    ledger = validate_ledger_successor(
        git_json(repo, f"{rows[0]['commit']}^", rows[0]["path"]),
        git_json(repo, rows[0]["commit"], rows[0]["path"]),
    )
    return {
        "status": "PASS",
        "history_count": 3,
        "path_count": 3,
        "objects": object_proofs,
        "ancestry": {
            "first_is_ancestor_of_second": True,
            "second_is_direct_parent_of_third": True,
            "acyclic": True,
        },
        "ledger": ledger,
    }


def validate_source_freeze(
    repo: Path, expected_hashes: dict[str, str]
) -> dict[str, Any]:
    if not isinstance(expected_hashes, dict) or not expected_hashes:
        raise ValueError("source-freeze hash set missing")
    actual: dict[str, str] = {}
    for relative, expected in expected_hashes.items():
        if not isinstance(relative, str) or not _is_sha256(expected):
            raise ValueError("source-freeze entry invalid")
        path = _repo_path(repo, relative)
        if not path.is_file():
            raise ValueError("source-freeze path is not a file")
        actual[relative] = _sha256_path(path)
        if actual[relative] != expected:
            raise ValueError(f"source-freeze drift: {relative}")
    return {"status": "PASS", "source_hashes": actual}


def _assert_source_commit(repo: Path, source_commit: str) -> dict[str, str]:
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ValueError("source freeze commit invalid")
    subject = str(_git(repo, "show", "-s", "--format=%s", source_commit))
    if subject != "feat(52-08): freeze post-live successor verifier":
        raise ValueError("source freeze commit subject invalid")
    changed = str(
        _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", source_commit)
    ).splitlines()
    if set(changed) != set(SOURCE_PATHS) or len(changed) != len(SOURCE_PATHS):
        raise ValueError("source freeze commit must modify exactly six source files")
    hashes: dict[str, str] = {}
    for relative in SOURCE_PATHS:
        committed = _git_blob(repo, source_commit, relative)
        current = _repo_path(repo, relative).read_bytes()
        if current != committed:
            raise ValueError(f"source-freeze worktree drift: {relative}")
        hashes[relative] = _sha256_bytes(committed)
    return hashes


def _combined_hash_set(
    history: dict[str, Any],
    source_commit: str,
    source_hashes: dict[str, str],
) -> str:
    members: list[dict[str, str]] = []
    for row in history["objects"]:
        members.append({"kind": "history-old", "path": row["path"], "sha256": row["old_sha256"]})
        members.append({"kind": "history-new", "path": row["path"], "sha256": row["new_sha256"]})
    for path, digest in sorted(source_hashes.items()):
        members.append({"kind": "frozen-source", "path": path, "sha256": digest})
    members.append(
        {
            "kind": "source-commit",
            "path": "git",
            "sha256": hashlib.sha256(source_commit.encode("ascii")).hexdigest(),
        }
    )
    members.append(
        {
            "kind": "schema-anchor",
            "path": PHASE52_POST_LIVE_SUCCESSOR_V1,
            "sha256": hashlib.sha256(PHASE52_POST_LIVE_SUCCESSOR_V1.encode("ascii")).hexdigest(),
        }
    )
    return _sha256_bytes(_canonical_bytes(members))


def build_successor_attestation(repo: Path) -> dict[str, Any]:
    root = repo.resolve()
    contract = load_json_strict(_repo_path(root, CONTRACT_PATH))
    if not isinstance(contract, dict):
        raise ValueError("successor contract must be an object")
    history = verify_historical_successor(root, contract)
    source_commit = str(_git(root, "rev-parse", "HEAD"))
    source_hashes = _assert_source_commit(root, source_commit)
    anchor_locations: list[str] = []
    for relative in ANCHOR_PATHS:
        if PHASE52_POST_LIVE_SUCCESSOR_V1 not in _repo_path(root, relative).read_text(
            encoding="utf-8"
        ):
            raise ValueError("schema anchor missing")
        anchor_locations.append(relative)
    committed_at = str(_git(root, "show", "-s", "--format=%cI", source_commit))
    return {
        "schema_anchor": PHASE52_POST_LIVE_SUCCESSOR_V1,
        "schema_version": 1,
        "status": "PASS",
        "attested_at": committed_at,
        "source_freeze_commit": source_commit,
        "source_hashes": source_hashes,
        "anchor_locations": anchor_locations,
        "history": history,
        "ledger_successor": history["ledger"],
        "hash_set_sha256": _combined_hash_set(history, source_commit, source_hashes),
        "authority": dict(AUTHORITY),
        "read_only": True,
        "secret_material_present": False,
    }


def validate_independent_reviews(
    reviews: list[dict[str, Any]],
    expected_hash_set: str,
    source_freeze_commit: str,
) -> dict[str, Any]:
    if (
        not isinstance(reviews, list)
        or len(reviews) != 2
        or not _is_sha256(expected_hash_set)
        or not isinstance(source_freeze_commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_freeze_commit) is None
    ):
        raise ValueError("independent review quorum requires exactly two reviews")
    identities: list[str] = []
    expected_keys = {
        "schema_anchor",
        "reviewer_id",
        "checkout_mode",
        "source_freeze_commit",
        "verdict",
        "hash_set_sha256",
        "unresolved_high_count",
        "findings",
        "checkout_before",
        "checkout_after",
        "mutation_detected",
        "secret_material_present",
    }
    for review in reviews:
        if (
            not isinstance(review, dict)
            or set(review) != expected_keys
            or review.get("schema_anchor") != PHASE52_POST_LIVE_SUCCESSOR_V1
            or review.get("checkout_mode") != "read-only"
            or review.get("source_freeze_commit") != source_freeze_commit
            or review.get("verdict") != "PASS"
            or review.get("hash_set_sha256") != expected_hash_set
            or not _is_sha256(review.get("hash_set_sha256"))
            or type(review.get("unresolved_high_count")) is not int
            or review.get("unresolved_high_count") != 0
            or review.get("findings") != []
            or review.get("checkout_before") != review.get("checkout_after")
            or not _is_sha256(review.get("checkout_before"))
            or review.get("mutation_detected") is not False
            or review.get("secret_material_present") is not False
            or not isinstance(review.get("reviewer_id"), str)
            or re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", review["reviewer_id"]) is None
        ):
            raise ValueError("independent review rejected")
        identities.append(review["reviewer_id"])
    if len(set(identities)) != 2:
        raise ValueError("independent reviewer identities must be distinct")
    return {
        "status": "PASS",
        "reviewer_ids": identities,
        "review_count": 2,
        "hash_set_sha256": expected_hash_set,
        "unresolved_high_count": 0,
    }


def _load_attestation(path: Path) -> dict[str, Any]:
    value = load_json_strict(path)
    if not isinstance(value, dict):
        raise ValueError("attestation must be an object")
    return value


def verify_attestation(
    repo: Path,
    attestation: dict[str, Any],
    reviews: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = repo.resolve()
    if (
        attestation.get("schema_anchor") != PHASE52_POST_LIVE_SUCCESSOR_V1
        or attestation.get("schema_version") != 1
        or attestation.get("status") != "PASS"
        or attestation.get("authority") != AUTHORITY
        or attestation.get("read_only") is not True
        or attestation.get("secret_material_present") is not False
        or attestation.get("anchor_locations") != list(ANCHOR_PATHS)
    ):
        raise ValueError("attestation boundary invalid")
    source_commit = attestation.get("source_freeze_commit")
    source_hashes = _assert_source_commit(root, source_commit)
    if attestation.get("source_hashes") != source_hashes:
        raise ValueError("attestation source hash drift")
    validate_source_freeze(root, source_hashes)
    contract = load_json_strict(_repo_path(root, CONTRACT_PATH))
    history = verify_historical_successor(root, contract)
    if attestation.get("history") != history or attestation.get("ledger_successor") != history["ledger"]:
        raise ValueError("attestation historical proof drift")
    expected = _combined_hash_set(history, source_commit, source_hashes)
    if attestation.get("hash_set_sha256") != expected:
        raise ValueError("attestation combined hash-set drift")
    result: dict[str, Any] = {
        "status": "PASS",
        "source_freeze_commit": source_commit,
        "hash_set_sha256": expected,
        "authority": dict(AUTHORITY),
    }
    if reviews is not None:
        result["reviews"] = validate_independent_reviews(
            reviews,
            expected,
            source_commit,
        )
    return result


def reconcile_phase53_read_only(repo: Path) -> dict[str, Any]:
    root = repo.resolve()
    phase_dir = _repo_path(
        root,
        ".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge",
    )
    rows = []
    for path in sorted(phase_dir.glob("53-*-PLAN.md")):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha256_path(path),
                "summary_exists": path.with_name(path.name.replace("-PLAN.md", "-SUMMARY.md")).is_file(),
            }
        )
    return {
        "status": "PASS",
        "read_only": True,
        "mutation_performed": False,
        "phase53_plan_count": len(rows),
        "plans": rows,
        "authority": dict(AUTHORITY),
        "secret_material_present": False,
    }


def collect_read_only_observations(
    repo: Path, paths: Iterable[str | Path]
) -> dict[str, Any]:
    observations = []
    for relative in paths:
        path = _repo_path(repo, relative)
        if not path.is_file():
            raise ValueError("observation path must be a file")
        observations.append(
            {
                "path": path.relative_to(repo.resolve()).as_posix(),
                "sha256": _sha256_path(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return {
        "status": "PASS",
        "read_only": True,
        "mutation_performed": False,
        "observations": observations,
        "secret_material_present": False,
    }


def validate_retained_recovery_parity(repo: Path) -> dict[str, Any]:
    root = repo.resolve()
    integrated = load_json_strict(
        _repo_path(root, "modules/rustdesk-fleet/evidence/phase52/integrated-gate.json")
    )
    transaction = load_json_strict(
        _repo_path(root, "modules/rustdesk-fleet/evidence/phase52/gate-b-transaction.json")
    )
    if not isinstance(integrated, dict) or not isinstance(transaction, dict):
        raise ValueError("retained recovery evidence invalid")
    serialized = json.dumps([integrated, transaction], sort_keys=True)
    forbidden = (
        "BEGIN OPENSSH " + "PRIVATE KEY",
        "BEGIN " + "PRIVATE KEY",
    )
    if any(marker in serialized for marker in forbidden):
        raise ValueError("secret material marker in retained recovery evidence")
    return {
        "status": "PASS",
        "read_only": True,
        "mutation_performed": False,
        "evidence_sha256": {
            "integrated_gate": _sha256_path(
                _repo_path(root, "modules/rustdesk-fleet/evidence/phase52/integrated-gate.json")
            ),
            "gate_b_transaction": _sha256_path(
                _repo_path(root, "modules/rustdesk-fleet/evidence/phase52/gate-b-transaction.json")
            ),
        },
        "secret_material_present": False,
    }


def build_current_projection(
    attestation: dict[str, Any],
    phase53: dict[str, Any],
    recovery: dict[str, Any],
) -> dict[str, Any]:
    statuses = [attestation.get("status"), phase53.get("status"), recovery.get("status")]
    if statuses != ["PASS", "PASS", "PASS"]:
        raise ValueError("current projection inputs are not PASS")
    return {
        "schema_anchor": PHASE52_POST_LIVE_SUCCESSOR_V1,
        "status": "PASS",
        "input_statuses": statuses,
        "hash_set_sha256": attestation["hash_set_sha256"],
        "read_only": True,
        "mutation_performed": False,
        "authority": dict(AUTHORITY),
        "secret_material_present": False,
    }


def validate_junit_outcomes(
    junit_path: Path, expected_xfails: Iterable[str] = ()
) -> dict[str, Any]:
    root = ET.parse(junit_path).getroot()
    cases = list(root.iter("testcase"))
    failures = [case for case in cases if case.find("failure") is not None or case.find("error") is not None]
    xfails = []
    for case in cases:
        skipped = case.find("skipped")
        if skipped is not None and "xfail" in (skipped.get("type", "") + skipped.get("message", "")).lower():
            xfails.append(f"{case.get('classname', '')}::{case.get('name', '')}".strip(":"))
    expected = sorted(expected_xfails)
    if failures or (expected and sorted(xfails) != expected):
        raise ValueError("JUnit outcomes do not match the strict contract")
    return {
        "status": "PASS",
        "test_count": len(cases),
        "failure_count": 0,
        "xfail_nodeids": sorted(xfails),
    }


def validate_closeout(*inputs: dict[str, Any]) -> dict[str, Any]:
    if not inputs or any(item.get("status") != "PASS" for item in inputs):
        raise ValueError("closeout input is not PASS")
    if any(item.get("secret_material_present") is True for item in inputs):
        raise ValueError("closeout input contains secret material")
    return {
        "status": "PASS",
        "input_count": len(inputs),
        "authority": dict(AUTHORITY),
        "secret_material_present": False,
    }


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _add_repo(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=Path, default=Path.cwd())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    attest = subparsers.add_parser("attest")
    _add_repo(attest)
    attest.add_argument("--out", type=Path, required=True)

    verify = subparsers.add_parser("verify-attestation")
    _add_repo(verify)
    verify.add_argument("--attestation", type=Path, required=True)
    verify.add_argument("--review", type=Path, action="append", default=[])

    reconcile = subparsers.add_parser("reconcile-phase53")
    _add_repo(reconcile)
    reconcile.add_argument("--out", type=Path)

    refresh = subparsers.add_parser("refresh-read-only")
    _add_repo(refresh)
    refresh.add_argument("--input", action="append", default=[])
    refresh.add_argument("--out", type=Path)

    project = subparsers.add_parser("project-current")
    _add_repo(project)
    project.add_argument("--attestation", type=Path, default=ATTESTATION_PATH)
    project.add_argument("--out", type=Path)

    junit = subparsers.add_parser("verify-junit")
    junit.add_argument("--junit", type=Path, required=True)
    junit.add_argument("--expected-xfail", action="append", default=[])

    hygiene = subparsers.add_parser("record-secret-hygiene")
    _add_repo(hygiene)
    hygiene.add_argument("--input", action="append", default=[])
    hygiene.add_argument("--out", type=Path)

    close_inputs = subparsers.add_parser("verify-closeout-inputs")
    close_inputs.add_argument("--input", type=Path, action="append", required=True)

    close = subparsers.add_parser("verify-closeout")
    close.add_argument("--input", type=Path, action="append", required=True)
    return parser


def _emit(payload: dict[str, Any], output: Path | None = None) -> None:
    if output is not None:
        _write_json_atomic(payload, output)
    print(json.dumps(payload, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "attest":
            payload = build_successor_attestation(args.repo)
            _emit(payload, args.out)
        elif args.command == "verify-attestation":
            attestation = _load_attestation(args.attestation)
            reviews = [_load_attestation(path) for path in args.review]
            payload = verify_attestation(args.repo, attestation, reviews)
            _emit(payload)
        elif args.command == "reconcile-phase53":
            _emit(reconcile_phase53_read_only(args.repo), args.out)
        elif args.command == "refresh-read-only":
            _emit(collect_read_only_observations(args.repo, args.input), args.out)
        elif args.command == "project-current":
            attestation = _load_attestation(args.attestation)
            verified = verify_attestation(args.repo, attestation)
            phase53 = reconcile_phase53_read_only(args.repo)
            recovery = validate_retained_recovery_parity(args.repo)
            _emit(build_current_projection(verified, phase53, recovery), args.out)
        elif args.command == "verify-junit":
            _emit(validate_junit_outcomes(args.junit, args.expected_xfail))
        elif args.command == "record-secret-hygiene":
            payload = collect_read_only_observations(args.repo, args.input)
            payload["category"] = "secret-hygiene"
            _emit(payload, args.out)
        elif args.command in {"verify-closeout-inputs", "verify-closeout"}:
            values = [_load_attestation(path) for path in args.input]
            _emit(validate_closeout(*values))
        else:  # pragma: no cover - argparse owns the allowlist
            raise ValueError("unsupported command")
    except (OSError, ValueError, subprocess.SubprocessError, ET.ParseError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
