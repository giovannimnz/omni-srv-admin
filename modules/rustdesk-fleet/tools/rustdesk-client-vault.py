#!/usr/bin/env python3
"""Ephemeral, value-free password boundary for Phase 54 clients.

This module deliberately has no Vault/network client.  A caller must inject a
fetcher (normally the reviewed Vault helper) and can only hand the resulting
bytes to a pipe or a tmpfs file.  References and metadata may be logged; secret
values never are.
"""

from __future__ import annotations

from contextlib import contextmanager
import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterator


class ClientVaultBlocked(RuntimeError):
    """Raised when a reference or ephemeral channel violates the contract."""


TARGETS = {
    "horistic-srv": "kv/atius/rustdesk/targets/horistic-srv",
    "GIOVANNI-W11-PC": "kv/atius/rustdesk/targets/giovanni-w11-pc",
}
MAX_SECRET_BYTES = 4096


def validate_reference(target: str, reference: object) -> dict[str, object]:
    """Validate a target password reference without resolving its value."""

    if target not in TARGETS or not isinstance(reference, dict):
        raise ClientVaultBlocked("target-or-reference-invalid")
    path = reference.get("vault_path")
    field = reference.get("field")
    delivery = reference.get("delivery")
    durable = reference.get("durable_value")
    if path != TARGETS[target] or field != "permanent_password":
        raise ClientVaultBlocked("vault-reference-drift")
    if delivery not in {"ephemeral-fd-pipe-or-tmpfs", "fd-pipe", "tmpfs"}:
        raise ClientVaultBlocked("credential-channel-invalid")
    if durable is not False:
        raise ClientVaultBlocked("durable-secret-forbidden")
    if any(key in reference for key in ("value", "password", "secret", "token")):
        raise ClientVaultBlocked("secret-value-in-reference")
    return {"vault_path": path, "field": field, "delivery": delivery, "durable_value": False}


def validate_fetcher(fetcher: object) -> Callable[[str, str], bytes]:
    if not callable(fetcher):
        raise ClientVaultBlocked("vault-fetcher-required")
    return fetcher  # type: ignore[return-value]


def _secret_bytes(value: object) -> bytearray:
    if isinstance(value, str):
        encoded = value.encode("utf-8")
    elif isinstance(value, (bytes, bytearray)):
        encoded = bytes(value)
    else:
        raise ClientVaultBlocked("secret-type-invalid")
    if not encoded or len(encoded) > MAX_SECRET_BYTES or b"\x00" in encoded:
        raise ClientVaultBlocked("secret-size-invalid")
    return bytearray(encoded)


@contextmanager
def fetch_ephemeral(
    target: str,
    reference: object,
    fetcher: Callable[[str, str], bytes],
) -> Iterator[int]:
    """Fetch directly into an ephemeral FD; never return raw secret bytes."""

    ref = validate_reference(target, reference)
    backend = validate_fetcher(fetcher)
    value = backend(ref["vault_path"], ref["field"])
    with secret_pipe(value) as read_fd:
        yield read_fd


@contextmanager
def secret_pipe(value: object) -> Iterator[int]:
    """Yield a read FD containing a bounded secret and clean it afterwards."""

    secret = _secret_bytes(value)
    read_fd, write_fd = os.pipe()
    try:
        os.set_inheritable(read_fd, False)
        os.set_inheritable(write_fd, False)
        written = 0
        while written < len(secret):
            written += os.write(write_fd, secret[written:])
        os.close(write_fd)
        write_fd = -1
        yield read_fd
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        os.close(read_fd)
        for index in range(len(secret)):
            secret[index] = 0


@contextmanager
def secret_tmpfs(value: object, *, directory: Path = Path("/dev/shm")) -> Iterator[Path]:
    """Yield a mode-0600 tmpfs file and unlink it after the transaction."""

    secret = _secret_bytes(value)
    tmpfs_root = Path("/dev/shm").resolve()
    if directory.is_symlink():
        raise ClientVaultBlocked("tmpfs-directory-symlink")
    directory = directory.resolve()
    if directory != tmpfs_root and tmpfs_root not in directory.parents:
        raise ClientVaultBlocked("tmpfs-directory-required")
    if not directory.is_dir() or not os.access(directory, os.W_OK):
        raise ClientVaultBlocked("tmpfs-directory-unavailable")
    descriptor, name = tempfile.mkstemp(prefix=".rustdesk-client-", dir=directory)
    path = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(secret)
            handle.flush()
            os.fsync(handle.fileno())
        yield path
    finally:
        try:
            path.write_bytes(b"\x00" * len(secret))
        except OSError:
            pass
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        for index in range(len(secret)):
            secret[index] = 0


def reference_from_contract(contract: dict, target: str) -> dict[str, object]:
    try:
        reference = contract["targets"][target]["password_ref"]
    except (KeyError, TypeError) as exc:
        raise ClientVaultBlocked("password-reference-missing") from exc
    return validate_reference(target, reference)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 54 Vault reference without resolving secrets")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.contract.read_text(encoding="utf-8"))
        ref = reference_from_contract(payload, args.target)
    except (ClientVaultBlocked, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "secret_material_present": False}))
        return 2
    print(json.dumps({"state": "READY_FOR_INJECTED_FETCHER", "target": args.target, **ref, "secret_material_present": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
