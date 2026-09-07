"""Swap saturation is pressure only when available memory is constrained."""

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "srv1-ops" / "scripts" / "resource-governor-watchdog.py"


def _load():
    spec = importlib.util.spec_from_file_location("resource_watchdog_swap", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config() -> dict[str, str]:
    return {
        "RG_WATCHDOG_DISK_CRITICAL_PCT": "92",
        "RG_WATCHDOG_SWAP_CRITICAL_PCT": "85",
        "RG_WATCHDOG_SWAP_MEM_AVAILABLE_OK_MIB": "4096",
        "RG_WATCHDOG_MEM_AVAILABLE_CRITICAL_MIB": "1536",
        "RG_WATCHDOG_PSI_IO_FULL_CRITICAL_AVG10": "2.0",
        "RG_WATCHDOG_PSI_MEMORY_FULL_CRITICAL_AVG10": "0.5",
        "RG_WATCHDOG_RECOVERY_DISK_PCT": "92",
        "RG_WATCHDOG_RECOVERY_SWAP_PCT": "70",
        "RG_WATCHDOG_RECOVERY_MEM_AVAILABLE_MIB": "4096",
    }


def _system(*, disk=50.0, swap=99.8, mem=12_288.0, io=0.0, memory_psi=0.0):
    return {
        "disk_pct": disk,
        "swap_pct": swap,
        "mem_available_mib": mem,
        "psi": {"io_full_avg10": io, "memory_full_avg10": memory_psi},
    }


def test_watchdog_ignores_cold_swap_with_ample_memory() -> None:
    module = _load()
    assert module.pressure_reasons(_system(), _config()) == []


def test_watchdog_reports_swap_when_memory_is_constrained() -> None:
    module = _load()
    reasons = module.pressure_reasons(_system(mem=1_024), _config())
    assert "swap-critical" in reasons
    assert "mem-low" in reasons


def test_recovery_does_not_require_swapout_when_memory_is_ample() -> None:
    module = _load()
    assert module.recovery_ready(_system(disk=90.0), _config(), 5, 5) is True


def test_recovery_still_blocks_on_low_memory() -> None:
    module = _load()
    assert module.recovery_ready(_system(disk=90.0, mem=1_024), _config(), 5, 5) is False


def test_live_config_has_valid_disk_hysteresis() -> None:
    values = {}
    config_path = REPO / "modules" / "srv1-ops" / "configs" / "resource-governor.env"
    for line in config_path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    assert float(values["RG_WATCHDOG_DISK_CRITICAL_PCT"]) > float(
        values["RG_WATCHDOG_RECOVERY_DISK_PCT"]
    )
