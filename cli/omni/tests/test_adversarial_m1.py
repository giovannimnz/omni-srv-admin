"""Adversarial stress harness for omni gdrive CLI and fleet Google Drive mount module.

Author: Challenger 1 (Adversarial CLI & FUSE Verifier)
Purpose: Stress-test assumptions, input validation, corrupted outputs, and edge cases.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
REPO_CLI = REPO / "cli"
if str(REPO_CLI) not in sys.path:
    sys.path.insert(0, str(REPO_CLI))

import pytest
from click.testing import CliRunner

from omni.gdrive import (
    DEFAULT_CACHE_DIR,
    DEFAULT_MOUNTPOINT,
    DEFAULT_QUOTA,
    HOST_CACHE_QUOTAS,
    get_host_quota,
    render_systemd_unit,
    build_rclone_conf_content,
    gdrive,
)


class TestHostQuotaAdversarial:
    """Stress-testing get_host_quota against invalid, malformed, and edge-case inputs."""

    @pytest.mark.parametrize(
        "hostname,expected_size,expected_age",
        [
            ("atius-srv-1", "3G", "6h"),
            ("ATIUS-SRV-1", "3G", "6h"),
            ("AtIuS-SrV-1", "3G", "6h"),
            ("atius-srv-1.internal", "3G", "6h"),
            ("atius-srv-1.atius.internal", "3G", "6h"),
            ("ATIUS-SRV-1.ATIUS.COM.BR", "3G", "6h"),
            ("atius-srv-2", "10G", "24h"),
            ("ATIUS-SRV-2.local", "10G", "24h"),
            ("atius-srv-3", "5G", "12h"),
            ("atius-srv-3.any.sub.domain.corp", "5G", "12h"),
            ("atius-srv-4", "30G", "48h"),
            ("ATIUS-SRV-4.internal", "30G", "48h"),
            ("horistic-srv", "10G", "24h"),
            ("HORISTIC-SRV", "10G", "24h"),
            ("HoRiStIc-SrV.atius.internal", "10G", "24h"),
        ],
    )
    def test_canonical_and_case_insensitive_hosts(
        self, hostname: str, expected_size: str, expected_age: str
    ):
        size, age = get_host_quota(hostname)
        assert size == expected_size
        assert age == expected_age

    @pytest.mark.parametrize(
        "unknown_or_alias",
        [
            "unknown-host",
            "nonexistent-srv-99",
            "random.subdomain.org",
            "srv-1",
            "srv1",
            "srv-2",
            "srv2",
            "srv-3",
            "srv4",
            "horistic",  # without -srv suffix
            "horistic-1",
            "",
            "...",
            "127.0.0.1",
            "10.13.1.13",
        ],
    )
    def test_unknown_and_alias_fallback_to_default(self, unknown_or_alias: str):
        """Unknown hostnames or unmapped aliases must safely fall back to 4G/12h."""
        size, age = get_host_quota(unknown_or_alias)
        assert size == DEFAULT_QUOTA[0]
        assert age == DEFAULT_QUOTA[1]


class TestBuildRcloneConfAdversarial:
    """Stress-testing build_rclone_conf_content with corrupted, empty, or malicious strings."""

    @pytest.mark.parametrize(
        "client_id,client_secret,refresh_token,err_match",
        [
            ("", "secret", "token", "client_id obrigatorio"),
            ("   ", "secret", "token", "client_id obrigatorio"),
            ("\t\n", "secret", "token", "client_id obrigatorio"),
            ("id", "", "token", "client_secret obrigatorio"),
            ("id", "   ", "token", "client_secret obrigatorio"),
            ("id", "secret", "", "refresh_token obrigatorio"),
            ("id", "secret", "   ", "refresh_token obrigatorio"),
        ],
    )
    def test_rejects_empty_and_whitespace_only(
        self, client_id: str, client_secret: str, refresh_token: str, err_match: str
    ):
        with pytest.raises(ValueError, match=err_match):
            build_rclone_conf_content(client_id, client_secret, refresh_token)

    def test_token_with_quotes_and_special_json_chars(self):
        """Refresh token with characters that need JSON escaping must remain valid parseable JSON."""
        tricky_token = '1//special"token/with\\escapes\nand\ttabs{"nested": true}'
        conf = build_rclone_conf_content("id-123", "sec-456", tricky_token)

        # Extract token line
        token_line = next(line for line in conf.splitlines() if line.startswith("token = "))
        raw_json = token_line.split("token = ", 1)[1]

        # Must parse as 100% valid JSON
        parsed = json.loads(raw_json)
        assert parsed["refresh_token"] == tricky_token
        assert parsed["token_type"] == "Bearer"
        assert parsed["access_token"] == ""
        # Compact serialization check: no space after separators
        assert '","' in raw_json or '":"' in raw_json
        assert '": "' not in raw_json
        assert '", "' not in raw_json


class TestRenderSystemdUnitAdversarial:
    """Stress-testing systemd unit generation for safety invariants."""

    @pytest.mark.parametrize(
        "host,expected_quota",
        [
            ("atius-srv-1", "3G"),
            ("ATIUS-SRV-2", "10G"),
            ("atius-srv-3.atius.internal", "5G"),
            ("atius-srv-4", "30G"),
            ("horistic-srv", "10G"),
            ("ghost-host", "4G"),
        ],
    )
    def test_quota_propagation(self, host: str, expected_quota: str):
        unit = render_systemd_unit(host)
        assert f"--vfs-cache-max-size {expected_quota}" in unit
        assert "AssertPathIsDirectory=/mnt/gdrive" in unit
        assert "ExecStop=/bin/fusermount -u -z /mnt/gdrive" in unit
        assert "CPUQuota=80%" in unit
        assert "Nice=10" in unit
        assert "TimeoutStopSec=30s" in unit


class TestCliAdversarialAndMalformedOutputs:
    """Stress-testing CLI subcommands against malformed outputs, errors, and invalid options."""

    def test_quotas_json_schema_validity(self):
        runner = CliRunner()
        result = runner.invoke(gdrive, ["quotas", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)

        assert "quotas" in data
        assert "default" in data
        assert "mountpoint" in data
        assert "cache_dir" in data

        for host in ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4", "horistic-srv"]:
            assert host in data["quotas"]
            assert "max_size" in data["quotas"][host]
            assert "max_age" in data["quotas"][host]

    @pytest.mark.parametrize(
        "args,expected_exit",
        [
            (["quotas", "--nonexistent-flag"], 2),
            (["status", "--nonexistent-flag"], 2),
            (["mount", "--nonexistent-flag"], 2),
            (["unmount", "--nonexistent-flag"], 2),
            (["test", "--nonexistent-flag"], 2),
            (["doctor", "--nonexistent-flag"], 2),
            (["check", "--nonexistent-flag"], 2),
            (["health", "--nonexistent-flag"], 2),
            (["list", "--nonexistent-flag"], 2),
            (["bogus_subcommand"], 2),
        ],
    )
    def test_cli_unrecognized_arguments_exit_code_2(self, args: list[str], expected_exit: int):
        runner = CliRunner()
        result = runner.invoke(gdrive, args)
        assert result.exit_code == expected_exit

    def test_status_malformed_stdout_handling(self):
        """When remote probe returns garbage stdout, status must report error and exit code 1."""
        runner = CliRunner()
        with patch("omni.gdrive._exec_host_cmd", return_value=(0, "GARBAGE_NO_PIPES", "")):
            result = runner.invoke(gdrive, ["status", "--host", "atius-srv-1", "--json"])
            # Inactive or error
            assert result.exit_code in (1, 2)
            data = json.loads(result.output)
            assert data["hosts"][0]["mount"] == "unknown"

    def test_doctor_handles_malformed_json_gracefully(self):
        """When remote doctor emits invalid JSON (e.g. bash error trace), doctor must not crash."""
        runner = CliRunner()
        with patch("omni.gdrive._exec_host_cmd", return_value=(0, "bash: syntax error near unexpected token", "stderr info")):
            result = runner.invoke(gdrive, ["doctor", "--host", "atius-srv-1", "--json"])
            assert result.exit_code == 1
            data = json.loads(result.output)
            assert data["status"] == "FAIL"
            assert data["results"][0]["doctor"]["status"] == "FAIL"

    def test_test_cmd_hash_mismatch_failure(self):
        """When probe script returns HASH_MISMATCH, test command must exit with code 1."""
        runner = CliRunner()
        with patch("omni.gdrive._exec_host_cmd", return_value=(1, "HASH_MISMATCH", "")):
            result = runner.invoke(gdrive, ["test", "--host", "atius-srv-1", "--json"])
            assert result.exit_code == 1
            data = json.loads(result.output)
            assert data["status"] == "FAIL"
            assert data["results"][0]["result"] == "HASH_MISMATCH"

    def test_check_cmd_timeout_handling(self):
        """When check probe times out or errors, exit code must be 1."""
        runner = CliRunner()
        with patch("omni.gdrive._exec_host_cmd", return_value=(124, "", "Timeout connecting")):
            result = runner.invoke(gdrive, ["check", "--host", "atius-srv-1", "--json"])
            assert result.exit_code == 1
            data = json.loads(result.output)
            assert data["status"] == "FAIL"
            assert data["results"][0]["status"] == "error"

    def test_mount_cmd_remote_failure(self):
        """When mount command fails remotely, exit code must be 1."""
        runner = CliRunner()
        with patch("omni.gdrive._exec_host_cmd", return_value=(1, "inactive|not-mounted", "Systemd error")):
            result = runner.invoke(gdrive, ["mount", "--host", "atius-srv-1", "--json"])
            assert result.exit_code == 1
            data = json.loads(result.output)
            assert data["status"] == "FAIL"
            assert data["results"][0]["success"] is False

    def test_unmount_cmd_still_mounted_failure(self):
        """When unmount command fails to unmount (device busy), exit code must be 1."""
        runner = CliRunner()
        with patch("omni.gdrive._exec_host_cmd", return_value=(0, "still-mounted", "")):
            result = runner.invoke(gdrive, ["unmount", "--host", "atius-srv-1", "--json"])
            assert result.exit_code == 1
            data = json.loads(result.output)
            assert data["status"] == "FAIL"
            assert data["results"][0]["unmounted"] is False
