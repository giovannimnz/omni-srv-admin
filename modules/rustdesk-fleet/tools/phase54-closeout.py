#!/usr/bin/env python3
"""Read-only Phase 54 closeout projection.

Closeout never writes a report, performs a live call or turns a summary into
evidence.  It consumes the derived validator result and requires explicit
value-free parity/freshness markers from the supplied manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

try:
    from validate_phase54_live_evidence import (
        EVIDENCE_RELATIVE,
        REPO_ROOT,
        SERIAL_ORDER,
        _head,
        _strict_json,
        Phase54EvidenceInvalid,
        validate,
    )
except ImportError:  # pragma: no cover - direct invocation from another cwd
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from validate_phase54_live_evidence import (  # type: ignore
        EVIDENCE_RELATIVE,
        REPO_ROOT,
        SERIAL_ORDER,
        _head,
        _strict_json,
        Phase54EvidenceInvalid,
        validate,
    )


def _blocked(target: str, blocker: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": 54,
        "target": target,
        "state": "BLOCKED",
        "value_free": True,
        "secret_material_present": False,
        "blockers": [blocker],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parity_path(repo: Path, manifest_path: Path, value: str, *, test_only: bool) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("report-parity-path-invalid")
    if test_only:
        root = manifest_path.parent.resolve(strict=True)
        candidate = (root / value).resolve(strict=True)
    else:
        root = (repo / EVIDENCE_RELATIVE).resolve(strict=True)
        if not value.startswith(EVIDENCE_RELATIVE.as_posix() + "/"):
            raise ValueError("report-parity-path-invalid")
        candidate = (repo / value).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("report-parity-path-escape") from exc
    original = (manifest_path.parent / value) if test_only else (repo / value)
    if original.is_symlink() or not candidate.is_file():
        raise ValueError("report-parity-file-invalid")
    return candidate


def _parity_current(repo: Path, manifest: Mapping[str, Any], manifest_path: Path, *, test_only: bool) -> None:
    parity = manifest.get("report_parity")
    if not isinstance(parity, Mapping):
        raise ValueError("report-parity-required")
    for name in ("json", "markdown", "uat"):
        row = parity.get(name)
        if not isinstance(row, Mapping):
            raise ValueError(f"report-parity-ref-required:{name}")
        path = _parity_path(repo, manifest_path, row.get("path"), test_only=test_only)
        digest = row.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or _sha256(path) != digest:
            raise ValueError(f"report-parity-digest-drift:{name}")
    if not test_only:
        try:
            command = [str(Path.home() / ".codex/gsd-core/bin/gsd-tools.cjs"), "graphify", "status"]
            completed = subprocess.run(command, cwd=repo, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=15)
            graphify = json.loads(completed.stdout)
        except (OSError, subprocess.SubprocessError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("graphify-status-unavailable") from exc
        head = _head(repo)
        current_commit = graphify.get("current_commit") if isinstance(graphify, Mapping) else None
        if not isinstance(graphify, Mapping) or graphify.get("stale") is not False or graphify.get("commit_stale") is not False or not isinstance(current_commit, str) or not head.startswith(current_commit):
            raise ValueError("graphify-not-current")
    if manifest.get("server_paths_untouched") is not True:
        raise ValueError("server-path-immutability-unproven")
    if manifest.get("client_only_rollback") is not True:
        raise ValueError("client-only-rollback-unproven")
    if manifest.get("secret_material_present") is not False or manifest.get("value_free") is not True:
        raise ValueError("closeout-value-free-invariant-drift")


def closeout(repo: Path = REPO_ROOT, target: str = "both", evidence_path: Path | None = None, *, _test_only: bool = False) -> dict[str, Any]:
    """Return a closeout verdict without writing any artifact."""

    result = validate(repo, target, evidence_path, _test_only=_test_only)
    if result.get("state") != "PASS":
        return {
            "schema_version": 1,
            "phase": 54,
            "target": target,
            "state": "BLOCKED",
            "value_free": True,
            "secret_material_present": False,
            "blockers": ["validator-blocked", *result.get("blockers", [])],
            "validator": result,
        }
    try:
        manifest_path = evidence_path or (Path(repo) / EVIDENCE_RELATIVE)
        payload = _strict_json(manifest_path)
        if not isinstance(payload, Mapping):
            raise ValueError("manifest-object-required")
        _parity_current(Path(repo).resolve(strict=True), payload, manifest_path, test_only=_test_only)
    except (Phase54EvidenceInvalid, OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return {
            "schema_version": 1,
            "phase": 54,
            "target": target,
            "state": "BLOCKED",
            "value_free": True,
            "secret_material_present": False,
            "blockers": [str(exc)],
            "validator": result,
        }
    return {
        "schema_version": 1,
        "phase": 54,
        "target": target,
        "state": "PASS",
        "value_free": True,
        "secret_material_present": False,
        "serial_order": list(SERIAL_ORDER),
        "validator": result,
        "blockers": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 54 read-only closeout")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--target", required=True)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = closeout(args.repo, args.target, args.evidence)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["state"] == "PASS" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
