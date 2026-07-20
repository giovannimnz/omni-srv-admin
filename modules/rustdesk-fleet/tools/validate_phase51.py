#!/usr/bin/env python3
"""Fail-closed Phase 51 RustDesk contract validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
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
    ]


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
        if server.get("approval_status") != "pending":
            errors.append("server-identity-approval")

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
            ) != "pending":
                errors.append("target-role-shape")
    if payload.get("value_distinctness_phase") != 52:
        errors.append("value-distinctness-phase")
    recovery = payload.get("recovery_authority")
    if not isinstance(recovery, dict) or recovery.get("role") != "rustdesk-recovery-owner" or recovery.get(
        "approval_status"
    ) != "pending":
        errors.append("recovery-authority")
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
        if len(compact) >= 48 and len(set(compact)) >= 16 and not node.startswith(("kv/", "modules/", ".planning/")):
            add("high-entropy", field_location)

    visit(value, location)
    return findings


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 51 Contract Validation",
        "",
        f"**Overall:** {report['overall_status']}",
        "",
        "| Check | Status | Evidence |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        lines.append(
            f"| `{check['id']}` | {check['status']} | {', '.join(check['evidence_ids'])} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        contract_path = validate_repo_path(repo, repo / "modules/rustdesk-fleet/contracts/scope.json")
        payload = load_json_strict(contract_path)
        results = validate_scope(payload, str(contract_path.relative_to(repo)))
        contract_validators = (
            ("product-decision.json", validate_product_decision),
            ("permission-profiles.json", validate_permission_profiles),
            ("threat-model.json", validate_threat_model),
            ("secret-roles.json", validate_secret_roles),
        )
        input_paths = [contract_path]
        for filename, validator in contract_validators:
            path = validate_repo_path(repo, repo / "modules/rustdesk-fleet/contracts" / filename)
            input_paths.append(path)
            results.append(validator(load_json_strict(path), str(path.relative_to(repo))))
    except (OSError, ValueError) as exc:
        print(f"BLOCKED: {exc.__class__.__name__}", file=sys.stderr)
        return 2

    overall = (
        "FAIL"
        if any(item.status == "FAIL" for item in results)
        else "BLOCKED"
        if any(item.status == "BLOCKED" for item in results)
        else "PASS"
    )
    report = {
        "schema_version": 1,
        "phase": 51,
        "workstream": "rustdesk-fleet",
        "inputs": [
            {
                "path": str(path.relative_to(repo)),
                "sha256": _sha256_file(path),
            }
            for path in sorted(input_paths)
        ],
        "checks": [_serialize_result(result) for result in results],
        "secret_material_present": False,
        "overall_status": overall,
    }

    if args.json_out:
        json_path = validate_repo_path(repo, args.json_out if args.json_out.is_absolute() else repo / args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        md_path = validate_repo_path(
            repo, args.markdown_out if args.markdown_out.is_absolute() else repo / args.markdown_out
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(_render_markdown(report), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if overall == "FAIL" else 2 if overall == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
