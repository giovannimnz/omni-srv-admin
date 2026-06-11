from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from fork_sync.core import sync_runner


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.name", "Test User")
    _git(path, "config", "user.email", "test@example.com")


def _commit_file(repo: Path, rel: str, content: str, message: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", message)


def _clone(src: Path, dest: Path) -> None:
    subprocess.run(["git", "clone", str(src), str(dest)], check=True, capture_output=True, text=True)
    _git(dest, "config", "user.name", "Test User")
    _git(dest, "config", "user.email", "test@example.com")


@pytest.fixture
def repo_pair(tmp_path: Path) -> tuple[Path, Path]:
    upstream = tmp_path / "upstream"
    fork = tmp_path / "fork"
    _init_repo(upstream)
    _commit_file(upstream, "README.md", "base\n", "base")
    _commit_file(upstream, "src/app.txt", "base\n", "base app")
    _clone(upstream, fork)
    subprocess.run(["git", "remote", "rename", "origin", "upstream"], cwd=fork, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(fork)], cwd=fork, check=True)
    return upstream, fork


def _cfg(upstream: Path, fork: Path, protected_paths: list[str]) -> dict:
    return {
        "upstream": str(upstream),
        "upstream_branch": "main",
        "fork": str(fork),
        "protected_paths": protected_paths,
        "merge_strategy": "theirs",
    }


def test_run_sync_restores_protected_files_after_merge(monkeypatch, repo_pair):
    upstream, fork = repo_pair
    _commit_file(fork, "README.md", "fork readme\n", "fork custom readme")
    _commit_file(upstream, "README.md", "upstream readme\n", "upstream readme")
    _commit_file(upstream, "src/app.txt", "upstream app\n", "upstream app")

    monkeypatch.setattr(sync_runner, "load_project", lambda name: _cfg(upstream, fork, ["README.md"]))

    result = sync_runner.run_sync("atius-router")

    assert result["status"] == "success"
    assert (fork / "README.md").read_text(encoding="utf-8") == "fork readme\n"
    assert (fork / "src/app.txt").read_text(encoding="utf-8") == "upstream app\n"
    assert not (fork / ".git" / "MERGE_HEAD").exists()


def test_run_sync_aborts_for_unprotected_conflicts(monkeypatch, repo_pair):
    upstream, fork = repo_pair
    _commit_file(fork, "src/app.txt", "fork app\n", "fork app change")
    _commit_file(upstream, "src/app.txt", "upstream app\n", "upstream app change")

    monkeypatch.setattr(sync_runner, "load_project", lambda name: _cfg(upstream, fork, []))

    result = sync_runner.run_sync("atius-router")

    assert result["status"] == "error"
    assert "protected_paths" in result["error"]
    assert not (fork / ".git" / "MERGE_HEAD").exists()
    assert (fork / "src/app.txt").read_text(encoding="utf-8") == "fork app\n"


def test_run_sync_dry_run_reports_dirty_and_stale_paths(monkeypatch, repo_pair):
    upstream, fork = repo_pair
    (fork / "README.md").write_text("dirty\n", encoding="utf-8")
    _commit_file(upstream, "src/app.txt", "upstream app v2\n", "upstream app v2")

    monkeypatch.setattr(
        sync_runner,
        "load_project",
        lambda name: _cfg(upstream, fork, ["README.md", "missing/path.txt"]),
    )

    result = sync_runner.run_sync("atius-router", dry_run=True)

    assert result["status"] == "success"
    assert result["can_apply"] is False
    assert "README.md" in result["dirty_files"]
    assert "missing/path.txt" in result["stale_protected_paths"]
