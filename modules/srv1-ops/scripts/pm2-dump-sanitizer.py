#!/usr/bin/env python3
"""Remove globally inherited secrets from PM2 persistence without restarting apps."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any


DEFAULT_DUMPS = (Path.home() / ".pm2" / "dump.pm2", Path.home() / ".pm2" / "dump.pm2.bak")
REMOVE_KEYS = frozenset({"DATABASE_URI", "GSD_WEB_LOGIN_USERNAME", "GSD_WEB_LOGIN_PASSWORD"})
DB_PASSWORD_ALLOWLIST = frozenset({"bybit-account-1002", "horistic-bot-BinanceGiovanni-60-binance"})
DEFAULT_LOCK = Path.home() / ".local" / "state" / "omni" / "pm2-dump-sanitizer.lock"
DEFAULT_STATE = Path.home() / ".local" / "state" / "omni" / "pm2-dump-sanitizer.json"


def sanitize_mapping(value: Any, *, app_name: str) -> int:
    removed = 0
    if isinstance(value, dict):
        for key in list(value):
            if key in REMOVE_KEYS or (key == "DB_PASSWORD" and app_name not in DB_PASSWORD_ALLOWLIST):
                value.pop(key, None)
                removed += 1
                continue
            removed += sanitize_mapping(value[key], app_name=app_name)
    elif isinstance(value, list):
        for item in value:
            removed += sanitize_mapping(item, app_name=app_name)
    return removed


def sanitize_document(document: Any) -> tuple[Any, int]:
    if not isinstance(document, list):
        raise ValueError("PM2 dump root must be a list")
    removed = 0
    for app in document:
        if not isinstance(app, dict):
            raise ValueError("PM2 dump entries must be objects")
        raw_pm2_env = app.get("pm2_env")
        pm2_env: dict[str, Any] = raw_pm2_env if isinstance(raw_pm2_env, dict) else {}
        name = str(app.get("name") or pm2_env.get("name") or "")
        if not name:
            raise ValueError("PM2 dump entry without name")
        removed += sanitize_mapping(app, app_name=name)
    return document, removed


def atomic_write_json(path: Path, document: Any, *, validate_dump: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        # Read back and revalidate before replacing PM2 persistence.
        loaded = json.loads(tmp.read_text(encoding="utf-8"))
        if validate_dump:
            checked, _ = sanitize_document(loaded)
            if checked != document:
                raise ValueError("sanitized PM2 dump failed readback")
        elif loaded != document:
            raise ValueError("JSON state failed readback")
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        tmp.unlink(missing_ok=True)


def sanitize_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "status": "missing", "removed": 0}
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or path.is_symlink():
        raise ValueError(f"unsafe PM2 dump path: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    original = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    sanitized, removed = sanitize_document(document)
    rendered = json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n"
    changed = rendered != original
    if changed:
        atomic_write_json(path, sanitized)
    elif stat.S_IMODE(st.st_mode) != 0o600:
        os.chmod(path, 0o600)
    return {"path": str(path), "status": "changed" if changed else "noop", "removed": removed}


def write_state(path: Path, results: list[dict[str, Any]]) -> None:
    payload = {
        "status": "success",
        "files": results,
        "removed": sum(int(item["removed"]) for item in results),
    }
    atomic_write_json(path, payload, validate_dump=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", action="append", dest="dumps")
    parser.add_argument("--lock", default=str(DEFAULT_LOCK))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    args = parser.parse_args()

    lock = Path(args.lock).expanduser()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock.open("a+")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("pm2-dump-sanitizer: already running")
        return 0

    dumps = tuple(Path(raw).expanduser() for raw in args.dumps) if args.dumps else DEFAULT_DUMPS
    results = [sanitize_file(path) for path in dumps]
    write_state(Path(args.state).expanduser(), results)
    print(json.dumps({"status": "success", "files": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
