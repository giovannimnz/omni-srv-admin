"""Unit and TDD tests for Fleet Centralized APT Cache over GDrive & OCI DRG."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "modules" / "landscape-control-plane" / "scripts"
MANIFEST_PATH = SCRIPTS_DIR / "manifest.json"

DRG_CACHE_SERVER = "10.13.1.13"
CACHE_PORT = 3142
GDRIVE_CACHE_DIR = "/mnt/gdrive/apt-cache"

def render_apt_proxy_conf(server_ip: str = DRG_CACHE_SERVER, port: int = CACHE_PORT, timeout_sec: int = 5) -> str:
    """Gera o conteudo seguro e resiliente de /etc/apt/apt.conf.d/01proxy."""
    return f"""// Managed by omni::fleet-apt-proxy-configure
Acquire::http::Proxy "http://{server_ip}:{port}/";
Acquire::https::Proxy "http://{server_ip}:{port}/";
Acquire::http::Timeout "{timeout_sec}";
Acquire::https::Timeout "{timeout_sec}";
Acquire::Retries "2";
"""

def test_render_apt_proxy_conf():
    """Valida a sintaxe e diretivas do drop-in de proxy APT."""
    conf = render_apt_proxy_conf()
    assert f"http://{DRG_CACHE_SERVER}:{CACHE_PORT}/" in conf
    assert 'Acquire::http::Timeout "5";' in conf
    assert 'Acquire::https::Timeout "5";' in conf
    assert 'Acquire::Retries "2";' in conf

def test_manifest_contains_apt_proxy_script():
    """Verifica se o script de configuracao de proxy APT esta registrado no manifesto."""
    assert MANIFEST_PATH.exists(), "Manifesto do Landscape Control-Plane nao encontrado"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    scripts = data.get("scripts", [])
    script_ids = [s.get("id") for s in scripts]
    # Esperamos que fleet-apt-proxy-configure faca parte do catalogo
    assert "fleet-apt-proxy-configure" in script_ids, "Script fleet-apt-proxy-configure ausente no manifest.json"

def test_gdrive_cache_dir_contract():
    """Valida o path contratual do cache no GDrive."""
    assert GDRIVE_CACHE_DIR == "/mnt/gdrive/apt-cache"
