"""Read-only Ubuntu Pro security collectors for Omni Fleet."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Callable

SecurityRunner = Callable[[list[str], int], tuple[int, str, str]]

DEFAULT_TIMEOUT = 20


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_command(argv: list[str], timeout: int = DEFAULT_TIMEOUT) -> tuple[int, str, str]:
    if "/" not in argv[0] and shutil.which(argv[0]) is None:
        return 127, "", f"{argv[0]}: command not found"
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _call(argv: list[str], runner: SecurityRunner, warnings: list[str]) -> Any:
    try:
        returncode, stdout, stderr = runner(argv, DEFAULT_TIMEOUT)
    except subprocess.TimeoutExpired:
        warnings.append(f"{argv[0]} timed out")
        return None
    except Exception as exc:
        warnings.append(f"{argv[0]} failed: {exc}")
        return None
    if returncode == 127:
        warnings.append(f"{argv[0]} missing")
        return None
    if returncode != 0:
        detail = (stderr or stdout).strip().splitlines()
        suffix = f": {detail[0][:160]}" if detail else ""
        warnings.append(f"{' '.join(argv[:3])} exited {returncode}{suffix}")
        return None
    if not stdout.strip():
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw_text": stdout.strip()}


def collect_security_report(host: str, runner: SecurityRunner | None = None) -> dict[str, Any]:
    """Collect local Pro security status and CVE view without applying fixes."""
    command_runner = runner or _run_command
    warnings: list[str] = []
    pro_status = _call(["pro", "status", "--format", "json"], command_runner, warnings)
    security_status = _call(["pro", "security-status", "--format", "json"], command_runner, warnings)
    cves = _call(["pro", "cves", "--format", "json"], command_runner, warnings)
    summary = {}
    if isinstance(security_status, dict):
        summary = security_status.get("summary") if isinstance(security_status.get("summary"), dict) else {}
    return {
        "host": host,
        "source": "ubuntu-pro-client",
        "generated_at": _now(),
        "summary": summary,
        "pro_status": pro_status,
        "security_status": security_status,
        "cves": cves,
        "warnings": warnings,
        "mutation": "none",
        "fix_policy": "dry-run-or-approved-update-plan-only",
    }

