"""Tests for the Cloudflare-Access-aware edge client (Phase 16 / M005).

Run with: ``pytest cli/omni/tests/test_edge.py`` from the repo root.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path

import pytest


# Make the omni package importable when running pytest from the repo root.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omni import edge  # noqa: E402


@pytest.fixture
def isolated_token_file(tmp_path, monkeypatch):
    """Point the module at a temp file and clean up env vars."""
    token = tmp_path / "cloudflare-service-token.json"
    monkeypatch.setattr(edge, "SERVICE_TOKEN_FILE", token)
    monkeypatch.delenv(edge.LEGACY_BASIC_AUTH_ENV_USER, raising=False)
    monkeypatch.delenv(edge.LEGACY_BASIC_AUTH_ENV_PASS, raising=False)
    return token


def test_admin_edges_known() -> None:
    assert edge.ADMIN_EDGES["portainer"] == "https://portainer.atius.com.br"
    assert edge.ADMIN_EDGES["docker"] == "https://docker.atius.com.br"


def test_edge_url_lookup() -> None:
    assert edge.edge_url("portainer") == "https://portainer.atius.com.br"
    assert edge.edge_url("docker") == "https://docker.atius.com.br"
    assert edge.edge_url("nope") is None


def test_token_file_absent_by_default(isolated_token_file) -> None:
    assert not edge.cf_service_token_exists()
    assert edge.load_cf_service_token() is None
    assert edge.cf_service_auth_headers() == {}


def test_write_creates_0600(isolated_token_file) -> None:
    p = edge.write_cf_service_token("abc.def", "secret-123")
    assert p == isolated_token_file
    st = isolated_token_file.stat()
    assert st.st_mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR
    payload = json.loads(isolated_token_file.read_text())
    assert payload["client_id"] == "abc.def"
    assert payload["client_secret"] == "secret-123"


def test_round_trip(isolated_token_file) -> None:
    edge.write_cf_service_token("abc.def", "secret-123")
    token = edge.load_cf_service_token()
    assert token is not None
    assert token["client_id"] == "abc.def"
    headers = edge.cf_service_auth_headers()
    assert headers == {
        edge.CF_ACCESS_HEADER_CLIENT_ID: "abc.def",
        edge.CF_ACCESS_HEADER_CLIENT_SECRET: "secret-123",
    }


def test_rotate_keeps_backup(isolated_token_file) -> None:
    edge.write_cf_service_token("v1.client", "v1.secret")
    edge.rotate_cf_service_token("v2.client", "v2.secret")
    backup = isolated_token_file.with_suffix(isolated_token_file.suffix + ".bak")
    assert backup.is_file()
    payload = json.loads(backup.read_text())
    assert payload["client_id"] == "v1.client"
    current = json.loads(isolated_token_file.read_text())
    assert current["client_id"] == "v2.client"


def test_resolve_auto_prefers_token(isolated_token_file, monkeypatch) -> None:
    monkeypatch.setenv(edge.LEGACY_BASIC_AUTH_ENV_USER, "admin")
    monkeypatch.setenv(edge.LEGACY_BASIC_AUTH_ENV_PASS, "secret")
    edge.write_cf_service_token("svc.id", "svc.secret")
    headers, label = edge.resolve_edge_auth("auto")
    assert label == "cf-service-token"
    assert headers[edge.CF_ACCESS_HEADER_CLIENT_ID] == "svc.id"


def test_resolve_auto_falls_back_to_basic(isolated_token_file, monkeypatch) -> None:
    monkeypatch.setenv(edge.LEGACY_BASIC_AUTH_ENV_USER, "admin")
    monkeypatch.setenv(edge.LEGACY_BASIC_AUTH_ENV_PASS, "secret")
    headers, label = edge.resolve_edge_auth("auto")
    assert label == "basic-auth"
    assert headers["Authorization"].startswith("Basic ")
    decoded = base64.b64decode(headers["Authorization"].split(" ", 1)[1]).decode()
    assert decoded == "admin:secret"


def test_resolve_basic_force(isolated_token_file, monkeypatch) -> None:
    monkeypatch.setenv(edge.LEGACY_BASIC_AUTH_ENV_USER, "admin")
    monkeypatch.setenv(edge.LEGACY_BASIC_AUTH_ENV_PASS, "secret")
    edge.write_cf_service_token("svc.id", "svc.secret")
    headers, label = edge.resolve_edge_auth("basic")
    # Even with a token present, --prefer basic uses env vars.
    assert label == "basic-auth"
    assert headers["Authorization"].startswith("Basic ")


def test_resolve_service_token_force_missing(isolated_token_file) -> None:
    headers, label = edge.resolve_edge_auth("service-token")
    assert label == "missing-service-token"
    assert headers == {}


def test_resolve_unknown_prefer(isolated_token_file) -> None:
    # Unknown values fall through to auto, just like in Click.
    headers, label = edge.resolve_edge_auth("banana")
    assert label == "none"
    assert headers == {}


def test_describe_auth_redacts_secrets(isolated_token_file, monkeypatch) -> None:
    monkeypatch.setenv(edge.LEGACY_BASIC_AUTH_ENV_USER, "admin")
    monkeypatch.setenv(edge.LEGACY_BASIC_AUTH_ENV_PASS, "sensitive")
    edge.write_cf_service_token("svc.id", "svc.secret")
    info = edge.describe_auth()
    # File-level metadata only — never the secret itself.
    assert info["service_token_present"] is True
    assert info["service_token_octal_mode"] == "0o600"
    assert info["basic_auth_user_set"] is True
    assert info["basic_auth_pass_set"] is True
    assert "svc.secret" not in json.dumps(info)
    assert "sensitive" not in json.dumps(info)


def test_malformed_token_returns_none(isolated_token_file) -> None:
    isolated_token_file.write_text("not json at all")
    assert edge.load_cf_service_token() is None
    assert edge.cf_service_auth_headers() == {}


def test_partial_token_returns_none(isolated_token_file) -> None:
    isolated_token_file.write_text(json.dumps({"client_id": "only.id"}))
    assert edge.load_cf_service_token() is None


def test_edge_check_uses_get_with_real_ua(isolated_token_file, monkeypatch) -> None:
    """``omni edge check`` should GET with a browser UA, not HEAD with the bare urllib UA.

    Cloudflare's WAF blocks the default ``Python-urllib/3.x`` UA, so
    the test verifies (a) the method is GET, (b) the User-Agent
    header is the real-browser one — even when no other auth header
    is set.
    """
    import urllib.request

    captured: dict = {}

    class _FakeResp:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, *a, **kw):
            return b""

    def fake_urlopen(req, timeout=10):  # noqa: ARG001
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.headers)
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(edge.edge, ["check", "--edge-name", "portainer"])
    assert result.exit_code == 0, result.output
    assert captured["method"] == "GET"
    ua = captured["headers"].get("User-agent") or captured["headers"].get("User-Agent")
    assert ua and ua.startswith("Mozilla/5.0"), ua


def test_edge_check_unknown_edge(isolated_token_file) -> None:
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(edge.edge, ["check", "--edge-name", "nope"])
    assert result.exit_code != 0
    assert "admin edge desconhecido" in result.output
