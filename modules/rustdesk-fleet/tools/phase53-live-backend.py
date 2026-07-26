#!/usr/bin/env python3
"""Capability-disjoint backend factories for the Phase 53 live workflow.

The read-only factory returns only deterministic read/preview callables.  The
apply factory can expose reviewed runtime/provider adapters only after explicit
live, admission, owner, hash, target, and expiry gates all pass.  Neither
factory executes a callback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import MappingProxyType
from typing import Any, Callable, Literal, Mapping


ExecutionMode = Literal["plan", "apply"]
Phase53Stage = Literal[
    "full",
    "edge-probes",
    "ops-api",
    "lifecycle",
    "rollback",
    "restore-production",
]

EXPECTED_MANIFEST_KEYS = {
    "schema_version",
    "phase",
    "workstream",
    "manifest_id",
    "execution_target",
    "edge_contract",
    "capability_profiles",
    "backends",
    "routes",
    "command_classes",
    "limits",
    "secret_material_present",
}
EXPECTED_EDGE_CONTRACT = "modules/rustdesk-fleet/contracts/phase53-edge.json"
HEX_40 = re.compile(r"[0-9a-f]{40}")
HEX_64 = re.compile(r"[0-9a-f]{64}")


class BackendBlocked(RuntimeError):
    """A backend factory refused an ambiguous or excessive capability."""


def _load_production_types() -> Any:
    name = "_atius_phase53_production_adapters"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = Path(__file__).with_name("phase53_production_adapters.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise BackendBlocked("production-adapter-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(name, None)
        raise BackendBlocked("production-adapter-unavailable") from exc
    return module


_PRODUCTION = _load_production_types()
RuntimeProvider = _PRODUCTION.RuntimeProvider
ProviderBundle = _PRODUCTION.ProviderBundle
RUNTIME_EDGE_STAGES = tuple(
    stage for stage in _PRODUCTION.EDGE_SEQUENCE if stage != "runtime"
)


def _duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise BackendBlocked("provider-manifest-invalid")
        result[key] = value
    return result


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65_536:
            raise BackendBlocked("provider-manifest-invalid")
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_duplicate_keys,
        )
    except BackendBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BackendBlocked("provider-manifest-invalid") from exc
    if not isinstance(payload, dict):
        raise BackendBlocked("provider-manifest-invalid")
    return payload


def validate_provider_manifest(manifest: Mapping[str, Any], *, repo: Path) -> None:
    """Validate the exact bounded provider/capability authority."""

    if not isinstance(manifest, Mapping) or set(manifest) != EXPECTED_MANIFEST_KEYS:
        raise BackendBlocked("provider-manifest-invalid")
    if (
        manifest.get("schema_version") != 2
        or manifest.get("phase") != 53
        or manifest.get("workstream") != "rustdesk-fleet"
        or manifest.get("manifest_id") != "phase53-production-providers-v1"
        or manifest.get("secret_material_present") is not False
    ):
        raise BackendBlocked("provider-manifest-invalid")
    if manifest.get("execution_target") != "10.21.1.21":
        raise BackendBlocked("provider-manifest-target-invalid")
    if manifest.get("edge_contract") != EXPECTED_EDGE_CONTRACT:
        raise BackendBlocked("provider-manifest-edge-contract-invalid")
    edge_path = (repo.resolve() / EXPECTED_EDGE_CONTRACT).resolve()
    try:
        edge_path.relative_to(repo.resolve())
    except ValueError as exc:
        raise BackendBlocked("provider-manifest-edge-contract-invalid") from exc
    if not edge_path.is_file() or edge_path.is_symlink():
        raise BackendBlocked("provider-manifest-edge-contract-invalid")
    if manifest.get("backends") != {
        "read_only": "phase53-read-only-v1",
        "apply": "phase53-apply-v1",
    }:
        raise BackendBlocked("provider-manifest-backend-invalid")
    if manifest.get("capability_profiles") != {
        "read_only": ["read", "preview"],
        "apply": ["read", "preview", "mutate", "contain", "rollback", "restore"],
    }:
        raise BackendBlocked("provider-manifest-capability-invalid")
    limits = manifest.get("limits")
    if (
        not isinstance(limits, Mapping)
        or set(limits)
        != {
            "command_timeout_seconds",
            "max_stdout_bytes",
            "max_stderr_bytes",
            "journal_mode",
        }
        or type(limits["command_timeout_seconds"]) is not int
        or not 1 <= limits["command_timeout_seconds"] <= 30
        or type(limits["max_stdout_bytes"]) is not int
        or not 1 <= limits["max_stdout_bytes"] <= 131_072
        or type(limits["max_stderr_bytes"]) is not int
        or not 1 <= limits["max_stderr_bytes"] <= 8_192
        or limits["journal_mode"] != "value-free-0600"
    ):
        raise BackendBlocked("provider-manifest-limit-invalid")
    routes = manifest.get("routes")
    if not isinstance(routes, Mapping) or set(routes) != {
        "ssh",
        "vault",
        "oci",
        "cloudflare",
        "apache",
    }:
        raise BackendBlocked("provider-manifest-route-invalid")
    cloudflare = routes["cloudflare"]
    if not isinstance(cloudflare, Mapping) or cloudflare.get("records") != [
        "rustdesk.atius.com.br",
        "rustdesk-id.atius.com.br",
        "rustdesk-relay.atius.com.br",
    ]:
        raise BackendBlocked("provider-manifest-route-invalid")
    command_classes = manifest.get("command_classes")
    if (
        not isinstance(command_classes, Mapping)
        or set(command_classes) != {"allowlisted", "forbidden"}
        or command_classes["forbidden"]
        != ["shell-eval", "ambient-path-search", "ambient-ssh-config", "raw-secret-output"]
        or not isinstance(command_classes["allowlisted"], list)
        or len(command_classes["allowlisted"]) != len(set(command_classes["allowlisted"]))
    ):
        raise BackendBlocked("provider-manifest-command-invalid")


@dataclass(frozen=True)
class ExecutionSourceBinding:
    commit: str
    tree_sha256: str
    blobs: Mapping[str, str]

    def __post_init__(self) -> None:
        if not HEX_40.fullmatch(self.commit) or not HEX_64.fullmatch(self.tree_sha256):
            raise BackendBlocked("source-binding-invalid")
        if (
            not isinstance(self.blobs, Mapping)
            or not self.blobs
            or any(
                not isinstance(path, str)
                or path.startswith("/")
                or ".." in Path(path).parts
                or not isinstance(digest, str)
                or not HEX_64.fullmatch(digest)
                for path, digest in self.blobs.items()
            )
        ):
            raise BackendBlocked("source-binding-invalid")
        object.__setattr__(self, "blobs", MappingProxyType(dict(self.blobs)))


@dataclass(frozen=True)
class ReadOnlyProviderBundle:
    read_prestate: Callable[[], Mapping[str, Any]]
    preview_oci: Callable[[], Mapping[str, Any]]
    preview_cloudflare: Callable[[], Mapping[str, Any]]
    preview_apache: Callable[[], Mapping[str, Any]]
    capabilities: frozenset[str] = frozenset({"read", "preview"})


@dataclass(frozen=True)
class ApplyProviderBundle:
    runtime: RuntimeProvider
    providers: ProviderBundle
    operation_plan_sha256: str
    approval_sha256: str


def _utc_now(clock: Callable[[], datetime]) -> datetime:
    current = clock()
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise BackendBlocked("trusted-clock-invalid")
    return current.astimezone(timezone.utc)


def _preview(
    surface: str,
    *,
    manifest_id: str,
    target: str,
    source_binding: ExecutionSourceBinding,
    observed_at: str,
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "schema_version": 1,
            "mode": "preview",
            "surface": surface,
            "manifest_id": manifest_id,
            "target": target,
            "source_commit": source_binding.commit,
            "source_tree_sha256": source_binding.tree_sha256,
            "observed_at": observed_at,
            "mutation_performed": False,
            "secret_material_present": False,
        }
    )


def build_phase53_read_only_backend(
    *,
    repo: Path,
    manifest_path: Path,
    source_binding: ExecutionSourceBinding,
    clock: Callable[[], datetime],
) -> ReadOnlyProviderBundle:
    manifest = _load_manifest(manifest_path)
    validate_provider_manifest(manifest, repo=repo)
    observed_at = _utc_now(clock).isoformat(timespec="seconds").replace("+00:00", "Z")
    common = {
        "manifest_id": str(manifest["manifest_id"]),
        "target": str(manifest["execution_target"]),
        "source_binding": source_binding,
        "observed_at": observed_at,
    }
    return ReadOnlyProviderBundle(
        read_prestate=lambda: _preview("prestate", **common),
        preview_oci=lambda: _preview("oci", **common),
        preview_cloudflare=lambda: _preview("cloudflare", **common),
        preview_apache=lambda: _preview("apache", **common),
    )


def _future(value: Any, now: datetime, blocker: str) -> datetime:
    if not isinstance(value, str):
        raise BackendBlocked(blocker)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BackendBlocked(blocker) from exc
    if parsed.tzinfo is None or parsed.astimezone(timezone.utc) <= now:
        raise BackendBlocked(blocker)
    return parsed.astimezone(timezone.utc)


def build_phase53_apply_backend(
    *,
    repo: Path,
    manifest_path: Path,
    operation_plan: Mapping[str, Any],
    owner_approval: Mapping[str, Any],
    live_enabled: bool,
    admitted: bool,
    clock: Callable[[], datetime],
) -> ApplyProviderBundle:
    if live_enabled is not True:
        raise BackendBlocked("live-flag-required")
    if admitted is not True:
        raise BackendBlocked("admission-required")
    manifest = _load_manifest(manifest_path)
    validate_provider_manifest(manifest, repo=repo)
    now = _utc_now(clock)
    if not isinstance(operation_plan, Mapping) or set(operation_plan) != {
        "schema_version",
        "target",
        "operation_plan_sha256",
        "expires_at",
        "runtime",
        "providers",
    }:
        raise BackendBlocked("operation-plan-invalid")
    if (
        operation_plan["schema_version"] != 1
        or operation_plan["target"] != manifest["execution_target"]
        or not isinstance(operation_plan["operation_plan_sha256"], str)
        or not HEX_64.fullmatch(operation_plan["operation_plan_sha256"])
        or not isinstance(operation_plan["runtime"], RuntimeProvider)
        or not isinstance(operation_plan["providers"], ProviderBundle)
    ):
        raise BackendBlocked("operation-plan-invalid")
    _future(operation_plan["expires_at"], now, "operation-plan-expired")
    if not isinstance(owner_approval, Mapping) or set(owner_approval) != {
        "schema_version",
        "owner",
        "operation_plan_sha256",
        "approval_sha256",
        "expires_at",
    }:
        raise BackendBlocked("owner-approval-invalid")
    if (
        owner_approval["schema_version"] != 1
        or owner_approval["owner"] != "Giovanni Muniz"
        or owner_approval["operation_plan_sha256"]
        != operation_plan["operation_plan_sha256"]
        or not isinstance(owner_approval["approval_sha256"], str)
        or not HEX_64.fullmatch(owner_approval["approval_sha256"])
    ):
        raise BackendBlocked("owner-approval-invalid")
    _future(owner_approval["expires_at"], now, "owner-approval-expired")
    return ApplyProviderBundle(
        runtime=operation_plan["runtime"],
        providers=operation_plan["providers"],
        operation_plan_sha256=operation_plan["operation_plan_sha256"],
        approval_sha256=owner_approval["approval_sha256"],
    )


__all__ = [
    "ApplyProviderBundle",
    "BackendBlocked",
    "ExecutionMode",
    "ExecutionSourceBinding",
    "Phase53Stage",
    "ProviderBundle",
    "ReadOnlyProviderBundle",
    "RUNTIME_EDGE_STAGES",
    "RuntimeProvider",
    "build_phase53_apply_backend",
    "build_phase53_read_only_backend",
    "validate_provider_manifest",
]
