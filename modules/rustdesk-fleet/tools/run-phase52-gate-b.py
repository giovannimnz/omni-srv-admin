#!/usr/bin/env python3
"""Local seal gate and explicit live coordinator for Phase 52 Gate B."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from typing import Any


REPO_DEFAULT = Path(__file__).resolve().parents[3]
CONTRACT_REL = Path("modules/rustdesk-fleet/contracts/phase52-gate-b-transaction.json")
EXECUTOR_REL = Path("modules/rustdesk-fleet/tools/phase52-vault-transaction.py")
COORDINATOR_REL = Path("modules/rustdesk-fleet/tools/run-phase52-gate-b.py")
TEST_REL = Path("modules/rustdesk-fleet/tests/test_phase52_gate_b_transaction.py")
GATE_A_REL = Path("modules/rustdesk-fleet/evidence/phase52/gate-a-verification.json")
RUNTIME_EVIDENCE_REL = Path("modules/rustdesk-fleet/evidence/phase52/gate-b-transaction.json")
SEALED_RELS = [CONTRACT_REL, EXECUTOR_REL, COORDINATOR_REL, TEST_REL]
MAX_BUNDLE = 4 * 1024 * 1024
os.umask(0o077)
EXPECTED_CHECKS = {
    "status": "PASS",
    "fault_injection_cases": 70,
    "success_write_count": 7,
    "cas_conflict_owned_rollback_count": 3,
    "network_performed": False,
    "live_write_performed": False,
}
GATE_BLOCKED_OUTPUT_REASON = "gate-blocked"


def _checks_are_exact(checks: Any) -> bool:
    return (
        isinstance(checks, dict)
        and set(checks) == set(EXPECTED_CHECKS)
        and checks.get("status") == "PASS"
        and type(checks.get("fault_injection_cases")) is int
        and checks["fault_injection_cases"] == 70
        and type(checks.get("success_write_count")) is int
        and checks["success_write_count"] == 7
        and type(checks.get("cas_conflict_owned_rollback_count")) is int
        and checks["cas_conflict_owned_rollback_count"] == 3
        and checks.get("network_performed") is False
        and checks.get("live_write_performed") is False
    )


def _load_executor(repo: Path):
    path = repo / EXECUTOR_REL
    spec = importlib.util.spec_from_file_location("phase52_vault_transaction_runtime", path)
    if not spec or not spec.loader:
        raise GateBlocked("executor-import-failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GateBlocked(RuntimeError):
    pass


class RouteUnavailable(GateBlocked):
    def __init__(self, transport_evidence: dict[str, str]):
        super().__init__("ssh-direct-and-fallback-unreachable")
        self.transport_evidence = transport_evidence


def _reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GateBlocked("duplicate-json-key")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    except GateBlocked:
        raise
    except Exception as exc:
        raise GateBlocked("json-invalid") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise GateBlocked("atomic-json-write-failed")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _gate_a_projection(repo: Path) -> dict[str, Any]:
    path = repo / GATE_A_REL
    payload = load_json(path)
    if not isinstance(payload, dict) or payload.get("status") != "PASS":
        raise GateBlocked("gate-a-not-pass")
    rows = payload.get("managed_sources")
    if not isinstance(rows, list) or not rows:
        raise GateBlocked("gate-a-managed-sources-invalid")
    normalized = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise GateBlocked("gate-a-managed-sources-invalid")
        relative = row["path"]
        digest = row["sha256"]
        if not isinstance(relative, str) or relative in seen or not isinstance(digest, str):
            raise GateBlocked("gate-a-managed-sources-invalid")
        resolved = (repo / relative).resolve()
        try:
            resolved.relative_to(repo.resolve())
        except ValueError as exc:
            raise GateBlocked("gate-a-managed-source-outside-repo") from exc
        if not resolved.is_file() or resolved.is_symlink() or sha256_file(resolved) != digest:
            raise GateBlocked("gate-a-managed-source-drift")
        seen.add(relative)
        normalized.append({"path": relative, "sha256": digest})
    return {"path": GATE_A_REL.as_posix(), "sha256": sha256_file(path), "managed_sources": normalized}


def _sealed_sources(repo: Path) -> list[dict[str, str]]:
    rows = []
    for relative in SEALED_RELS:
        path = repo / relative
        if not path.is_file() or path.is_symlink():
            raise GateBlocked("sealed-source-missing")
        rows.append({"path": relative.as_posix(), "sha256": sha256_file(path)})
    return rows


def _hash_set(sealed_sources: list[dict[str, str]], gate_a: dict[str, Any]) -> str:
    canonical = {"sealed_sources": sealed_sources, "gate_a": gate_a}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _new_transaction_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + os.urandom(4).hex()


class _SelfTestBackend:
    """Offline model used only by preflight; it never starts a subprocess."""

    def __init__(self, tx, *, cas_conflict_at=None):
        self.tx = tx
        self.cas_conflict_at = cas_conflict_at
        self.puts = []
        self.deleted = []

    def create_backups(self, directory, contract):
        snapshot = directory / "raft.snapshot"
        bundle = directory / "control-plane.tar"
        snapshot.write_bytes(b"offline-snapshot-proof")
        bundle.write_bytes(b"offline-control-plane-proof")
        snapshot.chmod(0o600); bundle.chmod(0o600)
        manifest = {
            "schema": "phase52-gate-b-backup-manifest-v1",
            "raft_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            "control_plane_bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "secret_material_present": False,
        }
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (directory / "manifest.json").chmod(0o600)
        return {"raft_snapshot_valid": True, "control_plane_bundle_valid": True}

    def prove_isolated_snapshot_restore(self, directory, contract):
        return {"status": "PASS", "network_namespace": "isolated", "host_listener": False, "public_listener": False, "port_bindings": [], "integrity": "PASS"}

    def install_control_plane(self, directory, managed_sources):
        return None

    def restore_control_plane(self, directory):
        return None

    def metadata(self, vault_path):
        return {"current_version": 0, "oldest_version": 0, "versions": {}}

    def generate_values(self, contract, runtime_dir):
        values = {}
        password_index = 0
        for row in contract["writes"]:
            fields = {}
            for field in row["fields"]:
                if field == "permanent_password":
                    fields[field] = "R" + str(password_index) * 31
                    password_index += 1
                elif field == "rclone_conf":
                    fields[field] = "[giovanni-drive]\ntype = drive\noffline = fixture\n"
                else:
                    fields[field] = "Z" * 44
            values[row["id"]] = fields
        return values

    def put_cas0_stdin(self, operation, encoded_private_json):
        if self.cas_conflict_at == len(self.puts):
            raise self.tx.CasConflict("cas-conflict")
        self.puts.append(operation["id"])
        return {"version": 1}

    def soft_delete_exact_version(self, vault_path, version):
        self.deleted.append((vault_path, version))

    def verify_created_values(self, contract, expected_versions):
        return {"status": "PASS", "write_count": len(expected_versions), "secret_material_present": False}


def _offline_self_tests(repo: Path) -> dict[str, Any]:
    tx = _load_executor(repo)
    contract = tx.load_contract(repo / CONTRACT_REL)
    points = [
        "before-intent-fsync", "after-intent-fsync", "before-intent-rename", "after-intent-rename",
        "before-put", "after-put-ack", "before-version-fsync", "after-version-fsync",
        "before-version-rename", "after-version-rename",
    ]
    fault_count = 0
    with tempfile.TemporaryDirectory(prefix="phase52-gate-b-preflight-", dir="/dev/shm") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        for index in range(7):
            for point in points:
                case_root = root / f"case-{index}-{point}"
                case_root.mkdir(mode=0o700)
                backend = _SelfTestBackend(tx)
                try:
                    tx.run_transaction(
                        contract, backend, case_root, f"20260722T1200{index:02d}Z-{fault_count:08x}",
                        fault=tx.FaultInjector({f"{index}:{point}"}), require_root=False,
                    )
                except tx.InjectedCrash:
                    fault_count += 1
                else:
                    raise GateBlocked("fault-injection-did-not-trigger")
        success_root = root / "success"
        success_root.mkdir(mode=0o700)
        success = tx.run_transaction(
            contract, _SelfTestBackend(tx), success_root, "20260722T125959Z-abcdef12", require_root=False,
        )
        if success.get("status") != "PASS" or success.get("write_count") != 7:
            raise GateBlocked("offline-success-model-failed")
        conflict_root = root / "conflict"
        conflict_root.mkdir(mode=0o700)
        conflict_backend = _SelfTestBackend(tx, cas_conflict_at=3)
        rolled = tx.run_transaction(
            contract, conflict_backend, conflict_root, "20260722T125958Z-abcdef13", require_root=False,
        )
        if rolled.get("status") != "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION" or len(conflict_backend.deleted) != 3:
            raise GateBlocked("offline-rollback-model-failed")
    return {
        "status": "PASS",
        "fault_injection_cases": fault_count,
        "success_write_count": 7,
        "cas_conflict_owned_rollback_count": 3,
        "network_performed": False,
        "live_write_performed": False,
    }


def preflight(repo: Path, seal: Path, *, run_self_tests: bool = True) -> dict[str, Any]:
    repo = repo.resolve()
    gate_a = _gate_a_projection(repo)
    sources = _sealed_sources(repo)
    tx = _load_executor(repo)
    tx.load_contract(repo / CONTRACT_REL)
    checks = _offline_self_tests(repo) if run_self_tests else {
        "status": "SKIPPED_BY_EXPLICIT_LOCAL_TEST_FLAG",
        "fault_injection_cases": 0,
        "network_performed": False,
        "live_write_performed": False,
    }
    payload = {
        "schema": "phase52-gate-b-pre-live-seal-v1",
        "phase": 52,
        "gate": "B",
        "status": "PENDING",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sealed_sources": sources,
        "gate_a": gate_a,
        "hash_set_sha256": _hash_set(sources, gate_a),
        "checks": checks,
        "reviews": [],
        "sealed_at": None,
        "network_performed": False,
        "ssh_performed": False,
        "live_write_performed": False,
        "secret_material_present": False,
    }
    atomic_json(seal, payload, mode=0o600)
    return payload


def _validate_current_seal(repo: Path, seal: Path, *, require_pass: bool) -> dict[str, Any]:
    payload = load_json(seal)
    exact_keys = {"schema","phase","gate","status","generated_at","sealed_sources","gate_a","hash_set_sha256","checks","reviews","sealed_at","network_performed","ssh_performed","live_write_performed","secret_material_present"}
    if not isinstance(payload, dict) or set(payload) != exact_keys or payload.get("schema") != "phase52-gate-b-pre-live-seal-v1" or payload.get("phase") != 52 or payload.get("gate") != "B":
        raise GateBlocked("seal-invalid")
    if require_pass and payload.get("status") != "PASS":
        raise GateBlocked("seal-not-pass")
    if require_pass:
        checks = payload.get("checks")
        reviews = payload.get("reviews")
        digest = payload.get("hash_set_sha256")
        if not _checks_are_exact(checks):
            raise GateBlocked("seal-checks-not-pass")
        if checks.get("network_performed") is not False or checks.get("live_write_performed") is not False:
            raise GateBlocked("seal-checks-not-pass")
        if not isinstance(reviews, list) or len(reviews) != 2 or len({r.get("reviewer") for r in reviews if isinstance(r,dict)}) != 2 or any(not isinstance(r,dict) or set(r)!={"reviewer","status","hash_set_sha256"} or r.get("status")!="PASS" or r.get("hash_set_sha256")!=digest for r in reviews):
            raise GateBlocked("seal-reviews-invalid")
        if not isinstance(payload.get("sealed_at"), str) or not payload["sealed_at"].endswith("Z"):
            raise GateBlocked("seal-timestamp-invalid")
        if any(payload.get(key) is not False for key in ("network_performed","ssh_performed","live_write_performed","secret_material_present")):
            raise GateBlocked("seal-flags-invalid")
    current_sources = _sealed_sources(repo)
    if payload.get("sealed_sources") != current_sources:
        raise GateBlocked("seal-source-drift")
    current_gate_a = _gate_a_projection(repo)
    if payload.get("gate_a") != current_gate_a:
        raise GateBlocked("seal-gate-a-drift")
    digest = _hash_set(current_sources, current_gate_a)
    if payload.get("hash_set_sha256") != digest:
        raise GateBlocked("seal-hash-set-drift")
    return payload


def finalize_seal(repo: Path, seal: Path) -> dict[str, Any]:
    repo = repo.resolve()
    payload = _validate_current_seal(repo, seal, require_pass=False)
    if payload.get("status") != "PENDING":
        raise GateBlocked("seal-not-pending")
    reviews = payload.get("reviews")
    digest = payload["hash_set_sha256"]
    checks = payload.get("checks")
    if not _checks_are_exact(checks):
        raise GateBlocked("seal-checks-not-pass")
    if (
        not isinstance(reviews, list)
        or len(reviews) != 2
        or len({row.get("reviewer") for row in reviews if isinstance(row, dict)}) != 2
        or any(
            not isinstance(row, dict)
            or set(row) != {"reviewer", "status", "hash_set_sha256"}
            or not isinstance(row["reviewer"], str)
            or not row["reviewer"]
            or row["status"] != "PASS"
            or row["hash_set_sha256"] != digest
            for row in reviews
        )
    ):
        raise GateBlocked("two-independent-pass-reviews-required")
    payload["status"] = "PASS"
    payload["sealed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    atomic_json(seal, payload, mode=0o600)
    return _validate_current_seal(repo, seal, require_pass=True)


def _reviewed_bundle(repo: Path, seal_payload: dict[str, Any], rclone_config: bytes) -> bytes:
    if not rclone_config or len(rclone_config) > 131072:
        raise GateBlocked("rclone-private-input-invalid")
    try:
        config_text = rclone_config.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateBlocked("rclone-private-input-invalid") from exc
    if not config_text.startswith("[giovanni-drive]\n") or "\n[" in config_text[1:]:
        raise GateBlocked("rclone-private-input-invalid")
    paths = [Path(row["path"]) for row in seal_payload["sealed_sources"]]
    paths.extend(Path(row["path"]) for row in seal_payload["gate_a"]["managed_sources"])
    paths.append(Path(seal_payload["gate_a"]["path"]))
    manifest = {
        "schema": "phase52-reviewed-root-bundle-v1",
        "hash_set_sha256": seal_payload["hash_set_sha256"],
        "sealed_sources": seal_payload["sealed_sources"],
        "gate_a": seal_payload["gate_a"],
        "files": sorted(
            ({"path": path.as_posix(), "sha256": sha256_file(repo / path)} for path in set(paths)),
            key=lambda row: row["path"],
        ),
        "secret_material_present": False,
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        manifest_raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest_raw); info.mode = 0o600; info.uid = 0; info.gid = 0; info.mtime = 0
        archive.addfile(info, io.BytesIO(manifest_raw))
        for row in manifest["files"]:
            raw = (repo / row["path"]).read_bytes()
            info = tarfile.TarInfo(row["path"])
            info.size = len(raw); info.mode = 0o600; info.uid = 0; info.gid = 0; info.mtime = 0
            archive.addfile(info, io.BytesIO(raw))
        info = tarfile.TarInfo("private/rclone.conf")
        info.size = len(rclone_config); info.mode = 0o600; info.uid = 0; info.gid = 0; info.mtime = 0
        archive.addfile(info, io.BytesIO(rclone_config))
    raw = buffer.getvalue()
    if not raw or len(raw) > MAX_BUNDLE:
        raise GateBlocked("reviewed-bundle-size-invalid")
    return raw


REMOTE_BOOTSTRAP = r'''
import hashlib,hmac,io,json,os,pathlib,re,shutil,signal,stat,subprocess,sys,tarfile,tempfile,time
def pairs(items):
 result={}
 for key,value in items:
  if key in result: raise SystemExit(23)
  result[key]=value
 return result
raw=sys.stdin.buffer.read(4194305)
if not raw or len(raw)>4194304: raise SystemExit(20)
operation=sys.argv[1]
expected_hash=sys.argv[2]
transaction_id=sys.argv[3]
deadline_epoch=int(sys.argv[4])
if operation not in {"execute-reviewed-live","status-reviewed-live","resume-reviewed-live"}: raise SystemExit(28)
if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}",transaction_id): raise SystemExit(26)
if time.time()>=deadline_epoch: raise SystemExit(27)
root=pathlib.Path(tempfile.mkdtemp(prefix="atius-phase52-reviewed-",dir="/dev/shm")); root.chmod(0o700)
child=None
child_group_stopped=False
def stop_group():
 global child_group_stopped
 if child is None or child_group_stopped: return
 child_group_stopped=True
 pgid=child.pid
 try: os.killpg(pgid,signal.SIGTERM)
 except ProcessLookupError: pass
 deadline=time.monotonic()+2
 while time.monotonic()<deadline:
  child.poll()
  try: os.killpg(pgid,0)
  except ProcessLookupError: break
  time.sleep(0.02)
 try: os.killpg(pgid,signal.SIGKILL)
 except ProcessLookupError: pass
 if child.poll() is None:
  try: child.wait(timeout=2)
  except subprocess.TimeoutExpired:
   try: os.killpg(pgid,signal.SIGKILL)
   except ProcessLookupError: pass
   child.wait(timeout=2)
def stop(signum,frame):
 if child is not None:
  try: os.killpg(child.pid,signal.SIGTERM)
  except ProcessLookupError: pass
 raise SystemExit(128+signum)
signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop); signal.signal(signal.SIGHUP,stop)
try:
 with tarfile.open(fileobj=io.BytesIO(raw),mode="r:") as archive:
  members=archive.getmembers()
  names=[m.name for m in members]
  if len(names)!=len(set(names)) or any(m.issym() or m.islnk() or not m.isfile() or pathlib.PurePosixPath(m.name).is_absolute() or ".." in pathlib.PurePosixPath(m.name).parts or m.size<0 or m.size>1048576 for m in members): raise SystemExit(21)
  manifest_file=archive.extractfile("manifest.json")
  if manifest_file is None: raise SystemExit(23)
  manifest=json.loads(manifest_file.read(),object_pairs_hook=pairs)
  if set(manifest)!={"schema","hash_set_sha256","sealed_sources","gate_a","files","secret_material_present"} or manifest["schema"]!="phase52-reviewed-root-bundle-v1" or manifest["secret_material_present"] is not False: raise SystemExit(23)
  canonical={"sealed_sources":manifest["sealed_sources"],"gate_a":manifest["gate_a"]}
  canonical_hash=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(",",":")).encode()).hexdigest()
  if manifest["hash_set_sha256"]!=canonical_hash or canonical_hash!=expected_hash: raise SystemExit(24)
  sealed=manifest["sealed_sources"]
  gate_a=manifest["gate_a"]
  if not isinstance(sealed,list) or not isinstance(gate_a,dict) or set(gate_a)!={"path","sha256","managed_sources"} or not isinstance(gate_a["managed_sources"],list): raise SystemExit(23)
  projected=sealed+gate_a["managed_sources"]+[{"path":gate_a["path"],"sha256":gate_a["sha256"]}]
  if any(not isinstance(row,dict) or set(row)!={"path","sha256"} or not isinstance(row["path"],str) or not re.fullmatch(r"[a-f0-9]{64}",row["sha256"]) for row in projected): raise SystemExit(23)
  projected_map={row["path"]:row["sha256"] for row in projected}
  if len(projected_map)!=len(projected): raise SystemExit(23)
  file_map={row["path"]:row["sha256"] for row in manifest["files"] if isinstance(row,dict) and set(row)=={"path","sha256"}}
  if file_map!=projected_map or len(file_map)!=len(manifest["files"]): raise SystemExit(23)
  expected={"manifest.json","private/rclone.conf"}|{row["path"] for row in manifest["files"] if isinstance(row,dict) and set(row)=={"path","sha256"}}
  if set(names)!=expected or len(expected)!=len(names): raise SystemExit(23)
  private_digest=None
  for member in members:
   target=root/member.name; target.parent.mkdir(parents=True,exist_ok=True)
   source=archive.extractfile(member)
   if source is None: raise SystemExit(25)
   data=source.read(1048577)
   if len(data)!=member.size: raise SystemExit(25)
   if member.name=="private/rclone.conf": private_digest=hashlib.sha256(data).digest()
   fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
   try:
    offset=0
    while offset<len(data):
     written=os.write(fd,data[offset:])
     if written<=0: raise SystemExit(25)
     offset+=written
    os.fsync(fd)
   finally: os.close(fd)
 for row in manifest["files"]:
  path=root/row["path"]
  if hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]: raise SystemExit(22)
 if private_digest is None or not hmac.compare_digest(private_digest,hashlib.sha256((root/"private/rclone.conf").read_bytes()).digest()): raise SystemExit(22)
 gate_a_payload=json.loads((root/gate_a["path"]).read_text(),object_pairs_hook=pairs)
 if not isinstance(gate_a_payload,dict) or gate_a_payload.get("status")!="PASS" or gate_a_payload.get("managed_sources")!=gate_a["managed_sources"]: raise SystemExit(23)
 if time.time()>=deadline_epoch: raise SystemExit(27)
 executor=root/"modules/rustdesk-fleet/tools/phase52-vault-transaction.py"
 child_env={key:value for key in ("PATH","HOME","USER","LOGNAME","LANG","LC_ALL","XDG_RUNTIME_DIR") if (value:=os.getenv(key))}
 child=subprocess.Popen([sys.executable,str(executor),operation,"--bundle-root",str(root),"--transaction-id",transaction_id,"--expected-hash",expected_hash,"--deadline-epoch",str(deadline_epoch)],env=child_env,stdin=subprocess.DEVNULL,close_fds=True,start_new_session=True)
 raise SystemExit(child.wait())
finally:
 stop_group()
 for _ in range(2):
  try:
   if root.exists() or root.is_symlink(): shutil.rmtree(root)
  except OSError: pass
 if root.exists() or root.is_symlink(): raise SystemExit(29)
'''


def _ambiguous_projection(
    transaction_id: str, transport_evidence: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "phase52-gate-b-transaction-evidence-v1",
        "transaction_id": transaction_id,
        "status": "REMOTE_OUTCOME_AMBIGUOUS_BLOCKED",
        "write_count": None,
        "vault_versions": [],
        "mutation_accounting": {
            "atius-srv-2": {
                "candidate_data_plane_mutation": False,
                "authorized_vault_control_plane_mutation": False,
            },
            "atius-srv-3": {
                "candidate_data_plane_mutation": False,
                "authorized_vault_control_plane_mutation": True,
            },
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
        "coordinator_transport": transport_evidence or {
            "policy": "direct-first", "direct_probe": "UNKNOWN",
            "fallback_probe": "UNKNOWN", "selected_route": "none",
            "forced_relay_policy": "preserve-approved-runtime-policy",
        },
    }


def _route_blocked_projection(
    transport_evidence: dict[str, str], *, recovery_transaction_id: str | None = None,
) -> dict[str, Any]:
    recovery = recovery_transaction_id is not None
    return {
        "schema": "phase52-gate-b-transaction-evidence-v1",
        "transaction_id": recovery_transaction_id,
        "status": "REMOTE_RECOVERY_ROUTE_BLOCKED" if recovery else "REMOTE_ROUTE_BLOCKED",
        "write_count": None if recovery else 0,
        "vault_versions": [],
        "mutation_accounting": {
            "atius-srv-2": {
                "candidate_data_plane_mutation": False,
                "authorized_vault_control_plane_mutation": False,
            },
            "atius-srv-3": {
                "candidate_data_plane_mutation": False,
                "authorized_vault_control_plane_mutation": True,
            },
            "vault_data_create_only_write_count": None if recovery else 0,
        },
        "live_write_performed": None if recovery else False,
        "vault_write_ownership": "UNRESOLVED" if recovery else "NONE",
        "secret_material_present": False,
        "windows_install_performed": False,
        "network_listener_created": False,
        "automatic_retry_allowed": False,
        "recovery_action": (
            "retry-route-probes-then-status-same-transaction"
            if recovery else "retry-route-probes-before-new-transaction"
        ),
        "send_attempted": False,
        "remote_transaction_exists": None if recovery else False,
        "coordinator_transport": transport_evidence,
    }


def _ssh_base(target: str) -> list[str]:
    return [
        "ssh", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
        "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3", target,
    ]


def _probe_ssh_target(target: str, coordinator: dict[str, Any], tx_module: Any) -> bool:
    if not isinstance(target, str) or not re.fullmatch(r"ubuntu@[0-9.]+", target):
        raise GateBlocked("ssh-target-invalid")
    try:
        code, stdout, stderr = tx_module._bounded_process_detailed(
            _ssh_base(target) + ["true"], b"", max_stdout=1024, max_stderr=4096,
            timeout_seconds=15,
        )
    except tx_module.Blocked:
        return False
    return code == 0 and stdout == b"" and stderr == b""


def _select_ssh_target(
    coordinator: dict[str, Any], tx_module: Any,
) -> tuple[str, dict[str, str]]:
    if (
        coordinator.get("route_policy") != "direct-first"
        or coordinator.get("private_first") is not True
        or coordinator.get("fallback_after_direct_probe_failure_only") is not True
        or coordinator.get("forced_relay_policy") != "preserve-approved-runtime-policy"
    ):
        raise GateBlocked("ssh-route-policy-invalid")
    direct = coordinator.get("ssh_target")
    fallback = coordinator.get("ssh_fallback_target")
    if _probe_ssh_target(direct, coordinator, tx_module):
        return direct, {
            "policy": "direct-first", "direct_probe": "PASS",
            "fallback_probe": "NOT_RUN", "selected_route": "direct",
            "forced_relay_policy": "preserve-approved-runtime-policy",
        }
    if _probe_ssh_target(fallback, coordinator, tx_module):
        return fallback, {
            "policy": "direct-first", "direct_probe": "FAILED",
            "fallback_probe": "PASS", "selected_route": "fallback",
            "forced_relay_policy": "preserve-approved-runtime-policy",
        }
    raise RouteUnavailable({
        "policy": "direct-first", "direct_probe": "FAILED",
        "fallback_probe": "FAILED", "selected_route": "none",
        "forced_relay_policy": "preserve-approved-runtime-policy",
    })


def _validate_remote_result(
    contract: dict[str, Any], result: Any, transaction_id: str,
) -> dict[str, Any]:
    exact_result = {
        "schema", "transaction_id", "status", "write_count", "vault_versions",
        "mutation_accounting", "live_write_performed", "vault_write_ownership",
        "secret_material_present", "windows_install_performed", "network_listener_created",
    }
    expected_versions = [
        {"id": row["id"], "vault_path": row["vault_path"], "version": 1}
        for row in contract["writes"]
    ]
    if (
        not isinstance(result, dict)
        or set(result) != exact_result
        or result.get("schema") != "phase52-gate-b-transaction-evidence-v1"
        or result.get("transaction_id") != transaction_id
        or result.get("status") != "PASS"
        or type(result.get("write_count")) is not int
        or result["write_count"] != 7
        or result.get("vault_versions") != expected_versions
        or any(type(row.get("version")) is not int for row in result.get("vault_versions", []) if isinstance(row, dict))
        or not _mutation_accounting_is_exact(result.get("mutation_accounting"), 7)
        or result.get("live_write_performed") is not True
        or result.get("vault_write_ownership") != "FSYNCED_WAL_ACK"
        or any(
            result.get(key) is not False
            for key in ("secret_material_present", "windows_install_performed", "network_listener_created")
        )
    ):
        raise GateBlocked("remote-result-invalid")
    return result


def _mutation_accounting_is_exact(value: Any, write_count: int) -> bool:
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


def _recovery_semantics_are_exact(
    contract: dict[str, Any], result: dict[str, Any],
) -> bool:
    status = result["status"]
    if status not in set(contract.get("states", [])):
        return False
    count = result["write_count"]
    live = result["live_write_performed"]
    ownership = result["vault_write_ownership"]
    no_write_states = {
        "PRE_BACKUP", "BACKUP_PROVED", "CONTROL_PLANE_INSTALLING",
        "CONTROL_PLANE_INSTALLED", "CONTROL_PLANE_RESTORED_BEFORE_REINSTALL",
        "CONTROL_PLANE_REINSTALLED", "METADATA_PROVED_PRISTINE", "BLOCKED",
        "PRE_BACKUP_NO_MUTATION_TERMINAL",
    }
    if status in no_write_states:
        return count == 0 and live is False and ownership == "NONE"
    if status == "CREATING":
        return (
            (count == 0 and live is False and ownership == "NONE")
            or (1 <= count <= 7 and live is True and ownership == "FSYNCED_WAL_ACK")
            or (0 <= count <= 6 and live is None and ownership == "UNRESOLVED")
        )
    if status in {
        "OWNERSHIP_AMBIGUOUS_BLOCKED",
        "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY",
    }:
        return 0 <= count <= 6 and live is None and ownership == "UNRESOLVED"
    if status == "ROLLING_BACK":
        return (
            (count == 0 and live is False and ownership == "NONE")
            or (1 <= count <= 7 and live is True and ownership == "FSYNCED_WAL_ACK")
        )
    if status == "ROLLBACK_BLOCKED_RETRY_REQUIRED":
        return (
            (count == 0 and live is False and ownership == "NONE")
            or (1 <= count <= 7 and live is True and ownership == "FSYNCED_WAL_ACK")
        )
    if status == "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION":
        return 1 <= count <= 7 and live is True and ownership == "FSYNCED_WAL_ACK"
    return False


def _validate_recovery_result(
    contract: dict[str, Any], result: Any, transaction_id: str,
) -> dict[str, Any]:
    if isinstance(result, dict) and result.get("status") == "PASS":
        return _validate_remote_result(contract, result, transaction_id)
    exact = {
        "schema", "transaction_id", "status", "write_count", "vault_versions",
        "mutation_accounting", "live_write_performed", "vault_write_ownership",
        "secret_material_present", "windows_install_performed", "network_listener_created",
    }
    allowed_statuses = {
        "PRE_BACKUP", "BACKUP_PROVED", "CONTROL_PLANE_INSTALLING",
        "CONTROL_PLANE_INSTALLED", "CONTROL_PLANE_RESTORED_BEFORE_REINSTALL",
        "CONTROL_PLANE_REINSTALLED", "METADATA_PROVED_PRISTINE",
        "BLOCKED", "PRE_BACKUP_NO_MUTATION_TERMINAL", "CREATING", "ROLLING_BACK", "ROLLBACK_BLOCKED_RETRY_REQUIRED",
        "ROLLED_BACK_REQUIRES_MANUAL_REAUTHORIZATION", "OWNERSHIP_AMBIGUOUS_BLOCKED",
        "OWNERSHIP_AMBIGUOUS_CONTROL_PLANE_RESTORE_RETRY",
    }
    if (
        not isinstance(result, dict) or set(result) != exact
        or result.get("schema") != "phase52-gate-b-transaction-evidence-v1"
        or result.get("transaction_id") != transaction_id
        or result.get("status") not in allowed_statuses
        or not isinstance(result.get("vault_versions"), list)
        or type(result.get("write_count")) is not int
        or result["write_count"] != len(result["vault_versions"])
        or result.get("secret_material_present") is not False
        or result.get("windows_install_performed") is not False
        or result.get("network_listener_created") is not False
    ):
        raise GateBlocked("remote-recovery-result-invalid")
    expected_prefix = [
        {"id": row["id"], "vault_path": row["vault_path"], "version": 1}
        for row in contract["writes"][: len(result["vault_versions"])]
    ]
    if result["vault_versions"] != expected_prefix:
        raise GateBlocked("remote-recovery-result-invalid")
    if not _mutation_accounting_is_exact(result.get("mutation_accounting"), len(expected_prefix)):
        raise GateBlocked("remote-recovery-result-invalid")
    if not _recovery_semantics_are_exact(contract, result):
        raise GateBlocked("remote-recovery-result-invalid")
    return result


def recover_remote(
    repo: Path, seal: Path, transaction_id: str, operation: str,
    rclone_config: bytes | None = None, *, runtime_evidence: Path | None = None,
) -> dict[str, Any]:
    if operation not in {"status-reviewed-live", "resume-reviewed-live"}:
        raise GateBlocked("remote-recovery-operation-invalid")
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", transaction_id):
        raise GateBlocked("transaction-id-invalid")
    repo = repo.resolve()
    seal_payload = _validate_current_seal(repo, seal, require_pass=True)
    if rclone_config is None:
        raise GateBlocked("rclone-private-stdin-required")
    bundle = _reviewed_bundle(repo, seal_payload, rclone_config)
    contract = load_json(repo / CONTRACT_REL)
    coordinator = contract["live_coordinator"]
    tx = _load_executor(repo)
    evidence_path = runtime_evidence or (repo / RUNTIME_EVIDENCE_REL)
    try:
        target, transport_evidence = _select_ssh_target(coordinator, tx)
    except RouteUnavailable as exc:
        atomic_json(
            evidence_path,
            _route_blocked_projection(
                exc.transport_evidence, recovery_transaction_id=transaction_id,
            ),
            mode=0o600,
        )
        raise
    deadline_seconds = coordinator.get("remote_deadline_seconds")
    if deadline_seconds != 600 or coordinator.get("recovery_protocol") != "phase52-reviewed-recovery-v1":
        raise GateBlocked("remote-recovery-policy-invalid")
    deadline_epoch = int(time.time()) + deadline_seconds
    remote_argv = [
        "sudo", "-n", "timeout", "--signal=TERM", "--kill-after=5s", str(deadline_seconds),
        "python3", "-c", REMOTE_BOOTSTRAP, operation, seal_payload["hash_set_sha256"],
        transaction_id, str(deadline_epoch),
    ]
    command = _ssh_base(target) + [" ".join(shlex.quote(part) for part in remote_argv)]
    try:
        _, output = tx._bounded_process(
            command, bundle, max_stdout=65536, max_stderr=4096,
            timeout_seconds=deadline_seconds + 15,
        )
        result = _validate_recovery_result(
            contract, tx.strict_json_bytes(output), transaction_id,
        )
    except (tx.Blocked, GateBlocked) as exc:
        atomic_json(evidence_path, _ambiguous_projection(transaction_id, transport_evidence), mode=0o600)
        raise GateBlocked("remote-recovery-outcome-ambiguous") from exc
    persisted = dict(result)
    persisted["coordinator_transport"] = transport_evidence
    atomic_json(evidence_path, persisted, mode=0o600)
    return result


def execute_live(
    repo: Path,
    seal: Path,
    rclone_config: bytes | None = None,
    *,
    runtime_evidence: Path | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    payload = _validate_current_seal(repo, seal, require_pass=True)
    if rclone_config is None:
        raise GateBlocked("rclone-private-stdin-required")
    bundle = _reviewed_bundle(repo, payload, rclone_config)
    contract = load_json(repo / CONTRACT_REL)
    coordinator = contract["live_coordinator"]
    tx = _load_executor(repo)
    deadline_seconds = coordinator.get("remote_deadline_seconds")
    if deadline_seconds != 600:
        raise GateBlocked("remote-deadline-policy-invalid")
    transaction_id = _new_transaction_id()
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}", transaction_id):
        raise GateBlocked("transaction-id-invalid")
    evidence_path = runtime_evidence or (repo / RUNTIME_EVIDENCE_REL)
    try:
        target, transport_evidence = _select_ssh_target(coordinator, tx)
    except RouteUnavailable as exc:
        atomic_json(
            evidence_path,
            _route_blocked_projection(exc.transport_evidence),
            mode=0o600,
        )
        raise
    deadline_epoch = int(time.time()) + deadline_seconds
    remote_argv = [
        "sudo", "-n", "timeout", "--signal=TERM", "--kill-after=5s", str(deadline_seconds),
        "python3", "-c", REMOTE_BOOTSTRAP, "execute-reviewed-live",
        payload["hash_set_sha256"], transaction_id,
        str(deadline_epoch),
    ]
    remote_command = " ".join(shlex.quote(part) for part in remote_argv)
    command = _ssh_base(target) + [remote_command]
    # ssh receives only the reviewed, value-free source bundle on stdin.  The
    # root executor generates secrets later and never returns them.
    try:
        _, output = tx._bounded_process(
            command,
            bundle,
            max_stdout=65536,
            max_stderr=4096,
            timeout_seconds=deadline_seconds + 15,
        )
    except tx.Blocked as exc:
        atomic_json(evidence_path, _ambiguous_projection(transaction_id, transport_evidence), mode=0o600)
        raise GateBlocked("remote-outcome-ambiguous") from exc
    try:
        result = tx.strict_json_bytes(output)
        result = _validate_remote_result(contract, result, transaction_id)
        valid = True
    except (tx.Blocked, GateBlocked):
        valid = False
        result = None
    if not valid:
        atomic_json(evidence_path, _ambiguous_projection(transaction_id, transport_evidence), mode=0o600)
        raise GateBlocked("remote-outcome-ambiguous")
    assert isinstance(result, dict)
    persisted = dict(result)
    persisted["coordinator_transport"] = transport_evidence
    atomic_json(evidence_path, persisted, mode=0o600)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--status-remote", metavar="TRANSACTION_ID")
    parser.add_argument("--resume-remote", metavar="TRANSACTION_ID")
    parser.add_argument("--repo", type=Path, default=REPO_DEFAULT)
    parser.add_argument("--seal", type=Path, default=REPO_DEFAULT / "modules/rustdesk-fleet/evidence/phase52/gate-b-pre-live-verification.json")
    sub = parser.add_subparsers(dest="command")
    pre = sub.add_parser("preflight")
    pre.add_argument("--repo", type=Path, default=REPO_DEFAULT)
    pre.add_argument("--seal", type=Path, required=True)
    pre.add_argument("--skip-self-tests", action="store_true")
    final = sub.add_parser("finalize-seal")
    final.add_argument("--repo", type=Path, default=REPO_DEFAULT)
    final.add_argument("--seal", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(args.repo, args.seal, run_self_tests=not args.skip_self_tests)
        elif args.command == "finalize-seal":
            result = finalize_seal(args.repo, args.seal)
        elif args.execute_live and args.command is None and not args.status_remote and not args.resume_remote:
            private_input = sys.stdin.buffer.read(131073)
            if len(private_input) > 131072:
                raise GateBlocked("rclone-private-input-too-large")
            result = execute_live(args.repo, args.seal, private_input)
        elif (args.status_remote or args.resume_remote) and args.command is None and not args.execute_live:
            if args.status_remote and args.resume_remote:
                raise GateBlocked("one-recovery-operation-required")
            private_input = sys.stdin.buffer.read(131073)
            if len(private_input) > 131072:
                raise GateBlocked("rclone-private-input-too-large")
            result = recover_remote(
                args.repo,
                args.seal,
                args.status_remote or args.resume_remote,
                "status-reviewed-live" if args.status_remote else "resume-reviewed-live",
                private_input,
            )
        else:
            raise GateBlocked("explicit-operation-required")
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except GateBlocked:
        print(
            json.dumps(
                {"status": "BLOCKED", "reason": GATE_BLOCKED_OUTPUT_REASON},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
