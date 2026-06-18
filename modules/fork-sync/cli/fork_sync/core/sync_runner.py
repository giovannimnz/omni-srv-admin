"""sync_runner — motor de sync com preservação real de protected_paths."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Optional

from fork_sync.core.config import DEPLOY_SH, REPO_ROOT
from fork_sync.core.registry import load_project


GIT_TIMEOUT = int(os.environ.get("FORK_SYNC_GIT_TIMEOUT", "120"))
HOOK_TIMEOUT = int(os.environ.get("FORK_SYNC_HOOK_TIMEOUT", "900"))


def _run_script(script: Path, args: list[str], cwd: Optional[Path] = None) -> dict:
    """Roda um script bash e captura resultado estruturado."""
    if not script.exists():
        return {
            "status": "error",
            "error": f"script não encontrado: {script}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }
    cmd = ["bash", str(script)] + args
    env = os.environ.copy()
    env.setdefault("FORK_SYNC_ROOT", str(REPO_ROOT))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else str(REPO_ROOT),
            env=env,
            timeout=600,
        )
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "timeout após 600s", "command": " ".join(cmd)}
    except Exception as exc:  # pragma: no cover - defensive path
        return {"status": "error", "error": str(exc), "command": " ".join(cmd)}


def _git(repo: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo),
            text=True,
            capture_output=True,
            check=check,
            timeout=GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"git {' '.join(args)} timed out after {GIT_TIMEOUT}s in {repo}"
        ) from exc


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _format_path(value: str, *, project: str, repo: Path) -> Path:
    formatted = value.format(project=project, repo=str(repo), repo_name=repo.name)
    return Path(formatted).expanduser().resolve()


def _normalise_post_sync(cfg: dict, *, project: str, repo: Path) -> dict:
    """Normaliza hooks pós-sync declarados em sync.yaml.

    Formatos aceitos:
    post_sync:
      enabled: true
      cwd: /repo/default
      run_on: [merged]
      commands:
        - uv run pytest
        - name: lint
          command: [uv, run, ruff, check, .]
          cwd: /repo/override
    """
    raw = cfg.get("post_sync")
    if not raw:
        return {"enabled": False, "commands": []}

    if isinstance(raw, list):
        enabled = True
        fail_fast = True
        run_on = ["merged"]
        default_cwd = repo
        raw_commands = raw
    elif isinstance(raw, dict):
        enabled = _as_bool(raw.get("enabled"), default=True)
        fail_fast = _as_bool(raw.get("fail_fast"), default=True)
        run_on = [str(item) for item in (raw.get("run_on") or ["merged"])]
        default_cwd = _format_path(str(raw.get("cwd") or repo), project=project, repo=repo)
        raw_commands = raw.get("commands") or []
    else:
        return {"enabled": False, "commands": [], "error": "post_sync inválido em sync.yaml"}

    commands = []
    for index, item in enumerate(raw_commands, 1):
        if isinstance(item, str):
            command = shlex.split(item)
            name = item
            cwd = default_cwd
        elif isinstance(item, list):
            command = [str(part) for part in item]
            name = " ".join(command)
            cwd = default_cwd
        elif isinstance(item, dict):
            raw_command = item.get("command") or item.get("cmd")
            if isinstance(raw_command, str):
                command = shlex.split(raw_command)
            elif isinstance(raw_command, list):
                command = [str(part) for part in raw_command]
            else:
                commands.append(
                    {
                        "name": str(item.get("name") or f"hook-{index}"),
                        "status": "invalid",
                        "error": "command ausente ou inválido",
                    }
                )
                continue
            name = str(item.get("name") or " ".join(command))
            cwd = _format_path(str(item.get("cwd") or default_cwd), project=project, repo=repo)
        else:
            commands.append(
                {
                    "name": f"hook-{index}",
                    "status": "invalid",
                    "error": "entrada de hook inválida",
                }
            )
            continue

        commands.append(
            {
                "name": name,
                "command": command,
                "cwd": str(cwd),
                "status": "pending",
            }
        )

    return {
        "enabled": enabled,
        "fail_fast": fail_fast,
        "run_on": run_on,
        "commands": commands,
    }


def _run_post_sync_hooks(cfg: dict, *, project: str, repo: Path, event: str) -> dict:
    plan = _normalise_post_sync(cfg, project=project, repo=repo)
    if not plan.get("enabled"):
        return {"enabled": False, "status": "skipped", "event": event, "commands": []}
    if event not in plan.get("run_on", []):
        return {
            "enabled": True,
            "status": "skipped",
            "event": event,
            "reason": f"event '{event}' not configured",
            "commands": plan.get("commands", []),
        }

    results = []
    overall = "success"
    env = os.environ.copy()
    env.update(
        {
            "FORK_SYNC_PROJECT": project,
            "FORK_SYNC_REPO": str(repo),
            "FORK_SYNC_EVENT": event,
        }
    )

    for hook in plan.get("commands", []):
        if hook.get("status") == "invalid":
            results.append(hook)
            overall = "error"
            if plan.get("fail_fast", True):
                break
            continue

        command = hook["command"]
        cwd = Path(hook["cwd"])
        if not cwd.exists():
            result = {
                **hook,
                "status": "error",
                "exit_code": -1,
                "error": f"cwd não existe: {cwd}",
            }
            results.append(result)
            overall = "error"
            if plan.get("fail_fast", True):
                break
            continue

        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd),
                text=True,
                capture_output=True,
                env=env,
                timeout=HOOK_TIMEOUT,
            )
            status = "success" if proc.returncode == 0 else "error"
            if status != "success":
                overall = "error"
            results.append(
                {
                    **hook,
                    "status": status,
                    "exit_code": proc.returncode,
                    "stdout": _tail(proc.stdout),
                    "stderr": _tail(proc.stderr),
                }
            )
            if status != "success" and plan.get("fail_fast", True):
                break
        except subprocess.TimeoutExpired:
            results.append(
                {
                    **hook,
                    "status": "timeout",
                    "exit_code": -1,
                    "error": f"timeout após {HOOK_TIMEOUT}s",
                }
            )
            overall = "error"
            if plan.get("fail_fast", True):
                break
        except OSError as exc:
            results.append(
                {
                    **hook,
                    "status": "error",
                    "exit_code": -1,
                    "error": str(exc),
                }
            )
            overall = "error"
            if plan.get("fail_fast", True):
                break

    return {
        "enabled": True,
        "status": overall,
        "event": event,
        "commands": results,
    }


def _version_plan(cfg: dict, *, project: str, upstream_sha: str) -> dict:
    scheme = cfg.get("version_scheme") or {}
    if not scheme:
        return {"enabled": False}

    suffix = str(scheme.get("suffix", "-rf"))
    upstream_version = str(cfg.get("upstream_version") or upstream_sha[:12])
    counter_template = str(scheme.get("counter_dir", "~/.fork-sync/{project}/versions/{upstream_version}"))
    counter_dir = counter_template.format(project=project, upstream_version=upstream_version)
    tag_template = str(scheme.get("tag_template", "v{upstream_version}{suffix}{counter}"))
    return {
        "enabled": True,
        "upstream_version": upstream_version,
        "suffix": suffix,
        "counter_dir": str(Path(counter_dir).expanduser()),
        "tag_template": tag_template,
        "release_notes_command": (
            f"fork-sync release generate {project} --upstream-version {upstream_version} --save-local"
        ),
    }


def _ensure_upstream_remote(repo: Path, url: str) -> None:
    remotes = _git(repo, ["remote"], check=False)
    if "upstream" in remotes.stdout.split():
        _git(repo, ["remote", "set-url", "upstream", url])
    else:
        _git(repo, ["remote", "add", "upstream", url])


def _branch(repo: Path) -> str:
    return _git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def _ahead_behind(repo: Path, upstream_ref: str) -> tuple[int, int]:
    proc = _git(repo, ["rev-list", "--left-right", "--count", f"HEAD...{upstream_ref}"])
    ahead_str, behind_str = proc.stdout.strip().split()
    return int(ahead_str), int(behind_str)


def _changed_since(repo: Path, start_ref: str, end_ref: str) -> list[str]:
    proc = _git(repo, ["diff", "--name-only", f"{start_ref}..{end_ref}"], check=False)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _dirty_files(repo: Path) -> list[str]:
    proc = _git(repo, ["status", "--porcelain", "--untracked-files=all"], check=False)
    files = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        files.append(line[3:] if len(line) > 3 else line)
    return files


def _configured_enabled(cfg: dict) -> bool:
    if str(cfg.get("enabled", True)).lower() == "false":
        return False
    if str(cfg.get("paused", False)).lower() == "true":
        return False
    return True


def _protected_patterns(cfg: dict) -> list[str]:
    patterns = []
    patterns.extend(cfg.get("protected_paths", []) or [])
    patterns.extend(cfg.get("protected_globs", []) or [])
    return [str(pattern) for pattern in patterns if str(pattern).strip()]


def _split_repo_patterns(patterns: list[str]) -> tuple[list[str], list[str]]:
    repo_patterns = []
    external_patterns = []
    for pattern in patterns:
        if Path(pattern).is_absolute():
            external_patterns.append(pattern)
        else:
            repo_patterns.append(pattern)
    return repo_patterns, external_patterns


def _expand_protected_paths(repo: Path, patterns: list[str]) -> tuple[list[str], list[str]]:
    matched: set[str] = set()
    stale: list[str] = []
    for pattern in patterns:
        proc = _git(repo, ["ls-files", "--cached", "--", pattern], check=False)
        files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if not files:
            stale.append(pattern)
            continue
        matched.update(files)
    return sorted(matched), stale


def _restore_protected_paths(repo: Path, patterns: list[str]) -> None:
    if not patterns:
        return
    _git(repo, ["checkout", "HEAD", "--", *patterns], check=False)


def _unmerged_files(repo: Path) -> list[str]:
    proc = _git(repo, ["diff", "--name-only", "--diff-filter=U"], check=False)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _merge_abort(repo: Path) -> None:
    merge_head = repo / ".git" / "MERGE_HEAD"
    if merge_head.exists():
        _git(repo, ["merge", "--abort"], check=False)


def run_detect(name: str) -> dict:
    """Detecta novo release."""
    cfg = load_project(name)
    out = _run_script(REPO_ROOT / "bin" / "detect-release.sh", [name, cfg.get("fork", "")])
    new_release = False
    version = None
    for line in out.get("stdout", "").splitlines():
        if line.startswith("NEW_RELEASE="):
            new_release = line.split("=", 1)[1].strip().lower() == "true"
        elif line.startswith("VERSION="):
            version = line.split("=", 1)[1].strip()
    out["new_release"] = new_release
    out["version"] = version
    return out


def run_sync(
    name: str,
    repo_path: Optional[str] = None,
    dry_run: bool = False,
    deploy: bool = False,
) -> dict:
    """Sincroniza fork com upstream preservando protected_paths."""
    cfg = load_project(name)
    if not _configured_enabled(cfg):
        return {
            "status": "skipped",
            "message": cfg.get("pause_reason") or "project disabled/paused in sync.yaml",
            "project": name,
        }

    repo_config = repo_path or cfg.get("fork")
    if not repo_config:
        return {
            "status": "error",
            "error": "fork path missing; set `fork:` in sync.yaml or pass --repo-path",
            "project": name,
        }

    repo = Path(repo_config).expanduser().resolve()
    upstream_url = cfg.get("upstream", "")
    upstream_branch = cfg.get("upstream_branch", "main")
    upstream_ref = f"upstream/{upstream_branch}"
    merge_strategy = cfg.get("merge_strategy", "merge")
    protected_patterns_all = _protected_patterns(cfg)
    protected_patterns, external_protected_patterns = _split_repo_patterns(protected_patterns_all)

    if not (repo / ".git").exists():
        return {
            "status": "error",
            "error": f"repo is not a git repository: {repo}",
            "repo": str(repo),
        }
    if not upstream_url:
        return {
            "status": "error",
            "error": f"upstream não configurado em {name}",
            "repo": str(repo),
        }

    _ensure_upstream_remote(repo, upstream_url)
    fetch = _git(repo, ["fetch", "upstream", upstream_branch], check=False)
    if fetch.returncode != 0:
        return {
            "status": "error",
            "error": f"falha no fetch de {upstream_ref}",
            "stdout": fetch.stdout,
            "stderr": fetch.stderr,
            "repo": str(repo),
        }

    branch = _branch(repo)
    local_sha = _git(repo, ["rev-parse", "HEAD"]).stdout.strip()
    remote_sha = _git(repo, ["rev-parse", upstream_ref]).stdout.strip()
    merge_base = _git(repo, ["merge-base", "HEAD", upstream_ref]).stdout.strip()
    ahead, behind = _ahead_behind(repo, upstream_ref)
    dirty_files = _dirty_files(repo)
    protected_files, stale_patterns = _expand_protected_paths(repo, protected_patterns)
    local_changes = set(_changed_since(repo, merge_base, "HEAD"))
    upstream_changes = set(_changed_since(repo, merge_base, upstream_ref))
    conflict_candidates = sorted(local_changes & upstream_changes)
    protected_conflicts = sorted(path for path in conflict_candidates if path in protected_files)
    unprotected_conflicts = sorted(path for path in conflict_candidates if path not in protected_files)

    result = {
        "project": name,
        "repo": str(repo),
        "branch": branch,
        "upstream": upstream_url,
        "upstream_ref": upstream_ref,
        "local_sha": local_sha,
        "upstream_sha": remote_sha,
        "merge_base": merge_base,
        "ahead": ahead,
        "behind": behind,
        "dirty_files": dirty_files,
        "protected_patterns": protected_patterns,
        "external_protected_patterns": external_protected_patterns,
        "protected_files": protected_files,
        "stale_protected_paths": stale_patterns,
        "conflict_candidates": conflict_candidates,
        "protected_conflicts": protected_conflicts,
        "unprotected_conflicts": unprotected_conflicts,
        "merge_strategy": merge_strategy,
        "deploy_requested": deploy,
        "version_plan": _version_plan(cfg, project=name, upstream_sha=remote_sha),
        "post_sync_plan": _normalise_post_sync(cfg, project=name, repo=repo),
    }

    if local_sha == remote_sha:
        result.update(
            {
                "status": "success",
                "message": "Already up to date",
                "can_apply": not dirty_files and not unprotected_conflicts,
            }
        )
        return result

    if behind == 0:
        push_stdout = ""
        push_stderr = ""
        push_exit_code = None
        if not dry_run and dirty_files:
            result.update(
                {
                    "status": "error",
                    "error": "working tree suja; faça checkpoint local antes do push",
                }
            )
            return result
        if not dry_run and str(cfg.get("auto_push", False)).lower() == "true":
            push = _git(repo, ["push", "origin", branch], check=False)
            push_stdout = push.stdout
            push_stderr = push.stderr
            push_exit_code = push.returncode
            if push.returncode != 0:
                result.update(
                    {
                        "status": "error",
                        "error": f"push falhou para origin/{branch}",
                        "push_stdout": push_stdout,
                        "push_stderr": push_stderr,
                        "push_exit_code": push_exit_code,
                    }
                )
                return result
        result.update(
            {
                "status": "success",
                "message": f"Already contains {upstream_ref}; local branch is ahead by {ahead}",
                "can_apply": not dirty_files,
                "push_stdout": push_stdout,
                "push_stderr": push_stderr,
                "push_exit_code": push_exit_code,
            }
        )
        if not dry_run:
            result["post_sync"] = _run_post_sync_hooks(
                cfg,
                project=name,
                repo=repo,
                event="ahead_only",
            )
            if result["post_sync"].get("status") == "error":
                result["status"] = "error"
                result["error"] = "branch ahead-only publicada, mas post_sync falhou"
        return result

    if dry_run:
        result.update(
            {
                "status": "success",
                "message": f"Would merge {upstream_ref} into {branch}",
                "can_apply": not dirty_files and not unprotected_conflicts,
            }
        )
        return result

    if dirty_files:
        result.update(
            {
                "status": "error",
                "error": "working tree suja; faça checkpoint local antes do sync",
            }
        )
        return result

    if unprotected_conflicts:
        result.update(
            {
                "status": "error",
                "error": "mudanças locais e upstream se sobrepõem fora dos protected_paths",
                "conflict_files": unprotected_conflicts,
            }
        )
        return result

    merge_args = ["merge", "--no-commit", "--no-ff"]
    if merge_strategy in {"ours", "theirs"}:
        merge_args.extend(["-X", merge_strategy])
    merge_args.append(upstream_ref)
    merge = _git(repo, merge_args, check=False)

    if merge.returncode != 0:
        unresolved = _unmerged_files(repo)
        unresolved_unprotected = [path for path in unresolved if path not in protected_files]
        if unresolved_unprotected:
            _merge_abort(repo)
            result.update(
                {
                    "status": "error",
                    "error": "merge gerou conflitos fora dos protected_paths",
                    "stdout": merge.stdout,
                    "stderr": merge.stderr,
                    "conflict_files": unresolved,
                    "unprotected_conflict_files": unresolved_unprotected,
                }
            )
            return result
    _restore_protected_paths(repo, protected_patterns)
    if protected_patterns:
        _git(repo, ["add", "--", *protected_patterns], check=False)

    remaining = _unmerged_files(repo)
    if remaining:
        _merge_abort(repo)
        result.update(
            {
                "status": "error",
                "error": "merge permaneceu com conflitos após restaurar protected_paths",
                "stdout": merge.stdout,
                "stderr": merge.stderr,
                "conflict_files": remaining,
            }
        )
        return result

    commit_message = f"chore(fork-sync): sync {name} with {upstream_ref}"
    commit = _git(repo, ["commit", "-m", commit_message], check=False)
    if commit.returncode != 0:
        _merge_abort(repo)
        result.update(
            {
                "status": "error",
                "error": "falha ao criar commit de merge",
                "stdout": commit.stdout,
                "stderr": commit.stderr,
            }
        )
        return result

    push_stdout = ""
    push_stderr = ""
    push_exit_code = None
    if str(cfg.get("auto_push", False)).lower() == "true":
        push = _git(repo, ["push", "origin", branch], check=False)
        push_stdout = push.stdout
        push_stderr = push.stderr
        push_exit_code = push.returncode
        if push.returncode != 0:
            result.update(
                {
                    "status": "error",
                    "error": f"push falhou para origin/{branch}",
                    "push_stdout": push_stdout,
                    "push_stderr": push_stderr,
                    "push_exit_code": push_exit_code,
                }
            )
            return result

    result.update(
        {
            "status": "success",
            "message": f"Merged {upstream_ref} into {branch}",
            "merge_stdout": merge.stdout,
            "merge_stderr": merge.stderr,
            "commit_sha": _git(repo, ["rev-parse", "HEAD"]).stdout.strip(),
            "push_stdout": push_stdout,
            "push_stderr": push_stderr,
            "push_exit_code": push_exit_code,
        }
    )
    result["post_sync"] = _run_post_sync_hooks(
        cfg,
        project=name,
        repo=repo,
        event="merged",
    )
    if result["post_sync"].get("status") == "error":
        result["status"] = "error"
        result["error"] = "sync aplicado, mas post_sync falhou"
    if deploy:
        result["deploy_note"] = "Deploy flag ignored by sync runner; use deploy command separately."
    return result


def run_deploy(name: str, repo_path: Optional[str] = None, dry_run: bool = False) -> dict:
    """Deploy Docker (requer deploy.yaml)."""
    cfg = load_project(name)
    if "deploy" not in cfg and not (Path(cfg.get("path", "")) / "deploy.yaml").exists():
        raise FileNotFoundError(f"Projeto '{name}' não tem deploy.yaml")
    args = [name]
    if repo_path:
        args.append(repo_path)
    elif cfg.get("fork"):
        args.append(cfg["fork"])
    if dry_run:
        args.append("--dry-run")
    return _run_script(DEPLOY_SH, args)
