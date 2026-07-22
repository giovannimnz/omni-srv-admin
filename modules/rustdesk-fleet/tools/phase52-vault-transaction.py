#!/usr/bin/env python3
"""Fail-closed Phase 52 Gate B root transaction.

The reusable state machine is deliberately backend-driven.  Production uses the
local Vault adapter below; tests use an in-process fake.  Secret values exist
only in the root process and a verified tmpfs directory, and are passed to the
CAS primitive as bounded JSON on stdin.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import argparse
import ctypes
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import secrets
import base64
import hmac
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Callable


os.umask(0o077)
MAX_JSON = 262_144
MAX_CONTROL_PLANE_BUNDLE = 64 * 1024 * 1024
MAX_CONTROL_PLANE_PAYLOAD = 16 * 1024 * 1024
TX_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$")
EXPECTED_PATH_FIELDS = [
    ("kv/atius/rustdesk/server", ["private_key", "public_key"]),
    ("kv/atius/rustdesk/targets/atius-srv-1", ["permanent_password"]),
    ("kv/atius/rustdesk/targets/atius-srv-2", ["permanent_password"]),
    ("kv/atius/rustdesk/targets/atius-srv-3", ["permanent_password"]),
    ("kv/atius/rustdesk/targets/horistic-srv", ["permanent_password"]),
    ("kv/atius/rustdesk/targets/giovanni-w11-pc", ["permanent_password"]),
    ("kv/atius/fleet-backup/rclone/giovanni-drive", ["rclone_conf"]),
]
APPROVED_HORISTIC_SSH_FINGERPRINT = "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0"
CONTROL_PLANE_STATE_ROOT = Path("/var/lib/atius-vault-phase52")
VAULT_CONTAINER = "hashicorp-vault-atius"
PODMAN = Path("/usr/bin/podman")
SAFE_BLOCKER_TOKENS = frozenset({
    "ambiguous-write-ownership",
    "ambiguous-write-ownership-control-plane-restore-retry",
    "cas-conflict",
    "control-plane-install-failed",
    "control-plane-reinstall-failed",
    "control-plane-restore-retry-required",
    "control-plane-restore-test-failed",
    "owned-version-soft-delete-failed",
    "pre-backup-failed",
    "pre-backup-interrupted-before-backup-proof",
    "raft-snapshot-failed",
    "resume-after-acknowledged-write",
    "rollback-resume",
    "transaction-rollback-triggered",
    "zero-ack-control-plane-restore-failed",
    "zero-ack-post-backup-resumed-and-restored",
})
SAFE_OUTPUT_REASONS = frozenset({
    *SAFE_BLOCKER_TOKENS,
    "operation-blocked",
    "rollback-retry-required",
})


class Blocked(RuntimeError):
    """A fail-closed condition with a value-free reason."""


class CasConflict(Blocked):
    """Proven CAS=0 rejection: the current intent did not create a version."""


class InjectedCrash(BaseException):
    """Abrupt test-only interruption; deliberately bypasses rollback."""


def _safe_token(value: Any, allowed: frozenset[str], fallback: str) -> str:
    if fallback not in allowed:
        raise Blocked("blocker-fallback-invalid")
    return value if type(value) is str and value in allowed else fallback


def _safe_exception_argument(exc: Blocked) -> Any:
    return exc.args[0] if len(exc.args) == 1 else None


def _safe_blocker(value: Any, fallback: str) -> str:
    return _safe_token(value, SAFE_BLOCKER_TOKENS, fallback)


def _fixed_blocker(token: str) -> str:
    if token not in SAFE_BLOCKER_TOKENS:
        raise Blocked("blocker-token-invalid")
    return token


def _sanitized_blocker(exc: Blocked, fallback: str) -> str:
    return _safe_blocker(_safe_exception_argument(exc), fallback)


def _safe_output_reason(exc: Blocked) -> str:
    return _safe_token(
        _safe_exception_argument(exc), SAFE_OUTPUT_REASONS, "operation-blocked",
    )


class FaultInjector:
    def __init__(self, points: set[str] | None = None):
        self.points = set(points or ())

    def hit(self, index: int, point: str) -> None:
        if f"{index}:{point}" in self.points:
            raise InjectedCrash(f"injected-crash:{index}:{point}")


class TransactionBackend(ABC):
    @abstractmethod
    def create_backups(self, transaction_dir: Path, contract: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def prove_isolated_snapshot_restore(self, transaction_dir: Path, contract: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def install_control_plane(self, transaction_dir: Path, managed_sources: dict[str, bytes]) -> None: ...

    @abstractmethod
    def restore_control_plane(self, transaction_dir: Path) -> None: ...

    @abstractmethod
    def metadata(self, vault_path: str) -> dict[str, Any]: ...

    @abstractmethod
    def generate_values(self, contract: dict[str, Any], runtime_dir: Path) -> dict[str, dict[str, str]]: ...

    @abstractmethod
    def put_cas0_stdin(self, operation: dict[str, Any], encoded_private_json: bytes) -> dict[str, Any]: ...

    @abstractmethod
    def soft_delete_exact_version(self, vault_path: str, version: int) -> None: ...

    @abstractmethod
    def verify_created_values(self, contract: dict[str, Any], expected_versions: list[dict[str, Any]]) -> dict[str, Any]: ...


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Blocked("duplicate-json-key")
        result[key] = value
    return result


def strict_json_bytes(raw: bytes) -> Any:
    if not raw or len(raw) > MAX_JSON:
        raise Blocked("json-size-invalid")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicates)
    except Blocked:
        raise
    except Exception as exc:
        raise Blocked("json-invalid") from exc


def _encoded(payload: Any) -> bytes:
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > MAX_JSON:
        raise Blocked("json-size-invalid")
    return raw


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_file_and_parent(path: Path) -> None:
    """Durably order an already-created regular file before a WAL marker."""
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise Blocked("backup-artifact-invalid")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_parent(path)


def atomic_json(
    path: Path,
    payload: Any,
    *,
    mode: int = 0o600,
    fault: FaultInjector | None = None,
    index: int = -1,
    event: str = "state",
) -> None:
    raw = _encoded(payload)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise Blocked("atomic-json-write-failed")
            offset += written
        if fault:
            fault.hit(index, f"before-{event}-fsync")
        os.fsync(descriptor)
        if fault:
            fault.hit(index, f"after-{event}-fsync")
        os.close(descriptor)
        descriptor = -1
        if fault:
            fault.hit(index, f"before-{event}-rename")
        os.replace(temporary, path)
        if fault:
            fault.hit(index, f"after-{event}-rename")
        _fsync_parent(path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def load_contract(path: Path) -> dict[str, Any]:
    payload = strict_json_bytes(path.read_bytes())
    if not isinstance(payload, dict):
        raise Blocked("contract-invalid")
    required = {
        "schema", "schema_version", "phase", "gate", "authorization", "generator", "writes",
        "write_policy", "lock", "backup", "wal", "states", "rollback", "mutation_accounting",
        "live_coordinator", "prohibitions",
    }
    writes = payload.get("writes")
    if (
        set(payload) != required
        or payload.get("schema") != "atius-rustdesk-phase52-gate-b-transaction-v1"
        or payload.get("schema_version") != 1
        or payload.get("phase") != 52
        or payload.get("gate") != "B"
        or not isinstance(writes, list)
        or len(writes) != 7
    ):
        raise Blocked("contract-invalid")
    observed: list[tuple[str, list[str]]] = []
    ids: set[str] = set()
    for row in writes:
        if not isinstance(row, dict) or set(row) != {"id", "vault_path", "fields", "cas"}:
            raise Blocked("contract-write-invalid")
        if not isinstance(row["id"], str) or row["id"] in ids or row["cas"] != 0:
            raise Blocked("contract-write-invalid")
        ids.add(row["id"])
        observed.append((row["vault_path"], row["fields"]))
    if observed != EXPECTED_PATH_FIELDS:
        raise Blocked("contract-write-set-drift")
    authorization = payload["authorization"]
    if (
        not isinstance(authorization, dict)
        or authorization.get("approved_horistic_ssh_key_fingerprint")
        != APPROVED_HORISTIC_SSH_FINGERPRINT
    ):
        raise Blocked("authorization-fingerprint-invalid")
    generator = payload["generator"]
    if (
        generator.get("image") != "docker.io/rustdesk/rustdesk-server:1.1.15"
        or generator.get("linux_arm64_digest")
        != "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
        or generator.get("network_mode") != "none"
        or generator.get("port_bindings") != []
    ):
        raise Blocked("generator-pin-invalid")
    policy = payload["write_policy"]
    if (
        policy.get("create_only") is not True
        or policy.get("expected_put_count") != 7
        or policy.get("expected_rustdesk_value_count") != 7
        or policy.get("expected_total_value_count") != 8
        or policy.get("metadata_reads") != 2
        or policy.get("required_current_version") != 0
        or policy.get("required_oldest_version") != 0
        or policy.get("required_history") != {}
        or policy.get("private_input") != "bounded-stdin-only"
    ):
        raise Blocked("write-policy-invalid")
    rollback = payload["rollback"]
    if rollback.get("terminal_after_soft_delete") != "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION":
        raise Blocked("rollback-policy-invalid")
    if (
        payload["backup"].get("root") != "/var/backups/atius-vault/phase52"
        or payload["backup"].get("control_plane_state_root") != CONTROL_PLANE_STATE_ROOT.as_posix()
        or payload["backup"].get("required_success_sequence")
        != ["install", "exact-restore", "reviewed-reinstall", "metadata", "data-writes"]
    ):
        raise Blocked("backup-policy-invalid")
    coordinator = payload["live_coordinator"]
    if (
        coordinator.get("remote_deadline_seconds") != 600
        or coordinator.get("transport_ambiguity_status") != "REMOTE_OUTCOME_AMBIGUOUS_BLOCKED"
        or coordinator.get("automatic_retry_on_transport_ambiguity") is not False
        or coordinator.get("recovery_action") != "explicit-status-then-restore-or-rollback-only-resume"
        or coordinator.get("recovery_protocol") != "phase52-reviewed-recovery-v1"
        or coordinator.get("route_policy") != "direct-first"
        or coordinator.get("fallback_after_direct_probe_failure_only") is not True
        or coordinator.get("forced_relay_policy") != "preserve-approved-runtime-policy"
    ):
        raise Blocked("live-coordinator-policy-invalid")
    return payload


def _validate_approved_fingerprint(observed: str, approved: str) -> str:
    pattern = r"SHA256:[A-Za-z0-9+/]{43}"
    if (
        approved != APPROVED_HORISTIC_SSH_FINGERPRINT
        or not re.fullmatch(pattern, observed)
        or not hmac.compare_digest(observed, approved)
    ):
        raise Blocked("authorized-key-fingerprint-mismatch")
    return approved


def _validate_private_values(contract: dict[str, Any], values: Any) -> None:
    if not isinstance(values, dict) or set(values) != {row["id"] for row in contract["writes"]}:
        raise Blocked("generated-value-shape-invalid")
    passwords: list[str] = []
    for row in contract["writes"]:
        fields = values.get(row["id"])
        if not isinstance(fields, dict) or list(fields) != row["fields"]:
            raise Blocked("generated-value-shape-invalid")
        if not all(isinstance(value, str) and value for value in fields.values()):
            raise Blocked("generated-value-shape-invalid")
        if "permanent_password" in fields:
            password = fields["permanent_password"]
            if not re.fullmatch(r"R[A-Za-z0-9]{31}", password):
                raise Blocked("generated-password-invalid")
            passwords.append(password)
    if len(passwords) != 5 or len(set(passwords)) != 5:
        raise Blocked("generated-password-distinctness-failed")
    config = values["rclone-config"]["rclone_conf"]
    if not config.startswith("[giovanni-drive]\n") or "\n[" in config[1:]:
        raise Blocked("rclone-stanza-invalid")


def _pristine(metadata: Any) -> bool:
    return (
        isinstance(metadata, dict)
        and set(metadata) == {"current_version", "oldest_version", "versions"}
        and type(metadata["current_version"]) is int
        and type(metadata["oldest_version"]) is int
        and metadata["current_version"] == 0
        and metadata["oldest_version"] == 0
        and metadata["versions"] == {}
    )


def _validate_root(
    root: Path,
    *,
    require_root: bool,
    expected_live_root: Path | None = None,
) -> None:
    if not root.is_absolute() or ".." in root.parts:
        raise Blocked("backup-root-not-canonical")
    if require_root and root != (expected_live_root or Path("/var/backups/atius-vault/phase52")):
        raise Blocked("backup-root-live-path-drift")

    # Never call resolve() here: resolving first would make a symlink-backed
    # backup root indistinguishable from the reviewed path.  Walk and create
    # each component so every existing ancestor is proven to be a directory.
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current = current / part
        final = current == root
        try:
            info = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o700)
            _fsync_parent(current)
            info = current.lstat()
        if current.is_symlink() or not stat.S_ISDIR(info.st_mode):
            raise Blocked("backup-root-not-canonical" if final else "backup-root-ancestor-invalid")
        if require_root and info.st_uid != 0:
            raise Blocked("backup-root-identity-invalid" if final else "backup-root-ancestor-invalid")

    info = root.lstat()
    expected_uid = 0 if require_root else os.geteuid()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != expected_uid
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise Blocked("backup-root-identity-invalid")
    if require_root and os.geteuid() != 0:
        raise Blocked("root-required")


def _acquire_lock(root: Path, contract: dict[str, Any], *, require_root: bool) -> int:
    path = Path(contract["lock"]["path"]) if require_root else root / ".phase52-gate-b.lock"
    if require_root and path != Path("/var/lock/atius-vault-phase52-gate-b.lock"):
        raise Blocked("transaction-lock-path-drift")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    os.fchmod(descriptor, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise Blocked("transaction-lock-contended") from exc
    return descriptor


def _validate_backup_proof(proof: Any, restore: Any) -> None:
    if proof != {"raft_snapshot_valid": True, "control_plane_bundle_valid": True}:
        raise Blocked("backup-proof-failed")
    expected = {
        "status": "PASS", "network_namespace": "isolated", "host_listener": False,
        "public_listener": False, "port_bindings": [], "integrity": "PASS",
    }
    if restore != expected:
        raise Blocked("isolated-restore-proof-failed")


def _validate_backup_artifacts(directory: Path, *, require_root: bool) -> None:
    expected_uid = 0 if require_root else os.geteuid()
    for name in ("raft.snapshot", "control-plane.tar", "manifest.json"):
        path = directory / name
        try:
            info = path.lstat()
        except OSError as exc:
            raise Blocked("backup-artifact-invalid") from exc
        if (
            path.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != expected_uid
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size <= 0
        ):
            raise Blocked("backup-artifact-invalid")
        if name == "control-plane.tar" and info.st_size > MAX_CONTROL_PLANE_BUNDLE:
            raise Blocked("backup-artifact-invalid")
    manifest = strict_json_bytes((directory / "manifest.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {
            "schema", "raft_snapshot_sha256", "control_plane_bundle_sha256", "secret_material_present",
        }
        or manifest.get("schema") != "phase52-gate-b-backup-manifest-v1"
        or manifest.get("secret_material_present") is not False
        or manifest.get("raft_snapshot_sha256") != sha256_file(directory / "raft.snapshot")
        or manifest.get("control_plane_bundle_sha256") != sha256_file(directory / "control-plane.tar")
    ):
        raise Blocked("backup-artifact-digest-drift")


def _initial_wal(transaction_id: str) -> dict[str, Any]:
    return {
        "schema": "phase52-gate-b-wal-v1",
        "transaction_id": transaction_id,
        "status": "PRE_BACKUP",
        "writes": [],
        "soft_delete_performed": False,
    }


def _runtime_projection(
    transaction_id: str,
    status: str,
    versions: list[dict[str, Any]],
    *,
    ownership_unresolved: bool = False,
) -> dict[str, Any]:
    if ownership_unresolved:
        live_write_performed: bool | None = None
        ownership = "UNRESOLVED"
    elif versions:
        live_write_performed = True
        ownership = "FSYNCED_WAL_ACK"
    else:
        live_write_performed = False
        ownership = "NONE"
    return {
        "schema": "phase52-gate-b-transaction-evidence-v1",
        "transaction_id": transaction_id,
        "status": status,
        "write_count": len(versions),
        "vault_versions": [
            {"id": row["id"], "vault_path": row["vault_path"], "version": row["version"]}
            for row in versions
        ],
        "mutation_accounting": {
            "atius-srv-2": {
                "candidate_data_plane_mutation": False,
                "authorized_vault_control_plane_mutation": False,
            },
            "atius-srv-3": {
                "candidate_data_plane_mutation": False,
                "authorized_vault_control_plane_mutation": True,
            },
            "vault_data_create_only_write_count": len(versions),
        },
        "live_write_performed": live_write_performed,
        "vault_write_ownership": ownership,
        "secret_material_present": False,
        "windows_install_performed": False,
        "network_listener_created": False,
    }


def _mutation_accounting_exact(value: Any, write_count: int) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"atius-srv-2", "atius-srv-3", "vault_data_create_only_write_count"}
        and isinstance(value.get("atius-srv-2"), dict)
        and set(value["atius-srv-2"]) == {
            "candidate_data_plane_mutation", "authorized_vault_control_plane_mutation",
        }
        and value["atius-srv-2"].get("candidate_data_plane_mutation") is False
        and value["atius-srv-2"].get("authorized_vault_control_plane_mutation") is False
        and isinstance(value.get("atius-srv-3"), dict)
        and set(value["atius-srv-3"]) == {
            "candidate_data_plane_mutation", "authorized_vault_control_plane_mutation",
        }
        and value["atius-srv-3"].get("candidate_data_plane_mutation") is False
        and value["atius-srv-3"].get("authorized_vault_control_plane_mutation") is True
        and type(value.get("vault_data_create_only_write_count")) is int
        and value["vault_data_create_only_write_count"] == write_count
    )


def _write_evidence(directory: Path, projection: dict[str, Any]) -> None:
    atomic_json(directory / "transaction-evidence.json", projection)


def _final_ledger(transaction_id: str, status: str, owned: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "phase52-gate-b-version-ledger-v1",
        "transaction_id": transaction_id,
        "status": status,
        "writes": [
            {
                "id": row["id"], "vault_path": row["vault_path"],
                "version": row["version"], "ownership": "fsynced-wal-ack",
            }
            for row in owned
        ],
        "secret_material_present": False,
    }


def _owned_from_wal(wal: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": row["id"], "vault_path": row["vault_path"], "version": row["version"]}
        for row in wal.get("writes", [])
        if isinstance(row, dict)
        and row.get("status") == "acknowledged"
        and type(row.get("version")) is int
    ]


def _validate_wal(contract: dict[str, Any], wal: Any, transaction_id: str) -> None:
    allowed = {
        "schema","transaction_id","status","writes","soft_delete_performed","blocker",
        "control_plane_restored","control_plane_install_proved","control_plane_restore_tested",
        "control_plane_reinstall_proved","metadata_proved_pristine","created_values_verified",
    }
    if not isinstance(wal,dict) or not {"schema","transaction_id","status","writes","soft_delete_performed"} <= set(wal) or not set(wal) <= allowed or wal.get("schema")!="phase52-gate-b-wal-v1" or wal.get("transaction_id")!=transaction_id or not isinstance(wal.get("writes"),list) or len(wal["writes"])>7 or type(wal.get("soft_delete_performed")) is not bool:
        raise Blocked("wal-shape-invalid")
    if "blocker" in wal and (
        type(wal["blocker"]) is not str
        or wal["blocker"] not in SAFE_BLOCKER_TOKENS
    ):
        raise Blocked("wal-blocker-invalid")
    statuses={
        "PRE_BACKUP","BACKUP_PROVED","CONTROL_PLANE_INSTALLING","CONTROL_PLANE_INSTALLED",
        "CONTROL_PLANE_RESTORED_BEFORE_REINSTALL","CONTROL_PLANE_REINSTALLED",
        "METADATA_PROVED_PRISTINE","CREATING","PASS","ROLLING_BACK",
        "ROLLBACK_BLOCKED_RETRY_REQUIRED","ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION",
        "OWNERSHIP_AMBIGUOUS_BLOCKED","OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY",
        "BLOCKED","PRE_BACKUP_NO_MUTATION_TERMINAL",
    }
    if wal.get("status") not in statuses: raise Blocked("wal-status-invalid")
    proof_fields = (
        "control_plane_install_proved", "control_plane_restore_tested",
        "control_plane_reinstall_proved", "metadata_proved_pristine",
        "created_values_verified",
    )
    if any(type(wal.get(key)) is not bool for key in proof_fields if key in wal):
        raise Blocked("wal-shape-invalid")
    for index,row in enumerate(wal["writes"]):
        expected=contract["writes"][index]
        if not isinstance(row,dict) or not {"id","vault_path","status"} <= set(row) or not set(row) <= {"id","vault_path","status","version","soft_deleted"} or row.get("id")!=expected["id"] or row.get("vault_path")!=expected["vault_path"] or row.get("status") not in {"intent","acknowledged"}:
            raise Blocked("wal-operation-invalid")
        if row["status"]=="acknowledged" and (row.get("version")!=1 or type(row.get("version")) is not int): raise Blocked("wal-version-invalid")
        if row["status"]=="intent" and ("version" in row or "soft_deleted" in row): raise Blocked("wal-operation-invalid")
        if "soft_deleted" in row and type(row["soft_deleted"]) is not bool: raise Blocked("wal-operation-invalid")


def _reconcile_status_projection(
    contract: dict[str, Any], wal: Any, evidence: Any, transaction_id: str,
) -> dict[str, Any]:
    """Derive status from the fsynced WAL; evidence may lag but never lead it."""
    _validate_wal(contract, wal, transaction_id)
    exact_evidence_keys = {
        "schema", "transaction_id", "status", "write_count", "vault_versions",
        "mutation_accounting", "live_write_performed", "vault_write_ownership",
        "secret_material_present", "windows_install_performed", "network_listener_created",
    }
    if (
        not isinstance(evidence, dict) or set(evidence) != exact_evidence_keys
        or evidence.get("schema") != "phase52-gate-b-transaction-evidence-v1"
        or evidence.get("transaction_id") != transaction_id
        or not isinstance(evidence.get("vault_versions"), list)
        or type(evidence.get("write_count")) is not int
        or evidence["write_count"] != len(evidence["vault_versions"])
        or evidence.get("secret_material_present") is not False
        or evidence.get("windows_install_performed") is not False
        or evidence.get("network_listener_created") is not False
        or not _mutation_accounting_exact(
            evidence.get("mutation_accounting"), len(evidence.get("vault_versions", [])),
        )
        or any(
            not isinstance(row, dict) or set(row) != {"id", "vault_path", "version"}
            or type(row.get("version")) is not int or row["version"] != 1
            for row in evidence.get("vault_versions", [])
        )
    ):
        raise Blocked("transaction-evidence-invalid")
    owned = _owned_from_wal(wal)
    expected_owned = [
        {"id": row["id"], "vault_path": row["vault_path"], "version": row["version"]}
        for row in owned
    ]
    evidence_versions = evidence["vault_versions"]
    if evidence_versions != expected_owned[: len(evidence_versions)]:
        raise Blocked("transaction-evidence-leads-wal")

    evidence_status = evidence.get("status")
    evidence_count = len(evidence_versions)
    evidence_live = evidence.get("live_write_performed")
    evidence_ownership = evidence.get("vault_write_ownership")
    no_write_evidence = {
        "PRE_BACKUP", "BACKUP_PROVED", "CONTROL_PLANE_INSTALLING",
        "CONTROL_PLANE_INSTALLED", "CONTROL_PLANE_RESTORED_BEFORE_REINSTALL",
        "CONTROL_PLANE_REINSTALLED", "METADATA_PROVED_PRISTINE", "BLOCKED",
        "PRE_BACKUP_NO_MUTATION_TERMINAL",
    }
    evidence_semantics_ok = (
        (evidence_status in no_write_evidence and evidence_count == 0 and evidence_live is False and evidence_ownership == "NONE")
        or (
            evidence_status == "CREATING"
            and (
                (evidence_count == 0 and evidence_live is False and evidence_ownership == "NONE")
                or (1 <= evidence_count <= 7 and evidence_live is True and evidence_ownership == "FSYNCED_WAL_ACK")
                or (0 <= evidence_count <= 6 and evidence_live is None and evidence_ownership == "UNRESOLVED")
            )
        )
        or (
            evidence_status in {"OWNERSHIP_AMBIGUOUS_BLOCKED", "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY"}
            and 0 <= evidence_count <= 6 and evidence_live is None and evidence_ownership == "UNRESOLVED"
        )
        or (
            evidence_status in {"ROLLING_BACK", "ROLLBACK_BLOCKED_RETRY_REQUIRED"}
            and (
                (evidence_count == 0 and evidence_live is False and evidence_ownership == "NONE")
                or (1 <= evidence_count <= 7 and evidence_live is True and evidence_ownership == "FSYNCED_WAL_ACK")
            )
        )
        or (
            evidence_status == "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION"
            and 1 <= evidence_count <= 7 and evidence_live is True and evidence_ownership == "FSYNCED_WAL_ACK"
        )
        or (
            evidence_status == "PASS" and evidence_count == 7
            and evidence_live is True and evidence_ownership == "FSYNCED_WAL_ACK"
        )
    )
    if not evidence_semantics_ok:
        raise Blocked("transaction-evidence-invalid")

    wal_status = wal["status"]
    prewrite_states = {
        "PRE_BACKUP", "BACKUP_PROVED", "CONTROL_PLANE_INSTALLING",
        "CONTROL_PLANE_INSTALLED", "CONTROL_PLANE_RESTORED_BEFORE_REINSTALL",
        "CONTROL_PLANE_REINSTALLED", "METADATA_PROVED_PRISTINE",
    }
    compatible = False
    if wal_status in prewrite_states:
        compatible = evidence_status in {"BLOCKED", wal_status} and evidence_count == 0
    elif wal_status == "PRE_BACKUP_NO_MUTATION_TERMINAL":
        compatible = evidence_status in {
            "PRE_BACKUP", "PRE_BACKUP_NO_MUTATION_TERMINAL",
        } and evidence_count == 0
    elif wal_status == "CREATING":
        compatible = evidence_status == "CREATING"
        if not wal["writes"]:
            compatible = compatible or (evidence_status == "BLOCKED" and evidence_count == 0)
    elif wal_status == "PASS":
        compatible = evidence_status == "PASS" or evidence_status == "CREATING"
    elif wal_status == "ROLLING_BACK":
        compatible = evidence_status in {"CREATING", "ROLLING_BACK"}
    elif wal_status == "ROLLBACK_BLOCKED_RETRY_REQUIRED":
        compatible = evidence_status in {"CREATING", "ROLLBACK_BLOCKED_RETRY_REQUIRED"}
        compatible = compatible or (not wal["writes"] and evidence_status == "BLOCKED")
    elif wal_status == "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION":
        compatible = evidence_status in {
            "CREATING", "ROLLBACK_BLOCKED_RETRY_REQUIRED",
            "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION",
        }
    elif wal_status in {
        "OWNERSHIP_AMBIGUOUS_BLOCKED",
        "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY",
    }:
        compatible = evidence_status in {
            "CREATING", "OWNERSHIP_AMBIGUOUS_BLOCKED",
            "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY",
        }
    elif wal_status == "BLOCKED":
        compatible = evidence_status in {"BLOCKED", "ROLLBACK_BLOCKED_RETRY_REQUIRED"}
    if not compatible:
        raise Blocked("transaction-evidence-leads-wal")

    status = wal_status
    rows = wal["writes"]
    no_write_states = {
        "PRE_BACKUP", "BACKUP_PROVED", "CONTROL_PLANE_INSTALLING",
        "CONTROL_PLANE_INSTALLED", "CONTROL_PLANE_RESTORED_BEFORE_REINSTALL",
        "CONTROL_PLANE_REINSTALLED", "METADATA_PROVED_PRISTINE", "BLOCKED",
        "PRE_BACKUP_NO_MUTATION_TERMINAL",
    }
    if status in no_write_states:
        if rows:
            raise Blocked("wal-state-write-count-invalid")
        return _runtime_projection(transaction_id, status, [])
    if status == "PASS":
        if (
            len(owned) != 7 or len(rows) != 7
            or any(row.get("status") != "acknowledged" or row.get("soft_deleted") is True for row in rows)
            or wal.get("soft_delete_performed") is not False
            or wal.get("control_plane_install_proved") is not True
            or wal.get("control_plane_restore_tested") is not True
            or wal.get("control_plane_reinstall_proved") is not True
            or wal.get("metadata_proved_pristine") is not True
            or wal.get("created_values_verified") is not True
            or wal.get("control_plane_restored") is not False
            or "blocker" in wal
        ):
            raise Blocked("wal-pass-proof-invalid")
        return _runtime_projection(transaction_id, status, owned)
    if status in {
        "OWNERSHIP_AMBIGUOUS_BLOCKED",
        "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY",
    }:
        if not rows or rows[-1].get("status") != "intent" or len(owned) != len(rows) - 1:
            raise Blocked("wal-ambiguous-proof-invalid")
        return _runtime_projection(
            transaction_id, status, owned, ownership_unresolved=True,
        )
    if status == "CREATING":
        if not rows:
            return _runtime_projection(transaction_id, status, [])
        if rows[-1].get("status") == "intent":
            if len(owned) != len(rows) - 1:
                raise Blocked("wal-creating-proof-invalid")
            return _runtime_projection(
                transaction_id, status, owned, ownership_unresolved=True,
            )
        if len(owned) != len(rows):
            raise Blocked("wal-creating-proof-invalid")
        return _runtime_projection(transaction_id, status, owned)
    if status in {
        "ROLLING_BACK", "ROLLBACK_BLOCKED_RETRY_REQUIRED",
        "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION",
    }:
        if any(row.get("status") == "intent" for row in rows) or len(owned) != len(rows):
            raise Blocked("wal-rollback-proof-invalid")
        if status == "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION" and not owned:
            raise Blocked("wal-rollback-proof-invalid")
        return _runtime_projection(transaction_id, status, owned)
    raise Blocked("wal-status-projection-invalid")


def _rollback_owned(
    backend: TransactionBackend,
    directory: Path,
    transaction_id: str,
    wal: dict[str, Any],
    blocker: Any,
) -> dict[str, Any]:
    if any(
        isinstance(row, dict) and row.get("status") == "intent"
        for row in wal.get("writes", [])
    ):
        _mark_zero_ack_ambiguous(backend, directory, transaction_id, wal)
    owned = _owned_from_wal(wal)
    wal["status"] = "ROLLING_BACK"
    atomic_json(directory / "wal.json", wal)
    indexed = {
        (row["vault_path"], row["version"]): row
        for row in wal.get("writes", [])
        if isinstance(row, dict) and row.get("status") == "acknowledged"
    }
    try:
        for row in reversed(owned):
            wal_row = indexed[(row["vault_path"], row["version"])]
            if wal_row.get("soft_deleted") is True:
                continue
            backend.soft_delete_exact_version(row["vault_path"], row["version"])
            wal_row["soft_deleted"] = True
            wal["soft_delete_performed"] = True
            atomic_json(directory / "wal.json", wal)
    except Blocked as exc:
        try:
            backend.restore_control_plane(directory)
            wal["control_plane_restored"] = True
        except Blocked:
            wal["control_plane_restored"] = False
        wal["status"] = "ROLLBACK_BLOCKED_RETRY_REQUIRED"
        wal["blocker"] = _sanitized_blocker(
            exc, "owned-version-soft-delete-failed",
        )
        atomic_json(directory / "wal.json", wal)
        _write_evidence(
            directory,
            _runtime_projection(transaction_id, "ROLLBACK_BLOCKED_RETRY_REQUIRED", owned),
        )
        raise Blocked("rollback-retry-required") from exc
    if wal.get("control_plane_restored") is not True:
        backend.restore_control_plane(directory)
        wal["control_plane_restored"] = True
    status = "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION" if owned else "BLOCKED"
    wal["status"] = status
    wal["soft_delete_performed"] = bool(owned)
    wal["blocker"] = _safe_blocker(blocker, "transaction-rollback-triggered")
    atomic_json(directory / "wal.json", wal)
    atomic_json(directory / "ledger.json", _final_ledger(transaction_id, status, owned))
    projection = _runtime_projection(transaction_id, status, owned)
    _write_evidence(directory, projection)
    return projection


def _transaction_dir(root: Path, transaction_id: str, *, create: bool) -> Path:
    if not TX_ID.fullmatch(transaction_id):
        raise Blocked("transaction-id-invalid")
    directory = root / transaction_id
    if create:
        try:
            directory.mkdir(mode=0o700, exist_ok=False)
        except OSError as exc:
            raise Blocked("transaction-directory-create-failed") from exc
        _fsync_parent(directory)
    try:
        info = directory.lstat()
    except OSError as exc:
        raise Blocked("transaction-directory-invalid") from exc
    if (
        directory.is_symlink() or not stat.S_ISDIR(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid()
    ):
        raise Blocked("transaction-directory-invalid")
    return directory


def _terminate_pre_backup_no_mutation(
    directory: Path,
    transaction_id: str,
    wal: dict[str, Any],
) -> dict[str, Any]:
    """Terminate before backup proof without invoking any mutation backend."""
    forbidden_proofs = {
        "control_plane_restored", "control_plane_install_proved",
        "control_plane_restore_tested", "control_plane_reinstall_proved",
        "metadata_proved_pristine", "created_values_verified",
    }
    if (
        wal.get("status") != "PRE_BACKUP"
        or wal.get("writes") != []
        or wal.get("soft_delete_performed") is not False
        or forbidden_proofs.intersection(wal)
    ):
        raise Blocked("pre-backup-wal-proof-invalid")
    blocker = wal.get("blocker")
    wal["status"] = "PRE_BACKUP_NO_MUTATION_TERMINAL"
    wal["blocker"] = _safe_blocker(
        blocker, "pre-backup-interrupted-before-backup-proof",
    )
    atomic_json(directory / "wal.json", wal)
    atomic_json(
        directory / "ledger.json",
        _final_ledger(transaction_id, "PRE_BACKUP_NO_MUTATION_TERMINAL", []),
    )
    projection = _runtime_projection(
        transaction_id, "PRE_BACKUP_NO_MUTATION_TERMINAL", [],
    )
    _write_evidence(directory, projection)
    return projection


def _restore_zero_ack_terminal(
    backend: TransactionBackend,
    directory: Path,
    transaction_id: str,
    wal: dict[str, Any],
) -> dict[str, Any]:
    """Conservatively restore the reviewed bundle after any post-backup crash."""
    if _owned_from_wal(wal):
        raise Blocked("zero-ack-wal-has-owned-write")
    try:
        backend.restore_control_plane(directory)
    except Blocked as exc:
        wal["status"] = "ROLLBACK_BLOCKED_RETRY_REQUIRED"
        wal["control_plane_restored"] = False
        wal["blocker"] = _fixed_blocker("zero-ack-control-plane-restore-failed")
        atomic_json(directory / "wal.json", wal)
        projection = _runtime_projection(transaction_id, "ROLLBACK_BLOCKED_RETRY_REQUIRED", [])
        _write_evidence(directory, projection)
        raise Blocked("rollback-retry-required") from exc
    wal["status"] = "BLOCKED"
    wal["control_plane_restored"] = True
    wal["blocker"] = _fixed_blocker("zero-ack-post-backup-resumed-and-restored")
    atomic_json(directory / "wal.json", wal)
    atomic_json(directory / "ledger.json", _final_ledger(transaction_id, "BLOCKED", []))
    projection = _runtime_projection(transaction_id, "BLOCKED", [])
    _write_evidence(directory, projection)
    return projection


def _mark_zero_ack_ambiguous(
    backend: TransactionBackend,
    directory: Path,
    transaction_id: str,
    wal: dict[str, Any],
) -> None:
    """Restore control-plane bytes but never claim/delete an unacked Vault put."""
    try:
        backend.restore_control_plane(directory)
    except Blocked as exc:
        wal["status"] = "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY"
        wal["control_plane_restored"] = False
        wal["blocker"] = _fixed_blocker(
            "ambiguous-write-ownership-control-plane-restore-retry",
        )
        atomic_json(directory / "wal.json", wal)
        _write_evidence(
            directory,
            _runtime_projection(
                transaction_id,
                "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY",
                _owned_from_wal(wal),
                ownership_unresolved=True,
            ),
        )
        raise Blocked("ambiguous-write-ownership-control-plane-restore-retry") from exc
    wal["status"] = "OWNERSHIP_AMBIGUOUS_BLOCKED"
    wal["control_plane_restored"] = True
    wal["blocker"] = _fixed_blocker("ambiguous-write-ownership")
    atomic_json(directory / "wal.json", wal)
    _write_evidence(
        directory,
        _runtime_projection(
            transaction_id,
            "OWNERSHIP_AMBIGUOUS_BLOCKED",
            _owned_from_wal(wal),
            ownership_unresolved=True,
        ),
    )
    raise Blocked("ambiguous-write-ownership")


def run_transaction(
    contract: dict[str, Any],
    backend: TransactionBackend,
    backup_root: Path,
    transaction_id: str,
    *,
    managed_sources: dict[str, bytes] | None = None,
    fault: FaultInjector | None = None,
    require_root: bool = True,
) -> dict[str, Any]:
    """Run a new transaction; only InjectedCrash bypasses normal rollback."""
    load_contract_from_payload(contract)
    root = Path(backup_root)
    _validate_root(
        root,
        require_root=require_root,
        expected_live_root=Path(contract["backup"]["root"]),
    )
    lock = _acquire_lock(root, contract, require_root=require_root)
    runtime: Path | None = None
    try:
        directory = _transaction_dir(root, transaction_id, create=True)
        wal = _initial_wal(transaction_id)
        atomic_json(directory / "wal.json", wal)
        _write_evidence(directory, _runtime_projection(transaction_id, "PRE_BACKUP", []))

        try:
            proof = backend.create_backups(directory, contract)
            _validate_backup_artifacts(directory, require_root=require_root)
            restore_proof = backend.prove_isolated_snapshot_restore(directory, contract)
            _validate_backup_proof(proof, restore_proof)
        except Blocked as exc:
            wal["blocker"] = _sanitized_blocker(exc, "pre-backup-failed")
            atomic_json(directory / "wal.json", wal)
            _write_evidence(
                directory, _runtime_projection(transaction_id, "PRE_BACKUP", []),
            )
            raise
        wal["status"] = "BACKUP_PROVED"
        atomic_json(directory / "wal.json", wal)

        wal["status"] = "CONTROL_PLANE_INSTALLING"
        atomic_json(directory / "wal.json", wal)
        try:
            backend.install_control_plane(directory, managed_sources or {})
        except Blocked as exc:
            backend.restore_control_plane(directory)
            wal["status"] = "BLOCKED"
            wal["blocker"] = _sanitized_blocker(
                exc, "control-plane-install-failed",
            )
            wal["control_plane_restored"] = True
            atomic_json(directory / "wal.json", wal)
            raise
        wal["status"] = "CONTROL_PLANE_INSTALLED"
        wal["control_plane_install_proved"] = True
        atomic_json(directory / "wal.json", wal)

        # Prove that the exact pre-transaction control plane can be restored,
        # then reinstall the reviewed candidate before any Vault metadata or
        # data operation is allowed.
        try:
            backend.restore_control_plane(directory)
            wal["status"] = "CONTROL_PLANE_RESTORED_BEFORE_REINSTALL"
            wal["control_plane_restored"] = True
            wal["control_plane_restore_tested"] = True
            atomic_json(directory / "wal.json", wal)
            wal["status"] = "CONTROL_PLANE_INSTALLING"
            wal["control_plane_restored"] = False
            atomic_json(directory / "wal.json", wal)
            backend.install_control_plane(directory, managed_sources or {})
        except Blocked as exc:
            failed_status = wal.get("status")
            try:
                backend.restore_control_plane(directory)
                wal["control_plane_restored"] = True
            except Blocked as restore_exc:
                wal["control_plane_restored"] = False
                wal["status"] = "ROLLBACK_BLOCKED_RETRY_REQUIRED"
                wal["blocker"] = _fixed_blocker(
                    "control-plane-restore-retry-required",
                )
                atomic_json(directory / "wal.json", wal)
                _write_evidence(
                    directory,
                    _runtime_projection(
                        transaction_id, "ROLLBACK_BLOCKED_RETRY_REQUIRED", [],
                    ),
                )
                raise Blocked("rollback-retry-required") from restore_exc
            wal["status"] = "BLOCKED"
            fallback = (
                "control-plane-reinstall-failed"
                if failed_status == "CONTROL_PLANE_INSTALLING"
                else "control-plane-restore-test-failed"
            )
            wal["blocker"] = _sanitized_blocker(exc, fallback)
            atomic_json(directory / "wal.json", wal)
            raise
        wal["status"] = "CONTROL_PLANE_REINSTALLED"
        wal["control_plane_reinstall_proved"] = True
        atomic_json(directory / "wal.json", wal)

        try:
            first_reads: dict[str, Any] = {}
            for row in contract["writes"]:
                first = backend.metadata(row["vault_path"])
                if not _pristine(first):
                    raise Blocked("vault-path-not-pristine")
                first_reads[row["vault_path"]] = first
            for row in contract["writes"]:
                second = backend.metadata(row["vault_path"])
                if second != first_reads[row["vault_path"]]:
                    raise Blocked("vault-metadata-drift")
                if not _pristine(second):
                    raise Blocked("vault-path-not-pristine")
            wal["status"] = "METADATA_PROVED_PRISTINE"
            wal["metadata_proved_pristine"] = True
            atomic_json(directory / "wal.json", wal)

            tmpfs_root = Path("/dev/shm")
            runtime = Path(tempfile.mkdtemp(prefix=f"atius-phase52-{transaction_id}-", dir=tmpfs_root))
            runtime.chmod(0o700)
            values = backend.generate_values(contract, runtime)
            _validate_private_values(contract, values)
            wal["status"] = "CREATING"
            atomic_json(directory / "wal.json", wal)
            for index, row in enumerate(contract["writes"]):
                intent = {"id": row["id"], "vault_path": row["vault_path"], "status": "intent"}
                wal["writes"].append(intent)
                atomic_json(directory / "wal.json", wal, fault=fault, index=index, event="intent")
                _write_evidence(
                    directory,
                    _runtime_projection(transaction_id, "CREATING", _owned_from_wal(wal), ownership_unresolved=True),
                )
                if fault:
                    fault.hit(index, "before-put")
                private_bytes = _encoded(values[row["id"]])
                try:
                    if len(private_bytes) > contract["write_policy"]["max_private_request_bytes"]:
                        raise Blocked("private-request-too-large")
                    result = backend.put_cas0_stdin(row, private_bytes)
                    if not isinstance(result, dict) or set(result) != {"version"} or type(result["version"]) is not int or result["version"] != 1:
                        raise Blocked("put-result-invalid")
                except CasConflict:
                    # CAS=0 conflict proves this intent did not create a new
                    # version, so remove it durably before rolling back only
                    # the preceding fsynced acknowledgements.
                    wal["writes"].pop()
                    atomic_json(directory / "wal.json", wal)
                    raise
                except Blocked:
                    _mark_zero_ack_ambiguous(backend, directory, transaction_id, wal)
                if fault:
                    fault.hit(index, "after-put-ack")
                intent["status"] = "acknowledged"
                intent["version"] = result["version"]
                atomic_json(directory / "wal.json", wal, fault=fault, index=index, event="version")
                _write_evidence(directory, _runtime_projection(transaction_id, "CREATING", _owned_from_wal(wal)))
            owned = _owned_from_wal(wal)
            verification = backend.verify_created_values(contract, owned)
            if verification != {"status": "PASS", "write_count": 7, "secret_material_present": False}:
                raise Blocked("created-value-verification-failed")
            wal["created_values_verified"] = True
            wal["status"] = "PASS"
            atomic_json(directory / "wal.json", wal)
            atomic_json(directory / "ledger.json", _final_ledger(transaction_id, "PASS", owned))
            projection = _runtime_projection(transaction_id, "PASS", owned)
            _write_evidence(directory, projection)
            return projection
        except Blocked as exc:
            if wal.get("status") in {
                "OWNERSHIP_AMBIGUOUS_BLOCKED",
                "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY",
            }:
                raise
            projection = _rollback_owned(
                backend, directory, transaction_id, wal,
                _safe_exception_argument(exc),
            )
            owned = _owned_from_wal(wal)
            if not owned:
                raise
            return projection
    finally:
        if runtime is not None:
            shutil.rmtree(runtime, ignore_errors=True)
        os.close(lock)


def load_contract_from_payload(payload: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(prefix="phase52-contract-", suffix=".json", dir="/dev/shm")
    path = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        raw = _encoded(payload)
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise Blocked("contract-write-failed")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        load_contract(path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def resume_transaction(
    contract: dict[str, Any], backend: TransactionBackend, backup_root: Path,
    transaction_id: str, *, require_root: bool = True,
) -> dict[str, Any]:
    load_contract_from_payload(contract)
    root = Path(backup_root)
    _validate_root(
        root,
        require_root=require_root,
        expected_live_root=Path(contract["backup"]["root"]),
    )
    lock = _acquire_lock(root, contract, require_root=require_root)
    try:
        directory = _transaction_dir(root, transaction_id, create=False)
        wal = strict_json_bytes((directory / "wal.json").read_bytes())
        _validate_wal(contract, wal, transaction_id)
        if wal.get("status") == "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION":
            raise Blocked("manual-reauthorization-required")
        if wal.get("status") == "PRE_BACKUP_NO_MUTATION_TERMINAL":
            raise Blocked("pre-backup-no-mutation-terminal")
        if wal.get("status") == "BLOCKED":
            raise Blocked("transaction-terminal-blocked")
        if wal.get("status") == "OWNERSHIP_AMBIGUOUS_BLOCKED":
            raise Blocked("ambiguous-write-ownership")
        if wal.get("status") == "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY":
            try:
                backend.restore_control_plane(directory)
            except Blocked as exc:
                wal["control_plane_restored"] = False
                atomic_json(directory / "wal.json", wal)
                raise Blocked("ambiguous-write-ownership-control-plane-restore-retry") from exc
            wal["status"] = "OWNERSHIP_AMBIGUOUS_BLOCKED"
            wal["control_plane_restored"] = True
            wal["blocker"] = _fixed_blocker("ambiguous-write-ownership")
            atomic_json(directory / "wal.json", wal)
            _write_evidence(
                directory,
                _runtime_projection(
                    transaction_id,
                    "OWNERSHIP_AMBIGUOUS_BLOCKED",
                    _owned_from_wal(wal),
                    ownership_unresolved=True,
                ),
            )
            raise Blocked("ambiguous-write-ownership")
        if wal.get("status") == "PASS":
            evidence = strict_json_bytes((directory / "transaction-evidence.json").read_bytes())
            return _reconcile_status_projection(contract, wal, evidence, transaction_id)
        if wal.get("status") == "PRE_BACKUP":
            return _terminate_pre_backup_no_mutation(
                directory, transaction_id, wal,
            )
        if any(
            isinstance(row, dict) and row.get("status") == "intent"
            for row in wal.get("writes", [])
        ):
            _mark_zero_ack_ambiguous(backend, directory, transaction_id, wal)
        if wal.get("status") in {"ROLLING_BACK", "ROLLBACK_BLOCKED_RETRY_REQUIRED"}:
            if not wal.get("writes"):
                return _restore_zero_ack_terminal(
                    backend, directory, transaction_id, wal,
                )
            return _rollback_owned(
                backend, directory, transaction_id, wal,
                _safe_blocker(wal.get("blocker"), "rollback-resume"),
            )
        acknowledged = _owned_from_wal(wal)
        if acknowledged:
            return _rollback_owned(backend, directory, transaction_id, wal, "resume-after-acknowledged-write")
        if wal.get("status") in {
            "BACKUP_PROVED",
            "CONTROL_PLANE_INSTALLING",
            "CONTROL_PLANE_INSTALLED",
            "CONTROL_PLANE_RESTORED_BEFORE_REINSTALL",
            "CONTROL_PLANE_REINSTALLED",
            "METADATA_PROVED_PRISTINE",
            "CREATING",
        } and not wal.get("writes"):
            return _restore_zero_ack_terminal(backend, directory, transaction_id, wal)
        operations = {row["id"]: row for row in contract["writes"]}
        wal_rows = wal.get("writes", [])
        if not isinstance(wal_rows, list) or len(wal_rows) > 7:
            raise Blocked("wal-operation-invalid")
        for index, row in enumerate(wal_rows):
            operation = operations.get(row.get("id"))
            if (
                not operation
                or operation is not contract["writes"][index]
                or row.get("vault_path") != operation["vault_path"]
            ):
                raise Blocked("wal-operation-invalid")
            if row.get("status") == "intent":
                metadata = backend.metadata(operation["vault_path"])
                if not _pristine(metadata):
                    _mark_zero_ack_ambiguous(backend, directory, transaction_id, wal)
            elif row.get("status") == "acknowledged":
                if row.get("version") != 1:
                    raise Blocked("wal-version-invalid")
                metadata = backend.metadata(operation["vault_path"])
                versions = metadata.get("versions") if isinstance(metadata, dict) else None
                if (
                    metadata.get("current_version") != 1
                    or metadata.get("oldest_version") != 1
                    or not isinstance(versions, dict)
                    or set(versions) != {"1"}
                ):
                    wal["status"] = "OWNERSHIP_AMBIGUOUS_BLOCKED"
                    atomic_json(directory / "wal.json", wal)
                    raise Blocked("ambiguous-write-ownership")
            else:
                raise Blocked("wal-status-invalid")
        return _restore_zero_ack_terminal(backend, directory, transaction_id, wal)
    finally:
        os.close(lock)


def _safe_child_env() -> dict[str, str]:
    allowed = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "XDG_RUNTIME_DIR")
    return {key: value for key in allowed if (value := os.getenv(key))}


def _descendant_pids(root_pid: int) -> list[int]:
    parent_by_pid: dict[int, int] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status_text = (entry / "status").read_text(encoding="ascii")
        except (OSError, UnicodeError):
            continue
        match = re.search(r"^PPid:\s+(\d+)$", status_text, re.MULTILINE)
        if match:
            parent_by_pid[int(entry.name)] = int(match.group(1))
    descendants: list[int] = []
    frontier = [root_pid]
    while frontier:
        parent = frontier.pop()
        children = sorted(pid for pid, ppid in parent_by_pid.items() if ppid == parent)
        descendants.extend(children)
        frontier.extend(children)
    return descendants


_PROCESS_TREE_LOCK = threading.Lock()


def _enable_child_subreaper() -> bool:
    """Enable adoption and return the process's prior subreaper state."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        prior = ctypes.c_int()
        if libc.prctl(37, ctypes.byref(prior), 0, 0, 0) != 0:  # PR_GET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "prctl")
        if prior.value == 0 and libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "prctl")
    except (AttributeError, OSError) as exc:
        raise Blocked("child-subreaper-unavailable") from exc
    return prior.value != 0


def _restore_child_subreaper(prior_enabled: bool) -> None:
    if prior_enabled:
        return
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 0, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "prctl")
    except (AttributeError, OSError) as exc:
        raise Blocked("child-subreaper-restore-failed") from exc


def _reap_pid(pid: int) -> bool:
    try:
        waited, _ = os.waitpid(pid, os.WNOHANG)
        return waited == pid
    except ChildProcessError:
        return not Path(f"/proc/{pid}").exists()


def _cleanup_descendant_pids(pids: set[int], baseline: set[int]) -> None:
    """Terminate and reap all descendants created by one bounded command."""
    pending = set(pids)
    pending.update(set(_descendant_pids(os.getpid())) - baseline)
    for pid in sorted(pending, reverse=True):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        pending.update(set(_descendant_pids(os.getpid())) - baseline)
        pending = {
            pid for pid in pending
            if not _reap_pid(pid) and Path(f"/proc/{pid}").exists()
        }
        if not pending:
            return
        time.sleep(0.01)
    for pid in sorted(pending, reverse=True):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        pending.update(set(_descendant_pids(os.getpid())) - baseline)
        pending = {
            pid for pid in pending
            if not _reap_pid(pid) and Path(f"/proc/{pid}").exists()
        }
        if not pending:
            return
        time.sleep(0.01)
    raise Blocked("child-descendant-cleanup-failed")


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    descendants = _descendant_pids(process.pid)
    for pid in reversed(descendants):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        for pid in reversed(descendants):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def _bounded_process_detailed_serial(
    command: list[str], private_input: bytes, *, max_stdout: int = 65536,
    max_stderr: int = 4096, timeout_seconds: float = 30,
) -> tuple[int, bytes, bytes]:
    baseline_descendants = set(_descendant_pids(os.getpid()))
    tracked_descendants: set[int] = set()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        env=_safe_child_env(),
    )
    assert process.stdin and process.stdout and process.stderr
    os.set_blocking(process.stdin.fileno(), False)
    selector = selectors.DefaultSelector()
    selector.register(process.stdin, selectors.EVENT_WRITE, ("in", len(private_input)))
    selector.register(process.stdout, selectors.EVENT_READ, ("out", max_stdout))
    selector.register(process.stderr, selectors.EVENT_READ, ("err", max_stderr))
    chunks: dict[str, list[bytes]] = {"out": [], "err": []}
    sizes = {"out": 0, "err": 0}
    input_offset = 0
    deadline = time.monotonic() + timeout_seconds
    try:
        while selector.get_map():
            tracked_descendants.update(_descendant_pids(process.pid))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Blocked("child-command-timeout")
            events = selector.select(min(remaining, 1.0))
            if not events and process.poll() is not None:
                for stream in tuple(selector.get_map().values()):
                    selector.unregister(stream.fileobj)
                break
            for key, _ in events:
                channel, limit = key.data
                if channel == "in":
                    if input_offset >= len(private_input):
                        selector.unregister(key.fileobj); process.stdin.close(); continue
                    try:
                        written = os.write(key.fd, private_input[input_offset:input_offset + 65536])
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        selector.unregister(key.fileobj); process.stdin.close(); continue
                    if written <= 0:
                        raise Blocked("child-input-write-failed")
                    input_offset += written
                    if input_offset >= len(private_input):
                        selector.unregister(key.fileobj); process.stdin.close()
                    continue
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                sizes[channel] += len(chunk)
                if sizes[channel] > limit:
                    raise Blocked("child-output-limit")
                chunks[channel].append(chunk)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise Blocked("child-command-timeout")
        code = process.wait(timeout=remaining)
        tracked_descendants.update(set(_descendant_pids(os.getpid())) - baseline_descendants)
        _cleanup_descendant_pids(tracked_descendants, baseline_descendants)
        return code, b"".join(chunks["out"]), b"".join(chunks["err"])
    except BaseException:
        tracked_descendants.update(_descendant_pids(process.pid))
        _terminate_process_tree(process)
        tracked_descendants.update(set(_descendant_pids(os.getpid())) - baseline_descendants)
        _cleanup_descendant_pids(tracked_descendants, baseline_descendants)
        raise
    finally:
        selector.close()


def _bounded_process_detailed(
    command: list[str], private_input: bytes, *, max_stdout: int = 65536,
    max_stderr: int = 4096, timeout_seconds: float = 30,
) -> tuple[int, bytes, bytes]:
    # Subreaper state is process-global. Serialize helpers and restore the
    # caller's original state even when spawn, I/O, timeout, or cleanup fails.
    with _PROCESS_TREE_LOCK:
        prior_enabled = _enable_child_subreaper()
        try:
            return _bounded_process_detailed_serial(
                command, private_input, max_stdout=max_stdout,
                max_stderr=max_stderr, timeout_seconds=timeout_seconds,
            )
        finally:
            _restore_child_subreaper(prior_enabled)


def _bounded_process(
    command: list[str], private_input: bytes, *, max_stdout: int = 65536,
    max_stderr: int = 4096, timeout_seconds: float = 30,
) -> tuple[int, bytes]:
    code, stdout, stderr = _bounded_process_detailed(
        command, private_input, max_stdout=max_stdout, max_stderr=max_stderr,
        timeout_seconds=timeout_seconds,
    )
    if code != 0 or stderr:
        raise Blocked("child-command-failed")
    return code, stdout


class LocalVaultBackend(TransactionBackend):
    """Production adapter. Every secret-bearing operation is stdin-only."""

    def __init__(self, source_root: Path, rclone_config: bytes, approved_fingerprint: str):
        self.source_root = source_root
        self.vault = Path("/usr/local/sbin/atius-vault")
        self.installer = source_root / "modules/rustdesk-fleet/tools/install-phase52-vault-control-plane.sh"
        self.rclone_config = rclone_config
        self.approved_fingerprint = _validate_approved_fingerprint(
            approved_fingerprint, APPROVED_HORISTIC_SSH_FINGERPRINT,
        )
        self._proof_key = secrets.token_bytes(32)
        self._expected: dict[str, str] = {}
        self._public_fingerprint: str | None = None
        self.control_paths = [
            Path("/usr/local/sbin/atius-vault-export-rustdesk-phase52"),
            Path("/usr/local/sbin/atius-vault-export-ssh-phase52"),
            Path("/etc/atius-vault/profiles/rustdesk-phase52-v1.json"),
            Path("/etc/atius-vault/profiles/rclone-giovanni-drive-phase52-v1.json"),
            Path("/etc/sudoers.d/atius-vault-phase52"),
            Path("/home/ubuntu/.ssh/authorized_keys"),
        ]
        self.control_state_path = CONTROL_PLANE_STATE_ROOT

    def _json(self, command: list[str], payload: bytes = b"") -> Any:
        _, raw = _bounded_process(command, payload)
        return strict_json_bytes(raw)

    def _create_raft_snapshot(self, snapshot: Path) -> None:
        """Bridge a Vault CLI snapshot from its container namespace to the host."""
        if snapshot.exists() or snapshot.is_symlink():
            raise Blocked("raft-snapshot-failed")
        container_snapshot = f"/tmp/phase52-raft-{secrets.token_hex(16)}.snapshot"
        staging_dir: Path | None = None
        staged: Path | None = None
        container_save_attempted = False
        published = False
        snapshot_ready = False
        operation_failed = False
        cleanup_failed = False
        try:
            staging_dir = Path(tempfile.mkdtemp(prefix=".raft-staging-", dir=snapshot.parent))
            staging_descriptor = os.open(
                staging_dir,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            try:
                staging_info = os.fstat(staging_descriptor)
                if (
                    not stat.S_ISDIR(staging_info.st_mode)
                    or staging_info.st_uid != os.geteuid()
                ):
                    raise Blocked("raft-snapshot-failed")
                os.fchmod(staging_descriptor, 0o700)
                os.fsync(staging_descriptor)
            finally:
                os.close(staging_descriptor)
            staged = staging_dir / Path(container_snapshot).name
            container_save_attempted = True
            _bounded_process(
                [str(self.vault), "operator", "raft", "snapshot", "save", container_snapshot],
                b"", max_stdout=4096,
            )
            _bounded_process(
                [str(PODMAN), "cp", f"{VAULT_CONTAINER}:{container_snapshot}", str(staging_dir)],
                b"", max_stdout=4096,
            )
            descriptor = os.open(staged, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                info = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_uid != os.geteuid()
                    or info.st_size == 0
                ):
                    raise Blocked("raft-snapshot-failed")
                os.fchmod(descriptor, 0o600)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except (Blocked, OSError):
            operation_failed = True
        finally:
            if container_save_attempted:
                try:
                    _bounded_process(
                        [str(PODMAN), "exec", VAULT_CONTAINER, "rm", "-f", "--", container_snapshot],
                        b"", max_stdout=4096,
                    )
                except (Blocked, OSError):
                    cleanup_failed = True
        if not operation_failed and not cleanup_failed and staged is not None:
            try:
                os.link(staged, snapshot, follow_symlinks=False)
                published = True
                staged.unlink()
                _fsync_file_and_parent(snapshot)
                snapshot_ready = True
            except (Blocked, OSError):
                operation_failed = True
        try:
            if staged is not None and (staged.exists() or staged.is_symlink()):
                staged.unlink()
            if staging_dir is not None:
                staging_dir.rmdir()
                _fsync_parent(staging_dir)
        except OSError:
            operation_failed = True
        if published and (operation_failed or cleanup_failed or not snapshot_ready):
            try:
                snapshot.unlink(missing_ok=True)
                _fsync_parent(snapshot)
                snapshot_ready = False
            except OSError:
                operation_failed = True
        if operation_failed or cleanup_failed or not snapshot_ready:
            raise Blocked("raft-snapshot-failed")

    def create_backups(self, transaction_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
        snapshot = transaction_dir / "raft.snapshot"
        self._create_raft_snapshot(snapshot)
        bundle = transaction_dir / "control-plane.tar"
        records = []
        file_bytes: list[tuple[str, bytes]] = []
        for index, path in enumerate(self.control_paths):
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise Blocked("control-plane-target-identity-invalid")
                raw = path.read_bytes()
                member = f"files/{index}"
                records.append({
                    "path": path.as_posix(), "present": True, "member": member,
                    "sha256": hashlib.sha256(raw).hexdigest(), "mode": stat.S_IMODE(info.st_mode),
                    "uid": info.st_uid, "gid": info.st_gid,
                })
                file_bytes.append((member, raw))
            else:
                records.append({"path": path.as_posix(), "present": False})
        state_records: list[dict[str, Any]] = []
        state_files: list[tuple[str, bytes]] = []
        state_root = self.control_state_path
        if state_root.exists() or state_root.is_symlink():
            root_info = state_root.lstat()
            if state_root.is_symlink() or not stat.S_ISDIR(root_info.st_mode):
                raise Blocked("control-plane-target-identity-invalid")
            for current, dir_names, file_names in os.walk(state_root, topdown=True, followlinks=False):
                current_path = Path(current)
                for name in sorted(dir_names):
                    path = current_path / name
                    info = path.lstat()
                    if path.is_symlink() or not stat.S_ISDIR(info.st_mode):
                        raise Blocked("control-plane-target-identity-invalid")
                    state_records.append({
                        "path": path.relative_to(state_root).as_posix(), "kind": "directory",
                        "mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid,
                    })
                for name in sorted(file_names):
                    path = current_path / name
                    info = path.lstat()
                    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise Blocked("control-plane-target-identity-invalid")
                    raw = path.read_bytes()
                    member = f"state/{len(state_files)}"
                    state_records.append({
                        "path": path.relative_to(state_root).as_posix(), "kind": "file",
                        "member": member, "sha256": hashlib.sha256(raw).hexdigest(),
                        "mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid,
                    })
                    state_files.append((member, raw))
            state_tree = {
                "path": state_root.as_posix(), "present": True,
                "mode": stat.S_IMODE(root_info.st_mode), "uid": root_info.st_uid,
                "gid": root_info.st_gid, "entries": sorted(state_records, key=lambda row: row["path"]),
            }
        else:
            state_tree = {"path": state_root.as_posix(), "present": False, "entries": []}
        control_manifest = {
            "schema": "phase52-gate-b-control-plane-backup-v1",
            "targets": records,
            "state_tree": state_tree,
            "secret_material_present": False,
        }
        descriptor = os.open(bundle, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as raw_handle:
            with tarfile.open(fileobj=raw_handle, mode="w") as archive:
                manifest_raw = _encoded(control_manifest)
                member_info = tarfile.TarInfo("control-plane-manifest.json")
                member_info.size = len(manifest_raw); member_info.mode = 0o600
                member_info.uid = 0; member_info.gid = 0; member_info.mtime = 0
                archive.addfile(member_info, io.BytesIO(manifest_raw))
                for member, raw in file_bytes:
                    member_info = tarfile.TarInfo(member)
                    member_info.size = len(raw); member_info.mode = 0o600
                    member_info.uid = 0; member_info.gid = 0; member_info.mtime = 0
                    archive.addfile(member_info, io.BytesIO(raw))
                for member, raw in state_files:
                    member_info = tarfile.TarInfo(member)
                    member_info.size = len(raw); member_info.mode = 0o600
                    member_info.uid = 0; member_info.gid = 0; member_info.mtime = 0
                    archive.addfile(member_info, io.BytesIO(raw))
            raw_handle.flush()
            os.fsync(raw_handle.fileno())
        _fsync_parent(bundle)
        manifest = {
            "schema": "phase52-gate-b-backup-manifest-v1",
            "raft_snapshot_sha256": sha256_file(snapshot),
            "control_plane_bundle_sha256": sha256_file(bundle),
            "secret_material_present": False,
        }
        atomic_json(transaction_dir / "manifest.json", manifest)
        return {"raft_snapshot_valid": True, "control_plane_bundle_valid": True}

    def prove_isolated_snapshot_restore(self, transaction_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
        command = [
            "unshare", "--net", "--mount", "--fork", "--pid", "--mount-proc", sys.executable,
            str(Path(__file__).resolve()), "isolated-raft-restore-proof",
            "--snapshot", str(transaction_dir / "raft.snapshot"),
        ]
        return self._json(command)

    def install_control_plane(self, transaction_dir: Path, managed_sources: dict[str, bytes]) -> None:
        if not managed_sources:
            raise Blocked("managed-source-bundle-missing")
        exact = {
            "atius-vault-export-rustdesk-phase52": self.source_root / "modules/rustdesk-fleet/tools/atius-vault-export-rustdesk-phase52",
            "atius-vault-export-ssh-phase52": self.source_root / "modules/rustdesk-fleet/tools/atius-vault-export-ssh-phase52",
            "phase52-vault-control-plane.json": self.source_root / "modules/rustdesk-fleet/contracts/phase52-vault-control-plane.json",
        }
        if set(managed_sources) != set(exact):
            raise Blocked("managed-source-bundle-invalid")
        for name, path in exact.items():
            if not path.is_file() or path.is_symlink() or path.read_bytes() != managed_sources[name]:
                raise Blocked("managed-source-rehash-failed")
        source_dir = Path(tempfile.mkdtemp(prefix="control-plane-key-", dir="/dev/shm"))
        try:
            source_dir.chmod(0o700)
            authorized = Path("/home/ubuntu/.ssh/authorized_keys")
            rows = []
            legacy = 'command="/home/ubuntu/.local/bin/atius-vault-export-ssh",no-agent-forwarding,no-X11-forwarding,no-pty,no-port-forwarding'
            for line in authorized.read_text(encoding="utf-8").splitlines():
                tokens = line.split()
                try:
                    key_index = next(index for index, token in enumerate(tokens) if token.startswith(("ssh-", "ecdsa-")))
                except StopIteration:
                    continue
                if " ".join(tokens[:key_index]) == legacy and key_index + 1 < len(tokens):
                    rows.append(" ".join(tokens[key_index:]))
            if len(rows) != 1:
                raise Blocked("authorized-key-entry-not-unique")
            public = source_dir / "horistic.pub"
            public.write_text(rows[0] + "\n", encoding="utf-8")
            public.chmod(0o600)
            _, fingerprint_raw = _bounded_process(["ssh-keygen", "-lf", str(public), "-E", "sha256"], b"", max_stdout=4096)
            parts = fingerprint_raw.decode().split()
            if len(parts) < 2 or not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", parts[1]):
                raise Blocked("authorized-key-fingerprint-invalid")
            approved = _validate_approved_fingerprint(parts[1], self.approved_fingerprint)
            try: _bounded_process([str(self.installer), "--install", "--authorized-key-file", str(public), "--expected-fingerprint", approved], b"", max_stdout=4096)
            except Blocked: raise Blocked("control-plane-install-failed")
        finally:
            shutil.rmtree(source_dir, ignore_errors=True)

    def restore_control_plane(self, transaction_dir: Path) -> None:
        # Every restore is bound to the original outer manifest.  Do this
        # immediately before reading or mutating any live control-plane path.
        _validate_backup_artifacts(transaction_dir, require_root=os.geteuid() == 0)
        bundle = transaction_dir / "control-plane.tar"
        with tarfile.open(bundle, mode="r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if (
                len(names) != len(set(names))
                or any(
                    not member.isfile() or member.issym() or member.islnk()
                    or member.size < 0 or member.size > MAX_CONTROL_PLANE_PAYLOAD
                    for member in members
                )
                or sum(member.size for member in members) > MAX_CONTROL_PLANE_BUNDLE
            ):
                raise Blocked("control-plane-backup-invalid")
            manifest_handle = archive.extractfile("control-plane-manifest.json")
            if manifest_handle is None:
                raise Blocked("control-plane-backup-invalid")
            manifest = strict_json_bytes(manifest_handle.read())
            if (
                not isinstance(manifest, dict)
                or set(manifest) != {"schema", "targets", "state_tree", "secret_material_present"}
                or manifest.get("schema") != "phase52-gate-b-control-plane-backup-v1"
                or manifest.get("secret_material_present") is not False
                or not isinstance(manifest.get("targets"), list)
                or not isinstance(manifest.get("state_tree"), dict)
            ):
                raise Blocked("control-plane-backup-invalid")
            expected_names = {"control-plane-manifest.json"} | {
                row["member"] for row in manifest.get("targets", []) if row.get("present") is True
            }
            tree = manifest["state_tree"]
            entries = tree.get("entries")
            def metadata_fields_valid(row: dict[str, Any]) -> bool:
                return (
                    type(row.get("mode")) is int and 0 <= row["mode"] <= 0o7777
                    and type(row.get("uid")) is int and 0 <= row["uid"] <= 2**31 - 1
                    and type(row.get("gid")) is int and 0 <= row["gid"] <= 2**31 - 1
                )
            if (
                tree.get("path") != self.control_state_path.as_posix()
                or type(tree.get("present")) is not bool
                or not isinstance(entries, list)
                or set(tree) != (
                    {"path", "present", "mode", "uid", "gid", "entries"}
                    if tree.get("present") is True
                    else {"path", "present", "entries"}
                )
                or (tree.get("present") is False and entries != [])
                or (tree.get("present") is True and not metadata_fields_valid(tree))
            ):
                raise Blocked("control-plane-backup-invalid")
            targets = manifest["targets"]
            if len(targets) != len(self.control_paths):
                raise Blocked("control-plane-backup-invalid")
            for index, row in enumerate(targets):
                if not isinstance(row, dict) or row.get("path") != self.control_paths[index].as_posix():
                    raise Blocked("control-plane-backup-invalid")
                expected = (
                    {"path", "present", "member", "sha256", "mode", "uid", "gid"}
                    if row.get("present") is True else {"path", "present"}
                )
                if (
                    set(row) != expected or type(row.get("present")) is not bool
                    or (
                        row.get("present") is True
                        and (
                            row.get("member") != f"files/{index}"
                            or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("sha256", "")))
                            or not metadata_fields_valid(row)
                        )
                    )
                ):
                    raise Blocked("control-plane-backup-invalid")
            entry_paths: set[str] = set()
            entry_members: set[str] = set()
            for row in entries:
                if not isinstance(row, dict) or row.get("kind") not in {"directory", "file"}:
                    raise Blocked("control-plane-backup-invalid")
                relative = Path(row.get("path", ""))
                if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                    raise Blocked("control-plane-backup-invalid")
                if row["path"] in entry_paths:
                    raise Blocked("control-plane-backup-invalid")
                entry_paths.add(row["path"])
                required = {"path", "kind", "mode", "uid", "gid"}
                if row["kind"] == "file":
                    required |= {"member", "sha256"}
                    if row.get("member") in entry_members:
                        raise Blocked("control-plane-backup-invalid")
                    entry_members.add(row["member"])
                    expected_names.add(row["member"])
                if (
                    set(row) != required
                    or not metadata_fields_valid(row)
                    or (
                        row["kind"] == "file"
                        and (
                            not re.fullmatch(r"state/[0-9]+", str(row.get("member", "")))
                            or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("sha256", "")))
                        )
                    )
                ):
                    raise Blocked("control-plane-backup-invalid")
            directories = {row["path"] for row in entries if row["kind"] == "directory"}
            for row in entries:
                parent = Path(row["path"]).parent.as_posix()
                if parent != "." and parent not in directories:
                    raise Blocked("control-plane-backup-invalid")
            payload_members = [
                row["member"] for row in targets if row["present"]
            ] + [row["member"] for row in entries if row["kind"] == "file"]
            if len(payload_members) != len(set(payload_members)):
                raise Blocked("control-plane-backup-invalid")
            if set(names) != expected_names:
                raise Blocked("control-plane-backup-invalid")

            # Stage and hash every payload before touching the first live byte.
            # Both per-member and aggregate bounds were checked above, so this
            # allocation is explicitly finite.
            staged_payloads: dict[str, bytes] = {}
            payload_rows = [row for row in targets if row["present"]] + [
                row for row in entries if row["kind"] == "file"
            ]
            for row in payload_rows:
                handle = archive.extractfile(row["member"])
                if handle is None:
                    raise Blocked("control-plane-backup-invalid")
                raw = handle.read(MAX_CONTROL_PLANE_PAYLOAD + 1)
                if (
                    len(raw) > MAX_CONTROL_PLANE_PAYLOAD
                    or hashlib.sha256(raw).hexdigest() != row["sha256"]
                ):
                    raise Blocked("control-plane-backup-invalid")
                staged_payloads[row["member"]] = raw

            # Prevalidate every independent live target and the entire mutable
            # tree.  No mutation is permitted until this inventory is complete.
            for path in self.control_paths:
                try:
                    parent_info = path.parent.lstat()
                except OSError as exc:
                    raise Blocked("control-plane-target-identity-invalid") from exc
                if path.parent.is_symlink() or not stat.S_ISDIR(parent_info.st_mode):
                    raise Blocked("control-plane-target-identity-invalid")
                if path.exists() or path.is_symlink():
                    info = path.lstat()
                    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise Blocked("control-plane-target-identity-invalid")
            # Validate the whole mutable state tree before deleting a byte.
            state_root = self.control_state_path
            try:
                state_parent_info = state_root.parent.lstat()
            except OSError as exc:
                raise Blocked("control-plane-target-identity-invalid") from exc
            if state_root.parent.is_symlink() or not stat.S_ISDIR(state_parent_info.st_mode):
                raise Blocked("control-plane-target-identity-invalid")
            if state_root.exists() or state_root.is_symlink():
                root_info = state_root.lstat()
                if state_root.is_symlink() or not stat.S_ISDIR(root_info.st_mode):
                    raise Blocked("control-plane-target-identity-invalid")
                for current, dir_names, file_names in os.walk(state_root, topdown=True, followlinks=False):
                    current_path = Path(current)
                    for name in dir_names:
                        path = current_path / name; info = path.lstat()
                        if path.is_symlink() or not stat.S_ISDIR(info.st_mode):
                            raise Blocked("control-plane-target-identity-invalid")
                    for name in file_names:
                        path = current_path / name; info = path.lstat()
                        if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                            raise Blocked("control-plane-target-identity-invalid")
            for row in manifest.get("targets", []):
                path = Path(row["path"])
                if row["present"]:
                    raw = staged_payloads[row["member"]]
                    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
                    temporary = Path(temporary_name)
                    try:
                        os.fchown(descriptor, row["uid"], row["gid"]); os.fchmod(descriptor, row["mode"])
                        offset = 0
                        while offset < len(raw):
                            written = os.write(descriptor, raw[offset:])
                            if written <= 0:
                                raise Blocked("control-plane-restore-write-failed")
                            offset += written
                        os.fsync(descriptor); os.close(descriptor); descriptor = -1
                        os.replace(temporary, path); _fsync_parent(path)
                    finally:
                        if descriptor >= 0: os.close(descriptor)
                        temporary.unlink(missing_ok=True)
                elif path.exists() or path.is_symlink():
                    info = path.lstat()
                    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise Blocked("control-plane-restore-drift")
                    path.unlink(); _fsync_parent(path)
            if state_root.exists():
                for current, dir_names, file_names in os.walk(state_root, topdown=False, followlinks=False):
                    current_path = Path(current)
                    for name in file_names:
                        path = current_path / name
                        path.unlink(); _fsync_parent(path)
                    for name in dir_names:
                        path = current_path / name
                        path.rmdir(); _fsync_parent(path)
                state_root.rmdir()
                _fsync_parent(state_root)
            if tree["present"]:
                state_root.mkdir(mode=tree["mode"])
                _fsync_parent(state_root)
                os.chown(state_root, tree["uid"], tree["gid"])
                os.chmod(state_root, tree["mode"])
                directory_rows = sorted(
                    (row for row in entries if row["kind"] == "directory"),
                    key=lambda row: len(Path(row["path"]).parts),
                )
                for row in directory_rows:
                    path = state_root / row["path"]
                    path.mkdir(mode=row["mode"])
                    _fsync_parent(path)
                    os.chown(path, row["uid"], row["gid"]); os.chmod(path, row["mode"])
                for row in (item for item in entries if item["kind"] == "file"):
                    raw = staged_payloads[row["member"]]
                    path = state_root / row["path"]
                    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, row["mode"])
                    try:
                        os.fchown(descriptor, row["uid"], row["gid"]); os.fchmod(descriptor, row["mode"])
                        offset = 0
                        while offset < len(raw):
                            written = os.write(descriptor, raw[offset:])
                            if written <= 0:
                                raise Blocked("control-plane-restore-write-failed")
                            offset += written
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                    _fsync_parent(path)
                for directory_row in reversed(directory_rows):
                    _fsync_directory(state_root / directory_row["path"])
                _fsync_directory(state_root)
                _fsync_parent(state_root)
            for row in manifest.get("targets", []):
                path = Path(row["path"])
                if row["present"]:
                    info = path.lstat()
                    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != row["mode"] or info.st_uid != row["uid"] or info.st_gid != row["gid"] or sha256_file(path) != row["sha256"]:
                        raise Blocked("control-plane-restore-drift")
                elif path.exists() or path.is_symlink():
                    raise Blocked("control-plane-restore-drift")
            if tree["present"]:
                root_info = state_root.lstat()
                if (
                    state_root.is_symlink() or not stat.S_ISDIR(root_info.st_mode)
                    or stat.S_IMODE(root_info.st_mode) != tree["mode"]
                    or root_info.st_uid != tree["uid"] or root_info.st_gid != tree["gid"]
                ):
                    raise Blocked("control-plane-restore-drift")
                observed_paths = set()
                for current, dir_names, file_names in os.walk(state_root, topdown=True, followlinks=False):
                    current_path = Path(current)
                    for name in dir_names + file_names:
                        observed_paths.add((current_path / name).relative_to(state_root).as_posix())
                if observed_paths != {row["path"] for row in entries}:
                    raise Blocked("control-plane-restore-drift")
                for row in entries:
                    path = state_root / row["path"]; info = path.lstat()
                    if stat.S_IMODE(info.st_mode) != row["mode"] or info.st_uid != row["uid"] or info.st_gid != row["gid"]:
                        raise Blocked("control-plane-restore-drift")
                    if row["kind"] == "directory" and (path.is_symlink() or not stat.S_ISDIR(info.st_mode)):
                        raise Blocked("control-plane-restore-drift")
                    if row["kind"] == "file" and (
                        path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or sha256_file(path) != row["sha256"]
                    ):
                        raise Blocked("control-plane-restore-drift")
            elif state_root.exists() or state_root.is_symlink():
                raise Blocked("control-plane-restore-drift")

    def metadata(self, vault_path: str) -> dict[str, Any]:
        code, stdout, stderr = _bounded_process_detailed(
            [str(self.vault), "kv", "metadata", "get", "-format=json", vault_path], b"",
        )
        if code == 2 and stdout == b"":
            expected = f"No value found at {vault_path}\n".encode()
            if stderr == expected:
                return {"current_version": 0, "oldest_version": 0, "versions": {}}
            raise Blocked("vault-metadata-absence-ambiguous")
        if code != 0 or stderr:
            raise Blocked("vault-metadata-read-failed")
        payload = strict_json_bytes(stdout)
        if (
            not isinstance(payload, dict)
            or payload.get("mount_type") != "kv"
            or "data" not in payload
        ):
            raise Blocked("vault-metadata-response-invalid")
        data = payload["data"]
        required = {"current_version", "oldest_version", "versions"}
        if (
            not isinstance(data, dict)
            or not required <= set(data)
            or type(data["current_version"]) is not int
            or type(data["oldest_version"]) is not int
            or not isinstance(data["versions"], dict)
        ):
            raise Blocked("vault-metadata-response-invalid")
        return {
            "current_version": data["current_version"],
            "oldest_version": data["oldest_version"],
            "versions": data["versions"],
        }

    def generate_values(self, contract: dict[str, Any], runtime_dir: Path) -> dict[str, dict[str, str]]:
        image = contract["generator"]["immutable_reference"]
        inspect = self._json(["podman", "image", "inspect", image])
        if (
            not isinstance(inspect, list) or len(inspect) != 1 or not isinstance(inspect[0], dict)
            or inspect[0].get("Architecture") != "arm64"
            or not any(
                isinstance(item, str) and item.endswith("@" + contract["generator"]["linux_arm64_digest"])
                for item in inspect[0].get("RepoDigests", [])
            )
        ):
            raise Blocked("generator-image-digest-drift")
        _, raw = _bounded_process([
            "podman", "run", "--rm", "--network", "none", "--pull", "never",
            "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,mode=0700",
            "--entrypoint", "rustdesk-utils", image, "genkeypair",
        ], b"", max_stdout=4096, max_stderr=4096, timeout_seconds=30)
        lines = [line.strip() for line in raw.decode("ascii", "strict").splitlines() if line.strip()]
        labelled = {}
        for line in lines:
            match = re.fullmatch(r"(?i)(private|public)(?: key)?\s*:\s*([A-Za-z0-9+/]{43}=?)", line)
            if match:
                labelled[match.group(1).lower()] = match.group(2)
        if set(labelled) != {"private", "public"}:
            raise Blocked("generator-output-invalid")
        for value in labelled.values():
            try:
                decoded = base64.b64decode(value + "=" * (-len(value) % 4), validate=True)
            except Exception as exc:
                raise Blocked("generator-output-invalid") from exc
            if len(decoded) != 32:
                raise Blocked("generator-output-invalid")
        private_key = labelled["private"]
        public_key = labelled["public"]
        self._public_fingerprint = hashlib.sha256(public_key.encode("ascii")).hexdigest()
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        passwords = ["R" + "".join(secrets.choice(alphabet) for _ in range(31)) for _ in range(5)]
        if len(set(passwords)) != 5:
            raise Blocked("generated-password-distinctness-failed")
        try:
            config = self.rclone_config.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Blocked("rclone-private-input-invalid") from exc
        if len(self.rclone_config) > 131072 or not config.startswith("[giovanni-drive]\n") or "\n[" in config[1:]:
            raise Blocked("rclone-private-input-invalid")
        values = {
            "rustdesk-server-identity": {"private_key": private_key, "public_key": public_key},
            "rustdesk-password-atius-srv-1": {"permanent_password": passwords[0]},
            "rustdesk-password-atius-srv-2": {"permanent_password": passwords[1]},
            "rustdesk-password-atius-srv-3": {"permanent_password": passwords[2]},
            "rustdesk-password-horistic-srv": {"permanent_password": passwords[3]},
            "rustdesk-password-giovanni-w11-pc": {"permanent_password": passwords[4]},
            "rclone-config": {"rclone_conf": config},
        }
        for operation in contract["writes"]:
            for field, value in values[operation["id"]].items():
                self._expected[f"{operation['vault_path']}#{field}"] = hmac.new(
                    self._proof_key, value.encode(), hashlib.sha256,
                ).hexdigest()
        return values

    def put_cas0_stdin(self, operation: dict[str, Any], encoded_private_json: bytes) -> dict[str, Any]:
        code, stdout, stderr = _bounded_process_detailed(
            [str(self.vault), "kv", "put", "-cas=0", "-format=json", operation["vault_path"], "@-"],
            encoded_private_json,
        )
        if code != 0:
            if (
                stdout == b""
                and b"check-and-set parameter did not match the current version" in stderr
            ):
                raise CasConflict("cas-conflict")
            raise Blocked("vault-put-failed")
        if stderr:
            raise Blocked("vault-put-failed")
        payload = strict_json_bytes(stdout)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or type(data.get("version")) is not int:
            raise Blocked("put-result-invalid")
        return {"version": data["version"]}

    def soft_delete_exact_version(self, vault_path: str, version: int) -> None:
        try: _bounded_process([str(self.vault), "kv", "delete", "-versions", str(version), vault_path], b"", max_stdout=4096)
        except Blocked: raise Blocked("exact-version-soft-delete-failed")
        observed = self.metadata(vault_path)
        version_row = observed.get("versions", {}).get(str(version)) if isinstance(observed,dict) else None
        if not isinstance(version_row,dict) or not isinstance(version_row.get("deletion_time"),str) or not version_row["deletion_time"] or version_row.get("destroyed") is not False:
            raise Blocked("exact-version-soft-delete-unconfirmed")

    def verify_created_values(self, contract: dict[str, Any], expected_versions: list[dict[str, Any]]) -> dict[str, Any]:
        if len(expected_versions) != 7:
            raise Blocked("created-value-verification-failed")
        password_proofs = set()
        for operation in contract["writes"]:
            payload = self._json([
                str(self.vault), "kv", "get", "-version=1", "-format=json", operation["vault_path"],
            ])
            data = payload.get("data", {}).get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict) or set(data) != set(operation["fields"]):
                raise Blocked("created-field-cardinality-invalid")
            for field, value in data.items():
                if not isinstance(value, str) or not hmac.compare_digest(
                    hmac.new(self._proof_key, value.encode(), hashlib.sha256).hexdigest(),
                    self._expected.get(f"{operation['vault_path']}#{field}", ""),
                ):
                    raise Blocked("created-value-proof-mismatch")
                if field == "permanent_password":
                    password_proofs.add(hmac.new(self._proof_key, value.encode(), hashlib.sha256).digest())
                elif field == "public_key" and hashlib.sha256(value.encode("ascii")).hexdigest() != self._public_fingerprint:
                    raise Blocked("created-public-fingerprint-mismatch")
                elif field == "rclone_conf" and (
                    not value.startswith("[giovanni-drive]\n") or "\n[" in value[1:]
                ):
                    raise Blocked("created-rclone-stanza-invalid")
            first = self.metadata(operation["vault_path"])
            second = self.metadata(operation["vault_path"])
            if first != second or first.get("current_version") != 1 or set(first.get("versions", {})) != {"1"}:
                raise Blocked("created-version-metadata-invalid")
        if len(password_proofs) != 5:
            raise Blocked("created-password-distinctness-failed")
        return {"status": "PASS", "write_count": 7, "secret_material_present": False}


def _validate_isolated_restore_identity(pre: Any, post: Any) -> None:
    if (
        not isinstance(pre, dict)
        or set(pre) != {"cluster_id", "raft_sha256", "sentinel_written"}
        or pre.get("sentinel_written") is not True
        or not isinstance(pre.get("cluster_id"), str)
        or not pre["cluster_id"]
        or not re.fullmatch(r"[a-f0-9]{64}", str(pre.get("raft_sha256", "")))
        or not isinstance(post, dict)
        or set(post) != {"cluster_id", "raft_sha256", "sealed", "storage_type"}
        or not isinstance(post.get("cluster_id"), str)
        or not post["cluster_id"]
        or not re.fullmatch(r"[a-f0-9]{64}", str(post.get("raft_sha256", "")))
        or post.get("sealed") is not True
        or post.get("storage_type") != "raft"
    ):
        raise Blocked("isolated-vault-restore-identity-invalid")
    if (
        hmac.compare_digest(pre["cluster_id"], post["cluster_id"])
        or hmac.compare_digest(pre["raft_sha256"], post["raft_sha256"])
    ):
        raise Blocked("isolated-vault-restore-noop")


def isolated_restore_proof(snapshot: Path) -> int:
    if not snapshot.is_file() or snapshot.is_symlink() or snapshot.stat().st_size == 0:
        return 2
    vault_bin = shutil.which("vault", path=_safe_child_env().get("PATH"))
    if not vault_bin:
        raise Blocked("isolated-vault-binary-missing")
    _, inspected = _bounded_process(
        [vault_bin, "operator", "raft", "snapshot", "inspect", str(snapshot)], b"",
        max_stdout=65536, max_stderr=4096, timeout_seconds=30,
    )
    if not inspected:
        raise Blocked("isolated-vault-snapshot-inspect-failed")
    _bounded_process(
        ["ip", "link", "set", "lo", "up"], b"",
        max_stdout=1024, max_stderr=1024, timeout_seconds=5,
    )
    runtime = Path(tempfile.mkdtemp(prefix="phase52-vault-restore-", dir="/dev/shm"))
    runtime.chmod(0o700)
    process: subprocess.Popen[bytes] | None = None
    try:
        config = runtime / "vault.hcl"
        config.write_text(
            'disable_mlock = true\nui = false\n'
            f'storage "raft" {{ path = "{runtime / "raft"}" node_id = "phase52-disposable" }}\n'
            'listener "tcp" { address = "127.0.0.1:18202" tls_disable = true }\n',
            encoding="utf-8",
        )
        config.chmod(0o600)
        base = "http://127.0.0.1:18202"

        def start() -> subprocess.Popen[bytes]:
            # Do not create another session/process group.  The enclosing
            # bounded unshare process owns the group, so a deadline kill reaches
            # this Vault child as well.
            return subprocess.Popen(
                [vault_bin, "server", "-config", str(config)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_safe_child_env(),
                close_fds=True,
            )

        def stop(child: subprocess.Popen[bytes] | None) -> None:
            if child is None or child.poll() is not None:
                return
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)

        def health() -> dict[str, Any]:
            request = urllib.request.Request(base + "/v1/sys/health")
            try:
                with urllib.request.urlopen(request, timeout=1) as response:
                    raw = response.read(131073)
            except urllib.error.HTTPError as exc:
                raw = exc.read(131073)
            payload = strict_json_bytes(raw)
            if not isinstance(payload, dict):
                raise Blocked("isolated-vault-health-invalid")
            return payload

        def wait_health(child: subprocess.Popen[bytes]) -> dict[str, Any]:
            deadline = time.monotonic() + 15
            while True:
                try:
                    return health()
                except (OSError, Blocked):
                    if time.monotonic() >= deadline or child.poll() is not None:
                        raise Blocked("isolated-vault-start-failed")
                    time.sleep(0.1)

        def request(path: str, payload: bytes, token: str | None = None) -> bytes:
            headers = {
                "Content-Type": (
                    "application/octet-stream"
                    if path.startswith("/v1/sys/storage/raft/snapshot")
                    else "application/json"
                )
            }
            if token is not None:
                headers["X-Vault-Token"] = token
            method = "POST" if path == "/v1/sys/storage/raft/snapshot?force=true" else "PUT"
            req = urllib.request.Request(base + path, data=payload, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read(131073)
            if len(raw) > 131072:
                raise Blocked("isolated-vault-response-too-large")
            return raw

        process = start()
        wait_health(process)
        init = strict_json_bytes(request("/v1/sys/init", b'{"secret_shares":1,"secret_threshold":1}'))
        token = init.get("root_token"); keys = init.get("keys")
        if not isinstance(token, str) or not isinstance(keys, list) or len(keys) != 1 or not isinstance(keys[0], str):
            raise Blocked("isolated-vault-init-failed")
        request("/v1/sys/unseal", _encoded({"key": keys[0]}))
        unsealed_health = wait_health(process)
        pre_cluster_id = unsealed_health.get("cluster_id")
        if not isinstance(pre_cluster_id, str) or not pre_cluster_id:
            raise Blocked("isolated-vault-cluster-identity-missing")
        request(
            "/v1/cubbyhole/phase52-restore-sentinel",
            b'{"marker":"phase52-pre-restore"}',
            token,
        )
        raft_db = runtime / "raft" / "raft.db"
        if not raft_db.is_file() or raft_db.is_symlink():
            raise Blocked("isolated-vault-raft-storage-missing")
        pre_identity = {
            "cluster_id": pre_cluster_id,
            "raft_sha256": sha256_file(raft_db),
            "sentinel_written": True,
        }
        request("/v1/sys/storage/raft/snapshot?force=true", snapshot.read_bytes(), token)
        # A force restore replaces the disposable cluster's seal and token
        # material.  Never use the bootstrap token as post-restore evidence.
        del token, keys, init
        stop(process)
        process = None

        try:
            raft_info = raft_db.lstat()
        except OSError as exc:
            raise Blocked("isolated-vault-raft-storage-missing") from exc
        if (
            raft_db.is_symlink()
            or not stat.S_ISREG(raft_info.st_mode)
            or raft_info.st_nlink != 1
            or raft_info.st_size <= 0
        ):
            raise Blocked("isolated-vault-raft-storage-missing")

        process = start()
        health_payload = wait_health(process)
        if process.poll() is not None:
            raise Blocked("isolated-vault-restore-failed")
        if (
            health_payload.get("initialized") is not True
            or health_payload.get("sealed") is not True
            or health_payload.get("storage_type") != "raft"
        ):
            raise Blocked("isolated-vault-post-restore-read-failed")
        _validate_isolated_restore_identity(
            pre_identity,
            {
                "cluster_id": health_payload.get("cluster_id"),
                "raft_sha256": sha256_file(raft_db),
                "sealed": health_payload.get("sealed"),
                "storage_type": health_payload.get("storage_type"),
            },
        )
        result = {"status": "PASS", "network_namespace": "isolated", "host_listener": False, "public_listener": False, "port_bindings": [], "integrity": "PASS"}
        raw_result = _encoded(result)
        offset = 0
        while offset < len(raw_result):
            written = os.write(sys.stdout.fileno(), raw_result[offset:])
            if written <= 0:
                raise Blocked("isolated-proof-output-failed")
            offset += written
        return 0
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        shutil.rmtree(runtime, ignore_errors=True)


def _reviewed_live_context(
    bundle_root: Path,
    transaction_id: str,
    expected_hash: str,
    deadline_epoch: int,
) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise Blocked("root-required")
    if not TX_ID.fullmatch(transaction_id):
        raise Blocked("transaction-id-invalid")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
        raise Blocked("reviewed-bundle-hash-invalid")
    if type(deadline_epoch) is not int or time.time() >= deadline_epoch:
        raise Blocked("remote-deadline-expired")
    root = bundle_root
    try:
        info = root.lstat()
    except OSError as exc:
        raise Blocked("reviewed-bundle-root-invalid") from exc
    if (
        not root.is_absolute() or root.is_symlink() or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700
        or not root.as_posix().startswith("/dev/shm/atius-phase52-reviewed-")
    ):
        raise Blocked("reviewed-bundle-root-invalid")
    manifest = strict_json_bytes((root / "manifest.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {
            "schema", "hash_set_sha256", "sealed_sources", "gate_a", "files",
            "secret_material_present",
        }
        or manifest.get("schema") != "phase52-reviewed-root-bundle-v1"
        or manifest.get("secret_material_present") is not False
        or not isinstance(manifest.get("files"), list)
    ):
        raise Blocked("reviewed-bundle-manifest-invalid")
    sealed_sources = manifest.get("sealed_sources")
    gate_a = manifest.get("gate_a")
    if (
        not isinstance(sealed_sources, list)
        or not isinstance(gate_a, dict)
        or set(gate_a) != {"path", "sha256", "managed_sources"}
        or not isinstance(gate_a.get("managed_sources"), list)
    ):
        raise Blocked("reviewed-bundle-manifest-invalid")
    canonical = {"sealed_sources": sealed_sources, "gate_a": gate_a}
    canonical_hash = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if manifest.get("hash_set_sha256") != canonical_hash or canonical_hash != expected_hash:
        raise Blocked("reviewed-bundle-hash-invalid")
    projected = sealed_sources + gate_a["managed_sources"] + [
        {"path": gate_a["path"], "sha256": gate_a["sha256"]}
    ]
    if any(
        not isinstance(row, dict)
        or set(row) != {"path", "sha256"}
        or not isinstance(row["path"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"])
        for row in projected
    ):
        raise Blocked("reviewed-bundle-manifest-invalid")
    projected_map = {row["path"]: row["sha256"] for row in projected}
    if len(projected_map) != len(projected):
        raise Blocked("reviewed-bundle-manifest-invalid")
    rows: dict[str, bytes] = {}
    observed_hashes: dict[str, str] = {}
    for row in manifest["files"]:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise Blocked("reviewed-bundle-manifest-invalid")
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() in rows:
            raise Blocked("reviewed-bundle-manifest-invalid")
        path = root / relative
        file_info = path.lstat()
        raw = path.read_bytes()
        if (
            path.is_symlink() or not stat.S_ISREG(file_info.st_mode) or file_info.st_nlink != 1
            or file_info.st_uid != 0 or stat.S_IMODE(file_info.st_mode) != 0o600
            or hashlib.sha256(raw).hexdigest() != row["sha256"]
        ):
            raise Blocked("reviewed-bundle-rehash-failed")
        rows[relative.as_posix()] = raw
        observed_hashes[relative.as_posix()] = row["sha256"]
    if observed_hashes != projected_map:
        raise Blocked("reviewed-bundle-manifest-invalid")
    private_config = root / "private/rclone.conf"
    private_info = private_config.lstat()
    if (
        private_config.is_symlink() or not stat.S_ISREG(private_info.st_mode) or private_info.st_nlink != 1
        or private_info.st_uid != 0 or stat.S_IMODE(private_info.st_mode) != 0o600
        or private_info.st_size <= 0 or private_info.st_size > 131072
    ):
        raise Blocked("rclone-private-input-invalid")
    rclone_config = private_config.read_bytes()
    private_digest = hashlib.sha256(rclone_config).digest()
    if not hmac.compare_digest(private_digest, hashlib.sha256(private_config.read_bytes()).digest()):
        raise Blocked("rclone-private-input-drift")
    gate_a_payload = strict_json_bytes(rows[gate_a["path"]])
    if (
        not isinstance(gate_a_payload, dict)
        or gate_a_payload.get("status") != "PASS"
        or gate_a_payload.get("managed_sources") != gate_a["managed_sources"]
    ):
        raise Blocked("gate-a-projection-invalid")
    contract_path = root / "modules/rustdesk-fleet/contracts/phase52-gate-b-transaction.json"
    contract = load_contract(contract_path)
    managed_sources = {
        "atius-vault-export-rustdesk-phase52": rows["modules/rustdesk-fleet/tools/atius-vault-export-rustdesk-phase52"],
        "atius-vault-export-ssh-phase52": rows["modules/rustdesk-fleet/tools/atius-vault-export-ssh-phase52"],
        "phase52-vault-control-plane.json": rows["modules/rustdesk-fleet/contracts/phase52-vault-control-plane.json"],
    }
    if time.time() >= deadline_epoch:
        raise Blocked("remote-deadline-expired")
    backend = LocalVaultBackend(
        root,
        rclone_config,
        contract["authorization"]["approved_horistic_ssh_key_fingerprint"],
    )
    try:
        private_config.unlink()
        _fsync_directory(private_config.parent)
        private_config.parent.rmdir()
        _fsync_directory(root)
    except OSError as exc:
        raise Blocked("rclone-private-cleanup-failed") from exc
    return {
        "root": root,
        "contract": contract,
        "backend": backend,
        "backup_root": Path(contract["backup"]["root"]),
        "managed_sources": managed_sources,
    }


def execute_reviewed_live(
    bundle_root: Path, transaction_id: str, expected_hash: str, deadline_epoch: int,
) -> dict[str, Any]:
    context = _reviewed_live_context(bundle_root, transaction_id, expected_hash, deadline_epoch)
    try:
        return run_transaction(
            context["contract"], context["backend"], context["backup_root"], transaction_id,
            managed_sources=context["managed_sources"], require_root=True,
        )
    finally:
        shutil.rmtree(context["root"], ignore_errors=True)


def _read_owned_regular_bytes(path: Path, *, expected_uid: int) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise Blocked("transaction-state-file-invalid") from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != expected_uid or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size <= 0 or info.st_size > MAX_JSON
        ):
            raise Blocked("transaction-state-file-invalid")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                raise Blocked("transaction-state-file-short-read")
            chunks.append(chunk); remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise Blocked("transaction-state-file-grew")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def status_reviewed_live(
    bundle_root: Path, transaction_id: str, expected_hash: str, deadline_epoch: int,
) -> dict[str, Any]:
    context = _reviewed_live_context(bundle_root, transaction_id, expected_hash, deadline_epoch)
    try:
        backup_root = context["backup_root"]
        try:
            root_info = backup_root.lstat()
        except OSError as exc:
            raise Blocked("remote-transaction-not-found") from exc
        if backup_root.is_symlink() or not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != 0:
            raise Blocked("backup-root-identity-invalid")
        directory = _transaction_dir(backup_root, transaction_id, create=False)
        wal_path = directory / "wal.json"
        evidence_path = directory / "transaction-evidence.json"
        for _ in range(3):
            wal_before = _read_owned_regular_bytes(wal_path, expected_uid=0)
            evidence_raw = _read_owned_regular_bytes(evidence_path, expected_uid=0)
            wal_after = _read_owned_regular_bytes(wal_path, expected_uid=0)
            if hmac.compare_digest(wal_before, wal_after):
                return _reconcile_status_projection(
                    context["contract"], strict_json_bytes(wal_after),
                    strict_json_bytes(evidence_raw), transaction_id,
                )
        raise Blocked("transaction-status-raced")
    finally:
        shutil.rmtree(context["root"], ignore_errors=True)


def resume_reviewed_live(
    bundle_root: Path, transaction_id: str, expected_hash: str, deadline_epoch: int,
) -> dict[str, Any]:
    context = _reviewed_live_context(bundle_root, transaction_id, expected_hash, deadline_epoch)
    try:
        return resume_transaction(
            context["contract"], context["backend"], context["backup_root"], transaction_id,
            require_root=True,
        )
    finally:
        shutil.rmtree(context["root"], ignore_errors=True)


def _cleanup_reviewed_bundle_root(bundle_root: Path) -> None:
    """Remove only bootstrap-owned tmpfs roots, including context-load failures."""
    root = Path(bundle_root)
    if (
        not root.is_absolute()
        or root.parent != Path("/dev/shm")
        or not re.fullmatch(r"atius-phase52-reviewed-[A-Za-z0-9._-]+", root.name)
    ):
        return
    try:
        if root.exists() or root.is_symlink():
            shutil.rmtree(root)
    except OSError as exc:
        raise Blocked("reviewed-bundle-cleanup-failed") from exc
    if root.exists() or root.is_symlink():
        raise Blocked("reviewed-bundle-cleanup-failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    proof = sub.add_parser("isolated-raft-restore-proof")
    proof.add_argument("--snapshot", type=Path, required=True)
    live_parsers = {}
    for command in ("execute-reviewed-live", "status-reviewed-live", "resume-reviewed-live"):
        live = sub.add_parser(command)
        live.add_argument("--bundle-root", type=Path, required=True)
        live.add_argument("--transaction-id", required=True)
        live.add_argument("--expected-hash", required=True)
        live.add_argument("--deadline-epoch", type=int, required=True)
        live_parsers[command] = live
    args = parser.parse_args(argv)
    try:
        if args.command == "isolated-raft-restore-proof":
            return isolated_restore_proof(args.snapshot)
        if args.command in {"execute-reviewed-live", "status-reviewed-live", "resume-reviewed-live"}:
            operation = {
                "execute-reviewed-live": execute_reviewed_live,
                "status-reviewed-live": status_reviewed_live,
                "resume-reviewed-live": resume_reviewed_live,
            }[args.command]
            try:
                result = operation(
                    args.bundle_root,
                    args.transaction_id,
                    args.expected_hash,
                    args.deadline_epoch,
                )
            finally:
                _cleanup_reviewed_bundle_root(args.bundle_root)
            print(json.dumps(result, sort_keys=True, separators=(",", ":")))
            return 0
        raise Blocked("unknown-command")
    except Blocked as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "reason": _safe_output_reason(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
