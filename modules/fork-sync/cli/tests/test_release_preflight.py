from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fork_sync.core.release_preflight import run_preflight


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")


def _commit_all(repo: Path, message: str = "test") -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)


def test_preflight_blocks_web_root_build_without_script(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "web" / "package.json", json.dumps({"private": True}))
    _write(
        repo / ".github" / "workflows" / "electron.yml",
        """
name: electron
jobs:
  build:
    steps:
      - run: |
          cd web
          bun install
          bun run build
""",
    )

    result = run_preflight(repo, secret_names=set())

    assert result["status"] == "error"
    assert {item["code"] for item in result["errors"]} == {"web-root-build-script-missing"}


def test_preflight_allows_web_root_build_with_script(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "web" / "package.json", json.dumps({"scripts": {"build": "echo ok"}}))
    _write(
        repo / ".github" / "workflows" / "electron.yml",
        """
name: electron
jobs:
  build:
    steps:
      - run: |
          cd web
          bun run build
""",
    )

    result = run_preflight(repo, secret_names=set())

    assert result["status"] == "success"


def test_preflight_blocks_unguarded_dockerhub_login_without_secrets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / ".github" / "workflows" / "docker.yml",
        """
name: docker
jobs:
  build:
    steps:
      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
""",
    )

    result = run_preflight(repo, secret_names=set())

    assert result["status"] == "error"
    assert {item["code"] for item in result["errors"]} == {"unguarded-dockerhub-login"}


def test_preflight_warns_for_guarded_dockerhub_login_without_secrets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / ".github" / "workflows" / "docker.yml",
        """
name: docker
jobs:
  build:
    steps:
      - id: image_targets
        run: echo dockerhub_enabled=false >> "$GITHUB_OUTPUT"
      - name: Log in to Docker Hub
        if: steps.image_targets.outputs.dockerhub_enabled == 'true'
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
""",
    )

    result = run_preflight(repo, secret_names=set())

    assert result["status"] == "success"
    assert {item["code"] for item in result["warnings"]} == {"dockerhub-optional"}


def test_preflight_blocks_four_part_tag_with_raw_npm_version(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / ".github" / "workflows" / "electron.yml",
        """
name: electron
jobs:
  build:
    steps:
      - run: |
          VERSION=$(git describe --tags)
          npm version "$VERSION" --no-git-tag-version
""",
    )

    result = run_preflight(repo, tag="v0.12.15.1", secret_names=set())

    assert result["status"] == "error"
    assert {item["code"] for item in result["errors"]} == {"electron-npm-version-not-normalized"}


def test_preflight_accepts_ghcr_deploy_image_without_dockerhub_secrets(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    deploy = tmp_path / "deploy.yaml"
    _write(deploy, "image: ghcr.io/giovannimnz/new-api\n")

    result = run_preflight(repo, deploy_config=deploy, secret_names=set())

    assert result["status"] == "success"


def test_preflight_blocks_dirty_tree_for_push_like_modes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write(repo / "README.md", "base\n")
    _commit_all(repo)
    _write(repo / "README.md", "dirty\n")

    result = run_preflight(repo, mode="fork-deploy", secret_names=set())

    assert result["status"] == "error"
    assert "dirty-working-tree" in {item["code"] for item in result["errors"]}


def test_preflight_blocks_origin_repo_mismatch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _git(repo, "remote", "add", "origin", "https://github.com/giovannimnz/router-ai-atius.git")

    result = run_preflight(repo, github_repo="giovannimnz/other-fork", secret_names=set())

    assert result["status"] == "error"
    assert "origin-repo-mismatch" in {item["code"] for item in result["errors"]}


def test_preflight_blocks_tracked_sensitive_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write(repo / ".env", "OPENAI_API_KEY=placeholder\n")
    _commit_all(repo)

    result = run_preflight(repo, secret_names=set())

    assert result["status"] == "error"
    assert "tracked-sensitive-files" in {item["code"] for item in result["errors"]}


def test_preflight_blocks_secret_like_values_in_tracked_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _write(
        repo / "config.txt",
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDabcdefghijklmnop\n"
        "qrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwx\n"
        "-----END PRIVATE KEY-----\n",
    )
    _commit_all(repo)

    result = run_preflight(repo, secret_names=set())

    assert result["status"] == "error"
    assert "tracked-secret-values" in {item["code"] for item in result["errors"]}


def test_preflight_flags_pull_request_target_risks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(
        repo / ".github" / "workflows" / "pr.yml",
        """
name: pr
on:
  pull_request_target:
jobs:
  risky:
    permissions: write-all
    steps:
      - uses: actions/checkout@v4
      - run: echo "${{ secrets.GITHUB_TOKEN }}"
""",
    )

    result = run_preflight(repo, secret_names=set())

    assert result["status"] == "error"
    assert "pull-request-target-risk" in {item["code"] for item in result["errors"]}
