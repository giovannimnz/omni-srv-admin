"""container_mirrors — diagnose migrated container worktrees."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fork_sync.core.registry import list_projects


def _git_valid(path: Path) -> bool:
    if not path.exists():
        return False
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_head(path: Path) -> str | None:
    if not _git_valid(path):
        return None
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def diagnose_container_mirrors() -> dict:
    """Return container mirror health for projects that declare container_mirror."""
    reports = []
    for project in list_projects():
        mirror = project.get("container_mirror")
        if not mirror:
            continue
        fork = Path(str(project.get("fork", ""))).expanduser()
        mirror_path = Path(str(mirror)).expanduser()
        fork_valid = _git_valid(fork)
        mirror_valid = _git_valid(mirror_path)
        invalid_git_copy = mirror_path.exists() and (mirror_path / ".git").exists() and not mirror_valid
        reports.append(
            {
                "project": project["name"],
                "fork": str(fork),
                "fork_git_valid": fork_valid,
                "fork_head": _git_head(fork),
                "container_mirror": str(mirror_path),
                "container_mirror_exists": mirror_path.exists(),
                "container_mirror_git_valid": mirror_valid,
                "container_mirror_head": _git_head(mirror_path),
                "invalid_git_copy": invalid_git_copy,
                "configured_status": project.get("container_mirror_status"),
                "recommended_action": (
                    "keep fork path as canonical; repair/reclone mirror before switching sync"
                    if invalid_git_copy or not mirror_valid
                    else "mirror is a valid git worktree"
                ),
            }
        )
    return {
        "status": "success",
        "mirror_count": len(reports),
        "invalid_count": sum(1 for report in reports if report["invalid_git_copy"]),
        "reports": reports,
    }
