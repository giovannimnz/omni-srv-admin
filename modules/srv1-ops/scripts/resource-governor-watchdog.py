#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import subprocess
import signal
import shutil
from datetime import datetime
from collections import deque
from pathlib import Path

SCRIPT = Path(__file__).resolve()
MODULE = SCRIPT.parent.parent
CONFIG_PATH = MODULE / 'configs' / 'resource-governor.env'
SNAPSHOT_SCRIPT = SCRIPT.parent / 'resource-governor-snapshot.py'
AUDIT_SCRIPT = SCRIPT.parent / 'resource-governor-audit.py'
CLEANUP_SCRIPT = SCRIPT.parent / 'cleanup-local.sh'

DEFAULTS = {
    'RG_LOG_DIR': str(Path.home() / '.logs' / 'resource-governor'),
    'RG_RUNTIME_OVERRIDE_FILE': str(Path.home() / '.config' / 'omni' / 'resource-governor.runtime.env'),
    'RG_WATCHDOG_STATE_FILE': str(Path.home() / '.local' / 'state' / 'omni' / 'resource-governor-watchdog.json'),
    'RG_WATCHDOG_LOG_FILE': str(Path.home() / '.logs' / 'resource-governor' / 'watchdog.log'),
    'RG_WATCHDOG_DISK_CRITICAL_PCT': '97',
    'RG_WATCHDOG_SWAP_CRITICAL_PCT': '95',
    'RG_WATCHDOG_MEM_AVAILABLE_CRITICAL_MIB': '1536',
    'RG_WATCHDOG_PSI_IO_FULL_CRITICAL_AVG10': '2.0',
    'RG_WATCHDOG_PSI_MEMORY_FULL_CRITICAL_AVG10': '0.5',
    'RG_WATCHDOG_COOLDOWN_MINUTES': '30',
    'RG_WATCHDOG_AUDIT_COOLDOWN_MINUTES': '120',
    'RG_WATCHDOG_RECOVERY_DISK_PCT': '92',
    'RG_WATCHDOG_RECOVERY_SWAP_PCT': '70',
    'RG_WATCHDOG_RECOVERY_MEM_AVAILABLE_MIB': '4096',
    'RG_WATCHDOG_POLL_INTERVAL_SEC': '1',
    'RG_WATCHDOG_PERF_WRITE_INTERVAL_SEC': '30',
    'RG_WATCHDOG_PERF_WINDOW_SIZE': '300',
}

# Cgroup v2 paths for resource enforcement (global 85% machine ceiling)
CGROUP_SLICE = '/sys/fs/cgroup/user.slice/user-1001.slice'
DISK_DEV = '8:0'  # /dev/sda major:minor

# Global limits for user slice (85% of machine), NOT per-process.
# Per-process/per-service 50% caps belong in profiles/wrappers/containers.
CGROUP_LIMITS = {
    'cpu': '340000 100000',           # 3.4 vCPUs out of 4 (85%)
    'io': '8:0 rbps=426770432 wbps=94371840',  # ~407MB/s read, 90MB/s write (85%)
}

CONSERVATIVE_OVERRIDE = {
    # 50% limits por processo (documentado em Atius-Spec-Servers.md)
    'RG_PROFILE_BUILDS_CPU_QUOTA': '200%',
    'RG_PROFILE_BUILDS_MEMORY_HIGH': '8G',
    'RG_PROFILE_BUILDS_MEMORY_MAX': '11G',
    'RG_PROFILE_BUILDS_MEMORY_SWAP_MAX': '5G',
    'RG_PROFILE_BUILDS_IO_READ_BW': '60M',
    'RG_PROFILE_BUILDS_IO_WRITE_BW': '54M',
    'RG_PROFILE_INTERACTIVE_CPU_QUOTA': '200%',
    'RG_PROFILE_INTERACTIVE_MEMORY_HIGH': '4G',
    'RG_PROFILE_INTERACTIVE_MEMORY_MAX': '6G',
    'RG_PROFILE_INTERACTIVE_MEMORY_SWAP_MAX': '2G',
    'RG_PROFILE_INTERACTIVE_IO_READ_BW': '60M',
    'RG_PROFILE_INTERACTIVE_IO_WRITE_BW': '54M',
    'RG_PROFILE_TRANSFERS_CPU_QUOTA': '100%',
    'RG_PROFILE_TRANSFERS_MEMORY_HIGH': '2G',
    'RG_PROFILE_TRANSFERS_MEMORY_MAX': '4G',
    'RG_PROFILE_TRANSFERS_MEMORY_SWAP_MAX': '1G',
    'RG_PROFILE_TRANSFERS_IO_READ_BW': '60M',
    'RG_PROFILE_TRANSFERS_IO_WRITE_BW': '30M',
}

RUNNING = True

def handle_signal(signum, _frame):
    global RUNNING
    RUNNING = False

def load_config() -> dict[str, str]:
    data = DEFAULTS.copy()
    if CONFIG_PATH.exists():
        for raw in CONFIG_PATH.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data

def run_cmd(cmd: list[str], env: dict | None = None) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    return proc.returncode, (proc.stdout.strip() or proc.stderr.strip())

def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return (default or {}).copy()
    try:
        return json.loads(path.read_text())
    except Exception:
        return (default or {}).copy()

def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().astimezone().isoformat()}] {message}\n"
    with path.open('a') as fh:
        fh.write(line)

class PerfWindow:
    def __init__(self, maxlen: int = 300):
        self.samples: deque = deque(maxlen=maxlen)
        self.maxlen = maxlen

    def add(self, sample: dict) -> None:
        self.samples.append(sample)

    def summarize(self) -> dict:
        if not self.samples:
            return {'count': 0}
        recent = list(self.samples)
        return {
            'count': len(recent),
            'cpu_avg': sum(s.get('cpu_pct', 0) for s in recent) / len(recent),
            'mem_avg': sum(s.get('mem_pct', 0) for s in recent) / len(recent),
            'rss_avg_kib': sum(s.get('rss_kib', 0) for s in recent) / len(recent),
            'last_seen': recent[-1].get('ts'),
            'first_seen': recent[0].get('ts'),
        }

    def as_json(self) -> list[dict]:
        return list(self.samples)

def sample_processes() -> dict:
    result: dict = {}
    env = os.environ.copy()
    env['LC_ALL'] = 'C'
    out = subprocess.run(
        ['ps', '-eo', 'pid=,pcpu=,pmem=,rss=,comm=,args=', '--sort=-pcpu'],
        capture_output=True, text=True, check=False, env=env
    ).stdout
    ts = datetime.now().astimezone().isoformat()
    for line in out.splitlines():
        parts = line.split(None, 5)
        if len(parts) < 5:
            continue
        pid = parts[0]
        name = parts[4][:40]
        result[pid] = {
            'ts': ts,
            'name': name,
            'cpu_pct': float(parts[1]),
            'mem_pct': float(parts[2]),
            'rss_kib': int(parts[3]),
            'cmd': (parts[5] if len(parts) > 5 else '')[:120],
        }
    return result

def sample_system() -> dict:
    load1, load5, load15 = os.getloadavg()
    disk = shutil.disk_usage('/')
    meminfo = {}
    for raw in Path('/proc/meminfo').read_text().splitlines():
        k, v = raw.split(':', 1)
        meminfo[k] = int(v.strip().split()[0])

    swap_total = meminfo.get('SwapTotal', 0)
    swap_free = meminfo.get('SwapFree', 0)
    swap_used = max(swap_total - swap_free, 0)
    swap_pct = round((swap_used / swap_total) * 100, 2) if swap_total else 0.0

    psi = {}
    for name in ('cpu', 'memory', 'io'):
        p = Path(f'/proc/pressure/{name}')
        if p.exists():
            for raw in p.read_text().splitlines():
                parts = raw.split()
                prefix = parts[0]
                for token in parts[1:]:
                    k, v = token.split('=', 1)
                    psi[f'{name}_{prefix}_{k}'] = float(v)

    containers = {
        'podman': run_cmd(['podman', 'ps', '--format', '{{.Names}}'])[1].count('\n') or 0,
        'docker': run_cmd(['docker', 'ps', '--format', '{{.Names}}'])[1].count('\n') or 0,
    }

    return {
        'load': {'1m': round(load1,2), '5m': round(load5,2), '15m': round(load15,2)},
        'disk_total_gib': round(disk.total / (1024**3), 2),
        'disk_used_gib': round(disk.used / (1024**3), 2),
        'disk_free_gib': round(disk.free / (1024**3), 2),
        'disk_pct': round((disk.used / disk.total) * 100, 2),
        'mem_available_mib': round(meminfo.get('MemAvailable', 0) / 1024, 1),
        'swap_pct': swap_pct,
        'psi': psi,
        'containers': containers,
    }


def apply_cgroup_limits() -> list[str]:
    """Apply 50% cgroup v2 limits via sudo. Returns list of actions taken."""
    actions = []
    limit = CGROUP_LIMITS.get('cpu')
    if limit:
        rc, _ = run_cmd(['sudo', 'sh', '-c', f'echo "{limit}" > {CGROUP_SLICE}/cpu.max'])
        if rc == 0:
            actions.append('cpu→340%')
    
    limit = CGROUP_LIMITS.get('io')
    if limit:
        rc, _ = run_cmd(['sudo', 'sh', '-c', f'echo "{limit}" > {CGROUP_SLICE}/io.max'])
        if rc == 0:
            actions.append('io→90MB/s')
    
    return actions


def remove_cgroup_limits() -> list[str]:
    """Remove cgroup v2 limits, restoring to unlimited. Returns list of actions."""
    actions = []
    rc, _ = run_cmd(['sudo', 'sh', '-c', f'echo "max 100000" > {CGROUP_SLICE}/cpu.max'])
    if rc == 0:
        actions.append('cpu→unlimited')
    
    rc, _ = run_cmd(['sudo', 'sh', '-c', f'echo "" > {CGROUP_SLICE}/io.max'])
    if rc == 0:
        actions.append('io→unlimited')
    
    return actions


def main() -> int:
    global RUNNING
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    config = load_config()
    poll_interval = float(config.get('RG_WATCHDOG_POLL_INTERVAL_SEC', '1'))
    write_interval = float(config.get('RG_WATCHDOG_PERF_WRITE_INTERVAL_SEC', '30'))
    window_size = int(config.get('RG_WATCHDOG_PERF_WINDOW_SIZE', '300'))

    log_dir = Path(os.path.expanduser(config['RG_LOG_DIR']))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path(os.path.expanduser(config['RG_WATCHDOG_LOG_FILE']))
    state_path = Path(os.path.expanduser(config['RG_WATCHDOG_STATE_FILE']))
    runtime_path = Path(os.path.expanduser(config['RG_RUNTIME_OVERRIDE_FILE']))
    latest_snapshot = log_dir / 'latest.json'

    perf_file = log_dir / 'perf.jsonl'
    state = load_json(state_path, {})
    state.setdefault('runtime_mode', 'base')
    state.setdefault('last_reasons', [])
    state.setdefault('last_cleanup_ts', 0.0)
    state.setdefault('last_audit_ts', 0.0)
    state.setdefault('total_cycles', 0)

    process_windows: dict[str, PerfWindow] = {}
    last_write_ts = time.time()
    last_cleanup_ts = state.get('last_cleanup_ts', 0.0)
    last_audit_ts = state.get('last_audit_ts', 0.0)

    append_log(log_path, f'watchdog-start poll={poll_interval}s write={write_interval}s window={window_size}')

    while RUNNING:
        cycle_start = time.time()
        state['total_cycles'] += 1
        ts = datetime.now().astimezone().isoformat()

        # Sample processes + system
        system_data = sample_system()
        process_data = sample_processes()

        # Track all processes in windows
        for pid, pinfo in process_data.items():
            name = pinfo['name']
            if name not in process_windows:
                process_windows[name] = PerfWindow(window_size)
            process_windows[name].add(pinfo)

        # Detect thresholds
        reasons: list[str] = []
        if system_data['disk_pct'] >= float(config['RG_WATCHDOG_DISK_CRITICAL_PCT']):
            reasons.append('disk-critical')
        if system_data['swap_pct'] >= float(config['RG_WATCHDOG_SWAP_CRITICAL_PCT']):
            reasons.append('swap-critical')
        if system_data['mem_available_mib'] <= float(config['RG_WATCHDOG_MEM_AVAILABLE_CRITICAL_MIB']):
            reasons.append('mem-low')
        psi = system_data.get('psi', {})
        if psi.get('io_full_avg10', 0.0) >= float(config['RG_WATCHDOG_PSI_IO_FULL_CRITICAL_AVG10']):
            reasons.append('psi-io-high')
        if psi.get('memory_full_avg10', 0.0) >= float(config['RG_WATCHDOG_PSI_MEMORY_FULL_CRITICAL_AVG10']):
            reasons.append('psi-memory-high')

        # Action: threshold detected
        if reasons:
            # Apply runtime override
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            if state.get('runtime_mode') != 'conservative':
                # FIRST TIME entering conservative mode — apply cgroup limits
                cgroup_actions = apply_cgroup_limits()
                append_log(log_path, f'cgroup-limits {" ".join(cgroup_actions)} reasons={",".join(reasons)}')
                
                lines = [
                    '# generated by resource-governor-watchdog.py (continuous)',
                    f"# reasons={','.join(reasons)}",
                    f"# updated={ts}",
                    '',
                ]
                for key, value in CONSERVATIVE_OVERRIDE.items():
                    lines.append(f'{key}={value}')
                runtime_path.write_text('\n'.join(lines) + '\n')
                append_log(log_path, f'runtime-override reasons={",".join(reasons)}')
                # Apply per-profile limits via cgroup-init
                cgroup_init_script = SCRIPT.parent / 'resource-governor-cgroup-init.sh'
                if cgroup_init_script.exists():
                    run_cmd(['/bin/bash', str(cgroup_init_script)])

            state['runtime_mode'] = 'conservative'
            state['last_reasons'] = reasons

            # Cleanup on cooldown
            cooldown = float(config['RG_WATCHDOG_COOLDOWN_MINUTES']) * 60
            if (time.time() - last_cleanup_ts) >= cooldown:
                env = os.environ.copy()
                env['CLEANUP_MODE'] = 'build-hygiene'
                env['TRIGGER_REASON'] = ','.join(reasons)
                rc, output = run_cmd(['/bin/bash', str(CLEANUP_SCRIPT)], env=env)
                append_log(log_path, f'cleanup rc={rc} reasons={",".join(reasons)} disk_before={system_data["disk_pct"]}%')
                last_cleanup_ts = time.time()

            # Audit on cooldown (only for multi-critical or disk-critical)
            audit_cooldown = float(config['RG_WATCHDOG_AUDIT_COOLDOWN_MINUTES']) * 60
            if ('disk-critical' in reasons or len(reasons) >= 2) and (time.time() - last_audit_ts) >= audit_cooldown:
                rc, output = run_cmd(['python3', str(AUDIT_SCRIPT)])
                append_log(log_path, f'audit rc={rc}')
                last_audit_ts = time.time()

        else:
            state['last_reasons'] = []
            # Recovery check
            recovered = (
                system_data['disk_pct'] <= float(config['RG_WATCHDOG_RECOVERY_DISK_PCT'])
                and system_data['swap_pct'] <= float(config['RG_WATCHDOG_RECOVERY_SWAP_PCT'])
                and system_data['mem_available_mib'] >= float(config['RG_WATCHDOG_RECOVERY_MEM_AVAILABLE_MIB'])
            )
            if recovered and state.get('runtime_mode') == 'conservative' and runtime_path.exists():
                runtime_path.unlink()
                state['runtime_mode'] = 'base'
                cgroup_actions = remove_cgroup_limits()
                append_log(log_path, f'cgroup-unlimited {" ".join(cgroup_actions)} disk={system_data["disk_pct"]}% swap={system_data["swap_pct"]}% mem={system_data["mem_available_mib"]}')
                # Restore per-profile limits to base values
                cgroup_init_script = SCRIPT.parent / 'resource-governor-cgroup-init.sh'
                if cgroup_init_script.exists():
                    run_cmd(['/bin/bash', str(cgroup_init_script)])

        # Write perf data
        current_ts = time.time()
        if (current_ts - last_write_ts) >= write_interval:
            window_summaries: dict[str, dict] = {}
            for name, window in sorted(process_windows.items()):
                summary = window.summarize()
                if summary['count'] >= 2:
                    window_summaries[name] = {
                        'cpu_avg': round(summary['cpu_avg'], 2),
                        'mem_avg': round(summary['mem_avg'], 2),
                        'rss_avg_mib': round(summary['rss_avg_kib'] / 1024, 1),
                    }

            # Top consumers by CPU and MEM
            top_cpu = sorted(process_data.values(), key=lambda x: x['cpu_pct'], reverse=True)[:10]
            top_mem = sorted(process_data.values(), key=lambda x: x['mem_pct'], reverse=True)[:10]

            perf_entry = {
                'ts': ts,
                'cycle': state['total_cycles'],
                'system': {
                    'load': system_data['load'],
                    'disk_pct': system_data['disk_pct'],
                    'disk_free_gib': system_data['disk_free_gib'],
                    'mem_available_mib': system_data['mem_available_mib'],
                    'swap_pct': system_data['swap_pct'],
                    'psi': {k: round(v, 2) for k, v in psi.items()},
                    'containers': system_data['containers'],
                },
                'mode': state.get('runtime_mode'),
                'reasons': reasons or None,
                'top_cpu': [{'pid': p.get('name','?'), 'cpu': p['cpu_pct'], 'mem': p['mem_pct']} for p in top_cpu],
                'top_mem': [{'pid': p.get('name','?'), 'mem': p['mem_pct'], 'cpu': p['cpu_pct'], 'rss_mib': round(p['rss_kib']/1024, 1)} for p in top_mem],
                'process_summaries': window_summaries,
            }

            fh = perf_file.open('a')
            fh.write(json.dumps(perf_entry, ensure_ascii=False) + '\n')
            fh.close()

            # Keep latest.json current
            latest_json = log_dir / 'latest.json'
            latest_json.write_text(json.dumps(perf_entry, indent=2, ensure_ascii=False) + '\n')

            last_write_ts = current_ts

        # Save state
        state['last_system'] = {
            'disk_pct': system_data['disk_pct'],
            'swap_pct': system_data['swap_pct'],
            'mem_available_mib': system_data['mem_available_mib'],
        }
        state['last_cleanup_ts'] = last_cleanup_ts
        state['last_audit_ts'] = last_audit_ts
        write_json(state_path, state)

        # Sleep for remaining of cycle
        elapsed = time.time() - cycle_start
        if elapsed < poll_interval:
            time.sleep(poll_interval - elapsed)

    append_log(log_path, f'watchdog-stop total_cycles={state["total_cycles"]}')
    write_json(state_path, state)
    return 0

def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')

if __name__ == '__main__':
    raise SystemExit(main())
