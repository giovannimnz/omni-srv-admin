"""Unit and TDD tests for Fleet Google Drive storage mount automation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[3]
REPO_CLI = REPO / "cli"
if str(REPO_CLI) not in sys.path:
    sys.path.insert(0, str(REPO_CLI))

import pytest
from click.testing import CliRunner

from omni.gdrive import (
    DEFAULT_CACHE_DIR,
    DEFAULT_MOUNTPOINT,
    HOST_CACHE_QUOTAS,
    get_host_quota,
    render_systemd_unit,
    build_rclone_conf_content,
    gdrive,
)
from omni.landscape import _load_manifest


def test_host_cache_quotas():
    """Valida as quotas de cache VFS estritas por host."""
    assert HOST_CACHE_QUOTAS["atius-srv-1"] == ("5G", "12h")
    assert HOST_CACHE_QUOTAS["atius-srv-2"] == ("10G", "24h")
    assert HOST_CACHE_QUOTAS["atius-srv-3"] == ("5G", "12h")
    assert HOST_CACHE_QUOTAS["atius-srv-4"] == ("30G", "48h")

    # Host desconhecido recebe cota conservadora default
    size, age = get_host_quota("unknown-host-x")
    assert size == "4G"
    assert age == "12h"

    # Host conhecido
    size_srv1, age_srv1 = get_host_quota("atius-srv-1")
    assert size_srv1 == "5G"
    assert age_srv1 == "12h"


def test_render_systemd_unit():
    """Valida renderizacao do systemd unit gdrive-mount.service."""
    unit = render_systemd_unit(
        hostname="atius-srv-1",
        mountpoint="/mnt/gdrive",
        cache_dir="/var/cache/rclone-gdrive",
    )
    assert "[Unit]" in unit
    assert "Description=Atius Fleet Google Drive FUSE Mount" in unit
    assert "After=network-online.target" in unit
    assert "Wants=network-online.target" in unit
    assert "[Service]" in unit
    assert "Type=notify" in unit
    assert "/mnt/gdrive" in unit
    assert "--vfs-cache-mode full" in unit
    assert "--vfs-cache-max-size 5G" in unit
    assert "--vfs-cache-max-age 12h" in unit
    assert "--config /run/rclone/rclone.conf" in unit
    assert "--allow-other" in unit
    assert "ExecStop=/bin/fusermount -u -z /mnt/gdrive" in unit
    assert "Restart=on-failure" in unit
    assert "KillMode=mixed" in unit
    assert "CPUQuota=20%" in unit
    assert "Nice=10" in unit
    assert "--tpslimit 4" in unit
    assert "--drive-pacer-min-sleep 100ms" in unit


def test_build_rclone_conf_content():
    """Valida geracao segura de rclone.conf a partir de credenciais Vault com compact JSON separators."""
    client_id = "test-client-id.apps.googleusercontent.com"
    client_secret = "test-client-secret"
    refresh_token = "1//test-refresh-token"

    conf = build_rclone_conf_content(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )
    assert "[gdrive-main]" in conf
    assert "type = drive" in conf
    assert f"client_id = {client_id}" in conf
    assert f"client_secret = {client_secret}" in conf
    assert "token = {" in conf
    # Verifica serializacao JSON sem espacos desnecessarios (separators=(',', ':'))
    assert f'"refresh_token":"{refresh_token}"' in conf
    assert "scope = drive" in conf


def test_build_rclone_conf_validation():
    """Rejeita valores vazios para evitar configuracao quebrada."""
    with pytest.raises(ValueError, match="client_id obrigatorio"):
        build_rclone_conf_content("", "secret", "token")

    with pytest.raises(ValueError, match="client_secret obrigatorio"):
        build_rclone_conf_content("id", "", "token")

    with pytest.raises(ValueError, match="refresh_token obrigatorio"):
        build_rclone_conf_content("id", "secret", "")


def test_gdrive_cli_help():
    """Valida estrutura do CLI omni gdrive e presenca de todos os subcomandos canonicos."""
    runner = CliRunner()
    result = runner.invoke(gdrive, ["--help"])
    assert result.exit_code == 0
    assert "quotas" in result.output
    assert "status" in result.output
    assert "mount" in result.output
    assert "unmount" in result.output
    assert "test" in result.output
    assert "doctor" in result.output
    assert "check" in result.output
    assert "health" in result.output


def test_gdrive_cli_quotas():
    """Valida comando omni gdrive quotas em modo texto e JSON."""
    runner = CliRunner()
    result = runner.invoke(gdrive, ["quotas"])
    assert result.exit_code == 0
    assert "atius-srv-1" in result.output
    assert "5G" in result.output
    assert "atius-srv-4" in result.output
    assert "30G" in result.output

    # Modo JSON
    res_json = runner.invoke(gdrive, ["quotas", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert "quotas" in data
    assert data["quotas"]["atius-srv-1"]["max_size"] == "5G"
    assert data["quotas"]["atius-srv-4"]["max_size"] == "30G"
    assert data["mountpoint"] == "/mnt/gdrive"


def test_gdrive_cli_status():
    """Valida omni gdrive status com saidas canonicas e flag --json."""
    runner = CliRunner()

    # Cenário 1: Sucesso (todos montados e ativos -> exit code 0)
    with patch("omni.gdrive._exec_host_cmd", return_value=(0, "active|mounted|1.2G|42", "")):
        result = runner.invoke(gdrive, ["status", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["hosts"][0]["service"] == "active"
        assert data["hosts"][0]["mount"] == "mounted"

    # Cenário 2: Inativo / Desmontado -> exit code 2
    with patch("omni.gdrive._exec_host_cmd", return_value=(0, "inactive|not-mounted|0|0", "")):
        result = runner.invoke(gdrive, ["status", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["status"] == "inactive"

    # Cenário 3: Erro de comunicacao SSH -> exit code 1
    with patch("omni.gdrive._exec_host_cmd", return_value=(1, "", "Connection timed out")):
        result = runner.invoke(gdrive, ["status", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["status"] == "error"


def test_gdrive_cli_mount_and_unmount():
    """Valida omni gdrive mount e unmount com mock e flag --json."""
    runner = CliRunner()

    # Mount Sucesso -> exit code 0
    with patch("omni.gdrive._exec_host_cmd", return_value=(0, "active|mounted", "")):
        result = runner.invoke(gdrive, ["mount", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "PASS"

    # Mount Falha -> exit code 1
    with patch("omni.gdrive._exec_host_cmd", return_value=(1, "failed|not-mounted", "Unit failed")):
        result = runner.invoke(gdrive, ["mount", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["status"] == "FAIL"

    # Unmount Sucesso -> exit code 0
    with patch("omni.gdrive._exec_host_cmd", return_value=(0, "unmounted", "")):
        result = runner.invoke(gdrive, ["unmount", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "PASS"


def test_gdrive_cli_test_and_check():
    """Valida omni gdrive test e check."""
    runner = CliRunner()

    # Test probe PASS -> exit code 0
    with patch("omni.gdrive._exec_host_cmd", return_value=(0, "PASS", "")):
        result = runner.invoke(gdrive, ["test", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "PASS"

    # Test probe FAIL -> exit code 1
    with patch("omni.gdrive._exec_host_cmd", return_value=(1, "WRITE_FAIL", "Disk full")):
        result = runner.invoke(gdrive, ["test", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 1

    # Check mounted -> exit code 0
    with patch("omni.gdrive._exec_host_cmd", return_value=(0, "OK", "")):
        result = runner.invoke(gdrive, ["check", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "PASS"

    # Check unmounted -> exit code 2
    with patch("omni.gdrive._exec_host_cmd", return_value=(0, "NOT_MOUNTED", "")):
        result = runner.invoke(gdrive, ["check", "--host", "atius-srv-1", "--json"])
        assert result.exit_code == 2


def test_landscape_manifest_registered_gdrive():
    """Valida registro do script gdrive-fleet-setup no manifest do Landscape."""
    manifest = _load_manifest()
    scripts = manifest.get("scripts", [])
    script_ids = [s.get("id") for s in scripts]
    assert "gdrive-fleet-setup" in script_ids

    spec = next(s for s in scripts if s.get("id") == "gdrive-fleet-setup")
    assert spec["interpreter"] == "/bin/bash"
    assert spec["username"] == "root"
    assert spec["path"] == "gdrive-fleet-setup.sh"


def test_gdrive_cli_list_subpath():
    """Valida omni gdrive list garantindo que subpath vazio nao gera aspas simples."""
    runner = CliRunner()
    with patch("omni.gdrive._exec_host_cmd") as mock_exec:
        mock_exec.return_value = (0, "total 0\n-rw-r--r-- 1 root root 0 test.txt", "")
        # Subpath vazio default
        res = runner.invoke(gdrive, ["list"])
        assert res.exit_code == 0
        assert mock_exec.call_args[0][1] == "ls -la /mnt/gdrive"

        # Subpath vazio explicito
        res2 = runner.invoke(gdrive, ["list", "--path", ""])
        assert res2.exit_code == 0
        assert mock_exec.call_args[0][1] == "ls -la /mnt/gdrive"

        # Subpath com barra
        res3 = runner.invoke(gdrive, ["list", "--path", "/backups"])
        assert res3.exit_code == 0
        assert mock_exec.call_args[0][1] == "ls -la /mnt/gdrive/backups"


def test_exec_host_cmd_ssh_routing():
    """Valida mapeamento de usuario e resolucao de FQDN/internal no comando SSH."""
    from omni.gdrive import _exec_host_cmd

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        # Host padrao sem ponto -> adiciona .atius.internal com usuario ubuntu
        _exec_host_cmd("atius-srv-1", "ls")
        assert mock_run.call_args[0][0][6] == "ubuntu@atius-srv-1.atius.internal"

        # Host com FQDN -> nao duplica .atius.internal
        _exec_host_cmd("atius-srv-1.atius.com.br", "ls")
        assert mock_run.call_args[0][0][6] == "ubuntu@atius-srv-1.atius.com.br"

        # Hosts excluidos -> geram ValueError
        with pytest.raises(ValueError, match="explicitly excluded"):
            _exec_host_cmd("horistic-srv", "ls")

        with pytest.raises(ValueError, match="explicitly excluded"):
            _exec_host_cmd("aln-srv", "ls")


def test_get_host_quota_whitespace_handling():
    """Valida que get_host_quota tolera espacos ao redor do hostname."""
    size, age = get_host_quota("  atius-srv-1  ")
    assert size == "5G"
    assert age == "12h"

