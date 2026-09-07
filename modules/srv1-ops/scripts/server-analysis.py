#!/usr/bin/env python3
"""
Server Analysis Engine — runs every 15 minutes.
Analyzes perf data, system logs, containers, and disk.
Auto-implements improvements: crash-loop recovery, disk reclaim, container health.

Two-layer system:
  L1: systemd timer (server-analysis.timer) — pure Python, 0 tokens
  L2: Hermes cron (server-analysis-deep)    — AI-powered deep analysis
"""

import json
import fcntl
import os
import subprocess
import sys
import time
import shlex
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# === CONFIG ===
PERF_FILE = Path.home() / ".logs/resource-governor/perf.jsonl"
ANALYSIS_LOG_DIR = Path.home() / ".logs/server-analysis"
ANALYSIS_INTERVAL_MIN = 15
DISK_REMEDIATION_STATE_FILE = (
    Path.home() / ".local/state/omni/server-analysis-remediation.json"
)
DISK_REMEDIATION_LOCK_FILE = (
    Path.home() / ".local/state/omni/server-analysis-remediation.lock"
)
DISK_CLEANUP_COOLDOWN_SECONDS = int(
    os.environ.get("SERVER_ANALYSIS_DISK_CLEANUP_COOLDOWN_SECONDS", str(6 * 60 * 60))
)
DISK_CLEANUP_UNIT = "resource-governor-post-build-cleanup.service"

# Thresholds for auto-fix
DISK_WARN = 85
DISK_CRITICAL = 92
SWAP_WARN = 85
SWAP_CRITICAL = 95
CPU_PSI_WARN = 15
CPU_PSI_CRITICAL = 30
MEM_LOW_WARN = 2048   # MiB
MEM_LOW_CRITICAL = 800
SWAP_MEMORY_OK = 4096  # MiB: high swap alone is normal cold-page retention

# Crash-loop detection
CRASH_LOOP_RESTART_THRESHOLD = 5
CRASH_LOOP_TIME_WINDOW_MIN = 60

ANALYSIS_LOG_DIR.mkdir(parents=True, exist_ok=True)

BRT_TZ = timezone(timedelta(hours=-3))

# Auto-repair is fail-closed. Add a fix only after its current Podman/systemd
# contract, backup and rollback are covered by tests. Legacy Docker commands and
# inline credentials are forbidden here.
KNOWN_FIXES = {}

def log(msg):
    ts = datetime.now(BRT_TZ).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry)
    with (ANALYSIS_LOG_DIR / "analysis.log").open("a", encoding="utf-8") as handle:
        handle.write(entry + "\n")

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", f"TIMEOUT ({timeout}s)", -1
    except Exception as e:
        return "", str(e), -1


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp.chmod(0o600)
        os.replace(tmp, path)
        path.chmod(0o600)
    finally:
        tmp.unlink(missing_ok=True)


def attempt_disk_cleanup(now=None):
    """Run light governed cleanup at most once per persistent cooldown."""
    attempted_at = float(time.time() if now is None else now)
    DISK_REMEDIATION_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISK_REMEDIATION_LOCK_FILE.touch(mode=0o600, exist_ok=True)
    DISK_REMEDIATION_LOCK_FILE.chmod(0o600)

    with DISK_REMEDIATION_LOCK_FILE.open("r+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        state = {}
        if DISK_REMEDIATION_STATE_FILE.exists():
            try:
                state = json.loads(DISK_REMEDIATION_STATE_FILE.read_text())
                if not isinstance(state, dict):
                    raise ValueError("state root must be an object")
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                log(f"  SKIP cleanup: state inválido ({exc})")
                return {"status": "state-invalid"}

        last_attempt = float(state.get("last_attempt_ts", 0.0) or 0.0)
        elapsed = max(0.0, attempted_at - last_attempt)
        if last_attempt > 0 and elapsed < DISK_CLEANUP_COOLDOWN_SECONDS:
            remaining = max(0, int(DISK_CLEANUP_COOLDOWN_SECONDS - elapsed))
            return {"status": "cooldown", "remaining_seconds": remaining}

        command = f"systemctl --user start {DISK_CLEANUP_UNIT}"
        state.update(
            {
                "last_attempt_ts": attempted_at,
                "last_command": command,
                "cooldown_seconds": DISK_CLEANUP_COOLDOWN_SECONDS,
            }
        )
        _write_json_atomic(DISK_REMEDIATION_STATE_FILE, state)

        out, err, rc = run_cmd(command, timeout=120)
        status = "success" if rc == 0 else "failed"
        state.update(
            {
                "last_result": status,
                "last_returncode": rc,
                "last_error": err[:200] if err else "",
            }
        )
        if rc == 0:
            state["last_success_ts"] = attempted_at
        _write_json_atomic(DISK_REMEDIATION_STATE_FILE, state)
        return {
            "status": status,
            "attempted_at": attempted_at,
            "returncode": rc,
            "stdout": out[:200] if out else "",
            "stderr": err[:200] if err else "",
        }

def read_perf_window(minutes=ANALYSIS_INTERVAL_MIN):
    if not PERF_FILE.exists():
        return [], 0
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    entries = []
    count_before = 0
    count_after = 0
    with open(PERF_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                ts_str = d.get("ts", "")
                entry_ts = datetime.fromisoformat(ts_str)
                count_before += 1
                if entry_ts >= cutoff:
                    count_after += 1
                    entries.append(d)
            except (json.JSONDecodeError, ValueError):
                continue
    return entries, count_after

# ============================================================
# CONTAINER CRASH-LOOP DETECTION + AUTO-REMEDIATION
# ============================================================

def detect_crash_loops():
    """
    Check ALL Docker + Podman containers for crash-loop patterns.
    Returns list of (name, runtime, restarts, status, log_snippet, known_fix)
    """
    issues = []

    # --- Docker ---
    out, _, _ = run_cmd("sudo docker ps -a --format '{{.Names}}|{{.Status}}|{{.Restarts}}' 2>/dev/null")
    if out:
        for line in out.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 2)
            if len(parts) < 3:
                continue
            name, status, restarts_str = parts
            try:
                restarts = int(restarts_str)
            except ValueError:
                restarts = 0

            is_crash_loop = False
            severity = "ok"

            if "Restarting" in status:
                is_crash_loop = True
                severity = "crash-loop"
            elif restarts >= CRASH_LOOP_RESTART_THRESHOLD:
                is_crash_loop = True
                severity = "crash-loop"
            elif "unhealthy" in status.lower():
                severity = "unhealthy"
            elif "exited" in status.lower() and "0" not in status:
                is_crash_loop = True
                severity = "crashed"

            if is_crash_loop or severity != "ok":
                # Get recent logs
                logs, _, _ = run_cmd(f"sudo docker logs {shlex.quote(name)} --tail 10 2>&1", timeout=5)
                log_snippet = logs[:300] if logs else "(no logs)"
                
                # Match against known fixes
                matched_fix = match_known_fix(name, logs)

                issues.append({
                    "name": name,
                    "runtime": "docker",
                    "severity": severity,
                    "restarts": restarts,
                    "status": status,
                    "log_snippet": log_snippet,
                    "known_fix": matched_fix
                })

    # --- Podman ---
    out, _, _ = run_cmd("podman ps -a --format '{{.Names}}|{{.Status}}|{{.RestartCount}}' 2>/dev/null")
    if out:
        for line in out.split('\n'):
            line = line.strip()
            if not line or '|' not in line:
                continue
            parts = line.split('|', 2)
            if len(parts) < 3:
                continue
            name, status, restarts_str = parts
            try:
                restarts = int(restarts_str)
            except ValueError:
                restarts = 0

            is_crash_loop = False
            severity = "ok"

            if "unhealthy" in status.lower():
                severity = "unhealthy"
            elif restarts >= CRASH_LOOP_RESTART_THRESHOLD:
                is_crash_loop = True
                severity = "crash-loop"

            if is_crash_loop or severity != "ok":
                logs, _, _ = run_cmd(f"podman logs {shlex.quote(name)} --tail 10 2>&1", timeout=5)
                log_snippet = logs[:300] if logs else "(no logs)"
                matched_fix = match_known_fix(name, logs)

                issues.append({
                    "name": name,
                    "runtime": "podman",
                    "severity": severity,
                    "restarts": restarts,
                    "status": status,
                    "log_snippet": log_snippet,
                    "known_fix": matched_fix
                })

    return issues


def match_known_fix(container_name, logs):
    """Match container against known fixes database."""
    logs_lower = logs.lower() if logs else ""

    for pattern, fixes in KNOWN_FIXES.items():
        if pattern in container_name.lower():
            for fix in fixes:
                check = fix.get("check", "")
                if check:
                    if any(token in logs_lower for token in check.split("|")):
                        return fix
    return None


def auto_fix_crash_loop(container_info):
    """Apply known fix for crash-looping container. Returns True if fix was applied."""
    fix = container_info.get("known_fix")
    if not fix:
        log(f"  Sem fix conhecido para {container_info['name']} — skip auto-repair")
        return False

    fix_cmd = fix.get("fix_cmd", "")
    desc = fix.get("desc", "")
    log(f"AUTO-FIX: Aplicando fix para {container_info['name']}: {desc}")
    log(f"  Comando: {fix_cmd[:120]}...")

    out, err, rc = run_cmd(fix_cmd, timeout=60)
    if rc == 0:
        log(f"  Fix aplicado com sucesso para {container_info['name']}")
        return True
    else:
        log(f"  Fix FALHOU para {container_info['name']}: {err[:200] if err else 'rc!=0'}")
        return False


# ============================================================
# DEEP DISK ANALYSIS
# ============================================================

def analyze_disk_deep():
    """
    Deep disk analysis — find major waste and categorise it.
    Returns list of recoverable items with estimated savings.
    """
    reclaimable = []
    
    # Podman dangling images
    out, _, _ = run_cmd(
        "podman images --filter dangling=true --format '{{.ID}} {{.Size}}' 2>/dev/null | "
        "awk '{sum+=$2} END {print sum}'",
        timeout=10
    )
    if out and out.strip():
        try:
            podman_bytes = int(out.strip())
            if podman_bytes > 100 * 1024 * 1024:  # >100MB
                reclaimable.append({
                    "source": "podman-dangling",
                    "size_bytes": podman_bytes,
                    "action": "podman image prune -f",
                    "desc": "Podman dangling images"
                })
        except ValueError:
            pass

    # Unused Podman volumes are reported for explicit review only.
    out, _, _ = run_cmd(
        "podman volume ls -qf dangling=true 2>/dev/null | wc -l",
        timeout=5
    )
    if out and out.strip():
        count = int(out.strip())
        if count > 0:
            reclaimable.append({
                "source": "podman-volumes",
                "action": "podman volume prune -f",
                "desc": f"Podman unused volumes ({count} encontrados; revisar antes de aplicar)",
                "auto_apply": False,
            })

    # Snap cache (old revisions)
    out, _, _ = run_cmd(
        "sudo snap list --all 2>/dev/null | awk '/disabled/{print $1, $3}' | sort -u",
        timeout=10
    )
    if out and out.strip():
        lines = [l.strip() for l in out.split('\n') if l.strip()]
        count = len(lines)
        if count > 0:
            # Build safe sequential remove per snap
            snaps_seen = {}
            for l in lines:
                parts = l.split()
                if len(parts) >= 2:
                    snap_name, rev = parts[0], parts[1]
                    if snap_name not in snaps_seen:
                        snaps_seen[snap_name] = []
                    snaps_seen[snap_name].append(rev)
            
            # Generate sequential remove commands (one snap at a time)
            remove_cmds = []
            for snap_name, revs in snaps_seen.items():
                for rev in revs:
                    remove_cmds.append(f"sudo snap remove {shlex.quote(snap_name)} --revision={rev} 2>/dev/null || true")
            
            if remove_cmds:
                reclaimable.append({
                    "source": "snap-revisions",
                    "action": "; ".join(remove_cmds),
                    "desc": f"Snap disabled revisions ({len(remove_cmds)} total)"
                })

    return reclaimable


def auto_reclaim_disk(reclaimable_items):
    """Execute disk reclamation for all items found. Returns list of results."""
    results = []
    for item in reclaimable_items:
        if item.get("auto_apply") is False:
            results.append(f"{item['source']}: SKIP revisão explícita necessária")
            log(f"  SKIP: {item['desc']}")
            continue
        log(f"AUTO-FIX: Recuperando espaço — {item['desc']}")
        out, err, rc = run_cmd(item["action"], timeout=120)
        if rc == 0:
            # Get freed space
            lines = out.split('\n')
            freed = "?"
            for l in lines:
                if 'reclaimed' in l.lower() or 'freed' in l.lower() or 'total' in l.lower():
                    freed = l.strip()[:60]
                    break
            results.append(f"{item['source']}: OK{f' ({freed})' if freed != '?' else ''}")
            log(f"  OK{f' — {freed}' if freed != '?' else ''}")
        else:
            results.append(f"{item['source']}: FALHOU ({err[:80]})")
            log(f"  FALHOU: {err[:100]}")
    return results


# ============================================================
# TREND ANALYSIS (existing)
# ============================================================

def analyze_trends(entries):
    issues = []
    if not entries:
        return issues, {}

    disk_pcts = [e.get("system", {}).get("disk_pct", 0) for e in entries if e.get("system")]
    swap_pcts = [e.get("system", {}).get("swap_pct", 0) for e in entries if e.get("system")]
    mem_avail = [e.get("system", {}).get("mem_available_mib", 0) for e in entries if e.get("system")]
    cpu_load_1m = [e.get("system", {}).get("load", {}).get("1m", 0) for e in entries if e.get("system")]
    cpu_psi = [e.get("system", {}).get("psi", {}).get("cpu_some_avg10", 0) for e in entries if e.get("system")]
    io_psi = [e.get("system", {}).get("psi", {}).get("io_some_avg10", 0) for e in entries if e.get("system")]

    latest = entries[-1].get("system", {})
    reasons = entries[-1].get("reasons", [])

    def avg(vals):
        return sum(vals) / len(vals) if vals else 0

    # Disk
    disk_avg = avg(disk_pcts)
    disk_latest = disk_pcts[-1] if disk_pcts else 0
    if disk_latest >= DISK_WARN:
        sev = "critical" if disk_latest >= DISK_CRITICAL else "warning"
        disk_trend = disk_pcts[-1] - disk_pcts[0] if len(disk_pcts) > 1 else 0
        trend_str = f"(+{disk_trend:.1f}%/15min)" if disk_trend > 1 else ("(estável)" if abs(disk_trend) <= 1 else f"({disk_trend:+.1f}%/15min)")
        issues.append({
            "type": "disk",
            "severity": sev,
            "value": f"{disk_latest:.1f}%",
            "trend": trend_str,
            "detail": (
                f"Disco atual {disk_latest:.1f}%; média 15min {disk_avg:.1f}% "
                f"({latest.get('disk_free_gib', 0):.1f}G livre) {trend_str}"
            )
        })

    mem_avg = avg(mem_avail)

    # Swap is pressure only when available memory is also constrained. This
    # desktop intentionally retains cold pages in swap while keeping >4 GiB
    # available; classifying that state as critical creates permanent noise.
    swap_avg = avg(swap_pcts)
    swap_pressure = "normal-cold-pages"
    if swap_avg >= SWAP_WARN and mem_avg < SWAP_MEMORY_OK:
        swap_pressure = "memory-pressure"
        sev = (
            "critical"
            if swap_avg >= SWAP_CRITICAL and mem_avg <= MEM_LOW_WARN
            else "warning"
        )
        issues.append({
            "type": "swap",
            "severity": sev,
            "value": f"{swap_avg:.1f}%",
            "detail": (
                f"Swap a {swap_avg:.1f}% com {mem_avg:.0f} MiB disponíveis "
                f"{'— CRÍTICO' if sev == 'critical' else '— elevado'}"
            )
        })

    # CPU pressure
    cpu_psi_avg = avg(cpu_psi) if cpu_psi else 0
    if cpu_psi_avg >= CPU_PSI_WARN:
        sev = "critical" if cpu_psi_avg >= CPU_PSI_CRITICAL else "warning"
        issues.append({
            "type": "cpu_pressure",
            "severity": sev,
            "value": f"PSI avg10={cpu_psi_avg:.1f}",
            "detail": f"Pressão CPU PSI some avg10={cpu_psi_avg:.1f}"
        })

    # Low memory
    if mem_avg <= MEM_LOW_WARN:
        sev = "critical" if mem_avg <= MEM_LOW_CRITICAL else "warning"
        issues.append({
            "type": "memory",
            "severity": sev,
            "value": f"{mem_avg:.0f} MiB disp.",
            "detail": f"Memória disponível: {mem_avg:.0f} MiB"
        })

    top_cpu = entries[-1].get("top_cpu", [])
    top_mem = entries[-1].get("top_mem", [])

    summary = {
        "disk_pct": f"{disk_latest:.1f}%",
        "disk_avg_pct": f"{disk_avg:.1f}%",
        "disk_free_gib": latest.get("disk_free_gib", 0),
        "swap_pct": f"{swap_avg:.1f}%",
        "swap_pressure": swap_pressure,
        "mem_available_mib": f"{mem_avg:.0f}",
        "cpu_load_1m": f"{avg(cpu_load_1m):.2f}",
        "cpu_psi_some_avg10": f"{cpu_psi_avg:.1f}",
        "io_psi_some_avg10": f"{avg(io_psi):.1f}",
        "reasons": reasons,
        "top_cpu": [f"{p.get('pid','?')}@{p.get('cpu',0)}%" for p in top_cpu[:5]],
        "top_mem": [f"{p.get('pid','?')}@{p.get('mem',0)}%" for p in top_mem[:5]],
        "entries_analyzed": len(entries),
        "mode": entries[-1].get("mode", "unknown"),
    }
    return issues, summary


def auto_fix(issues, summary):
    fixes = []

    for issue in issues:
        # DISK CRITICAL → one governed light cleanup per persistent cooldown.
        if issue["type"] == "disk" and issue["severity"] == "critical":
            cleanup = attempt_disk_cleanup()
            summary["disk_cleanup"] = cleanup
            if cleanup["status"] == "success":
                log("AUTO-FIX: Disco crítico — cleanup leve governado executado")
                out2, _, _ = run_cmd("df -h / | tail -1 | awk '{print $5, $4}'")
                fixes.append(f"cleanup-local leve: {out2}")
            elif cleanup["status"] == "cooldown":
                log(
                    "SKIP cleanup: cooldown persistente "
                    f"({cleanup['remaining_seconds']}s restantes)"
                )
            elif cleanup["status"] == "failed":
                fixes.append(
                    "cleanup-local leve FALHOU: "
                    f"rc={cleanup.get('returncode', '?')}"
                )

        # DISK WARNING → inventory only. Mutations require the governed lane.
        elif issue["type"] == "disk" and issue["severity"] == "warning":
            log("Disco elevado — inventariando reclaim sem aplicar")
            reclaimable = analyze_disk_deep()
            summary["disk_reclaim_candidates"] = [
                item["desc"] for item in reclaimable
            ]
            if reclaimable:
                log(f"  {len(reclaimable)} candidate(s); nenhuma mutação aplicada")
            else:
                log("  Nada recuperável via prune")
                # Check what's using space
                out, _, _ = run_cmd("du -sh /home/ubuntu/.local/share/* 2>/dev/null | sort -rh | head -5", timeout=10)
                if out:
                    fixes.append(f"maiores dirs: {out[:200]}")

        # SWAP CRITICAL
        elif issue["type"] == "swap" and issue["severity"] == "critical":
            log("AUTO-FIX: Swap crítico — identificando consumidores")
            out, _, _ = run_cmd(
                "for pid in $(find /proc -maxdepth 1 -type d -name '[0-9]*' 2>/dev/null); do "
                "swap=$(awk '/Swap:/ {sum+=$2} END {print sum}' $pid/smaps 2>/dev/null); "
                "name=$(cat $pid/comm 2>/dev/null); "
                "[ -n \"$swap\" ] && [ \"$swap\" -gt 1024 ] 2>/dev/null && "
                "printf '%d %s\\n' $swap \"$name\"; "
                "done | sort -rn | head -5"
            )
            if out:
                lines = [
                    f"{int(l.split()[0])//1024}M {l.split(' ',1)[1] if len(l.split(' ',1))>1 else '?'}"
                    for l in out.strip().split('\n') if l.strip()
                ]
                fixes.append(f"top swap: {', '.join(lines)}")

    # === ALWAYS RUN: container health check ===
    log("Container health check...")
    crash_issues = detect_crash_loops()
    if crash_issues:
        log(f"  {len(crash_issues)} containers com problemas:")
        for ci in crash_issues:
            if ci["severity"] == "crash-loop":
                log(f"  CRASH-LOOP [{ci['runtime']}] {ci['name']} ({ci['restarts']} restart(s)): {ci['status']}")
                fix_applied = auto_fix_crash_loop(ci)
                if fix_applied:
                    fixes.append(f"crash-loop {ci['name']}: fix aplicado")
                else:
                    fixes.append(f"crash-loop {ci['name']}: sem fix automático")
            elif ci["severity"] == "unhealthy":
                log(f"  UNHEALTHY [{ci['runtime']}] {ci['name']}: {ci['status']}")
                fixes.append(f"unhealthy {ci['name']}: {ci['status']}")
            elif ci["severity"] == "crashed":
                log(f"  CRASHED [{ci['runtime']}] {ci['name']}: {ci['status']}")
                fixes.append(f"crashed {ci['name']}: intervenção governada necessária")
    else:
        log("  Todos os containers saudáveis")

    # === ALWAYS RUN: journal errors ===
    log("Verificando journal (15min)...")
    out, _, _ = run_cmd(
        "journalctl --since '15 min ago' -p err --no-pager 2>/dev/null | "
        "grep -v -E 'systemd-logind|dbus|audit|snapd' | tail -10"
    )
    if out:
        errors = [e.strip()[:120] for e in out.strip().split('\n') if e.strip()][:5]
        summary["journal_error_count"] = len(errors)
        summary["journal_error_sample"] = errors[0]
        log(f"  {len(errors)} erros (amostra: {errors[0] if errors else '?'})")
    else:
        summary["journal_error_count"] = 0
        log("  Sem erros novos")

    return fixes


def save_report(issues, crash_issues, reclaimable, summary, fixes):
    now = datetime.now(BRT_TZ)
    report = {
        "ts": now.isoformat(),
        "window_minutes": ANALYSIS_INTERVAL_MIN,
        "issues": issues,
        "crash_loops": crash_issues or [],
        "reclaimable": reclaimable or [],
        "summary": summary,
        "fixes_applied": fixes,
        "issue_count": len(issues),
        "crash_loop_count": len(crash_issues) if crash_issues else 0,
        "fix_count": len(fixes),
    }
    latest_path = ANALYSIS_LOG_DIR / "latest.json"
    latest_path.write_text(json.dumps(report, indent=2, default=str))

    daily_path = ANALYSIS_LOG_DIR / f"analysis-{now.strftime('%Y-%m-%d')}.jsonl"
    with daily_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, default=str) + "\n")

    brief = (
        f"[{now.strftime('%H:%M')}] "
        f"issues={len(issues)} fixes={len(fixes)} "
        f"crash={len(crash_issues) if crash_issues else 0} "
        f"disk={summary.get('disk_pct','?')} "
        f"swap={summary.get('swap_pct','?')} "
        f"mem={summary.get('mem_available_mib','?')}MiB "
        f"psi={summary.get('cpu_psi_some_avg10','?')}"
    )
    with (ANALYSIS_LOG_DIR / "brief.log").open("a", encoding="utf-8") as handle:
        handle.write(brief + "\n")
    return report


def main():
    start = time.time()
    log("=" * 65)
    log(f"ANÁLISE SRV-1 ({ANALYSIS_INTERVAL_MIN}min window)")

    # Read perf data
    entries, count = read_perf_window()
    log(f"perf: {len(entries)}/{count} entries (últimos {ANALYSIS_INTERVAL_MIN}min)")

    # Trend analysis
    issues, summary = analyze_trends(entries)
    for i in issues:
        log(f"  ISSUE [{i['severity']}] {i['type']}: {i['detail']}")

    # Deep disk analysis (always run, even if no perf data)
    log("Disk deep scan...")
    reclaimable = analyze_disk_deep()
    if reclaimable:
        log(f"  {len(reclaimable)} itens recuperáveis:")
        for r in reclaimable:
            log(f"    - {r['desc']}")

    # Container crash-loop detection
    log("Crash-loop scan...")
    crash_issues = detect_crash_loops()
    if crash_issues:
        for ci in crash_issues:
            log(f"  [{ci['severity']}] {ci['name']} ({ci['restarts']} restarts): {ci['status']}")
    else:
        log("  Nenhum crash-loop detectado")

    # Auto-fix
    fixes = auto_fix(issues, summary)
    for f in fixes:
        log(f"  FIX: {f}")

    # Save report
    report = save_report(issues, crash_issues, reclaimable, summary, fixes)

    elapsed = time.time() - start
    log(f"Análise completa em {elapsed:.1f}s")
    log("=" * 65)

    # Summary line for cron delivery
    issue_lines = []
    if issues:
        for i in issues:
            issue_lines.append(f"[{i['severity'].upper()}] {i['type']}: {i['detail']}")
    if crash_issues:
        for ci in crash_issues[:3]:
            issue_lines.append(f"[CRASH] {ci['name']}: {ci['status']} ({ci['restarts']} restarts)")
    if fixes:
        for f in fixes:
            issue_lines.append(f"  -> {f}")

    if issue_lines:
        print(f"\n[SERVER ANALYSIS] {report['issue_count']} issue(s), {report['fix_count']} auto-fix(es):")
        for l in issue_lines:
            print(f"  {l}")
    else:
        print(f"\n[SERVER ANALYSIS] OK | disk={summary.get('disk_pct','?')} swap={summary.get('swap_pct','?')} mem={summary.get('mem_available_mib','?')}MiB")

    sys.exit(0 if (not issues and not crash_issues) else 1)


if __name__ == "__main__":
    main()
