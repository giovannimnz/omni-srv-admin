"""Unit and integration tests for Omni Landscape control-plane module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from omni.landscape import (
    CONTROLLED_HOSTS,
    DEFAULT_ENDPOINT,
    LandscapeClient,
    LandscapeError,
    _find_script,
    _host_query,
    _load_manifest,
    _script_specs,
    landscape,
)


def test_controlled_hosts_definition():
    """Valida a lista canônica dos 5 servidores administrados."""
    assert len(CONTROLLED_HOSTS) == 5
    assert "atius-srv-1" in CONTROLLED_HOSTS
    assert "atius-srv-2" in CONTROLLED_HOSTS
    assert "atius-srv-3" in CONTROLLED_HOSTS
    assert "atius-srv-4" in CONTROLLED_HOSTS
    assert "horistic-srv" in CONTROLLED_HOSTS


def test_host_query_syntax():
    """Valida que queries do Landscape usam title:{host} sem parenteses."""
    # Query para todos
    all_query = _host_query("all")
    assert not all_query.startswith("(")
    assert not all_query.endswith(")")
    assert "title:atius-srv-1" in all_query
    assert "title:horistic-srv" in all_query
    assert " OR " in all_query

    # Query para host especifico
    single_query = _host_query("atius-srv-2")
    assert single_query == "title:atius-srv-2"

    # Query customizada sobrepoe hosts
    custom_query = _host_query("all", query="tag:g18")
    assert custom_query == "tag:g18"


def test_manifest_and_scripts_loading():
    """Valida que o manifest de scripts existe e tem estrutura correta."""
    manifest = _load_manifest()
    assert "scripts" in manifest
    assert isinstance(manifest["scripts"], list)
    assert len(manifest["scripts"]) >= 5

    specs = _script_specs()
    assert len(specs) >= 5
    ids = [s.script_id for s in specs]
    assert "reboot-required" in ids
    assert "fleet-status" in ids

    reboot_spec = _find_script("reboot-required")
    assert reboot_spec.title == "omni::reboot-required"
    assert reboot_spec.sha256 is not None
    assert len(reboot_spec.code) > 0


def test_landscape_client_headers_contain_user_agent():
    """Valida que o User-Agent e injetado para Cloudflare WAF bypass."""
    client = LandscapeClient(endpoint=DEFAULT_ENDPOINT, access_key="test_key", secret_key="test_secret")
    
    with patch("omni.landscape.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client._request_json("GET", "https://landscape.atius.io/api/")
        
        req = mock_urlopen.call_args[0][0]
        assert "omni-cli/1.0 (Atius Fleet Landscape Client)" in req.headers.get("User-agent")


def test_cli_status_command():
    """Valida que 'omni landscape status' roda sem erros."""
    runner = CliRunner()
    result = runner.invoke(landscape, ["status"])
    assert result.exit_code == 0
    assert "manifest:" in result.output
    assert "atius-srv-1" in result.output
    assert "horistic-srv" in result.output


def test_cli_run_plan_only():
    """Valida que 'omni landscape run' sem --yes opera em modo plan-only."""
    runner = CliRunner()
    with patch("omni.landscape._remote_scripts_by_title") as mock_remote:
        mock_remote.return_value = {"omni::reboot-required": {"id": 42}}
        result = runner.invoke(landscape, ["run", "reboot-required", "--hosts", "atius-srv-1"])
        assert result.exit_code == 0
        assert "plan-only: use --yes para executar no Landscape" in result.output
        assert '"action": "ExecuteScript"' in result.output
