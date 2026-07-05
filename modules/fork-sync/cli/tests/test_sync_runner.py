from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from fork_sync.core import sync_runner
from fork_sync.core import automerge
from fork_sync.core import container_mirrors


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


def test_run_sync_errors_when_fork_path_missing(monkeypatch, tmp_path):
    cwd = tmp_path / "cwd"
    _init_repo(cwd)
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(
        sync_runner,
        "load_project",
        lambda name: {
            "upstream": "https://example.invalid/upstream.git",
            "upstream_branch": "main",
            "protected_paths": [],
        },
    )

    result = sync_runner.run_sync("missing-fork", dry_run=True)

    assert result["status"] == "error"
    assert "fork path missing" in result["error"]
    assert _git(cwd, "remote") == ""


def test_run_sync_skips_paused_projects(monkeypatch):
    monkeypatch.setattr(
        sync_runner,
        "load_project",
        lambda name: {
            "enabled": False,
            "pause_reason": "maintenance window",
            "upstream": "https://example.invalid/upstream.git",
        },
    )

    result = sync_runner.run_sync("paused", dry_run=True)

    assert result["status"] == "skipped"
    assert result["message"] == "maintenance window"


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


def test_run_sync_dry_run_reports_version_and_post_sync_plan(monkeypatch, repo_pair):
    upstream, fork = repo_pair
    _commit_file(upstream, "src/app.txt", "upstream app v2\n", "upstream app v2")

    cfg = _cfg(upstream, fork, [])
    cfg["version_scheme"] = {
        "suffix": "-rf",
        "counter_dir": "~/.fork-sync/{project}/versions/{upstream_version}",
    }
    cfg["post_sync"] = {
        "enabled": True,
        "commands": [
            {
                "name": "tests",
                "command": ["python", "-c", "print('ok')"],
                "cwd": str(fork),
            }
        ],
    }
    monkeypatch.setattr(sync_runner, "load_project", lambda name: cfg)

    result = sync_runner.run_sync("notebooklm-py", dry_run=True)

    assert result["status"] == "success"
    assert result["version_plan"]["enabled"] is True
    assert result["version_plan"]["suffix"] == "-rf"
    assert result["post_sync_plan"]["enabled"] is True
    assert result["post_sync_plan"]["commands"][0]["name"] == "tests"
    assert "post_sync" not in result


def test_run_sync_dry_run_accepts_legacy_string_version_scheme(monkeypatch, repo_pair):
    upstream, fork = repo_pair
    _commit_file(upstream, "src/app.txt", "upstream app v2\n", "upstream app v2")

    cfg = _cfg(upstream, fork, [])
    cfg["version_scheme"] = "v{upstream_version}-rf{N}"
    monkeypatch.setattr(sync_runner, "load_project", lambda name: cfg)

    result = sync_runner.run_sync("atius-router", dry_run=True)

    assert result["status"] == "success"
    assert result["version_plan"]["enabled"] is True
    assert result["version_plan"]["tag_template"] == "v{upstream_version}-rf{N}"
    assert result["version_plan"]["suffix"] == ""


def test_run_sync_dry_run_includes_protected_globs(monkeypatch, repo_pair):
    upstream, fork = repo_pair
    _commit_file(fork, "docs/pt/index.md", "fork docs\n", "fork docs")
    _commit_file(upstream, "src/app.txt", "upstream app v2\n", "upstream app v2")

    monkeypatch.setattr(
        sync_runner,
        "load_project",
        lambda name: {
            "upstream": str(upstream),
            "upstream_branch": "main",
            "fork": str(fork),
            "protected_paths": [],
            "protected_globs": ["docs/pt/**"],
            "merge_strategy": "theirs",
        },
    )

    result = sync_runner.run_sync("docs", dry_run=True)

    assert result["status"] == "success"
    assert "docs/pt/index.md" in result["protected_files"]


def test_run_sync_runs_post_sync_hooks_after_merge(monkeypatch, repo_pair, tmp_path):
    upstream, fork = repo_pair
    marker = tmp_path / "hook-ran.txt"
    _commit_file(upstream, "src/app.txt", "upstream app v2\n", "upstream app v2")

    cfg = _cfg(upstream, fork, [])
    cfg["post_sync"] = {
        "enabled": True,
        "commands": [
            {
                "name": "marker",
                "command": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('hook-ran.txt').write_text('ok', encoding='utf-8')",
                ],
                "cwd": str(tmp_path),
            }
        ],
    }
    monkeypatch.setattr(sync_runner, "load_project", lambda name: cfg)

    result = sync_runner.run_sync("notebooklm-py")

    assert result["status"] == "success"
    assert result["post_sync"]["status"] == "success"
    assert result["post_sync"]["commands"][0]["exit_code"] == 0
    assert marker.read_text(encoding="utf-8") == "ok"


def test_run_sync_reports_push_failure_after_merge(monkeypatch, repo_pair, tmp_path):
    upstream, fork = repo_pair
    _commit_file(upstream, "src/app.txt", "upstream app v2\n", "upstream app v2")
    _git(fork, "remote", "set-url", "origin", str(tmp_path / "missing-origin.git"))

    cfg = _cfg(upstream, fork, [])
    cfg["auto_push"] = True
    monkeypatch.setattr(sync_runner, "load_project", lambda name: cfg)

    result = sync_runner.run_sync("notebooklm-py")

    assert result["status"] == "error"
    assert "push falhou" in result["error"]
    assert result["push_exit_code"] != 0


def test_run_sync_handles_ahead_only_without_empty_merge(monkeypatch, repo_pair):
    upstream, fork = repo_pair
    _commit_file(fork, "README.md", "fork readme\n", "fork-only change")

    monkeypatch.setattr(
        sync_runner,
        "load_project",
        lambda name: {
            "upstream": str(upstream),
            "upstream_branch": "main",
            "fork": str(fork),
            "protected_paths": ["README.md"],
            "merge_strategy": "theirs",
            "auto_push": False,
        },
    )

    before = _git(fork, "rev-parse", "HEAD")
    result = sync_runner.run_sync("ahead-only")
    after = _git(fork, "rev-parse", "HEAD")

    assert result["status"] == "success"
    assert "ahead by 1" in result["message"]
    assert before == after


def test_run_sync_all_applies_only_safe_projects(monkeypatch):
    calls = []

    monkeypatch.setattr(
        automerge,
        "list_projects",
        lambda only_enabled=True: [{"name": "safe"}, {"name": "dirty"}],
    )

    def fake_run_sync(name, dry_run=False):
        calls.append((name, dry_run))
        if name == "safe":
            return {"status": "success", "can_apply": True, "dirty_files": []}
        return {"status": "success", "can_apply": False, "dirty_files": ["README.md"]}

    monkeypatch.setattr(automerge, "run_sync", fake_run_sync)

    result = automerge.run_sync_all(apply=True)

    assert result["safe_count"] == 1
    assert result["applied_count"] == 1
    assert calls == [("safe", True), ("safe", False), ("dirty", True)]


def test_diagnose_container_mirrors_detects_invalid_git_copy(monkeypatch, tmp_path):
    fork = tmp_path / "fork"
    mirror = tmp_path / "mirror"
    _init_repo(fork)
    mirror.mkdir()
    (mirror / ".git").mkdir()

    monkeypatch.setattr(
        container_mirrors,
        "list_projects",
        lambda: [
            {
                "name": "router",
                "fork": str(fork),
                "container_mirror": str(mirror),
                "container_mirror_status": "invalid_git_copy",
            }
        ],
    )

    result = container_mirrors.diagnose_container_mirrors()

    assert result["invalid_count"] == 1
    assert result["reports"][0]["fork_git_valid"] is True
    assert result["reports"][0]["container_mirror_git_valid"] is False
