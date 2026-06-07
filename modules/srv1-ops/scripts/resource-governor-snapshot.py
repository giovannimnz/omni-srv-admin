#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve()
MODULE = SCRIPT.parent.parent
CONFIG_PATH = MODULE / 'configs' / 'resource-governor.env'
DEFAULT_CONFIG = {
    'RG_ROOT_DEVICE': '/dev/sda',
    'RG_LOG_DIR': str(Path.home() / '.logs' / 'resource-governor'),
    'RG_SNAPSHOT_ALERT_DISK_PCT': '95',
    'RG_SNAPSHOT_ALERT_SWAP_PCT': '85',
    'RG_SNAPSHOT_ALERT_MEM_AVAILABLE_MIB': '2048',
    'RG_SNAPSHOT_ALERT_PSI_IO_FULL_AVG10': '5.0',
    'RG_SNAPSHOT_ALERT_PSI_MEMORY_FULL_AVG10': '1.0',
}


def load_config() -> dict[str, str]:
    data = DEFAULT_CONFIG.copy()
    if CONFIG_PATH.exists():
        for raw in CONFIG_PATH.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def parse_meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    for raw in Path('/proc/meminfo').read_text().splitlines():
        key, value = raw.split(':', 1)
        out[key] = int(value.strip().split()[0])
    return out


def parse_pressure(name: str) -> dict[str, float]:
    result: dict[str, float] = {}
    path = Path('/proc/pressure') / name
    if not path.exists():
        return result
    for raw in path.read_text().splitlines():
        parts = raw.split()
        prefix = parts[0]
        for token in parts[1:]:
            k, v = token.split('=', 1)
            result[f'{prefix}_{k}'] = float(v)
    return result


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return proc.stdout.strip()


def top_processes(sort_flag: str, limit: int = 5) -> list[dict[str, str]]:
    out = run(['ps', '-eo', 'pid=,pcpu=,pmem=,rss=,comm=', f'--sort={sort_flag}'])
    rows = []
    for line in out.splitlines()[:limit]:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        rows.append({
            'pid': parts[0],
            'cpu_pct': parts[1],
            'mem_pct': parts[2],
            'rss_kib': parts[3],
            'comm': parts[4],
        })
    return rows


def count_lines(cmd: list[str]) -> int:
    out = run(cmd)
    return len([line for line in out.splitlines() if line.strip()])


def mib_from_kib(value: int) -> float:
    return round(value / 1024, 1)


def gib_from_bytes(value: int) -> float:
    return round(value / (1024 ** 3), 2)


def write_text_summary(path: Path, snapshot: dict) -> None:
    alerts = snapshot.get('alerts') or ['none']
    lines = [
        f"timestamp: {snapshot['timestamp']}",
        f"loadavg: {snapshot['loadavg']}",
        f"disk_root_pct: {snapshot['disk_root_pct']}",
        f"mem_available_mib: {snapshot['mem_available_mib']}",
        f"swap_used_pct: {snapshot['swap_used_pct']}",
        f"psi_cpu_some_avg10: {snapshot['psi']['cpu'].get('some_avg10', 0.0)}",
        f"psi_memory_full_avg10: {snapshot['psi']['memory'].get('full_avg10', 0.0)}",
        f"psi_io_full_avg10: {snapshot['psi']['io'].get('full_avg10', 0.0)}",
        f"containers: podman={snapshot['containers']['podman_running']} docker={snapshot['containers']['docker_running']}",
        f"alerts: {', '.join(alerts)}",
        '',
        'top_cpu:',
    ]
    for row in snapshot['top_cpu']:
        lines.append(f"- pid={row['pid']} comm={row['comm']} cpu={row['cpu_pct']} mem={row['mem_pct']} rss_kib={row['rss_kib']}")
    lines.append('')
    lines.append('top_mem:')
    for row in snapshot['top_mem']:
        lines.append(f"- pid={row['pid']} comm={row['comm']} cpu={row['cpu_pct']} mem={row['mem_pct']} rss_kib={row['rss_kib']}")
    path.write_text('\n'.join(lines) + '\n')


def main() -> int:
    config = load_config()
    log_dir = Path(os.path.expanduser(config['RG_LOG_DIR']))
    log_dir.mkdir(parents=True, exist_ok=True)

    meminfo = parse_meminfo()
    load1, load5, load15 = os.getloadavg()
    disk = shutil.disk_usage('/')
    disk_pct = round((disk.used / disk.total) * 100, 2)
    mem_available_mib = mib_from_kib(meminfo.get('MemAvailable', 0))
    swap_total_kib = meminfo.get('SwapTotal', 0)
    swap_free_kib = meminfo.get('SwapFree', 0)
    swap_used_kib = max(swap_total_kib - swap_free_kib, 0)
    swap_used_pct = round((swap_used_kib / swap_total_kib) * 100, 2) if swap_total_kib else 0.0
    psi = {
        'cpu': parse_pressure('cpu'),
        'memory': parse_pressure('memory'),
        'io': parse_pressure('io'),
    }
    snapshot = {
        'timestamp': datetime.now().astimezone().isoformat(),
        'host': os.uname().nodename,
        'root_device': config.get('RG_ROOT_DEVICE', '/dev/sda'),
        'loadavg': {'1m': round(load1, 2), '5m': round(load5, 2), '15m': round(load15, 2)},
        'mem_total_mib': mib_from_kib(meminfo.get('MemTotal', 0)),
        'mem_available_mib': mem_available_mib,
        'swap_total_mib': mib_from_kib(swap_total_kib),
        'swap_used_mib': mib_from_kib(swap_used_kib),
        'swap_used_pct': swap_used_pct,
        'disk_root_total_gib': gib_from_bytes(disk.total),
        'disk_root_used_gib': gib_from_bytes(disk.used),
        'disk_root_free_gib': gib_from_bytes(disk.free),
        'disk_root_pct': disk_pct,
        'psi': psi,
        'top_cpu': top_processes('-pcpu'),
        'top_mem': top_processes('-pmem'),
        'containers': {
            'podman_running': count_lines(['podman', 'ps', '--format', '{{.Names}}']),
            'docker_running': count_lines(['docker', 'ps', '--format', '{{.Names}}']),
        },
        'alerts': [],
    }

    if disk_pct >= float(config['RG_SNAPSHOT_ALERT_DISK_PCT']):
        snapshot['alerts'].append('disk-root-high')
    if swap_used_pct >= float(config['RG_SNAPSHOT_ALERT_SWAP_PCT']):
        snapshot['alerts'].append('swap-high')
    if mem_available_mib <= float(config['RG_SNAPSHOT_ALERT_MEM_AVAILABLE_MIB']):
        snapshot['alerts'].append('mem-available-low')
    if psi['io'].get('full_avg10', 0.0) >= float(config['RG_SNAPSHOT_ALERT_PSI_IO_FULL_AVG10']):
        snapshot['alerts'].append('psi-io-full-high')
    if psi['memory'].get('full_avg10', 0.0) >= float(config['RG_SNAPSHOT_ALERT_PSI_MEMORY_FULL_AVG10']):
        snapshot['alerts'].append('psi-memory-full-high')

    snapshots_path = log_dir / 'snapshots.jsonl'
    latest_json = log_dir / 'latest.json'
    latest_txt = log_dir / 'latest.txt'
    with snapshots_path.open('a') as fh:
        fh.write(json.dumps(snapshot, ensure_ascii=False) + '\n')
    latest_json.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + '\n')
    write_text_summary(latest_txt, snapshot)

    print(f'ok: snapshot -> {snapshots_path}')
    print(f'latest: {latest_json}')
    print('alerts:', ', '.join(snapshot['alerts']) if snapshot['alerts'] else 'none')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
