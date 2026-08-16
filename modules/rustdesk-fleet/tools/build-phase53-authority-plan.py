#!/usr/bin/env python3
"""Build Phase 53 authority artifacts from one explicit read-only observation.

This module is deliberately capability-disjoint from live execution.  It can
collect read/preview results, validate immutable Git objects, construct a
non-authorizing six-file generation, and record an explicit owner response.
It never discovers ambient routes or credentials and has no provider-write
interface.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable


FREEZE_COMMIT = "6bb2e0abad5cad3eb1ff750bcb92130c06ee0f6c"
ATTESTATION_COMMIT = "e552c876f32cc87bb0d97b71308056f30423c452"
CLOSEOUT_COMMIT = "11fa627fdd27c7032f0029cd594bc2e1241e20bb"
D2D_SUMMARY_PATH = Path(
    ".planning/workstreams/rustdesk-fleet/phases/"
    "53-primary-relay-and-public-edge/53-05D2D-SUMMARY.md"
)
D2H_SUMMARY_PATH = Path(
    ".planning/workstreams/rustdesk-fleet/phases/"
    "53-primary-relay-and-public-edge/53-05D2H-SUMMARY.md"
)
SOURCE_SCOPE_PATH = Path(
    "modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json"
)
PROVIDER_MANIFEST_PATH = Path(
    "modules/rustdesk-fleet/contracts/phase53-provider-manifest.json"
)
QUARANTINE_ROOT = Path("/var/tmp/omni-rustdesk-phase53-quarantine")
CANONICAL_05F_PATHS = (
    "modules/rustdesk-fleet/evidence/phase53/deploy-transaction.json",
    "modules/rustdesk-fleet/evidence/phase53/edge-probes.json",
    "modules/rustdesk-fleet/evidence/phase53/ops-api-probes.json",
    "modules/rustdesk-fleet/evidence/phase53/lifecycle.json",
    "modules/rustdesk-fleet/evidence/phase53/rollback-drill.json",
    "modules/rustdesk-fleet/evidence/phase53/restore-production-transaction.json",
    "modules/rustdesk-fleet/evidence/phase53/direct-relay-metrics.json",
)
AUTHORITY_FILENAMES = (
    "topology-discovery.json",
    "phase52-successor-attestation.json",
    "candidate-admission.json",
    "capacity-current.json",
    "preflight.json",
    "edge-forwarder-operation-plan.json",
)
DEPENDENCY_FILENAMES = AUTHORITY_FILENAMES[:-1]
HEX_40 = re.compile(r"[0-9a-f]{40}")
HEX_64 = re.compile(r"[0-9a-f]{64}")
SECRET_KEYS = {
    "authorization",
    "authorization_header",
    "api_token",
    "token",
    "bearer_token",
    "password",
    "private_key",
    "client_secret",
    "secret",
}
VERDICT_KEYS = {"pass", "passed", "verdict", "overall_status"}
OBSERVATION_KEYS = {
    "schema_version",
    "observed_at",
    "ttl_seconds",
    "read_only",
    "synthetic",
    "mutation_performed",
    "secret_material_present",
    "topology",
    "supply",
    "capacity_samples",
    "vault_public_fingerprint",
    "provider",
}
EXPECTED_CAPACITY_ORDER = (
    "atius-srv-2",
    "atius-srv-2",
    "atius-srv-3",
    "atius-srv-3",
    "horistic-srv",
    "horistic-srv",
)


class AuthorityPlanBlocked(RuntimeError):
    """The read-only authority lane rejected incomplete or unsafe input."""


def _duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise AuthorityPlanBlocked("duplicate-json-key")
        result[key] = value
    return result


def _strict_json_bytes(raw: bytes, *, blocker: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_duplicate_keys)
    except AuthorityPlanBlocked:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorityPlanBlocked(blocker) from exc
    if not isinstance(payload, dict):
        raise AuthorityPlanBlocked(blocker)
    return payload


def _read_regular(path: Path, *, blocker: str, maximum: int = 8_388_608) -> bytes:
    try:
        info = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or not 0 < info.st_size <= maximum
        ):
            raise AuthorityPlanBlocked(blocker)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            chunks: list[bytes] = []
            remaining = maximum + 1
            while remaining:
                chunk = os.read(descriptor, min(131_072, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
        finally:
            os.close(descriptor)
        raw = b"".join(chunks)
    except AuthorityPlanBlocked:
        raise
    except OSError as exc:
        raise AuthorityPlanBlocked(blocker) from exc
    if len(raw) > maximum:
        raise AuthorityPlanBlocked(blocker)
    return raw


def _strict_json_file(path: Path, *, blocker: str) -> dict[str, Any]:
    return _strict_json_bytes(_read_regular(path, blocker=blocker), blocker=blocker)


def canonical_projection(value: Any, *, path: str = "$") -> Any:
    """Project supported immutable values into deterministic JSON primitives."""

    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise AuthorityPlanBlocked("unsupported-canonical-value")
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise AuthorityPlanBlocked("bytes-forbidden")
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str) or not key:
                raise AuthorityPlanBlocked("canonical-key-invalid")
            lowered = key.lower()
            if lowered in SECRET_KEYS:
                raise AuthorityPlanBlocked("secret-key-forbidden")
            if lowered in VERDICT_KEYS:
                raise AuthorityPlanBlocked("stored-verdict-forbidden")
            projected[key] = canonical_projection(child, path=f"{path}.{key}")
        return {key: projected[key] for key in sorted(projected)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            canonical_projection(child, path=f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    raise AuthorityPlanBlocked("unsupported-canonical-value")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        canonical_projection(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _parse_utc(value: Any, *, blocker: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AuthorityPlanBlocked(blocker)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except (TypeError, ValueError, OverflowError) as exc:
        raise AuthorityPlanBlocked(blocker) from exc
    if parsed.tzinfo is None:
        raise AuthorityPlanBlocked(blocker)
    return parsed.astimezone(timezone.utc)


def _trusted_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise AuthorityPlanBlocked("trusted-clock-invalid")
    return current.astimezone(timezone.utc)


def _git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=text,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuthorityPlanBlocked("git-read-failed") from exc
    if completed.returncode != 0:
        raise AuthorityPlanBlocked("git-read-failed")
    return completed.stdout


def _git_json(repo: Path, commit: str, relative: str) -> dict[str, Any]:
    raw = _git(repo, "show", f"{commit}:{relative}", text=False)
    assert isinstance(raw, bytes)
    return _strict_json_bytes(raw, blocker="frozen-git-object-invalid")


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=20,
    )
    return completed.returncode == 0


def validate_frozen_phase52(repo: Path) -> dict[str, Any]:
    """Validate Phase 52 only from its immutable, reviewed Git objects."""

    root = repo.resolve(strict=True)
    parent = str(_git(root, "rev-parse", f"{ATTESTATION_COMMIT}^")).strip()
    head = str(_git(root, "rev-parse", "HEAD")).strip()
    if (
        parent != FREEZE_COMMIT
        or not _is_ancestor(root, ATTESTATION_COMMIT, CLOSEOUT_COMMIT)
        or not _is_ancestor(root, CLOSEOUT_COMMIT, head)
    ):
        raise AuthorityPlanBlocked("phase52-ancestry-invalid")
    contract_path = "modules/rustdesk-fleet/contracts/phase52-post-live-successor.json"
    attestation_path = (
        "modules/rustdesk-fleet/evidence/phase52/post-live/successor-attestation.json"
    )
    review_paths = (
        "modules/rustdesk-fleet/evidence/phase52/post-live/review-1.json",
        "modules/rustdesk-fleet/evidence/phase52/post-live/review-2.json",
    )
    closeout_path = (
        ".planning/workstreams/rustdesk-fleet/phases/"
        "52-supply-chain-capacity-and-recoverable-placement/52-10-CLOSEOUT.json"
    )
    contract = _git_json(root, FREEZE_COMMIT, contract_path)
    attestation = _git_json(root, ATTESTATION_COMMIT, attestation_path)
    reviews = [_git_json(root, ATTESTATION_COMMIT, path) for path in review_paths]
    closeout = _git_json(root, CLOSEOUT_COMMIT, closeout_path)
    if (
        contract.get("schema_anchor") != "phase52_post_live_successor_v1"
        or contract.get("authority")
        != {
            "live_authority": False,
            "replay_authorized": False,
            "vault_write_authorized": False,
        }
        or attestation.get("status") != "PASS"
        or attestation.get("source_freeze_commit") != FREEZE_COMMIT
        or attestation.get("authority") != contract.get("authority")
    ):
        raise AuthorityPlanBlocked("phase52-frozen-input-invalid")
    source_paths = contract.get("source_freeze", {}).get("paths")
    source_hashes = attestation.get("source_hashes")
    if (
        not isinstance(source_paths, list)
        or len(source_paths) != len(set(source_paths)) == 6
        or not isinstance(source_hashes, Mapping)
        or set(source_hashes) != set(source_paths)
    ):
        raise AuthorityPlanBlocked("phase52-source-freeze-invalid")
    for relative in source_paths:
        content = _git(root, "show", f"{FREEZE_COMMIT}:{relative}", text=False)
        assert isinstance(content, bytes)
        if hashlib.sha256(content).hexdigest() != source_hashes[relative]:
            raise AuthorityPlanBlocked("phase52-source-freeze-invalid")
    reviewer_ids = [review.get("reviewer_id") for review in reviews]
    if (
        len(set(reviewer_ids)) != 2
        or any(review.get("verdict") != "PASS" for review in reviews)
        or any(review.get("findings") != [] for review in reviews)
        or any(review.get("unresolved_high_count") != 0 for review in reviews)
        or any(review.get("mutation_detected") is not False for review in reviews)
        or any(review.get("source_freeze_commit") != FREEZE_COMMIT for review in reviews)
        or len({review.get("hash_set_sha256") for review in reviews}) != 1
        or reviews[0].get("hash_set_sha256") != attestation.get("hash_set_sha256")
    ):
        raise AuthorityPlanBlocked("phase52-review-quorum-invalid")
    if (
        closeout.get("status") != "PASS"
        or closeout.get("closeout_kind") != "metadata-only"
        or closeout.get("fresh_operational_replay") is not False
        or closeout.get("authority") != contract.get("authority")
        or closeout.get("source_freeze", {}).get("commit") != FREEZE_COMMIT
    ):
        raise AuthorityPlanBlocked("phase52-closeout-invalid")
    attestation_raw = _git(root, "show", f"{ATTESTATION_COMMIT}:{attestation_path}", text=False)
    assert isinstance(attestation_raw, bytes)
    if (
        closeout.get("inputs", {})
        .get("successor_attestation", {})
        .get("sha256")
        != hashlib.sha256(attestation_raw).hexdigest()
    ):
        raise AuthorityPlanBlocked("phase52-closeout-input-drift")
    return {
        "schema_version": 1,
        "source_freeze_commit": FREEZE_COMMIT,
        "attestation_commit": ATTESTATION_COMMIT,
        "closeout_commit": CLOSEOUT_COMMIT,
        "source_hashes": dict(source_hashes),
        "successor_attestation_sha256": hashlib.sha256(attestation_raw).hexdigest(),
        "hash_set_sha256": attestation["hash_set_sha256"],
        "reviewer_ids": reviewer_ids,
        "historical_replay": False,
        "historical_rebaseline": False,
        "authorizes_live": False,
        "vault_write_authorized": False,
        "secret_material_present": False,
        "mutation_performed": False,
    }


def validate_authority_observation(
    observation: Mapping[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    current = _trusted_now(now)
    projected = canonical_projection(observation)
    if not isinstance(projected, dict) or set(projected) != OBSERVATION_KEYS:
        raise AuthorityPlanBlocked("observation-schema-invalid")
    ttl = projected.get("ttl_seconds")
    observed = _parse_utc(projected.get("observed_at"), blocker="observation-time-invalid")
    if (
        projected.get("schema_version") != 1
        or type(ttl) is not int
        or not 0 < ttl <= 3600
        or observed > current
        or (current - observed).total_seconds() > ttl
        or projected.get("read_only") is not True
        or projected.get("synthetic") is not False
        or projected.get("mutation_performed") is not False
        or projected.get("secret_material_present") is not False
    ):
        raise AuthorityPlanBlocked("observation-not-current")
    topology = projected.get("topology")
    if not isinstance(topology, Mapping) or topology.get("state") != "CURRENT":
        raise AuthorityPlanBlocked("topology-not-current")
    if topology.get("backend_ingress_source_ipv4") == "10.0.0.238":
        raise AuthorityPlanBlocked("public-vnic-backend-source-forbidden")
    if {
        "public_edge_host": topology.get("public_edge_host"),
        "public_ipv4": topology.get("public_ipv4"),
        "public_vnic_private_ipv4": topology.get("public_vnic_private_ipv4"),
        "route_vnic_private_ipv4": topology.get("route_vnic_private_ipv4"),
        "backend_host": topology.get("backend_host"),
        "backend_private_ipv4": topology.get("backend_private_ipv4"),
        "backend_ingress_source_ipv4": topology.get(
            "backend_ingress_source_ipv4"
        ),
    } != {
        "public_edge_host": "atius-srv-1",
        "public_ipv4": "137.131.140.20",
        "public_vnic_private_ipv4": "10.0.0.238",
        "route_vnic_private_ipv4": "10.11.1.11",
        "backend_host": "horistic-srv",
        "backend_private_ipv4": "10.21.1.21",
        "backend_ingress_source_ipv4": "10.11.1.11",
    }:
        raise AuthorityPlanBlocked("topology-contract-drift")
    supply = projected.get("supply")
    if (
        not isinstance(supply, Mapping)
        or supply.get("state") != "CURRENT"
        or not isinstance(supply.get("immutable_reference"), str)
        or "@sha256:" not in supply["immutable_reference"]
    ):
        raise AuthorityPlanBlocked("supply-not-current")
    samples = projected.get("capacity_samples")
    if (
        not isinstance(samples, list)
        or len(samples) != 6
        or tuple(
            sample.get("host") if isinstance(sample, Mapping) else None
            for sample in samples
        )
        != EXPECTED_CAPACITY_ORDER
    ):
        raise AuthorityPlanBlocked("capacity-sample-order-invalid")
    for index, sample in enumerate(samples):
        if (
            not isinstance(sample, Mapping)
            or sample.get("zero_cleanup_performed") is not False
            or _parse_utc(
                sample.get("observed_at"), blocker="capacity-sample-time-invalid"
            )
            > current
            or (
                current
                - _parse_utc(
                    sample.get("observed_at"),
                    blocker="capacity-sample-time-invalid",
                )
            ).total_seconds()
            > ttl
        ):
            raise AuthorityPlanBlocked("capacity-sample-stale")
        if index < 4 and sample.get("placement_state") != "NO-GO":
            raise AuthorityPlanBlocked("capacity-predecessor-state-drift")
        if index >= 4 and (
            sample.get("placement_state") != "GO"
            or sample.get("raw_capacity_state") != "CURRENT"
            or sample.get("capacity_finalize_state") != "CURRENT"
        ):
            raise AuthorityPlanBlocked("capacity-primary-state-drift")
    fingerprint = projected.get("vault_public_fingerprint")
    if (
        not isinstance(fingerprint, Mapping)
        or fingerprint.get("vault_path") != "kv/atius/rustdesk/server"
        or fingerprint.get("value_free") is not True
        or not isinstance(fingerprint.get("public_fingerprint_sha256"), str)
        or not HEX_64.fullmatch(fingerprint["public_fingerprint_sha256"])
    ):
        raise AuthorityPlanBlocked("vault-public-fingerprint-invalid")
    provider = projected.get("provider")
    surfaces = {"host", "oci", "cloudflare", "apache"}
    if (
        not isinstance(provider, Mapping)
        or set(provider) != {"prestates", "previews"}
        or not isinstance(provider["prestates"], Mapping)
        or not isinstance(provider["previews"], Mapping)
        or set(provider["prestates"]) != surfaces
        or set(provider["previews"]) != surfaces
    ):
        raise AuthorityPlanBlocked("provider-observation-invalid")
    for surface in sorted(surfaces):
        prestate = provider["prestates"][surface]
        preview = provider["previews"][surface]
        if (
            not isinstance(prestate, Mapping)
            or prestate.get("kind") != "prestate"
            or prestate.get("surface") != surface
            or prestate.get("mutation_performed") is not False
            or not isinstance(preview, Mapping)
            or preview.get("kind") != "preview"
            or preview.get("surface") != surface
            or preview.get("mutation_performed") is not False
            or not HEX_64.fullmatch(str(preview.get("confirmation_sha256", "")))
        ):
            raise AuthorityPlanBlocked("provider-observation-invalid")
    return projected


def collect_read_only_observation(
    bundle: Any,
    *,
    observed_at: str,
    ttl_seconds: int = 900,
    output: Path | None = None,
) -> dict[str, Any]:
    fields = {
        "read_topology",
        "read_supply",
        "read_capacity",
        "read_vault_public_fingerprint",
        "read_provider_prestates",
        "preview_provider_changes",
    }
    if getattr(bundle, "capabilities", None) != frozenset({"read", "preview"}):
        raise AuthorityPlanBlocked("read-only-capability-drift")
    if any(
        hasattr(bundle, name)
        for name in (
            "apply",
            "mutate",
            "contain",
            "containment",
            "rollback",
            "restore",
            "runtime",
            "providers",
        )
    ) or not all(callable(getattr(bundle, name, None)) for name in fields):
        raise AuthorityPlanBlocked("write-capability-present")
    observation = {
        "schema_version": 1,
        "observed_at": observed_at,
        "ttl_seconds": ttl_seconds,
        "read_only": True,
        "synthetic": False,
        "mutation_performed": False,
        "secret_material_present": False,
        "topology": bundle.read_topology(),
        "supply": bundle.read_supply(),
        "capacity_samples": bundle.read_capacity(),
        "vault_public_fingerprint": bundle.read_vault_public_fingerprint(),
        "provider": {
            "prestates": bundle.read_provider_prestates(),
            "previews": bundle.preview_provider_changes(),
        },
    }
    validated = validate_authority_observation(
        observation, now=_parse_utc(observed_at, blocker="observation-time-invalid")
    )
    if output is not None:
        _write_exclusive(output, canonical_bytes(validated))
    return validated


def _mode_is_private(info: os.stat_result, expected: int) -> bool:
    return (
        info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == expected
    )


def _summary_value(text: str, key: str) -> str:
    values = re.findall(
        rf"(?mi)^\s*(?:[-*]\s*)?[`'\"]?{re.escape(key)}[`'\"]?\s*[:=]\s*[`'\"]?([^`'\"\s]+)",
        text,
    )
    unique = list(dict.fromkeys(values))
    if len(unique) != 1:
        raise AuthorityPlanBlocked("housekeeping-summary-binding-invalid")
    return unique[0]


def validate_housekeeping_receipt(
    *,
    repo: Path,
    summary_path: Path,
    quarantine_pointer: Path,
    expected_05d2d_summary_commit: str,
    quarantine_root: Path = QUARANTINE_ROOT,
) -> dict[str, Any]:
    root = repo.resolve(strict=True)
    expected_summary = root / D2H_SUMMARY_PATH
    supplied_summary = (
        summary_path if summary_path.is_absolute() else root / summary_path
    )
    try:
        summary_info = supplied_summary.lstat()
    except OSError as exc:
        raise AuthorityPlanBlocked("housekeeping-summary-invalid") from exc
    if (
        supplied_summary.resolve() != expected_summary.resolve()
        or supplied_summary.is_symlink()
        or not stat.S_ISREG(summary_info.st_mode)
    ):
        raise AuthorityPlanBlocked("housekeeping-summary-invalid")
    summary_commit = str(
        _git(root, "log", "-n", "1", "--format=%H", "--", D2H_SUMMARY_PATH.as_posix())
    ).strip()
    if (
        not HEX_40.fullmatch(expected_05d2d_summary_commit)
        or not HEX_40.fullmatch(summary_commit)
        or not _is_ancestor(root, expected_05d2d_summary_commit, summary_commit)
    ):
        raise AuthorityPlanBlocked("housekeeping-summary-ancestry-invalid")
    changed = sorted(
        str(
            _git(
                root,
                "diff-tree",
                "--root",
                "--no-commit-id",
                "--name-only",
                "-r",
                summary_commit,
            )
        ).splitlines()
    )
    if changed != [D2H_SUMMARY_PATH.as_posix()]:
        raise AuthorityPlanBlocked("housekeeping-summary-commit-invalid")
    try:
        quarantine_info = quarantine_root.lstat()
        pointer_info = quarantine_pointer.lstat()
    except OSError as exc:
        raise AuthorityPlanBlocked("housekeeping-pointer-invalid") from exc
    expected_pointer = quarantine_root / "current-phase53.json"
    if (
        quarantine_pointer != expected_pointer
        or quarantine_root.is_symlink()
        or not stat.S_ISDIR(quarantine_info.st_mode)
        or not _mode_is_private(quarantine_info, 0o700)
        or quarantine_pointer.is_symlink()
        or not stat.S_ISREG(pointer_info.st_mode)
        or not _mode_is_private(pointer_info, 0o600)
    ):
        raise AuthorityPlanBlocked("housekeeping-pointer-invalid")
    pointer_raw = _read_regular(
        quarantine_pointer, blocker="housekeeping-pointer-invalid", maximum=1_048_576
    )
    pointer = _strict_json_bytes(pointer_raw, blocker="housekeeping-pointer-invalid")
    if set(pointer) != {"manifest_path", "manifest_sha256", "generation_id"}:
        raise AuthorityPlanBlocked("housekeeping-pointer-invalid")
    generation_id = pointer.get("generation_id")
    if (
        not isinstance(generation_id, str)
        or not HEX_64.fullmatch(generation_id)
        or not HEX_64.fullmatch(str(pointer.get("manifest_sha256", "")))
    ):
        raise AuthorityPlanBlocked("housekeeping-pointer-invalid")
    generation = quarantine_root / generation_id
    manifest = Path(str(pointer.get("manifest_path", "")))
    try:
        generation_info = generation.lstat()
        manifest_info = manifest.lstat()
    except OSError as exc:
        raise AuthorityPlanBlocked("housekeeping-manifest-invalid") from exc
    if (
        generation.is_symlink()
        or not stat.S_ISDIR(generation_info.st_mode)
        or not _mode_is_private(generation_info, 0o700)
        or manifest != generation / "manifest.json"
        or manifest.is_symlink()
        or not stat.S_ISREG(manifest_info.st_mode)
        or not _mode_is_private(manifest_info, 0o600)
    ):
        raise AuthorityPlanBlocked("housekeeping-manifest-invalid")
    manifest_raw = _read_regular(
        manifest, blocker="housekeeping-manifest-invalid"
    )
    if hashlib.sha256(manifest_raw).hexdigest() != pointer["manifest_sha256"]:
        raise AuthorityPlanBlocked("housekeeping-manifest-digest-drift")
    document = _strict_json_bytes(
        manifest_raw, blocker="housekeeping-manifest-invalid"
    )
    if (
        document.get("status") != "complete"
        or document.get("generation_id") != generation_id
        or document.get("inventory_sha256") != generation_id
        or sorted(document.get("canonical_paths", []))
        != sorted(CANONICAL_05F_PATHS)
        or len(set(document.get("canonical_paths", []))) != 7
    ):
        raise AuthorityPlanBlocked("housekeeping-manifest-invalid")
    rows = document.get("files")
    moved = document.get("moved_paths")
    if (
        not isinstance(rows, list)
        or not isinstance(moved, list)
        or len(moved) != len(set(moved))
        or len(rows) != len(moved)
        or {row.get("source") for row in rows if isinstance(row, Mapping)}
        != set(moved)
        or not set(moved).issubset(CANONICAL_05F_PATHS)
    ):
        raise AuthorityPlanBlocked("housekeeping-manifest-invalid")
    backups: set[Path] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise AuthorityPlanBlocked("housekeeping-manifest-invalid")
        backup = Path(str(row.get("backup", "")))
        if backup in backups or backup.parent != generation or not backup.is_absolute():
            raise AuthorityPlanBlocked("housekeeping-backup-invalid")
        backups.add(backup)
        try:
            info = backup.lstat()
        except OSError as exc:
            raise AuthorityPlanBlocked("housekeeping-backup-invalid") from exc
        raw = _read_regular(backup, blocker="housekeeping-backup-invalid")
        if (
            backup.is_symlink()
            or not stat.S_ISREG(info.st_mode)
            or not _mode_is_private(info, 0o600)
            or type(row.get("size")) is not int
            or row["size"] != len(raw)
            or row.get("sha256") != hashlib.sha256(raw).hexdigest()
        ):
            raise AuthorityPlanBlocked("housekeeping-backup-invalid")
    if any(os.path.lexists(root / relative) for relative in CANONICAL_05F_PATHS):
        raise AuthorityPlanBlocked("housekeeping-canonical-path-present")
    absent_digest = _sha256(
        [
            {"path": relative, "lexically_absent": True}
            for relative in CANONICAL_05F_PATHS
        ]
    )
    text = supplied_summary.read_text(encoding="utf-8")
    expected_summary_values = {
        "quarantine_manifest_sha256": pointer["manifest_sha256"],
        "generation_id": generation_id,
        "canonical_paths_absent": "true",
    }
    for key, expected in expected_summary_values.items():
        if _summary_value(text, key).lower() != str(expected).lower():
            raise AuthorityPlanBlocked("housekeeping-summary-binding-invalid")
    return {
        "05D2H_summary_commit": summary_commit,
        "quarantine_manifest_sha256": pointer["manifest_sha256"],
        "generation_id": generation_id,
        "canonical_seven_absent_sha256": absent_digest,
        "canonical_paths_absent": True,
        "provider_writes": 0,
        "live_mutations": 0,
    }


def _cross_fields(
    *, generation_id: str, source_binding: Mapping[str, Any], phase52: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "generation_id": generation_id,
        "execution_source_commit": source_binding["execution_source_commit"],
        "execution_source_tree_sha256": source_binding[
            "execution_source_tree_sha256"
        ],
        "phase52_successor_sha256": phase52["successor_attestation_sha256"],
        "mutation_performed": False,
        "secret_material_present": False,
    }


def build_authority_payloads(
    *,
    observation: Mapping[str, Any],
    source_binding: Mapping[str, Any],
    phase52: Mapping[str, Any],
    housekeeping_receipt: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    current = _trusted_now(now)
    observed = validate_authority_observation(observation, now=current)
    if (
        not HEX_40.fullmatch(
            str(source_binding.get("execution_source_commit", ""))
        )
        or not HEX_64.fullmatch(
            str(source_binding.get("execution_source_tree_sha256", ""))
        )
        or len(source_binding.get("manifest_paths", [])) != 34
    ):
        raise AuthorityPlanBlocked("execution-source-binding-invalid")
    if (
        phase52.get("authorizes_live") is not False
        or phase52.get("historical_replay") is not False
        or phase52.get("historical_rebaseline") is not False
        or housekeeping_receipt.get("canonical_paths_absent") is not True
    ):
        raise AuthorityPlanBlocked("authority-input-invalid")
    generation_id = _sha256(
        {
            "observation": observed,
            "source": source_binding,
            "phase52": phase52,
            "housekeeping": housekeeping_receipt,
        }
    )
    common = _cross_fields(
        generation_id=generation_id, source_binding=source_binding, phase52=phase52
    )
    housekeeping_binding = {
        "05D2H_summary_commit": housekeeping_receipt["05D2H_summary_commit"],
        "quarantine_manifest_sha256": housekeeping_receipt[
            "quarantine_manifest_sha256"
        ],
        "quarantine_generation_id": housekeeping_receipt["generation_id"],
        "canonical_seven_absent_sha256": housekeeping_receipt[
            "canonical_seven_absent_sha256"
        ],
        "canonical_paths_absent": True,
    }
    topology = {
        **common,
        "schema_version": 1,
        "state": "CURRENT",
        "observed_at": observed["observed_at"],
        "topology": observed["topology"],
        "read_only": True,
    }
    successor = {
        **common,
        "schema_version": 1,
        "state": "CURRENT",
        "source_freeze_commit": phase52["source_freeze_commit"],
        "attestation_commit": phase52["attestation_commit"],
        "closeout_commit": phase52["closeout_commit"],
        "reviewer_ids": phase52["reviewer_ids"],
        "historical_replay": False,
        "historical_rebaseline": False,
        "authorizes_live": False,
        "vault_write_authorized": False,
    }
    candidate = {
        **common,
        "schema_version": 1,
        "state": "CURRENT",
        "selected_primary": "horistic-srv",
        "supply": observed["supply"],
        "admission_performed": False,
        "owner_approval_recorded": False,
    }
    capacity = {
        **common,
        "schema_version": 1,
        "state": "CURRENT",
        "placement_order": ["atius-srv-2", "atius-srv-3", "horistic-srv"],
        "selected_primary": "horistic-srv",
        "samples": observed["capacity_samples"],
        "zero_cleanup_performed": False,
    }
    preflight = {
        **common,
        "schema_version": 1,
        "state": "CURRENT",
        "observed_at": observed["observed_at"],
        "topology": observed["topology"],
        "vault_public_fingerprint": observed["vault_public_fingerprint"],
        "provider": observed["provider"],
        "rollback_ready": True,
        **housekeeping_binding,
        "journal_created": False,
        "provider_constructed": False,
    }
    dependencies = {
        "topology-discovery.json": topology,
        "phase52-successor-attestation.json": successor,
        "candidate-admission.json": candidate,
        "capacity-current.json": capacity,
        "preflight.json": preflight,
    }
    dependency_digests = {
        name: _sha256(payload) for name, payload in dependencies.items()
    }
    expires_at = (
        current.replace(microsecond=0) + timedelta(hours=1)
    ).isoformat().replace("+00:00", "Z")
    operation_core = {
        **common,
        "schema_version": 1,
        "status": "AWAITING_OWNER_HASH_APPROVAL",
        "target": "10.21.1.21",
        "public_edge": observed["topology"],
        "dependency_digests": dependency_digests,
        "typed_confirmations": {
            surface: observed["provider"]["previews"][surface][
                "confirmation_sha256"
            ]
            for surface in ("host", "oci", "cloudflare", "apache")
        },
        "expected_05f_prestate": {
            path: "absent" for path in CANONICAL_05F_PATHS
        },
        **housekeeping_binding,
        "expires_at": expires_at,
        "risk_acknowledgement_required": True,
        "rollback_acknowledgement_required": True,
        "owner_approval_recorded": False,
        "journal_created": False,
        "provider_constructed": False,
    }
    plan_digest = _sha256(operation_core)
    operation_plan = {
        **operation_core,
        "operation_plan_sha256": plan_digest,
    }
    return {
        **{
            name: {**payload, "operation_plan_sha256": plan_digest}
            for name, payload in dependencies.items()
        },
        "edge-forwarder-operation-plan.json": operation_plan,
    }


def validate_authority_generation(
    directory: Path, *, expected_generation: str | None = None
) -> dict[str, Any]:
    marker_path = directory / "edge-forwarder-operation-plan.json"
    marker = _strict_json_file(marker_path, blocker="authority-marker-invalid")
    generation = marker.get("generation_id")
    if (
        not isinstance(generation, str)
        or not HEX_64.fullmatch(generation)
        or (expected_generation is not None and generation != expected_generation)
    ):
        raise AuthorityPlanBlocked("authority-generation-invalid")
    if any(not (directory / name).is_file() for name in AUTHORITY_FILENAMES):
        raise AuthorityPlanBlocked("authority-generation-partial")
    plan_digest = marker.get("operation_plan_sha256")
    operation_core = dict(marker)
    operation_core.pop("operation_plan_sha256", None)
    if (
        not isinstance(plan_digest, str)
        or _sha256(operation_core) != plan_digest
    ):
        raise AuthorityPlanBlocked("authority-plan-digest-drift")
    for name in DEPENDENCY_FILENAMES:
        payload = _strict_json_file(
            directory / name, blocker="authority-dependency-invalid"
        )
        normalized = dict(payload)
        if normalized.pop("operation_plan_sha256", None) != plan_digest:
            raise AuthorityPlanBlocked("authority-cross-binding-invalid")
        if (
            payload.get("generation_id") != generation
            or _sha256(normalized) != marker["dependency_digests"].get(name)
        ):
            raise AuthorityPlanBlocked("authority-dependency-digest-drift")
    return marker


def _write_exclusive(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError as exc:
        raise AuthorityPlanBlocked("output-exists") from exc
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(path, mode)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def promote_authority_generation(
    output_dir: Path,
    payloads: Mapping[str, Mapping[str, Any]],
    *,
    fail_after: int | None = None,
) -> dict[str, Any]:
    if set(payloads) != set(AUTHORITY_FILENAMES):
        raise AuthorityPlanBlocked("authority-payload-set-invalid")
    output_dir.mkdir(parents=True, exist_ok=True)
    generation = payloads["edge-forwarder-operation-plan.json"].get("generation_id")
    with tempfile.TemporaryDirectory(
        prefix=".phase53-authority-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary)
        for name in AUTHORITY_FILENAMES:
            _write_exclusive(staging / name, canonical_bytes(payloads[name]))
        validate_authority_generation(staging, expected_generation=str(generation))
        promoted = 0
        for name in DEPENDENCY_FILENAMES:
            os.replace(staging / name, output_dir / name)
            promoted += 1
            if fail_after == promoted:
                raise AuthorityPlanBlocked("injected-promotion-failure")
        os.replace(
            staging / "edge-forwarder-operation-plan.json",
            output_dir / "edge-forwarder-operation-plan.json",
        )
    return validate_authority_generation(
        output_dir, expected_generation=str(generation)
    )


def awaiting_owner_result(operation_plan: Mapping[str, Any]) -> dict[str, Any]:
    if (
        operation_plan.get("status") != "AWAITING_OWNER_HASH_APPROVAL"
        or operation_plan.get("mutation_performed") is not False
        or operation_plan.get("secret_material_present") is not False
    ):
        raise AuthorityPlanBlocked("operation-plan-not-awaiting-owner")
    return {
        "status": "AWAITING_OWNER_HASH_APPROVAL",
        "exit_code": 0,
        "operation_plan_sha256": operation_plan["operation_plan_sha256"],
        "owner_record_created": False,
        "journal_created": False,
        "provider_constructed": False,
        "mutation_performed": False,
        "secret_material_present": False,
    }


def build_owner_approval(
    response: Mapping[str, Any],
    operation_plan: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _trusted_now(now)
    required = {
        "owner",
        "decision",
        "operation_plan_sha256",
        "expires_at",
        "risk_acknowledged",
        "rollback_acknowledged",
    }
    projected = canonical_projection(response)
    if not isinstance(projected, Mapping) or set(projected) != required:
        raise AuthorityPlanBlocked("owner-response-invalid")
    if (
        projected["owner"] != "Giovanni Muniz"
        or projected["decision"] != "approve"
        or projected["risk_acknowledged"] is not True
        or projected["rollback_acknowledged"] is not True
    ):
        raise AuthorityPlanBlocked("owner-response-invalid")
    if (
        projected["operation_plan_sha256"]
        != operation_plan.get("operation_plan_sha256")
    ):
        raise AuthorityPlanBlocked("owner-plan-hash-mismatch")
    expiry = _parse_utc(projected["expires_at"], blocker="owner-expiry-invalid")
    plan_expiry = _parse_utc(
        operation_plan.get("expires_at"), blocker="operation-plan-expiry-invalid"
    )
    if expiry <= current or expiry > plan_expiry:
        raise AuthorityPlanBlocked("owner-expiry-invalid")
    return {
        "schema_version": 1,
        "owner": "Giovanni Muniz",
        "decision": "approve",
        "operation_plan_sha256": projected["operation_plan_sha256"],
        "execution_source_commit": operation_plan["execution_source_commit"],
        "execution_source_tree_sha256": operation_plan[
            "execution_source_tree_sha256"
        ],
        "expires_at": projected["expires_at"],
        "risk_acknowledged": True,
        "rollback_acknowledged": True,
        "response_sha256": _sha256(projected),
        "secret_material_present": False,
        "mutation_performed": False,
    }


def write_owner_record(output: Path, approval: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "owner",
        "decision",
        "operation_plan_sha256",
        "execution_source_commit",
        "execution_source_tree_sha256",
        "expires_at",
        "risk_acknowledged",
        "rollback_acknowledged",
        "response_sha256",
        "secret_material_present",
        "mutation_performed",
    }
    projected = canonical_projection(approval)
    if not isinstance(projected, Mapping) or set(projected) != expected:
        raise AuthorityPlanBlocked("owner-record-invalid")
    _write_exclusive(output, canonical_bytes(projected))


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AuthorityPlanBlocked("module-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(spec.name, None)
        raise AuthorityPlanBlocked("module-unavailable") from exc
    return module


def _metadata(text: str, key: str) -> str:
    values = re.findall(
        rf"(?mi)^\s*(?:[-*]\s*)?[`'\"]?{re.escape(key)}[`'\"]?\s*[:=]\s*[`'\"]?([^`'\"\s]+)",
        text,
    )
    unique = list(dict.fromkeys(values))
    if len(unique) != 1:
        raise AuthorityPlanBlocked(f"summary-field-invalid:{key}")
    return unique[0]


def _source_binding_from_summary(repo: Path) -> dict[str, Any]:
    text = (repo / D2D_SUMMARY_PATH).read_text(encoding="utf-8")
    commit = _metadata(text, "execution_source_commit")
    tree = _metadata(text, "execution_source_tree_sha256")
    checker = _load_module(
        repo / "modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py",
        "_phase53_authority_binding_checker",
    )
    scope = _strict_json_file(
        repo / SOURCE_SCOPE_PATH, blocker="execution-source-scope-invalid"
    )
    paths = checker.validate_execution_source_scope_payload(scope)
    checker.validate_execution_source_commit_paths(repo, commit)
    return checker.require_clean_execution_source(
        repo=repo,
        execution_source_commit=commit,
        manifest_paths=paths,
        expected_tree=tree,
    )


def _collect_cli(repo: Path, output: Path) -> dict[str, Any]:
    backend = _load_module(
        repo / "modules/rustdesk-fleet/tools/phase53-live-backend.py",
        "_phase53_authority_read_only_backend",
    )
    source = _source_binding_from_summary(repo)
    binding = backend.ExecutionSourceBinding(
        commit=source["execution_source_commit"],
        tree_sha256=source["execution_source_tree_sha256"],
        blobs={
            path: row["content_sha256"] for path, row in source["blobs"].items()
        },
    )
    bundle = backend.build_phase53_read_only_backend(
        repo=repo,
        manifest_path=repo / PROVIDER_MANIFEST_PATH,
        source_binding=binding,
        clock=lambda: datetime.now(timezone.utc),
    )
    return collect_read_only_observation(
        bundle,
        observed_at=datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        output=output,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect = subparsers.add_parser("collect-observation")
    collect.add_argument("--repo", type=Path, required=True)
    collect.add_argument("--output", type=Path, required=True)
    build = subparsers.add_parser("build-plan")
    build.add_argument("--repo", type=Path, required=True)
    build.add_argument("--observation", type=Path, required=True)
    build.add_argument("--housekeeping-receipt", type=Path, required=True)
    build.add_argument("--quarantine-pointer", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    owner = subparsers.add_parser("record-owner")
    owner.add_argument("--repo", type=Path, required=True)
    owner.add_argument("--response", type=Path, required=True)
    owner.add_argument("--operation-plan", type=Path, required=True)
    owner.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        repo = args.repo.resolve(strict=True)
        if args.command == "collect-observation":
            result = _collect_cli(repo, args.output)
        elif args.command == "build-plan":
            observation = _strict_json_file(
                args.observation, blocker="observation-file-invalid"
            )
            source = _source_binding_from_summary(repo)
            d2d_commit = str(
                _git(
                    repo,
                    "log",
                    "-n",
                    "1",
                    "--format=%H",
                    "--",
                    D2D_SUMMARY_PATH.as_posix(),
                )
            ).strip()
            receipt = validate_housekeeping_receipt(
                repo=repo,
                summary_path=args.housekeeping_receipt,
                quarantine_pointer=args.quarantine_pointer,
                expected_05d2d_summary_commit=d2d_commit,
            )
            payloads = build_authority_payloads(
                observation=observation,
                source_binding=source,
                phase52=validate_frozen_phase52(repo),
                housekeeping_receipt=receipt,
            )
            result = awaiting_owner_result(
                promote_authority_generation(args.output_dir, payloads)
            )
        else:
            response = _strict_json_file(
                args.response, blocker="owner-response-invalid"
            )
            plan = _strict_json_file(
                args.operation_plan, blocker="operation-plan-invalid"
            )
            approval = build_owner_approval(response, plan)
            write_owner_record(args.output, approval)
            result = {
                "status": "OWNER_HASH_APPROVED",
                "owner_record_created": True,
                "journal_created": False,
                "provider_constructed": False,
                "mutation_performed": False,
                "secret_material_present": False,
            }
    except (AuthorityPlanBlocked, OSError, ValueError) as exc:
        payload = {
            "status": "BLOCKED",
            "blocker": str(exc)
            if isinstance(exc, AuthorityPlanBlocked)
            else "authority-input-invalid",
            "owner_record_created": False,
            "journal_created": False,
            "provider_constructed": False,
            "mutation_performed": False,
            "secret_material_present": False,
        }
        sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
