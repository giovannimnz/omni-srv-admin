#!/usr/bin/env python3
"""Keep browser MIME defaults stable without invoking desktop portals."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from datetime import datetime, timezone

DEFAULT_SECTION = "Default Applications"
BROWSER_KEYS = (
    "text/html",
    "x-scheme-handler/http",
    "x-scheme-handler/https",
)
CODEX_KEY = "x-scheme-handler/codex"
DESKTOP_RE = re.compile(r"^[A-Za-z0-9._+-]+\.desktop$")


def _section_bounds(lines: list[str], section: str) -> tuple[int, int] | None:
    header = f"[{section}]"
    start = None
    for index, line in enumerate(lines):
        if line.strip() == header:
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break
    return start, end


def reconcile_text(
    source: str,
    browser_desktop: str,
    codex_desktop: str = "chatgpt.desktop",
) -> tuple[str, bool]:
    """Upsert managed defaults while preserving unrelated bytes and order."""
    for value in (browser_desktop, codex_desktop):
        if not DESKTOP_RE.fullmatch(value):
            raise ValueError(f"invalid desktop entry: {value!r}")

    had_trailing_newline = source.endswith("\n")
    lines = source.splitlines()
    bounds = _section_bounds(lines, DEFAULT_SECTION)
    if bounds is None:
        if lines and lines[-1] != "":
            lines.append("")
        start = len(lines)
        lines.append(f"[{DEFAULT_SECTION}]")
        end = len(lines)
    else:
        start, end = bounds

    desired = {key: browser_desktop for key in BROWSER_KEYS}
    desired[CODEX_KEY] = codex_desktop
    managed = set(desired)
    seen: set[str] = set()
    body: list[str] = []
    for line in lines[start + 1 : end]:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key not in managed:
            body.append(line)
            continue
        if key in seen:
            continue
        body.append(f"{key}={desired[key]}")
        seen.add(key)
    for key in (*BROWSER_KEYS, CODEX_KEY):
        if key not in seen:
            body.append(f"{key}={desired[key]}")

    output_lines = lines[: start + 1] + body + lines[end:]
    output = "\n".join(output_lines)
    if had_trailing_newline or output:
        output += "\n"
    return output, output != source


def _write_in_place(path: Path, content: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    os.chmod(path, mode)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        tmp.unlink(missing_ok=True)


def reconcile_file(
    mimeapps: Path,
    state_path: Path,
    lock_path: Path,
    browser_desktop: str,
    codex_desktop: str,
) -> dict[str, object]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(mode=0o600, exist_ok=True)
    os.chmod(lock_path, 0o600)
    with lock_path.open("r+") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        source = mimeapps.read_text(encoding="utf-8") if mimeapps.exists() else ""
        mode = stat.S_IMODE(mimeapps.stat().st_mode) if mimeapps.exists() else 0o644
        output, changed = reconcile_text(source, browser_desktop, codex_desktop)
        if changed:
            _write_in_place(mimeapps, output, mode)
        payload: dict[str, object] = {
            "status": "success",
            "changed": changed,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "mimeapps": str(mimeapps),
            "browser_desktop": browser_desktop,
            "handlers": {
                **{key: browser_desktop for key in BROWSER_KEYS},
                CODEX_KEY: codex_desktop,
            },
        }
        _atomic_json(state_path, payload)
        return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mimeapps", type=Path, default=Path.home() / ".config/mimeapps.list")
    parser.add_argument("--state", type=Path, default=Path.home() / ".local/state/omni/browser-default-reconciler.json")
    parser.add_argument("--lock", type=Path, default=Path.home() / ".local/state/omni/browser-default-reconciler.lock")
    parser.add_argument("--browser-desktop", required=True)
    parser.add_argument("--codex-desktop", default="chatgpt.desktop")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = reconcile_file(
        args.mimeapps,
        args.state,
        args.lock,
        args.browser_desktop,
        args.codex_desktop,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
