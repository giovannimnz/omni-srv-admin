#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from collections import deque
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve()
MODULE = SCRIPT.parent.parent
LOG_FILE = Path.home() / '.logs' / 'resource-governor' / 'cap75-monitor.log'
STATE_FILE = Path.home() / '.local' / 'state' / 'omni' / 'resource-governor-cap75.json'
INVIOLABLE_PATTERNS_PATH = MODULE / 'configs' / 'inviolable-services.env'
CGROUP_USER = Path('/sys/fs/cgroup/user.slice/user-1001.slice')
CAP75_PATH = CGROUP_USER / 'omni-cap75'
BUILD_PATH = CGROUP_USER / 'omni-builds'
ME_UID = os.getuid()
RUNNING = True
POLL_SEC = 5
BREACH_STREAK = 2
ACTION_COOLDOWN_SEC = 60
SUMMARY_EVERY_SEC = 30
DURATION_SEC = 8 * 60 * 60
CPU_CORE_COUNT = max(os.cpu_count() or 1, 1)
CAP75_CPU_PCT = 75.0
CAP75_MEM_MIB = 12 * 1024
CAP75_WRITE_MBPS = 79.5
BUILD_CPU_PCT = 20.0 * CPU_CORE_COUNT
BUILD_MEM_MIB = 12 * 1024
BUILD_WRITE_MBPS = 79.5

PROTECTED_PATTERNS = [
    r'(^|/)(systemd|init|login|sudo|su|sshd)(\\s|$)',
    r'(^|/)(bash|zsh|sh|fish)(\\s|$)',
    r'(^|/)(dbus-daemon|dbus-broker|cron|atd)(\\s|$)',
    r'resource-governor-(watchdog|patcher|cap75)',
    r'srv1-defense-monitor',
    r'codex app-server --listen',
]

INVIOLABLE_PATTERNS = [
    r'(^|/)(sshd|xrdp|xrdp-sesman|xrdp-chansrv|polkitd|systemd-logind|dbus-(daemon|broker))(\\s|$)',
    r'(^|/)(apache2|nginx|httpd|caddy|haproxy|traefik|pm2-runtime)(\\s|$)',
    r'(^|/)(wg-quick|wg-crypt|wg0)(\\s|$)',
    r'atius-(router|web|web-healthcheck|router-docs)',
    r'router-ai-atius',
    r'conmon.*router-ai-atius',
    r'hermes-(telegram|ws-gateway|os-webapp|gateway|agent|acp)',
    r'(^|/)gbrain(\\s|$)',
    r'(^|/)gdrive-mount(\\s|$)',
    r'inviolable-watchdog',
]

BUILD_DOCKER_PATTERNS = [
    r'(^|/)(cargo|rustc|gcc|g\\+\\+|clang|cc1|ld|make)(\\s|$|-)',
    r'(^|/)(podman|docker)(\\s|$)',
    r'(^|/)(buildkitd|buildctl|docker-buildx)(\\s|$)',
    r'(^|/)fuse-overlayfs(\\s|$)',
    r'(^|/)(next|vite|webpack|esbuild|tsc|tsserver)(\\s|$)',
    r'(^|/)(bun|npm|pnpm|yarn)\\s+(run|install|build|i\\s)',
    r'(^|/)(pip|uv)\\s+install',
    r'(^|/)go\\s+(build|test|run|install)',
    r'(^|/)node-gyp(\\s|$)',
]

TRANSFER_PATTERNS = [
    r'(^|/)rclone(\\s|$)',
    r'(^|/)rsync(\\s|$)',
    r'(^|/)scp(\\s|$)',
    r'(^|/)sftp(\\s|$)',
    r'(^|/)(tar|gtar|bsdtar)(\\s|$)',
    r'(^|/)(gzip|pigz|bzip2|xz|lz4|zstd)(\\s|$)',
    r'(^|/)7zz?(\\s|$)',
]

INTERACTIVE_PATTERNS = [
    r'(^|/)obsidian(\\s|$)',
    r'(^|/)(chromium|chrome|firefox)(\\s|$)',
    r'(^|/)(electron|Hermes|signal|slack|discord)(\\s|$)',
    r'(^|/)code(\\s|$)',
]


def handle_signal(signum, frame):
    global RUNNING
    RUNNING = False


def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().astimezone().isoformat()}] {msg}\n"
    with LOG_FILE.open('a') as fh:
        fh.write(line)


def run(cmd: list[str], input_text: str | None = None, timeout: int = 10) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, input=input_text, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, '', f'timeout-after-{timeout}s'
    except Exception as exc:
        return 1, '', f'{type(exc).__name__}:{exc}'


def load_external_inviolables() -> None:
    if not INVIOLABLE_PATTERNS_PATH.exists():
        return
    try:
        for raw in INVIOLABLE_PATTERNS_PATH.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            pat = line.split()[0]
            if pat:
                INVIOLABLE_PATTERNS.append(pat)
    except Exception as exc:
        log(f'inviolable-load-failed exc={exc}')


def is_protected(cmd: str, comm: str) -> bool:
    for pat in PROTECTED_PATTERNS + INVIOLABLE_PATTERNS:
        if re.search(pat, cmd) or re.search(pat, comm):
            return True
    return False


def classify_kind(cmd: str, comm: str) -> str:
    text = f'{comm} {cmd}'
    for pat in BUILD_DOCKER_PATTERNS:
        if re.search(pat, text):
            return 'build-docker'
    for pat in TRANSFER_PATTERNS:
        if re.search(pat, text):
            return 'transfer'
    for pat in INTERACTIVE_PATTERNS:
        if re.search(pat, text):
            return 'interactive'
    return 'generic'


def ensure_cap75_cgroup() -> None:
    run(['sudo', 'mkdir', '-p', str(CAP75_PATH)], timeout=10)
    run(['sudo', 'chown', 'ubuntu:ubuntu', str(CAP75_PATH)], timeout=10)
    writes = {
        'cpu.max': '75000 100000\n',
        'memory.high': str(10 * 1024 * 1024 * 1024) + '\n',
        'memory.max': str(12 * 1024 * 1024 * 1024) + '\n',
        'memory.swap.max': str(2 * 1024 * 1024 * 1024) + '\n',
        'cpu.weight': '50\n',
        'io.weight': '50\n',
        'io.max': '8:0 rbps=max wbps=79500000 riops=max wiops=max\n',
    }
    for name, content in writes.items():
        fp = CAP75_PATH / name
        if fp.exists():
            run(['sudo', 'tee', str(fp)], input_text=content, timeout=10)


def ensure_guard_services() -> dict[str, str]:
    env = os.environ.copy()
    env['XDG_RUNTIME_DIR'] = f'/run/user/{ME_UID}'
    units = {
        'resource-governor-watchdog.service': 'active',
        'resource-governor-patcher.service': 'active',
        'resource-governor-watchdog.timer': 'active',
        'inviolable-watchdog.timer': 'active',
    }
    state = {}
    for unit, expect in units.items():
        p = subprocess.run(['systemctl', '--user', 'is-active', unit], capture_output=True, text=True, env=env, timeout=10, check=False)
        current = p.stdout.strip() or p.stderr.strip() or 'unknown'
        state[unit] = current
        if current != expect:
            subprocess.run(['systemctl', '--user', 'start', unit], capture_output=True, text=True, env=env, timeout=15, check=False)
            p2 = subprocess.run(['systemctl', '--user', 'is-active', unit], capture_output=True, text=True, env=env, timeout=10, check=False)
            state[unit] = p2.stdout.strip() or p2.stderr.strip() or current
    # inviolable-watchdog.service é oneshot e pode levar >15s. O timer já garante execução.
    # Não bloquear o monitor principal esperando este ciclo terminar.
    p3 = subprocess.run(['systemctl', '--user', 'is-active', 'inviolable-watchdog.service'], capture_output=True, text=True, env=env, timeout=10, check=False)
    state['inviolable-watchdog.service'] = p3.stdout.strip() or p3.stderr.strip() or 'unknown'
    return state


def pid_uid(pid: int) -> int | None:
    try:
        return os.stat(f'/proc/{pid}').st_uid
    except OSError:
        return None


def get_cmdline(pid: int) -> str:
    try:
        raw = Path(f'/proc/{pid}/cmdline').read_bytes()
        return raw.replace(b'\x00', b' ').decode('utf-8', errors='replace').strip()
    except OSError:
        return ''


def get_comm(pid: int) -> str:
    try:
        return Path(f'/proc/{pid}/comm').read_text().strip()
    except OSError:
        return ''


def get_cgroup(pid: int) -> str:
    try:
        return Path(f'/proc/{pid}/cgroup').read_text().strip().split('\n')[-1].replace('0::', '')
    except OSError:
        return ''


def get_rss_kib(pid: int) -> int:
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):
                return int(line.split()[1])
    except OSError:
        return 0
    return 0


def get_cpu_jiffies(pid: int) -> int | None:
    try:
        content = Path(f'/proc/{pid}/stat').read_text()
        rpar = content.rfind(')')
        if rpar < 0:
            return None
        rest = content[rpar + 2:].split()
        utime = int(rest[11]) if len(rest) > 12 else 0
        stime = int(rest[12]) if len(rest) > 13 else 0
        return utime + stime
    except (OSError, ValueError, IndexError):
        return None


def get_write_bytes(pid: int) -> int | None:
    try:
        for line in Path(f'/proc/{pid}/io').read_text().splitlines():
            if line.startswith('write_bytes:'):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def proc_cpu_pct(cur: int, prev: int, dt: float) -> float:
    clk_tck = os.sysconf('SC_CLK_TCK') or 100
    if dt <= 0:
        return 0.0
    return (cur - prev) / dt * 100 / clk_tck


def write_mbps(cur: int, prev: int, dt: float) -> float:
    if dt <= 0:
        return 0.0
    delta = max(cur - prev, 0)
    return delta / 1024 / 1024 / dt


def move_pid(pid: int, target: Path) -> bool:
    rc, out, err = run(['sudo', 'tee', '-a', str(target / 'cgroup.procs')], input_text=str(pid), timeout=10)
    return rc == 0


def soften_pid(pid: int, kind: str) -> None:
    nice = '10' if kind != 'build-docker' else '5'
    run(['sudo', 'renice', '-n', nice, '-p', str(pid)], timeout=10)
    run(['sudo', 'ionice', '-c', '2', '-n', '7', '-p', str(pid)], timeout=10)


def top_summary(candidates: list[dict]) -> tuple[str, str, str]:
    if not candidates:
        return '-', '-', '-'
    by_cpu = max(candidates, key=lambda x: x.get('cpu_pct', 0.0))
    by_mem = max(candidates, key=lambda x: x.get('rss_mib', 0))
    by_io = max(candidates, key=lambda x: x.get('write_mbps', 0.0))
    cpu_txt = f"pid={by_cpu['pid']} {by_cpu['comm']} cpu={by_cpu['cpu_pct']:.1f}% kind={by_cpu['kind']}"
    mem_txt = f"pid={by_mem['pid']} {by_mem['comm']} rss={by_mem['rss_mib']}MiB kind={by_mem['kind']}"
    io_txt = f"pid={by_io['pid']} {by_io['comm']} write={by_io['write_mbps']:.1f}MB/s kind={by_io['kind']}"
    return cpu_txt, mem_txt, io_txt


def main() -> int:
    global RUNNING
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    load_external_inviolables()
    ensure_cap75_cgroup()
    service_state = ensure_guard_services()
    log('start duration=8h policy=build/docker<=20% total host cpu,<=12GiB; others<=75%cpu,<=12GiB,<=79.5MB/s services=' + json.dumps(service_state, ensure_ascii=False))

    cpu_prev: dict[int, tuple[int, float]] = {}
    io_prev: dict[int, tuple[int, float]] = {}
    streaks: dict[int, int] = {}
    last_action: dict[int, float] = {}
    last_summary = 0.0
    deadline = time.time() + DURATION_SEC

    while RUNNING and time.time() < deadline:
        cycle_ts = time.time()
        if int(cycle_ts) % 60 < POLL_SEC:
            ensure_cap75_cgroup()
        if int(cycle_ts) % 120 < POLL_SEC:
            service_state = ensure_guard_services()

        candidates = []
        actions = []
        live_pids = set()

        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            live_pids.add(pid)
            if pid <= 1 or pid == os.getpid():
                continue
            if pid_uid(pid) != ME_UID:
                continue
            cmd = get_cmdline(pid)
            if not cmd:
                continue
            comm = get_comm(pid)
            if is_protected(cmd, comm):
                continue

            kind = classify_kind(cmd, comm)
            rss_mib = get_rss_kib(pid) // 1024
            cur_cpu = get_cpu_jiffies(pid)
            cur_write = get_write_bytes(pid)
            if cur_cpu is None:
                continue

            prev_cpu = cpu_prev.get(pid)
            prev_io = io_prev.get(pid)
            cpu_pct = 0.0
            write_rate = 0.0
            if prev_cpu:
                cpu_pct = max(proc_cpu_pct(cur_cpu, prev_cpu[0], cycle_ts - prev_cpu[1]), 0.0)
            if cur_write is not None and prev_io:
                write_rate = max(write_mbps(cur_write, prev_io[0], cycle_ts - prev_io[1]), 0.0)
            cpu_prev[pid] = (cur_cpu, cycle_ts)
            if cur_write is not None:
                io_prev[pid] = (cur_write, cycle_ts)

            cpu_limit = BUILD_CPU_PCT if kind == 'build-docker' else CAP75_CPU_PCT
            mem_limit = BUILD_MEM_MIB if kind == 'build-docker' else CAP75_MEM_MIB
            write_limit = BUILD_WRITE_MBPS if kind == 'build-docker' else CAP75_WRITE_MBPS
            reasons = []
            if cpu_pct > cpu_limit:
                reasons.append(f'cpu={cpu_pct:.1f}%>{cpu_limit:.1f}%')
            if rss_mib > mem_limit:
                reasons.append(f'rss={rss_mib}MiB>{mem_limit}MiB')
            if write_rate > write_limit:
                reasons.append(f'write={write_rate:.1f}MB/s>{write_limit:.1f}MB/s')

            cgroup = get_cgroup(pid)
            cand = {
                'pid': pid,
                'comm': comm,
                'cmd': cmd[:140],
                'kind': kind,
                'cpu_pct': cpu_pct,
                'rss_mib': rss_mib,
                'write_mbps': write_rate,
                'reasons': reasons,
                'cgroup': cgroup,
            }
            candidates.append(cand)

            if reasons:
                streaks[pid] = streaks.get(pid, 0) + 1
            else:
                streaks[pid] = 0
                continue

            if streaks[pid] < BREACH_STREAK:
                continue
            if cycle_ts - last_action.get(pid, 0.0) < ACTION_COOLDOWN_SEC:
                continue

            target = BUILD_PATH if kind == 'build-docker' else CAP75_PATH
            target_name = target.name
            moved = target_name in cgroup
            if not moved:
                moved = move_pid(pid, target)
            soften_pid(pid, kind)
            last_action[pid] = cycle_ts
            actions.append({
                'pid': pid,
                'comm': comm,
                'kind': kind,
                'target': target_name,
                'moved': moved,
                'reasons': reasons,
            })
            log(f"contain pid={pid} comm={comm} kind={kind} target={target_name} moved={int(moved)} reasons={'|'.join(reasons)} cmd={cmd[:160]}")

        for pid in list(cpu_prev.keys()):
            if pid not in live_pids:
                cpu_prev.pop(pid, None)
                io_prev.pop(pid, None)
                streaks.pop(pid, None)
                last_action.pop(pid, None)

        if cycle_ts - last_summary >= SUMMARY_EVERY_SEC:
            cpu_txt, mem_txt, io_txt = top_summary(candidates)
            try:
                import sys
                sys.path.insert(0, str(MODULE / 'lib'))
                import metrics  # type: ignore
                m = metrics.all_metrics()
            except Exception:
                m = {'mem_pct': -1, 'proc_pct': -1, 'disk_spc_pct': -1, 'disk_rw_pct': -1}
            log(
                'summary '
                f"host_mem={m['mem_pct']}% host_proc={m['proc_pct']}% host_disk={m['disk_spc_pct']}% host_disk_rw={m['disk_rw_pct']}% "
                f"top_cpu='{cpu_txt}' top_mem='{mem_txt}' top_write='{io_txt}' actions={len(actions)} services="
                + json.dumps(service_state, ensure_ascii=False)
            )
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps({
                'ts': datetime.now().astimezone().isoformat(),
                'services': service_state,
                'actions_last_cycle': actions,
                'top_cpu': cpu_txt,
                'top_mem': mem_txt,
                'top_write': io_txt,
                'candidate_count': len(candidates),
                'remaining_sec': max(int(deadline - cycle_ts), 0),
            }, indent=2))
            last_summary = cycle_ts

        elapsed = time.time() - cycle_ts
        if elapsed < POLL_SEC:
            time.sleep(POLL_SEC - elapsed)

    log('stop reason=' + ('signal' if not RUNNING else 'deadline'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
