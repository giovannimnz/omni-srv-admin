#!/usr/bin/env python3
"""Fail-closed Phase 51 RustDesk contract validator."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def scan_secret_material(value: Any, path: str = "contract", location: str = "root") -> list[Finding]:
    """Task 51-01 seam; Task 51-01-03 adds the complete non-disclosing scanner."""
    del value, path, location
    return []


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
    except (OSError, ValueError) as exc:
        print(f"BLOCKED: {exc.__class__.__name__}", file=sys.stderr)
        return 2

    overall = "FAIL" if any(item.status == "FAIL" for item in results) else "PASS"
    report = {
        "schema_version": 1,
        "phase": 51,
        "workstream": "rustdesk-fleet",
        "inputs": [
            {
                "path": str(contract_path.relative_to(repo)),
                "sha256": _sha256_file(contract_path),
            }
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
    return 1 if overall == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
