#!/usr/bin/env python3
"""Deterministic, path-scoped exporter transform with retained O_EXCL backup."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import tempfile


LIVE_TARGET = pathlib.Path("/usr/local/sbin/atius-vault-export-env")
LIVE_BACKUP_PREFIX = "/var/backups/atius-vault-export-env.keycloak-admin-readonly."
MARKER_BEGIN = "# BEGIN ATIUS MANAGED PROFILE: keycloak-admin-readonly"
MARKER_END = "# END ATIUS MANAGED PROFILE: keycloak-admin-readonly"
PROFILE_BLOCK = r'''
# BEGIN ATIUS MANAGED PROFILE: keycloak-admin-readonly
if [[ "$#" -eq 1 && "${1:-}" == "keycloak-admin-readonly" ]]; then
  (
    set -euo pipefail
    /usr/local/sbin/atius-vault kv get -format=json kv/atius/keycloak/admin-readonly |
      /usr/bin/python3 -c 'import json,shlex,sys
d=json.load(sys.stdin)["data"]["data"]
e=["KEYCLOAK_BASE_URL","KEYCLOAK_READONLY_CLIENT_ID","KEYCLOAK_READONLY_CLIENT_SECRET","KEYCLOAK_REALM"]
assert sorted(d)==e
assert all(isinstance(d[k],str) and d[k] for k in e)
sys.stdout.write("".join("export "+k+"="+shlex.quote(d[k])+"\n" for k in e))'
  )
  exit $?
fi
# END ATIUS MANAGED PROFILE: keycloak-admin-readonly
'''


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_owner(args: argparse.Namespace) -> tuple[int, int]:
    return (os.getuid(), os.getgid()) if args.sandbox else (0, 0)


def validate_paths(args: argparse.Namespace) -> tuple[pathlib.Path, pathlib.Path]:
    target = pathlib.Path(args.file)
    backup = pathlib.Path(args.backup)
    if args.sandbox:
        if os.geteuid() == 0:
            raise SystemExit("root may not use exporter sandbox mode")
        raw_root = os.environ.get("KARO_TEST_ROOT")
        if not raw_root:
            raise SystemExit("KARO_TEST_ROOT is required")
        root = pathlib.Path(raw_root).resolve(strict=True)
        root_info = root.lstat()
        if not stat.S_ISDIR(root_info.st_mode) or stat.S_IMODE(root_info.st_mode) != 0o700:
            raise SystemExit("sandbox root must be a 0700 directory")
        for item in (target, backup):
            resolved_parent = item.parent.resolve(strict=True)
            if resolved_parent != root:
                raise SystemExit("sandbox paths must be direct children of KARO_TEST_ROOT")
    else:
        if os.geteuid() != 0:
            raise SystemExit("live exporter transform requires root")
        if target != LIVE_TARGET or not str(backup).startswith(LIVE_BACKUP_PREFIX):
            raise SystemExit("live exporter/backup path is outside the exact scope")
        if backup.parent != pathlib.Path("/var/backups") or "/" in backup.name:
            raise SystemExit("invalid retained exporter backup path")
    return target, backup


def read_fd_checked(
    file_path: pathlib.Path,
    *,
    expected_sha: str,
    expected_mode: int,
    args: argparse.Namespace,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(file_path, flags)
    try:
        metadata = os.fstat(descriptor)
        expected_uid, expected_gid = expected_owner(args)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != expected_uid
            or metadata.st_gid != expected_gid
            or stat.S_IMODE(metadata.st_mode) != expected_mode
        ):
            raise SystemExit(f"{file_path} metadata mismatch")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        data = b"".join(chunks)
    finally:
        os.close(descriptor)
    actual_sha = sha256_bytes(data)
    if actual_sha != expected_sha:
        raise SystemExit(f"{file_path} sha256 drift: expected {expected_sha}, got {actual_sha}")
    return data


def transform_bytes(source: bytes) -> bytes:
    text = source.decode("utf-8")
    if MARKER_BEGIN in text or MARKER_END in text or "keycloak-admin-readonly" in text:
        raise SystemExit("exporter already contains the managed profile or a conflicting token")
    first_line, separator, remainder = text.partition("\n")
    if not separator or first_line not in ("#!/usr/bin/env bash", "#!/bin/bash"):
        raise SystemExit("exporter must have a supported bash shebang")
    return f"{first_line}\n{PROFILE_BLOCK.lstrip()}\n{remainder}".encode()


def fsync_directory(directory: pathlib.Path) -> None:
    descriptor = os.open(
        directory,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_backup_exclusive(backup: pathlib.Path, data: bytes, args: argparse.Namespace) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(backup, flags, 0o600)
    try:
        expected_uid, expected_gid = expected_owner(args)
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, expected_uid, expected_gid)
        os.write(descriptor, data)
        os.fsync(descriptor)
    except Exception:
        os.close(descriptor)
        backup.unlink(missing_ok=True)
        raise
    else:
        os.close(descriptor)
    fsync_directory(backup.parent)


def atomic_replace(target: pathlib.Path, data: bytes, args: argparse.Namespace) -> None:
    directory_fd = os.open(
        target.parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    temporary_name = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        expected_uid, expected_gid = expected_owner(args)
        os.fchmod(descriptor, 0o700)
        os.fchown(descriptor, expected_uid, expected_gid)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, target)
        temporary_name = None
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
        if temporary_name:
            pathlib.Path(temporary_name).unlink(missing_ok=True)


def emit(value: dict[str, object]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def preview(args: argparse.Namespace) -> None:
    target, backup = validate_paths(args)
    source = read_fd_checked(
        target, expected_sha=args.expected_before_sha256, expected_mode=0o700, args=args
    )
    transformed = transform_bytes(source)
    emit(
        {
            "action": "preview",
            "backup": str(backup),
            "beforeSha256": sha256_bytes(source),
            "installedSha256": sha256_bytes(transformed),
            "markerCount": transformed.count(MARKER_BEGIN.encode()),
        }
    )


def apply_transform(args: argparse.Namespace) -> None:
    target, backup = validate_paths(args)
    source = read_fd_checked(
        target, expected_sha=args.expected_before_sha256, expected_mode=0o700, args=args
    )
    transformed = transform_bytes(source)
    installed_sha = sha256_bytes(transformed)
    if installed_sha != args.expected_installed_sha256:
        raise SystemExit("deterministic installed exporter sha256 mismatch")
    write_backup_exclusive(backup, source, args)
    atomic_replace(target, transformed, args)
    emit(
        {
            "action": "apply",
            "backup": str(backup),
            "backupSha256": sha256_bytes(source),
            "beforeSha256": args.expected_before_sha256,
            "installedSha256": installed_sha,
            "markerCount": transformed.count(MARKER_BEGIN.encode()),
        }
    )


def read_backup(backup: pathlib.Path, args: argparse.Namespace) -> bytes:
    return read_fd_checked(
        backup,
        expected_sha=args.expected_before_sha256,
        expected_mode=0o600,
        args=args,
    )


def reapply_transform(args: argparse.Namespace) -> None:
    target, backup = validate_paths(args)
    source = read_fd_checked(
        target, expected_sha=args.expected_before_sha256, expected_mode=0o700, args=args
    )
    original = read_backup(backup, args)
    transformed = transform_bytes(source)
    installed_sha = sha256_bytes(transformed)
    if installed_sha != args.expected_installed_sha256:
        raise SystemExit("reapply installed exporter sha256 mismatch")
    atomic_replace(target, transformed, args)
    emit(
        {
            "action": "reapply",
            "backup": str(backup),
            "backupSha256": sha256_bytes(original),
            "beforeSha256": args.expected_before_sha256,
            "installedSha256": installed_sha,
            "markerCount": transformed.count(MARKER_BEGIN.encode()),
        }
    )


def verify_transform(args: argparse.Namespace) -> None:
    target, backup = validate_paths(args)
    installed = read_fd_checked(
        target,
        expected_sha=args.expected_installed_sha256,
        expected_mode=0o700,
        args=args,
    )
    original = read_backup(backup, args)
    text = installed.decode("utf-8")
    if text.count(MARKER_BEGIN) != 1 or text.count(MARKER_END) != 1:
        raise SystemExit("managed exporter marker must occur exactly once")
    emit(
        {
            "action": "verify",
            "backupSha256": sha256_bytes(original),
            "installedSha256": sha256_bytes(installed),
            "markerCount": 1,
        }
    )


def restore_transform(args: argparse.Namespace) -> None:
    target, backup = validate_paths(args)
    read_fd_checked(
        target,
        expected_sha=args.expected_installed_sha256,
        expected_mode=0o700,
        args=args,
    )
    original = read_backup(backup, args)
    atomic_replace(target, original, args)
    read_fd_checked(
        target, expected_sha=args.expected_before_sha256, expected_mode=0o700, args=args
    )
    emit(
        {
            "action": "restore",
            "restoredSha256": sha256_bytes(original),
            "expectedSha256": args.expected_before_sha256,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preview", "apply", "reapply", "verify", "restore"))
    parser.add_argument("--file", required=True)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--expected-before-sha256", required=True)
    parser.add_argument("--expected-installed-sha256")
    parser.add_argument("--sandbox", action="store_true")
    args = parser.parse_args()
    if args.sandbox and os.environ.get("KARO_TEST_CONTEXT") != "candidate":
        parser.error("--sandbox is restricted to KARO_TEST_CONTEXT=candidate")
    if args.mode in ("apply", "reapply", "verify", "restore") and not args.expected_installed_sha256:
        parser.error("--expected-installed-sha256 is required")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    {
        "preview": preview,
        "apply": apply_transform,
        "reapply": reapply_transform,
        "verify": verify_transform,
        "restore": restore_transform,
    }[parsed.mode](parsed)
