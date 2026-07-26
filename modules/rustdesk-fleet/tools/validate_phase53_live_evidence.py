#!/usr/bin/env python3
"""Validate current Phase 53 evidence without authorizing infrastructure writes.

The validator accepts either the safe ``NOT_ADMITTED``/``BLOCKED`` terminal
state or a fully current ``ADMITTED_PHASE53`` pre-mutation state. It rejects
malformed, stale, secret-bearing or stored-verdict evidence and never turns
metadata into a live approval.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


EVIDENCE_NAMES = (
    "candidate-admission.json",
    "compatibility-pending.json",
    "contract-parity.json",
    "server-1.1.16-evaluation.json",
    "capacity-current.json",
    "deploy-transaction.json",
    "edge-probes.json",
    "ops-api-probes.json",
)
CONTRACT_NAMES = (
    "phase53-runtime.json",
    "phase53-edge.json",
    "phase53-ops-api.json",
    "phase53-candidate-admission.json",
    "phase53-provider-manifest.json",
    "phase53-runtime-candidate.json",
)
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
REQUIRED_ADMISSION_GATES = {
    "fresh_supply",
    "compatibility_matrix",
    "contract_parity",
    "pre_state",
    "rollback_ready",
    "capacity_finalize",
}


def _future_utc(value: Any) -> bool:
    """Return true only for a timezone-aware UTC expiry in the future."""

    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        expiry = datetime.fromisoformat(value[:-1] + "+00:00")
    except (TypeError, ValueError, OverflowError):
        return False
    return expiry.tzinfo is not None and expiry > datetime.now(timezone.utc)


class EvidenceInvalid(RuntimeError):
    pass


def _strict(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in items:
            if key in payload:
                raise EvidenceInvalid(f"duplicate-json-key:{path.name}:{key}")
            payload[key] = value
        return payload

    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceInvalid(f"json-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise EvidenceInvalid(f"json-object-required:{path.name}")
    return payload


def _scan(value: Any, *, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            if lowered in SECRET_KEYS and child not in (False, None, "[REDACTED]"):
                raise EvidenceInvalid(f"secret-surface:{path}.{key}")
            if lowered == "secret_material_present" and child is not False:
                raise EvidenceInvalid(f"secret-surface:{path}.{key}")
            if lowered in VERDICT_KEYS:
                raise EvidenceInvalid(f"stored-verdict:{path}.{key}")
            if lowered == "status" and isinstance(child, str) and child.upper() == "PASS":
                raise EvidenceInvalid(f"stored-verdict:{path}.{key}")
            _scan(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan(child, path=f"{path}[{index}]")
    elif isinstance(value, str) and value.lower().startswith("bearer "):
        raise EvidenceInvalid(f"secret-surface:{path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _head(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        raise EvidenceInvalid("source-head-unavailable")
    return completed.stdout.strip()


def _sha256_value(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise EvidenceInvalid(f"{field}-digest-invalid")
    try:
        int(value, 16)
    except ValueError as exc:
        raise EvidenceInvalid(f"{field}-digest-invalid") from exc
    return value.lower()


def _sha256_reference(value: Any, *, field: str) -> str:
    """Validate a content-addressed ``sha256:`` reference exactly."""

    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise EvidenceInvalid(f"{field}-digest-invalid")
    _sha256_value(value[7:], field=field)
    return value


def _iso_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EvidenceInvalid(f"{field}-timestamp-invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except (TypeError, ValueError, OverflowError) as exc:
        raise EvidenceInvalid(f"{field}-timestamp-invalid") from exc
    if parsed.tzinfo is None:
        raise EvidenceInvalid(f"{field}-timestamp-invalid")
    return parsed.astimezone(timezone.utc)


def _consumer_path(repo: Path, name: str) -> Path:
    root = repo / "modules/rustdesk-fleet"
    candidates = (root / name, root / "quadlets" / name, root / "tools" / name)
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    raise EvidenceInvalid(f"consumer-missing:{name}")


def _validate_admitted_semantics(
    repo: Path,
    evidence: dict[str, dict[str, Any]],
    contract_payloads: dict[str, dict[str, Any]],
    contract_digests: dict[str, str],
) -> None:
    admission = evidence["candidate-admission.json"]
    evaluation = evidence["server-1.1.16-evaluation.json"]
    candidate = admission.get("candidate_contract")
    runtime_candidate = contract_payloads["phase53-runtime-candidate.json"]
    if not isinstance(candidate, dict):
        raise EvidenceInvalid("candidate-contract-missing")
    upstream = runtime_candidate.get("upstream")
    if not isinstance(upstream, dict) or runtime_candidate.get("candidate_status_required") != "ADMITTED_PHASE53":
        raise EvidenceInvalid("candidate-runtime-contract-invalid")
    candidate_digest = _sha256_reference(
        candidate.get("image_linux_arm64_digest"), field="candidate-image"
    )
    runtime_digest = _sha256_reference(
        upstream.get("linux_arm64_digest"), field="runtime-image"
    )
    immutable_reference = upstream.get("immutable_reference")
    if not isinstance(immutable_reference, str) or "@" not in immutable_reference:
        raise EvidenceInvalid("candidate-immutable-reference-invalid")
    immutable_digest = _sha256_reference(
        immutable_reference.rsplit("@", 1)[1], field="candidate-immutable-reference"
    )
    if (
        candidate.get("version") != upstream.get("version")
        or candidate_digest != runtime_digest
        or immutable_digest != candidate_digest
    ):
        raise EvidenceInvalid("candidate-runtime-hash-drift")
    server = evaluation.get("server")
    release_zip = server.get("release_zip") if isinstance(server, dict) else None
    image = server.get("image") if isinstance(server, dict) else None
    evaluation_digest = (
        _sha256_reference(image.get("linux_arm64_digest"), field="evaluation-image")
        if isinstance(image, Mapping)
        else None
    )
    if (
        not isinstance(server, dict)
        or server.get("version") != candidate.get("version")
        or server.get("commit") != candidate.get("server_commit")
        or not isinstance(release_zip, dict)
        or release_zip.get("sha256") != candidate.get("release_zip_sha256")
        or not isinstance(image, dict)
        or evaluation_digest != candidate_digest
    ):
        raise EvidenceInvalid("candidate-evaluation-hash-drift")

    admission_contract = contract_payloads["phase53-candidate-admission.json"]
    client_contract = admission_contract.get("client_compatibility")
    compatibility = evidence["compatibility-pending.json"]
    matrix = compatibility.get("matrix")
    if not isinstance(client_contract, dict) or not isinstance(matrix, dict):
        raise EvidenceInvalid("compatibility-contract-invalid")
    if compatibility.get("state") != "CURRENT" or compatibility.get("install_performed") is not False:
        raise EvidenceInvalid("compatibility-not-current")
    if compatibility.get("candidate_version") != candidate.get("version"):
        raise EvidenceInvalid("compatibility-candidate-drift")
    if compatibility.get("client_version") != client_contract.get("version"):
        raise EvidenceInvalid("compatibility-client-drift")
    expected_matrix = {
        "linux_arm64": client_contract.get("linux_arm64_sha256"),
        "windows_x86_64": client_contract.get("windows_x86_64_msi_sha256"),
    }
    if set(matrix) != set(expected_matrix):
        raise EvidenceInvalid("compatibility-matrix-shape-invalid")
    for key, expected_digest in expected_matrix.items():
        item = matrix.get(key)
        if not isinstance(item, dict) or item.get("artifact_sha256") != expected_digest or item.get("tested") is not True:
            raise EvidenceInvalid(f"compatibility-vector-not-current:{key}")
    required_vectors = client_contract.get("required_matrix")
    if compatibility.get("required_vectors") != required_vectors or compatibility.get("vectors_tested") != required_vectors:
        raise EvidenceInvalid("compatibility-required-vectors-drift")

    parity = evidence["contract-parity.json"]
    if parity.get("state") != "CURRENT" or parity.get("current_contract_digests") != contract_digests:
        raise EvidenceInvalid("contract-parity-drift")
    runtime_consumers = runtime_candidate.get("consumer_contracts")
    expected_successors = set()
    if isinstance(runtime_consumers, dict):
        for value in runtime_consumers.values():
            expected_successors.update(value if isinstance(value, list) else [value])
    expected_successors.add("phase53-runtime-candidate.json")
    if set(parity.get("successor_consumers", [])) != expected_successors:
        raise EvidenceInvalid("contract-parity-consumer-set-drift")
    consumer_digests = parity.get("consumer_digests")
    expected_consumer_names = expected_successors - {"phase53-runtime-candidate.json"}
    if not isinstance(consumer_digests, dict) or set(consumer_digests) != expected_consumer_names:
        raise EvidenceInvalid("contract-parity-consumer-digests-invalid")
    for name in expected_consumer_names:
        observed = _sha256(_consumer_path(repo, name))
        if consumer_digests.get(name) != observed:
            raise EvidenceInvalid(f"contract-parity-consumer-digest-drift:{name}")

    capacity = evidence["capacity-current.json"]
    if (
        capacity.get("state") != "CURRENT"
        or capacity.get("read_only") is not True
        or capacity.get("mutation_performed") is not False
        or capacity.get("placement_order") != ["atius-srv-2", "atius-srv-3", "horistic-srv"]
        or capacity.get("selected_primary") != "horistic-srv"
        or capacity.get("predecessor_receipts_persisted") != ["atius-srv-2:NO-GO", "atius-srv-3:NO-GO"]
    ):
        raise EvidenceInvalid("capacity-finalize-not-current")
    ttl = capacity.get("finalize_ttl_seconds")
    if not isinstance(ttl, int) or not 0 < ttl <= 3600:
        raise EvidenceInvalid("capacity-ttl-invalid")
    samples = capacity.get("samples")
    if not isinstance(samples, list) or len(samples) != 6:
        raise EvidenceInvalid("capacity-two-samples-required")
    expected_sample_order = [
        "atius-srv-2",
        "atius-srv-2",
        "atius-srv-3",
        "atius-srv-3",
        "horistic-srv",
        "horistic-srv",
    ]
    actual_sample_order = [
        sample.get("host") if isinstance(sample, Mapping) else None
        for sample in samples
    ]
    if actual_sample_order != expected_sample_order:
        raise EvidenceInvalid("capacity-sample-order-invalid")
    now = datetime.now(timezone.utc)
    by_host: dict[str, list[dict[str, Any]]] = {host: [] for host in capacity["placement_order"]}
    for sample in samples:
        if not isinstance(sample, dict) or sample.get("host") not in by_host:
            raise EvidenceInvalid("capacity-sample-host-invalid")
        if sample.get("zero_cleanup_performed") is not False:
            raise EvidenceInvalid("capacity-cleanup-invariant-drift")
        observed_at = _iso_utc(sample.get("observed_at"), field="capacity-sample")
        if observed_at > now or (now - observed_at).total_seconds() > ttl:
            raise EvidenceInvalid("capacity-sample-stale")
        by_host[sample["host"]].append(sample)
    if any(len(items) != 2 for items in by_host.values()):
        raise EvidenceInvalid("capacity-two-samples-required")
    for host in ("atius-srv-2", "atius-srv-3"):
        if any(item.get("placement_state") != "NO-GO" for item in by_host[host]):
            raise EvidenceInvalid("capacity-predecessor-state-drift")
    for item in by_host["horistic-srv"]:
        if item.get("raw_capacity_state") != "CURRENT" or item.get("capacity_finalize_state") != "CURRENT":
            raise EvidenceInvalid("capacity-primary-state-drift")

    deploy = evidence["deploy-transaction.json"]
    if (
        deploy.get("state") != "READY_BEFORE_MUTATION"
        or deploy.get("transaction_id") is not None
        or deploy.get("mutation_performed") is not False
        or deploy.get("journal_created") is not False
        or deploy.get("rollback_state") != "ready"
        or deploy.get("rollback_ready") is not True
    ):
        raise EvidenceInvalid("deploy-prestate-rollback-invalid")
    _sha256_value(deploy.get("pre_state_digest"), field="deploy-pre-state")

    edge_contract = contract_payloads["phase53-edge.json"]
    edge = evidence["edge-probes.json"]
    external = edge_contract.get("external_probes") if isinstance(edge_contract, Mapping) else None
    external_tcp = external.get("tcp") if isinstance(external, Mapping) else None
    external_udp = external.get("udp") if isinstance(external, Mapping) else None
    public_edge = edge_contract.get("public_edge")
    backend = edge_contract.get("backend")
    if (
        not isinstance(external, Mapping)
        or not isinstance(external_tcp, Mapping)
        or not isinstance(external_udp, Mapping)
        or not isinstance(public_edge, Mapping)
        or not isinstance(backend, Mapping)
    ):
        raise EvidenceInvalid("edge-contract-shape-invalid")
    if (
        edge.get("state") != "CURRENT"
        or edge.get("mutation_performed") is not False
        or edge.get("probes_completed") is not True
        or edge.get("udp_reflection_negative") is not True
        or edge.get("origins_required") != external.get("origins")
        or edge.get("positive_tcp_ports") != external_tcp.get("positive")
        or edge.get("negative_tcp_ports") != external_tcp.get("negative")
        or edge.get("targets") != external_tcp.get("targets")
        or edge.get("udp_targets") != external_udp.get("targets")
        or edge.get("udp_external_port") != external_udp.get("external_port")
        or edge.get("udp_backend_port") != external_udp.get("backend_port")
        or edge.get("dns_records") != [
            item["name"] for item in edge_contract.get("dns_records", [])
        ]
        or edge.get("public_edge_host") != public_edge.get("host")
        or edge.get("backend_host") != backend.get("host")
        or edge.get("backend_ingress_source_ipv4")
        != backend.get("native_ingress_source_ipv4")
        or edge.get("native_public_positive") is not False
    ):
        raise EvidenceInvalid("edge-probes-not-current")

    ops_contract = contract_payloads["phase53-ops-api.json"]
    ops = evidence["ops-api-probes.json"]
    if (
        ops.get("state") != "CURRENT"
        or ops.get("hostname") != ops_contract.get("hostname")
        or ops.get("authenticated_probe_required") is not True
        or ops.get("probes_completed") is not True
        or ops.get("redacted") is not True
        or ops.get("vhost_mutation_performed") is not False
        or ops.get("mutation_performed") is not False
        or ops.get("final_receipt_present") is not True
    ):
        raise EvidenceInvalid("ops-probes-not-current")

    provider = contract_payloads["phase53-provider-manifest.json"]
    routes = provider.get("routes")
    commands = provider.get("command_classes")
    limits = provider.get("limits")
    if (
        not isinstance(provider.get("manifest_id"), str)
        or not isinstance(routes, Mapping)
        or set(routes) != {"ssh", "vault", "oci", "cloudflare", "apache"}
        or not isinstance(commands, Mapping)
        or not isinstance(limits, Mapping)
        or provider.get("secret_material_present") is not False
    ):
        raise EvidenceInvalid("provider-manifest-shape-invalid")
    ssh = routes.get("ssh")
    vault = routes.get("vault")
    oci = routes.get("oci")
    allowlisted = commands.get("allowlisted")
    forbidden = commands.get("forbidden")
    required_allowlisted = {
        "ssh-batch-safe", "vault-profile-dispatch", "oci-cas-read-write", "cloudflare-dns-cas",
        "apache-configtest-reload", "rustdesk-server-transaction", "rustdesk-edge-transaction", "two-origin-probes",
    }
    if (
        not isinstance(ssh, Mapping)
        or ssh.get("batch_mode") is not True
        or ssh.get("stdin_safe") is not True
        or ssh.get("known_hosts_required") is not True
        or not isinstance(vault, Mapping)
        or vault.get("provider") != "hashicorp-vault"
        or vault.get("value_free_output") is not True
        or not isinstance(oci, Mapping)
        or oci.get("execution_targets")
        != {
            "public_edge": {
                "host": "atius-srv-1",
                "private_ipv4": "10.0.0.238",
                "capabilities": [
                    "nft-dnat",
                    "nft-forward",
                    "nft-snat",
                    "oci-edge-ingress",
                ],
            },
            "backend": {
                "host": "horistic-srv",
                "private_ipv4": "10.21.1.21",
                "capabilities": [
                    "rustdesk-server",
                    "native-ingress-source-restriction",
                ],
            },
        }
        or not isinstance(allowlisted, list)
        or not isinstance(forbidden, list)
        or not required_allowlisted.issubset(set(allowlisted))
        or not {"shell-eval", "ambient-path-search", "ambient-ssh-config", "raw-secret-output"}.issubset(set(forbidden))
        or limits.get("journal_mode") != "value-free-0600"
        or limits.get("command_timeout_seconds") != 30
        or limits.get("max_stdout_bytes") != 131072
        or limits.get("max_stderr_bytes") != 8192
    ):
        raise EvidenceInvalid("provider-manifest-semantics-invalid")


def validate(repo: Path) -> dict[str, Any]:
    repo = repo.resolve(strict=True)
    evidence_dir = repo / "modules/rustdesk-fleet/evidence/phase53"
    contract_dir = repo / "modules/rustdesk-fleet/contracts"
    evidence: dict[str, dict[str, Any]] = {}
    for name in EVIDENCE_NAMES:
        path = evidence_dir / name
        if not path.is_file() or path.is_symlink():
            raise EvidenceInvalid(f"evidence-missing:{name}")
        evidence[name] = _strict(path)
        _scan(evidence[name], path=name)
    contracts: dict[str, str] = {}
    contract_payloads: dict[str, dict[str, Any]] = {}
    for name in CONTRACT_NAMES:
        path = contract_dir / name
        if not path.is_file() or path.is_symlink():
            raise EvidenceInvalid(f"contract-missing:{name}")
        payload = _strict(path)
        _scan(payload, path=name)
        contract_payloads[name] = payload
        contracts[name] = _sha256(path)

    admission = evidence["candidate-admission.json"]
    evaluation = evidence["server-1.1.16-evaluation.json"]
    candidate_status = admission.get("candidate_status")
    evaluation_status = evaluation.get("candidate_status")
    if candidate_status not in {"NOT_ADMITTED", "ADMITTED_PHASE53"}:
        raise EvidenceInvalid("candidate-status-invalid")
    if evaluation_status != candidate_status:
        raise EvidenceInvalid("evaluation-status-drift")
    admitted = candidate_status == "ADMITTED_PHASE53"
    if admission.get("admission_performed") is not admitted:
        raise EvidenceInvalid("admission-flag-drift")
    if admitted:
        if admission.get("state") != "ADMITTED_PHASE53":
            raise EvidenceInvalid("admission-state-invalid")
        provenance = admission.get("provenance")
        approval = admission.get("owner_approval")
        gates = admission.get("required_gates")
        if (
            not isinstance(provenance, dict)
            or not isinstance(approval, dict)
            or not isinstance(gates, dict)
            or set(gates) != REQUIRED_ADMISSION_GATES
            or not (
                provenance.get("signature_verified") is True
                or provenance.get("disposition") == "OWNER_EXCEPTION_APPROVED"
            )
            or approval.get("owner") != "Giovanni Muniz"
            or not isinstance(approval.get("approval_ref"), str)
            or not approval.get("approval_ref")
            or not _future_utc(approval.get("expires_at"))
            or not isinstance(approval.get("risk_disposition"), str)
            or not approval.get("risk_disposition")
            or approval.get("hash_binding") is not True
            or any(value not in {"PASS", "CURRENT", True} for value in gates.values())
        ):
            raise EvidenceInvalid("admission-authority-incomplete")
    if admission.get("live_mutation_performed") is not False:
        raise EvidenceInvalid("live-mutation-flag-drift")
    if evaluation.get("admission_performed") is not admitted:
        raise EvidenceInvalid("evaluation-admission-drift")
    if evaluation.get("live_mutation_performed") is not False:
        raise EvidenceInvalid("evaluation-live-mutation-drift")
    if evidence["compatibility-pending.json"].get("install_performed") is not False:
        raise EvidenceInvalid("client-install-invariant-drift")
    allowed_parity = {"CURRENT"} if admitted else {"PENDING", "BLOCKED"}
    if evidence["contract-parity.json"].get("state") not in allowed_parity:
        raise EvidenceInvalid("parity-state-invalid")

    source_head = _head(repo)
    recorded_heads = {
        admission.get("source_head"),
        evaluation.get("source_head"),
        evidence["contract-parity.json"].get("source_head"),
    }
    if any(item != source_head for item in recorded_heads):
        raise EvidenceInvalid("source-head-drift")
    if admitted:
        _validate_admitted_semantics(repo, evidence, contract_payloads, contracts)

    return {
        "schema_version": 1,
        "phase": 53,
        "state": "ADMITTED_PHASE53" if admitted else "BLOCKED",
        "candidate_status": candidate_status,
        "source_head": source_head,
        "contract_digests": contracts,
        "evidence_files": sorted(evidence),
        "mutation_performed": False,
        "secret_material_present": False,
        **(
            {
                "admission_authority": {
                    "owner": admission["owner_approval"]["owner"],
                    "approval_ref": admission["owner_approval"]["approval_ref"],
                    "expires_at": admission["owner_approval"]["expires_at"],
                    "risk_disposition": admission["owner_approval"]["risk_disposition"],
                    "hash_binding": True,
                }
            }
            if admitted
            else {}
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = validate(args.repo)
    except (EvidenceInvalid, OSError, subprocess.SubprocessError, ValueError) as exc:
        result = {
            "schema_version": 1,
            "state": "INVALID",
            "blocker": str(exc),
            "mutation_performed": False,
            "secret_material_present": False,
        }
        sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        return 2
    sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
