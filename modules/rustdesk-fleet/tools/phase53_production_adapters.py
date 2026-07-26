#!/usr/bin/env python3
"""Typed, bounded provider seam for the Phase 53 live gate.

This module deliberately contains no default SSH/Vault/OCI/Cloudflare/Apache
implementation.  A deployment must inject reviewed callbacks after the live
authority gates have passed.  The seam turns callback metadata into the
value-free ``StageReceipt`` shape consumed by ``run-phase53-live-gate.py`` and
rejects ambient commands, secrets, verdicts, and route drift before a callback
can run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable, Mapping

try:
    from phase53_live_adapters import (
        AdapterBlocked,
        CONTAINMENT_STAGE,
        EDGE_SEQUENCE,
        ProductionBackend,
        SECRET_KEYS,
        VERDICT_KEYS,
        redact,
    )
except ModuleNotFoundError:  # loaded directly by a test/spec rather than CLI
    import importlib.util
    from pathlib import Path
    import sys

    _path = Path(__file__).with_name("phase53-live-adapters.py")
    _spec = importlib.util.spec_from_file_location("phase53_live_adapters", _path)
    if _spec is None or _spec.loader is None:
        raise
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
    AdapterBlocked = _module.AdapterBlocked
    CONTAINMENT_STAGE = _module.CONTAINMENT_STAGE
    EDGE_SEQUENCE = _module.EDGE_SEQUENCE
    ProductionBackend = _module.ProductionBackend
    SECRET_KEYS = _module.SECRET_KEYS
    VERDICT_KEYS = _module.VERDICT_KEYS
    redact = _module.redact


ProviderCallback = Callable[[], Mapping[str, Any]]

REQUIRED_ROUTE_KEYS = {"ssh", "vault", "oci", "cloudflare", "apache"}
REQUIRED_ALLOWLIST = {
    "ssh-batch-safe",
    "vault-profile-dispatch",
    "oci-cas-read-write",
    "cloudflare-dns-cas",
    "apache-configtest-reload",
    "rustdesk-server-transaction",
    "rustdesk-edge-transaction",
    "two-origin-probes",
}
FORBIDDEN_COMMANDS = {
    "shell-eval",
    "ambient-path-search",
    "ambient-ssh-config",
    "raw-secret-output",
}
CURRENT_EXECUTION_TARGET = "10.21.1.21"
FUTURE_EXECUTION_TARGET = "10.31.1.31"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _contains_secret(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in SECRET_KEYS and child != "[REDACTED]":
                return True
            if _contains_secret(child):
                return True
    elif isinstance(value, list):
        return any(_contains_secret(child) for child in value)
    elif isinstance(value, str):
        lowered = value.lower()
        return lowered.startswith("bearer ") or "fixture-secret" in lowered
    return False


def _contains_verdict(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in VERDICT_KEYS or (
                lowered == "status" and isinstance(child, str) and child.upper() == "PASS"
            ):
                return True
            if _contains_verdict(child):
                return True
    elif isinstance(value, list):
        return any(_contains_verdict(child) for child in value)
    return False


def validate_provider_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the reviewed provider manifest without resolving a provider."""

    routes = manifest.get("routes")
    classes = manifest.get("command_classes")
    limits = manifest.get("limits")
    if not isinstance(routes, Mapping) or set(routes) != REQUIRED_ROUTE_KEYS:
        raise AdapterBlocked("provider-manifest-routes-invalid")
    if manifest.get("execution_target") == FUTURE_EXECUTION_TARGET:
        raise AdapterBlocked("provider-manifest-target-invalid")
    if manifest.get("execution_target") != CURRENT_EXECUTION_TARGET:
        raise AdapterBlocked("provider-manifest-target-invalid")
    if not isinstance(classes, Mapping):
        raise AdapterBlocked("provider-manifest-command-classes-invalid")
    allowlisted = classes.get("allowlisted")
    forbidden = classes.get("forbidden")
    if (
        not isinstance(allowlisted, list)
        or set(allowlisted) != REQUIRED_ALLOWLIST
        or not isinstance(forbidden, list)
        or not FORBIDDEN_COMMANDS.issubset(set(forbidden))
    ):
        raise AdapterBlocked("provider-manifest-command-classes-invalid")
    if not isinstance(limits, Mapping):
        raise AdapterBlocked("provider-manifest-limits-invalid")
    timeout = limits.get("command_timeout_seconds")
    stdout = limits.get("max_stdout_bytes")
    stderr = limits.get("max_stderr_bytes")
    if (
        not isinstance(timeout, int)
        or not 1 <= timeout <= 30
        or not isinstance(stdout, int)
        or not 1 <= stdout <= 131072
        or not isinstance(stderr, int)
        or not 1 <= stderr <= 8192
        or limits.get("journal_mode") != "value-free-0600"
        or manifest.get("secret_material_present") is not False
    ):
        raise AdapterBlocked("provider-manifest-limits-invalid")
    ssh = routes["ssh"]
    if (
        not isinstance(ssh, Mapping)
        or ssh.get("batch_mode") is not True
        or ssh.get("stdin_safe") is not True
        or ssh.get("known_hosts_required") is not True
        or ssh.get("fallback_only_on") != ["tcp-or-banner-or-ssh-rc255"]
    ):
        raise AdapterBlocked("provider-manifest-ssh-route-invalid")
    vault = routes["vault"]
    if (
        not isinstance(vault, Mapping)
        or vault.get("provider") != "hashicorp-vault"
        or vault.get("value_free_output") is not True
    ):
        raise AdapterBlocked("provider-manifest-vault-route-invalid")
    oci = routes["oci"]
    targets = oci.get("execution_targets") if isinstance(oci, Mapping) else None
    backend = targets.get("backend") if isinstance(targets, Mapping) else None
    if (
        not isinstance(backend, Mapping)
        or backend.get("private_ipv4") == FUTURE_EXECUTION_TARGET
        or backend.get("private_ipv4") != CURRENT_EXECUTION_TARGET
    ):
        raise AdapterBlocked("provider-manifest-target-invalid")


def select_ssh_route(private_rc: int) -> str:
    """Return the route selected by the approved W11 private-first policy."""

    if private_rc == 0:
        return "private"
    if private_rc == 255:
        return "public-native-fallback"
    raise AdapterBlocked("ssh-private-probe-failed")


def validate_command_argv(argv: Any) -> tuple[str, ...]:
    """Reject shell/eval and ambient command construction before execution."""

    if not isinstance(argv, (list, tuple)) or not argv or not all(
        isinstance(item, str) and item for item in argv
    ):
        raise AdapterBlocked("provider-argv-invalid")
    forbidden = {"sh", "bash", "zsh", "-c", "--command", "eval"}
    if any(item in forbidden or any(token in item for token in ("$(", "`", ";")) for item in argv):
        raise AdapterBlocked("provider-shell-eval-forbidden")
    return tuple(argv)


@dataclass(frozen=True)
class ProviderBundle:
    """Explicit callbacks supplied by a reviewed deployment embedding."""

    stages: Mapping[str, ProviderCallback]
    containment: ProviderCallback
    transaction_id: str


@dataclass(frozen=True)
class RuntimeProvider:
    """Hermetic runtime transaction adapter built only from injected callbacks.

    This adapter intentionally has no default constructor for SSH, Vault,
    subprocesses or environment discovery.  The factory is called by the
    caller-supplied provider bundle only after the live authority gates have
    passed.  The runtime stage performs the smallest server transaction unit
    (pre-state, closed install, rollback on fault); all edge stages remain
    explicit callbacks supplied by the same caller.
    """

    transaction_id: str
    snapshot_prestate: ProviderCallback
    install_closed: ProviderCallback
    rollback_server: ProviderCallback
    edge_stages: Mapping[str, ProviderCallback]
    containment: ProviderCallback

    def to_bundle(self) -> ProviderBundle:
        """Return a value-free provider bundle without invoking a callback."""

        transaction_id = self.transaction_id
        if (
            not isinstance(transaction_id, str)
            or len(transaction_id) != 32
            or any(character not in "0123456789abcdef" for character in transaction_id)
        ):
            raise AdapterBlocked("runtime-provider-transaction-invalid")

        required_edge_stages = set(EDGE_SEQUENCE) - {"runtime"}
        if not isinstance(self.edge_stages, Mapping) or set(self.edge_stages) != required_edge_stages:
            raise AdapterBlocked("runtime-provider-stage-set-invalid")
        callbacks = {
            "snapshot_prestate": self.snapshot_prestate,
            "install_closed": self.install_closed,
            "rollback_server": self.rollback_server,
            "containment": self.containment,
            **{f"edge:{stage}": callback for stage, callback in self.edge_stages.items()},
        }
        invalid = [name for name, callback in callbacks.items() if not callable(callback)]
        if invalid:
            raise AdapterBlocked(f"runtime-provider-callback-invalid:{','.join(invalid)}")

        def runtime_stage() -> Mapping[str, Any]:
            try:
                prestate = self.snapshot_prestate()
            except Exception as exc:
                raise AdapterBlocked("runtime-provider-prestate-failed") from exc
            if not isinstance(prestate, Mapping):
                raise AdapterBlocked("runtime-provider-prestate-invalid")
            if _contains_secret(prestate) or _contains_verdict(prestate):
                raise AdapterBlocked("runtime-provider-prestate-output-invalid")

            try:
                installed = self.install_closed()
            except Exception as exc:
                try:
                    rollback = self.rollback_server()
                except Exception as rollback_exc:
                    raise AdapterBlocked("runtime-provider-rollback-failed") from rollback_exc
                if not isinstance(rollback, Mapping):
                    raise AdapterBlocked("runtime-provider-rollback-invalid")
                raise AdapterBlocked("runtime-provider-install-failed") from exc
            if not isinstance(installed, Mapping):
                try:
                    self.rollback_server()
                except Exception as rollback_exc:
                    raise AdapterBlocked("runtime-provider-rollback-failed") from rollback_exc
                raise AdapterBlocked("runtime-provider-install-invalid")
            if _contains_secret(installed) or _contains_verdict(installed):
                try:
                    self.rollback_server()
                except Exception as rollback_exc:
                    raise AdapterBlocked("runtime-provider-rollback-failed") from rollback_exc
                raise AdapterBlocked("runtime-provider-install-output-invalid")
            return {
                "prestate": dict(prestate),
                "install": dict(installed),
                "mutation_performed": True,
                "mutation_classes": ["server-runtime"],
                "cleanup_pending": [],
            }

        stages: dict[str, ProviderCallback] = {
            stage: callback for stage, callback in self.edge_stages.items()
        }
        stages["runtime"] = runtime_stage
        return ProviderBundle(
            stages=stages,
            containment=self.containment,
            transaction_id=transaction_id,
        )


def _receipt(transaction_id: str, stage: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        raise AdapterBlocked(f"provider-result-invalid:{stage}")
    if _contains_secret(metadata):
        raise AdapterBlocked(f"provider-secret-output:{stage}")
    if _contains_verdict(metadata):
        raise AdapterBlocked(f"provider-verdict-output:{stage}")
    safe = redact(dict(metadata))
    return {
        "schema_version": 1,
        "transaction_id": transaction_id,
        "stage": stage,
        "input_digest": _digest({"stage": stage, "metadata": safe}),
        "started_at": _utc_now(),
        "completed_at": _utc_now(),
        "status": "COMPLETED",
        "observations": {"provider_metadata_digest": _digest(safe)},
        "mutation": {
            "performed": bool(safe.get("mutation_performed", False)),
            "classes": list(safe.get("mutation_classes", [])),
            "cleanup_pending": list(safe.get("cleanup_pending", [])),
        },
        "rollback_state": str(safe.get("rollback_state", "ready")),
        "secret_material_present": False,
    }


def bind_provider_bundle(
    manifest: Mapping[str, Any],
    bundle: ProviderBundle,
    *,
    authorized: bool,
    expected_transaction_id: str | None = None,
) -> ProductionBackend:
    """Bind callbacks only after the caller proves all live authority gates."""

    validate_provider_manifest(manifest)
    if not authorized:
        raise AdapterBlocked("provider-authority-required")
    if not isinstance(bundle.transaction_id, str) or len(bundle.transaction_id) != 32:
        raise AdapterBlocked("provider-transaction-invalid")
    if expected_transaction_id is not None and bundle.transaction_id != expected_transaction_id:
        raise AdapterBlocked("provider-transaction-drift")
    if set(bundle.stages) != set(EDGE_SEQUENCE):
        raise AdapterBlocked("provider-stage-set-invalid")
    invalid_callbacks = [
        stage for stage in EDGE_SEQUENCE if not callable(bundle.stages.get(stage))
    ]
    if invalid_callbacks:
        raise AdapterBlocked(f"provider-callback-invalid:{','.join(invalid_callbacks)}")
    if not callable(bundle.containment):
        raise AdapterBlocked("provider-containment-invalid")

    def stage_adapter(stage: str) -> Callable[[], Mapping[str, Any]]:
        callback = bundle.stages[stage]

        def invoke() -> Mapping[str, Any]:
            result = callback()
            return _receipt(bundle.transaction_id, stage, result)

        return invoke

    def contain() -> Mapping[str, Any]:
        result = bundle.containment()
        if not isinstance(result, Mapping) or _contains_secret(result) or _contains_verdict(result):
            raise AdapterBlocked("provider-containment-result-invalid")
        return {"containment_requested": True, "containment_digest": _digest(redact(dict(result)))}

    return ProductionBackend(
        stages={stage: stage_adapter(stage) for stage in EDGE_SEQUENCE},
        containment=contain,
    )


__all__ = [
    "ProviderBundle",
    "RuntimeProvider",
    "bind_provider_bundle",
    "select_ssh_route",
    "validate_command_argv",
    "validate_provider_manifest",
]
