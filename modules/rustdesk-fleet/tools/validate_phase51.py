#!/usr/bin/env python3
"""Fail-closed Phase 51 RustDesk contract validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_INCLUDED_HOSTS = (
    "atius-srv-1",
    "atius-srv-2",
    "atius-srv-3",
    "horistic-srv",
    "GIOVANNI-W11-PC",
)
EXPECTED_EXCLUDED_HOSTS = ("WSL", "GIOVANNI-S23")
EXPECTED_ACCESS_TOOLS = ("RustGuac", "XRDP", "AnyDesk", "NoMachine", "noVNC")
EXPECTED_RELAY_PURPOSES = ("controlled-validation", "proven-fallback")
EXPECTED_GSD_MUTATING_VERBS = (
    "begin-phase",
    "advance-plan",
    "update-progress",
    "complete-phase",
    "complete-milestone",
    "plan-phase",
    "execute-phase",
    "verify-work",
)
EXPECTED_SHARED_WRITER_PATHS = (
    ".planning/PROJECT.md",
    ".planning/MILESTONES.md",
    ".planning/graphs/graph.json",
    ".planning/graphs/GRAPH_REPORT.md",
    ".planning/graphs/manifest.json",
)
PHASE48_LEGACY_ROOT = ".planning/phases/48-codex-oauth-wayland-acp-convergence"
PHASE48_WORKSTREAM_ROOT = (
    ".planning/workstreams/runtime-trust-codex-delivery-convergence/"
    "phases/48-codex-oauth-wayland-acp-convergence"
)
PHASE48_FILES = (
    "48-01-PLAN.md",
    "48-01-ROUTER-EVIDENCE.md",
    "48-02-PLAN.md",
    "48-CONTEXT.md",
    "48-EXECUTION-CHECKPOINT-2026-07-12.md",
    "48-PATTERNS.md",
    "48-RESEARCH.md",
    "48-VALIDATION.md",
    "tools/verify-router-evidence.py",
)
PHASE48_EXCLUSIONS = ("__pycache__", "*.pyc", "*.swp", "*~")
ACCEPTANCE_KIND_BY_PHASE = {
    51: "governance-contract",
    52: "supply-chain-live",
    53: "server-edge-live",
    54: "canary-live",
    55: "fleet-rollout-live",
    56: "matrix-live",
    57: "resilience-live",
    58: "closeout-evidence",
}
FIXTURE_DOCUMENT_PATHS = {
    "scope": "contracts/scope.json",
    "product_decision": "contracts/product-decision.json",
    "threat_model": "contracts/threat-model.json",
    "permission_profiles": "contracts/permission-profiles.json",
    "secret_roles": "contracts/secret-roles.json",
    "ledger": "evidence/ledger.json",
    "phase48_baseline": "evidence/phase48-baseline.json",
    "operational_review": "evidence/operational-review.json",
}
CHECK_ORDER = (
    "P51-SCOPE-001",
    "P51-LEGACY-001",
    "P51-PRODUCT-001",
    "P51-TRANSPORT-001",
    "P51-SECRET-001",
    "P51-PERM-001",
    "P51-LEDGER-001",
    "P51-WS-001",
    "P51-P48-001",
    "P51-THREAT-001",
    "P51-REPORT-001",
)
PHASE51_DIR = (
    ".planning/workstreams/rustdesk-fleet/phases/"
    "51-contract-threat-model-and-workstream-isolation"
)
PRE_REPORT_INPUTS = (
    "modules/rustdesk-fleet/contracts/scope.json",
    "modules/rustdesk-fleet/contracts/product-decision.json",
    "modules/rustdesk-fleet/contracts/permission-profiles.json",
    "modules/rustdesk-fleet/contracts/threat-model.json",
    "modules/rustdesk-fleet/contracts/secret-roles.json",
    f"{PHASE51_DIR}/51-SECURITY.md",
    "modules/rustdesk-fleet/evidence/phase48-baseline.json",
    "modules/rustdesk-fleet/evidence/ledger.json",
)
REQUIREMENTS_RELATIVE_PATH = ".planning/workstreams/rustdesk-fleet/REQUIREMENTS.md"
REVIEW_RELATIVE_PATH = f"{PHASE51_DIR}/51-OPERATIONAL-REVIEW.md"
POST_REVIEW_ALLOWED_PATHS = (
    REVIEW_RELATIVE_PATH,
    f"{PHASE51_DIR}/51-CONTRACT-VALIDATION.json",
    f"{PHASE51_DIR}/51-CONTRACT-VALIDATION.md",
    f"{PHASE51_DIR}/51-03-SUMMARY.md",
    f"{PHASE51_DIR}/51-VERIFICATION.md",
    f"{PHASE51_DIR}/51-UAT.md",
    ".planning/workstreams/rustdesk-fleet/STATE.md",
)
REVIEW_NORMATIVE_PATHS = (
    "modules/rustdesk-fleet/tools/validate_phase51.py",
    f"{PHASE51_DIR}/51-03-PLAN.md",
    REQUIREMENTS_RELATIVE_PATH,
    ".planning/workstreams/rustdesk-fleet/ROADMAP.md",
)
VALIDATOR_VERSION = 2
ENTERPRISE_CONTROLS = (
    "sso_oidc",
    "rbac",
    "mfa",
    "central_api",
    "central_device_policy",
    "human_attributed_audit",
)
CAPABILITIES = (
    "screen_view",
    "keyboard_mouse",
    "clipboard",
    "file_transfer",
    "audio",
    "terminal",
    "tcp_tunnel",
    "remote_restart",
    "privacy_mode",
    "recording",
    "remote_config_modification",
)
EXPECTED_PERMISSION_PROFILES = {
    "admin-maintenance": {
        "screen_view": "allow",
        "keyboard_mouse": "allow",
        "clipboard": "allow",
        "file_transfer": "deny",
        "audio": "deny",
        "terminal": "allow",
        "tcp_tunnel": "deny",
        "remote_restart": "allow",
        "privacy_mode": "deny",
        "recording": "deny",
        "remote_config_modification": "deny",
    },
    "support-observe": {capability: "allow" if capability == "screen_view" else "deny" for capability in CAPABILITIES},
}
ASVS_L1 = (
    "v5.0.0-2.1.1",
    "v5.0.0-2.2.1",
    "v5.0.0-2.2.2",
    "v5.0.0-2.3.1",
    "v5.0.0-6.1.1",
    "v5.0.0-6.3.1",
    "v5.0.0-8.1.1",
    "v5.0.0-8.2.1",
    "v5.0.0-8.2.2",
    "v5.0.0-8.3.1",
    "v5.0.0-11.4.1",
    "v5.0.0-15.3.1",
)
ASVS_L2_V16 = (
    "v5.0.0-16.1.1",
    "v5.0.0-16.2.5",
    "v5.0.0-16.3.3",
    "v5.0.0-16.4.2",
    "v5.0.0-16.5.1",
    "v5.0.0-16.5.3",
)
TARGET_SECRET_PATHS = (
    "kv/atius/rustdesk/targets/atius-srv-1",
    "kv/atius/rustdesk/targets/atius-srv-2",
    "kv/atius/rustdesk/targets/atius-srv-3",
    "kv/atius/rustdesk/targets/horistic-srv",
    "kv/atius/rustdesk/targets/giovanni-w11-pc",
)
EXPECTED_VAULT_REVIEW_PATHS = (
    "kv/atius/rustdesk/server",
    *TARGET_SECRET_PATHS,
)
SECRET_PATTERNS = (
    ("private-key-header", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", re.I)),
    ("bearer-token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}", re.I)),
    (
        "secret-assignment",
        re.compile(r"\b(?:password|passwd|secret|token|private[_-]?key)\b\s*[:=]\s*[^\s,;]{6,}", re.I),
    ),
    ("uri-credential", re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.I)),
    ("argv-transcript", re.compile(r"\b(?:argv|command|process)\b[^\n]*(?:--password|--token|--secret)", re.I)),
    ("screenshot-redaction", re.compile(r"screenshot[_-]redaction[_-]status\s*[:=]\s*(?:failed|missing|unsafe)", re.I)),
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


def _result(check_id: str, passed: bool, categories: list[str], source: str) -> CheckResult:
    findings = [Finding(category, source, "contract") for category in categories]
    return CheckResult(
        id=check_id,
        status="PASS" if passed else "FAIL",
        evidence_ids=[f"P51-EV-{check_id.removeprefix('P51-').removesuffix('-001') }"],
        findings=findings,
    )


def _is_exact_string_list(value: Any, expected: tuple[str, ...]) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and tuple(value) == expected
        and len(set(value)) == len(value)
    )


def validate_scope(payload: dict[str, Any], source: str = "scope.json") -> list[CheckResult]:
    if not isinstance(payload, dict):
        return [
            _result("P51-SCOPE-001", False, ["invalid-shape"], source),
            _result("P51-LEGACY-001", False, ["invalid-shape"], source),
            _result("P51-TRANSPORT-001", False, ["invalid-shape"], source),
            _result("P51-WS-001", False, ["invalid-shape"], source),
        ]

    scope_errors: list[str] = []
    included = payload.get("included_hosts")
    excluded = payload.get("excluded_hosts")
    if payload.get("schema_version") != 1 or payload.get("workstream") != "rustdesk-fleet":
        scope_errors.append("invalid-schema")
    if not _is_exact_string_list(included, EXPECTED_INCLUDED_HOSTS):
        scope_errors.append("included-host-set")
    if not _is_exact_string_list(excluded, EXPECTED_EXCLUDED_HOSTS):
        scope_errors.append("excluded-host-set")
    if isinstance(included, list) and isinstance(excluded, list) and set(included) & set(excluded):
        scope_errors.append("host-set-overlap")

    legacy_errors: list[str] = []
    tools = payload.get("preserved_access_tools")
    if not isinstance(tools, list) or len(tools) != len(EXPECTED_ACCESS_TOOLS):
        legacy_errors.append("preserved-tool-cardinality")
    else:
        ids: list[str] = []
        for tool in tools:
            if not isinstance(tool, dict):
                legacy_errors.append("preserved-tool-shape")
                continue
            tool_id = tool.get("id")
            if isinstance(tool_id, str):
                ids.append(tool_id)
            if tool.get("action") != "preserve" or tool.get("independently_usable") is not True:
                legacy_errors.append("preserved-tool-policy")
        if tuple(ids) != EXPECTED_ACCESS_TOOLS or len(set(ids)) != len(ids):
            legacy_errors.append("preserved-tool-set")

    transport_errors: list[str] = []
    transport = payload.get("production_transport")
    if not isinstance(transport, dict):
        transport_errors.append("transport-shape")
    else:
        if transport.get("policy") != "direct-first":
            transport_errors.append("transport-policy")
        if transport.get("force_relay_default") is not False:
            transport_errors.append("forced-relay-default")
        purposes = transport.get("forced_relay_allowed_purposes")
        if not _is_exact_string_list(purposes, EXPECTED_RELAY_PURPOSES):
            transport_errors.append("forced-relay-purpose-set")

    return [
        _result("P51-SCOPE-001", not scope_errors, scope_errors, source),
        _result("P51-LEGACY-001", not legacy_errors, legacy_errors, source),
        _result("P51-TRANSPORT-001", not transport_errors, transport_errors, source),
        validate_workstream_policy(payload, source),
    ]


def extract_executable_gsd_commands(text: str, source_kind: str = "script") -> list[str]:
    """Extract shell commands without treating surrounding prose as executable."""
    if source_kind == "markdown":
        regions = re.findall(r"```(?:bash|sh|shell|zsh)\s*\n(.*?)```", text, flags=re.I | re.S)
    elif source_kind == "script":
        regions = [text]
    else:
        raise ValueError("unsupported command source kind")

    commands: list[str] = []
    for region in regions:
        logical = ""
        for raw_line in region.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            logical = f"{logical} {line}".strip()
            if logical.endswith("\\"):
                logical = logical[:-1].rstrip()
                continue
            for part in re.split(r"\s*(?:&&|\|\||;)\s*", logical):
                if part:
                    commands.append(part)
            logical = ""
        if logical:
            commands.append(logical)
    return commands


def validate_workstream_commands(
    commands: list[str],
    mutating_verbs: list[str] | tuple[str, ...] = EXPECTED_GSD_MUTATING_VERBS,
    source: str = "executable-command",
) -> list[CheckResult]:
    """Validate every command independently; read-only commands do not mutate a lane."""
    results: list[CheckResult] = []
    for index, command in enumerate(commands):
        try:
            tokens = shlex.split(command, comments=True, posix=True)
        except ValueError:
            results.append(_result("P51-WS-001", False, ["invalid-shell-command"], source))
            continue
        is_mutating = any(verb in tokens for verb in mutating_verbs)
        if not is_mutating:
            results.append(_result("P51-WS-001", True, [], source))
            continue
        scoped_values = [tokens[pos + 1] for pos, token in enumerate(tokens[:-1]) if token == "--ws"]
        if scoped_values == ["rustdesk-fleet"]:
            results.append(_result("P51-WS-001", True, [], source))
            continue
        category = "wrong-explicit-workstream" if scoped_values else "missing-explicit-workstream"
        results.append(
            CheckResult(
                id="P51-WS-001",
                status="FAIL",
                evidence_ids=["P51-EV-WS"],
                findings=[Finding(category, source, f"command[{index}]")],
            )
        )
    return results


def validate_workstream_policy(payload: dict[str, Any], source: str = "scope.json") -> CheckResult:
    errors: list[str] = []
    lifecycle = payload.get("gsd_lifecycle")
    if not isinstance(lifecycle, dict):
        errors.append("lifecycle-policy-shape")
    else:
        if lifecycle.get("required_workstream") != "rustdesk-fleet" or lifecycle.get("required_flag") != "--ws":
            errors.append("lifecycle-explicit-scope")
        if not _is_exact_string_list(lifecycle.get("mutating_verbs"), EXPECTED_GSD_MUTATING_VERBS):
            errors.append("lifecycle-mutating-verbs")
        if not _is_exact_string_list(lifecycle.get("command_sources"), ("fenced-shell", "script")):
            errors.append("lifecycle-command-sources")
    writers = payload.get("shared_writers")
    if not isinstance(writers, dict) or writers.get("mode") != "serialized-single-writer" or not _is_exact_string_list(
        writers.get("paths"), EXPECTED_SHARED_WRITER_PATHS
    ):
        errors.append("shared-writer-policy")
    gates = payload.get("transition_gates")
    if not isinstance(gates, dict) or gates.get("precheck_ids") != ["P51-WS-001"] or gates.get(
        "postcheck_ids"
    ) != ["P51-P48-001"]:
        errors.append("transition-gate-policy")
    return _result("P51-WS-001", not errors, errors, source)


def resolve_legacy_blob(repo: Path, source_head: str, legacy_git_path: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", source_head):
        return ""
    if not legacy_git_path.startswith(f"{PHASE48_LEGACY_ROOT}/"):
        return ""
    completed = subprocess.run(
        ["git", "rev-parse", f"{source_head}:{legacy_git_path}"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else ""


def _phase48_visible_files(root: Path) -> set[str]:
    visible: set[str] = set()
    if not root.is_dir():
        return visible
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".swp"} or path.name.endswith("~"):
            continue
        visible.add(relative.as_posix())
    return visible


def validate_phase48_baseline(
    payload: dict[str, Any],
    repo: Path,
    source: str = "phase48-baseline.json",
    workstream_root: Path | None = None,
) -> CheckResult:
    errors: list[str] = []
    if not isinstance(payload, dict):
        errors.append("invalid-shape")
        payload = {}
    if payload.get("schema_version") != 1:
        errors.append("invalid-schema")
    if payload.get("source_phase") != PHASE48_LEGACY_ROOT or payload.get("migrated_phase") != PHASE48_WORKSTREAM_ROOT:
        errors.append("phase-root-mismatch")
    if payload.get("allowed_exclusions") != list(PHASE48_EXCLUSIONS):
        errors.append("invalid-exclusions")
    if payload.get("rebaseline_policy") != "explicit-serialized-review-only":
        errors.append("unsafe-rebaseline-policy")
    source_head = payload.get("source_head")
    if not isinstance(source_head, str) or not re.fullmatch(r"[0-9a-f]{40}", source_head):
        errors.append("invalid-source-head")
        source_head = ""
    rows = payload.get("files")
    if payload.get("file_count") != 9 or not isinstance(rows, list) or len(rows) != 9:
        errors.append("baseline-row-count")
        rows = rows if isinstance(rows, list) else []

    canonical_legacy = [f"{PHASE48_LEGACY_ROOT}/{relative}" for relative in PHASE48_FILES]
    canonical_current = [f"{PHASE48_WORKSTREAM_ROOT}/{relative}" for relative in PHASE48_FILES]
    observed_legacy = [item.get("legacy_git_path") for item in rows if isinstance(item, dict)]
    observed_current = [item.get("workstream_path") for item in rows if isinstance(item, dict)]
    if observed_legacy != canonical_legacy or len(set(observed_legacy)) != len(observed_legacy):
        errors.append("legacy-path-set")
    if observed_current != canonical_current or len(set(observed_current)) != len(observed_current):
        errors.append("workstream-path-set")

    current_root = (workstream_root or (repo / PHASE48_WORKSTREAM_ROOT)).resolve()
    if _phase48_visible_files(current_root) != set(PHASE48_FILES):
        errors.append("workstream-file-set-drift")
    for row in rows:
        if not isinstance(row, dict):
            errors.append("baseline-row-shape")
            continue
        legacy_path = row.get("legacy_git_path")
        current_path = row.get("workstream_path")
        expected_blob = row.get("legacy_blob_id")
        expected_sha = row.get("workstream_sha256")
        if not all(isinstance(value, str) and value for value in (legacy_path, current_path, expected_blob, expected_sha)):
            errors.append("baseline-row-shape")
            continue
        if not re.fullmatch(r"[0-9a-f]{40}", expected_blob) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            errors.append("baseline-digest-shape")
            continue
        if resolve_legacy_blob(repo, source_head, legacy_path) != expected_blob:
            errors.append("legacy-blob-drift")
        try:
            relative = Path(current_path).relative_to(PHASE48_WORKSTREAM_ROOT)
            actual_path = (current_root / relative).resolve(strict=True)
            if not actual_path.is_relative_to(current_root) or _sha256_file(actual_path) != expected_sha:
                errors.append("workstream-sha256-drift")
        except (OSError, ValueError):
            errors.append("workstream-file-missing")
    if not errors:
        return _result("P51-P48-001", True, [], source)
    return CheckResult(
        id="P51-P48-001",
        status="BLOCKED",
        evidence_ids=["P51-EV-P48"],
        findings=[Finding(category, source, "manifest") for category in sorted(set(errors))],
    )


def parse_canonical_requirements(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    requirements_section = text.split("## v1.9 Requirements", 1)[1].split("## Future Requirements", 1)[0]
    defined = re.findall(r"^- \[[ xX]\] \*\*([A-Z]+-\d+)\*\*:", requirements_section, flags=re.M)
    traceability_section = text.split("## Traceability", 1)[1]
    traced = re.findall(r"^\| ([A-Z]+-\d+) \| Phase (\d+) \|", traceability_section, flags=re.M)
    traced_ids = [requirement_id for requirement_id, _ in traced]
    if len(defined) != 36 or len(set(defined)) != 36 or defined != traced_ids:
        raise ValueError("canonical requirement definitions and traceability differ")
    return {requirement_id: int(phase) for requirement_id, phase in traced}


def _ledger_blocked(categories: list[str], source: str) -> CheckResult:
    return CheckResult(
        id="P51-LEDGER-001",
        status="BLOCKED",
        evidence_ids=["P51-EV-LEDGER"],
        findings=[Finding(category, source, "requirements") for category in sorted(set(categories))],
    )


def validate_ledger(
    payload: dict[str, Any], canonical: dict[str, int], repo: Path, source: str = "ledger.json"
) -> CheckResult:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return _ledger_blocked(["invalid-shape"], source)
    if payload.get("schema_version") != 1 or payload.get("milestone") != "v1.9":
        errors.append("ledger-schema")
    rows = payload.get("requirements")
    if payload.get("requirement_count") != 36 or not isinstance(rows, list) or len(rows) != 36:
        errors.append("ledger-row-count")
        rows = rows if isinstance(rows, list) else []
    observed_ids = [row.get("requirement_id") for row in rows if isinstance(row, dict)]
    if observed_ids != list(canonical) or len(set(observed_ids)) != len(observed_ids):
        errors.append("ledger-requirement-set")
    catalog = payload.get("evidence_catalog")
    if not isinstance(catalog, dict):
        errors.append("evidence-catalog-shape")
        catalog = {}
    all_evidence_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append("ledger-row-shape")
            continue
        requirement_id = row.get("requirement_id")
        expected_phase = canonical.get(requirement_id)
        if row.get("owner_phase") != expected_phase:
            errors.append("owner-phase-mismatch")
        if row.get("acceptance_kind") != ACCEPTANCE_KIND_BY_PHASE.get(expected_phase):
            errors.append("acceptance-kind-mismatch")
        status = row.get("status")
        if status not in {"pending", "pass", "blocked", "fail"}:
            errors.append("invalid-requirement-status")
        evidence_ids = row.get("evidence_ids")
        if not isinstance(evidence_ids, list) or len(evidence_ids) != 1 or not all(
            isinstance(item, str) and re.fullmatch(r"RDF-V19-[A-Z]+-\d+", item) for item in evidence_ids
        ):
            errors.append("evidence-id-shape")
            evidence_ids = []
        all_evidence_ids.extend(evidence_ids)
        last_verified_at = row.get("last_verified_at")
        if status == "pending":
            if last_verified_at is not None:
                errors.append("pending-has-currentness")
            continue
        if status != "pass":
            continue
        if not isinstance(last_verified_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", last_verified_at):
            errors.append("last-verified-at")
        for evidence_id in evidence_ids:
            evidence = catalog.get(evidence_id)
            if not isinstance(evidence, dict):
                errors.append("unresolved-evidence-id")
                continue
            evidence_path = evidence.get("path")
            digest = evidence.get("sha256")
            input_digest = evidence.get("input_digest")
            observed_at = evidence.get("observed_at")
            if not isinstance(evidence_path, str):
                errors.append("evidence-path-shape")
                continue
            candidate = Path(evidence_path)
            allowed_prefix = evidence_path.startswith("modules/rustdesk-fleet/") or evidence_path.startswith(
                ".planning/workstreams/rustdesk-fleet/"
            )
            if candidate.is_absolute() or ".." in candidate.parts or not allowed_prefix:
                errors.append("evidence-path-outside-scope")
            if candidate.name.upper().endswith("SUMMARY.MD"):
                errors.append("summary-only-evidence")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or not isinstance(
                input_digest, str
            ) or not re.fullmatch(r"[0-9a-f]{64}", input_digest):
                errors.append("evidence-digest-shape")
            if observed_at != last_verified_at:
                errors.append("evidence-currentness")
    if len(set(all_evidence_ids)) != len(all_evidence_ids):
        errors.append("duplicate-evidence-id")
    orphan_catalog_ids = set(catalog) - set(all_evidence_ids)
    if orphan_catalog_ids:
        errors.append("orphan-evidence-catalog-entry")
    return _result("P51-LEDGER-001", True, [], source) if not errors else _ledger_blocked(errors, source)


def materialize_fixture_bundle(bundle: dict[str, Any], destination: Path) -> dict[str, Path]:
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        raise ValueError("invalid fixture bundle")
    documents = bundle.get("documents")
    if not isinstance(documents, dict) or set(documents) != set(FIXTURE_DOCUMENT_PATHS):
        raise ValueError("fixture bundle document set mismatch")
    root = destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, relative in FIXTURE_DOCUMENT_PATHS.items():
        document = documents[name]
        if not isinstance(document, dict):
            raise ValueError("fixture document must be an object")
        target = (root / relative).resolve(strict=False)
        if not target.is_relative_to(root):
            raise ValueError("fixture path escape")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written[name] = target
    return written


def load_structural_fixture(path: Path, repo: Path) -> dict[str, Any]:
    descriptor = load_json_strict(path)
    kind = descriptor.get("kind") if isinstance(descriptor, dict) else None
    if kind == "missing-legacy-tool":
        payload = load_json_strict(repo / "modules/rustdesk-fleet/contracts/scope.json")
        payload["preserved_access_tools"] = [
            item for item in payload["preserved_access_tools"] if item.get("id") != "noVNC"
        ]
        return payload
    if kind == "duplicate-secret-ref":
        payload = load_json_strict(repo / "modules/rustdesk-fleet/contracts/secret-roles.json")
        payload["target_password_roles"][1]["vault_path"] = payload["target_password_roles"][0]["vault_path"]
        return payload
    if kind == "summary-only-ledger":
        payload = load_json_strict(repo / "modules/rustdesk-fleet/evidence/ledger.json")
        requirement_id = descriptor.get("requirement_id")
        row = next(
            (item for item in payload["requirements"] if item.get("requirement_id") == requirement_id),
            None,
        )
        if row is None or descriptor.get("status") != "pass" or not isinstance(descriptor.get("evidence"), dict):
            raise ValueError("invalid summary-only ledger fixture")
        row["status"] = "pass"
        row["last_verified_at"] = descriptor.get("last_verified_at")
        payload["evidence_catalog"][row["evidence_ids"][0]] = descriptor["evidence"]
        return payload
    raise ValueError("unsupported structural fixture")


def derive_product_decision(payload: dict[str, Any]) -> dict[str, str | None]:
    controls = payload.get("enterprise_controls")
    if not isinstance(controls, list):
        return {"decision": "BLOCKED", "required_edition": None}
    if any(isinstance(item, dict) and item.get("mandatory") is True for item in controls):
        return {"decision": "NO-GO", "required_edition": "pro"}
    reviewed_acceptance = (
        payload.get("operator_scope") == "single-operator"
        and len(controls) == len(ENTERPRISE_CONTROLS)
        and all(
            isinstance(item, dict)
            and item.get("review_status") == "reviewed"
            and item.get("accepted_absence") is True
            for item in controls
        )
    )
    if reviewed_acceptance:
        return {"decision": "GO", "required_edition": "oss"}
    return {"decision": "BLOCKED", "required_edition": None}


def validate_product_decision(
    payload: dict[str, Any], source: str = "product-decision.json"
) -> CheckResult:
    errors: list[str] = []
    controls = payload.get("enterprise_controls")
    if payload.get("schema_version") != 1 or payload.get("operator_scope") != "single-operator":
        errors.append("product-shape")
    if not isinstance(controls, list) or [item.get("id") for item in controls if isinstance(item, dict)] != list(
        ENTERPRISE_CONTROLS
    ):
        errors.append("enterprise-control-set")
    elif any(
        not isinstance(item.get("mandatory"), bool)
        or item.get("review_status") not in {"pending", "reviewed"}
        or not isinstance(item.get("accepted_absence"), bool)
        or not isinstance(item.get("source"), str)
        or not item.get("source")
        for item in controls
    ):
        errors.append("enterprise-control-shape")
    if payload.get("custom_ops_api") != {
        "status": "approved-to-plan-and-implement",
        "kind": "atius-ops-api",
        "rustdesk_native_api": False,
        "configure_client_api_server": False,
        "rustdesk_api_port_21114": "closed",
        "phase": 53,
        "requirement_id": "OPS-01",
    }:
        errors.append("custom-ops-api-boundary")
    derived = derive_product_decision(payload)
    if payload.get("declared_decision") != derived["decision"]:
        errors.append("declared-derived-mismatch")
    if payload.get("derived_decision") != derived["decision"]:
        errors.append("stored-derived-mismatch")
    if payload.get("required_edition") != derived["required_edition"]:
        errors.append("required-edition-mismatch")
    if errors:
        return _result("P51-PRODUCT-001", False, errors, source)
    if derived["decision"] == "BLOCKED":
        return CheckResult(
            id="P51-PRODUCT-001",
            status="BLOCKED",
            evidence_ids=["P51-EV-PRODUCT"],
            findings=[Finding("accountable-review-pending", source, "enterprise_controls")],
        )
    return _result("P51-PRODUCT-001", True, [], source)


def validate_permission_profiles(
    payload: dict[str, Any], source: str = "permission-profiles.json"
) -> CheckResult:
    errors: list[str] = []
    profiles = payload.get("profiles")
    if payload.get("schema_version") != 1 or payload.get("enforcement_model") != "desired-local-policy-with-verified-compensating-controls":
        errors.append("permission-shape")
    if not isinstance(profiles, list) or len(profiles) != 2:
        errors.append("profile-cardinality")
    else:
        observed = {
            item.get("id"): item.get("capabilities")
            for item in profiles
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if observed != EXPECTED_PERMISSION_PROFILES:
            errors.append("capability-matrix")
    controls = payload.get("compensating_controls")
    if not isinstance(controls, list) or not {
        "per-client-config-verification",
        "negative-capability-tests",
        "single-operator-accountability",
    }.issubset(set(controls)):
        errors.append("compensating-controls")
    if payload.get("centralized_rbac_claimed") is not False:
        errors.append("oss-rbac-overclaim")
    return _result("P51-PERM-001", not errors, errors, source)


def validate_threat_model(payload: dict[str, Any], source: str = "threat-model.json") -> CheckResult:
    errors: list[str] = []
    blocked: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("blocking_threshold") != "high":
        errors.append("threat-model-shape")
    if tuple(payload.get("asvs_baseline", [])) != ASVS_L1:
        errors.append("asvs-l1-set")
    if tuple(payload.get("risk_based_l2_subset", [])) != ASVS_L2_V16:
        errors.append("asvs-v16-l2-set")
    threats = payload.get("threats")
    if not isinstance(threats, list) or [item.get("id") for item in threats if isinstance(item, dict)] != [
        f"T-{number:02d}" for number in range(1, 13)
    ]:
        errors.append("threat-id-set")
    else:
        for item in threats:
            if not isinstance(item, dict):
                errors.append("threat-shape")
                continue
            required_text = ("stride", "severity", "status", "disposition", "owner", "mitigation")
            if any(not isinstance(item.get(key), str) or not item.get(key) for key in required_text):
                errors.append("threat-required-field")
                continue
            if not isinstance(item.get("evidence_ids"), list) or not item["evidence_ids"]:
                errors.append("threat-evidence")
            if not isinstance(item.get("asvs_ids"), list) or not item["asvs_ids"]:
                errors.append("threat-asvs")
            if item["severity"] == "high" and item["status"] not in {"mitigated", "resolved"}:
                blocked.append("unresolved-high")
            if item["severity"] == "medium" and (
                not item["owner"] or not item["mitigation"] or not item.get("evidence_ids")
            ):
                blocked.append("unowned-medium")
    if errors:
        return _result("P51-THREAT-001", False, sorted(set(errors)), source)
    if blocked:
        return CheckResult(
            id="P51-THREAT-001",
            status="BLOCKED",
            evidence_ids=["P51-EV-THREAT"],
            findings=[Finding(category, source, "threats") for category in sorted(set(blocked))],
        )
    return _result("P51-THREAT-001", True, [], source)


def validate_secret_roles(payload: dict[str, Any], source: str = "secret-roles.json") -> CheckResult:
    errors: list[str] = []
    approvals: list[str] = []
    if payload.get("schema_version") != 1 or payload.get("authority") != "hashicorp-vault":
        errors.append("secret-role-shape")
    server = payload.get("server_identity")
    if not isinstance(server, dict):
        errors.append("server-identity-shape")
    else:
        private_ref = server.get("private_key_ref")
        public_ref = server.get("public_key_ref")
        expected = {
            "private_key_ref": (private_ref, "server-identity-private", "private_key"),
            "public_key_ref": (public_ref, "server-identity-public", "public_key"),
        }
        for _, (reference, role, field_name) in expected.items():
            if not isinstance(reference, dict) or reference != {
                "role": role,
                "vault_path": "kv/atius/rustdesk/server",
                "field": field_name,
            }:
                errors.append("server-identity-reference")
        if server.get("approval_status") not in {"pending", "approved"}:
            errors.append("server-identity-approval")
        else:
            approvals.append(server["approval_status"])

    roles = payload.get("target_password_roles")
    if not isinstance(roles, list) or len(roles) != 5:
        errors.append("target-role-cardinality")
    else:
        observed_hosts = tuple(item.get("host") for item in roles if isinstance(item, dict))
        observed_paths = tuple(item.get("vault_path") for item in roles if isinstance(item, dict))
        observed_roles = tuple(item.get("role") for item in roles if isinstance(item, dict))
        if observed_hosts != EXPECTED_INCLUDED_HOSTS:
            errors.append("target-role-host-set")
        if observed_paths != TARGET_SECRET_PATHS or len(set(observed_paths)) != 5:
            errors.append("target-vault-reference-set")
        if len(observed_roles) != 5 or len(set(observed_roles)) != 5:
            errors.append("target-role-set")
        for item in roles:
            if not isinstance(item, dict) or item.get("field") != "permanent_password" or item.get(
                "approval_status"
            ) not in {"pending", "approved"}:
                errors.append("target-role-shape")
            elif isinstance(item, dict):
                approvals.append(item["approval_status"])
    if payload.get("value_distinctness_phase") != 52:
        errors.append("value-distinctness-phase")
    recovery = payload.get("recovery_authority")
    if not isinstance(recovery, dict) or recovery.get("role") != "rustdesk-recovery-owner" or recovery.get(
        "approval_status"
    ) not in {"pending", "approved"}:
        errors.append("recovery-authority")
    elif isinstance(recovery, dict):
        approvals.append(recovery["approval_status"])
    if payload.get("client_identity_inventory_ref") != "modules/rustdesk-fleet/evidence/client-identities.json":
        errors.append("client-identity-role")
    if payload.get("permission_profiles_ref") != "modules/rustdesk-fleet/contracts/permission-profiles.json":
        errors.append("permission-profile-role")
    findings = scan_secret_material(payload, path=source)
    if findings:
        errors.append("secret-material")
    result = _result("P51-SECRET-001", not errors, sorted(set(errors)), source)
    if findings:
        result.findings.extend(findings)
    if not errors and approvals and set(approvals) != {"approved"}:
        return CheckResult(
            id="P51-SECRET-001",
            status="BLOCKED",
            evidence_ids=["P51-EV-SECRET"],
            findings=[Finding("vault-owner-review-pending", source, "approval_status")],
        )
    return result


def scan_secret_material(value: Any, path: str = "contract", location: str = "root") -> list[Finding]:
    """Return category/path/location only; never retain or echo matched material."""
    findings: list[Finding] = []

    def add(category: str, field_location: str) -> None:
        finding = Finding(category, path, field_location)
        if finding not in findings:
            findings.append(finding)

    def visit(node: Any, field_location: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                child_location = f"{field_location}.{key}"
                lowered = key.lower()
                if isinstance(child, str) and any(term in lowered for term in ("password", "secret", "token")):
                    safe_reference = lowered.endswith("_ref") or lowered in {
                        "role",
                        "vault_path",
                        "field",
                        "approval_status",
                    }
                    if not safe_reference and child:
                        add("sensitive-field-value", child_location)
                visit(child, child_location)
            return
        if isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{field_location}[{index}]")
            return
        if not isinstance(node, str):
            return
        for category, pattern in SECRET_PATTERNS:
            if pattern.search(node):
                add(category, field_location)
        compact = re.sub(r"[^A-Za-z0-9+/=_-]", "", node)
        field_name = field_location.rsplit(".", maxsplit=1)[-1]
        named_sha256 = (
            field_name
            in {
                "sha256",
                "input_digest",
                "review_input_manifest_digest",
            }
            and re.fullmatch(r"[0-9a-f]{64}", node) is not None
        )
        if (
            len(compact) >= 48
            and len(set(compact)) >= 16
            and not node.startswith(("kv/", "modules/", ".planning/"))
            and not named_sha256
        ):
            add("high-entropy", field_location)

    visit(value, location)
    return findings


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True, capture_output=True, check=False
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("unable to resolve repository HEAD")
    return value


def git_commit_exists(repo: Path, commit: object) -> bool:
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        return False
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def git_is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def git_changed_paths(repo: Path, source_head: str, current_head: str) -> set[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", source_head, current_head, "--"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("unable to resolve post-review changes")
    return {line for line in completed.stdout.splitlines() if line}


def git_has_worktree_changes(repo: Path, paths: tuple[str, ...]) -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("unable to inspect review authority worktree")
    return bool(completed.stdout.strip())


def collect_input_digests(repo: Path, paths: list[Path] | tuple[Path, ...]) -> list[dict[str, str]]:
    root = repo.resolve()
    inputs: list[dict[str, str]] = []
    for path in paths:
        candidate = path if path.is_absolute() else root / path
        resolved = validate_repo_path(root, candidate)
        if not resolved.is_file():
            raise ValueError("report input is missing")
        inputs.append({"path": resolved.relative_to(root).as_posix(), "sha256": _sha256_file(resolved)})
    return sorted(inputs, key=lambda item: item["path"])


def collect_git_input_digests(
    repo: Path, source_head: str, paths: list[Path] | tuple[Path, ...]
) -> list[dict[str, str]]:
    if not git_commit_exists(repo, source_head):
        raise ValueError("review source HEAD is not a commit")
    inputs: list[dict[str, str]] = []
    for path in paths:
        relative = path.as_posix()
        if path.is_absolute() or relative.startswith("../") or "/../" in relative:
            raise ValueError("review input path escapes repository")
        completed = subprocess.run(
            ["git", "show", f"{source_head}:{relative}"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError("review input is absent from source HEAD")
        inputs.append({"path": relative, "sha256": hashlib.sha256(completed.stdout).hexdigest()})
    return sorted(inputs, key=lambda item: item["path"])


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_review_input_manifest(repo: Path, source_head: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": 51,
        "workstream": "rustdesk-fleet",
        "validator_version": VALIDATOR_VERSION,
        "source_head": source_head,
        "inputs": collect_git_input_digests(
            repo, source_head, tuple(Path(item) for item in PRE_REPORT_INPUTS)
        ),
    }


def is_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ):
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def validate_review_source(
    repo: Path, source_head: object, manifest: dict[str, Any]
) -> list[str]:
    categories: list[str] = []
    if not git_commit_exists(repo, source_head):
        return ["invalid-review-source-head"]
    assert isinstance(source_head, str)
    current_head = git_head(repo)
    if not git_is_ancestor(repo, source_head, current_head):
        return ["review-source-not-ancestor"]
    try:
        pinned_manifest = build_review_input_manifest(repo, source_head)
        if manifest != pinned_manifest:
            categories.append("review-manifest-source-mismatch")
        current_inputs = collect_input_digests(
            repo, tuple(Path(item) for item in PRE_REPORT_INPUTS)
        )
        if current_inputs != pinned_manifest["inputs"]:
            categories.append("reviewed-input-drift")
        changed_paths = git_changed_paths(repo, source_head, current_head)
        if changed_paths - set(POST_REVIEW_ALLOWED_PATHS):
            categories.append("post-review-scope-drift")
        if git_has_worktree_changes(repo, REVIEW_NORMATIVE_PATHS):
            categories.append("uncommitted-review-authority-drift")
    except ValueError:
        categories.append("review-source-unreadable")
    return sorted(set(categories))


def load_operational_review(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```json\s*\n(.*?)\n```", text, flags=re.S | re.I)
    if not match:
        raise ValueError("operational review JSON block missing")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate operational review key")
            result[key] = value
        return result

    return json.loads(match.group(1), object_pairs_hook=reject_duplicates)


def _blocked_result(check_id: str, categories: list[str], source: str, location: str) -> CheckResult:
    return CheckResult(
        id=check_id,
        status="BLOCKED",
        evidence_ids=[f"P51-EV-{check_id.removeprefix('P51-').removesuffix('-001')}"],
        findings=[Finding(category, source, location) for category in sorted(set(categories))],
    )


def validate_operational_review(
    review: dict[str, Any], repo: Path, manifest: dict[str, Any], source: str = REVIEW_RELATIVE_PATH
) -> CheckResult:
    blocked: list[str] = []
    if not isinstance(review, dict) or review.get("schema_version") != 1:
        return _blocked_result("P51-REPORT-001", ["operational-review-shape"], source, "review")
    reviewer = review.get("reviewer")
    reviewed_at = review.get("reviewed_at")
    controls = review.get("enterprise_controls")
    operator_ready = (
        review.get("status") == "APPROVED"
        and isinstance(reviewer, str)
        and bool(reviewer.strip())
        and is_utc_timestamp(reviewed_at)
        and isinstance(controls, list)
        and [item.get("id") for item in controls if isinstance(item, dict)] == list(ENTERPRISE_CONTROLS)
        and all(
            isinstance(item, dict)
            and isinstance(item.get("mandatory"), bool)
            and isinstance(item.get("accepted_absence"), bool)
            for item in controls or []
        )
    )
    if not operator_ready:
        blocked.append("operator-review-pending")
    blocked.extend(validate_review_source(repo, review.get("source_head"), manifest))

    product = load_json_strict(repo / "modules/rustdesk-fleet/contracts/product-decision.json")
    product_result = validate_product_decision(product)
    product_controls = product.get("enterprise_controls", []) if isinstance(product, dict) else []
    review_by_id = {item.get("id"): item for item in controls or [] if isinstance(item, dict)}
    if operator_ready and any(
        review_by_id.get(item.get("id"), {}).get("mandatory") != item.get("mandatory")
        or review_by_id.get(item.get("id"), {}).get("accepted_absence") != item.get("accepted_absence")
        for item in product_controls
        if isinstance(item, dict)
    ):
        blocked.append("product-review-contract-mismatch")
    derived = derive_product_decision(product) if isinstance(product, dict) else {"decision": "BLOCKED"}
    selection = review.get("oss_absence_acceptance_or_pro_selection")
    if derived.get("decision") == "GO" and selection != "accept-oss-absences":
        blocked.append("oss-absence-acceptance-missing")
    elif derived.get("decision") == "NO-GO" and (
        selection != "select-pro" or review.get("pro_replan_authorized") is not True
    ):
        blocked.append("product-no-go-without-replan")
    elif product_result.status != "PASS":
        blocked.append("product-decision-not-approved")

    vault_ready = (
        isinstance(review.get("vault_owner"), str)
        and bool(review["vault_owner"].strip())
        and review.get("vault_paths_reviewed") == list(EXPECTED_VAULT_REVIEW_PATHS)
        and review.get("vault_paths_approval_status") == "approved"
        and is_utc_timestamp(review.get("vault_paths_approved_at"))
    )
    secret_result = validate_secret_roles(
        load_json_strict(repo / "modules/rustdesk-fleet/contracts/secret-roles.json")
    )
    if not vault_ready or secret_result.status != "PASS":
        blocked.append("vault-owner-review-pending")

    if review.get("permission_transport_review") != "approved":
        blocked.append("permission-transport-review-pending")
    threat_result = validate_threat_model(
        load_json_strict(repo / "modules/rustdesk-fleet/contracts/threat-model.json")
    )
    if (
        review.get("threat_review") != "approved"
        or review.get("unresolved_high_count") != 0
        or threat_result.status != "PASS"
    ):
        blocked.append("threat-review-pending")
    if review.get("phase48_drift_decision") != "no-drift":
        blocked.append("phase48-review-pending")
    if review.get("review_input_manifest_digest") != _canonical_digest(manifest):
        blocked.append("review-input-manifest-mismatch")
    if scan_secret_material(review, path=source):
        blocked.append("review-secret-material")
    return (
        _result("P51-REPORT-001", True, [], source)
        if not blocked
        else _blocked_result("P51-REPORT-001", blocked, source, "review")
    )


def derive_overall_status(results: list[CheckResult]) -> str:
    if any(item.status == "FAIL" for item in results):
        return "FAIL"
    if any(item.status == "BLOCKED" for item in results):
        return "BLOCKED"
    return "PASS"


def exit_code_for_status(status: str) -> int:
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[status]


def run_checks(repo: Path) -> tuple[list[CheckResult], list[Path]]:
    root = repo.resolve()
    scope_path = root / "modules/rustdesk-fleet/contracts/scope.json"
    by_id = {item.id: item for item in validate_scope(load_json_strict(scope_path), scope_path.relative_to(root).as_posix())}
    validators = (
        ("product-decision.json", validate_product_decision),
        ("permission-profiles.json", validate_permission_profiles),
        ("threat-model.json", validate_threat_model),
        ("secret-roles.json", validate_secret_roles),
    )
    for filename, validator in validators:
        path = root / "modules/rustdesk-fleet/contracts" / filename
        result = validator(load_json_strict(path), path.relative_to(root).as_posix())
        by_id[result.id] = result
    baseline_path = root / "modules/rustdesk-fleet/evidence/phase48-baseline.json"
    baseline = validate_phase48_baseline(
        load_json_strict(baseline_path), root, baseline_path.relative_to(root).as_posix()
    )
    by_id[baseline.id] = baseline
    requirements_path = root / REQUIREMENTS_RELATIVE_PATH
    ledger_path = root / "modules/rustdesk-fleet/evidence/ledger.json"
    ledger = validate_ledger(
        load_json_strict(ledger_path),
        parse_canonical_requirements(requirements_path),
        root,
        ledger_path.relative_to(root).as_posix(),
    )
    by_id[ledger.id] = ledger
    review_path = root / REVIEW_RELATIVE_PATH
    review = load_operational_review(review_path)
    source_head = review.get("source_head")
    if not git_commit_exists(root, source_head):
        source_head = git_head(root)
    assert isinstance(source_head, str)
    manifest = build_review_input_manifest(root, source_head)
    review_result = validate_operational_review(
        review, root, manifest, review_path.relative_to(root).as_posix()
    )
    by_id[review_result.id] = review_result
    if set(by_id) != set(CHECK_ORDER):
        raise ValueError("validator check set is incomplete")
    inputs = [root / item for item in PRE_REPORT_INPUTS]
    inputs.extend([requirements_path, review_path])
    return [by_id[check_id] for check_id in CHECK_ORDER], inputs


def validate_report_currentness(report: dict[str, Any], repo: Path) -> CheckResult:
    errors: list[str] = []
    root = repo.resolve()
    inputs = report.get("inputs") if isinstance(report, dict) else None
    if not isinstance(inputs, list):
        return _blocked_result("P51-REPORT-001", ["report-input-shape"], "report", "inputs")
    for item in inputs:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(
            item.get("sha256"), str
        ):
            errors.append("report-input-shape")
            continue
        try:
            path = validate_repo_path(root, root / item["path"])
            if not path.is_file():
                errors.append("missing-report-input")
            elif _sha256_file(path) != item["sha256"]:
                errors.append("stale-input-digest")
        except ValueError:
            errors.append("report-input-path")
    return (
        _result("P51-REPORT-001", True, [], "report")
        if not errors
        else _blocked_result("P51-REPORT-001", errors, "report", "inputs")
    )


def build_report(repo: Path, generated_at: str | None = None) -> dict[str, Any]:
    root = repo.resolve()
    results, input_paths = run_checks(root)
    inputs = collect_input_digests(root, tuple(input_paths))
    secret_categories = {
        "secret-material",
        "private-key-header",
        "bearer-token",
        "secret-assignment",
        "uri-credential",
        "argv-transcript",
        "screenshot-redaction",
        "sensitive-field-value",
        "high-entropy",
        "review-secret-material",
    }
    secret_material_present = any(
        finding.category in secret_categories for result in results for finding in result.findings
    )
    timestamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "phase": 51,
        "workstream": "rustdesk-fleet",
        "source_head": git_head(root),
        "validator_version": VALIDATOR_VERSION,
        "generated_at": timestamp,
        "inputs": inputs,
        "checks": [_serialize_result(result) for result in results],
        "secret_material_present": secret_material_present,
        "overall_status": derive_overall_status(results),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    return parser


def _serialize_result(result: CheckResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "status": result.status,
        "evidence_ids": result.evidence_ids,
        "findings": [
            {"category": item.category, "path": item.path, "location": item.location}
            for item in result.findings
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 51 Contract Validation",
        "",
        "## Report Identity",
        "",
        f"- **Source HEAD:** `{report['source_head']}`",
        f"- **Validator Version:** `{report['validator_version']}`",
        f"- **Generated At:** `{report['generated_at']}`",
        "",
        "## Input Digests",
        "",
        "| Path | SHA-256 |",
        "|---|---|",
    ]
    for item in report["inputs"]:
        lines.append(f"| `{item['path']}` | `{item['sha256']}` |")
    lines.extend([
        "",
        "## Check Matrix",
        "",
        "| Check | Status | Evidence |",
        "|---|---|---|",
    ])
    for check in report["checks"]:
        lines.append(
            f"| `{check['id']}` | {check['status']} | {', '.join(check['evidence_ids'])} |"
        )
    lines.extend(
        [
            "",
            "## Operational Review",
            "",
            "The accountable review is represented by `P51-REPORT-001`; a BLOCKED status cannot authorize Phase 52.",
            "",
            "## Overall Status",
            "",
            f"**{report['overall_status']}**",
            "",
            f"Secret material present: `{str(report['secret_material_present']).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_reports_atomically(
    report: dict[str, Any], json_path: Path, markdown_path: Path, repo: Path
) -> None:
    root = repo.resolve()
    resolved_json = validate_repo_path(root, json_path if json_path.is_absolute() else root / json_path)
    resolved_markdown = validate_repo_path(
        root, markdown_path if markdown_path.is_absolute() else root / markdown_path
    )
    if resolved_json.name != "51-CONTRACT-VALIDATION.json" or resolved_markdown.name != "51-CONTRACT-VALIDATION.md":
        raise ValueError("runtime report names are fixed")
    payloads = (
        (resolved_json, json.dumps(report, indent=2, sort_keys=True) + "\n"),
        (resolved_markdown, render_markdown(report)),
    )
    temporary_paths: list[Path] = []
    try:
        for target, content in payloads:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", delete=False
            ) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_paths.append(Path(handle.name))
        for temporary, (target, _) in zip(temporary_paths, payloads, strict=True):
            os.replace(temporary, target)
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        report = build_report(repo)
    except (OSError, ValueError) as exc:
        print(f"BLOCKED: {exc.__class__.__name__}", file=sys.stderr)
        return 2
    if bool(args.json_out) != bool(args.markdown_out):
        print("BLOCKED: both report output paths are required", file=sys.stderr)
        return 2
    if args.json_out and args.markdown_out:
        try:
            write_reports_atomically(report, args.json_out, args.markdown_out, repo)
        except (OSError, ValueError) as exc:
            print(f"BLOCKED: {exc.__class__.__name__}", file=sys.stderr)
            return 2
    if not args.json_out and not args.markdown_out:
        print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code_for_status(report["overall_status"])


if __name__ == "__main__":
    raise SystemExit(main())
