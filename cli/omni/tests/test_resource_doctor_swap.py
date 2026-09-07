"""Resource doctor swap pressure must account for available memory."""

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "srv1-ops" / "scripts" / "resource-governor-doctor.py"


def _load():
    spec = importlib.util.spec_from_file_location("resource_doctor_swap", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report(monkeypatch, tmp_path, *, swap: float, mem_mib: float):
    doctor = _load()
    cgroup = tmp_path / "omni-builds.slice"
    cgroup.mkdir()
    (cgroup / "cpu.max").write_text("80000 100000\n")
    hygiene = tmp_path / "hygiene.json"
    hygiene.write_text('{"pending": {}}\n')
    audit = tmp_path / "audit.json"
    audit.write_text('{"status": "success", "timestamp": "2099-01-01T00:00:00+00:00"}\n')
    monkeypatch.setattr(doctor, "build_cgroup", lambda: cgroup)
    monkeypatch.setattr(doctor, "legacy_unit_state", lambda: {"enabled": "not-found", "active": "inactive", "unsafe": False})
    monkeypatch.setattr(doctor, "LEGACY_CGROUP", tmp_path / "legacy")
    monkeypatch.setattr(doctor, "legacy_transient_count", lambda: 0)
    monkeypatch.setattr(doctor, "hot_build_escapes", lambda max_cpus=None: [])
    monkeypatch.setattr(doctor, "user_unit_state", lambda _unit: {"enabled": "enabled", "active": "active", "healthy": True})
    monkeypatch.setattr(doctor, "cpu_psi_avg10", lambda: 0.0)
    monkeypatch.setattr(doctor, "swap_used_pct", lambda: swap)
    monkeypatch.setattr(doctor, "memory_available_mib", lambda: mem_mib)
    monkeypatch.setattr(doctor.os, "cpu_count", lambda: 4)
    return doctor.collect({
        "RG_PROFILE_BUILDS_CPU_TOTAL_PCT": "20",
        "RG_HYGIENE_STATE_FILE": str(hygiene),
        "RG_AUDIT_STATE_FILE": str(audit),
        "RG_PROFILE_BUILDS_LOCK_FILE": str(tmp_path / "build.lock"),
        "RG_DOCTOR_QUEUE_MAX_AGE_SEC": "7200",
        "RG_DOCTOR_AUDIT_MAX_AGE_SEC": "172800",
        "RG_DOCTOR_CPU_PSI_WARN_AVG10": "70",
        "RG_DOCTOR_SWAP_WARN_PCT": "85",
        "RG_DOCTOR_SWAP_MEM_AVAILABLE_OK_MIB": "4096",
    })


def test_high_swap_is_ok_with_ample_available_memory(monkeypatch, tmp_path) -> None:
    report = _report(monkeypatch, tmp_path, swap=99.8, mem_mib=12_288)
    swap = next(check for check in report["checks"] if check["name"] == "swap_pressure")
    assert swap["ok"] is True
    assert "mem_available_mib=12288" in swap["detail"]


def test_high_swap_warns_when_available_memory_is_low(monkeypatch, tmp_path) -> None:
    report = _report(monkeypatch, tmp_path, swap=99.8, mem_mib=1_024)
    swap = next(check for check in report["checks"] if check["name"] == "swap_pressure")
    assert swap["ok"] is False
    assert report["doctor_ok"] is False
