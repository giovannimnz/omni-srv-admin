"""metrics.py — cálculo unificado de uso de recursos para omni-srv-admin.

Mesma lógica do srv1-mission-checkpoint.sh (aplicado 2026-06-12):
  - Mem%   = (MemTotal - MemAvailable) / MemTotal * 100
  - Proc%  = soma %CPU de todos processos / nproc
  - Disk-Spc% = (used / total) * 100
  - Disk-RW% = MB/s agregado (exclui loop/ram/sr/dm-) / DISK_RW_MAX_MBPS * 100

Referência: 60-LOGS/2026-06-12-srv1-checkpoint-percent.md

Use:
  from metrics import mem_pct, proc_pct, disk_spc_pct, disk_rw_pct
  # valores inteiros 0-100+ (clamp 999 onde faz sentido)
"""
from __future__ import annotations

import os
import time
from pathlib import Path

CLK_TCK = os.sysconf("SC_CLK_TCK") or 100
DISK_RW_MAX_MBPS = float(os.environ.get("DISK_RW_MAX_MBPS", "250"))
DISK_RW_STATE_DIR = Path.home() / ".local" / "state" / "omni"


def _read_meminfo() -> dict[str, int]:
    """Parse /proc/meminfo (kB) safely."""
    out: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            parts = v.strip().split()
            try:
                out[k] = int(parts[0])
            except (ValueError, IndexError):
                pass
    except FileNotFoundError:
        pass
    return out


def mem_pct() -> int:
    """Memória em uso: (MemTotal - MemAvailable) / MemTotal * 100."""
    mi = _read_meminfo()
    total = mi.get("MemTotal", 0)
    avail = mi.get("MemAvailable", total)
    if total <= 0:
        return 0
    return int((total - avail) * 100 / total)


def proc_pct() -> int:
    """Soma CPU% de todos processos / nproc. 100% = uma CPU saturada.

    Lê /proc/[pid]/stat utime+stime entre 2 amostras (intervalo dt).
    CPU% = (delta_jiffies / dt) * 100 / CLK_TCK.

    Para chamada one-shot (snapshot): usa 1 amostra curta (50ms).
    """
    nproc = os.cpu_count() or 1
    snap1 = _sample_all_proc_cpu()
    time.sleep(0.05)
    snap2 = _sample_all_proc_cpu()
    total_jiffies = 0
    for pid, j1 in snap1.items():
        j2 = snap2.get(pid)
        if j2 is None:
            continue
        if j2 >= j1:
            total_jiffies += j2 - j1
    # total_jiffies em 50ms. CPU% agregado = total_jiffies / dt * 100 / CLK_TCK
    dt = 0.05
    pct = (total_jiffies / dt) * 100 / CLK_TCK
    pct = pct / nproc  # normaliza por nCPU
    if pct < 0:
        pct = 0
    if pct > 999:
        pct = 999
    return int(pct)


def _sample_all_proc_cpu() -> dict[int, int]:
    """Soma utime+stime de todos processos. Retorna {pid: jiffies}."""
    out: dict[int, int] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            pid = int(entry.name)
        except ValueError:
            continue
        try:
            content = (entry / "stat").read_text()
            rpar = content.rfind(")")
            if rpar < 0:
                continue
            rest = content[rpar + 2:].split()
            utime = int(rest[11]) if len(rest) > 12 else 0
            stime = int(rest[12]) if len(rest) > 13 else 0
            out[pid] = utime + stime
        except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError, ValueError):
            continue
    return out


def disk_spc_pct(path: str = "/") -> int:
    """% usado do filesystem. Via /proc/self/mountinfo + statvfs."""
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        if total <= 0:
            return 0
        used = total - free
        return int(used * 100 / total)
    except (FileNotFoundError, OSError):
        return 0


def _diskstats_total_sectors() -> int:
    """Soma sectors lidos+escritos de block devs reais (exclui loop/ram/sr/dm-)."""
    total = 0
    try:
        for line in Path("/proc/diskstats").read_text().splitlines():
            parts = line.split()
            if len(parts) < 11:
                continue
            dev = parts[2]
            if dev.startswith(("loop", "ram", "sr", "dm-")):
                continue
            try:
                rs = int(parts[5])
                ws = int(parts[9])
            except ValueError:
                continue
            total += rs + ws
    except FileNotFoundError:
        pass
    return total


def disk_rw_pct(state_path: Path | None = None) -> int:
    """I/O throughput agregado do sistema, normalizado por DISK_RW_MAX_MBPS.

    Mantém estado em .local/state/omni/disk-rw-prev (sectors + timestamp).
    """
    if state_path is None:
        state_path = DISK_RW_STATE_DIR / "disk-rw-prev"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    s_now = _diskstats_total_sectors()
    if state_path.exists():
        try:
            parts = state_path.read_text().split()
            if len(parts) == 2:
                s_prev = int(parts[0])
                t_prev = int(parts[1])
                dt = now - t_prev
                if dt <= 0:
                    dt = 1
                delta = s_now - s_prev
                if delta < 0:
                    delta = 0
                # bytes = delta * 512, MB/s = bytes / 1024 / 1024 / dt
                mb_s = delta * 512 / 1024 / 1024 / dt
                pct = mb_s * 100 / DISK_RW_MAX_MBPS
                if pct < 0:
                    pct = 0
                if pct > 999:
                    pct = 999
                # persistir nova amostra
                state_path.write_text(f"{s_now} {now}\n")
                return int(pct)
        except (ValueError, OSError):
            pass
    # primeira amostra: sem histórico
    state_path.write_text(f"{s_now} {now}\n")
    return 0


def proc_cpu_pct_from_jiffies(cur: int, prev: int, dt: float) -> float:
    """Helper: converte delta jiffies (utime+stime) em %CPU.

    Uso em loops de sampling per-PID:
        prev = cand.get('cpu_jiffies', cur)
        cand['cpu_pct'] = proc_cpu_pct_from_jiffies(cur, prev, dt)
    """
    if dt <= 0:
        return 0.0
    return (cur - prev) / dt * 100 / CLK_TCK


def all_metrics() -> dict[str, int]:
    """Coleta tudo de uma vez. Útil para snapshot único."""
    return {
        "mem_pct": mem_pct(),
        "proc_pct": proc_pct(),
        "disk_spc_pct": disk_spc_pct(),
        "disk_rw_pct": disk_rw_pct(),
    }


if __name__ == "__main__":
    # smoke test
    import sys
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "json":
        print(json.dumps(all_metrics()))
    else:
        m = all_metrics()
        print(f"Mem={m['mem_pct']}% Process={m['proc_pct']}% "
              f"Disk-Spc={m['disk_spc_pct']}% Disk-RW={m['disk_rw_pct']}%")
