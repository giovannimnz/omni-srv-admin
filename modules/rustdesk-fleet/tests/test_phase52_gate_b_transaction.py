from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import fcntl
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

import pytest


REPO = Path(__file__).resolve().parents[3]
CONTRACT = REPO / "modules/rustdesk-fleet/contracts/phase52-gate-b-transaction.json"
EXECUTOR = REPO / "modules/rustdesk-fleet/tools/phase52-vault-transaction.py"
COORDINATOR = REPO / "modules/rustdesk-fleet/tools/run-phase52-gate-b.py"
GATE_A = REPO / "modules/rustdesk-fleet/evidence/phase52/gate-a-verification.json"
SEAL = REPO / "modules/rustdesk-fleet/evidence/phase52/gate-b-pre-live-verification.json"
RUNTIME_EVIDENCE = REPO / "modules/rustdesk-fleet/evidence/phase52/gate-b-transaction.json"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tx = _load(EXECUTOR, "phase52_vault_transaction")
gate = _load(COORDINATOR, "run_phase52_gate_b")


class FakeBackend(tx.TransactionBackend):
    def __init__(self, *, metadata=None, corrupt_backup=False, cas_conflict_at=None, delete_fail_once=False, restore_fail_once=False):
        self.metadata_by_path = metadata or {}
        self.corrupt_backup = corrupt_backup
        self.cas_conflict_at = cas_conflict_at
        self.delete_fail_once = delete_fail_once
        self.restore_fail_once = restore_fail_once
        self.puts = []
        self.deleted = []
        self.events = []
        self._versions = {}

    def create_backups(self, transaction_dir, contract):
        self.events.append("backup")
        snapshot = transaction_dir / "raft.snapshot"
        bundle = transaction_dir / "control-plane.tar"
        snapshot.write_bytes(b"fixture-snapshot")
        bundle.write_bytes(b"fixture-control-plane")
        for path in (snapshot, bundle):
            path.chmod(0o600)
        manifest = {
            "schema": "phase52-gate-b-backup-manifest-v1",
            "raft_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            "control_plane_bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "secret_material_present": False,
        }
        (transaction_dir / "manifest.json").write_text(json.dumps(manifest))
        (transaction_dir / "manifest.json").chmod(0o600)
        if self.corrupt_backup:
            snapshot.write_bytes(b"corrupt-after-manifest")
        return {"raft_snapshot_valid": True, "control_plane_bundle_valid": True}

    def prove_isolated_snapshot_restore(self, transaction_dir, contract):
        self.events.append("isolated-restore")
        return {
            "status": "PASS",
            "network_namespace": "isolated",
            "host_listener": False,
            "public_listener": False,
            "port_bindings": [],
            "integrity": "PASS",
        }

    def install_control_plane(self, transaction_dir, managed_sources):
        self.events.append("install-control-plane")

    def restore_control_plane(self, transaction_dir):
        self.events.append("restore-control-plane")
        if self.restore_fail_once:
            self.restore_fail_once = False
            raise tx.Blocked("fixture-control-plane-restore-failed")

    def metadata(self, vault_path):
        self.events.append(f"metadata:{vault_path}")
        if vault_path in self._versions:
            return {"current_version": 1, "oldest_version": 1, "versions": {"1": {"deletion_time": "", "destroyed": False}}}
        return self.metadata_by_path.get(vault_path, {"current_version": 0, "oldest_version": 0, "versions": {}})

    def generate_values(self, contract, runtime_dir):
        self.events.append("generate")
        values = {}
        for index, row in enumerate(contract["writes"]):
            values[row["id"]] = {
                field: ("R" + str(index) * 31 if field in {"permanent_password", "rclone_conf"} else ("k" * 44))
                for field in row["fields"]
            }
        values["rclone-config"]["rclone_conf"] = "[giovanni-drive]\ntype = drive\nfixture = opaque-sentinel\n"
        return values

    def put_cas0_stdin(self, operation, encoded_private_json):
        assert operation["cas"] == 0
        assert operation["vault_path"] not in repr(encoded_private_json)
        index = len(self.puts)
        if self.cas_conflict_at == index:
            raise tx.CasConflict("cas-conflict")
        private = json.loads(encoded_private_json)
        assert set(private) == set(operation["fields"])
        self.puts.append(operation["id"])
        self._versions[operation["vault_path"]] = 1
        return {"version": 1}

    def soft_delete_exact_version(self, vault_path, version):
        assert version == 1
        if self.delete_fail_once:
            self.delete_fail_once = False
            raise tx.Blocked("fixture-soft-delete-failed")
        self.deleted.append((vault_path, version))

    def verify_created_values(self, contract, expected_versions):
        return {"status": "PASS", "write_count": len(expected_versions), "secret_material_present": False}


class SensitiveStageFailureBackend(FakeBackend):
    def __init__(self, failure_stage, reason):
        super().__init__(cas_conflict_at=1 if failure_stage == "rollback" else None)
        self.failure_stage = failure_stage
        self.reason = reason
        self.install_calls = 0
        self.restore_calls = 0

    def create_backups(self, transaction_dir, contract):
        if self.failure_stage == "backup":
            self.events.append("backup")
            raise tx.Blocked(self.reason)
        return super().create_backups(transaction_dir, contract)

    def install_control_plane(self, transaction_dir, managed_sources):
        self.install_calls += 1
        self.events.append("install-control-plane")
        if self.failure_stage == "install" and self.install_calls == 1:
            raise tx.Blocked(self.reason)
        if self.failure_stage == "reinstall" and self.install_calls == 2:
            raise tx.Blocked(self.reason)

    def restore_control_plane(self, transaction_dir):
        self.restore_calls += 1
        self.events.append("restore-control-plane")
        if self.failure_stage == "restore" and self.restore_calls == 1:
            raise tx.Blocked(self.reason)

    def soft_delete_exact_version(self, vault_path, version):
        if self.failure_stage == "rollback":
            raise tx.Blocked(self.reason)
        return super().soft_delete_exact_version(vault_path, version)


def contract():
    return tx.load_contract(CONTRACT)


def fake_vault_snapshot_bridge(snapshot_bytes=b"snapshot", fail_at=None):
    container_files = {}
    calls = []

    def fake_process(command, private_input, **kwargs):
        calls.append(command)
        if command[:5] == [
            "/usr/local/sbin/atius-vault", "operator", "raft", "snapshot", "save",
        ]:
            if fail_at == "save":
                raise tx.Blocked("fixture-save-failed")
            container_files[command[-1]] = snapshot_bytes
        elif command[:2] == ["/usr/bin/podman", "cp"]:
            if fail_at == "copy":
                raise tx.Blocked("fixture-copy-failed")
            _, container_path = command[2].split(":", 1)
            (Path(command[3]) / Path(container_path).name).write_bytes(container_files[container_path])
        elif command[:4] == ["/usr/bin/podman", "exec", tx.VAULT_CONTAINER, "rm"]:
            if fail_at == "cleanup":
                raise tx.Blocked("fixture-cleanup-failed")
            if fail_at == "cleanup_oserror":
                raise OSError("fixture-cleanup-oserror")
            container_files.pop(command[-1], None)
        else:
            raise AssertionError(command)
        return 0, b""

    return fake_process, container_files, calls


def reviewed_bootstrap_fixture(executor_source: bytes) -> tuple[bytes, str]:
    executor_path = "modules/rustdesk-fleet/tools/phase52-vault-transaction.py"
    gate_a_path = "gate-a.json"
    gate_a_raw = json.dumps(
        {"status": "PASS", "managed_sources": []},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    sealed_sources = [{"path": executor_path, "sha256": hashlib.sha256(executor_source).hexdigest()}]
    gate_a = {
        "path": gate_a_path,
        "sha256": hashlib.sha256(gate_a_raw).hexdigest(),
        "managed_sources": [],
    }
    canonical = {"sealed_sources": sealed_sources, "gate_a": gate_a}
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    files = [*sealed_sources, {"path": gate_a_path, "sha256": gate_a["sha256"]}]
    manifest = {
        "schema": "phase52-reviewed-root-bundle-v1",
        "hash_set_sha256": digest,
        "sealed_sources": sealed_sources,
        "gate_a": gate_a,
        "files": files,
        "secret_material_present": False,
    }
    rows = {
        "manifest.json": json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode() + b"\n",
        executor_path: executor_source,
        gate_a_path: gate_a_raw,
        "private/rclone.conf": b"[giovanni-drive]\ntype = drive\nfixture = private\n",
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, raw in rows.items():
            info = tarfile.TarInfo(name); info.size = len(raw); info.mode = 0o600
            archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue(), digest


def test_contract_is_exact_value_free_and_create_only():
    payload = contract()
    assert payload["schema"] == "atius-rustdesk-phase52-gate-b-transaction-v1"
    assert len(payload["writes"]) == 7
    assert [(r["vault_path"], r["fields"]) for r in payload["writes"]] == [
        ("kv/atius/rustdesk/server", ["private_key", "public_key"]),
        ("kv/atius/rustdesk/targets/atius-srv-1", ["permanent_password"]),
        ("kv/atius/rustdesk/targets/atius-srv-2", ["permanent_password"]),
        ("kv/atius/rustdesk/targets/atius-srv-3", ["permanent_password"]),
        ("kv/atius/rustdesk/targets/horistic-srv", ["permanent_password"]),
        ("kv/atius/rustdesk/targets/giovanni-w11-pc", ["permanent_password"]),
        ("kv/atius/fleet-backup/rclone/giovanni-drive", ["rclone_conf"]),
    ]
    assert all(r["cas"] == 0 for r in payload["writes"])
    assert payload["write_policy"]["expected_put_count"] == 7
    assert payload["write_policy"]["expected_rustdesk_value_count"] == 7
    assert payload["write_policy"]["expected_total_value_count"] == 8
    assert payload["generator"]["image"] == "docker.io/rustdesk/rustdesk-server:1.1.15"
    assert payload["generator"]["linux_arm64_digest"] == "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
    assert payload["backup"]["root"] == "/var/backups/atius-vault/phase52"
    assert payload["backup"]["directory_mode"] == "0700"
    assert payload["authorization"]["approved_horistic_ssh_key_fingerprint"] == "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0"
    assert payload["backup"]["control_plane_state_root"] == "/var/lib/atius-vault-phase52"
    assert payload["backup"]["required_success_sequence"] == [
        "install", "exact-restore", "reviewed-reinstall", "metadata", "data-writes",
    ]
    assert "ROLLBACK_BLOCKED_RETRY_REQUIRED" in payload["states"]
    assert "PRE_BACKUP_NO_MUTATION_TERMINAL" in payload["states"]
    assert set(payload["rollback"]["forbidden_operations"]) >= {"metadata-delete", "destroy", "undelete", "remote-delete"}
    text = CONTRACT.read_text()
    assert "private_key_value" not in text and "password_value" not in text


def test_transaction_orders_backup_restore_proof_before_install_and_put(tmp_path):
    backend = FakeBackend()
    result = tx.run_transaction(contract(), backend, tmp_path, "20260722T120000Z-abcdef12", require_root=False)
    assert result["status"] == "PASS"
    assert backend.events[:5] == [
        "backup", "isolated-restore", "install-control-plane",
        "restore-control-plane", "install-control-plane",
    ]
    assert backend.events.index("install-control-plane", 3) < next(
        index for index, event in enumerate(backend.events) if event.startswith("metadata:")
    )
    assert backend.puts == [row["id"] for row in contract()["writes"]]
    assert backend.deleted == []
    final_wal = json.loads((tmp_path / "20260722T120000Z-abcdef12" / "wal.json").read_text())
    assert final_wal["control_plane_restore_tested"] is True
    assert final_wal["control_plane_reinstall_proved"] is True
    assert result["mutation_accounting"]["atius-srv-2"] == {
        "candidate_data_plane_mutation": False,
        "authorized_vault_control_plane_mutation": False,
    }
    assert result["mutation_accounting"]["atius-srv-3"]["authorized_vault_control_plane_mutation"] is True
    assert "mutation" not in result
    assert not any(token in json.dumps(result) for token in ("opaque-sentinel", "kkkkkkkk", "R000000"))


def test_backup_failure_persists_sanitized_pre_backup_blocker_and_state(tmp_path):
    class PartialBackupFailure(FakeBackend):
        def create_backups(self, transaction_dir, contract):
            self.events.append("backup")
            (transaction_dir / "raft.snapshot.partial").write_bytes(b"retained-partial")
            raise tx.Blocked("raft-snapshot-failed")

    backend = PartialBackupFailure()
    transaction_id = "20260722T120000Z-babefeed"
    with pytest.raises(tx.Blocked, match="raft-snapshot-failed"):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id, require_root=False,
        )

    directory = tmp_path / transaction_id
    wal = json.loads((directory / "wal.json").read_text())
    evidence = json.loads((directory / "transaction-evidence.json").read_text())
    assert wal["status"] == "PRE_BACKUP"
    assert wal["blocker"] == "raft-snapshot-failed"
    assert evidence["status"] == "PRE_BACKUP"
    assert evidence["live_write_performed"] is False
    assert evidence["vault_write_ownership"] == "NONE"
    assert (directory / "raft.snapshot.partial").read_bytes() == b"retained-partial"
    assert backend.events == ["backup"]
    assert backend.puts == [] and backend.deleted == []


def test_backup_failure_never_persists_arbitrary_blocked_detail(tmp_path):
    class UnsafeBackupFailure(FakeBackend):
        def create_backups(self, transaction_dir, contract):
            self.events.append("backup")
            raise tx.Blocked("raft failed: opaque-sentinel\nprivate detail")

    backend = UnsafeBackupFailure()
    transaction_id = "20260722T120000Z-5afe5afe"
    with pytest.raises(tx.Blocked, match="opaque-sentinel"):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id, require_root=False,
        )

    directory = tmp_path / transaction_id
    wal = json.loads((directory / "wal.json").read_text())
    assert wal["status"] == "PRE_BACKUP"
    assert wal["blocker"] == "pre-backup-failed"
    for artifact in directory.iterdir():
        assert "opaque-sentinel" not in artifact.read_text(errors="ignore")
        assert "private detail" not in artifact.read_text(errors="ignore")


def test_pre_backup_zero_write_resume_is_explicit_no_mutation_terminal(tmp_path):
    class PartialBackupFailure(FakeBackend):
        def create_backups(self, transaction_dir, contract):
            self.events.append("backup")
            (transaction_dir / "raft.snapshot.partial").write_bytes(b"retained-partial")
            raise tx.Blocked("raft-snapshot-failed")

    backend = PartialBackupFailure()
    transaction_id = "20260722T120000Z-acde5050"
    with pytest.raises(tx.Blocked, match="raft-snapshot-failed"):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id, require_root=False,
        )
    events_before_resume = list(backend.events)

    result = tx.resume_transaction(
        contract(), backend, tmp_path, transaction_id, require_root=False,
    )

    assert result["status"] == "PRE_BACKUP_NO_MUTATION_TERMINAL"
    assert result["write_count"] == 0
    assert result["live_write_performed"] is False
    assert result["vault_write_ownership"] == "NONE"
    assert backend.events == events_before_resume
    assert backend.puts == [] and backend.deleted == []
    directory = tmp_path / transaction_id
    assert (directory / "raft.snapshot.partial").read_bytes() == b"retained-partial"
    wal = json.loads((directory / "wal.json").read_text())
    assert wal["status"] == "PRE_BACKUP_NO_MUTATION_TERMINAL"
    assert wal["blocker"] == "raft-snapshot-failed"
    evidence = json.loads((directory / "transaction-evidence.json").read_text())
    assert tx._reconcile_status_projection(
        contract(), wal, evidence, transaction_id,
    ) == result
    assert gate._validate_recovery_result(
        contract(), result, transaction_id,
    ) == result
    with pytest.raises(tx.Blocked, match="pre-backup-no-mutation-terminal"):
        tx.resume_transaction(
            contract(), backend, tmp_path, transaction_id, require_root=False,
        )
    assert backend.events == events_before_resume


UNSAFE_WAL_BLOCKERS = [
    None,
    7,
    {"detail": "not-a-token"},
    "vault failed",
    "vault-failed\nnext-line",
    "vault failed: SECRET=opaque-sentinel\n/path/to/private",
    "/path/to/private",
    "a" * 129,
    "opaque-sentinel",
]


@pytest.mark.parametrize(
    "status",
    [
        "PRE_BACKUP",
        "PRE_BACKUP_NO_MUTATION_TERMINAL",
        "BLOCKED",
        "ROLLBACK_BLOCKED_RETRY_REQUIRED",
    ],
)
@pytest.mark.parametrize("unsafe_blocker", UNSAFE_WAL_BLOCKERS)
def test_wal_rejects_unsafe_blocker_for_every_recovery_state(status, unsafe_blocker):
    transaction_id = "20260722T120000Z-b10c0bad"
    wal = tx._initial_wal(transaction_id)
    wal["status"] = status
    wal["blocker"] = unsafe_blocker

    with pytest.raises(tx.Blocked, match="wal-blocker-invalid"):
        tx._validate_wal(contract(), wal, transaction_id)


def test_pre_backup_rejects_unsafe_wal_blocker_before_artifact_or_backend_mutation(tmp_path):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-b10c0bee"
    directory = tmp_path / transaction_id
    directory.mkdir(mode=0o700)
    wal = tx._initial_wal(transaction_id)
    wal["blocker"] = "vault failed: SECRET=opaque-sentinel\n/path/to/private"
    tx.atomic_json(directory / "wal.json", wal)
    tx.atomic_json(
        directory / "transaction-evidence.json",
        tx._runtime_projection(transaction_id, "PRE_BACKUP", []),
    )
    wal_before = (directory / "wal.json").read_bytes()
    evidence_before = (directory / "transaction-evidence.json").read_bytes()
    events_before = list(backend.events)

    with pytest.raises(tx.Blocked, match="wal-blocker-invalid"):
        tx.resume_transaction(
            contract(), backend, tmp_path, transaction_id, require_root=False,
        )

    assert (directory / "wal.json").read_bytes() == wal_before
    assert (directory / "transaction-evidence.json").read_bytes() == evidence_before
    assert not (directory / "ledger.json").exists()
    assert backend.events == events_before
    assert backend.puts == [] and backend.deleted == []


def test_wal_accepts_strict_blocker_tokens_for_recovery_states(tmp_path):
    assert tx._fixed_blocker("raft-snapshot-failed") == "raft-snapshot-failed"
    with pytest.raises(tx.Blocked, match="blocker-token-invalid"):
        tx._fixed_blocker("opaque-sentinel")

    transaction_id = "20260722T120000Z-b10c0bef"
    for status in (
        "PRE_BACKUP",
        "PRE_BACKUP_NO_MUTATION_TERMINAL",
        "BLOCKED",
        "ROLLBACK_BLOCKED_RETRY_REQUIRED",
    ):
        wal = tx._initial_wal(transaction_id)
        wal["status"] = status
        wal["blocker"] = "raft-snapshot-failed"
        tx._validate_wal(contract(), wal, transaction_id)

    for index, unsafe in enumerate((
        "vault failed: SECRET=opaque-sentinel\n/path/to/private",
        "opaque-sentinel",
    )):
        direct_id = f"20260722T120000Z-b10c0bf{index}"
        directory = tmp_path / direct_id
        directory.mkdir(mode=0o700)
        direct_wal = tx._initial_wal(direct_id)
        direct_wal["blocker"] = unsafe
        result = tx._terminate_pre_backup_no_mutation(
            directory, direct_id, direct_wal,
        )
        assert result["status"] == "PRE_BACKUP_NO_MUTATION_TERMINAL"
        terminal = json.loads((directory / "wal.json").read_text())
        assert terminal["blocker"] == "pre-backup-interrupted-before-backup-proof"
        assert "opaque-sentinel" not in (directory / "wal.json").read_text()


@pytest.mark.parametrize(
    ("failure_stage", "expected_blocker"),
    [
        ("backup", "pre-backup-failed"),
        ("install", "control-plane-install-failed"),
        ("restore", "control-plane-restore-test-failed"),
        ("reinstall", "control-plane-reinstall-failed"),
        ("rollback", "owned-version-soft-delete-failed"),
    ],
)
def test_every_wal_blocker_producer_maps_regex_valid_sensitive_detail_to_fixed_token(
    tmp_path, failure_stage, expected_blocker,
):
    backend = SensitiveStageFailureBackend(failure_stage, "opaque-sentinel")
    transaction_id = {
        "backup": "20260722T120000Z-b10c1001",
        "install": "20260722T120000Z-b10c1002",
        "restore": "20260722T120000Z-b10c1003",
        "reinstall": "20260722T120000Z-b10c1004",
        "rollback": "20260722T120000Z-b10c1005",
    }[failure_stage]

    with pytest.raises(tx.Blocked):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id, require_root=False,
        )

    directory = tmp_path / transaction_id
    wal = json.loads((directory / "wal.json").read_text())
    assert wal["blocker"] == expected_blocker
    for artifact in directory.iterdir():
        assert "opaque-sentinel" not in artifact.read_text(errors="ignore")


@pytest.mark.parametrize(
    ("failure_stage", "expected_reason"),
    [
        ("backup", "operation-blocked"),
        ("install", "operation-blocked"),
        ("restore", "operation-blocked"),
        ("reinstall", "operation-blocked"),
        ("rollback", "rollback-retry-required"),
    ],
)
def test_executor_entrypoint_never_emits_sensitive_stage_exception_detail(
    monkeypatch, tmp_path, capsys, failure_stage, expected_reason,
):
    backend = SensitiveStageFailureBackend(failure_stage, "opaque-sentinel")
    transaction_id = {
        "backup": "20260722T120000Z-b10c2001",
        "install": "20260722T120000Z-b10c2002",
        "restore": "20260722T120000Z-b10c2003",
        "reinstall": "20260722T120000Z-b10c2004",
        "rollback": "20260722T120000Z-b10c2005",
    }[failure_stage]

    def execute_without_live_access(*_args):
        return tx.run_transaction(
            contract(), backend, tmp_path, transaction_id, require_root=False,
        )

    monkeypatch.setattr(tx, "execute_reviewed_live", execute_without_live_access)
    result = tx.main([
        "execute-reviewed-live",
        "--bundle-root", str(tmp_path),
        "--transaction-id", transaction_id,
        "--expected-hash", "0" * 64,
        "--deadline-epoch", str(int(time.time()) + 60),
    ])
    captured = capsys.readouterr()
    assert result == 2 and captured.out == ""
    assert json.loads(captured.err) == {"status": "BLOCKED", "reason": expected_reason}
    assert "opaque-sentinel" not in captured.err


@pytest.mark.parametrize(
    ("reason", "expected_reason"),
    [
        ("raft-snapshot-failed", "raft-snapshot-failed"),
        ("arbitrary-valid-looking-token", "operation-blocked"),
        ("private detail\n/private/path/opaque-sentinel", "operation-blocked"),
        ({"private": "opaque-sentinel"}, "operation-blocked"),
    ],
)
def test_executor_entrypoint_uses_only_finite_safe_output_reasons(
    monkeypatch, tmp_path, capsys, reason, expected_reason,
):
    def fail_without_live_access(*_args):
        raise tx.Blocked(reason)

    monkeypatch.setattr(tx, "execute_reviewed_live", fail_without_live_access)
    result = tx.main([
        "execute-reviewed-live",
        "--bundle-root", str(tmp_path),
        "--transaction-id", "20260722T120000Z-b10c3001",
        "--expected-hash", "0" * 64,
        "--deadline-epoch", str(int(time.time()) + 60),
    ])
    captured = capsys.readouterr()
    assert result == 2 and captured.out == ""
    assert json.loads(captured.err) == {"status": "BLOCKED", "reason": expected_reason}
    assert not any(
        marker in captured.err
        for marker in ("arbitrary-valid-looking-token", "private detail", "/private/path", "opaque-sentinel")
    )


def test_executor_entrypoint_cleans_reviewed_tmpfs_when_context_load_fails(
    monkeypatch, capsys,
):
    root = Path(tempfile.mkdtemp(prefix="atius-phase52-reviewed-test-", dir="/dev/shm"))
    root.chmod(0o700)
    private = root / "private"; private.mkdir(mode=0o700)
    (private / "rclone.conf").write_text("opaque-private-sentinel", encoding="utf-8")

    def fail_context(*_args, **_kwargs):
        raise tx.Blocked("reviewed-bundle-manifest-invalid")

    monkeypatch.setattr(tx, "_reviewed_live_context", fail_context)
    result = tx.main([
        "execute-reviewed-live", "--bundle-root", str(root),
        "--transaction-id", "20260722T120000Z-b10c3002",
        "--expected-hash", "0" * 64,
        "--deadline-epoch", str(int(time.time()) + 60),
    ])
    captured = capsys.readouterr()

    assert result == 2 and not root.exists()
    assert "opaque-private-sentinel" not in captured.out + captured.err


def test_executor_entrypoint_cleanup_failure_is_fail_closed_and_sanitized(
    monkeypatch, capsys,
):
    root = Path(tempfile.mkdtemp(prefix="atius-phase52-reviewed-test-", dir="/dev/shm"))
    root.chmod(0o700)
    real_rmtree = tx.shutil.rmtree

    monkeypatch.setattr(
        tx, "execute_reviewed_live",
        lambda *_args: (_ for _ in ()).throw(tx.Blocked("opaque-private-sentinel")),
    )
    monkeypatch.setattr(
        tx.shutil, "rmtree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("opaque-cleanup-detail")),
    )
    try:
        result = tx.main([
            "execute-reviewed-live", "--bundle-root", str(root),
            "--transaction-id", "20260722T120000Z-b10c3003",
            "--expected-hash", "0" * 64,
            "--deadline-epoch", str(int(time.time()) + 60),
        ])
        captured = capsys.readouterr()
    finally:
        monkeypatch.setattr(tx.shutil, "rmtree", real_rmtree)
        real_rmtree(root, ignore_errors=True)

    assert result == 2
    assert json.loads(captured.err) == {"status": "BLOCKED", "reason": "operation-blocked"}
    assert "opaque" not in captured.out + captured.err


@pytest.mark.parametrize(
    "reason",
    [
        "arbitrary-valid-looking-token",
        "private detail\n/private/path/opaque-sentinel",
        {"private": "opaque-sentinel"},
    ],
)
def test_coordinator_entrypoint_never_emits_gate_exception_detail(
    monkeypatch, tmp_path, capsys, reason,
):
    def fail_preflight(*_args, **_kwargs):
        raise gate.GateBlocked(reason)

    monkeypatch.setattr(gate, "preflight", fail_preflight)
    result = gate.main([
        "preflight", "--repo", str(REPO), "--seal", str(tmp_path / "seal.json"),
        "--skip-self-tests",
    ])
    captured = capsys.readouterr()
    assert result == 2 and captured.out == ""
    assert json.loads(captured.err) == {"status": "BLOCKED", "reason": "gate-blocked"}
    assert not any(
        marker in captured.err
        for marker in ("arbitrary-valid-looking-token", "private detail", "/private/path", "opaque-sentinel")
    )


@pytest.mark.parametrize("index", range(7))
@pytest.mark.parametrize("point", [
    "before-intent-fsync", "after-intent-fsync", "before-intent-rename", "after-intent-rename",
    "before-put", "after-put-ack", "before-version-fsync", "after-version-fsync",
    "before-version-rename", "after-version-rename",
])
def test_fault_injection_every_create_is_fail_closed_and_value_free(tmp_path, index, point):
    backend = FakeBackend()
    fault = tx.FaultInjector({f"{index}:{point}"})
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(contract(), backend, tmp_path, f"20260722T1200{index:02d}Z-abcdef12", fault=fault, require_root=False)
    evidence = list(tmp_path.glob("*/transaction-evidence.json"))
    if evidence:
        raw = evidence[0].read_text()
        assert "opaque-sentinel" not in raw and "kkkkkkkk" not in raw


def test_restart_with_unacknowledged_visible_create_is_ambiguous_and_never_deletes(tmp_path):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-aaaabbbb"
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id,
            fault=tx.FaultInjector({"0:after-put-ack"}), require_root=False,
        )
    interrupted = json.loads((tmp_path / transaction_id / "transaction-evidence.json").read_text())
    assert interrupted["live_write_performed"] is None
    assert interrupted["vault_write_ownership"] == "UNRESOLVED"
    with pytest.raises(tx.Blocked, match="ambiguous-write-ownership"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert backend.deleted == []
    assert backend.events[-1] == "restore-control-plane"


def test_ambiguous_ownership_restore_failure_is_restore_only_retryable(tmp_path):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-aabbccdd"
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id,
            fault=tx.FaultInjector({"0:after-put-ack"}), require_root=False,
        )
    backend.restore_fail_once = True
    with pytest.raises(tx.Blocked, match="ambiguous-write-ownership-control-plane-restore-retry"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    wal_path = tmp_path / transaction_id / "wal.json"
    assert json.loads(wal_path.read_text())["status"] == "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY"
    assert backend.deleted == []
    metadata_count = len([event for event in backend.events if event.startswith("metadata:")])
    with pytest.raises(tx.Blocked, match="ambiguous-write-ownership"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert json.loads(wal_path.read_text())["status"] == "OWNERSHIP_AMBIGUOUS_BLOCKED"
    assert len([event for event in backend.events if event.startswith("metadata:")]) == metadata_count
    assert backend.deleted == []


def test_any_unacknowledged_intent_with_prior_acks_is_ambiguous_and_never_deletes(tmp_path):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-acde5555"
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id,
            fault=tx.FaultInjector({"2:after-put-ack"}), require_root=False,
        )
    assert len(backend.puts) == 3
    wal_path = tmp_path / transaction_id / "wal.json"
    wal = json.loads(wal_path.read_text())
    assert [row["status"] for row in wal["writes"]] == ["acknowledged", "acknowledged", "intent"]
    with pytest.raises(tx.Blocked, match="ambiguous-write-ownership"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert backend.deleted == []
    assert json.loads(wal_path.read_text())["status"] == "OWNERSHIP_AMBIGUOUS_BLOCKED"


def test_restart_with_pristine_unacknowledged_intent_is_ambiguous_and_never_deletes(tmp_path):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-a1b2c3d4"
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id,
            fault=tx.FaultInjector({"0:before-put"}), require_root=False,
        )
    with pytest.raises(tx.Blocked, match="ambiguous-write-ownership"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert backend.deleted == []
    assert backend.events[-1] == "restore-control-plane"
    with pytest.raises(tx.Blocked, match="ambiguous-write-ownership"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)


@pytest.mark.parametrize("metadata", [
    {"current_version": 1, "oldest_version": 1, "versions": {"1": {}}},
    {"current_version": 0, "oldest_version": 0, "versions": {"1": {"deletion_time": ""}}},
])
def test_metadata_history_or_drift_blocks_before_generation_or_put(tmp_path, metadata):
    first = contract()["writes"][0]["vault_path"]
    backend = FakeBackend(metadata={first: metadata})
    with pytest.raises(tx.Blocked, match="vault-path-not-pristine"):
        tx.run_transaction(contract(), backend, tmp_path, "20260722T120000Z-ccccdddd", require_root=False)
    assert "generate" not in backend.events and backend.puts == [] and backend.deleted == []


def test_double_metadata_read_drift_blocks(tmp_path):
    class Drift(FakeBackend):
        def metadata(self, vault_path):
            count = sum(event == f"metadata:{vault_path}" for event in self.events)
            self.events.append(f"metadata:{vault_path}")
            return {"current_version": count, "oldest_version": count, "versions": {} if count == 0 else {"1": {}}}
    backend = Drift()
    with pytest.raises(tx.Blocked, match="vault-metadata-drift"):
        tx.run_transaction(contract(), backend, tmp_path, "20260722T120000Z-ddddeeee", require_root=False)
    assert backend.puts == []


def test_metadata_failure_after_install_restores_control_plane(tmp_path):
    first = contract()["writes"][0]["vault_path"]
    backend = FakeBackend(metadata={first: {"current_version": 1, "oldest_version": 1, "versions": {"1": {}}}})
    with pytest.raises(tx.Blocked, match="vault-path-not-pristine"):
        tx.run_transaction(contract(), backend, tmp_path, "20260722T120000Z-abcdabcd", require_root=False)
    assert backend.events[-1] == "restore-control-plane"


def test_successful_empty_metadata_json_is_not_pristine(monkeypatch, tmp_path):
    backend = object.__new__(tx.LocalVaultBackend)
    backend.vault = tmp_path / "atius-vault"
    monkeypatch.setattr(tx, "_bounded_process_detailed", lambda *a, **k: (0, b"{}", b""))
    with pytest.raises(tx.Blocked, match="vault-metadata-response-invalid"):
        backend.metadata("kv/atius/rustdesk/server")


def test_metadata_success_requires_explicit_kv_schema_and_fields(monkeypatch, tmp_path):
    backend = object.__new__(tx.LocalVaultBackend)
    backend.vault = tmp_path / "atius-vault"
    raw = json.dumps({
        "mount_type": "kv",
        "data": {"current_version": 0, "oldest_version": 0, "versions": {}},
    }).encode()
    monkeypatch.setattr(tx, "_bounded_process_detailed", lambda *a, **k: (0, raw, b""))
    assert backend.metadata("kv/atius/rustdesk/server") == {
        "current_version": 0,
        "oldest_version": 0,
        "versions": {},
    }


@pytest.mark.parametrize(
    "state",
    [
        "BACKUP_PROVED",
        "CONTROL_PLANE_INSTALLING",
        "CONTROL_PLANE_INSTALLED",
        "METADATA_PROVED_PRISTINE",
        "CREATING",
    ],
)
def test_zero_ack_post_backup_resume_restores_bundle_and_becomes_terminal(tmp_path, state):
    class InstallCrash(FakeBackend):
        def install_control_plane(self, transaction_dir, managed_sources):
            self.events.append("install-control-plane")
            raise tx.InjectedCrash("install-interrupted")

    backend = InstallCrash()
    transaction_id = "20260722T120000Z-51aa51aa"
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    wal_path = tmp_path / transaction_id / "wal.json"
    wal = json.loads(wal_path.read_text())
    wal["status"] = state
    wal["writes"] = []
    tx.atomic_json(wal_path, wal)

    result = tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert result["status"] == "BLOCKED"
    assert backend.events[-1] == "restore-control-plane"
    terminal = json.loads(wal_path.read_text())
    assert terminal["status"] == "BLOCKED"
    assert terminal["control_plane_restored"] is True
    with pytest.raises(tx.Blocked, match="transaction-terminal-blocked"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)


def test_install_intent_is_fsynced_before_control_plane_mutation(tmp_path):
    class InstallCrash(FakeBackend):
        def install_control_plane(self, transaction_dir, managed_sources):
            wal = json.loads((transaction_dir / "wal.json").read_text())
            assert wal["status"] == "CONTROL_PLANE_INSTALLING"
            raise tx.InjectedCrash("install-interrupted")

    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(
            contract(), InstallCrash(), tmp_path, "20260722T120000Z-52aa52aa", require_root=False,
        )


@pytest.mark.parametrize("point", ["after-version-rename"])
def test_restart_after_any_ack_rolls_back_owned_and_requires_reauthorization(tmp_path, point):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-abcddcba"
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id,
            fault=tx.FaultInjector({f"2:{point}"}), require_root=False,
        )
    result = tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert result["status"] == "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION"
    assert len(backend.deleted) in {2, 3}


def test_corrupt_backup_blocks_control_plane_install_and_put(tmp_path):
    backend = FakeBackend(corrupt_backup=True)
    with pytest.raises(tx.Blocked, match="backup-(proof-failed|artifact-digest-drift)"):
        tx.run_transaction(contract(), backend, tmp_path, "20260722T120000Z-eeeeffff", require_root=False)
    assert "install-control-plane" not in backend.events and backend.puts == []


def test_cas_conflict_restores_control_plane_and_soft_deletes_only_owned_versions(tmp_path):
    backend = FakeBackend(cas_conflict_at=3)
    transaction_id = "20260722T120000Z-ffffaaaa"
    result = tx.run_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert result["status"] == "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION"
    assert len(backend.deleted) == 3
    with pytest.raises(tx.Blocked, match="manual-reauthorization-required"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert len(backend.deleted) == 3
    assert backend.events[-1] == "restore-control-plane"
    with pytest.raises(tx.Blocked, match="manual-reauthorization-required"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert len(backend.deleted) == 3


def test_interrupted_rollback_retries_only_exact_owned_versions_then_is_terminal(tmp_path):
    backend = FakeBackend(cas_conflict_at=3, delete_fail_once=True)
    transaction_id = "20260722T120000Z-fedcba98"
    with pytest.raises(tx.Blocked, match="rollback-retry-required"):
        tx.run_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    result = tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert result["status"] == "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION"
    assert len(backend.deleted) == 3


def test_zero_ack_rollback_retry_state_only_retries_restore_and_never_puts(tmp_path):
    class InstallCrash(FakeBackend):
        def install_control_plane(self, transaction_dir, managed_sources):
            self.events.append("install-control-plane")
            raise tx.InjectedCrash("install-interrupted")

    backend = InstallCrash()
    transaction_id = "20260722T120000Z-acde6666"
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    wal_path = tmp_path / transaction_id / "wal.json"
    wal = json.loads(wal_path.read_text())
    wal.update({
        "status": "ROLLBACK_BLOCKED_RETRY_REQUIRED", "writes": [],
        "control_plane_restored": False, "blocker": "zero-ack-control-plane-restore-failed",
    })
    tx.atomic_json(wal_path, wal)
    result = tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    assert result["status"] == "BLOCKED"
    assert backend.puts == [] and backend.deleted == []
    assert backend.events[-1] == "restore-control-plane"


def test_pre_reinstall_restore_double_failure_persists_retry_and_resume_is_restore_only(tmp_path):
    class RestoreFailures(FakeBackend):
        def __init__(self, failures):
            super().__init__()
            self.restore_failures = failures

        def restore_control_plane(self, transaction_dir):
            self.events.append("restore-control-plane")
            if self.restore_failures:
                self.restore_failures -= 1
                raise tx.Blocked("fixture-control-plane-restore-failed")

    backend = RestoreFailures(2)
    transaction_id = "20260722T120000Z-acde1010"
    with pytest.raises(tx.Blocked, match="rollback-retry-required"):
        tx.run_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    wal_path = tmp_path / transaction_id / "wal.json"
    wal = json.loads(wal_path.read_text())
    assert wal["status"] == "ROLLBACK_BLOCKED_RETRY_REQUIRED"
    assert wal["control_plane_restored"] is False and wal["writes"] == []
    retry = json.loads((tmp_path / transaction_id / "transaction-evidence.json").read_text())
    assert retry["status"] == "ROLLBACK_BLOCKED_RETRY_REQUIRED"
    assert retry["write_count"] == 0 and retry["live_write_performed"] is False
    assert retry["vault_write_ownership"] == "NONE"
    event_count = len(backend.events)
    put_count = len(backend.puts)
    delete_count = len(backend.deleted)
    install_count = backend.events.count("install-control-plane")

    recovered = tx.resume_transaction(
        contract(), backend, tmp_path, transaction_id, require_root=False,
    )
    assert recovered["status"] == "BLOCKED"
    assert backend.events[event_count:] == ["restore-control-plane"]
    assert backend.events.count("install-control-plane") == install_count
    assert len(backend.puts) == put_count and len(backend.deleted) == delete_count == 0
    terminal = json.loads(wal_path.read_text())
    assert terminal["status"] == "BLOCKED" and terminal["control_plane_restored"] is True


def test_pre_reinstall_restore_retry_remains_retryable_after_repeated_failure(tmp_path):
    class RestoreFailures(FakeBackend):
        def __init__(self):
            super().__init__()
            self.restore_failures = 3

        def restore_control_plane(self, transaction_dir):
            self.events.append("restore-control-plane")
            if self.restore_failures:
                self.restore_failures -= 1
                raise tx.Blocked("fixture-control-plane-restore-failed")

    backend = RestoreFailures()
    transaction_id = "20260722T120000Z-acde2020"
    with pytest.raises(tx.Blocked, match="rollback-retry-required"):
        tx.run_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    with pytest.raises(tx.Blocked, match="rollback-retry-required"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    wal = json.loads((tmp_path / transaction_id / "wal.json").read_text())
    assert wal["status"] == "ROLLBACK_BLOCKED_RETRY_REQUIRED"
    assert wal["control_plane_restored"] is False and wal["writes"] == []
    evidence = json.loads((tmp_path / transaction_id / "transaction-evidence.json").read_text())
    assert evidence["status"] == "ROLLBACK_BLOCKED_RETRY_REQUIRED"
    assert evidence["write_count"] == 0 and evidence["live_write_performed"] is False
    assert evidence["vault_write_ownership"] == "NONE"
    assert backend.puts == [] and backend.deleted == []
    assert backend.events.count("install-control-plane") == 1


@pytest.mark.parametrize("fault_point", ["0:before-put", "2:after-put-ack"])
def test_rollback_retry_with_any_unacknowledged_intent_normalizes_to_ambiguous_without_delete(
    tmp_path, fault_point,
):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-acde8888"
    with pytest.raises(tx.InjectedCrash):
        tx.run_transaction(
            contract(), backend, tmp_path, transaction_id,
            fault=tx.FaultInjector({fault_point}), require_root=False,
        )
    wal_path = tmp_path / transaction_id / "wal.json"
    wal = json.loads(wal_path.read_text())
    assert any(row["status"] == "intent" for row in wal["writes"])
    wal["status"] = "ROLLBACK_BLOCKED_RETRY_REQUIRED"
    wal["blocker"] = "owned-version-soft-delete-failed"
    tx.atomic_json(wal_path, wal)

    with pytest.raises(tx.Blocked, match="ambiguous-write-ownership"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    terminal = json.loads(wal_path.read_text())
    assert terminal["status"] == "OWNERSHIP_AMBIGUOUS_BLOCKED"
    assert backend.deleted == []
    evidence = json.loads((tmp_path / transaction_id / "transaction-evidence.json").read_text())
    assert evidence["live_write_performed"] is None
    assert evidence["vault_write_ownership"] == "UNRESOLVED"


def test_rollback_retry_projection_rejects_trailing_and_nontrailing_intents():
    payload = contract()
    transaction_id = "20260722T235959Z-acde9999"
    ack = lambda index: {
        "id": payload["writes"][index]["id"],
        "vault_path": payload["writes"][index]["vault_path"],
        "status": "acknowledged", "version": 1,
    }
    intent = lambda index: {
        "id": payload["writes"][index]["id"],
        "vault_path": payload["writes"][index]["vault_path"],
        "status": "intent",
    }
    for writes in ([intent(0)], [ack(0), intent(1)], [intent(0), ack(1)]):
        wal = {
            "schema": "phase52-gate-b-wal-v1", "transaction_id": transaction_id,
            "status": "ROLLBACK_BLOCKED_RETRY_REQUIRED", "writes": writes,
            "soft_delete_performed": False,
        }
        evidence = tx._runtime_projection(
            transaction_id, "ROLLBACK_BLOCKED_RETRY_REQUIRED", [],
        )
        with pytest.raises(tx.Blocked, match="wal-rollback-proof-invalid"):
            tx._reconcile_status_projection(payload, wal, evidence, transaction_id)

    unresolved = tx._runtime_projection(
        transaction_id, "ROLLBACK_BLOCKED_RETRY_REQUIRED", [],
        ownership_unresolved=True,
    )
    with pytest.raises(gate.GateBlocked, match="remote-recovery-result-invalid"):
        gate._validate_recovery_result(payload, unresolved, transaction_id)


def test_resume_pass_revalidates_complete_wal_proofs_and_never_trusts_evidence_directly(tmp_path):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-acde7777"
    tx.run_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    wal_path = tmp_path / transaction_id / "wal.json"
    wal = json.loads(wal_path.read_text())
    wal.pop("metadata_proved_pristine", None)
    tx.atomic_json(wal_path, wal)
    with pytest.raises(tx.Blocked, match="wal-pass-proof-invalid"):
        tx.resume_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)


def test_lock_contention_blocks_without_mutation(tmp_path):
    root = tmp_path.resolve()
    root.mkdir(exist_ok=True)
    root.chmod(0o700)
    lock_path = root / ".phase52-gate-b.lock"
    lock = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        backend = FakeBackend()
        with pytest.raises(tx.Blocked, match="transaction-lock-contended"):
            tx.run_transaction(contract(), backend, root, "20260722T120000Z-bbbbcccc", require_root=False)
        assert backend.events == []
    finally:
        os.close(lock)


def test_backup_root_symlink_and_symlink_ancestor_are_rejected(tmp_path):
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(tx.Blocked, match="backup-root-not-canonical"):
        tx.run_transaction(
            contract(), FakeBackend(), link, "20260722T120000Z-53aa53aa", require_root=False,
        )
    with pytest.raises(tx.Blocked, match="backup-root-ancestor-invalid"):
        tx.run_transaction(
            contract(), FakeBackend(), link / "child", "20260722T120000Z-54aa54aa", require_root=False,
        )


def test_live_root_must_equal_contract_root(tmp_path):
    with pytest.raises(tx.Blocked, match="backup-root-live-path-drift"):
        tx._validate_root(tmp_path, require_root=True, expected_live_root=Path("/var/backups/atius-vault/phase52"))


def test_fsync_file_and_parent_is_explicit(monkeypatch, tmp_path):
    artifact = tmp_path / "raft.snapshot"
    artifact.write_bytes(b"snapshot")
    calls = []
    original = os.fsync

    def observed(descriptor):
        calls.append(descriptor)
        return original(descriptor)

    monkeypatch.setattr(os, "fsync", observed)
    tx._fsync_file_and_parent(artifact)
    assert len(calls) == 2


def test_root_backup_modes_and_redacted_ledger(tmp_path):
    backend = FakeBackend()
    transaction_id = "20260722T120000Z-1234abcd"
    tx.run_transaction(contract(), backend, tmp_path, transaction_id, require_root=False)
    root = tmp_path / transaction_id
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    for name in ("raft.snapshot", "control-plane.tar", "manifest.json", "ledger.json", "transaction-evidence.json"):
        assert stat.S_IMODE((root / name).stat().st_mode) == 0o600
    ledger = json.loads((root / "ledger.json").read_text())
    assert [row["version"] for row in ledger["writes"]] == [1] * 7
    assert all(set(row) == {"id", "vault_path", "version", "ownership"} for row in ledger["writes"])


def test_preflight_candidate_binds_gate_a_and_managed_sources(tmp_path):
    seal = tmp_path / "seal.json"
    result = gate.preflight(REPO, seal, run_self_tests=True)
    assert result["status"] == "PENDING" and result["reviews"] == []
    assert result["gate_a"]["sha256"] == hashlib.sha256(GATE_A.read_bytes()).hexdigest()
    gate_a = json.loads(GATE_A.read_text())
    assert result["gate_a"]["managed_sources"] == gate_a["managed_sources"]
    assert {row["path"] for row in result["sealed_sources"]} == {
        CONTRACT.relative_to(REPO).as_posix(), EXECUTOR.relative_to(REPO).as_posix(),
        COORDINATOR.relative_to(REPO).as_posix(), Path(__file__).relative_to(REPO).as_posix(),
    }
    assert result["network_performed"] is False and result["live_write_performed"] is False


def test_finalize_requires_two_distinct_pass_reviews_on_exact_hash_set(tmp_path):
    seal = tmp_path / "seal.json"
    candidate = gate.preflight(REPO, seal, run_self_tests=True)
    with pytest.raises(gate.GateBlocked, match="two-independent-pass-reviews-required"):
        gate.finalize_seal(REPO, seal)
    digest = candidate["hash_set_sha256"]
    candidate["reviews"] = [
        {"reviewer": "review-a", "status": "PASS", "hash_set_sha256": digest},
        {"reviewer": "review-b", "status": "PASS", "hash_set_sha256": digest},
    ]
    gate.atomic_json(seal, candidate, mode=0o600)
    passed = gate.finalize_seal(REPO, seal)
    assert passed["status"] == "PASS" and passed["sealed_at"].endswith("Z")
    assert stat.S_IMODE(seal.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "mutator",
    [
        lambda checks: checks.__setitem__("success_write_count", 0),
        lambda checks: checks.__setitem__("cas_conflict_owned_rollback_count", 0),
        lambda checks: checks.__setitem__("network_performed", 0),
        lambda checks: checks.__setitem__("unexpected", False),
    ],
)
def test_finalize_requires_exact_offline_check_schema_and_counts(tmp_path, mutator):
    seal = tmp_path / "seal.json"
    candidate = gate.preflight(REPO, seal, run_self_tests=True)
    digest = candidate["hash_set_sha256"]
    candidate["reviews"] = [
        {"reviewer": "review-a", "status": "PASS", "hash_set_sha256": digest},
        {"reviewer": "review-b", "status": "PASS", "hash_set_sha256": digest},
    ]
    mutator(candidate["checks"])
    gate.atomic_json(seal, candidate, mode=0o600)
    with pytest.raises(gate.GateBlocked, match="seal-checks-not-pass"):
        gate.finalize_seal(REPO, seal)


def _valid_remote_result(transaction_id="20260722T235959Z-acde1234"):
    payload = contract()
    return {
        "schema": "phase52-gate-b-transaction-evidence-v1",
        "transaction_id": transaction_id,
        "status": "PASS",
        "write_count": 7,
        "vault_versions": [
            {"id": row["id"], "vault_path": row["vault_path"], "version": 1}
            for row in payload["writes"]
        ],
        "mutation_accounting": {
            "atius-srv-2": {"candidate_data_plane_mutation": False, "authorized_vault_control_plane_mutation": False},
            "atius-srv-3": {"candidate_data_plane_mutation": False, "authorized_vault_control_plane_mutation": True},
            "vault_data_create_only_write_count": 7,
        },
        "live_write_performed": True,
        "vault_write_ownership": "FSYNCED_WAL_ACK",
        "secret_material_present": False,
        "windows_install_performed": False,
        "network_listener_created": False,
    }


def test_remote_result_requires_exact_authorized_rows_versions_and_accounting():
    expected = _valid_remote_result()
    assert gate._validate_remote_result(contract(), expected, expected["transaction_id"]) == expected
    mutations = []
    fake = copy.deepcopy(expected)
    fake["vault_versions"] = [{"id": "evil", "vault_path": "kv/evil", "version": 999}] * 7
    mutations.append(fake)
    fake = copy.deepcopy(expected); fake["vault_versions"][0]["version"] = None; mutations.append(fake)
    fake = copy.deepcopy(expected); fake["mutation_accounting"]["vault_data_create_only_write_count"] = 999; mutations.append(fake)
    fake = copy.deepcopy(expected); fake["mutation_accounting"]["atius-srv-3"]["authorized_vault_control_plane_mutation"] = 1; mutations.append(fake)
    fake = copy.deepcopy(expected); fake["mutation_accounting"]["extra"] = False; mutations.append(fake)
    for candidate in mutations:
        with pytest.raises(gate.GateBlocked, match="remote-result-invalid"):
            gate._validate_remote_result(contract(), candidate, expected["transaction_id"])


def test_recovery_result_rejects_impossible_status_write_ownership_combinations():
    transaction_id = "20260722T235959Z-acde1234"
    blocked = _valid_remote_result(transaction_id)
    blocked.update({
        "status": "BLOCKED", "write_count": 0, "vault_versions": [],
        "live_write_performed": True, "vault_write_ownership": "FSYNCED_WAL_ACK",
    })
    blocked["mutation_accounting"]["vault_data_create_only_write_count"] = 0
    ambiguous = copy.deepcopy(blocked)
    ambiguous.update({
        "status": "OWNERSHIP_AMBIGUOUS_BLOCKED",
        "live_write_performed": False,
    })
    for candidate in (blocked, ambiguous):
        with pytest.raises(gate.GateBlocked, match="remote-recovery-result-invalid"):
            gate._validate_recovery_result(contract(), candidate, transaction_id)


def test_recovery_result_accepts_zero_ack_restore_retry_without_live_write():
    transaction_id = "20260722T235959Z-acde1234"
    retry = tx._runtime_projection(
        transaction_id, "ROLLBACK_BLOCKED_RETRY_REQUIRED", [],
    )
    assert gate._validate_recovery_result(contract(), retry, transaction_id) == retry


def test_status_reconciliation_uses_wal_as_authority_and_never_invents_zero_writes():
    payload = contract()
    transaction_id = "20260722T235959Z-a1b2c3d4"
    writes = [
        {"id": row["id"], "vault_path": row["vault_path"], "status": "acknowledged", "version": 1}
        for row in payload["writes"][:2]
    ]
    wal = {
        "schema": "phase52-gate-b-wal-v1", "transaction_id": transaction_id,
        "status": "CREATING", "writes": writes, "soft_delete_performed": False,
    }
    stale = tx._runtime_projection(transaction_id, "CREATING", [
        {"id": row["id"], "vault_path": row["vault_path"], "version": 1}
        for row in payload["writes"][:1]
    ])
    reconciled = tx._reconcile_status_projection(payload, wal, stale, transaction_id)
    assert reconciled["status"] == "CREATING"
    assert reconciled["write_count"] == 2
    assert reconciled["vault_versions"] == [
        {"id": row["id"], "vault_path": row["vault_path"], "version": 1}
        for row in payload["writes"][:2]
    ]
    assert reconciled["live_write_performed"] is True
    assert reconciled["vault_write_ownership"] == "FSYNCED_WAL_ACK"
    assert gate._validate_recovery_result(payload, reconciled, transaction_id) == reconciled

    leading = tx._runtime_projection(transaction_id, "CREATING", [
        {"id": row["id"], "vault_path": row["vault_path"], "version": 1}
        for row in payload["writes"][:3]
    ])
    with pytest.raises(tx.Blocked, match="transaction-evidence-leads-wal"):
        tx._reconcile_status_projection(payload, wal, leading, transaction_id)

    terminal_lead = tx._runtime_projection(
        transaction_id, "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION", [
            {"id": payload["writes"][0]["id"], "vault_path": payload["writes"][0]["vault_path"], "version": 1},
        ],
    )
    with pytest.raises(tx.Blocked, match="transaction-evidence-leads-wal"):
        tx._reconcile_status_projection(payload, wal, terminal_lead, transaction_id)


def test_status_reconciliation_reports_terminal_and_ambiguous_wal_not_stale_evidence():
    payload = contract()
    transaction_id = "20260722T235959Z-b1c2d3e4"
    acknowledged = [
        {"id": row["id"], "vault_path": row["vault_path"], "status": "acknowledged", "version": 1}
        for row in payload["writes"]
    ]
    pass_wal = {
        "schema": "phase52-gate-b-wal-v1", "transaction_id": transaction_id,
        "status": "PASS", "writes": acknowledged, "soft_delete_performed": False,
        "control_plane_install_proved": True, "control_plane_restore_tested": True,
        "control_plane_reinstall_proved": True, "metadata_proved_pristine": True,
        "created_values_verified": True, "control_plane_restored": False,
    }
    stale = tx._runtime_projection(transaction_id, "CREATING", [
        {"id": row["id"], "vault_path": row["vault_path"], "version": 1}
        for row in payload["writes"][:2]
    ])
    passed = tx._reconcile_status_projection(payload, pass_wal, stale, transaction_id)
    assert passed["status"] == "PASS"
    assert gate._validate_recovery_result(payload, passed, transaction_id) == passed

    ambiguous_wal = {
        "schema": "phase52-gate-b-wal-v1", "transaction_id": transaction_id,
        "status": "OWNERSHIP_AMBIGUOUS_BLOCKED",
        "writes": [{"id": payload["writes"][0]["id"], "vault_path": payload["writes"][0]["vault_path"], "status": "intent"}],
        "soft_delete_performed": False, "control_plane_restored": True,
    }
    ambiguous_stale = tx._runtime_projection(
        transaction_id, "CREATING", [], ownership_unresolved=True,
    )
    ambiguous = tx._reconcile_status_projection(payload, ambiguous_wal, ambiguous_stale, transaction_id)
    assert ambiguous["status"] == "OWNERSHIP_AMBIGUOUS_BLOCKED"
    assert ambiguous["live_write_performed"] is None
    assert ambiguous["vault_write_ownership"] == "UNRESOLVED"
    assert ambiguous["vault_versions"] == []
    assert gate._validate_recovery_result(payload, ambiguous, transaction_id) == ambiguous


def test_isolated_restore_identity_rejects_noop_snapshot_post():
    pre = {"cluster_id": "same", "raft_sha256": "a" * 64, "sentinel_written": True}
    no_op_post = {"cluster_id": "same", "raft_sha256": "a" * 64, "sealed": True, "storage_type": "raft"}
    with pytest.raises(tx.Blocked, match="isolated-vault-restore-noop"):
        tx._validate_isolated_restore_identity(pre, no_op_post)
    post = {"cluster_id": "different", "raft_sha256": "b" * 64, "sealed": True, "storage_type": "raft"}
    tx._validate_isolated_restore_identity(pre, post)


def test_raft_snapshot_bridges_container_namespace_and_cleans_temp(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    fake_process, container_files, calls = fake_vault_snapshot_bridge(b"raft-snapshot")
    monkeypatch.setattr(tx, "_bounded_process", fake_process)
    snapshot = tmp_path / "raft.snapshot"

    backend._create_raft_snapshot(snapshot)

    assert snapshot.read_bytes() == b"raft-snapshot"
    assert stat.S_IMODE(snapshot.stat().st_mode) == 0o600
    assert snapshot.stat().st_uid == os.geteuid()
    assert snapshot.stat().st_nlink == 1
    assert container_files == {}
    assert calls[0][:5] == [str(backend.vault), "operator", "raft", "snapshot", "save"]
    assert calls[1][:2] == [str(tx.PODMAN), "cp"]
    assert calls[2][:4] == [str(tx.PODMAN), "exec", tx.VAULT_CONTAINER, "rm"]
    assert calls[0][-1].startswith("/tmp/phase52-raft-")
    assert calls[1][2] == f"{tx.VAULT_CONTAINER}:{calls[0][-1]}"
    assert list(tmp_path.glob(".raft-staging-*")) == []


@pytest.mark.parametrize("fail_at", ["save", "copy", "cleanup", "cleanup_oserror"])
def test_raft_snapshot_bridge_failure_is_sanitized_and_removes_host_partial(
    monkeypatch, tmp_path, fail_at
):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    fake_process, _, calls = fake_vault_snapshot_bridge(fail_at=fail_at)
    monkeypatch.setattr(tx, "_bounded_process", fake_process)
    snapshot = tmp_path / "raft.snapshot"

    with pytest.raises(tx.Blocked, match="^raft-snapshot-failed$"):
        backend._create_raft_snapshot(snapshot)

    assert not snapshot.exists()
    assert any(command[:4] == [str(tx.PODMAN), "exec", tx.VAULT_CONTAINER, "rm"] for command in calls)
    assert list(tmp_path.glob(".raft-staging-*")) == []


def test_raft_snapshot_bridge_rejects_empty_staged_snapshot(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    fake_process, container_files, _ = fake_vault_snapshot_bridge(b"")
    monkeypatch.setattr(tx, "_bounded_process", fake_process)
    snapshot = tmp_path / "raft.snapshot"

    with pytest.raises(tx.Blocked, match="^raft-snapshot-failed$"):
        backend._create_raft_snapshot(snapshot)

    assert not snapshot.exists() and container_files == {}
    assert list(tmp_path.glob(".raft-staging-*")) == []


@pytest.mark.parametrize("invalid_kind", ["symlink", "directory", "hardlink", "wrong_uid"])
def test_raft_snapshot_bridge_rejects_invalid_staged_identity(
    monkeypatch, tmp_path, invalid_kind
):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    base_process, _, _ = fake_vault_snapshot_bridge()

    def invalid_process(command, private_input, **kwargs):
        result = base_process(command, private_input, **kwargs)
        if command[:2] == [str(tx.PODMAN), "cp"] and invalid_kind != "wrong_uid":
            _, container_path = command[2].split(":", 1)
            staged = Path(command[3]) / Path(container_path).name
            if invalid_kind == "symlink":
                staged.unlink(); staged.symlink_to(tmp_path / "missing")
            elif invalid_kind == "directory":
                staged.unlink(); staged.mkdir()
            elif invalid_kind == "hardlink":
                os.link(staged, staged.parent / "unexpected-hardlink")
        return result

    if invalid_kind == "wrong_uid":
        real_euid = os.geteuid()
        euid_calls = 0

        def mismatched_euid():
            nonlocal euid_calls
            euid_calls += 1
            return real_euid if euid_calls == 1 else real_euid + 1

        monkeypatch.setattr(tx.os, "geteuid", mismatched_euid)
    monkeypatch.setattr(tx, "_bounded_process", invalid_process)
    snapshot = tmp_path / "raft.snapshot"

    with pytest.raises(tx.Blocked, match="^raft-snapshot-failed$"):
        backend._create_raft_snapshot(snapshot)

    assert not snapshot.exists()


def test_raft_snapshot_bridge_publish_race_never_overwrites_competitor(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    fake_process, _, _ = fake_vault_snapshot_bridge()
    monkeypatch.setattr(tx, "_bounded_process", fake_process)
    snapshot = tmp_path / "raft.snapshot"

    def racing_link(source_path, destination_path, **kwargs):
        Path(destination_path).write_bytes(b"competitor")
        raise FileExistsError(destination_path)

    monkeypatch.setattr(tx.os, "link", racing_link)
    with pytest.raises(tx.Blocked, match="^raft-snapshot-failed$"):
        backend._create_raft_snapshot(snapshot)

    assert snapshot.read_bytes() == b"competitor"
    assert list(tmp_path.glob(".raft-staging-*")) == []


def test_raft_snapshot_bridge_mkdtemp_failure_is_sanitized(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    calls = []
    monkeypatch.setattr(tx.tempfile, "mkdtemp", lambda **kwargs: (_ for _ in ()).throw(OSError("fixture-mkdtemp")))
    monkeypatch.setattr(tx, "_bounded_process", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(tx.Blocked, match="^raft-snapshot-failed$"):
        backend._create_raft_snapshot(tmp_path / "raft.snapshot")

    assert calls == [] and list(tmp_path.glob(".raft-staging-*")) == []


def test_raft_snapshot_bridge_staging_setup_failure_is_sanitized_and_cleaned(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    real_mkdtemp = tx.tempfile.mkdtemp
    real_open = tx.os.open
    created = []
    calls = []

    def tracked_mkdtemp(**kwargs):
        value = real_mkdtemp(**kwargs); created.append(Path(value)); return value

    def failing_open(path, flags, *args, **kwargs):
        if created and Path(path) == created[0]:
            raise OSError("fixture-staging-open")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(tx.tempfile, "mkdtemp", tracked_mkdtemp)
    monkeypatch.setattr(tx.os, "open", failing_open)
    monkeypatch.setattr(tx, "_bounded_process", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(tx.Blocked, match="^raft-snapshot-failed$"):
        backend._create_raft_snapshot(tmp_path / "raft.snapshot")

    assert calls == [] and list(tmp_path.glob(".raft-staging-*")) == []


def test_raft_snapshot_bridge_rejects_preexisting_host_target(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    snapshot = tmp_path / "raft.snapshot"; snapshot.write_bytes(b"do-not-overwrite")
    monkeypatch.setattr(tx, "_bounded_process", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")))

    with pytest.raises(tx.Blocked, match="^raft-snapshot-failed$"):
        backend._create_raft_snapshot(snapshot)

    assert snapshot.read_bytes() == b"do-not-overwrite"


def test_raft_snapshot_bridge_rejects_preexisting_dangling_symlink_without_commands(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    snapshot = tmp_path / "raft.snapshot"; snapshot.symlink_to(tmp_path / "missing")
    monkeypatch.setattr(tx, "_bounded_process", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")))

    with pytest.raises(tx.Blocked, match="^raft-snapshot-failed$"):
        backend._create_raft_snapshot(snapshot)

    assert snapshot.is_symlink() and snapshot.readlink() == tmp_path / "missing"


def test_control_plane_tree_backup_restores_exact_state_and_absence(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    legacy = tmp_path / "legacy"; legacy.write_bytes(b"before"); legacy.chmod(0o640)
    state_root = tmp_path / "state"; (state_root / "nested").mkdir(parents=True)
    (state_root / "nested" / "value").write_bytes(b"original")
    backend.control_paths = [legacy]
    backend.control_state_path = state_root
    transaction = tmp_path / "transaction"; transaction.mkdir()

    fake_process, _, _ = fake_vault_snapshot_bridge()
    monkeypatch.setattr(tx, "_bounded_process", fake_process)
    backend.create_backups(transaction, contract())
    legacy.write_bytes(b"after")
    (state_root / "nested" / "value").write_bytes(b"changed")
    (state_root / "residual").write_bytes(b"must-disappear")
    backend.restore_control_plane(transaction)
    assert legacy.read_bytes() == b"before" and stat.S_IMODE(legacy.stat().st_mode) == 0o640
    assert (state_root / "nested" / "value").read_bytes() == b"original"
    assert not (state_root / "residual").exists()

    absent = tmp_path / "absent"; backend.control_state_path = absent
    transaction2 = tmp_path / "transaction2"; transaction2.mkdir()
    backend.create_backups(transaction2, contract())
    absent.mkdir(); (absent / "residual").write_bytes(b"remove")
    backend.restore_control_plane(transaction2)
    assert not absent.exists()


def test_control_plane_tree_restore_rejects_symlink_without_deleting(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    backend.control_paths = []
    state_root = tmp_path / "state"; state_root.mkdir(); (state_root / "value").write_bytes(b"before")
    backend.control_state_path = state_root
    transaction = tmp_path / "transaction"; transaction.mkdir()
    fake_process, _, _ = fake_vault_snapshot_bridge()
    monkeypatch.setattr(tx, "_bounded_process", fake_process)
    backend.create_backups(transaction, contract())
    (state_root / "value").unlink(); (state_root / "value").symlink_to(tmp_path / "outside")
    with pytest.raises(tx.Blocked, match="control-plane-target-identity-invalid"):
        backend.restore_control_plane(transaction)
    assert (state_root / "value").is_symlink()


def test_restore_prevalidates_every_payload_before_first_live_mutation(monkeypatch, tmp_path):
    source = tmp_path / "source"; source.mkdir()
    backend = tx.LocalVaultBackend(source, b"[giovanni-drive]\ntype = drive\n", "SHA256:4m+0420TZvKfUXyKrD5lLK2n/65QOBdWSgnW4AXJ7W0")
    first = tmp_path / "first"; second = tmp_path / "second"
    first.write_bytes(b"original-first"); second.write_bytes(b"original-second")
    backend.control_paths = [first, second]
    backend.control_state_path = tmp_path / "absent-state"
    transaction = tmp_path / "transaction"; transaction.mkdir()

    fake_process, _, _ = fake_vault_snapshot_bridge()
    monkeypatch.setattr(tx, "_bounded_process", fake_process)
    backend.create_backups(transaction, contract())
    first.write_bytes(b"live-first"); second.write_bytes(b"live-second")

    bundle = transaction / "control-plane.tar"
    with tarfile.open(bundle, mode="r:") as archive:
        staged = {member.name: archive.extractfile(member).read() for member in archive.getmembers()}
    staged["files/1"] = b"corrupt-late-payload"
    replacement = transaction / "replacement.tar"
    with tarfile.open(replacement, mode="w") as archive:
        for name, raw in staged.items():
            info = tarfile.TarInfo(name); info.size = len(raw); info.mode = 0o600
            archive.addfile(info, io.BytesIO(raw))
    replacement.chmod(0o600); os.replace(replacement, bundle)
    outer = json.loads((transaction / "manifest.json").read_text())
    outer["control_plane_bundle_sha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
    tx.atomic_json(transaction / "manifest.json", outer)

    with pytest.raises(tx.Blocked, match="control-plane-backup-invalid"):
        backend.restore_control_plane(transaction)
    assert first.read_bytes() == b"live-first"
    assert second.read_bytes() == b"live-second"


def test_approved_fingerprint_is_external_and_observed_must_match():
    approved = contract()["authorization"]["approved_horistic_ssh_key_fingerprint"]
    assert tx._validate_approved_fingerprint(approved, approved) == approved
    with pytest.raises(tx.Blocked, match="authorized-key-fingerprint-mismatch"):
        tx._validate_approved_fingerprint("SHA256:" + "A" * 43, approved)


def test_direct_first_route_uses_fallback_only_after_direct_probe_failure(monkeypatch):
    calls = []
    def probe(target, coordinator, tx_module):
        calls.append(target)
        return target.endswith("10.100.100.3")
    monkeypatch.setattr(gate, "_probe_ssh_target", probe)
    coordinator = contract()["live_coordinator"]
    selected, evidence = gate._select_ssh_target(coordinator, tx)
    assert calls == [coordinator["ssh_target"], coordinator["ssh_fallback_target"]]
    assert selected == coordinator["ssh_fallback_target"]
    assert evidence == {
        "policy": "direct-first",
        "direct_probe": "FAILED",
        "fallback_probe": "PASS",
        "selected_route": "fallback",
        "forced_relay_policy": "preserve-approved-runtime-policy",
    }


def test_both_route_probes_failed_is_confirmed_pre_send_block_not_outcome_ambiguity(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.json"
    seal_payload = {
        "hash_set_sha256": "a" * 64,
        "sealed_sources": [],
        "gate_a": {"path": "gate-a.json", "sha256": "b" * 64, "managed_sources": []},
    }
    payload = contract()
    monkeypatch.setattr(gate, "_validate_current_seal", lambda *a, **k: seal_payload)
    monkeypatch.setattr(gate, "_reviewed_bundle", lambda *a, **k: b"bundle")
    monkeypatch.setattr(gate, "load_json", lambda *a, **k: payload)
    monkeypatch.setattr(gate, "_probe_ssh_target", lambda *a, **k: False)
    monkeypatch.setattr(gate, "_new_transaction_id", lambda: "20260722T235959Z-acde1234")

    class Executor:
        Blocked = tx.Blocked
        @staticmethod
        def _bounded_process(*args, **kwargs):
            raise AssertionError("reviewed bundle must not be sent")

    monkeypatch.setattr(gate, "_load_executor", lambda *a, **k: Executor)
    with pytest.raises(gate.RouteUnavailable):
        gate.execute_live(REPO, SEAL, b"[giovanni-drive]\ntype = drive\n", runtime_evidence=runtime)
    evidence = json.loads(runtime.read_text())
    assert evidence["status"] == "REMOTE_ROUTE_BLOCKED"
    assert evidence["transaction_id"] is None
    assert evidence["write_count"] == 0 and evidence["vault_versions"] == []
    assert evidence["live_write_performed"] is False
    assert evidence["vault_write_ownership"] == "NONE"
    assert evidence["send_attempted"] is False
    assert evidence["remote_transaction_exists"] is False
    assert evidence["recovery_action"] == "retry-route-probes-before-new-transaction"


def test_recovery_route_block_preserves_known_transaction_but_never_invents_zero(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.json"
    transaction_id = "20260722T235959Z-acde1234"
    runtime.write_text(json.dumps({
        "status": "CREATING", "transaction_id": transaction_id,
        "write_count": 3, "live_write_performed": True,
        "vault_write_ownership": "FSYNCED_WAL_ACK",
    }))
    seal_payload = {
        "hash_set_sha256": "a" * 64,
        "sealed_sources": [],
        "gate_a": {"path": "gate-a.json", "sha256": "b" * 64, "managed_sources": []},
    }
    payload = contract()
    monkeypatch.setattr(gate, "_validate_current_seal", lambda *a, **k: seal_payload)
    monkeypatch.setattr(gate, "_reviewed_bundle", lambda *a, **k: b"bundle")
    monkeypatch.setattr(gate, "load_json", lambda *a, **k: payload)
    monkeypatch.setattr(gate, "_probe_ssh_target", lambda *a, **k: False)

    class Executor:
        Blocked = tx.Blocked
        @staticmethod
        def _bounded_process(*args, **kwargs):
            raise AssertionError("recovery bundle must not be sent")

    monkeypatch.setattr(gate, "_load_executor", lambda *a, **k: Executor)
    with pytest.raises(gate.RouteUnavailable):
        gate.recover_remote(
            REPO, SEAL, transaction_id, "status-reviewed-live",
            b"[giovanni-drive]\ntype = drive\n", runtime_evidence=runtime,
        )
    evidence = json.loads(runtime.read_text())
    assert evidence["status"] == "REMOTE_RECOVERY_ROUTE_BLOCKED"
    assert evidence["transaction_id"] == transaction_id
    assert evidence["write_count"] is None and evidence["vault_versions"] == []
    assert evidence["mutation_accounting"]["vault_data_create_only_write_count"] is None
    assert evidence["live_write_performed"] is None
    assert evidence["vault_write_ownership"] == "UNRESOLVED"
    assert evidence["send_attempted"] is False
    assert evidence["remote_transaction_exists"] is None
    assert evidence["recovery_action"] == "retry-route-probes-then-status-same-transaction"


def test_remote_recovery_protocol_is_versioned_hash_bound_and_explicit():
    assert "status-reviewed-live" in gate.REMOTE_BOOTSTRAP
    assert "resume-reviewed-live" in gate.REMOTE_BOOTSTRAP
    assert "--transaction-id" in gate.REMOTE_BOOTSTRAP
    assert "expected_hash" in gate.REMOTE_BOOTSTRAP
    with pytest.raises(SystemExit) as help_exit:
        gate.main(["--help"])
    assert help_exit.value.code == 0


def test_finalize_rejects_stale_source_and_execute_live_never_reaches_network(monkeypatch, tmp_path):
    seal = tmp_path / "seal.json"
    candidate = gate.preflight(REPO, seal, run_self_tests=True)
    digest = candidate["hash_set_sha256"]
    candidate["reviews"] = [
        {"reviewer": "stale-review-a", "status": "PASS", "hash_set_sha256": digest},
        {"reviewer": "stale-review-b", "status": "PASS", "hash_set_sha256": digest},
    ]
    gate.atomic_json(seal, candidate, mode=0o600)
    finalized = gate.finalize_seal(REPO, seal)
    finalized["sealed_sources"][0]["sha256"] = "0" * 64
    gate.atomic_json(seal, finalized, mode=0o600)
    called = False
    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network attempted")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    with pytest.raises(gate.GateBlocked, match="seal-source-drift"):
        gate.execute_live(REPO, seal)
    assert called is False


def test_transport_failure_persists_redacted_ambiguous_projection_without_retry(monkeypatch, tmp_path):
    runtime = tmp_path / "runtime.json"
    seal_payload = {
        "hash_set_sha256": "a" * 64,
        "sealed_sources": [],
        "gate_a": {"path": "gate-a.json", "sha256": "b" * 64, "managed_sources": []},
    }
    monkeypatch.setattr(gate, "_validate_current_seal", lambda *a, **k: seal_payload)
    monkeypatch.setattr(gate, "_reviewed_bundle", lambda *a, **k: b"bundle")
    monkeypatch.setattr(
        gate,
        "load_json",
        lambda *a, **k: {
            "live_coordinator": {
                "ssh_target": "ubuntu@10.13.1.13",
                "ssh_fallback_target": "ubuntu@10.100.100.3",
                "private_first": True,
                "route_policy": "direct-first",
                "fallback_after_direct_probe_failure_only": True,
                "forced_relay_policy": "preserve-approved-runtime-policy",
                "remote_deadline_seconds": 600,
            }
        },
    )

    class Executor:
        Blocked = tx.Blocked

        @staticmethod
        def _bounded_process_detailed(*args, **kwargs):
            return 0, b"", b""

        @staticmethod
        def _bounded_process(*args, **kwargs):
            command = args[0]
            assert any("timeout" in str(part) for part in command)
            assert any("20260722T235959Z-acde1234" in str(part) for part in command)
            assert kwargs["timeout_seconds"] > 600
            raise tx.Blocked("child-command-timeout")

    monkeypatch.setattr(gate, "_load_executor", lambda *a, **k: Executor)
    monkeypatch.setattr(gate, "_new_transaction_id", lambda: "20260722T235959Z-acde1234")
    with pytest.raises(gate.GateBlocked, match="remote-outcome-ambiguous"):
        gate.execute_live(REPO, SEAL, b"[giovanni-drive]\ntype = drive\n", runtime_evidence=runtime)
    projection = json.loads(runtime.read_text())
    assert projection == {
        "schema": "phase52-gate-b-transaction-evidence-v1",
        "transaction_id": "20260722T235959Z-acde1234",
        "status": "REMOTE_OUTCOME_AMBIGUOUS_BLOCKED",
        "write_count": None,
        "vault_versions": [],
        "mutation_accounting": {
            "atius-srv-2": {"candidate_data_plane_mutation": False, "authorized_vault_control_plane_mutation": False},
            "atius-srv-3": {"candidate_data_plane_mutation": False, "authorized_vault_control_plane_mutation": True},
            "vault_data_create_only_write_count": None,
        },
        "live_write_performed": None,
        "vault_write_ownership": "UNRESOLVED",
        "secret_material_present": False,
        "windows_install_performed": False,
        "network_listener_created": False,
        "automatic_retry_allowed": False,
        "recovery_action": "inspect-remote-transaction-before-any-retry",
        "send_attempted": True,
        "remote_transaction_exists": None,
        "coordinator_transport": {
            "policy": "direct-first",
            "direct_probe": "PASS",
            "fallback_probe": "NOT_RUN",
            "selected_route": "direct",
            "forced_relay_policy": "preserve-approved-runtime-policy",
        },
    }


def test_cli_without_explicit_execute_live_is_local_only(monkeypatch, tmp_path):
    called = False
    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network attempted")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    seal = tmp_path / "seal.json"
    assert gate.main(["preflight", "--repo", str(REPO), "--seal", str(seal), "--skip-self-tests"]) == 0
    assert called is False


def test_source_has_no_secret_transport_in_argv_env_or_output():
    executor = EXECUTOR.read_text()
    coordinator = COORDINATOR.read_text()
    assert "put_cas0_stdin" in executor
    assert "encoded_private_json" in executor
    assert "capture_output=True" not in coordinator
    assert "shell=True" not in executor + coordinator
    assert "os.environ[" not in executor + coordinator
    assert re.search(r"ssh.*stdin", coordinator, re.DOTALL)
    assert '"--network", "none"' in executor and '"--pull", "never"' in executor
    assert "created-field-cardinality-invalid" in executor
    assert "isolated-vault-restore-failed" in executor
    assert "ROLLBACK_BLOCKED_RETRY_REQUIRED" in executor
    assert "len(names)!=len(set(names))" in coordinator
    isolated = executor[executor.index("def isolated_restore_proof"):executor.index("def execute_reviewed_live")]
    assert '"ip", "link", "set", "lo", "up"' in isolated
    assert isolated.count('"vault", "server"') == 0  # argv is built from vault_bin, not a shell string
    assert isolated.count("process = start()") == 2
    assert "start_new_session=True" not in isolated
    assert "/v1/sys/storage/raft/configuration" not in isolated
    assert 'health_payload.get("sealed") is not True' in isolated
    assert 'health_payload.get("storage_type") != "raft"' in isolated
    assert "raft.db" in isolated
    assert "_fsync_file_and_parent(snapshot)" in executor
    assert "private_config.unlink()" in executor
    assert "_fsync_directory(private_config.parent)" in executor
    assert "start_new_session=True" not in executor
    assert "start_new_session=True" in coordinator
    assert "/var/lib/atius-vault-phase52" in executor


def test_remote_bootstrap_recomputes_canonical_hash_and_private_digest_ephemerally():
    bootstrap = gate.REMOTE_BOOTSTRAP
    assert '"sealed_sources","gate_a"' in bootstrap
    assert 'canonical={"sealed_sources":manifest["sealed_sources"],"gate_a":manifest["gate_a"]}' in bootstrap
    assert "canonical_hash" in bootstrap and "expected_hash" in bootstrap
    assert "while offset<len(data)" in bootstrap
    assert "hmac.compare_digest" in bootstrap
    assert "private_digest" in bootstrap
    assert "os.execve" not in bootstrap
    assert "subprocess.Popen" in bootstrap and "child.wait" in bootstrap
    assert "os.killpg" in bootstrap and "start_new_session=True" in bootstrap
    assert "signal.SIGTERM" in bootstrap and "signal.SIGKILL" in bootstrap
    assert "shutil.rmtree(root" in bootstrap
    assert "private_digest" not in json.dumps(gate.preflight(REPO, tmp_path := Path("/dev/shm/phase52-no-write-seal.json"), run_self_tests=False))
    tmp_path.unlink(missing_ok=True)


@pytest.mark.parametrize("child_exit", [0, 2])
def test_remote_bootstrap_supervisor_propagates_exit_and_removes_private_root(child_exit):
    bundle, digest = reviewed_bootstrap_fixture(
        f"raise SystemExit({child_exit})\n".encode()
    )
    before = set(Path("/dev/shm").glob("atius-phase52-reviewed-*"))
    result = subprocess.run(
        [
            sys.executable, "-c", gate.REMOTE_BOOTSTRAP,
            "execute-reviewed-live", digest, "20260722T120000Z-b10c4001",
            str(int(time.time()) + 60),
        ],
        input=bundle, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=10, check=False,
    )
    after = set(Path("/dev/shm").glob("atius-phase52-reviewed-*"))

    assert result.returncode == child_exit
    assert after - before == set()


def test_remote_bootstrap_term_stops_child_and_removes_private_root(tmp_path):
    pid_file = Path("/dev/shm") / f"phase52-bootstrap-child-{os.getpid()}.pid"
    pid_file.unlink(missing_ok=True)
    executor_source = (
        "import json,os,pathlib,subprocess,sys,time\n"
        "grandchild=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
        f"pathlib.Path({str(pid_file)!r}).write_text(json.dumps([os.getpid(),grandchild.pid]))\n"
        "time.sleep(30)\n"
    ).encode()
    bundle, digest = reviewed_bootstrap_fixture(executor_source)
    before = set(Path("/dev/shm").glob("atius-phase52-reviewed-*"))
    process = subprocess.Popen(
        [
            sys.executable, "-c", gate.REMOTE_BOOTSTRAP,
            "execute-reviewed-live", digest, "20260722T120000Z-b10c4002",
            str(int(time.time()) + 60),
        ],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdin is not None
    process.stdin.write(bundle); process.stdin.close()
    deadline = time.monotonic() + 5
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert pid_file.exists()
    child_pids = json.loads(pid_file.read_text())
    process.send_signal(signal.SIGTERM)
    process.wait(timeout=5)
    deadline = time.monotonic() + 2
    while any(Path(f"/proc/{pid}").exists() for pid in child_pids) and time.monotonic() < deadline:
        time.sleep(0.02)
    after = set(Path("/dev/shm").glob("atius-phase52-reviewed-*"))
    pid_file.unlink(missing_ok=True)

    assert all(not Path(f"/proc/{pid}").exists() for pid in child_pids)
    assert after - before == set()


def test_remote_bootstrap_unexpected_executor_exit_kills_grandchild_group():
    pid_file = Path("/dev/shm") / f"phase52-bootstrap-orphan-{os.getpid()}.pid"
    pid_file.unlink(missing_ok=True)
    executor_source = (
        "import pathlib,subprocess,sys\n"
        "grandchild=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
        f"pathlib.Path({str(pid_file)!r}).write_text(str(grandchild.pid))\n"
        "raise SystemExit(2)\n"
    ).encode()
    bundle, digest = reviewed_bootstrap_fixture(executor_source)
    before = set(Path("/dev/shm").glob("atius-phase52-reviewed-*"))
    result = subprocess.run(
        [
            sys.executable, "-c", gate.REMOTE_BOOTSTRAP,
            "execute-reviewed-live", digest, "20260722T120000Z-b10c4003",
            str(int(time.time()) + 60),
        ],
        input=bundle, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=10, check=False,
    )
    assert pid_file.exists()
    grandchild_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while Path(f"/proc/{grandchild_pid}").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    after = set(Path("/dev/shm").glob("atius-phase52-reviewed-*"))
    pid_file.unlink(missing_ok=True)

    assert result.returncode == 2
    assert not Path(f"/proc/{grandchild_pid}").exists()
    assert after - before == set()


def test_child_environment_is_allowlisted_and_silent_child_times_out(monkeypatch):
    monkeypatch.setenv("ATIUS_SECRET_SENTINEL", "must-not-inherit")
    assert "ATIUS_SECRET_SENTINEL" not in tx._safe_child_env()
    with pytest.raises(tx.Blocked, match="child-command-timeout"):
        tx._bounded_process(
            [sys.executable, "-c", "import time; time.sleep(5)"], b"", timeout_seconds=0.05,
        )


def test_internal_timeout_terminates_descendant_process_tree(tmp_path):
    pid_file = tmp_path / "grandchild.pid"
    script = (
        "import pathlib,subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid)); "
        "time.sleep(30)"
    )
    with pytest.raises(tx.Blocked, match="child-command-timeout"):
        tx._bounded_process([sys.executable, "-c", script], b"", timeout_seconds=0.2)
    grandchild = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while Path(f"/proc/{grandchild}").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not Path(f"/proc/{grandchild}").exists()


def test_successful_parent_exit_still_terminates_detached_descendant(tmp_path):
    pid_file = tmp_path / "detached-child.pid"
    script = (
        "import pathlib,subprocess,sys; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid))"
    )
    child_pid = None
    try:
        code, output = tx._bounded_process(
            [sys.executable, "-c", script], b"", timeout_seconds=2,
        )
        assert code == 0 and output == b""
        child_pid = int(pid_file.read_text())
        deadline = time.monotonic() + 2
        while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not Path(f"/proc/{child_pid}").exists()
    finally:
        if child_pid is not None and Path(f"/proc/{child_pid}").exists():
            os.kill(child_pid, signal.SIGKILL)


def test_bounded_helpers_serialize_subreaper_and_restore_process_state(tmp_path):
    def subreaper_state():
        state = tx.ctypes.c_int()
        libc = tx.ctypes.CDLL(None, use_errno=True)
        assert libc.prctl(37, tx.ctypes.byref(state), 0, 0, 0) == 0
        return state.value

    prior = subreaper_state()

    def run_one(index):
        pid_file = tmp_path / f"concurrent-{index}.pid"
        script = (
            "import pathlib,subprocess,sys; "
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],"
            "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
            f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid))"
        )
        assert tx._bounded_process([sys.executable, "-c", script], b"", timeout_seconds=2) == (0, b"")
        return int(pid_file.read_text())

    with ThreadPoolExecutor(max_workers=2) as pool:
        child_pids = list(pool.map(run_one, range(2)))
    assert subreaper_state() == prior
    assert all(not Path(f"/proc/{pid}").exists() for pid in child_pids)


def test_committed_runtime_evidence_is_initial_redacted_blocked_projection():
    evidence = json.loads(RUNTIME_EVIDENCE.read_text())
    assert evidence["status"] == "BLOCKED"
    assert evidence["live_write_performed"] is False
    assert evidence["write_count"] == 0
    assert evidence["vault_write_ownership"] == "NONE"
    assert evidence["send_attempted"] is False
    assert evidence["remote_transaction_exists"] is False
    assert evidence["vault_versions"] == []
    assert evidence["secret_material_present"] is False
    assert "mutation" not in evidence
