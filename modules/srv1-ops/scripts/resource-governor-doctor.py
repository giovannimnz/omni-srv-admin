#!/usr/bin/env python3
"""Low-cost structural and pressure doctor for the resource governor."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve()
MODULE = SCRIPT.parent.parent
CONFIG_PATH = MODULE / "configs" / "resource-governor.env"
STATE_DIR = Path.home() / ".local" / "state" / "omni"
DEFAULT_STATE_FILE = STATE_DIR / "resource-governor-doctor.json"
DEFAULT_METRICS_FILE = STATE_DIR / "textfile-collector" / "resource-governor-doctor.prom"
DEFAULT_HYGIENE_STATE = STATE_DIR / "resource-governor-hygiene.json"
DEFAULT_AUDIT_STATE = STATE_DIR / "resource-governor-audit.json"
DEFAULT_BUILD_LOCK = STATE_DIR / "resource-governor-builds.lock"
LEGACY_CGROUP = Path("/sys/fs/cgroup/atius-build-throttle")
BUILD_PATTERN = re.compile(
    r"(graphify\s+update|\b(cargo|rustc|gcc|g\+\+|clang|cc1|make|ninja|node-gyp)\b|"
    r"\b(podman|docker)\s+build|\b(npm|pnpm|yarn|bun)\s+(build|install|test)|"
    r"\b(go|pytest)\s+(build|test|install|run)?)"
)


def load_key_values(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def load_config() -> dict[str, str]:
    data = {
        "RG_DOCTOR_STATE_FILE": str(DEFAULT_STATE_FILE),
        "RG_DOCTOR_METRICS_FILE": str(DEFAULT_METRICS_FILE),
        "RG_DOCTOR_QUEUE_MAX_AGE_SEC": "7200",
        "RG_DOCTOR_AUDIT_MAX_AGE_SEC": "172800",
        "RG_DOCTOR_CPU_PSI_WARN_AVG10": "70",
        "RG_DOCTOR_SWAP_WARN_PCT": "85",
        "RG_PROFILE_BUILDS_CPU_TOTAL_PCT": "20",
    }
    data.update(load_key_values(CONFIG_PATH))
    override = Path(os.path.expanduser(data.get("RG_RUNTIME_OVERRIDE_FILE", "")))
    if str(override) not in ("", "."):
        data.update(load_key_values(override))
    return data


def user_systemd_env() -> dict[str, str]:
    env = os.environ.copy()
    runtime_dir = f"/run/user/{os.getuid()}"
    env["XDG_RUNTIME_DIR"] = runtime_dir
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"
    return env


def run(cmd: list[str], *, user_systemd: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=user_systemd_env() if user_systemd else None,
    )


def parse_timestamp(value: Any) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return None


def json_file(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, "missing"
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"corrupt:{exc.__class__.__name__}"
    if not isinstance(value, dict):
        return {}, "corrupt:not-object"
    return value, None


def expected_cpu_max(config: dict[str, str]) -> str:
    period = 100_000
    total_pct = float(config.get("RG_PROFILE_BUILDS_CPU_TOTAL_PCT", "20"))
    quota = round((total_pct / 100.0) * (os.cpu_count() or 1) * period)
    return f"{quota} {period}"


def expected_cpu_units(config: dict[str, str]) -> float:
    return float(config.get("RG_PROFILE_BUILDS_CPU_TOTAL_PCT", "20")) * (os.cpu_count() or 1) / 100.0


def build_cgroup() -> Path:
    proc = run(
        ["systemctl", "--user", "show", "omni-builds.slice", "-p", "ControlGroup", "--value"],
        user_systemd=True,
    )
    relative = proc.stdout.strip()
    if relative.startswith("/"):
        return Path("/sys/fs/cgroup") / relative.lstrip("/")
    uid = os.getuid()
    return Path(
        f"/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service/omni.slice/omni-builds.slice"
    )


def legacy_unit_state() -> dict[str, Any]:
    enabled = run(["systemctl", "is-enabled", "atius-build-throttle.timer"])
    active = run(["systemctl", "is-active", "atius-build-throttle.timer"])
    enabled_value = (enabled.stdout or enabled.stderr).strip().splitlines()
    active_value = (active.stdout or active.stderr).strip().splitlines()
    return {
        "enabled": enabled_value[0] if enabled_value else "unknown",
        "active": active_value[0] if active_value else "unknown",
        "unsafe": enabled.returncode == 0 or active.returncode == 0,
    }


def user_unit_state(unit: str) -> dict[str, Any]:
    enabled = run(["systemctl", "--user", "is-enabled", unit], user_systemd=True)
    active = run(["systemctl", "--user", "is-active", unit], user_systemd=True)
    enabled_value = (enabled.stdout or enabled.stderr).strip().splitlines()
    active_value = (active.stdout or active.stderr).strip().splitlines()
    return {
        "enabled": enabled_value[0] if enabled_value else "unknown",
        "active": active_value[0] if active_value else "unknown",
        "healthy": enabled.returncode == 0 and active.returncode == 0,
    }


def legacy_transient_count() -> int:
    proc = run(
        ["systemctl", "--user", "list-units", "omni-post-build-*", "--all", "--no-legend", "--plain"],
        user_systemd=True,
    )
    return sum(1 for line in proc.stdout.splitlines() if line.strip())


def self_and_ancestor_pids() -> set[int]:
    pids: set[int] = set()
    pid = os.getpid()
    while pid > 1 and pid not in pids:
        pids.add(pid)
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().split()
            pid = int(fields[3])
        except (OSError, ValueError, IndexError):
            break
    return pids


def externally_cpu_bounded(cgroup: str, max_cpus: float) -> bool:
    relative = next((line.split("::", 1)[1] for line in cgroup.splitlines() if "::" in line), "")
    if not relative.startswith("/"):
        return False
    path = Path("/sys/fs/cgroup") / relative.lstrip("/")
    root = Path("/sys/fs/cgroup")
    while path == root or root in path.parents:
        cpu_max = path / "cpu.max"
        try:
            quota_text, period_text = cpu_max.read_text().split()[:2]
            if quota_text != "max" and float(quota_text) / float(period_text) <= max_cpus + 1e-9:
                return True
        except (OSError, ValueError, IndexError):
            pass
        if path == root:
            break
        path = path.parent
    return False


def hot_build_escapes(max_cpus: float | None = None) -> list[dict[str, Any]]:
    proc = run(["ps", "-eo", "pid=,pcpu=,args=", "--sort=-pcpu"])
    escapes: list[dict[str, Any]] = []
    ignored_pids = self_and_ancestor_pids()
    for line in proc.stdout.splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) != 3:
            continue
        pid_text, cpu_text, args = parts
        try:
            pid, cpu = int(pid_text), float(cpu_text)
        except ValueError:
            continue
        if pid in ignored_pids:
            continue
        if cpu < 3.0 or not BUILD_PATTERN.search(args):
            continue
        try:
            cgroup = Path(f"/proc/{pid}/cgroup").read_text().strip()
        except OSError:
            continue
        if "omni-builds" not in cgroup:
            if max_cpus is not None and externally_cpu_bounded(cgroup, max_cpus):
                continue
            escapes.append({"pid": pid, "cpu_pct": cpu, "cgroup": cgroup, "args": args[:200]})
    return escapes[:20]


def cpu_psi_avg10() -> float:
    try:
        line = next(line for line in Path("/proc/pressure/cpu").read_text().splitlines() if line.startswith("some "))
        match = re.search(r"avg10=([0-9.]+)", line)
        return float(match.group(1)) if match else 0.0
    except (OSError, StopIteration, ValueError):
        return 0.0


def swap_used_pct() -> float:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in {"SwapTotal", "SwapFree"}:
                values[key] = int(value.strip().split()[0])
    except (OSError, ValueError):
        return 0.0
    total = values.get("SwapTotal", 0)
    return 0.0 if total <= 0 else 100.0 * (total - values.get("SwapFree", 0)) / total


def semaphore_busy(path: Path) -> bool:
    if not path.exists():
        return False
    proc = run(["flock", "--nonblock", str(path), "true"])
    return proc.returncode != 0


def warn_output_path(path: Path, exc: OSError) -> None:
    print(
        f"WARN output_path_unwritable path={path} error={exc.__class__.__name__}: {exc}",
        file=sys.stderr,
    )


def prepare_output_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o755)
        return True
    except PermissionError as exc:
        warn_output_path(path, exc)
    except OSError as exc:
        warn_output_path(path, exc)
    return False


def collect(config: dict[str, str]) -> dict[str, Any]:
    now = time.time()
    checks: list[dict[str, Any]] = []

    def add(name: str, severity: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "severity": severity, "ok": ok, "detail": detail})

    cgroup = build_cgroup()
    cpu_max_path = cgroup / "cpu.max"
    actual_cpu_max = cpu_max_path.read_text().strip() if cpu_max_path.exists() else "missing"
    expected = expected_cpu_max(config)
    add("build_cgroup_present", "critical", cgroup.exists(), str(cgroup))
    add("build_cpu_quota", "critical", actual_cpu_max == expected, f"actual={actual_cpu_max} expected={expected}")

    legacy = legacy_unit_state()
    add("legacy_scanner_absent", "critical", not legacy["unsafe"], f"enabled={legacy['enabled']} active={legacy['active']}")
    add("legacy_cgroup_absent", "critical", not LEGACY_CGROUP.exists(), str(LEGACY_CGROUP))
    transient_count = legacy_transient_count()
    add("legacy_transient_units_absent", "critical", transient_count == 0, f"count={transient_count}")

    escapes = hot_build_escapes(expected_cpu_units(config))
    add("hot_builds_contained", "critical", not escapes, f"escaped={len(escapes)}")

    doctor_timer = user_unit_state("resource-governor-doctor.timer")
    add(
        "doctor_timer_active",
        "warning",
        doctor_timer["healthy"],
        f"enabled={doctor_timer['enabled']} active={doctor_timer['active']}",
    )

    hygiene_path = Path(os.path.expanduser(config.get("RG_HYGIENE_STATE_FILE", str(DEFAULT_HYGIENE_STATE))))
    hygiene, hygiene_error = json_file(hygiene_path)
    add("hygiene_state_readable", "warning", hygiene_error is None, hygiene_error or str(hygiene_path))
    pending = hygiene.get("pending") or {}
    request_at = parse_timestamp(hygiene.get("last_request_at"))
    queue_age = max(0.0, now - request_at) if request_at and any(pending.values()) else 0.0
    queue_max_age = float(config.get("RG_DOCTOR_QUEUE_MAX_AGE_SEC", "7200"))
    add("hygiene_queue_fresh", "warning", queue_age <= queue_max_age, f"pending_age_sec={queue_age:.0f} max={queue_max_age:.0f}")

    audit_path = Path(os.path.expanduser(config.get("RG_AUDIT_STATE_FILE", str(DEFAULT_AUDIT_STATE))))
    audit, audit_error = json_file(audit_path)
    audit_at = parse_timestamp(audit.get("timestamp"))
    audit_age = max(0.0, now - audit_at) if audit_at else float("inf")
    audit_max_age = float(config.get("RG_DOCTOR_AUDIT_MAX_AGE_SEC", "172800"))
    audit_ok = audit_error is None and audit.get("status") == "success" and audit_age <= audit_max_age
    add("audit_recent_success", "warning", audit_ok, f"status={audit.get('status', audit_error or 'unknown')} age_sec={audit_age:.0f}")

    psi = cpu_psi_avg10()
    psi_warn = float(config.get("RG_DOCTOR_CPU_PSI_WARN_AVG10", "70"))
    add("cpu_pressure", "warning", psi < psi_warn, f"psi_some_avg10={psi:.2f} warn={psi_warn:.2f}")
    swap = swap_used_pct()
    swap_warn = float(config.get("RG_DOCTOR_SWAP_WARN_PCT", "85"))
    add("swap_pressure", "warning", swap < swap_warn, f"used_pct={swap:.2f} warn={swap_warn:.2f}")

    structural_ok = all(check["ok"] for check in checks if check["severity"] == "critical")
    doctor_ok = all(check["ok"] for check in checks)
    build_lock = Path(os.path.expanduser(config.get("RG_PROFILE_BUILDS_LOCK_FILE", str(DEFAULT_BUILD_LOCK))))
    return {
        "timestamp": datetime.now().astimezone().isoformat(),
        "doctor_ok": doctor_ok,
        "structural_ok": structural_ok,
        "checks": checks,
        "observations": {
            "build_cgroup": str(cgroup),
            "actual_cpu_max": actual_cpu_max,
            "expected_cpu_max": expected,
            "legacy_transient_units": transient_count,
            "hot_build_escapes": escapes,
            "queue_pending_age_seconds": round(queue_age, 3),
            "audit_age_seconds": None if audit_age == float("inf") else round(audit_age, 3),
            "build_semaphore_busy": semaphore_busy(build_lock),
            "cpu_psi_some_avg10": psi,
            "swap_used_pct": round(swap, 3),
        },
    }


def write_outputs(report: dict[str, Any], config: dict[str, str]) -> None:
    state_file = Path(os.path.expanduser(config["RG_DOCTOR_STATE_FILE"]))
    metrics_file = Path(os.path.expanduser(config["RG_DOCTOR_METRICS_FILE"]))
    state_file.parent.mkdir(parents=True, exist_ok=True)
    metrics_dir_ready = prepare_output_dir(metrics_file.parent)
    state_tmp = state_file.with_suffix(".tmp")
    state_tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    state_tmp.replace(state_file)
    obs = report["observations"]
    checks = {item["name"]: item for item in report["checks"]}
    lines = [
        "# HELP omni_resource_governor_doctor_ok All structural and pressure checks are healthy.",
        "# TYPE omni_resource_governor_doctor_ok gauge",
        f"omni_resource_governor_doctor_ok {int(report['doctor_ok'])}",
        "# HELP omni_resource_governor_structural_ok Build admission structural checks are healthy.",
        "# TYPE omni_resource_governor_structural_ok gauge",
        f"omni_resource_governor_structural_ok {int(report['structural_ok'])}",
        "# HELP omni_resource_governor_cpu_quota_match Build slice cpu.max matches the configured host-total cap.",
        "# TYPE omni_resource_governor_cpu_quota_match gauge",
        f"omni_resource_governor_cpu_quota_match {int(checks['build_cpu_quota']['ok'])}",
        "# HELP omni_resource_governor_hot_build_escapes Hot build processes outside omni-builds.slice.",
        "# TYPE omni_resource_governor_hot_build_escapes gauge",
        f"omni_resource_governor_hot_build_escapes {len(obs['hot_build_escapes'])}",
        "# HELP omni_resource_governor_queue_pending_age_seconds Age of a pending hygiene batch.",
        "# TYPE omni_resource_governor_queue_pending_age_seconds gauge",
        f"omni_resource_governor_queue_pending_age_seconds {obs['queue_pending_age_seconds']}",
        "# HELP omni_resource_governor_audit_age_seconds Age of the last successful audit state.",
        "# TYPE omni_resource_governor_audit_age_seconds gauge",
        f"omni_resource_governor_audit_age_seconds {obs['audit_age_seconds'] or 0}",
        "# HELP omni_resource_governor_build_semaphore_busy Whether one build owns the singleton lock.",
        "# TYPE omni_resource_governor_build_semaphore_busy gauge",
        f"omni_resource_governor_build_semaphore_busy {int(obs['build_semaphore_busy'])}",
        "# HELP omni_resource_governor_cpu_psi_some_avg10 Current CPU PSI some avg10.",
        "# TYPE omni_resource_governor_cpu_psi_some_avg10 gauge",
        f"omni_resource_governor_cpu_psi_some_avg10 {obs['cpu_psi_some_avg10']}",
        "# HELP omni_resource_governor_swap_used_pct Current swap used percentage.",
        "# TYPE omni_resource_governor_swap_used_pct gauge",
        f"omni_resource_governor_swap_used_pct {obs['swap_used_pct']}",
        "# HELP omni_resource_governor_doctor_timestamp_seconds Last doctor metrics refresh.",
        "# TYPE omni_resource_governor_doctor_timestamp_seconds gauge",
        f"omni_resource_governor_doctor_timestamp_seconds {int(time.time())}",
    ]
    if not metrics_dir_ready:
        return
    metrics_tmp = metrics_file.with_suffix(".tmp")
    try:
        metrics_tmp.write_text("\n".join(lines) + "\n")
        metrics_tmp.chmod(0o644)
        metrics_tmp.replace(metrics_file)
    except PermissionError as exc:
        warn_output_path(metrics_file, exc)
    except OSError as exc:
        warn_output_path(metrics_file, exc)


def print_report(report: dict[str, Any]) -> None:
    print(f"doctor_ok: {report['doctor_ok']}")
    print(f"structural_ok: {report['structural_ok']}")
    for check in report["checks"]:
        state = "PASS" if check["ok"] else check["severity"].upper()
        print(f"- {state} {check['name']}: {check['detail']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--admission", action="store_true", help="fail when structural checks are unsafe")
    args = parser.parse_args()
    config = load_config()
    report = collect(config)
    write_outputs(report, config)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)
    return 2 if args.admission and not report["structural_ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
