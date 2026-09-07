"""Regression tests for SRV-1 server pressure classification."""

import importlib.util
import json
import stat
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "srv1-ops" / "scripts" / "server-analysis.py"
CLEANUP_SCRIPT = REPO / "modules" / "srv1-ops" / "scripts" / "cleanup-local.sh"


def _load():
    spec = importlib.util.spec_from_file_location("server_analysis", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(*, swap: float, mem_mib: float, disk: float = 50.0) -> dict:
    return {
        "ts": "2026-09-05T04:00:00+00:00",
        "system": {
            "disk_pct": disk,
            "disk_free_gib": 100.0,
            "swap_pct": swap,
            "mem_available_mib": mem_mib,
            "load": {"1m": 0.1},
            "psi": {"cpu_some_avg10": 0.0, "io_some_avg10": 0.0},
        },
        "reasons": [],
        "top_cpu": [],
        "top_mem": [],
        "mode": "base",
    }


def test_high_swap_with_ample_memory_is_not_an_issue() -> None:
    module = _load()
    issues, summary = module.analyze_trends([_entry(swap=99.8, mem_mib=12_288)])
    assert not [item for item in issues if item["type"] == "swap"]
    assert summary["swap_pressure"] == "normal-cold-pages"


def test_high_swap_with_low_memory_is_critical() -> None:
    module = _load()
    issues, summary = module.analyze_trends([_entry(swap=99.8, mem_mib=1_024)])
    swap = next(item for item in issues if item["type"] == "swap")
    assert swap["severity"] == "critical"
    assert "1024 MiB" in swap["detail"]
    assert summary["swap_pressure"] == "memory-pressure"


def test_high_swap_with_intermediate_memory_is_warning() -> None:
    module = _load()
    issues, summary = module.analyze_trends([_entry(swap=90.0, mem_mib=3_072)])
    swap = next(item for item in issues if item["type"] == "swap")
    assert swap["severity"] == "warning"
    assert summary["swap_pressure"] == "memory-pressure"


def test_disk_severity_uses_latest_sample_not_stale_window_average() -> None:
    module = _load()
    entries = [
        _entry(swap=0.0, mem_mib=12_288, disk=95.0),
        _entry(swap=0.0, mem_mib=12_288, disk=90.0),
    ]
    issues, summary = module.analyze_trends(entries)
    disk = next(item for item in issues if item["type"] == "disk")
    assert disk["severity"] == "warning"
    assert disk["value"] == "90.0%"
    assert "média 15min 92.5%" in disk["detail"]
    assert summary["disk_pct"] == "90.0%"
    assert summary["disk_avg_pct"] == "92.5%"


def test_container_auto_fix_registry_is_fail_closed_and_secret_free() -> None:
    module = _load()
    source = SCRIPT.read_text()
    assert module.KNOWN_FIXES == {}
    assert ("POSTGRES_" + "PASSWORD" + "=") not in source
    assert "docker run" not in source
    assert "sudo docker compose" not in source


def test_unknown_crash_loop_is_not_restarted(monkeypatch) -> None:
    module = _load()
    calls = []
    monkeypatch.setattr(module, "run_cmd", lambda *args, **kwargs: calls.append(args))
    applied = module.auto_fix_crash_loop({"name": "unknown", "runtime": "podman", "known_fix": None})
    assert applied is False
    assert calls == []


def test_podman_volumes_require_explicit_review(monkeypatch) -> None:
    module = _load()
    calls = []
    monkeypatch.setattr(module, "run_cmd", lambda *args, **kwargs: calls.append(args))
    results = module.auto_reclaim_disk([
        {
            "source": "podman-volumes",
            "action": "podman volume prune -f",
            "desc": "unused volumes",
            "auto_apply": False,
        }
    ])
    assert results == ["podman-volumes: SKIP revisão explícita necessária"]
    assert calls == []


def test_journal_observation_does_not_count_as_applied_fix(monkeypatch) -> None:
    module = _load()
    calls = []

    def run(command, timeout=30):
        calls.append(command)
        if "journalctl" in command:
            return "sample error", "", 0
        if "du -sh" in command:
            return "", "", 0
        return "", "", 0

    monkeypatch.setattr(module, "run_cmd", run)
    monkeypatch.setattr(module, "detect_crash_loops", lambda: [])
    monkeypatch.setattr(module, "analyze_disk_deep", lambda: [])
    summary = {}
    fixes = module.auto_fix([], summary)
    assert fixes == []
    assert summary["journal_error_count"] == 1


def test_disk_cleanup_uses_governed_light_unit_and_persistent_cooldown(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load()
    state_path = tmp_path / "server-analysis-remediation.json"
    lock_path = tmp_path / "server-analysis-remediation.lock"
    monkeypatch.setattr(module, "DISK_REMEDIATION_STATE_FILE", state_path)
    monkeypatch.setattr(module, "DISK_REMEDIATION_LOCK_FILE", lock_path)
    monkeypatch.setattr(module, "DISK_CLEANUP_COOLDOWN_SECONDS", 6 * 60 * 60)

    calls = []

    def run(command, timeout=30):
        calls.append((command, timeout))
        return "", "", 0

    monkeypatch.setattr(module, "run_cmd", run)

    first = module.attempt_disk_cleanup(now=1_000.0)
    second = module.attempt_disk_cleanup(now=1_900.0)
    third = module.attempt_disk_cleanup(now=1_000.0 + 6 * 60 * 60)

    expected = "systemctl --user start resource-governor-post-build-cleanup.service"
    assert first["status"] == "success"
    assert second["status"] == "cooldown"
    assert second["remaining_seconds"] == 6 * 60 * 60 - 900
    assert third["status"] == "success"
    assert calls == [(expected, 120), (expected, 120)]

    state = json.loads(state_path.read_text())
    assert state["last_attempt_ts"] == third["attempted_at"]
    assert state["last_success_ts"] == third["attempted_at"]
    assert state["last_result"] == "success"
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600


def test_disk_cleanup_cooldown_is_observation_not_applied_fix(monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(module, "log", lambda *_: None)
    monkeypatch.setattr(module, "detect_crash_loops", lambda: [])
    monkeypatch.setattr(module, "analyze_disk_deep", lambda: [])
    monkeypatch.setattr(
        module,
        "attempt_disk_cleanup",
        lambda: {"status": "cooldown", "remaining_seconds": 12_345},
    )

    def run(command, timeout=30):
        if "journalctl" in command:
            return "", "", 0
        return "", "", 0

    monkeypatch.setattr(module, "run_cmd", run)
    summary = {}
    fixes = module.auto_fix(
        [{"type": "disk", "severity": "critical", "detail": "disk critical"}],
        summary,
    )

    assert fixes == []
    assert summary["disk_cleanup"] == {
        "status": "cooldown",
        "remaining_seconds": 12_345,
    }


def test_cleanup_local_never_auto_prunes_podman_volumes() -> None:
    source = CLEANUP_SCRIPT.read_text()
    assert "podman volume prune -f" not in source
    assert "SKIP podman volume prune: revisão explícita necessária" in source
