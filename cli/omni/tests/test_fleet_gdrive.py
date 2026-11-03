r"""Unit and TDD tests for Fleet Google Drive storage mount automation.

Covering the 6 Architecture Pillars:
1. Forbidden host rejection (aln-srv and horistic-srv)
2. Allowed hosts allowlist (atius-srv-1, atius-srv-2, atius-srv-3, giovanni-w11-pc)
3. 3-tier connectivity fallback (DNS -> DRG IP -> Public IP)
4. Concurrency lock (/run/lock/omni-gdrive.lock)
5. Vault rclone config generation & dual schema parsing ([gdrive-main] & [giovanni-drive])
6. Host cache quotas (SRV-1 5G, SRV-2 10G, SRV-3 5G) & CPUQuota=20%
Plus Windows 11 native Google Drive (G:\) handling.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
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
    DEFAULT_LOCK_PATH,
    DEFAULT_MOUNTPOINT,
    ALLOWED_HOSTS,
    FLEET_HOSTS,
    FORBIDDEN_HOSTS,
    HOST_CACHE_QUOTAS,
    OCI_DRG_IPS,
    PUBLIC_FALLBACK_IPS,
    GDriveLock,
    _exec_host_cmd,
    build_rclone_conf_content,
    gdrive,
    get_host_quota,
    parse_rclone_conf_content,
    render_systemd_unit,
    validate_host,
)
from omni.landscape import _load_manifest


# ═══════════════════════════════════════════════════════════════
# Pillar 1 & 2: Host Guardrails & Strict Allowlist
# ═══════════════════════════════════════════════════════════════

def test_forbidden_hosts_rejected():
    """Valida rejeicao imediata de aln-srv e horistic-srv com ValueError."""
    forbidden = ["aln-srv", "horistic-srv", "aln-srv.atius.internal", "horistic-srv.atius.internal"]
    for h in forbidden:
        with pytest.raises(ValueError, match="explicitly excluded"):
            validate_host(h)

        with pytest.raises(ValueError, match="explicitly excluded"):
            render_systemd_unit(h)

        with pytest.raises(ValueError, match="explicitly excluded"):
            _exec_host_cmd(h, "ls")


def test_allowed_hosts_allowlist():
    """Valida que FLEET_HOSTS e ALLOWED_HOSTS contem estritamente a frota autorizada."""
    expected = {"atius-srv-1", "atius-srv-2", "atius-srv-3", "giovanni-w11-pc"}
    assert ALLOWED_HOSTS == expected
    assert set(FLEET_HOSTS) == expected
    assert "horistic-srv" not in FLEET_HOSTS
    assert "aln-srv" not in FLEET_HOSTS
    assert "horistic-srv" in FORBIDDEN_HOSTS
    assert "aln-srv" in FORBIDDEN_HOSTS


def test_validate_host_success():
    """Valida que hosts autorizados passam pela validacao normalizados."""
    assert validate_host("atius-srv-1") == "atius-srv-1"
    assert validate_host("atius-srv-1.atius.internal") == "atius-srv-1"
    assert validate_host("  atius-srv-2  ") == "atius-srv-2"
    assert validate_host("giovanni-w11-pc") == "giovanni-w11-pc"


# ═══════════════════════════════════════════════════════════════
# Pillar 3: 3-Tier Connectivity Fallback
# ═══════════════════════════════════════════════════════════════

def test_connectivity_fallback_tier1_to_tier2():
    """Valida fallback de Tier 1 (DNS *.atius.internal) para Tier 2 (DRG IP) em caso de falha."""
    with patch("subprocess.run") as mock_run:
        # 1ª chamada (DNS) falha com retorno 255 (transporte SSH)
        # 2ª chamada (DRG IP) tem sucesso com retorno 0
        call1 = MagicMock(returncode=255, stdout="", stderr="Could not resolve hostname")
        call2 = MagicMock(returncode=0, stdout="tier2_success", stderr="")
        mock_run.side_effect = [call1, call2]

        rc, out, err = _exec_host_cmd("atius-srv-1", "echo ok")
        assert rc == 0
        assert out == "tier2_success"
        assert mock_run.call_count == 2
        # Verifica que 1ª chamada tentou internal DNS e 2ª tentou DRG IP
        assert mock_run.call_args_list[0][0][0][6] == "ubuntu@atius-srv-1.atius.internal"
        assert mock_run.call_args_list[1][0][0][6] == f"ubuntu@{OCI_DRG_IPS['atius-srv-1']}"


def test_connectivity_fallback_tier1_tier2_to_tier3():
    """Valida fallback atraves de todos os 3 niveis alcancando o IP publico em Tier 3."""
    with patch("subprocess.run") as mock_run:
        call1 = MagicMock(returncode=255, stdout="", stderr="DNS timeout")
        call2 = MagicMock(returncode=255, stdout="", stderr="DRG route unreachable")
        call3 = MagicMock(returncode=0, stdout="tier3_public_ok", stderr="")
        mock_run.side_effect = [call1, call2, call3]

        rc, out, err = _exec_host_cmd("atius-srv-1", "echo ok")
        assert rc == 0
        assert out == "tier3_public_ok"
        assert mock_run.call_count == 3
        assert mock_run.call_args_list[2][0][0][6] == f"ubuntu@{PUBLIC_FALLBACK_IPS['atius-srv-1']}"


def test_connectivity_all_tiers_failed():
    """Valida retorno gracioso de erro quando todos os 3 niveis de conexao falham."""
    with patch("subprocess.run") as mock_run:
        call1 = MagicMock(returncode=255, stdout="", stderr="DNS fail")
        call2 = MagicMock(returncode=255, stdout="", stderr="DRG fail")
        call3 = MagicMock(returncode=255, stdout="", stderr="Public fail")
        mock_run.side_effect = [call1, call2, call3]

        rc, out, err = _exec_host_cmd("atius-srv-1", "echo ok")
        assert rc == 255
        assert "Falha" in err or "fail" in err


# ═══════════════════════════════════════════════════════════════
# Pillar 4: Concurrency Lock Management
# ═══════════════════════════════════════════════════════════════

def test_concurrency_lock_lifecycle(tmp_path: Path):
    """Valida aquisicao, colisao, recuperacao de stale lock e liberacao de GDriveLock."""
    lock_file = tmp_path / "omni-gdrive.lock"
    lock1 = GDriveLock(lock_path=str(lock_file), timeout_seconds=60)
    assert lock1.acquire() is True
    assert lock1.is_active is True
    assert lock_file.exists()

    # Segunda tentativa de aquisicao concorrente deve falhar
    lock2 = GDriveLock(lock_path=str(lock_file), timeout_seconds=60)
    assert lock2.acquire() is False

    # Liberacao do primeiro lock
    lock1.release()
    assert lock1.is_active is False
    assert not lock_file.exists()

    # Aquisicao pelo segundo lock agora tem sucesso
    assert lock2.acquire() is True
    lock2.release()


def test_concurrency_lock_stale_recovery(tmp_path: Path):
    """Valida recuperacao automatica caso exista um lockfile expirado (stale)."""
    lock_file = tmp_path / "omni-gdrive.lock"
    stale_payload = {
        "pid": 99999,
        "acquired_at": time.time() - 300,
        "expires_at": time.time() - 60,  # Expirado ha 60s
    }
    lock_file.write_text(json.dumps(stale_payload), encoding="utf-8")

    # Novo lock deve detectar expiração e sobrescrever
    fresh_lock = GDriveLock(lock_path=str(lock_file), timeout_seconds=30)
    assert fresh_lock.acquire() is True
    fresh_lock.release()


def test_concurrency_lock_context_manager(tmp_path: Path):
    """Valida suporte a context manager with GDriveLock()."""
    lock_file = tmp_path / "omni-gdrive.lock"
    with GDriveLock(lock_path=str(lock_file), timeout_seconds=60) as lk:
        assert lk.is_active is True
        assert lock_file.exists()
    assert not lock_file.exists()


# ═══════════════════════════════════════════════════════════════
# Pillar 5: Vault rclone config & Dual Schema Parsing
# ═══════════════════════════════════════════════════════════════

def test_build_and_parse_rclone_conf():
    """Valida geracao segura e parsing de rclone.conf."""
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
    assert f'"refresh_token":"{refresh_token}"' in conf

    # Parsing e validacao de contrato INI
    parsed = parse_rclone_conf_content(conf)
    assert "gdrive-main" in parsed
    assert parsed["gdrive-main"]["type"] == "drive"
    assert parsed["gdrive-main"]["client_id"] == client_id


def test_parse_rclone_conf_dual_schema():
    """Valida parsing de ambas as secoes [gdrive-main] e [giovanni-drive]."""
    dual_conf = """[gdrive-main]
type = drive
client_id = id_omni
client_secret = sec_omni
token = {"refresh_token":"token_omni"}

[giovanni-drive]
type = drive
client_id = id_backup
client_secret = sec_backup
token = {"refresh_token":"token_backup"}
"""
    parsed = parse_rclone_conf_content(dual_conf)
    assert "gdrive-main" in parsed
    assert "giovanni-drive" in parsed
    assert parsed["gdrive-main"]["client_id"] == "id_omni"
    assert parsed["giovanni-drive"]["client_id"] == "id_backup"


def test_parse_rclone_conf_invalid():
    """Rejeita configuracao sem drive type ou secao invalida."""
    invalid_conf = """[bad-drive]
type = s3
client_id = xxx
"""
    with pytest.raises(ValueError, match="nao eh do tipo drive"):
        parse_rclone_conf_content(invalid_conf)

    with pytest.raises(ValueError, match="Nenhuma secao valida"):
        parse_rclone_conf_content("")


def test_build_rclone_conf_validation():
    """Rejeita valores vazios para evitar configuracao quebrada."""
    with pytest.raises(ValueError, match="client_id obrigatorio"):
        build_rclone_conf_content("", "secret", "token")

    with pytest.raises(ValueError, match="client_secret obrigatorio"):
        build_rclone_conf_content("id", "", "token")

    with pytest.raises(ValueError, match="refresh_token obrigatorio"):
        build_rclone_conf_content("id", "secret", "")


# ═══════════════════════════════════════════════════════════════
# Pillar 6: Host Cache Quotas & CPU 20% Governance
# ═══════════════════════════════════════════════════════════════

def test_host_cache_quotas():
    """Valida as quotas de cache VFS estritas por host (SRV-1 5G, SRV-2 10G, SRV-3 5G)."""
    assert HOST_CACHE_QUOTAS["atius-srv-1"] == ("5G", "12h")
    assert HOST_CACHE_QUOTAS["atius-srv-2"] == ("10G", "24h")
    assert HOST_CACHE_QUOTAS["atius-srv-3"] == ("5G", "12h")
    assert HOST_CACHE_QUOTAS["atius-srv-4"] == ("30G", "48h")
    assert "horistic-srv" not in HOST_CACHE_QUOTAS

    # Host desconhecido recebe cota conservadora default
    size, age = get_host_quota("unknown-host-x")
    assert size == "4G"
    assert age == "12h"

    # Host conhecido
    size_srv1, age_srv1 = get_host_quota("atius-srv-1")
    assert size_srv1 == "5G"
    assert age_srv1 == "12h"


def test_render_systemd_unit():
    """Valida renderizacao do systemd unit com CPUQuota=20% e quotas alinhadas."""
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


# ═══════════════════════════════════════════════════════════════
# Windows 11 Native Handling (G:\)
# ═══════════════════════════════════════════════════════════════

def test_windows_11_gdrive_handling():
    r"""Valida deteccao e suporte a Google Drive nativo G:\ no Windows 11."""
    with patch("pathlib.Path.exists", return_value=True), patch("os.path.exists", return_value=True):
        rc, stdout, stderr = _exec_host_cmd("giovanni-w11-pc", "mountpoint -q /mnt/gdrive && stat")
        assert rc == 0
        assert stdout == "OK"

        rc_stat, out_stat, _ = _exec_host_cmd("giovanni-w11-pc", "SVC=$(systemctl is-active)")
        assert rc_stat == 0
        assert "active" in out_stat
        assert "mounted" in out_stat

    with patch("pathlib.Path.exists", return_value=False), patch("os.path.exists", return_value=False):
        rc_fail, out_fail, err_fail = _exec_host_cmd("giovanni-w11-pc", "mountpoint -q /mnt/gdrive && stat")
        assert out_fail == "NOT_MOUNTED" or rc_fail != 0


# ═══════════════════════════════════════════════════════════════
# CLI Click Tests
# ═══════════════════════════════════════════════════════════════

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


def test_get_host_quota_whitespace_handling():
    """Valida que get_host_quota tolera espacos ao redor do hostname."""
    size, age = get_host_quota("  atius-srv-1  ")
    assert size == "5G"
    assert age == "12h"

    # Host desconhecido ou removido recebe default
    size_h, age_h = get_host_quota("  horistic-srv \n")
    assert size_h == "4G"
    assert age_h == "12h"
