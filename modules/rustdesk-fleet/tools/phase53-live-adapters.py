#!/usr/bin/env python3
"""Fail-closed adapter factory and value-free journal for Phase 53.

The real host/provider adapters are deliberately not inferred from ambient
shell state.  A live invocation must provide a current, admitted candidate and
an explicit backend implementation; tests can inject deterministic adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping


LIVE_FLAG = "ATIUS_RUN_RUSTDESK_PHASE53_LIVE"
ADMISSION_FLAG = "ADMITTED_PHASE53"
CURRENT_EXECUTION_TARGET = "10.21.1.21"
FUTURE_EXECUTION_TARGET = "10.31.1.31"
CONTRACT_NAMES = (
    "phase53-runtime.json",
    "phase53-edge.json",
    "phase53-ops-api.json",
    "phase53-candidate-admission.json",
    "phase53-provider-manifest.json",
    "phase53-runtime-candidate.json",
)
EDGE_SEQUENCE = (
    "preflight",
    "runtime",
    "ops-api",
    "host-edge",
    "oci-edge",
    "ip-probes",
    "dns-publication",
    "hostname-probes",
)
CONTAINMENT_STAGE = "contain_on_failure"
ALL_STAGES = EDGE_SEQUENCE + ("lifecycle", "rollback", "report")
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


class AdapterBlocked(RuntimeError):
    """A live adapter refused to operate without explicit current authority."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in SECRET_KEYS and child != "[REDACTED]":
                return True
            if _contains_secret(child):
                return True
    elif isinstance(value, list):
        return any(_contains_secret(child) for child in value)
    elif isinstance(value, str):
        return value.lower().startswith("bearer ") or "fixture-secret" in value.lower()
    return False


def _contains_verdict(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            if lowered in VERDICT_KEYS or (
                lowered == "status" and isinstance(child, str) and child.upper() == "PASS"
            ):
                return True
            if _contains_verdict(child):
                return True
    elif isinstance(value, list):
        return any(_contains_verdict(child) for child in value)
    return False


def redact(value: Any) -> Any:
    """Project arbitrary adapter output to metadata safe for evidence."""

    if isinstance(value, dict):
        projected: dict[str, Any] = {}
        for key, child in value.items():
            lowered = key.lower()
            if lowered in {"argv", "env", "headers", "stdout", "stderr", "payload"}:
                projected[key] = {"redacted": True}
            elif lowered in SECRET_KEYS:
                projected[key] = "[REDACTED]"
            else:
                projected[key] = redact(child)
        return projected
    if isinstance(value, list):
        return [redact(child) for child in value]
    if isinstance(value, str) and value.lower().startswith("bearer "):
        return "[REDACTED]"
    return value


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@dataclass
class ValueFreeJournal:
    """Atomic, resumable journal that never stores raw adapter output."""

    path: Path
    transaction_id: str
    receipts: list[dict[str, Any]]

    @classmethod
    def open(cls, path: Path, transaction_id: str) -> "ValueFreeJournal":
        if not path.exists():
            return cls(path=path, transaction_id=transaction_id, receipts=[])
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AdapterBlocked("journal-invalid") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or payload.get("transaction_id") != transaction_id
            or payload.get("secret_material_present") is not False
            or _contains_secret(payload)
            or _contains_verdict(payload)
            or not isinstance(payload.get("receipts"), list)
        ):
            raise AdapterBlocked("journal-invalid")
        receipts = list(payload["receipts"])
        previous: str | None = None
        seen: set[str] = set()
        for row in receipts:
            if not isinstance(row, dict):
                raise AdapterBlocked("journal-invalid")
            stage = row.get("stage")
            digest = row.get("receipt_digest")
            observed_at = row.get("observed_at")
            if (
                stage not in ALL_STAGES
                or stage in seen
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
                or not isinstance(observed_at, str)
                or not observed_at.endswith("Z")
            ):
                raise AdapterBlocked("journal-invalid")
            previous = stage
            seen.add(stage)
        if receipts and payload.get("last_stage") != receipts[-1]["stage"]:
            raise AdapterBlocked("journal-invalid")
        return cls(path=path, transaction_id=transaction_id, receipts=receipts)

    def append(self, stage: str, receipt: Mapping[str, Any]) -> None:
        if stage not in ALL_STAGES or _contains_secret(receipt) or _contains_verdict(receipt):
            raise AdapterBlocked("journal-receipt-invalid")
        safe = redact(dict(receipt))
        if _contains_secret(safe) or _contains_verdict(safe):
            raise AdapterBlocked("journal-receipt-invalid")
        self.receipts.append({"stage": stage, "receipt_digest": _digest(safe), "observed_at": _utc_now()})
        _atomic_json(
            self.path,
            {
                "schema_version": 1,
                "transaction_id": self.transaction_id,
                "receipts": self.receipts,
                "last_stage": stage,
                "secret_material_present": False,
            },
        )


@dataclass(frozen=True)
class AdapterContext:
    repo: Path
    evidence_dir: Path
    preflight: Mapping[str, Any]
    environ: Mapping[str, str]
    transaction_id: str
    journal: ValueFreeJournal | None


StageAdapter = Callable[[], Mapping[str, Any]]


def build_live_adapters(
    context: AdapterContext,
    *,
    injected: Mapping[str, StageAdapter] | None = None,
) -> dict[str, StageAdapter]:
    """Build adapters only when admission and a provider backend are explicit.

    ``injected`` is the hermetic-test seam.  Production adapters are intentionally
    not guessed from PATH, SSH config or ambient credentials; a missing provider
    is a deterministic blocker before any mutation.
    """

    if context.environ.get(LIVE_FLAG) != "1":
        raise AdapterBlocked("explicit-live-flag-required")
    if context.preflight.get("candidate_admission_performed") is not True:
        raise AdapterBlocked("candidate-not-admitted")
    if context.preflight.get("rollback_ready") is not True:
        raise AdapterBlocked("rollback-readiness-required")
    if injected is None:
        raise AdapterBlocked("live-backend-not-configured")
    missing = [stage for stage in EDGE_SEQUENCE if stage not in injected]
    if missing:
        raise AdapterBlocked(f"live-backend-stages-missing:{','.join(missing)}")
    if CONTAINMENT_STAGE not in injected:
        raise AdapterBlocked("live-backend-containment-missing")
    return dict(injected)


def _strict_json(path: Path) -> dict[str, Any]:
    """Read a small contract with duplicate-key and symlink protection."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in items:
            if key in payload:
                raise AdapterBlocked("duplicate-contract-key")
            payload[key] = value
        return payload

    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_size <= 0 or info.st_size > 1_048_576:
            raise AdapterBlocked("contract-file-invalid")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except AdapterBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterBlocked("contract-file-invalid") from exc
    if not isinstance(payload, dict):
        raise AdapterBlocked("contract-object-required")
    return payload


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_provider_contracts(repo: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    contract_dir = repo.resolve(strict=True) / "modules/rustdesk-fleet/contracts"
    payloads: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    for name in CONTRACT_NAMES:
        path = contract_dir / name
        payloads[name] = _strict_json(path)
        digests[name] = _file_digest(path)
    return payloads, digests


def _admission_evidence(repo: Path) -> dict[str, Any]:
    return _strict_json(
        repo.resolve(strict=True)
        / "modules/rustdesk-fleet/evidence/phase53/candidate-admission.json"
    )


def _validate_production_authority(context: "AdapterContext") -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if context.environ.get(LIVE_FLAG) != "1":
        raise AdapterBlocked("explicit-live-flag-required")
    if context.environ.get(ADMISSION_FLAG) != "1":
        raise AdapterBlocked("admission-flag-required")
    if context.preflight.get("candidate_admission_performed") is not True:
        raise AdapterBlocked("candidate-not-admitted")
    if context.preflight.get("rollback_ready") is not True:
        raise AdapterBlocked("rollback-readiness-required")
    payloads, digests = load_provider_contracts(context.repo)
    admission = _admission_evidence(context.repo)
    if admission.get("candidate_status") != "ADMITTED_PHASE53":
        raise AdapterBlocked("candidate-evidence-not-admitted")
    if admission.get("admission_performed") is not True or admission.get("live_mutation_performed") is not False:
        raise AdapterBlocked("candidate-admission-state-invalid")
    expected = context.preflight.get("contract_digests")
    if expected != digests:
        raise AdapterBlocked("provider-contract-digest-drift")
    if context.preflight.get("candidate_contract_digest") != digests["phase53-runtime-candidate.json"]:
        raise AdapterBlocked("candidate-contract-digest-drift")
    if context.preflight.get("provider_manifest_digest") != digests["phase53-provider-manifest.json"]:
        raise AdapterBlocked("provider-manifest-digest-drift")
    if payloads["phase53-candidate-admission.json"].get("candidate_status") != "ADMITTED_PHASE53":
        raise AdapterBlocked("candidate-contract-state-invalid")
    manifest = payloads["phase53-provider-manifest.json"]
    execution_target = manifest.get("execution_target")
    if execution_target == FUTURE_EXECUTION_TARGET:
        raise AdapterBlocked("provider-manifest-target-invalid")
    if execution_target != CURRENT_EXECUTION_TARGET:
        raise AdapterBlocked("provider-manifest-target-invalid")
    routes = manifest.get("routes")
    command_classes = manifest.get("command_classes")
    limits = manifest.get("limits")
    if (
        not isinstance(routes, dict)
        or set(routes) != {"ssh", "vault", "oci", "cloudflare", "apache"}
        or not isinstance(command_classes, dict)
        or not isinstance(command_classes.get("allowlisted"), list)
        or not isinstance(command_classes.get("forbidden"), list)
        or not isinstance(limits, dict)
        or limits.get("journal_mode") != "value-free-0600"
        or manifest.get("secret_material_present") is not False
    ):
        raise AdapterBlocked("provider-manifest-shape-invalid")
    return payloads, digests


@dataclass(frozen=True)
class ProductionBackend:
    """Named provider callback set; no shell/path/credential inference."""

    stages: Mapping[str, StageAdapter]
    containment: StageAdapter


def build_production_adapters(
    context: "AdapterContext",
    *,
    backend: ProductionBackend | None = None,
    provider_bundle: Any | None = None,
    provider_bundle_factory: Callable[[], Any] | None = None,
) -> dict[str, StageAdapter]:
    """Bind concrete provider stages only after current authority is proven.

    The CLI intentionally has no ambient backend.  A deployment embedding this
    runner must construct ``ProductionBackend`` from the reviewed SSH/Vault/OCI/
    DNS/Apache wrappers and pass it explicitly; otherwise the invocation blocks
    before opening a journal or calling a provider.
    """

    if provider_bundle is not None and provider_bundle_factory is not None:
        raise AdapterBlocked("provider-bundle-input-ambiguous")
    payloads, _ = _validate_production_authority(context)
    if provider_bundle_factory is not None:
        if not callable(provider_bundle_factory):
            raise AdapterBlocked("provider-bundle-factory-invalid")
        provider_bundle = provider_bundle_factory()
    if backend is None and provider_bundle is not None:
        # The reviewed bundle seam is opt-in and requires the caller to pass
        # concrete callbacks.  The CLI does not construct one from ambient
        # PATH, SSH config, Vault, or environment state.
        try:
            from phase53_production_adapters import bind_provider_bundle
        except ModuleNotFoundError:
            import importlib.util

            module_path = Path(__file__).with_name("phase53_production_adapters.py")
            spec = importlib.util.spec_from_file_location(
                "phase53_production_adapters", module_path
            )
            if spec is None or spec.loader is None:
                raise AdapterBlocked("provider-seam-unavailable")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            bind_provider_bundle = module.bind_provider_bundle
        backend = bind_provider_bundle(
            payloads["phase53-provider-manifest.json"],
            provider_bundle,
            authorized=True,
            expected_transaction_id=context.transaction_id,
        )
    if backend is None:
        raise AdapterBlocked("provider-backend-not-configured")
    missing = [stage for stage in EDGE_SEQUENCE if stage not in backend.stages]
    if missing:
        raise AdapterBlocked(f"production-stages-missing:{','.join(missing)}")
    return {**dict(backend.stages), CONTAINMENT_STAGE: backend.containment}



__all__ = [
    "AdapterBlocked",
    "AdapterContext",
    "CONTAINMENT_STAGE",
    "EDGE_SEQUENCE",
    "ValueFreeJournal",
    "build_live_adapters",
    "build_production_adapters",
    "ProductionBackend",
    "load_provider_contracts",
    "redact",
]
