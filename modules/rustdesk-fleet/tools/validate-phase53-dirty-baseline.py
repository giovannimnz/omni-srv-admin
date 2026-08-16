#!/usr/bin/env python3
"""Seal and verify the Phase 53 carry-forward dirty-file baseline."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
READ_CHUNK = 1024 * 1024
CAPTURED_PATHS = (
    "modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json",
    "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py",
    "modules/rustdesk-fleet/tools/build-phase53-authority-plan.py",
    "modules/rustdesk-fleet/tools/phase53-live-backend.py",
    "modules/rustdesk-fleet/tools/run-phase53-live-gate.py",
    "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py",
    "modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py",
)
SOURCE_PATHS = frozenset(
    {
        ".planning/workstreams/rustdesk-fleet/phases/"
        "53-primary-relay-and-public-edge/53-05D2Q-DIRTY-BASELINE.json",
        "modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py",
        "modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py",
    }
)
SUMMARY_PATH = (
    ".planning/workstreams/rustdesk-fleet/phases/"
    "53-primary-relay-and-public-edge/53-05D2Q-SUMMARY.md"
)
TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "captured_at",
        "captured_head",
        "path_count",
        "paths",
        "baseline_sha256",
    }
)
ENTRY_FIELDS = frozenset(
    {"path", "tracked", "xy", "file_type", "mode", "size", "sha256"}
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)


class ValidationError(Exception):
    """Expected fail-closed validation error."""


def _run_git(repo: Path, args: Iterable[str], *, check: bool = True) -> bytes:
    completed = subprocess.run(
        ["git", "-C", os.fspath(repo), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode != 0:
        raise ValidationError("git command failed")
    if not check and completed.returncode not in (0, 1):
        raise ValidationError("git command failed")
    return completed.stdout


def _head(repo: Path) -> str:
    raw = _run_git(repo, ["rev-parse", "--verify", "HEAD"])
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ValidationError("invalid HEAD") from exc
    if not COMMIT_RE.fullmatch(value):
        raise ValidationError("invalid HEAD")
    return value


def _validate_literal_path(path: str) -> tuple[str, ...]:
    if not path or "\x00" in path:
        raise ValidationError("invalid path")
    candidate = Path(path)
    if candidate.is_absolute():
        raise ValidationError("absolute path")
    parts = candidate.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValidationError("unconfined path")
    return parts


def _open_parent_dir(repo_fd: int, path: str) -> tuple[int, str]:
    parts = _validate_literal_path(path)
    current = os.dup(repo_fd)
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        for part in parts[:-1]:
            next_fd = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = next_fd
        return current, parts[-1]
    except Exception:
        os.close(current)
        raise


def _file_observation(repo_fd: int, path: str) -> dict[str, Any]:
    parent_fd, name = _open_parent_dir(repo_fd, path)
    descriptor = -1
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ValidationError("captured path is not a regular file")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, dir_fd=parent_fd)
        opened = os.fstat(descriptor)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
        )
        identity_opened = (
            opened.st_dev,
            opened.st_ino,
            opened.st_mode,
            opened.st_size,
            opened.st_mtime_ns,
        )
        if identity_before != identity_opened or not stat.S_ISREG(opened.st_mode):
            raise ValidationError("file identity changed before read")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, READ_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
        )
        final_lstat = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        identity_lstat = (
            final_lstat.st_dev,
            final_lstat.st_ino,
            final_lstat.st_mode,
            final_lstat.st_size,
            final_lstat.st_mtime_ns,
        )
        if identity_after != identity_opened or identity_lstat != identity_opened:
            raise ValidationError("file identity changed during read")
        return {
            "file_type": "regular",
            "mode": stat.S_IMODE(opened.st_mode),
            "size": opened.st_size,
            "sha256": digest.hexdigest(),
        }
    except OSError as exc:
        raise ValidationError("unsafe captured path") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def _tracked(repo: Path, path: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", os.fspath(repo), "ls-files", "--error-unmatch", "--", path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise ValidationError("git ls-files failed")


def _xy(repo: Path, path: str) -> str:
    raw = _run_git(
        repo,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", path],
    )
    encoded_path = os.fsencode(path)
    expected_suffix = b" " + encoded_path + b"\x00"
    if len(raw) != len(expected_suffix) + 2 or raw[2:] != expected_suffix:
        raise ValidationError("captured path must have exactly one status record")
    xy_raw = raw[:2]
    if b"\x00" in xy_raw:
        raise ValidationError("invalid XY")
    try:
        return xy_raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationError("invalid XY") from exc


def _observe_pass(repo: Path) -> dict[str, Any]:
    first_head = _head(repo)
    repo_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
    repo_flags |= getattr(os, "O_NOFOLLOW", 0)
    repo_fd = os.open(repo, repo_flags)
    try:
        entries = []
        for path in CAPTURED_PATHS:
            entry = {
                "path": path,
                "tracked": _tracked(repo, path),
                "xy": _xy(repo, path),
            }
            entry.update(_file_observation(repo_fd, path))
            entries.append(entry)
    finally:
        os.close(repo_fd)
    second_head = _head(repo)
    if first_head != second_head:
        raise ValidationError("HEAD changed during observation")
    return {"captured_head": first_head, "paths": entries}


def _stable_observation(repo: Path) -> dict[str, Any]:
    first = _observe_pass(repo)
    second = _observe_pass(repo)
    if first != second:
        raise ValidationError("two-pass observation mismatch")
    return first


def _canonical_without_digest(payload: dict[str, Any]) -> bytes:
    unsigned = dict(payload)
    unsigned.pop("baseline_sha256", None)
    return json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _baseline_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_without_digest(payload)).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON key")
        result[key] = value
    return result


def _load_baseline(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("invalid baseline") from exc
    if not isinstance(payload, dict) or frozenset(payload) != TOP_LEVEL_FIELDS:
        raise ValidationError("invalid top-level schema")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValidationError("invalid schema version")
    if not isinstance(payload["captured_at"], str) or not RFC3339_UTC_RE.fullmatch(
        payload["captured_at"]
    ):
        raise ValidationError("invalid captured_at")
    try:
        parsed_at = dt.datetime.fromisoformat(
            payload["captured_at"].removesuffix("Z") + "+00:00"
        )
    except ValueError as exc:
        raise ValidationError("invalid captured_at") from exc
    if parsed_at.utcoffset() != dt.timedelta(0):
        raise ValidationError("captured_at is not UTC")
    if not isinstance(payload["captured_head"], str) or not COMMIT_RE.fullmatch(
        payload["captured_head"]
    ):
        raise ValidationError("invalid captured_head")
    if type(payload["path_count"]) is not int or payload["path_count"] != len(
        CAPTURED_PATHS
    ):
        raise ValidationError("invalid path_count")
    entries = payload["paths"]
    if not isinstance(entries, list) or len(entries) != len(CAPTURED_PATHS):
        raise ValidationError("invalid paths")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or frozenset(entry) != ENTRY_FIELDS:
            raise ValidationError("invalid path entry schema")
        path_value = entry["path"]
        if not isinstance(path_value, str) or path_value in seen:
            raise ValidationError("duplicate or invalid path")
        seen.add(path_value)
        if type(entry["tracked"]) is not bool:
            raise ValidationError("invalid tracked")
        if (
            not isinstance(entry["xy"], str)
            or len(entry["xy"]) != 2
            or "\x00" in entry["xy"]
        ):
            raise ValidationError("invalid XY")
        if entry["file_type"] != "regular":
            raise ValidationError("invalid file type")
        if type(entry["mode"]) is not int or not 0 <= entry["mode"] <= 0o7777:
            raise ValidationError("invalid mode")
        if type(entry["size"]) is not int or entry["size"] < 0:
            raise ValidationError("invalid size")
        if not isinstance(entry["sha256"], str) or not SHA256_RE.fullmatch(
            entry["sha256"]
        ):
            raise ValidationError("invalid sha256")
    if seen != set(CAPTURED_PATHS):
        raise ValidationError("baseline path set mismatch")
    if not isinstance(payload["baseline_sha256"], str) or not SHA256_RE.fullmatch(
        payload["baseline_sha256"]
    ):
        raise ValidationError("invalid baseline digest")
    if payload["baseline_sha256"] != _baseline_digest(payload):
        raise ValidationError("baseline digest mismatch")
    return payload


def _observation_matches(payload: dict[str, Any], observed: dict[str, Any]) -> None:
    if observed["captured_head"] != payload["captured_head"]:
        raise ValidationError("captured HEAD mismatch")
    if observed["paths"] != payload["paths"]:
        raise ValidationError("dirty baseline mismatch")


def _write_create_only(path: Path, payload: dict[str, Any]) -> None:
    parent = path.parent
    parent_fd = os.open(
        parent,
        os.O_RDONLY
        | os.O_DIRECTORY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    descriptor = -1
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        os.fchmod(descriptor, 0o600)
        encoded = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ValidationError("short baseline write")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.fsync(parent_fd)
    except FileExistsError as exc:
        raise ValidationError("baseline already exists") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def capture(repo: Path, baseline: Path) -> None:
    observed = _stable_observation(repo)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "captured_head": observed["captured_head"],
        "path_count": len(CAPTURED_PATHS),
        "paths": observed["paths"],
    }
    payload["baseline_sha256"] = _baseline_digest(payload)
    _write_create_only(baseline, payload)


def _commit_parents(repo: Path, commit: str) -> tuple[str, list[str]]:
    raw = _run_git(repo, ["rev-list", "--parents", "-n", "1", commit])
    try:
        parts = raw.decode("ascii").strip().split()
    except UnicodeDecodeError as exc:
        raise ValidationError("invalid commit") from exc
    if not parts or any(not COMMIT_RE.fullmatch(part) for part in parts):
        raise ValidationError("invalid commit")
    return parts[0], parts[1:]


def _commit_paths(repo: Path, commit: str) -> frozenset[str]:
    raw = _run_git(
        repo,
        ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", commit],
    )
    items = raw.split(b"\x00")
    if items and items[-1] == b"":
        items.pop()
    try:
        decoded = [item.decode("utf-8") for item in items]
    except UnicodeDecodeError as exc:
        raise ValidationError("invalid commit path") from exc
    if len(decoded) != len(set(decoded)):
        raise ValidationError("duplicate commit path")
    return frozenset(decoded)


def _is_ancestor(repo: Path, ancestor: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", os.fspath(repo), "merge-base", "--is-ancestor", ancestor, "HEAD"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise ValidationError("git ancestry check failed")
    return completed.returncode == 0


def _source_child_exists(repo: Path, captured_head: str) -> bool:
    raw = _run_git(repo, ["rev-list", "--all", "--parents"])
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValidationError("invalid git history") from exc
    for line in lines:
        parts = line.split()
        if len(parts) == 2 and parts[1] == captured_head:
            if _commit_paths(repo, parts[0]) == SOURCE_PATHS:
                return True
    return False


def exact(repo: Path, baseline: Path) -> None:
    payload = _load_baseline(baseline)
    if _head(repo) != payload["captured_head"]:
        raise ValidationError("exact is only legal at captured HEAD")
    if _source_child_exists(repo, payload["captured_head"]):
        raise ValidationError("exact is forbidden after source commit exists")
    _observation_matches(payload, _stable_observation(repo))


def ancestor(
    repo: Path,
    baseline: Path,
    source_commit: str,
    summary_commit: str | None,
    summary_path: str | None,
) -> None:
    if (summary_commit is None) != (summary_path is None):
        raise ValidationError("summary arguments must be paired")
    payload = _load_baseline(baseline)
    observed = _stable_observation(repo)
    if observed["paths"] != payload["paths"]:
        raise ValidationError("dirty baseline mismatch")
    resolved_source, source_parents = _commit_parents(repo, source_commit)
    if len(source_parents) != 1 or source_parents[0] != payload["captured_head"]:
        raise ValidationError("invalid source parent")
    if _commit_paths(repo, resolved_source) != SOURCE_PATHS:
        raise ValidationError("invalid source diff")
    if not _is_ancestor(repo, resolved_source):
        raise ValidationError("source is not an ancestor of HEAD")
    if summary_commit is not None:
        if summary_path != SUMMARY_PATH:
            raise ValidationError("invalid summary path")
        resolved_summary, summary_parents = _commit_parents(repo, summary_commit)
        if len(summary_parents) != 1 or summary_parents[0] != resolved_source:
            raise ValidationError("invalid summary parent")
        if _commit_paths(repo, resolved_summary) != frozenset({SUMMARY_PATH}):
            raise ValidationError("invalid summary diff")
        if not _is_ancestor(repo, resolved_summary):
            raise ValidationError("summary is not an ancestor of HEAD")


def _absolute_repo(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValidationError("repo must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValidationError("invalid repo") from exc
    if not resolved.is_dir():
        raise ValidationError("repo is not a directory")
    return resolved


def _absolute_baseline(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValidationError("baseline must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("capture", "exact"):
        command = subparsers.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--baseline", required=True)
    command = subparsers.add_parser("ancestor")
    command.add_argument("--repo", required=True)
    command.add_argument("--baseline", required=True)
    command.add_argument("--source-commit", required=True)
    command.add_argument("--summary-commit")
    command.add_argument("--summary-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        repo = _absolute_repo(args.repo)
        baseline = _absolute_baseline(args.baseline)
        if args.command == "capture":
            capture(repo, baseline)
        elif args.command == "exact":
            exact(repo, baseline)
        else:
            ancestor(
                repo,
                baseline,
                args.source_commit,
                args.summary_commit,
                args.summary_path,
            )
        return 0
    except (ValidationError, OSError, ValueError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
