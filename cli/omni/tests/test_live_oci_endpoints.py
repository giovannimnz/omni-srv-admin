"""Live Integration Test for oci.atius.io and oci.atius.com.br endpoints.

Performs real HTTPS requests to ensure:
- DNS resolves for both domains.
- HTTPS connection succeeds with valid TLS.
- Redirections from root / go to /sso.
- /login returns 200 OK with the Atius SSO UI.
- Both endpoints exhibit identical routing behavior.
"""

from __future__ import annotations

import urllib.request
import urllib.parse
import ssl
import pytest

ENDPOINTS = [
    "https://oci.atius.com.br",
    "https://oci.atius.io",
]


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not follow redirect automatically


@pytest.mark.parametrize("base_url", ENDPOINTS)
def test_live_root_redirects_to_sso(base_url: str) -> None:
    opener = urllib.request.build_opener(NoRedirectHandler)
    req = urllib.request.Request(f"{base_url}/", headers={"User-Agent": "Mozilla/5.0 (OmniFleetHealthCheck)"})
    try:
        resp = opener.open(req, timeout=10)
        status = resp.status
        location = resp.headers.get("Location")
    except urllib.error.HTTPError as e:
        status = e.code
        location = e.headers.get("Location")

    assert status == 303, f"Expected 303 See Other on {base_url}/, got {status}"
    assert location == "/sso", f"Expected Location /sso on {base_url}/, got {location}"


@pytest.mark.parametrize("base_url", ENDPOINTS)
def test_live_login_surface_returns_200_ok(base_url: str) -> None:
    req = urllib.request.Request(f"{base_url}/login", headers={"User-Agent": "Mozilla/5.0 (OmniFleetHealthCheck)"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200 OK on {base_url}/login, got {resp.status}"
        body = resp.read().decode("utf-8", errors="ignore")
        assert "Atius" in body or "SSO" in body or "login" in body.lower()
