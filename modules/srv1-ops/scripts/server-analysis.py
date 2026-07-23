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

# Thresholds for auto-fix
DISK_WARN = 85
DISK_CRITICAL = 92
SWAP_WARN = 85
SWAP_CRITICAL = 95
CPU_PSI_WARN = 15
CPU_PSI_CRITICAL = 30
MEM_LOW_WARN = 2048   # MiB
MEM_LOW_CRITICAL = 800

# Crash-loop detection
CRASH_LOOP_RESTART_THRESHOLD = 5
CRASH_LOOP_TIME_WINDOW_MIN = 60

ANALYSIS_LOG_DIR.mkdir(parents=True, exist_ok=True)

BRT_TZ = timezone(timedelta(hours=-3))

# === KNOWN FIXES DATABASE ===
# Container name patterns -> fix actions for crash-loop
KNOWN_FIXES = {
    "cloudbeaver": [
        {
            "check": "permission denied",
            "fix_cmd": "sudo chown -R 8978:8978 /home/ubuntu/docker/infra/cloudbeaver/workspace && sudo docker stop cloudbeaver-cloudbeaver-1 2>/dev/null; sudo docker rm cloudbeaver-cloudbeaver-1 2>/dev/null; sudo docker run -d --name cloudbeaver-cloudbeaver-1 --restart unless-stopped -p 8978:8978 -v /home/ubuntu/docker/infra/cloudbeaver/workspace:/opt/cloudbeaver/workspace dbeaver/cloudbeaver:latest",
            "desc": "Workspace owned by root. Recreate with UID 8978 perms."
        }
    ],
    "hermes-ws-gateway": [
        {
            "check": "address already in use|port.*in use|eaddrinuse",
            "fix_cmd": "lsof -ti:8300 2>/dev/null | xargs kill -9 2>/dev/null; sleep 2; pm2 restart hermes-ws-gateway-pg",
            "desc": "Port conflict — kill lingering PID, restart via PM2."
        }
    ],
    "plane-app": [
        {
            "check": "connection refused|econnrefused.*db|postgres.*connect",
            "fix_cmd": "cd /home/ubuntu/docker/Atius/plane && sudo docker compose restart plane-db 2>/dev/null; sleep 5; sudo docker compose up -d 2>/dev/null",
            "desc": "DB connection issue — restart database first, then stack."
        }
    ],
    "paperclip": [
        {
            "check": "port.*already allocated|address.*in use",
            "fix_cmd": "sudo docker stop paperclip-atius-db 2>/dev/null; sudo docker rm paperclip-atius-db 2>/dev/null; sudo docker run -d --name paperclip-atius-db --restart unless-stopped -e POSTGRES_PASSWORD=atius2024 postgres:17-alpine",
            "desc": "Port conflict or DB corruption — recreate container."
        }
    ]
}

def log(msg):
    ts = datetime.now(BRT_TZ).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry)
    (ANALYSIS_LOG_DIR / "analysis.log").open("a").write(entry + "\n")

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", f"TIMEOUT ({timeout}s)", -1
    except Exception as e:
        return "", str(e), -1

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
        # Fallback: try generic restart
        runtime = container_info["runtime"]
        name = container_info["name"]
        log(f"  Fallback: tentando {runtime} restart {name}")
        r_out, r_err, r_rc = run_cmd(
            f"sudo {runtime} restart {shlex.quote(name)} 2>/dev/null", timeout=30
        ) if runtime == "docker" else run_cmd(
            f"{runtime} restart {shlex.quote(name)} 2>/dev/null", timeout=30
        )
        return r_rc == 0


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
                "desc": f"Podman unused volumes ({count} encontrados; revisar antes de aplicar)"
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
    if disk_avg >= DISK_WARN:
        sev = "critical" if disk_avg >= DISK_CRITICAL else "warning"
        disk_trend = disk_pcts[-1] - disk_pcts[0] if len(disk_pcts) > 1 else 0
        trend_str = f"(+{disk_trend:.1f}%/15min)" if disk_trend > 1 else ("(estável)" if abs(disk_trend) <= 1 else f"({disk_trend:+.1f}%/15min)")
        issues.append({
            "type": "disk",
            "severity": sev,
            "value": f"{disk_avg:.1f}%",
            "trend": trend_str,
            "detail": f"Disco a {disk_avg:.1f}% ({latest.get('disk_free_gib', 0):.1f}G livre) {trend_str}"
        })

    # Swap
    swap_avg = avg(swap_pcts)
    if swap_avg >= SWAP_WARN:
        sev = "critical" if swap_avg >= SWAP_CRITICAL else "warning"
        issues.append({
            "type": "swap",
            "severity": sev,
            "value": f"{swap_avg:.1f}%",
            "detail": f"Swap a {swap_avg:.1f}% {'— CRÍTICO' if swap_avg >= SWAP_CRITICAL else '— elevado'}"
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
    mem_avg = avg(mem_avail)
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
        "disk_pct": f"{disk_avg:.1f}%",
        "disk_free_gib": latest.get("disk_free_gib", 0),
        "swap_pct": f"{swap_avg:.1f}%",
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
        # DISK CRITICAL → cleanup + deep reclaim
        if issue["type"] == "disk" and issue["severity"] == "critical":
            log("AUTO-FIX: Disco crítico — executando cleanup-local.sh")
            out, err, rc = run_cmd(
                "~/GitHub/omni-srv-admin/modules/srv1-ops/scripts/cleanup-local.sh",
                timeout=120
            )
            if rc == 0:
                out2, _, _ = run_cmd("df -h / | tail -1 | awk '{print $5, $4}'")
                fixes.append(f"cleanup-local: {out2}")
            else:
                fixes.append(f"cleanup-local FALHOU: {err[:80] if err else 'rc!=0'}")

            # Deep reclaim: prune dangling images + unused volumes
            reclaimable = analyze_disk_deep()
            if reclaimable:
                log(f"AUTO-FIX: Recuperação profunda — {len(reclaimable)} itens encontrados")
                results = auto_reclaim_disk(reclaimable)
                fixes.extend(results)
            else:
                log("  Nada recuperável via prune")

        # DISK WARNING (not critical) → just deep reclaim check
        elif issue["type"] == "disk" and issue["severity"] == "warning":
            log("AUTO-FIX: Disco elevado — verificando reclaim profundo")
            reclaimable = analyze_disk_deep()
            if reclaimable:
                results = auto_reclaim_disk(reclaimable)
                fixes.extend(results)
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
                # Try generic restart
                runtime = ci["runtime"]
                name = ci["name"]
                r_out, r_err, r_rc = run_cmd(
                    f"sudo {runtime} start {shlex.quote(name)} 2>/dev/null", timeout=30
                ) if runtime == "docker" else run_cmd(
                    f"{runtime} start {shlex.quote(name)} 2>/dev/null", timeout=30
                )
                if r_rc == 0:
                    fixes.append(f"restart {ci['name']}: OK")
                else:
                    fixes.append(f"restart {ci['name']}: FALHOU ({r_err[:80]})")
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
        fixes.append(f"journal errors: {len(errors)} (ex: {errors[0]})")
        log(f"  {len(errors)} erros (amostra: {errors[0] if errors else '?'})")
    else:
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
    daily_path.open("a").write(json.dumps(report, default=str) + "\n")

    brief = (
        f"[{now.strftime('%H:%M')}] "
        f"issues={len(issues)} fixes={len(fixes)} "
        f"crash={len(crash_issues) if crash_issues else 0} "
        f"disk={summary.get('disk_pct','?')} "
        f"swap={summary.get('swap_pct','?')} "
        f"mem={summary.get('mem_available_mib','?')}MiB "
        f"psi={summary.get('cpu_psi_some_avg10','?')}"
    )
    (ANALYSIS_LOG_DIR / "brief.log").open("a").write(brief + "\n")
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
