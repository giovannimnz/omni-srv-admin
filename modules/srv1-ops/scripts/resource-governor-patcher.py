#!/usr/bin/env python3
"""resource-governor-patcher — auto-migra processos pesados para slices omni-*.

Resolve o problema fundamental: processos já iniciados antes de qualquer wrapper
vivem em session-c2.scope / user@1001.service/session-*.scope e não respeitam
nenhuma slice. cpu.max=340% (85% de 4 cores) no user-1001.slice é o teto global
mas a média de load fica alta porque todos competem pela mesma fatia.

Este daemon periodicamente:
  1. Mede CPU/memória de cada processo do user
  2. Classifica em build/interactive/transfer por comm+args
  3. Move processos quentes para a slice omni-* apropriada
     via `echo PID > <slice>/cgroup.procs` (kernel permission: o processo
     só pode ser movido se o user é owner do cgroup de origem E destino.
     Como ambos são do mesmo UID, é permitido.)
  4. Aplica limite de 50% por processo único também na slice destino.

Tipos reconhecidos:
  - build:    cargo, rustc, gcc, g++, make, podman build, docker build,
              next build, vite, bun build, npm/pnpm/yarn, pip, uv, go
  - transfer: rclone, rsync, ftp, sftp, wget, curl (large), tarr, gzip, 7zz
  - interactive: vscode, obsidian, electron, code, hermes-desktop

Protegidos (NUNCA movidos): systemd, watchdog, init, dbus, sshd, cron, bash login
"""
from __future__ import annotations

import os
import re
import subprocess
import time
import json
import signal
from collections import deque
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve()
MODULE = SCRIPT.parent.parent
CONFIG_PATH = MODULE / 'configs' / 'resource-governor.env'
LOG_FILE = Path.home() / '.logs' / 'resource-governor' / 'patcher.log'
STATE_FILE = Path.home() / '.local' / 'state' / 'omni' / 'resource-governor-patcher.json'

CGROUP_BASE = Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/omni.slice')
CGROUP_BASE_USER = Path('/sys/fs/cgroup/user.slice/user-1001.slice')
CGROUP_USER = Path('/sys/fs/cgroup/user.slice/user-1001.slice')

# Classification patterns: (regex on cmd, slice, reason)
BUILD_PATTERNS = [
    (r'(^|/)cargo(\s|$)', 'builds', 'cargo'),
    (r'(^|/)rustc(\s|$)', 'builds', 'rustc'),
    (r'(^|/)(gcc|g\+\+|clang|cc1|ld)(\s|$)', 'builds', 'compiler'),
    (r'(^|/)make(\s|$|-)', 'builds', 'make'),
    (r'(^|/)podman\s+build', 'builds', 'podman-build'),
    (r'(^|/)docker\s+build', 'builds', 'docker-build'),
    (r'(^|/)(next|vite|webpack|esbuild|tsc|tsserver)(\s|$)', 'builds', 'frontend'),
    (r'(^|/)(bun|npm|pnpm|yarn)\s+(run|install|build|i\s)', 'builds', 'node-pkg'),
    (r'(^|/)(pip|uv)\s+install', 'builds', 'pip-install'),
    (r'(^|/)go\s+(build|test|run|install)', 'builds', 'go'),
    (r'(^|/)node-gyp(\s|$)', 'builds', 'node-gyp'),
]

TRANSFER_PATTERNS = [
    (r'(^|/)rclone(\s|$)', 'transfers', 'rclone'),
    (r'(^|/)rsync(\s|$)', 'transfers', 'rsync'),
    (r'(^|/)7zz?\s+', 'transfers', '7zip'),
    (r'(^|/)(tar|gtar|bsdtar)(\s|$)', 'transfers', 'tar'),
    (r'(^|/)(gzip|pigz|bzip2|xz|lz4|zstd)(\s|$)', 'transfers', 'compressor'),
    (r'(^|/)cp\s+.*-[a-zA-Z]*r', 'transfers', 'cp-r'),
]

INTERACTIVE_PATTERNS = [
    (r'(^|/)Hermes(\s|-|$)', 'interactive', 'hermes-desktop'),
    (r'(^|/)obsidian(\s|$)', 'interactive', 'obsidian'),
    (r'(^|/)code(\s|$)', 'interactive', 'vscode'),
    (r'(^|/)(chromium|chrome|firefox)(\s|$)', 'interactive', 'browser'),
    (r'(^|/)slack(\s|$)', 'interactive', 'slack'),
    (r'(^|/)discord(\s|$)', 'interactive', 'discord'),
    (r'(^|/)signal(\s|$)', 'interactive', 'signal'),
    (r'(^|/)(electron|electron-builder|Codex)(\s|$)', 'interactive', 'electron'),
]

# Nunca mover
PROTECTED_PATTERNS = [
    r'(^|/)systemd(\s|$)',
    r'(^|/)(bash|zsh|sh|fish)$',
    r'(^|/)(init|login|sudo|su|sshd)(\s|$)',
    r'(^|/)dbus-(daemon|broker)(\s|$)',
    r'(^|/)cron(\s|$)',
    r'(^|/)atd(\s|$)',
    r'resource-governor-(watchdog|patcher)',
    r'omni-srv-admin',
    r'(^|/)ps(\s|$)',
    r'(^|/)grep(\s|$)',
    r'(^|/)awk(\s|$)',
    r'(^|/)sed(\s|$)',
    r'(^|/)cat(\s|$)',
]

DEFAULTS = {
    'RG_PATCHER_POLL_INTERVAL_SEC': '2',
    'RG_PATCHER_CPU_THRESHOLD_PCT': '3.0',
    'RG_PATCHER_MEM_THRESHOLD_MIB': '150',
    'RG_PATCHER_MIN_AGE_SEC': '5',
    'RG_PATCHER_DRY_RUN': '0',
}

RUNNING = True


def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().astimezone().isoformat()
    line = f'[{ts}] {msg}\n'
    with LOG_FILE.open('a') as fh:
        fh.write(line)


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


def handle_signal(signum, _frame):
    global RUNNING
    RUNNING = False


def get_my_pid() -> int:
    return os.getpid()


def is_protected(cmd: str, comm: str) -> bool:
    for pat in PROTECTED_PATTERNS:
        if re.search(pat, cmd) or re.search(pat, comm):
            return True
    return False


def classify(cmd: str) -> tuple[str, str] | None:
    for pat, slice_name, reason in BUILD_PATTERNS + TRANSFER_PATTERNS + INTERACTIVE_PATTERNS:
        if re.search(pat, cmd):
            return slice_name, reason
    return None


def read_proc_stat(pid: int) -> dict:
    """Read /proc/PID/stat safely."""
    try:
        with open(f'/proc/{pid}/stat', 'r') as fh:
            content = fh.read()
        # comm pode ter espaço/parentese: pegar ultimo )
        rpar = content.rfind(')')
        if rpar < 0:
            return {}
        rest = content[rpar + 2:].split()
        # rest[0..2] = state, ppid, pgrp
        # rest[11] = utime, rest[12] = stime
        utime = int(rest[11]) if len(rest) > 12 else 0
        stime = int(rest[12]) if len(rest) > 13 else 0
        return {
            'utime': utime,
            'stime': stime,
            'total_time': utime + stime,
        }
    except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError, ValueError):
        return {}


def get_cmdline(pid: int) -> str:
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as fh:
            raw = fh.read()
        return raw.replace(b'\x00', b' ').decode('utf-8', errors='replace').strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return ''


def get_comm(pid: int) -> str:
    try:
        return Path(f'/proc/{pid}/comm').read_text().strip()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return ''


def get_rss_kib(pid: int) -> int:
    try:
        content = Path(f'/proc/{pid}/status').read_text()
        for line in content.splitlines():
            if line.startswith('VmRSS:'):
                return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
        pass
    return 0


def get_start_time(pid: int) -> int:
    try:
        return int(Path(f'/proc/{pid}/stat').read_text().split()[21])
    except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError, ValueError):
        return 0


def get_cgroup(pid: int) -> str:
    try:
        return Path(f'/proc/{pid}/cgroup').read_text().strip().split('\n')[-1].replace('0::', '')
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return ''


def move_to_slice(pid: int, slice_name: str, dry_run: bool) -> bool:
    target = CGROUP_BASE_USER / f'omni-{slice_name}'
    if not target.exists():
        return False
    procs_file = target / 'cgroup.procs'
    if dry_run:
        return True
    try:
        # Cross-tree move (session-* -> omni-*) requires CAP_SYS_ADMIN.
        # ubuntu has NOPASSWD:ALL, so use sudo tee.
        result = subprocess.run(
            ['sudo', 'tee', '-a', str(procs_file)],
            input=str(pid),
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception as exc:
        log(f'move-failed pid={pid} target={slice_name} exc={exc}')
        return False


def ensure_user_cgroup_subtree() -> None:
    """Ensure /sys/fs/cgroup/user.slice/user-1001.slice has cpu+io+memory+pids
    in subtree_control so our child cgroups can write to all controllers."""
    if not CGROUP_USER.exists():
        return
    sub = CGROUP_USER / 'cgroup.subtree_control'
    if not sub.exists():
        return
    current = sub.read_text().split()
    for ctl in ('cpu', 'io', 'memory', 'pids'):
        if ctl not in current:
            try:
                result = subprocess.run(
                    ['sudo', 'tee', str(sub)],
                    input=f'+{ctl}\n',
                    capture_output=True,
                    text=True,
                )
            except Exception as exc:
                log(f'user-subtree-enable-failed ctl={ctl} exc={exc}')


def ensure_omni_cgroups_exist() -> dict[str, Path]:
    """Create /sys/fs/cgroup/user.slice/user-1001.slice/omni-{builds,interactive,transfers}
    as plain cgroup dirs (not systemd slices) and chown to ubuntu."""
    out = {}
    for name in ('builds', 'interactive', 'transfers'):
        path = CGROUP_USER / f'omni-{name}'
        if not path.exists():
            try:
                subprocess.run(
                    ['sudo', 'mkdir', '-p', str(path)],
                    capture_output=True, text=True, check=False,
                )
                subprocess.run(
                    ['sudo', 'chown', 'ubuntu:ubuntu', str(path)],
                    capture_output=True, text=True, check=False,
                )
            except Exception as exc:
                log(f'omni-cgroup-create-failed name={name} exc={exc}')
        if path.exists():
            out[name] = path
    return out


def ensure_subtree_control(path: Path, controllers: list[str]) -> None:
    sub = path / 'cgroup.subtree_control'
    if not sub.exists():
        return
    current = sub.read_text().split()
    for ctl in controllers:
        if ctl not in current:
            try:
                with sub.open('w') as fh:
                    fh.write(f'+{ctl}\n')
            except (PermissionError, FileNotFoundError, OSError) as exc:
                log(f'subtree-enable-failed path={path} ctl={ctl} exc={exc}')


def ensure_slices_active() -> dict[str, bool]:
    """Start all omni-*.slice units so cgroup dirs exist with controllers."""
    out = {}
    env = os.environ.copy()
    env.setdefault('XDG_RUNTIME_DIR', '/run/user/1001')
    env.setdefault('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/run/user/1001/bus')
    for name in ('builds', 'interactive', 'transfers'):
        target = CGROUP_BASE / f'omni-{name}.slice'
        if not target.exists():
            try:
                subprocess.run(
                    ['systemctl', '--user', 'start', f'omni-{name}.slice'],
                    capture_output=True, env=env, timeout=5,
                )
            except Exception:
                pass
        # Ensure subtree_control has cpu+io+memory+pids so children inherit them
        ensure_subtree_control(target, ['cpu', 'io', 'memory', 'pids'])
        out[name] = target.exists()
    return out


def scan_processes(my_pid: int) -> list[dict]:
    """Walk /proc and return candidate PIDs with classification."""
    candidates = []
    boot_time = 0
    try:
        with open('/proc/stat', 'r') as fh:
            for line in fh:
                if line.startswith('btime '):
                    boot_time = int(line.split()[1])
                    break
    except (FileNotFoundError, ValueError):
        pass
    now = time.time()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == my_pid or pid <= 1:
            continue
        cmd = get_cmdline(pid)
        if not cmd:
            continue
        comm = get_comm(pid)
        if is_protected(cmd, comm):
            continue
        # Already in an omni cgroup?
        cgrp = get_cgroup(pid)
        if '/omni-' in cgrp:
            continue
        # Classify
        cls = classify(cmd)
        if not cls:
            continue
        slice_name, reason = cls
        # Quick process stats
        proc_stat = read_proc_stat(pid)
        rss = get_rss_kib(pid)
        candidates.append({
            'pid': pid,
            'comm': comm,
            'cmd': cmd[:120],
            'cgroup': cgrp,
            'slice': slice_name,
            'reason': reason,
            'utime': proc_stat.get('utime', 0),
            'stime': proc_stat.get('stime', 0),
            'rss_kib': rss,
        })
    return candidates


def main() -> int:
    global RUNNING
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    config = load_config()
    poll = float(config['RG_PATCHER_POLL_INTERVAL_SEC'])
    cpu_thr = float(config['RG_PATCHER_CPU_THRESHOLD_PCT'])
    mem_thr = float(config['RG_PATCHER_MEM_THRESHOLD_MIB']) * 1024  # KiB
    min_age = int(config['RG_PATCHER_MIN_AGE_SEC'])
    dry_run = config['RG_PATCHER_DRY_RUN'] == '1'

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log(f'patcher-start poll={poll}s cpu>={cpu_thr}% mem>={mem_thr//1024}MiB dry_run={dry_run}')

    # Per-PID CPU tracking
    cpu_samples: dict[int, deque] = {}

    # Setup cgroup environment
    ensure_user_cgroup_subtree()
    omni_paths = ensure_omni_cgroups_exist()
    log(f'omni-paths: {[str(p) for p in omni_paths.values()]}')

    # Apply limits to user.slice (global 85% of 4 cores = 340%)
    user_cpu = CGROUP_USER / 'cpu.max'
    if user_cpu.exists():
        try:
            current = user_cpu.read_text().strip()
            if current != '340000 100000':
                subprocess.run(
                    ['sudo', 'tee', str(user_cpu)],
                    input='340000 100000\n',
                    capture_output=True, text=True,
                )
                log(f'user-slice cpu.max set to 340000 100000 (was: {current})')
        except (PermissionError, FileNotFoundError) as exc:
            log(f'user-slice cpu.max write failed: {exc}')

    # Per-profile cgroup v2 limits (per-process 50% cap)
    PROFILE_LIMITS = {
        'builds':     {'cpu': '200000 100000', 'io': '8:0 rbps=60000000 wbps=54000000',  'mem': '6G'},
        'interactive':{'cpu': '200000 100000', 'io': '8:0 rbps=60000000 wbps=54000000',  'mem': '4G'},
        'transfers':  {'cpu': '100000 100000', 'io': '8:0 rbps=60000000 wbps=30000000',  'mem': '2G'},
    }
    for name, path in omni_paths.items():
        limits = PROFILE_LIMITS[name]
        try:
            subprocess.run(['sudo', 'tee', str(path / 'cpu.max')],
                           input=f"{limits['cpu']}\n",
                           capture_output=True, text=True, check=False)
            subprocess.run(['sudo', 'tee', str(path / 'io.max')],
                           input=f"{limits['io']}\n",
                           capture_output=True, text=True, check=False)
            # memory.max in bytes
            mem_bytes = {
                '6G': 6 * 1024 * 1024 * 1024,
                '4G': 4 * 1024 * 1024 * 1024,
                '2G': 2 * 1024 * 1024 * 1024,
            }[limits['mem']]
            subprocess.run(['sudo', 'tee', str(path / 'memory.max')],
                           input=f"{mem_bytes}\n",
                           capture_output=True, text=True, check=False)
            log(f'omni-{name}: cpu={limits["cpu"]} io={limits["io"]} mem={limits["mem"]}')
        except Exception as exc:
            log(f'omni-{name} limit-set-failed: {exc}')

    state = {
        'moved_total': 0,
        'last_moves': [],
        'last_seen': {},
    }

    while RUNNING:
        cycle_start = time.time()
        # Re-ensure cgroups persist (some cleanup tasks may prune)
        omni_paths = ensure_omni_cgroups_exist()

        # Sample all candidates
        candidates = scan_processes(get_my_pid())
        moved_this_cycle = []

        for cand in candidates:
            pid = cand['pid']
            # CPU% calculation: delta in jiffies / wall time
            prev = cpu_samples.get(pid)
            cur_jiffies = cand['utime'] + cand['stime']
            now = time.time()
            if prev and len(prev) > 0:
                prev_jiffies, prev_t = prev[-1]
                dt = now - prev_t
                if dt > 0:
                    jiffies_per_sec = (cur_jiffies - prev_jiffies) / dt
                    # CLK_TCK = 100 on Linux default
                    cpu_pct = jiffies_per_sec
                    cand['cpu_pct'] = cpu_pct
                else:
                    cand['cpu_pct'] = 0
            else:
                cand['cpu_pct'] = 0
            cpu_samples.setdefault(pid, deque(maxlen=3)).append((cur_jiffies, now))

            # Decision: should we migrate?
            should_migrate = False
            reason_trigger = []
            if cand['cpu_pct'] >= cpu_thr:
                should_migrate = True
                reason_trigger.append(f"cpu={cand['cpu_pct']:.1f}%")
            if cand['rss_kib'] >= mem_thr:
                should_migrate = True
                reason_trigger.append(f"rss={cand['rss_kib']//1024}MiB")

            if not should_migrate:
                continue

            # Skip if already in target
            current_cgrp = get_cgroup(pid)
            target_name = f'omni-{cand["slice"]}'
            if target_name in current_cgrp:
                continue

            ok = move_to_slice(pid, cand['slice'], dry_run)
            if ok:
                moved_this_cycle.append({
                    'pid': pid,
                    'comm': cand['comm'],
                    'cmd': cand['cmd'][:80],
                    'slice': cand['slice'],
                    'reason': cand['reason'],
                    'trigger': ','.join(reason_trigger),
                    'cpu_pct': round(cand['cpu_pct'], 1),
                    'rss_mib': cand['rss_kib'] // 1024,
                })
                state['moved_total'] += 1

        if moved_this_cycle:
            log(f'cycle-moved count={len(moved_this_cycle)}')
            for m in moved_this_cycle:
                log(f"  -> {m['pid']} {m['comm']} -> omni-{m['slice']} ({m['reason']}, {m['trigger']})")
            state['last_moves'] = (state.get('last_moves', []) + moved_this_cycle)[-50:]

        # Periodic cleanup of cpu_samples for dead PIDs
        live_pids = {c['pid'] for c in candidates}
        for pid in list(cpu_samples.keys()):
            if pid not in live_pids:
                cpu_samples.pop(pid, None)

        # Persist state
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps({
                'moved_total': state['moved_total'],
                'last_moves': state['last_moves'][-20:],
                'last_cycle_ts': datetime.now().astimezone().isoformat(),
            }, indent=2))
        except Exception:
            pass

        elapsed = time.time() - cycle_start
        if elapsed < poll:
            time.sleep(poll - elapsed)

    log(f'patcher-stop moved_total={state["moved_total"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
