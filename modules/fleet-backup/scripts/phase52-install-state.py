#!/usr/bin/env python3
"""Transactional install/rollback state for the Horistic Phase 52 backup tools."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import tempfile
from typing import Any


SCHEMA = "atius-fleet-backup-phase52-install-v2"
GENERATION_RE = re.compile(r"^[0-9a-f]{32}$")
TARGET_ROWS = (
    ("scripts/rclone-copy-verified-phase52.sh", ".local/bin/rclone-copy-verified-phase52", 0o700),
    ("scripts/atius-rclone-vault-hydrate", ".local/bin/atius-rclone-vault-hydrate", 0o700),
    ("configs/fleet-backup-map.yaml", ".config/atius/fleet-backup/fleet-backup-map.yaml", 0o600),
)
os.umask(0o077)


class StateError(RuntimeError):
    pass


class TransactionInterrupted(StateError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path) -> str:
    info = path.lstat()
    return ":".join(
        str(value)
        for value in (
            info.st_dev,
            info.st_ino,
            info.st_uid,
            info.st_nlink,
            stat.S_IMODE(info.st_mode),
            info.st_size,
        )
    )


def canonical_existing(path: Path, *, directory: bool) -> Path:
    if not path.is_absolute():
        raise StateError("path-not-absolute")
    resolved = path.resolve(strict=True)
    if resolved != path or path.is_symlink():
        raise StateError("path-not-canonical")
    if directory and not path.is_dir():
        raise StateError("directory-required")
    if not directory and not path.is_file():
        raise StateError("file-required")
    return path


def secure_directory(path: Path, *, exact_mode: int | None = None) -> None:
    canonical_existing(path, directory=True)
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if info.st_uid != os.getuid() or mode & 0o022:
        raise StateError("directory-owner-or-mode")
    if exact_mode is not None and mode != exact_mode:
        raise StateError("directory-mode")


def secure_chain(home: Path, parent: Path) -> None:
    canonical_existing(home, directory=True)
    canonical_existing(parent, directory=True)
    try:
        relative = parent.relative_to(home)
    except ValueError as exc:
        raise StateError("parent-outside-home") from exc
    current = home
    secure_directory(current)
    for part in relative.parts:
        current = current / part
        secure_directory(current)


def secure_prospective_chain(home: Path, parent: Path) -> None:
    """Reject unsafe/symlink ancestors before mkdir can follow them."""
    if not parent.is_absolute():
        raise StateError("parent-not-absolute")
    try:
        relative = parent.relative_to(home)
    except ValueError as exc:
        raise StateError("parent-outside-home") from exc
    current = home
    secure_directory(current)
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            secure_directory(current)
        else:
            break


def secure_file(path: Path, *, mode: int | None = None) -> None:
    canonical_existing(path, directory=False)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise StateError("file-identity")
    if mode is not None and stat.S_IMODE(info.st_mode) != mode:
        raise StateError("file-mode")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StateError("duplicate-json-key")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    secure_file(path, mode=0o600)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StateError("manifest-invalid-json") from exc
    if not isinstance(payload, dict):
        raise StateError("manifest-shape")
    return payload


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def copy_exclusive(source: Path, destination: Path, mode: int) -> None:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with source.open("rb") as input_handle, os.fdopen(descriptor, "wb") as output_handle:
            shutil.copyfileobj(input_handle, output_handle)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.chmod(destination, mode)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def copy_stable(source: Path, destination: Path, mode: int) -> tuple[str, str]:
    before_identity = identity(source)
    before_hash = sha256(source)
    copy_exclusive(source, destination, mode)
    if identity(source) != before_identity or sha256(source) != before_hash or sha256(destination) != before_hash:
        destination.unlink(missing_ok=True)
        raise StateError("source-snapshot-unstable")
    return before_identity, before_hash


def specs(home: Path, module: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_relative, target_relative, mode in TARGET_ROWS:
        source = module / source_relative
        target = home / target_relative
        rows.append({"source": source, "target": target, "mode": mode})
    return rows


def prepare_parents(home: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        target: Path = row["target"]
        secure_prospective_chain(home, target.parent)
        existed = target.parent.exists()
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if target.parent == home / ".config/atius/fleet-backup":
            if existed:
                secure_directory(target.parent, exact_mode=0o700)
            else:
                os.chmod(target.parent, 0o700)
        secure_chain(home, target.parent)


def validate_sources(module: Path, rows: list[dict[str, Any]]) -> None:
    canonical_existing(module, directory=True)
    for row in rows:
        source: Path = row["source"]
        secure_file(source)
        if source.parent.resolve(strict=True) != source.parent:
            raise StateError("source-parent-not-canonical")


def expected_targets(home: Path) -> list[str]:
    return [str(home / target) for _, target, _ in TARGET_ROWS]


def validate_state_dir(home: Path, state_dir: Path) -> None:
    secure_directory(state_dir, exact_mode=0o700)
    expected_root = home / ".local/state/atius-fleet-backup"
    secure_directory(expected_root, exact_mode=0o700)
    if state_dir.parent != expected_root:
        raise StateError("state-dir-outside-root")


def validate_manifest(home: Path, state_dir: Path, *, required_status: str) -> dict[str, Any]:
    validate_state_dir(home, state_dir)
    manifest_path = state_dir / "manifest.json"
    payload = load_json(manifest_path)
    expected_keys = {
        "schema",
        "generation_id",
        "home",
        "state_dir",
        "status",
        "targets",
        "created_at",
        "installed_at",
        "consumed_at",
    }
    if set(payload) != expected_keys:
        raise StateError("manifest-keys")
    generation = payload.get("generation_id")
    if (
        payload.get("schema") != SCHEMA
        or not isinstance(generation, str)
        or not GENERATION_RE.fullmatch(generation)
        or payload.get("home") != str(home)
        or payload.get("state_dir") != str(state_dir)
        or payload.get("status") != required_status
        or state_dir.name != f"phase52-{generation}"
    ):
        raise StateError("manifest-header")
    marker = state_dir / ".generation"
    secure_file(marker, mode=0o600)
    if marker.read_text(encoding="ascii") != f"{generation}\n":
        raise StateError("generation-marker")
    targets = payload.get("targets")
    if not isinstance(targets, list) or len(targets) != len(TARGET_ROWS):
        raise StateError("manifest-target-count")
    if [row.get("target") for row in targets if isinstance(row, dict)] != expected_targets(home):
        raise StateError("manifest-targets")
    expected_record_keys = {
        "source",
        "source_sha256",
        "target",
        "mode",
        "previous",
        "backup_basename",
        "backup_sha256",
        "previous_mode",
        "previous_identity",
        "installed_identity",
    }
    for index, record in enumerate(targets):
        if not isinstance(record, dict) or set(record) != expected_record_keys:
            raise StateError("manifest-target-shape")
        if record.get("mode") != TARGET_ROWS[index][2]:
            raise StateError("manifest-target-mode")
        if not isinstance(record.get("source_sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", record["source_sha256"]
        ):
            raise StateError("manifest-source-hash")
        previous = record.get("previous")
        backup_basename = record.get("backup_basename")
        if previous is True:
            if backup_basename != f"previous-{index}" or Path(backup_basename).name != backup_basename:
                raise StateError("manifest-backup-name")
            backup = state_dir / backup_basename
            secure_file(backup)
            if sha256(backup) != record.get("backup_sha256"):
                raise StateError("manifest-backup-hash")
            if not isinstance(record.get("previous_mode"), int) or not isinstance(
                record.get("previous_identity"), str
            ):
                raise StateError("manifest-previous-metadata")
        elif previous is False:
            if any(record.get(key) is not None for key in ("backup_basename", "backup_sha256", "previous_mode", "previous_identity")):
                raise StateError("manifest-absent-metadata")
        else:
            raise StateError("manifest-previous")
        installed_identity = record.get("installed_identity")
        if required_status == "captured" and installed_identity is not None:
            raise StateError("manifest-installed-identity")
        if required_status == "installed" and not isinstance(installed_identity, str):
            raise StateError("manifest-installed-identity")
    return payload


def emit(status: str, **extra: Any) -> None:
    print(json.dumps({"status": status, "secret_material_present": False, **extra}, sort_keys=True))


def preflight(home: Path, module: Path) -> None:
    secure_directory(home)
    rows = specs(home, module)
    validate_sources(module, rows)
    for row in rows:
        secure_prospective_chain(home, row["target"].parent)
    emit("PASS", action="preflight", target_count=len(rows))


def capture(home: Path, module: Path, state_dir: Path, generation: str) -> None:
    if not GENERATION_RE.fullmatch(generation):
        raise StateError("generation-invalid")
    secure_directory(home)
    rows = specs(home, module)
    validate_sources(module, rows)
    prepare_parents(home, rows)
    state_root = state_dir.parent
    secure_prospective_chain(home, state_root)
    state_root_existed = state_root.exists()
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if state_root_existed:
        secure_directory(state_root, exact_mode=0o700)
    else:
        os.chmod(state_root, 0o700)
    secure_chain(home, state_root)
    if state_dir.exists() or state_dir.is_symlink() or state_dir.name != f"phase52-{generation}":
        raise StateError("state-dir-preexists-or-name")
    state_dir.mkdir(mode=0o700)
    previous_signals = transaction_signals()
    records: list[dict[str, Any]] = []
    try:
        marker = state_dir / ".generation"
        marker.write_text(f"{generation}\n", encoding="ascii")
        marker.chmod(0o600)
        for index, row in enumerate(rows):
            source: Path = row["source"]
            target: Path = row["target"]
            source_hash = sha256(source)
            record: dict[str, Any] = {
                "source": str(source),
                "source_sha256": source_hash,
                "target": str(target),
                "mode": row["mode"],
                "previous": False,
                "backup_basename": None,
                "backup_sha256": None,
                "previous_mode": None,
                "previous_identity": None,
                "installed_identity": None,
            }
            if target.exists() or target.is_symlink():
                secure_file(target)
                backup_basename = f"previous-{index}"
                backup = state_dir / backup_basename
                previous_identity, previous_hash = copy_stable(
                    target, backup, stat.S_IMODE(target.stat().st_mode)
                )
                record.update(
                    previous=True,
                    backup_basename=backup_basename,
                    backup_sha256=previous_hash,
                    previous_mode=stat.S_IMODE(target.stat().st_mode),
                    previous_identity=previous_identity,
                )
            records.append(record)
        manifest = {
            "schema": SCHEMA,
            "generation_id": generation,
            "home": str(home),
            "state_dir": str(state_dir),
            "status": "captured",
            "targets": records,
            "created_at": now(),
            "installed_at": None,
            "consumed_at": None,
        }
        atomic_json(state_dir / "manifest.json", manifest)
        validate_manifest(home, state_dir, required_status="captured")
    except BaseException:
        for child in state_dir.iterdir():
            if child.is_file() and not child.is_symlink():
                child.unlink(missing_ok=True)
        state_dir.rmdir()
        raise
    finally:
        restore_signals(previous_signals)
    emit("PASS", action="capture", generation_id=generation, state_dir=str(state_dir))


def stage_file(source: Path, parent: Path, mode: int) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".phase52-install.", dir=parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, mode)
        with source.open("rb") as input_handle, os.fdopen(descriptor, "wb") as output_handle:
            shutil.copyfileobj(input_handle, output_handle)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def restore_captured(state_dir: Path, records: list[dict[str, Any]]) -> None:
    for record in records:
        target = Path(record["target"])
        if record["previous"]:
            backup = state_dir / record["backup_basename"]
            temporary = stage_file(backup, target.parent, record["previous_mode"])
            os.replace(temporary, target)
        else:
            target.unlink(missing_ok=True)


def compensate_install(state_dir: Path, manifest: dict[str, Any]) -> None:
    """Restore captured state from filesystem reality, including post-replace exceptions."""
    records: list[dict[str, Any]] = manifest["targets"]
    for record in records:
        target = Path(record["target"])
        if target.exists() and not target.is_symlink():
            current_hash = sha256(target)
            if current_hash == record["source_sha256"]:
                continue
            if record["previous"] and current_hash == record["backup_sha256"]:
                continue
        elif not record["previous"]:
            continue
        raise StateError("install-compensation-ambiguous")
    restore_captured(state_dir, records)
    manifest["status"] = "captured"
    manifest["installed_at"] = None
    for record in records:
        record["installed_identity"] = None
    atomic_json(state_dir / "manifest.json", manifest)


def signal_handler(signum: int, _frame: Any) -> None:
    raise TransactionInterrupted(f"signal-{signum}")


def transaction_signals() -> dict[int, Any]:
    previous: dict[int, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[sig] = signal.signal(sig, signal_handler)
    return previous


def restore_signals(previous: dict[int, Any]) -> None:
    for sig, handler in previous.items():
        signal.signal(sig, handler)


def install(home: Path, module: Path, state_dir: Path) -> None:
    rows = specs(home, module)
    validate_sources(module, rows)
    manifest = validate_manifest(home, state_dir, required_status="captured")
    records: list[dict[str, Any]] = manifest["targets"]
    for row, record in zip(rows, records, strict=True):
        source: Path = row["source"]
        target: Path = row["target"]
        if str(source) != record["source"] or sha256(source) != record["source_sha256"]:
            raise StateError("source-stale")
        if record["previous"]:
            secure_file(target)
            if identity(target) != record["previous_identity"]:
                raise StateError("target-stale-before-install")
        elif target.exists() or target.is_symlink():
            raise StateError("target-appeared-before-install")
    previous_signals = transaction_signals()
    staged: list[Path] = []
    try:
        for row in rows:
            temporary = stage_file(row["source"], row["target"].parent, row["mode"])
            expected_hash = records[len(staged)]["source_sha256"]
            if sha256(temporary) != expected_hash:
                temporary.unlink(missing_ok=True)
                raise StateError("staged-install-hash")
            staged.append(temporary)
        for row, temporary in zip(rows, staged, strict=True):
            os.replace(temporary, row["target"])
        for row, record in zip(rows, records, strict=True):
            target: Path = row["target"]
            secure_file(target, mode=row["mode"])
            if sha256(target) != record["source_sha256"]:
                raise StateError("installed-hash")
            record["installed_identity"] = identity(target)
        manifest["status"] = "installed"
        manifest["installed_at"] = now()
        atomic_json(state_dir / "manifest.json", manifest)
    except BaseException:
        compensate_install(state_dir, manifest)
        raise
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)
        restore_signals(previous_signals)
    emit("PASS", action="install", generation_id=manifest["generation_id"], state_dir=str(state_dir))


def rollback(home: Path, state_dir: Path) -> None:
    manifest = validate_manifest(home, state_dir, required_status="installed")
    records: list[dict[str, Any]] = manifest["targets"]
    for record in records:
        target = Path(record["target"])
        secure_chain(home, target.parent)
        secure_file(target, mode=record["mode"])
        if identity(target) != record["installed_identity"] or sha256(target) != record["source_sha256"]:
            raise StateError("stale-rollback-target")
    stashes = [state_dir / f".rollback-current-{index}" for index in range(len(records))]
    if any(path.exists() or path.is_symlink() for path in stashes):
        raise StateError("rollback-stash-preexists")
    previous_signals = transaction_signals()
    staged: list[Path | None] = []
    try:
        for record in records:
            if record["previous"]:
                staged.append(
                    stage_file(
                        state_dir / record["backup_basename"],
                        Path(record["target"]).parent,
                        record["previous_mode"],
                    )
                )
                if sha256(staged[-1]) != record["backup_sha256"]:
                    staged[-1].unlink(missing_ok=True)
                    raise StateError("staged-rollback-hash")
            else:
                staged.append(None)
        for record, stash in zip(records, stashes, strict=True):
            target = Path(record["target"])
            secure_file(target, mode=record["mode"])
            if identity(target) != record["installed_identity"] or sha256(target) != record["source_sha256"]:
                raise StateError("stale-rollback-target")
            os.replace(target, stash)
        for record, temporary in zip(records, staged, strict=True):
            target = Path(record["target"])
            if temporary is not None:
                os.replace(temporary, target)
        manifest["status"] = "consumed"
        manifest["consumed_at"] = now()
        atomic_json(state_dir / "manifest.json", manifest)
    except BaseException:
        for index in range(len(records) - 1, -1, -1):
            target = Path(records[index]["target"])
            stash = stashes[index]
            if stash.exists() and not stash.is_symlink():
                target.unlink(missing_ok=True)
                os.replace(stash, target)
        manifest["status"] = "installed"
        manifest["consumed_at"] = None
        atomic_json(state_dir / "manifest.json", manifest)
        raise
    finally:
        for temporary in staged:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        if manifest["status"] == "consumed":
            for stash in stashes:
                stash.unlink(missing_ok=True)
        restore_signals(previous_signals)
    emit("PASS", action="rollback", consumed=True, generation_id=manifest["generation_id"])


def discard(home: Path, state_dir: Path) -> None:
    manifest = validate_manifest(home, state_dir, required_status="captured")
    for record in manifest["targets"]:
        target = Path(record["target"])
        if record["previous"]:
            secure_file(target, mode=record["previous_mode"])
            if sha256(target) != record["backup_sha256"]:
                raise StateError("discard-target-stale")
        elif target.exists() or target.is_symlink():
            raise StateError("discard-target-appeared")
    for record in manifest["targets"]:
        if record["previous"]:
            (state_dir / record["backup_basename"]).unlink()
    (state_dir / "manifest.json").unlink()
    (state_dir / ".generation").unlink()
    state_dir.rmdir()
    emit("PASS", action="discard", generation_id=manifest["generation_id"])


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("action", choices=("preflight", "capture", "install", "rollback", "discard"))
    result.add_argument("--home", required=True, type=Path)
    result.add_argument("--module-dir", type=Path)
    result.add_argument("--state-dir", type=Path)
    result.add_argument("--generation")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        home = canonical_existing(args.home, directory=True)
        if args.action == "preflight":
            if args.module_dir is None:
                raise StateError("module-dir-required")
            preflight(home, args.module_dir)
        elif args.action == "capture":
            if args.module_dir is None or args.state_dir is None or args.generation is None:
                raise StateError("capture-arguments")
            capture(home, args.module_dir, args.state_dir, args.generation)
        elif args.action == "install":
            if args.module_dir is None or args.state_dir is None:
                raise StateError("install-arguments")
            install(home, args.module_dir, args.state_dir)
        elif args.action == "rollback":
            if args.state_dir is None:
                raise StateError("state-dir-required")
            rollback(home, args.state_dir)
        else:
            if args.state_dir is None:
                raise StateError("state-dir-required")
            discard(home, args.state_dir)
    except (OSError, StateError) as exc:
        emit("BLOCKED", action=args.action, blocker=str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
