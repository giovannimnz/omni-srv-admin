#!/usr/bin/env python3
"""Fail-closed, read-only validation gate for Phase 54.

Evidence is untrusted input.  The runner derives status from fresh,
runner-observed checks and recomputed artifact lineage; an evidence document
cannot authorize its own progression.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


SCHEMA_EVIDENCE = "phase54.evidence.v1"
SCHEMA_GATE = "phase54.gate.v1"
SCHEMA_BACKUP_RECEIPT = "phase54.backup-receipt.v1"
SCHEMA_PUBLIC_IP_READBACK = "phase54.public-ip-readback.v1"
SCHEMA_S20_RETIREMENT_RECEIPT = "phase54.s20-retirement-receipt.v1"
SCHEMA_OPERATION_PLAN = "phase54.operation-plan.v1"
SCHEMA_APPROVAL = "phase54.approval.v1"
SCHEMA_APPLY_RECEIPT = "phase54.apply-receipt.v1"
SCHEMA_ROLLBACK_RECEIPT = "phase54.rollback-receipt.v1"
SCHEMA_KNOWLEDGE_FREEZE = "phase54.knowledge-freeze.v1"
SCHEMA_REVIEW_EVIDENCE = "phase54.review-evidence.v1"
SCHEMA_REVIEW_GATE = "phase54.review-gate.v1"
DEFAULT_MAX_AGE_SECONDS = 900
PLAN_IDS = tuple(f"54-{number:02d}" for number in range(1, 11))
STAGE_IDS = {"preflight", "stability", "preview", "approval", "apply", "sync"}
STAGES_BY_PLAN: dict[str, frozenset[str | None]] = {
    "54-01": frozenset({None}),
    "54-02": frozenset({"preflight", "preview", "approval", "apply"}),
    "54-03": frozenset({None}),
    "54-04": frozenset({"preview", "approval", "apply"}),
    "54-05": frozenset({"preview", "approval", "apply"}),
    "54-06": frozenset({"preview", "approval", "apply"}),
    "54-07": frozenset({"preview", "approval", "apply"}),
    "54-08": frozenset({"preview", "approval", "apply", "sync"}),
    "54-09": frozenset({"stability", "preview", "approval", "apply"}),
    "54-10": frozenset({"preflight", "sync"}),
}
TERMINAL_STAGE_BY_PLAN: dict[str, str | None] = {
    "54-01": None,
    "54-02": "apply",
    "54-03": None,
    "54-04": "apply",
    "54-05": "apply",
    "54-06": "apply",
    "54-07": "apply",
    "54-08": "sync",
    "54-09": "apply",
}
OPERATION_STAGES_BY_PLAN: dict[str, frozenset[str]] = {
    "54-02": frozenset({"preview", "approval", "apply"}),
    "54-04": frozenset({"preview", "approval", "apply"}),
    "54-05": frozenset({"preview", "approval", "apply"}),
    "54-06": frozenset({"preview", "approval", "apply"}),
    "54-07": frozenset({"preview", "approval", "apply"}),
    "54-08": frozenset({"preview", "approval", "apply", "sync"}),
    "54-09": frozenset({"preview", "approval", "apply"}),
}
BASE_REQUIRED_CHECK_IDS: dict[str, tuple[str, ...]] = {
    "54-01": (
        "workstream_config_routing",
        "focused_pytest",
        "syntax_compile",
        "adversarial_matrix",
        "secret_scan",
        "graphify_preflight",
    ),
    "54-02": (
        "independent_review_gate",
        "live_inventory",
        "backup_restore_staging",
        "public_ip_baseline",
        "dns_edge_baseline",
    ),
    "54-03": ("builder_receipt", "builder_targets", "vcn_architecture"),
    "54-04": ("target_network", "drg_bidirectional", "security_bidirectional"),
    "54-05": ("vnic_private_ip", "host_k3s_dual_path", "public_ip_binding"),
    "54-06": ("freeipa_authority", "resolver_forwarding", "service_matrix"),
    "54-07": ("edge_transaction", "s23_unchanged", "s20_target"),
    "54-08": ("device_receipts", "s20_handshake", "dual_ssh_paths"),
    "54-09": ("stable_readbacks", "retirement_targets", "retirement_approval"),
    "54-10": ("retirement_readback", "full_matrix", "knowledge_receipts"),
}
STAGE_REQUIRED_CHECK_IDS = {
    "preflight": ("stage_preflight",),
    "stability": ("stage_stability",),
    "preview": ("operation_plan_preview",),
    "approval": ("typed_approval",),
    "apply": ("apply_receipt",),
    "sync": ("knowledge_sync",),
}
EDGE_TARGET_MAP = {
    "horistic_wireguard": {"from": "10.100.100.4", "to": "10.100.100.31"},
    "s23_lan": {
        "from": "192.168.1.10",
        "to": "192.168.1.10",
        "mac": "64:1B:2F:C2:DC:A3",
    },
    "s23_wireguard": {"from": "10.100.100.10", "to": "10.100.100.10"},
    "s20_lan": {
        "from": "192.168.1.9",
        "to": "192.168.1.11",
        "mac": "30:AB:6A:3C:96:D1",
    },
    "s20_wireguard": {"from": "10.100.100.9", "to": "10.100.100.11"},
}
EXPECTED_BUILDER_TARGETS = {
    "vcn": "10.31.0.0/16",
    "subnet": "10.31.1.0/24",
    "private_ip": "10.31.1.31",
}
LEGACY_FAILURE_STATES = {"BLOCK", "BLOCKED", "UNKNOWN", "PARTIAL"}
SENSITIVE_KEYS = {
    "authorization",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\b(?:token|password|secret)=[^\s<]+", re.IGNORECASE),
)
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")
HEX_40_PATTERN = re.compile(r"^[0-9a-f]{40}$")
BASELINE_PUBLIC_BINDING = "10.0.0.65"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PHASE_DIR = (
    REPO_ROOT
    / ".planning/workstreams/network-horistic-readdress/phases"
    / "54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re"
)
REVIEW_EVIDENCE_NAME = "54-REVIEW-EVIDENCE.json"
REVIEW_GATE_NAME = "54-REVIEW-GATE.json"
REVIEW_SCOPE_NAMES = (
    "54-CONTEXT.md",
    "54-RESEARCH.md",
    "54-VALIDATION.md",
    "54-VALIDATION-CONTRACT.md",
    *(f"54-{number:02d}-PLAN.md" for number in range(1, 11)),
)
REVIEW_SCOPE_PATHS = tuple(
    (PHASE_DIR / name).relative_to(REPO_ROOT).as_posix() for name in REVIEW_SCOPE_NAMES
)
ADAPTER_PATH = (
    REPO_ROOT / "modules/fleet-control-plane/scripts/phase54_probe_adapters.py"
)
LOCAL_CHECK_IDS = frozenset(BASE_REQUIRED_CHECK_IDS["54-01"])
MAX_PREDECESSOR_DEPTH = len(PLAN_IDS)
OPERATION_CONTRACTS = {
    "54-02": {
        "filename": "54-02-BACKUP-OPERATION-PLAN.json",
        "owner": "phase54-backup-executor",
        "operations": {"oci_boot_backup", "explicit_refresh"},
        "rollback": "54-02-ROLLBACK-RECEIPT.json",
    },
    "54-04": {
        "filename": "54-04-OPERATION-PLAN.json",
        "owner": "oci-admin",
        "operations": {"network_create_or_update"},
        "rollback": "54-04-ROLLBACK-RECEIPT.json",
    },
    "54-05": {
        "filename": "54-05-OPERATION-PLAN.json",
        "owner": "oci-admin",
        "operations": {"vnic_public_ip_cutover"},
        "rollback": "54-05-ROLLBACK-RECEIPT.json",
    },
    "54-06": {
        "filename": "54-06-DNS-TRANSACTION.json",
        "owner": "dns-admin",
        "operations": {"dns_service_cutover"},
        "rollback": "54-06-ROLLBACK-RECEIPT.json",
    },
    "54-07": {
        "filename": "54-07-EDGE-TRANSACTION.json",
        "owner": "edge-admin",
        "operations": {"edge_dual_path"},
        "rollback": "54-07-ROLLBACK-RECEIPT.json",
    },
    "54-08": {
        "filename": "54-08-OPERATION-PLAN.json",
        "owner": "edge-device-admin",
        "operations": {"device_import", "s20_retirement"},
        "rollback": "54-08-ROLLBACK-RECEIPT.json",
    },
    "54-09": {
        "filename": "54-09-RETIREMENT-OPERATION-PLAN.json",
        "owner": "oci-admin",
        "operations": {"retire_10_21"},
        "rollback": "54-09-ROLLBACK-RECEIPT.json",
    },
}


@dataclass(frozen=True)
class ProbeContext:
    plan: str
    stage: str | None
    evidence: pathlib.Path
    evidence_dir: pathlib.Path
    max_age_seconds: int


@dataclass(frozen=True)
class ProbeSpec:
    plan: str
    stage: str | None
    check_id: str
    kind: str
    argv: tuple[str, ...]
    timeout_seconds: int = 30
    expects_json: bool = True


def _fixed_executable(name: str) -> str:
    resolved = shutil.which(name)
    return str(pathlib.Path(resolved).resolve()) if resolved else f"/missing/{name}"


def _build_probe_registry() -> dict[tuple[str, str | None, str], ProbeSpec]:
    runner = str(pathlib.Path(__file__).resolve())
    adapter = str(ADAPTER_PATH.resolve())
    python = str(pathlib.Path(sys.executable).resolve())
    registry: dict[tuple[str, str | None, str], ProbeSpec] = {}
    for plan, stages in STAGES_BY_PLAN.items():
        for stage in stages:
            for check_id in required_check_ids(plan, stage):
                runner_contract = check_id == "independent_review_gate" or check_id in {
                    item
                    for values in STAGE_REQUIRED_CHECK_IDS.values()
                    for item in values
                }
                registry[(plan, stage, check_id)] = ProbeSpec(
                    plan=plan,
                    stage=stage,
                    check_id=check_id,
                    kind=(
                        "local"
                        if plan == "54-01"
                        else "runner-contract"
                        if runner_contract
                        else "remote-owner"
                    ),
                    argv=(
                        (python, runner, "probe", "--probe-id", check_id)
                        if plan == "54-01"
                        else ()
                        if runner_contract
                        else (
                            python,
                            adapter,
                            "probe",
                            "--plan",
                            plan,
                            "--stage",
                            stage or "none",
                            "--probe-id",
                            check_id,
                        )
                    ),
                )
    return registry


def _value_strings(value: Any) -> set[str]:
    result: set[str] = set()
    if isinstance(value, str):
        result.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            result.update(_value_strings(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_value_strings(item))
    return result


def _normalized_public_ip_valid(
    normalized: dict[str, Any],
    evidence: dict[str, Any],
    *,
    require_target: bool,
    baseline_mode: bool,
) -> bool:
    semantic = normalized.get("semantic")
    public_rows = (
        semantic.get("reserved_public_ips") if isinstance(semantic, dict) else None
    )
    public_evidence = evidence.get("public_ip")
    if not isinstance(public_rows, list) or not isinstance(public_evidence, dict):
        return False
    observed = next(
        (
            item
            for item in public_rows
            if isinstance(item, dict)
            and item.get("public_ip_ocid") == public_evidence.get("ocid")
        ),
        None,
    )
    if not isinstance(observed, dict):
        return False
    expected_binding = (
        "10.31.1.31"
        if require_target
        else BASELINE_PUBLIC_BINDING
        if baseline_mode
        else public_evidence.get("binding")
    )
    private_rows = semantic.get("private_ips")
    private_match = (
        next(
            (
                item
                for item in private_rows
                if isinstance(item, dict)
                and item.get("private_ip_ocid") == observed.get("private_ip_ocid")
            ),
            None,
        )
        if isinstance(private_rows, list)
        else None
    )
    binding = {
        "public_ip_ocid": observed.get("public_ip_ocid"),
        "address": observed.get("address"),
        "private_ip_address": private_match.get("address")
        if isinstance(private_match, dict)
        else None,
        "private_ip_ocid": observed.get("private_ip_ocid"),
        "vnic_ocid": private_match.get("vnic_ocid")
        if isinstance(private_match, dict)
        else None,
        "subnet_ocid": private_match.get("subnet_ocid")
        if isinstance(private_match, dict)
        else None,
    }
    secondary_current = (
        next(
            (
                item
                for item in private_rows
                if isinstance(item, dict) and item.get("address") == "10.21.1.21"
            ),
            None,
        )
        if isinstance(private_rows, list)
        else None
    )
    return bool(
        observed.get("address") == "163.176.232.119"
        and observed.get("public_ip_ocid") == public_evidence.get("ocid")
        and observed.get("label") == "horistic-srv-1"
        and observed.get("lifetime") == "RESERVED"
        and observed.get("lifecycle_state") in {"RESERVED", "ASSIGNED"}
        and isinstance(private_match, dict)
        and private_match.get("address") == expected_binding
        and observed.get("private_ip_ocid") == public_evidence.get("private_ip_ocid")
        and private_match.get("vnic_ocid") == public_evidence.get("vnic_ocid")
        and private_match.get("subnet_ocid") == public_evidence.get("subnet_ocid")
        and (
            not baseline_mode
            or (
                public_evidence.get("current_binding_sha256") == sha256_json(binding)
                and isinstance(secondary_current, dict)
                and secondary_current.get("private_ip_ocid")
                != observed.get("private_ip_ocid")
                and secondary_current.get("vnic_ocid") != private_match.get("vnic_ocid")
            )
        )
    )


def _normalized_drg_valid(
    semantic: dict[str, Any],
    *,
    target_cidr: str,
) -> bool:
    attachments = semantic.get("attachments")
    routes = semantic.get("route_tables")
    distributions = semantic.get("route_distributions")
    if not all(
        isinstance(value, list) and value
        for value in (attachments, routes, distributions)
    ):
        return False
    profiles = {"atius1", "atius2", "atius3", "horistic"}
    attached = {
        item.get("profile_name")
        for item in attachments
        if isinstance(item, dict)
        and item.get("blocked") is False
        and item.get("state") == "attached_to_central"
        and isinstance(item.get("attachment_ocid"), str)
        and item["attachment_ocid"].startswith("ocid1.drgattachment.")
    }
    route_map: dict[str, set[str]] = {}
    for item in routes:
        if not isinstance(item, dict) or item.get("blocked") is not False:
            continue
        route_map.setdefault(str(item.get("profile_name")), set()).update(
            value for value in item.get("target_cidrs", []) if isinstance(value, str)
        )
    forward = all(
        target_cidr in route_map.get(profile, set())
        for profile in {"atius1", "atius2", "atius3"}
    )
    reverse = set(("10.11.0.0/16", "10.12.0.0/16", "10.13.0.0/16")) <= route_map.get(
        "horistic", set()
    )
    distribution_profiles = {
        item.get("profile_name")
        for item in distributions
        if isinstance(item, dict)
        and item.get("blocked") is False
        and isinstance(item.get("attachment_ocid"), str)
    }
    return bool(
        attached == profiles
        and distribution_profiles == profiles
        and forward
        and reverse
        and semantic.get("applies_live_oci_writes") is False
    )


def _normalized_security_valid(
    normalized: dict[str, Any],
    evidence: dict[str, Any],
) -> bool:
    semantic = normalized.get("semantic")
    if not isinstance(semantic, dict):
        return False
    rows = semantic.get("security_lists")
    argument_ids = semantic.get("argument_security_list_ocids")
    evidence_ids = sorted(
        value
        for value in _value_strings(evidence)
        if value.startswith("ocid1.securitylist.")
    )
    if (
        not isinstance(rows, list)
        or not rows
        or not isinstance(argument_ids, list)
        or sorted(argument_ids) != evidence_ids
    ):
        return False
    required_ingress = {"10.11.0.0/16", "10.12.0.0/16", "10.13.0.0/16"}
    return all(
        isinstance(row, dict)
        and row.get("security_list_ocid") in evidence_ids
        and row.get("lifecycle_state") == "AVAILABLE"
        and required_ingress
        <= {
            item.get("source")
            for item in row.get("ingress", [])
            if isinstance(item, dict) and item.get("direction") == "INGRESS"
        }
        and any(
            isinstance(item, dict)
            and item.get("direction") == "EGRESS"
            and isinstance(item.get("destination"), str)
            for item in row.get("egress", [])
        )
        for row in rows
    )


def _normalized_probe_valid(
    spec: ProbeSpec,
    context: ProbeContext,
    payload: dict[str, Any],
) -> bool:
    normalized = payload.get("normalized")
    evidence = read_json(context.evidence)
    evidence_sha256 = sha256_file(context.evidence)
    if (
        not isinstance(normalized, dict)
        or not isinstance(evidence, dict)
        or normalized.get("evidence_sha256") != evidence_sha256
        or payload.get("evidence_sha256") != evidence_sha256
        or _contains_secret(normalized)
    ):
        return False
    semantic = normalized.get("semantic")
    check_id = spec.check_id
    if check_id == "live_inventory":
        return bool(
            normalized.get("operation") == "peering.inventory"
            and isinstance(semantic, dict)
            and {"10.21.0.0/16"} <= set(semantic.get("vcn_cidrs", []))
            and {"10.21.1.0/24"} <= set(semantic.get("subnet_cidrs", []))
            and "10.21.1.21" in semantic.get("current_host_ips", [])
            and {"10.31.0.0/16", "10.31.1.0/24", "10.31.1.31"}
            <= _value_strings(evidence)
        )
    if check_id in {
        "builder_receipt",
        "builder_targets",
        "vcn_architecture",
        "target_network",
    }:
        target = semantic.get("target") if isinstance(semantic, dict) else None
        return bool(
            normalized.get("operation") == "peering.address_plan"
            and isinstance(target, dict)
            and target.get("vcn") == "10.31.0.0/16"
            and target.get("subnet") == "10.31.1.0/24"
            and target.get("private_ip") == "10.31.1.31"
            and semantic.get("applies_live_oci_writes") is False
            and semantic.get("target_contains_10_21") is False
        )
    if check_id in {"drg_bidirectional", "retirement_targets", "retirement_approval"}:
        target = (
            "10.31.0.0/16"
            if context.stage == "apply" or context.plan == "54-10"
            else "10.21.0.0/16"
        )
        return bool(
            normalized.get("operation") == "peering.drg_status"
            and isinstance(semantic, dict)
            and _normalized_drg_valid(semantic, target_cidr=target)
        )
    if check_id == "security_bidirectional":
        return bool(
            normalized.get("operation") == "network.security_list"
            and _normalized_security_valid(normalized, evidence)
        )
    if check_id in {"public_ip_baseline", "public_ip_binding", "vnic_private_ip"}:
        return bool(
            normalized.get("operation") == "inventory.get"
            and _normalized_public_ip_valid(
                normalized,
                evidence,
                require_target=(
                    context.plan in {"54-10"}
                    or (context.plan == "54-05" and context.stage == "apply")
                ),
                baseline_mode=context.plan == "54-02",
            )
            and _public_ip_valid(evidence, context.plan, context.evidence_dir)
        )
    if check_id == "backup_restore_staging":
        backups = normalized.get("backups")
        expected = {
            "srv1": (
                "/var/backups/omni-srv-admin/phase54/20260726T041249Z-srv1",
                "5bcf242294a97636f41ebc00780fb1b7b32246bb2c408cd4cc9409fb3542b9be",
            ),
            "srv3": (
                "/var/backups/omni-srv-admin/phase54/20260726T041546Z-srv3",
                "e537458856b9aeee9f0f86030717d2c0e54fbf953adbc391f44351f18cdeeef1",
            ),
            "offhost": (
                "/home/ubuntu/.local/state/home-router-be3/backups/phase54",
                "866adbef8a1434622f0b4028ddaf5b5bd76afaeafc246e7a576b675c889cb781",
            ),
        }
        observed = (
            {item.get("owner"): item for item in backups if isinstance(item, dict)}
            if isinstance(backups, list)
            else {}
        )
        return bool(
            set(observed) == set(expected)
            and all(
                observed[owner].get("root") == root
                and observed[owner].get("archive_sha256") == digest
                and observed[owner].get("mode") == "600"
                and (
                    owner == "offhost"
                    or (
                        observed[owner].get("manifest_verified") is True
                        and observed[owner].get("tar_list_verified") is True
                        and observed[owner].get("isolated_restore_staging") is True
                    )
                )
                for owner, (root, digest) in expected.items()
            )
        )
    if check_id in {"dns_edge_baseline", "freeipa_authority", "resolver_forwarding"}:
        expected_address = (
            "10.31.1.31"
            if context.plan in {"54-07", "54-08", "54-09", "54-10"}
            or (context.plan == "54-06" and context.stage == "apply")
            else "10.21.1.21"
        )
        authority = normalized.get("authority")
        resolvers = normalized.get("resolvers")
        resolver_servers = ["10.11.1.11", "127.0.0.2"]
        resolver_fields = ("a", "ptr", "soa", "ns", "nxdomain")
        resolver_matrix = (
            resolvers.get("matrix") if isinstance(resolvers, dict) else None
        )
        resolver_matrix_valid = bool(
            isinstance(resolver_matrix, dict)
            and set(resolver_matrix) == set(resolver_servers)
            and all(
                isinstance(item, dict)
                and set(item) == set(resolver_fields)
                and all(isinstance(item[field], bool) for field in resolver_fields)
                for item in resolver_matrix.values()
            )
        )
        resolver_missing_expected = (
            {
                server: sorted(
                    field.upper()
                    for field in ("soa", "ns", "nxdomain")
                    if not resolver_matrix[server][field]
                )
                for server in resolver_servers
            }
            if resolver_matrix_valid
            else None
        )
        resolver_summary_valid = bool(
            resolver_matrix_valid
            and resolvers.get("servers") == resolver_servers
            and resolvers.get("nxdomain_count")
            == sum(resolver_matrix[server]["nxdomain"] for server in resolver_servers)
            and resolvers.get("soa_count")
            == sum(resolver_matrix[server]["soa"] for server in resolver_servers)
            and resolvers.get("ns_count")
            == sum(resolver_matrix[server]["ns"] for server in resolver_servers)
            and resolvers.get("a_ptr_complete")
            is all(
                resolver_matrix[server]["a"] and resolver_matrix[server]["ptr"]
                for server in resolver_servers
            )
            and resolvers.get("soa")
            is all(resolver_matrix[server]["soa"] for server in resolver_servers)
            and resolvers.get("ns")
            is all(resolver_matrix[server]["ns"] for server in resolver_servers)
        )
        if check_id == "dns_edge_baseline":
            baseline_gap = normalized.get("baseline_gap")
            gap_material = {
                "expected_address": normalized.get("expected_address"),
                "expected_reverse": normalized.get("expected_reverse"),
                "authority": authority,
                "resolvers": resolvers,
            }
            return bool(
                normalized.get("expected_address") == "10.21.1.21"
                and normalized.get("expected_reverse") == "21.1.21.10.in-addr.arpa"
                and isinstance(authority, dict)
                and authority.get("server") == "10.89.53.10"
                and authority.get("a_aa") is True
                and authority.get("ptr_aa") is False
                and authority.get("soa_aa") is True
                and authority.get("ns_aa") is True
                and authority.get("aa") is False
                and authority.get("nxdomain") is True
                and authority.get("soa") is True
                and authority.get("ns") is True
                and authority.get("a_address") is None
                and authority.get("ptr_owner") is None
                and isinstance(resolvers, dict)
                and resolver_summary_valid
                and resolvers.get("a_ptr_complete") is True
                and resolvers.get("a_address") == "10.21.1.21"
                and resolvers.get("ptr_owner") == "21.1.21.10.in-addr.arpa"
                and all(
                    resolver_matrix[server]["a"] and resolver_matrix[server]["ptr"]
                    for server in resolver_servers
                )
                and isinstance(resolver_missing_expected, dict)
                and any(
                    resolver_missing_expected[server] for server in resolver_servers
                )
                and isinstance(baseline_gap, dict)
                and baseline_gap.get("schema") == "phase54.dns-baseline-gap.v1"
                and baseline_gap.get("authority_missing") == ["A", "PTR"]
                and baseline_gap.get("resolver_missing") == resolver_missing_expected
                and baseline_gap.get("observed_sha256") == sha256_json(gap_material)
                and isinstance(normalized.get("ttl_min"), int)
                and normalized["ttl_min"] > 0
            )
        return bool(
            normalized.get("expected_address") == expected_address
            and normalized.get("expected_reverse")
            == (
                "31.1.31.10.in-addr.arpa"
                if expected_address == "10.31.1.31"
                else "21.1.21.10.in-addr.arpa"
            )
            and isinstance(authority, dict)
            and authority.get("server") == "10.89.53.10"
            and authority.get("a_aa") is True
            and authority.get("ptr_aa") is True
            and authority.get("soa_aa") is True
            and authority.get("ns_aa") is True
            and authority.get("aa") is True
            and authority.get("nxdomain") is True
            and authority.get("soa") is True
            and authority.get("ns") is True
            and authority.get("a_address") == expected_address
            and authority.get("ptr_owner") == normalized.get("expected_reverse")
            and isinstance(resolvers, dict)
            and resolver_summary_valid
            and resolvers.get("nxdomain_count") == 2
            and resolvers.get("soa_count") == 2
            and resolvers.get("ns_count") == 2
            and resolvers.get("a_ptr_complete") is True
            and resolvers.get("a_address") == expected_address
            and resolvers.get("ptr_owner") == normalized.get("expected_reverse")
            and resolvers.get("soa") is True
            and resolvers.get("ns") is True
            and all(
                all(resolver_matrix[server][field] for field in resolver_fields)
                for server in resolver_servers
            )
            and isinstance(normalized.get("ttl_min"), int)
            and normalized["ttl_min"] > 0
        )
    if check_id in {"edge_transaction", "s23_unchanged", "s20_target"}:
        be3 = normalized.get("be3")
        wg = normalized.get("wireguard")
        expected_s20 = (
            "192.168.1.11"
            if context.plan in {"54-08", "54-09", "54-10"}
            or (context.plan == "54-07" and context.stage == "apply")
            else "192.168.1.9"
        )
        return bool(
            isinstance(be3, dict)
            and be3.get("source_commit") == "24f2562af086625b0678c4573f1c03a77270fc22"
            and be3.get("headless") is True
            and be3.get("authenticated") is True
            and be3.get("applies_changes") is False
            and be3.get("s23", {}).get("mac") == "64:1B:2F:C2:DC:A3"
            and be3.get("s23", {}).get("ips") == ["192.168.1.10"]
            and be3.get("s20", {}).get("mac") == "30:AB:6A:3C:96:D1"
            and be3.get("s20", {}).get("expected") == expected_s20
            and isinstance(wg, dict)
            and wg.get("raw_keys_present") is False
            and bool(wg.get("peer_fingerprints"))
        )
    if check_id in {"device_receipts", "s20_handshake"}:
        wg = normalized.get("wireguard")
        return bool(
            isinstance(wg, dict)
            and wg.get("raw_keys_present") is False
            and "10.100.100.11/32" in wg.get("allowed_ips", [])
            and bool(wg.get("peer_fingerprints"))
            and wg.get("handshake_fresh") is True
        )
    if check_id in {"host_k3s_dual_path", "dual_ssh_paths", "service_matrix"}:
        return bool(
            normalized.get("private_path") == "PASS"
            and normalized.get("public_path") == "PASS"
            and (
                check_id != "service_matrix"
                or normalized.get("services") == {"apache2": "active", "k3s": "active"}
            )
        )
    if check_id in {"stable_readbacks", "retirement_readback", "full_matrix"}:
        residuals = normalized.get("operational_10_21")
        residual_live = normalized.get("residual_live")
        return bool(
            normalized.get("matrix_complete") is True
            and normalized.get("oci") == "PASS"
            and normalized.get("dns") == "PASS"
            and normalized.get("host_private") == "PASS"
            and normalized.get("host_public") == "PASS"
            and (
                check_id != "full_matrix"
                or (
                    isinstance(residuals, list)
                    and all(
                        isinstance(item, str) and "10.21" in item for item in residuals
                    )
                    and isinstance(residual_live, dict)
                    and residual_live.get("present") is bool(residuals)
                    and residual_live.get("count") == len(residuals)
                    and residual_live.get("sha256") == sha256_json(residuals)
                    and isinstance(normalized.get("live_readback_sha256"), str)
                    and HEX_64_PATTERN.fullmatch(normalized["live_readback_sha256"])
                )
            )
        )
    if check_id == "knowledge_receipts":
        return bool(
            normalized.get("stale") is False
            and normalized.get("commit_stale") is False
            and normalized.get("relevant_nodes") is True
            and normalized.get("query") == "phase54_network_gate"
        )
    return False


def run_fixed_argv(spec: ProbeSpec, context: ProbeContext) -> dict[str, Any]:
    command = list(spec.argv)
    if spec.kind == "remote-owner":
        command.extend(("--evidence", str(context.evidence.resolve())))
    started_at = utc_now()
    if (
        not command
        or not pathlib.Path(command[0]).is_absolute()
        or any("\n" in item or "\r" in item for item in command)
    ):
        return {
            "id": spec.check_id,
            "required": True,
            "adapter": spec.kind,
            "command_id": f"phase54.{spec.check_id}",
            "exit_code": None,
            "result": "BLOCK",
            "reason": "invalid fixed argv",
            "artifact_hashes": {},
        }
    sanitized_env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": "/var/tmp",
    }
    for name in ("HOME", "CODEX_HOME"):
        if os.environ.get(name):
            sanitized_env[name] = os.environ[name]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=False,
            timeout=spec.timeout_seconds,
            shell=False,
            stdin=subprocess.DEVNULL,
            env=sanitized_env,
        )
        stdout = completed.stdout[: 1024 * 1024]
        stderr = completed.stderr[: 1024 * 1024]
        truncated = len(completed.stdout) > len(stdout) or len(completed.stderr) > len(
            stderr
        )
        payload: dict[str, Any] | None = None
        if spec.expects_json:
            try:
                parsed = json.loads(stdout.decode("utf-8"))
                payload = parsed if isinstance(parsed, dict) else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
        passed = bool(
            completed.returncode == 0
            and not truncated
            and payload
            and payload.get("schema") == "phase54.check-observation.v1"
            and payload.get("probe_id") == spec.check_id
            and payload.get("status") == "PASS"
            and payload.get("read_only") is True
            and payload.get("mutation_performed") is False
            and payload.get("secret_material_present") is False
            and isinstance(payload.get("request_id"), str)
            and payload.get("request_id")
            and isinstance(payload.get("observed_sha256"), str)
            and HEX_64_PATTERN.fullmatch(payload["observed_sha256"])
            and (
                spec.kind != "remote-owner"
                or _normalized_probe_valid(spec, context, payload)
            )
        )
        return {
            "id": spec.check_id,
            "required": True,
            "adapter": spec.kind,
            "command_id": f"phase54.{spec.check_id}",
            "started_at": started_at,
            "finished_at": utc_now(),
            "exit_code": completed.returncode,
            "result": "PASS" if passed else "BLOCK",
            "artifact_hashes": {
                "captured-output": hashlib.sha256(stdout + stderr).hexdigest()
            },
            "normalized": (
                payload.get("normalized")
                if passed and spec.kind == "remote-owner"
                else None
            ),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "id": spec.check_id,
            "required": True,
            "adapter": spec.kind,
            "command_id": f"phase54.{spec.check_id}",
            "started_at": started_at,
            "finished_at": utc_now(),
            "exit_code": None,
            "result": "BLOCK",
            "reason": type(exc).__name__,
            "artifact_hashes": {},
        }


def execute_registered_probe(
    context: ProbeContext,
    check_id: str,
    *,
    local_transport: Any = run_fixed_argv,
    remote_transport: Any = run_fixed_argv,
) -> dict[str, Any]:
    spec = PROBE_REGISTRY.get((context.plan, context.stage, check_id))
    if spec is None:
        return {
            "id": check_id,
            "required": True,
            "adapter": "registry-miss",
            "command_id": f"phase54.{check_id}",
            "exit_code": None,
            "result": "BLOCK",
            "artifact_hashes": {},
        }
    if spec.kind == "runner-contract":
        return _runner_contract_probe(context, check_id)
    transport = local_transport if spec.kind == "local" else remote_transport
    return transport(spec, context)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def required_check_ids(plan: str, stage: str | None) -> tuple[str, ...]:
    base = BASE_REQUIRED_CHECK_IDS.get(plan, ())
    stage_checks = STAGE_REQUIRED_CHECK_IDS.get(stage, ()) if stage is not None else ()
    return base + stage_checks


PROBE_REGISTRY = _build_probe_registry()


def result_check(
    check_id: str, expected: Any, observed: Any, passed: bool
) -> dict[str, Any]:
    return {
        "id": check_id,
        "required": True,
        "expected": expected,
        "observed": observed,
        "result": "PASS" if passed else "BLOCK",
    }


def _path_from_evidence(
    raw_path: Any, evidence_dir: pathlib.Path
) -> pathlib.Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = pathlib.Path(raw_path)
    if candidate.is_absolute():
        return candidate
    cwd_candidate = pathlib.Path.cwd() / candidate
    if cwd_candidate.exists():
        return cwd_candidate
    return evidence_dir / candidate


def _freshness(
    generated_at: Any,
    expires_at: Any,
    max_age_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    generated = parse_timestamp(generated_at)
    if generated is None:
        return False
    age = (current - generated).total_seconds()
    if age < -60 or age > max_age_seconds:
        return False
    if expires_at is None:
        return True
    expiry = parse_timestamp(expires_at)
    return bool(expiry and expiry > current)


def _review_window_valid(
    document: dict[str, Any],
    max_age_seconds: int,
    *,
    now: datetime | None = None,
    not_before: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    started = parse_timestamp(document.get("started_at"))
    finished = parse_timestamp(document.get("finished_at"))
    expires = parse_timestamp(document.get("expires_at"))
    return bool(
        started
        and finished
        and expires
        and started <= finished <= current.replace(microsecond=current.microsecond)
        and (current - finished).total_seconds() <= max_age_seconds
        and (current - finished).total_seconds() >= -60
        and expires > current
        and expires >= finished
        and (not_before is None or started >= not_before)
    )


def _review_identity_valid(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and value.strip() == value
        and len(value) >= 3
        and len(value) <= 200
    )


def _review_evidence_valid(
    evidence_path: pathlib.Path,
    max_age_seconds: int,
    *,
    scope_root: pathlib.Path = REPO_ROOT,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    evidence = read_json(evidence_path)
    expected_keys = {
        "schema",
        "phase",
        "status",
        "planner_identity",
        "reviewer_identity",
        "started_at",
        "finished_at",
        "expires_at",
        "scope",
        "blockers",
        "warnings",
        "redacted",
    }
    if (
        evidence_path.name != REVIEW_EVIDENCE_NAME
        or not isinstance(evidence, dict)
        or set(evidence) != expected_keys
        or evidence.get("schema") != SCHEMA_REVIEW_EVIDENCE
        or evidence.get("phase") != 54
        or evidence.get("status") != "PASS"
        or evidence.get("blockers") != []
        or evidence.get("warnings") != []
        or evidence.get("redacted") is not True
        or _contains_secret(evidence)
        or not _review_identity_valid(evidence.get("planner_identity"))
        or not _review_identity_valid(evidence.get("reviewer_identity"))
        or evidence["planner_identity"].casefold()
        == evidence["reviewer_identity"].casefold()
        or not _review_window_valid(
            evidence,
            max_age_seconds,
            now=now,
        )
    ):
        return None
    scope = evidence.get("scope")
    if not isinstance(scope, list) or len(scope) != len(REVIEW_SCOPE_PATHS):
        return None
    observed_paths: list[str] = []
    for entry in scope:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"path", "sha256"}
            or not isinstance(entry.get("path"), str)
            or not isinstance(entry.get("sha256"), str)
            or not HEX_64_PATTERN.fullmatch(entry["sha256"])
        ):
            return None
        observed_paths.append(entry["path"])
        candidate = scope_root / entry["path"]
        if sha256_file(candidate) != entry["sha256"]:
            return None
    if tuple(observed_paths) != REVIEW_SCOPE_PATHS:
        return None
    return evidence


def _review_gate_valid(
    evidence_path: pathlib.Path,
    gate_path: pathlib.Path,
    max_age_seconds: int,
    *,
    scope_root: pathlib.Path = REPO_ROOT,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    evidence = _review_evidence_valid(
        evidence_path,
        max_age_seconds,
        scope_root=scope_root,
        now=current,
    )
    gate = read_json(gate_path)
    expected_keys = {
        "schema",
        "phase",
        "status",
        "planner_identity",
        "reviewer_identity",
        "started_at",
        "finished_at",
        "expires_at",
        "evidence_path",
        "evidence_sha256",
        "scope_sha256",
        "blockers",
        "warnings",
        "redacted",
    }
    if (
        evidence is None
        or gate_path.name != REVIEW_GATE_NAME
        or gate_path.parent.resolve() != evidence_path.parent.resolve()
        or not isinstance(gate, dict)
        or set(gate) != expected_keys
        or gate.get("schema") != SCHEMA_REVIEW_GATE
        or gate.get("phase") != 54
        or gate.get("status") != "PASS"
        or gate.get("planner_identity") != evidence.get("planner_identity")
        or gate.get("reviewer_identity") != evidence.get("reviewer_identity")
        or gate.get("blockers") != []
        or gate.get("warnings") != []
        or gate.get("redacted") is not True
        or _contains_secret(gate)
    ):
        return False
    bound_evidence = _path_from_evidence(gate.get("evidence_path"), gate_path.parent)
    evidence_finished = parse_timestamp(evidence.get("finished_at"))
    return bool(
        bound_evidence
        and bound_evidence.resolve() == evidence_path.resolve()
        and gate.get("evidence_sha256") == sha256_file(evidence_path)
        and gate.get("scope_sha256") == sha256_json(evidence["scope"])
        and evidence_finished
        and _review_window_valid(
            gate,
            max_age_seconds,
            now=current,
            not_before=evidence_finished,
        )
    )


def _contains_secret(value: Any, key: str | None = None) -> bool:
    if key and key.lower() in SENSITIVE_KEYS:
        return True
    if isinstance(value, dict):
        return any(
            _contains_secret(item, str(item_key)) for item_key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS)
    return False


def _hash_entries_valid(
    entries: Iterable[tuple[Any, Any]],
    evidence_dir: pathlib.Path,
) -> bool:
    for raw_path, expected_hash in entries:
        path = _path_from_evidence(raw_path, evidence_dir)
        if (
            path is None
            or not isinstance(expected_hash, str)
            or not HEX_64_PATTERN.fullmatch(expected_hash)
            or sha256_file(path) != expected_hash
        ):
            return False
    return True


def _artifacts_valid(evidence_json: dict[str, Any], evidence_dir: pathlib.Path) -> bool:
    artifacts = evidence_json.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return False
    entries: list[tuple[Any, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            return False
        entries.append((artifact.get("path"), artifact.get("sha256")))
    return _hash_entries_valid(entries, evidence_dir)


def _previous_gate_valid(
    evidence_json: dict[str, Any],
    plan: str,
    evidence_dir: pathlib.Path,
    max_age_seconds: int,
    *,
    visited: frozenset[tuple[pathlib.Path, pathlib.Path]],
    depth: int,
    remote_transport: Any,
    pin_validator: Any,
    immediate: bool = True,
) -> bool:
    if plan == "54-01":
        return True
    if depth >= MAX_PREDECESSOR_DEPTH:
        return False
    lineage = evidence_json.get("previous_gate")
    if not isinstance(lineage, dict):
        return False
    expected_plan = f"54-{int(plan[-2:]) - 1:02d}"
    expected_stage = TERMINAL_STAGE_BY_PLAN[expected_plan]
    gate_path = _path_from_evidence(lineage.get("gate_path"), evidence_dir)
    prior_evidence_path = _path_from_evidence(
        lineage.get("evidence_path"), evidence_dir
    )
    if gate_path is None or prior_evidence_path is None:
        return False
    gate_path = gate_path.resolve()
    prior_evidence_path = prior_evidence_path.resolve()
    pair = (prior_evidence_path, gate_path)
    if (
        pair in visited
        or gate_path.name != f"{expected_plan}-GATE.json"
        or prior_evidence_path.name != f"{expected_plan}-EVIDENCE.json"
        or gate_path.parent != evidence_dir.resolve()
        or prior_evidence_path.parent != evidence_dir.resolve()
    ):
        return False
    gate_hash = sha256_file(gate_path)
    prior_evidence_hash = sha256_file(prior_evidence_path)
    prior_gate = read_json(gate_path)
    prior_evidence = read_json(prior_evidence_path)
    if (
        gate_hash != lineage.get("gate_sha256")
        or prior_evidence_hash != lineage.get("evidence_sha256")
        or prior_gate is None
        or prior_evidence is None
    ):
        return False
    del remote_transport
    expected_required = list(required_check_ids(expected_plan, expected_stage))
    previous_chain = (
        prior_evidence.get("previous_gate", {}).get("chain_sha256")
        if isinstance(prior_evidence.get("previous_gate"), dict)
        else None
    )
    expected_chain = sha256_json(
        {
            "plan": expected_plan,
            "stage": expected_stage,
            "evidence_sha256": prior_evidence_hash,
            "gate_sha256": gate_hash,
            "previous_chain_sha256": previous_chain,
        }
    )
    pin_state = lineage.get("pin_state")
    commit_pinned = bool(
        pin_state == "commit-pinned"
        and isinstance(lineage.get("source_commit"), str)
        and HEX_40_PATTERN.fullmatch(lineage["source_commit"])
        and lineage.get("atomic_commit_required") is False
        and pin_validator(
            lineage,
            prior_evidence_path,
            gate_path,
            prior_gate.get("runner_sha256"),
        )
    )
    structurally_valid = bool(
        lineage.get("plan") == expected_plan
        and lineage.get("stage") == expected_stage
        and lineage.get("chain_sha256") == expected_chain
        and prior_evidence.get("plan") == expected_plan
        and prior_evidence.get("stage") == expected_stage
        and prior_evidence.get("schema") == SCHEMA_EVIDENCE
        and prior_gate.get("schema") == SCHEMA_GATE
        and prior_gate.get("plan") == expected_plan
        and prior_gate.get("stage") == expected_stage
        and prior_gate.get("status") == "PASS"
        and prior_gate.get("evidence_sha256") == prior_evidence_hash
        and prior_gate.get("required_check_ids") == expected_required
        and isinstance(prior_gate.get("checks"), list)
        and prior_gate["checks"]
        and all(item.get("result") == "PASS" for item in prior_gate["checks"])
        and isinstance(prior_gate.get("runner_sha256"), str)
        and HEX_64_PATTERN.fullmatch(prior_gate["runner_sha256"])
        and (
            not immediate
            or _freshness(prior_gate.get("finished_at"), None, max_age_seconds)
        )
        and commit_pinned
    )
    if not structurally_valid or expected_plan == "54-01":
        return structurally_valid
    return _previous_gate_valid(
        prior_evidence,
        expected_plan,
        prior_evidence_path.parent,
        max_age_seconds,
        visited=visited | {pair},
        depth=depth + 1,
        remote_transport=run_fixed_argv,
        pin_validator=pin_validator,
        immediate=False,
    )


def _git_pin_valid(
    lineage: dict[str, Any],
    evidence_path: pathlib.Path,
    gate_path: pathlib.Path,
    runner_sha256: str,
) -> bool:
    if lineage.get("pin_state") != "commit-pinned":
        return False
    source_commit = lineage.get("source_commit")
    if not isinstance(source_commit, str) or not HEX_40_PATTERN.fullmatch(
        source_commit
    ):
        return False
    git = _fixed_executable("git")
    try:
        relative_evidence = evidence_path.resolve().relative_to(REPO_ROOT)
        relative_gate = gate_path.resolve().relative_to(REPO_ROOT)
        runner_relative = pathlib.Path(__file__).resolve().relative_to(REPO_ROOT)
    except ValueError:
        return False
    for relative_path, expected_hash in (
        (relative_evidence, sha256_file(evidence_path)),
        (relative_gate, sha256_file(gate_path)),
        (runner_relative, runner_sha256),
    ):
        completed = subprocess.run(
            [git, "show", f"{source_commit}:{relative_path.as_posix()}"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"},
            shell=False,
            timeout=10,
        )
        if (
            completed.returncode != 0
            or hashlib.sha256(completed.stdout).hexdigest() != expected_hash
        ):
            return False
    ancestor = subprocess.run(
        [git, "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"},
        shell=False,
        timeout=10,
    )
    return ancestor.returncode == 0


def _operation_lineage_valid(
    evidence_json: dict[str, Any],
    plan: str,
    stage: str | None,
    evidence_dir: pathlib.Path,
) -> bool:
    if stage not in OPERATION_STAGES_BY_PLAN.get(plan, frozenset()):
        return True
    operation = evidence_json.get("operation")
    if not isinstance(operation, dict):
        return False
    contract = OPERATION_CONTRACTS.get(plan)
    if contract is None:
        return False
    operation_path = _path_from_evidence(
        operation.get("operation_plan_path"), evidence_dir
    )
    operation_hash = sha256_file(operation_path) if operation_path else None
    if (
        operation_path is None
        or operation_path.resolve().parent != evidence_dir.resolve()
        or operation_path.name != contract["filename"]
        or operation_hash is None
        or operation_hash != operation.get("operation_plan_sha256")
        or not HEX_64_PATTERN.fullmatch(operation_hash)
    ):
        return False
    operation_json = read_json(operation_path)
    input_hashes = operation.get("input_hashes")
    operations = operation_json.get("operations") if operation_json else None
    created_at = (
        parse_timestamp(operation_json.get("created_at")) if operation_json else None
    )
    expires_at = (
        parse_timestamp(operation_json.get("expires_at")) if operation_json else None
    )
    rollback_path = _path_from_evidence(
        operation_json.get("rollback_receipt_path") if operation_json else None,
        evidence_dir,
    )
    rollback_hash = sha256_file(rollback_path) if rollback_path else None
    rollback = read_json(rollback_path) if rollback_path else None
    if (
        operation_json is None
        or operation_json.get("schema") != SCHEMA_OPERATION_PLAN
        or operation_json.get("plan") != plan
        or operation_json.get("stage") != "preview"
        or operation_json.get("owner") != contract["owner"]
        or not isinstance(operations, list)
        or not operations
        or not all(isinstance(item, str) for item in operations)
        or not set(operations) <= contract["operations"]
        or len(operations) != len(set(operations))
        or not isinstance(input_hashes, dict)
        or not input_hashes
        or operation_json.get("input_hashes") != input_hashes
        or not _hash_entries_valid(input_hashes.items(), evidence_dir)
        or created_at is None
        or expires_at is None
        or expires_at <= created_at
        or not _freshness(
            operation_json.get("created_at"),
            operation_json.get("expires_at"),
            DEFAULT_MAX_AGE_SECONDS,
        )
        or rollback_path is None
        or rollback_path.resolve().parent != evidence_dir.resolve()
        or rollback_path.name != contract["rollback"]
        or rollback_hash != operation_json.get("rollback_receipt_sha256")
        or rollback is None
        or rollback.get("schema") != SCHEMA_ROLLBACK_RECEIPT
        or rollback.get("owner") != contract["owner"]
        or rollback.get("plan") != plan
        or rollback.get("stage") != "preview"
        or rollback.get("status") != "READY"
        or rollback.get("operations") != operations
        or rollback.get("input_hashes") != input_hashes
    ):
        return False
    if stage == "preview":
        return True
    approval_path = _path_from_evidence(operation.get("approval_path"), evidence_dir)
    approval_hash = sha256_file(approval_path) if approval_path else None
    approval = read_json(approval_path) if approval_path else None
    typed = f"APPROVE {plan} {operation_hash}"
    approved_at = parse_timestamp(approval.get("approved_at")) if approval else None
    approval_expires_at = (
        parse_timestamp(approval.get("approval_expires_at")) if approval else None
    )
    if (
        approval_path is None
        or approval_path.resolve().parent != evidence_dir.resolve()
        or approval_path.name != f"{plan}-APPROVAL.json"
        or approval is None
        or approval_hash != operation.get("approval_sha256")
        or approval.get("schema") != SCHEMA_APPROVAL
        or approval.get("owner") != "human-approval"
        or approval.get("plan") != plan
        or approval.get("stage") != "approval"
        or not isinstance(approval.get("actor"), str)
        or not approval.get("actor")
        or approval.get("operation_plan_sha256") != operation_hash
        or approval.get("approval_typed") != typed
        or operation.get("approval_typed") != typed
        or approval.get("approval_expires_at") != operation.get("approval_expires_at")
        or approved_at is None
        or approval_expires_at is None
        or approval_expires_at <= approved_at
        or not _freshness(
            approval.get("approved_at"),
            operation.get("approval_expires_at"),
            DEFAULT_MAX_AGE_SECONDS,
        )
        or approval.get("input_hashes") != input_hashes
        or approval.get("anti_drift_sha256") != sha256_json(input_hashes)
    ):
        return False
    if stage == "approval":
        return True
    anti_drift_path = _path_from_evidence(
        operation.get("anti_drift_readback_path"),
        evidence_dir,
    )
    anti_drift_hash = sha256_file(anti_drift_path) if anti_drift_path else None
    anti_drift = read_json(anti_drift_path) if anti_drift_path else None
    apply_path = _path_from_evidence(operation.get("apply_receipt_path"), evidence_dir)
    apply_hash = sha256_file(apply_path) if apply_path else None
    apply_receipt = read_json(apply_path) if apply_path else None
    apply_started = (
        parse_timestamp(apply_receipt.get("started_at")) if apply_receipt else None
    )
    apply_finished = (
        parse_timestamp(apply_receipt.get("finished_at")) if apply_receipt else None
    )
    return bool(
        anti_drift_path is not None
        and anti_drift_path.resolve().parent == evidence_dir.resolve()
        and anti_drift_path.name == f"{plan}-ANTI-DRIFT.json"
        and anti_drift_hash == operation.get("anti_drift_readback_sha256")
        and anti_drift is not None
        and anti_drift.get("schema") == "phase54.anti-drift.v1"
        and anti_drift.get("plan") == plan
        and anti_drift.get("operation_plan_sha256") == operation_hash
        and anti_drift.get("input_hashes") == input_hashes
        and anti_drift.get("status") == "PASS"
        and apply_path is not None
        and apply_path.resolve().parent == evidence_dir.resolve()
        and apply_path.name == f"{plan}-APPLY-RECEIPT.json"
        and apply_hash == operation.get("apply_receipt_sha256")
        and apply_receipt is not None
        and apply_receipt.get("schema") == SCHEMA_APPLY_RECEIPT
        and apply_receipt.get("owner") == contract["owner"]
        and apply_receipt.get("plan") == plan
        and apply_receipt.get("stage") == "apply"
        and apply_receipt.get("status") == "PASS"
        and apply_receipt.get("operation_plan_sha256") == operation_hash
        and apply_receipt.get("approval_sha256") == approval_hash
        and apply_receipt.get("anti_drift_sha256") == anti_drift_hash
        and apply_receipt.get("rollback_receipt_sha256") == rollback_hash
        and apply_receipt.get("operations") == operations
        and isinstance(apply_receipt.get("request_ids"), list)
        and apply_receipt["request_ids"]
        and all(isinstance(item, str) and item for item in apply_receipt["request_ids"])
        and apply_started is not None
        and apply_finished is not None
        and apply_finished >= apply_started
    )


def _backup_evidence_valid(
    evidence_json: dict[str, Any],
    evidence_dir: pathlib.Path,
) -> bool:
    backups = evidence_json.get("backups")
    if (
        not isinstance(backups, dict)
        or backups.get("retroactive_approval") is not False
    ):
        return False
    pre_existing = backups.get("pre_existing")
    pending_writes = backups.get("pending_writes")
    if (
        not isinstance(pre_existing, list)
        or not isinstance(pending_writes, list)
        or not all(isinstance(item, str) for item in pending_writes)
    ):
        return False
    expected_receipts = {
        "srv1": "54-02-SRV1-BACKUP-RECEIPT.json",
        "srv3": "54-02-SRV3-BACKUP-RECEIPT.json",
        "be3": "54-02-BE3-BACKUP-RECEIPT.json",
    }
    observed_owners: set[str] = set()
    for item in pre_existing:
        if not isinstance(item, dict):
            return False
        receipt_path = _path_from_evidence(item.get("receipt_path"), evidence_dir)
        receipt = read_json(receipt_path) if receipt_path else None
        if (
            receipt is None
            or sha256_file(receipt_path) != item.get("receipt_sha256")
            or receipt.get("schema") != SCHEMA_BACKUP_RECEIPT
            or item.get("classification") != "pre-existing-evidence"
            or item.get("approval_claimed") is not False
            or receipt.get("classification") != "pre-existing-evidence"
            or receipt.get("approval_claimed") is not False
            or not isinstance(receipt.get("remote_path"), str)
            or not receipt.get("remote_path")
            or not isinstance(receipt.get("remote_sha256"), str)
            or not HEX_64_PATTERN.fullmatch(receipt["remote_sha256"])
            or not isinstance(receipt.get("owner"), str)
            or not receipt.get("owner")
            or receipt.get("owner") not in expected_receipts
            or receipt_path.name != expected_receipts[receipt["owner"]]
            or receipt.get("owner") in observed_owners
            or receipt.get("mode") != "read-only-proof"
        ):
            return False
        observed_owners.add(receipt["owner"])
        if receipt["owner"] == "be3" and (
            receipt.get("source_branch")
            != "codex/phase54-be3-readonly-evidence-20260726"
            or receipt.get("source_commit")
            != "24f2562af086625b0678c4573f1c03a77270fc22"
            or receipt.get("source_evidence_path")
            != "modules/home-router-be3/evidence/phase54/be3-lan-readonly-20260726-final-v13.json"
            or receipt.get("source_evidence_sha256")
            != "dbb8311dd341a8f9dd71f0da1ea13760aa53cae711525faa170c7d54d15de00c"
            or receipt.get("metadata_path")
            != "modules/home-router-be3/evidence/phase54/be3-native-export-20260726-final-v11.json"
            or receipt.get("metadata_sha256")
            != "5d93a2d45323249f4bf4ddc0530f5a03d5c054640ec53a909d8d5d09d02a9aa3"
            or receipt.get("remote_path")
            != "/home/ubuntu/.local/state/home-router-be3/backups/phase54/be3-native-20260726T052404Z.bin"
            or receipt.get("remote_sha256")
            != "866adbef8a1434622f0b4028ddaf5b5bd76afaeafc246e7a576b675c889cb781"
            or receipt.get("size") != 32864
            or receipt.get("file_mode") != "0600"
            or receipt.get("apply") != "NOT RUN"
            or receipt.get("restore") != "NOT RUN"
        ):
            return False
    allowed_pending = {"oci_boot_backup", "explicit_refresh"}
    return bool(
        observed_owners == set(expected_receipts)
        and set(pending_writes) <= allowed_pending
        and not ({"srv1_existing_backup", "srv3_existing_backup"} & set(pending_writes))
    )


def _builder_valid(
    evidence_json: dict[str, Any],
    evidence_dir: pathlib.Path,
) -> bool:
    builder = evidence_json.get("builder")
    if not isinstance(builder, dict):
        return False
    receipt_path = _path_from_evidence(builder.get("receipt_path"), evidence_dir)
    receipt_hash = sha256_file(receipt_path) if receipt_path else None
    receipt = read_json(receipt_path) if receipt_path else None
    targets = builder.get("targets")
    if (
        builder.get("owner") != "oci-admin"
        or builder.get("validated") is not True
        or not isinstance(builder.get("commit"), str)
        or not HEX_40_PATTERN.fullmatch(builder["commit"])
        or receipt_hash != builder.get("receipt_sha256")
        or receipt is None
        or targets != EXPECTED_BUILDER_TARGETS
    ):
        return False
    serialized_targets = json.dumps(targets, sort_keys=True)
    return bool(
        "10.21" not in serialized_targets
        and receipt
        == {
            "owner": builder["owner"],
            "validated": builder["validated"],
            "commit": builder["commit"],
            "targets": targets,
        }
    )


def _public_ip_valid(
    evidence_json: dict[str, Any],
    plan: str,
    evidence_dir: pathlib.Path,
) -> bool:
    public_ip = evidence_json.get("public_ip")
    if not isinstance(public_ip, dict):
        return False
    forbidden_operations = {"release", "delete", "recreate"}
    common_valid = bool(
        public_ip.get("address") == "163.176.232.119"
        and public_ip.get("ocid")
        and public_ip.get("ocid") == public_ip.get("baseline_ocid")
        and public_ip.get("label") == "horistic-srv-1"
        and public_ip.get("state") in {"RESERVED", "ASSIGNED"}
        and public_ip.get("operation") not in forbidden_operations
    )
    if not common_valid:
        return False
    if plan == "54-02":
        binding = {
            "public_ip_ocid": public_ip.get("ocid"),
            "address": public_ip.get("address"),
            "private_ip_address": public_ip.get("private_ip_address"),
            "private_ip_ocid": public_ip.get("private_ip_ocid"),
            "vnic_ocid": public_ip.get("vnic_ocid"),
            "subnet_ocid": public_ip.get("subnet_ocid"),
        }
        return bool(
            public_ip.get("binding") == BASELINE_PUBLIC_BINDING
            and public_ip.get("private_ip_address") == BASELINE_PUBLIC_BINDING
            and public_ip.get("baseline_private_ip_ocid")
            == public_ip.get("private_ip_ocid")
            and public_ip.get("lifetime") == "RESERVED"
            and public_ip.get("scope") == "REGION"
            and all(isinstance(value, str) and value for value in binding.values())
            and public_ip.get("current_binding_sha256") == sha256_json(binding)
            and public_ip.get("operation") == "read"
        )
    if plan not in {"54-05", "54-10"}:
        return False
    binding = {
        "public_ip_ocid": public_ip.get("ocid"),
        "address": public_ip.get("address"),
        "private_ip_address": public_ip.get("private_ip_address"),
        "private_ip_ocid": public_ip.get("private_ip_ocid"),
        "vnic_ocid": public_ip.get("vnic_ocid"),
        "subnet_ocid": public_ip.get("subnet_ocid"),
        "vcn_ocid": public_ip.get("vcn_ocid"),
    }
    if binding["private_ip_address"] != "10.31.1.31" or not all(
        isinstance(value, str) and value for value in binding.values()
    ):
        return False
    operation_path = _path_from_evidence(
        public_ip.get("approved_operation_plan_path"),
        evidence_dir,
    )
    operation_hash = sha256_file(operation_path) if operation_path else None
    operation = read_json(operation_path) if operation_path else None
    readback_path = _path_from_evidence(
        public_ip.get("binding_readback_path"),
        evidence_dir,
    )
    readback_hash = sha256_file(readback_path) if readback_path else None
    readback = read_json(readback_path) if readback_path else None
    if (
        operation is None
        or operation_hash != public_ip.get("approved_operation_plan_sha256")
        or operation.get("plan") != "54-05"
        or operation.get("public_ip_binding") != binding
        or readback is None
        or readback_path is None
        or readback_path.resolve().parent != evidence_dir.resolve()
        or readback_path.name != "54-05-PUBLIC-IP-READBACK.json"
        or readback_hash != public_ip.get("binding_readback_sha256")
        or readback.get("schema") != SCHEMA_PUBLIC_IP_READBACK
        or readback.get("status") != "PASS"
        or readback.get("approved_operation_plan_sha256") != operation_hash
        or readback.get("binding") != binding
        or readback.get("binding_sha256") != sha256_json(binding)
        or public_ip.get("current_binding_sha256") != sha256_json(binding)
    ):
        return False
    if plan == "54-05":
        operation_lineage = evidence_json.get("operation")
        return bool(
            isinstance(operation_lineage, dict)
            and operation_lineage.get("operation_plan_path")
            == public_ip.get("approved_operation_plan_path")
            and operation_lineage.get("operation_plan_sha256") == operation_hash
        )
    anchor = public_ip.get("cutover_anchor")
    if not isinstance(anchor, dict):
        return False
    exact_anchor_files = {
        "evidence": "54-05-EVIDENCE.json",
        "gate": "54-05-GATE.json",
        "operation": OPERATION_CONTRACTS["54-05"]["filename"],
        "approval": "54-05-APPROVAL.json",
        "apply": "54-05-APPLY-RECEIPT.json",
    }
    resolved: dict[str, pathlib.Path] = {}
    for key, filename in exact_anchor_files.items():
        path = _path_from_evidence(anchor.get(f"{key}_path"), evidence_dir)
        if (
            path is None
            or path.resolve().parent != evidence_dir.resolve()
            or path.name != filename
            or sha256_file(path) != anchor.get(f"{key}_sha256")
        ):
            return False
        resolved[key] = path
    anchored_evidence = read_json(resolved["evidence"])
    anchored_gate = read_json(resolved["gate"])
    anchored_apply = read_json(resolved["apply"])
    return bool(
        anchored_evidence
        and anchored_evidence.get("schema") == SCHEMA_EVIDENCE
        and anchored_evidence.get("plan") == "54-05"
        and anchored_evidence.get("stage") == "apply"
        and anchored_evidence.get("operation", {}).get("operation_plan_sha256")
        == operation_hash
        and anchored_gate
        and anchored_gate.get("schema") == SCHEMA_GATE
        and anchored_gate.get("plan") == "54-05"
        and anchored_gate.get("stage") == "apply"
        and anchored_gate.get("status") == "PASS"
        and anchored_gate.get("evidence_sha256") == anchor.get("evidence_sha256")
        and anchored_apply
        and anchored_apply.get("schema") == SCHEMA_APPLY_RECEIPT
        and anchored_apply.get("operation_plan_sha256") == operation_hash
        and anchored_apply.get("status") == "PASS"
    )


def _s20_retirement_valid(
    evidence_json: dict[str, Any],
    evidence_dir: pathlib.Path,
) -> bool:
    retirement = evidence_json.get("s20_retirement")
    if not isinstance(retirement, dict):
        return False
    receipt_path = _path_from_evidence(retirement.get("receipt_path"), evidence_dir)
    receipt_hash = sha256_file(receipt_path) if receipt_path else None
    receipt = read_json(receipt_path) if receipt_path else None
    return bool(
        receipt is not None
        and receipt_hash == retirement.get("receipt_sha256")
        and receipt.get("schema") == SCHEMA_S20_RETIREMENT_RECEIPT
        and receipt.get("plan") == "54-08"
        and receipt.get("decision") == "retire"
        and receipt.get("old_peer") == "10.100.100.9"
        and receipt.get("peer_present") is False
        and receipt.get("allowed_ip_present") is False
        and receipt.get("new_peer") == "10.100.100.11"
        and receipt.get("new_peer_handshake") == "PASS"
        and receipt.get("status") == "PASS"
    )


def _gate_status(checks: Iterable[dict[str, Any]]) -> str:
    return "PASS" if all(item.get("result") == "PASS" for item in checks) else "BLOCK"


def _stability_gate_valid(
    evidence: dict[str, Any],
    evidence_dir: pathlib.Path,
) -> bool:
    reference = evidence.get("stability_gate")
    if not isinstance(reference, dict):
        return False
    gate_path = _path_from_evidence(reference.get("gate_path"), evidence_dir)
    evidence_path = _path_from_evidence(reference.get("evidence_path"), evidence_dir)
    gate = read_json(gate_path) if gate_path else None
    stability_evidence = read_json(evidence_path) if evidence_path else None
    return bool(
        gate_path
        and evidence_path
        and gate_path.resolve().parent == evidence_dir.resolve()
        and evidence_path.resolve().parent == evidence_dir.resolve()
        and gate_path.name == "54-09-STABILITY-GATE.json"
        and evidence_path.name == "54-09-STABILITY-EVIDENCE.json"
        and sha256_file(gate_path) == reference.get("gate_sha256")
        and sha256_file(evidence_path) == reference.get("evidence_sha256")
        and gate
        and gate.get("schema") == SCHEMA_GATE
        and gate.get("plan") == "54-09"
        and gate.get("stage") == "stability"
        and gate.get("status") == "PASS"
        and gate.get("evidence_sha256") == reference.get("evidence_sha256")
        and gate.get("required_check_ids")
        == list(required_check_ids("54-09", "stability"))
        and stability_evidence
        and stability_evidence.get("schema") == SCHEMA_EVIDENCE
        and stability_evidence.get("plan") == "54-09"
        and stability_evidence.get("stage") == "stability"
    )


def _knowledge_freeze_valid(
    evidence: dict[str, Any],
    evidence_dir: pathlib.Path,
) -> bool:
    reference = evidence.get("knowledge_freeze")
    if not isinstance(reference, dict):
        return False
    freeze_path = _path_from_evidence(reference.get("path"), evidence_dir)
    freeze = read_json(freeze_path) if freeze_path else None
    artifact_hashes = freeze.get("artifact_hashes") if freeze else None
    graphify = freeze.get("graphify") if freeze else None
    receipts = freeze.get("receipt_hashes") if freeze else None
    if (
        freeze_path is None
        or freeze_path.resolve().parent != evidence_dir.resolve()
        or freeze_path.name != "54-10-KNOWLEDGE-FREEZE.json"
        or sha256_file(freeze_path) != reference.get("sha256")
        or not isinstance(freeze, dict)
        or freeze.get("schema") != SCHEMA_KNOWLEDGE_FREEZE
        or freeze.get("plan") != "54-10"
        or freeze.get("status") != "FROZEN"
        or freeze.get("mutations_after_freeze") is not False
        or not isinstance(graphify, dict)
        or graphify.get("stale") is not False
        or graphify.get("commit_stale") is not False
        or graphify.get("relevant_nodes") is not True
        or graphify.get("query") != "phase54_network_gate"
        or not isinstance(artifact_hashes, dict)
        or not artifact_hashes
        or not isinstance(receipts, dict)
        or not receipts
    ):
        return False
    required_semantic = {
        "54-CONTEXT.md",
        "54-RESEARCH.md",
        "54-VALIDATION.md",
        "54-VALIDATION-CONTRACT.md",
        "54-10-SUMMARY.md",
    }
    if {pathlib.Path(item).name for item in artifact_hashes} != required_semantic:
        return False
    return bool(
        _hash_entries_valid(artifact_hashes.items(), evidence_dir)
        and _hash_entries_valid(receipts.items(), evidence_dir)
    )


def _runner_contract_probe(
    context: ProbeContext,
    check_id: str,
) -> dict[str, Any]:
    evidence = read_json(context.evidence)
    passed = bool(
        evidence
        and evidence.get("schema") == SCHEMA_EVIDENCE
        and evidence.get("plan") == context.plan
        and evidence.get("stage") == context.stage
        and _freshness(
            evidence.get("generated_at"),
            evidence.get("expires_at"),
            context.max_age_seconds,
        )
    )
    if passed and check_id in {
        "operation_plan_preview",
        "typed_approval",
        "apply_receipt",
    }:
        passed = _operation_lineage_valid(
            evidence,
            context.plan,
            context.stage,
            context.evidence_dir,
        )
    if passed and check_id == "independent_review_gate":
        passed = _review_gate_valid(
            context.evidence_dir / REVIEW_EVIDENCE_NAME,
            context.evidence_dir / REVIEW_GATE_NAME,
            context.max_age_seconds,
        )
    if passed and check_id == "operation_plan_preview" and context.plan == "54-09":
        passed = _stability_gate_valid(evidence, context.evidence_dir)
    if passed and check_id == "stage_preflight" and context.plan == "54-02":
        passed = _backup_evidence_valid(evidence, context.evidence_dir)
    if passed and check_id == "stage_stability":
        stability = evidence.get("stability")
        readings = stability.get("readings") if isinstance(stability, dict) else None
        passed = bool(
            isinstance(readings, list)
            and len(readings) == 2
            and all(
                isinstance(item, dict)
                and parse_timestamp(item.get("observed_at")) is not None
                and isinstance(item.get("sha256"), str)
                and HEX_64_PATTERN.fullmatch(item["sha256"])
                for item in readings
            )
            and (
                parse_timestamp(readings[1]["observed_at"])
                - parse_timestamp(readings[0]["observed_at"])
            ).total_seconds()
            >= 900
        )
    if passed and check_id == "knowledge_sync":
        if context.plan == "54-08":
            passed = _operation_lineage_valid(
                evidence,
                context.plan,
                context.stage,
                context.evidence_dir,
            ) and _s20_retirement_valid(evidence, context.evidence_dir)
        elif context.plan == "54-10":
            forbidden = (
                "operation",
                "apply",
                "apply_operation",
                "apply_receipts",
                "writes",
                "write_operations",
                "write_receipts",
            )
            passed = bool(
                _knowledge_freeze_valid(evidence, context.evidence_dir)
                and evidence.get("mutations_attempted") is False
                and evidence.get("production_mutations_attempted", False) is False
                and all(evidence.get(key) in (None, [], {}) for key in forbidden)
            )
    if passed and check_id == "stage_preflight" and context.plan == "54-10":
        passed = _knowledge_freeze_valid(evidence, context.evidence_dir)
    return {
        "id": check_id,
        "required": True,
        "adapter": "runner-contract",
        "command_id": f"phase54.{check_id}",
        "exit_code": 0 if passed else 2,
        "result": "PASS" if passed else "BLOCK",
        "read_only": True,
        "mutation_performed": False,
        "secret_material_present": False,
        "request_id": f"runner-contract-{context.plan}-{context.stage or 'none'}",
        "observed_sha256": sha256_file(context.evidence),
        "artifact_hashes": {"canonical-evidence": sha256_file(context.evidence) or ""},
    }


def _adapter_coverage_valid(plan: str) -> bool:
    if plan == "54-01":
        return True
    if plan not in PLAN_IDS or not ADAPTER_PATH.is_file():
        return False
    result = _run_local_command(
        [
            str(pathlib.Path(sys.executable).resolve()),
            str(ADAPTER_PATH.resolve()),
            "list",
            "--plan",
            plan,
        ]
    )
    if not result or result[0] != 0:
        return False
    try:
        payload = json.loads(result[1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list):
        return False
    observed = {
        (item.get("stage"), item.get("check_id"))
        for item in keys
        if isinstance(item, dict)
    }
    expected = {
        (stage, check_id)
        for (candidate, stage, check_id), spec in PROBE_REGISTRY.items()
        if candidate == plan and spec.kind == "remote-owner"
    }
    return bool(
        payload.get("schema") == "phase54.adapter-coverage.v1"
        and payload.get("plan") == plan
        and payload.get("status") == "READY"
        and len(observed) == len(keys)
        and observed == expected
    )


def evaluate_evidence(
    evidence_path: pathlib.Path,
    plan: str,
    stage: str | None,
    max_age_seconds: int,
    *,
    _visited: frozenset[tuple[pathlib.Path, pathlib.Path]] = frozenset(),
    _depth: int = 0,
    _local_transport: Any = run_fixed_argv,
    _remote_transport: Any = run_fixed_argv,
    _adapter_validator: Any = _adapter_coverage_valid,
    _pin_validator: Any = _git_pin_valid,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None]:
    checks: list[dict[str, Any]] = []
    evidence_hash = sha256_file(evidence_path)
    checks.append(
        result_check(
            "evidence_exists",
            "non-empty evidence file",
            str(evidence_path),
            evidence_hash is not None,
        )
    )
    evidence_json = read_json(evidence_path) if evidence_hash else None
    checks.append(
        result_check(
            "evidence_machine_readable",
            SCHEMA_EVIDENCE,
            evidence_json.get("schema") if evidence_json else None,
            bool(evidence_json and evidence_json.get("schema") == SCHEMA_EVIDENCE),
        )
    )
    expected_ids = required_check_ids(plan, stage)
    plan_valid = plan in PLAN_IDS and bool(
        evidence_json and evidence_json.get("plan") == plan
    )
    checks.append(
        result_check(
            "plan_id",
            plan,
            evidence_json.get("plan") if evidence_json else None,
            plan_valid,
        )
    )
    stage_valid = bool(
        plan in STAGES_BY_PLAN
        and stage in STAGES_BY_PLAN[plan]
        and stage not in (STAGE_IDS - STAGES_BY_PLAN[plan])
        and evidence_json
        and evidence_json.get("stage") == stage
    )
    checks.append(
        result_check(
            "stage",
            sorted(item for item in STAGES_BY_PLAN.get(plan, ()) if item is not None)
            or [None],
            stage,
            stage_valid,
        )
    )
    fresh = bool(
        evidence_json
        and _freshness(
            evidence_json.get("generated_at"),
            evidence_json.get("expires_at"),
            max_age_seconds,
        )
    )
    checks.append(
        result_check(
            "freshness",
            f"generated within {max_age_seconds}s and unexpired",
            evidence_json.get("generated_at") if evidence_json else None,
            fresh,
        )
    )
    claimed_status = evidence_json.get("status") if evidence_json else None
    legacy_ok = claimed_status not in LEGACY_FAILURE_STATES
    checks.append(
        result_check(
            "legacy_status",
            "legacy BLOCK/BLOCKED/UNKNOWN/PARTIAL absent",
            claimed_status,
            legacy_ok,
        )
    )
    redaction_ok = bool(
        evidence_json
        and evidence_json.get("redacted") is True
        and not _contains_secret(evidence_json)
    )
    checks.append(
        result_check(
            "redaction",
            "redacted evidence with no secret material",
            evidence_json.get("redacted") if evidence_json else None,
            redaction_ok,
        )
    )
    raw_observed_checks = evidence_json.get("check_inputs") if evidence_json else None
    observed_by_id: dict[str, dict[str, Any]] = {}
    duplicates = False
    forbidden_input_fields = {
        "adapter",
        "argv",
        "command",
        "command_id",
        "host",
        "tool",
        "result",
        "observed",
        "exit_code",
    }
    if isinstance(raw_observed_checks, dict):
        for check_id, item in raw_observed_checks.items():
            if not isinstance(check_id, str) or not isinstance(item, dict):
                duplicates = True
                continue
            if check_id in observed_by_id or forbidden_input_fields & set(item):
                duplicates = True
            observed_by_id[check_id] = item
    complete = bool(
        expected_ids and not duplicates and set(expected_ids) == set(observed_by_id)
    )
    checks.append(
        result_check(
            "required_checks_complete",
            list(expected_ids),
            sorted(observed_by_id),
            complete,
        )
    )
    evidence_dir = evidence_path.parent
    context = ProbeContext(
        plan=plan,
        stage=stage,
        evidence=evidence_path,
        evidence_dir=evidence_dir,
        max_age_seconds=max_age_seconds,
    )
    adapters_ready = bool(_adapter_validator(plan))
    checks.append(
        result_check(
            "adapter_coverage",
            "owner adapter registry exactly covers every required plan/stage/check tuple",
            plan,
            adapters_ready,
        )
    )
    executed_checks = (
        [
            execute_registered_probe(
                context,
                check_id,
                local_transport=_local_transport,
                remote_transport=_remote_transport,
            )
            for check_id in expected_ids
        ]
        if complete and adapters_ready
        else []
    )
    observed_valid = bool(
        complete
        and executed_checks
        and all(item.get("result") == "PASS" for item in executed_checks)
    )
    checks.append(
        result_check(
            "observed_checks",
            "all required checks executed from runner-owned fixed adapters",
            executed_checks,
            observed_valid,
        )
    )
    artifact_valid = bool(
        evidence_json and _artifacts_valid(evidence_json, evidence_dir)
    )
    checks.append(
        result_check(
            "artifact_hashes",
            "all artifacts exist and SHA-256 hashes match",
            len(evidence_json.get("artifacts", [])) if evidence_json else 0,
            artifact_valid,
        )
    )
    previous_valid = bool(
        evidence_json
        and _previous_gate_valid(
            evidence_json,
            plan,
            evidence_dir,
            max_age_seconds,
            visited=_visited,
            depth=_depth,
            remote_transport=_remote_transport,
            pin_validator=_pin_validator,
        )
    )
    checks.append(
        result_check(
            "previous_gate_lineage",
            "immediate predecessor gate is fresh and hash-valid",
            evidence_json.get("previous_gate") if evidence_json else None,
            previous_valid,
        )
    )
    operation_valid = bool(
        evidence_json
        and _operation_lineage_valid(evidence_json, plan, stage, evidence_dir)
    )
    checks.append(
        result_check(
            "operation_lineage",
            "operation/input/approval/anti-drift hashes match stage",
            stage,
            operation_valid,
        )
    )
    if plan == "54-02":
        backup_evidence_valid = bool(
            evidence_json and _backup_evidence_valid(evidence_json, evidence_dir)
        )
        checks.append(
            result_check(
                "backup_evidence_classification",
                "pre-existing backups are non-authorizing hash-bound evidence; pending writes are new",
                evidence_json.get("backups") if evidence_json else None,
                backup_evidence_valid,
            )
        )
    if plan == "54-03":
        builder_valid = bool(
            evidence_json and _builder_valid(evidence_json, evidence_dir)
        )
        checks.append(
            result_check(
                "builder_targets",
                EXPECTED_BUILDER_TARGETS,
                evidence_json.get("builder", {}).get("targets")
                if evidence_json
                else None,
                builder_valid,
            )
        )
    if plan in {"54-02", "54-05", "54-10"}:
        public_ip_valid = bool(
            evidence_json and _public_ip_valid(evidence_json, plan, evidence_dir)
        )
        checks.append(
            result_check(
                "public_ip_identity",
                "same public/private OCIDs, label and terminal state",
                evidence_json.get("public_ip") if evidence_json else None,
                public_ip_valid,
            )
        )
    if plan == "54-08" and stage == "sync":
        retirement_valid = bool(
            evidence_json and _s20_retirement_valid(evidence_json, evidence_dir)
        )
        checks.append(
            result_check(
                "s20_old_peer_absent",
                "10.100.100.9 peer and AllowedIP absent with hash-bound receipt",
                evidence_json.get("s20_retirement") if evidence_json else None,
                retirement_valid,
            )
        )
    if plan in {"54-07", "54-08", "54-10"}:
        observed_map = evidence_json.get("target_map") if evidence_json else None
        checks.append(
            result_check(
                "edge_target_map",
                EDGE_TARGET_MAP,
                observed_map,
                observed_map == EDGE_TARGET_MAP,
            )
        )
    if plan == "54-10":
        full_matrix = next(
            (
                item
                for item in executed_checks
                if item.get("id") == "full_matrix"
                and item.get("result") == "PASS"
                and isinstance(item.get("normalized"), dict)
            ),
            None,
        )
        residuals = (
            full_matrix["normalized"].get("operational_10_21") if full_matrix else None
        )
        residual_live = (
            full_matrix["normalized"].get("residual_live") if full_matrix else None
        )
        checks.append(
            result_check(
                "zero_operational_10_21",
                "empty residual list derived from live normalized full_matrix adapter inventory",
                {"operational_10_21": residuals, "residual_live": residual_live},
                bool(
                    residuals == []
                    and isinstance(residual_live, dict)
                    and residual_live.get("present") is False
                    and residual_live.get("count") == 0
                    and residual_live.get("sha256") == sha256_json([])
                ),
            )
        )
    if plan == "54-10" and stage == "sync":
        write_signal_keys = (
            "operation",
            "apply",
            "apply_operation",
            "apply_receipts",
            "writes",
            "write_operations",
            "write_receipts",
        )
        present_write_signals = {
            key: evidence_json.get(key)
            for key in write_signal_keys
            if evidence_json and evidence_json.get(key) not in (None, [], {})
        }
        no_write_valid = bool(
            evidence_json
            and evidence_json.get("mutations_attempted") is False
            and evidence_json.get("production_mutations_attempted", False) is False
            and not present_write_signals
        )
        checks.append(
            result_check(
                "sync_read_only",
                "no production mutation, write receipt or apply operation",
                {
                    "mutations_attempted": evidence_json.get("mutations_attempted")
                    if evidence_json
                    else None,
                    "production_mutations_attempted": evidence_json.get(
                        "production_mutations_attempted"
                    )
                    if evidence_json
                    else None,
                    "write_signals": present_write_signals,
                },
                no_write_valid,
            )
        )
    return checks, evidence_json, evidence_hash


def _write_gate(path: pathlib.Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def run(args: argparse.Namespace) -> int:
    evidence = pathlib.Path(args.evidence).resolve()
    gate = pathlib.Path(args.gate).resolve()
    max_age_seconds = int(getattr(args, "max_age_seconds", DEFAULT_MAX_AGE_SECONDS))
    stage = getattr(args, "stage", None)
    checks, evidence_json, evidence_hash = evaluate_evidence(
        evidence,
        args.plan,
        stage,
        max_age_seconds,
        _local_transport=getattr(args, "local_transport", run_fixed_argv),
        _remote_transport=getattr(args, "remote_transport", run_fixed_argv),
        _adapter_validator=getattr(args, "adapter_validator", _adapter_coverage_valid),
        _pin_validator=getattr(args, "pin_validator", _git_pin_valid),
    )
    status = _gate_status(checks)
    receipt = {
        "schema": SCHEMA_GATE,
        "phase": 54,
        "plan": args.plan,
        "stage": stage,
        "mode": "read-only",
        "status": status,
        "started_at": getattr(args, "started_at", utc_now()),
        "finished_at": utc_now(),
        "required_check_ids": list(required_check_ids(args.plan, stage)),
        "checks": checks,
        "evidence_sha256": evidence_hash,
        "runner_sha256": sha256_file(pathlib.Path(__file__).resolve()),
        "next_wave_gate": f"PASS:{args.plan}" if status == "PASS" else None,
        "mutations_attempted": bool(evidence_json.get("mutations_attempted", False))
        if evidence_json
        else False,
        "redacted": bool(getattr(args, "redact", False)),
    }
    _write_gate(gate, receipt)
    print(
        json.dumps(
            {
                "status": status,
                "plan": args.plan,
                "stage": stage,
                "gate": str(gate),
                "evidence_sha256": evidence_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 2


def assert_gate(args: argparse.Namespace) -> int:
    evidence = pathlib.Path(args.evidence).resolve()
    gate_path = pathlib.Path(args.gate).resolve()
    max_age_seconds = int(getattr(args, "max_age_seconds", DEFAULT_MAX_AGE_SECONDS))
    stage = getattr(args, "stage", None)
    gate_json = read_json(gate_path)
    evidence_hash = sha256_file(evidence)
    checks, _, _ = evaluate_evidence(
        evidence,
        args.plan,
        stage,
        max_age_seconds,
        _local_transport=getattr(args, "local_transport", run_fixed_argv),
        _remote_transport=getattr(args, "remote_transport", run_fixed_argv),
        _adapter_validator=getattr(args, "adapter_validator", _adapter_coverage_valid),
        _pin_validator=getattr(args, "pin_validator", _git_pin_valid),
    )
    derived_status = _gate_status(checks)
    gate_valid = bool(
        gate_json
        and gate_json.get("schema") == SCHEMA_GATE
        and gate_json.get("phase") == 54
        and gate_json.get("plan") == args.plan
        and gate_json.get("stage") == stage
        and gate_json.get("status") == "PASS"
        and gate_json.get("evidence_sha256") == evidence_hash
        and gate_json.get("required_check_ids")
        == list(required_check_ids(args.plan, stage))
        and isinstance(gate_json.get("checks"), list)
        and gate_json["checks"]
        and all(item.get("result") == "PASS" for item in gate_json["checks"])
        and _freshness(gate_json.get("finished_at"), None, max_age_seconds)
        and derived_status == "PASS"
    )
    status = "PASS" if gate_valid else "BLOCK"
    print(
        json.dumps(
            {
                "status": status,
                "plan": args.plan,
                "stage": stage,
                "gate": str(gate_path),
                "evidence_sha256": evidence_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if gate_valid else 2


def assert_review_gate(args: argparse.Namespace) -> int:
    evidence = pathlib.Path(args.evidence).resolve()
    gate_path = pathlib.Path(args.gate).resolve()
    max_age_seconds = int(getattr(args, "max_age_seconds", DEFAULT_MAX_AGE_SECONDS))
    scope_root = pathlib.Path(getattr(args, "scope_root", REPO_ROOT)).resolve()
    valid = _review_gate_valid(
        evidence,
        gate_path,
        max_age_seconds,
        scope_root=scope_root,
    )
    status = "PASS" if valid else "BLOCK"
    print(
        json.dumps(
            {
                "status": status,
                "phase": 54,
                "gate": str(gate_path),
                "evidence_sha256": sha256_file(evidence),
                "scope_count": len(REVIEW_SCOPE_PATHS) if valid else None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if valid else 2


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--plan", required=True)
    parser.add_argument("--stage")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)


def _run_local_command(
    argv: list[str],
    *,
    timeout: int = 25,
) -> tuple[int, bytes, bytes] | None:
    if (
        not argv
        or not pathlib.Path(argv[0]).is_absolute()
        or any("\n" in item or "\r" in item for item in argv)
    ):
        return None
    try:
        child_env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TMPDIR": "/var/tmp",
        }
        for name in ("HOME", "CODEX_HOME"):
            if os.environ.get(name):
                child_env[name] = os.environ[name]
        completed = subprocess.run(
            argv,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=False,
            timeout=timeout,
            shell=False,
            stdin=subprocess.DEVNULL,
            env=child_env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if len(completed.stdout) > 1024 * 1024 or len(completed.stderr) > 1024 * 1024:
        return None
    return completed.returncode, completed.stdout, completed.stderr


def _workstream_routing_probe(wrapper_path: pathlib.Path) -> bool:
    config_path = (
        REPO_ROOT / ".planning/workstreams/network-horistic-readdress/config.json"
    )
    config = read_json(config_path)
    workflow = config.get("workflow") if config else None
    graphify = config.get("graphify") if config else None
    semantic_config = bool(
        config
        and config.get("runtime") == "codex"
        and config.get("granularity") == "fine"
        and config.get("parallelization") is False
        and isinstance(workflow, dict)
        and workflow.get("verifier") is True
        and workflow.get("nyquist_validation") is True
        and workflow.get("security_enforcement") is True
        and workflow.get("auto_advance") is False
        and workflow.get("use_worktrees") is False
        and isinstance(graphify, dict)
        and graphify.get("enabled") is True
    )
    result = _run_local_command(
        [
            str(wrapper_path.resolve()),
            "init-plan-phase",
            "network-horistic-readdress",
            "54",
        ]
    )
    return bool(
        semantic_config
        and result
        and result[0] == 0
        and result[1].decode("utf-8", "replace").strip().lower() == "true"
    )


def _pytest_probe(test_path: pathlib.Path, selector: str) -> bool:
    result = _run_local_command(
        [
            str(pathlib.Path(sys.executable).resolve()),
            "-m",
            "pytest",
            "-q",
            str(test_path),
            "-k",
            selector,
        ],
        timeout=29,
    )
    return bool(result and result[0] == 0)


def _secret_scan_probe(
    runner_path: pathlib.Path,
    test_path: pathlib.Path,
    wrapper_path: pathlib.Path,
) -> bool:
    candidates = [
        runner_path,
        ADAPTER_PATH,
        wrapper_path,
    ]
    candidates.extend(sorted(PHASE_DIR.glob("54-*.json")))
    for path in candidates:
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        if any(pattern.search(raw) for pattern in SENSITIVE_VALUE_PATTERNS):
            return False
        if path.suffix == ".json":
            parsed = read_json(path)
            if parsed is None or _contains_secret(parsed):
                return False
    return bool(candidates)


def _graphify_probe(wrapper_path: pathlib.Path) -> bool:
    status = _run_local_command([str(wrapper_path.resolve()), "status"])
    query = _run_local_command(
        [
            str(wrapper_path.resolve()),
            "query",
            "phase54_network_gate",
        ]
    )
    if (
        not status
        or status[0] != 0
        or not query
        or query[0] != 0
        or not query[1].strip()
    ):
        return False
    query_text = query[1].decode("utf-8", "replace")
    try:
        query_value: Any = json.loads(query_text)
    except json.JSONDecodeError:
        query_value = query_text
    query_terms = " ".join(_value_strings(query_value)).lower()
    relevant_query = bool(
        "phase54" in re.sub(r"[^a-z0-9]+", "", query_terms)
        and any(
            term in query_terms for term in ("adapter", "network gate", "workstream")
        )
    )
    if not relevant_query:
        return False
    status_text = status[1].decode("utf-8", "replace")
    try:
        status_json = json.loads(status_text)
    except json.JSONDecodeError:
        normalized = re.sub(r"\s+", "", status_text.lower())
        graph_fresh = "stale:false" in normalized or "stale=false" in normalized
        commit_fresh = (
            "commit_stale:false" in normalized or "commit_stale=false" in normalized
        )
        return graph_fresh and commit_fresh

    stale_values: dict[str, list[bool]] = {"stale": [], "commit_stale": []}

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in stale_values and isinstance(item, bool):
                    stale_values[key].append(item)
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(status_json)
    return all(values and not any(values) for values in stale_values.values())


def run_local_probe(probe_id: str) -> int:
    runner_path = pathlib.Path(__file__).resolve()
    test_path = (
        REPO_ROOT / "modules/fleet-control-plane/tests/test_phase54_network_gate.py"
    )
    wrapper_path = REPO_ROOT / "scripts/graphify-sync.sh"
    passed = False
    if probe_id == "workstream_config_routing":
        passed = _workstream_routing_probe(wrapper_path)
    elif probe_id == "syntax_compile":
        try:
            compile(runner_path.read_text(encoding="utf-8"), str(runner_path), "exec")
            compile(test_path.read_text(encoding="utf-8"), str(test_path), "exec")
            compile(ADAPTER_PATH.read_text(encoding="utf-8"), str(ADAPTER_PATH), "exec")
            adapter_test = (
                REPO_ROOT
                / "modules/fleet-control-plane/tests/test_phase54_probe_adapters.py"
            )
            compile(
                adapter_test.read_text(encoding="utf-8"),
                str(adapter_test),
                "exec",
            )
            passed = True
        except (OSError, SyntaxError, UnicodeDecodeError):
            passed = False
    elif probe_id == "focused_pytest":
        passed = _pytest_probe(
            test_path,
            (
                "probe_registry_covers_every_required_tuple "
                "or run_fixed_argv_uses_exact_safe_subprocess_contract "
                "or plan_contract_uses_canonical_evidence"
            ),
        )
    elif probe_id == "adversarial_matrix":
        passed = _pytest_probe(
            test_path,
            (
                "check_inputs_reject "
                "or manually_fabricated_happy_path_blocks "
                "or remote_normalized_semantics "
                "or immediate_predecessor_requires_commit_pin"
            ),
        )
    elif probe_id == "secret_scan":
        passed = _secret_scan_probe(runner_path, test_path, wrapper_path)
    elif probe_id == "graphify_preflight":
        passed = wrapper_path.is_file() and _graphify_probe(wrapper_path)
    payload = {
        "schema": "phase54.check-observation.v1",
        "probe_id": probe_id,
        "status": "PASS" if passed else "BLOCK",
        "read_only": True,
        "mutation_performed": False,
        "secret_material_present": False,
        "request_id": f"local-{probe_id}",
        "observed_sha256": hashlib.sha256(
            f"local:{probe_id}:{passed}".encode()
        ).hexdigest(),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if passed else 2


def adapters_ready(args: argparse.Namespace) -> int:
    plan = args.plan
    coverage = _adapter_coverage_valid(plan)
    smoke_count = 0
    smoke_passed = not args.smoke
    if coverage and args.smoke:
        result = _run_local_command(
            [
                str(pathlib.Path(sys.executable).resolve()),
                str(ADAPTER_PATH.resolve()),
                "smoke",
                "--plan",
                plan,
            ],
            timeout=55,
        )
        payload: dict[str, Any] | None = None
        if result and result[0] == 0:
            try:
                parsed = json.loads(result[1].decode("utf-8"))
                payload = parsed if isinstance(parsed, dict) else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
        smoke_checks = payload.get("checks") if payload else None
        smoke_count = len(smoke_checks) if isinstance(smoke_checks, list) else 0
        smoke_passed = bool(
            payload
            and payload.get("schema") == "phase54.adapter-smoke.v1"
            and payload.get("plan") == plan
            and payload.get("status") == "PASS"
            and isinstance(smoke_checks, list)
            and smoke_checks
            and all(
                isinstance(item, dict) and item.get("status") == "PASS"
                for item in smoke_checks
            )
        )
    status = "PASS" if coverage and smoke_passed else "BLOCK"
    print(
        json.dumps(
            {
                "schema": "phase54.adapters-ready.v1",
                "plan": plan,
                "coverage": coverage,
                "smoke": bool(args.smoke),
                "smoke_count": smoke_count,
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    final_parser = subparsers.add_parser("final")
    _add_common_arguments(final_parser)
    final_parser.add_argument("--redact", action="store_true")
    assert_parser = subparsers.add_parser("assert-gate")
    _add_common_arguments(assert_parser)
    review_parser = subparsers.add_parser("assert-review-gate")
    review_parser.add_argument("--evidence", required=True)
    review_parser.add_argument("--gate", required=True)
    review_parser.add_argument(
        "--max-age-seconds",
        type=int,
        default=DEFAULT_MAX_AGE_SECONDS,
    )
    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("--probe-id", required=True)
    adapter_parser = subparsers.add_parser("adapters-ready")
    adapter_parser.add_argument("--plan", required=True, choices=PLAN_IDS[1:])
    adapter_parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    args.started_at = utc_now()
    if args.mode == "probe":
        return run_local_probe(args.probe_id)
    if args.mode == "adapters-ready":
        return adapters_ready(args)
    if args.mode == "assert-gate":
        return assert_gate(args)
    if args.mode == "assert-review-gate":
        return assert_review_gate(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
