#!/usr/bin/env python3
"""Fail-closed W11 RustDesk client transaction for Phase 54.

This is a code-only transaction boundary.  It never opens SSH, invokes
``msiexec`` or PowerShell, and never contacts Vault.  The future live adapter
must inject read-only MSI/Authenticode probes and a client-only backend after
the shared Phase 54 preflight has admitted a current Phase 53 authority.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Protocol

from phase54_preflight import Phase54PreflightBlocked, validate as validate_phase54_preflight


class Phase54WindowsBlocked(RuntimeError):
    """Raised for every missing gate, drift or unsafe Windows mutation."""


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-client-runtime.json")
TOPOLOGY_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-canary-topology.json")
PREFLIGHT_RELATIVE = Path("modules/rustdesk-fleet/contracts/phase54-preflight.json")
TARGET = "GIOVANNI-W11-PC"
BACKEND_SCOPE = "phase54-client-only-v1"
FORBIDDEN_MARKERS = (
    "phase53",
    "server/state",
    "server-identity",
    "quadlets/atius-rustdesk-server-",
    "rustdesk-ops-api",
)


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise Phase54WindowsBlocked(f"duplicate-json-key:{path.name}:{key}")
            result[key] = value
        return result

    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_size <= 0 or info.st_size > 4 * 1024 * 1024:
            raise Phase54WindowsBlocked(f"contract-file-invalid:{path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except Phase54WindowsBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase54WindowsBlocked(f"contract-json-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise Phase54WindowsBlocked(f"contract-object-required:{path.name}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_contracts(repo: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repo = repo.resolve(strict=True)
    runtime = _strict_json(repo / RUNTIME_RELATIVE)
    topology = _strict_json(repo / TOPOLOGY_RELATIVE)
    preflight = _strict_json(repo / PREFLIGHT_RELATIVE)
    for payload in (runtime, topology, preflight):
        if payload.get("phase") != 54 or payload.get("workstream") != "rustdesk-fleet":
            raise Phase54WindowsBlocked("phase54-contract-identity-drift")
    return runtime, topology, preflight


def validate_preflight(repo: Path, receipt_path: Path, target: str) -> dict[str, Any]:
    if target != TARGET:
        raise Phase54WindowsBlocked("windows-installer-target-not-allowed")
    try:
        return validate_phase54_preflight(repo, receipt_path, target)
    except Phase54PreflightBlocked as exc:
        raise Phase54WindowsBlocked(str(exc)) from exc


def verify_msi(
    package: Path,
    runtime: dict[str, Any],
    target: str,
    *,
    architecture_probe: Callable[[Path], str] | None = None,
    authenticode_probe: Callable[[Path], bool] | None = None,
) -> dict[str, Any]:
    """Verify MSI name/hash/architecture/signature through injected probes."""

    if target != TARGET:
        raise Phase54WindowsBlocked("msi-target-not-allowed")
    if package.is_symlink() or not package.is_file():
        raise Phase54WindowsBlocked("msi-file-invalid")
    target_contract = runtime.get("targets", {}).get(target)
    if not isinstance(target_contract, dict):
        raise Phase54WindowsBlocked("windows-runtime-contract-missing")
    expected = target_contract.get("asset")
    if not isinstance(expected, dict) or package.name != expected.get("asset_name"):
        raise Phase54WindowsBlocked("msi-name-drift")
    actual_hash = _sha256(package)
    if actual_hash != expected.get("sha256"):
        raise Phase54WindowsBlocked("msi-hash-mismatch")
    if architecture_probe is None:
        raise Phase54WindowsBlocked("msi-architecture-probe-required")
    observed_architecture = architecture_probe(package)
    if observed_architecture != target_contract.get("architecture"):
        raise Phase54WindowsBlocked("msi-architecture-mismatch")
    if authenticode_probe is None:
        raise Phase54WindowsBlocked("msi-authenticode-probe-required")
    if authenticode_probe(package) is not True:
        raise Phase54WindowsBlocked("msi-authenticode-invalid")
    return {
        "asset_name": package.name,
        "sha256": actual_hash,
        "architecture_expected": target_contract["architecture"],
        "architecture_observed": observed_architecture,
        "architecture_verified": True,
        "authenticode_verified": True,
        "verification_state": "HASH_ARCH_AUTHENTICODE_VERIFIED",
    }


def select_ssh_route(private_rc: int) -> str:
    """Model private-first fallback policy without making an SSH call."""

    if private_rc == 0:
        return "private-first"
    if private_rc == 255:
        return "public-native-fallback"
    raise Phase54WindowsBlocked("private-route-failure-not-fallbackable")


def route_plan() -> tuple[dict[str, Any], ...]:
    """Return the approved route metadata; this function performs no I/O."""

    return (
        {
            "route": "private-first",
            "ssh_target": "muniz@10.100.100.8",
            "port": 22,
            "fallback_on": ["ssh-rc255"],
        },
        {
            "route": "public-native-fallback",
            "ssh_target": "muniz@ssh-giovanni-w11-pc.atius.com.br",
            "port": 8122,
            "fallback_on": [],
        },
    )


def assert_windows_path(path: str, runtime: dict[str, Any], target: str) -> None:
    """Reject server paths, traversal and paths outside the client roots."""

    if target != TARGET or not isinstance(path, str) or not path or ".." in path.replace("/", "\\").split("\\"):
        raise Phase54WindowsBlocked("windows-path-not-canonical")
    text = path.replace("/", "\\").lower()
    if any(marker in text for marker in FORBIDDEN_MARKERS):
        raise Phase54WindowsBlocked("server-path-write-forbidden")
    roots = runtime["targets"][target]["paths"]
    allowed = [str(roots["config"]).replace("/", "\\").rstrip("\\"), str(roots["state"]).replace("/", "\\").rstrip("\\"), str(roots["rollback"]).replace("<transaction-id>", "").replace("/", "\\").rstrip("\\")]
    if not any(text == root.lower() or text.startswith(root.lower() + "\\") for root in allowed):
        raise Phase54WindowsBlocked("windows-path-outside-contract")


class WindowsBackend(Protocol):
    phase54_scope: str
    server_paths_mutable: bool
    credential_channel: str

    def snapshot(self, target: str, rollback_root: str) -> None: ...
    def install_msi(self, package: Path, password_fd: int) -> None: ...
    def configure(self, target: str) -> None: ...
    def readback(self, target: str) -> dict[str, Any]: ...
    def rollback(self, target: str, rollback_root: str) -> None: ...


@dataclass
class DryRunBackend:
    events: list[str]
    phase54_scope: str = BACKEND_SCOPE
    server_paths_mutable: bool = False
    credential_channel: str = "fd-pipe"

    def snapshot(self, target: str, rollback_root: str) -> None:
        self.events.append("snapshot")

    def install_msi(self, package: Path, password_fd: int) -> None:
        self.events.append("install-blocked-dry-run")
        raise Phase54WindowsBlocked("dry-run-backend-cannot-install")

    def configure(self, target: str) -> None:
        self.events.append("configure-blocked-dry-run")
        raise Phase54WindowsBlocked("dry-run-backend-cannot-configure")

    def readback(self, target: str) -> dict[str, Any]:
        self.events.append("readback")
        return {"target": target, "value_free": True}

    def rollback(self, target: str, rollback_root: str) -> None:
        self.events.append("rollback")


def run_transaction(
    repo: Path,
    *,
    target: str,
    package: Path,
    receipt: Path,
    rollback_root: str,
    backend: WindowsBackend,
    password_fd: int,
    architecture_probe: Callable[[Path], str] | None = None,
    authenticode_probe: Callable[[Path], bool] | None = None,
) -> dict[str, Any]:
    """Run only an injected fake/backend after every gate passes."""

    admission = validate_preflight(repo, receipt, target)
    if (
        getattr(backend, "phase54_scope", None) != BACKEND_SCOPE
        or getattr(backend, "server_paths_mutable", True) is not False
        or getattr(backend, "credential_channel", None) not in {"fd-pipe", "stdin"}
        or any(not callable(getattr(backend, method, None)) for method in ("snapshot", "install_msi", "configure", "readback", "rollback"))
    ):
        raise Phase54WindowsBlocked("client-backend-contract-required")
    if not isinstance(password_fd, int) or password_fd < 0:
        raise Phase54WindowsBlocked("password-fd-required")
    try:
        if not fcntl.fcntl(password_fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC:
            raise Phase54WindowsBlocked("password-fd-must-be-non-inheritable")
    except (OSError, ValueError) as exc:
        raise Phase54WindowsBlocked("password-fd-invalid") from exc
    runtime, _, _ = load_contracts(repo)
    package_observation = verify_msi(
        package,
        runtime,
        target,
        architecture_probe=architecture_probe,
        authenticode_probe=authenticode_probe,
    )
    assert_windows_path(rollback_root, runtime, target)
    events: list[str] = ["preflight", "package", "path"]
    try:
        backend.snapshot(target, rollback_root)
        events.append("snapshot")
        backend.install_msi(package, password_fd)
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
            raise Phase54WindowsBlocked("client-rollback-failed") from rollback_exc
        if isinstance(exc, Phase54WindowsBlocked):
            raise
        raise Phase54WindowsBlocked("client-transaction-failed") from exc
    if not isinstance(readback, dict) or readback.get("value_free") is not True:
        raise Phase54WindowsBlocked("readback-not-value-free")
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
    parser = argparse.ArgumentParser(description="Phase 54 Windows client preflight (no live install)")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--target", default=TARGET)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        if not args.package or not args.receipt:
            raise Phase54WindowsBlocked("package-and-preflight-receipt-required")
        validate_preflight(args.repo, args.receipt, args.target)
        raise Phase54WindowsBlocked("injected-probes-required-no-live-side-effect")
    except (Phase54WindowsBlocked, OSError, ValueError) as exc:
        print(json.dumps({"schema_version": 1, "phase": 54, "state": "BLOCKED", "reason": str(exc), "mutation_performed": False, "secret_material_present": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
