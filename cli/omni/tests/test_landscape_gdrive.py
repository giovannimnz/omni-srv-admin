"""Tier 3 Automated Test Suite for Landscape Control Plane Google Drive Automation.

Validates:
1. Landscape manifest integrity (schema v1, registered entries, script existence).
2. Bash syntax checking (bash -n) on setup-fleet-gdrive.sh and gdrive-fleet-setup.sh.
3. Concurrency lock (/var/lock/setup-fleet-gdrive.lock via flock) and idempotency.
4. Host-specific VFS cache quotas mapping and systemd integration.
5. Aggregatable JSON stdout contract parseable on the last line.
6. CLI integration via 'omni landscape scripts list'.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from click.testing import CliRunner

import pytest

from omni.landscape import (
    MANIFEST_PATH,
    _find_script,
    _load_manifest,
    _script_specs,
    landscape,
)

SCRIPTS_DIR = MANIFEST_PATH.parent
REPO_ROOT = MANIFEST_PATH.resolve().parents[2]
SETUP_SCRIPT_PATH = SCRIPTS_DIR / "setup-fleet-gdrive.sh"
ALIAS_SCRIPT_PATH = SCRIPTS_DIR / "gdrive-fleet-setup.sh"


def test_manifest_schema_and_integrity():
    """Valida conformidade do schema version 1 e integridade dos scripts registrados."""
    manifest = _load_manifest()

    assert manifest.get("schema_version") == 1
    assert manifest.get("namespace") == "omni-landscape"

    managed_hosts = manifest.get("managed_hosts", [])
    expected_hosts = ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4", "horistic-srv"]
    for host in expected_hosts:
        assert host in managed_hosts, f"Host {host} deve constar em managed_hosts"

    scripts = manifest.get("scripts", [])
    assert isinstance(scripts, list)
    assert len(scripts) >= 15

    # Sem duplicatas de id
    script_ids = [s.get("id") for s in scripts]
    assert len(script_ids) == len(set(script_ids)), "IDs de scripts no manifest nao podem conter duplicatas"

    # Presenca dos scripts de automacao gdrive
    assert "setup-fleet-gdrive" in script_ids, "setup-fleet-gdrive deve estar registrado no manifest"
    assert "gdrive-fleet-setup" in script_ids, "gdrive-fleet-setup deve estar registrado no manifest"

    # Validacao de campos mandatorios de cada script
    required_keys = {"id", "title", "version", "path", "interpreter", "username", "time_limit", "access_group", "risk", "description"}
    for script in scripts:
        missing = required_keys - set(script.keys())
        assert not missing, f"Script {script.get('id')} sem campos obrigatorios: {missing}"


def test_setup_fleet_gdrive_manifest_spec():
    """Valida especificacao detalhada do setup-fleet-gdrive no manifest."""
    spec = _find_script("setup-fleet-gdrive")
    assert spec.script_id == "setup-fleet-gdrive"
    assert spec.title == "omni::setup-fleet-gdrive"
    assert spec.version == "1.0.0"
    assert spec.interpreter == "/bin/bash"
    assert spec.username == "root"
    assert spec.time_limit == 300
    assert spec.access_group == "global"
    assert spec.risk == "reconcile"
    assert "Google Drive" in spec.description

    assert spec.path.is_file(), f"Arquivo do script {spec.path} deve existir fisicamente"
    assert len(spec.code) > 0, "Conteudo do script nao pode estar vazio"
    assert len(spec.sha256) == 64, "SHA256 deve ser um hex digest de 64 caracteres"

    alias_spec = _find_script("gdrive-fleet-setup")
    assert alias_spec.script_id == "gdrive-fleet-setup"
    assert alias_spec.path.is_file()
    assert len(alias_spec.code) > 0


def test_bash_syntax_validation():
    """Valida sintaxe bash (bash -n) em setup-fleet-gdrive.sh e gdrive-fleet-setup.sh."""
    bash_path = shutil.which("bash")
    if not bash_path:
        pytest.skip("Binario 'bash' nao disponivel no ambiente para sintaxe lint")

    for script_file in [SETUP_SCRIPT_PATH, ALIAS_SCRIPT_PATH]:
        assert script_file.is_file(), f"Arquivo {script_file} inexistente"

        rel_path = script_file.resolve().relative_to(REPO_ROOT).as_posix()

        proc = subprocess.run(
            [bash_path, "-n", rel_path],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"Erro de sintaxe bash em {script_file.name}:\n{proc.stderr}"
        assert proc.stderr == "", f"Stderr inesperado em {script_file.name}: {proc.stderr}"


def test_concurrency_lock_and_idempotency_contracts():
    """Valida presenca de lockfile, flock, idempotencia e higienizacao de legados."""
    code = SETUP_SCRIPT_PATH.read_text(encoding="utf-8")

    # 1. Concurrency lock
    assert "/var/lock/setup-fleet-gdrive.lock" in code, "Lockfile canônico deve ser /var/lock/setup-fleet-gdrive.lock"
    assert "flock -n 200" in code, "Deve utilizar flock -n 200 para concorrencia exclusiva"

    # 2. Instalacao nao-interativa
    assert "DEBIAN_FRONTEND=noninteractive" in code
    assert "apt-get -y -qq install fuse3 rclone" in code or "apt-get -y -qq install" in code

    # 3. Idempotencia em /etc/fuse.conf
    assert "/etc/fuse.conf" in code
    assert "user_allow_other" in code

    # 4. Higienizacao de legados
    assert "rclone-gdrive-mount.service" in code
    assert "mask rclone-gdrive-mount.service" in code
    assert "/home/ubuntu/GDrive" in code
    assert "fusermount -u -z" in code

    # 5. Helpers operacionais
    assert "/usr/local/bin/gdrive-vault-hydrate" in code
    assert "/usr/local/bin/gdrive-doctor" in code
    assert "chmod 755 /usr/local/bin/gdrive-vault-hydrate" in code
    assert "chmod 755 /usr/local/bin/gdrive-doctor" in code

    # 6. Unit systemd canônica
    assert "/etc/systemd/system/gdrive-mount.service" in code
    assert "systemctl daemon-reload" in code
    assert "systemctl enable gdrive-mount.service" in code
    assert "systemctl restart gdrive-mount.service" in code
    assert "mountpoint -q" in code


def test_host_cache_quotas_configuration():
    """Valida mapeamento das cotas VFS por host gravadas em /etc/default/gdrive-mount."""
    code = SETUP_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "/etc/default/gdrive-mount" in code

    # Quotas de cada host
    expected_quotas = {
        "atius-srv-1": ("3G", "6h"),
        "atius-srv-2": ("10G", "24h"),
        "atius-srv-3": ("5G", "12h"),
        "atius-srv-4": ("30G", "48h"),
        "horistic-srv": ("10G", "24h"),
    }

    for host, (size, age) in expected_quotas.items():
        assert host in code, f"Host {host} deve constar no case de hostname"
        assert f'CACHE_MAX_SIZE="{size}"' in code or f"CACHE_MAX_SIZE={size}" in code
        assert f'CACHE_MAX_AGE="{age}"' in code or f"CACHE_MAX_AGE={age}" in code

    # Default fallback
    assert 'CACHE_MAX_SIZE="4G"' in code or "CACHE_MAX_SIZE=4G" in code
    assert 'CACHE_MAX_AGE="12h"' in code or "CACHE_MAX_AGE=12h" in code


def test_aggregatable_json_output_contract():
    """Valida que o payload emitido na ultima linha obedece ao contrato JSON agregavel."""
    code = SETUP_SCRIPT_PATH.read_text(encoding="utf-8")

    # Extrai o printf de saida JSON final
    json_match = re.search(r'printf \'({\s*"status":\s*"PASS".*?})\s*\\n\'', code, re.DOTALL)
    assert json_match is not None, "Padrao de emissao JSON 'PASS' nao encontrado no final do script"

    template = json_match.group(1)
    # Substitui marcadores %s via formatacao posicional
    formatted_json = template % ("atius-srv-1", "/mnt/gdrive")

    data = json.loads(formatted_json)
    assert data["status"] == "PASS"
    assert data["host"] == "atius-srv-1"
    assert data["mountpoint"] == "/mnt/gdrive"
    assert data["service_active"] is True

    # Valida tambem os payloads de erro emitidos pelo script
    fail_matches = re.findall(r'printf \'({.*?"status":\s*"FAIL".*?})\s*\\n\'', code)
    assert len(fail_matches) >= 2, "Devem existir payloads JSON parseaveis de falha"
    for fail_tpl in fail_matches:
        if "%s" in fail_tpl:
            count_s = fail_tpl.count("%s")
            args = ("test-val",) * count_s
            rendered = fail_tpl % args
        else:
            rendered = fail_tpl
        fail_data = json.loads(rendered)
        assert fail_data["status"] == "FAIL"


def test_landscape_cli_scripts_list():
    """Valida que 'omni landscape scripts list' exibe setup-fleet-gdrive e gdrive-fleet-setup."""
    runner = CliRunner()
    result = runner.invoke(landscape, ["scripts", "list"])

    assert result.exit_code == 0
    assert "setup-fleet-gdrive" in result.output
    assert "gdrive-fleet-setup" in result.output
    assert "reconcile" in result.output
    assert "omni::setup-fleet-gdrive" in result.output


def test_scripts_synchronization():
    """Valida que gdrive-fleet-setup.sh permanece sincronizado com setup-fleet-gdrive.sh."""
    setup_code = SETUP_SCRIPT_PATH.read_text(encoding="utf-8")
    alias_code = ALIAS_SCRIPT_PATH.read_text(encoding="utf-8")

    # Ambos devem conter o lockfile, a unit gdrive-mount.service e o payload JSON
    for critical_string in [
        "/var/lock/setup-fleet-gdrive.lock",
        "flock -n 200",
        "/etc/default/gdrive-mount",
        "gdrive-mount.service",
        "/usr/local/bin/gdrive-vault-hydrate",
        "/usr/local/bin/gdrive-doctor",
        '"status": "PASS"',
    ]:
        assert critical_string in setup_code, f"String '{critical_string}' ausente em setup-fleet-gdrive.sh"
        assert critical_string in alias_code, f"String '{critical_string}' ausente em gdrive-fleet-setup.sh"
