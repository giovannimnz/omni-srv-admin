#!/usr/bin/env python3
"""Read-only verifier for the immutable Phase 53 execution/evidence chain."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


HEX_32 = re.compile(r"[0-9a-f]{32}")
HEX_40 = re.compile(r"[0-9a-f]{40}")
HEX_64 = re.compile(r"[0-9a-f]{64}")
MAX_INPUT_BYTES = 2_097_152
REQUIREMENTS = ["SRV-02", "SRV-03", "SRV-04", "SRV-06", "OPS-01"]
SOURCE_SCOPE_PATH = Path(
    "modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json"
)
EXECUTION_SOURCE_SCOPE_KEYS = {
    "schema_version",
    "scope_id",
    "phase",
    "aggregate",
    "paths",
}
REQUIRED_EXECUTION_SOURCE_PATHS = (
    "modules/rustdesk-fleet/apache/rustdesk-ops.atius.com.br.conf",
    "modules/rustdesk-fleet/contracts/phase53-candidate-admission.json",
    "modules/rustdesk-fleet/contracts/phase53-edge.json",
    "modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json",
    "modules/rustdesk-fleet/contracts/phase53-horistic-migration-handoff.json",
    "modules/rustdesk-fleet/contracts/phase53-ops-api.json",
    "modules/rustdesk-fleet/contracts/phase53-provider-manifest.json",
    "modules/rustdesk-fleet/contracts/phase53-runtime-candidate.json",
    "modules/rustdesk-fleet/contracts/phase53-runtime.json",
    "modules/rustdesk-fleet/contracts/phase53-topology.json",
    "modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft",
    "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbr.container",
    "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-ops-api.service",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-phase53.slice",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.service",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.timer",
    "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py",
    "modules/rustdesk-fleet/tests/test_phase53_topology.py",
    "modules/rustdesk-fleet/tools/apply-phase53-edge.py",
    "modules/rustdesk-fleet/tools/build-phase53-authority-plan.py",
    "modules/rustdesk-fleet/tools/discover-phase53-topology.py",
    "modules/rustdesk-fleet/tools/install-phase53-server.py",
    "modules/rustdesk-fleet/tools/phase53-live-adapters.py",
    "modules/rustdesk-fleet/tools/phase53-live-backend.py",
    "modules/rustdesk-fleet/tools/phase53-production-adapters.py",
    "modules/rustdesk-fleet/tools/phase53_production_adapters.py",
    "modules/rustdesk-fleet/tools/probe-phase53-edge.ps1",
    "modules/rustdesk-fleet/tools/probe-phase53-edge.py",
    "modules/rustdesk-fleet/tools/run-phase53-live-gate.py",
    "modules/rustdesk-fleet/tools/rustdesk-ops-api.py",
    "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py",
    "modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py",
)
EXECUTION_SOURCE_COMMIT_PATHS = (
    "modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json",
    "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py",
    "modules/rustdesk-fleet/tools/build-phase53-authority-plan.py",
    "modules/rustdesk-fleet/tools/phase53-live-backend.py",
    "modules/rustdesk-fleet/tools/run-phase53-live-gate.py",
    "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py",
    "modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py",
)
FORBIDDEN_SOURCE_PATH_MARKERS = (
    "/evidence/",
    "/.planning/",
    "approval",
    "operation-plan",
)
CANONICAL_INPUTS = {
    "preflight": Path("modules/rustdesk-fleet/evidence/phase53/preflight.json"),
    "operation_plan": Path(
        "modules/rustdesk-fleet/evidence/phase53/edge-forwarder-operation-plan.json"
    ),
    "owner_approval": Path(
        "modules/rustdesk-fleet/evidence/phase53/edge-forwarder-owner-approval.json"
    ),
    "deploy": Path("modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json"),
    "edge_probes": Path("modules/rustdesk-fleet/evidence/phase53/edge-probes.json"),
    "ops_api_probes": Path(
        "modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json"
    ),
    "lifecycle": Path("modules/rustdesk-fleet/evidence/phase53/lifecycle.json"),
    "rollback": Path("modules/rustdesk-fleet/evidence/phase53/rollback-drill.json"),
    "restore_production": Path(
        "modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json"
    ),
    "direct_relay_metrics": Path(
        "modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json"
    ),
    "summary": Path(
        ".planning/workstreams/rustdesk-fleet/phases/"
        "53-primary-relay-and-public-edge/53-05F-SUMMARY.md"
    ),
    "verification": Path(
        ".planning/workstreams/rustdesk-fleet/phases/"
        "53-primary-relay-and-public-edge/53-05F-VERIFICATION.md"
    ),
}
EVIDENCE_ROLES = (
    "deploy",
    "edge_probes",
    "ops_api_probes",
    "lifecycle",
    "rollback",
    "restore_production",
    "direct_relay_metrics",
)
AUTHORITY_ROLES = ("preflight", "operation_plan", "owner_approval")
FORBIDDEN_EVIDENCE_KEYS = {
    "live_executor_commit",
    "05f_summary_commit",
    "verification_commit",
    "self_sha256",
    "manifest_sha256",
    "whole_manifest_sha256",
}


class BindingChainInvalid(RuntimeError):
    """The explicit Phase 53 binding chain is incomplete or contradictory."""


def _git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=text,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BindingChainInvalid("git-read-failed") from exc
    if completed.returncode != 0:
        raise BindingChainInvalid("git-read-failed")
    return completed.stdout


def _commit(repo: Path, value: Any, blocker: str) -> str:
    if not isinstance(value, str) or not HEX_40.fullmatch(value):
        raise BindingChainInvalid(blocker)
    resolved = str(_git(repo, "rev-parse", "--verify", f"{value}^{{commit}}")).strip()
    if resolved != value:
        raise BindingChainInvalid(blocker)
    return value


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=20,
    )
    return completed.returncode == 0


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise BindingChainInvalid("duplicate-json-key")
            result[key] = value
        return result

    try:
        info = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or not 0 < info.st_size <= MAX_INPUT_BYTES
        ):
            raise BindingChainInvalid("explicit-path-invalid")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except BindingChainInvalid:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BindingChainInvalid("explicit-json-invalid") from exc
    if not isinstance(payload, dict):
        raise BindingChainInvalid("explicit-json-invalid")
    return payload


def _explicit_relative(repo: Path, value: Path | str) -> tuple[Path, str]:
    candidate = Path(value)
    absolute = candidate if candidate.is_absolute() else repo / candidate
    try:
        info = absolute.lstat()
    except OSError as exc:
        raise BindingChainInvalid("explicit-path-missing") from exc
    if absolute.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise BindingChainInvalid("explicit-path-invalid")
    resolved = absolute.resolve()
    try:
        relative = resolved.relative_to(repo)
    except ValueError as exc:
        raise BindingChainInvalid("explicit-path-outside-repo") from exc
    return resolved, relative.as_posix()


def _validate_explicit_paths(
    repo: Path, supplied: Mapping[str, Path | str]
) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    seen: set[str] = set()
    for role, expected in CANONICAL_INPUTS.items():
        if role not in supplied:
            raise BindingChainInvalid(f"explicit-path-missing:{role}")
        absolute, relative = _explicit_relative(repo, supplied[role])
        if relative in seen:
            raise BindingChainInvalid("explicit-path-duplicate")
        if relative != expected.as_posix():
            raise BindingChainInvalid(f"explicit-path-noncanonical:{role}")
        seen.add(relative)
        resolved[role] = absolute
    if set(supplied) != set(CANONICAL_INPUTS):
        raise BindingChainInvalid("explicit-path-extra")
    return resolved


def _canonical_manifest_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\0" in value or "\n" in value:
        raise BindingChainInvalid("explicit-path-list-invalid")
    candidate = Path(value)
    if (
        candidate.is_absolute()
        or value != candidate.as_posix()
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise BindingChainInvalid("explicit-path-noncanonical")
    return value


def validate_execution_source_scope_payload(payload: Mapping[str, Any]) -> list[str]:
    """Require the reviewed, closed Phase 53 execution-source inventory."""

    if not isinstance(payload, Mapping) or set(payload) != EXECUTION_SOURCE_SCOPE_KEYS:
        raise BindingChainInvalid("source-scope-schema-invalid")
    aggregate = payload.get("aggregate")
    if (
        payload.get("schema_version") != 1
        or payload.get("scope_id") != "phase53-execution-source-v1"
        or payload.get("phase") != "53-primary-relay-and-public-edge"
        or not isinstance(aggregate, Mapping)
        or set(aggregate) != {"algorithm", "object_source", "order", "record"}
        or aggregate.get("algorithm") != "sha256"
        or aggregate.get("object_source") != "git-blob-oid"
        or aggregate.get("order") != "path-bytewise-ascending"
        or aggregate.get("record") != "path NUL Git-blob-OID LF"
    ):
        raise BindingChainInvalid("source-scope-schema-invalid")
    candidates = payload.get("paths")
    if (
        not isinstance(candidates, list)
        or not candidates
        or not all(isinstance(item, str) and item for item in candidates)
    ):
        raise BindingChainInvalid("source-scope-invalid")
    if len(candidates) != len(set(candidates)):
        raise BindingChainInvalid("source-scope-duplicate")
    if candidates != sorted(candidates):
        raise BindingChainInvalid("source-scope-order-invalid")
    for candidate in candidates:
        _canonical_manifest_path(candidate)
        if any(marker in candidate for marker in FORBIDDEN_SOURCE_PATH_MARKERS):
            raise BindingChainInvalid("source-scope-forbidden")
    required = set(REQUIRED_EXECUTION_SOURCE_PATHS)
    actual = set(candidates)
    if required - actual:
        raise BindingChainInvalid("source-scope-missing")
    if actual - required:
        raise BindingChainInvalid("source-scope-extra")
    return list(candidates)


def _git_blob_oid(repo: Path, commit: str, relative: str) -> str:
    raw = _git(
        repo,
        "ls-tree",
        "-z",
        commit,
        "--",
        relative,
        text=False,
    )
    assert isinstance(raw, bytes)
    records = [item for item in raw.split(b"\0") if item]
    if not records:
        raise BindingChainInvalid("git-object-missing")
    if len(records) != 1:
        raise BindingChainInvalid("git-object-ambiguous")
    try:
        header, encoded_path = records[0].split(b"\t", 1)
        mode, object_type, oid = header.decode("ascii").split(" ", 2)
        object_path = encoded_path.decode("utf-8")
    except (UnicodeError, ValueError) as exc:
        raise BindingChainInvalid("git-object-invalid") from exc
    if object_path != relative:
        raise BindingChainInvalid("git-object-invalid")
    if mode == "120000":
        raise BindingChainInvalid("git-object-symlink")
    if object_type != "blob" or mode not in {"100644", "100755"}:
        raise BindingChainInvalid("git-object-invalid")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid):
        raise BindingChainInvalid("git-blob-oid-invalid")
    return oid


def compute_execution_source_binding(
    *,
    repo: Path,
    execution_source_commit: str,
    manifest_paths: Sequence[Path | str],
) -> dict[str, Any]:
    """Hash sorted ``path NUL Git-blob-OID LF`` records from one Git commit."""

    root = repo.resolve(strict=True)
    source_commit = _commit(root, execution_source_commit, "execution-source-invalid")
    if (
        not isinstance(manifest_paths, Sequence)
        or isinstance(manifest_paths, (str, bytes))
        or not manifest_paths
    ):
        raise BindingChainInvalid("explicit-path-list-invalid")
    relative_paths: list[str] = []
    seen: set[str] = set()
    for supplied in manifest_paths:
        relative = _canonical_manifest_path(supplied)
        if relative in seen:
            raise BindingChainInvalid("explicit-path-duplicate")
        seen.add(relative)
        relative_paths.append(relative)
    if relative_paths != sorted(relative_paths):
        raise BindingChainInvalid("explicit-path-order-invalid")

    records: list[bytes] = []
    blobs: dict[str, dict[str, str]] = {}
    for relative in relative_paths:
        oid = _git_blob_oid(root, source_commit, relative)
        content = _git(root, "show", f"{source_commit}:{relative}", text=False)
        assert isinstance(content, bytes)
        records.append(relative.encode("utf-8") + b"\0" + oid.encode("ascii") + b"\n")
        blobs[relative] = {
            "git_blob_oid": oid,
            "content_sha256": hashlib.sha256(content).hexdigest(),
        }
    return {
        "execution_source_commit": source_commit,
        "execution_source_tree_sha256": hashlib.sha256(b"".join(records)).hexdigest(),
        "manifest_paths": relative_paths,
        "blobs": blobs,
    }


def _metadata(text: str, key: str, blocker: str) -> str:
    escaped = re.escape(key)
    patterns = (
        rf"(?mi)^\s*{escaped}\s*:\s*[`'\"]?([^`'\"\s]+)",
        rf"(?mi)^\s*(?:[-*]\s*)?{escaped}\s*=\s*[`'\"]?([^`'\"\s]+)",
    )
    values: list[str] = []
    for pattern in patterns:
        values.extend(match.group(1).strip() for match in re.finditer(pattern, text))
    unique = list(dict.fromkeys(values))
    if len(unique) != 1:
        raise BindingChainInvalid(blocker)
    return unique[0]


def _manifest_digest_table(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r"(?m)^\|\s*([^|]+?)\s*\|\s*([0-9a-f]{64})\s*\|$")
    for match in pattern.finditer(text):
        path = match.group(1).strip(" `")
        if path in result:
            raise BindingChainInvalid("summary-manifest-duplicate")
        result[path] = match.group(2)
    return result


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def _exact_commit_paths(repo: Path, commit: str) -> list[str]:
    output = str(
        _git(
            repo,
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        )
    )
    return sorted(item for item in output.splitlines() if item)


def validate_execution_source_commit_paths(repo: Path, commit: str) -> list[str]:
    """Require the exact seven-path 05D2D source seal without broad staging."""

    root = repo.resolve(strict=True)
    source_commit = _commit(root, commit, "execution-source-invalid")
    paths = _exact_commit_paths(root, source_commit)
    expected = list(EXECUTION_SOURCE_COMMIT_PATHS)
    if paths != expected:
        raise BindingChainInvalid("execution-source-commit-paths-invalid")
    return paths


def _latest_path_commit(repo: Path, relative: str) -> str:
    value = str(_git(repo, "log", "-n", "1", "--format=%H", "--", relative)).strip()
    return _commit(repo, value, "path-commit-invalid")


def _read_source_scope(repo: Path) -> list[str]:
    payload = _strict_json(repo / SOURCE_SCOPE_PATH)
    return validate_execution_source_scope_payload(payload)


def require_clean_execution_source(
    *,
    repo: Path,
    execution_source_commit: str,
    manifest_paths: Sequence[Path | str],
    expected_tree: str,
) -> dict[str, Any]:
    """Bind Git objects and reject any missing, symlinked, dirty or later source."""

    root = repo.resolve(strict=True)
    relative_paths: list[str] = []
    for supplied in manifest_paths:
        relative = _canonical_manifest_path(supplied)
        _absolute, worktree_relative = _explicit_relative(root, relative)
        if worktree_relative != relative:
            raise BindingChainInvalid("explicit-path-noncanonical")
        relative_paths.append(relative)
    binding = compute_execution_source_binding(
        repo=root,
        execution_source_commit=execution_source_commit,
        manifest_paths=relative_paths,
    )
    if binding["execution_source_tree_sha256"] != expected_tree:
        raise BindingChainInvalid("execution-source-tree-drift")
    status = str(
        _git(
            root,
            "--literal-pathspecs",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *relative_paths,
        )
    )
    if status.strip():
        raise BindingChainInvalid("execution-source-dirty")
    head = str(_git(root, "rev-parse", "HEAD")).strip()
    head_binding = compute_execution_source_binding(
        repo=root,
        execution_source_commit=head,
        manifest_paths=relative_paths,
    )
    if (
        head_binding["execution_source_tree_sha256"]
        != binding["execution_source_tree_sha256"]
        or head_binding["blobs"] != binding["blobs"]
    ):
        raise BindingChainInvalid("execution-source-changed")
    return binding


def _require_clean_source(
    repo: Path,
    source_commit: str,
    source_paths: Sequence[Path | str],
    expected_tree: str,
) -> dict[str, Any]:
    return require_clean_execution_source(
        repo=repo,
        execution_source_commit=source_commit,
        manifest_paths=source_paths,
        expected_tree=expected_tree,
    )


def _default_strict_validator(repo: Path) -> Mapping[str, Any]:
    path = repo / "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py"
    spec = importlib.util.spec_from_file_location("_phase53_strict_validator", path)
    if spec is None or spec.loader is None:
        raise BindingChainInvalid("strict-validator-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        result = module.validate(repo)
    except Exception as exc:
        raise BindingChainInvalid("strict-validator-failed") from exc
    if not isinstance(result, Mapping):
        raise BindingChainInvalid("strict-validator-failed")
    return result


def validate_phase53_binding_chain(
    *,
    repo: Path,
    preflight: Path,
    operation_plan: Path,
    owner_approval: Path,
    deploy: Path,
    edge_probes: Path,
    ops_api_probes: Path,
    lifecycle: Path,
    rollback: Path,
    restore_production: Path,
    direct_relay_metrics: Path,
    summary: Path,
    verification: Path,
    execution_source_paths: Sequence[Path | str] | None = None,
    strict_validator: Callable[[Path], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate the explicit source/live/summary/verification chain without writes."""

    root = repo.resolve(strict=True)
    supplied = {
        "preflight": preflight,
        "operation_plan": operation_plan,
        "owner_approval": owner_approval,
        "deploy": deploy,
        "edge_probes": edge_probes,
        "ops_api_probes": ops_api_probes,
        "lifecycle": lifecycle,
        "rollback": rollback,
        "restore_production": restore_production,
        "direct_relay_metrics": direct_relay_metrics,
        "summary": summary,
        "verification": verification,
    }
    paths = _validate_explicit_paths(root, supplied)
    payloads = {
        role: _strict_json(paths[role]) for role in AUTHORITY_ROLES + EVIDENCE_ROLES
    }
    for role in EVIDENCE_ROLES:
        if _walk_keys(payloads[role]) & FORBIDDEN_EVIDENCE_KEYS:
            raise BindingChainInvalid("self-hash-forbidden")

    summary_text = paths["summary"].read_text(encoding="utf-8")
    verification_text = paths["verification"].read_text(encoding="utf-8")
    if _metadata(verification_text, "status", "verification-status-invalid") != "passed":
        raise BindingChainInvalid("verification-status-invalid")
    live_commit = _commit(
        root,
        _metadata(summary_text, "live_executor_commit", "live-commit-missing"),
        "live-commit-invalid",
    )
    if (
        _metadata(verification_text, "live_executor_commit", "live-commit-mismatch")
        != live_commit
    ):
        raise BindingChainInvalid("live-commit-mismatch")
    summary_commit = _commit(
        root,
        _metadata(
            verification_text, "05F_summary_commit", "summary-commit-missing"
        ),
        "summary-commit-invalid",
    )
    actual_summary_commit = _latest_path_commit(
        root, CANONICAL_INPUTS["summary"].as_posix()
    )
    if summary_commit != actual_summary_commit:
        raise BindingChainInvalid("summary-commit-mismatch")
    source_commit = _commit(
        root,
        _metadata(
            summary_text, "execution_source_commit", "execution-source-missing"
        ),
        "execution-source-invalid",
    )
    source_tree = _metadata(
        summary_text,
        "execution_source_tree_sha256",
        "execution-source-tree-missing",
    )
    if not HEX_64.fullmatch(source_tree):
        raise BindingChainInvalid("execution-source-tree-invalid")
    if (
        _metadata(
            verification_text,
            "execution_source_commit",
            "execution-source-mismatch",
        )
        != source_commit
        or _metadata(
            verification_text,
            "execution_source_tree_sha256",
            "execution-source-tree-mismatch",
        )
        != source_tree
    ):
        raise BindingChainInvalid("execution-source-mismatch")
    plan_digest = _metadata(
        summary_text, "operation_plan_sha256", "operation-plan-digest-missing"
    )
    if not HEX_64.fullmatch(plan_digest):
        raise BindingChainInvalid("operation-plan-digest-invalid")

    if not _is_ancestor(root, source_commit, live_commit):
        raise BindingChainInvalid("source-live-ancestry-invalid")
    live_parent = str(_git(root, "rev-parse", f"{summary_commit}^")).strip()
    if live_parent != live_commit:
        raise BindingChainInvalid("summary-not-direct-descendant")
    verification_commit = _latest_path_commit(
        root, CANONICAL_INPUTS["verification"].as_posix()
    )
    if not _is_ancestor(root, summary_commit, verification_commit):
        raise BindingChainInvalid("verification-ancestry-invalid")
    if _exact_commit_paths(root, live_commit) != sorted(
        CANONICAL_INPUTS[role].as_posix() for role in EVIDENCE_ROLES
    ):
        raise BindingChainInvalid("evidence-only-commit-invalid")
    if _exact_commit_paths(root, summary_commit) != [
        CANONICAL_INPUTS["summary"].as_posix()
    ]:
        raise BindingChainInvalid("summary-only-commit-invalid")

    manifest_digests = _manifest_digest_table(summary_text)
    expected_evidence = {
        CANONICAL_INPUTS[role].as_posix() for role in EVIDENCE_ROLES
    }
    if set(manifest_digests) != expected_evidence:
        raise BindingChainInvalid("summary-manifest-set-invalid")
    for role in EVIDENCE_ROLES:
        relative = CANONICAL_INPUTS[role].as_posix()
        committed = _git(root, "show", f"{live_commit}:{relative}", text=False)
        assert isinstance(committed, bytes)
        if paths[role].read_bytes() != committed:
            raise BindingChainInvalid("evidence-bytes-drift")
        if hashlib.sha256(committed).hexdigest() != manifest_digests[relative]:
            raise BindingChainInvalid("summary-manifest-digest-mismatch")

    for role in AUTHORITY_ROLES + EVIDENCE_ROLES:
        payload = payloads[role]
        if (
            payload.get("execution_source_commit") != source_commit
            or payload.get("execution_source_tree_sha256") != source_tree
            or payload.get("operation_plan_sha256") != plan_digest
        ):
            raise BindingChainInvalid(f"binding-field-mismatch:{role}")
        if payload.get("secret_material_present") is not False:
            raise BindingChainInvalid(f"secret-material-present:{role}")
    if (
        payloads["operation_plan"].get(
            "target", payloads["operation_plan"].get("execution_target")
        )
        != "10.21.1.21"
        or payloads["owner_approval"].get("owner") != "Giovanni Muniz"
        or payloads["owner_approval"].get("decision") != "approve"
    ):
        raise BindingChainInvalid("authority-binding-invalid")

    apply_id = payloads["deploy"].get(
        "apply_transaction_id", payloads["deploy"].get("transaction_id")
    )
    rollback_id = payloads["rollback"].get(
        "rollback_transaction_id", payloads["rollback"].get("transaction_id")
    )
    restore_id = payloads["restore_production"].get(
        "restore_production_transaction_id",
        payloads["restore_production"].get("transaction_id"),
    )
    if (
        not all(
            isinstance(item, str) and HEX_32.fullmatch(item)
            for item in (apply_id, rollback_id, restore_id)
        )
        or len({apply_id, rollback_id, restore_id}) != 3
    ):
        raise BindingChainInvalid("transaction-identity-invalid")
    for role in ("edge_probes", "ops_api_probes", "lifecycle", "rollback"):
        if payloads[role].get("apply_transaction_id") != apply_id:
            raise BindingChainInvalid("apply-transaction-drift")
    if (
        payloads["restore_production"].get("apply_transaction_id") != apply_id
        or payloads["restore_production"].get("rollback_transaction_id")
        != rollback_id
        or payloads["direct_relay_metrics"].get("apply_transaction_id") != apply_id
        or payloads["direct_relay_metrics"].get(
            "restore_production_transaction_id"
        )
        != restore_id
    ):
        raise BindingChainInvalid("transaction-binding-invalid")
    rollback_seal = payloads["rollback"].get("rollback_seal_sha256")
    if (
        not isinstance(rollback_seal, str)
        or not HEX_64.fullmatch(rollback_seal)
        or payloads["restore_production"].get("rollback_seal_sha256")
        != rollback_seal
    ):
        raise BindingChainInvalid("rollback-seal-invalid")

    source_paths = (
        list(execution_source_paths)
        if execution_source_paths is not None
        else _read_source_scope(root)
    )
    source_commit_paths: list[str] | None = None
    if execution_source_paths is None:
        source_commit_paths = validate_execution_source_commit_paths(
            root, source_commit
        )
    binding = _require_clean_source(root, source_commit, source_paths, source_tree)
    validator = strict_validator or _default_strict_validator
    strict_result = validator(root)
    if (
        not isinstance(strict_result, Mapping)
        or strict_result.get("state") != "PASS"
        or strict_result.get("requirements") != REQUIREMENTS
    ):
        raise BindingChainInvalid("strict-validator-not-pass")
    return {
        "schema_version": 1,
        "status": "PASS",
        "live_executor_commit": live_commit,
        "05F_summary_commit": summary_commit,
        "verification_commit": verification_commit,
        "execution_source_commit": source_commit,
        "execution_source_tree_sha256": source_tree,
        "operation_plan_sha256": plan_digest,
        "apply_transaction_id": apply_id,
        "rollback_transaction_id": rollback_id,
        "restore_production_transaction_id": restore_id,
        "rollback_seal_sha256": rollback_seal,
        "manifest_digests": manifest_digests,
        "source_binding": binding,
        "execution_source_commit_paths": source_commit_paths,
        "requirements": REQUIREMENTS,
        "strict_validator_state": "PASS",
        "provider_constructed": False,
        "mutation_performed": False,
        "secret_material_present": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    for role in CANONICAL_INPUTS:
        parser.add_argument(f"--{role.replace('_', '-')}", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    values = vars(args)
    try:
        result = validate_phase53_binding_chain(
            repo=args.repo,
            **{role: values[role] for role in CANONICAL_INPUTS},
        )
    except (BindingChainInvalid, OSError, UnicodeError, ValueError) as exc:
        result = {
            "schema_version": 1,
            "status": "BLOCKED",
            "blocker": str(exc)
            if isinstance(exc, BindingChainInvalid)
            else "binding-check-failed",
            "provider_constructed": False,
            "mutation_performed": False,
            "secret_material_present": False,
        }
        sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
