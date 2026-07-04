"""Version matrix and self-update helpers for omni-srv-admin fleet."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", str(Path(__file__).resolve().parents[2])))
DEFAULT_OMNI_VERSION_MATRIX = REPO / "modules" / "fleet-control-plane" / "configs" / "omni-version-matrix.json"
VERSION_RE = re.compile(r'__version__ = "([^"]+)"')

CollectorRunner = Callable[[list[str], Path | None, int], tuple[int, str, str]]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run(argv: list[str], cwd: Path | None = None, timeout: int = 30) -> tuple[int, str, str]:
    binary = argv[0]
    if os.path.sep not in binary and shutil.which(binary) is None:
        return 127, "", f"{binary}: command not found"
    completed = subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout,
    )
    return completed.returncode, completed.stdout, completed.stderr


def load_omni_version_matrix(source: Path = DEFAULT_OMNI_VERSION_MATRIX) -> dict[str, Any]:
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"manifest inválido: {source}")
    hosts = data.get("hosts")
    if not isinstance(hosts, dict):
        raise RuntimeError(f"manifest sem hosts válidos: {source}")
    target_hosts = data.get("target_hosts")
    if not isinstance(target_hosts, list):
        raise RuntimeError(f"manifest sem target_hosts válidos: {source}")
    data["source"] = str(source)
    return data


def _normalize_version(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw[1:] if raw.startswith("v") else raw


def _tag_name(value: str | None) -> str:
    normalized = _normalize_version(value)
    return f"v{normalized}" if normalized else ""


def _read_repo_version(repo_root: Path) -> str:
    init_file = repo_root / "cli" / "omni" / "__init__.py"
    if not init_file.exists():
        return ""
    match = VERSION_RE.search(init_file.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def _safe_git(
    repo_root: Path,
    *args: str,
    runner: CollectorRunner = _run,
    timeout: int = 30,
) -> tuple[int, str, str]:
    return runner(["git", *args], repo_root, timeout)


def collect_omni_version(
    host_id: str,
    *,
    repo_root: Path,
    github_repo: str,
    desired_version: str = "",
    track_branch: str = "main",
    runner: CollectorRunner = _run,
) -> dict[str, Any]:
    installed_version = _read_repo_version(repo_root)
    branch = ""
    commit = ""
    dirty = False
    observed_tag = ""
    current_branch_rc, current_branch_out, current_branch_err = _safe_git(
        repo_root, "rev-parse", "--abbrev-ref", "HEAD", runner=runner, timeout=10
    )
    if current_branch_rc == 0:
        branch = current_branch_out.strip()
    else:
        branch = f"error:{(current_branch_err or current_branch_out).strip()[:120]}"
    head_rc, head_out, head_err = _safe_git(repo_root, "rev-parse", "HEAD", runner=runner, timeout=10)
    if head_rc == 0:
        commit = head_out.strip()
    else:
        commit = f"error:{(head_err or head_out).strip()[:120]}"
    status_rc, status_out, _ = _safe_git(repo_root, "status", "--porcelain", runner=runner, timeout=20)
    if status_rc == 0:
        dirty = bool(status_out.strip())
    tag_rc, tag_out, _ = _safe_git(repo_root, "describe", "--tags", "--exact-match", runner=runner, timeout=10)
    if tag_rc == 0:
        observed_tag = tag_out.strip()

    github_commit = ""
    tag_name = _tag_name(desired_version)
    if tag_name:
        tag_commit_rc, tag_commit_out, _ = _safe_git(repo_root, "rev-list", "-n", "1", tag_name, runner=runner, timeout=10)
        if tag_commit_rc == 0:
            github_commit = tag_commit_out.strip()

    return {
        "host": host_id,
        "component": "omni-srv-admin",
        "installed_version": installed_version or None,
        "git_branch": branch or None,
        "git_commit": commit or None,
        "git_dirty": dirty,
        "github_version": _normalize_version(desired_version) or None,
        "github_commit": github_commit or None,
        "source": "omni-fleet-agent",
        "observed_at": _now(),
        "metadata": {
            "github_repo": github_repo,
            "repo_root": str(repo_root),
            "track_branch": track_branch,
            "observed_tag": observed_tag or None,
        },
    }


def _default_backup_root(repo_root: Path) -> Path:
    home = Path.home()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "omni-srv-admin" / "backups"
    return home / ".backups" / repo_root.name


def apply_omni_self_update(
    host_id: str,
    *,
    repo_root: Path,
    desired_version: str,
    track_branch: str,
    github_repo: str,
    runner: CollectorRunner = _run,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = _default_backup_root(repo_root) / f"auto-update-{host_id}-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    def _write(name: str, data: str | None) -> None:
        (backup_dir / name).write_text(data or "", encoding="utf-8")

    pre = collect_omni_version(
        host_id,
        repo_root=repo_root,
        github_repo=github_repo,
        desired_version=desired_version,
        track_branch=track_branch,
        runner=runner,
    )
    _write("pre-state.json", json.dumps(pre, indent=2, sort_keys=True))

    _, status_text, _ = _safe_git(repo_root, "status", "--short", "--branch", runner=runner, timeout=20)
    _write("git-status.txt", status_text)
    _, diff_text, _ = _safe_git(repo_root, "diff", "--binary", runner=runner, timeout=60)
    _write("git-diff.patch", diff_text)

    stash_ref = ""
    if pre["git_dirty"]:
        stash_rc, stash_out, stash_err = _safe_git(
            repo_root,
            "stash",
            "push",
            "--include-untracked",
            "-m",
            f"omni-auto-update:{host_id}:{_tag_name(desired_version) or 'branch'}:{timestamp}",
            runner=runner,
            timeout=120,
        )
        if stash_rc != 0:
            return {
                "host": host_id,
                "status": "failed",
                "reason": "stash-failed",
                "backup_dir": str(backup_dir),
                "stderr": (stash_err or stash_out).strip()[:4000],
                "finished_at": _now(),
            }
        stash_ref = (stash_out or stash_err).strip()
        _write("git-stash.txt", stash_ref + "\n")

    fetch_rc, fetch_out, fetch_err = _safe_git(repo_root, "fetch", "origin", "--tags", runner=runner, timeout=180)
    if fetch_rc != 0:
        return {
            "host": host_id,
            "status": "failed",
            "reason": "fetch-failed",
            "backup_dir": str(backup_dir),
            "stderr": (fetch_err or fetch_out).strip()[:4000],
            "finished_at": _now(),
        }

    checkout_rc, checkout_out, checkout_err = _safe_git(repo_root, "checkout", track_branch, runner=runner, timeout=60)
    if checkout_rc != 0:
        create_rc, create_out, create_err = _safe_git(
            repo_root, "checkout", "-b", track_branch, f"origin/{track_branch}", runner=runner, timeout=60
        )
        if create_rc != 0:
            return {
                "host": host_id,
                "status": "failed",
                "reason": "checkout-failed",
                "backup_dir": str(backup_dir),
                "stderr": (create_err or create_out or checkout_err or checkout_out).strip()[:4000],
                "finished_at": _now(),
            }

    pull_rc, pull_out, pull_err = _safe_git(repo_root, "pull", "--ff-only", "origin", track_branch, runner=runner, timeout=180)
    if pull_rc != 0:
        return {
            "host": host_id,
            "status": "failed",
            "reason": "pull-failed",
            "backup_dir": str(backup_dir),
            "stderr": (pull_err or pull_out).strip()[:4000],
            "finished_at": _now(),
        }

    tag_name = _tag_name(desired_version)
    tag_missing_fallback = False
    if tag_name:
        verify_rc, _, verify_err = _safe_git(repo_root, "rev-parse", "--verify", tag_name, runner=runner, timeout=30)
        if verify_rc != 0:
            tag_missing_fallback = True
        else:
            head_rc, head_out, head_err = _safe_git(repo_root, "rev-parse", "HEAD", runner=runner, timeout=20)
            tag_rc, tag_out, tag_err = _safe_git(repo_root, "rev-list", "-n", "1", tag_name, runner=runner, timeout=20)
            if head_rc != 0 or tag_rc != 0:
                return {
                    "host": host_id,
                    "status": "failed",
                    "reason": "tag-compare-failed",
                    "backup_dir": str(backup_dir),
                    "stderr": " / ".join(part for part in [head_err.strip(), tag_err.strip()] if part)[:4000],
                    "finished_at": _now(),
                }
            if head_out.strip() != tag_out.strip():
                merge_rc, merge_out, merge_err = _safe_git(repo_root, "merge", "--ff-only", tag_name, runner=runner, timeout=120)
                if merge_rc != 0:
                    return {
                        "host": host_id,
                        "status": "failed",
                        "reason": "tag-merge-failed",
                        "backup_dir": str(backup_dir),
                        "stderr": (merge_err or merge_out).strip()[:4000],
                        "finished_at": _now(),
                    }

    post = collect_omni_version(
        host_id,
        repo_root=repo_root,
        github_repo=github_repo,
        desired_version=desired_version,
        track_branch=track_branch,
        runner=runner,
    )
    _write("post-state.json", json.dumps(post, indent=2, sort_keys=True))
    return {
        "host": host_id,
        "status": "succeeded",
        "backup_dir": str(backup_dir),
        "stashed": bool(stash_ref),
        "stash_ref": stash_ref or None,
        "tag_missing_fallback": tag_missing_fallback,
        "before": pre,
        "after": post,
        "finished_at": _now(),
    }
