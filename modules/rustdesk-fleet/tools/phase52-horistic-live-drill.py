#!/usr/bin/env python3
"""Thin orchestrator for direct versioned Phase 52 Horistic recovery actions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
import hashlib
import importlib.util
from typing import Any

import phase52_recovery as recovery

# Kept explicit so managed-source review pins the exact offline image identity.
ARM64_IMAGE_DIGEST = "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
assert ARM64_IMAGE_DIGEST == recovery.ARM64_IMAGE_DIGEST
STATE_FILE = ".phase52-live-drill-state.json"
REMOTE_INTENT_FILE = "remote-object-intent.json"
REMOTE_INTENT_SCHEMA = "phase52-remote-object-intent-v1"
MAX_STATE_BYTES = 262_144
CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contracts/phase52-live-drill-contract.json"
os.umask(0o077)


def tmpfs_owned(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink() or path.resolve(strict=True) != path:
        raise recovery.RecoveryBlocked("transaction-dir-not-canonical")
    info = path.stat()
    if info.st_uid != os.getuid() or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise recovery.RecoveryBlocked("transaction-dir-identity")
    probe = subprocess.run(["stat", "-f", "-c", "%T", str(path)], text=True, capture_output=True, check=False)
    if probe.returncode or probe.stdout.strip() != "tmpfs":
        raise recovery.RecoveryBlocked("transaction-dir-not-tmpfs")


def load_state(root: Path) -> dict[str, Any]:
    path = root / STATE_FILE
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_STATE_BYTES:
        raise recovery.RecoveryBlocked("transaction-state-invalid")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != recovery.STATE_SCHEMA:
        raise recovery.RecoveryBlocked("transaction-state-invalid")
    return payload


def atomic_state(root: Path, state: dict[str, Any]) -> None:
    encoded = (json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_STATE_BYTES:
        raise recovery.RecoveryBlocked("transaction-state-too-large")
    descriptor, name = tempfile.mkstemp(prefix=".phase52-state.", dir=root)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, encoded)
        os.fsync(descriptor)
        os.close(descriptor)
        os.replace(temporary, root / STATE_FILE)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_STATE_BYTES:
        raise recovery.RecoveryBlocked("transaction-artifact-too-large")
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, encoded)
        os.fsync(descriptor)
        os.close(descriptor)
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)


def planned_mutation(action: str, dry_run: bool) -> dict[str, Any]:
    plans = {
        "preflight": ([], []),
        "vault": (["ephemeral-vault-hydration"], ["ephemeral-identity"]),
        "backup": (["isolated-source-runtime", "isolated-hbbs-container-lifecycle", "state-only-backup-a", "state-only-backup-b-local", "state-only-backup-b-remote-create", "redacted-evidence-write"], ["source-runtime", "disposable_partial"]),
        "restore": (["disposable-isolated-restore-state", "isolated-hbbs-container-lifecycle"], ["restore-state", "restore-b.tar", "disposable_partial"]),
        "capacity-finalize": ([], []),
        "rollback": (["verified-drill-artifact-rollback-removal"], []),
    }
    classes, cleanup = plans[action]
    return recovery.mutation(bool(classes) and not dry_run, classes if not dry_run else [], cleanup if not dry_run else [])


def verify_managed_source_digests(raw: str | None, *, dry_run: bool) -> None:
    if raw is None:
        if dry_run:
            return
        raise recovery.RecoveryBlocked("remote-managed-source-digest-drift")
    expected = recovery.strict_json_bytes(raw.encode())
    repo = Path(__file__).resolve().parents[3]
    paths = {
        "live_drill_sha256": Path(__file__),
        "recovery_sha256": Path(recovery.__file__),
        "live_drill_contract_sha256": CONTRACT_PATH,
        "validator_sha256": repo / "modules/rustdesk-fleet/tools/validate_phase52.py",
        "capacity_policy_sha256": repo / "modules/rustdesk-fleet/contracts/capacity-policy.json",
        "provider_sha256": repo / "modules/rustdesk-fleet/tools/rustdesk-vault-provider",
        "client_sha256": repo / "modules/rustdesk-fleet/tools/atius-vault-phase52-client",
        "rclone_hydrate_sha256": repo / "modules/fleet-backup/scripts/atius-rclone-vault-hydrate",
        "rclone_copy_sha256": repo / "modules/fleet-backup/scripts/rclone-copy-verified-phase52.sh",
        "rclone_fetch_sha256": repo / "modules/fleet-backup/scripts/rclone-fetch-verified-phase52.sh",
    }
    actual = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}
    if expected != actual:
        raise recovery.RecoveryBlocked("remote-managed-source-digest-drift")
    if dry_run:
        return
    installed = {
        "provider_sha256": Path.home() / ".local/bin/rustdesk-vault-provider",
        "client_sha256": Path.home() / ".local/bin/atius-vault-phase52-client",
        "rclone_hydrate_sha256": Path.home() / ".local/bin/atius-rclone-vault-hydrate",
        "rclone_copy_sha256": Path.home() / ".local/bin/rclone-copy-verified-phase52",
        "rclone_fetch_sha256": Path.home() / ".local/bin/rclone-fetch-verified-phase52",
    }
    for key, path in installed.items():
        try:
            info = path.lstat()
        except OSError as exc:
            raise recovery.RecoveryBlocked("installed-managed-source-digest-drift") from exc
        if (
            path.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected[key]
        ):
            raise recovery.RecoveryBlocked("installed-managed-source-digest-drift")


def journal_artifact(root: Path, state: dict[str, Any], path: Path, *, disposable: bool) -> None:
    info = path.lstat()
    state.setdefault("artifact_journal", []).append({
        "path": str(path), "st_dev": info.st_dev, "st_ino": info.st_ino,
        "disposable": disposable,
    })
    atomic_state(root, state)


def validate_journaled_artifact(
    state: dict[str, Any], path: Path, *, disposable: bool
) -> None:
    rows = [
        row
        for row in state.get("artifact_journal", [])
        if isinstance(row, dict) and row.get("path") == str(path)
    ]
    if len(rows) != 1 or rows[0].get("disposable") is not disposable:
        raise recovery.RecoveryBlocked("rollback-artifact-journal-missing")
    info = path.lstat()
    if (info.st_dev, info.st_ino) != (rows[0].get("st_dev"), rows[0].get("st_ino")):
        raise recovery.RecoveryBlocked("rollback-artifact-identity-drift")


def validate_retained_directory(state: dict[str, Any], retained: Path) -> None:
    validate_journaled_artifact(state, retained, disposable=False)
    info = retained.lstat()
    if (
        retained.is_symlink()
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise recovery.RecoveryBlocked("retained-identity-drift")


def remote_intent_payload(
    transaction_id: str, destination: str, archive_sha256: str, size_bytes: int,
    *, verified: bool,
) -> dict[str, Any]:
    return {
        "schema": REMOTE_INTENT_SCHEMA,
        "transaction_id": transaction_id,
        "status": "copy-verified" if verified else "copy-planned",
        "remote_object": destination,
        "local_sha256": archive_sha256,
        "expected_remote_sha256": archive_sha256,
        "verified_remote_sha256": archive_sha256 if verified else None,
        "size_bytes": size_bytes,
        "retention": {
            "retain_until": "phase57-pass-plus-30-days",
            "deletion_requires_new_explicit_approval": True,
        },
    }


def persist_remote_object_intent(
    retained: Path, transaction_id: str, destination: str,
    archive_sha256: str, size_bytes: int, *, verified: bool,
) -> dict[str, Any]:
    payload = remote_intent_payload(
        transaction_id, destination, archive_sha256, size_bytes, verified=verified
    )
    atomic_json(retained / REMOTE_INTENT_FILE, payload)
    return payload


def load_remote_object_intent(retained: Path, transaction_id: str) -> dict[str, Any]:
    path = retained / REMOTE_INTENT_FILE
    try:
        info = path.lstat()
        payload = recovery.strict_json_bytes(path.read_bytes())
    except (OSError, recovery.RecoveryBlocked) as exc:
        raise recovery.RecoveryBlocked("remote-object-inventory-invalid") from exc
    expected_keys = {
        "schema", "transaction_id", "status", "remote_object", "local_sha256",
        "expected_remote_sha256", "verified_remote_sha256", "size_bytes", "retention",
    }
    digest = lambda value: isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
    retention = payload.get("retention") if isinstance(payload, dict) else None
    expected_destination = (
        "giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/"
        f"phase52/backup-b/{transaction_id}.tar"
    )
    if (
        path.is_symlink()
        or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or not isinstance(payload, dict)
        or set(payload) != expected_keys
        or payload.get("schema") != REMOTE_INTENT_SCHEMA
        or payload.get("transaction_id") != transaction_id
        or payload.get("status") not in {"copy-planned", "copy-verified"}
        or payload.get("remote_object") != expected_destination
        or not digest(payload.get("local_sha256"))
        or payload.get("expected_remote_sha256") != payload.get("local_sha256")
        or (
            payload.get("verified_remote_sha256")
            != (payload["local_sha256"] if payload.get("status") == "copy-verified" else None)
        )
        or type(payload.get("size_bytes")) is not int
        or not 0 < payload["size_bytes"] <= recovery.ARCHIVE_MAX_BYTES
        or not isinstance(retention, dict)
        or set(retention) != {"retain_until", "deletion_requires_new_explicit_approval"}
        or retention.get("retain_until") != "phase57-pass-plus-30-days"
        or type(retention.get("deletion_requires_new_explicit_approval")) is not bool
        or retention.get("deletion_requires_new_explicit_approval") is not True
    ):
        raise recovery.RecoveryBlocked("remote-object-inventory-invalid")
    return payload


def load_reconciled_backup_manifests(
    retained: Path, transaction_id: str
) -> dict[str, dict[str, Any]]:
    manifest_path = retained / "backup-manifests.json"
    try:
        recovery.secure_regular(manifest_path, maximum=MAX_STATE_BYTES)
        manifests = recovery.strict_json_bytes(manifest_path.read_bytes())
        if set(manifests) != {"A", "B"}:
            raise recovery.RecoveryBlocked("backup-manifest-schema-invalid")
        recovery.validate_action_result(
            "backup",
            {
                "backup_a": manifests["A"],
                "backup_b": manifests["B"],
                "state_only": ["db_v2.sqlite3"],
                "remote_rehash_verified": True,
                "sqlite_ready": True,
            },
        )
    except (OSError, KeyError, recovery.RecoveryBlocked) as exc:
        if isinstance(exc, recovery.RecoveryBlocked) and str(exc) == "backup-manifest-schema-invalid":
            raise
        raise recovery.RecoveryBlocked("backup-manifest-schema-invalid") from exc
    if any(manifests[label].get("transaction_id") != transaction_id for label in ("A", "B")):
        raise recovery.RecoveryBlocked("backup-manifest-transaction-drift")
    if (
        manifests["A"].get("source_snapshot_sha256")
        != manifests["B"].get("source_snapshot_sha256")
        or manifests["A"].get("member_sha256")
        != manifests["B"].get("member_sha256")
        or manifests["A"].get("archive_sha256")
        != manifests["B"].get("archive_sha256")
        or manifests["A"].get("size_bytes")
        != manifests["B"].get("size_bytes")
        or manifests["A"].get("generation_id")
        == manifests["B"].get("generation_id")
    ):
        raise recovery.RecoveryBlocked("backup-manifest-pair-drift")
    intent = load_remote_object_intent(retained, transaction_id)
    backup_b = manifests["B"]
    if (
        intent.get("status") != "copy-verified"
        or intent.get("remote_object") != backup_b.get("remote_object")
        or intent.get("local_sha256") != backup_b.get("local_sha256")
        or intent.get("expected_remote_sha256") != backup_b.get("remote_sha256")
        or intent.get("verified_remote_sha256") != backup_b.get("remote_sha256")
        or intent.get("size_bytes") != backup_b.get("size_bytes")
        or intent.get("retention") != backup_b.get("retention")
    ):
        raise recovery.RecoveryBlocked("remote-object-intent-manifest-drift")
    return {"A": manifests["A"], "B": manifests["B"]}


def validate_retained_tar(path: Path, manifest: dict[str, Any]) -> None:
    try:
        recovery.validate_canonical_state_tar(path, manifest.get("member_sha256"))
    except recovery.RecoveryBlocked:
        raise recovery.RecoveryBlocked("retained-tar-invalid")
    except (OSError, EOFError, tarfile.TarError) as exc:
        raise recovery.RecoveryBlocked("retained-tar-invalid") from exc


def load_validated_retained_backups(
    state: dict[str, Any], retained: Path
) -> dict[str, dict[str, Any]]:
    validate_retained_directory(state, retained)
    try:
        retained_entries = {entry.name for entry in retained.iterdir()}
    except OSError as exc:
        raise recovery.RecoveryBlocked("retained-inventory-drift") from exc
    if retained_entries != {
        "backup-a.tar", "backup-b.tar", "backup-manifests.json",
        REMOTE_INTENT_FILE,
    }:
        raise recovery.RecoveryBlocked("retained-inventory-drift")
    manifests = load_reconciled_backup_manifests(retained, state["transaction_id"])
    for label in ("A", "B"):
        archive = retained / f"backup-{label.lower()}.tar"
        validate_journaled_artifact(state, archive, disposable=False)
        recovery.secure_regular(archive)
        if archive.stat().st_size != manifests[label]["size_bytes"]:
            raise recovery.RecoveryBlocked("retained-backup-size-drift")
        if recovery.sha256_file(archive) != manifests[label]["archive_sha256"]:
            raise recovery.RecoveryBlocked("retained-backup-drift")
        validate_retained_tar(archive, manifests[label])
    facts = state.get("facts")
    backup_facts = facts.get("backup") if isinstance(facts, dict) else None
    backup_required = "backup" in state.get("completed_actions", [])
    if backup_required and not isinstance(backup_facts, dict):
        raise recovery.RecoveryBlocked("backup-state-facts-missing")
    if backup_facts is not None:
        try:
            recovery.validate_action_result("backup", backup_facts)
        except recovery.RecoveryBlocked as exc:
            raise recovery.RecoveryBlocked("backup-state-facts-invalid") from exc
        expected_facts = {
            "backup_a": manifests["A"],
            "backup_b": manifests["B"],
            "state_only": ["db_v2.sqlite3"],
            "remote_rehash_verified": True,
            "sqlite_ready": True,
        }
        if backup_facts != expected_facts:
            raise recovery.RecoveryBlocked("backup-state-facts-drift")
    return manifests


def observed_mutation(state: dict[str, Any]) -> dict[str, Any]:
    observed = state.get("observed_mutation")
    if not isinstance(observed, dict):
        return recovery.mutation(False, [])
    recovery.validate_mutation(observed)
    return observed


def observe_mutation(
    root: Path, state: dict[str, Any], mutation_class: str, cleanup_pending: list[str] | None = None
) -> None:
    current = observed_mutation(state)
    classes = list(current["classes"])
    cleanup = list(current["cleanup_pending"])
    if mutation_class not in classes:
        classes.append(mutation_class)
    for item in cleanup_pending or []:
        if item not in cleanup:
            cleanup.append(item)
    updated = recovery.mutation(True, classes, cleanup)
    state["observed_mutation"] = updated
    state.setdefault("action_journal", []).append(
        {
            "action": state.get("active_action"),
            "status": "mutation-observed",
            "mutation_class": mutation_class,
            "cleanup_pending": list(cleanup_pending or []),
        }
    )
    atomic_state(root, state)


def direct_action(action: str, root: Path, state: dict[str, Any], dry_run: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    if dry_run:
        return recovery.dry_run_details(action, root)
    if action == "preflight":
        missing = [name for name in ("python3", "podman", "rclone", "sqlite3", "timeout") if shutil.which(name) is None]
        if missing:
            raise recovery.RecoveryBlocked("preflight-prerequisite-missing")
        code, stdout, stderr = recovery.bounded_process(["podman", "image", "inspect", "--format", "{{.Digest}}", recovery.IMMUTABLE_HBBS], timeout=30)
        if code or stderr or stdout.decode().strip() != recovery.ARM64_IMAGE_DIGEST:
            raise recovery.RecoveryBlocked("pinned-image-missing")
        return {"image": recovery.IMMUTABLE_HBBS, "image_running": False, "network_mode": "none", "published_ports": []}, recovery.mutation(False, [])
    if action == "vault":
        provider = Path.home() / ".local/bin/rustdesk-vault-provider"
        if not provider.is_file() or provider.is_symlink() or not os.access(provider, os.X_OK):
            raise recovery.RecoveryBlocked("rustdesk-vault-provider-missing")
        references = [{"vault_path": path, "field": field} for path, field in recovery.RUSTDESK_REFERENCES]
        request = json.dumps({"references": references}, separators=(",", ":")).encode()
        code, stdout, stderr = recovery.bounded_process([str(provider)], request, timeout=30, stdout_limit=131072)
        payload = recovery.strict_json_bytes(stdout)
        keys = {f"{path}#{field}" for path, field in recovery.RUSTDESK_REFERENCES}
        if code or stderr or set(payload) != {"request_count", "values"} or payload.get("request_count") != 7 or not isinstance(payload.get("values"), dict) or set(payload["values"]) != keys:
            raise recovery.RecoveryBlocked("vault-not-ready")
        values = payload["values"]
        public_fingerprint = recovery.validate_vault_values(values)
        identity = root / "identity"
        identity.mkdir(mode=0o700)
        observe_mutation(root, state, "ephemeral-vault-hydration", ["ephemeral-identity"])
        private = values["kv/atius/rustdesk/server#private_key"]
        public = values["kv/atius/rustdesk/server#public_key"]
        recovery.write_exclusive(identity / "id_ed25519", private.encode())
        recovery.write_exclusive(identity / "id_ed25519.pub", public.encode())
        journal_artifact(root, state, identity, disposable=True)
        return {"reference_count": 7, "provider_api": "references-v1", "public_fingerprint": public_fingerprint}, observed_mutation(state)
    retained = Path.home() / ".local/share/atius-rustdesk-phase52" / state["transaction_id"]
    if action == "backup":
        retained.mkdir(parents=True, mode=0o700, exist_ok=False)
        observe_mutation(root, state, "isolated-source-runtime", ["source-runtime", "disposable-partial"])
        journal_artifact(root, state, retained, disposable=False)
        identity = root / "identity"
        source_root = root / "source-hbbs"
        source_root.mkdir(mode=0o700)
        journal_artifact(root, state, source_root, disposable=True)
        for name in ("id_ed25519", "id_ed25519.pub"):
            recovery.write_exclusive(source_root / name, (identity / name).read_bytes())
        before_listeners = recovery.listener_snapshot()
        container_name = f"phase52-source-{state['transaction_id'][:12]}"
        state.setdefault("containers", []).append(container_name); atomic_state(root, state)
        observe_mutation(root, state, "isolated-hbbs-container-lifecycle", ["source-runtime"])
        code, stdout, stderr = recovery.bounded_process(recovery.hbbs_command(container_name, source_root), timeout=120)
        if code or stderr or not stdout.strip():
            raise recovery.RecoveryBlocked("source-hbbs-start-failed")
        try:
            if not recovery.wait_hbbs_liveness(container_name, source_root):
                raise recovery.RecoveryBlocked("source-hbbs-not-ready")
            code, inspect_out, inspect_err = recovery.bounded_process(["podman", "inspect", container_name], timeout=30)
            inspected = json.loads(inspect_out)[0]
            host = inspected.get("HostConfig", {})
            if code or inspect_err or host.get("NetworkMode") != "none" or host.get("PortBindings") not in ({}, None):
                raise recovery.RecoveryBlocked("source-hbbs-isolation-failed")
        finally:
            recovery.checked_stop_remove(container_name)
            state["containers"].remove(container_name); atomic_state(root, state)
        if recovery.listener_snapshot() != before_listeners:
            raise recovery.RecoveryBlocked("public-listener-delta")
        source = source_root / "db_v2.sqlite3"
        recovery.normalize_hbbs_sqlite(source)
        snapshot_a = root / "sqlite-a.work"
        snapshot_b = root / "sqlite-b.work"
        a = recovery.sqlite_snapshot(source, snapshot_a)
        journal_artifact(root, state, snapshot_a, disposable=True)
        b = recovery.sqlite_snapshot(source, snapshot_b)
        journal_artifact(root, state, snapshot_b, disposable=True)
        if a["sha256"] != b["sha256"] or snapshot_a.stat().st_ino == snapshot_b.stat().st_ino:
            raise recovery.RecoveryBlocked("backup-independence-failed")
        manifest_a = recovery.state_archive(snapshot_a, retained / "backup-a.tar", label="A", transaction_id=state["transaction_id"])
        observe_mutation(root, state, "state-only-backup-a")
        manifest_b = recovery.state_archive(snapshot_b, retained / "backup-b.tar", label="B", transaction_id=state["transaction_id"])
        observe_mutation(root, state, "state-only-backup-b-local")
        snapshot_a.unlink(); snapshot_b.unlink()
        journal_artifact(root, state, retained / "backup-a.tar", disposable=False)
        journal_artifact(root, state, retained / "backup-b.tar", disposable=False)
        destination = f"giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/phase52/backup-b/{state['transaction_id']}.tar"
        persist_remote_object_intent(
            retained, state["transaction_id"], destination,
            manifest_b["archive_sha256"], manifest_b["size_bytes"], verified=False,
        )
        copy_tool = Path.home() / ".local/bin/rclone-copy-verified-phase52"
        code, copy_out, copy_err = recovery.bounded_process([
            str(copy_tool), "--source", str(retained / "backup-b.tar"), "--destination", destination,
            "--expected-size-bytes", str(manifest_b["size_bytes"]),
        ], timeout=930)
        copy_result = recovery.strict_json_bytes(copy_out)
        expected_copy_keys = {"status", "operation", "destination", "local_sha256", "remote_sha256", "size_bytes", "verified_copy", "source_snapshot_private", "config_provenance_verified", "retention", "secret_material_present"}
        if code or copy_err or set(copy_result) != expected_copy_keys or copy_result.get("status") != "PASS" or copy_result.get("destination") != destination or copy_result.get("size_bytes") != manifest_b["size_bytes"] or copy_result.get("local_sha256") != manifest_b["archive_sha256"] or copy_result.get("remote_sha256") != manifest_b["archive_sha256"]:
            raise recovery.RecoveryBlocked("backup-b-remote-copy-invalid")
        persist_remote_object_intent(
            retained, state["transaction_id"], destination,
            manifest_b["archive_sha256"], manifest_b["size_bytes"], verified=True,
        )
        observe_mutation(root, state, "state-only-backup-b-remote-create")
        manifest_b.update({"destination_class": "modules/fleet-backup:gdrive", "remote_object": destination, "local_sha256": copy_result["local_sha256"], "remote_sha256": copy_result["remote_sha256"], "retention": copy_result["retention"]})
        manifest_a["destination_class"] = "candidate-local"
        atomic_json(retained / "backup-manifests.json", {"A": manifest_a, "B": manifest_b})
        observe_mutation(root, state, "redacted-evidence-write")
        return {"backup_a": manifest_a, "backup_b": manifest_b, "state_only": ["db_v2.sqlite3"], "remote_rehash_verified": True, "sqlite_ready": True}, observed_mutation(state)
    if action == "restore":
        manifests = load_validated_retained_backups(state, retained)
        archive = root / "restore-b.tar"
        fetch_tool = Path.home() / ".local/bin/rclone-fetch-verified-phase52"
        code, fetch_out, fetch_err = recovery.bounded_process([
            str(fetch_tool), "--source", manifests["B"]["remote_object"],
            "--expected-sha256", manifests["B"]["remote_sha256"],
            "--expected-size-bytes", str(manifests["B"]["size_bytes"]), "--output", str(archive),
        ], timeout=930)
        fetch_result = recovery.strict_json_bytes(fetch_out)
        if code or fetch_err or fetch_result != {"hash_verified": True, "operation": "fetch-verified", "output_mode": "0600", "secret_material_present": False, "status": "PASS"}:
            raise recovery.RecoveryBlocked("backup-b-remote-fetch-invalid")
        observe_mutation(root, state, "disposable-isolated-restore-state", ["restore-b.tar", "disposable-partial"])
        recovery.secure_regular(archive)
        journal_artifact(root, state, archive, disposable=True)
        if (
            archive.stat().st_size != manifests["B"]["size_bytes"]
            or recovery.sha256_file(archive) != manifests["B"]["archive_sha256"]
        ):
            raise recovery.RecoveryBlocked("backup-b-drift")
        validate_retained_tar(archive, manifests["B"])
        restore = root / "restore-state"
        restore.mkdir(mode=0o700)
        journal_artifact(root, state, restore, disposable=True)
        with tarfile.open(archive, "r:") as bundle:
            member = bundle.getmember("db_v2.sqlite3")
            target = restore / "db_v2.sqlite3"
            source = bundle.extractfile(member)
            if source is None:
                raise recovery.RecoveryBlocked("restore-member-missing")
            with target.open("xb") as output:
                shutil.copyfileobj(source, output, recovery.CHUNK_BYTES)
            os.chmod(target, 0o600)
        recovery.secure_regular(target, maximum=recovery.SQLITE_MAX_BYTES)
        with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as database:
            if database.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise recovery.RecoveryBlocked("sqlite-integrity-failure")
        identity = root / "identity"
        for name in ("id_ed25519", "id_ed25519.pub"):
            recovery.write_exclusive(restore / name, (identity / name).read_bytes())
        observed_fingerprint = __import__("hashlib").sha256((restore / "id_ed25519.pub").read_bytes()).hexdigest()
        expected_fingerprint = state.get("facts", {}).get("vault", {}).get("public_fingerprint")
        if observed_fingerprint != expected_fingerprint:
            raise recovery.RecoveryBlocked("public-fingerprint-mismatch")
        before_listeners = recovery.listener_snapshot()
        container_name = f"phase52-restore-{state['transaction_id'][:12]}"
        state.setdefault("containers", []).append(container_name); atomic_state(root, state)
        observe_mutation(root, state, "isolated-hbbs-container-lifecycle", ["restore-state"])
        code, stdout, stderr = recovery.bounded_process(recovery.hbbs_command(container_name, restore), timeout=120)
        if code or stderr or not stdout.strip():
            raise recovery.RecoveryBlocked("restore-hbbs-start-failed")
        try:
            if not recovery.wait_hbbs_liveness(container_name, restore):
                raise recovery.RecoveryBlocked("restore-hbbs-not-ready")
            code, inspect_out, inspect_err = recovery.bounded_process(["podman", "inspect", container_name], timeout=30)
            inspected = json.loads(inspect_out)[0]
            host = inspected.get("HostConfig", {})
            port_code, port_out, port_err = recovery.bounded_process(["podman", "port", container_name], timeout=30)
            if code or inspect_err or port_code or port_err or port_out or host.get("NetworkMode") != "none" or host.get("PortBindings") not in ({}, None):
                raise recovery.RecoveryBlocked("restore-hbbs-isolation-failed")
        finally:
            recovery.checked_stop_remove(container_name)
            state["containers"].remove(container_name); atomic_state(root, state)
        if recovery.listener_snapshot() != before_listeners:
            raise recovery.RecoveryBlocked("public-listener-delta")
        return {"sqlite_integrity": "ok", "sqlite_ready": True, "public_fingerprint": observed_fingerprint, "image": recovery.IMMUTABLE_HBBS, "image_running": True, "network_mode": "none", "port_bindings": {}, "public_listener_delta": []}, observed_mutation(state)
    if action == "capacity-finalize":
        validator_path = Path(__file__).with_name("validate_phase52.py")
        spec = importlib.util.spec_from_file_location("phase52_capacity_validator", validator_path)
        if not spec or not spec.loader: raise recovery.RecoveryBlocked("capacity-validator-missing")
        capacity_validator = importlib.util.module_from_spec(spec); sys.modules[spec.name]=capacity_validator; spec.loader.exec_module(capacity_validator)
        policy_path = Path(__file__).resolve().parent.parent / "contracts/capacity-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        stats = os.statvfs(retained); block=stats.f_frsize
        observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        mount_point = str(retained.anchor); filesystem_source = str(retained.stat().st_dev)
        base = {"observed_at":observed_at,"hostname":"horistic-srv","architecture":"aarch64","filesystem_source":filesystem_source,"mount_point":mount_point,"total_bytes":stats.f_blocks*block,"used_bytes":(stats.f_blocks-stats.f_bfree)*block,"available_bytes":stats.f_bavail*block,"inode_total":stats.f_files,"inode_used":stats.f_files-stats.f_ffree,"inode_available":stats.f_favail,"podman_graphroot":"not-observed","podman_version":"not-observed","resource_wrapper":"omni","resource_profile":"builds-20pct","command_version":"phase52-capacity-read-only-v2","read_only":True,"mutation_performed":False}
        actual_a=(retained/"backup-a.tar").stat().st_size; actual_b=(retained/"backup-b.tar").stat().st_size
        finalize={**base,"actual_backup_a_bytes":actual_a,"actual_backup_b_bytes":actual_b,"materialized_reservations":{"backup_a_bytes":actual_a,"backup_b_bytes":actual_b}}
        base["capacity_finalize"]=finalize
        sample = capacity_validator.derive_candidate_capacity(base, policy)
        if sample["status"] != "PASS":
            raise recovery.RecoveryBlocked("capacity-finalize-nogo")
        return {"capacity": sample, "actual_backup_a_bytes": actual_a, "actual_backup_b_bytes": actual_b}, recovery.mutation(False, [])
    if action == "rollback":
        manifest_path = retained / "backup-manifests.json"
        intent_path = retained / REMOTE_INTENT_FILE
        observed = observed_mutation(state)
        remote_create_observed = "state-only-backup-b-remote-create" in observed["classes"]
        if not manifest_path.is_file():
            if intent_path.exists() or intent_path.is_symlink():
                load_remote_object_intent(retained, state["transaction_id"])
                raise recovery.RecoveryBlocked("remote-object-intent-unresolved")
            if remote_create_observed:
                raise recovery.RecoveryBlocked("remote-object-inventory-missing")
            local_classes = {"state-only-backup-a", "state-only-backup-b-local"}
            declared_local_classes = local_classes.intersection(observed["classes"])
            retained_exists = retained.exists() or retained.is_symlink()
            if declared_local_classes and not retained_exists:
                raise recovery.RecoveryBlocked("retained-local-backup-inventory-missing")
            if retained_exists:
                validate_retained_directory(state, retained)
                try:
                    partial_entries = {entry.name for entry in retained.iterdir()}
                except OSError as exc:
                    raise recovery.RecoveryBlocked("partial-retained-inventory-drift") from exc
                allowed_partial = {"backup-a.tar", "backup-b.tar"}
                if not partial_entries.issubset(allowed_partial):
                    raise recovery.RecoveryBlocked("partial-retained-inventory-drift")
                if partial_entries or declared_local_classes:
                    for name in sorted(partial_entries):
                        archive = retained / name
                        validate_journaled_artifact(state, archive, disposable=False)
                        recovery.secure_regular(archive)
                    raise recovery.RecoveryBlocked("retained-local-backup-inventory-unresolved")
        for container in list(state.get("containers", [])):
            recovery.checked_stop_remove(container)
            state["containers"].remove(container)
        disposable_dirs = (root / "restore-state", root / "source-hbbs", root / "identity")
        disposable_files = (
            root / "restore-b.tar", root / "rollback-remote-rehash-b.tar",
            root / "sqlite-a.work", root / "sqlite-b.work",
        )
        present_dirs = [path for path in disposable_dirs if path.exists() or path.is_symlink()]
        present_files = [path for path in disposable_files if path.exists() or path.is_symlink()]
        for path in present_dirs:
            validate_journaled_artifact(state, path, disposable=True)
            info = path.lstat()
            if path.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise recovery.RecoveryBlocked("rollback-artifact-identity-drift")
        for path in present_files:
            validate_journaled_artifact(state, path, disposable=True)
            recovery.secure_regular(path)
        retained_present = retained.exists() or retained.is_symlink()
        if retained_present:
            validate_retained_directory(state, retained)
        manifests: dict[str, dict[str, Any]] | None = None
        if manifest_path.is_file():
            manifests = load_validated_retained_backups(state, retained)
        removed = False
        for disposable in present_dirs:
            shutil.rmtree(disposable)
            removed = True
        for disposable_file in present_files:
            disposable_file.unlink()
            removed = True
        if not manifest_path.is_file() and retained_present:
            shutil.rmtree(retained)
            removed = True
        if removed:
            observe_mutation(root, state, "verified-drill-artifact-rollback-removal")
        if not manifest_path.is_file():
            return {"terminal": True, "retained_artifacts": [], "cleanup_pending": [], "retained_rehash_verified": False, "remote_rehash_verified": False, "remote_delete_performed": False}, observed_mutation(state)
        assert manifests is not None
        retained_rehash_verified = all(recovery.sha256_file(retained/f"backup-{label.lower()}.tar") == manifests[label]["archive_sha256"] for label in ("A","B"))
        if not retained_rehash_verified: raise recovery.RecoveryBlocked("retained-backup-drift")
        remote_probe = root / "rollback-remote-rehash-b.tar"
        fetch_tool = Path.home() / ".local/bin/rclone-fetch-verified-phase52"
        code, fetch_out, fetch_err = recovery.bounded_process([
            str(fetch_tool), "--source", manifests["B"]["remote_object"],
            "--expected-sha256", manifests["B"]["remote_sha256"],
            "--expected-size-bytes", str(manifests["B"]["size_bytes"]),
            "--output", str(remote_probe),
        ], timeout=930)
        fetch_result = recovery.strict_json_bytes(fetch_out)
        expected_fetch = {"hash_verified": True, "operation": "fetch-verified", "output_mode": "0600", "secret_material_present": False, "status": "PASS"}
        if code or fetch_err or fetch_result != expected_fetch:
            raise recovery.RecoveryBlocked("retained-remote-rehash-failed")
        recovery.secure_regular(remote_probe)
        journal_artifact(root, state, remote_probe, disposable=True)
        observe_mutation(root, state, "verified-drill-artifact-rollback-removal", ["rollback-remote-rehash-b.tar"])
        remote_rehash_verified = recovery.sha256_file(remote_probe) == manifests["B"]["remote_sha256"]
        remote_probe.unlink()
        current_observed = observed_mutation(state)
        state["observed_mutation"] = recovery.mutation(
            current_observed["performed"], current_observed["classes"], []
        )
        atomic_state(root, state)
        if not remote_rehash_verified:
            raise recovery.RecoveryBlocked("retained-remote-rehash-failed")
        remote_delete_performed = False
        return {"terminal": True, "retained_artifacts": list(recovery.RETAINED), "cleanup_pending": [], "retained_rehash_verified": retained_rehash_verified, "remote_rehash_verified": remote_rehash_verified, "remote_delete_performed": remote_delete_performed}, observed_mutation(state)
    raise recovery.RecoveryBlocked("unknown-action")


def result_payload(action: str, state: dict[str, Any], status: str, details: dict[str, Any], mutation: dict[str, Any], blocker: str | None = None) -> dict[str, Any]:
    payload = {
        "schema": recovery.RESULT_SCHEMA, "transaction_id": state["transaction_id"],
        "action": action, "status": status, "details": details, "mutation": mutation,
        "secret_material_present": False,
    }
    if blocker is not None:
        payload["blocker"] = blocker
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", required=True, choices=recovery.ACTIONS)
    parser.add_argument("--transaction-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--expected-managed-source-digests")
    args = parser.parse_args()
    state: dict[str, Any] | None = None
    try:
        verify_managed_source_digests(args.expected_managed_source_digests, dry_run=args.dry_run)
        if args.initialize:
            if args.action != "preflight" or args.transaction_dir.exists():
                raise recovery.RecoveryBlocked("initialize-contract-invalid")
            tmpfs_owned(args.transaction_dir.parent)
            args.transaction_dir.mkdir(mode=0o700)
            state = recovery.initial_state(os.urandom(16).hex())
            atomic_state(args.transaction_dir, state)
        tmpfs_owned(args.transaction_dir)
        state = load_state(args.transaction_dir)
        recovery.validate_transition(args.action, state)
        if args.action == "rollback" and state.get("terminal"):
            mutation = recovery.mutation(False, [])
            details = state.get("facts", {}).get("rollback")
            if not isinstance(details, dict):
                raise recovery.RecoveryBlocked("terminal-rollback-proof-missing")
            recovery.validate_action_result("rollback", details)
            print(json.dumps(result_payload(args.action, state, "PASS", details, mutation), sort_keys=True, separators=(",", ":")))
            return 0
        state["active_action"] = args.action
        state["planned_mutation"] = planned_mutation(args.action, args.dry_run)
        state["observed_mutation"] = recovery.mutation(False, [])
        state["planned_cleanup"] = state["planned_mutation"]["cleanup_pending"]
        state.setdefault("action_journal", []).append({"action": args.action, "status": "started", "planned_mutation": state["planned_mutation"]})
        atomic_state(args.transaction_dir, state)
        details, mutation = direct_action(args.action, args.transaction_dir, state, args.dry_run)
        action = args.action
        recovery.validate_action_result(action, details)
        recovery.validate_mutation(mutation)
        if args.action == "rollback":
            state.setdefault("facts", {})["rollback"] = details
            state["retained_artifacts"] = details["retained_artifacts"]
            state["cleanup_pending"] = details["cleanup_pending"]
            state = recovery.rollback_state(state)
        else:
            state["active_action"] = None
            state["completed_actions"].append(args.action)
            state["cleanup_pending"] = mutation["cleanup_pending"]
            state.setdefault("facts", {})[args.action] = details
        atomic_state(args.transaction_dir, state)
        print(json.dumps(result_payload(args.action, state, "PASS", details, mutation), sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError, recovery.RecoveryBlocked) as exc:
        blocker = str(exc) if isinstance(exc, recovery.RecoveryBlocked) else "live-drill-error"
        if state is None:
            state = recovery.initial_state("0" * 32)
        failure_mutation = observed_mutation(state)
        failure_cleanup_pending = failure_mutation.get("cleanup_pending", [])
        state.setdefault("action_journal", []).append({"action": args.action, "status": "failed", "blocker": blocker, "failure_cleanup_pending": failure_cleanup_pending})
        if args.transaction_dir.exists() and state.get("transaction_id") != "0" * 32:
            atomic_state(args.transaction_dir, state)
        mutation = failure_mutation
        print(json.dumps(result_payload(args.action, state, "BLOCKED", {}, mutation, blocker), sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
