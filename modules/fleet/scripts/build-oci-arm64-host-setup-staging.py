#!/usr/bin/env python3
"""Build a deterministic OCI ARM64 host setup staging tree.

The staging tree is consumed by modules/fleet/scripts/oci-arm64-host-setup.sh.
It intentionally copies only the allowlisted files, emits SOURCE-MANIFEST.json,
creates a deterministic tar archive, and verifies an extraction readback.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import errno
import os
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterable


SCHEMA = "omni-oci-arm64-host-setup-source-manifest-v1"
DEFAULT_FILE_LIST = Path("modules/fleet/configs/oci-arm64-host-setup-files.txt")
DEFAULT_OUTPUT = Path("/tmp/omni-oci-arm64-host-setup-source")


class BuildError(RuntimeError):
    """Fail-closed staging build error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(raw: str) -> Path:
    value = raw.strip()
    if not value or value.startswith("#"):
        raise BuildError("empty/comment path reached safe_relative")
    posix = PurePosixPath(value)
    if posix.is_absolute() or ".." in posix.parts or any(part == "" for part in posix.parts):
        raise BuildError(f"unsafe path: {value!r}")
    return Path(*posix.parts)


def load_paths(file_list: Path) -> list[Path]:
    rows: list[Path] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(file_list.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rel = safe_relative(stripped)
        key = rel.as_posix()
        if key in seen:
            raise BuildError(f"duplicate path at {file_list}:{lineno}: {key}")
        seen.add(key)
        rows.append(rel)
    if not rows:
        raise BuildError(f"empty file list: {file_list}")
    return sorted(rows, key=lambda item: item.as_posix())


def read_source_file(root: Path, rel: Path) -> tuple[bytes, int]:
    """Read one allowlisted file without following symlinks in any component."""
    if not hasattr(os, "O_NOFOLLOW"):
        raise BuildError("O_NOFOLLOW is required for fail-closed source reads")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptors: list[int] = []
    try:
        current_fd = os.open(root, directory_flags)
        descriptors.append(current_fd)
        for component in rel.parts[:-1]:
            current_fd = os.open(component, directory_flags, dir_fd=current_fd)
            descriptors.append(current_fd)
        leaf_fd = os.open(rel.parts[-1], file_flags, dir_fd=current_fd)
        descriptors.append(leaf_fd)
        st = os.fstat(leaf_fd)
        if not stat.S_ISREG(st.st_mode):
            raise BuildError(f"not a regular file: {rel.as_posix()}")
        with os.fdopen(os.dup(leaf_fd), "rb") as handle:
            data = handle.read()
        return data, stat.S_IMODE(st.st_mode)
    except FileNotFoundError as exc:
        raise BuildError(f"missing source: {rel.as_posix()}") from exc
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise BuildError(f"symlink forbidden: {rel.as_posix()}") from exc
        raise BuildError(f"cannot read source {rel.as_posix()}: {exc}") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def file_record(root: Path, rel: Path) -> dict[str, object]:
    data, mode = read_source_file(root, rel)
    return {
        "path": rel.as_posix(),
        "bytes": len(data),
        "mode": f"{mode:04o}",
        "sha256": sha256_bytes(data),
    }


def write_manifest(staging: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    manifest = {
        "schema": SCHEMA,
        "file_count": len(rows),
        "files": rows,
    }
    target = staging / "SOURCE-MANIFEST.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    target.chmod(0o600)
    return manifest


def verify_manifest_tree(staging: Path, manifest: dict[str, object]) -> None:
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise BuildError("manifest files must be a non-empty list")
    declared = {str(row["path"]) for row in files}
    actual = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*")
        if path.is_file() and path.name != "SOURCE-MANIFEST.json"
    }
    if actual != declared:
        raise BuildError(json.dumps({"missing": sorted(declared - actual), "undeclared": sorted(actual - declared)}))
    for row in files:
        rel = safe_relative(str(row["path"]))
        path = staging / rel
        if path.is_symlink() or not path.is_file():
            raise BuildError(f"invalid staged file: {rel.as_posix()}")
        st = path.stat()
        data = path.read_bytes()
        if len(data) != int(row["bytes"]):
            raise BuildError(f"byte drift: {rel.as_posix()}")
        if f"{stat.S_IMODE(st.st_mode):04o}" != str(row["mode"]):
            raise BuildError(f"mode drift: {rel.as_posix()}")
        if sha256_bytes(data) != row["sha256"]:
            raise BuildError(f"sha drift: {rel.as_posix()}")


def copy_allowlist(root: Path, staging: Path, rels: Iterable[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for rel in rels:
        data, mode = read_source_file(root, rel)
        record = {
            "path": rel.as_posix(),
            "bytes": len(data),
            "mode": f"{mode:04o}",
            "sha256": sha256_bytes(data),
        }
        target = staging / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(int(str(record["mode"]), 8))
        records.append(record)
    return records


def iter_archive_files(staging: Path) -> list[Path]:
    return sorted((path for path in staging.rglob("*") if path.is_file()), key=lambda item: item.relative_to(staging).as_posix())


def create_archive(staging: Path, archive: Path) -> str:
    if archive.exists():
        archive.unlink()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for path in iter_archive_files(staging):
                    rel = path.relative_to(staging).as_posix()
                    info = tar.gettarinfo(str(path), arcname=rel)
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    info.mtime = 0
                    info.pax_headers = {}
                    with path.open("rb") as handle:
                        tar.addfile(info, handle)
    archive.chmod(0o600)
    return sha256_bytes(archive.read_bytes())


def verify_archive(archive: Path, expected: dict[str, object]) -> None:
    with tempfile.TemporaryDirectory(prefix="omni-oci-arm64-host-setup-restore-") as tmp_raw:
        tmp = Path(tmp_raw)
        with tarfile.open(archive, "r:gz") as tar:
            def is_safe_regular(member: tarfile.TarInfo) -> bool:
                rel = PurePosixPath(member.name)
                return (
                    member.isreg()
                    and not rel.is_absolute()
                    and ".." not in rel.parts
                    and bool(rel.parts)
                )

            members = tar.getmembers()
            if len({member.name for member in members}) != len(members):
                raise BuildError("duplicate archive member")
            if not all(is_safe_regular(member) for member in members):
                raise BuildError("archive must contain regular files with safe paths")
            for member in members:
                source = tar.extractfile(member)
                if source is None:
                    raise BuildError(f"archive member unreadable: {member.name}")
                target = tmp / Path(*PurePosixPath(member.name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read())
                target.chmod(stat.S_IMODE(member.mode))
        manifest_path = tmp / "SOURCE-MANIFEST.json"
        if not manifest_path.is_file():
            raise BuildError("archive restore missing SOURCE-MANIFEST.json")
        restored = json.loads(manifest_path.read_text(encoding="utf-8"))
        if restored != expected:
            raise BuildError("archive manifest drift after restore")
        verify_manifest_tree(tmp, restored)


def _validated_destination(root: Path, path: Path, label: str) -> Path:
    raw = path.expanduser().absolute()
    current = Path(raw.anchor)
    for part in raw.parts[1:]:
        current /= part
        if current.is_symlink():
            raise BuildError(f"{label} path contains symlink: {current}")
    resolved = raw.resolve()
    if resolved == root or resolved.is_relative_to(root) or root.is_relative_to(resolved):
        raise BuildError(f"{label} must stay outside repo root and its ancestors")
    return resolved


def _remove_candidate(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif os.path.lexists(path):
        path.unlink()


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def build(root: Path, file_list: Path, output: Path, archive: Path, replace: bool) -> dict[str, object]:
    root = root.resolve()
    file_list = (root / file_list).resolve() if not file_list.is_absolute() else file_list.resolve()
    output = _validated_destination(root, output, "output")
    archive = _validated_destination(root, archive, "archive")
    receipt = _validated_destination(
        root, output.parent / f"{output.name}-BUILD-RECEIPT.json", "receipt"
    )
    targets = (output, archive, receipt)
    for index, left in enumerate(targets):
        for right in targets[index + 1 :]:
            if _paths_overlap(left, right):
                raise BuildError("output, archive, and receipt must be distinct and non-overlapping")
    if not file_list.is_file():
        raise BuildError(f"file list missing: {file_list}")
    if not str(file_list).startswith(str(root) + os.sep):
        raise BuildError("file list must live under repo root")
    if output.exists() and not replace:
        raise BuildError(f"output exists; pass --replace: {output}")
    if archive.exists() and not replace:
        raise BuildError(f"archive exists; pass --replace: {archive}")
    if receipt.exists() and not replace:
        raise BuildError(f"receipt exists; pass --replace: {receipt}")
    if output.exists() and not output.is_dir():
        raise BuildError(f"output must be a directory: {output}")
    if archive.exists() and not archive.is_file():
        raise BuildError(f"archive must be a regular file: {archive}")
    if receipt.exists() and not receipt.is_file():
        raise BuildError(f"receipt must be a regular file: {receipt}")

    output.parent.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{output.name}.candidate-", dir=output.parent))
    archive_dir = Path(tempfile.mkdtemp(prefix=f".{archive.name}.candidate-", dir=archive.parent))
    receipt_dir = Path(tempfile.mkdtemp(prefix=f".{receipt.name}.candidate-", dir=receipt.parent))
    candidate_archive = archive_dir / "archive.tgz"
    candidate_receipt = receipt_dir / "receipt.json"
    backups = {
        output: output.with_name(f".{output.name}.backup-{os.getpid()}"),
        archive: archive.with_name(f".{archive.name}.backup-{os.getpid()}"),
        receipt: receipt.with_name(f".{receipt.name}.backup-{os.getpid()}"),
    }
    for backup in backups.values():
        for target in targets:
            if _paths_overlap(backup, target):
                raise BuildError(f"transaction backup collides with destination: {backup}")
    promoted: list[Path] = []
    committed = False
    try:
        rows = copy_allowlist(root, tmp, load_paths(file_list))
        manifest = write_manifest(tmp, rows)
        verify_manifest_tree(tmp, manifest)
        archive_sha = create_archive(tmp, candidate_archive)
        verify_archive(candidate_archive, manifest)
        result = {
            "status": "PASS",
            "schema": SCHEMA,
            "repo_root": str(root),
            "file_list": str(file_list),
            "output": str(output),
            "archive": str(archive),
            "archive_sha256": archive_sha,
            "manifest_sha256": sha256_bytes((tmp / "SOURCE-MANIFEST.json").read_bytes()),
            "file_count": len(rows),
        }
        candidate_receipt.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        candidate_receipt.chmod(0o600)

        for target, backup in backups.items():
            if os.path.lexists(backup):
                raise BuildError(f"stale transaction backup exists: {backup}")
            if os.path.lexists(target):
                target.rename(backup)
        tmp.rename(output)
        promoted.append(output)
        candidate_archive.rename(archive)
        promoted.append(archive)
        candidate_receipt.rename(receipt)
        promoted.append(receipt)
        committed = True
    except BaseException:
        if not committed:
            for target in reversed(promoted):
                _remove_candidate(target)
            for target, backup in backups.items():
                if os.path.lexists(backup):
                    backup.rename(target)
        raise
    finally:
        for path in (tmp, archive_dir, receipt_dir):
            _remove_candidate(path)
    cleanup_failures: list[str] = []
    for backup in backups.values():
        try:
            _remove_candidate(backup)
        except OSError as exc:
            cleanup_failures.append(f"{backup}: {exc}")
    if cleanup_failures:
        result["backup_cleanup_warning"] = cleanup_failures
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--file-list", type=Path, default=DEFAULT_FILE_LIST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive", type=Path, default=Path("/tmp/omni-oci-arm64-host-setup-source.tgz"))
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = build(args.repo_root, args.file_list, args.output, args.archive, args.replace)
    except BuildError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
