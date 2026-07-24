#!/usr/bin/env python3
"""Fail-closed pre-execution bootstrap for GSD Phase 59.

This tool prepares execution; it never invokes a Codex skill and never edits the
owner checkout.  The final receipt is intentionally external to the worktree.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


PHASE = 59
WORKSTREAM = "qwen-local-ai"
OWNER_REPO = Path("/home/ubuntu/GitHub/omni-srv-admin")
EXECUTION_WORKTREE = Path("/home/ubuntu/GitHub/worktrees/omni-srv-admin-phase59")
EXTERNAL_STATE = Path("/home/ubuntu/.local/state/gsd/phase59")
OMNI = Path("/home/ubuntu/.local/bin/omni")
GRAPHIFY = Path("/home/ubuntu/.local/bin/graphify")
GSD_TOOLS = Path("/home/ubuntu/.codex/gsd-core/bin/gsd-tools.cjs")
AUTOPILOT_SKILL = Path("/home/ubuntu/.codex/skills/gsd-execute-autopilot/SKILL.md")
AUTOPILOT_WORKFLOW = Path("/home/ubuntu/.codex/gsd-core/workflows/execute-autopilot.md")
GRAPHIFY_WORKTREE_PARENT = Path("/home/ubuntu/GitHub/worktrees")
GRAPHIFY_GENERATED_PREFIXES = ("graphify-out/", ".planning/graphs/")
EXECUTOR_LOCK = EXTERNAL_STATE / "59-EXECUTOR-LOCK.json"
COMBINED_RECEIPT = EXTERNAL_STATE / "59-AUTOPILOT-COMBINED-RECEIPT.json"
PHASE_DIR = (
    ".planning/workstreams/qwen-local-ai/phases/"
    "59-qwen3-embedding-e-rerank-podman-para-k3s"
)
SIGNED_PATHS = tuple(
    [f"{PHASE_DIR}/59-{number:02d}-PLAN.md" for number in range(1, 10)]
    + [
        f"{PHASE_DIR}/59-CONTEXT.md",
        f"{PHASE_DIR}/59-RESEARCH.md",
        f"{PHASE_DIR}/59-PATTERNS.md",
        f"{PHASE_DIR}/59-VALIDATION.md",
        f"{PHASE_DIR}/59-REVIEWS.md",
        f"{PHASE_DIR}/59-AUTOPILOT-BOOTSTRAP.md",
        "scripts/embeddings-bench/phase59-autopilot-bootstrap.py",
        "scripts/embeddings-bench/tests/test_phase59_autopilot_bootstrap.py",
    ]
)
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class BootstrapError(RuntimeError):
    pass


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise BootstrapError(f"command failed ({result.returncode}): {argv!r}: {detail}")
    return result


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_bytes(repo: Path, commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise BootstrapError(
            f"missing signed tree path {path!r}: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout


def assert_absolute_non_symlink(path: Path, *, must_exist: bool) -> Path:
    if not path.is_absolute():
        raise BootstrapError(f"path must be absolute: {path}")
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        if cursor.exists() or cursor.is_symlink():
            if cursor.is_symlink():
                raise BootstrapError(f"symlink path component rejected: {cursor}")
    if must_exist and not path.exists():
        raise BootstrapError(f"required path does not exist: {path}")
    resolved = path.resolve(strict=must_exist)
    if path.exists() and resolved != path:
        raise BootstrapError(f"realpath mismatch rejected: {path} -> {resolved}")
    return resolved


def assert_external_output(path: Path, repo: Path, worktree: Path) -> None:
    resolved = assert_absolute_non_symlink(path, must_exist=False)
    for forbidden in (repo.resolve(), worktree.resolve(strict=False)):
        try:
            resolved.relative_to(forbidden)
        except ValueError:
            continue
        raise BootstrapError(f"external artifact cannot be inside {forbidden}: {resolved}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BootstrapError(f"JSON root must be an object: {path}")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with tmp.open("x", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def validate_executor_owner(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", value):
        raise BootstrapError("executor owner ID is missing or invalid")
    return value


def create_or_verify_executor_lock(
    path: Path,
    *,
    executor_mode: str,
    executor_owner: str,
    bundle_sha256: str,
    base_commit: str,
) -> dict[str, Any]:
    assert_external_output(path, OWNER_REPO, EXECUTION_WORKTREE)
    expected = {
        "schema_version": 1,
        "phase": PHASE,
        "workstream": WORKSTREAM,
        "executor_mode": executor_mode,
        "executor_owner": validate_executor_owner(executor_owner),
        "bundle_sha256": bundle_sha256,
        "base_commit": base_commit,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(expected, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        current = load_json(path)
        if current != expected:
            raise BootstrapError("Phase 59 is owned by another executor or mode")
    return expected


def verify_executor_lock_against_receipt(
    path: Path,
    receipt: dict[str, Any],
    *,
    required_mode: str | None = None,
) -> tuple[dict[str, Any], str]:
    path = assert_absolute_non_symlink(path, must_exist=True)
    executor_mode = receipt.get("executor_mode")
    if required_mode is not None and executor_mode != required_mode:
        raise BootstrapError("executor lock receipt mode mismatch")
    expected = {
        "schema_version": 1,
        "phase": PHASE,
        "workstream": WORKSTREAM,
        "executor_mode": executor_mode,
        "executor_owner": validate_executor_owner(
            str(receipt.get("executor_owner", ""))
        ),
        "bundle_sha256": receipt.get("bundle_sha256"),
        "base_commit": receipt.get("final_execution_commit"),
    }
    current = load_json(path)
    if current != expected:
        raise BootstrapError("executor lock content differs from bootstrap receipt")
    current_sha256 = sha256_bytes(path.read_bytes())
    if receipt.get("executor_lock_sha256") != current_sha256:
        raise BootstrapError("executor lock hash differs from bootstrap receipt")
    return current, current_sha256


def resolve_commit(repo: Path, revision: str) -> str:
    commit = run(["git", "-C", str(repo), "rev-parse", f"{revision}^{{commit}}"]).stdout.strip()
    if not SHA1_RE.fullmatch(commit):
        raise BootstrapError(f"unexpected commit identity: {commit!r}")
    return commit


def normalized_remote(value: str) -> str:
    value = value.strip().removesuffix("/")
    if not value:
        raise BootstrapError("empty repository remote")
    return value.removesuffix(".git")


def validate_execution_branch(branch: str) -> str:
    branch = branch.strip()
    if not branch or branch in {"main", "master"}:
        raise BootstrapError("bundle must use a dedicated Phase 59 branch")
    if not branch.startswith("phase59-"):
        raise BootstrapError("execution branch must start with phase59-")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
        raise BootstrapError("execution branch contains unsupported characters")
    return branch


def create_bundle(
    repo: Path,
    commitish: str,
    output: Path,
    remote: str,
    branch: str,
) -> dict[str, Any]:
    repo = assert_absolute_non_symlink(repo, must_exist=True)
    assert_external_output(output, repo, EXECUTION_WORKTREE)
    commit = resolve_commit(repo, commitish)
    files = [
        {"path": path, "sha256": sha256_bytes(git_bytes(repo, commit, path))}
        for path in SIGNED_PATHS
    ]
    branch = validate_execution_branch(branch)
    bundle = {
        "schema_version": 1,
        "phase": PHASE,
        "workstream": WORKSTREAM,
        "final_execution_commit": commit,
        "repo_remote": remote,
        "repo_branch": branch,
        "execution_worktree": str(EXECUTION_WORKTREE),
        "files": files,
    }
    atomic_json(output, bundle)
    verify_bundle(repo, output)
    return bundle


def verify_bundle(
    repo: Path,
    bundle_path: Path,
    *,
    require_remote_tip: bool = True,
) -> dict[str, Any]:
    repo = assert_absolute_non_symlink(repo, must_exist=True)
    bundle_path = assert_absolute_non_symlink(bundle_path, must_exist=True)
    bundle = load_json(bundle_path)
    expected = {
        "schema_version": 1,
        "phase": PHASE,
        "workstream": WORKSTREAM,
        "execution_worktree": str(EXECUTION_WORKTREE),
    }
    for key, value in expected.items():
        if bundle.get(key) != value:
            raise BootstrapError(f"bundle {key} mismatch: {bundle.get(key)!r}")
    commit = bundle.get("final_execution_commit")
    if not isinstance(commit, str) or not SHA1_RE.fullmatch(commit):
        raise BootstrapError("bundle final_execution_commit is not a full SHA-1")
    if resolve_commit(repo, commit) != commit:
        raise BootstrapError("bundle commit cannot be resolved exactly")
    files = bundle.get("files")
    if not isinstance(files, list):
        raise BootstrapError("bundle files must be an array")
    paths = [item.get("path") for item in files if isinstance(item, dict)]
    if paths != list(SIGNED_PATHS) or len(paths) != len(set(paths)):
        raise BootstrapError("bundle signed path list/order is incomplete or duplicated")
    for item in files:
        digest = item.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise BootstrapError(f"invalid SHA-256 for {item.get('path')!r}")
        actual = sha256_bytes(git_bytes(repo, commit, item["path"]))
        if actual != digest:
            raise BootstrapError(f"signed content mismatch: {item['path']}")
    remote = bundle.get("repo_remote")
    branch = bundle.get("repo_branch")
    if not isinstance(remote, str) or not isinstance(branch, str):
        raise BootstrapError("bundle remote/branch contract is missing")
    branch = validate_execution_branch(branch)
    configured = run(["git", "-C", str(repo), "remote", "get-url", "origin"]).stdout
    if normalized_remote(configured) != normalized_remote(remote):
        raise BootstrapError("bundle remote differs from configured origin")
    if require_remote_tip:
        remote_line = run(
            ["git", "ls-remote", remote, f"refs/heads/{branch}"]
        ).stdout.strip()
        fields = remote_line.split()
        if len(fields) != 2 or fields[0] != commit:
            raise BootstrapError("durable remote branch does not resolve to final commit")
    return bundle


def registered_worktrees(repo: Path) -> dict[Path, str]:
    output = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"]).stdout
    result: dict[Path, str] = {}
    current: Path | None = None
    for line in output.splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif current is not None and line.startswith("HEAD "):
            result[current] = line.removeprefix("HEAD ")
    return result


def verify_worktree(repo: Path, bundle: dict[str, Any], worktree: Path) -> None:
    worktree = assert_absolute_non_symlink(worktree, must_exist=True)
    if worktree != EXECUTION_WORKTREE:
        raise BootstrapError(f"unexpected execution worktree: {worktree}")
    commit = bundle["final_execution_commit"]
    if registered_worktrees(repo).get(worktree) != commit:
        raise BootstrapError("worktree registration/HEAD does not match bundle")
    head = run(["git", "-C", str(worktree), "rev-parse", "HEAD"]).stdout.strip()
    if head != commit:
        raise BootstrapError("worktree HEAD differs from final execution commit")
    if run(["git", "-C", str(worktree), "status", "--porcelain"]).stdout:
        raise BootstrapError("execution worktree is dirty or has untracked files")
    branch = run(
        ["git", "-C", str(worktree), "symbolic-ref", "--short", "HEAD"]
    ).stdout.strip()
    if branch != bundle["repo_branch"]:
        raise BootstrapError("execution worktree is detached or on the wrong branch")
    for item in bundle["files"]:
        actual = sha256_bytes(git_bytes(worktree, "HEAD", item["path"]))
        if actual != item["sha256"]:
            raise BootstrapError(f"worktree signed content mismatch: {item['path']}")


def verify_runtime_worktree(
    repo: Path,
    bundle: dict[str, Any],
    worktree: Path,
) -> str:
    worktree = assert_absolute_non_symlink(worktree, must_exist=True)
    if worktree != EXECUTION_WORKTREE:
        raise BootstrapError("runtime worktree path mismatch")
    base = bundle["final_execution_commit"]
    head = run(["git", "-C", str(worktree), "rev-parse", "HEAD"]).stdout.strip()
    if not SHA1_RE.fullmatch(head):
        raise BootstrapError("runtime HEAD is invalid")
    ancestry = subprocess.run(
        ["git", "-C", str(worktree), "merge-base", "--is-ancestor", base, head],
        check=False,
    )
    if ancestry.returncode != 0:
        raise BootstrapError("runtime HEAD is not a descendant of signed base")
    if registered_worktrees(repo).get(worktree) != head:
        raise BootstrapError("runtime worktree registration/HEAD mismatch")
    branch = run(
        ["git", "-C", str(worktree), "symbolic-ref", "--short", "HEAD"]
    ).stdout.strip()
    if branch != bundle["repo_branch"]:
        raise BootstrapError("runtime branch differs from signed branch")
    if porcelain_paths(worktree):
        raise BootstrapError("runtime task boundary requires a clean worktree")
    for item in bundle["files"]:
        actual = sha256_bytes(git_bytes(worktree, head, item["path"]))
        if actual != item["sha256"]:
            raise BootstrapError(f"signed runtime path changed: {item['path']}")
    return head


def porcelain_paths(repo: Path) -> list[str]:
    output = run(["git", "-C", str(repo), "status", "--porcelain=v1"]).stdout
    paths: list[str] = []
    for line in output.splitlines():
        if len(line) < 4:
            raise BootstrapError(f"unexpected git status record: {line!r}")
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def verify_graphify_generated_only(worktree: Path) -> list[str]:
    paths = porcelain_paths(worktree)
    unexpected = [
        path
        for path in paths
        if not any(
            path == prefix.rstrip("/") or path.startswith(prefix)
            for prefix in GRAPHIFY_GENERATED_PREFIXES
        )
    ]
    if unexpected:
        raise BootstrapError(
            f"Graphify verification worktree has undeclared changes: {unexpected}"
        )
    return paths


def prepare_graphify_worktree(repo: Path, commit: str) -> Path:
    parent = assert_absolute_non_symlink(GRAPHIFY_WORKTREE_PARENT, must_exist=True)
    worktree = parent / f"omni-srv-admin-phase59-bootstrap-graphify-{commit[:12]}"
    if worktree.exists():
        worktree = assert_absolute_non_symlink(worktree, must_exist=True)
    else:
        run(
            [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "--detach",
                str(worktree),
                commit,
            ]
        )
    registered = registered_worktrees(repo).get(worktree)
    head = run(["git", "-C", str(worktree), "rev-parse", "HEAD"]).stdout.strip()
    if registered != commit or head != commit:
        raise BootstrapError("Graphify verification worktree is not the bundle commit")
    verify_graphify_generated_only(worktree)
    return worktree


def prepare_worktree(repo: Path, bundle_path: Path, worktree: Path) -> dict[str, Any]:
    repo = assert_absolute_non_symlink(repo, must_exist=True)
    if repo != OWNER_REPO:
        raise BootstrapError(f"operational owner repo must be {OWNER_REPO}")
    if worktree != EXECUTION_WORKTREE:
        raise BootstrapError(f"operational worktree must be {EXECUTION_WORKTREE}")
    bundle = verify_bundle(repo, bundle_path)
    if not worktree.exists():
        assert_absolute_non_symlink(worktree.parent, must_exist=True)
        branch = bundle["repo_branch"]
        branch_exists = subprocess.run(
            ["git", "-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            check=False,
        ).returncode == 0
        if branch_exists:
            branch_commit = resolve_commit(repo, branch)
            if branch_commit != bundle["final_execution_commit"]:
                raise BootstrapError("existing local execution branch is not final commit")
            argv = ["git", "-C", str(repo), "worktree", "add", str(worktree), branch]
        else:
            argv = [
                "git",
                "-C",
                str(repo),
                "worktree",
                "add",
                "-b",
                branch,
                str(worktree),
                bundle["final_execution_commit"],
            ]
        run(argv)
    verify_worktree(repo, bundle, worktree)
    return bundle


def parse_graphify_evidence(
    status_raw: str,
    query_raw: str,
    *,
    commit: str,
    worktree_head: str,
) -> dict[str, Any]:
    try:
        status = json.loads(status_raw)
        query = json.loads(query_raw)
    except json.JSONDecodeError as exc:
        raise BootstrapError(f"Graphify output is not JSON: {exc}") from exc
    if not isinstance(status, dict) or not isinstance(query, dict):
        raise BootstrapError("Graphify status/query roots must be objects")
    if worktree_head != commit:
        raise BootstrapError("Graphify worktree HEAD differs from bundle commit")
    if status.get("exists") is not True:
        raise BootstrapError("Graphify graph does not exist")
    if status.get("stale") is not False or status.get("commit_stale") is not False:
        raise BootstrapError("Graphify status is stale")
    for key in ("built_at_commit", "current_commit"):
        short = status.get(key)
        if not isinstance(short, str) or len(short) < 7 or not commit.startswith(short):
            raise BootstrapError(f"Graphify {key} is not the bundle commit")
    if not isinstance(query.get("total_nodes"), int) or query["total_nodes"] < 0:
        raise BootstrapError("Graphify query total_nodes is invalid")
    if not isinstance(query.get("nodes"), list):
        raise BootstrapError("Graphify query nodes is not an array")
    if query["total_nodes"] != len(query["nodes"]):
        raise BootstrapError("Graphify query count/list mismatch")
    return {
        "status_sha256": sha256_bytes(status_raw.encode()),
        "query_sha256": sha256_bytes(query_raw.encode()),
        "built_at_commit": status["built_at_commit"],
        "total_nodes": query["total_nodes"],
        "query_route": (
            "graph"
            if query["total_nodes"] > 0
            else "focused_reads_required"
        ),
    }


def graphify_doctor(repo: Path, commit: str) -> dict[str, Any]:
    for required in (OMNI, GRAPHIFY, GSD_TOOLS):
        assert_absolute_non_symlink(required, must_exist=True)
    worktree = prepare_graphify_worktree(repo, commit)
    run([str(OMNI), "srv1-ops", "resources", "doctor", "builds"], cwd=worktree)
    run(
        [
            str(OMNI),
            "srv1-ops",
            "resources",
            "run",
            "builds",
            "--",
            str(GRAPHIFY),
            "update",
            ".",
        ],
        cwd=worktree,
    )
    generated_paths = verify_graphify_generated_only(worktree)
    status_raw = run(
        ["node", str(GSD_TOOLS), "graphify", "status"], cwd=worktree
    ).stdout.strip()
    query_raw = run(
        [
            "node",
            str(GSD_TOOLS),
            "graphify",
            "query",
            "phase 59 qwen3 embedding reranker 1024 cutover",
        ],
        cwd=worktree,
    ).stdout.strip()
    head = run(["git", "-C", str(worktree), "rev-parse", "HEAD"]).stdout.strip()
    evidence = parse_graphify_evidence(
        status_raw, query_raw, commit=commit, worktree_head=head
    )
    evidence["verification_worktree"] = str(worktree)
    evidence["generated_paths"] = generated_paths
    return evidence


def doctor(
    repo: Path,
    bundle_path: Path,
    worktree: Path,
    receipt_path: Path,
    executor_mode: str,
    executor_owner: str,
) -> dict[str, Any]:
    if executor_mode not in {"autopilot", "execute-phase-fallback"}:
        raise BootstrapError("executor_mode is invalid")
    assert_external_output(receipt_path, repo, worktree)
    bundle = prepare_worktree(repo, bundle_path, worktree)
    graphify = graphify_doctor(repo, bundle["final_execution_commit"])
    # Graphify refresh runs only in a detached verification worktree. The signed
    # execution branch must remain byte-identical and clean.
    verify_worktree(repo, bundle, worktree)
    bundle_sha256 = sha256_bytes(bundle_path.read_bytes())
    executor_lock = create_or_verify_executor_lock(
        EXECUTOR_LOCK,
        executor_mode=executor_mode,
        executor_owner=executor_owner,
        bundle_sha256=bundle_sha256,
        base_commit=bundle["final_execution_commit"],
    )
    receipt = {
        "schema_version": 1,
        "phase": PHASE,
        "workstream": WORKSTREAM,
        "status": "BOOTSTRAP_PASS",
        "final_execution_commit": bundle["final_execution_commit"],
        "bundle_sha256": bundle_sha256,
        "executor_mode": executor_mode,
        "executor_owner": executor_lock["executor_owner"],
        "executor_lock_sha256": sha256_bytes(EXECUTOR_LOCK.read_bytes()),
        "worktree": str(worktree),
        "worktree_head": bundle["final_execution_commit"],
        "graphify": graphify,
        "codex_skill_invoked": False,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    atomic_json(receipt_path, receipt)
    return receipt


def verify_runtime(
    repo: Path,
    bundle_path: Path,
    worktree: Path,
    receipt_path: Path,
    executor_owner: str,
) -> dict[str, Any]:
    bundle = verify_bundle(repo, bundle_path, require_remote_tip=False)
    receipt = load_json(
        assert_absolute_non_symlink(receipt_path, must_exist=True)
    )
    bundle_sha256 = sha256_bytes(bundle_path.read_bytes())
    expected_receipt = {
        "status": "BOOTSTRAP_PASS",
        "final_execution_commit": bundle["final_execution_commit"],
        "bundle_sha256": bundle_sha256,
        "worktree": str(EXECUTION_WORKTREE),
        "executor_owner": validate_executor_owner(executor_owner),
    }
    for key, value in expected_receipt.items():
        if receipt.get(key) != value:
            raise BootstrapError(f"runtime bootstrap receipt {key} mismatch")
    executor_mode = receipt.get("executor_mode")
    if executor_mode not in {"autopilot", "execute-phase-fallback"}:
        raise BootstrapError("runtime executor mode is invalid")
    expected_lock = create_or_verify_executor_lock(
        EXECUTOR_LOCK,
        executor_mode=executor_mode,
        executor_owner=executor_owner,
        bundle_sha256=bundle_sha256,
        base_commit=bundle["final_execution_commit"],
    )
    if receipt.get("executor_lock_sha256") != sha256_bytes(EXECUTOR_LOCK.read_bytes()):
        raise BootstrapError("executor lock hash differs from bootstrap receipt")
    head = verify_runtime_worktree(repo, bundle, worktree)
    return {
        "status": "RUNTIME_PASS",
        "executor_mode": executor_mode,
        "executor_owner": expected_lock["executor_owner"],
        "base_commit": bundle["final_execution_commit"],
        "current_head": head,
        "bundle_sha256": bundle_sha256,
        "executor_lock_sha256": sha256_bytes(EXECUTOR_LOCK.read_bytes()),
        "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def validate_behavior_transcript(
    transcript: dict[str, Any],
    *,
    expected_binding: dict[str, Any],
) -> None:
    for key, value in expected_binding.items():
        if transcript.get(key) != value:
            raise BootstrapError(f"behavior transcript {key} mismatch")
    checks = transcript.get("checks")
    if not isinstance(checks, list) or len(checks) != 2:
        raise BootstrapError("behavior transcript must contain exactly two checks")
    checks_by_name = {
        check.get("name"): check for check in checks if isinstance(check, dict)
    }
    if set(checks_by_name) != {
        "resume-existing-original-uid",
        "summary-then-dispatch-next-plan",
    }:
        raise BootstrapError("behavior transcript check set mismatch")
    resume_check = checks_by_name["resume-existing-original-uid"]
    summary_check = checks_by_name["summary-then-dispatch-next-plan"]
    for check in (resume_check, summary_check):
        if (
            check.get("status") != "PASS"
            or check.get("exit_code") != 0
            or not isinstance(check.get("argv_sha256"), str)
            or not SHA256_RE.fullmatch(check["argv_sha256"])
            or not isinstance(check.get("stdout_sha256"), str)
            or not SHA256_RE.fullmatch(check["stdout_sha256"])
        ):
            raise BootstrapError("behavior transcript check result is invalid")
    if resume_check.get("observed") != {
        "original_uid_preserved": True,
        "redispatch_count": 0,
        "resume_handoff_count": 1,
    }:
        raise BootstrapError("resume behavior transcript result mismatch")
    if summary_check.get("observed") != {
        "summary_created": True,
        "next_plan_dispatched": True,
        "dispatch_count": 1,
    }:
        raise BootstrapError("summary dispatch transcript result mismatch")


def combine_skill_doctor_receipt(
    bootstrap_receipt_path: Path,
    doctor_result_path: Path,
    task_root: Path,
    output: Path,
) -> dict[str, Any]:
    bootstrap = load_json(
        assert_absolute_non_symlink(bootstrap_receipt_path, must_exist=True)
    )
    doctor_result_path = assert_absolute_non_symlink(
        doctor_result_path, must_exist=True
    )
    task_root = assert_absolute_non_symlink(task_root, must_exist=True)
    if task_root != EXECUTION_WORKTREE:
        raise BootstrapError("skill doctor task root is not the Phase 59 worktree")
    doctor_result = load_json(doctor_result_path)
    for required in (AUTOPILOT_SKILL, AUTOPILOT_WORKFLOW, EXECUTOR_LOCK):
        assert_absolute_non_symlink(required, must_exist=True)
    executor_lock, executor_lock_sha256 = verify_executor_lock_against_receipt(
        EXECUTOR_LOCK,
        bootstrap,
        required_mode="autopilot",
    )
    skill_sha256 = sha256_bytes(AUTOPILOT_SKILL.read_bytes())
    workflow_sha256 = sha256_bytes(AUTOPILOT_WORKFLOW.read_bytes())
    transcript_path_raw = doctor_result.get("behavior_fixture_transcript_path")
    if not isinstance(transcript_path_raw, str):
        raise BootstrapError("skill doctor behavior transcript path is missing")
    transcript_path = assert_absolute_non_symlink(
        Path(transcript_path_raw), must_exist=True
    )
    assert_external_output(transcript_path, OWNER_REPO, EXECUTION_WORKTREE)
    transcript_sha256 = sha256_bytes(transcript_path.read_bytes())
    if doctor_result.get("behavior_fixture_transcript_sha256") != transcript_sha256:
        raise BootstrapError("skill doctor behavior transcript hash mismatch")
    transcript = load_json(transcript_path)
    expected_transcript = {
        "schema_version": 1,
        "fixture_suite": "gsd-execute-autopilot-resume-summary-v1",
        "status": "PASS",
        "task_root": str(EXECUTION_WORKTREE),
        "bundle_sha256": bootstrap.get("bundle_sha256"),
        "final_execution_commit": bootstrap.get("final_execution_commit"),
        "executor_owner": executor_lock["executor_owner"],
        "executor_lock_sha256": executor_lock_sha256,
        "skill_sha256": skill_sha256,
        "workflow_sha256": workflow_sha256,
    }
    validate_behavior_transcript(transcript, expected_binding=expected_transcript)
    expected = {
        "status": "PASS",
        "skill": "gsd-execute-autopilot",
        "workstream": WORKSTREAM,
        "task_root": str(EXECUTION_WORKTREE),
        "bundle_sha256": bootstrap.get("bundle_sha256"),
        "final_execution_commit": bootstrap.get("final_execution_commit"),
        "executor_mode": "autopilot",
        "executor_owner": executor_lock["executor_owner"],
        "executor_lock_sha256": executor_lock_sha256,
        "skill_sha256": skill_sha256,
        "workflow_sha256": workflow_sha256,
        "resume_capability": True,
        "behavior_fixture_transcript_path": str(transcript_path),
        "behavior_fixture_transcript_sha256": transcript_sha256,
    }
    if bootstrap.get("status") != "BOOTSTRAP_PASS":
        raise BootstrapError("bootstrap receipt is not PASS")
    if bootstrap.get("executor_mode") != "autopilot":
        raise BootstrapError("skill doctor can combine only an autopilot bootstrap")
    for key, value in expected.items():
        if doctor_result.get(key) != value:
            raise BootstrapError(f"skill doctor result {key} mismatch")
    assert_external_output(output, OWNER_REPO, EXECUTION_WORKTREE)
    combined = {
        "schema_version": 1,
        "phase": PHASE,
        "workstream": WORKSTREAM,
        "status": "PASS",
        "bundle_sha256": bootstrap["bundle_sha256"],
        "final_execution_commit": bootstrap["final_execution_commit"],
        "task_root": str(task_root),
        "executor_mode": "autopilot",
        "executor_owner": executor_lock["executor_owner"],
        "executor_lock_sha256": executor_lock_sha256,
        "skill_sha256": skill_sha256,
        "workflow_sha256": workflow_sha256,
        "resume_capability": True,
        "behavior_fixture_transcript_path": str(transcript_path),
        "behavior_fixture_transcript_sha256": transcript_sha256,
        "bootstrap_receipt_sha256": sha256_bytes(bootstrap_receipt_path.read_bytes()),
        "skill_doctor_result_sha256": sha256_bytes(doctor_result_path.read_bytes()),
        "skill_doctor_pass": True,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    atomic_json(output, combined)
    return combined


def validate_fallback_transition_inputs(
    bootstrap: dict[str, Any],
    failure: dict[str, Any],
    *,
    bundle_sha256: str,
    final_execution_commit: str,
    executor_owner: str,
    skill_sha256: str,
    workflow_sha256: str,
) -> None:
    expected_bootstrap = {
        "status": "BOOTSTRAP_PASS",
        "executor_mode": "autopilot",
        "executor_owner": validate_executor_owner(executor_owner),
        "bundle_sha256": bundle_sha256,
        "final_execution_commit": final_execution_commit,
        "worktree": str(EXECUTION_WORKTREE),
    }
    for key, value in expected_bootstrap.items():
        if bootstrap.get(key) != value:
            raise BootstrapError(f"fallback bootstrap {key} mismatch")
    expected_failure = {
        "skill": "gsd-execute-autopilot",
        "workstream": WORKSTREAM,
        "task_root": str(EXECUTION_WORKTREE),
        "bundle_sha256": bundle_sha256,
        "final_execution_commit": final_execution_commit,
        "executor_mode": "autopilot",
        "executor_owner": executor_owner,
        "skill_sha256": skill_sha256,
        "workflow_sha256": workflow_sha256,
        "wave0_started": False,
    }
    if failure.get("status") not in {"FAIL", "BLOCK"}:
        raise BootstrapError("fallback requires an explicit failed skill-doctor receipt")
    for key, value in expected_failure.items():
        if failure.get(key) != value:
            raise BootstrapError(f"skill-doctor failure {key} mismatch")


def transition_to_fallback(
    repo: Path,
    bundle_path: Path,
    worktree: Path,
    bootstrap_receipt_path: Path,
    skill_failure_path: Path,
    output: Path,
    executor_owner: str,
    *,
    executor_lock_path: Path = EXECUTOR_LOCK,
    combined_receipt_path: Path = COMBINED_RECEIPT,
) -> dict[str, Any]:
    """Perform the sole legal pre-Wave-0 autopilot-to-fallback ownership change."""
    bundle = verify_bundle(repo, bundle_path, require_remote_tip=False)
    verify_worktree(repo, bundle, worktree)
    assert_external_output(output, repo, worktree)
    assert_external_output(executor_lock_path, repo, worktree)
    assert_external_output(combined_receipt_path, repo, worktree)
    if combined_receipt_path.exists():
        raise BootstrapError("combined autopilot receipt exists; fallback is forbidden")
    for forbidden in ("59-WAVE-0-GATE.json", "59-01-SUMMARY.md"):
        if (worktree / PHASE_DIR / forbidden).exists():
            raise BootstrapError(f"Wave 0 already started: {forbidden}")
    bootstrap = load_json(
        assert_absolute_non_symlink(bootstrap_receipt_path, must_exist=True)
    )
    failure = load_json(
        assert_absolute_non_symlink(skill_failure_path, must_exist=True)
    )
    for required in (AUTOPILOT_SKILL, AUTOPILOT_WORKFLOW):
        assert_absolute_non_symlink(required, must_exist=True)
    bundle_sha256 = sha256_bytes(bundle_path.read_bytes())
    skill_sha256 = sha256_bytes(AUTOPILOT_SKILL.read_bytes())
    workflow_sha256 = sha256_bytes(AUTOPILOT_WORKFLOW.read_bytes())
    validate_fallback_transition_inputs(
        bootstrap,
        failure,
        bundle_sha256=bundle_sha256,
        final_execution_commit=bundle["final_execution_commit"],
        executor_owner=executor_owner,
        skill_sha256=skill_sha256,
        workflow_sha256=workflow_sha256,
    )
    old_lock, old_lock_sha256 = verify_executor_lock_against_receipt(
        executor_lock_path,
        bootstrap,
        required_mode="autopilot",
    )
    fallback_lock = {
        **old_lock,
        "executor_mode": "execute-phase-fallback",
    }
    atomic_json(executor_lock_path, fallback_lock)
    fallback_receipt = {
        "schema_version": 1,
        "phase": PHASE,
        "workstream": WORKSTREAM,
        "status": "BOOTSTRAP_PASS",
        "final_execution_commit": bundle["final_execution_commit"],
        "bundle_sha256": bundle_sha256,
        "executor_mode": "execute-phase-fallback",
        "executor_owner": executor_owner,
        "executor_lock_sha256": sha256_bytes(executor_lock_path.read_bytes()),
        "superseded_autopilot_lock_sha256": old_lock_sha256,
        "skill_doctor_failure_sha256": sha256_bytes(skill_failure_path.read_bytes()),
        "worktree": str(worktree),
        "worktree_head": bundle["final_execution_commit"],
        "wave0_started": False,
        "codex_skill_invoked": False,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    atomic_json(output, fallback_receipt)
    return fallback_receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    bundle = sub.add_parser("bundle")
    bundle.add_argument("--repo", type=Path, required=True)
    bundle.add_argument("--commit", required=True)
    bundle.add_argument("--output", type=Path, required=True)
    bundle.add_argument("--remote", required=True)
    bundle.add_argument("--branch", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--repo", type=Path, required=True)
    verify.add_argument("--bundle", type=Path, required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repo", type=Path, default=OWNER_REPO)
    prepare.add_argument("--bundle", type=Path, required=True)
    prepare.add_argument("--worktree", type=Path, default=EXECUTION_WORKTREE)
    check = sub.add_parser("doctor")
    check.add_argument("--repo", type=Path, default=OWNER_REPO)
    check.add_argument("--bundle", type=Path, required=True)
    check.add_argument("--worktree", type=Path, default=EXECUTION_WORKTREE)
    check.add_argument(
        "--receipt",
        type=Path,
        default=EXTERNAL_STATE / "59-AUTOPILOT-BOOTSTRAP-RECEIPT.json",
    )
    check.add_argument(
        "--executor-mode",
        choices=("autopilot", "execute-phase-fallback"),
        required=True,
    )
    check.add_argument("--executor-owner", required=True)
    runtime = sub.add_parser("verify-runtime")
    runtime.add_argument("--repo", type=Path, default=OWNER_REPO)
    runtime.add_argument("--bundle", type=Path, required=True)
    runtime.add_argument("--worktree", type=Path, default=EXECUTION_WORKTREE)
    runtime.add_argument("--bootstrap-receipt", type=Path, required=True)
    runtime.add_argument("--executor-owner", required=True)
    runtime.add_argument(
        "--output",
        type=Path,
        default=EXTERNAL_STATE / "59-RUNTIME-RECEIPT.json",
    )
    combine = sub.add_parser("combine-skill-doctor")
    combine.add_argument("--bootstrap-receipt", type=Path, required=True)
    combine.add_argument("--doctor-result", type=Path, required=True)
    combine.add_argument("--task-root", type=Path, default=EXECUTION_WORKTREE)
    combine.add_argument(
        "--output",
        type=Path,
        default=COMBINED_RECEIPT,
    )
    fallback = sub.add_parser("transition-fallback")
    fallback.add_argument("--repo", type=Path, default=OWNER_REPO)
    fallback.add_argument("--bundle", type=Path, required=True)
    fallback.add_argument("--worktree", type=Path, default=EXECUTION_WORKTREE)
    fallback.add_argument("--bootstrap-receipt", type=Path, required=True)
    fallback.add_argument("--skill-doctor-failure", type=Path, required=True)
    fallback.add_argument("--executor-owner", required=True)
    fallback.add_argument(
        "--output",
        type=Path,
        default=EXTERNAL_STATE / "59-FALLBACK-BOOTSTRAP-RECEIPT.json",
    )
    return result


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "bundle":
            create_bundle(args.repo, args.commit, args.output, args.remote, args.branch)
        elif args.command == "verify":
            verify_bundle(args.repo, args.bundle)
        elif args.command == "prepare":
            prepare_worktree(args.repo, args.bundle, args.worktree)
        elif args.command == "doctor":
            doctor(
                args.repo,
                args.bundle,
                args.worktree,
                args.receipt,
                args.executor_mode,
                args.executor_owner,
            )
        elif args.command == "verify-runtime":
            runtime_receipt = verify_runtime(
                args.repo,
                args.bundle,
                args.worktree,
                args.bootstrap_receipt,
                args.executor_owner,
            )
            assert_external_output(args.output, args.repo, args.worktree)
            atomic_json(args.output, runtime_receipt)
        elif args.command == "combine-skill-doctor":
            combine_skill_doctor_receipt(
                args.bootstrap_receipt,
                args.doctor_result,
                args.task_root,
                args.output,
            )
        elif args.command == "transition-fallback":
            transition_to_fallback(
                args.repo,
                args.bundle,
                args.worktree,
                args.bootstrap_receipt,
                args.skill_doctor_failure,
                args.output,
                args.executor_owner,
            )
        else:
            raise BootstrapError(f"unsupported command: {args.command}")
    except BootstrapError as exc:
        print(f"BLOCK: {exc}", file=sys.stderr)
        return 2
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
