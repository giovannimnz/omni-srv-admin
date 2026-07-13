#!/usr/bin/env python3
"""Bounded/coalescing post-build hygiene queue for the resource governor."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_DIR = Path.home() / ".local" / "state" / "omni"
STATE_FILE = STATE_DIR / "resource-governor-hygiene.json"
LOCK_FILE = STATE_DIR / "resource-governor-hygiene.lock"
METRICS_FILE = STATE_DIR / "textfile-collector" / "resource-governor.prom"
STAGE_TIMERS = {
    "cleanup": "resource-governor-post-build-cleanup.timer",
    "snapshot": "resource-governor-post-build-snapshot.timer",
    "audit": "resource-governor-post-build-audit.timer",
}
STAGE_SERVICES = {
    "cleanup": "resource-governor-post-build-cleanup.service",
    "snapshot": "resource-governor-post-build-snapshot.service",
    "audit": "resource-governor-audit.service",
}


def now() -> str:
    return datetime.now().astimezone().isoformat()


def user_systemd_env() -> dict[str, str]:
    env = os.environ.copy()
    runtime_dir = f"/run/user/{os.getuid()}"
    env["XDG_RUNTIME_DIR"] = runtime_dir
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"
    return env


def run_systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        check=False,
        env=user_systemd_env(),
    )


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(STATE_FILE)


def stage_pending(stage: str, timer: str) -> bool:
    timer_active = run_systemctl("is-active", "--quiet", timer).returncode == 0
    service_active = (
        run_systemctl("is-active", "--quiet", STAGE_SERVICES[stage]).returncode == 0
    )
    return timer_active or service_active


def legacy_transient_count() -> int:
    proc = run_systemctl(
        "list-units", "omni-post-build-*", "--all", "--no-legend", "--plain"
    )
    return sum(1 for line in proc.stdout.splitlines() if line.strip())


def legacy_scanner_active() -> int:
    proc = subprocess.run(
        ["systemctl", "is-active", "--quiet", "atius-build-throttle.timer"],
        check=False,
    )
    return int(proc.returncode == 0)


def live_pending_map() -> dict[str, bool]:
    return {stage: stage_pending(stage, timer) for stage, timer in STAGE_TIMERS.items()}


def queued_pending_map(state: dict[str, Any]) -> dict[str, bool]:
    saved = state.get("pending") or {}
    return {stage: bool(saved.get(stage, False)) for stage in STAGE_TIMERS}


def write_metrics(state: dict[str, Any], pending: dict[str, bool]) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # node-exporter runs as nobody (65534) and mounts this directory read-only.
    # Metrics contain no secrets; keep the directory traversable/readable.
    METRICS_FILE.parent.chmod(0o755)
    lines = [
        "# HELP omni_resource_governor_hygiene_requests_total Post-build hygiene requests.",
        "# TYPE omni_resource_governor_hygiene_requests_total counter",
        f"omni_resource_governor_hygiene_requests_total {int(state.get('requests_total', 0))}",
        "# HELP omni_resource_governor_hygiene_coalesced_total Requests merged into an existing queue.",
        "# TYPE omni_resource_governor_hygiene_coalesced_total counter",
        f"omni_resource_governor_hygiene_coalesced_total {int(state.get('coalesced_total', 0))}",
        "# HELP omni_resource_governor_hygiene_schedule_failures_total Failed timer restarts.",
        "# TYPE omni_resource_governor_hygiene_schedule_failures_total counter",
        f"omni_resource_governor_hygiene_schedule_failures_total {int(state.get('schedule_failures_total', 0))}",
        "# HELP omni_resource_governor_hygiene_pending Whether a bounded stage timer is pending.",
        "# TYPE omni_resource_governor_hygiene_pending gauge",
    ]
    for stage in STAGE_TIMERS:
        lines.append(
            f'omni_resource_governor_hygiene_pending{{stage="{stage}"}} {int(pending[stage])}'
        )
    lines.extend(
        [
            "# HELP omni_resource_governor_metrics_timestamp_seconds Last successful metrics refresh.",
            "# TYPE omni_resource_governor_metrics_timestamp_seconds gauge",
            f"omni_resource_governor_metrics_timestamp_seconds {int(time.time())}",
            "# HELP omni_resource_governor_legacy_transient_units Legacy timestamped post-build units loaded.",
            "# TYPE omni_resource_governor_legacy_transient_units gauge",
            f"omni_resource_governor_legacy_transient_units {legacy_transient_count()}",
            "# HELP omni_resource_governor_legacy_scanner_active Whether atius-build-throttle.timer is active.",
            "# TYPE omni_resource_governor_legacy_scanner_active gauge",
            f"omni_resource_governor_legacy_scanner_active {legacy_scanner_active()}",
        ]
    )
    tmp = METRICS_FILE.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n")
    tmp.chmod(0o644)
    tmp.replace(METRICS_FILE)


def locked_state() -> tuple[Any, dict[str, Any]]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_fh = LOCK_FILE.open("a+")
    fcntl.flock(lock_fh, fcntl.LOCK_EX)
    return lock_fh, load_state()


def request(reason: str) -> int:
    lock_fh, state = locked_state()
    try:
        before = queued_pending_map(state)
        failures: list[str] = []
        # A pending batch owns all three stages.  Further requests only update
        # counters/reason; they never push deadlines forward or create more
        # work, so a continuous build stream cannot starve hygiene forever.
        if not any(before.values()):
            for stage, timer in STAGE_TIMERS.items():
                proc = run_systemctl("restart", timer)
                if proc.returncode != 0:
                    detail = (proc.stderr or proc.stdout).strip()
                    failures.append(f"{stage}: {detail or 'restart failed'}")

        state["requests_total"] = int(state.get("requests_total", 0)) + 1
        if any(before.values()):
            state["coalesced_total"] = int(state.get("coalesced_total", 0)) + 1
        state["schedule_failures_total"] = int(
            state.get("schedule_failures_total", 0)
        ) + len(failures)
        state["last_request_at"] = now()
        state["last_reason"] = reason
        state["last_failures"] = failures
        if any(before.values()):
            after = before
        else:
            failed_stages = {failure.split(":", 1)[0] for failure in failures}
            after = {stage: stage not in failed_stages for stage in STAGE_TIMERS}
        state["pending"] = after
        state["live"] = live_pending_map()
        write_state(state)
        write_metrics(state, after)
    finally:
        lock_fh.close()

    mode = "coalesced" if any(before.values()) else "queued"
    print(f"{mode}: cleanup + snapshot + audit; reason={reason}")
    for stage, timer in STAGE_TIMERS.items():
        print(f"- {stage}: {timer} pending={after[stage]}")
    for failure in failures:
        print(f"ERROR {failure}")
    return int(bool(failures))


def complete(stage: str) -> int:
    lock_fh, state = locked_state()
    try:
        # Also cancels a still-pending timer when the stage was run manually or
        # by the watchdog, preventing a second execution of the same batch.
        run_systemctl("stop", STAGE_TIMERS[stage])
        completed = state.setdefault("last_completed_at", {})
        completed[stage] = now()
        pending = queued_pending_map(state)
        if pending.get(stage):
            pending[stage] = False
        state["pending"] = pending
        state["live"] = live_pending_map()
        write_state(state)
        write_metrics(state, pending)
    finally:
        lock_fh.close()
    return 0


def status(json_output: bool) -> int:
    lock_fh, state = locked_state()
    try:
        pending = queued_pending_map(state)
        state["live"] = live_pending_map()
        state["pending"] = pending
        write_state(state)
        write_metrics(state, pending)
    finally:
        lock_fh.close()
    if json_output:
        print(json.dumps(state, indent=2, sort_keys=True))
    else:
        print(f"state: {STATE_FILE}")
        print(f"metrics: {METRICS_FILE}")
        print(f"requests_total: {state.get('requests_total', 0)}")
        print(f"coalesced_total: {state.get('coalesced_total', 0)}")
        print(f"schedule_failures_total: {state.get('schedule_failures_total', 0)}")
        print(f"last_request_at: {state.get('last_request_at', 'never')}")
        print(f"last_reason: {state.get('last_reason', 'none')}")
        for stage in STAGE_TIMERS:
            print(f"pending_{stage}: {pending[stage]}")
            print(f"live_{stage}: {state['live'][stage]}")
        print(f"legacy_transient_units: {legacy_transient_count()}")
        print(f"legacy_scanner_active: {legacy_scanner_active()}")
    return 0


def refresh() -> int:
    lock_fh, state = locked_state()
    try:
        state["live"] = live_pending_map()
        pending = queued_pending_map(state)
        write_state(state)
        write_metrics(state, pending)
    finally:
        lock_fh.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    request_parser = sub.add_parser("request")
    request_parser.add_argument("--reason", default="profile=builds")
    complete_parser = sub.add_parser("complete")
    complete_parser.add_argument("stage", choices=sorted(STAGE_TIMERS))
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    sub.add_parser("refresh")
    args = parser.parse_args()
    if args.command == "request":
        return request(args.reason)
    if args.command == "complete":
        return complete(args.stage)
    if args.command == "refresh":
        return refresh()
    return status(args.json)


if __name__ == "__main__":
    raise SystemExit(main())
