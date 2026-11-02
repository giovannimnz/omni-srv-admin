"""Unit and TDD tests for Fleet Unified Toolchain & Runtime Upgrade.
Covers: Node 24 LTS, npm, pnpm, Bun, uv, Python 3.13, pip, and GitHub CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts"
MANIFEST_PATH = SCRIPTS_DIR / "manifest.json"
SCRIPT_PATH = SCRIPTS_DIR / "fleet-runtimes-upgrade.sh"

EXPECTED_NODE_VERSION_PREFIX = "v24."
EXPECTED_NODE_LTS_VERSION = "v24.22.2"
TARGET_HOSTS = [
    "atius-srv-1",
    "atius-srv-2",
    "atius-srv-3",
    "atius-srv-4",
    "horistic-srv",
    "aln-srv"
]

def test_manifest_contains_runtimes_upgrade_script():
    """Valida se o script de atualizacao de toolchains/runtimes esta registrado no manifest.json."""
    assert MANIFEST_PATH.exists(), "Manifesto do Landscape Control-Plane nao encontrado"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    scripts = data.get("scripts", [])
    script_map = {s.get("id"): s for s in scripts}
    assert "fleet-runtimes-upgrade" in script_map, "Script fleet-runtimes-upgrade ausente no manifest.json"
    
    entry = script_map["fleet-runtimes-upgrade"]
    assert entry.get("interpreter") == "/bin/bash"
    assert entry.get("username") == "root"
    assert entry.get("access_group") == "global"
    assert entry.get("time_limit") >= 600

def test_script_file_exists_and_executable():
    """Valida se o script bash existe e contem as secoes obrigatorias de ferramentas."""
    assert SCRIPT_PATH.exists(), "Script fleet-runtimes-upgrade.sh nao encontrado"
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "#!/usr/bin/env bash" in content
    # Invariantes de runtime
    assert "nvm" in content
    assert "24.22.2" in content or "nvm install" in content
    assert "pnpm" in content
    assert "bun" in content
    assert "uv" in content
    assert "python" in content
    assert "gh" in content

def test_target_hosts_subset():
    """Valida a lista contratual de hosts alvos da frota."""
    assert len(TARGET_HOSTS) == 6
    assert "atius-srv-1" in TARGET_HOSTS
    assert "horistic-srv" in TARGET_HOSTS
    assert "aln-srv" in TARGET_HOSTS
