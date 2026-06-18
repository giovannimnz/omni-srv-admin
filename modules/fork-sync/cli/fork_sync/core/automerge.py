"""automerge — safe multi-project sync gate."""

from __future__ import annotations

from fork_sync.core.registry import list_projects
from fork_sync.core.sync_runner import run_sync


def _safe_to_apply(result: dict) -> bool:
    return (
        result.get("status") == "success"
        and result.get("can_apply") is True
        and not result.get("dirty_files")
        and not result.get("unprotected_conflicts")
        and not result.get("unprotected_conflict_files")
        and not result.get("stale_protected_paths")
    )


def run_sync_all(apply: bool = False, include_paused: bool = False) -> dict:
    """Run dry-run for configured projects and apply only safe candidates."""
    projects = list_projects(only_enabled=not include_paused)
    reports = []
    for project in projects:
        name = project["name"]
        dry = run_sync(name, dry_run=True)
        report = {
            "project": name,
            "enabled": project.get("enabled", True),
            "dry_run": dry,
            "safe_to_apply": _safe_to_apply(dry),
            "applied": False,
            "apply_result": None,
        }
        if apply and report["safe_to_apply"]:
            applied = run_sync(name, dry_run=False)
            report["applied"] = applied.get("status") == "success"
            report["apply_result"] = applied
        reports.append(report)

    return {
        "status": "success",
        "mode": "apply" if apply else "dry-run",
        "include_paused": include_paused,
        "project_count": len(reports),
        "safe_count": sum(1 for report in reports if report["safe_to_apply"]),
        "applied_count": sum(1 for report in reports if report["applied"]),
        "reports": reports,
    }
