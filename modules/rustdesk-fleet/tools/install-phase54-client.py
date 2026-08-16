#!/usr/bin/env python3
"""Fail-closed Linux RustDesk client transaction for Phase 54.

The default entry point is observation/dry-run only.  A real backend must be
injected by a later live plan after an owner-bound Phase 53 admission receipt;
this module never SSHes, talks to Vault, installs packages, or mutates a host
by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
from typing import Any, Callable, Protocol

from phase54_preflight import Phase54PreflightBlocked, validate as validate_phase54_preflight


class Phase54ClientBlocked(RuntimeError):
    """Raised for any missing gate, drift or unsafe mutation boundary."""


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-client-runtime.json")
TOPOLOGY_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-canary-topology.json")
PREFLIGHT_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-preflight.json")
ALLOWED_TARGET = "horistic-srv"
FORBIDDEN_PATH_MARKERS = (
    "phase53",
    "server/state",
    "server-identity",
    "quadlets/atius-rustdesk-server-",
    "rustdesk-ops-api",
)
MAX_OUTPUT_BYTES = 128 * 1024
MAX_ERROR_BYTES = 16 * 1024
BACKEND_SCOPE = "phase54-client-only-v1"


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise Phase54ClientBlocked(f"duplicate-json-key:{path.name}:{key}")
            result[key] = value
        return result

    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_size <= 0 or info.st_size > 4 * 1024 * 1024:
            raise Phase54ClientBlocked(f"contract-file-invalid:{path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except Phase54ClientBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase54ClientBlocked(f"contract-json-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise Phase54ClientBlocked(f"contract-object-required:{path.name}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _value_free_scan(value: Any, path: str = "root") -> None:
    forbidden_keys = {
        "password",
        "private_key",
        "bearer_token",
        "client_secret",
        "raw_client_id",
        "raw_gui_payload",
        "authorization",
        "authorization_header",
        "api_token",
        "secret",
        "token",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in forbidden_keys and child not in (False, None, "[REDACTED]"):
                raise Phase54ClientBlocked(f"secret-surface:{path}.{key}")
            _value_free_scan(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _value_free_scan(child, f"{path}[{index}]")
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise Phase54ClientBlocked(f"secret-surface:{path}")


def load_contracts(repo: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repo = repo.resolve(strict=True)
    runtime = _strict_json(repo / RUNTIME_RELATIVE)
    topology = _strict_json(repo / TOPOLOGY_RELATIVE)
    preflight = _strict_json(repo / PREFLIGHT_RELATIVE)
    for payload in (runtime, topology, preflight):
        if payload.get("phase") != 54 or payload.get("workstream") != "rustdesk-fleet":
            raise Phase54ClientBlocked("phase54-contract-identity-drift")
        _value_free_scan(payload)
    return runtime, topology, preflight


def validate_preflight(repo: Path, receipt_path: Path, target: str) -> dict[str, Any]:
    """Use the shared read-only validator; never maintain an alternate path."""

    try:
        return validate_phase54_preflight(repo, receipt_path, target)
    except Phase54PreflightBlocked as exc:
        raise Phase54ClientBlocked(str(exc)) from exc


def _probe_deb_architecture(package: Path) -> str:
    """Read Debian metadata through a bounded, read-only helper."""

    code, stdout, _ = bounded_process(["/usr/bin/dpkg-deb", "--field", str(package), "Architecture"])
    if code != 0:
        raise Phase54ClientBlocked("deb-architecture-probe-failed")
    architecture = stdout.decode("ascii", errors="strict").strip()
    if not architecture or "\n" in architecture:
        raise Phase54ClientBlocked("deb-architecture-invalid")
    return architecture


def verify_package(
    package: Path,
    runtime: dict[str, Any],
    target: str,
    *,
    architecture_probe: Callable[[Path], str] | None = None,
) -> dict[str, Any]:
    """Check package regular-file/hash/architecture without installing it."""

    if target != ALLOWED_TARGET:
        raise Phase54ClientBlocked("package-target-not-allowed")
    if package.is_symlink() or not package.is_file():
        raise Phase54ClientBlocked("package-file-invalid")
    target_contract = runtime["targets"][target]
    expected = target_contract["asset"]
    if package.name != expected["asset_name"]:
        raise Phase54ClientBlocked("package-name-drift")
    actual_hash = _sha256(package)
    if actual_hash != expected["sha256"]:
        raise Phase54ClientBlocked("package-hash-mismatch")
    # The canonical Phase 54 contract pins architecture beside `asset`, not
    # inside the package metadata object. Keep the verifier aligned with that
    # schema so a real contract cannot be accidentally masked by a test fixture.
    architecture = target_contract["architecture"]
    probe = architecture_probe or _probe_deb_architecture
    observed_architecture = probe(package)
    if observed_architecture != architecture:
        raise Phase54ClientBlocked("package-architecture-mismatch")
    return {
        "asset_name": package.name,
        "sha256": actual_hash,
        "architecture_expected": architecture,
        "architecture_observed": observed_architecture,
        "architecture_verified": True,
        "verification_state": "HASH_AND_ARCH_VERIFIED",
    }


def assert_client_path(path: Path, runtime: dict[str, Any], target: str) -> None:
    raw = Path(path)
    if not raw.is_absolute() or ".." in raw.parts:
        raise Phase54ClientBlocked("client-path-not-canonical")
    lexical_text = str(raw).replace("\\", "/").lower()
    if any(marker in lexical_text for marker in FORBIDDEN_PATH_MARKERS):
        raise Phase54ClientBlocked("server-path-write-forbidden")
    current = Path(raw.anchor)
    for part in raw.parts[1:]:
        current /= part
        try:
            if current.is_symlink():
                raise Phase54ClientBlocked("client-path-symlink-forbidden")
        except OSError as exc:
            raise Phase54ClientBlocked("client-path-lstat-failed") from exc
    try:
        canonical = raw.resolve(strict=False)
    except OSError as exc:
        raise Phase54ClientBlocked("client-path-resolve-failed") from exc
    text = str(canonical).replace("\\", "/").lower()
    if any(marker in text for marker in FORBIDDEN_PATH_MARKERS):
        raise Phase54ClientBlocked("server-path-write-forbidden")
    allowed = runtime["targets"][target]["paths"]
    roots = [
        Path(str(allowed["config"]))
        .resolve(strict=False),
        Path(str(allowed["state"]))
        .resolve(strict=False),
        Path(str(allowed["rollback"]).replace("<transaction-id>", ""))
        .resolve(strict=False),
    ]
    if not any(canonical == root or root in canonical.parents for root in roots):
        raise Phase54ClientBlocked("client-path-outside-contract")


def bounded_process(
    argv: list[str],
    *,
    request: bytes | None = None,
    pass_fds: tuple[int, ...] = (),
    timeout: float = 30.0,
) -> tuple[int, bytes, bytes]:
    """Run a bounded argv-only helper; no shell or inherited secret env."""

    if not argv or any(not isinstance(item, str) or not item or "\n" in item for item in argv):
        raise Phase54ClientBlocked("command-invalid")
    process: subprocess.Popen[bytes] | None = None
    safe_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"}
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE if request is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=safe_env,
            pass_fds=pass_fds,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(request, timeout=timeout)
        if len(stdout) > MAX_OUTPUT_BYTES or len(stderr) > MAX_ERROR_BYTES:
            raise Phase54ClientBlocked("command-output-too-large")
        return process.returncode, stdout, stderr
    except (OSError, subprocess.SubprocessError) as exc:
        raise Phase54ClientBlocked("command-failed") from exc
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


class ClientBackend(Protocol):
    phase54_scope: str
    server_paths_mutable: bool
    credential_channel: str

    def snapshot(self, target: str, rollback_root: Path) -> None: ...
    def install_package(self, package: Path, password_fd: int) -> None: ...
    def configure(self, target: str) -> None: ...
    def readback(self, target: str) -> dict[str, Any]: ...
    def rollback(self, target: str, rollback_root: Path) -> None: ...


@dataclass
class DryRunBackend:
    """Safe default backend that cannot mutate a host."""

    events: list[str]
    phase54_scope: str = BACKEND_SCOPE
    server_paths_mutable: bool = False
    credential_channel: str = "fd-pipe"

    def snapshot(self, target: str, rollback_root: Path) -> None:
        self.events.append("snapshot")

    def install_package(self, package: Path, password_fd: int) -> None:
        self.events.append("install-blocked-dry-run")
        raise Phase54ClientBlocked("dry-run-backend-cannot-install")

    def configure(self, target: str) -> None:
        self.events.append("configure-blocked-dry-run")
        raise Phase54ClientBlocked("dry-run-backend-cannot-configure")

    def readback(self, target: str) -> dict[str, Any]:
        self.events.append("readback")
        return {"target": target, "value_free": True}

    def rollback(self, target: str, rollback_root: Path) -> None:
        self.events.append("rollback")


def run_transaction(
    repo: Path,
    *,
    target: str,
    package: Path,
    receipt: Path,
    rollback_root: Path,
    backend: ClientBackend,
    password_fd: int,
    architecture_probe: Callable[[Path], str] | None = None,
) -> dict[str, Any]:
    """Run the ordered fake/backend transaction after every gate passes."""

    admission = validate_preflight(repo, receipt, target)
    if (
        getattr(backend, "phase54_scope", None) != BACKEND_SCOPE
        or getattr(backend, "server_paths_mutable", True) is not False
        or getattr(backend, "credential_channel", None) not in {"fd-pipe", "tmpfs"}
        or any(not callable(getattr(backend, method, None)) for method in ("snapshot", "install_package", "configure", "readback", "rollback"))
    ):
        raise Phase54ClientBlocked("client-backend-contract-required")
    if not isinstance(password_fd, int) or password_fd < 0:
        raise Phase54ClientBlocked("password-fd-required")
    try:
        fd_flags = fcntl.fcntl(password_fd, fcntl.F_GETFD)
    except (OSError, ValueError) as exc:
        raise Phase54ClientBlocked("password-fd-invalid") from exc
    if not fd_flags & fcntl.FD_CLOEXEC:
        raise Phase54ClientBlocked("password-fd-must-be-non-inheritable")
    runtime, _, _ = load_contracts(repo)
    package_observation = verify_package(
        package,
        runtime,
        target,
        architecture_probe=architecture_probe,
    )
    assert_client_path(rollback_root, runtime, target)
    events: list[str] = ["preflight", "package", "path"]
    try:
        backend.snapshot(target, rollback_root)
        events.append("snapshot")
        backend.install_package(package, password_fd)
        events.append("install")
        backend.configure(target)
        events.append("configure")
        readback = backend.readback(target)
        events.append("readback")
    except Exception as exc:
        try:
            backend.rollback(target, rollback_root)
            events.append("rollback")
        except Exception as rollback_exc:
            raise Phase54ClientBlocked("client-rollback-failed") from rollback_exc
        if isinstance(exc, Phase54ClientBlocked):
            raise
        raise Phase54ClientBlocked("client-transaction-failed") from exc
    if not isinstance(readback, dict) or readback.get("value_free") is not True:
        raise Phase54ClientBlocked("readback-not-value-free")
    return {
        **admission,
        "state": "PENDING_LIVE_READBACK",
        "mutation_performed": True,
        "secret_material_present": False,
        "package": package_observation,
        "readback": readback,
        "events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 54 Linux client preflight (no live install by default)")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--target", default=ALLOWED_TARGET)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        if not args.package or not args.receipt:
            raise Phase54ClientBlocked("package-and-preflight-receipt-required")
        runtime, _, _ = load_contracts(args.repo)
        receipt = validate_preflight(args.repo, args.receipt, args.target)
        observation = verify_package(args.package, runtime, args.target)
        print(json.dumps({**receipt, "state": "READY_NO_MUTATION", "package": observation, "mutation_performed": False}, sort_keys=True))
        return 0
    except (Phase54ClientBlocked, OSError, ValueError) as exc:
        print(json.dumps({"schema_version": 1, "phase": 54, "state": "BLOCKED", "reason": str(exc), "mutation_performed": False, "secret_material_present": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
