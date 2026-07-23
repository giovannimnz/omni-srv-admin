#!/usr/bin/env python3
"""
Backup Dangling Podman Volumes + Images → GDrive.
Robusto: state tracking, per-item timeout, single-pass pipeline, resume automático.

Problemas corrigidos:
- ❌ Sequential 3-pass (tar → gzip → cp) → ✅ Pipeline single-pass (tar czf - | pv > dest)
- ❌ ionice em CPU-bound (gzip) → ✅ pv rate-limit no write, sem ionice no CPU
- ❌ Timeout global de 600s → ✅ Per-item timeout de 300s com state tracking
- ❌ Sem resume → ✅ State file JSON, skipa itens já feitos
- ❌ GDrive via cp (sem retry) → ✅ rclone copy (checksums, retries, progress)
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# === CONFIG ===
GDRIVE_BASE = Path.home() / "GDrive" / "Backups" / "cleanup-pre-clean-2026-06-07"
STATE_FILE = Path.home() / ".logs" / "backup-dangling-state.json"
LOG_FILE = Path.home() / ".logs" / "backup-dangling.log"
LOCAL_TEMP = Path("/tmp/backup-dangling")
IO_RATE = "80M"  # MB/s — ≈75% de 108 MB/s
ITEM_TIMEOUT = 300  # seconds per item (small volumes)
ITEM_TIMEOUT_LARGE = 600  # seconds for volumes >1G
MAX_RETRIES = 3
COMPRESS_CMD = "pigz --fast"  # parallel gzip (uses >1 core, ~4x faster on ARM64)

BRT_TZ = timezone(timedelta(hours=-3))

LOCAL_TEMP.mkdir(parents=True, exist_ok=True)
GDRIVE_BASE.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.now(BRT_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG_FILE.open("a").write(line + "\n")

def run_cmd(cmd, timeout=ITEM_TIMEOUT):
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", f"TIMEOUT ({timeout}s)", 124
    except Exception as e:
        return "", str(e), -1

# === STATE MANAGEMENT ===

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, Exception):
            pass
    return {"volumes": {}, "images": {}, "started_at": None, "completed_at": None}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

def is_volume_done(state, vol_name):
    return state["volumes"].get(vol_name, {}).get("status") == "done"

def mark_volume_done(state, vol_name, size, gdrive_path):
    state["volumes"][vol_name] = {
        "status": "done",
        "size": size,
        "gdrive_path": str(gdrive_path),
        "completed_at": datetime.now(BRT_TZ).isoformat()
    }
    save_state(state)

def mark_volume_failed(state, vol_name, error):
    state["volumes"][vol_name] = {
        "status": "failed",
        "error": error[:200],
        "attempted_at": datetime.now(BRT_TZ).isoformat()
    }
    save_state(state)

# === BACKUP FUNCTIONS ===

def backup_volume(vol_name, mount_path):
    """
    Backup single Podman volume using single-pass pipeline:
    tar czf - (reads + compresses) | pv -L 80M (rate-limit) > dest.tar.gz
    No intermediate files. No 3x I/O.
    """
    local_dest = LOCAL_TEMP / f"{vol_name}.tar.gz"
    gdrive_dest = GDRIVE_BASE / "podman-volumes" / f"{vol_name}.tar.gz"
    
    # Ensure GDrive dir exists
    gdrive_dest.parent.mkdir(parents=True, exist_ok=True)

    log(f"  Backup: {vol_name}")
    log(f"    Source: {mount_path}")
    
    # Check size for dynamic timeout
    size_bytes_out, _, _ = run_cmd(
        f"du -sb {shlex_quote(mount_path)} 2>/dev/null | awk '{{print $1}}'",
        timeout=10
    )
    try:
        size_bytes = int(size_bytes_out.strip())
        size_mb = size_bytes / 1024 / 1024
        timeout = ITEM_TIMEOUT_LARGE if size_mb > 1000 else ITEM_TIMEOUT
        size_hr = f"{size_mb:.0f}M" if size_mb < 1024 else f"{size_mb/1024:.1f}G"
    except (ValueError, IndexError):
        size_mb = 0
        timeout = ITEM_TIMEOUT_LARGE  # be safe if we can't detect
        size_hr = "?"
    log(f"    Tamanho: {size_hr}, timeout: {timeout}s")

    # Single-pass pipeline: tar | pigz (parallel compress) | pv (I/O throttle) > file
    cmd = (
        f"tar cf - -C {shlex_quote(mount_path)} . 2>/dev/null "
        f"| {COMPRESS_CMD} "
        f"| pv -q -L {IO_RATE} -W "
        f"> {shlex_quote(str(local_dest))}"
    )
    
    start = time.time()
    log(f"    Pipeline (tar|{COMPRESS_CMD.split()[0]}|pv)...")
    out, err, rc = run_cmd(cmd, timeout=timeout)
    elapsed = time.time() - start

    if rc != 0:
        log(f"    ERRO (rc={rc}, {elapsed:.0f}s): {err[:150]}")
        # Clean up partial
        local_dest.unlink(missing_ok=True)
        return False

    # Check file
    if not local_dest.exists() or local_dest.stat().st_size == 0:
        log(f"    ERRO: arquivo vazio após pipeline")
        local_dest.unlink(missing_ok=True)
        return False

    dest_size = local_dest.stat().st_size
    log(f"    Concluído em {elapsed:.0f}s, {dest_size / 1024 / 1024:.1f} MB")

    # Copy to GDrive via rclone (reliable, retries, checksums)
    log(f"    Copiando para GDrive (rclone)...")
    cmd = (
        f"rclone copy {shlex_quote(str(local_dest))} {shlex_quote(str(gdrive_dest.parent))}/ "
        f"--bwlimit={IO_RATE} --retries=3 --low-level-retries=5 --log-level=ERROR"
    )
    copy_out, copy_err, copy_rc = run_cmd(cmd, timeout=120)
    
    if copy_rc != 0:
        log(f"    ERRO rclone: {copy_err[:150]}")
        # Fallback: cp direto
        log(f"    Fallback: cp direto...")
        shutil.copy2(local_dest, gdrive_dest)

    # Verify
    if gdrive_dest.exists():
        gdr_size = gdrive_dest.stat().st_size
        log(f"    ✓ GDrive: {gdr_size / 1024 / 1024:.1f} MB")
    else:
        log(f"    FALHA: arquivo não encontrado no GDrive")
        local_dest.unlink(missing_ok=True)
        return False

    # Clean local temp
    local_dest.unlink(missing_ok=True)
    return True


def backup_podman_image(img_id, img_size):
    """Backup Podman dangling image — save diretamente no GDrive (sem disco local)."""
    dest_name = f"image-{img_id[:12]}.tar"
    gdrive_dest = GDRIVE_BASE / "podman-images" / dest_name
    
    # Ensure GDrive dir exists
    gdrive_dest.parent.mkdir(parents=True, exist_ok=True)

    log(f"  Backup image: {img_id[:12]} (size={img_size})")
    log(f"    Salvando direto no GDrive (disco local cheio)...")

    # podman save directly to GDrive mount (avoids local temp disk entirely)
    timeout = ITEM_TIMEOUT_LARGE
    cmd = f"ionice -c 2 -n 7 podman save -o {shlex_quote(str(gdrive_dest))} {img_id} 2>/dev/null"
    
    start = time.time()
    out, err, rc = run_cmd(cmd, timeout=timeout)
    elapsed = time.time() - start

    if rc != 0:
        log(f"    ERRO save (rc={rc}, {elapsed:.0f}s): {err[:150]}")
        gdrive_dest.unlink(missing_ok=True)
        return False

    if not gdrive_dest.exists() or gdrive_dest.stat().st_size == 0:
        log(f"    ERRO: arquivo vazio ({gdrive_dest})")
        return False

    dest_size = gdrive_dest.stat().st_size
    log(f"    ✓ Salvo em {elapsed:.0f}s, {dest_size / 1024 / 1024:.1f} MB no GDrive")
    return True


def shlex_quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def main():
    start_time = time.time()
    state = load_state()
    
    if state.get("completed_at"):
        log("Backup já foi concluído anteriormente. Pulando.")
        return

    log("=" * 65)
    log("BACKUP DANGLING — Podman Volumes + Images")
    log(f"GDrive: {GDRIVE_BASE}")
    log(f"I/O limit: {IO_RATE}/s via pv")
    log(f"Per-item timeout: {ITEM_TIMEOUT}s")
    log(f"State: {STATE_FILE}")
    log("=" * 65)

    # === FASE 1: Podman Volumes ===
    log("\n=== FASE 1: Podman Volumes ===")
    out, _, _ = run_cmd("podman volume ls -qf dangling=true 2>/dev/null", timeout=10)
    volumes = [v for v in out.strip().split('\n') if v.strip()]
    log(f"Volumes dangling: {len(volumes)}")

    if state["started_at"] is None:
        state["started_at"] = datetime.now(BRT_TZ).isoformat()
        save_state(state)

    vol_ok = 0
    vol_fail = 0
    for vol_name in volumes:
        if is_volume_done(state, vol_name):
            log(f"  SKIP {vol_name} — já concluído")
            vol_ok += 1
            continue

        mount_out, _, _ = run_cmd(
            f"podman volume inspect {vol_name} --format '{{{{.Mountpoint}}}}' 2>/dev/null",
            timeout=10
        )
        mount_path = mount_out.strip()
        if not mount_path:
            log(f"  PULANDO {vol_name} — sem mountpoint")
            vol_fail += 1
            continue

        ok = backup_volume(vol_name, mount_path)
        if ok:
            mark_volume_done(state, vol_name, "?", 
                           GDRIVE_BASE / "podman-volumes" / f"{vol_name}.tar.gz")
            vol_ok += 1
        else:
            mark_volume_failed(state, vol_name, "backup failed")
            vol_fail += 1

    # === FASE 2: Podman Images ===
    log("\n=== FASE 2: Podman Dangling Images ===")
    out, _, _ = run_cmd(
        "podman images --filter dangling=true --format '{{.ID}} {{.Size}}' 2>/dev/null",
        timeout=10
    )
    images = [l.strip() for l in out.strip().split('\n') if l.strip()]
    log(f"Imagens dangling: {len(images)}")

    img_ok = 0
    img_fail = 0
    for img_line in images:
        parts = img_line.split(None, 1)
        img_id = parts[0]
        img_size = parts[1] if len(parts) > 1 else "?"
        
        if state["images"].get(img_id, {}).get("status") == "done":
            log(f"  SKIP {img_id[:12]} — já concluído")
            img_ok += 1
            continue

        ok = backup_podman_image(img_id, img_size)
        if ok:
            state["images"][img_id] = {
                "status": "done",
                "size": img_size,
                "completed_at": datetime.now(BRT_TZ).isoformat()
            }
            save_state(state)
            img_ok += 1
        else:
            state["images"][img_id] = {"status": "failed"}
            save_state(state)
            img_fail += 1

    # === FASE 3: Verify ===
    log("\n=== FASE 3: Verificação ===")
    size_out, _, _ = run_cmd(
        f"du -sh {shlex_quote(str(GDRIVE_BASE))} 2>/dev/null", timeout=10
    )
    log(f"Total no GDrive: {size_out}")

    find_out, _, _ = run_cmd(
        f"find {shlex_quote(str(GDRIVE_BASE))} -type f | wc -l", timeout=10
    )
    find_size, _, _ = run_cmd(
        f"du -sh {shlex_quote(str(GDRIVE_BASE))} 2>/dev/null | awk '{{print $1}}'", timeout=10
    )
    log(f"Arquivos: {find_out.strip()} ({find_size})")

    # === CLEANUP ===
    log("\n=== CLEANUP ===")
    out, err, rc = run_cmd("podman volume prune -f", timeout=60)
    log(f"podman volume prune: {'OK' if rc == 0 else err[:100]}")

    out, err, rc = run_cmd("podman image prune -f", timeout=60)
    log(f"podman image prune: {'OK' if rc == 0 else err[:100]}")

    # Disk after
    disk_out, _, _ = run_cmd("df -h / | tail -1", timeout=5)
    log(f"Disco final: {disk_out}")

    state["completed_at"] = datetime.now(BRT_TZ).isoformat()
    save_state(state)

    elapsed = time.time() - start_time
    log(f"\nResumo: {vol_ok}/{len(volumes)} volumes, {img_ok}/{len(images)} imagens")
    log(f"Tempo total: {elapsed:.0f}s")
    log("=" * 65)


if __name__ == "__main__":
    # Force UTF-8
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, TypeError):
        pass
    main()
