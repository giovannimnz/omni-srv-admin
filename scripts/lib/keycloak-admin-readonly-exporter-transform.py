#!/usr/bin/env python3
"""Deterministically add, verify, or roll back one Vault export profile.

The transform never reads Vault. It only edits the exporter after exact hash,
mode, owner, marker, and backup checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import tempfile


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
    if args.sandbox:
        return os.getuid(), os.getgid()
    return 0, 0


def read_checked(path: pathlib.Path, expected_sha: str, args: argparse.Namespace) -> bytes:
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise SystemExit(f"{path} is not a regular file")
    expected_uid, expected_gid = expected_owner(args)
    if metadata.st_uid != expected_uid or metadata.st_gid != expected_gid:
        raise SystemExit(f"{path} owner/group mismatch")
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise SystemExit(f"{path} must be mode 0700")
    data = path.read_bytes()
    actual_sha = sha256_bytes(data)
    if actual_sha != expected_sha:
        raise SystemExit(f"{path} sha256 drift: expected {expected_sha}, got {actual_sha}")
    return data


def atomic_replace(path: pathlib.Path, data: bytes, mode: int, args: argparse.Namespace) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = pathlib.Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        expected_uid, expected_gid = expected_owner(args)
        os.chown(path, expected_uid, expected_gid)
        os.chmod(path, mode)
    finally:
        if temporary.exists():
            temporary.unlink()


def emit(value: dict[str, object]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def apply_transform(args: argparse.Namespace) -> None:
    target = pathlib.Path(args.file)
    backup = pathlib.Path(args.backup)
    source = read_checked(target, args.expected_before_sha256, args)
    text = source.decode("utf-8")
    if MARKER_BEGIN in text or MARKER_END in text or "keycloak-admin-readonly" in text:
        raise SystemExit("exporter already contains the managed profile or a conflicting profile token")
    first_line, separator, remainder = text.partition("\n")
    if not separator or first_line not in ("#!/usr/bin/env bash", "#!/bin/bash"):
        raise SystemExit("exporter must have a supported bash shebang")
    backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(backup, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        backup.unlink(missing_ok=True)
        raise
    expected_uid, expected_gid = expected_owner(args)
    os.chown(backup, expected_uid, expected_gid)
    os.chmod(backup, 0o600)
    transformed = f"{first_line}\n{PROFILE_BLOCK.lstrip()}\n{remainder}".encode()
    atomic_replace(target, transformed, 0o700, args)
    installed_sha = sha256_bytes(transformed)
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


def reapply_transform(args: argparse.Namespace) -> None:
    target = pathlib.Path(args.file)
    backup = pathlib.Path(args.backup)
    source = read_checked(target, args.expected_before_sha256, args)
    original = backup.read_bytes()
    if sha256_bytes(original) != args.expected_before_sha256:
        raise SystemExit("refusing reapply: retained backup sha256 mismatch")
    expected_uid, expected_gid = expected_owner(args)
    if (
        stat.S_IMODE(backup.stat().st_mode) != 0o600
        or backup.stat().st_uid != expected_uid
        or backup.stat().st_gid != expected_gid
    ):
        raise SystemExit("refusing reapply: retained backup mode/owner mismatch")
    text = source.decode("utf-8")
    if MARKER_BEGIN in text or MARKER_END in text or "keycloak-admin-readonly" in text:
        raise SystemExit("refusing reapply: restored exporter is not the exact clean preimage")
    first_line, separator, remainder = text.partition("\n")
    if not separator or first_line not in ("#!/usr/bin/env bash", "#!/bin/bash"):
        raise SystemExit("exporter must have a supported bash shebang")
    transformed = f"{first_line}\n{PROFILE_BLOCK.lstrip()}\n{remainder}".encode()
    atomic_replace(target, transformed, 0o700, args)
    emit(
        {
            "action": "reapply",
            "backup": str(backup),
            "backupSha256": sha256_bytes(original),
            "beforeSha256": args.expected_before_sha256,
            "installedSha256": sha256_bytes(transformed),
            "markerCount": transformed.count(MARKER_BEGIN.encode()),
        }
    )


def verify_transform(args: argparse.Namespace) -> None:
    target = pathlib.Path(args.file)
    backup = pathlib.Path(args.backup)
    installed = read_checked(target, args.expected_installed_sha256, args)
    original = backup.read_bytes()
    if sha256_bytes(original) != args.expected_before_sha256:
        raise SystemExit("backup sha256 mismatch")
    expected_uid, expected_gid = expected_owner(args)
    if (
        stat.S_IMODE(backup.stat().st_mode) != 0o600
        or backup.stat().st_uid != expected_uid
        or backup.stat().st_gid != expected_gid
    ):
        raise SystemExit("backup mode/owner mismatch")
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
    target = pathlib.Path(args.file)
    backup = pathlib.Path(args.backup)
    read_checked(target, args.expected_installed_sha256, args)
    original = backup.read_bytes()
    backup_sha = sha256_bytes(original)
    if backup_sha != args.expected_before_sha256:
        raise SystemExit("refusing restore: backup sha256 mismatch")
    atomic_replace(target, original, 0o700, args)
    restored = read_checked(target, args.expected_before_sha256, args)
    emit(
        {
            "action": "restore",
            "restoredSha256": sha256_bytes(restored),
            "expectedSha256": args.expected_before_sha256,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("apply", "reapply", "verify", "restore"))
    parser.add_argument("--file", required=True)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--expected-before-sha256", required=True)
    parser.add_argument("--expected-installed-sha256")
    parser.add_argument("--sandbox", action="store_true")
    args = parser.parse_args()
    if args.sandbox and os.environ.get("KARO_TEST_CONTEXT") != "candidate":
        parser.error("--sandbox is restricted to KARO_TEST_CONTEXT=candidate")
    if args.mode in ("verify", "restore") and not args.expected_installed_sha256:
        parser.error("--expected-installed-sha256 is required for verify/restore")
    return args


if __name__ == "__main__":
    parsed = parse_args()
    if parsed.mode == "apply":
        apply_transform(parsed)
    elif parsed.mode == "reapply":
        reapply_transform(parsed)
    elif parsed.mode == "verify":
        verify_transform(parsed)
    else:
        restore_transform(parsed)
