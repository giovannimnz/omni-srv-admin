#!/usr/bin/env python3
"""Live validation script for Phase 16 / M005 Cloudflare Access cutover.

This script is the **gating** validation: it probes the actual admin
edges and produces a clear pass/fail per the table documented in
``docs/operations/edge-auth.md``.

It does NOT mutate anything — it only issues HEAD requests. It is safe
to run in any environment.

Usage::

    python3 scripts/validate-edge-auth.py
    python3 scripts/validate-edge-auth.py --expect access-live
    python3 scripts/validate-edge-auth.py --expect basic-only

Exit code 0 = all expected checks pass; 1 = mismatch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Make omni package importable when run from anywhere.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "cli"))

from omni import edge  # noqa: E402


_REAL_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def get_or_head(url: str, headers: dict[str, str] | None = None, timeout: int = 10) -> tuple[int, dict[str, str], bytes]:
    """Issue a GET request, return (status_code, response_headers, body).

    HEAD is intentionally avoided — Cloudflare often returns 403 on
    HEAD against admin edges (anti-bot). GET is the canonical probe.
    The body is read but not used in validation; a 401 page is ~470
    bytes which is well within reason.

    A normal-looking User-Agent is sent by default; Cloudflare's WAF
    returns 403 to the bare ``Python-urllib/3.x`` UA. Callers may
    override ``User-Agent`` via ``headers``.
    """
    merged = {"User-Agent": _REAL_UA}
    if headers:
        merged.update(headers)
    req = urllib.request.Request(url, method="GET", headers=merged)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - admin edge only
            return resp.status, dict(resp.headers), resp.read(2048)
    except urllib.error.HTTPError as e:
        # On 401/403/etc urllib raises HTTPError; capture the response too.
        body = b""
        try:
            body = e.read(2048)
        except Exception:
            pass
        return e.code, dict(e.headers or {}), body


def looks_like_basic_challenge(headers: dict[str, str], body: bytes = b"") -> bool:
    """True when the response advertises WWW-Authenticate: Basic realm=ATIUS Admin.

    The Cloudflare WAF sometimes strips the ``WWW-Authenticate`` header
    from responses to challenged clients (seen 2026-06-18: ~60% of
    requests from this script lose the header, even though the origin
    always sends it). As a fallback we inspect the response body for
    the Apache 401 page signature — that signature is stable because
    it's served by Apache on the origin, not modified by Cloudflare.
    """
    auth = headers.get("WWW-Authenticate", "")
    if "Basic" in auth and "ATIUS" in auth:
        return True
    body_sig = b"401 Unauthorized" in body and b"Apache" in body
    return body_sig


def looks_like_cf_access_redirect(headers: dict[str, str]) -> bool:
    """True when the response redirects to a Cloudflare Access login URL."""
    location = headers.get("Location", "")
    return any(host in location for host in ("cloudflareaccess.com", "cloudflare.com"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect",
        choices=["pre-cutover", "access-live", "basic-only"],
        default="pre-cutover",
        help=(
            "Which state to assert. "
            "pre-cutover (default): 401 Basic challenge on both edges. "
            "access-live: 302 to Cloudflare Access login OR 200 with service token. "
            "basic-only: 401 Basic challenge and Basic Auth credentials work."
        ),
    )
    parser.add_argument("--edge", action="append", choices=list(edge.ADMIN_EDGES), default=None)
    args = parser.parse_args()

    edges = args.edge or list(edge.ADMIN_EDGES)
    auth_info = edge.describe_auth()
    basic_user = os.environ.get(edge.LEGACY_BASIC_AUTH_ENV_USER)
    basic_pass = os.environ.get(edge.LEGACY_BASIC_AUTH_ENV_PASS)

    print("=" * 70)
    print("Phase 16 / M005 Cloudflare Access — live validation")
    print("=" * 70)
    print(json.dumps(auth_info, indent=2))
    print()
    print(f"basic auth env: user={'set' if basic_user else 'unset'} pass={'set' if basic_pass else 'unset'}")
    print(f"expecting: {args.expect}")
    print()

    failures: list[str] = []

    for name in edges:
        url = edge.ADMIN_EDGES[name]
        print(f"--- {name} ({url}) ---")

        # 1. anonymous request — no creds
        code, hdrs, body = get_or_head(url)
        basic = looks_like_basic_challenge(hdrs, body)
        redirect = looks_like_cf_access_redirect(hdrs)
        print(f"  anon GET             → HTTP {code}  basic_challenge={basic}  cf_access_redirect={redirect}")

        # 2. with service token (if available)
        cf_headers = edge.cf_service_auth_headers()
        if cf_headers:
            code_cf, hdrs_cf, _ = get_or_head(url, headers=cf_headers)
            print(f"  + CF service token   → HTTP {code_cf}")
        else:
            code_cf = None
            print(f"  + CF service token   → (no token file, skipping)")

        # 3. with basic auth (if env vars set)
        if basic_user and basic_pass:
            basic_hdrs = edge.basic_auth_header(basic_user, basic_pass)
            code_basic, hdrs_basic, _ = get_or_head(url, headers=basic_hdrs)
            print(f"  + Basic Auth         → HTTP {code_basic}")
        else:
            code_basic = None
            print(f"  + Basic Auth         → (env unset, skipping)")

        # 4. assert against --expect
        if args.expect == "pre-cutover":
            if code != 401 or not basic:
                failures.append(f"{name}: expected 401+Basic challenge, got HTTP {code} basic={basic}")
        elif args.expect == "access-live":
            if code == 401 and not basic:
                failures.append(f"{name}: still returning 401 with no WWW-Authenticate — Access not gating yet")
            elif code == 302 and redirect:
                pass  # expected 302 → Cloudflare Access login
            elif code == 200:
                pass  # expected 200 (e.g. service token on auto)
            elif code_cf == 200:
                pass  # service token made it through
            else:
                failures.append(f"{name}: expected 302/200 with Access, got HTTP {code}")
        elif args.expect == "basic-only":
            if code != 401 or not basic:
                failures.append(f"{name}: expected 401+Basic challenge, got HTTP {code} basic={basic}")
            if code_basic is not None and code_basic not in (200, 302):
                failures.append(f"{name}: basic auth unexpectedly returned HTTP {code_basic}")

    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK — all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
