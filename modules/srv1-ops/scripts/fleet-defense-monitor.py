#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path('/home/ubuntu/GitHub/omni-srv-admin')
SCRIPT = Path(__file__).resolve()
LOG_DIR = Path.home() / '.logs' / 'resource-governor'
LOG_FILE = LOG_DIR / 'fleet-defense-monitor.log'
LOCK_FILE = Path.home() / '.local' / 'state' / 'omni' / 'fleet-defense-monitor.lock'
MAX_SECONDS = int(os.environ.get('FLEET_DEFENSE_MAX_SECONDS', str(12 * 60 * 60)))
POLL_SECONDS = int(os.environ.get('FLEET_DEFENSE_POLL_SECONDS', '30'))
SSH_TIMEOUT = int(os.environ.get('FLEET_DEFENSE_SSH_TIMEOUT', '5'))
HOSTS = {
    'srv1': None,
    'srv2': 'ubuntu@10.1.1.2',
    'srv3': 'ubuntu@10.1.1.3',
}
LOCAL_INVIOLABLE = Path('/home/ubuntu/scripts/inviolable-watchdog.sh')
REMOTE_INVIOLABLE = '/home/ubuntu/scripts/inviolable-watchdog.sh'
REMOTE_CGROUP_INIT = '/home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/resource-governor-cgroup-init.sh'
LOCAL_CGROUP_INIT = REPO / 'modules' / 'srv1-ops' / 'scripts' / 'resource-governor-cgroup-init.sh'
REMOTE_PATCHER = '/home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/resource-governor-patcher.py'

RUNNING = True


def handle_signal(signum, _frame):
    global RUNNING
    RUNNING = False


for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, handle_signal)


def log(msg: str) -> None:
    ts = datetime.now().astimezone().isoformat(timespec='seconds')
    line = f'[{ts}] {msg}'
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open('a') as fh:
        fh.write(line + '\n')
    print(line, flush=True)


def run(cmd, timeout=20, check=False):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f'cmd failed rc={p.returncode}: {cmd!r}: {p.stderr.strip()}')
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def local_shell(command: str, timeout=20):
    return run(['/bin/bash', '-lc', command], timeout=timeout)


def ssh(host: str, command: str, timeout: int = SSH_TIMEOUT):
    return run([
        'ssh',
        '-o', 'BatchMode=yes',
        '-o', f'ConnectTimeout={timeout}',
        host,
        command,
    ], timeout=timeout + 10)


def scp(src: Path, host: str, dest: str, timeout: int = 20):
    return run([
        'scp',
        '-q',
        str(src),
        f'{host}:{dest}',
    ], timeout=timeout)


def local_is_active(unit: str) -> bool:
    rc, _, _ = local_shell(f'XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user is-active --quiet {unit!s}')
    return rc == 0


def local_start(unit: str) -> None:
    local_shell(f'XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user start {unit!s}', timeout=20)


def local_start_no_block(unit: str) -> None:
    local_shell(f'XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user start --no-block {unit!s}', timeout=20)


def remote_state_cmd() -> str:
    return r'''
set -e
export XDG_RUNTIME_DIR=/run/user/$(id -u)
for unit in resource-governor-watchdog.service resource-governor-patcher.service inviolable-watchdog.timer; do
  if systemctl --user is-active --quiet "$unit" 2>/dev/null; then
    echo "$unit=active"
  else
    echo "$unit=inactive"
  fi
done
if ps -eo args= | grep -q '[r]esource-governor-patcher.py'; then
  echo "resource-governor-patcher.process=active"
else
  echo "resource-governor-patcher.process=inactive"
fi
'''


def remote_bootstrap_cmd() -> str:
    return f'''
set -e
export XDG_RUNTIME_DIR=/run/user/$(id -u)
cd {REPO}
bash {REMOTE_CGROUP_INIT} >/tmp/fleet-defense-cgroup-init.log 2>&1 || true
if ! systemctl --user is-active --quiet resource-governor-watchdog.service 2>/dev/null; then
  systemctl --user start resource-governor-watchdog.service
fi
if ! ps -eo args= | grep -q '[r]esource-governor-patcher.py'; then
  nohup python3 {REMOTE_PATCHER} >/home/ubuntu/.logs/resource-governor-patcher.log 2>&1 < /dev/null &
fi
if ! systemctl --user is-active --quiet inviolable-watchdog.timer 2>/dev/null; then
  systemctl --user start inviolable-watchdog.timer
fi
'''

def sync_remote_files(host: str) -> None:
    scp(LOCAL_INVIOLABLE, host, REMOTE_INVIOLABLE, timeout=20)
    scp(LOCAL_CGROUP_INIT, host, REMOTE_CGROUP_INIT, timeout=20)


def ensure_local() -> list[str]:
    actions: list[str] = []
    for slice_unit in ('omni-builds.slice', 'omni-interactive.slice', 'omni-transfers.slice'):
        if not local_is_active(slice_unit):
            local_start(slice_unit)
            actions.append(f'local:{slice_unit}:started')

    if not local_is_active('resource-governor-cgroup-init.service'):
        local_start('resource-governor-cgroup-init.service')
        actions.append('local:resource-governor-cgroup-init:started')

    if not local_is_active('resource-governor-watchdog.service'):
        local_start('resource-governor-watchdog.service')
        actions.append('local:resource-governor-watchdog:started')

    if not local_is_active('inviolable-watchdog.timer'):
        local_start('inviolable-watchdog.timer')
        actions.append('local:inviolable-watchdog.timer:started')

    return actions


@dataclass
class HostResult:
    host: str
    reachable: bool
    banner_stall: bool = False
    started: list[str] | None = None
    status: list[str] | None = None
    error: str = ''


def ensure_remote(host: str, ssh_target: str) -> HostResult:
    result = HostResult(host=host, reachable=False, started=[], status=[])

    rc, out, err = ssh(ssh_target, 'hostname', timeout=SSH_TIMEOUT)
    if rc != 0:
        text = f'{out} {err}'.strip()
        if 'banner exchange' in text.lower() or 'timed out' in text.lower():
            result.banner_stall = True
        result.error = text
        return result

    result.reachable = True

    # Sync the two files that gate the emergency path.
    sync_remote_files(ssh_target)

    # Check current state.
    rc, out, err = ssh(ssh_target, remote_state_cmd(), timeout=SSH_TIMEOUT)
    state_lines = [line.strip() for line in out.splitlines() if line.strip()]
    result.status = state_lines

    # Bootstrap/repair when the host is reachable.
    ssh(ssh_target, remote_bootstrap_cmd(), timeout=20)

    return result


def summary_to_string(result: HostResult) -> str:
    if not result.reachable:
        if result.banner_stall:
            return f'{result.host}:ssh-banner-stall'
        return f'{result.host}:unreachable'
    if result.status:
        return f'{result.host}:' + ','.join(result.status)
    return f'{result.host}:ok'


def main() -> int:
    deadline = time.monotonic() + MAX_SECONDS
    log(f'start max_seconds={MAX_SECONDS} poll_seconds={POLL_SECONDS} ssh_timeout={SSH_TIMEOUT}')

    # Keep the local protection layers alive immediately.
    try:
        local_actions = ensure_local()
        if local_actions:
            log('local-bootstrap ' + ' '.join(local_actions))
    except Exception as exc:
        log(f'local-bootstrap-error {type(exc).__name__}: {exc}')

    while RUNNING and time.monotonic() < deadline:
        cycle_started = time.monotonic()
        results: list[HostResult] = []

        for host, target in HOSTS.items():
            try:
                if host == 'srv1':
                    # Re-check local protection each cycle.
                    local_actions = ensure_local()
                    if local_actions:
                        log('local-heal ' + ' '.join(local_actions))
                    results.append(HostResult(host='srv1', reachable=True, status=['local-ok']))
                    continue

                assert target is not None
                result = ensure_remote(host, target)
                results.append(result)
                if result.reachable:
                    log(f'{host}:reachable ' + ' '.join(result.status or ['ok']))
                else:
                    log(summary_to_string(result))
            except Exception as exc:
                log(f'{host}:error {type(exc).__name__}: {exc}')

        elapsed = time.monotonic() - cycle_started
        sleep_for = max(1, POLL_SECONDS - int(elapsed))
        time.sleep(sleep_for)

    log('stop')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
