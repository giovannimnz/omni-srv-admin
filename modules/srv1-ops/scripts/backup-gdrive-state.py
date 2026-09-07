#!/usr/bin/env python3
"""Atomic resumable state for the SRV-1 GDrive snapshot backup."""

from __future__ import annotations

import argparse
import configparser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_state(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("version") != 1:
        raise SystemExit("invalid backup state")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def validate_config(path: Path, remote: str) -> int:
    parser = configparser.RawConfigParser(strict=True, interpolation=None)
    try:
        with path.open(encoding="utf-8") as handle:
            parser.read_file(handle)
        if parser.sections() != [remote] or parser.defaults():
            raise ValueError("remote contract")
        section = parser[remote]
        if section.get("type") != "drive":
            raise ValueError("backend type")
        required = ("client_id", "client_secret", "token")
        if any(not section.get(key, "").strip() for key in required):
            raise ValueError("dedicated oauth client missing")
    except (OSError, UnicodeError, configparser.Error, ValueError):
        print(json.dumps({"dedicated_oauth_client": False, "remote": remote}, sort_keys=True))
        return 1
    print(json.dumps({"dedicated_oauth_client": True, "remote": remote}, sort_keys=True))
    return 0


def mutate(path: Path, action: str, args: argparse.Namespace) -> int:
    if action == "init":
        if not SAFE_ID.fullmatch(args.snapshot_id):
            raise SystemExit("unsafe snapshot id")
        if path.exists():
            state = read_state(path)
            if state.get("snapshot_id") != args.snapshot_id or state.get("destination") != args.destination:
                raise SystemExit("state identity mismatch")
        else:
            timestamp = now()
            state = {
                "version": 1,
                "snapshot_id": args.snapshot_id,
                "destination": args.destination,
                "status": "pending",
                "started_at": timestamp,
                "updated_at": timestamp,
                "completed_at": None,
                "current_label": None,
                "copied_labels": [],
                "completed_labels": [],
                "skipped_labels": [],
                "attempts": {},
                "last_error_class": None,
                "last_exit_code": None,
            }
            atomic_write(path, state)
        return 0

    state = read_state(path)
    copied = set(state.get("copied_labels", []))
    completed = set(state.get("completed_labels", []))
    skipped = set(state.get("skipped_labels", []))

    if action == "is-complete":
        return 0 if args.label in completed or args.label in skipped else 1

    if action == "is-copied":
        return 0 if args.label in copied else 1

    if action == "show":
        print(json.dumps(state, sort_keys=True))
        return 0

    if action == "status":
        print(state.get("status", "unknown"))
        return 0

    if action == "begin":
        attempts = dict(state.get("attempts", {}))
        attempts[args.label] = int(attempts.get(args.label, 0)) + 1
        state.update(
            status="running",
            current_label=args.label,
            attempts=attempts,
            last_error_class=None,
            last_exit_code=None,
        )
    elif action == "copy-complete":
        copied.add(args.label)
        state.update(
            status="running",
            current_label=args.label,
            copied_labels=sorted(copied),
            last_error_class=None,
            last_exit_code=0,
        )
    elif action == "invalidate-copy":
        copied.discard(args.label)
        completed.discard(args.label)
        state.update(
            status="retryable",
            current_label=args.label,
            copied_labels=sorted(copied),
            completed_labels=sorted(completed),
            last_error_class=args.error_class,
            last_exit_code=args.exit_code,
        )
    elif action == "complete":
        completed.add(args.label)
        state.update(
            status="running",
            current_label=None,
            completed_labels=sorted(completed),
            last_error_class=None,
            last_exit_code=0,
        )
    elif action == "skip":
        skipped.add(args.label)
        state.update(
            status="running",
            current_label=None,
            skipped_labels=sorted(skipped),
            last_error_class=None,
            last_exit_code=0,
        )
    elif action in {"retry", "fail", "quarantine"}:
        state.update(
            status={"retry": "retryable", "fail": "failed", "quarantine": "quarantined"}[action],
            current_label=args.label,
            last_error_class=args.error_class,
            last_exit_code=args.exit_code,
        )
    elif action == "finalize":
        state.update(
            status="complete",
            current_label=None,
            completed_at=now(),
            last_error_class=None,
            last_exit_code=0,
        )
    else:
        raise SystemExit(f"unsupported action: {action}")

    state["updated_at"] = now()
    atomic_write(path, state)
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    root.add_argument("--state", required=True, type=Path)
    sub = root.add_subparsers(dest="action", required=True)

    init = sub.add_parser("init")
    init.add_argument("--snapshot-id", required=True)
    init.add_argument("--destination", required=True)

    for action in ("is-complete", "is-copied", "begin", "copy-complete", "complete", "skip"):
        command = sub.add_parser(action)
        command.add_argument("--label", required=True)

    for action in ("retry", "fail", "quarantine", "invalidate-copy"):
        command = sub.add_parser(action)
        command.add_argument("--label", required=True)
        command.add_argument("--error-class", required=True)
        command.add_argument("--exit-code", required=True, type=int)

    sub.add_parser("finalize")
    sub.add_parser("show")
    sub.add_parser("status")
    validate = sub.add_parser("validate-config")
    validate.add_argument("--config", required=True, type=Path)
    validate.add_argument("--remote", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    if args.action == "validate-config":
        return validate_config(args.config, args.remote)
    return mutate(args.state, args.action, args)


if __name__ == "__main__":
    raise SystemExit(main())
