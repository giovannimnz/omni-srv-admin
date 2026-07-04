"""Release/deploy preflight checks for fork sends.

The checks are intentionally static and conservative. They catch deterministic
CI failures before a tag, push, or deploy triggers GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


FOUR_PART_VERSION = re.compile(r"^v?[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(?:[-+].*)?$")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data: dict[str, Any] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" not in line or line.lstrip() != line:
                continue
            key, value = line.split(":", 1)
            data[key.strip()] = value.split("#", 1)[0].strip().strip("'\"")
        return data


def _github_slug_from_remote(repo: Path) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "remote", "get-url", "origin"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        return None
    url = proc.stdout.strip()
    patterns = [
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
        r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    return None


def _secret_names(github_repo: str | None) -> tuple[set[str] | None, str | None]:
    if not github_repo:
        return None, "github repo slug unavailable; secret checks are static only"
    try:
        proc = subprocess.run(
            ["gh", "secret", "list", "--repo", github_repo],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return None, f"could not list GitHub secrets for {github_repo}: {exc}"
    if proc.returncode != 0:
        return None, f"could not list GitHub secrets for {github_repo}: {proc.stderr.strip()}"
    names = {line.split()[0] for line in proc.stdout.splitlines() if line.strip()}
    return names, None


def _workflow_files(repo: Path) -> list[Path]:
    workflows = repo / ".github" / "workflows"
    if not workflows.exists():
        return []
    return sorted(
        path
        for path in workflows.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )


def _has_web_build_script(repo: Path) -> bool:
    pkg = _load_json(repo / "web" / "package.json")
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    return bool(scripts.get("build"))


def _uses_web_root_bun_build(text: str) -> bool:
    if re.search(r"working-directory:\s*web\b[\s\S]{0,500}?bun\s+run\s+build", text):
        return True
    return bool(re.search(r"cd\s+web\b[\s\S]{0,500}?bun\s+(?:--[^\n]+\s+)*run\s+build", text))


def _dockerhub_refs(text: str) -> bool:
    return "DOCKERHUB_USERNAME" in text or "DOCKERHUB_TOKEN" in text


def _dockerhub_guarded(text: str) -> bool:
    if "dockerhub_enabled" in text.lower():
        return True
    if re.search(r"if:\s*.*dockerhub", text, flags=re.IGNORECASE):
        return True
    if re.search(r"if:\s*\$\{\{[^}]*DOCKERHUB", text):
        return True
    return False


def _uses_raw_npm_version(text: str) -> bool:
    return "npm version" in text and "normalize-electron-version" not in text


def _add_issue(issues: list[dict[str, str]], code: str, message: str, path: Path | None = None) -> None:
    item = {"code": code, "message": message}
    if path:
        item["path"] = str(path)
    issues.append(item)


def run_preflight(
    repo: str | Path,
    *,
    tag: str | None = None,
    mode: str = "push",
    github_repo: str | None = None,
    deploy_config: str | Path | None = None,
    secret_names: set[str] | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo).expanduser().resolve()
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []

    if not repo_path.exists():
        _add_issue(issues, "repo-missing", f"repo path does not exist: {repo_path}")
        return {"status": "error", "repo": str(repo_path), "mode": mode, "errors": issues, "warnings": warnings, "checks": checks}

    github_repo = github_repo or _github_slug_from_remote(repo_path)
    if secret_names is None:
        secret_names, secret_warning = _secret_names(github_repo)
        if secret_warning:
            _add_issue(warnings, "secret-list-unavailable", secret_warning)

    has_dockerhub_secrets = bool(
        secret_names is not None
        and {"DOCKERHUB_USERNAME", "DOCKERHUB_TOKEN"}.issubset(secret_names)
    )

    has_web_build = _has_web_build_script(repo_path)
    four_part_tag = bool(tag and FOUR_PART_VERSION.match(tag))

    for workflow in _workflow_files(repo_path):
        text = _read_text(workflow)
        rel = workflow.relative_to(repo_path)
        checks.append({"check": "workflow-scanned", "path": str(rel)})

        if _uses_web_root_bun_build(text) and not has_web_build:
            _add_issue(
                issues,
                "web-root-build-script-missing",
                "workflow runs `bun run build` from web/, but web/package.json has no scripts.build",
                rel,
            )

        if _dockerhub_refs(text) and not _dockerhub_guarded(text) and not has_dockerhub_secrets:
            _add_issue(
                issues,
                "unguarded-dockerhub-login",
                "workflow references DockerHub secrets without an optional guard and repo secrets are missing",
                rel,
            )
        elif _dockerhub_refs(text) and _dockerhub_guarded(text) and not has_dockerhub_secrets:
            _add_issue(
                warnings,
                "dockerhub-optional",
                "DockerHub secrets are missing; guarded workflow must publish GHCR or skip DockerHub",
                rel,
            )

        if four_part_tag and _uses_raw_npm_version(text):
            _add_issue(
                issues,
                "electron-npm-version-not-normalized",
                f"tag {tag} has four numeric components; workflow uses raw npm version without normalization",
                rel,
            )

    deploy_data = _load_yaml(Path(deploy_config).expanduser()) if deploy_config else {}
    image = str(deploy_data.get("image") or "")
    if image:
        checks.append({"check": "deploy-image", "image": image})
        if "ghcr.io/" not in image and not has_dockerhub_secrets:
            _add_issue(
                issues,
                "deploy-image-needs-registry-auth",
                f"deploy image {image!r} is not GHCR and DockerHub secrets are missing",
                Path(deploy_config) if deploy_config else None,
            )

    status = "success" if not issues else "error"
    return {
        "status": status,
        "mode": mode,
        "repo": str(repo_path),
        "github_repo": github_repo,
        "tag": tag,
        "errors": issues,
        "warnings": warnings,
        "checks": checks,
    }


def _print_text(result: dict[str, Any]) -> None:
    print(f"release_preflight={result['status']} repo={result['repo']} mode={result['mode']}")
    if result.get("tag"):
        print(f"tag={result['tag']}")
    if result.get("github_repo"):
        print(f"github_repo={result['github_repo']}")
    for item in result.get("errors", []):
        location = f" [{item['path']}]" if item.get("path") else ""
        print(f"ERROR {item['code']}{location}: {item['message']}")
    for item in result.get("warnings", []):
        location = f" [{item['path']}]" if item.get("path") else ""
        print(f"WARN {item['code']}{location}: {item['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight GitHub Actions/release/deploy sends.")
    parser.add_argument("repo", help="Target repository path.")
    parser.add_argument("--tag", default=None)
    parser.add_argument("--mode", default="push")
    parser.add_argument("--github-repo", default=None)
    parser.add_argument("--deploy-config", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = run_preflight(
        args.repo,
        tag=args.tag,
        mode=args.mode,
        github_repo=args.github_repo,
        deploy_config=args.deploy_config,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_text(result)
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
