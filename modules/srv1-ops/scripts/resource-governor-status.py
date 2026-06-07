#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve()
MODULE = SCRIPT.parent.parent
CONFIG_PATH = MODULE / 'configs' / 'resource-governor.env'
LOG_DIR_DEFAULT = Path.home() / '.logs' / 'resource-governor'
LIVE_SYSTEMD_DIR = Path.home() / '.config' / 'systemd' / 'user'
DEFAULT_RUNTIME_OVERRIDE = Path.home() / '.config' / 'omni' / 'resource-governor.runtime.env'
DEFAULT_WATCHDOG_STATE = Path.home() / '.local' / 'state' / 'omni' / 'resource-governor-watchdog.json'
DEFAULT_WATCHDOG_LOG = Path.home() / '.logs' / 'resource-governor' / 'watchdog.log'


def load_config() -> dict[str, str]:
    data: dict[str, str] = {
        'RG_LOG_DIR': str(LOG_DIR_DEFAULT),
        'RG_ROOT_DEVICE': '/dev/sda',
        'RG_RUNTIME_OVERRIDE_FILE': str(DEFAULT_RUNTIME_OVERRIDE),
        'RG_WATCHDOG_STATE_FILE': str(DEFAULT_WATCHDOG_STATE),
        'RG_WATCHDOG_LOG_FILE': str(DEFAULT_WATCHDOG_LOG),
    }
    if CONFIG_PATH.exists():
        for raw in CONFIG_PATH.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    runtime_override = Path(os.path.expanduser(data['RG_RUNTIME_OVERRIDE_FILE']))
    if runtime_override.exists():
        for raw in runtime_override.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def run(cmd: list[str], env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    return proc.stdout.strip() or proc.stderr.strip()


def main() -> int:
    config = load_config()
    log_dir = Path(os.path.expanduser(config['RG_LOG_DIR']))
    latest_json = log_dir / 'latest.json'
    latest_audit = log_dir / 'latest-audit.txt'
    runtime_override = Path(os.path.expanduser(config['RG_RUNTIME_OVERRIDE_FILE']))
    watchdog_state = Path(os.path.expanduser(config['RG_WATCHDOG_STATE_FILE']))
    watchdog_log = Path(os.path.expanduser(config['RG_WATCHDOG_LOG_FILE']))
    env = os.environ.copy()
    env.setdefault('XDG_RUNTIME_DIR', '/run/user/1001')
    env.setdefault('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/run/user/1001/bus')

    print(f'config: {CONFIG_PATH}')
    print(f'logs:   {log_dir}')
    print(f'device: {config.get("RG_ROOT_DEVICE", "/dev/sda")}')
    print(f'runtime-override: {runtime_override} ({"ok" if runtime_override.exists() else "missing"})')
    print(f'watchdog-state:   {watchdog_state} ({"ok" if watchdog_state.exists() else "missing"})')
    print(f'watchdog-log:     {watchdog_log} ({"ok" if watchdog_log.exists() else "missing"})')
    print('')
    print('profiles:')
    for profile in ('BUILDS', 'INTERACTIVE', 'TRANSFERS'):
        prefix = f'RG_PROFILE_{profile}_'
        print(f"- {profile.lower()}: slice={config.get(prefix + 'SLICE', '?')} cpu={config.get(prefix + 'CPU_QUOTA', '?')} mem_high={config.get(prefix + 'MEMORY_HIGH', '?')} mem_max={config.get(prefix + 'MEMORY_MAX', '?')} swap_max={config.get(prefix + 'MEMORY_SWAP_MAX', '?')} io_read={config.get(prefix + 'IO_READ_BW', '?')} io_write={config.get(prefix + 'IO_WRITE_BW', '?')}")

    print('')
    print('repo_units:')
    for name in [
        'omni-builds.slice',
        'omni-interactive.slice',
        'omni-transfers.slice',
        'resource-governor-snapshot.service',
        'resource-governor-snapshot.timer',
        'resource-governor-audit.service',
        'resource-governor-audit.timer',
        'resource-governor-watchdog.service',
        'resource-governor-watchdog.timer',
    ]:
        repo_path = MODULE / 'systemd' / name
        live_path = LIVE_SYSTEMD_DIR / name
        print(f'- {name}: repo={"ok" if repo_path.exists() else "missing"} live={"ok" if live_path.exists() else "missing"}')

    print('')
    print('systemctl --user:')
    timers = run(['systemctl', '--user', 'list-timers', '--all', '--no-pager'], env=env)
    matches = [line for line in timers.splitlines() if 'resource-governor' in line or 'omni-' in line]
    if matches:
        for line in matches:
            print(line)
    else:
        print('no live resource-governor timers/slices detected')

    print('')
    if latest_json.exists():
        data = json.loads(latest_json.read_text())
        print('latest_perf:')
        print(f"- timestamp: {data.get('ts', '?')}")
        system = data.get('system', {})
        print(f"- disk_root_pct: {system.get('disk_pct')}")
        print(f"- mem_available_mib: {system.get('mem_available_mib')}")
        print(f"- swap_used_pct: {system.get('swap_pct')}")
        print(f"- mode: {data.get('mode')}")
        print(f"- reasons: {data.get('reasons') or 'none'}")
        print(f"- top_cpu: {[x.get('pid') for x in (data.get('top_cpu') or [])[:5]]}")
    else:
        print('latest_perf: missing')

    print('')
    if latest_audit.exists():
        print(f'latest_audit: {latest_audit}')
    else:
        print('latest_audit: missing')

    print('')
    if watchdog_state.exists():
        data = json.loads(watchdog_state.read_text())
        print('watchdog:')
        print(f"- runtime_mode: {data.get('runtime_mode')}")
        print(f"- last_reasons: {', '.join(data.get('last_reasons') or ['none'])}")
        print(f"- total_cycles: {data.get('total_cycles')}")
        last_sys = data.get('last_system', {})
        print(f"- last_disk: {last_sys.get('disk_pct')}%")
        print(f"- last_swap: {last_sys.get('swap_pct')}%")
        print(f"- last_mem_available: {last_sys.get('mem_available_mib')} MiB")
    else:
        print('watchdog: missing')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
