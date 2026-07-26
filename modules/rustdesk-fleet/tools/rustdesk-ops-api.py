#!/usr/bin/env python3
"""Read-only, authenticated and redacted ATIUS RustDesk operations API."""

from __future__ import annotations

import argparse
import copy
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Callable


EXPECTED_DIGEST = "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
EXPECTED_LISTENERS = {
    "hbbs": {"tcp": [21115, 21116, 21118], "udp": [21116], "digest": EXPECTED_DIGEST},
    "hbbr": {"tcp": [21117, 21119], "udp": [], "digest": EXPECTED_DIGEST},
}
EXPECTED_EDGE = {
    "ipv4_tcp": [21115, 21116, 21117],
    "ipv4_udp": [21116],
    "ipv6": [],
    "forbidden_not_open": [21114, 21118, 21119],
}
READINESS_INPUTS = (
    "immutable-image-digest",
    "exact-listener-ownership",
    "public-fingerprint-continuity",
    "effective-edge-policy",
    "resource-ceilings",
    "disk-and-log-bounds",
    "bounded-restart-counters",
)
HEADERS = {"Cache-Control": "no-store", "Content-Type": "application/json"}
ENDPOINTS = {"/v1/health", "/v1/readiness", "/v1/status", "/v1/metrics/summary"}


class OpsApiBlocked(RuntimeError):
    pass


def expected_listener_contract(digest: str) -> dict[str, dict[str, Any]]:
    """Bind listener observations to the selected immutable runtime digest."""

    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise OpsApiBlocked("runtime-digest-invalid")
    return {
        "hbbs": {"tcp": [21115, 21116, 21118], "udp": [21116], "digest": digest},
        "hbbr": {"tcp": [21117, 21119], "udp": [], "digest": digest},
    }


def select_runtime_digest(repo: Path | None = None, environ: dict[str, str] | None = None) -> str:
    """Select baseline or an admitted successor without ambient promotion."""

    environment = os.environ if environ is None else environ
    if environment.get("ADMITTED_PHASE53") != "1":
        return EXPECTED_DIGEST
    root = (repo or Path(__file__).resolve().parents[3]).resolve(strict=True)
    candidate_path = root / "modules/rustdesk-fleet/contracts/phase53-runtime-candidate.json"
    evidence_path = root / "modules/rustdesk-fleet/evidence/phase53/candidate-admission.json"
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OpsApiBlocked("candidate-runtime-unavailable") from exc
    if (
        not isinstance(candidate, dict)
        or candidate.get("candidate_status_required") != "ADMITTED_PHASE53"
        or not isinstance(evidence, dict)
        or evidence.get("candidate_status") != "ADMITTED_PHASE53"
        or evidence.get("admission_performed") is not True
        or evidence.get("live_mutation_performed") is not False
    ):
        raise OpsApiBlocked("candidate-admission-required")
    upstream = candidate.get("upstream")
    digest = upstream.get("linux_arm64_digest") if isinstance(upstream, dict) else None
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise OpsApiBlocked("candidate-runtime-digest-invalid")
    return digest


def authenticate_request(headers: dict[str, str], expected_token: str) -> bool:
    authorization = headers.get("Authorization", "")
    prefix = "Bearer "
    if not expected_token or not authorization.startswith(prefix):
        return False
    supplied = authorization[len(prefix) :]
    return bool(supplied) and " " not in supplied and hmac.compare_digest(supplied, expected_token)


def derive_readiness(observations: dict[str, Any]) -> dict[str, Any]:
    cgroups = observations.get("cgroups", {})
    edge = observations.get("edge", {})
    fingerprint = observations.get("public_fingerprint")
    expected_fingerprint = observations.get("expected_public_fingerprint")
    runtime_digest = observations.get("runtime_contract_digest", EXPECTED_DIGEST)
    listeners = expected_listener_contract(runtime_digest)
    checks = {
        "immutable-image-digest": observations.get("image_digest") == runtime_digest,
        "exact-listener-ownership": observations.get("listeners") == listeners,
        "public-fingerprint-continuity": (
            isinstance(fingerprint, str)
            and fingerprint == expected_fingerprint
            and fingerprint.startswith("sha256:")
            and len(fingerprint) == 71
        ),
        "effective-edge-policy": edge == EXPECTED_EDGE,
        "resource-ceilings": cgroups == {
            "parent_cpu_percent": 80,
            "parent_memory_bytes": 1073741824,
            "ops_cpu_percent": 10,
            "ops_memory_bytes": 201326592,
        },
        "disk-and-log-bounds": (
            isinstance(observations.get("disk_free_bytes"), int)
            and observations["disk_free_bytes"] >= 4026531840
            and isinstance(observations.get("log_growth_bytes"), int)
            and 0 <= observations["log_growth_bytes"] <= 134217728
        ),
        "bounded-restart-counters": (
            type(observations.get("restart_count")) is int
            and type(observations.get("restart_limit")) is int
            and 0 <= observations["restart_count"] <= observations["restart_limit"] <= 3
        ),
    }
    assert tuple(checks) == READINESS_INPUTS
    return {"schema_version": 1, "ready": all(checks.values()), "checks": checks}


def collect_metric_summary(observations: dict[str, Any]) -> dict[str, Any]:
    return {
        "listeners": copy.deepcopy(observations.get("listeners", {})),
        "restarts": observations.get("restart_count", 0),
        "cpu_percent": observations.get("cpu_percent", 0),
        "memory_bytes": observations.get("memory_bytes", 0),
        "disk_bytes": observations.get("disk_bytes", 0),
        "log_growth_bytes": observations.get("log_growth_bytes", 0),
        "direct_bytes": observations.get("direct_bytes", 0),
        "relay_bytes": observations.get("relay_bytes", 0),
        "failures": observations.get("failures", 0),
        "transport_semantics": "observational-only",
        "session_transport_asserted": False,
    }


def handle_request(
    method: str,
    path: str,
    headers: dict[str, str],
    *,
    observations: dict[str, Any],
    expected_token: str,
) -> dict[str, Any]:
    if method != "GET" or path not in ENDPOINTS:
        return {"status": 404, "headers": dict(HEADERS), "body": {"error": "not_found"}}
    if not authenticate_request(headers, expected_token):
        return {"status": 401, "headers": dict(HEADERS), "body": {"error": "unauthorized"}}
    if path == "/v1/health":
        body = {"schema_version": 1, "service": "atius-rustdesk-ops", "healthy": True}
    elif path == "/v1/readiness":
        body = derive_readiness(observations)
    elif path == "/v1/status":
        body = {
            "schema_version": 1,
            "service": "atius-rustdesk-ops",
            "primary_host": "horistic-srv",
            "service_active": observations.get("service_active") is True,
            "image_digest": observations.get("image_digest"),
            "public_fingerprint": observations.get("public_fingerprint"),
        }
    else:
        body = {"schema_version": 1, **collect_metric_summary(observations)}
    return {"status": 200, "headers": dict(HEADERS), "body": body}


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


class ApacheVhostTransaction:
    """Configtest-first, ownership-scoped Apache vhost transaction for Plan 05."""

    def __init__(
        self,
        *,
        candidate: Path,
        destination: Path,
        command_runner: Callable[[list[str]], tuple[int, bytes, bytes]],
        existing_vhost_probe: Callable[[], dict[str, bool]],
    ) -> None:
        self.candidate = candidate
        self.destination = destination
        self.command_runner = command_runner
        self.existing_vhost_probe = existing_vhost_probe
        self._existed = destination.exists()
        self._before = destination.read_bytes() if self._existed else None
        self._mode = stat.S_IMODE(destination.stat().st_mode) if self._existed else 0o640
        self._rolled_back = False

    def _run(self, argv: list[str]) -> None:
        code, _stdout, stderr = self.command_runner(argv)
        if code or stderr:
            raise OpsApiBlocked("apache-command-failed")

    def apply_candidate(self) -> dict[str, Any]:
        try:
            data = self.candidate.read_bytes()
            if b"Managed-By: omni-srv-admin/rustdesk-fleet/phase53" not in data:
                raise OpsApiBlocked("apache-ownership-marker-missing")
            _atomic_write(self.destination, data, 0o640)
            self._run(["apachectl", "configtest"])
            self._run(["systemctl", "reload", "apache2"])
            probes = self.existing_vhost_probe()
            if not probes or not all(probes.values()):
                raise OpsApiBlocked("apache-vhost-regression")
            return {"applied": True, "existing_vhosts": sorted(probes), "secret_material_present": False}
        except Exception:
            self.rollback()
            raise

    def rollback(self) -> dict[str, Any]:
        if self._rolled_back:
            return {"terminal": True, "state": "ROLLED_BACK"}
        if self._existed:
            assert self._before is not None
            _atomic_write(self.destination, self._before, self._mode)
        else:
            self.destination.unlink(missing_ok=True)
        self._rolled_back = True
        return {"terminal": True, "state": "ROLLED_BACK"}


def _load_secure(path: Path) -> str:
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
        raise OpsApiBlocked("runtime-file-invalid")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise OpsApiBlocked("runtime-file-empty")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=32113)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--observations-file", required=True, type=Path)
    args = parser.parse_args()
    if args.listen != "127.0.0.1" or not 1024 <= args.port <= 65535:
        return 2
    try:
        token = _load_secure(args.token_file)
        observations = json.loads(args.observations_file.read_text(encoding="utf-8"))
        if not isinstance(observations, dict):
            return 2
        selected_digest = select_runtime_digest()
        observed_digest = observations.get("runtime_contract_digest", EXPECTED_DIGEST)
        if observed_digest != selected_digest:
            return 2
    except (OSError, OpsApiBlocked, json.JSONDecodeError):
        return 2

    class Handler(BaseHTTPRequestHandler):
        def _serve(self) -> None:
            result = handle_request(
                self.command,
                self.path,
                {key: value for key, value in self.headers.items()},
                observations=observations,
                expected_token=token,
            )
            body = json.dumps(result["body"], sort_keys=True, separators=(",", ":")).encode()
            self.send_response(result["status"])
            for key, value in result["headers"].items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = _serve
        do_POST = _serve
        do_PUT = _serve
        do_DELETE = _serve

        def log_message(self, _format: str, *args: object) -> None:
            del args

    ThreadingHTTPServer((args.listen, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
