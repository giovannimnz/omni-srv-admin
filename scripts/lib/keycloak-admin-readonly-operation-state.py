#!/usr/bin/env python3
"""Append-only, no-follow operation journal for the Keycloak readonly harness."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import stat
import sys
import tempfile


LIVE_ROOT = pathlib.Path("/var/lib/atius-keycloak-admin-readonly/operations")
OPERATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
EVENT_RE = re.compile(r"^[0-9]{3}-[a-z0-9-]{3,64}\.json$")


def root_path() -> pathlib.Path:
    if os.environ.get("KARO_TEST_CONTEXT") == "candidate":
        raw = os.environ.get("KARO_TEST_OPERATION_ROOT")
        if not raw:
            raise SystemExit("KARO_TEST_OPERATION_ROOT is required in candidate tests")
        root = pathlib.Path(raw).resolve()
        if root == pathlib.Path("/") or not root.is_dir():
            raise SystemExit("invalid candidate operation root")
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
            raise SystemExit("candidate operation root must be a 0700 directory")
        return root
    if os.geteuid() != 0:
        raise SystemExit("live operation journal requires root")
    return LIVE_ROOT


def operation_dir(operation_id: str) -> pathlib.Path:
    if not OPERATION_RE.fullmatch(operation_id):
        raise SystemExit("invalid operation id")
    root = root_path()
    directory = root / operation_id
    root_real = root.resolve(strict=True)
    parent_real = directory.parent.resolve(strict=True)
    if parent_real != root_real:
        raise SystemExit("operation directory escapes fixed root")
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise SystemExit("operation path is not a real directory")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("operation directory mode must be 0700")
    return directory


def read_payload() -> dict:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise SystemExit("journal payload must be an object")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    lowered = serialized.lower()
    for forbidden in (
        "kc_recovery_admin_password",
        "keycloak_readonly_client_secret",
        '"access_token"',
        '"refresh_token"',
        '"client_secret"',
    ):
        if forbidden in lowered:
            raise SystemExit("secret-bearing keys are forbidden in operation journal")
    return payload


def write_exclusive(directory: pathlib.Path, filename: str, payload: dict) -> None:
    if filename not in ("claim.json", "terminal.json") and not EVENT_RE.fullmatch(filename):
        raise SystemExit("invalid journal filename")
    directory_fd = os.open(
        directory,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(filename, flags, 0o600, dir_fd=directory_fd)
        try:
            encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("event", "terminal"))
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--event-file")
    args = parser.parse_args()
    directory = operation_dir(args.operation_id)
    payload = read_payload()
    if payload.get("operationId") != args.operation_id:
        raise SystemExit("journal operationId mismatch")
    if args.kind == "event":
        if not args.event_file:
            raise SystemExit("--event-file is required")
        write_exclusive(directory, args.event_file, payload)
    else:
        if args.event_file:
            raise SystemExit("--event-file is invalid for terminal")
        write_exclusive(directory, "terminal.json", payload)


if __name__ == "__main__":
    main()
