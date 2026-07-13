"""Regression tests for the resource-governor execution environment."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
REPO_CLI = REPO / "cli"

if str(REPO_CLI) not in sys.path:
    sys.path.insert(0, str(REPO_CLI))

from omni import srv1_ops


def load_script_module(name: str, relative_path: str):
    path = REPO / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_user_systemd_env_replaces_desktop_session_bus(monkeypatch):
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/dbus-stale")
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(srv1_ops.os, "getuid", lambda: 4242)

    env = srv1_ops._user_systemd_env()

    assert env["XDG_RUNTIME_DIR"] == "/run/user/4242"
    assert env["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/run/user/4242/bus"


def test_build_wrapper_canonicalizes_user_systemd_bus():
    wrapper = (
        REPO / "modules" / "srv1-ops" / "scripts" / "build-cpu-guard-wrapper.sh"
    ).read_text(encoding="utf-8")

    assert 'XDG_RUNTIME_DIR="$runtime_dir"' in wrapper
    assert 'DBUS_SESSION_BUS_ADDRESS="unix:path=${runtime_dir}/bus"' in wrapper
    assert 'PYTHONPATH="${repo}/cli${PYTHONPATH:+:${PYTHONPATH}}"' in wrapper
    assert "python3 -m omni srv1-ops resources run builds" in wrapper
    assert 'cd "$repo"' not in wrapper
    assert 'candidate="${HOME}/.cargo/bin/${name}"' in wrapper
    assert 'python3 -m omni srv1-ops resources run builds -- "$real_cmd" "$@"\n  exit $?' in wrapper
    assert "inside_build_cgroup" in wrapper
    assert 'grep -q \'omni-builds\'' in wrapper


def test_resource_run_preserves_callers_working_directory(monkeypatch):
    calls: list[tuple[list[str], Path | str | None]] = []

    def fake_run(cmd, *, env=None, cwd=None):
        calls.append((cmd, cwd))
        return 0

    monkeypatch.setattr(srv1_ops, "_run", fake_run)

    with pytest.raises(SystemExit) as exc:
        srv1_ops.resource_run.callback(
            "builds", False, False, ("/usr/bin/make", "--version")
        )

    assert exc.value.code == 0
    assert calls[-1][1] == Path.cwd()


def test_build_profile_uses_single_host_semaphore(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, *, env=None, cwd=None):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(srv1_ops, "_run", fake_run)
    monkeypatch.setattr(
        srv1_ops,
        "_resource_config",
        lambda: {
            **srv1_ops.RESOURCE_DEFAULTS,
            "RG_PROFILE_BUILDS_SLICE": "omni-builds.slice",
            "RG_PROFILE_BUILDS_SERIALIZE": "1",
            "RG_PROFILE_BUILDS_QUEUE_TIMEOUT_SEC": "60",
            "RG_PROFILE_BUILDS_LOCK_FILE": str(tmp_path / "build.lock"),
        },
    )

    with pytest.raises(SystemExit):
        srv1_ops.resource_run.callback("builds", False, False, ("/usr/bin/make", "all"))

    scope = calls[-1]
    assert "/usr/bin/flock" in scope
    assert "--wait=60" in scope
    assert str(tmp_path / "build.lock") in scope


def test_build_admission_fails_closed_before_systemd_scope(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, *, env=None, cwd=None):
        calls.append(cmd)
        if cmd[-1:] == ["--admission"]:
            return 2
        return 0

    monkeypatch.setattr(srv1_ops, "_run", fake_run)
    monkeypatch.setattr(
        srv1_ops,
        "_resource_config",
        lambda: {
            **srv1_ops.RESOURCE_DEFAULTS,
            "RG_PROFILE_BUILDS_SLICE": "omni-builds.slice",
            "RG_ADMISSION_STRUCTURAL_FAIL_CLOSED": "1",
            "RG_PROFILE_BUILDS_LOCK_FILE": str(tmp_path / "build.lock"),
        },
    )

    with pytest.raises(srv1_ops.click.ClickException, match="admission gate recusou"):
        srv1_ops.resource_run.callback("builds", False, False, ("/usr/bin/make", "all"))

    assert not any(cmd and cmd[0] == "systemd-run" for cmd in calls)


def test_doctor_computes_host_total_cpu_quota(monkeypatch):
    doctor = load_script_module(
        "resource_governor_doctor_quota",
        "modules/srv1-ops/scripts/resource-governor-doctor.py",
    )
    monkeypatch.setattr(doctor.os, "cpu_count", lambda: 4)
    assert doctor.expected_cpu_max({"RG_PROFILE_BUILDS_CPU_TOTAL_PCT": "20"}) == "80000 100000"


def test_doctor_ignores_its_own_launcher_chain(monkeypatch):
    doctor = load_script_module(
        "resource_governor_doctor_ancestors",
        "modules/srv1-ops/scripts/resource-governor-doctor.py",
    )
    monkeypatch.setattr(doctor, "self_and_ancestor_pids", lambda: {100, 200})
    monkeypatch.setattr(
        doctor,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd,
            0,
            stdout="100 99.0 pytest -q\n300 50.0 make all\n",
            stderr="",
        ),
    )
    monkeypatch.setattr(doctor.Path, "read_text", lambda self: "0::/user.slice/not-governed\n")

    escapes = doctor.hot_build_escapes()

    assert [item["pid"] for item in escapes] == [300]


def test_doctor_detects_structural_quota_drift(monkeypatch, tmp_path):
    doctor = load_script_module(
        "resource_governor_doctor_drift",
        "modules/srv1-ops/scripts/resource-governor-doctor.py",
    )
    cgroup = tmp_path / "omni-builds.slice"
    cgroup.mkdir()
    (cgroup / "cpu.max").write_text("max 100000\n")
    hygiene = tmp_path / "hygiene.json"
    hygiene.write_text("{}\n")
    audit = tmp_path / "audit.json"
    audit.write_text("{}\n")
    monkeypatch.setattr(doctor, "build_cgroup", lambda: cgroup)
    monkeypatch.setattr(doctor, "legacy_unit_state", lambda: {"enabled": "not-found", "active": "inactive", "unsafe": False})
    monkeypatch.setattr(doctor, "LEGACY_CGROUP", tmp_path / "legacy")
    monkeypatch.setattr(doctor, "legacy_transient_count", lambda: 0)
    monkeypatch.setattr(doctor, "hot_build_escapes", lambda max_cpus=None: [])
    monkeypatch.setattr(doctor, "user_unit_state", lambda unit: {"enabled": "enabled", "active": "active", "healthy": True})
    monkeypatch.setattr(doctor, "cpu_psi_avg10", lambda: 0.0)
    monkeypatch.setattr(doctor, "swap_used_pct", lambda: 0.0)
    monkeypatch.setattr(doctor.os, "cpu_count", lambda: 4)

    report = doctor.collect(
        {
            "RG_PROFILE_BUILDS_CPU_TOTAL_PCT": "20",
            "RG_HYGIENE_STATE_FILE": str(hygiene),
            "RG_AUDIT_STATE_FILE": str(audit),
            "RG_PROFILE_BUILDS_LOCK_FILE": str(tmp_path / "build.lock"),
            "RG_DOCTOR_QUEUE_MAX_AGE_SEC": "7200",
            "RG_DOCTOR_AUDIT_MAX_AGE_SEC": "172800",
            "RG_DOCTOR_CPU_PSI_WARN_AVG10": "70",
            "RG_DOCTOR_SWAP_WARN_PCT": "85",
        }
    )

    assert report["structural_ok"] is False
    quota = next(check for check in report["checks"] if check["name"] == "build_cpu_quota")
    assert quota["ok"] is False


def test_cgroup_init_updates_systemd_runtime_quota_before_workloads():
    script = (
        REPO / "modules" / "srv1-ops" / "scripts" / "resource-governor-cgroup-init.sh"
    ).read_text(encoding="utf-8")

    assert 'quota_pct="$(profile_cpu_quota_pct "$key")"' in script
    assert 'systemctl --user set-property --runtime' in script
    assert '"$slice" "CPUQuota=${quota_pct}%"' in script


def test_post_build_scheduler_uses_bounded_queue(monkeypatch):
    calls: list[list[str]] = []

    def fake_subprocess_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="queued: cleanup + snapshot + audit\n", stderr="")

    monkeypatch.setattr(srv1_ops.subprocess, "run", fake_subprocess_run)
    output = srv1_ops._schedule_post_workload_hygiene({}, "test")

    assert output == ["queued: cleanup + snapshot + audit"]
    assert calls[0][1].endswith("resource-governor-hygiene-queue.py")
    assert "systemd-run" not in calls[0]


def test_hygiene_queue_coalesces_without_moving_deadlines(monkeypatch, tmp_path):
    queue = load_script_module(
        "resource_governor_hygiene_queue",
        "modules/srv1-ops/scripts/resource-governor-hygiene-queue.py",
    )
    monkeypatch.setattr(queue, "STATE_DIR", tmp_path)
    monkeypatch.setattr(queue, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(queue, "LOCK_FILE", tmp_path / "queue.lock")
    monkeypatch.setattr(queue, "METRICS_FILE", tmp_path / "textfile" / "governor.prom")
    monkeypatch.setattr(queue, "legacy_transient_count", lambda: 0)
    monkeypatch.setattr(queue, "legacy_scanner_active", lambda: 0)
    active: set[str] = set()
    restarts: list[str] = []

    def fake_run_systemctl(*args):
        if args[0] == "is-active":
            return subprocess.CompletedProcess(args, 0 if args[-1] in active else 3, "", "")
        if args[0] == "restart":
            active.add(args[1])
            restarts.append(args[1])
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(args)

    monkeypatch.setattr(queue, "run_systemctl", fake_run_systemctl)

    assert queue.request("first") == 0
    assert queue.request("second") == 0
    assert len(restarts) == 3
    state = queue.load_state()
    assert state["requests_total"] == 2
    assert state["coalesced_total"] == 1
    assert (tmp_path / "textfile").stat().st_mode & 0o777 == 0o755
    assert queue.METRICS_FILE.stat().st_mode & 0o777 == 0o644


def test_audit_has_nonblocking_singleton_lock(tmp_path):
    audit = load_script_module(
        "resource_governor_audit",
        "modules/srv1-ops/scripts/resource-governor-audit.py",
    )
    lock_path = tmp_path / "audit.lock"
    first = audit.acquire_audit_lock(lock_path)
    assert first is not None
    assert audit.acquire_audit_lock(lock_path) is None
    first.close()


def test_audit_treats_optional_container_cli_as_unavailable(monkeypatch):
    audit = load_script_module(
        "resource_governor_audit_optional_cli",
        "modules/srv1-ops/scripts/resource-governor-audit.py",
    )

    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(audit.subprocess, "run", missing)
    assert audit.run(["docker", "images"]) == "unavailable: docker"


def test_heavy_hygiene_services_run_in_collective_build_slice():
    systemd = REPO / "modules" / "srv1-ops" / "systemd"
    for name in (
        "resource-governor-post-build-cleanup.service",
        "resource-governor-post-build-snapshot.service",
        "resource-governor-audit.service",
        "resource-governor-snapshot.service",
    ):
        content = (systemd / name).read_text()
        assert "Slice=omni-builds.slice" in content
        assert "OMNI_RESOURCE_HYGIENE_ACTIVE=1" in content


def test_graphify_auto_update_uses_build_slice_and_semaphore():
    content = (
        REPO
        / "modules"
        / "srv1-ops"
        / "systemd"
        / "gsd-graphify-auto-update.service"
    ).read_text()
    assert "Slice=omni-builds.slice" in content
    assert "/usr/bin/flock --wait=7200" in content
    assert "resource-governor-builds.lock" in content


def test_patcher_classifies_graphify_and_pytest_as_builds():
    patcher = load_script_module(
        "resource_governor_patcher",
        "modules/srv1-ops/scripts/resource-governor-patcher.py",
    )
    assert patcher.classify("/home/ubuntu/.local/bin/graphify update .") == (
        "builds",
        "graphify-index",
    )
    assert patcher.classify("/repo/.venv/bin/python /repo/.venv/bin/pytest -q") == (
        "builds",
        "pytest",
    )
    assert patcher.classify("/home/ubuntu/.local/bin/uv run pytest -q") == (
        "builds",
        "uv-pytest",
    )


def test_status_normalizes_snapshot_schema():
    status = load_script_module(
        "resource_governor_status",
        "modules/srv1-ops/scripts/resource-governor-status.py",
    )
    perf = status.normalize_latest_perf(
        {
            "timestamp": "2026-07-13T02:23:21-03:00",
            "disk_root_pct": 74.9,
            "mem_available_mib": 11862.8,
            "swap_used_pct": 91.5,
            "alerts": ["swap-high"],
            "top_cpu": [{"pid": 123}],
        }
    )
    assert perf["timestamp"] == "2026-07-13T02:23:21-03:00"
    assert perf["disk_pct"] == 74.9
    assert perf["swap_pct"] == 91.5
    assert perf["mode"] == "snapshot"
