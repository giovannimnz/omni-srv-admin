#!/usr/bin/env python3
"""Recover the SRV-1 RustDesk image and tmpfs identity before Quadlet start."""

from __future__ import annotations

import argparse
import base64
import binascii
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

IMAGE = "docker.io/rustdesk/rustdesk-server@sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
PINNED_TAG = "localhost/atius-rustdesk-server:1.1.15-pinned"
APPROVED_PUBLIC_FINGERPRINT = "17857234cdcf8cb4a2709871da5b6f6342cfa37fb893226ab420897a7b3cb937"
REFERENCES = (
    ("kv/atius/rustdesk/server", "private_key"),
    ("kv/atius/rustdesk/server", "public_key"),
    ("kv/atius/rustdesk/targets/atius-srv-1", "permanent_password"),
    ("kv/atius/rustdesk/targets/atius-srv-2", "permanent_password"),
    ("kv/atius/rustdesk/targets/atius-srv-3", "permanent_password"),
    ("kv/atius/rustdesk/targets/horistic-srv", "permanent_password"),
    ("kv/atius/rustdesk/targets/giovanni-w11-pc", "permanent_password"),
)


class PreflightError(RuntimeError):
    pass


def run(command: list[str], *, input_bytes: bytes | None = None, timeout: int = 60) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def runtime_is_tmpfs(runtime_dir: Path) -> bool:
    result = run(["findmnt", "-n", "-o", "FSTYPE", "-T", str(runtime_dir)])
    return result.returncode == 0 and result.stdout.decode("ascii", "strict").strip() == "tmpfs"


def image_present(podman: Path, image: str) -> bool:
    return run([str(podman), "image", "exists", image]).returncode == 0


def ensure_image(podman: Path, image: str, pinned_tag: str = PINNED_TAG) -> bool:
    recovered = False
    if not image_present(podman, image):
        result = run([str(podman), "pull", image], timeout=300)
        if result.returncode != 0 or not image_present(podman, image):
            raise PreflightError("immutable-image-recovery-failed")
        recovered = True
    if not image_present(podman, pinned_tag):
        result = run([str(podman), "tag", image, pinned_tag])
        if result.returncode != 0 or not image_present(podman, pinned_tag):
            raise PreflightError("immutable-image-pin-failed")
        recovered = True
    return recovered


def decode_identity(private: str, public: str) -> tuple[bytes, bytes]:
    try:
        private_raw = base64.b64decode(private, validate=True)
        public_raw = base64.b64decode(public, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PreflightError("identity-encoding-invalid") from exc
    if len(private_raw) != 64 or len(public_raw) != 32:
        raise PreflightError("identity-length-invalid")
    if private_raw[-32:] != public_raw:
        raise PreflightError("identity-pair-invalid")
    if hashlib.sha256(public.encode("ascii")).hexdigest() != APPROVED_PUBLIC_FINGERPRINT:
        raise PreflightError("identity-fingerprint-invalid")
    return private_raw, public_raw


def existing_identity_valid(identity_dir: Path) -> bool:
    private_path = identity_dir / "id_ed25519"
    public_path = identity_dir / "id_ed25519.pub"
    try:
        if identity_dir.is_symlink() or not identity_dir.is_dir():
            return False
        if (identity_dir.stat().st_mode & 0o777) != 0o700:
            return False
        if any(path.is_symlink() or not path.is_file() or (path.stat().st_mode & 0o777) != 0o600 for path in (private_path, public_path)):
            return False
        private = private_path.read_text("ascii")
        public = public_path.read_text("ascii")
        decode_identity(private, public)
    except (OSError, UnicodeError, PreflightError):
        return False
    return True


def provider_values(provider: Path) -> dict[str, str]:
    request = json.dumps(
        {"references": [{"vault_path": path, "field": field} for path, field in REFERENCES]},
        separators=(",", ":"),
    ).encode("utf-8")
    result = run([str(provider)], input_bytes=request, timeout=40)
    if result.returncode != 0 or result.stderr:
        raise PreflightError("vault-provider-failed")
    try:
        payload: Any = json.loads(result.stdout)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise PreflightError("vault-provider-response-invalid") from exc
    expected = {f"{path}#{field}" for path, field in REFERENCES}
    if not isinstance(payload, dict) or set(payload) != {"request_count", "values"}:
        raise PreflightError("vault-provider-response-invalid")
    values = payload["values"]
    if payload["request_count"] != len(REFERENCES) or not isinstance(values, dict) or set(values) != expected:
        raise PreflightError("vault-provider-response-invalid")
    if any(not isinstance(value, str) or not value for value in values.values()):
        raise PreflightError("vault-provider-value-missing")
    return values


def atomic_write(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, value.encode("ascii"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def ensure_identity(identity_dir: Path, provider: Path) -> bool:
    if existing_identity_valid(identity_dir):
        return False
    if identity_dir.exists() or identity_dir.is_symlink():
        if identity_dir.is_symlink() or not identity_dir.is_dir():
            raise PreflightError("identity-path-invalid")
        for child in identity_dir.iterdir():
            if child.is_symlink() or not child.is_file():
                raise PreflightError("identity-path-invalid")
            child.unlink()
    else:
        identity_dir.mkdir(parents=True, mode=0o700)
    os.chmod(identity_dir, 0o700)
    values = provider_values(provider)
    private = values["kv/atius/rustdesk/server#private_key"]
    public = values["kv/atius/rustdesk/server#public_key"]
    decode_identity(private, public)
    atomic_write(identity_dir / "id_ed25519", private)
    atomic_write(identity_dir / "id_ed25519.pub", public)
    values.clear()
    if not existing_identity_valid(identity_dir):
        raise PreflightError("identity-postwrite-invalid")
    return True


def sqlite_ok(database: Path) -> bool:
    if not database.is_file() or database.is_symlink() or database.stat().st_size <= 0:
        return False
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        value = connection.execute("PRAGMA integrity_check").fetchone()
        connection.close()
    except (OSError, sqlite3.Error):
        return False
    return value == ("ok",)


def check(paths: argparse.Namespace) -> dict[str, Any]:
    return {
        "image_present": image_present(paths.podman, paths.image),
        "image_pinned": image_present(paths.podman, paths.pinned_tag),
        "identity_valid": existing_identity_valid(paths.identity_dir),
        "runtime_tmpfs": runtime_is_tmpfs(paths.runtime_dir),
        "sqlite_integrity": sqlite_ok(paths.database),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure", action="store_true")
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--pinned-tag", default=PINNED_TAG)
    parser.add_argument("--podman", type=Path, default=Path("/usr/bin/podman"))
    parser.add_argument("--runtime-dir", type=Path, default=Path(f"/run/user/{os.getuid()}"))
    parser.add_argument("--identity-dir", type=Path)
    parser.add_argument("--provider", type=Path, default=Path.home() / ".local/bin/rustdesk-vault-provider")
    parser.add_argument("--database", type=Path, default=Path.home() / ".local/share/atius-rustdesk/server/state/db_v2.sqlite3")
    args = parser.parse_args()
    if args.identity_dir is None:
        args.identity_dir = args.runtime_dir / "atius-rustdesk/server-identity"
    lock_path = args.runtime_dir / "atius-rustdesk/runtime-preflight.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        recovered_image = False
        recovered_identity = False
        if args.ensure:
            if not runtime_is_tmpfs(args.runtime_dir):
                raise PreflightError("runtime-not-tmpfs")
            if not sqlite_ok(args.database):
                raise PreflightError("sqlite-integrity-failed")
            recovered_image = ensure_image(args.podman, args.image, args.pinned_tag)
            recovered_identity = ensure_identity(args.identity_dir, args.provider)
        status = check(args)
        if not all(status.values()):
            raise PreflightError("postcheck-failed")
        status.update(
            {
                "status": "PASS",
                "recovered_image": recovered_image,
                "recovered_identity": recovered_identity,
                "secret_material_present": False,
            }
        )
        print(json.dumps(status, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, PreflightError, sqlite3.Error, subprocess.SubprocessError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "blocker": str(exc), "secret_material_present": False}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
