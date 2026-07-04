from __future__ import annotations

import json
from pathlib import Path

from fork_sync.core.release_preflight import run_preflight


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
