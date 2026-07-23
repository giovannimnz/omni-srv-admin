#!/usr/bin/env python3
"""Common, dependency-free MCP edge policy.

The guard is intentionally a small policy module: a deployment-specific proxy
may call :func:`validate_request` before forwarding bytes.  It never retries a
request and never logs Authorization, cookies, session IDs, or request bodies.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class EdgePolicy:
    allowed_hosts: frozenset[str]
    allowed_origins: frozenset[str]
    max_payload_bytes: int = 262_144
    max_cardinality: int = 20
    backend_timeout_seconds: float = 120.0
    allow_missing_origin: bool = True


def validate_request(
    headers: Mapping[str, str],
    body: bytes,
    *,
    method: str = "POST",
    policy: EdgePolicy,
) -> tuple[int, str | None]:
    """Return ``(status, error)``; valid Streamable HTTP requests return ``(0, None)``."""

    host = headers.get("host", "").lower().split(":", 1)[0].strip()
    if host not in policy.allowed_hosts:
        return 421, "misdirected_request"
    origin = headers.get("origin")
    if origin is None and not policy.allow_missing_origin:
        return 403, "origin_required"
    if origin is not None and origin not in policy.allowed_origins:
        return 403, "origin_forbidden"
    if method.upper() != "POST":
        return 405, "method_not_allowed"
    content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        return 415, "unsupported_media_type"
    accepted = {item.split(";", 1)[0].strip().lower() for item in headers.get("accept", "").split(",")}
    if not {"application/json", "text/event-stream"}.issubset(accepted):
        return 406, "not_acceptable"
    if len(body) > policy.max_payload_bytes:
        return 413, "payload_too_large"
    try:
        envelope = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, "invalid_json"
    if not isinstance(envelope, dict) or envelope.get("jsonrpc") != "2.0":
        return 400, "invalid_jsonrpc"
    if not isinstance(envelope.get("method"), str) or not envelope["method"].strip():
        return 400, "invalid_jsonrpc"
    if not _within_cardinality(envelope, policy.max_cardinality):
        return 400, "invalid_jsonrpc"
    return 0, None


def _within_cardinality(value: Any, maximum: int) -> bool:
    if isinstance(value, list):
        return len(value) <= maximum and all(_within_cardinality(item, maximum) for item in value)
    if isinstance(value, dict):
        return all(_within_cardinality(item, maximum) for item in value.values())
    return True


class _HealthServer(asyncio.Protocol):
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport

    def data_received(self, data: bytes) -> None:
        if data.startswith(b"GET /healthz"):
            body = b'{"status":"ok"}'
            self.transport.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
        else:
            self.transport.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        self.transport.close()


async def _serve(host: str, port: int) -> None:
    loop = asyncio.get_running_loop()
    server = await loop.create_server(_HealthServer, host, port)
    async with server:
        await server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3138)
    parser.add_argument("--check", action="store_true", help="validate module constants only")
    args = parser.parse_args()
    if args.check:
        policy = EdgePolicy(frozenset({"mcp.atius.com.br"}), frozenset({"https://oci.atius.com.br"}))
        assert validate_request({}, b"", policy=policy)[0] == 421
        return 0
    asyncio.run(_serve(args.listen, args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
