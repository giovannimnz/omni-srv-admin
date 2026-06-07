#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve()
MODULE = SCRIPT.parent.parent
CONFIG_PATH = MODULE / 'configs' / 'resource-governor.env'
DEFAULT_LOG_DIR = Path.home() / '.logs' / 'resource-governor'
ROOTS = [Path('/home/ubuntu/GitHub'), Path('/home/ubuntu/docker')]
INTERESTING = {'node_modules', '.next', 'target', 'dist', 'build', '.venv', 'venv', 'db-data', 'data', '.turbo', '.cache'}
EXCLUDE_WALK = {'.git', '__pycache__', '.idea', '.vscode'}
FIXED_PATHS = [
    Path('/home/ubuntu/.cache/codex-update-manager'),
    Path('/home/ubuntu/.cache/ms-playwright'),
    Path('/home/ubuntu/.cargo'),
    Path('/home/ubuntu/.rustup'),
    Path('/home/ubuntu/.local/share/containers/storage'),
]


def load_config() -> dict[str, str]:
    data = {'RG_LOG_DIR': str(DEFAULT_LOG_DIR)}
    if CONFIG_PATH.exists():
        for raw in CONFIG_PATH.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return proc.stdout.strip() or proc.stderr.strip()


def dir_size(path: Path) -> int:
    total = 0
    try:
        for root, dirs, files in os.walk(path, onerror=lambda _e: None):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_WALK]
            for name in files:
                fp = os.path.join(root, name)
                try:
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except OSError:
                    pass
    except Exception:
        return total
    return total


def gib(value: int) -> float:
    return round(value / (1024 ** 3), 2)


def scan_artifacts() -> tuple[list[tuple[int, str]], list[tuple[int, str, dict[str, int]]]]:
    results: list[tuple[int, str]] = []
    for base in ROOTS:
        for root, dirs, _files in os.walk(base, topdown=True, onerror=lambda _e: None):
            keep = []
            for dname in dirs:
                if dname in INTERESTING:
                    path = Path(root) / dname
                    results.append((dir_size(path), str(path)))
                elif dname not in EXCLUDE_WALK:
                    keep.append(dname)
            dirs[:] = keep
    results.sort(reverse=True)

    parent_summary: dict[str, dict[str, int]] = {}
    for size, path in results:
        parent = str(Path(path).parent)
        name = Path(path).name
        parent_summary.setdefault(parent, {item: 0 for item in INTERESTING})
        parent_summary[parent][name] += size
    ranked = []
    for parent, data in parent_summary.items():
        total = sum(data.values())
        if total:
            ranked.append((total, parent, data))
    ranked.sort(reverse=True)
    return results, ranked


def fixed_sizes() -> list[dict[str, object]]:
    rows = []
    for path in FIXED_PATHS:
        if path.exists():
            rows.append({'path': str(path), 'size_gib': gib(dir_size(path))})
    return rows


def build_report() -> dict[str, Any]:
    top_dirs, top_parents = scan_artifacts()
    disk = shutil.disk_usage('/')
    report = {
        'timestamp': datetime.now().astimezone().isoformat(),
        'host': os.uname().nodename,
        'disk_root': {
            'total_gib': gib(disk.total),
            'used_gib': gib(disk.used),
            'free_gib': gib(disk.free),
            'used_pct': round((disk.used / disk.total) * 100, 2),
        },
        'top_artifact_dirs': [
            {'path': path, 'size_gib': gib(size)}
            for size, path in top_dirs[:25]
            if gib(size) >= 0.05
        ],
        'top_artifact_parents': [
            {
                'path': parent,
                'total_gib': gib(total),
                'breakdown': {name: gib(size) for name, size in data.items() if gib(size) > 0},
            }
            for total, parent, data in top_parents[:20]
            if gib(total) >= 0.05
        ],
        'fixed_paths': fixed_sizes(),
        'podman_images': run(['podman', 'images', '--format', '{{.Repository}}\t{{.Tag}}\t{{.Size}}']).splitlines()[:20],
        'docker_images': run(['docker', 'images', '--format', '{{.Repository}}\t{{.Tag}}\t{{.Size}}']).splitlines()[:20],
        'podman_ps': run(['podman', 'ps', '--format', '{{.Names}}\t{{.Status}}\t{{.Image}}']).splitlines()[:20],
        'docker_ps': run(['docker', 'ps', '--format', '{{.Names}}\t{{.Status}}\t{{.Image}}']).splitlines()[:20],
        'top_cpu': run(['ps', '-eo', 'pid,comm,pcpu,pmem,rss,args', '--sort=-pcpu']).splitlines()[:15],
        'top_mem': run(['ps', '-eo', 'pid,comm,pcpu,pmem,rss,args', '--sort=-pmem']).splitlines()[:15],
    }
    return report


def write_text(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"timestamp: {report['timestamp']}",
        f"host: {report['host']}",
        f"disk_root_used_pct: {report['disk_root']['used_pct']}",
        '',
        'top_artifact_dirs:',
    ]
    for row in report['top_artifact_dirs'][:15]:
        lines.append(f"- {row['size_gib']} GiB  {row['path']}")
    lines.append('')
    lines.append('top_artifact_parents:')
    for row in report['top_artifact_parents'][:12]:
        breakdown = ', '.join(f"{k}={v}G" for k, v in row['breakdown'].items())
        lines.append(f"- {row['total_gib']} GiB  {row['path']}  [{breakdown}]")
    lines.append('')
    lines.append('fixed_paths:')
    for row in report['fixed_paths']:
        lines.append(f"- {row['size_gib']} GiB  {row['path']}")
    lines.append('')
    lines.append('podman_images:')
    lines.extend(f"- {line}" for line in report['podman_images'])
    lines.append('')
    lines.append('docker_images:')
    lines.extend(f"- {line}" for line in report['docker_images'])
    path.write_text('\n'.join(lines) + '\n')


def main() -> int:
    config = load_config()
    log_dir = Path(os.path.expanduser(config['RG_LOG_DIR']))
    log_dir.mkdir(parents=True, exist_ok=True)
    report = build_report()
    stamp = datetime.now().strftime('%Y-%m-%d')
    audit_json = log_dir / f'audit-{stamp}.json'
    audit_txt = log_dir / f'audit-{stamp}.txt'
    latest_txt = log_dir / 'latest-audit.txt'
    audit_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    write_text(audit_txt, report)
    latest_txt.write_text(audit_txt.read_text())
    print(f'ok: audit -> {audit_json}')
    print(f'latest: {latest_txt}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
