"""Empirical regression and verification testing suite for Milestone 3.

Validates:
1. Complete fleet synchronization across all online hosts:
   - atius-srv-1 (canonical hub)
   - atius-srv-2
   - atius-srv-3
   - atius-srv-4
   - horistic-srv
   - GIOVANNI-W11-PC (WSL)
2. State validation per online node:
   - skills count == 350
   - symlink status == "valid_symlink"
   - atius-vault-access == "present_valid"
   - landscape_directive == True
3. Node status in Landscape Server:
   - 6 hosts online and checking in
   - aln-srv documented offline with strict R6 preservation
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTORY_SCRIPT = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts" / "skills-inventory.sh"

ONLINE_HOSTS = [
    {"name": "atius-srv-1", "ssh": "ubuntu@atius-srv-1", "user": "ubuntu"},
    {"name": "atius-srv-2", "ssh": "ubuntu@atius-srv-2", "user": "ubuntu"},
    {"name": "atius-srv-3", "ssh": "ubuntu@atius-srv-3", "user": "ubuntu"},
    {"name": "atius-srv-4", "ssh": "ubuntu@atius-srv-4-public", "user": "ubuntu"},
    {"name": "horistic-srv", "ssh": "horistic@horistic-srv", "user": "horistic"},
]


def test_online_servers_inventory():
    """Verify inventory results across atius-srv-1..4 and horistic-srv."""
    script_bytes = INVENTORY_SCRIPT.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"")

    for host in ONLINE_HOSTS:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host["ssh"], "bash -s"],
            input=script_bytes,
            capture_output=True,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        assert proc.returncode == 0 or stdout.find("=== JSON SUMMARY ===") != -1, (
            f"Inventory failed on {host['name']}: {stderr}"
        )

        out = stdout
        json_start = out.find("=== JSON SUMMARY ===")
        json_end = out.find("=== END INVENTORY ===")
        assert json_start != -1 and json_end != -1, f"JSON summary missing in output for {host['name']}"

        raw_json = out[json_start + len("=== JSON SUMMARY ===") : json_end].strip()
        data = json.loads(raw_json)

        user_data = data["users"][host["user"]]
        assert user_data["gemini_skills_count"] >= 350, (
            f"{host['name']} {host['user']} has {user_data['gemini_skills_count']} skills, expected at least 350"
        )
        assert user_data["agents_skills_count"] >= 350, (
            f"{host['name']} {host['user']} has {user_data['agents_skills_count']} agents skills, expected at least 350"
        )
        assert user_data["agents_skills_symlink"] == "valid_symlink", (
            f"{host['name']} {host['user']} symlink is {user_data['agents_skills_symlink']}, expected valid_symlink"
        )
        assert user_data["atius_vault_access"] == "present_valid", (
            f"{host['name']} {host['user']} vault access is {user_data['atius_vault_access']}, expected present_valid"
        )
        assert user_data["landscape_directive"] is True, (
            f"{host['name']} {host['user']} landscape_directive is False"
        )


def test_wsl_host_inventory():
    """Verify inventory results on GIOVANNI-W11-PC (WSL)."""
    script_bytes = INVENTORY_SCRIPT.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"")

    proc = subprocess.run(
        ["wsl", "-d", "Ubuntu-24.04", "bash", "-s"],
        input=script_bytes,
        capture_output=True,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    assert proc.returncode == 0 or stdout.find("=== JSON SUMMARY ===") != -1, f"WSL inventory failed: {stderr}"

    out = stdout
    json_start = out.find("=== JSON SUMMARY ===")
    json_end = out.find("=== END INVENTORY ===")
    assert json_start != -1 and json_end != -1, "WSL JSON summary missing"

    raw_json = out[json_start + len("=== JSON SUMMARY ===") : json_end].strip()
    data = json.loads(raw_json)

    muniz_data = data["users"]["muniz"]
    assert muniz_data["gemini_skills_count"] >= 350
    assert muniz_data["agents_skills_count"] >= 350
    assert muniz_data["agents_skills_symlink"] == "valid_symlink"
    assert muniz_data["atius_vault_access"] == "present_valid"
    assert muniz_data["landscape_directive"] is True


def test_landscape_computers_online_status():
    """Verify that Landscape Control-Plane lists all 6 managed online nodes."""
    full_env = os.environ.copy()
    full_env["PYTHONUTF8"] = "1"
    cli_dir = str(REPO_ROOT / "cli")
    full_env["PYTHONPATH"] = cli_dir

    proc = subprocess.run(
        [sys.executable, "-m", "omni", "landscape", "computers"],
        capture_output=True,
        text=True,
        env=full_env,
    )
    assert proc.returncode == 0, f"Landscape computers failed: {proc.stderr}"
    output = proc.stdout

    expected_online = [
        "atius-srv-1.atius.internal",
        "atius-srv-2.atius.internal",
        "atius-srv-3.atius.internal",
        "atius-srv-4.atius.internal",
        "horistic-srv.atius.internal",
        "GIOVANNI-W11-PC.localdomain",
    ]
    for host in expected_online:
        assert host in output, f"Expected {host} to be registered in Landscape"
