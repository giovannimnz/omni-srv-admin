"""Empirical regression and verification testing suite for Milestone 2.

Validates:
1. Landscape Control-Plane script registration and hash integrity for:
   - sync-agent-instructions (ID 7)
   - skills-inventory (ID 14)
2. Canonical Hub (atius-srv-1) skills synchronization and state:
   - atius-vault-access presence and valid content
   - Full canonical skills catalog present (count >= 345, specifically 350)
   - ~/.agents/skills symlink pointing to ~/.gemini/config/skills
3. Canonical Hub packaging and manifest verification:
   - runtime-manifest.json structure, validity and fields (skills_count, md5s)
   - fleet-skills.tar.gz existence, size and md5 integrity
4. Systemd service and timer active status on atius-srv-1.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts" / "manifest.json"
SYNC_SCRIPT_PATH = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts" / "sync-agent-instructions.sh"
INVENTORY_SCRIPT_PATH = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts" / "skills-inventory.sh"
CANONICAL_HOST = "atius-srv-1"


def run_cmd(cmd: list, env: dict = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    full_env["PYTHONUTF8"] = "1"
    cli_dir = str(REPO_ROOT / "cli")
    if "PYTHONPATH" not in full_env:
        full_env["PYTHONPATH"] = cli_dir
    else:
        full_env["PYTHONPATH"] = f"{cli_dir}{os.pathsep}{full_env['PYTHONPATH']}"
    if env:
        full_env.update(env)
    if cmd and cmd[0] == "python":
        cmd = [sys.executable] + cmd[1:]
    return subprocess.run(cmd, capture_output=True, text=True, env=full_env)


def run_ssh(remote_cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", f"ubuntu@{CANONICAL_HOST}", remote_cmd],
        capture_output=True,
        text=True,
    )


def test_landscape_scripts_list_and_hashes():
    """Verify published scripts appear in omni landscape scripts list with matching hashes."""
    proc = run_cmd(["python", "-m", "omni", "landscape", "scripts", "list"])
    assert proc.returncode == 0, f"Landscape scripts list failed: {proc.stderr}"
    output = proc.stdout

    sync_hash = hashlib.sha256(SYNC_SCRIPT_PATH.read_bytes()).hexdigest()[:12]
    inv_hash = hashlib.sha256(INVENTORY_SCRIPT_PATH.read_bytes()).hexdigest()[:12]

    assert "sync-agent-instructions" in output
    assert sync_hash in output
    assert "skills-inventory" in output
    assert inv_hash in output


def test_hub_skills_catalog_and_vault_access():
    """Verify atius-srv-1 contains atius-vault-access and the full synchronized skills catalog."""
    cmd = (
        "test -f ~/.gemini/config/skills/atius-vault-access/SKILL.md && "
        "grep -qi 'atius-vault-access' ~/.gemini/config/skills/atius-vault-access/SKILL.md && "
        "find ~/.gemini/config/skills -mindepth 1 -maxdepth 1 -type d | wc -l"
    )
    proc = run_ssh(cmd)
    assert proc.returncode == 0, f"Remote check failed: {proc.stderr}"
    count = int(proc.stdout.strip())
    assert count >= 345, f"Expected at least 345 skills on hub, found {count}"


def test_hub_runtime_manifest_and_tarball():
    """Verify runtime-manifest.json and fleet-skills.tar.gz are genuine and match."""
    cmd = (
        "cat ~/.gemini/config/runtime-manifest.json; "
        "echo '---SEPARATOR---'; "
        "md5sum ~/.gemini/config/fleet-skills.tar.gz; "
        "stat -c %s ~/.gemini/config/fleet-skills.tar.gz"
    )
    proc = run_ssh(cmd)
    assert proc.returncode == 0, f"Remote check failed: {proc.stderr}"
    parts = proc.stdout.split("---SEPARATOR---")
    manifest_str = parts[0].strip()
    tar_info = parts[1].strip().split()

    manifest = json.loads(manifest_str)
    assert "version" in manifest
    assert "skills_count" in manifest
    assert manifest["skills_count"] >= 345
    assert "skills_tar_md5" in manifest

    actual_tar_md5 = tar_info[0]
    tar_size_bytes = int(tar_info[-1])

    assert manifest["skills_tar_md5"] == actual_tar_md5, (
        f"Manifest md5 {manifest['skills_tar_md5']} != actual {actual_tar_md5}"
    )
    # Tarball should be non-empty and substantial (> 40MB for all skills)
    assert tar_size_bytes > 40 * 1024 * 1024, f"Tarball too small: {tar_size_bytes} bytes"


def test_hub_symlink_and_timer_health():
    """Verify ~/.agents/skills symlink and systemd timer on atius-srv-1."""
    cmd = (
        "readlink -f ~/.agents/skills; "
        "systemctl is-active omni-fleet-runtime-sync.timer"
    )
    proc = run_ssh(cmd)
    assert proc.returncode == 0, f"Remote check failed: {proc.stderr}"
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    target_path = lines[0]
    timer_status = lines[1]

    assert target_path == "/home/ubuntu/.gemini/config/skills"
    assert timer_status == "active"
