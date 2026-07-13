#!/usr/bin/env python3
"""Reconcile the ATIUS collaboration/browser policy in global and project AGENTS.md files."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tarfile
import tempfile
from datetime import datetime, timezone


START = b"<!-- codex-policy:parallel-headless:start -->"
END = b"<!-- codex-policy:parallel-headless:end -->"
BLOCK = b"""<!-- codex-policy:parallel-headless:start -->
## Paralelismo e automacao de browser

- Use multiplos subagentes sempre que houver trabalho paralelo util. Atribua objetivos delimitados e sem sobreposicao, depois integre e valide os resultados no agente principal.
- Toda automacao de browser deve executar em modo headless, incluindo chrome-devtools, Playwright, Selenium, Puppeteer ou ferramenta equivalente. Nao abra janelas visiveis do browser.

<!-- codex-policy:parallel-headless:end -->"""

EXCLUDED_DIRS = {
    ".git",
    ".cache",
    ".npm",
    ".cargo",
    ".rustup",
    ".venv",
    "venv",
    "node_modules",
    "target",
    "dist",
    "out",
    "build",
    "cache",
    "caches",
    "__pycache__",
    ".tmp",
    "Trash",
}


def reconcile_bytes(content: bytes) -> tuple[bytes, bool]:
    starts = content.count(START)
    ends = content.count(END)
    if starts > 1 or ends > 1 or starts != ends:
        raise ValueError("incomplete or duplicated managed policy markers")
    if starts == 1:
        start = content.index(START)
        end = content.index(END, start) + len(END)
        updated = content[:start] + BLOCK + content[end:]
    else:
        updated = content.rstrip() + b"\n\n" + BLOCK + b"\n"
    return updated, updated != content


def discover(global_file: Path | None, roots: list[Path]) -> list[Path]:
    found: set[Path] = set()
    if global_file and global_file.is_file() and not global_file.is_symlink():
        found.add(global_file.resolve())
    for root in roots:
        if not root.is_dir():
            continue
        for current, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS]
            if "AGENTS.md" not in files:
                continue
            candidate = Path(current, "AGENTS.md")
            if candidate.is_file() and not candidate.is_symlink():
                found.add(candidate.resolve())
    return sorted(found, key=lambda path: str(path).lower())


def backup_targets(paths: list[Path], backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = backup_dir / f"agents-policy-{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in paths:
            drive = path.drive.replace(":", "") or "root"
            relative = str(path).replace("\\", "/").lstrip("/")
            tar.add(path, arcname=f"{drive}/{relative}", recursive=False)
    return archive


def atomic_write(path: Path, content: bytes) -> None:
    stat = path.stat()
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temp = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temp, stat.st_mode)
        if hasattr(os, "chown"):
            os.chown(temp, stat.st_uid, stat.st_gid)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--global-file")
    parser.add_argument("--backup-dir")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    paths = discover(Path(args.global_file) if args.global_file else None, [Path(root) for root in args.root])
    pending: list[tuple[Path, bytes]] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        try:
            updated, changed = reconcile_bytes(path.read_bytes())
            if changed:
                pending.append((path, updated))
        except (OSError, ValueError) as error:
            errors.append({"path": str(path), "error": str(error)})

    archive = None
    if args.apply and pending and not errors:
        if not args.backup_dir:
            parser.error("--backup-dir is required with --apply")
        archive = backup_targets([path for path, _ in pending], Path(args.backup_dir))
        for path, content in pending:
            atomic_write(path, content)

    result = {
        "mode": "apply" if args.apply else "dry-run",
        "targets": len(paths),
        "changed": len(pending),
        "unchanged": len(paths) - len(pending) - len(errors),
        "errors": errors,
        "backup": str(archive) if archive else None,
    }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
