#!/usr/bin/env python3
"""Versioned direct recovery primitives for the Horistic Phase 52 live drill."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import shutil
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
import time
from typing import Any

STATE_SCHEMA = "phase52-live-drill-state-v2"
RESULT_SCHEMA = "phase52-live-drill-result-v2"
BACKUP_SCHEMA = "phase52-backup-manifest-v2"
ACTIONS = ("preflight", "vault", "backup", "restore", "capacity-finalize", "rollback")
ARCHIVE_MAX_BYTES = 4_294_967_296
SQLITE_MAX_BYTES = 4_294_957_056
CHUNK_BYTES = 1024 * 1024
TAR_BLOCK_BYTES = 512
ARM64_IMAGE_DIGEST = "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
IMMUTABLE_HBBS = f"docker.io/rustdesk/rustdesk-server@{ARM64_IMAGE_DIGEST}"
MUTATION_CLASSES = frozenset({
    "redacted-evidence-write", "ephemeral-vault-hydration", "isolated-source-runtime",
    "isolated-hbbs-container-lifecycle", "state-only-backup-a",
    "state-only-backup-b-local", "state-only-backup-b-remote-create",
    "disposable-isolated-restore-state", "verified-drill-artifact-rollback-removal",
})
RETAINED = ("backup-a", "backup-b-local", "backup-b-remote")
RUSTDESK_REFERENCES = (
    ("kv/atius/rustdesk/server", "private_key"), ("kv/atius/rustdesk/server", "public_key"),
    ("kv/atius/rustdesk/targets/atius-srv-1", "permanent_password"),
    ("kv/atius/rustdesk/targets/atius-srv-2", "permanent_password"),
    ("kv/atius/rustdesk/targets/atius-srv-3", "permanent_password"),
    ("kv/atius/rustdesk/targets/horistic-srv", "permanent_password"),
    ("kv/atius/rustdesk/targets/giovanni-w11-pc", "permanent_password"),
)
ACTION_DETAIL_KEYS = {
    "preflight": {"image", "image_running", "network_mode", "published_ports"},
    "vault": {"reference_count", "provider_api", "public_fingerprint"},
    "backup": {"backup_a", "backup_b", "state_only", "remote_rehash_verified", "sqlite_ready"},
    "restore": {"sqlite_integrity", "sqlite_ready", "public_fingerprint", "image", "image_running", "network_mode", "port_bindings", "public_listener_delta"},
    "capacity-finalize": {"capacity", "actual_backup_a_bytes", "actual_backup_b_bytes"},
    "rollback": {"terminal", "retained_artifacts", "cleanup_pending", "retained_rehash_verified", "remote_rehash_verified", "remote_delete_performed"},
}
os.umask(0o077)


class RecoveryBlocked(RuntimeError):
    pass


def initial_state(transaction_id: str) -> dict[str, Any]:
    if len(transaction_id) != 32 or any(ch not in "0123456789abcdef" for ch in transaction_id):
        raise ValueError("transaction-id-invalid")
    return {
        "schema": STATE_SCHEMA,
        "transaction_id": transaction_id,
        "completed_actions": [],
        "active_action": None,
        "terminal": False,
        "cleanup_pending": [],
        "retained_artifacts": list(RETAINED),
        "secret_material_present": False,
    }


def validate_mutation(mutation: Any) -> None:
    if not isinstance(mutation, dict) or set(mutation) != {
        "performed", "classes", "cleanup_pending", "retained_artifacts"
    }:
        raise RecoveryBlocked("mutation-schema-invalid")
    performed = mutation["performed"]
    classes = mutation["classes"]
    if not isinstance(performed, bool) or not isinstance(classes, list) or len(classes) != len(set(classes)):
        raise RecoveryBlocked("mutation-schema-invalid")
    if performed and not classes:
        raise RecoveryBlocked("mutation-empty-classes")
    if not set(classes).issubset(MUTATION_CLASSES):
        raise RecoveryBlocked("mutation-class-invalid")
    if not isinstance(mutation["cleanup_pending"], list) or not isinstance(mutation["retained_artifacts"], list):
        raise RecoveryBlocked("mutation-schema-invalid")
    if not performed and (classes or mutation["cleanup_pending"]):
        raise RecoveryBlocked("mutation-false-contradiction")


def validate_vault_values(values: Any) -> str:
    expected = {f"{path}#{field}" for path, field in RUSTDESK_REFERENCES}
    if not isinstance(values, dict) or set(values) != expected or not all(
        isinstance(value, str) and value for value in values.values()
    ):
        raise RecoveryBlocked("vault-value-contract-invalid")
    private = values["kv/atius/rustdesk/server#private_key"]
    public = values["kv/atius/rustdesk/server#public_key"]
    try:
        private_raw = base64.b64decode(private, validate=True)
        public_raw = base64.b64decode(public, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RecoveryBlocked("vault-identity-encoding-invalid") from exc
    if len(private_raw) != 64 or len(public_raw) != 32 or private == public:
        raise RecoveryBlocked("vault-identity-encoding-invalid")
    passwords = [
        values[f"{path}#{field}"]
        for path, field in RUSTDESK_REFERENCES
        if field == "permanent_password"
    ]
    if len(passwords) != 5 or len(set(passwords)) != 5 or any(
        len(password) != 32
        or not password.startswith("R")
        or not password[1:].isalnum()
        or not password.isascii()
        for password in passwords
    ):
        raise RecoveryBlocked("vault-password-contract-invalid")
    return hashlib.sha256(public.encode("ascii")).hexdigest()


def validate_transition(action: str, state: dict[str, Any]) -> None:
    if action not in ACTIONS or state.get("schema") != STATE_SCHEMA:
        raise RecoveryBlocked("transition-schema-invalid")
    completed = state.get("completed_actions")
    if not isinstance(completed, list):
        raise RecoveryBlocked("action-history-invalid")
    allowed_prefix = list(ACTIONS[:-1])[: len(completed)]
    valid_terminal = completed[-1:] == ["rollback"] and completed[:-1] == list(ACTIONS[:-1])[:len(completed)-1]
    if completed != allowed_prefix and not valid_terminal:
        raise RecoveryBlocked("action-history-invalid")
    if state.get("terminal"):
        if action == "rollback" and completed[-1:] == ["rollback"]:
            return
        raise RecoveryBlocked("transaction-terminal")
    if action == "rollback":
        return
    expected = ACTIONS[len(completed)] if len(completed) < len(ACTIONS) else None
    if action != expected or state.get("active_action") not in {None, action}:
        raise RecoveryBlocked("action-out-of-order")


def rollback_state(state: dict[str, Any]) -> dict[str, Any]:
    validate_transition("rollback", state)
    if state.get("terminal") and state.get("completed_actions", [])[-1:] == ["rollback"]:
        return state
    rolled = json.loads(json.dumps(state))
    rolled["active_action"] = None
    rolled["cleanup_pending"] = []
    rolled["terminal"] = True
    if rolled["completed_actions"][-1:] != ["rollback"]:
        rolled["completed_actions"].append("rollback")
    return rolled


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_process(
    command: list[str], request: bytes | None = None, *, timeout: int = 900,
    stdout_limit: int = 65_536, stderr_limit: int = 4_096,
) -> tuple[int, bytes, bytes]:
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE if request is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    try:
        if request is not None:
            assert process.stdin is not None
            process.stdin.write(request)
            process.stdin.close()
        assert process.stdout and process.stderr
        selector.register(process.stdout, selectors.EVENT_READ, ("stdout", stdout_limit))
        selector.register(process.stderr, selectors.EVENT_READ, ("stderr", stderr_limit))
        chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
        sizes = {"stdout": 0, "stderr": 0}
        deadline = time.monotonic() + timeout
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            events = selector.select(remaining)
            if not events:
                raise TimeoutError
            for key, _ in events:
                name, limit = key.data
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                sizes[name] += len(chunk)
                if sizes[name] > limit:
                    raise OverflowError
                chunks[name].append(chunk)
        return process.wait(timeout=max(0.01, deadline - time.monotonic())), b"".join(chunks["stdout"]), b"".join(chunks["stderr"])
    except BaseException:
        kill_process_group(process)
        raise
    finally:
        selector.close()


def kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.SubprocessError:
        pass


def validate_action_result(action: str, details: Any) -> None:
    if action not in ACTION_DETAIL_KEYS or not isinstance(details, dict):
        raise RecoveryBlocked("action-result-schema-invalid")
    # Dry-run adds only these public proof fields.
    extra = {"direct_versioned_action", "transaction_root"}
    if set(details) - extra != ACTION_DETAIL_KEYS[action]:
        raise RecoveryBlocked("action-result-schema-invalid")
    public = {key: value for key, value in details.items() if key not in extra}
    digest = lambda value: isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )

    def backup_manifest(value: Any, label: str) -> bool:
        base_keys = {
            "schema", "transaction_id", "label", "generation_id",
            "source_snapshot_sha256", "archive_sha256", "member_sha256",
            "size_bytes", "entries", "mode", "secret_material_present",
            "destination_class",
        }
        expected = base_keys if label == "A" else base_keys | {
            "remote_object", "local_sha256", "remote_sha256", "retention",
        }
        if not isinstance(value, dict) or set(value) != expected:
            return False
        if (
            value.get("schema") != BACKUP_SCHEMA
            or not isinstance(value.get("transaction_id"), str)
            or len(value["transaction_id"]) != 32
            or not digest(value.get("source_snapshot_sha256"))
            or not digest(value.get("archive_sha256"))
            or value.get("member_sha256") != value.get("source_snapshot_sha256")
            or not isinstance(value.get("generation_id"), str)
            or len(value["generation_id"]) != 32
            or any(character not in "0123456789abcdef" for character in value["generation_id"])
            or value.get("label") != label
            or type(value.get("size_bytes")) is not int
            or not 0 < value["size_bytes"] <= ARCHIVE_MAX_BYTES
            or value.get("entries") != ["db_v2.sqlite3"]
            or value.get("mode") != "0600"
            or value.get("secret_material_present") is not False
        ):
            return False
        if label == "A":
            return value.get("destination_class") == "candidate-local"
        retention = value.get("retention")
        expected_prefix = (
            "giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/"
            f"phase52/backup-b/{value['transaction_id']}.tar"
        )
        return (
            value.get("destination_class") == "modules/fleet-backup:gdrive"
            and value.get("remote_object") == expected_prefix
            and value.get("local_sha256") == value.get("archive_sha256")
            and value.get("remote_sha256") == value.get("archive_sha256")
            and isinstance(retention, dict)
            and set(retention) == {"retain_until", "deletion_requires_new_explicit_approval"}
            and retention.get("retain_until") == "phase57-pass-plus-30-days"
            and retention.get("deletion_requires_new_explicit_approval") is True
        )

    valid = False
    if action == "preflight":
        valid = public == {
            "image": IMMUTABLE_HBBS,
            "image_running": False,
            "network_mode": "none",
            "published_ports": [],
        }
    elif action == "vault":
        valid = (
            public.get("reference_count") == len(RUSTDESK_REFERENCES)
            and public.get("provider_api") == "references-v1"
            and digest(public.get("public_fingerprint"))
        )
    elif action == "backup":
        valid = (
            backup_manifest(public.get("backup_a"), "A")
            and backup_manifest(public.get("backup_b"), "B")
            and public.get("state_only") == ["db_v2.sqlite3"]
            and public.get("remote_rehash_verified") is True
            and public.get("sqlite_ready") is True
        )
    elif action == "restore":
        valid = (
            public.get("sqlite_integrity") == "ok"
            and public.get("sqlite_ready") is True
            and digest(public.get("public_fingerprint"))
            and public.get("image") == IMMUTABLE_HBBS
            and public.get("image_running") is True
            and public.get("network_mode") == "none"
            and public.get("port_bindings") == {}
            and public.get("public_listener_delta") == []
        )
    elif action == "capacity-finalize":
        capacity = public.get("capacity")
        valid = (
            isinstance(capacity, dict)
            and capacity.get("status") == "PASS"
            and capacity.get("capacity_finalize_status") == "PASS"
            and all(
                capacity.get(key) is True
                for key in ("pre_disk_ok", "inode_ok", "projected_post_ok", "headroom_ok")
            )
            and all(
                type(public.get(key)) is int and 0 < public[key] <= ARCHIVE_MAX_BYTES
                for key in ("actual_backup_a_bytes", "actual_backup_b_bytes")
            )
        )
    elif action == "rollback":
        retained = public.get("retained_artifacts")
        valid = (
            public.get("terminal") is True
            and retained in ([], list(RETAINED))
            and public.get("cleanup_pending") == []
            and public.get("retained_rehash_verified") is bool(retained)
            and public.get("remote_rehash_verified") is bool(retained)
            and public.get("remote_delete_performed") is False
        )
    if not valid:
        raise RecoveryBlocked("action-result-value-invalid")


def checked_stop_remove(name: str) -> None:
    def exists() -> bool:
        code, output, error = bounded_process(["podman", "container", "exists", name], timeout=30)
        if error or output or code not in {0, 1}:
            raise RecoveryBlocked("container-exists-check-failed")
        return code == 0

    container_absent = not exists()
    if container_absent:
        return
    for command in (["podman", "stop", "--time", "10", name], ["podman", "rm", "-f", name]):
        code, _, error = bounded_process(command, timeout=30)
        if code != 0 or error:
            raise RecoveryBlocked("container-cleanup-failed")
    if exists():
        raise RecoveryBlocked("container-residual")


def container_running(name: str) -> bool:
    code, output, error = bounded_process(["podman", "inspect", "--format", "{{.State.Running}}", name], timeout=30)
    return code == 0 and not error and output.strip() == b"true"


def hbbs_liveness(name: str, state_dir: Path) -> bool:
    sqlite_readiness = state_dir.joinpath("db_v2.sqlite3").is_file()
    return container_running(name) and sqlite_readiness


def wait_hbbs_liveness(
    name: str, state_dir: Path, *, timeout_seconds: float = 15.0, poll_interval: float = 0.1
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while True:
        if hbbs_liveness(name, state_dir):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(poll_interval, remaining))


def strict_json_bytes(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise RecoveryBlocked("duplicate-json-key")
            result[key] = value
        return result
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryBlocked("result-json-invalid") from exc
    if not isinstance(payload, dict):
        raise RecoveryBlocked("result-schema-invalid")
    return payload


def secure_regular(path: Path, *, mode: int = 0o600, maximum: int = ARCHIVE_MAX_BYTES) -> None:
    resolved = path.resolve(strict=True)
    info = path.lstat()
    if resolved != path or path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise RecoveryBlocked("file-identity-invalid")
    if info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != mode:
        raise RecoveryBlocked("file-owner-mode-invalid")
    if info.st_size <= 0 or info.st_size > maximum:
        raise RecoveryBlocked("file-size-invalid")


def normalize_hbbs_sqlite(path: Path) -> None:
    try:
        resolved = path.resolve(strict=True)
        info = path.lstat()
    except OSError as exc:
        raise RecoveryBlocked("file-identity-invalid") from exc
    if (
        resolved != path
        or path.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) not in {0o600, 0o644}
        or info.st_size <= 0
        or info.st_size > SQLITE_MAX_BYTES
    ):
        raise RecoveryBlocked("file-owner-mode-invalid")
    os.chmod(path, 0o600)
    secure_regular(path, maximum=SQLITE_MAX_BYTES)


def sqlite_snapshot(source: Path, destination: Path) -> dict[str, Any]:
    secure_regular(source, maximum=SQLITE_MAX_BYTES)
    if destination.exists() or destination.is_symlink():
        raise RecoveryBlocked("snapshot-destination-exists")
    before = source.stat()
    connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=10)
    try:
        output = sqlite3.connect(destination)
        try:
            connection.backup(output)
            if output.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise RecoveryBlocked("sqlite-integrity-failure")
        finally:
            output.close()
    finally:
        connection.close()
    os.chmod(destination, 0o600)
    after = source.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ):
        destination.unlink(missing_ok=True)
        raise RecoveryBlocked("sqlite-source-changed")
    secure_regular(destination, maximum=SQLITE_MAX_BYTES)
    return {"path": str(destination), "sha256": sha256_file(destination), "size_bytes": destination.stat().st_size}


def canonical_state_tar_size(member_size: int) -> int:
    if type(member_size) is not int or not 0 < member_size <= SQLITE_MAX_BYTES:
        raise RecoveryBlocked("archive-member-size-invalid")
    padded_member = ((member_size + TAR_BLOCK_BYTES - 1) // TAR_BLOCK_BYTES) * TAR_BLOCK_BYTES
    return TAR_BLOCK_BYTES + padded_member + (2 * TAR_BLOCK_BYTES)


def canonical_state_tar_info(member_size: int) -> tarfile.TarInfo:
    canonical_state_tar_size(member_size)
    info = tarfile.TarInfo("db_v2.sqlite3")
    info.size = member_size
    info.mode = 0o600
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    info.type = tarfile.REGTYPE
    info.linkname = ""
    info.devmajor = info.devminor = 0
    info.pax_headers = {}
    return info


def validate_canonical_state_tar(path: Path, expected_member_sha256: str) -> str:
    if not (
        isinstance(expected_member_sha256, str)
        and len(expected_member_sha256) == 64
        and all(character in "0123456789abcdef" for character in expected_member_sha256)
    ):
        raise RecoveryBlocked("archive-member-digest-invalid")
    try:
        with path.open("rb") as source:
            header = source.read(TAR_BLOCK_BYTES)
            if len(header) != TAR_BLOCK_BYTES:
                raise RecoveryBlocked("archive-physical-format-invalid")
            parsed = tarfile.TarInfo.frombuf(header, "utf-8", "strict")
            expected_header = canonical_state_tar_info(parsed.size).tobuf(
                format=tarfile.USTAR_FORMAT, encoding="utf-8", errors="strict"
            )
            if header != expected_header or path.stat().st_size != canonical_state_tar_size(parsed.size):
                raise RecoveryBlocked("archive-physical-format-invalid")
            digest = hashlib.sha256()
            remaining = parsed.size
            while remaining:
                chunk = source.read(min(CHUNK_BYTES, remaining))
                if not chunk:
                    raise RecoveryBlocked("archive-physical-format-invalid")
                digest.update(chunk)
                remaining -= len(chunk)
            padding_size = (-parsed.size) % TAR_BLOCK_BYTES
            if source.read(padding_size) != b"\0" * padding_size:
                raise RecoveryBlocked("archive-physical-format-invalid")
            if source.read(2 * TAR_BLOCK_BYTES) != b"\0" * (2 * TAR_BLOCK_BYTES):
                raise RecoveryBlocked("archive-physical-format-invalid")
            if source.read(1):
                raise RecoveryBlocked("archive-physical-format-invalid")
    except RecoveryBlocked:
        raise
    except (OSError, UnicodeError, ValueError, tarfile.TarError) as exc:
        raise RecoveryBlocked("archive-physical-format-invalid") from exc
    member_digest = digest.hexdigest()
    if member_digest != expected_member_sha256:
        raise RecoveryBlocked("archive-member-mismatch")
    return member_digest


def state_archive(snapshot: Path, archive: Path, *, label: str, transaction_id: str) -> dict[str, Any]:
    secure_regular(snapshot, maximum=SQLITE_MAX_BYTES)
    if label not in {"A", "B"} or archive.exists() or archive.is_symlink():
        raise RecoveryBlocked("archive-interface-invalid")
    info = canonical_state_tar_info(snapshot.stat().st_size)
    with archive.open("xb") as output:
        with tarfile.open(fileobj=output, mode="w:", format=tarfile.USTAR_FORMAT) as bundle, snapshot.open("rb") as source:
            bundle.addfile(info, source)
        output.truncate(canonical_state_tar_size(info.size))
    os.chmod(archive, 0o600)
    secure_regular(archive)
    if archive.stat().st_size > ARCHIVE_MAX_BYTES:
        archive.unlink(missing_ok=True)
        raise RecoveryBlocked("archive-size-exceeded")
    snapshot_hash = sha256_file(snapshot)
    member_digest = validate_canonical_state_tar(archive, snapshot_hash)
    return {
        "schema": BACKUP_SCHEMA, "transaction_id": transaction_id, "label": label,
        "generation_id": os.urandom(16).hex(), "source_snapshot_sha256": snapshot_hash,
        "archive_sha256": sha256_file(archive), "member_sha256": member_digest,
        "size_bytes": archive.stat().st_size, "entries": ["db_v2.sqlite3"], "mode": "0600",
        "secret_material_present": False,
    }


def capacity_sample(path: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    projected = ((usage.used + ARCHIVE_MAX_BYTES * 2) * 100 + usage.total - 1) // usage.total
    return {
        "filesystem_device": path.stat().st_dev, "total_bytes": usage.total,
        "used_bytes": usage.used, "available_bytes": usage.free,
        "projected_used_percent": projected, "status": "PASS" if projected <= 80 else "NO-GO",
    }


def hbbs_command(name: str, state_dir: Path) -> list[str]:
    return [
        "podman", "run", "--detach", "--name", name, "--network", "none",
        "--cpus", "0.8", "--memory", "1g", "--read-only",
        "--volume", f"{state_dir}:/root:Z", IMMUTABLE_HBBS, "hbbs",
    ]


def listener_snapshot() -> list[str]:
    listeners: set[str] = set()
    for source in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        try:
            rows = source.read_text(encoding="ascii").splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            fields = row.split()
            if len(fields) > 3 and fields[3] == "0A":
                port = int(fields[1].rsplit(":", 1)[1], 16)
                if 21114 <= port <= 21119:
                    listeners.add(f"{source.name}:{port}")
    return sorted(listeners)


def write_exclusive(path: Path, data: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def mutation(performed: bool, classes: list[str], cleanup: list[str] | None = None) -> dict[str, Any]:
    result = {
        "performed": performed, "classes": classes,
        "cleanup_pending": cleanup or [], "retained_artifacts": list(RETAINED),
    }
    validate_mutation(result)
    return result


def dry_run_details(action: str, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    details: dict[str, Any] = {"direct_versioned_action": True, "transaction_root": str(root)}
    classes: list[str] = []
    digest = "0" * 64
    transaction_id = "0" * 32
    backup_a = {
        "schema": BACKUP_SCHEMA, "transaction_id": transaction_id, "label": "A",
        "generation_id": "1" * 32, "source_snapshot_sha256": digest,
        "archive_sha256": digest, "member_sha256": digest, "size_bytes": 10240,
        "entries": ["db_v2.sqlite3"], "mode": "0600", "secret_material_present": False,
        "destination_class": "candidate-local",
    }
    backup_b = {
        **backup_a, "label": "B", "generation_id": "2" * 32,
        "destination_class": "modules/fleet-backup:gdrive",
        "remote_object": (
            "giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/"
            f"phase52/backup-b/{transaction_id}.tar"
        ),
        "local_sha256": digest, "remote_sha256": digest,
        "retention": {
            "retain_until": "phase57-pass-plus-30-days",
            "deletion_requires_new_explicit_approval": True,
        },
    }
    if action == "preflight":
        details.update({"image": IMMUTABLE_HBBS, "image_running": False, "network_mode": "none", "published_ports": []})
    elif action == "vault":
        details.update({"provider_api": "references-v1", "reference_count": 7, "public_fingerprint": digest})
    elif action == "backup":
        details.update({"backup_a": backup_a, "backup_b": backup_b, "state_only": ["db_v2.sqlite3"], "remote_rehash_verified": True, "sqlite_ready": True})
    elif action == "restore":
        details.update({"sqlite_integrity": "ok", "sqlite_ready": True, "public_fingerprint": digest, "image": IMMUTABLE_HBBS, "image_running": True, "network_mode": "none", "port_bindings": {}, "public_listener_delta": []})
    elif action == "capacity-finalize":
        details.update({"capacity": {"status": "PASS", "capacity_finalize_status": "PASS", "pre_disk_ok": True, "inode_ok": True, "projected_post_ok": True, "headroom_ok": True}, "actual_backup_a_bytes": 10240, "actual_backup_b_bytes": 10240})
    elif action == "rollback":
        details.update({"terminal": True, "retained_artifacts": [], "cleanup_pending": [], "retained_rehash_verified": False, "remote_rehash_verified": False, "remote_delete_performed": False})
    return details, mutation(False, classes)
