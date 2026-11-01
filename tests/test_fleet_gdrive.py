"""Unit and TDD tests for Fleet Google Drive storage mount automation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    assert HOST_CACHE_QUOTAS["atius-srv-1"] == ("3G", "6h")
    assert HOST_CACHE_QUOTAS["atius-srv-2"] == ("10G", "24h")
    assert HOST_CACHE_QUOTAS["atius-srv-3"] == ("5G", "12h")
    assert HOST_CACHE_QUOTAS["atius-srv-4"] == ("30G", "48h")
    assert HOST_CACHE_QUOTAS["horistic-srv"] == ("10G", "24h")

    # Host desconhecido recebe cota conservadora default
    size, age = get_host_quota("unknown-host-x")
    assert size == "4G"
    assert age == "12h"

    # Host conhecido
    size_srv1, age_srv1 = get_host_quota("atius-srv-1")
    assert size_srv1 == "3G"
    assert age_srv1 == "6h"


def test_render_systemd_unit():
    """Valida renderizacao do systemd unit rclone-gdrive.service."""
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
    assert "--vfs-cache-max-size 3G" in unit
    assert "--vfs-cache-max-age 6h" in unit
    assert "--config /run/rclone/rclone.conf" in unit
    assert "--allow-other" in unit
    assert "ExecStop=/bin/fusermount -u -z /mnt/gdrive" in unit
    assert "Restart=on-failure" in unit or "Restart=always" in unit
    assert "KillMode=mixed" in unit


def test_build_rclone_conf_content():
    """Valida geracao segura de rclone.conf a partir de credenciais Vault."""
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
    assert f'"refresh_token": "{refresh_token}"' in conf
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
    """Valida estrutura do CLI omni gdrive."""
    runner = CliRunner()
    result = runner.invoke(gdrive, ["--help"])
    assert result.exit_code == 0
    assert "status" in result.output
    assert "mount" in result.output
    assert "unmount" in result.output
    assert "health" in result.output
    assert "quotas" in result.output


def test_gdrive_cli_quotas():
    """Valida comando omni gdrive quotas."""
    runner = CliRunner()
    result = runner.invoke(gdrive, ["quotas"])
    assert result.exit_code == 0
    assert "atius-srv-1" in result.output
    assert "3G" in result.output
    assert "atius-srv-4" in result.output
    assert "30G" in result.output


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
