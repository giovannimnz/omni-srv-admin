#!/usr/bin/env python3
"""Read-only MCP edge conformance smoke.

It can run against live endpoints, but assertions that require infrastructure
fail closed when a target is unreachable.  Output is deliberately redacted.
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

TARGETS = {
    "oci-admin": "https://mcp.atius.com.br/oci-admin",
    "gbrain": "https://mcp.atius.com.br/gbrain",
    "obsidian": "https://mcp.atius.com.br/obsidian",
}


def _post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=12, context=ssl.create_default_context()) as response:
            return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read(4096)
    except urllib.error.HTTPError as exc:
        return exc.code, {key.lower(): value for key, value in exc.headers.items()}, exc.read(4096)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", default=", ".join(TARGETS))
    parser.add_argument("--boundaries", default="n")
    for name in ("backend-direct", "host-421", "single-allow", "tls-scope", "pm2-resurrect", "isolated-recovery", "omni-health"):
        parser.add_argument(f"--assert-{name}", action="store_true")
    parser.add_argument("--token", default="", help="optional token; never printed")
    args = parser.parse_args(argv)
    selected = [item.strip() for item in args.targets.split(",") if item.strip()]
    unknown = sorted(set(selected) - TARGETS.keys())
    if unknown:
        parser.error(f"targets desconhecidos: {', '.join(unknown)}")

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Host": "mcp.atius.com.br",
    }
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    initialize = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode()
    failures: list[str] = []
    observed: dict[str, int] = {}
    for target in selected:
        status, raw_headers, _ = _post(TARGETS[target], initialize, headers)
        observed[target] = status
        if args.assert_backend_direct and status in {401, 403} and not args.token:
            failures.append(f"{target}: auth required (provide token from Vault)")
        elif args.assert_backend_direct and status >= 500:
            failures.append(f"{target}: HTTP {status}")
        if args.assert_host_421:
            bad = dict(headers)
            bad["Host"] = "invalid.example"
            bad_status, _, _ = _post(TARGETS[target], initialize, bad)
            if bad_status != 421:
                failures.append(f"{target}: invalid Host returned HTTP {bad_status}, expected 421")
        if args.assert_single_allow:
            allow = raw_headers.get("allow", "")
            if allow.count(",") > 0:
                failures.append(f"{target}: Allow has multiple values")
    if args.assert_tls_scope:
        apache = Path("deploy/apache/mcp-atius-oci-admin.conf.inc")
        if apache.exists() and "SSLProxyVerify none" in apache.read_text(encoding="utf-8"):
            failures.append("oci-admin: global SSLProxyVerify none remains")
    if args.assert_pm2_resurrect or args.assert_isolated_recovery:
        ecosystem = Path("deploy/pm2/ecosystem.config.cjs")
        text = ecosystem.read_text(encoding="utf-8") if ecosystem.exists() else ""
        for app in ("oci-admin-web", "oci-admin-mcp-http"):
            if app not in text or "namespace: \"oci-admin\"" not in text:
                failures.append(f"pm2: missing namespace/app {app}")
        if args.assert_isolated_recovery and "autorestart: true" not in text:
            failures.append("pm2: autorestart missing")
    if args.assert_omni_health:
        watchdog = Path("/home/ubuntu/GitHub/omni-srv-admin/modules/srv3-ops/scripts/oci-admin-watchdog.sh")
        text = watchdog.read_text(encoding="utf-8") if watchdog.exists() else ""
        for app in ("oci-admin-web", "oci-admin-mcp-http"):
            if f'check_app "{app}"' not in text:
                failures.append(f"omni: missing health check {app}")
    print(json.dumps({"targets": observed, "boundaries": args.boundaries, "failures": failures}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
