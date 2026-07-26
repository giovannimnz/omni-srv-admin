#!/usr/bin/env python3
"""Fail-closed Phase 53 transaction orchestrator.

The stage dispatcher is deliberately adapter-driven: the transaction contract,
ordering and evidence checks live here, while runtime/network/provider adapters
must be injected explicitly by the owning live plan.  This keeps the CLI safe
when a handler or its current preflight inputs are absent.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping

try:
    from phase53_live_adapters import (
        AdapterBlocked,
        AdapterContext,
        ValueFreeJournal,
        build_live_adapters,
        build_production_adapters,
    )
except ModuleNotFoundError:  # imported from a test loader rather than as a script
    import importlib.util

    _ADAPTERS_PATH = Path(__file__).resolve().with_name("phase53-live-adapters.py")
    _ADAPTERS_SPEC = importlib.util.spec_from_file_location("phase53_live_adapters", _ADAPTERS_PATH)
    if _ADAPTERS_SPEC is None or _ADAPTERS_SPEC.loader is None:
        raise
    _ADAPTERS_MODULE = importlib.util.module_from_spec(_ADAPTERS_SPEC)
    sys.modules[_ADAPTERS_SPEC.name] = _ADAPTERS_MODULE
    _ADAPTERS_SPEC.loader.exec_module(_ADAPTERS_MODULE)
    AdapterBlocked = _ADAPTERS_MODULE.AdapterBlocked
    AdapterContext = _ADAPTERS_MODULE.AdapterContext
    ValueFreeJournal = _ADAPTERS_MODULE.ValueFreeJournal
    build_live_adapters = _ADAPTERS_MODULE.build_live_adapters
    build_production_adapters = _ADAPTERS_MODULE.build_production_adapters


LIVE_FLAG = "ATIUS_RUN_RUSTDESK_PHASE53_LIVE"
CONTRACT_NAMES = (
    "phase53-runtime.json",
    "phase53-edge.json",
    "phase53-ops-api.json",
    "phase53-candidate-admission.json",
    "phase53-provider-manifest.json",
    "phase53-runtime-candidate.json",
)
STAGES = (
    "preflight",
    "runtime",
    "ops-api",
    "host-edge",
    "oci-edge",
    "ip-probes",
    "dns-publication",
    "hostname-probes",
    "lifecycle",
    "rollback",
    "report",
)
CLI_STAGES = STAGES + ("edge-probes",)
EDGE_PROBES_SEQUENCE = (
    "preflight",
    "runtime",
    "ops-api",
    "host-edge",
    "oci-edge",
    "ip-probes",
    "dns-publication",
    "hostname-probes",
)
PREFLIGHT_FILENAMES = ("preflight.json", "phase53-preflight.json")
RECEIPT_KEYS = {
    "schema_version",
    "transaction_id",
    "stage",
    "input_digest",
    "started_at",
    "completed_at",
    "status",
    "observations",
    "mutation",
    "rollback_state",
    "secret_material_present",
}
MUTATION_KEYS = {"performed", "classes", "cleanup_pending"}
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
DROP_KEYS = {"payload_nonce", "nonce_payload", "raw_payload"}
STORED_VERDICT_KEYS = {"pass", "passed", "verdict", "overall_status"}
MAX_CONTRACT_BYTES = 1_048_576


class GateBlocked(RuntimeError):
    """A deterministic safety gate refused to authorize work."""


StageAdapter = Callable[[], Mapping[str, Any] | "StageReceipt"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _strict_json(path: Path) -> dict[str, Any]:
    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or not 0 < info.st_size <= MAX_CONTRACT_BYTES:
            raise GateBlocked("contract-file-invalid")
        raw = path.read_bytes()

        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in items:
                if key in result:
                    raise GateBlocked("duplicate-json-key")
                result[key] = value
            return result

        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except GateBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateBlocked("contract-file-invalid") from exc
    if not isinstance(payload, dict):
        raise GateBlocked("contract-file-invalid")
    return payload


@dataclass(frozen=True)
class ContractBundle:
    payloads: dict[str, dict[str, Any]]
    digests: dict[str, str]


def load_current_contracts(repo: Path) -> ContractBundle:
    contract_dir = repo.resolve(strict=True) / "modules/rustdesk-fleet/contracts"
    payloads: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    for name in CONTRACT_NAMES:
        path = contract_dir / name
        payloads[name] = _strict_json(path)
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return ContractBundle(payloads=payloads, digests=digests)


def current_source_head(repo: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GateBlocked("source-head-unavailable") from exc
    source_head = completed.stdout.strip()
    if completed.returncode != 0 or not _is_hex(source_head, 40):
        raise GateBlocked("source-head-unavailable")
    return source_head


def _contains_stored_verdict(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            if lowered in STORED_VERDICT_KEYS or (
                lowered == "status" and isinstance(child, str) and child.upper() == "PASS"
            ):
                return True
            if _contains_stored_verdict(child):
                return True
    elif isinstance(value, list):
        return any(_contains_stored_verdict(child) for child in value)
    return False


def sanitize_for_evidence(value: Any) -> Any:
    """Return a metadata-only projection safe for receipts and logs."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            lowered = key.lower()
            if lowered in DROP_KEYS:
                continue
            if lowered in {"argv", "env", "headers", "stdout", "stderr"}:
                result[key] = {"redacted": True}
            elif lowered in SECRET_KEYS:
                result[key] = "[REDACTED]"
            else:
                result[key] = sanitize_for_evidence(child)
        return result
    if isinstance(value, list):
        return [sanitize_for_evidence(child) for child in value]
    if isinstance(value, str) and value.lower().startswith("bearer "):
        return "[REDACTED]"
    return value


def contains_secret_material(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            if lowered in DROP_KEYS:
                return True
            if lowered in SECRET_KEYS and child != "[REDACTED]":
                return True
            if contains_secret_material(child):
                return True
    elif isinstance(value, list):
        return any(contains_secret_material(child) for child in value)
    elif isinstance(value, str):
        lowered = value.lower()
        return lowered.startswith("bearer ") or "fixture-secret" in lowered
    return False


def deny_untrusted_backend_auth(_headers: Mapping[str, str]) -> dict[str, Any]:
    """Uniform response used before any credential comparison is implemented."""
    return {
        "status": 401,
        "body": {"error": "unauthorized"},
        "headers": {"Cache-Control": "no-store"},
    }


@dataclass(frozen=True)
class StageReceipt:
    schema_version: int
    transaction_id: str
    stage: str
    input_digest: str
    started_at: str
    completed_at: str
    status: str
    observations: dict[str, Any]
    mutation: dict[str, Any]
    rollback_state: str
    secret_material_present: bool

    @classmethod
    def create(
        cls,
        *,
        transaction_id: str,
        stage: str,
        input_digest: str,
        observations: dict[str, Any],
        mutation: dict[str, Any],
        rollback_state: str,
    ) -> "StageReceipt":
        timestamp = _utc_now()
        return cls.from_mapping(
            {
                "schema_version": 1,
                "transaction_id": transaction_id,
                "stage": stage,
                "input_digest": input_digest,
                "started_at": timestamp,
                "completed_at": timestamp,
                "status": "COMPLETED",
                "observations": sanitize_for_evidence(observations),
                "mutation": mutation,
                "rollback_state": rollback_state,
                "secret_material_present": False,
            }
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "StageReceipt":
        if set(payload) != RECEIPT_KEYS:
            raise GateBlocked("receipt-schema-invalid")
        observations = payload.get("observations")
        mutation = payload.get("mutation")
        if payload.get("schema_version") != 1:
            raise GateBlocked("receipt-schema-invalid")
        if not _is_hex(payload.get("transaction_id"), 32):
            raise GateBlocked("receipt-transaction-invalid")
        if payload.get("stage") not in STAGES:
            raise GateBlocked("receipt-stage-invalid")
        if not _is_hex(payload.get("input_digest"), 64):
            raise GateBlocked("receipt-input-digest-invalid")
        if payload.get("status") != "COMPLETED":
            raise GateBlocked("receipt-status-invalid")
        if not isinstance(observations, dict) or _contains_stored_verdict(observations):
            raise GateBlocked("stored-verdict-forbidden")
        if contains_secret_material(observations):
            raise GateBlocked("secret-material-forbidden")
        if not isinstance(mutation, dict) or set(mutation) != MUTATION_KEYS:
            raise GateBlocked("receipt-mutation-invalid")
        if (
            not isinstance(mutation.get("performed"), bool)
            or not isinstance(mutation.get("classes"), list)
            or not isinstance(mutation.get("cleanup_pending"), list)
            or len(mutation["classes"]) != len(set(mutation["classes"]))
            or (not mutation["performed"] and (mutation["classes"] or mutation["cleanup_pending"]))
        ):
            raise GateBlocked("receipt-mutation-invalid")
        if payload.get("rollback_state") not in {
            "ready",
            "pending",
            "contained",
            "rolled-back",
            "production-restored",
        }:
            raise GateBlocked("receipt-rollback-state-invalid")
        if payload.get("secret_material_present") is not False:
            raise GateBlocked("secret-material-forbidden")
        if not all(
            isinstance(payload.get(field), str) and payload[field].endswith("Z")
            for field in ("started_at", "completed_at")
        ):
            raise GateBlocked("receipt-timestamp-invalid")
        return cls(**dict(payload))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "transaction_id": self.transaction_id,
            "stage": self.stage,
            "input_digest": self.input_digest,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "observations": self.observations,
            "mutation": self.mutation,
            "rollback_state": self.rollback_state,
            "secret_material_present": self.secret_material_present,
        }


class Phase53LiveGate:
    def __init__(
        self,
        *,
        repo: Path,
        environ: Mapping[str, str] | None = None,
        evidence_dir: Path | None = None,
        stage_adapters: Mapping[str, StageAdapter] | None = None,
    ) -> None:
        self.repo = repo.resolve(strict=True)
        self.environ = dict(os.environ if environ is None else environ)
        self.evidence_dir = (
            (evidence_dir or self.repo / "modules/rustdesk-fleet/evidence/phase53")
            .resolve()
        )
        self.contracts = load_current_contracts(self.repo)
        self.stage_adapters = dict(stage_adapters or {})
        self.receipts: list[StageReceipt] = []
        self._completed_stages: list[str] = []
        self.transaction_id: str | None = None
        self._mutation_authorized = False
        self.journal: ValueFreeJournal | None = None

    def require_explicit_live_flag(self) -> None:
        if self.environ.get(LIVE_FLAG) != "1":
            raise GateBlocked("explicit-live-flag-required")

    def authorize_first_mutation(self, preflight: Mapping[str, Any]) -> None:
        self.require_explicit_live_flag()
        if preflight.get("contract_digests") != self.contracts.digests:
            raise GateBlocked("contract-digest-drift")
        if preflight.get("source_head") != current_source_head(self.repo):
            raise GateBlocked("source-head-drift")
        if not _is_hex(preflight.get("pre_state_digest"), 64):
            raise GateBlocked("pre-state-required")
        if preflight.get("ownership_unambiguous") is not True:
            raise GateBlocked("ownership-ambiguous")
        if preflight.get("rollback_ready") is not True:
            raise GateBlocked("rollback-readiness-required")
        if _contains_stored_verdict(preflight) or contains_secret_material(preflight):
            raise GateBlocked("preflight-evidence-invalid")
        self._mutation_authorized = True

    def hydrate_journal(self, journal: ValueFreeJournal) -> None:
        """Resume only a valid ordered prefix; never replay completed stages."""

        stages = [row["stage"] for row in journal.receipts]
        if "rollback" in stages:
            raise GateBlocked("journal-terminal-rollback")
        if stages != list(STAGES[: len(stages)]):
            raise GateBlocked("journal-stage-order-invalid")
        self.journal = journal
        self.transaction_id = journal.transaction_id
        self._completed_stages = stages

    def load_preflight(self) -> dict[str, Any]:
        """Load one current, value-free preflight descriptor from the evidence dir."""
        for filename in PREFLIGHT_FILENAMES:
            path = self.evidence_dir / filename
            if not path.exists():
                continue
            return _strict_json(path)
        raise GateBlocked("preflight-input-required")

    def accept_receipt(self, receipt: StageReceipt) -> None:
        if not self._mutation_authorized:
            raise GateBlocked("mutation-not-authorized")
        if receipt.stage in self._completed_stages or any(
            existing.stage == receipt.stage for existing in self.receipts
        ):
            raise GateBlocked("duplicate-stage-receipt")
        if self.transaction_id is None:
            self.transaction_id = receipt.transaction_id
        elif receipt.transaction_id != self.transaction_id:
            raise GateBlocked("receipt-transaction-drift")
        expected_stage = STAGES[len(self._completed_stages) + len(self.receipts)]
        if receipt.stage != expected_stage:
            raise GateBlocked("ambiguous-stage-resume")
        self.receipts.append(receipt)
        if self.journal is not None:
            self.journal.append(receipt.stage, receipt.to_mapping())

    def _run_adapter(self, stage: str) -> dict[str, Any]:
        adapter = self.stage_adapters.get(stage)
        if adapter is None:
            raise GateBlocked(f"stage-adapter-required:{stage}")
        try:
            result = adapter()
        except GateBlocked:
            raise
        except Exception as exc:
            raise GateBlocked(f"stage-adapter-failed:{stage}") from exc
        if isinstance(result, StageReceipt):
            receipt = result
        elif isinstance(result, Mapping):
            try:
                receipt = StageReceipt.from_mapping(result)
            except GateBlocked:
                raise
            except (TypeError, ValueError) as exc:
                raise GateBlocked(f"stage-receipt-invalid:{stage}") from exc
        else:
            raise GateBlocked(f"stage-receipt-invalid:{stage}")
        self.accept_receipt(receipt)
        return receipt.to_mapping()

    def _contain_on_failure(self, *, failed_stage: str, blocker: str) -> None:
        """Request containment without allowing adapter output into evidence."""

        callback = self.stage_adapters.get("contain_on_failure")
        callback_completed = False
        if callback is not None:
            try:
                callback()
            except Exception:
                callback_completed = False
            else:
                callback_completed = True
        if self.journal is not None:
            self.journal.append(
                "rollback",
                {
                    "containment_requested": True,
                    "callback_configured": callback is not None,
                    "callback_completed": callback_completed,
                    "failed_stage": failed_stage,
                    "blocker_digest": hashlib.sha256(blocker.encode("utf-8")).hexdigest(),
                },
            )

    def run_stage(self, stage: str) -> dict[str, Any]:
        self.require_explicit_live_flag()
        if not self._mutation_authorized:
            raise GateBlocked("mutation-not-authorized")
        if stage not in CLI_STAGES:
            raise GateBlocked("stage-not-allowed")
        if stage != "edge-probes" and stage in self._completed_stages:
            raise GateBlocked("journal-stage-already-complete")
        sequence = (
            tuple(item for item in EDGE_PROBES_SEQUENCE if item not in self._completed_stages)
            if stage == "edge-probes"
            else (stage,)
        )
        if not sequence:
            raise GateBlocked("journal-stage-already-complete")
        receipts: list[dict[str, Any]] = []
        for item in sequence:
            try:
                receipts.append(self._run_adapter(item))
            except GateBlocked as exc:
                self._contain_on_failure(failed_stage=item, blocker=str(exc))
                raise
        return {
            "stage": stage,
            "receipt_count": len(receipts),
            "receipts": receipts,
            "secret_material_present": False,
        }


def _blocked_payload(blocker: str) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "blocker": blocker,
        "mutation_performed": False,
        "secret_material_present": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--stage", choices=CLI_STAGES)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        gate = Phase53LiveGate(repo=args.repo, evidence_dir=args.evidence_dir)
        gate.require_explicit_live_flag()
        preflight = gate.load_preflight()
        gate.authorize_first_mutation(preflight)
        transaction_id = hashlib.sha256(
            json.dumps(preflight, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:32]
        journal_path = args.journal or gate.evidence_dir / "phase53-journal.json"
        # Provider/admission checks happen before journal creation.  A blocked
        # invocation must leave no resumable journal or provider side effect.
        gate.stage_adapters = build_production_adapters(
            AdapterContext(
                repo=gate.repo,
                evidence_dir=gate.evidence_dir,
                preflight=preflight,
                environ=gate.environ,
                transaction_id=transaction_id,
                journal=None,
            )
        )
        gate.hydrate_journal(ValueFreeJournal.open(journal_path, transaction_id))
        stage = args.stage or "preflight"
        result = gate.run_stage(stage)
        sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except (GateBlocked, AdapterBlocked, OSError, ValueError) as exc:
        blocker = (
            str(exc)
            if isinstance(exc, (GateBlocked, AdapterBlocked))
            else "gate-initialization-failed"
        )
        sys.stdout.write(json.dumps(_blocked_payload(blocker), sort_keys=True, separators=(",", ":")) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
