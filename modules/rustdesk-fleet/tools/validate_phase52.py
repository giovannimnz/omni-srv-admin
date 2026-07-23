#!/usr/bin/env python3
"""Fail-closed Phase 52 RustDesk supply/capacity/recovery validator."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import importlib.util
import json
import os
import re
import selectors
import secrets
import shlex
import shutil
import signal
import sqlite3
import stat
import struct
import subprocess
import sys
import tempfile
import tarfile
import urllib.error
import urllib.request
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPLY_CONTRACT = Path("modules/rustdesk-fleet/contracts/supply-chain.json")
SUPPLY_OBSERVATION = Path("modules/rustdesk-fleet/evidence/phase52/supply-observation.json")
CAPACITY_POLICY = Path("modules/rustdesk-fleet/contracts/capacity-policy.json")
PLACEMENT_DECISION = Path("modules/rustdesk-fleet/contracts/placement-decision.json")
CAPACITY_PROPOSAL = Path("modules/rustdesk-fleet/evidence/phase52/capacity-proposal.json")
CAPACITY_SUMMARY = Path("modules/rustdesk-fleet/evidence/phase52/capacity-summary.json")
FULL_GATE_SUMMARY = Path("modules/rustdesk-fleet/evidence/phase52/full-gate-summary.json")
INTEGRATED_GATE = Path("modules/rustdesk-fleet/evidence/phase52/integrated-gate.json")
LEDGER = Path("modules/rustdesk-fleet/evidence/ledger.json")
SECRET_ROLES = Path("modules/rustdesk-fleet/contracts/secret-roles.json")
HORISTIC_REVIEW = Path(
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/"
    "52-HORISTIC-TOPOLOGY-IMPACT-REVIEW.md"
)
OPERATIONAL_DECISIONS = Path(
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/"
    "52-OPERATIONAL-DECISIONS.md"
)
PHASE52_DIR = Path(
    ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement"
)
PHASE52_REPORT_JSON = PHASE52_DIR / "52-GATE-REPORT.json"
PHASE52_REPORT_MARKDOWN = PHASE52_DIR / "52-GATE-REPORT.md"
PHASE53_TOPOLOGY_REVIEW = PHASE52_DIR / "52-PHASE53-TOPOLOGY-REVIEW.md"
PHASE48_BASELINE = Path("modules/rustdesk-fleet/evidence/phase48-baseline.json")
PHASE51_VALIDATOR = Path("modules/rustdesk-fleet/tools/validate_phase51.py")
PHASE52_TESTS = Path("modules/rustdesk-fleet/tests/test_phase52_supply_capacity_restore.py")
PHASE52_POST_LIVE_SUCCESSOR = Path(
    "modules/rustdesk-fleet/contracts/phase52-post-live-successor.json"
)
PHASE52_POST_LIVE_ATTESTATION = Path(
    "modules/rustdesk-fleet/evidence/phase52/post-live/successor-attestation.json"
)
PHASE52_POST_LIVE_SUCCESSOR_V1 = "phase52_post_live_successor_v1"
LIVE_DRILL_SOURCE = Path("modules/rustdesk-fleet/tools/phase52-horistic-live-drill.py")
RECOVERY_SOURCE = Path("modules/rustdesk-fleet/tools/phase52_recovery.py")
LIVE_DRILL_CONTRACT = Path("modules/rustdesk-fleet/contracts/phase52-live-drill-contract.json")
REMOTE_MANAGED_SOURCE_DIGEST_BLOCKER = "remote-managed-source-digest-drift"
SCOPE_CONTRACT = Path("modules/rustdesk-fleet/contracts/scope.json")
PHASE52_REQUIREMENTS = ("SCP-04", "SRV-01", "SRV-05", "SRV-07")
PHASE52_CHECK_ORDER = (
    "P52-SUPPLY-001",
    "P52-CAPACITY-001",
    "P52-PLACEMENT-001",
    "P52-VAULT-001",
    "P52-BACKUP-001",
    "P52-RESTORE-001",
    "P52-ROLLBACK-001",
    "P52-TOPOLOGY-001",
    "P52-REPORT-001",
    "P51-WS-001",
    "P51-P48-001",
)
PHASE52_REPORT_INPUTS = (
    SUPPLY_CONTRACT,
    SUPPLY_OBSERVATION,
    CAPACITY_POLICY,
    PLACEMENT_DECISION,
    FULL_GATE_SUMMARY,
    SECRET_ROLES,
    OPERATIONAL_DECISIONS,
    HORISTIC_REVIEW,
    LEDGER,
    PHASE48_BASELINE,
    SCOPE_CONTRACT,
    PHASE51_VALIDATOR,
    Path("modules/rustdesk-fleet/tools/validate_phase52.py"),
    PHASE52_TESTS,
)
SERVER_COMMIT = "9bae9f2f39d92c4b4ba2e28e089da5071897b22e"
CLIENT_COMMIT = "6c578292e8ebbbec708b76986ba8c4bc7c509747"
MULTIARCH_DIGEST = "sha256:10818ec05b179039c6660f4d8e74b303f0db2858bbad2b18e24992ea22d54cd6"
ARM64_IMAGE_DIGEST = "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
ZIP_SHA256 = "4998dd6d32431f9aaf5841663339793bc154d7152313e128832d6b610580abe4"
DEB_SHA256 = "ce62c996f14d33f3bbe3a330e953644a44bace7f05885a7953f7395d69fb49c0"
MSI_SHA256 = "c87d2f4cef2a5acd6003b6507dcfbf5d5168a256db082cd90b54d35193224aaa"
CANDIDATES = ("atius-srv-2", "atius-srv-3", "horistic-srv")
MAX_BYTES = (2**63) - 1
CAPACITY_RESERVATION_KEYS = (
    "loaded_image_bytes",
    "preserved_oci_archive_bytes",
    "peak_import_workspace_bytes",
    "backup_a_bytes",
    "backup_b_bytes",
    "combined_daily_log_budget_bytes",
    "log_retention_days",
    "log_reserve_30d_bytes",
    "state_growth_budget_bytes",
)
COUNTED_RESERVATION_KEYS = (
    "loaded_image_bytes",
    "preserved_oci_archive_bytes",
    "peak_import_workspace_bytes",
    "backup_a_bytes",
    "backup_b_bytes",
    "log_reserve_30d_bytes",
    "state_growth_budget_bytes",
)
MATERIALIZABLE_RESERVATION_KEYS = COUNTED_RESERVATION_KEYS[:5]
STAGE_FIELDS = (
    "supply_status",
    "capacity_status",
    "vault_status",
    "backup_status",
    "restore_status",
    "capacity_finalize_status",
    "rollback_status",
    "topology_security_status",
)
BOUNDED_FULL_GATE_WRITES = (
    "pinned-artifact-staging",
    "pinned-artifact-load",
    "state-only-backup-a",
    "state-only-backup-b",
    "disposable-isolated-restore-state",
    "redacted-evidence-write",
    "verified-drill-artifact-rollback-removal",
)
AUTHORIZED_LIVE_WRITE_CANDIDATE = "horistic-srv"
LIVE_WRITE_CAPABLE_STAGES = (
    "vault",
    "backup",
    "restore",
    "capacity_finalize",
    "rollback",
)
SSH_ALIASES = {
    "atius-srv-2": "atius-srv-2-direct",
    "atius-srv-3": "atius-srv-3-direct",
    "horistic-srv": "horistic-srv-1",
}
CAPACITY_EVIDENCE_NAMES = {
    "atius-srv-2": "capacity-atius-srv-2.json",
    "atius-srv-3": "capacity-atius-srv-3.json",
    "horistic-srv": "capacity-horistic-srv.json",
}
FULL_GATE_EVIDENCE_NAMES = {
    "atius-srv-2": "candidate-atius-srv-2.json",
    "atius-srv-3": "candidate-atius-srv-3.json",
    "horistic-srv": "candidate-horistic-srv.json",
}
READ_ONLY_PREFLIGHT_ACTIONS = ("capacity-sample",)
APPROVED_VAULT_REFERENCES = (
    ("kv/atius/rustdesk/server", "private_key"),
    ("kv/atius/rustdesk/server", "public_key"),
    ("kv/atius/rustdesk/targets/atius-srv-1", "permanent_password"),
    ("kv/atius/rustdesk/targets/atius-srv-2", "permanent_password"),
    ("kv/atius/rustdesk/targets/atius-srv-3", "permanent_password"),
    ("kv/atius/rustdesk/targets/horistic-srv", "permanent_password"),
    ("kv/atius/rustdesk/targets/giovanni-w11-pc", "permanent_password"),
)
REMOTE_CAPACITY_SCRIPT = """\
import datetime
import json
import os
import platform
import shutil
import socket

mount_source = "not-observed"
try:
    for line in open("/proc/self/mountinfo", encoding="utf-8"):
        fields = line.split()
        if len(fields) > 6 and fields[4] == "/" and "-" in fields:
            separator = fields.index("-")
            mount_source = fields[separator + 2]
            break
except OSError:
    pass

stats = os.statvfs("/")
block_size = stats.f_frsize
total_bytes = stats.f_blocks * block_size
available_bytes = stats.f_bavail * block_size
used_bytes = (stats.f_blocks - stats.f_bfree) * block_size
inode_total = stats.f_files
inode_available = stats.f_favail
inode_used = stats.f_files - stats.f_ffree

profile = "not-observed"
profile_path = "/home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/configs/resource-governor.env"
try:
    for line in open(profile_path, encoding="utf-8"):
        if line.startswith("RG_PROFILE_BUILDS_CPU_TOTAL_PCT="):
            profile = line.strip()
            break
except OSError:
    pass

print(json.dumps({
    "observed_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "hostname": socket.gethostname(),
    "architecture": platform.machine(),
    "filesystem_source": mount_source,
    "mount_point": "/",
    "total_bytes": total_bytes,
    "used_bytes": used_bytes,
    "available_bytes": available_bytes,
    "inode_total": inode_total,
    "inode_used": inode_used,
    "inode_available": inode_available,
    "podman_graphroot": "not-observed",
    "podman_version": "not-observed",
    "resource_wrapper": shutil.which("omni") or "not-observed",
    "resource_profile": profile,
    "command_version": "phase52-capacity-read-only-v2",
    "read_only": True,
    "mutation_performed": False,
}, sort_keys=True))
"""

REMOTE_FULL_GATE_READINESS_SCRIPT = """\
import json
import os
import pathlib
import shutil

home = pathlib.Path.home()
runtime_root = pathlib.Path('/run/user') / str(os.getuid())
paths = {
    "vault_helper": home / ".local/bin/atius-vault-env",
    "rustdesk_vault_provider": home / ".local/bin/rustdesk-vault-provider",
    "rustdesk_vault_backend": home / ".local/bin/atius-vault-phase52-client",
    "fleet_backup_module": home / "GitHub/omni-srv-admin/modules/fleet-backup",
    "rclone_vault_hydrator": home / ".local/bin/atius-rclone-vault-hydrate",
    "rclone_copy": home / ".local/bin/rclone-copy-verified-phase52",
    "rclone_fetch": home / ".local/bin/rclone-fetch-verified-phase52",
    "live_drill": home / "GitHub/omni-srv-admin/modules/rustdesk-fleet/tools/phase52-horistic-live-drill.py",
    "runtime_tmpfs": runtime_root,
}
provider = paths["rustdesk_vault_provider"]
backend = paths["rustdesk_vault_backend"]
provider_ready = provider.is_file() and backend.is_file()
provider_probe = {
    "status": "PASS" if provider_ready else "BLOCKED",
    "blocker": "none" if provider_ready else "rustdesk-vault-provider-missing",
    "secret_material_present": False,
}
print(json.dumps({
    "home": str(home),
    "runtime_root": str(runtime_root),
    "tools": {name: bool(shutil.which(name)) for name in ("python3", "omni", "podman", "rclone", "sqlite3")},
    "paths": {name: {"exists": path.exists(), "is_file": path.is_file(), "is_dir": path.is_dir()} for name, path in paths.items()},
    "vault_provider": provider_probe,
    "read_only": True,
    "mutation_performed": False,
}, sort_keys=True))
"""


@dataclass(frozen=True)
class Finding:
    category: str
    path: str
    location: str


@dataclass
class CheckResult:
    id: str
    status: str
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def load_json_strict(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key rejected")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path.name}:{exc.lineno}") from None


def validate_post_live_successor_boundary(repo: Path) -> CheckResult:
    """Validate only the non-authorizing successor boundary; never dispatch live work."""
    contract_path = validate_repo_path(repo, repo / PHASE52_POST_LIVE_SUCCESSOR)
    blocked: list[str] = []
    try:
        contract = load_json_strict(contract_path)
    except (OSError, ValueError):
        contract = {}
        blocked.append("post-live-successor-contract-invalid")
    if contract.get("schema_anchor") != PHASE52_POST_LIVE_SUCCESSOR_V1:
        blocked.append("post-live-successor-anchor-drift")
    if contract.get("authority") != {
        "live_authority": False,
        "replay_authorized": False,
        "vault_write_authorized": False,
    }:
        blocked.append("post-live-successor-authority-drift")
    quorum = contract.get("review_quorum")
    if (
        not isinstance(quorum, dict)
        or quorum.get("require_checkout_snapshots_equal") is not True
        or quorum.get("require_source_freeze_commit") is not True
        or quorum.get("required_findings") != []
        or quorum.get("required_mutation_detected") is not False
    ):
        blocked.append("post-live-successor-review-boundary-drift")
    return _check_result(
        "P52-POST-LIVE-SUCCESSOR-001",
        "PASS" if not blocked else "BLOCKED",
        blocked,
        PHASE52_POST_LIVE_SUCCESSOR.as_posix(),
    )


def validate_repo_path(repo: Path, candidate: Path) -> Path:
    root = repo.resolve()
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError("path is outside repository")
    return resolved


def derive_overall_status(results: list[CheckResult]) -> str:
    if any(item.status == "FAIL" for item in results):
        return "FAIL"
    if any(item.status == "BLOCKED" for item in results):
        return "BLOCKED"
    return "PASS"


def exit_code_for_status(status: str) -> int:
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[status]


def _finding(category: str, source: str, location: str = "contract") -> Finding:
    return Finding(category=category, path=source, location=location)


def _result(status: str, categories: list[str], source: str) -> CheckResult:
    return CheckResult(
        id="P52-SUPPLY-001",
        status=status,
        evidence_ids=["P52-EV-SUPPLY"],
        findings=[_finding(category, source) for category in sorted(set(categories))],
    )


def _check_result(check_id: str, status: str, categories: list[str], source: str) -> CheckResult:
    evidence = check_id.removeprefix("P52-").removesuffix("-001")
    return CheckResult(
        id=check_id,
        status=status,
        evidence_ids=[f"P52-EV-{evidence}"],
        findings=[_finding(category, source) for category in sorted(set(categories))],
    )


def approved_vault_references(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Return contract references only; secret values are never accepted here."""
    server = payload.get("server_identity") if isinstance(payload, dict) else None
    targets = payload.get("target_password_roles") if isinstance(payload, dict) else None
    if not isinstance(server, dict) or not isinstance(targets, list):
        return []
    rows: list[tuple[str, str]] = []
    for key in ("private_key_ref", "public_key_ref"):
        reference = server.get(key)
        if not isinstance(reference, dict):
            return []
        path, field_name = reference.get("vault_path"), reference.get("field")
        if not isinstance(path, str) or not isinstance(field_name, str):
            return []
        rows.append((path, field_name))
    for reference in targets:
        if not isinstance(reference, dict):
            return []
        path, field_name = reference.get("vault_path"), reference.get("field")
        if not isinstance(path, str) or not isinstance(field_name, str):
            return []
        rows.append((path, field_name))
    return rows


def validate_vault_metadata(
    payload: dict[str, Any], source: str = "modules/rustdesk-fleet/contracts/secret-roles.json"
) -> CheckResult:
    blocked: list[str] = []
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or payload.get("authority") != "hashicorp-vault":
        blocked.append("vault-contract-shape")
    references = approved_vault_references(payload)
    if tuple(references) != APPROVED_VAULT_REFERENCES or len(set(references)) != len(references):
        blocked.append("unknown-vault-reference")
    server = payload.get("server_identity") if isinstance(payload, dict) else None
    targets = payload.get("target_password_roles") if isinstance(payload, dict) else None
    approvals = []
    if isinstance(server, dict):
        approvals.append(server.get("approval_status"))
    if isinstance(targets, list):
        approvals.extend(item.get("approval_status") for item in targets if isinstance(item, dict))
    recovery = payload.get("recovery_authority") if isinstance(payload, dict) else None
    if isinstance(recovery, dict):
        approvals.append(recovery.get("approval_status"))
    if approvals != ["approved"] * 7:
        blocked.append("vault-approval-missing")
    if isinstance(payload, dict) and payload.get("value_distinctness_phase") != 52:
        blocked.append("distinctness-phase-drift")
    return _check_result("P52-VAULT-001", "PASS" if not blocked else "BLOCKED", blocked, source)


def _mount_type(path: Path) -> str | None:
    resolved = path.resolve(strict=False)
    best: tuple[int, str] | None = None
    try:
        rows = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for row in rows:
        fields = row.split()
        if "-" not in fields or len(fields) < 7:
            continue
        separator = fields.index("-")
        mount_point = Path(fields[4].replace("\\040", " ")).resolve(strict=False)
        if resolved != mount_point and not resolved.is_relative_to(mount_point):
            continue
        candidate = (len(mount_point.parts), fields[separator + 1])
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best[1] if best else None


def _mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def validate_hydration_runtime(runtime_dir: Path) -> dict[str, Any]:
    files = (runtime_dir / "id_ed25519", runtime_dir / "id_ed25519.pub")
    tmpfs = _mount_type(runtime_dir) == "tmpfs"
    runtime_mode = _mode(runtime_dir) if runtime_dir.is_dir() else "missing"
    file_modes = {path.name: _mode(path) if path.is_file() else "missing" for path in files}
    passed = tmpfs and runtime_mode == "0700" and all(value == "0600" for value in file_modes.values())
    return {
        "status": "PASS" if passed else "BLOCKED",
        "runtime_tmpfs": tmpfs,
        "runtime_mode": runtime_mode,
        "file_modes": file_modes,
        "secret_material_present": False,
    }


def verify_password_distinctness(passwords: list[str]) -> dict[str, Any]:
    if len(passwords) != 5 or any(not isinstance(value, str) or not value for value in passwords):
        return {"count": len(passwords), "unique": 0, "status": "BLOCKED", "secret_material_present": False}
    ephemeral_key = secrets.token_bytes(32)
    digests = {hmac.digest(ephemeral_key, value.encode("utf-8"), "sha256") for value in passwords}
    unique = len(digests)
    return {
        "count": 5,
        "unique": unique,
        "status": "PASS" if unique == 5 else "BLOCKED",
        "secret_material_present": False,
    }


def _vault_provider_values(provider: Path, references: list[tuple[str, str]]) -> dict[str, str]:
    if not provider.is_absolute() or not provider.is_file() or not os.access(provider, os.X_OK):
        raise ValueError("Vault provider is unavailable")
    request = {"references": [{"vault_path": path, "field": field} for path, field in references]}
    completed = subprocess.run(
        [str(provider)],
        input=json.dumps(request, separators=(",", ":")),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0 or completed.stderr:
        raise ValueError("Vault provider failed")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise ValueError("Vault provider response is invalid") from None
    expected = {f"{path}#{field}" for path, field in references}
    values = response.get("values") if isinstance(response, dict) else None
    if (
        not isinstance(response, dict)
        or set(response) != {"request_count", "values"}
        or response.get("request_count") != len(references)
        or not isinstance(values, dict)
        or set(values) != expected
        or any(not isinstance(value, str) or not value for value in values.values())
    ):
        raise ValueError("Vault provider response does not match approved references")
    return values


def _write_private_file(path: Path, value: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(descriptor, value.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_runtime_target(runtime_dir: Path) -> None:
    if runtime_dir.name in {"", ".", ".."} or not runtime_dir.name.startswith("rustdesk-"):
        raise ValueError("runtime directory name is unsafe")
    if runtime_dir.is_symlink() or _mount_type(runtime_dir.parent) != "tmpfs":
        raise ValueError("runtime directory is not on confirmed tmpfs")


def _cleanup_runtime(runtime_dir: Path) -> None:
    _validate_runtime_target(runtime_dir)
    if runtime_dir.exists():
        if runtime_dir.is_symlink() or not runtime_dir.is_dir():
            raise ValueError("runtime cleanup target is unsafe")
        shutil.rmtree(runtime_dir)
    if runtime_dir.exists():
        raise ValueError("runtime cleanup could not be proved")


def _write_safe_result(payload: dict[str, Any]) -> None:
    descriptor_text = os.environ.get("RUSTDESK_VAULT_RESULT_FD")
    if descriptor_text is None or not descriptor_text.isdigit() or int(descriptor_text) < 3:
        raise ValueError("dedicated result descriptor is required")
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    os.write(int(descriptor_text), encoded)


def vault_helper_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("mode", choices=("verify-metadata", "hydrate-server-identity", "verify-password-distinctness", "cleanup"))
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--runtime-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode == "cleanup":
            if args.runtime_dir is None:
                raise ValueError("cleanup requires runtime directory")
            _cleanup_runtime(args.runtime_dir)
            return 0
        if args.contract is None:
            raise ValueError("Vault contract is required")
        contract = load_json_strict(args.contract)
        metadata = validate_vault_metadata(contract, args.contract.name)
        if metadata.status != "PASS":
            _write_safe_result({"status": "BLOCKED", "secret_material_present": False})
            return 2
        references = approved_vault_references(contract)
        provider_text = os.environ.get("RUSTDESK_VAULT_PROVIDER", "")
        values = _vault_provider_values(Path(provider_text), references)
        if args.mode == "verify-metadata":
            result = {
                "status": "PASS",
                "vault_path_count": 6,
                "value_count": 7,
                "secret_material_present": False,
            }
        elif args.mode == "verify-password-distinctness":
            result = verify_password_distinctness(
                [values[f"{path}#{field}"] for path, field in references if field == "permanent_password"]
            )
        else:
            if args.runtime_dir is None:
                raise ValueError("hydration requires runtime directory")
            _validate_runtime_target(args.runtime_dir)
            args.runtime_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
            try:
                _write_private_file(
                    args.runtime_dir / "id_ed25519",
                    values["kv/atius/rustdesk/server#private_key"],
                )
                public_value = values["kv/atius/rustdesk/server#public_key"]
                _write_private_file(args.runtime_dir / "id_ed25519.pub", public_value)
                result = validate_hydration_runtime(args.runtime_dir)
                result["public_key_fingerprint"] = "sha256:" + hashlib.sha256(
                    public_value.encode("utf-8")
                ).hexdigest()
                if result["status"] != "PASS":
                    raise ValueError("runtime hygiene validation failed")
            except BaseException:
                _cleanup_runtime(args.runtime_dir)
                raise
        _write_safe_result(result)
        return exit_code_for_status(result["status"])
    except (OSError, ValueError, subprocess.SubprocessError):
        try:
            _write_safe_result({"status": "BLOCKED", "secret_material_present": False})
        except (OSError, ValueError):
            pass
        return 2


STATE_BACKUP_ALLOWLIST = ("db_v2.sqlite3",)
FULL_CANDIDATE_STAGES = (
    "supply",
    "capacity",
    "vault",
    "backup",
    "restore",
    "capacity_finalize",
    "rollback",
    "topology_security",
)


def verify_state_allowlist(source_dir: Path, source: str = "state-directory") -> CheckResult:
    blocked: list[str] = []
    if not source_dir.is_dir() or source_dir.is_symlink():
        blocked.append("state-directory-missing")
    else:
        observed = sorted(
            path.relative_to(source_dir).as_posix()
            for path in source_dir.rglob("*")
            if path.is_file() or path.is_symlink()
        )
        if "id_ed25519" in observed or "id_ed25519.pub" in observed:
            blocked.append("private-key-in-state" if "id_ed25519" in observed else "identity-in-state")
        if observed != list(STATE_BACKUP_ALLOWLIST):
            blocked.append("state-allowlist-drift")
        database = source_dir / "db_v2.sqlite3"
        if database.is_symlink() or not database.is_file() or _mode(database) != "0600":
            blocked.append("state-mode-or-type")
    return _check_result("P52-RESTORE-001", "PASS" if not blocked else "BLOCKED", blocked, source)


def verify_sqlite_integrity(database: Path, source: str = "db_v2.sqlite3") -> CheckResult:
    blocked: list[str] = []
    if database.name != "db_v2.sqlite3" or not database.is_file() or database.is_symlink():
        blocked.append("wrong-database")
    else:
        try:
            uri = f"file:{database.resolve()}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=5) as connection:
                rows = connection.execute("PRAGMA integrity_check").fetchall()
            if rows != [("ok",)]:
                blocked.append("sqlite-integrity-failure")
        except sqlite3.DatabaseError:
            blocked.append("sqlite-integrity-failure")
    return _check_result("P52-RESTORE-001", "PASS" if not blocked else "BLOCKED", blocked, source)


def quiesce_source(source_state: dict[str, Any], source: str = "source-runtime") -> CheckResult:
    blocked: list[str] = []
    if not isinstance(source_state, dict):
        blocked.append("source-state-shape")
    else:
        if source_state.get("active") is not False:
            blocked.append("active-source")
        if source_state.get("public_listener") is not False:
            blocked.append("public-listener")
        if source_state.get("image_digest") != ARM64_IMAGE_DIGEST:
            blocked.append("unpinned-source-image")
        if source_state.get("architecture") != "arm64":
            blocked.append("source-architecture")
    return _check_result("P52-RESTORE-001", "PASS" if not blocked else "BLOCKED", blocked, source)


def _verify_archive(archive_path: Path) -> dict[str, Any]:
    if not archive_path.is_file() or archive_path.is_symlink() or _mode(archive_path) != "0600":
        raise ValueError("archive mode or type is invalid")
    try:
        with tarfile.open(archive_path, "r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if names != list(STATE_BACKUP_ALLOWLIST):
                raise ValueError("archive allowlist mismatch")
            for member in members:
                candidate = Path(member.name)
                if (
                    candidate.is_absolute()
                    or ".." in candidate.parts
                    or not member.isfile()
                    or member.issym()
                    or member.islnk()
                    or stat.S_IMODE(member.mode) != 0o600
                ):
                    raise ValueError("archive allowlist mismatch")
    except tarfile.TarError:
        raise ValueError("archive is corrupt") from None
    return {
        "entries": names,
        "sha256": _sha256_file(archive_path),
        "size_bytes": archive_path.stat().st_size,
        "archive_mode": _mode(archive_path),
    }


def create_verified_backup(
    source_dir: Path,
    archive_path: Path,
    source_state: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    if label not in {"A", "B"}:
        raise ValueError("backup label must be A or B")
    if quiesce_source(source_state).status != "PASS":
        raise ValueError("source must be quiesced before backup")
    if verify_state_allowlist(source_dir).status != "PASS":
        raise ValueError("source state is not allowlisted")
    if verify_sqlite_integrity(source_dir / "db_v2.sqlite3").status != "PASS":
        raise ValueError("source SQLite integrity failed")
    archive_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if archive_path.exists() or archive_path.is_symlink():
        raise ValueError("backup target already exists")
    lock_path = archive_path.with_name(f".{archive_path.name}.lock")
    temporary = archive_path.with_name(f".{archive_path.name}.partial")
    temporary.unlink(missing_ok=True)
    with lock_path.open("a+b") as lock:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("backup lock is held") from None
        try:
            database = source_dir / "db_v2.sqlite3"
            with database.open("rb") as input_handle, tarfile.open(temporary, "w:") as archive:
                info = tarfile.TarInfo("db_v2.sqlite3")
                info.size = database.stat().st_size
                info.mode = 0o600
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                archive.addfile(info, input_handle)
            os.chmod(temporary, 0o600)
            os.replace(temporary, archive_path)
        finally:
            temporary.unlink(missing_ok=True)
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    verified = _verify_archive(archive_path)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    source_input_digest = _sha256_file(source_dir / "db_v2.sqlite3")
    return {
        "status": "PASS",
        "label": label,
        "archive_path": str(archive_path),
        **verified,
        "archive_sha256": verified["sha256"],
        "generated_at": generated_at,
        "generation_id": secrets.token_hex(16),
        "destination_class": (
            "candidate-local" if label == "A" else "modules/fleet-backup:gdrive"
        ),
        "source_input_digest": source_input_digest,
        "verified_copy": True,
        "retention": {
            "retain_until": "phase57-pass-plus-30-days",
            "deletion_requires_new_explicit_approval": True,
        },
        "secret_material_present": False,
    }


def validate_recovery_backups(
    backup_a: dict[str, Any] | None,
    backup_b: dict[str, Any] | None,
    source: str = "backup-manifests",
) -> CheckResult:
    blocked: list[str] = []
    if not isinstance(backup_a, dict) or backup_a.get("label") != "A":
        blocked.append("missing-backup-a")
    if not isinstance(backup_b, dict) or backup_b.get("label") != "B":
        blocked.append("missing-backup-b")
    if not blocked:
        assert isinstance(backup_a, dict) and isinstance(backup_b, dict)
        if backup_a.get("archive_path") == backup_b.get("archive_path"):
            blocked.append("backup-path-collision")
        if not (
            backup_a.get("status") == backup_b.get("status") == "PASS"
            and (
                backup_a.get("archive_sha256") != backup_b.get("archive_sha256")
                or backup_a.get("generated_at") != backup_b.get("generated_at")
            )
        ):
            blocked.append("backup-generation-not-independent")
        if backup_a.get("generation_id") == backup_b.get("generation_id"):
            blocked.append("backup-generation-id-collision")
        if (
            backup_a.get("destination_class") != "candidate-local"
            or backup_b.get("destination_class") != "modules/fleet-backup:gdrive"
        ):
            blocked.append("backup-destination-drift")
        if (
            not _sha256(backup_a.get("source_input_digest"))
            or backup_a.get("source_input_digest") != backup_b.get("source_input_digest")
        ):
            blocked.append("backup-source-input-drift")
        expected_retention = {
            "retain_until": "phase57-pass-plus-30-days",
            "deletion_requires_new_explicit_approval": True,
        }
        for backup in (backup_a, backup_b):
            if (
                backup.get("verified_copy") is not True
                or backup.get("secret_material_present") is not False
                or backup.get("retention") != expected_retention
            ):
                blocked.append(f"backup-{str(backup.get('label', '')).lower()}-verification-drift")
            try:
                observed = _verify_archive(Path(str(backup.get("archive_path"))))
            except (OSError, ValueError):
                blocked.append(f"corrupt-backup-{str(backup.get('label', '')).lower()}")
                continue
            if any(backup.get(key) != observed[key] for key in ("entries", "sha256", "size_bytes", "archive_mode")):
                blocked.append(f"backup-{str(backup.get('label', '')).lower()}-manifest-drift")
    return _check_result("P52-RESTORE-001", "PASS" if not blocked else "BLOCKED", blocked, source)


def restore_isolated(archive_path: Path, restore_parent: Path) -> dict[str, Any]:
    verified = _verify_archive(archive_path)
    restore_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(restore_parent, 0o700)
    runtime_dir = Path(tempfile.mkdtemp(prefix="rustdesk-restore-", dir=restore_parent))
    os.chmod(runtime_dir, 0o700)
    try:
        marker = runtime_dir / ".phase52-disposable-restore"
        marker.write_text("phase52-disposable\n", encoding="utf-8")
        marker.chmod(0o600)
        with tarfile.open(archive_path, "r:") as archive:
            member = archive.getmember("db_v2.sqlite3")
            input_handle = archive.extractfile(member)
            if input_handle is None:
                raise ValueError("archive database is missing")
            destination = runtime_dir / "db_v2.sqlite3"
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as output_handle:
                    shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
                    output_handle.flush()
                    os.fsync(output_handle.fileno())
            finally:
                os.close(descriptor)
        if verify_sqlite_integrity(runtime_dir / "db_v2.sqlite3").status != "PASS":
            raise ValueError("restored SQLite integrity failed")
        return {
            "status": "PASS",
            "runtime_dir": str(runtime_dir),
            "archive_sha256": verified["sha256"],
            "entries": verified["entries"],
            "public_network": False,
            "published_ports": [],
            "secret_material_present": False,
        }
    except BaseException:
        shutil.rmtree(runtime_dir, ignore_errors=False)
        raise


def verify_public_fingerprint(
    public_key_path: Path, expected_fingerprint: str, source: str = "public-identity"
) -> CheckResult:
    blocked: list[str] = []
    if not public_key_path.is_file() or public_key_path.is_symlink():
        blocked.append("public-key-missing")
    else:
        observed = "sha256:" + hashlib.sha256(public_key_path.read_bytes()).hexdigest()
        if observed != expected_fingerprint:
            blocked.append("fingerprint-mismatch")
    return _check_result("P52-RESTORE-001", "PASS" if not blocked else "BLOCKED", blocked, source)


def verify_no_public_listener(runtime_state: dict[str, Any], source: str = "restore-runtime") -> CheckResult:
    blocked = [] if isinstance(runtime_state, dict) and runtime_state.get("public_listener") is False else ["public-listener"]
    return _check_result("P52-RESTORE-001", "PASS" if not blocked else "BLOCKED", blocked, source)


def cleanup_restore_runtime(
    runtime_dir: Path,
    runtime_state: dict[str, Any],
    *,
    restore_verified: bool,
    source: str = "restore-runtime",
) -> CheckResult:
    blocked: list[str] = []
    marker = runtime_dir / ".phase52-disposable-restore"
    if not restore_verified:
        blocked.append("restore-not-verified")
    if runtime_dir.is_symlink() or not runtime_dir.name.startswith("rustdesk-restore-") or not marker.is_file():
        blocked.append("unsafe-cleanup-target")
    if not isinstance(runtime_state, dict) or runtime_state.get("service_active") is not False:
        blocked.append("restored-service-active")
    if not isinstance(runtime_state, dict) or runtime_state.get("service_enabled") is not False:
        blocked.append("restored-service-enabled")
    if not isinstance(runtime_state, dict) or runtime_state.get("public_listener") is not False:
        blocked.append("public-listener")
    if blocked:
        return _check_result("P52-ROLLBACK-001", "BLOCKED", blocked, source)
    try:
        shutil.rmtree(runtime_dir)
    except OSError:
        return _check_result("P52-ROLLBACK-001", "BLOCKED", ["cleanup-failure"], source)
    if runtime_dir.exists():
        return _check_result("P52-ROLLBACK-001", "BLOCKED", ["cleanup-failure"], source)
    return _check_result("P52-ROLLBACK-001", "PASS", [], source)


def _stage_record(candidate: str, stage: str, value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = {"status": value}
    if not isinstance(value, dict):
        raise ValueError("candidate stage returned invalid result")
    status = value.get("status")
    if status not in {"PASS", "NO-GO", "FAIL", "BLOCKED"}:
        raise ValueError("candidate stage returned invalid status")
    digest = value.get("input_digest")
    if not _sha256(digest):
        digest = hashlib.sha256(f"{candidate}:{stage}".encode("utf-8")).hexdigest()
    evidence_ids = value.get("evidence_ids", [])
    if not isinstance(evidence_ids, list) or not all(
        isinstance(item, str) and item for item in evidence_ids
    ):
        raise ValueError("candidate stage evidence IDs are invalid")
    findings = value.get("findings", [])
    if not isinstance(findings, list) or not all(isinstance(item, str) for item in findings):
        raise ValueError("candidate stage findings are invalid")
    mutation = value.get("mutation", {"performed": False, "classes": []})
    if (
        not isinstance(mutation, dict)
        or mutation.get("performed") not in {True, False}
        or not isinstance(mutation.get("classes"), list)
        or not all(isinstance(item, str) and item for item in mutation.get("classes", []))
        or len(mutation.get("classes", [])) != len(set(mutation.get("classes", [])))
        or (mutation.get("performed") is True and not mutation.get("classes"))
    ):
        raise ValueError("candidate stage mutation metadata is invalid")
    return {
        **value,
        "status": status,
        "observed_at": value.get("observed_at")
        or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "input_digest": digest,
        "evidence_ids": evidence_ids,
        "findings": findings,
        "mutation": mutation,
        "secret_material_present": False,
    }


def _skipped_stage_record(candidate: str, stage: str, predecessor: str) -> dict[str, Any]:
    return {
        "status": "SKIPPED_DUE_TO_GATE",
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "input_digest": hashlib.sha256(f"{candidate}:{stage}:{predecessor}".encode("utf-8")).hexdigest(),
        "evidence_ids": [],
        "findings": ["predecessor-stage-not-pass"],
        "predecessor_stage": predecessor,
        "mutation": {"performed": False, "classes": []},
        "secret_material_present": False,
    }


def enforce_candidate_write(
    candidate: str,
    action: str,
    *,
    capacity_status: str,
    isolated: bool,
    authorized: bool = True,
    authorized_live_write_candidate: str = AUTHORIZED_LIVE_WRITE_CANDIDATE,
) -> None:
    if candidate not in CANDIDATES:
        raise ValueError("unknown candidate")
    if action not in BOUNDED_FULL_GATE_WRITES:
        raise ValueError("candidate write action is forbidden")
    if (
        authorized_live_write_candidate != AUTHORIZED_LIVE_WRITE_CANDIDATE
        or candidate != authorized_live_write_candidate
    ):
        raise ValueError("unauthorized-live-write-candidate")
    if capacity_status != "PASS":
        raise ValueError("candidate write requires current capacity PASS")
    if isolated is not True:
        raise ValueError("candidate write isolation is not proven")
    if authorized is not True:
        raise ValueError("candidate write authorization is absent")


def horistic_topology_evidence() -> dict[str, Any]:
    return {
        "status": "PASS",
        "client_colocation": True,
        "independent_dr_claimed": False,
        "phase52_review_status": "PASS",
        "phase53_review": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
        "phase54_review": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
        "phase57_review": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
        "server_client_resource_domains": {
            "server": "rustdesk-server-horistic-srv",
            "client": "rustdesk-client-horistic-srv",
        },
        "server_client_evidence_domains": {
            "server": "phase53-server-evidence",
            "client": "phase54-client-evidence",
        },
        "server_client_rollback_domains": {
            "server": "phase53-server-rollback",
            "client": "phase54-client-rollback",
        },
        "secret_material_present": False,
    }


def run_full_candidate_gate(
    candidate: str,
    stage_callbacks: dict[str, Any],
    persist: Any,
    *,
    authorized_live_write_candidate: str = AUTHORIZED_LIVE_WRITE_CANDIDATE,
) -> dict[str, Any]:
    if candidate not in CANDIDATES or set(stage_callbacks) != set(FULL_CANDIDATE_STAGES):
        raise ValueError("candidate gate contract is incomplete")
    if authorized_live_write_candidate != AUTHORIZED_LIVE_WRITE_CANDIDATE:
        raise ValueError("authorized live write candidate is invalid")
    stages: dict[str, dict[str, Any]] = {}
    first_non_pass: str | None = None
    for stage in FULL_CANDIDATE_STAGES:
        if first_non_pass is not None and stage != "rollback":
            stages[stage] = _skipped_stage_record(candidate, stage, first_non_pass)
            continue
        if stage == "rollback" and stages.get("capacity", {}).get("status") != "PASS":
            record = _stage_record(
                candidate,
                stage,
                {
                    "status": "BLOCKED",
                    "findings": ["rollback-requires-current-capacity-pass"],
                    "inactive": True,
                    "mutation": {"performed": False, "classes": []},
                },
            )
            stages[stage] = record
            if first_non_pass is None:
                first_non_pass = stage
            continue
        if stage in LIVE_WRITE_CAPABLE_STAGES and candidate != authorized_live_write_candidate:
            record = _stage_record(
                candidate,
                stage,
                {
                    "status": "BLOCKED",
                    "findings": ["unauthorized-live-write-candidate"],
                    "mutation": {"performed": False, "classes": []},
                },
            )
            stages[stage] = record
            if first_non_pass is None:
                first_non_pass = stage
            continue
        try:
            record = _stage_record(candidate, stage, stage_callbacks[stage]())
        except Exception:
            record = _stage_record(
                candidate,
                stage,
                {"status": "BLOCKED", "findings": ["stage-exception"]},
            )
        stages[stage] = record
        if record["status"] != "PASS" and first_non_pass is None:
            first_non_pass = stage
    verdict = "PASS" if all(record["status"] == "PASS" for record in stages.values()) else "NO-GO"
    result = {
        "schema_version": 1,
        "candidate": candidate,
        "stages": stages,
        "verdict": verdict,
        "first_non_pass_stage": first_non_pass,
        "persisted_before_fallback": True,
        "secret_material_present": False,
        "windows_install_performed": False,
        "public_listener_created": False,
        "authorized_live_write_candidate": authorized_live_write_candidate,
    }
    result["record_digest"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    persist(result)
    return result


def run_candidate_chain(
    candidates: tuple[str, ...],
    callbacks_by_candidate: dict[str, dict[str, Any]],
    persist: Any,
    *,
    authorized_live_write_candidate: str = AUTHORIZED_LIVE_WRITE_CANDIDATE,
) -> dict[str, Any]:
    if authorized_live_write_candidate != AUTHORIZED_LIVE_WRITE_CANDIDATE:
        raise ValueError("authorized live write candidate is invalid")
    if not candidates or tuple(CANDIDATES[: len(candidates)]) != candidates:
        raise ValueError("candidate chain order is invalid")
    attempts: list[dict[str, Any]] = []
    selected: str | None = None
    predecessor_nogo_digests: list[str] = []
    for candidate in candidates:
        if candidate not in callbacks_by_candidate:
            raise ValueError("candidate callbacks are missing")
        result = run_full_candidate_gate(
            candidate,
            callbacks_by_candidate[candidate],
            persist,
            authorized_live_write_candidate=authorized_live_write_candidate,
        )
        attempts.append(result)
        if result["verdict"] == "PASS":
            selected = candidate
            break
        predecessor_nogo_digests.append(result["record_digest"])
    return {
        "schema_version": 1,
        "attempt_order": [row["candidate"] for row in attempts],
        "attempts": attempts,
        "predecessor_nogo_digests": predecessor_nogo_digests,
        "selected_candidate": selected,
        "overall_status": "PASS" if selected is not None else "BLOCKED",
        "windows_install_performed": False,
        "secret_material_present": False,
        "authorized_live_write_candidate": authorized_live_write_candidate,
    }


def build_full_gate_readiness_command(candidate: str) -> list[str]:
    if candidate not in CANDIDATES:
        raise ValueError("unknown candidate")
    return [
        "ssh",
        "-n",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        SSH_ALIASES[candidate],
        f"python3 -c {shlex.quote(REMOTE_FULL_GATE_READINESS_SCRIPT)}",
    ]


def collect_full_gate_readiness(candidate: str) -> dict[str, Any]:
    completed = subprocess.run(
        build_full_gate_readiness_command(candidate),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(f"read-only full-gate readiness probe failed for {candidate}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise ValueError(f"invalid full-gate readiness output for {candidate}") from None
    if (
        not isinstance(payload, dict)
        or payload.get("read_only") is not True
        or payload.get("mutation_performed") is not False
        or not isinstance(payload.get("tools"), dict)
        or not isinstance(payload.get("paths"), dict)
        or not isinstance(payload.get("home"), str)
        or not payload["home"].startswith("/")
        or not isinstance(payload.get("runtime_root"), str)
        or not payload["runtime_root"].startswith("/")
        or not isinstance(payload.get("vault_provider"), dict)
        or payload["vault_provider"].get("status") not in {"PASS", "BLOCKED"}
        or payload["vault_provider"].get("secret_material_present") is not False
    ):
        raise ValueError(f"unsafe full-gate readiness output for {candidate}")
    return payload


def build_live_drill_command(
    candidate: str, action: str, transaction_dir: str, *, initialize: bool = False
) -> list[str]:
    if candidate != "horistic-srv" or action not in (
        "preflight", "vault", "backup", "restore", "capacity-finalize", "rollback"
    ):
        raise ValueError("live drill is restricted to Horistic and exact actions")
    transaction = Path(transaction_dir)
    if not transaction.is_absolute() or transaction.name.startswith("."):
        raise ValueError("invalid live-drill transaction path")
    arguments = [
        "--action", action,
        "--transaction-dir", transaction.as_posix(),
    ]
    repo_root = Path(__file__).resolve().parents[3]
    managed = {
        "live_drill_sha256": _sha256_file(repo_root / LIVE_DRILL_SOURCE),
        "recovery_sha256": _sha256_file(repo_root / RECOVERY_SOURCE),
        "live_drill_contract_sha256": _sha256_file(repo_root / LIVE_DRILL_CONTRACT),
        "validator_sha256": _sha256_file(repo_root / Path("modules/rustdesk-fleet/tools/validate_phase52.py")),
        "capacity_policy_sha256": _sha256_file(repo_root / CAPACITY_POLICY),
        "provider_sha256": _sha256_file(repo_root / Path("modules/rustdesk-fleet/tools/rustdesk-vault-provider")),
        "client_sha256": _sha256_file(repo_root / Path("modules/rustdesk-fleet/tools/atius-vault-phase52-client")),
        "rclone_hydrate_sha256": _sha256_file(repo_root / Path("modules/fleet-backup/scripts/atius-rclone-vault-hydrate")),
        "rclone_copy_sha256": _sha256_file(repo_root / Path("modules/fleet-backup/scripts/rclone-copy-verified-phase52.sh")),
        "rclone_fetch_sha256": _sha256_file(repo_root / Path("modules/fleet-backup/scripts/rclone-fetch-verified-phase52.sh")),
    }
    arguments.extend(["--expected-managed-source-digests", json.dumps(managed, sort_keys=True, separators=(",", ":"))])
    if initialize:
        arguments.append("--initialize")
    remote_command = "python3 \"$HOME/GitHub/omni-srv-admin/modules/rustdesk-fleet/tools/phase52-horistic-live-drill.py\" " + " ".join(
        shlex.quote(item) for item in arguments
    )
    return [
        "ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        "-o", "ConnectionAttempts=1", SSH_ALIASES[candidate],
        remote_command,
    ]


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.SubprocessError:
        pass


def _run_bounded_text_command(
    command: list[str], *, timeout: int, stdout_limit: int, stderr_limit: int
) -> tuple[int, str, str]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    sizes = {"stdout": 0, "stderr": 0}
    deadline = time.monotonic() + timeout
    try:
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, ("stdout", stdout_limit))
        selector.register(process.stderr, selectors.EVENT_READ, ("stderr", stderr_limit))
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("bounded-command-timeout")
            events = selector.select(remaining)
            if not events:
                raise TimeoutError("bounded-command-timeout")
            for key, _ in events:
                name, limit = key.data
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                sizes[name] += len(chunk)
                if sizes[name] > limit:
                    raise OverflowError(f"bounded-command-{name}-overflow")
                chunks[name].append(chunk)
        code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        return (
            code,
            b"".join(chunks["stdout"]).decode("utf-8", errors="strict"),
            b"".join(chunks["stderr"]).decode("utf-8", errors="strict"),
        )
    except BaseException:
        _kill_process_group(process)
        raise
    finally:
        selector.close()


def _validate_live_action_contract(action: str, details: dict[str, Any], mutation: dict[str, Any], status: str) -> None:
    recovery_path = Path(__file__).with_name("phase52_recovery.py")
    spec = importlib.util.spec_from_file_location("phase52_controller_recovery_contract", recovery_path)
    if spec is None or spec.loader is None:
        raise ValueError("live-drill action details invalid")
    recovery = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = recovery
    try:
        spec.loader.exec_module(recovery)
        recovery.validate_mutation(mutation)
        if status == "PASS":
            recovery.validate_action_result(action, details)
    except Exception as exc:
        raise ValueError("live-drill action details invalid") from exc


def run_live_drill_action(
    candidate: str, action: str, transaction_dir: str, *, initialize: bool = False
) -> dict[str, Any]:
    returncode, stdout, stderr = _run_bounded_text_command(
        build_live_drill_command(candidate, action, transaction_dir, initialize=initialize),
        timeout=930,
        stdout_limit=131072,
        stderr_limit=4096,
    )
    if stderr:
        raise ValueError("live-drill stream contract failed")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        raise ValueError("live-drill output invalid") from None
    if not isinstance(payload, dict):
        raise ValueError("live-drill result invalid")
    expected_keys = {
        "schema", "transaction_id", "action", "status", "details", "mutation",
        "secret_material_present",
    }
    if payload.get("status") == "BLOCKED":
        expected_keys.add("blocker")
    mutation = payload.get("mutation")
    allowed_mutations = {
        "redacted-evidence-write", "ephemeral-vault-hydration", "isolated-source-runtime",
        "isolated-hbbs-container-lifecycle", "state-only-backup-a",
        "state-only-backup-b-local", "state-only-backup-b-remote-create",
        "disposable-isolated-restore-state", "verified-drill-artifact-rollback-removal",
    }
    if (
        set(payload) != expected_keys
        or payload.get("schema") != "phase52-live-drill-result-v2"
        or payload.get("action") != action
        or not isinstance(payload.get("transaction_id"), str)
        or re.fullmatch(r"[0-9a-f]{32}", payload["transaction_id"]) is None
        or payload.get("secret_material_present") is not False
        or not isinstance(payload.get("details"), dict)
        or not isinstance(mutation, dict)
        or set(mutation) != {"performed", "classes", "cleanup_pending", "retained_artifacts"}
        or mutation.get("performed") not in {True, False}
        or not isinstance(mutation.get("classes"), list)
        or len(mutation["classes"]) != len(set(mutation["classes"]))
        or not set(mutation["classes"]).issubset(allowed_mutations)
        or (mutation.get("performed") is True and not mutation["classes"])
        or not isinstance(mutation.get("cleanup_pending"), list)
        or mutation.get("retained_artifacts") != ["backup-a", "backup-b-local", "backup-b-remote"]
        or (returncode == 0) != (payload.get("status") == "PASS")
        or (returncode == 2) != (payload.get("status") == "BLOCKED")
        or returncode not in {0, 2}
    ):
        raise ValueError("live-drill result invalid")
    _validate_live_action_contract(
        action, payload["details"], mutation, str(payload["status"])
    )
    return payload


def validate_all_predecessor_mutations(summary: dict[str, Any]) -> list[str]:
    attempts = summary.get("attempts") if isinstance(summary, dict) else None
    selected = summary.get("selected_candidate") if isinstance(summary, dict) else None
    if not isinstance(attempts, list):
        return []
    findings: list[str] = []
    for attempt in attempts:
        if not isinstance(attempt, dict) or (selected is not None and attempt.get("candidate") == selected):
            break
        stages = attempt.get("stages")
        if not isinstance(stages, dict) or any(
            not isinstance(record, dict)
            or record.get("mutation") != {"performed": False, "classes": []}
            for record in stages.values()
        ):
            findings.append("predecessor-mutation")
    return sorted(set(findings))


def _stage_input_digest(*payloads: Any) -> str:
    return hashlib.sha256(
        json.dumps(payloads, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _update_placement_from_full_gate(
    placement: dict[str, Any], summary: dict[str, Any]
) -> dict[str, Any]:
    updated = json.loads(json.dumps(placement))
    by_candidate = {row["candidate"]: row for row in summary["attempts"]}
    stage_to_field = dict(zip(FULL_CANDIDATE_STAGES, STAGE_FIELDS, strict=True))
    for row in updated["candidates"]:
        candidate = row["candidate"]
        attempt = by_candidate.get(candidate)
        if attempt is None:
            row["evaluated"] = False
            continue
        row["evaluated"] = True
        evidence_ids: list[str] = []
        for stage, field_name in stage_to_field.items():
            stage_record = attempt["stages"][stage]
            row[field_name] = stage_record["status"]
            evidence_ids.extend(stage_record.get("evidence_ids", []))
        row["evidence_ids"] = list(dict.fromkeys(evidence_ids))
        row["verdict"] = attempt["verdict"]
    derived = derive_placement(updated)
    updated["selected_candidate"] = derived["selected_candidate"]
    updated["overall_status"] = derived["overall_status"]
    updated["windows_install_performed"] = False
    updated["windows_access_proven"] = False
    updated["cold_standby_claimed"] = False
    return updated


def validate_full_candidate_summary(
    summary: dict[str, Any], placement: dict[str, Any], evidence_root: Path
) -> CheckResult:
    fail: list[str] = []
    blocked: list[str] = []
    fail.extend(validate_all_predecessor_mutations(summary))
    if summary.get("authorized_live_write_candidate") != AUTHORIZED_LIVE_WRITE_CANDIDATE:
        fail.append("authorized-live-write-candidate-drift")
    if summary.get("attempt_order") != list(CANDIDATES):
        fail.append("candidate-order-bypass")
    attempts = summary.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != len(CANDIDATES):
        fail.append("candidate-shape")
        attempts = []
    for index, attempt in enumerate(attempts):
        candidate = CANDIDATES[index]
        if not isinstance(attempt, dict) or attempt.get("candidate") != candidate:
            fail.append("candidate-shape")
            continue
        if attempt.get("authorized_live_write_candidate") != AUTHORIZED_LIVE_WRITE_CANDIDATE:
            fail.append("authorized-live-write-candidate-drift")
        if set(attempt.get("stages", {})) != set(FULL_CANDIDATE_STAGES):
            fail.append("stage-vector-shape")
        unsigned = dict(attempt)
        stored_digest = unsigned.pop("record_digest", None)
        expected_digest = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if stored_digest != expected_digest:
            fail.append("candidate-record-digest-drift")
        evidence_path = evidence_root / FULL_GATE_EVIDENCE_NAMES[candidate]
        try:
            persisted = load_json_strict(evidence_path)
        except (OSError, ValueError):
            fail.append("candidate-evidence-missing")
        else:
            if persisted != attempt:
                fail.append("candidate-evidence-drift")
        if attempt.get("secret_material_present") is not False or attempt.get(
            "windows_install_performed"
        ) is not False:
            fail.append("phase-boundary-drift")
        if index and attempts[index - 1].get("verdict") != "NO-GO":
            fail.append("candidate-order-bypass")
    derived = derive_placement(placement)
    if (
        summary.get("selected_candidate") != derived["selected_candidate"]
        or summary.get("overall_status") != derived["overall_status"]
    ):
        fail.append("stored-verdict-drift")
    placement_result = validate_placement_decision(placement)
    if placement_result.status == "FAIL":
        fail.extend(item.category for item in placement_result.findings)
    if summary.get("windows_install_performed") is not False or summary.get(
        "secret_material_present"
    ) is not False:
        fail.append("phase-boundary-drift")
    if not fail and summary.get("overall_status") != "PASS":
        first_non_pass = next(
            (
                row.get("first_non_pass_stage")
                for row in reversed(attempts)
                if row.get("first_non_pass_stage") is not None
            ),
            "unknown",
        )
        blocked.append(f"no-primary:{first_non_pass}")
    return _check_result(
        "P52-FULL-GATE-001",
        "FAIL" if fail else "BLOCKED" if blocked else "PASS",
        sorted(set(fail + blocked)),
        FULL_GATE_SUMMARY.as_posix(),
    )


def run_full_candidate_chain(repo: Path, evidence_dir: Path) -> CheckResult:
    policy = load_json_strict(validate_repo_path(repo, repo / CAPACITY_POLICY))
    placement_path = validate_repo_path(repo, repo / PLACEMENT_DECISION)
    placement = load_json_strict(placement_path)
    supply_contract = load_json_strict(validate_repo_path(repo, repo / SUPPLY_CONTRACT))
    supply_path = validate_repo_path(repo, repo / SUPPLY_OBSERVATION)
    supply = load_json_strict(supply_path)
    secret_roles_path = validate_repo_path(repo, repo / SECRET_ROLES)
    secret_roles = load_json_strict(secret_roles_path)
    decision_path = validate_repo_path(repo, repo / OPERATIONAL_DECISIONS)
    review_path = validate_repo_path(repo, repo / HORISTIC_REVIEW)
    evidence_root = validate_repo_path(repo, repo / evidence_dir)

    if validate_capacity_policy(policy).status != "PASS":
        raise ValueError("capacity policy is not approved")
    if validate_supply_contract(supply_contract).status != "PASS" or validate_supply_observation(
        supply, supply_contract, repo=repo
    ).status != "PASS":
        raise ValueError("supply evidence is not current PASS")
    if validate_vault_metadata(secret_roles).status != "PASS":
        raise ValueError("Vault reference contract is not approved")
    if policy["approval"]["source_sha256"] != _sha256_file(decision_path):
        raise ValueError("capacity approval source digest drift")
    review_text = review_path.read_text(encoding="utf-8")
    if "**Status:** Approved for Phase 52 candidate evaluation" not in review_text:
        raise ValueError("Horistic Phase 52 topology review is not current PASS")

    supply_digest = _sha256_file(supply_path)
    decision_digest = _sha256_file(decision_path)
    secret_roles_digest = _sha256_file(secret_roles_path)
    review_digest = _sha256_file(review_path)
    contexts: dict[str, dict[str, Any]] = {candidate: {} for candidate in CANDIDATES}
    callbacks_by_candidate: dict[str, dict[str, Any]] = {}

    for candidate in CANDIDATES:
        context = contexts[candidate]

        def supply_stage(host: str = candidate) -> dict[str, Any]:
            return {
                "status": "PASS",
                "input_digest": supply_digest,
                "evidence_ids": ["P52-EV-SUPPLY-OBSERVATION"],
                "findings": [],
                "mutation": {"performed": False, "classes": []},
                "candidate": host,
            }

        def capacity_stage(host: str = candidate, state: dict[str, Any] = context) -> dict[str, Any]:
            samples = [collect_capacity_sample(host), collect_capacity_sample(host)]
            calculations = [derive_candidate_capacity(sample, policy) for sample in samples]
            state["samples"] = samples
            status = "PASS" if all(row["status"] == "PASS" for row in calculations) else "NO-GO"
            return {
                "status": status,
                "input_digest": _stage_input_digest(decision_digest, supply_digest, samples),
                "evidence_ids": [f"P52-EV-FULL-CAPACITY-{host.upper()}"],
                "findings": [] if status == "PASS" else _capacity_findings(calculations),
                "samples": samples,
                "calculations": calculations,
                "read_only": True,
                "mutation": {"performed": False, "classes": []},
            }

        def vault_stage(host: str = candidate, state: dict[str, Any] = context) -> dict[str, Any]:
            readiness = collect_full_gate_readiness(host)
            state["readiness"] = readiness
            vault_helper = readiness["paths"].get("vault_helper", {})
            provider = readiness["paths"].get("rustdesk_vault_provider", {})
            provider_probe = readiness.get("vault_provider", {})
            findings: list[str] = []
            vault_result: dict[str, Any] | None = None
            if vault_helper.get("is_file") is not True:
                findings.append("vault-export-helper-missing")
            if provider.get("is_file") is not True:
                findings.append("rustdesk-vault-provider-missing")
            elif provider_probe.get("status") != "PASS":
                blocker = provider_probe.get("blocker")
                findings.append(
                    blocker if isinstance(blocker, str) and blocker else "rustdesk-vault-provider-not-ready"
                )
            required_paths = ("rclone_vault_hydrator", "rclone_copy", "rclone_fetch", "live_drill")
            for required_path in required_paths:
                if readiness["paths"].get(required_path, {}).get("is_file") is not True:
                    findings.append(f"{required_path.replace('_', '-')}-missing")
            if host == "horistic-srv" and not findings:
                transaction_dir = str(
                    Path(readiness["runtime_root"])
                    / f"rustdesk-phase52-{secrets.token_hex(12)}"
                )
                state["transaction_dir"] = transaction_dir
                preflight = run_live_drill_action(
                    host, "preflight", transaction_dir, initialize=True
                )
                if preflight.get("status") != "PASS":
                    findings.append(str(preflight.get("blocker") or "live-drill-preflight-blocked"))
                else:
                    vault_result = run_live_drill_action(host, "vault", transaction_dir)
                    if vault_result.get("status") != "PASS":
                        findings.append(str(vault_result.get("blocker") or "live-vault-blocked"))
            return {
                "status": "PASS" if not findings else "BLOCKED",
                "input_digest": _stage_input_digest(secret_roles_digest, readiness),
                "evidence_ids": [f"P52-EV-VAULT-READINESS-{host.upper()}"],
                "findings": findings,
                "reference_count": len(APPROVED_VAULT_REFERENCES),
                "readiness": readiness,
                "action_details": (vault_result or {}).get("details", {}),
                "mutation": (vault_result or {}).get("mutation", {"performed": False, "classes": []}),
            }

        def backup_stage(host: str = candidate, state: dict[str, Any] = context) -> dict[str, Any]:
            readiness = state.get("readiness") or collect_full_gate_readiness(host)
            tools = readiness["tools"]
            paths = readiness["paths"]
            findings: list[str] = []
            if tools.get("rclone") is not True:
                findings.append("rclone-missing")
            if paths.get("rclone_vault_hydrator", {}).get("is_file") is not True:
                findings.append("rclone-vault-hydrator-missing")
            if paths.get("rclone_copy", {}).get("is_file") is not True:
                findings.append("rclone-copy-missing")
            if paths.get("rclone_fetch", {}).get("is_file") is not True:
                findings.append("rclone-fetch-missing")
            if paths.get("fleet_backup_module", {}).get("is_dir") is not True:
                findings.append("managed-fleet-backup-module-missing")
            live_result: dict[str, Any] | None = None
            if not findings and host == "horistic-srv" and isinstance(state.get("transaction_dir"), str):
                live_result = run_live_drill_action(host, "backup", state["transaction_dir"])
                if live_result.get("status") != "PASS":
                    findings.append(str(live_result.get("blocker") or "live-backup-blocked"))
            return {
                "status": "PASS" if not findings else "BLOCKED",
                "input_digest": _stage_input_digest(readiness),
                "evidence_ids": [f"P52-EV-BACKUP-READINESS-{host.upper()}"],
                "findings": findings,
                "action_details": (live_result or {}).get("details", {}),
                "mutation": (live_result or {}).get("mutation", {"performed": False, "classes": []}),
            }

        def live_stage(name: str, host: str = candidate, state: dict[str, Any] = context) -> dict[str, Any]:
            transaction_dir = state.get("transaction_dir")
            if host != "horistic-srv" or not isinstance(transaction_dir, str):
                result = {"status": "BLOCKED", "blocker": "stage-preconditions-not-satisfied"}
            else:
                result = run_live_drill_action(host, name, transaction_dir)
            return {
                "status": result.get("status", "BLOCKED"),
                "input_digest": _stage_input_digest(host, name),
                "evidence_ids": [f"P52-EV-{name.upper()}-{host.upper()}"],
                "findings": [] if result.get("status") == "PASS" else [str(result.get("blocker") or "live-drill-blocked")],
                "action_details": result.get("details", {}),
                "mutation": result.get("mutation", {"performed": False, "classes": []}),
            }

        def rollback_stage(host: str = candidate, state: dict[str, Any] = context) -> dict[str, Any]:
            if not isinstance(state.get("transaction_dir"), str):
                return {
                    "status": "PASS", "input_digest": _stage_input_digest(host, "rollback", "no-artifacts"),
                    "evidence_ids": [f"P52-EV-ROLLBACK-NOOP-{host.upper()}"], "findings": [],
                    "inactive": True, "disposable_artifacts_present": False,
                    "retained_backups_deleted": False, "mutation": {"performed": False, "classes": []},
                }
            result = run_live_drill_action(host, "rollback", state["transaction_dir"])
            return {
                "status": result.get("status", "BLOCKED"),
                "input_digest": _stage_input_digest(host, "rollback"),
                "evidence_ids": [f"P52-EV-ROLLBACK-{host.upper()}"],
                "findings": [] if result.get("status") == "PASS" else [str(result.get("blocker") or "rollback-blocked")],
                "retained_backups_deleted": result.get("retained_backups_deleted", False),
                "action_details": result.get("details", {}),
                "mutation": result.get("mutation", {"performed": False, "classes": []}),
            }

        def topology_stage(host: str = candidate) -> dict[str, Any]:
            topology = horistic_topology_evidence() if host == "horistic-srv" else {
                "status": "PASS",
                "client_colocation": False,
                "independent_dr_claimed": False,
            }
            return {
                **topology,
                "input_digest": review_digest if host == "horistic-srv" else _stage_input_digest(host),
                "evidence_ids": [f"P52-EV-TOPOLOGY-{host.upper()}"],
                "findings": [],
                "mutation": {"performed": False, "classes": []},
            }

        callbacks_by_candidate[candidate] = {
            "supply": supply_stage,
            "capacity": capacity_stage,
            "vault": vault_stage,
            "backup": backup_stage,
            "restore": lambda host=candidate: live_stage("restore", host),
            "capacity_finalize": lambda host=candidate: live_stage("capacity-finalize", host),
            "rollback": rollback_stage,
            "topology_security": topology_stage,
        }

    def persist(payload: dict[str, Any]) -> None:
        path = validate_repo_path(
            repo, evidence_root / FULL_GATE_EVIDENCE_NAMES[payload["candidate"]]
        )
        _write_json_atomically(payload, path)

    lock_path = evidence_root / ".full-candidate-chain.lock"
    with lock_path.open("a+b") as lock:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("full candidate chain lock is held") from None
        summary = run_candidate_chain(
            CANDIDATES,
            callbacks_by_candidate,
            persist,
            authorized_live_write_candidate=AUTHORIZED_LIVE_WRITE_CANDIDATE,
        )
        summary["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )
        summary["decision_source_digest"] = decision_digest
        summary["supply_digest"] = supply_digest
        summary["topology_review_digest"] = review_digest
        summary["windows_access_proven"] = False
        summary["public_listener_created"] = False
        updated_placement = _update_placement_from_full_gate(placement, summary)
        _write_json_atomically(summary, evidence_root / FULL_GATE_SUMMARY.name)
        _write_json_atomically(updated_placement, placement_path)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    lock_path.unlink(missing_ok=True)
    return validate_full_candidate_summary(summary, updated_placement, evidence_root)


def _exact_keys(value: Any, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _sha256(value: Any, prefix: bool = False) -> bool:
    pattern = r"sha256:[0-9a-f]{64}" if prefix else r"[0-9a-f]{64}"
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _bounded_int(value: Any, *, allow_zero: bool = True) -> bool:
    minimum = 0 if allow_zero else 1
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= MAX_BYTES


def pct_at_most(used: Any, total: Any, limit: Any) -> bool:
    """Compare raw integer counters without floats, rounding, or bool coercion."""
    return (
        _bounded_int(used)
        and _bounded_int(total, allow_zero=False)
        and _bounded_int(limit)
        and limit <= 100
        and used <= total
        and used * 100 <= total * limit
    )


def checked_add_bytes(*values: Any) -> int:
    total = 0
    for value in values:
        if not _bounded_int(value):
            raise ValueError("invalid byte counter")
        if total > MAX_BYTES - value:
            raise ValueError("byte counter overflow")
        total += value
    return total


def validate_capacity_policy(
    payload: dict[str, Any], source: str = "modules/rustdesk-fleet/contracts/capacity-policy.json"
) -> CheckResult:
    errors: list[str] = []
    expected_keys = {
        "schema_version",
        "workstream",
        "pre_disk_pct_max",
        "post_disk_pct_max",
        "inode_pct_max",
        "observation_max_age_seconds",
        "same_mount_required",
        "zero_or_unset_is_blocked",
        "reservations",
        "still_unmaterialized_policy",
        "backup_a_retention",
        "backup_b_retention",
        "remediation_policy",
        "zero_cleanup_candidates",
        "bounded_full_gate_write_allowlist",
        "bounded_writes_require_capacity_pass",
        "destructive_storage_mutation_default",
        "approval",
    }
    if not _exact_keys(payload, expected_keys):
        return _check_result("P52-CAPACITY-001", "FAIL", ["contract-shape"], source)
    if payload.get("schema_version") != 1 or payload.get("workstream") != "rustdesk-fleet":
        errors.append("contract-shape")
    if (payload.get("pre_disk_pct_max"), payload.get("post_disk_pct_max"), payload.get("inode_pct_max")) != (
        78,
        80,
        80,
    ):
        errors.append("threshold-drift")
    if not _bounded_int(payload.get("observation_max_age_seconds"), allow_zero=False):
        errors.append("observation-ttl")
    if payload.get("same_mount_required") is not True or payload.get("zero_or_unset_is_blocked") is not True:
        errors.append("fail-closed-policy-drift")

    reservations = payload.get("reservations")
    if not _exact_keys(reservations, set(CAPACITY_RESERVATION_KEYS)):
        errors.append("contract-shape")
        reservations = reservations if isinstance(reservations, dict) else {}
    if any(not _bounded_int(reservations.get(key), allow_zero=False) for key in CAPACITY_RESERVATION_KEYS):
        errors.append("invalid-reservation")
    expected_approved = {
        "combined_daily_log_budget_bytes": 134_217_728,
        "log_retention_days": 30,
        "log_reserve_30d_bytes": 4_026_531_840,
        "state_growth_budget_bytes": 4_294_967_296,
        "backup_a_bytes": 4_294_967_296,
        "backup_b_bytes": 4_294_967_296,
    }
    if any(reservations.get(key) != value for key, value in expected_approved.items()):
        errors.append("approved-reservation-drift")
    if reservations.get("combined_daily_log_budget_bytes", 0) * reservations.get(
        "log_retention_days", 0
    ) != reservations.get("log_reserve_30d_bytes"):
        errors.append("log-reservation-reconciliation")
    if payload.get("still_unmaterialized_policy") != list(COUNTED_RESERVATION_KEYS):
        errors.append("unmaterialized-policy-drift")

    expected_retention = {
        "retain_until": "phase57-pass-plus-30-days",
        "deletion_requires_new_explicit_approval": True,
    }
    for key, destination in (
        ("backup_a_retention", "candidate-local"),
        ("backup_b_retention", "modules/fleet-backup:gdrive"),
    ):
        retention = payload.get(key)
        if not isinstance(retention, dict) or retention != {"destination": destination, **expected_retention}:
            errors.append("backup-retention-drift")
    if payload.get("remediation_policy") != "none":
        errors.append("remediation-authority-drift")
    if payload.get("zero_cleanup_candidates") != ["atius-srv-2", "atius-srv-3"]:
        errors.append("zero-cleanup-candidate-drift")
    if payload.get("bounded_full_gate_write_allowlist") != list(BOUNDED_FULL_GATE_WRITES):
        errors.append("bounded-write-allowlist-drift")
    if payload.get("bounded_writes_require_capacity_pass") is not True:
        errors.append("bounded-write-precondition-drift")
    if payload.get("destructive_storage_mutation_default") != "blocked":
        errors.append("destructive-mutation-policy-drift")

    approval = payload.get("approval")
    if not isinstance(approval, dict) or set(approval) != {
        "status",
        "accountable",
        "approved_at",
        "source_path",
        "source_sha256",
    }:
        errors.append("approval-shape")
    elif (
        approval.get("status") != "approved"
        or approval.get("accountable") != "Giovanni Muniz"
        or approval.get("approved_at") != "2026-07-22T00:51:46Z"
        or approval.get("source_path")
        != ".planning/workstreams/rustdesk-fleet/phases/52-supply-chain-capacity-and-recoverable-placement/52-OPERATIONAL-DECISIONS.md"
        or not _sha256(approval.get("source_sha256"))
    ):
        errors.append("approval-drift")
    return _check_result("P52-CAPACITY-001", "PASS" if not errors else "FAIL", errors, source)


def _raw_counter_errors(sample: Any) -> list[str]:
    if not isinstance(sample, dict):
        return ["raw-counter-shape"]
    required_strings = (
        "observed_at",
        "hostname",
        "architecture",
        "filesystem_source",
        "mount_point",
        "podman_graphroot",
        "podman_version",
        "resource_wrapper",
        "resource_profile",
        "command_version",
    )
    required_ints = (
        "total_bytes",
        "used_bytes",
        "available_bytes",
        "inode_total",
        "inode_used",
        "inode_available",
    )
    errors: list[str] = []
    if any(not isinstance(sample.get(key), str) or not sample.get(key) for key in required_strings):
        errors.append("raw-counter-shape")
    if any(not _bounded_int(sample.get(key)) for key in required_ints):
        errors.append("raw-counter-shape")
    if sample.get("read_only") is not True or sample.get("mutation_performed") is not False:
        errors.append("observation-mutation")
    if not errors:
        if sample["used_bytes"] > sample["total_bytes"] or sample["available_bytes"] > sample["total_bytes"]:
            errors.append("byte-counter-reconciliation")
        if sample["inode_used"] + sample["inode_available"] != sample["inode_total"]:
            errors.append("inode-counter-reconciliation")
        if sample["total_bytes"] <= 0 or sample["inode_total"] <= 0:
            errors.append("raw-counter-shape")
    return errors


def _is_current(timestamp: Any, max_age: int, now: datetime | None = None) -> bool:
    parsed = _parse_utc(timestamp)
    current = now or datetime.now(timezone.utc)
    if parsed is None:
        return False
    age = (current - parsed).total_seconds()
    return -300 <= age <= max_age


def derive_candidate_capacity(
    sample: dict[str, Any], policy: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    reservations = policy["reservations"]
    try:
        required = checked_add_bytes(*(reservations[key] for key in COUNTED_RESERVATION_KEYS))
    except (KeyError, ValueError):
        return {
            "status": "NO-GO",
            "pre_disk_ok": False,
            "inode_ok": False,
            "projected_post_ok": False,
            "headroom_ok": False,
            "capacity_finalize_status": "NO-GO",
            "required_incremental_bytes": None,
            "still_unmaterialized_reservations": None,
        }
    shape_ok = not _raw_counter_errors(sample)
    current = shape_ok and _is_current(sample.get("observed_at"), policy["observation_max_age_seconds"], now)
    pre_ok = shape_ok and pct_at_most(sample["used_bytes"], sample["total_bytes"], policy["pre_disk_pct_max"])
    inode_ok = shape_ok and pct_at_most(sample["inode_used"], sample["inode_total"], policy["inode_pct_max"])
    try:
        projected_used = checked_add_bytes(sample.get("used_bytes"), required)
    except ValueError:
        projected_used = None
    projected_ok = projected_used is not None and pct_at_most(
        projected_used, sample.get("total_bytes"), policy["post_disk_pct_max"]
    )
    headroom_ok = shape_ok and sample["available_bytes"] >= required

    finalize_status = "PENDING"
    still_unmaterialized = required
    finalize = sample.get("capacity_finalize")
    if finalize is not None:
        finalize_errors = _raw_counter_errors(finalize)
        if not _is_current(finalize.get("observed_at"), policy["observation_max_age_seconds"], now):
            finalize_errors.append("stale-finalize-observation")
        if finalize.get("filesystem_source") != sample.get("filesystem_source") or finalize.get(
            "mount_point"
        ) != sample.get("mount_point"):
            finalize_errors.append("finalize-mount-mismatch")
        if finalize.get("total_bytes") != sample.get("total_bytes"):
            finalize_errors.append("finalize-total-mismatch")
        actual_a = finalize.get("actual_backup_a_bytes")
        actual_b = finalize.get("actual_backup_b_bytes")
        if not _bounded_int(actual_a, allow_zero=False) or actual_a > reservations["backup_a_bytes"]:
            finalize_errors.append("backup-a-reserve-exceeded")
        if not _bounded_int(actual_b, allow_zero=False) or actual_b > reservations["backup_b_bytes"]:
            finalize_errors.append("backup-b-reserve-exceeded")
        materialized = finalize.get("materialized_reservations")
        if not isinstance(materialized, dict) or set(materialized) - set(MATERIALIZABLE_RESERVATION_KEYS):
            finalize_errors.append("materialized-reservation-shape")
            materialized = {}
        for key, value in materialized.items():
            if not _bounded_int(value, allow_zero=False) or value > reservations[key]:
                finalize_errors.append("materialized-reservation-mismatch")
        if materialized.get("backup_a_bytes") != actual_a or materialized.get("backup_b_bytes") != actual_b:
            finalize_errors.append("backup-materialized-mismatch")
        try:
            still_unmaterialized = checked_add_bytes(
                *(reservations[key] for key in COUNTED_RESERVATION_KEYS if key not in materialized)
            )
            final_projected = checked_add_bytes(finalize.get("used_bytes"), still_unmaterialized)
        except ValueError:
            finalize_errors.append("finalize-overflow")
            final_projected = None
        if final_projected is None or not pct_at_most(
            final_projected, finalize.get("total_bytes"), policy["post_disk_pct_max"]
        ):
            finalize_errors.append("finalize-post-threshold")
        if not pct_at_most(finalize.get("inode_used"), finalize.get("inode_total"), policy["inode_pct_max"]):
            finalize_errors.append("finalize-inode-threshold")
        finalize_status = "PASS" if not finalize_errors else "NO-GO"

    status = "PASS" if all((current, pre_ok, inode_ok, projected_ok, headroom_ok)) else "NO-GO"
    if finalize is not None and finalize_status != "PASS":
        status = "NO-GO"
    return {
        "status": status,
        "pre_disk_ok": pre_ok,
        "inode_ok": inode_ok,
        "projected_post_ok": projected_ok,
        "headroom_ok": headroom_ok,
        "capacity_finalize_status": finalize_status,
        "required_incremental_bytes": required,
        "still_unmaterialized_reservations": still_unmaterialized,
    }


def validate_capacity_observation(
    sample: dict[str, Any],
    policy: dict[str, Any],
    source: str = "capacity-observation",
    *,
    now: datetime | None = None,
) -> CheckResult:
    errors = _raw_counter_errors(sample)
    blocked: list[str] = []
    if not _is_current(sample.get("observed_at"), policy.get("observation_max_age_seconds", 0), now):
        blocked.append("stale-observation")
    finalize = sample.get("capacity_finalize") if isinstance(sample, dict) else None
    if isinstance(finalize, dict):
        if finalize.get("filesystem_source") != sample.get("filesystem_source") or finalize.get(
            "mount_point"
        ) != sample.get("mount_point"):
            errors.append("finalize-mount-mismatch")
        derived = derive_candidate_capacity(sample, policy, now=now)
        if derived["capacity_finalize_status"] != "PASS":
            blocked.append("capacity-finalize-no-go")
    elif isinstance(sample, dict) and any(key in sample for key in ("disk_percent", "inode_percent")):
        errors.append("raw-counter-shape")
    if not errors and not blocked and derive_candidate_capacity(sample, policy, now=now)["status"] != "PASS":
        blocked.append("capacity-no-go")
    status = "FAIL" if errors else "BLOCKED" if blocked else "PASS"
    return _check_result("P52-CAPACITY-001", status, errors + blocked, source)


def enforce_zero_cleanup(candidate: str, action: str) -> None:
    """Reject every action not explicitly allowed by the read-only routing preflight."""
    if candidate not in CANDIDATES:
        raise ValueError("unknown capacity candidate")
    if action not in READ_ONLY_PREFLIGHT_ACTIONS:
        raise ValueError("action is forbidden by the read-only capacity preflight")


def build_capacity_probe_command(candidate: str) -> list[str]:
    """Construct the bounded SSH argv only after the action-class gate passes."""
    enforce_zero_cleanup(candidate, "capacity-sample")
    return [
        "ssh",
        "-n",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        SSH_ALIASES[candidate],
        f"python3 -c {shlex.quote(REMOTE_CAPACITY_SCRIPT)}",
    ]


def collect_capacity_sample(candidate: str) -> dict[str, Any]:
    """Collect one structured sample without invoking a shell or a remote write action."""
    command = build_capacity_probe_command(candidate)
    completed = subprocess.run(command, text=True, capture_output=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise ValueError(f"read-only capacity probe failed for {candidate}")
    try:
        sample = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise ValueError(f"invalid capacity probe output for {candidate}") from None
    errors = _raw_counter_errors(sample)
    if errors:
        raise ValueError(f"invalid capacity sample for {candidate}: {','.join(sorted(set(errors)))}")
    return sample


def _capacity_findings(results: list[dict[str, Any]]) -> list[str]:
    findings: set[str] = set()
    if any(not item["pre_disk_ok"] for item in results):
        findings.add("pre-disk-threshold-exceeded")
    if any(not item["inode_ok"] for item in results):
        findings.add("inode-threshold-exceeded")
    if any(not item["projected_post_ok"] for item in results):
        findings.add("projected-post-threshold-exceeded")
    if any(not item["headroom_ok"] for item in results):
        findings.add("insufficient-available-bytes")
    if not findings:
        findings.add("full-candidate-gate-pending")
    return sorted(findings)


def evaluate_capacity_chain(
    samples_by_candidate: dict[str, list[dict[str, Any]]],
    policy: dict[str, Any],
    *,
    decision_source_digest: str,
    supply_digest: str,
    persisted_predecessors: set[str],
) -> dict[str, Any]:
    """Derive the strict serial preflight without turning capacity into placement."""
    if not _sha256(decision_source_digest) or not _sha256(supply_digest):
        raise ValueError("capacity chain requires current input digests")
    attempts: list[dict[str, Any]] = []
    eligible: str | None = None
    for index, candidate in enumerate(CANDIDATES):
        samples = samples_by_candidate.get(candidate)
        if samples is None:
            continue
        if index > 0 and CANDIDATES[index - 1] not in persisted_predecessors:
            raise ValueError("persisted predecessor NO-GO is required before fallback")
        if len(samples) != 2:
            raise ValueError("exactly two current samples are required per candidate")
        if samples[0].get("filesystem_source") != samples[1].get("filesystem_source") or samples[0].get(
            "mount_point"
        ) != samples[1].get("mount_point") or samples[0].get("total_bytes") != samples[1].get("total_bytes"):
            raise ValueError("capacity samples do not describe the same current mount")
        results = [derive_candidate_capacity(sample, policy) for sample in samples]
        preliminary = "NO-GO" if any(item["status"] == "NO-GO" for item in results) else "PRELIMINARY_ELIGIBLE"
        if eligible is not None:
            raise ValueError("candidate evaluated after preliminary eligibility")
        if preliminary == "PRELIMINARY_ELIGIBLE":
            eligible = candidate
        attempts.append(
            {
                "candidate": candidate,
                "ssh_alias": SSH_ALIASES[candidate],
                "predecessor": CANDIDATES[index - 1] if index else None,
                "predecessor_status": "NO-GO" if index else "NOT_APPLICABLE",
                "samples": samples,
                "calculations": results,
                "reservations": policy["reservations"],
                "decision_source_digest": decision_source_digest,
                "supply_digest": supply_digest,
                "read_only": True,
                "mutation_performed": False,
                "preliminary_verdict": preliminary,
                "findings": _capacity_findings(results),
                "horistic_colocation": (
                    {
                        "client_colocation": True,
                        "server_resource_domain": "rustdesk-server-horistic-srv",
                        "future_client_resource_domain": "rustdesk-client-horistic-srv",
                        "phase52_review_status": "PASS",
                        "phase53_review": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
                        "phase54_review": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
                        "phase57_review": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
                        "independent_dr_claimed": False,
                    }
                    if candidate == "horistic-srv"
                    else None
                ),
            }
        )
    return {
        "schema_version": 1,
        "phase": 52,
        "workstream": "rustdesk-fleet",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "attempt_order": [item["candidate"] for item in attempts],
        "attempts": attempts,
        "decision_source_digest": decision_source_digest,
        "supply_digest": supply_digest,
        "capacity_eligible_candidate": eligible,
        "selected_candidate": None,
        "unmaterialized_reservation_terms": list(COUNTED_RESERVATION_KEYS),
        "pending_stages": [
            "vault",
            "backup",
            "restore",
            "capacity_finalize",
            "rollback",
            "topology-security",
        ],
        "read_only": True,
        "mutation_performed": False,
        "windows_install_performed": False,
        "windows_access_proven": False,
        "overall_status": "BLOCKED",
    }


def _candidate_evidence(attempt: dict[str, Any], generated_at: str) -> dict[str, Any]:
    candidate = attempt["candidate"]
    return {
        "schema_version": 1,
        "phase": 52,
        "workstream": "rustdesk-fleet",
        "evidence_id": f"P52-EV-CAPACITY-{candidate.upper()}",
        "generated_at": generated_at,
        **attempt,
    }


def _apply_capacity_chain_to_placement(
    placement: dict[str, Any], chain: dict[str, Any]
) -> dict[str, Any]:
    updated = json.loads(json.dumps(placement))
    attempts = {item["candidate"]: item for item in chain["attempts"]}
    for row in updated["candidates"]:
        attempt = attempts.get(row["candidate"])
        if attempt is None:
            continue
        row["evaluated"] = True
        row["supply_status"] = "PASS"
        row["capacity_status"] = "NO-GO" if attempt["preliminary_verdict"] == "NO-GO" else "PASS"
        for field in (
            "vault_status",
            "backup_status",
            "restore_status",
            "capacity_finalize_status",
            "rollback_status",
            "topology_security_status",
        ):
            row[field] = "PENDING"
        row["evidence_ids"] = [f"P52-EV-CAPACITY-{row['candidate'].upper()}"]
        row["verdict"] = _candidate_verdict(row)
    updated["selected_candidate"] = None
    updated["overall_status"] = "BLOCKED"
    updated["windows_install_performed"] = False
    updated["windows_access_proven"] = False
    updated["cold_standby_claimed"] = False
    return updated


def validate_capacity_live_summary(
    chain: dict[str, Any],
    policy: dict[str, Any],
    placement: dict[str, Any],
    repo: Path,
    *,
    now: datetime | None = None,
) -> CheckResult:
    fail: list[str] = []
    blocked: list[str] = []
    reference_time = _parse_utc(chain.get("generated_at"))
    if reference_time is None:
        fail.append("generated-at-shape")
    if chain.get("attempt_order") != [item.get("candidate") for item in chain.get("attempts", [])]:
        fail.append("candidate-order-drift")
    if chain.get("attempt_order") != list(CANDIDATES[: len(chain.get("attempt_order", []))]):
        fail.append("candidate-order-drift")
    if (
        chain.get("selected_candidate") is not None
        or chain.get("overall_status") != "BLOCKED"
        or chain.get("mutation_performed") is not False
        or chain.get("read_only") is not True
        or chain.get("windows_install_performed") is not False
        or chain.get("windows_access_proven") is not False
    ):
        fail.append("preflight-boundary-drift")
    if chain.get("decision_source_digest") != _sha256_file(repo / OPERATIONAL_DECISIONS):
        blocked.append("approval-source-drift")
    if chain.get("supply_digest") != _sha256_file(repo / SUPPLY_OBSERVATION):
        blocked.append("supply-evidence-drift")

    eligible: str | None = None
    for index, attempt in enumerate(chain.get("attempts", [])):
        samples = attempt.get("samples")
        if not isinstance(samples, list) or len(samples) != 2:
            fail.append("sample-cardinality")
            continue
        for sample in samples:
            sample_result = validate_capacity_observation(sample, policy, now=now)
            if sample_result.status == "FAIL":
                fail.extend(item.category for item in sample_result.findings)
            elif "stale-observation" in {item.category for item in sample_result.findings}:
                if "stale-observation" not in blocked:
                    blocked.append("stale-observation")
        derived = [derive_candidate_capacity(sample, policy, now=reference_time) for sample in samples]
        expected = "NO-GO" if any(item["status"] == "NO-GO" for item in derived) else "PRELIMINARY_ELIGIBLE"
        if attempt.get("calculations") != derived or attempt.get("preliminary_verdict") != expected:
            fail.append("stored-verdict-drift")
        if index and chain["attempts"][index - 1].get("preliminary_verdict") != "NO-GO":
            fail.append("candidate-order-bypass")
        if expected == "PRELIMINARY_ELIGIBLE" and eligible is None:
            eligible = attempt["candidate"]
    if chain.get("capacity_eligible_candidate") != eligible:
        fail.append("stored-verdict-drift")

    placement_result = validate_placement_decision(placement)
    if placement_result.status == "FAIL":
        fail.extend(item.category for item in placement_result.findings)
    if not fail:
        blocked.append("full-gate-pending")
    return _check_result(
        "P52-CAPACITY-LIVE-001",
        "FAIL" if fail else "BLOCKED",
        fail + blocked,
        CAPACITY_SUMMARY.as_posix(),
    )


def run_capacity_live(repo: Path, evidence_dir: Path) -> CheckResult:
    """Execute the serial read-only routing chain and persist each reached verdict immediately."""
    policy_path = validate_repo_path(repo, repo / CAPACITY_POLICY)
    placement_path = validate_repo_path(repo, repo / PLACEMENT_DECISION)
    supply_path = validate_repo_path(repo, repo / SUPPLY_OBSERVATION)
    decision_path = validate_repo_path(repo, repo / OPERATIONAL_DECISIONS)
    policy = load_json_strict(policy_path)
    placement = load_json_strict(placement_path)
    supply = load_json_strict(supply_path)
    if validate_capacity_policy(policy).status != "PASS":
        raise ValueError("capacity policy is not approved")
    if validate_supply_observation(supply, load_json_strict(repo / SUPPLY_CONTRACT), repo=repo).status != "PASS":
        raise ValueError("supply evidence is not current PASS")
    decision_digest = _sha256_file(decision_path)
    if policy["approval"]["source_sha256"] != decision_digest:
        raise ValueError("capacity approval source digest drift")
    supply_digest = _sha256_file(supply_path)

    samples_by_candidate: dict[str, list[dict[str, Any]]] = {}
    persisted_predecessors: set[str] = set()
    chain: dict[str, Any] | None = None
    evidence_root = validate_repo_path(repo, repo / evidence_dir)
    for candidate in CANDIDATES:
        samples_by_candidate[candidate] = [collect_capacity_sample(candidate), collect_capacity_sample(candidate)]
        chain = evaluate_capacity_chain(
            samples_by_candidate,
            policy,
            decision_source_digest=decision_digest,
            supply_digest=supply_digest,
            persisted_predecessors=persisted_predecessors,
        )
        attempt = chain["attempts"][-1]
        evidence_path = validate_repo_path(repo, evidence_root / CAPACITY_EVIDENCE_NAMES[candidate])
        _write_json_atomically(_candidate_evidence(attempt, chain["generated_at"]), evidence_path)
        if attempt["preliminary_verdict"] == "NO-GO":
            persisted_predecessors.add(candidate)
            continue
        break
    if chain is None:
        raise ValueError("capacity chain produced no evidence")
    chain["routing"] = [
        {
            "candidate": candidate,
            "status": (
                next(item["preliminary_verdict"] for item in chain["attempts"] if item["candidate"] == candidate)
                if candidate in chain["attempt_order"]
                else "NOT_NEEDED_AFTER_PRELIMINARY_ELIGIBILITY"
            ),
        }
        for candidate in CANDIDATES
    ]
    updated_placement = _apply_capacity_chain_to_placement(placement, chain)
    summary_path = validate_repo_path(repo, evidence_root / CAPACITY_SUMMARY.name)
    _write_json_atomically(chain, summary_path)
    _write_json_atomically(updated_placement, placement_path)
    return validate_capacity_live_summary(chain, policy, updated_placement, repo)


def _candidate_verdict(candidate: dict[str, Any]) -> str:
    if candidate.get("evaluated") is not True:
        return "PENDING"
    stages = [candidate.get(field) for field in STAGE_FIELDS]
    if stages and all(status == "PASS" for status in stages):
        return "PASS"
    if any(status in {"NO-GO", "FAIL", "BLOCKED"} for status in stages):
        return "NO-GO"
    return "PENDING"


def _horistic_contract_valid(candidate: Any) -> bool:
    if not isinstance(candidate, dict) or candidate.get("client_colocation") is not True:
        return False
    for field in (
        "server_client_resource_domains",
        "server_client_evidence_domains",
        "server_client_rollback_domains",
    ):
        domains = candidate.get(field)
        if (
            not isinstance(domains, dict)
            or set(domains) != {"server", "client"}
            or not all(isinstance(value, str) and value for value in domains.values())
            or domains["server"] == domains["client"]
        ):
            return False
    return all(candidate.get(field) is True for field in (
        "phase53_review_required",
        "phase54_review_required",
        "phase57_review_required",
    ))


def derive_placement(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list) or len(candidates) != len(CANDIDATES):
        return {"selected_candidate": None, "overall_status": "BLOCKED", "verdicts": [], "errors": ["candidate-shape"]}
    verdicts = [_candidate_verdict(item) if isinstance(item, dict) else "PENDING" for item in candidates]
    errors: list[str] = []
    selected: str | None = None
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or candidate.get("candidate") != CANDIDATES[index]:
            errors.append("candidate-shape")
            continue
        if candidate.get("evaluated") is True and any(verdict != "NO-GO" for verdict in verdicts[:index]):
            errors.append("candidate-order-bypass")
        if verdicts[index] == "PASS" and selected is None and all(
            verdict == "NO-GO" for verdict in verdicts[:index]
        ):
            selected = CANDIDATES[index]
        if selected is not None and any(
            isinstance(later, dict) and later.get("evaluated") is True for later in candidates[index + 1 :]
        ):
            errors.append("candidate-order-bypass")
    if selected == "horistic-srv" and not _horistic_contract_valid(candidates[2]):
        errors.append("horistic-colocation-contract")
        selected = None
    return {
        "selected_candidate": selected,
        "overall_status": "PASS" if selected is not None and not errors else "BLOCKED",
        "verdicts": verdicts,
        "errors": sorted(set(errors)),
    }


def validate_placement_decision(
    payload: dict[str, Any], source: str = "modules/rustdesk-fleet/contracts/placement-decision.json"
) -> CheckResult:
    errors: list[str] = []
    blocked: list[str] = []
    expected_top = {
        "schema_version",
        "workstream",
        "candidate_order",
        "candidates",
        "selected_candidate",
        "overall_status",
        "windows_install_performed",
        "windows_access_proven",
        "cold_standby_claimed",
    }
    if not _exact_keys(payload, expected_top):
        return _check_result("P52-PLACEMENT-001", "FAIL", ["contract-shape"], source)
    if payload.get("schema_version") != 1 or payload.get("workstream") != "rustdesk-fleet" or payload.get(
        "candidate_order"
    ) != list(CANDIDATES):
        errors.append("contract-shape")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        errors.append("candidate-shape")
        candidates = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or candidate.get("candidate") != CANDIDATES[index]:
            errors.append("candidate-shape")
            continue
        base_keys = {"candidate", "evaluated", *STAGE_FIELDS, "evidence_ids", "verdict"}
        horistic_keys = {
            "client_colocation",
            "server_client_resource_domains",
            "server_client_evidence_domains",
            "server_client_rollback_domains",
            "phase53_review_required",
            "phase54_review_required",
            "phase57_review_required",
        }
        if set(candidate) != (base_keys | horistic_keys if index == 2 else base_keys):
            errors.append("candidate-shape" if index < 2 else "horistic-colocation-contract")
        if not isinstance(candidate.get("evaluated"), bool):
            errors.append("candidate-shape")
        if any(
            candidate.get(field)
            not in {
                "PASS",
                "NO-GO",
                "FAIL",
                "BLOCKED",
                "PENDING",
                "SKIPPED_BY_GATE",
                "SKIPPED_DUE_TO_GATE",
            }
            for field in STAGE_FIELDS
        ):
            errors.append("stage-status-shape")
        if candidate.get("verdict") != _candidate_verdict(candidate):
            errors.append("stored-verdict-drift")
        if not isinstance(candidate.get("evidence_ids"), list) or not all(
            isinstance(item, str) and item for item in candidate.get("evidence_ids", [])
        ):
            errors.append("evidence-id-shape")
    if len(candidates) == 3 and not _horistic_contract_valid(candidates[2]):
        errors.append("horistic-colocation-contract")
    derived = derive_placement(payload)
    errors.extend(derived["errors"])
    if payload.get("selected_candidate") != derived["selected_candidate"] or payload.get(
        "overall_status"
    ) != derived["overall_status"]:
        errors.append("stored-verdict-drift")
    if payload.get("windows_install_performed") is not False or payload.get("windows_access_proven") is not False:
        errors.append("windows-phase-boundary")
    if payload.get("cold_standby_claimed") is not False:
        errors.append("premature-standby-claim")
    if not errors and derived["overall_status"] != "PASS":
        blocked.append("placement-pending")
    status = "FAIL" if errors else "BLOCKED" if blocked else "PASS"
    return _check_result("P52-PLACEMENT-001", status, errors + blocked, source)


def _proposal_capacity_verdict(
    samples: list[dict[str, Any]], policy: dict[str, Any], *, now: datetime | None = None
) -> str:
    results = [derive_candidate_capacity(sample, policy, now=now) for sample in samples]
    return "NO-GO" if any(item["status"] == "NO-GO" for item in results) else "FULL-GATE-PENDING"


def validate_capacity_proposal(
    proposal: dict[str, Any],
    policy: dict[str, Any],
    repo: Path,
    source: str = "modules/rustdesk-fleet/evidence/phase52/capacity-proposal.json",
) -> CheckResult:
    fail: list[str] = []
    blocked: list[str] = []
    expected_keys = {
        "schema_version",
        "phase",
        "workstream",
        "generated_at",
        "input_digests",
        "approval",
        "candidate_order",
        "candidates",
        "read_only",
        "mutation_performed",
        "remediation_policy",
        "selected_candidate",
        "overall_status",
        "windows_install_performed",
        "windows_access_proven",
        "findings",
    }
    if not _exact_keys(proposal, expected_keys):
        return _check_result("P52-CAPACITY-001", "FAIL", ["proposal-shape"], source)
    if proposal.get("schema_version") != 1 or proposal.get("phase") != 52 or proposal.get(
        "workstream"
    ) != "rustdesk-fleet":
        fail.append("proposal-shape")
    if not _is_current(proposal.get("generated_at"), policy.get("observation_max_age_seconds", 0)):
        blocked.append("stale-proposal")
    if proposal.get("read_only") is not True or proposal.get("mutation_performed") is not False:
        fail.append("proposal-mutation")
    if proposal.get("remediation_policy") != "none":
        fail.append("remediation-authority-drift")
    if proposal.get("selected_candidate") is not None or proposal.get("overall_status") != "BLOCKED":
        fail.append("stored-verdict-drift")
    if proposal.get("windows_install_performed") is not False or proposal.get("windows_access_proven") is not False:
        fail.append("windows-phase-boundary")
    if proposal.get("findings") != ["full-candidate-gate-not-run"]:
        fail.append("proposal-finding-drift")
    if proposal.get("candidate_order") != list(CANDIDATES):
        fail.append("candidate-order-drift")

    root = repo.resolve()
    expected_inputs = collect_input_digests(root, [CAPACITY_POLICY, PLACEMENT_DECISION, OPERATIONAL_DECISIONS])
    if proposal.get("input_digests") != expected_inputs:
        blocked.append("stale-input-digest")
    approval = proposal.get("approval")
    expected_approval = policy.get("approval")
    if not isinstance(approval, dict) or approval != expected_approval:
        blocked.append("approval-contract-drift")
    if isinstance(approval, dict):
        try:
            approval_path = validate_repo_path(root, root / approval["source_path"])
            if not approval_path.is_file() or _sha256_file(approval_path) != approval["source_sha256"]:
                blocked.append("approval-source-drift")
        except (KeyError, ValueError):
            blocked.append("approval-source-drift")
    else:
        blocked.append("approval-source-drift")

    aliases = {
        "atius-srv-2": "atius-srv-2-direct",
        "atius-srv-3": "atius-srv-3-direct",
        "horistic-srv": "horistic-srv-1",
    }
    hostnames = {
        "atius-srv-2": {"atius-srv-2", "atius-srv-2.atius.internal"},
        "atius-srv-3": {"atius-srv-3", "atius-srv-3.atius.internal"},
        "horistic-srv": {"horistic-srv", "horistic-srv.atius.internal"},
    }
    candidates = proposal.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        fail.append("candidate-shape")
        candidates = []
    proposal_reference_time = _parse_utc(proposal.get("generated_at"))
    for index, candidate in enumerate(candidates):
        expected_candidate = CANDIDATES[index]
        if not _exact_keys(candidate, {"candidate", "ssh_alias", "samples", "capacity_verdict", "latest_capacity"}):
            fail.append("candidate-shape")
            continue
        if candidate.get("candidate") != expected_candidate or candidate.get("ssh_alias") != aliases[expected_candidate]:
            fail.append("candidate-order-drift")
        samples = candidate.get("samples")
        if not isinstance(samples, list) or len(samples) != 2:
            fail.append("sample-cardinality")
            continue
        for sample_index, sample in enumerate(samples):
            if not isinstance(sample, dict) or sample.get("hostname") not in hostnames[expected_candidate]:
                fail.append("candidate-hostname-drift")
                continue
            sample_result = validate_capacity_observation(
                sample, policy, f"{source}:candidates[{index}].samples[{sample_index}]"
            )
            if sample_result.status == "FAIL":
                fail.extend(item.category for item in sample_result.findings)
            elif "stale-observation" in {item.category for item in sample_result.findings}:
                blocked.append("stale-observation")
        derived_verdict = _proposal_capacity_verdict(samples, policy, now=proposal_reference_time)
        latest = derive_candidate_capacity(samples[-1], policy, now=proposal_reference_time)
        if candidate.get("capacity_verdict") != derived_verdict or candidate.get("latest_capacity") != latest:
            fail.append("stored-verdict-drift")
    if not fail:
        blocked.append("full-gate-pending")
    status = "FAIL" if fail else "BLOCKED"
    return _check_result("P52-CAPACITY-001", status, fail + blocked, source)


def validate_supply_contract(
    payload: dict[str, Any], source: str = "modules/rustdesk-fleet/contracts/supply-chain.json"
) -> CheckResult:
    errors: list[str] = []
    if not _exact_keys(payload, {"schema_version", "workstream", "policy", "server", "clients"}):
        return _result("FAIL", ["contract-shape"], source)
    if payload.get("schema_version") != 1 or payload.get("workstream") != "rustdesk-fleet":
        errors.append("contract-shape")

    policy = payload.get("policy")
    if not _exact_keys(
        policy,
        {
            "automatic_pin_refresh",
            "build_on_target",
            "candidate_admission_performed",
            "managed_cache_root",
            "observation_ttl_seconds",
            "windows_install_performed",
        },
    ):
        errors.append("contract-shape")
        policy = policy if isinstance(policy, dict) else {}
    if policy.get("automatic_pin_refresh") is not False:
        errors.append("automatic-pin-refresh")
    if policy.get("build_on_target") is not False:
        errors.append("target-build-enabled")
    if policy.get("candidate_admission_performed") is not False:
        errors.append("candidate-admission-claimed")
    if policy.get("windows_install_performed") is not False:
        errors.append("windows-install-attempt")
    if not _positive_int(policy.get("observation_ttl_seconds")):
        errors.append("invalid-observation-ttl")
    cache_root = policy.get("managed_cache_root")
    if not isinstance(cache_root, str) or not cache_root.startswith("/") or "/GitHub/omni-srv-admin" in cache_root:
        errors.append("managed-cache-inside-repo")

    server = payload.get("server")
    if not _exact_keys(
        server,
        {
            "version",
            "tag",
            "commit",
            "git_repository",
            "release_api_url",
            "candidates",
            "classic_image",
            "release_zip",
        },
    ):
        errors.append("contract-shape")
        server = server if isinstance(server, dict) else {}
    if server.get("version") != "1.1.15" or server.get("tag") != "1.1.15":
        errors.append("mutable-reference" if server.get("tag") == "latest" else "server-version-drift")
    if server.get("commit") != SERVER_COMMIT:
        errors.append("server-commit-drift")
    if server.get("git_repository") != "https://github.com/rustdesk/rustdesk-server.git":
        errors.append("server-source-drift")
    if server.get("release_api_url") != "https://api.github.com/repos/rustdesk/rustdesk-server/releases/tags/1.1.15":
        errors.append("server-source-drift")

    image = server.get("classic_image")
    image_keys = {
        "repository",
        "tag_reference",
        "immutable_reference",
        "registry_tag_api_url",
        "multiarch_digest",
        "linux_arm64_digest",
        "architecture",
        "os",
        "cache_path",
        "phase52_action",
        "install_phase",
    }
    if not _exact_keys(image, image_keys):
        errors.append("contract-shape")
        image = image if isinstance(image, dict) else {}
    if image.get("multiarch_digest") != MULTIARCH_DIGEST or not _sha256(image.get("multiarch_digest"), True):
        errors.append("multiarch-digest-drift")
    if image.get("linux_arm64_digest") != ARM64_IMAGE_DIGEST or not _sha256(
        image.get("linux_arm64_digest"), True
    ):
        errors.append("arm64-digest-drift")
    if image.get("architecture") != "arm64" or image.get("os") != "linux":
        errors.append("server-architecture-drift")
    if image.get("immutable_reference") != f"docker.io/rustdesk/rustdesk-server@{ARM64_IMAGE_DIGEST}":
        errors.append("mutable-reference")
    if image.get("phase52_action") != "verify-and-stage" or image.get("install_phase") != 53:
        errors.append("phase-boundary-drift")

    release_zip = server.get("release_zip")
    artifact_keys = {
        "asset_name",
        "source_url",
        "sha256",
        "size_bytes",
        "architecture",
        "cache_path",
        "phase52_action",
        "install_phase",
    }
    if not _exact_keys(release_zip, artifact_keys):
        errors.append("contract-shape")
        release_zip = release_zip if isinstance(release_zip, dict) else {}
    if release_zip.get("sha256") != ZIP_SHA256 or not _sha256(release_zip.get("sha256")):
        errors.append("release-zip-checksum-drift")
    if release_zip.get("architecture") != "linux-arm64v8":
        errors.append("server-architecture-drift")
    if not _positive_int(release_zip.get("size_bytes")):
        errors.append("invalid-byte-size")

    candidates = server.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 3:
        errors.append("candidate-set-drift")
        candidates = candidates if isinstance(candidates, list) else []
    elif [item.get("host") for item in candidates if isinstance(item, dict)] != list(CANDIDATES):
        errors.append("candidate-set-drift")
    candidate_keys = {
        "host",
        "linux_arm64_digest",
        "selected",
        "client_colocation_if_selected",
        "server_identity_domain",
        "future_client_identity_domain",
    }
    for index, candidate in enumerate(candidates):
        if not _exact_keys(candidate, candidate_keys):
            errors.append("candidate-shape")
            continue
        if candidate.get("linux_arm64_digest") != ARM64_IMAGE_DIGEST:
            errors.append("candidate-artifact-drift")
        if candidate.get("selected") is not False:
            errors.append("candidate-admission-claimed")
        expected_colocation = index == 2
        if candidate.get("client_colocation_if_selected") is not expected_colocation:
            errors.append("horistic-colocation-drift")
        if candidate.get("server_identity_domain") == candidate.get("future_client_identity_domain"):
            errors.append("identity-domain-conflation")

    clients = payload.get("clients")
    if not _exact_keys(
        clients,
        {"version", "tag", "commit", "git_repository", "release_api_url", "linux_arm64_deb", "windows_x86_64_msi"},
    ):
        errors.append("contract-shape")
        clients = clients if isinstance(clients, dict) else {}
    if clients.get("version") != "1.4.9" or clients.get("tag") != "1.4.9":
        errors.append("mutable-reference" if clients.get("tag") == "latest" else "client-version-drift")
    if clients.get("commit") != CLIENT_COMMIT:
        errors.append("client-commit-drift")
    if clients.get("git_repository") != "https://github.com/rustdesk/rustdesk.git":
        errors.append("client-source-drift")
    if clients.get("release_api_url") != "https://api.github.com/repos/rustdesk/rustdesk/releases/tags/1.4.9":
        errors.append("client-source-drift")

    deb = clients.get("linux_arm64_deb")
    deb_keys = artifact_keys | {"fleet_install_phase"}
    if not _exact_keys(deb, deb_keys):
        errors.append("contract-shape")
        deb = deb if isinstance(deb, dict) else {}
    if deb.get("sha256") != DEB_SHA256 or not _sha256(deb.get("sha256")):
        errors.append("linux-deb-checksum-drift")
    if deb.get("architecture") != "arm64":
        errors.append("linux-client-architecture-drift")
    if deb.get("phase52_action") != "verify-and-stage" or deb.get("install_phase") != 54 or deb.get(
        "fleet_install_phase"
    ) != 55:
        errors.append("phase-boundary-drift")
    if not _positive_int(deb.get("size_bytes")):
        errors.append("invalid-byte-size")

    msi = clients.get("windows_x86_64_msi")
    if not _exact_keys(msi, artifact_keys):
        errors.append("contract-shape")
        msi = msi if isinstance(msi, dict) else {}
    if msi.get("sha256") != MSI_SHA256 or not _sha256(msi.get("sha256")):
        errors.append("windows-msi-checksum-drift")
    if msi.get("architecture") != "x86_64":
        errors.append("windows-client-architecture-drift")
    if msi.get("phase52_action") != "verify-and-stage" or msi.get("install_phase") != 54:
        errors.append("windows-install-attempt")
    if not _positive_int(msi.get("size_bytes")):
        errors.append("invalid-byte-size")

    for artifact in (image, release_zip, deb, msi):
        cache_path = artifact.get("cache_path") if isinstance(artifact, dict) else None
        if not isinstance(cache_path, str) or not isinstance(cache_root, str) or not cache_path.startswith(f"{cache_root}/"):
            errors.append("managed-cache-path-drift")
        source_url = artifact.get("source_url") if isinstance(artifact, dict) else None
        if source_url is not None and (not isinstance(source_url, str) or not source_url.startswith("https://github.com/rustdesk/")):
            errors.append("artifact-source-drift")

    return _result("PASS" if not errors else "FAIL", errors, source)


def validate_supply_observation(
    observation: dict[str, Any],
    contract: dict[str, Any],
    source: str = "supply-observation.json",
    *,
    repo: Path | None = None,
    allowed_cache_root: Path | None = None,
    now: datetime | None = None,
) -> CheckResult:
    fail: list[str] = []
    blocked: list[str] = []
    expected_keys = {
        "schema_version",
        "phase",
        "workstream",
        "observed_at",
        "source_urls",
        "input_digests",
        "server",
        "clients",
        "classic_image",
        "artifacts",
        "windows_install_performed",
        "candidate_admission_performed",
        "secret_material_present",
        "findings",
        "status",
    }
    if not _exact_keys(observation, expected_keys):
        return _result("FAIL", ["observation-shape"], source)
    if observation.get("schema_version") != 1 or observation.get("phase") != 52 or observation.get(
        "workstream"
    ) != "rustdesk-fleet":
        fail.append("observation-shape")

    observed_at = observation.get("observed_at")
    parsed = _parse_utc(observed_at)
    if parsed is None:
        fail.append("observation-timestamp")
    else:
        current = now or datetime.now(timezone.utc)
        age = (current - parsed).total_seconds()
        if age < -300 or age > contract["policy"]["observation_ttl_seconds"]:
            blocked.append("stale-observation")

    expected_sources = sorted(
        {
            contract["server"]["git_repository"],
            contract["server"]["release_api_url"],
            contract["server"]["classic_image"]["registry_tag_api_url"],
            contract["server"]["release_zip"]["source_url"],
            contract["clients"]["git_repository"],
            contract["clients"]["release_api_url"],
            contract["clients"]["linux_arm64_deb"]["source_url"],
            contract["clients"]["windows_x86_64_msi"]["source_url"],
        }
    )
    if observation.get("source_urls") != expected_sources:
        fail.append("official-source-drift")
    if observation.get("server") != {"tag": "1.1.15", "commit": SERVER_COMMIT}:
        fail.append("server-tag-observation-drift")
    if observation.get("clients") != {"tag": "1.4.9", "commit": CLIENT_COMMIT}:
        fail.append("client-tag-observation-drift")
    expected_image = {
        "tag": "1.1.15",
        "multiarch_digest": MULTIARCH_DIGEST,
        "linux_arm64_digest": ARM64_IMAGE_DIGEST,
        "architecture": "arm64",
        "os": "linux",
        "inspection_method": "docker-hub-platform-manifest+podman-image-inspect",
    }
    if observation.get("classic_image") != expected_image:
        fail.append("image-observation-drift")
    if observation.get("windows_install_performed") is not False:
        fail.append("windows-install-attempt")
    if observation.get("candidate_admission_performed") is not False:
        fail.append("candidate-admission-claimed")
    if observation.get("secret_material_present") is not False:
        fail.append("secret-material")
    if observation.get("findings") != []:
        fail.append("unexpected-findings")

    input_digests = observation.get("input_digests")
    if repo is not None:
        expected_inputs = collect_input_digests(repo, [SUPPLY_CONTRACT])
        if input_digests != expected_inputs:
            blocked.append("stale-input-digest")
    elif not isinstance(input_digests, list):
        fail.append("input-digest-shape")

    artifacts = observation.get("artifacts")
    if not isinstance(artifacts, list) or [item.get("kind") for item in artifacts if isinstance(item, dict)] != [
        "server-oci-archive",
        "server-release-zip",
        "linux-client-deb",
        "windows-client-msi",
    ]:
        fail.append("artifact-set-drift")
        artifacts = artifacts if isinstance(artifacts, list) else []
    expected_static = {
        "server-release-zip": (ZIP_SHA256, 5494849, "linux-arm64v8"),
        "linux-client-deb": (DEB_SHA256, 21694032, "arm64"),
        "windows-client-msi": (MSI_SHA256, 24825856, "x86_64"),
    }
    cache_root = (allowed_cache_root or Path(contract["policy"]["managed_cache_root"])).resolve()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {
            "kind",
            "source_url",
            "cache_path",
            "size_bytes",
            "sha256",
            "architecture",
            "inspection_method",
        }:
            fail.append("artifact-observation-shape")
            continue
        kind = artifact["kind"]
        if kind in expected_static:
            expected_sha, expected_size, expected_arch = expected_static[kind]
            if (artifact.get("sha256"), artifact.get("size_bytes"), artifact.get("architecture")) != (
                expected_sha,
                expected_size,
                expected_arch,
            ):
                fail.append("artifact-byte-observation-drift")
        elif kind == "server-oci-archive":
            if not _sha256(artifact.get("sha256")) or not _positive_int(artifact.get("size_bytes")) or artifact.get(
                "architecture"
            ) != "arm64":
                fail.append("oci-archive-observation-drift")
        cache_path = Path(artifact.get("cache_path", "")).resolve(strict=False)
        if not cache_path.is_relative_to(cache_root):
            fail.append("cache-path-outside-managed-root")
            continue
        if not cache_path.is_file():
            blocked.append("cached-asset-missing")
            continue
        if cache_path.stat().st_size != artifact.get("size_bytes") or _sha256_file(cache_path) != artifact.get(
            "sha256"
        ):
            blocked.append("cached-asset-drift")

    computed = "FAIL" if fail else "BLOCKED" if blocked else "PASS"
    if observation.get("status") != computed:
        if computed == "PASS":
            fail.append("stored-verdict-drift")
        else:
            blocked.append("stored-verdict-drift")
    categories = fail + blocked
    return _result("FAIL" if fail else "BLOCKED" if blocked else "PASS", categories, source)


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def verify_or_quarantine_file(path: Path, expected_sha256: str) -> Path | None:
    if _sha256_file(path) == expected_sha256:
        return None
    quarantine_dir = path.parent / "quarantine"
    quarantine_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = quarantine_dir / f"{path.name}.sha256-mismatch"
    if target.exists():
        target = quarantine_dir / f"{path.name}.{_sha256_file(path)[:12]}.sha256-mismatch"
    os.replace(path, target)
    os.chmod(target, 0o600)
    return target


def _download_verified(url: str, destination: Path, expected_sha256: str, expected_size: int) -> dict[str, Any]:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == expected_size and _sha256_file(destination) == expected_sha256:
        return {"size_bytes": expected_size, "sha256": expected_sha256}
    temporary = destination.with_name(f".{destination.name}.download")
    temporary.unlink(missing_ok=True)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "omni-srv-admin-phase52/1"})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as handle:
            shutil.copyfileobj(response, handle, length=1024 * 1024)
        os.chmod(temporary, 0o600)
        if temporary.stat().st_size != expected_size or _sha256_file(temporary) != expected_sha256:
            verify_or_quarantine_file(temporary, expected_sha256)
            raise ValueError("downloaded artifact failed checksum or size")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {"size_bytes": destination.stat().st_size, "sha256": _sha256_file(destination)}


def _http_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "omni-srv-admin-phase52/1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("official JSON response is not an object")
    return payload


def _resolve_tag_commit(repository: str, tag: str) -> str:
    completed = subprocess.run(
        ["git", "ls-remote", "--tags", repository, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("official git tag resolution failed")
    rows = [line.split() for line in completed.stdout.splitlines() if line.strip()]
    peeled = [sha for sha, ref in rows if ref.endswith("^{}")]
    direct = [sha for sha, ref in rows if ref == f"refs/tags/{tag}"]
    commits = peeled or direct
    if len(commits) != 1 or not re.fullmatch(r"[0-9a-f]{40}", commits[0]):
        raise ValueError("official git tag resolution is ambiguous")
    return commits[0]


def _release_asset(release: dict[str, Any], asset_name: str) -> dict[str, Any]:
    matches = [item for item in release.get("assets", []) if isinstance(item, dict) and item.get("name") == asset_name]
    if len(matches) != 1:
        raise ValueError("official release asset is absent or ambiguous")
    return matches[0]


def _zip_arm64(path: Path) -> bool:
    with zipfile.ZipFile(path) as archive:
        binaries = [name for name in archive.namelist() if Path(name).name in {"hbbs", "hbbr"}]
        if {Path(name).name for name in binaries} != {"hbbs", "hbbr"}:
            return False
        for name in binaries:
            header = archive.read(name)[:20]
            if len(header) < 20 or header[:4] != b"\x7fELF" or struct.unpack("<H", header[18:20])[0] != 183:
                return False
    return True


def _run_checked(command: list[str], timeout: int) -> str:
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise ValueError("guarded artifact inspection failed")
    return completed.stdout.strip()


def _stage_oci(contract: dict[str, Any]) -> dict[str, Any]:
    image = contract["server"]["classic_image"]
    reference = image["immutable_reference"]
    destination = Path(image["cache_path"])
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _run_checked(["podman", "pull", "--arch", "arm64", "--os", "linux", reference], 300)
    inspect = json.loads(_run_checked(["podman", "image", "inspect", reference], 60))
    if not isinstance(inspect, list) or len(inspect) != 1 or inspect[0].get("Architecture") != "arm64" or inspect[0].get(
        "Os"
    ) != "linux":
        raise ValueError("pinned image architecture inspection failed")
    temporary = destination.with_name(f".{destination.name}.save")
    temporary.unlink(missing_ok=True)
    try:
        _run_checked(["podman", "save", "--format", "oci-archive", "-o", str(temporary), reference], 300)
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "kind": "server-oci-archive",
        "source_url": reference,
        "cache_path": str(destination),
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256_file(destination),
        "architecture": "arm64",
        "inspection_method": "podman-image-inspect+oci-archive-save",
    }


def refresh_supply_observation(repo: Path, contract: dict[str, Any]) -> dict[str, Any]:
    contract_result = validate_supply_contract(contract)
    if contract_result.status != "PASS":
        raise ValueError("supply contract is not valid")
    server_commit = _resolve_tag_commit(contract["server"]["git_repository"], contract["server"]["tag"])
    client_commit = _resolve_tag_commit(contract["clients"]["git_repository"], contract["clients"]["tag"])
    if server_commit != SERVER_COMMIT or client_commit != CLIENT_COMMIT:
        raise ValueError("official tag commit drift")

    server_release = _http_json(contract["server"]["release_api_url"])
    client_release = _http_json(contract["clients"]["release_api_url"])
    registry = _http_json(contract["server"]["classic_image"]["registry_tag_api_url"])
    if registry.get("digest") != MULTIARCH_DIGEST:
        raise ValueError("official image manifest drift")
    children = [
        item
        for item in registry.get("images", [])
        if isinstance(item, dict) and item.get("architecture") == "arm64" and item.get("os") == "linux"
    ]
    if len(children) != 1 or children[0].get("digest") != ARM64_IMAGE_DIGEST:
        raise ValueError("official image ARM64 child drift")

    artifact_specs = (
        ("server-release-zip", contract["server"]["release_zip"], server_release),
        ("linux-client-deb", contract["clients"]["linux_arm64_deb"], client_release),
        ("windows-client-msi", contract["clients"]["windows_x86_64_msi"], client_release),
    )
    artifacts = [_stage_oci(contract)]
    for kind, spec, release in artifact_specs:
        official = _release_asset(release, spec["asset_name"])
        official_digest = official.get("digest")
        if official.get("browser_download_url") != spec["source_url"] or official.get("size") != spec[
            "size_bytes"
        ] or official_digest != f"sha256:{spec['sha256']}":
            raise ValueError("official release asset drift")
        destination = Path(spec["cache_path"])
        byte_meta = _download_verified(spec["source_url"], destination, spec["sha256"], spec["size_bytes"])
        if kind == "server-release-zip":
            if not _zip_arm64(destination):
                raise ValueError("server ZIP architecture inspection failed")
            method = "elf-e_machine-aarch64-for-hbbs-and-hbbr"
        elif kind == "linux-client-deb":
            if _run_checked(["dpkg-deb", "-f", str(destination), "Architecture"], 30) != "arm64":
                raise ValueError("DEB architecture inspection failed")
            method = "dpkg-deb-architecture"
        else:
            method = "official-x86_64-asset-name+sha256;metadata-and-authenticode-deferred-phase54"
        artifacts.append(
            {
                "kind": kind,
                "source_url": spec["source_url"],
                "cache_path": str(destination),
                "size_bytes": byte_meta["size_bytes"],
                "sha256": byte_meta["sha256"],
                "architecture": spec["architecture"],
                "inspection_method": method,
            }
        )

    source_urls = sorted(
        {
            contract["server"]["git_repository"],
            contract["server"]["release_api_url"],
            contract["server"]["classic_image"]["registry_tag_api_url"],
            contract["server"]["release_zip"]["source_url"],
            contract["clients"]["git_repository"],
            contract["clients"]["release_api_url"],
            contract["clients"]["linux_arm64_deb"]["source_url"],
            contract["clients"]["windows_x86_64_msi"]["source_url"],
        }
    )
    return {
        "schema_version": 1,
        "phase": 52,
        "workstream": "rustdesk-fleet",
        "observed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_urls": source_urls,
        "input_digests": collect_input_digests(repo, [SUPPLY_CONTRACT]),
        "server": {"tag": "1.1.15", "commit": server_commit},
        "clients": {"tag": "1.4.9", "commit": client_commit},
        "classic_image": {
            "tag": "1.1.15",
            "multiarch_digest": MULTIARCH_DIGEST,
            "linux_arm64_digest": ARM64_IMAGE_DIGEST,
            "architecture": "arm64",
            "os": "linux",
            "inspection_method": "docker-hub-platform-manifest+podman-image-inspect",
        },
        "artifacts": artifacts,
        "windows_install_performed": False,
        "candidate_admission_performed": False,
        "secret_material_present": False,
        "findings": [],
        "status": "PASS",
    }


def _write_json_atomically(payload: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_input_digests(repo: Path, paths: list[Path] | tuple[Path, ...]) -> list[dict[str, str]]:
    root = repo.resolve()
    rows: list[dict[str, str]] = []
    for path in paths:
        candidate = path if path.is_absolute() else root / path
        resolved = validate_repo_path(root, candidate)
        if not resolved.is_file():
            raise ValueError("report input is missing")
        rows.append({"path": resolved.relative_to(root).as_posix(), "sha256": _sha256_file(resolved)})
    return sorted(rows, key=lambda item: item["path"])


def _serialize_check(result: CheckResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "status": result.status,
        "evidence_ids": result.evidence_ids,
        "findings": [
            {"category": item.category, "path": item.path, "location": item.location}
            for item in result.findings
        ],
    }


def _load_phase51_validator(repo: Path) -> Any:
    path = validate_repo_path(repo, repo / PHASE51_VALIDATOR)
    name = "rustdesk_phase51_for_phase52"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Phase 51 validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _phase51_checks(repo: Path) -> tuple[CheckResult, CheckResult]:
    phase51 = _load_phase51_validator(repo)
    scope_path = validate_repo_path(repo, repo / SCOPE_CONTRACT)
    scope_results = phase51.validate_scope(
        phase51.load_json_strict(scope_path), scope_path.relative_to(repo).as_posix()
    )
    workstream = next(item for item in scope_results if item.id == "P51-WS-001")
    baseline_path = validate_repo_path(repo, repo / PHASE48_BASELINE)
    baseline = phase51.validate_phase48_baseline(
        phase51.load_json_strict(baseline_path), repo, baseline_path.relative_to(repo).as_posix()
    )

    def convert(result: Any) -> CheckResult:
        return CheckResult(
            id=result.id,
            status=result.status,
            evidence_ids=list(result.evidence_ids),
            findings=[Finding(item.category, item.path, item.location) for item in result.findings],
        )

    return convert(workstream), convert(baseline)


def _stage_check(
    check_id: str,
    stage: str,
    full_gate: dict[str, Any],
    *,
    require_selected: bool = False,
) -> CheckResult:
    attempts = full_gate.get("attempts") if isinstance(full_gate, dict) else None
    if not isinstance(attempts, list) or not attempts:
        return _check_result(check_id, "FAIL", ["candidate-shape"], FULL_GATE_SUMMARY.as_posix())
    records: list[dict[str, Any]] = []
    candidates: list[str] = []
    for attempt in attempts:
        stages = attempt.get("stages") if isinstance(attempt, dict) else None
        record = stages.get(stage) if isinstance(stages, dict) else None
        if not isinstance(record, dict):
            return _check_result(check_id, "FAIL", ["stage-vector-shape"], FULL_GATE_SUMMARY.as_posix())
        records.append(record)
        candidate = attempt.get("candidate") if isinstance(attempt, dict) else None
        if not isinstance(candidate, str) or not candidate:
            return _check_result(check_id, "FAIL", ["candidate-shape"], FULL_GATE_SUMMARY.as_posix())
        candidates.append(candidate)
    if len(set(candidates)) != len(candidates):
        return _check_result(check_id, "FAIL", ["candidate-duplicate"], FULL_GATE_SUMMARY.as_posix())
    selected = full_gate.get("selected_candidate")
    evaluation_records = records
    if selected is not None:
        if candidates.count(selected) != 1:
            return _check_result(check_id, "FAIL", ["selected-candidate-shape"], FULL_GATE_SUMMARY.as_posix())
        evaluation_records = [records[candidates.index(selected)]]
        predecessor_records = records[: candidates.index(selected)]
        if any(
            isinstance(record.get("mutation"), dict)
            and record["mutation"].get("performed") is not False
            for record in predecessor_records
        ):
            return _check_result(
                check_id, "FAIL", ["predecessor-mutation"], FULL_GATE_SUMMARY.as_posix()
            )
    evidence_ids = list(
        dict.fromkeys(
            item
            for record in evaluation_records
            for item in record.get("evidence_ids", [])
            if isinstance(item, str) and item
        )
    )
    findings = list(
        dict.fromkeys(
            item
            for record in evaluation_records
            for item in record.get("findings", [])
            if isinstance(item, str)
        )
    )
    statuses = [record.get("status") for record in evaluation_records]
    if any(status == "FAIL" for status in statuses):
        status = "FAIL"
    elif require_selected and selected is None:
        status = "BLOCKED"
        findings.append("no-selected-candidate")
    elif any(status in {"BLOCKED", "NO-GO", "SKIPPED_DUE_TO_GATE", "SKIPPED_BY_GATE"} for status in statuses):
        status = "BLOCKED"
    elif statuses and all(status == "PASS" for status in statuses):
        status = "PASS"
    else:
        status = "BLOCKED"
        findings.append("stage-status-incomplete")
    return CheckResult(
        id=check_id,
        status=status,
        evidence_ids=evidence_ids or [f"P52-EV-{stage.upper().replace('_', '-')}"],
        findings=[
            Finding(category, FULL_GATE_SUMMARY.as_posix(), f"attempts.*.stages.{stage}")
            for category in sorted(set(findings))
        ],
    )


def _capacity_report_check(
    policy: dict[str, Any], full_gate: dict[str, Any], *, now: datetime | None = None
) -> CheckResult:
    policy_result = validate_capacity_policy(policy)
    if policy_result.status != "PASS":
        return policy_result
    result = _stage_check("P52-CAPACITY-001", "capacity", full_gate, require_selected=True)
    attempts = full_gate.get("attempts", []) if isinstance(full_gate, dict) else []
    if any(
        not _is_current(sample.get("observed_at"), policy["observation_max_age_seconds"], now)
        for attempt in attempts
        if isinstance(attempt, dict)
        for sample in attempt.get("stages", {}).get("capacity", {}).get("samples", [])
        if isinstance(sample, dict)
    ):
        result.findings.append(
            Finding(
                "stale-observation",
                FULL_GATE_SUMMARY.as_posix(),
                "attempts.*.stages.capacity.samples",
            )
        )
        if result.status == "PASS":
            result.status = "BLOCKED"
    return result


def _backup_report_check(full_gate: dict[str, Any]) -> CheckResult:
    result = _stage_check("P52-BACKUP-001", "backup", full_gate, require_selected=True)
    horistic = next(
        (
            item
            for item in full_gate.get("attempts", [])
            if isinstance(item, dict) and item.get("candidate") == "horistic-srv"
        ),
        None,
    )
    vault = horistic.get("stages", {}).get("vault") if isinstance(horistic, dict) else None
    readiness = vault.get("readiness") if isinstance(vault, dict) else None
    if isinstance(readiness, dict):
        tools = readiness.get("tools", {})
        paths = readiness.get("paths", {})
        categories = [item.category for item in result.findings]
        if tools.get("rclone") is not True:
            categories.append("rclone-missing")
        if paths.get("rclone_vault_hydrator", {}).get("is_file") is not True:
            categories.append("rclone-vault-hydrator-missing")
        if paths.get("rclone_copy", {}).get("is_file") is not True:
            categories.append("rclone-copy-missing")
        if paths.get("rclone_fetch", {}).get("is_file") is not True:
            categories.append("rclone-fetch-missing")
        if paths.get("fleet_backup_module", {}).get("is_dir") is not True:
            categories.append("managed-fleet-backup-module-missing")
        result.findings = [
            Finding(category, FULL_GATE_SUMMARY.as_posix(), "attempts.horistic-srv.readiness")
            for category in sorted(set(categories))
        ]
    return result


def _topology_report_check(full_gate: dict[str, Any]) -> CheckResult:
    selected = full_gate.get("selected_candidate")
    if selected is None:
        return _check_result(
            "P52-TOPOLOGY-001",
            "BLOCKED",
            ["no-selected-candidate"],
            FULL_GATE_SUMMARY.as_posix(),
        )
    attempts = {
        item.get("candidate"): item
        for item in full_gate.get("attempts", [])
        if isinstance(item, dict)
    }
    selected_attempt = attempts.get(selected)
    record = (
        selected_attempt.get("stages", {}).get("topology_security")
        if isinstance(selected_attempt, dict)
        else None
    )
    if not isinstance(record, dict):
        return _check_result(
            "P52-TOPOLOGY-001", "FAIL", ["selected-topology-missing"], FULL_GATE_SUMMARY.as_posix()
        )
    status = record.get("status")
    return CheckResult(
        id="P52-TOPOLOGY-001",
        status="PASS" if status == "PASS" else "FAIL" if status == "FAIL" else "BLOCKED",
        evidence_ids=list(record.get("evidence_ids", [])) or ["P52-EV-TOPOLOGY"],
        findings=[
            Finding(item, FULL_GATE_SUMMARY.as_posix(), "selected.topology_security")
            for item in record.get("findings", [])
            if isinstance(item, str)
        ],
    )


def _git_head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True, capture_output=True, check=False
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError("unable to resolve source HEAD")
    return value


def build_phase52_report(repo: Path, generated_at: str | None = None) -> dict[str, Any]:
    root = repo.resolve()
    timestamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    report_now = _parse_utc(timestamp)
    if report_now is None:
        raise ValueError("generated_at must be an ISO-8601 UTC timestamp")
    contract = load_json_strict(validate_repo_path(root, root / SUPPLY_CONTRACT))
    observation = load_json_strict(validate_repo_path(root, root / SUPPLY_OBSERVATION))
    policy = load_json_strict(validate_repo_path(root, root / CAPACITY_POLICY))
    placement = load_json_strict(validate_repo_path(root, root / PLACEMENT_DECISION))
    full_gate = load_json_strict(validate_repo_path(root, root / FULL_GATE_SUMMARY))
    secret_roles = load_json_strict(validate_repo_path(root, root / SECRET_ROLES))

    contract_result = validate_supply_contract(contract)
    supply = (
        contract_result
        if contract_result.status != "PASS"
        else validate_supply_observation(observation, contract, repo=root, now=report_now)
    )
    capacity = _capacity_report_check(policy, full_gate, now=report_now)
    placement_result = validate_placement_decision(placement)
    vault_contract = validate_vault_metadata(secret_roles)
    vault = (
        vault_contract
        if vault_contract.status != "PASS"
        else _stage_check("P52-VAULT-001", "vault", full_gate, require_selected=True)
    )
    backup = _backup_report_check(full_gate)
    restore = _stage_check("P52-RESTORE-001", "restore", full_gate, require_selected=True)
    rollback = _stage_check("P52-ROLLBACK-001", "rollback", full_gate, require_selected=True)
    topology = _topology_report_check(full_gate)
    report_check = _check_result("P52-REPORT-001", "PASS", [], INTEGRATED_GATE.as_posix())
    workstream, phase48 = _phase51_checks(root)
    results = [
        supply,
        capacity,
        placement_result,
        vault,
        backup,
        restore,
        rollback,
        topology,
        report_check,
        workstream,
        phase48,
    ]
    if tuple(item.id for item in results) != PHASE52_CHECK_ORDER:
        raise ValueError("Phase 52 report check set is incomplete")
    selected = full_gate.get("selected_candidate")
    overall = derive_overall_status(results)
    topology_status = topology.status if selected is not None else "BLOCKED"
    attempts = full_gate.get("attempts", [])
    candidate_attempts = [
        {
            "candidate": item.get("candidate"),
            "record_digest": item.get("record_digest"),
            "verdict": item.get("verdict"),
            "first_non_pass_stage": item.get("first_non_pass_stage"),
        }
        for item in attempts
        if isinstance(item, dict)
    ]
    return {
        "schema_version": 1,
        "phase": 52,
        "workstream": "rustdesk-fleet",
        "source_head": _git_head(root),
        "generated_at": timestamp,
        "inputs": collect_input_digests(root, PHASE52_REPORT_INPUTS),
        "checks": [_serialize_check(item) for item in results],
        "selected_candidate": selected,
        "candidate_attempts": candidate_attempts,
        "phase53_topology_review_status": topology_status,
        "phase53_advance_status": (
            "READY" if overall == "PASS" and selected is not None and topology_status == "PASS" else "BLOCKED"
        ),
        "future_topology_reviews": {
            "phase54": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
            "phase57": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
        },
        "windows_install_performed": False,
        "windows_access_proven": False,
        "public_listener_created": False,
        "secret_material_present": False,
        "overall_status": overall,
    }


def validate_phase52_report(report: dict[str, Any], repo: Path) -> CheckResult:
    root = repo.resolve()
    fail: list[str] = []
    blocked: list[str] = []
    expected_keys = {
        "schema_version",
        "phase",
        "workstream",
        "source_head",
        "generated_at",
        "inputs",
        "checks",
        "selected_candidate",
        "candidate_attempts",
        "phase53_topology_review_status",
        "phase53_advance_status",
        "future_topology_reviews",
        "windows_install_performed",
        "windows_access_proven",
        "public_listener_created",
        "secret_material_present",
        "overall_status",
    }
    if not _exact_keys(report, expected_keys) or report.get("schema_version") != 1 or report.get(
        "phase"
    ) != 52 or report.get("workstream") != "rustdesk-fleet":
        fail.append("report-shape")
    checks = report.get("checks")
    check_ids = [item.get("id") for item in checks if isinstance(item, dict)] if isinstance(checks, list) else []
    if tuple(check_ids) != PHASE52_CHECK_ORDER or len(check_ids) != len(set(check_ids)):
        fail.append("report-check-set")
    statuses: list[str] = []
    if isinstance(checks, list):
        for item in checks:
            if not isinstance(item, dict) or set(item) != {"id", "status", "evidence_ids", "findings"}:
                fail.append("report-check-shape")
                continue
            if item.get("status") not in {"PASS", "BLOCKED", "FAIL"}:
                fail.append("report-check-status")
            else:
                statuses.append(item["status"])
    inputs = report.get("inputs")
    input_paths: list[str] = []
    output_paths = {
        INTEGRATED_GATE.as_posix(),
        PHASE52_REPORT_JSON.as_posix(),
        PHASE52_REPORT_MARKDOWN.as_posix(),
        PHASE53_TOPOLOGY_REVIEW.as_posix(),
    }
    if not isinstance(inputs, list):
        fail.append("report-input-shape")
    else:
        for item in inputs:
            if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
                fail.append("report-input-shape")
                continue
            path_text = item.get("path")
            digest = item.get("sha256")
            if not isinstance(path_text, str) or not _sha256(digest):
                fail.append("report-input-shape")
                continue
            input_paths.append(path_text)
            if path_text in output_paths:
                fail.append("report-self-hash-cycle")
                continue
            try:
                path = validate_repo_path(root, root / path_text)
                if not path.is_file() or _sha256_file(path) != digest:
                    blocked.append("stale-input-digest")
            except ValueError:
                fail.append("report-input-path")
        if input_paths != sorted(input_paths) or len(input_paths) != len(set(input_paths)):
            fail.append("report-input-order")
    full_gate = load_json_strict(validate_repo_path(root, root / FULL_GATE_SUMMARY))
    placement = load_json_strict(validate_repo_path(root, root / PLACEMENT_DECISION))
    expected_attempts = [
        {
            "candidate": item.get("candidate"),
            "record_digest": item.get("record_digest"),
            "verdict": item.get("verdict"),
            "first_non_pass_stage": item.get("first_non_pass_stage"),
        }
        for item in full_gate.get("attempts", [])
        if isinstance(item, dict)
    ]
    if report.get("candidate_attempts") != expected_attempts:
        blocked.append("candidate-attempt-digest-drift")
    if report.get("selected_candidate") != full_gate.get("selected_candidate") or report.get(
        "selected_candidate"
    ) != placement.get("selected_candidate"):
        fail.append("stored-placement-drift")
    expected_overall = "FAIL" if "FAIL" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS"
    if report.get("overall_status") != expected_overall:
        fail.append("stored-verdict-drift")
    expected_advance = (
        "READY"
        if expected_overall == "PASS"
        and report.get("selected_candidate") is not None
        and report.get("phase53_topology_review_status") == "PASS"
        else "BLOCKED"
    )
    if report.get("phase53_advance_status") != expected_advance:
        fail.append("stored-verdict-drift")
    if report.get("future_topology_reviews") != {
        "phase54": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
        "phase57": "REQUIRED_IMMEDIATELY_BEFORE_PHASE",
    }:
        fail.append("temporal-review-drift")
    if (
        report.get("windows_install_performed") is not False
        or report.get("windows_access_proven") is not False
        or report.get("public_listener_created") is not False
    ):
        fail.append("phase-boundary-drift")
    if report.get("secret_material_present") is not False:
        fail.append("secret-material")
    if re.search(
        r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/-]{16,}",
        json.dumps(report, sort_keys=True),
        flags=re.I,
    ):
        fail.append("secret-material")
    source_head = report.get("source_head")
    if not isinstance(source_head, str) or re.fullmatch(r"[0-9a-f]{40}", source_head) is None:
        fail.append("source-head-shape")
    elif subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_head, "HEAD"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode != 0:
        blocked.append("source-head-not-current-ancestor")
    if not isinstance(report.get("generated_at"), str) or _parse_utc(report.get("generated_at")) is None:
        fail.append("report-timestamp")
    status = "FAIL" if fail else "BLOCKED" if blocked else "PASS"
    return _check_result(
        "P52-REPORT-001",
        status,
        sorted(set(fail + blocked)),
        INTEGRATED_GATE.as_posix(),
    )


def render_phase52_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 52 Supply Chain, Capacity and Recoverable Placement Gate",
        "",
        "## Report Identity",
        "",
        f"- **Source HEAD:** `{report['source_head']}`",
        f"- **Generated at:** `{report['generated_at']}`",
        f"- **Selected candidate:** `{report['selected_candidate'] or 'none'}`",
        f"- **Phase 53 advance status:** `{report['phase53_advance_status']}`",
        f"- **Windows install performed:** `{str(report['windows_install_performed']).lower()}`",
        f"- **Secret material present:** `{str(report['secret_material_present']).lower()}`",
        "",
        "## Check Matrix",
        "",
        "| Check | Status | Findings |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        findings = ", ".join(item["category"] for item in check["findings"]) or "none"
        lines.append(f"| `{check['id']}` | {check['status']} | {findings} |")
    lines.extend(["", "## Candidate Attempts", "", "| Candidate | Verdict | First non-PASS | Record digest |", "|---|---|---|---|"])
    for attempt in report["candidate_attempts"]:
        lines.append(
            f"| `{attempt['candidate']}` | {attempt['verdict']} | {attempt['first_non_pass_stage'] or 'none'} | `{attempt['record_digest']}` |"
        )
    lines.extend(
        [
            "",
            "## Temporal Boundaries",
            "",
            "Phase 54 and Phase 57 topology reviews remain required immediately before their own phases; neither is a Phase 53 prerequisite.",
            "The verified MSI remains staged only. Phase 54 still owns Windows installation and real access proof to the Atius servers.",
            "",
            "## Overall Status",
            "",
            f"**{report['overall_status']}**",
        ]
    )
    return "\n".join(lines) + "\n"


def render_phase53_topology_review(report: dict[str, Any]) -> str:
    selected = report.get("selected_candidate") or "none"
    blocker_checks = {
        "P52-CAPACITY-001",
        "P52-PLACEMENT-001",
        "P52-VAULT-001",
        "P52-BACKUP-001",
        "P52-RESTORE-001",
        "P52-TOPOLOGY-001",
    }
    blockers = sorted(
        {
            finding["category"]
            for item in report["checks"]
            if item["id"] in blocker_checks
            for finding in item["findings"]
        }
    ) or ["no-selected-candidate"]
    status = report["phase53_topology_review_status"]
    if status == "PASS" and selected != "none" and report.get("phase53_advance_status") == "READY":
        decision = (
            f"Horistic candidate `{selected}` has the current full-vector PASS. "
            "Phase 53 is READY within the reviewed rootless server budget; no native listener, DNS, edge, or Windows mutation is performed by this review."
        )
        blocker_line = "Current blockers: none."
    else:
        decision = "No recoverable primary is selected. Phase 53 is blocked and no production deployment, native listener, DNS or edge change is authorized."
        blocker_line = f"Current blockers: {', '.join(blockers)}."
    return "\n".join(
        [
            "# Phase 52 — Phase 53 Topology Review",
            "",
            f"**Status:** {status}",
            f"**Reviewed at:** `{report['generated_at']}`",
            "**Accountable decision source:** `52-OPERATIONAL-DECISIONS.md` (Giovanni Muniz)",
            f"**Selected candidate:** `{selected}`",
            f"**Phase 53 advance status:** `{report['phase53_advance_status']}`",
            "**Secret material present:** false",
            "",
            "## Current decision",
            "",
            decision,
            blocker_line,
            "",
            "## Deferred selected-host contract",
            "",
            "When a candidate earns one current full-vector PASS, Phase 53 must use rootless server placement with the approved combined budget of at most 0.8 CPU, at most 1 GiB RAM, bounded disk/log reservations, and only the approved future native listener boundary.",
            "The native listener boundary remains disabled in this review. Rollback must preserve RustGuac, XRDP, AnyDesk, NoMachine and noVNC.",
            "If Horistic is selected after remediation and a fresh full gate, server/client resource, identity, evidence and rollback domains remain separate; co-location is not independent DR.",
            "",
            "## Temporal reviews",
            "",
            "- Phase 54 topology review remains required immediately before Phase 54.",
            "- Phase 57 topology review remains required immediately before Phase 57.",
            "- Neither future review is required merely to evaluate a later Phase 53 transition.",
            "",
            "## Windows boundary",
            "",
            "`windows_install_performed=false`; Phase 54 still owns installation and real Atius-server access proof.",
            "",
        ]
    )


def _phase52_json_text(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def write_phase52_outputs_atomically(
    report: dict[str, Any],
    *,
    integrated_path: Path,
    json_path: Path,
    markdown_path: Path,
    topology_path: Path,
    repo: Path,
    allow_test_paths: bool = False,
) -> None:
    root = repo.resolve()
    paths = [integrated_path, json_path, markdown_path, topology_path]
    resolved = (
        [item.resolve(strict=False) for item in paths]
        if allow_test_paths
        else [validate_repo_path(root, item if item.is_absolute() else root / item) for item in paths]
    )
    if not allow_test_paths and [item.relative_to(root) for item in resolved] != [
        INTEGRATED_GATE,
        PHASE52_REPORT_JSON,
        PHASE52_REPORT_MARKDOWN,
        PHASE53_TOPOLOGY_REVIEW,
    ]:
        raise ValueError("Phase 52 report output names are fixed")
    json_text = _phase52_json_text(report)
    payloads = (
        (resolved[0], json_text),
        (resolved[1], json_text),
        (resolved[2], render_phase52_markdown(report)),
        (resolved[3], render_phase53_topology_review(report)),
    )
    temporary_paths: list[Path] = []
    try:
        for target, content in payloads:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", delete=False
            ) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_paths.append(Path(handle.name))
        for temporary, (target, _) in zip(temporary_paths, payloads, strict=True):
            os.replace(temporary, target)
    finally:
        for temporary in temporary_paths:
            temporary.unlink(missing_ok=True)


def validate_phase52_output_parity(
    report: dict[str, Any], integrated_path: Path, json_path: Path, markdown_path: Path
) -> CheckResult:
    errors: list[str] = []
    try:
        expected_json = _phase52_json_text(report)
        if integrated_path.read_text(encoding="utf-8") != expected_json or json_path.read_text(
            encoding="utf-8"
        ) != expected_json:
            errors.append("json-parity-drift")
        if markdown_path.read_text(encoding="utf-8") != render_phase52_markdown(report):
            errors.append("markdown-parity-drift")
    except OSError:
        errors.append("report-output-missing")
    return _check_result(
        "P52-REPORT-001",
        "PASS" if not errors else "FAIL",
        errors,
        PHASE52_REPORT_JSON.as_posix(),
    )


def update_phase52_ledger(
    ledger: dict[str, Any], report: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    updated = copy.deepcopy(ledger)
    if report.get("overall_status") != "PASS" or report.get("phase53_advance_status") != "READY":
        return updated, False
    rows = {
        item.get("requirement_id"): item
        for item in updated.get("requirements", [])
        if isinstance(item, dict)
    }
    if set(PHASE52_REQUIREMENTS) - set(rows):
        raise ValueError("Phase 52 ledger rows are missing")
    report_digest = hashlib.sha256(_phase52_json_text(report).encode("utf-8")).hexdigest()
    catalog = updated.get("evidence_catalog")
    if not isinstance(catalog, dict):
        raise ValueError("ledger evidence catalog is invalid")
    for requirement in PHASE52_REQUIREMENTS:
        row = rows[requirement]
        evidence_id = f"RDF-V19-{requirement}"
        if row.get("evidence_ids") != [evidence_id]:
            raise ValueError("Phase 52 ledger evidence ID drift")
        row["status"] = "pass"
        row["last_verified_at"] = report["generated_at"]
        catalog[evidence_id] = {
            "path": INTEGRATED_GATE.as_posix(),
            "sha256": report_digest,
            "input_digest": report_digest,
            "observed_at": report["generated_at"],
        }
    return updated, True


def run_gate_a_secret_scan(repo: Path) -> CheckResult:
    reviewed = (
        Path("modules/rustdesk-fleet/contracts/phase52-vault-control-plane.json"),
        Path("modules/rustdesk-fleet/contracts/phase52-live-drill-contract.json"),
        Path("modules/rustdesk-fleet/tools/atius-vault-phase52-client"),
        Path("modules/rustdesk-fleet/tools/atius-vault-export-rustdesk-phase52"),
        Path("modules/rustdesk-fleet/tools/atius-vault-export-ssh-phase52"),
        Path("modules/rustdesk-fleet/tools/atius-vault-phase52-write"),
        Path("modules/rustdesk-fleet/tools/install-phase52-vault-control-plane.sh"),
        Path("modules/rustdesk-fleet/tools/phase52-horistic-live-drill.py"),
        Path("modules/rustdesk-fleet/tools/phase52_recovery.py"),
        Path("modules/rustdesk-fleet/tools/rustdesk-vault-provider"),
        Path("modules/rustdesk-fleet/tools/install-rustdesk-vault-provider.sh"),
        Path("modules/fleet-backup/scripts/atius-rclone-vault-hydrate"),
        Path("modules/fleet-backup/scripts/rclone-copy-verified-phase52.sh"),
        Path("modules/fleet-backup/scripts/rclone-fetch-verified-phase52.sh"),
        PHASE52_DIR / "52-07-AUTHORIZATION.md",
        Path("modules/rustdesk-fleet/evidence/phase52/gate-a-verification.json"),
    )
    findings: list[str] = []
    patterns = (
        re.compile(r"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----"),
        re.compile(r"(?<![A-Za-z0-9])R[A-Za-z0-9]{31}(?![A-Za-z0-9])"),
        re.compile(r"(?im)^\s*(?:token|password|private_key)\s*=\s*[^<\s][^\n]+$"),
    )
    for relative in reviewed:
        path = validate_repo_path(repo, repo / relative)
        if not path.is_file():
            findings.append(f"managed-source-missing:{relative.as_posix()}")
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in patterns):
            findings.append(f"secret-pattern:{relative.as_posix()}")
    return _check_result(
        "P52-GATE-A-SECRET-SCAN",
        "PASS" if not findings else "FAIL",
        findings,
        "modules/rustdesk-fleet/evidence/phase52/gate-a-verification.json",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--only",
        choices=("supply", "capacity-proposal", "capacity-live", "full-candidate-chain", "report", "secret-scan"),
        default="supply",
    )
    parser.add_argument("--evidence-dir", type=Path, default=SUPPLY_OBSERVATION.parent)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--integrated-out", type=Path, default=INTEGRATED_GATE)
    parser.add_argument("--topology-out", type=Path, default=PHASE53_TOPOLOGY_REVIEW)
    return parser


def main(argv: list[str] | None = None) -> int:
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv[:1] == ["--vault-helper"]:
        return vault_helper_main(effective_argv[1:])
    args = build_parser().parse_args(effective_argv)
    repo = args.repo.resolve()
    try:
        if args.only == "secret-scan":
            result = run_gate_a_secret_scan(repo)
            print(json.dumps({"status": result.status, "check": result.id}, sort_keys=True))
            return exit_code_for_status(result.status)
        report_requested = args.only == "report" or args.json_out is not None or args.markdown_out is not None
        if report_requested:
            if args.json_out is None or args.markdown_out is None:
                raise ValueError("both Phase 52 report projections are required")
            report = build_phase52_report(repo)
            report_result = validate_phase52_report(report, repo)
            if report_result.status != "PASS":
                print(json.dumps({"status": report_result.status, "check": report_result.id}, sort_keys=True))
                return exit_code_for_status(report_result.status)
            write_phase52_outputs_atomically(
                report,
                integrated_path=args.integrated_out,
                json_path=args.json_out,
                markdown_path=args.markdown_out,
                topology_path=args.topology_out,
                repo=repo,
            )
            parity = validate_phase52_output_parity(
                report,
                validate_repo_path(repo, repo / args.integrated_out),
                validate_repo_path(repo, repo / args.json_out),
                validate_repo_path(repo, repo / args.markdown_out),
            )
            if parity.status != "PASS":
                print(json.dumps({"status": parity.status, "check": parity.id}, sort_keys=True))
                return exit_code_for_status(parity.status)
            ledger_path = validate_repo_path(repo, repo / LEDGER)
            ledger, promoted = update_phase52_ledger(load_json_strict(ledger_path), report)
            if promoted:
                _write_json_atomically(ledger, ledger_path)
            print(json.dumps({"status": report["overall_status"], "check": "P52-REPORT-001"}, sort_keys=True))
            return exit_code_for_status(report["overall_status"])
        if args.only == "full-candidate-chain":
            result = run_full_candidate_chain(repo, args.evidence_dir)
            print(json.dumps({"status": result.status, "check": result.id}, sort_keys=True))
            return exit_code_for_status(result.status)
        if args.only == "capacity-live":
            result = run_capacity_live(repo, args.evidence_dir)
            print(json.dumps({"status": result.status, "check": result.id}, sort_keys=True))
            return exit_code_for_status(result.status)
        if args.only == "capacity-proposal":
            policy_path = validate_repo_path(repo, repo / CAPACITY_POLICY)
            proposal_path = validate_repo_path(repo, repo / args.evidence_dir / CAPACITY_PROPOSAL.name)
            policy = load_json_strict(policy_path)
            policy_result = validate_capacity_policy(policy, policy_path.relative_to(repo).as_posix())
            if policy_result.status != "PASS":
                print(json.dumps({"status": policy_result.status, "check": policy_result.id}, sort_keys=True))
                return exit_code_for_status(policy_result.status)
            proposal = load_json_strict(proposal_path)
            result = validate_capacity_proposal(proposal, policy, repo, proposal_path.relative_to(repo).as_posix())
            print(json.dumps({"status": result.status, "check": result.id}, sort_keys=True))
            return exit_code_for_status(result.status)
        contract_path = validate_repo_path(repo, repo / SUPPLY_CONTRACT)
        contract = load_json_strict(contract_path)
        contract_result = validate_supply_contract(contract, contract_path.relative_to(repo).as_posix())
        if contract_result.status != "PASS":
            print(json.dumps({"status": contract_result.status, "check": contract_result.id}, sort_keys=True))
            return exit_code_for_status(contract_result.status)
        observation_path = validate_repo_path(repo, repo / args.evidence_dir / SUPPLY_OBSERVATION.name)
        observation = refresh_supply_observation(repo, contract)
        result = validate_supply_observation(observation, contract, repo=repo)
        if result.status == "PASS":
            _write_json_atomically(observation, observation_path)
    except (OSError, ValueError, subprocess.SubprocessError, urllib.error.URLError) as exc:
        print(f"BLOCKED: {exc.__class__.__name__}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result.status, "check": result.id}, sort_keys=True))
    return exit_code_for_status(result.status)


if __name__ == "__main__":
    raise SystemExit(main())
