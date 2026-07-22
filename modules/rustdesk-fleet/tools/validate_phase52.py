#!/usr/bin/env python3
"""Fail-closed Phase 52 RustDesk supply/capacity/recovery validator."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPLY_CONTRACT = Path("modules/rustdesk-fleet/contracts/supply-chain.json")
SUPPLY_OBSERVATION = Path("modules/rustdesk-fleet/evidence/phase52/supply-observation.json")
CAPACITY_POLICY = Path("modules/rustdesk-fleet/contracts/capacity-policy.json")
PLACEMENT_DECISION = Path("modules/rustdesk-fleet/contracts/placement-decision.json")
CAPACITY_PROPOSAL = Path("modules/rustdesk-fleet/evidence/phase52/capacity-proposal.json")
SERVER_COMMIT = "9bae9f2f39d92c4b4ba2e28e089da5071897b22e"
CLIENT_COMMIT = "6c578292e8ebbbec708b76986ba8c4bc7c509747"
MULTIARCH_DIGEST = "sha256:10818ec05b179039c6660f4d8e74b303f0db2858bbad2b18e24992ea22d54cd6"
ARM64_IMAGE_DIGEST = "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
ZIP_SHA256 = "4998dd6d32431f9aaf5841663339793bc154d7152313e128832d6b610580abe4"
DEB_SHA256 = "ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0"
MSI_SHA256 = "c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa"
CANDIDATES = ("atius-srv-2", "atius-srv-3", "horistic-srv")
MAX_BYTES = (2**63) - 1
CAPACITY_RESERVATION_KEYS = (
    "loaded_image_bytes",
    "preserved_oci_archive_bytes",
    "peak_import_workspace_bytes",
    "backup_a_bytes",
    "backup_b_bytes",
    "combined_daily_log_budget_bytes",
    "log_retention_days",
    "log_reserve_30d_bytes",
    "state_growth_budget_bytes",
)
COUNTED_RESERVATION_KEYS = (
    "loaded_image_bytes",
    "preserved_oci_archive_bytes",
    "peak_import_workspace_bytes",
    "backup_a_bytes",
    "backup_b_bytes",
    "log_reserve_30d_bytes",
    "state_growth_budget_bytes",
)
MATERIALIZABLE_RESERVATION_KEYS = COUNTED_RESERVATION_KEYS[:5]
STAGE_FIELDS = (
    "supply_status",
    "capacity_status",
    "vault_status",
    "backup_status",
    "restore_status",
    "capacity_finalize_status",
    "rollback_status",
    "topology_security_status",
)
BOUNDED_FULL_GATE_WRITES = (
    "pinned-artifact-staging",
    "pinned-artifact-load",
    "state-only-backup-a",
    "state-only-backup-b",
    "disposable-isolated-restore-state",
    "redacted-evidence-write",
    "verified-drill-artifact-rollback-removal",
)


@dataclass(frozen=True)
class Finding:
    category: str
    path: str
    location: str


@dataclass
class CheckResult:
    id: str
    status: str
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def load_json_strict(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key rejected")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path.name}:{exc.lineno}") from None


def validate_repo_path(repo: Path, candidate: Path) -> Path:
    root = repo.resolve()
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("path is outside repository")
    return resolved


def derive_overall_status(results: list[CheckResult]) -> str:
    if any(item.status == "FAIL" for item in results):
        return "FAIL"
    if any(item.status == "BLOCKED" for item in results):
        return "BLOCKED"
    return "PASS"


def exit_code_for_status(status: str) -> int:
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[status]


def _finding(category: str, source: str, location: str = "contract") -> Finding:
    return Finding(category=category, path=source, location=location)


def _result(status: str, categories: list[str], source: str) -> CheckResult:
    return CheckResult(
        id="P52-SUPPLY-001",
        status=status,
        evidence_ids=["P52-EV-SUPPLY"],
        findings=[_finding(category, source) for category in sorted(set(categories))],
    )


def _check_result(check_id: str, status: str, categories: list[str], source: str) -> CheckResult:
    evidence = check_id.removeprefix("P52-").removesuffix("-001")
    return CheckResult(
        id=check_id,
        status=status,
        evidence_ids=[f"P52-EV-{evidence}"],
        findings=[_finding(category, source) for category in sorted(set(categories))],
    )


def _exact_keys(value: Any, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sha256(value: Any, prefix: bool = False) -> bool:
    pattern = r"sha256:[0-9a-f]{64}" if prefix else r"[0-9a-f]{64}"
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _bounded_int(value: Any, *, allow_zero: bool = True) -> bool:
    minimum = 0 if allow_zero else 1
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= MAX_BYTES


def pct_at_most(used: Any, total: Any, limit: Any) -> bool:
    """Compare raw integer counters without floats, rounding, or bool coercion."""
    return (
        _bounded_int(used)
        and _bounded_int(total, allow_zero=False)
        and _bounded_int(limit)
        and limit <= 100
        and used <= total
        and used * 100 <= total * limit
    )


def checked_add_bytes(*values: Any) -> int:
    total = 0
    for value in values:
        if not _bounded_int(value):
            raise ValueError("invalid byte counter")
        if total > MAX_BYTES - value:
            raise ValueError("byte counter overflow")
        total += value
    return total


def validate_capacity_policy(
    payload: dict[str, Any], source: str = "modules/rustdesk-fleet/contracts/capacity-policy.json"
) -> CheckResult:
    errors: list[str] = []
    expected_keys = {
        "schema_version",
        "workstream",
        "pre_disk_pct_max",
        "post_disk_pct_max",
        "inode_pct_max",
        "observation_max_age_seconds",
        "same_mount_required",
        "zero_or_unset_is_blocked",
        "reservations",
        "still_unmaterialized_policy",
        "backup_a_retention",
        "backup_b_retention",
        "remediation_policy",
        "zero_cleanup_candidates",
        "bounded_full_gate_write_allowlist",
        "bounded_writes_require_capacity_pass",
        "destructive_storage_mutation_default",
        "approval",
    }
    if not _exact_keys(payload, expected_keys):
        return _check_result("P52-CAPACITY-001", "FAIL", ["contract-shape"], source)
    if payload.get("schema_version") != 1 or payload.get("workstream") != "rustdesk-fleet":
        errors.append("contract-shape")
    if (payload.get("pre_disk_pct_max"), payload.get("post_disk_pct_max"), payload.get("inode_pct_max")) != (
        78,
        80,
        80,
    ):
        errors.append("threshold-drift")
    if not _bounded_int(payload.get("observation_max_age_seconds"), allow_zero=False):
        errors.append("observation-ttl")
    if payload.get("same_mount_required") is not True or payload.get("zero_or_unset_is_blocked") is not True:
        errors.append("fail-closed-policy-drift")

    reservations = payload.get("reservations")
    if not _exact_keys(reservations, set(CAPACITY_RESERVATION_KEYS)):
        errors.append("contract-shape")
        reservations = reservations if isinstance(reservations, dict) else {}
    if any(not _bounded_int(reservations.get(key), allow_zero=False) for key in CAPACITY_RESERVATION_KEYS):
        errors.append("invalid-reservation")
    expected_approved = {
        "combined_daily_log_budget_bytes": 134_217_728,
        "log_retention_days": 30,
        "log_reserve_30d_bytes": 4_026_531_840,
        "state_growth_budget_bytes": 4_294_967_296,
        "backup_a_bytes": 4_294_967_296,
        "backup_b_bytes": 4_294_967_296,
    }
    if any(reservations.get(key) != value for key, value in expected_approved.items()):
        errors.append("approved-reservation-drift")
    if reservations.get("combined_daily_log_budget_bytes", 0) * reservations.get(
        "log_retention_days", 0
    ) != reservations.get("log_reserve_30d_bytes"):
        errors.append("log-reservation-reconciliation")
    if payload.get("still_unmaterialized_policy") != list(COUNTED_RESERVATION_KEYS):
        errors.append("unmaterialized-policy-drift")

    expected_retention = {
        "retain_until": "phase57-pass-plus-30-days",
        "deletion_requires_new_explicit_approval": True,
    }
    for key, destination in (
        ("backup_a_retention", "candidate-local"),
        ("backup_b_retention", "modules/fleet-backup:gdrive"),
    ):
        retention = payload.get(key)
        if not isinstance(retention, dict) or retention != {"destination": destination, **expected_retention}:
            errors.append("backup-retention-drift")
    if payload.get("remediation_policy") != "none":
        errors.append("remediation-authority-drift")
    if payload.get("zero_cleanup_candidates") != ["atius-srv-2", "atius-srv-3"]:
        errors.append("zero-cleanup-candidate-drift")
    if payload.get("bounded_full_gate_write_allowlist") != list(BOUNDED_FULL_GATE_WRITES):
        errors.append("bounded-write-allowlist-drift")
    if payload.get("bounded_writes_require_capacity_pass") is not True:
        errors.append("bounded-write-precondition-drift")
    if payload.get("destructive_storage_mutation_default") != "blocked":
        errors.append("destructive-mutation-policy-drift")

    approval = payload.get("approval")
    if not isinstance(approval, dict) or set(approval) != {
        "status",
        "accountable",
        "approved_at",
        "source_path",
        "source_sha256",
    }:
        errors.append("approval-shape")
    elif (
        approval.get("status") != "approved"
        or approval.get("accountable") != "Giovanni Muniz"
        or approval.get("approved_at") != "2026-07-22T00:51:46Z"
        or approval.get("source_path")
        != ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-OPERATIONAL-DECISIONS.md"
        or not _sha256(approval.get("source_sha256"))
    ):
        errors.append("approval-drift")
    return _check_result("P52-CAPACITY-001", "PASS" if not errors else "FAIL", errors, source)


def _raw_counter_errors(sample: Any) -> list[str]:
    if not isinstance(sample, dict):
        return ["raw-counter-shape"]
    required_strings = (
        "observed_at",
        "hostname",
        "architecture",
        "filesystem_source",
        "mount_point",
        "podman_graphroot",
        "podman_version",
        "resource_wrapper",
        "resource_profile",
        "command_version",
    )
    required_ints = (
        "total_bytes",
        "used_bytes",
        "available_bytes",
        "inode_total",
        "inode_used",
        "inode_available",
    )
    errors: list[str] = []
    if any(not isinstance(sample.get(key), str) or not sample.get(key) for key in required_strings):
        errors.append("raw-counter-shape")
    if any(not _bounded_int(sample.get(key)) for key in required_ints):
        errors.append("raw-counter-shape")
    if sample.get("read_only") is not True or sample.get("mutation_performed") is not False:
        errors.append("observation-mutation")
    if not errors:
        if sample["used_bytes"] + sample["available_bytes"] != sample["total_bytes"]:
            errors.append("byte-counter-reconciliation")
        if sample["inode_used"] + sample["inode_available"] != sample["inode_total"]:
            errors.append("inode-counter-reconciliation")
        if sample["total_bytes"] <= 0 or sample["inode_total"] <= 0:
            errors.append("raw-counter-shape")
    return errors


def _is_current(timestamp: Any, max_age: int, now: datetime | None = None) -> bool:
    parsed = _parse_utc(timestamp)
    current = now or datetime.now(timezone.utc)
    if parsed is None:
        return False
    age = (current - parsed).total_seconds()
    return -300 <= age <= max_age


def derive_candidate_capacity(
    sample: dict[str, Any], policy: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    reservations = policy["reservations"]
    try:
        required = checked_add_bytes(*(reservations[key] for key in COUNTED_RESERVATION_KEYS))
    except (KeyError, ValueError):
        return {
            "status": "NO-GO",
            "pre_disk_ok": False,
            "inode_ok": False,
            "projected_post_ok": False,
            "headroom_ok": False,
            "capacity_finalize_status": "NO-GO",
            "required_incremental_bytes": None,
            "still_unmaterialized_reservations": None,
        }
    shape_ok = not _raw_counter_errors(sample)
    current = shape_ok and _is_current(sample.get("observed_at"), policy["observation_max_age_seconds"], now)
    pre_ok = shape_ok and pct_at_most(sample["used_bytes"], sample["total_bytes"], policy["pre_disk_pct_max"])
    inode_ok = shape_ok and pct_at_most(sample["inode_used"], sample["inode_total"], policy["inode_pct_max"])
    try:
        projected_used = checked_add_bytes(sample.get("used_bytes"), required)
    except ValueError:
        projected_used = None
    projected_ok = projected_used is not None and pct_at_most(
        projected_used, sample.get("total_bytes"), policy["post_disk_pct_max"]
    )
    headroom_ok = shape_ok and sample["available_bytes"] >= required

    finalize_status = "PENDING"
    still_unmaterialized = required
    finalize = sample.get("capacity_finalize")
    if finalize is not None:
        finalize_errors = _raw_counter_errors(finalize)
        if not _is_current(finalize.get("observed_at"), policy["observation_max_age_seconds"], now):
            finalize_errors.append("stale-finalize-observation")
        if finalize.get("filesystem_source") != sample.get("filesystem_source") or finalize.get(
            "mount_point"
        ) != sample.get("mount_point"):
            finalize_errors.append("finalize-mount-mismatch")
        if finalize.get("total_bytes") != sample.get("total_bytes"):
            finalize_errors.append("finalize-total-mismatch")
        actual_a = finalize.get("actual_backup_a_bytes")
        actual_b = finalize.get("actual_backup_b_bytes")
        if not _bounded_int(actual_a, allow_zero=False) or actual_a > reservations["backup_a_bytes"]:
            finalize_errors.append("backup-a-reserve-exceeded")
        if not _bounded_int(actual_b, allow_zero=False) or actual_b > reservations["backup_b_bytes"]:
            finalize_errors.append("backup-b-reserve-exceeded")
        materialized = finalize.get("materialized_reservations")
        if not isinstance(materialized, dict) or set(materialized) - set(MATERIALIZABLE_RESERVATION_KEYS):
            finalize_errors.append("materialized-reservation-shape")
            materialized = {}
        for key, value in materialized.items():
            if not _bounded_int(value, allow_zero=False) or value > reservations[key]:
                finalize_errors.append("materialized-reservation-mismatch")
        if materialized.get("backup_a_bytes") != actual_a or materialized.get("backup_b_bytes") != actual_b:
            finalize_errors.append("backup-materialized-mismatch")
        try:
            still_unmaterialized = checked_add_bytes(
                *(reservations[key] for key in COUNTED_RESERVATION_KEYS if key not in materialized)
            )
            final_projected = checked_add_bytes(finalize.get("used_bytes"), still_unmaterialized)
        except ValueError:
            finalize_errors.append("finalize-overflow")
            final_projected = None
        if final_projected is None or not pct_at_most(
            final_projected, finalize.get("total_bytes"), policy["post_disk_pct_max"]
        ):
            finalize_errors.append("finalize-post-threshold")
        if not pct_at_most(finalize.get("inode_used"), finalize.get("inode_total"), policy["inode_pct_max"]):
            finalize_errors.append("finalize-inode-threshold")
        finalize_status = "PASS" if not finalize_errors else "NO-GO"

    status = "PASS" if all((current, pre_ok, inode_ok, projected_ok, headroom_ok)) else "NO-GO"
    if finalize is not None and finalize_status != "PASS":
        status = "NO-GO"
    return {
        "status": status,
        "pre_disk_ok": pre_ok,
        "inode_ok": inode_ok,
        "projected_post_ok": projected_ok,
        "headroom_ok": headroom_ok,
        "capacity_finalize_status": finalize_status,
        "required_incremental_bytes": required,
        "still_unmaterialized_reservations": still_unmaterialized,
    }


def validate_capacity_observation(
    sample: dict[str, Any],
    policy: dict[str, Any],
    source: str = "capacity-observation",
    *,
    now: datetime | None = None,
) -> CheckResult:
    errors = _raw_counter_errors(sample)
    blocked: list[str] = []
    if not _is_current(sample.get("observed_at"), policy.get("observation_max_age_seconds", 0), now):
        blocked.append("stale-observation")
    finalize = sample.get("capacity_finalize") if isinstance(sample, dict) else None
    if isinstance(finalize, dict):
        if finalize.get("filesystem_source") != sample.get("filesystem_source") or finalize.get(
            "mount_point"
        ) != sample.get("mount_point"):
            errors.append("finalize-mount-mismatch")
        derived = derive_candidate_capacity(sample, policy, now=now)
        if derived["capacity_finalize_status"] != "PASS":
            blocked.append("capacity-finalize-no-go")
    elif isinstance(sample, dict) and any(key in sample for key in ("disk_percent", "inode_percent")):
        errors.append("raw-counter-shape")
    if not errors and not blocked and derive_candidate_capacity(sample, policy, now=now)["status"] != "PASS":
        blocked.append("capacity-no-go")
    status = "FAIL" if errors else "BLOCKED" if blocked else "PASS"
    return _check_result("P52-CAPACITY-001", status, errors + blocked, source)


def _candidate_verdict(candidate: dict[str, Any]) -> str:
    if candidate.get("evaluated") is not True:
        return "PENDING"
    stages = [candidate.get(field) for field in STAGE_FIELDS]
    if stages and all(status == "PASS" for status in stages):
        return "PASS"
    if any(status in {"NO-GO", "FAIL", "BLOCKED"} for status in stages):
        return "NO-GO"
    return "PENDING"


def _horistic_contract_valid(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or candidate.get("client_colocation") is not True:
        return False
    for field in (
        "server_client_resource_domains",
        "server_client_evidence_domains",
        "server_client_rollback_domains",
    ):
        domains = candidate.get(field)
        if (
            not isinstance(domains, dict)
            or set(domains) != {"server", "client"}
            or not all(isinstance(value, str) and value for value in domains.values())
            or domains["server"] == domains["client"]
        ):
            return False
    return all(candidate.get(field) is True for field in (
        "phase53_review_required",
        "phase54_review_required",
        "phase57_review_required",
    ))


def derive_placement(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list) or len(candidates) != len(CANDIDATES):
        return {"selected_candidate": None, "overall_status": "BLOCKED", "verdicts": [], "errors": ["candidate-shape"]}
    verdicts = [_candidate_verdict(item) if isinstance(item, dict) else "PENDING" for item in candidates]
    errors: list[str] = []
    selected: str | None = None
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or candidate.get("candidate") != CANDIDATES[index]:
            errors.append("candidate-shape")
            continue
        if candidate.get("evaluated") is True and any(verdict != "NO-GO" for verdict in verdicts[:index]):
            errors.append("candidate-order-bypass")
        if verdicts[index] == "PASS" and selected is None and all(
            verdict == "NO-GO" for verdict in verdicts[:index]
        ):
            selected = CANDIDATES[index]
        if selected is not None and any(
            isinstance(later, dict) and later.get("evaluated") is True for later in candidates[index + 1 :]
        ):
            errors.append("candidate-order-bypass")
    if selected == "horistic-srv" and not _horistic_contract_valid(candidates[2]):
        errors.append("horistic-colocation-contract")
        selected = None
    return {
        "selected_candidate": selected,
        "overall_status": "PASS" if selected is not None and not errors else "BLOCKED",
        "verdicts": verdicts,
        "errors": sorted(set(errors)),
    }


def validate_placement_decision(
    payload: dict[str, Any], source: str = "modules/rustdesk-fleet/contracts/placement-decision.json"
) -> CheckResult:
    errors: list[str] = []
    blocked: list[str] = []
    expected_top = {
        "schema_version",
        "workstream",
        "candidate_order",
        "candidates",
        "selected_candidate",
        "overall_status",
        "windows_install_performed",
        "windows_access_proven",
        "cold_standby_claimed",
    }
    if not _exact_keys(payload, expected_top):
        return _check_result("P52-PLACEMENT-001", "FAIL", ["contract-shape"], source)
    if payload.get("schema_version") != 1 or payload.get("workstream") != "rustdesk-fleet" or payload.get(
        "candidate_order"
    ) != list(CANDIDATES):
        errors.append("contract-shape")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        errors.append("candidate-shape")
        candidates = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or candidate.get("candidate") != CANDIDATES[index]:
            errors.append("candidate-shape")
            continue
        base_keys = {"candidate", "evaluated", *STAGE_FIELDS, "evidence_ids", "verdict"}
        horistic_keys = {
            "client_colocation",
            "server_client_resource_domains",
            "server_client_evidence_domains",
            "server_client_rollback_domains",
            "phase53_review_required",
            "phase54_review_required",
            "phase57_review_required",
        }
        if set(candidate) != (base_keys | horistic_keys if index == 2 else base_keys):
            errors.append("candidate-shape" if index < 2 else "horistic-colocation-contract")
        if not isinstance(candidate.get("evaluated"), bool):
            errors.append("candidate-shape")
        if any(candidate.get(field) not in {"PASS", "NO-GO", "PENDING", "SKIPPED_BY_GATE"} for field in STAGE_FIELDS):
            errors.append("stage-status-shape")
        if candidate.get("verdict") != _candidate_verdict(candidate):
            errors.append("stored-verdict-drift")
        if not isinstance(candidate.get("evidence_ids"), list) or not all(
            isinstance(item, str) and item for item in candidate.get("evidence_ids", [])
        ):
            errors.append("evidence-id-shape")
    if len(candidates) == 3 and not _horistic_contract_valid(candidates[2]):
        errors.append("horistic-colocation-contract")
    derived = derive_placement(payload)
    errors.extend(derived["errors"])
    if payload.get("selected_candidate") != derived["selected_candidate"] or payload.get(
        "overall_status"
    ) != derived["overall_status"]:
        errors.append("stored-verdict-drift")
    if payload.get("windows_install_performed") is not False or payload.get("windows_access_proven") is not False:
        errors.append("windows-phase-boundary")
    if payload.get("cold_standby_claimed") is not False:
        errors.append("premature-standby-claim")
    if not errors and derived["overall_status"] != "PASS":
        blocked.append("placement-pending")
    status = "FAIL" if errors else "BLOCKED" if blocked else "PASS"
    return _check_result("P52-PLACEMENT-001", status, errors + blocked, source)


def validate_supply_contract(
    payload: dict[str, Any], source: str = "modules/rustdesk-fleet/contracts/supply-chain.json"
) -> CheckResult:
    errors: list[str] = []
    if not _exact_keys(payload, {"schema_version", "workstream", "policy", "server", "clients"}):
        return _result("FAIL", ["contract-shape"], source)
    if payload.get("schema_version") != 1 or payload.get("workstream") != "rustdesk-fleet":
        errors.append("contract-shape")

    policy = payload.get("policy")
    if not _exact_keys(
        policy,
        {
            "automatic_pin_refresh",
            "build_on_target",
            "candidate_admission_performed",
            "managed_cache_root",
            "observation_ttl_seconds",
            "windows_install_performed",
        },
    ):
        errors.append("contract-shape")
        policy = policy if isinstance(policy, dict) else {}
    if policy.get("automatic_pin_refresh") is not False:
        errors.append("automatic-pin-refresh")
    if policy.get("build_on_target") is not False:
        errors.append("target-build-enabled")
    if policy.get("candidate_admission_performed") is not False:
        errors.append("candidate-admission-claimed")
    if policy.get("windows_install_performed") is not False:
        errors.append("windows-install-attempt")
    if not _positive_int(policy.get("observation_ttl_seconds")):
        errors.append("invalid-observation-ttl")
    cache_root = policy.get("managed_cache_root")
    if not isinstance(cache_root, str) or not cache_root.startswith("/") or "/GitHub/omni-srv-admin" in cache_root:
        errors.append("managed-cache-inside-repo")

    server = payload.get("server")
    if not _exact_keys(
        server,
        {
            "version",
            "tag",
            "commit",
            "git_repository",
            "release_api_url",
            "candidates",
            "classic_image",
            "release_zip",
        },
    ):
        errors.append("contract-shape")
        server = server if isinstance(server, dict) else {}
    if server.get("version") != "1.1.15" or server.get("tag") != "1.1.15":
        errors.append("mutable-reference" if server.get("tag") == "latest" else "server-version-drift")
    if server.get("commit") != SERVER_COMMIT:
        errors.append("server-commit-drift")
    if server.get("git_repository") != "https://github.com/rustdesk/rustdesk-server.git":
        errors.append("server-source-drift")
    if server.get("release_api_url") != "https://api.github.com/repos/rustdesk/rustdesk-server/releases/tags/1.1.15":
        errors.append("server-source-drift")

    image = server.get("classic_image")
    image_keys = {
        "repository",
        "tag_reference",
        "immutable_reference",
        "registry_tag_api_url",
        "multiarch_digest",
        "linux_arm64_digest",
        "architecture",
        "os",
        "cache_path",
        "phase52_action",
        "install_phase",
    }
    if not _exact_keys(image, image_keys):
        errors.append("contract-shape")
        image = image if isinstance(image, dict) else {}
    if image.get("multiarch_digest") != MULTIARCH_DIGEST or not _sha256(image.get("multiarch_digest"), True):
        errors.append("multiarch-digest-drift")
    if image.get("linux_arm64_digest") != ARM64_IMAGE_DIGEST or not _sha256(
        image.get("linux_arm64_digest"), True
    ):
        errors.append("arm64-digest-drift")
    if image.get("architecture") != "arm64" or image.get("os") != "linux":
        errors.append("server-architecture-drift")
    if image.get("immutable_reference") != f"docker.io/rustdesk/rustdesk-server@{ARM64_IMAGE_DIGEST}":
        errors.append("mutable-reference")
    if image.get("phase52_action") != "verify-and-stage" or image.get("install_phase") != 53:
        errors.append("phase-boundary-drift")

    release_zip = server.get("release_zip")
    artifact_keys = {
        "asset_name",
        "source_url",
        "sha256",
        "size_bytes",
        "architecture",
        "cache_path",
        "phase52_action",
        "install_phase",
    }
    if not _exact_keys(release_zip, artifact_keys):
        errors.append("contract-shape")
        release_zip = release_zip if isinstance(release_zip, dict) else {}
    if release_zip.get("sha256") != ZIP_SHA256 or not _sha256(release_zip.get("sha256")):
        errors.append("release-zip-checksum-drift")
    if release_zip.get("architecture") != "linux-arm64v8":
        errors.append("server-architecture-drift")
    if not _positive_int(release_zip.get("size_bytes")):
        errors.append("invalid-byte-size")

    candidates = server.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        errors.append("candidate-set-drift")
        candidates = candidates if isinstance(candidates, list) else []
    elif [item.get("host") for item in candidates if isinstance(item, dict)] != list(CANDIDATES):
        errors.append("candidate-set-drift")
    candidate_keys = {
        "host",
        "linux_arm64_digest",
        "selected",
        "client_colocation_if_selected",
        "server_identity_domain",
        "future_client_identity_domain",
    }
    for index, candidate in enumerate(candidates):
        if not _exact_keys(candidate, candidate_keys):
            errors.append("candidate-shape")
            continue
        if candidate.get("linux_arm64_digest") != ARM64_IMAGE_DIGEST:
            errors.append("candidate-artifact-drift")
        if candidate.get("selected") is not False:
            errors.append("candidate-admission-claimed")
        expected_colocation = index == 2
        if candidate.get("client_colocation_if_selected") is not expected_colocation:
            errors.append("horistic-colocation-drift")
        if candidate.get("server_identity_domain") == candidate.get("future_client_identity_domain"):
            errors.append("identity-domain-conflation")

    clients = payload.get("clients")
    if not _exact_keys(
        clients,
        {"version", "tag", "commit", "git_repository", "release_api_url", "linux_arm64_deb", "windows_x86_64_msi"},
    ):
        errors.append("contract-shape")
        clients = clients if isinstance(clients, dict) else {}
    if clients.get("version") != "1.4.9" or clients.get("tag") != "1.4.9":
        errors.append("mutable-reference" if clients.get("tag") == "latest" else "client-version-drift")
    if clients.get("commit") != CLIENT_COMMIT:
        errors.append("client-commit-drift")
    if clients.get("git_repository") != "https://github.com/rustdesk/rustdesk.git":
        errors.append("client-source-drift")
    if clients.get("release_api_url") != "https://api.github.com/repos/rustdesk/rustdesk/releases/tags/1.4.9":
        errors.append("client-source-drift")

    deb = clients.get("linux_arm64_deb")
    deb_keys = artifact_keys | {"fleet_install_phase"}
    if not _exact_keys(deb, deb_keys):
        errors.append("contract-shape")
        deb = deb if isinstance(deb, dict) else {}
    if deb.get("sha256") != DEB_SHA256 or not _sha256(deb.get("sha256")):
        errors.append("linux-deb-checksum-drift")
    if deb.get("architecture") != "arm64":
        errors.append("linux-client-architecture-drift")
    if deb.get("phase52_action") != "verify-and-stage" or deb.get("install_phase") != 54 or deb.get(
        "fleet_install_phase"
    ) != 55:
        errors.append("phase-boundary-drift")
    if not _positive_int(deb.get("size_bytes")):
        errors.append("invalid-byte-size")

    msi = clients.get("windows_x86_64_msi")
    if not _exact_keys(msi, artifact_keys):
        errors.append("contract-shape")
        msi = msi if isinstance(msi, dict) else {}
    if msi.get("sha256") != MSI_SHA256 or not _sha256(msi.get("sha256")):
        errors.append("windows-msi-checksum-drift")
    if msi.get("architecture") != "x86_64":
        errors.append("windows-client-architecture-drift")
    if msi.get("phase52_action") != "verify-and-stage" or msi.get("install_phase") != 54:
        errors.append("windows-install-attempt")
    if not _positive_int(msi.get("size_bytes")):
        errors.append("invalid-byte-size")

    for artifact in (image, release_zip, deb, msi):
        cache_path = artifact.get("cache_path") if isinstance(artifact, dict) else None
        if not isinstance(cache_path, str) or not isinstance(cache_root, str) or not cache_path.startswith(f"{cache_root}/"):
            errors.append("managed-cache-path-drift")
        source_url = artifact.get("source_url") if isinstance(artifact, dict) else None
        if source_url is not None and (not isinstance(source_url, str) or not source_url.startswith("https://github.com/rustdesk/")):
            errors.append("artifact-source-drift")

    return _result("PASS" if not errors else "FAIL", errors, source)


def validate_supply_observation(
    observation: dict[str, Any],
    contract: dict[str, Any],
    source: str = "supply-observation.json",
    *,
    repo: Path | None = None,
    allowed_cache_root: Path | None = None,
) -> CheckResult:
    fail: list[str] = []
    blocked: list[str] = []
    expected_keys = {
        "schema_version",
        "phase",
        "workstream",
        "observed_at",
        "source_urls",
        "input_digests",
        "server",
        "clients",
        "classic_image",
        "artifacts",
        "windows_install_performed",
        "candidate_admission_performed",
        "secret_material_present",
        "findings",
        "status",
    }
    if not _exact_keys(observation, expected_keys):
        return _result("FAIL", ["observation-shape"], source)
    if observation.get("schema_version") != 1 or observation.get("phase") != 52 or observation.get(
        "workstream"
    ) != "rustdesk-fleet":
        fail.append("observation-shape")

    observed_at = observation.get("observed_at")
    parsed = _parse_utc(observed_at)
    if parsed is None:
        fail.append("observation-timestamp")
    else:
        age = (datetime.now(timezone.utc) - parsed).total_seconds()
        if age < -300 or age > contract["policy"]["observation_ttl_seconds"]:
            blocked.append("stale-observation")

    expected_sources = sorted(
        {
            contract["server"]["git_repository"],
            contract["server"]["release_api_url"],
            contract["server"]["classic_image"]["registry_tag_api_url"],
            contract["server"]["release_zip"]["source_url"],
            contract["clients"]["git_repository"],
            contract["clients"]["release_api_url"],
            contract["clients"]["linux_arm64_deb"]["source_url"],
            contract["clients"]["windows_x86_64_msi"]["source_url"],
        }
    )
    if observation.get("source_urls") != expected_sources:
        fail.append("official-source-drift")
    if observation.get("server") != {"tag": "1.1.15", "commit": SERVER_COMMIT}:
        fail.append("server-tag-observation-drift")
    if observation.get("clients") != {"tag": "1.4.9", "commit": CLIENT_COMMIT}:
        fail.append("client-tag-observation-drift")
    expected_image = {
        "tag": "1.1.15",
        "multiarch_digest": MULTIARCH_DIGEST,
        "linux_arm64_digest": ARM64_IMAGE_DIGEST,
        "architecture": "arm64",
        "os": "linux",
        "inspection_method": "docker-hub-platform-manifest+podman-image-inspect",
    }
    if observation.get("classic_image") != expected_image:
        fail.append("image-observation-drift")
    if observation.get("windows_install_performed") is not False:
        fail.append("windows-install-attempt")
    if observation.get("candidate_admission_performed") is not False:
        fail.append("candidate-admission-claimed")
    if observation.get("secret_material_present") is not False:
        fail.append("secret-material")
    if observation.get("findings") != []:
        fail.append("unexpected-findings")

    input_digests = observation.get("input_digests")
    if repo is not None:
        expected_inputs = collect_input_digests(repo, [SUPPLY_CONTRACT])
        if input_digests != expected_inputs:
            blocked.append("stale-input-digest")
    elif not isinstance(input_digests, list):
        fail.append("input-digest-shape")

    artifacts = observation.get("artifacts")
    if not isinstance(artifacts, list) or [item.get("kind") for item in artifacts if isinstance(item, dict)] != [
        "server-oci-archive",
        "server-release-zip",
        "linux-client-deb",
        "windows-client-msi",
    ]:
        fail.append("artifact-set-drift")
        artifacts = artifacts if isinstance(artifacts, list) else []
    expected_static = {
        "server-release-zip": (ZIP_SHA256, 5494849, "linux-arm64v8"),
        "linux-client-deb": (DEB_SHA256, 21694032, "arm64"),
        "windows-client-msi": (MSI_SHA256, 24825856, "x86_64"),
    }
    cache_root = (allowed_cache_root or Path(contract["policy"]["managed_cache_root"])).resolve()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {
            "kind",
            "source_url",
            "cache_path",
            "size_bytes",
            "sha256",
            "architecture",
            "inspection_method",
        }:
            fail.append("artifact-observation-shape")
            continue
        kind = artifact["kind"]
        if kind in expected_static:
            expected_sha, expected_size, expected_arch = expected_static[kind]
            if (artifact.get("sha256"), artifact.get("size_bytes"), artifact.get("architecture")) != (
                expected_sha,
                expected_size,
                expected_arch,
            ):
                fail.append("artifact-byte-observation-drift")
        elif kind == "server-oci-archive":
            if not _sha256(artifact.get("sha256")) or not _positive_int(artifact.get("size_bytes")) or artifact.get(
                "architecture"
            ) != "arm64":
                fail.append("oci-archive-observation-drift")
        cache_path = Path(artifact.get("cache_path", "")).resolve(strict=False)
        if not cache_path.is_relative_to(cache_root):
            fail.append("cache-path-outside-managed-root")
            continue
        if not cache_path.is_file():
            blocked.append("cached-asset-missing")
            continue
        if cache_path.stat().st_size != artifact.get("size_bytes") or _sha256_file(cache_path) != artifact.get(
            "sha256"
        ):
            blocked.append("cached-asset-drift")

    computed = "FAIL" if fail else "BLOCKED" if blocked else "PASS"
    if observation.get("status") != computed:
        if computed == "PASS":
            fail.append("stored-verdict-drift")
        else:
            blocked.append("stored-verdict-drift")
    categories = fail + blocked
    return _result("FAIL" if fail else "BLOCKED" if blocked else "PASS", categories, source)


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def verify_or_quarantine_file(path: Path, expected_sha256: str) -> Path | None:
    if _sha256_file(path) == expected_sha256:
        return None
    quarantine_dir = path.parent / "quarantine"
    quarantine_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = quarantine_dir / f"{path.name}.sha256-mismatch"
    if target.exists():
        target = quarantine_dir / f"{path.name}.{_sha256_file(path)[:12]}.sha256-mismatch"
    os.replace(path, target)
    os.chmod(target, 0o600)
    return target


def _download_verified(url: str, destination: Path, expected_sha256: str, expected_size: int) -> dict[str, Any]:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == expected_size and _sha256_file(destination) == expected_sha256:
        return {"size_bytes": expected_size, "sha256": expected_sha256}
    temporary = destination.with_name(f".{destination.name}.download")
    temporary.unlink(missing_ok=True)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "omni-srv-admin-phase52/1"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as handle:
            shutil.copyfileobj(response, handle, length=1024 * 1024)
        os.chmod(temporary, 0o600)
        if temporary.stat().st_size != expected_size or _sha256_file(temporary) != expected_sha256:
            verify_or_quarantine_file(temporary, expected_sha256)
            raise ValueError("downloaded artifact failed checksum or size")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"size_bytes": destination.stat().st_size, "sha256": _sha256_file(destination)}


def _http_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "omni-srv-admin-phase52/1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("official JSON response is not an object")
    return payload


def _resolve_tag_commit(repository: str, tag: str) -> str:
    completed = subprocess.run(
        ["git", "ls-remote", "--tags", repository, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("official git tag resolution failed")
    rows = [line.split() for line in completed.stdout.splitlines() if line.strip()]
    peeled = [sha for sha, ref in rows if ref.endswith("^{}")]
    direct = [sha for sha, ref in rows if ref == f"refs/tags/{tag}"]
    commits = peeled or direct
    if len(commits) != 1 or not re.fullmatch(r"[0-9a-f]{40}", commits[0]):
        raise ValueError("official git tag resolution is ambiguous")
    return commits[0]


def _release_asset(release: dict[str, Any], asset_name: str) -> dict[str, Any]:
    matches = [item for item in release.get("assets", []) if isinstance(item, dict) and item.get("name") == asset_name]
    if len(matches) != 1:
        raise ValueError("official release asset is absent or ambiguous")
    return matches[0]


def _zip_arm64(path: Path) -> bool:
    with zipfile.ZipFile(path) as archive:
        binaries = [name for name in archive.namelist() if Path(name).name in {"hbbs", "hbbr"}]
        if {Path(name).name for name in binaries} != {"hbbs", "hbbr"}:
            return False
        for name in binaries:
            header = archive.read(name)[:20]
            if len(header) < 20 or header[:4] != b"\x7fELF" or struct.unpack("<H", header[18:20])[0] != 183:
                return False
    return True


def _run_checked(command: list[str], timeout: int) -> str:
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise ValueError("guarded artifact inspection failed")
    return completed.stdout.strip()


def _stage_oci(contract: dict[str, Any]) -> dict[str, Any]:
    image = contract["server"]["classic_image"]
    reference = image["immutable_reference"]
    destination = Path(image["cache_path"])
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _run_checked(["podman", "pull", "--arch", "arm64", "--os", "linux", reference], 300)
    inspect = json.loads(_run_checked(["podman", "image", "inspect", reference], 60))
    if not isinstance(inspect, list) or len(inspect) != 1 or inspect[0].get("Architecture") != "arm64" or inspect[0].get(
        "Os"
    ) != "linux":
        raise ValueError("pinned image architecture inspection failed")
    temporary = destination.with_name(f".{destination.name}.save")
    temporary.unlink(missing_ok=True)
    try:
        _run_checked(["podman", "save", "--format", "oci-archive", "-o", str(temporary), reference], 300)
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "kind": "server-oci-archive",
        "source_url": reference,
        "cache_path": str(destination),
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256_file(destination),
        "architecture": "arm64",
        "inspection_method": "podman-image-inspect+oci-archive-save",
    }


def refresh_supply_observation(repo: Path, contract: dict[str, Any]) -> dict[str, Any]:
    contract_result = validate_supply_contract(contract)
    if contract_result.status != "PASS":
        raise ValueError("supply contract is not valid")
    server_commit = _resolve_tag_commit(contract["server"]["git_repository"], contract["server"]["tag"])
    client_commit = _resolve_tag_commit(contract["clients"]["git_repository"], contract["clients"]["tag"])
    if server_commit != SERVER_COMMIT or client_commit != CLIENT_COMMIT:
        raise ValueError("official tag commit drift")

    server_release = _http_json(contract["server"]["release_api_url"])
    client_release = _http_json(contract["clients"]["release_api_url"])
    registry = _http_json(contract["server"]["classic_image"]["registry_tag_api_url"])
    if registry.get("digest") != MULTIARCH_DIGEST:
        raise ValueError("official image manifest drift")
    children = [
        item
        for item in registry.get("images", [])
        if isinstance(item, dict) and item.get("architecture") == "arm64" and item.get("os") == "linux"
    ]
    if len(children) != 1 or children[0].get("digest") != ARM64_IMAGE_DIGEST:
        raise ValueError("official image ARM64 child drift")

    artifact_specs = (
        ("server-release-zip", contract["server"]["release_zip"], server_release),
        ("linux-client-deb", contract["clients"]["linux_arm64_deb"], client_release),
        ("windows-client-msi", contract["clients"]["windows_x86_64_msi"], client_release),
    )
    artifacts = [_stage_oci(contract)]
    for kind, spec, release in artifact_specs:
        official = _release_asset(release, spec["asset_name"])
        official_digest = official.get("digest")
        if official.get("browser_download_url") != spec["source_url"] or official.get("size") != spec[
            "size_bytes"
        ] or official_digest != f"sha256:{spec['sha256']}":
            raise ValueError("official release asset drift")
        destination = Path(spec["cache_path"])
        byte_meta = _download_verified(spec["source_url"], destination, spec["sha256"], spec["size_bytes"])
        if kind == "server-release-zip":
            if not _zip_arm64(destination):
                raise ValueError("server ZIP architecture inspection failed")
            method = "elf-e_machine-aarch64-for-hbbs-and-hbbr"
        elif kind == "linux-client-deb":
            if _run_checked(["dpkg-deb", "-f", str(destination), "Architecture"], 30) != "arm64":
                raise ValueError("DEB architecture inspection failed")
            method = "dpkg-deb-architecture"
        else:
            method = "official-x86_64-asset-name+sha256;metadata-and-authenticode-deferred-phase54"
        artifacts.append(
            {
                "kind": kind,
                "source_url": spec["source_url"],
                "cache_path": str(destination),
                "size_bytes": byte_meta["size_bytes"],
                "sha256": byte_meta["sha256"],
                "architecture": spec["architecture"],
                "inspection_method": method,
            }
        )

    source_urls = sorted(
        {
            contract["server"]["git_repository"],
            contract["server"]["release_api_url"],
            contract["server"]["classic_image"]["registry_tag_api_url"],
            contract["server"]["release_zip"]["source_url"],
            contract["clients"]["git_repository"],
            contract["clients"]["release_api_url"],
            contract["clients"]["linux_arm64_deb"]["source_url"],
            contract["clients"]["windows_x86_64_msi"]["source_url"],
        }
    )
    return {
        "schema_version": 1,
        "phase": 52,
        "workstream": "rustdesk-fleet",
        "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_urls": source_urls,
        "input_digests": collect_input_digests(repo, [SUPPLY_CONTRACT]),
        "server": {"tag": "1.1.15", "commit": server_commit},
        "clients": {"tag": "1.4.9", "commit": client_commit},
        "classic_image": {
            "tag": "1.1.15",
            "multiarch_digest": MULTIARCH_DIGEST,
            "linux_arm64_digest": ARM64_IMAGE_DIGEST,
            "architecture": "arm64",
            "os": "linux",
            "inspection_method": "docker-hub-platform-manifest+podman-image-inspect",
        },
        "artifacts": artifacts,
        "windows_install_performed": False,
        "candidate_admission_performed": False,
        "secret_material_present": False,
        "findings": [],
        "status": "PASS",
    }


def _write_json_atomically(payload: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_input_digests(repo: Path, paths: list[Path] | tuple[Path, ...]) -> list[dict[str, str]]:
    root = repo.resolve()
    rows: list[dict[str, str]] = []
    for path in paths:
        candidate = path if path.is_absolute() else root / path
        resolved = validate_repo_path(root, candidate)
        if not resolved.is_file():
            raise ValueError("report input is missing")
        rows.append({"path": resolved.relative_to(root).as_posix(), "sha256": _sha256_file(resolved)})
    return sorted(rows, key=lambda item: item["path"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--only", choices=("supply",), default="supply")
    parser.add_argument("--evidence-dir", type=Path, default=SUPPLY_OBSERVATION.parent)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        contract_path = validate_repo_path(repo, repo / SUPPLY_CONTRACT)
        contract = load_json_strict(contract_path)
        contract_result = validate_supply_contract(contract, contract_path.relative_to(repo).as_posix())
        if contract_result.status != "PASS":
            print(json.dumps({"status": contract_result.status, "check": contract_result.id}, sort_keys=True))
            return exit_code_for_status(contract_result.status)
        observation_path = validate_repo_path(repo, repo / args.evidence_dir / SUPPLY_OBSERVATION.name)
        observation = refresh_supply_observation(repo, contract)
        result = validate_supply_observation(observation, contract, repo=repo)
        if result.status == "PASS":
            _write_json_atomically(observation, observation_path)
    except (OSError, ValueError, subprocess.SubprocessError, urllib.error.URLError) as exc:
        print(f"BLOCKED: {exc.__class__.__name__}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result.status, "check": result.id}, sort_keys=True))
    return exit_code_for_status(result.status)


if __name__ == "__main__":
    raise SystemExit(main())
