#!/usr/bin/env python3
"""Create and verify value-free recursive scope manifests for Phase 52 closeout."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(repo: Path, roots: list[str]) -> dict[str, object]:
    files: dict[str, str] = {}
    for raw in roots:
        root = (repo / raw).resolve()
        if not root.is_dir() or root.is_symlink() or repo not in root.parents and root != repo:
            raise SystemExit(f"invalid scope root: {raw}")
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                files[path.relative_to(repo).as_posix()] = digest(path)
    canonical = "\n".join(f"{name}\t{files[name]}" for name in sorted(files)) + "\n"
    return {
        "schema": "phase52-scoped-manifest-v1",
        "status": "PASS",
        "read_only": True,
        "mutation_performed": False,
        "scope_roots": roots,
        "file_count": len(files),
        "files": files,
        "manifest_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "secret_material_present": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("write", "verify"))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scope", action="append", required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    current = collect(repo, args.scope)
    if args.action == "write":
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        expected = json.loads(args.manifest.read_text(encoding="utf-8"))
        if expected != current:
            raise SystemExit("scoped manifest drift")
    print(json.dumps({"status": "PASS", "file_count": current["file_count"], "manifest_sha256": current["manifest_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
