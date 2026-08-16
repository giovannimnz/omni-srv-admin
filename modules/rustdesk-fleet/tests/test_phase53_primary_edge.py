from __future__ import annotations

import copy
import configparser
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from types import MappingProxyType
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[3]
CONTRACT_DIR = REPO / "modules/rustdesk-fleet/contracts"
RUNTIME_CONTRACT = CONTRACT_DIR / "phase53-runtime.json"
EDGE_CONTRACT = CONTRACT_DIR / "phase53-edge.json"
OPS_API_CONTRACT = CONTRACT_DIR / "phase53-ops-api.json"
ADMISSION_CONTRACT = CONTRACT_DIR / "phase53-candidate-admission.json"
PROVIDER_CONTRACT = CONTRACT_DIR / "phase53-provider-manifest.json"
CANDIDATE_RUNTIME_CONTRACT = CONTRACT_DIR / "phase53-runtime-candidate.json"
LIVE_GATE_PATH = REPO / "modules/rustdesk-fleet/tools/run-phase53-live-gate.py"
HBBS_QUADLET = REPO / "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container"
HBBR_QUADLET = REPO / "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbr.container"
PHASE53_SLICE = REPO / "modules/rustdesk-fleet/systemd/atius-rustdesk-phase53.slice"
SERVER_INSTALLER = REPO / "modules/rustdesk-fleet/tools/install-phase53-server.py"
SERVER_LOGROTATE_SERVICE = (
    REPO / "modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.service"
)
SERVER_LOGROTATE_TIMER = (
    REPO / "modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.timer"
)
OPS_API_PATH = REPO / "modules/rustdesk-fleet/tools/rustdesk-ops-api.py"
OPS_API_SERVICE = REPO / "modules/rustdesk-fleet/systemd/atius-rustdesk-ops-api.service"
OPS_API_VHOST = REPO / "modules/rustdesk-fleet/apache/rustdesk-ops.atius.com.br.conf"
EDGE_APPLIER = REPO / "modules/rustdesk-fleet/tools/apply-phase53-edge.py"
EDGE_PROBE = REPO / "modules/rustdesk-fleet/tools/probe-phase53-edge.py"
EDGE_PROBE_PS1 = REPO / "modules/rustdesk-fleet/tools/probe-phase53-edge.ps1"
EDGE_NFT_POLICY = REPO / "modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft"
EDGE_BOOT_SERVICE = REPO / "modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service"
LIVE_BACKEND = REPO / "modules/rustdesk-fleet/tools/phase53-live-backend.py"
MIGRATION_HANDOFF = (
    REPO / "modules/rustdesk-fleet/contracts/phase53-horistic-migration-handoff.json"
)
BINDING_CHECKER = (
    REPO / "modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py"
)
AUTHORITY_BUILDER = (
    REPO / "modules/rustdesk-fleet/tools/build-phase53-authority-plan.py"
)
EXECUTION_SOURCE_SCOPE = (
    CONTRACT_DIR / "phase53-execution-source-scope.json"
)
EXPECTED_EXECUTION_SOURCE_PATHS = (
    "modules/rustdesk-fleet/apache/rustdesk-ops.atius.com.br.conf",
    "modules/rustdesk-fleet/contracts/phase53-candidate-admission.json",
    "modules/rustdesk-fleet/contracts/phase53-edge.json",
    "modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json",
    "modules/rustdesk-fleet/contracts/phase53-horistic-migration-handoff.json",
    "modules/rustdesk-fleet/contracts/phase53-ops-api.json",
    "modules/rustdesk-fleet/contracts/phase53-provider-manifest.json",
    "modules/rustdesk-fleet/contracts/phase53-runtime-candidate.json",
    "modules/rustdesk-fleet/contracts/phase53-runtime.json",
    "modules/rustdesk-fleet/contracts/phase53-topology.json",
    "modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft",
    "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbr.container",
    "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-ops-api.service",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-phase53.slice",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.service",
    "modules/rustdesk-fleet/systemd/atius-rustdesk-server-logrotate.timer",
    "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py",
    "modules/rustdesk-fleet/tests/test_phase53_topology.py",
    "modules/rustdesk-fleet/tools/apply-phase53-edge.py",
    "modules/rustdesk-fleet/tools/build-phase53-authority-plan.py",
    "modules/rustdesk-fleet/tools/discover-phase53-topology.py",
    "modules/rustdesk-fleet/tools/install-phase53-server.py",
    "modules/rustdesk-fleet/tools/phase53-live-adapters.py",
    "modules/rustdesk-fleet/tools/phase53-live-backend.py",
    "modules/rustdesk-fleet/tools/phase53-production-adapters.py",
    "modules/rustdesk-fleet/tools/phase53_production_adapters.py",
    "modules/rustdesk-fleet/tools/probe-phase53-edge.ps1",
    "modules/rustdesk-fleet/tools/probe-phase53-edge.py",
    "modules/rustdesk-fleet/tools/run-phase53-live-gate.py",
    "modules/rustdesk-fleet/tools/rustdesk-ops-api.py",
    "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py",
    "modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py",
)
EXPECTED_EXECUTION_SOURCE_COMMIT_PATHS = (
    "modules/rustdesk-fleet/contracts/phase53-execution-source-scope.json",
    "modules/rustdesk-fleet/tests/test_phase53_primary_edge.py",
    "modules/rustdesk-fleet/tools/build-phase53-authority-plan.py",
    "modules/rustdesk-fleet/tools/phase53-live-backend.py",
    "modules/rustdesk-fleet/tools/run-phase53-live-gate.py",
    "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py",
    "modules/rustdesk-fleet/tools/verify-phase53-binding-chain.py",
)


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains a repeated member name."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_strict(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
    )
    assert isinstance(payload, dict)
    return payload


def _load_unit(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    with path.open(encoding="utf-8") as handle:
        parser.read_file(handle)
    return parser


def _server_installer_module() -> Any:
    assert SERVER_INSTALLER.is_file(), SERVER_INSTALLER
    spec = importlib.util.spec_from_file_location("phase53_server_installer", SERVER_INSTALLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _ops_api_module() -> Any:
    assert OPS_API_PATH.is_file(), OPS_API_PATH
    spec = importlib.util.spec_from_file_location("phase53_ops_api", OPS_API_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _edge_applier_module() -> Any:
    assert EDGE_APPLIER.is_file(), EDGE_APPLIER
    spec = importlib.util.spec_from_file_location("phase53_edge_applier", EDGE_APPLIER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _edge_probe_module() -> Any:
    assert EDGE_PROBE.is_file(), EDGE_PROBE
    spec = importlib.util.spec_from_file_location("phase53_edge_probe", EDGE_PROBE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _live_backend_module() -> Any:
    assert LIVE_BACKEND.is_file(), LIVE_BACKEND
    spec = importlib.util.spec_from_file_location("phase53_live_backend", LIVE_BACKEND)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _binding_checker_module() -> Any:
    assert BINDING_CHECKER.is_file(), BINDING_CHECKER
    spec = importlib.util.spec_from_file_location(
        "phase53_binding_checker", BINDING_CHECKER
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _authority_builder_module() -> Any:
    assert AUTHORITY_BUILDER.is_file(), AUTHORITY_BUILDER
    spec = importlib.util.spec_from_file_location(
        "phase53_authority_builder", AUTHORITY_BUILDER
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_python_module(path: Path, name: str) -> Any:
    assert path.is_file(), path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assert_keys(payload: dict[str, Any], expected: set[str]) -> None:
    assert set(payload) == expected


def _walk_keys(payload: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(key.lower())
            keys.update(_walk_keys(value))
    elif isinstance(payload, list):
        for value in payload:
            keys.update(_walk_keys(value))
    return keys


def _validate_runtime(payload: dict[str, Any]) -> None:
    _assert_keys(
        payload,
        {
            "schema_version",
            "workstream",
            "primary_host",
            "upstream",
            "runtime",
            "paths",
            "identity",
            "resources",
            "logs",
            "rollback",
            "prohibitions",
        },
    )
    assert payload["schema_version"] == 1
    assert payload["workstream"] == "rustdesk-fleet"
    assert payload["primary_host"] == "horistic-srv"

    upstream = payload["upstream"]
    _assert_keys(
        upstream,
        {
            "version",
            "architecture",
            "repository",
            "immutable_reference",
            "linux_arm64_digest",
            "pull_policy",
            "build_on_target",
        },
    )
    assert upstream["version"] == "1.1.15"
    assert upstream["architecture"] == "arm64"
    assert upstream["immutable_reference"] == (
        "docker.io/rustdesk/rustdesk-server@"
        "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
    )
    assert upstream["linux_arm64_digest"] == (
        "sha256:17c3422e0a6a65199ef69ac5cbb265ce9314a04524afcf9bb7a374fec0b1c208"
    )
    assert upstream["pull_policy"] == "never"
    assert upstream["build_on_target"] is False

    runtime = payload["runtime"]
    _assert_keys(
        runtime,
        {
            "engine",
            "rootless",
            "manager",
            "network",
            "read_only_rootfs",
            "no_new_privileges",
            "drop_capabilities",
            "containers",
            "local_runtime_required",
            "local_runtime_forbidden",
        },
    )
    assert runtime["engine"] == "podman"
    assert runtime["rootless"] is True
    assert runtime["manager"] == "user-systemd-quadlet"
    assert runtime["network"] == "host"
    assert runtime["read_only_rootfs"] is True
    assert runtime["no_new_privileges"] is True
    assert runtime["drop_capabilities"] == "all"
    assert runtime["containers"] == {
        "hbbs": {"command": "hbbs", "tcp": [21115, 21116, 21118], "udp": [21116]},
        "hbbr": {"command": "hbbr", "tcp": [21117, 21119], "udp": []},
    }
    assert runtime["local_runtime_required"] == {
        "hbbs": {"tcp": [21115, 21116, 21118], "udp": [21116]},
        "hbbr": {"tcp": [21117, 21119], "udp": []},
    }
    assert runtime["local_runtime_forbidden"] == {
        "tcp": [21114],
        "unexpected_delta": "any-socket-outside-pinned-upstream-set",
    }

    paths = payload["paths"]
    _assert_keys(paths, {"quadlets", "state", "runtime_identity", "logs", "rollback"})
    assert all("client" not in path for path in paths.values())
    assert paths["runtime_identity"].startswith("/run/user/<uid>/")

    identity = payload["identity"]
    _assert_keys(
        identity,
        {
            "authority",
            "private_key_ref",
            "public_key_ref",
            "runtime_medium",
            "durable_evidence",
            "forbidden_surfaces",
        },
    )
    assert identity["authority"] == "hashicorp-vault"
    assert identity["runtime_medium"] == "tmpfs"
    assert identity["durable_evidence"] == ["public_fingerprint", "value_free_metadata"]
    assert identity["private_key_ref"] == {
        "vault_path": "kv/atius/rustdesk/server",
        "field": "private_key",
    }

    resources = payload["resources"]
    _assert_keys(resources, {"parent_slice", "services", "server_pair", "aggregate"})
    services = resources["services"]
    assert services == {
        "hbbs": {"cpu_percent": 35, "memory_bytes": 469762048},
        "hbbr": {"cpu_percent": 35, "memory_bytes": 402653184},
        "ops_api": {"cpu_percent": 10, "memory_bytes": 201326592},
    }
    assert resources["server_pair"] == {"cpu_percent": 70, "memory_bytes": 872415232}
    assert resources["aggregate"] == {"cpu_percent": 80, "memory_bytes": 1073741824}
    assert sum(row["cpu_percent"] for row in services.values()) == 80
    assert sum(row["memory_bytes"] for row in services.values()) == 1073741824

    logs = payload["logs"]
    _assert_keys(logs, {"authoritative_path", "daily_bytes", "retention_days", "reserve_bytes"})
    assert logs == {
        "authoritative_path": "/home/horistic/.local/state/atius-rustdesk/server/logs",
        "daily_bytes": 134217728,
        "retention_days": 30,
        "reserve_bytes": 4026531840,
    }

    rollback = payload["rollback"]
    _assert_keys(
        rollback,
        {
            "containment_first",
            "terminal_states",
            "preserve_phase52_backups",
            "preserve_legacy_access",
            "future_client_domain_untouched",
        },
    )
    assert rollback["containment_first"][0] == "restore-host-and-oci-ingress"
    assert rollback["terminal_states"] == ["ROLLED_BACK", "RESTORED_PRODUCTION"]
    assert rollback["preserve_phase52_backups"] is True
    assert rollback["future_client_domain_untouched"] is True


def _validate_edge(payload: dict[str, Any]) -> None:
    _assert_keys(
        payload,
        {
            "schema_version",
            "workstream",
            "primary_host",
            "public_edge",
            "backend",
            "target",
            "hostnames",
            "dns_records",
            "translations",
            "internal_native_listeners",
            "address_consensus",
            "effective_ingress",
            "public_ipv4_allowed",
            "public_forbidden",
            "ipv6_policy",
            "dns_last",
            "external_probes",
            "transaction_order",
            "rollback_order",
        },
    )
    assert payload["schema_version"] == 2
    assert payload["primary_host"] == "horistic-srv"
    assert payload["target"] == {
        "private_ipv4": "10.21.1.21",
        "reserved_public_ipv4": "137.131.140.20",
    }
    assert payload["public_edge"] == {
        "host": "atius-srv-1",
        "public_ipv4": "137.131.140.20",
        "public_vnic_private_ipv4": "10.0.0.238",
        "route_vnic_private_ipv4": "10.11.1.11",
        "route_interface": "enp1s0",
    }
    assert payload["backend"] == {
        "host": "horistic-srv",
        "private_ipv4": "10.21.1.21",
        "native_ingress_source_ipv4": "10.11.1.11",
        "native_listeners": {
            "tcp": [21115, 21116, 21117],
            "udp": [21116],
        },
    }
    assert payload["hostnames"] == {
        "general": "rustdesk.atius.com.br",
        "id": "rustdesk-id.atius.com.br",
        "relay": "rustdesk-relay.atius.com.br",
        "operations": "rustdesk-ops.atius.com.br",
    }
    assert payload["dns_records"] == [
        {
            "name": "rustdesk.atius.com.br",
            "role": "general",
            "type": "A",
            "content": "137.131.140.20",
            "proxied": False,
        },
        {
            "name": "rustdesk-id.atius.com.br",
            "role": "id",
            "type": "A",
            "content": "137.131.140.20",
            "proxied": False,
        },
        {
            "name": "rustdesk-relay.atius.com.br",
            "role": "relay",
            "type": "A",
            "content": "137.131.140.20",
            "proxied": False,
        },
    ]
    assert payload["translations"] == [
        {"role": "id", "protocol": "tcp", "external_port": 34099, "internal_port": 21115},
        {
            "role": "rendezvous",
            "protocol": "tcp",
            "external_port": 34100,
            "internal_port": 21116,
        },
        {
            "role": "rendezvous",
            "protocol": "udp",
            "external_port": 34100,
            "internal_port": 21116,
        },
        {
            "role": "relay",
            "protocol": "tcp",
            "external_port": 34101,
            "internal_port": 21117,
        },
    ]
    assert payload["internal_native_listeners"] == {
        "tcp": [21115, 21116, 21117],
        "udp": [21116],
    }
    assert payload["public_ipv4_allowed"] == {
        "tcp": [34099, 34100, 34101],
        "udp": [34100],
    }
    assert payload["public_forbidden"] == {
        "tcp": [21114, 21115, 21116, 21117, 21118, 21119],
        "udp": [21116],
        "unexpected": "all-other-direct-public-listeners",
    }
    assert payload["ipv6_policy"] == {"rustdesk": "deny-all", "aaaa_record": False}

    consensus = payload["address_consensus"]
    _assert_keys(consensus, {"required_equal_sources", "mismatch_action"})
    assert consensus["required_equal_sources"] == [
        "oci-edge-vnic-public-ipv4",
        "edge-vnic-public-ipv4",
        "reserved-public-ipv4",
    ]
    assert consensus["mismatch_action"] == "block-before-write"

    ingress = payload["effective_ingress"]
    _assert_keys(
        ingress,
        {
            "host_policy",
            "oci_policy",
            "backend_policy",
            "backend_source_ipv4",
            "union_audit_required",
            "broad_allow_action",
        },
    )
    assert ingress["host_policy"] == "owned-cross-host-dnat-forward-snat"
    assert ingress["oci_policy"] == "edge-public-vnic-security-lists-plus-attached-nsgs"
    assert ingress["backend_policy"] == "native-listeners-from-deterministic-edge-identity-only"
    assert ingress["backend_source_ipv4"] == "10.11.1.11"
    assert ingress["union_audit_required"] is True
    assert ingress["broad_allow_action"] == "block"

    dns = payload["dns_last"]
    _assert_keys(dns, {"type", "proxied", "aaaa", "concurrent_cname", "publish_after", "rollback_exact"})
    assert dns["type"] == "A"
    assert dns["proxied"] is False
    assert dns["aaaa"] is False
    assert dns["concurrent_cname"] is False
    assert dns["publish_after"] == ["host-ingress", "oci-ingress", "public-ip-probes"]
    assert dns["rollback_exact"] is True

    probes = payload["external_probes"]
    _assert_keys(probes, {"origins", "tcp", "udp", "udp_correlation", "same_host_allowed"})
    assert probes["origins"][0] == "GIOVANNI-W11-PC-private-first"
    assert len(probes["origins"]) == 2
    assert probes["same_host_allowed"] is False
    assert probes["tcp"] == {
        "positive": [34099, 34100, 34101],
        "negative": [21114, 21115, 21116, 21117, 21118, 21119],
        "targets": [
            "public-ipv4",
            "rustdesk.atius.com.br",
            "rustdesk-id.atius.com.br",
            "rustdesk-relay.atius.com.br",
        ],
    }
    assert probes["udp"] == {
        "external_port": 34100,
        "backend_port": 21116,
        "targets": [
            "public-ipv4",
            "rustdesk.atius.com.br",
            "rustdesk-id.atius.com.br",
            "rustdesk-relay.atius.com.br",
        ],
    }
    assert probes["udp_correlation"] == [
        "disposable-nonce-not-persisted",
        "nft-counter-delta",
        "metadata-only-capture-tuple",
        "pinned-hbbs-socket-owner",
        "distinct-origin-attempt-timestamp",
    ]
    assert payload["transaction_order"].index("publish-dns-a") > payload["transaction_order"].index(
        "public-ip-probes"
    )
    assert payload["rollback_order"][0] == "close-or-restore-ingress"


def _validate_ops_api(payload: dict[str, Any]) -> None:
    _assert_keys(
        payload,
        {
            "schema_version",
            "workstream",
            "hostname",
            "transport",
            "endpoints",
            "backend_auth",
            "redaction",
            "readiness_inputs",
            "metrics_semantics",
            "forbidden_semantics",
        },
    )
    assert payload["schema_version"] == 1
    assert payload["hostname"] == "rustdesk-ops.atius.com.br"
    assert payload["transport"] == {
        "public": "apache-https-443",
        "backend": "loopback-or-private-unix-socket",
        "direct_public_backend": False,
    }
    assert payload["endpoints"] == [
        {"method": "GET", "path": "/v1/health"},
        {"method": "GET", "path": "/v1/readiness"},
        {"method": "GET", "path": "/v1/status"},
        {"method": "GET", "path": "/v1/metrics/summary"},
    ]
    assert payload["backend_auth"]["required"] is True
    assert payload["backend_auth"]["uniform_denial_status"] == 401
    assert payload["backend_auth"]["credential_authority"] == "hashicorp-vault"
    assert payload["redaction"]["authorization_header_logged"] is False
    assert payload["redaction"]["secret_material_in_response"] is False
    assert set(payload["readiness_inputs"]) == {
        "immutable-image-digest",
        "exact-listener-ownership",
        "public-fingerprint-continuity",
        "effective-edge-policy",
        "resource-ceilings",
        "disk-and-log-bounds",
        "bounded-restart-counters",
    }
    assert payload["metrics_semantics"]["transport_claim_allowed"] is False
    assert payload["forbidden_semantics"] == {
        "rustdesk_client_api_server": False,
        "tcp_21114": False,
        "pro_device_or_account_api": False,
        "stored_pass_verdict": False,
    }


def test_contract_schema_files_parse_strictly() -> None:
    for path in (
        RUNTIME_CONTRACT,
        EDGE_CONTRACT,
        OPS_API_CONTRACT,
        ADMISSION_CONTRACT,
        PROVIDER_CONTRACT,
        CANDIDATE_RUNTIME_CONTRACT,
    ):
        assert path.is_file(), path
        _load_strict(path)


def test_successor_admission_and_evidence_validator_are_fail_closed() -> None:
    admission = _load_strict(ADMISSION_CONTRACT)
    candidate = _load_strict(CANDIDATE_RUNTIME_CONTRACT)
    evidence = _load_strict(
        REPO / "modules/rustdesk-fleet/evidence/phase53/candidate-admission.json"
    )
    assert admission["candidate_status"] == "NOT_ADMITTED"
    assert admission["provenance"]["signature_verified"] is False
    assert candidate["upstream"]["version"] == "1.1.16"
    assert evidence["candidate_status"] == "NOT_ADMITTED"
    assert evidence["admission_performed"] is False
    assert evidence["live_mutation_performed"] is False
    validator_path = REPO / "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py"
    spec = importlib.util.spec_from_file_location("phase53_evidence_validator", validator_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with pytest.raises(module.EvidenceInvalid, match="^obsolete-05b-authority-set$"):
        module.validate(REPO)


def test_evidence_validator_supports_current_admitted_pre_mutation_state(monkeypatch: Any) -> None:
    validator_path = REPO / "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py"
    spec = importlib.util.spec_from_file_location("phase53_evidence_validator_admitted", validator_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    originals = {
        name: copy.deepcopy(
            _load_strict(REPO / "modules/rustdesk-fleet/evidence/phase53" / name)
        )
        for name in module.EVIDENCE_NAMES
    }
    contract_originals = {
        name: copy.deepcopy(_load_strict(CONTRACT_DIR / name))
        for name in module.CONTRACT_NAMES
    }
    for payload in originals.values():
        payload["source_head"] = "head"
    originals["candidate-admission.json"].update(
        {
            "candidate_status": "ADMITTED_PHASE53",
            "state": "ADMITTED_PHASE53",
            "admission_performed": True,
            "provenance": {
                "signature_verified": False,
                "disposition": "OWNER_EXCEPTION_APPROVED",
            },
            "owner_approval": {
                "owner": "Giovanni Muniz",
                "approval_ref": "review-53-05C",
                "expires_at": "2099-01-01T00:00:00Z",
                "risk_disposition": "accepted-for-test",
                "hash_binding": True,
            },
            "required_gates": {
                "fresh_supply": "PASS",
                "compatibility_matrix": "PASS",
                "contract_parity": "CURRENT",
                "pre_state": "PASS",
                "rollback_ready": "PASS",
                "capacity_finalize": "PASS",
            },
        }
    )
    originals["server-1.1.16-evaluation.json"].update(
        {"candidate_status": "ADMITTED_PHASE53", "admission_performed": True}
    )
    originals["contract-parity.json"].update(
        {
            "state": "CURRENT",
            "current_contract_digests": {
                name: "a" * 64 for name in module.CONTRACT_NAMES
            },
            "consumer_digests": {
                "atius-rustdesk-server-hbbs.container": "a" * 64,
                "atius-rustdesk-server-hbbr.container": "a" * 64,
                "install-phase53-server.py": "a" * 64,
                "rustdesk-ops-api.py": "a" * 64,
            },
        }
    )
    required_vectors = contract_originals["phase53-candidate-admission.json"][
        "client_compatibility"
    ]["required_matrix"]
    compatibility = originals["compatibility-pending.json"]
    compatibility.update(
        {
            "state": "CURRENT",
            "vectors_tested": list(required_vectors),
        }
    )
    for item in compatibility["matrix"].values():
        item["tested"] = True
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    samples = []
    for host in ("atius-srv-2", "atius-srv-3"):
        for _ in range(2):
            samples.append(
                {
                    "host": host,
                    "observed_at": now,
                    "placement_state": "NO-GO",
                    "zero_cleanup_performed": False,
                }
            )
    for _ in range(2):
        samples.append(
            {
                "host": "horistic-srv",
                "observed_at": now,
                "placement_state": "GO",
                "raw_capacity_state": "CURRENT",
                "capacity_finalize_state": "CURRENT",
                "zero_cleanup_performed": False,
            }
        )
    originals["capacity-current.json"].update(
        {
            "state": "CURRENT",
            "finalize_ttl_seconds": 3600,
            "selected_primary": "horistic-srv",
            "samples": samples,
        }
    )
    originals["deploy-transaction.json"].update(
        {
            "state": "READY_BEFORE_MUTATION",
            "rollback_ready": True,
            "pre_state_digest": "b" * 64,
            "transaction_id": None,
            "mutation_performed": False,
            "journal_created": False,
        }
    )
    originals["edge-probes.json"].update(
        {
                "state": "CURRENT",
                "probes_completed": True,
                "udp_reflection_negative": True,
                "positive_tcp_ports": [34099, 34100, 34101],
                "negative_tcp_ports": [21114, 21115, 21116, 21117, 21118, 21119],
                "targets": [
                    "public-ipv4",
                    "rustdesk.atius.com.br",
                    "rustdesk-id.atius.com.br",
                    "rustdesk-relay.atius.com.br",
                ],
                "udp_targets": [
                    "public-ipv4",
                    "rustdesk.atius.com.br",
                    "rustdesk-id.atius.com.br",
                    "rustdesk-relay.atius.com.br",
                ],
                "udp_external_port": 34100,
                "udp_backend_port": 21116,
                "dns_records": [
                    "rustdesk.atius.com.br",
                    "rustdesk-id.atius.com.br",
                    "rustdesk-relay.atius.com.br",
                ],
                "public_edge_host": "atius-srv-1",
                "backend_host": "horistic-srv",
                "backend_ingress_source_ipv4": "10.11.1.11",
                "native_public_positive": False,
        }
    )
    originals["ops-api-probes.json"].update(
        {
            "state": "CURRENT",
            "probes_completed": True,
            "mutation_performed": False,
            "final_receipt_present": True,
        }
    )

    monkeypatch.setattr(module, "_head", lambda repo: "head")
    monkeypatch.setattr(
        module,
        "_strict",
        lambda path: originals[path.name]
        if path.name in originals
        else contract_originals[path.name],
    )
    monkeypatch.setattr(module, "_sha256", lambda path: "a" * 64)
    result = module.validate_legacy_05b(REPO)
    assert result["state"] == "ADMITTED_PHASE53"
    assert result["candidate_status"] == "ADMITTED_PHASE53"
    assert result["mutation_performed"] is False

    samples = originals["capacity-current.json"]["samples"]
    samples[1], samples[2] = samples[2], samples[1]
    with pytest.raises(module.EvidenceInvalid, match="capacity-sample-order-invalid"):
        module.validate_legacy_05b(REPO)
    samples[1], samples[2] = samples[2], samples[1]

    bad_digest = "sha256:" + "g" * 64
    digest_targets = (
        (
            originals["candidate-admission.json"]["candidate_contract"],
            "image_linux_arm64_digest",
            "candidate-image-digest-invalid",
        ),
        (
            contract_originals["phase53-runtime-candidate.json"]["upstream"],
            "linux_arm64_digest",
            "runtime-image-digest-invalid",
        ),
        (
            originals["server-1.1.16-evaluation.json"]["server"]["image"],
            "linux_arm64_digest",
            "evaluation-image-digest-invalid",
        ),
    )
    for target, key, error in digest_targets:
        original_value = target[key]
        target[key] = bad_digest
        with pytest.raises(module.EvidenceInvalid, match=error):
            module.validate_legacy_05b(REPO)
        target[key] = original_value
    immutable_upstream = contract_originals["phase53-runtime-candidate.json"]["upstream"]
    original_reference = immutable_upstream["immutable_reference"]
    immutable_upstream["immutable_reference"] = "docker.io/rustdesk/rustdesk-server@" + bad_digest
    with pytest.raises(module.EvidenceInvalid, match="candidate-immutable-reference-digest-invalid"):
        module.validate_legacy_05b(REPO)
    immutable_upstream["immutable_reference"] = original_reference

    originals["capacity-current.json"]["secret_material_present"] = True
    with pytest.raises(module.EvidenceInvalid, match="secret-surface:capacity-current.json.secret_material_present"):
        module.validate_legacy_05b(REPO)
    originals["capacity-current.json"].pop("secret_material_present")

    provider_payload = contract_originals["phase53-provider-manifest.json"]
    original_routes = provider_payload["routes"]
    provider_payload["routes"] = []
    with pytest.raises(module.EvidenceInvalid, match="provider-manifest-shape-invalid"):
        module.validate_legacy_05b(REPO)
    provider_payload["routes"] = original_routes

    edge_payload = contract_originals["phase53-edge.json"]
    original_external = edge_payload["external_probes"]
    edge_payload["external_probes"] = []
    with pytest.raises(module.EvidenceInvalid, match="edge-contract-shape-invalid"):
        module.validate_legacy_05b(REPO)
    edge_payload["external_probes"] = original_external

    originals["capacity-current.json"]["state"] = "BLOCKED_STALE"
    with pytest.raises(module.EvidenceInvalid, match="capacity-finalize-not-current"):
        module.validate_legacy_05b(REPO)
    originals["capacity-current.json"]["state"] = "CURRENT"

    originals["compatibility-pending.json"]["state"] = "PENDING"
    with pytest.raises(module.EvidenceInvalid, match="compatibility-not-current"):
        module.validate_legacy_05b(REPO)
    originals["compatibility-pending.json"]["state"] = "CURRENT"

    contract_originals["phase53-provider-manifest.json"]["routes"]["ssh"]["batch_mode"] = False
    with pytest.raises(module.EvidenceInvalid, match="provider-manifest-semantics-invalid"):
        module.validate_legacy_05b(REPO)
    contract_originals["phase53-provider-manifest.json"]["routes"]["ssh"]["batch_mode"] = True

    contract_originals["phase53-runtime-candidate.json"]["upstream"]["version"] = "drift"
    with pytest.raises(module.EvidenceInvalid, match="candidate-runtime-hash-drift"):
        module.validate_legacy_05b(REPO)
    originals["candidate-admission.json"]["required_gates"].pop("capacity_finalize")
    with pytest.raises(module.EvidenceInvalid, match="admission-authority-incomplete"):
        module.validate_legacy_05b(REPO)


def test_contract_schema_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
    with pytest.raises(DuplicateKeyError, match="duplicate JSON key"):
        _load_strict(path)


def test_runtime_contract_schema_and_resource_arithmetic() -> None:
    _validate_runtime(_load_strict(RUNTIME_CONTRACT))


def test_edge_contract_schema_and_dns_last_order() -> None:
    _validate_edge(_load_strict(EDGE_CONTRACT))


def test_d06_cross_host_contract_and_provider_roles_are_exact() -> None:
    edge = _load_strict(EDGE_CONTRACT)
    provider = _load_strict(PROVIDER_CONTRACT)

    assert edge["public_edge"] == {
        "host": "atius-srv-1",
        "public_ipv4": "137.131.140.20",
        "public_vnic_private_ipv4": "10.0.0.238",
        "route_vnic_private_ipv4": "10.11.1.11",
        "route_interface": "enp1s0",
    }
    assert edge["backend"] == {
        "host": "horistic-srv",
        "private_ipv4": "10.21.1.21",
        "native_ingress_source_ipv4": "10.11.1.11",
        "native_listeners": {
            "tcp": [21115, 21116, 21117],
            "udp": [21116],
        },
    }
    assert provider["routes"]["oci"]["execution_targets"] == {
        "public_edge": {
            "host": "atius-srv-1",
            "private_ipv4": "10.0.0.238",
            "capabilities": ["nft-dnat", "nft-forward", "nft-snat", "oci-edge-ingress"],
        },
        "backend": {
            "host": "horistic-srv",
            "private_ipv4": "10.21.1.21",
            "capabilities": ["rustdesk-server", "native-ingress-source-restriction"],
        },
    }


def test_d06_nft_and_boot_unit_are_transactional_cross_host_policy() -> None:
    nft = EDGE_NFT_POLICY.read_text(encoding="utf-8")
    for required in (
        "type nat hook prerouting priority dstnat; policy accept;",
        "ct status dnat",
        "ct original proto-dst 34099",
        "ct original proto-dst 34100",
        "ct original proto-dst 34101",
        "dnat ip to 10.21.1.21:21115",
        "dnat ip to 10.21.1.21:21116",
        "dnat ip to 10.21.1.21:21117",
        "type filter hook forward priority filter; policy accept;",
        "type nat hook postrouting priority srcnat; policy accept;",
        "snat ip to 10.11.1.11",
    ):
        assert required in nft
    assert "redirect to" not in nft

    service = _load_unit(EDGE_BOOT_SERVICE)["Service"]
    assert service["ExecStart"].startswith(
        "/usr/local/libexec/apply-phase53-edge.py --apply-host-policy-transaction "
    )
    assert "/usr/sbin/nft --file" not in service["ExecStart"]
    assert "ExecStartPost" not in service


def test_translated_edge_contract_is_single_consumer_authority(tmp_path: Path) -> None:
    expected = _load_strict(EDGE_CONTRACT)
    probe = _edge_probe_module()
    apply = _edge_applier_module()

    assert probe.load_edge_contract(EDGE_CONTRACT) == expected
    assert apply.load_edge_contract(EDGE_CONTRACT) == expected

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        EDGE_CONTRACT.read_text(encoding="utf-8").replace(
                '"schema_version": 2,',
                '"schema_version": 2, "schema_version": 2,',
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(probe.ProbeBlocked, match="edge-contract-invalid"):
        probe.load_edge_contract(duplicate)
    with pytest.raises(apply.EdgeBlocked, match="edge-contract-invalid"):
        apply.load_edge_contract(duplicate)

    stale = copy.deepcopy(expected)
    stale["translations"][3]["external_port"] = 21117
    stale_path = tmp_path / "stale.json"
    stale_path.write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(probe.ProbeBlocked, match="edge-contract-invalid"):
        probe.load_edge_contract(stale_path)
    with pytest.raises(apply.EdgeBlocked, match="edge-contract-invalid"):
        apply.load_edge_contract(stale_path)


def test_hbbs_relay_announcement_is_derived_from_translated_edge_contract() -> None:
    edge = _load_strict(EDGE_CONTRACT)
    relay_record = next(item for item in edge["dns_records"] if item["role"] == "relay")
    relay_mapping = next(
        item
        for item in edge["translations"]
        if item["role"] == "relay" and item["protocol"] == "tcp"
    )
    expected = f"{relay_record['name']}:{relay_mapping['external_port']}"
    unit = _load_unit(HBBS_QUADLET)
    assert unit["Container"]["Exec"] == f"hbbs -r {expected}"
    assert expected == "rustdesk-relay.atius.com.br:34101"


def test_phase53_server_installer_rejects_source_and_runtime_hbbs_tamper(
    tmp_path: Path,
) -> None:
    module = _server_installer_module()
    runner = _FakeServerRunner()
    repo = tmp_path / "repo"
    shutil.copytree(
        REPO / "modules/rustdesk-fleet",
        repo / "modules/rustdesk-fleet",
    )
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    transaction = _new_server_transaction(module, sandbox, runner, repo=repo)
    transaction._validate_sources()

    source = transaction.repo / "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container"
    source.write_text(
        source.read_text(encoding="utf-8").replace(":34101", ":21117"),
        encoding="utf-8",
    )
    with pytest.raises(module.Phase53ServerBlocked, match="hbbs-relay-endpoint-invalid"):
        transaction._validate_sources()
    shutil.copy2(HBBS_QUADLET, source)

    transaction.snapshot_prestate()
    transaction.render_and_verify_units()
    installed = transaction.quadlet_dir / source.name
    transaction._validate_installed_hbbs()
    installed.write_text(
        installed.read_text(encoding="utf-8").replace(":34101", ":21117"),
        encoding="utf-8",
    )
    with pytest.raises(module.Phase53ServerBlocked, match="installed-hbbs-command-invalid"):
        transaction._validate_installed_hbbs()


def test_provider_manifest_is_exact_and_rejects_mutable_or_unbounded_backends(
    tmp_path: Path,
) -> None:
    backend = _live_backend_module()
    manifest = _load_strict(PROVIDER_CONTRACT)
    backend.validate_provider_manifest(manifest, repo=REPO)

    mutations = [
        ("provider-manifest-target-invalid", lambda item: item.update({"execution_target": "10.31.1.31"})),
        (
            "provider-manifest-edge-contract-invalid",
            lambda item: item.update({"edge_contract": "/tmp/phase53-edge.json"}),
        ),
        (
            "provider-manifest-backend-invalid",
            lambda item: item["backends"].update({"apply": "shell"}),
        ),
        (
            "provider-manifest-limit-invalid",
            lambda item: item["limits"].update({"command_timeout_seconds": 0}),
        ),
    ]
    for blocker, mutate in mutations:
        candidate = copy.deepcopy(manifest)
        mutate(candidate)
        with pytest.raises(backend.BackendBlocked, match=f"^{blocker}$"):
            backend.validate_provider_manifest(candidate, repo=REPO)

    candidate_path = tmp_path / "manifest.json"
    candidate_path.write_text(json.dumps(manifest), encoding="utf-8")
    binding = backend.ExecutionSourceBinding(
        commit="a" * 40,
        tree_sha256="b" * 64,
        blobs={"modules/rustdesk-fleet/contracts/phase53-edge.json": "c" * 64},
    )
    read_only = backend.build_phase53_read_only_backend(
        repo=REPO,
        manifest_path=candidate_path,
        source_binding=binding,
        clock=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
    )
    assert read_only.capabilities == frozenset({"read", "preview"})
    assert not any(
        hasattr(read_only, name)
        for name in ("runtime", "providers", "mutate", "containment", "rollback", "restore")
    )
    for callback in (
        read_only.read_prestate,
        read_only.preview_oci,
        read_only.preview_cloudflare,
        read_only.preview_apache,
    ):
        result = callback()
        assert result["mutation_performed"] is False
        assert result["secret_material_present"] is False


def test_apply_backend_is_owner_hash_and_expiry_bound() -> None:
    backend = _live_backend_module()
    now = datetime(2026, 7, 25, tzinfo=timezone.utc)
    noop = lambda: {"mutation_performed": False}
    edge_stages = {stage: noop for stage in backend.RUNTIME_EDGE_STAGES}
    runtime = backend.RuntimeProvider(
        transaction_id="d" * 32,
        snapshot_prestate=noop,
        install_closed=noop,
        rollback_server=noop,
        edge_stages=edge_stages,
        containment=noop,
    )
    providers = runtime.to_bundle()
    plan = {
        "schema_version": 1,
        "target": "10.21.1.21",
        "operation_plan_sha256": "a" * 64,
        "expires_at": "2026-07-25T01:00:00Z",
        "runtime": runtime,
        "providers": providers,
    }
    approval = {
        "schema_version": 1,
        "owner": "Giovanni Muniz",
        "operation_plan_sha256": "a" * 64,
        "approval_sha256": "b" * 64,
        "expires_at": "2026-07-25T01:00:00Z",
    }
    with pytest.raises(backend.BackendBlocked, match="^live-flag-required$"):
        backend.build_phase53_apply_backend(
            repo=REPO,
            manifest_path=PROVIDER_CONTRACT,
            operation_plan=plan,
            owner_approval=approval,
            live_enabled=False,
            admitted=True,
            clock=lambda: now,
        )
    with pytest.raises(backend.BackendBlocked, match="^admission-required$"):
        backend.build_phase53_apply_backend(
            repo=REPO,
            manifest_path=PROVIDER_CONTRACT,
            operation_plan=plan,
            owner_approval=approval,
            live_enabled=True,
            admitted=False,
            clock=lambda: now,
        )
    drifted = dict(approval, operation_plan_sha256="f" * 64)
    with pytest.raises(backend.BackendBlocked, match="^owner-approval-invalid$"):
        backend.build_phase53_apply_backend(
            repo=REPO,
            manifest_path=PROVIDER_CONTRACT,
            operation_plan=plan,
            owner_approval=drifted,
            live_enabled=True,
            admitted=True,
            clock=lambda: now,
        )
    result = backend.build_phase53_apply_backend(
        repo=REPO,
        manifest_path=PROVIDER_CONTRACT,
        operation_plan=plan,
        owner_approval=approval,
        live_enabled=True,
        admitted=True,
        clock=lambda: now,
    )
    assert result.runtime is runtime
    assert result.providers is providers
    assert result.operation_plan_sha256 == "a" * 64
    assert result.approval_sha256 == "b" * 64

    expired = dict(approval, expires_at="2026-07-24T23:59:59Z")
    with pytest.raises(backend.BackendBlocked, match="^owner-approval-expired$"):
        backend.build_phase53_apply_backend(
            repo=REPO,
            manifest_path=PROVIDER_CONTRACT,
            operation_plan=plan,
            owner_approval=expired,
            live_enabled=True,
            admitted=True,
            clock=lambda: now,
        )


def test_cli_mode_and_stage_matrix_are_literal() -> None:
    module = _live_gate_module()
    parser = module.build_parser()
    parsed = parser.parse_args(
        [
            "--repo",
            str(REPO),
            "--live-backend",
            "phase53-production",
            "--mode",
            "plan",
            "--stage",
            "full",
            "--operation-plan",
            "operation-plan.json",
        ]
    )
    assert parsed.live_backend == "phase53-production"
    assert parsed.mode == "plan"
    assert parsed.stage == "full"
    assert parsed.owner_approval is None
    assert set(module.EXECUTION_STAGES) == {
        "full",
        "edge-probes",
        "ops-api",
        "lifecycle",
        "rollback",
        "restore-production",
    }
    assert module.EXIT_USAGE == 2
    assert module.EXIT_AUTHORITY == 3
    assert module.EXIT_APPLY_FAILED == 4


def test_stage_full_uses_distinct_journals_and_immutable_rollback(
    tmp_path: Path,
) -> None:
    module = _live_gate_module()
    calls: list[str] = []

    def callback(stage: str) -> Any:
        def invoke() -> dict[str, Any]:
            calls.append(stage)
            return {
                "stage": stage,
                "mutation_performed": stage
                not in {"preflight", "ip-probes", "hostname-probes", "lifecycle"},
                "secret_material_present": False,
            }

        return invoke

    adapters = {
        stage: callback(stage) for stage in module.FULL_TRANSACTION_SEQUENCE
    }
    result = module.execute_apply_transaction(
        journal_dir=tmp_path,
        operation_plan_sha256="a" * 64,
        approval_sha256="b" * 64,
        execution_source_commit="c" * 40,
        execution_source_tree_sha256="d" * 64,
        adapters=adapters,
    )
    assert calls == list(module.FULL_TRANSACTION_SEQUENCE)
    assert len(
        {
            result["apply_transaction_id"],
            result["rollback_transaction_id"],
            result["restore_production_transaction_id"],
        }
    ) == 3
    assert result["apply_journal"] == "deploy-transaction.json"
    assert result["rollback_journal"] == "rollback-drill.json"
    assert result["restore_production_journal"] == "restore-production-transaction.json"
    rollback = tmp_path / result["rollback_journal"]
    before = rollback.read_bytes()
    assert hashlib.sha256(before).hexdigest() == result["rollback_seal_sha256"]
    assert rollback.stat().st_mode & 0o222 == 0
    assert rollback.read_bytes() == before


def test_migration_handoff_is_non_executable_and_future_target_is_rejected(
    tmp_path: Path,
) -> None:
    handoff = _load_strict(MIGRATION_HANDOFF)
    assert handoff["current"] == {
        "host": "horistic-srv",
        "private_ipv4": "10.21.1.21",
    }
    assert handoff["future"] == {
        "host": "horistic-srv",
        "private_ipv4": "10.31.1.31",
        "executable": False,
        "phase53_provider_allowed": False,
    }
    assert handoff["preserve"] == {
        "server_identity": True,
        "state_database": True,
        "public_edge_contract": True,
        "rollback_boundary": True,
    }

    backend = _live_backend_module()
    manifest = _load_strict(PROVIDER_CONTRACT)
    manifest["execution_target"] = "10.31.1.31"
    candidate = tmp_path / "provider.json"
    candidate.write_text(json.dumps(manifest), encoding="utf-8")
    binding = backend.ExecutionSourceBinding(
        commit="a" * 40,
        tree_sha256="b" * 64,
        blobs={"modules/rustdesk-fleet/contracts/phase53-edge.json": "c" * 64},
    )
    with pytest.raises(
        backend.BackendBlocked, match="provider-manifest-target-invalid"
    ):
        backend.build_phase53_read_only_backend(
            repo=REPO,
            manifest_path=candidate,
            source_binding=binding,
            clock=lambda: datetime(2026, 7, 25, tzinfo=timezone.utc),
        )

    production = _production_adapters_module()
    with pytest.raises(
        production.AdapterBlocked, match="provider-manifest-target-invalid"
    ):
        production.validate_provider_manifest(manifest)


def test_apply_cli_negative_authority_has_zero_side_effect(
    tmp_path: Path,
) -> None:
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1",
        "ADMITTED_PHASE53": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    before = sorted(item.relative_to(tmp_path) for item in tmp_path.rglob("*"))
    completed = subprocess.run(
        [
            sys.executable,
            str(LIVE_GATE_PATH),
            "--repo",
            str(REPO),
            "--live-backend",
            "phase53-production",
            "--mode",
            "apply",
            "--stage",
            "full",
            "--operation-plan",
            str(tmp_path / "missing-plan.json"),
            "--owner-approval",
            str(tmp_path / "missing-approval.json"),
        ],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 3
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload["status"] == "BLOCKED"
    assert payload["mutation_performed"] is False
    assert payload["journal_created"] is False
    assert payload["provider_constructed"] is False
    assert sorted(item.relative_to(tmp_path) for item in tmp_path.rglob("*")) == before


def _git_fixture(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def _phase53_binding_chain_fixture(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "binding-repo"
    repo.mkdir()
    _git_fixture(repo, "init", "-q")
    _git_fixture(repo, "config", "user.name", "Phase53 Test")
    _git_fixture(repo, "config", "user.email", "phase53@example.invalid")

    source_path = "source/runner.py"
    source = repo / source_path
    source.parent.mkdir(parents=True)
    source.write_text("EXECUTION_TARGET = '10.21.1.21'\n", encoding="utf-8")
    _git_fixture(repo, "add", "--", source_path)
    _git_fixture(repo, "commit", "-qm", "source")
    source_commit = _git_fixture(repo, "rev-parse", "HEAD")
    source_oid = _git_fixture(repo, "rev-parse", f"{source_commit}:{source_path}")
    source_tree = hashlib.sha256(
        f"{source_path}\0{source_oid}\n".encode()
    ).hexdigest()

    evidence_root = repo / "modules/rustdesk-fleet/evidence/phase53"
    evidence_root.mkdir(parents=True)
    plan_digest = "a" * 64
    apply_id = "1" * 32
    rollback_id = "2" * 32
    restore_id = "3" * 32
    seal = "b" * 64
    common = {
        "schema_version": 1,
        "execution_source_commit": source_commit,
        "execution_source_tree_sha256": source_tree,
        "operation_plan_sha256": plan_digest,
        "secret_material_present": False,
    }
    authority_payloads = {
        "preflight.json": {**common, "source_scope_clean": True},
        "edge-forwarder-operation-plan.json": {
            **common,
            "target": "10.21.1.21",
            "expires_at": "2099-01-01T00:00:00Z",
        },
        "edge-forwarder-owner-approval.json": {
            **common,
            "owner": "Giovanni Muniz",
            "decision": "approve",
            "expires_at": "2099-01-01T00:00:00Z",
        },
    }
    authority_paths: dict[str, Path] = {}
    for name, payload in authority_payloads.items():
        file_path = evidence_root / name
        file_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        authority_paths[name] = file_path
    _git_fixture(
        repo,
        "add",
        "--",
        *[str(item.relative_to(repo)) for item in authority_paths.values()],
    )
    _git_fixture(repo, "commit", "-qm", "authority")

    evidence_payloads = {
        "deploy-transaction.json": {
            **common,
            "apply_transaction_id": apply_id,
        },
        "edge-probes.json": {**common, "apply_transaction_id": apply_id},
        "ops-api-probes.json": {**common, "apply_transaction_id": apply_id},
        "lifecycle.json": {**common, "apply_transaction_id": apply_id},
        "rollback-drill.json": {
            **common,
            "apply_transaction_id": apply_id,
            "rollback_transaction_id": rollback_id,
            "rollback_seal_sha256": seal,
        },
        "restore-production-transaction.json": {
            **common,
            "apply_transaction_id": apply_id,
            "rollback_transaction_id": rollback_id,
            "restore_production_transaction_id": restore_id,
            "rollback_seal_sha256": seal,
        },
        "direct-relay-metrics.json": {
            **common,
            "apply_transaction_id": apply_id,
            "restore_production_transaction_id": restore_id,
        },
    }
    evidence_paths: dict[str, Path] = {}
    for name, payload in evidence_payloads.items():
        file_path = evidence_root / name
        file_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        evidence_paths[name] = file_path
    _git_fixture(
        repo,
        "add",
        "--",
        *[str(item.relative_to(repo)) for item in evidence_paths.values()],
    )
    _git_fixture(repo, "commit", "-qm", "evidence only")
    live_commit = _git_fixture(repo, "rev-parse", "HEAD")
    manifest_digests = {
        str(file_path.relative_to(repo)): hashlib.sha256(
            _git_fixture(
                repo, "show", f"{live_commit}:{file_path.relative_to(repo)}"
            ).encode()
        ).hexdigest()
        for file_path in evidence_paths.values()
    }

    phase_root = (
        repo
        / ".planning/workstreams/rustdesk-fleet/phases/53-primary-relay-and-public-edge"
    )
    phase_root.mkdir(parents=True)
    summary = phase_root / "53-05F-SUMMARY.md"
    table = "\n".join(
        f"| {name} | {digest} |" for name, digest in manifest_digests.items()
    )
    summary.write_text(
        "---\n"
        f"live_executor_commit: {live_commit}\n"
        f"execution_source_commit: {source_commit}\n"
        f"execution_source_tree_sha256: {source_tree}\n"
        f"operation_plan_sha256: {plan_digest}\n"
        "---\n"
        "# 53-05F Summary\n\n"
        "| path | sha256 |\n|---|---|\n"
        f"{table}\n",
        encoding="utf-8",
    )
    _git_fixture(repo, "add", "--", str(summary.relative_to(repo)))
    _git_fixture(repo, "commit", "-qm", "summary only")
    summary_commit = _git_fixture(repo, "rev-parse", "HEAD")

    verification = phase_root / "53-05F-VERIFICATION.md"
    verification.write_text(
        "---\n"
        "status: passed\n"
        f"live_executor_commit: {live_commit}\n"
        f"05F_summary_commit: {summary_commit}\n"
        f"execution_source_commit: {source_commit}\n"
        f"execution_source_tree_sha256: {source_tree}\n"
        "---\n# Independent verification\n",
        encoding="utf-8",
    )
    _git_fixture(repo, "add", "--", str(verification.relative_to(repo)))
    _git_fixture(repo, "commit", "-qm", "independent verification")

    return {
        "repo": repo,
        "source_path": source,
        "source_relative": source_path,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "live_commit": live_commit,
        "summary_commit": summary_commit,
        "summary": summary,
        "verification": verification,
        "authority": authority_paths,
        "evidence": evidence_paths,
    }


def _validate_binding_fixture(module: Any, fixture: dict[str, Any]) -> dict[str, Any]:
    authority = fixture["authority"]
    evidence = fixture["evidence"]
    return module.validate_phase53_binding_chain(
        repo=fixture["repo"],
        preflight=authority["preflight.json"],
        operation_plan=authority["edge-forwarder-operation-plan.json"],
        owner_approval=authority["edge-forwarder-owner-approval.json"],
        deploy=evidence["deploy-transaction.json"],
        edge_probes=evidence["edge-probes.json"],
        ops_api_probes=evidence["ops-api-probes.json"],
        lifecycle=evidence["lifecycle.json"],
        rollback=evidence["rollback-drill.json"],
        restore_production=evidence["restore-production-transaction.json"],
        direct_relay_metrics=evidence["direct-relay-metrics.json"],
        summary=fixture["summary"],
        verification=fixture["verification"],
        execution_source_paths=[fixture["source_relative"]],
        strict_validator=lambda _repo: {
            "state": "PASS",
            "requirements": ["SRV-02", "SRV-03", "SRV-04", "SRV-06", "OPS-01"],
        },
    )


def test_binding_chain_proves_evidence_only_summary_only_and_ancestry(
    tmp_path: Path,
) -> None:
    module = _binding_checker_module()
    fixture = _phase53_binding_chain_fixture(tmp_path)
    computed = module.compute_execution_source_binding(
        repo=fixture["repo"],
        execution_source_commit=fixture["source_commit"],
        manifest_paths=[fixture["source_relative"]],
    )
    assert computed["execution_source_tree_sha256"] == fixture["source_tree"]
    result = _validate_binding_fixture(module, fixture)
    assert result["status"] == "PASS"
    assert result["live_executor_commit"] == fixture["live_commit"]
    assert result["05F_summary_commit"] == fixture["summary_commit"]
    assert result["mutation_performed"] is False
    assert result["provider_constructed"] is False


def test_binding_chain_rejects_self_hash_ancestry_and_duplicate_inputs(
    tmp_path: Path,
) -> None:
    module = _binding_checker_module()
    fixture = _phase53_binding_chain_fixture(tmp_path)
    deploy = fixture["evidence"]["deploy-transaction.json"]
    payload = _load_strict(deploy)
    payload["self_sha256"] = "f" * 64
    deploy.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.BindingChainInvalid, match="self-hash-forbidden"):
        _validate_binding_fixture(module, fixture)
    _git_fixture(
        fixture["repo"],
        "checkout",
        "--",
        str(deploy.relative_to(fixture["repo"])),
    )

    verification = fixture["verification"]
    text = verification.read_text(encoding="utf-8").replace(
        fixture["summary_commit"], fixture["source_commit"]
    )
    verification.write_text(text, encoding="utf-8")
    with pytest.raises(module.BindingChainInvalid, match="summary-commit-mismatch"):
        _validate_binding_fixture(module, fixture)

    with pytest.raises(module.BindingChainInvalid, match="explicit-path-duplicate"):
        module.compute_execution_source_binding(
            repo=fixture["repo"],
            execution_source_commit=fixture["source_commit"],
            manifest_paths=[
                fixture["source_relative"],
                fixture["source_relative"],
            ],
        )


def test_binding_chain_rejects_dirty_scope_without_writes(tmp_path: Path) -> None:
    module = _binding_checker_module()
    fixture = _phase53_binding_chain_fixture(tmp_path)
    fixture["source_path"].write_text("DIRTY = True\n", encoding="utf-8")
    before = {
        item.relative_to(fixture["repo"]): item.read_bytes()
        for item in fixture["repo"].rglob("*")
        if item.is_file() and ".git" not in item.parts
    }
    with pytest.raises(module.BindingChainInvalid, match="execution-source-dirty"):
        _validate_binding_fixture(module, fixture)
    after = {
        item.relative_to(fixture["repo"]): item.read_bytes()
        for item in fixture["repo"].rglob("*")
        if item.is_file() and ".git" not in item.parts
    }
    assert after == before


def test_execution_source_scope_is_closed_sorted_and_excludes_mutable_authority() -> None:
    module = _binding_checker_module()
    payload = _load_strict(EXECUTION_SOURCE_SCOPE)
    paths = module.validate_execution_source_scope_payload(payload)

    assert tuple(paths) == EXPECTED_EXECUTION_SOURCE_PATHS
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths)) == 34
    assert all((REPO / item).is_file() for item in paths)
    assert not any((REPO / item).is_symlink() for item in paths)
    assert not any(
        marker in item
        for item in paths
        for marker in ("/evidence/", "/.planning/", "approval", "operation-plan")
    )
    assert not {
        ".planning/workstreams/rustdesk-fleet/REQUIREMENTS.md",
        "modules/rustdesk-fleet/evidence/ledger.json",
        "modules/rustdesk-fleet/tests/test_phase51_contracts.py",
    }.intersection(paths)


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        ("unknown-field", "source-scope-schema-invalid"),
        ("missing", "source-scope-missing"),
        ("extra", "source-scope-extra"),
        ("duplicate", "source-scope-duplicate"),
        ("unsorted", "source-scope-order-invalid"),
        ("evidence", "source-scope-forbidden"),
    ],
)
def test_execution_source_scope_rejects_unknown_missing_extra_and_mutable_paths(
    mutation: str,
    blocker: str,
) -> None:
    module = _binding_checker_module()
    payload = _load_strict(EXECUTION_SOURCE_SCOPE)
    if mutation == "unknown-field":
        payload["stored_verdict"] = "PASS"
    elif mutation == "missing":
        payload["paths"].remove(EXPECTED_EXECUTION_SOURCE_PATHS[0])
    elif mutation == "extra":
        payload["paths"].append(
            "modules/rustdesk-fleet/tools/phase53-unknown-live-consumer.py"
        )
        payload["paths"].sort()
    elif mutation == "duplicate":
        payload["paths"].append(payload["paths"][-1])
    elif mutation == "unsorted":
        payload["paths"] = list(reversed(payload["paths"]))
    else:
        payload["paths"].append(
            "modules/rustdesk-fleet/evidence/phase53/preflight.json"
        )
        payload["paths"].sort()

    with pytest.raises(module.BindingChainInvalid, match=blocker):
        module.validate_execution_source_scope_payload(payload)


def test_source_tree_digest_uses_only_sorted_git_blob_records(tmp_path: Path) -> None:
    module = _binding_checker_module()
    fixture = _phase53_binding_chain_fixture(tmp_path)
    second_relative = "source/validator.py"
    second_path = fixture["repo"] / second_relative
    second_path.write_text("STRICT = True\n", encoding="utf-8")
    _git_fixture(fixture["repo"], "add", "--", second_relative)
    _git_fixture(fixture["repo"], "commit", "-qm", "second source")
    source_commit = _git_fixture(fixture["repo"], "rev-parse", "HEAD")
    paths = sorted([fixture["source_relative"], second_relative])
    records = b""
    for relative in paths:
        oid = _git_fixture(
            fixture["repo"], "rev-parse", f"{source_commit}:{relative}"
        )
        records += relative.encode() + b"\0" + oid.encode() + b"\n"

    binding = module.compute_execution_source_binding(
        repo=fixture["repo"],
        execution_source_commit=source_commit,
        manifest_paths=paths,
    )
    assert binding["execution_source_tree_sha256"] == hashlib.sha256(records).hexdigest()
    assert binding["manifest_paths"] == paths


def test_execution_source_commit_accepts_exact_seven_paths_and_rejects_eighth(
    tmp_path: Path,
) -> None:
    module = _binding_checker_module()
    repo = tmp_path / "source-commit-repo"
    repo.mkdir()
    _git_fixture(repo, "init", "-q")
    _git_fixture(repo, "config", "user.name", "Phase53 Test")
    _git_fixture(repo, "config", "user.email", "phase53@example.invalid")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git_fixture(repo, "add", "--", "base.txt")
    _git_fixture(repo, "commit", "-qm", "base")
    for relative in EXPECTED_EXECUTION_SOURCE_COMMIT_PATHS:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n", encoding="utf-8")
    _git_fixture(repo, "add", "--", *EXPECTED_EXECUTION_SOURCE_COMMIT_PATHS)
    _git_fixture(repo, "commit", "-qm", "exact source seal")
    source_commit = _git_fixture(repo, "rev-parse", "HEAD")

    assert module.validate_execution_source_commit_paths(repo, source_commit) == list(
        EXPECTED_EXECUTION_SOURCE_COMMIT_PATHS
    )

    eighth = "modules/rustdesk-fleet/tools/unreviewed-eighth.py"
    eighth_path = repo / eighth
    eighth_path.write_text("UNREVIEWED = True\n", encoding="utf-8")
    _git_fixture(repo, "add", "--", eighth)
    _git_fixture(repo, "commit", "--amend", "--no-edit", "-q")
    with pytest.raises(
        module.BindingChainInvalid,
        match="execution-source-commit-paths-invalid",
    ):
        module.validate_execution_source_commit_paths(
            repo, _git_fixture(repo, "rev-parse", "HEAD")
        )


def test_execution_source_git_objects_reject_missing_and_symlink_entries(
    tmp_path: Path,
) -> None:
    module = _binding_checker_module()
    fixture = _phase53_binding_chain_fixture(tmp_path)
    with pytest.raises(module.BindingChainInvalid, match="git-object-missing"):
        module.compute_execution_source_binding(
            repo=fixture["repo"],
            execution_source_commit=fixture["source_commit"],
            manifest_paths=["source/missing.py"],
        )

    link = fixture["repo"] / "source/link.py"
    link.symlink_to("runner.py")
    _git_fixture(fixture["repo"], "add", "--", "source/link.py")
    _git_fixture(fixture["repo"], "commit", "-qm", "symlink source")
    link_commit = _git_fixture(fixture["repo"], "rev-parse", "HEAD")
    with pytest.raises(module.BindingChainInvalid, match="git-object-symlink"):
        module.compute_execution_source_binding(
            repo=fixture["repo"],
            execution_source_commit=link_commit,
            manifest_paths=["source/link.py"],
        )


@pytest.mark.parametrize("mutation", ["missing", "symlink", "modified-commit"])
def test_execution_source_worktree_rejects_missing_symlink_and_modified_entries(
    tmp_path: Path,
    mutation: str,
) -> None:
    module = _binding_checker_module()
    fixture = _phase53_binding_chain_fixture(tmp_path)
    if mutation == "missing":
        fixture["source_path"].unlink()
        blocker = "explicit-path-missing"
    elif mutation == "symlink":
        fixture["source_path"].unlink()
        fixture["source_path"].symlink_to("../source/runner.py")
        blocker = "explicit-path-invalid"
    else:
        fixture["source_path"].write_text("CHANGED = True\n", encoding="utf-8")
        _git_fixture(fixture["repo"], "add", "--", fixture["source_relative"])
        _git_fixture(fixture["repo"], "commit", "-qm", "changed source")
        blocker = "execution-source-changed"

    with pytest.raises(module.BindingChainInvalid, match=blocker):
        module.require_clean_execution_source(
            repo=fixture["repo"],
            execution_source_commit=fixture["source_commit"],
            manifest_paths=[fixture["source_relative"]],
            expected_tree=fixture["source_tree"],
        )


def test_ops_api_contract_schema_auth_and_readiness() -> None:
    _validate_ops_api(_load_strict(OPS_API_CONTRACT))


@pytest.mark.parametrize(
    ("contract_name", "mutator"),
    [
        ("runtime", lambda item: item["upstream"].update({"pull_policy": "always"})),
        ("runtime", lambda item: item["runtime"].update({"rootless": False})),
        ("runtime", lambda item: item["resources"]["services"]["hbbs"].update({"cpu_percent": 45})),
        ("runtime", lambda item: item["runtime"]["local_runtime_forbidden"].update({"tcp": []})),
        ("edge", lambda item: item["public_ipv4_allowed"]["tcp"].append(21118)),
        ("edge", lambda item: item["ipv6_policy"].update({"rustdesk": "allow"})),
        ("edge", lambda item: item["dns_last"].update({"proxied": True})),
        ("edge", lambda item: item["effective_ingress"].update({"union_audit_required": False})),
        ("ops", lambda item: item["backend_auth"].update({"required": False})),
        ("ops", lambda item: item["forbidden_semantics"].update({"tcp_21114": True})),
    ],
)
def test_contract_mutation_catalog_fails_closed(contract_name: str, mutator: Any) -> None:
    mapping = {
        "runtime": (RUNTIME_CONTRACT, _validate_runtime),
        "edge": (EDGE_CONTRACT, _validate_edge),
        "ops": (OPS_API_CONTRACT, _validate_ops_api),
    }
    path, validator = mapping[contract_name]
    payload = copy.deepcopy(_load_strict(path))
    mutator(payload)
    with pytest.raises(AssertionError):
        validator(payload)


def test_contract_mutation_rejects_extra_fields_and_stored_verdicts() -> None:
    for path, validator in (
        (RUNTIME_CONTRACT, _validate_runtime),
        (EDGE_CONTRACT, _validate_edge),
        (OPS_API_CONTRACT, _validate_ops_api),
    ):
        extra = copy.deepcopy(_load_strict(path))
        extra["unexpected"] = True
        with pytest.raises(AssertionError):
            validator(extra)

        stored = copy.deepcopy(_load_strict(path))
        stored["status"] = "PASS"
        assert {"status", "verdict", "pass"} & _walk_keys(stored)
        with pytest.raises(AssertionError):
            validator(stored)


def test_contract_schema_preserves_phase_boundaries() -> None:
    payloads = [_load_strict(path) for path in (RUNTIME_CONTRACT, EDGE_CONTRACT, OPS_API_CONTRACT)]
    encoded = json.dumps(payloads, sort_keys=True).lower()
    assert "msiexec" not in encoded
    assert "install-client" not in encoded
    assert _load_strict(RUNTIME_CONTRACT)["prohibitions"][-2:] == [
        "phase52-gate-b-replay",
        "phase54-client-installation",
    ]


def test_quadlets_are_digest_pinned_rootless_hardened_and_socket_exact() -> None:
    runtime = _load_strict(RUNTIME_CONTRACT)
    expected_image = runtime["upstream"]["immutable_reference"]
    expected = {
        HBBS_QUADLET: ("hbbs", "35%", "448M", {21115, 21116, 21118}, {21116}),
        HBBR_QUADLET: ("hbbr", "35%", "384M", {21117, 21119}, set()),
    }

    for path, (command, cpu, memory, tcp, udp) in expected.items():
        assert path.is_file(), path
        unit = _load_unit(path)
        container = unit["Container"]
        service = unit["Service"]
        encoded = path.read_text(encoding="utf-8")

        assert container["Image"] == expected_image
        assert container["Pull"] == "never"
        assert container["Network"] == "host"
        assert container["ReadOnly"] == "true"
        assert container["NoNewPrivileges"] == "true"
        assert container["DropCapability"] == "ALL"
        assert container["PidsLimit"] == "128"
        assert container["Exec"].split()[0] == command
        assert service["Slice"] == "atius-rustdesk-phase53.slice"
        assert service["CPUQuota"] == cpu
        assert service["MemoryMax"] == memory
        assert service["StandardOutput"] == "null"
        assert service["StandardError"] == "null"

        assert "%h/.local/share/atius-rustdesk/server/state:/root:rw" in encoded
        assert "%t/atius-rustdesk/server-identity/id_ed25519:/root/id_ed25519:ro" in encoded
        assert "%t/atius-rustdesk/server-identity/id_ed25519.pub:/root/id_ed25519.pub:ro" in encoded
        assert "%h/.local/state/atius-rustdesk/server/logs" in encoded
        assert "/run/podman/podman.sock" not in encoded
        assert "Privileged=true" not in encoded
        assert "AddCapability=" not in encoded

        declared = runtime["runtime"]["local_runtime_required"][command]
        assert set(declared["tcp"]) == tcp
        assert set(declared["udp"]) == udp
        assert 21114 not in tcp | udp


def test_runtime_parent_and_child_cgroup_arithmetic_effective_readback() -> None:
    runtime = _load_strict(RUNTIME_CONTRACT)
    assert PHASE53_SLICE.is_file(), PHASE53_SLICE
    unit = _load_unit(PHASE53_SLICE)
    assert unit["Slice"]["CPUQuota"] == "80%"
    assert unit["Slice"]["MemoryMax"] == "1G"
    assert unit["Slice"]["TasksMax"] == "512"

    fake_effective_readback = {
        "atius-rustdesk-phase53.slice": {"cpu_percent": 80, "memory_bytes": 1073741824},
        "atius-rustdesk-server-hbbs.service": {"cpu_percent": 35, "memory_bytes": 469762048},
        "atius-rustdesk-server-hbbr.service": {"cpu_percent": 35, "memory_bytes": 402653184},
    }
    assert fake_effective_readback["atius-rustdesk-phase53.slice"] == runtime["resources"][
        "aggregate"
    ]
    children = [
        fake_effective_readback["atius-rustdesk-server-hbbs.service"],
        fake_effective_readback["atius-rustdesk-server-hbbr.service"],
    ]
    assert sum(item["cpu_percent"] for item in children) == 70
    assert sum(item["memory_bytes"] for item in children) == 872415232


def _vault_fixture() -> dict[str, str]:
    values = {
        "kv/atius/rustdesk/server#private_key": base64.b64encode(b"p" * 64).decode(),
        "kv/atius/rustdesk/server#public_key": base64.b64encode(b"u" * 32).decode(),
    }
    for index, host in enumerate(
        ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv", "giovanni-w11-pc"),
        start=1,
    ):
        values[f"kv/atius/rustdesk/targets/{host}#permanent_password"] = (
            f"R{index:031d}"
        )
    return values


class _FakeServerRunner:
    def __init__(self, *, linger: bool = False) -> None:
        self.linger = linger
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self,
        argv: list[str],
        request: bytes | None = None,
        *,
        timeout: float = 30,
        stdout_limit: int = 131072,
    ) -> tuple[int, bytes, bytes]:
        del request, timeout, stdout_limit
        command = tuple(argv)
        self.calls.append(command)
        if command[:2] == ("loginctl", "show-user"):
            return 0, (b"yes\n" if self.linger else b"no\n"), b""
        if command[:2] == ("loginctl", "enable-linger"):
            self.linger = True
        elif command[:2] == ("loginctl", "disable-linger"):
            self.linger = False
        return 0, b"", b""


def _new_server_transaction(
    module: Any,
    tmp_path: Path,
    runner: _FakeServerRunner,
    *,
    fault_after: str | None = None,
    repo: Path = REPO,
) -> Any:
    home = tmp_path / "home"
    runtime = tmp_path / "run-user-1000"
    home.mkdir()
    runtime.mkdir()
    return module.Phase53ServerTransaction(
        repo=repo,
        home=home,
        runtime_dir=runtime,
        uid=1000,
        command_runner=runner,
        provider_exchange=_vault_fixture,
        tmpfs_checker=lambda path: path == runtime,
        fault_after=fault_after,
    )


def test_identity_hydration_is_tmpfs_only_and_evidence_is_value_free(
    tmp_path: Path,
) -> None:
    module = _server_installer_module()
    transaction = _new_server_transaction(module, tmp_path, _FakeServerRunner())
    transaction.snapshot_prestate()
    evidence = transaction.hydrate_identity()

    identity = transaction.runtime_dir / "atius-rustdesk/server-identity"
    assert identity.parent.parent == transaction.runtime_dir
    assert {path.name for path in identity.iterdir()} == {"id_ed25519", "id_ed25519.pub"}
    assert all((path.stat().st_mode & 0o777) == 0o600 for path in identity.iterdir())
    assert set(evidence) == {
        "provider_api",
        "reference_count",
        "public_fingerprint",
        "secret_material_present",
    }
    assert evidence["secret_material_present"] is False
    encoded = json.dumps(evidence, sort_keys=True)
    assert not any(value in encoded for value in _vault_fixture().values())
    assert not list(transaction.home.rglob("id_ed25519*"))


def test_candidate_runtime_rendering_is_owner_admission_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _server_installer_module()
    monkeypatch.delenv("ADMITTED_PHASE53", raising=False)
    assert module.select_runtime_candidate(REPO) is None
    monkeypatch.setenv("ADMITTED_PHASE53", "1")
    with pytest.raises(module.Phase53ServerBlocked, match="candidate-admission-required"):
        module.select_runtime_candidate(REPO)

    monkeypatch.delenv("ADMITTED_PHASE53", raising=False)
    transaction = _new_server_transaction(module, tmp_path, _FakeServerRunner())
    source = REPO / "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container"
    baseline = transaction._source_bytes(source)
    assert baseline == source.read_bytes()


def test_sqlite_state_digest_and_integrity_are_preserved_by_install_and_rollback(
    tmp_path: Path,
) -> None:
    module = _server_installer_module()
    runner = _FakeServerRunner()
    transaction = _new_server_transaction(module, tmp_path, runner)
    state = transaction.state_dir
    state.mkdir(parents=True)
    database = state / "db_v2.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE peer (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO peer VALUES ('fixture-peer')")

    before = module.sqlite_observation(database)
    transaction.install_closed()
    transaction.rollback_server()
    after = module.sqlite_observation(database)
    assert before == after
    assert after["integrity"] == "ok"


@pytest.mark.parametrize("fault_after", ["prestate", "identity", "units", "linger", "reload", "start"])
def test_rollback_restores_units_linger_and_preserves_client_legacy_paths(
    tmp_path: Path, fault_after: str
) -> None:
    module = _server_installer_module()
    runner = _FakeServerRunner(linger=False)
    transaction = _new_server_transaction(module, tmp_path, runner, fault_after=fault_after)
    existing_unit = transaction.quadlet_dir / "atius-rustdesk-server-hbbs.container"
    existing_unit.parent.mkdir(parents=True)
    existing_unit.write_text("preexisting-unit\n", encoding="utf-8")
    client = transaction.home / ".local/share/atius-rustdesk/client/sentinel"
    legacy = transaction.home / ".local/share/RustGuac/sentinel"
    for sentinel in (client, legacy):
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("preserve\n", encoding="utf-8")

    with pytest.raises(module.Phase53ServerBlocked, match=f"fault-injected-{fault_after}"):
        transaction.install_closed()

    assert existing_unit.read_text(encoding="utf-8") == "preexisting-unit\n"
    assert client.read_text(encoding="utf-8") == "preserve\n"
    assert legacy.read_text(encoding="utf-8") == "preserve\n"
    assert runner.linger is False
    assert not transaction.identity_dir.exists()
    assert not transaction.state_dir.exists()
    assert not transaction.log_dir.exists()
    transaction.rollback_server()
    assert runner.linger is False


def test_linger_preexisting_yes_is_never_disabled_on_rollback(tmp_path: Path) -> None:
    module = _server_installer_module()
    runner = _FakeServerRunner(linger=True)
    transaction = _new_server_transaction(module, tmp_path, runner)
    transaction.install_closed()
    transaction.rollback_server()
    assert runner.linger is True
    assert not any(call[:2] == ("loginctl", "disable-linger") for call in runner.calls)


def test_log_bound_rotation_is_actual_bounded_and_retained(tmp_path: Path) -> None:
    module = _server_installer_module()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "hbbs.log").write_bytes(b"a" * 800)
    (log_dir / "hbbr.log").write_bytes(b"b" * 800)
    stale = log_dir / "hbbs-20231231.log"
    stale.write_bytes(b"stale")

    result = module.enforce_log_bounds(
        log_dir,
        daily_bytes=1024,
        retention_days=30,
        now=module.datetime(2026, 7, 22, tzinfo=module.timezone.utc),
    )
    current = sum((log_dir / name).stat().st_size for name in ("hbbs.log", "hbbr.log"))
    today = sum(path.stat().st_size for path in log_dir.glob("*-20260722.log"))
    assert current == 0
    assert 0 < today <= 1024
    assert result["rotated_bytes"] == today
    assert result["daily_limit_bytes"] == 1024
    assert stale.exists() is False

    for path in (SERVER_LOGROTATE_SERVICE, SERVER_LOGROTATE_TIMER):
        assert path.is_file(), path
    service = SERVER_LOGROTATE_SERVICE.read_text(encoding="utf-8")
    timer = _load_unit(SERVER_LOGROTATE_TIMER)
    assert "--rotate-logs" in service
    assert "%h/.local/state/atius-rustdesk/server/logs" in service
    assert timer["Timer"]["Persistent"] == "true"
    assert timer["Install"]["WantedBy"] == "timers.target"


@pytest.mark.parametrize(
    ("artifact", "owner_plan"),
    [
        ("tools/validate_phase53.py", "53-06"),
    ],
)
@pytest.mark.xfail(strict=True, reason="implementation intentionally belongs to a later Phase 53 plan")
def test_future_implementation_symbol_is_red_only_for_owner_plan(
    artifact: str, owner_plan: str
) -> None:
    assert owner_plan in {"53-02", "53-03", "53-04", "53-05", "53-06"}
    assert (REPO / "modules/rustdesk-fleet" / artifact).is_file()


def _live_gate_module() -> Any:
    spec = importlib.util.spec_from_file_location("phase53_live_gate", LIVE_GATE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _current_preflight(module: Any, *, rollback_ready: bool = True) -> dict[str, Any]:
    bundle = module.load_current_contracts(REPO)
    return {
        "source_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip(),
        "contract_digests": bundle.digests,
        "pre_state_digest": "b" * 64,
        "rollback_ready": rollback_ready,
        "ownership_unambiguous": True,
    }


def test_live_flag_is_exact_and_required_before_first_mutation() -> None:
    module = _live_gate_module()
    gate = module.Phase53LiveGate(repo=REPO, environ={})
    with pytest.raises(module.GateBlocked, match="explicit-live-flag-required"):
        gate.require_explicit_live_flag()

    malformed = module.Phase53LiveGate(
        repo=REPO, environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "true"}
    )
    with pytest.raises(module.GateBlocked, match="explicit-live-flag-required"):
        malformed.require_explicit_live_flag()

    enabled = module.Phase53LiveGate(
        repo=REPO, environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"}
    )
    enabled.require_explicit_live_flag()


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        ({"rollback_ready": False}, "rollback-readiness-required"),
        ({"ownership_unambiguous": False}, "ownership-ambiguous"),
        ({"pre_state_digest": None}, "pre-state-required"),
        ({"contract_digests": {}}, "contract-digest-drift"),
    ],
)
def test_live_flag_preflight_and_rollback_gate_fail_closed(
    mutation: dict[str, Any], blocker: str
) -> None:
    module = _live_gate_module()
    gate = module.Phase53LiveGate(
        repo=REPO, environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"}
    )
    preflight = _current_preflight(module)
    preflight.update(mutation)
    with pytest.raises(module.GateBlocked, match=blocker):
        gate.authorize_first_mutation(preflight)


def test_stage_receipt_schema_rejects_pass_text_and_ambiguous_resume() -> None:
    module = _live_gate_module()
    gate = module.Phase53LiveGate(
        repo=REPO, environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"}
    )
    gate.authorize_first_mutation(_current_preflight(module))
    receipt = module.StageReceipt.create(
        transaction_id="c" * 32,
        stage="preflight",
        input_digest="d" * 64,
        observations={"source_head": "a" * 40},
        mutation={"performed": False, "classes": [], "cleanup_pending": []},
        rollback_state="ready",
    )
    gate.accept_receipt(receipt)
    with pytest.raises(module.GateBlocked, match="duplicate-stage-receipt"):
        gate.accept_receipt(receipt)

    stored = receipt.to_mapping()
    stored["status"] = "PASS"
    with pytest.raises(module.GateBlocked, match="receipt-status-invalid"):
        module.StageReceipt.from_mapping(stored)

    stored = receipt.to_mapping()
    stored["observations"] = {"verdict": "PASS"}
    with pytest.raises(module.GateBlocked, match="stored-verdict-forbidden"):
        module.StageReceipt.from_mapping(stored)


@pytest.mark.parametrize("boundary_index", range(1, 11))
def test_stage_receipt_fault_injection_blocks_every_skipped_boundary(
    boundary_index: int,
) -> None:
    module = _live_gate_module()
    gate = module.Phase53LiveGate(
        repo=REPO, environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"}
    )
    gate.authorize_first_mutation(_current_preflight(module))
    transaction_id = "e" * 32
    for stage in module.STAGES[:boundary_index]:
        gate.accept_receipt(
            module.StageReceipt.create(
                transaction_id=transaction_id,
                stage=stage,
                input_digest="f" * 64,
                observations={"raw_observation_digest": "0" * 64},
                mutation={"performed": False, "classes": [], "cleanup_pending": []},
                rollback_state="ready",
            )
        )
    skipped = module.STAGES[(boundary_index + 1) % len(module.STAGES)]
    blocker = "duplicate-stage-receipt" if boundary_index == 10 else "ambiguous-stage-resume"
    with pytest.raises(module.GateBlocked, match=blocker):
        gate.accept_receipt(
            module.StageReceipt.create(
                transaction_id=transaction_id,
                stage=skipped,
                input_digest="f" * 64,
                observations={"raw_observation_digest": "0" * 64},
                mutation={"performed": False, "classes": [], "cleanup_pending": []},
                rollback_state="ready",
            )
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"argv": ["tool", "--token", "fixture-secret"]},
        {"env": {"API_TOKEN": "fixture-secret"}},
        {"headers": {"Authorization": "Bearer fixture-secret"}},
        {"private_key": "fixture-secret"},
        {"payload_nonce": "fixture-secret"},
    ],
)
def test_secret_and_redact_surfaces_are_value_free(payload: dict[str, Any]) -> None:
    module = _live_gate_module()
    sanitized = module.sanitize_for_evidence(payload)
    encoded = json.dumps(sanitized, sort_keys=True)
    assert "fixture-secret" not in encoded
    assert "payload_nonce" not in encoded
    assert module.contains_secret_material(sanitized) is False


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Basic invalid"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer fixture-secret extra"},
    ],
)
def test_auth_missing_and_malformed_receive_uniform_denial(headers: dict[str, str]) -> None:
    module = _live_gate_module()
    response = module.deny_untrusted_backend_auth(headers)
    assert response == {
        "status": 401,
        "body": {"error": "unauthorized"},
        "headers": {"Cache-Control": "no-store"},
    }
    assert "fixture-secret" not in json.dumps(response, sort_keys=True)


def _healthy_ops_observations() -> dict[str, Any]:
    runtime = _load_strict(RUNTIME_CONTRACT)
    edge = _load_strict(EDGE_CONTRACT)
    digest = runtime["upstream"]["linux_arm64_digest"]
    return {
        "service_active": True,
        "image_digest": digest,
        "listeners": {
            "hbbs": {
                "tcp": [21115, 21116, 21118],
                "udp": [21116],
                "digest": digest,
            },
            "hbbr": {"tcp": [21117, 21119], "udp": [], "digest": digest},
        },
        "public_fingerprint": "sha256:" + "a" * 64,
        "expected_public_fingerprint": "sha256:" + "a" * 64,
        "edge_forwarder": {
            "host": "atius-srv-1",
            "public_ipv4": edge["public_edge"]["public_ipv4"],
            "external_tcp": edge["public_ipv4_allowed"]["tcp"],
            "external_udp": edge["public_ipv4_allowed"]["udp"],
            "native_public_closed_tcp": edge["public_forbidden"]["tcp"],
            "native_public_closed_udp": edge["public_forbidden"]["udp"],
            "backend_ipv4": edge["backend"]["private_ipv4"],
            "snat_source_ipv4": edge["backend"]["native_ingress_source_ipv4"],
        },
        "cgroups": {
            "parent_cpu_percent": 80,
            "parent_memory_bytes": 1073741824,
            "ops_cpu_percent": 10,
            "ops_memory_bytes": 201326592,
        },
        "disk_free_bytes": runtime["logs"]["reserve_bytes"],
        "log_growth_bytes": runtime["logs"]["daily_bytes"],
        "restart_count": 3,
        "restart_limit": 3,
        "cpu_percent": 7,
        "memory_bytes": 104857600,
        "disk_bytes": 536870912,
        "direct_bytes": 1024,
        "relay_bytes": 2048,
        "failures": 1,
    }


def test_ops_api_endpoints_auth_redaction_and_unknown_route_denial() -> None:
    module = _ops_api_module()
    observations = _healthy_ops_observations()
    token = "fixture-runtime-token"
    authorized = {"Authorization": f"Bearer {token}"}

    responses = {
        path: module.handle_request(
            "GET", path, authorized, observations=observations, expected_token=token
        )
        for path in (
            "/v1/health",
            "/v1/readiness",
            "/v1/status",
            "/v1/metrics/summary",
        )
    }
    assert all(response["status"] == 200 for response in responses.values())
    assert responses["/v1/health"]["body"] == {
        "schema_version": 1,
        "service": "atius-rustdesk-ops",
        "healthy": True,
    }
    assert responses["/v1/readiness"]["body"]["ready"] is True
    assert responses["/v1/status"]["body"] == {
        "schema_version": 1,
        "service": "atius-rustdesk-ops",
        "primary_host": "horistic-srv",
        "public_edge": observations["edge_forwarder"],
        "backend_listeners": observations["listeners"],
        "service_active": True,
        "image_digest": observations["image_digest"],
        "public_fingerprint": observations["public_fingerprint"],
    }

    denials = [
        module.handle_request(
            method,
            path,
            headers,
            observations=observations,
            expected_token=token,
        )
        for method, path, headers in (
            ("GET", "/v1/health", {}),
            ("GET", "/v1/health", {"Authorization": "Bearer wrong"}),
            ("POST", "/v1/health", authorized),
            ("GET", "/v1/private", authorized),
        )
    ]
    assert denials[0] == denials[1] == {
        "status": 401,
        "headers": {"Cache-Control": "no-store", "Content-Type": "application/json"},
        "body": {"error": "unauthorized"},
    }
    assert denials[2] == denials[3] == {
        "status": 404,
        "headers": {"Cache-Control": "no-store", "Content-Type": "application/json"},
        "body": {"error": "not_found"},
    }
    encoded = json.dumps({"responses": responses, "denials": denials}, sort_keys=True)
    assert token not in encoded
    assert "Authorization" not in encoded


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        ({"image_digest": "sha256:" + "0" * 64}, "immutable-image-digest"),
        ({"listeners": {}}, "exact-listener-ownership"),
        ({"public_fingerprint": "sha256:" + "b" * 64}, "public-fingerprint-continuity"),
        ({"edge_forwarder": {"external_tcp": [21114]}}, "effective-edge-policy"),
        ({"cgroups": {"ops_cpu_percent": 11}}, "resource-ceilings"),
        ({"log_growth_bytes": 134217729}, "disk-and-log-bounds"),
        ({"restart_count": 4}, "bounded-restart-counters"),
    ],
)
def test_ops_api_readiness_derives_current_inputs_and_fails_on_drift(
    mutation: dict[str, Any], failed_check: str
) -> None:
    module = _ops_api_module()
    observations = _healthy_ops_observations()
    baseline = module.derive_readiness(observations)
    assert baseline["ready"] is True
    assert set(baseline["checks"]) == set(
        _load_strict(OPS_API_CONTRACT)["readiness_inputs"]
    )

    drifted = copy.deepcopy(observations)
    drifted.update(mutation)
    result = module.derive_readiness(drifted)
    assert result["ready"] is False
    assert result["checks"][failed_check] is False


def test_ops_api_successor_digest_requires_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _ops_api_module()
    monkeypatch.delenv("ADMITTED_PHASE53", raising=False)
    assert module.select_runtime_digest(environ={}) == module.EXPECTED_DIGEST
    monkeypatch.setenv("ADMITTED_PHASE53", "1")
    with pytest.raises(module.OpsApiBlocked, match="candidate-admission-required"):
        module.select_runtime_digest(repo=REPO)


def test_ops_api_metrics_are_allowlisted_observational_and_secret_free() -> None:
    module = _ops_api_module()
    observations = _healthy_ops_observations()
    observations.update(
        {
            "Authorization": "Bearer fixture-secret",
            "client_id": "forbidden-client-id",
            "private_key": "forbidden-private-key",
        }
    )
    metrics = module.collect_metric_summary(observations)
    assert set(metrics) == {
        "listeners",
        "restarts",
        "cpu_percent",
        "memory_bytes",
        "disk_bytes",
        "log_growth_bytes",
        "direct_bytes",
        "relay_bytes",
        "failures",
        "transport_semantics",
        "session_transport_asserted",
    }
    assert metrics["transport_semantics"] == "observational-only"
    assert metrics["session_transport_asserted"] is False
    encoded = json.dumps(metrics, sort_keys=True)
    assert "fixture-secret" not in encoded
    assert "client" not in encoded.lower()
    assert "private" not in encoded.lower()


def test_ops_api_service_is_private_hardened_and_inside_parent_budget() -> None:
    assert OPS_API_SERVICE.is_file(), OPS_API_SERVICE
    unit = _load_unit(OPS_API_SERVICE)
    service = unit["Service"]
    encoded = OPS_API_SERVICE.read_text(encoding="utf-8")
    assert service["Slice"] == "atius-rustdesk-phase53.slice"
    assert service["CPUQuota"] == "10%"
    assert service["MemoryMax"] == "192M"
    assert service["MemorySwapMax"] == "0"
    assert service["NoNewPrivileges"] == "true"
    assert "--listen 127.0.0.1" in service["ExecStart"]
    assert "--port 32113" in service["ExecStart"]
    assert "--token-file %d/ops-api-token" in service["ExecStart"]
    assert "LoadCredential=ops-api-token:%t/atius-rustdesk/ops-api-token" in encoded
    assert "21114" not in encoded
    assert "0.0.0.0" not in encoded
    assert "API Server" not in encoded


def test_apache_vhost_is_https_only_private_proxy_with_sanitized_logs() -> None:
    assert OPS_API_VHOST.is_file(), OPS_API_VHOST
    encoded = OPS_API_VHOST.read_text(encoding="utf-8")
    assert "Managed-By: omni-srv-admin/rustdesk-fleet/phase53" in encoded
    assert "<VirtualHost *:443>" in encoded
    assert "<VirtualHost *:80>" not in encoded
    assert "ServerName rustdesk-ops.atius.com.br" in encoded
    assert "ProxyPass / http://127.0.0.1:32113/" in encoded
    assert "ProxyPassReverse / http://127.0.0.1:32113/" in encoded
    assert "%{Authorization}i" not in encoded
    assert "%q" not in encoded
    assert "%U" in encoded
    assert "21114" not in encoded
    assert "API Server" not in encoded


@pytest.mark.parametrize("failure", ["configtest", "reload", "regression"])
def test_apache_transaction_restores_exact_prestate_on_every_failure(
    tmp_path: Path, failure: str
) -> None:
    module = _ops_api_module()
    destination = tmp_path / "sites-available/rustdesk-ops.conf"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"preexisting-vhost\n")
    destination.chmod(0o640)
    calls: list[tuple[str, ...]] = []

    def runner(argv: list[str]) -> tuple[int, bytes, bytes]:
        calls.append(tuple(argv))
        if failure == "configtest" and tuple(argv) == ("apachectl", "configtest"):
            return 1, b"", b"syntax error"
        if failure == "reload" and tuple(argv) == ("systemctl", "reload", "apache2"):
            return 1, b"", b"reload failed"
        return 0, b"", b""

    transaction = module.ApacheVhostTransaction(
        candidate=OPS_API_VHOST,
        destination=destination,
        command_runner=runner,
        existing_vhost_probe=lambda: {"legacy": failure != "regression"},
    )
    with pytest.raises(module.OpsApiBlocked):
        transaction.apply_candidate()

    assert destination.read_bytes() == b"preexisting-vhost\n"
    assert destination.stat().st_mode & 0o777 == 0o640
    assert calls[0] == ("apachectl", "configtest")
    transaction.rollback()
    assert destination.read_bytes() == b"preexisting-vhost\n"


def test_unflagged_cli_refuses_without_runtime_evidence(tmp_path: Path) -> None:
    env = {"PATH": os.environ["PATH"]}
    completed = subprocess.run(
        [sys.executable, str(LIVE_GATE_PATH), "--repo", str(REPO), "--evidence-dir", str(tmp_path)],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload == {
        "blocker": "explicit-live-flag-required",
        "mutation_performed": False,
        "secret_material_present": False,
        "status": "BLOCKED",
    }
    assert list(tmp_path.iterdir()) == []


def test_explicit_cli_uses_requested_evidence_dir_and_stays_fail_closed(
    tmp_path: Path,
) -> None:
    env = {
        "PATH": os.environ["PATH"],
        "ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(LIVE_GATE_PATH),
            "--repo",
            str(REPO),
            "--evidence-dir",
            str(tmp_path),
            "--stage",
            "edge-probes",
        ],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload == {
        "blocker": "preflight-input-required",
        "mutation_performed": False,
        "secret_material_present": False,
        "status": "BLOCKED",
    }
    assert list(tmp_path.iterdir()) == []


def test_cli_checks_admission_and_provider_before_opening_journal(tmp_path: Path) -> None:
    module = _live_gate_module()
    preflight = _current_preflight(module)
    preflight.update(
        {
            "candidate_admission_performed": True,
            "candidate_contract_digest": preflight["contract_digests"][
                "phase53-runtime-candidate.json"
            ],
            "provider_manifest_digest": preflight["contract_digests"][
                "phase53-provider-manifest.json"
            ],
        }
    )
    (tmp_path / "preflight.json").write_text(json.dumps(preflight), encoding="utf-8")
    env = {
        "PATH": os.environ["PATH"],
        "ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1",
        "ADMITTED_PHASE53": "1",
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(LIVE_GATE_PATH),
            "--repo",
            str(REPO),
            "--evidence-dir",
            str(tmp_path),
            "--stage",
            "edge-probes",
        ],
        cwd=REPO,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "candidate-evidence-not-admitted"
    assert not (tmp_path / "phase53-journal.json").exists()


def test_edge_probes_dispatches_ordered_injected_adapters() -> None:
    module = _live_gate_module()
    transaction_id = "1" * 32
    calls: list[str] = []
    adapters: dict[str, Any] = {}

    for stage in module.EDGE_PROBES_SEQUENCE:
        def adapter(stage: str = stage) -> Any:
            calls.append(stage)
            return module.StageReceipt.create(
                transaction_id=transaction_id,
                stage=stage,
                input_digest="2" * 64,
                observations={"raw_observation_digest": "3" * 64},
                mutation={
                    "performed": False,
                    "classes": [],
                    "cleanup_pending": [],
                },
                rollback_state="ready",
            )

        adapters[stage] = adapter

    gate = module.Phase53LiveGate(
        repo=REPO,
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"},
        stage_adapters=adapters,
    )
    gate.authorize_first_mutation(_current_preflight(module))

    result = gate.run_stage("edge-probes")

    assert calls == list(module.EDGE_PROBES_SEQUENCE)
    assert result["stage"] == "edge-probes"
    assert result["receipt_count"] == len(module.EDGE_PROBES_SEQUENCE)
    assert [receipt["stage"] for receipt in result["receipts"]] == calls
    assert result["secret_material_present"] is False


def test_stage_dispatch_requires_explicit_adapter() -> None:
    module = _live_gate_module()
    gate = module.Phase53LiveGate(
        repo=REPO,
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"},
    )
    gate.authorize_first_mutation(_current_preflight(module))

    with pytest.raises(module.GateBlocked, match="stage-adapter-required:preflight"):
        gate.run_stage("preflight")


def test_stage_failure_requests_containment_and_writes_rollback_journal(tmp_path: Path) -> None:
    module = _live_gate_module()
    calls: list[str] = []
    transaction_id = "9" * 32

    def preflight() -> Any:
        return module.StageReceipt.create(
            transaction_id=transaction_id,
            stage="preflight",
            input_digest="a" * 64,
            observations={"raw_observation_digest": "b" * 64},
            mutation={"performed": False, "classes": [], "cleanup_pending": []},
            rollback_state="ready",
        )

    def runtime() -> Any:
        raise RuntimeError("provider failure")

    def contain_on_failure() -> dict[str, Any]:
        calls.append("contain")
        return {"status": "ignored", "token": "never-recorded"}

    gate = module.Phase53LiveGate(
        repo=REPO,
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"},
        stage_adapters={
            "preflight": preflight,
            "runtime": runtime,
            "contain_on_failure": contain_on_failure,
        },
    )
    gate.authorize_first_mutation(_current_preflight(module))
    gate.journal = module.ValueFreeJournal.open(tmp_path / "journal.json", transaction_id)
    gate.run_stage("preflight")

    with pytest.raises(module.GateBlocked, match="stage-adapter-failed:runtime"):
        gate.run_stage("runtime")

    assert calls == ["contain"]
    payload = _load_strict(tmp_path / "journal.json")
    assert payload["last_stage"] == "rollback"
    serialized = json.dumps(payload)
    assert "provider failure" not in serialized
    assert "never-recorded" not in serialized


def _live_adapters_module() -> Any:
    path = REPO / "modules/rustdesk-fleet/tools/phase53-live-adapters.py"
    spec = importlib.util.spec_from_file_location("phase53_live_adapters_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_adapters_module() -> Any:
    path = REPO / "modules/rustdesk-fleet/tools/phase53_production_adapters.py"
    spec = importlib.util.spec_from_file_location("phase53_production_adapters_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_adapter_factory_requires_admitted_candidate(tmp_path: Path) -> None:
    module = _live_adapters_module()
    journal = module.ValueFreeJournal.open(tmp_path / "journal.json", "a" * 32)
    context = module.AdapterContext(
        repo=REPO,
        evidence_dir=REPO / "modules/rustdesk-fleet/evidence/phase53",
        preflight={"candidate_admission_performed": False, "rollback_ready": True},
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"},
        transaction_id="a" * 32,
        journal=journal,
    )
    with pytest.raises(module.AdapterBlocked, match="candidate-not-admitted"):
        module.build_live_adapters(context, injected={stage: lambda: {} for stage in module.EDGE_SEQUENCE})

    admitted = module.AdapterContext(
        repo=REPO,
        evidence_dir=REPO / "modules/rustdesk-fleet/evidence/phase53",
        preflight={"candidate_admission_performed": True, "rollback_ready": True},
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"},
        transaction_id="a" * 32,
        journal=journal,
    )
    with pytest.raises(module.AdapterBlocked, match="live-backend-containment-missing"):
        module.build_live_adapters(admitted, injected={stage: lambda: {} for stage in module.EDGE_SEQUENCE})


def test_production_adapter_factory_requires_current_candidate_and_provider_digests(tmp_path: Path) -> None:
    module = _live_adapters_module()
    journal = module.ValueFreeJournal.open(tmp_path / "journal.json", "c" * 32)
    context = module.AdapterContext(
        repo=REPO,
        evidence_dir=REPO / "modules/rustdesk-fleet/evidence/phase53",
        preflight={"candidate_admission_performed": False, "rollback_ready": True},
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1", "ADMITTED_PHASE53": "1"},
        transaction_id="c" * 32,
        journal=None,
    )
    with pytest.raises(module.AdapterBlocked, match="candidate-not-admitted"):
        module.build_production_adapters(context)

    admitted = copy.deepcopy(context.preflight)
    admitted["candidate_admission_performed"] = True
    context = module.AdapterContext(
        repo=REPO,
        evidence_dir=context.evidence_dir,
        preflight=admitted,
        environ=context.environ,
        transaction_id=context.transaction_id,
        journal=journal,
    )
    with pytest.raises(module.AdapterBlocked, match="candidate-evidence-not-admitted"):
        module.build_production_adapters(context)


def test_production_bundle_factory_is_not_constructed_before_authority(tmp_path: Path) -> None:
    module = _live_adapters_module()
    calls: list[str] = []
    context = module.AdapterContext(
        repo=REPO,
        evidence_dir=REPO / "modules/rustdesk-fleet/evidence/phase53",
        preflight={"candidate_admission_performed": False, "rollback_ready": True},
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1", "ADMITTED_PHASE53": "1"},
        transaction_id="4" * 32,
        journal=None,
    )

    def factory() -> Any:
        calls.append("constructed")
        return object()

    with pytest.raises(module.AdapterBlocked, match="candidate-not-admitted"):
        module.build_production_adapters(context, provider_bundle_factory=factory)
    assert calls == []


def test_production_provider_seam_is_explicit_and_route_policy_is_fail_closed() -> None:
    module = _production_adapters_module()
    manifest = _load_strict(PROVIDER_CONTRACT)
    module.validate_provider_manifest(manifest)
    assert module.select_ssh_route(0) == "private"
    assert module.select_ssh_route(255) == "public-native-fallback"
    with pytest.raises(module.AdapterBlocked, match="ssh-private-probe-failed"):
        module.select_ssh_route(1)
    with pytest.raises(module.AdapterBlocked, match="provider-shell-eval-forbidden"):
        module.validate_command_argv(["ssh", "-o", "ProxyCommand=$(id)"])


def test_production_provider_bundle_requires_authority_before_callbacks() -> None:
    module = _production_adapters_module()
    manifest = _load_strict(PROVIDER_CONTRACT)
    calls: list[str] = []

    def callback() -> dict[str, Any]:
        calls.append("provider")
        return {"mutation_performed": False, "mutation_classes": [], "cleanup_pending": []}

    stages = {stage: callback for stage in module.EDGE_SEQUENCE}
    bundle = module.ProviderBundle(stages=stages, containment=callback, transaction_id="d" * 32)
    with pytest.raises(module.AdapterBlocked, match="provider-authority-required"):
        module.bind_provider_bundle(manifest, bundle, authorized=False)
    assert calls == []

    backend = module.bind_provider_bundle(manifest, bundle, authorized=True)
    receipt = backend.stages["preflight"]()
    assert receipt["stage"] == "preflight"
    assert receipt["secret_material_present"] is False
    assert receipt["mutation"] == {
        "performed": False,
        "classes": [],
        "cleanup_pending": [],
    }
    assert calls == ["provider"]


def test_production_provider_bundle_rejects_transaction_drift_before_callbacks() -> None:
    module = _production_adapters_module()
    manifest = _load_strict(PROVIDER_CONTRACT)
    calls: list[str] = []

    def callback() -> dict[str, Any]:
        calls.append("provider")
        return {"mutation_performed": False, "mutation_classes": [], "cleanup_pending": []}

    bundle = module.ProviderBundle(
        stages={stage: callback for stage in module.EDGE_SEQUENCE},
        containment=callback,
        transaction_id="f" * 32,
    )
    with pytest.raises(module.AdapterBlocked, match="provider-transaction-drift"):
        module.bind_provider_bundle(
            manifest, bundle, authorized=True, expected_transaction_id="0" * 32
        )
    assert calls == []


def test_production_provider_bundle_validates_all_callbacks_before_binding() -> None:
    module = _production_adapters_module()
    manifest = _load_strict(PROVIDER_CONTRACT)
    callback = lambda: {
        "mutation_performed": False,
        "mutation_classes": [],
        "cleanup_pending": [],
    }
    stages = {stage: callback for stage in module.EDGE_SEQUENCE}
    stages["runtime"] = object()
    bundle = module.ProviderBundle(
        stages=stages, containment=callback, transaction_id="1" * 32
    )
    with pytest.raises(module.AdapterBlocked, match="provider-callback-invalid:runtime"):
        module.bind_provider_bundle(manifest, bundle, authorized=True)


def test_runtime_provider_builds_explicit_bundle_without_invoking_callbacks() -> None:
    module = _production_adapters_module()
    calls: list[str] = []

    def callback(name: str) -> Any:
        def run() -> dict[str, Any]:
            calls.append(name)
            return {"mutation_performed": False, "mutation_classes": [], "cleanup_pending": []}

        return run

    provider = module.RuntimeProvider(
        transaction_id="a" * 32,
        snapshot_prestate=callback("prestate"),
        install_closed=callback("install"),
        rollback_server=callback("rollback"),
        edge_stages={stage: callback(stage) for stage in module.EDGE_SEQUENCE if stage != "runtime"},
        containment=callback("containment"),
    )
    bundle = provider.to_bundle()
    assert isinstance(bundle, module.ProviderBundle)
    assert calls == []


def test_runtime_provider_orders_prestate_before_install_and_is_value_free() -> None:
    module = _production_adapters_module()
    calls: list[str] = []

    def prestate() -> dict[str, Any]:
        calls.append("prestate")
        return {"pre_state_digest": "a" * 64}

    def install() -> dict[str, Any]:
        calls.append("install")
        return {"managed_units": 3}

    provider = module.RuntimeProvider(
        transaction_id="b" * 32,
        snapshot_prestate=prestate,
        install_closed=install,
        rollback_server=lambda: {"rollback": "ready"},
        edge_stages={
            stage: lambda: {"mutation_performed": False, "mutation_classes": [], "cleanup_pending": []}
            for stage in module.EDGE_SEQUENCE
            if stage != "runtime"
        },
        containment=lambda: {"contained": True},
    )
    bundle = provider.to_bundle()
    backend = module.bind_provider_bundle(
        _load_strict(PROVIDER_CONTRACT), bundle, authorized=True, expected_transaction_id="b" * 32
    )
    receipt = backend.stages["runtime"]()
    assert calls == ["prestate", "install"]
    serialized = json.dumps(receipt, sort_keys=True)
    assert "argv" not in serialized
    assert "stdout" not in serialized
    assert "fixture-secret" not in serialized.lower()
    assert receipt["mutation"]["performed"] is True


def test_runtime_provider_rolls_back_on_install_fault_without_leaking_error() -> None:
    module = _production_adapters_module()
    calls: list[str] = []

    def install() -> dict[str, Any]:
        calls.append("install")
        raise RuntimeError("fixture secret and argv must not escape")

    def rollback() -> dict[str, Any]:
        calls.append("rollback")
        return {"state": "restored"}

    provider = module.RuntimeProvider(
        transaction_id="c" * 32,
        snapshot_prestate=lambda: {"pre_state_digest": "d" * 64},
        install_closed=install,
        rollback_server=rollback,
        edge_stages={
            stage: lambda: {"mutation_performed": False, "mutation_classes": [], "cleanup_pending": []}
            for stage in module.EDGE_SEQUENCE
            if stage != "runtime"
        },
        containment=lambda: {"contained": True},
    )
    backend = module.bind_provider_bundle(
        _load_strict(PROVIDER_CONTRACT), provider.to_bundle(), authorized=True
    )
    with pytest.raises(module.AdapterBlocked, match="runtime-provider-install-failed") as error:
        backend.stages["runtime"]()
    assert calls == ["install", "rollback"]
    assert "fixture secret" not in str(error.value)


def test_runtime_provider_rolls_back_when_install_output_contains_secret() -> None:
    module = _production_adapters_module()
    calls: list[str] = []

    def install() -> dict[str, Any]:
        calls.append("install")
        return {"password": "fixture-secret"}

    def rollback() -> dict[str, Any]:
        calls.append("rollback")
        return {"state": "restored"}

    provider = module.RuntimeProvider(
        transaction_id="d" * 32,
        snapshot_prestate=lambda: {"pre_state_digest": "e" * 64},
        install_closed=install,
        rollback_server=rollback,
        edge_stages={
            stage: lambda: {"mutation_performed": False, "mutation_classes": [], "cleanup_pending": []}
            for stage in module.EDGE_SEQUENCE
            if stage != "runtime"
        },
        containment=lambda: {"contained": True},
    )
    backend = module.bind_provider_bundle(
        _load_strict(PROVIDER_CONTRACT), provider.to_bundle(), authorized=True
    )
    with pytest.raises(module.AdapterBlocked, match="runtime-provider-install-output-invalid"):
        backend.stages["runtime"]()
    assert calls == ["install", "rollback"]


def test_live_gate_resumes_only_after_completed_journal_prefix(tmp_path: Path) -> None:
    module = _live_gate_module()
    transaction_id = "2" * 32
    journal = module.ValueFreeJournal.open(tmp_path / "journal.json", transaction_id)
    journal.append("preflight", {"metadata_digest": "a" * 64})

    calls: list[str] = []

    def runtime() -> Any:
        calls.append("runtime")
        return module.StageReceipt.create(
            transaction_id=transaction_id,
            stage="runtime",
            input_digest="b" * 64,
            observations={"raw_observation_digest": "c" * 64},
            mutation={"performed": False, "classes": [], "cleanup_pending": []},
            rollback_state="ready",
        )

    gate = module.Phase53LiveGate(
        repo=REPO,
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"},
        stage_adapters={"runtime": runtime},
    )
    gate.authorize_first_mutation(_current_preflight(module))
    gate.hydrate_journal(module.ValueFreeJournal.open(tmp_path / "journal.json", transaction_id))
    with pytest.raises(module.GateBlocked, match="journal-stage-already-complete"):
        gate.run_stage("preflight")
    gate.run_stage("runtime")
    assert calls == ["runtime"]


def test_live_gate_rejects_terminal_rollback_journal(tmp_path: Path) -> None:
    module = _live_gate_module()
    transaction_id = "3" * 32
    journal = module.ValueFreeJournal.open(tmp_path / "journal.json", transaction_id)
    journal.append("rollback", {"containment_requested": True, "blocker_digest": "a" * 64})
    gate = module.Phase53LiveGate(
        repo=REPO,
        environ={"ATIUS_RUN_RUSTDESK_PHASE53_LIVE": "1"},
    )
    with pytest.raises(module.GateBlocked, match="journal-terminal-rollback"):
        gate.hydrate_journal(module.ValueFreeJournal.open(tmp_path / "journal.json", transaction_id))


def test_production_provider_bundle_rejects_secret_output_before_receipt() -> None:
    module = _production_adapters_module()
    manifest = _load_strict(PROVIDER_CONTRACT)

    def secret_callback() -> dict[str, Any]:
        return {
            "mutation_performed": False,
            "mutation_classes": [],
            "cleanup_pending": [],
            "password": "fixture-secret",
        }

    stages = {stage: secret_callback for stage in module.EDGE_SEQUENCE}
    bundle = module.ProviderBundle(
        stages=stages, containment=secret_callback, transaction_id="e" * 32
    )
    backend = module.bind_provider_bundle(manifest, bundle, authorized=True)
    with pytest.raises(module.AdapterBlocked, match="provider-secret-output:runtime"):
        backend.stages["runtime"]()


def test_value_free_journal_redacts_and_rejects_verdicts(tmp_path: Path) -> None:
    module = _live_adapters_module()
    journal = module.ValueFreeJournal.open(tmp_path / "journal.json", "b" * 32)
    journal.append("preflight", {"observations": {"token": "[REDACTED]", "digest": "c" * 64}})
    payload = _load_strict(tmp_path / "journal.json")
    assert payload["secret_material_present"] is False
    assert payload["last_stage"] == "preflight"
    assert "fixture-secret" not in json.dumps(payload).lower()
    with pytest.raises(module.AdapterBlocked, match="journal-receipt-invalid"):
        journal.append("runtime", {"status": "PASS"})


def _oci_rule(
    protocol: str,
    first: int,
    last: int,
    *,
    family: str = "ipv4",
    source: str | None = None,
) -> dict[str, Any]:
    return {
        "family": family,
        "protocol": protocol,
        "source": source or ("0.0.0.0/0" if family == "ipv4" else "::/0"),
        "source_type": "CIDR_BLOCK",
        "stateless": False,
        "port_min": first,
        "port_max": last,
    }


def _allowed_oci_pages() -> dict[str, Any]:
    return {
        "pagination_complete": True,
        "pages": [
            {
                "page_token": "first",
                "next_page": "second",
                "security_lists": [
                    {
                        "id": "sl-primary",
                        "ingress_rules": [_oci_rule("tcp", 34099, 34101)],
                    }
                ],
                "network_security_groups": [],
                "attachments": [
                    {
                        "id": "vnic-primary",
                        "security_list_ids": ["sl-primary"],
                        "nsg_ids": ["nsg-edge"],
                    }
                ],
            },
            {
                "page_token": "second",
                "next_page": None,
                "security_lists": [],
                "network_security_groups": [
                    {
                        "id": "nsg-edge",
                        "ingress_rules": [_oci_rule("udp", 34100, 34100)],
                    }
                ],
                "attachments": [],
            },
        ],
    }


def _phase53_edge_preflight() -> dict[str, Any]:
    digests = {
        "phase53-edge.json": "a" * 64,
        "phase53-runtime.json": "b" * 64,
    }
    return {
        "phase52_pass_count": 11,
        "phase52_check_count": 11,
        "selected_primary": "horistic-srv",
        "address_consensus": {
            "oci-edge-vnic-public-ipv4": "203.0.113.8",
            "edge-vnic-public-ipv4": "203.0.113.8",
            "reserved-public-ipv4": "203.0.113.8",
        },
        "address_observations": [
            {
                "source": "oci-edge-vnic-public-ipv4",
                "ipv4": "203.0.113.8",
                "observed_at": "2026-07-23T02:00:00Z",
                "topology_id": "vnic:atius-srv-1-public",
                "record_types": ["A"],
            },
            {
                "source": "edge-vnic-public-ipv4",
                "ipv4": "203.0.113.8",
                "observed_at": "2026-07-23T02:00:00Z",
                "topology_id": "host:atius-srv-1:10.0.0.238",
                "record_types": ["A"],
            },
            {
                "source": "reserved-public-ipv4",
                "ipv4": "203.0.113.8",
                "observed_at": "2026-07-23T02:00:00Z",
                "topology_id": "reservation:137.131.140.20",
                "record_types": ["A"],
            },
        ],
        "address_observed_at": "2026-07-23T02:00:00Z",
        "authorization_time": "2026-07-23T02:01:00Z",
        "source_head": "c" * 40,
        "current_source_head": "c" * 40,
        "contract_digests": digests,
        "current_contract_digests": copy.deepcopy(digests),
        "backups_retained": True,
        "dns_closed": True,
        "native_ingress_closed": True,
        "legacy_smokes": True,
        "rollback_ready": True,
        "native_record_set": [],
    }


class _FakeEdgeBackend:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "nft": {"present": False, "candidate": None, "semantics": None},
            "oci": _allowed_oci_pages(),
            "k3s": "k3s-byte-sentinel",
        }
        self.revision = 1
        self.calls: list[str] = []
        self.mutation_count = 0
        self.contained = False
        self.force_stale_revision = False
        self.force_concurrent_drift = False
        self.raise_after_nft_write = False
        self.raise_after_oci_write = False
        self.raise_on_restore = False
        self.raise_on_contain = False
        self.race_before_restore = False

    def snapshot(self) -> dict[str, Any]:
        self.calls.append("snapshot")
        return {
            "revision": str(self.revision),
            "state": copy.deepcopy(self.state),
        }

    def current_revision(self) -> str:
        if self.force_stale_revision:
            return str(self.revision + 1)
        return str(self.revision)

    def syntax_check_nft(self, candidate: str) -> None:
        assert "table inet atius_rustdesk_phase53" in candidate
        self.calls.append("nft-check")

    def apply_nft(self, candidate: str, semantics: dict[str, Any]) -> None:
        self.calls.append("nft-apply")
        self.state["nft"] = {
            "present": True,
            "candidate": candidate,
            "semantics": copy.deepcopy(semantics),
        }
        self.revision += 1
        self.mutation_count += 1
        if self.raise_after_nft_write:
            raise RuntimeError("backend-nft-partial-write")

    def apply_oci(self, candidate: dict[str, Any]) -> None:
        self.calls.append("oci-apply")
        self.state["oci"] = copy.deepcopy(candidate)
        self.revision += 1
        self.mutation_count += 1
        if self.raise_after_oci_write:
            raise RuntimeError("backend-oci-partial-write")

    def observe(self) -> dict[str, Any]:
        if self.force_concurrent_drift:
            self.state["oci"]["pages"][0]["security_lists"][0]["ingress_rules"].append(
                _oci_rule("tcp", 21114, 21114)
            )
            self.revision += 1
            self.force_concurrent_drift = False
        return {"revision": str(self.revision), "state": copy.deepcopy(self.state)}

    def restore_if_current(
        self, snapshot: dict[str, Any], *, expected_revision: str
    ) -> None:
        self.calls.append("restore-if-current")
        if self.race_before_restore:
            self.revision += 1
        if str(self.revision) != str(expected_revision):
            raise RuntimeError("backend-restore-cas-conflict")
        if self.raise_on_restore:
            raise RuntimeError("backend-restore-failed")
        self.state = copy.deepcopy(snapshot["state"])
        self.revision += 1

    def contain_owned_ingress(self) -> None:
        self.calls.append("contain")
        if self.raise_on_contain:
            raise RuntimeError("backend-containment-failed")
        self.contained = True


def _rendered_nft_candidate(module: Any) -> str:
    return module.render_nft_candidate(_nft_template(), public_interface="ens3")


def _nft_template() -> str:
    return EDGE_NFT_POLICY.read_text(encoding="utf-8")


class _FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _edge_transaction(module: Any, backend: Any, **kwargs: Any) -> Any:
    kwargs.setdefault(
        "clock",
        _FakeClock(datetime(2026, 7, 23, 2, 1, 30, tzinfo=timezone.utc)),
    )
    kwargs.setdefault("runtime_digest", _phase53_digest())
    kwargs.setdefault(
        "address_source_policy",
        {
            "oci-edge-vnic-public-ipv4": "vnic:atius-srv-1-public",
            "edge-vnic-public-ipv4": "host:atius-srv-1:10.0.0.238",
            "reserved-public-ipv4": "reservation:137.131.140.20",
        },
    )
    return module.EdgeTransaction(
        contract=_load_strict(EDGE_CONTRACT),
        backend=backend,
        nft_template=_nft_template(),
        **kwargs,
    )


def test_oci_pagination_audits_full_security_list_and_nsg_union() -> None:
    module = _edge_applier_module()
    result = module.audit_effective_oci_ingress(
        _allowed_oci_pages(), _load_strict(EDGE_CONTRACT)
    )
    assert result == {
        "pagination_complete": True,
        "security_list_ids": ["sl-primary"],
        "network_security_group_ids": ["nsg-edge"],
        "attachment_ids": ["vnic-primary"],
        "ipv4_tcp": [34099, 34100, 34101],
        "ipv4_udp": [34100],
        "ipv6": [],
    }


@pytest.mark.parametrize(
    ("mutator", "blocker"),
    [
        (
            lambda pages: pages["pages"][0]["security_lists"][0]["ingress_rules"].append(
                _oci_rule("tcp", 21114, 21119)
            ),
            "oci-effective-ingress-forbidden",
        ),
        (
            lambda pages: pages["pages"][1]["network_security_groups"][0][
                "ingress_rules"
            ].append(_oci_rule("all", 0, 65535)),
            "oci-effective-ingress-broad",
        ),
        (
            lambda pages: pages["pages"][1]["network_security_groups"][0][
                "ingress_rules"
            ].append(_oci_rule("tcp", 21115, 21117, family="ipv6")),
            "oci-effective-ingress-ipv6",
        ),
    ],
)
def test_oci_union_broad_forbidden_and_ipv6_rules_fail_closed(
    mutator: Any, blocker: str
) -> None:
    module = _edge_applier_module()
    pages = _allowed_oci_pages()
    mutator(pages)
    with pytest.raises(module.EdgeBlocked, match=blocker):
        module.audit_effective_oci_ingress(pages, _load_strict(EDGE_CONTRACT))


@pytest.mark.parametrize(
    ("mutator", "blocker"),
    [
        (lambda pages: pages.update({"pagination_complete": False}), "oci-pagination-incomplete"),
        (
            lambda pages: pages["pages"][1].update({"page_token": "first"}),
            "oci-pagination-token-repeated",
        ),
        (
            lambda pages: pages["pages"][1].update(
                {"network_security_groups": []}
            ),
            "oci-attachment-unexpanded",
        ),
    ],
)
def test_oci_pagination_and_attachment_completeness_are_mandatory(
    mutator: Any, blocker: str
) -> None:
    module = _edge_applier_module()
    pages = _allowed_oci_pages()
    mutator(pages)
    with pytest.raises(module.EdgeBlocked, match=blocker):
        module.audit_effective_oci_ingress(pages, _load_strict(EDGE_CONTRACT))


def test_listener_audit_rejects_extra_owner_and_digest_drift() -> None:
    module = _edge_applier_module()
    digest = _load_strict(RUNTIME_CONTRACT)["upstream"]["linux_arm64_digest"]
    exact = [
        {"owner": "hbbs", "protocol": "tcp", "port": port, "digest": digest}
        for port in (21115, 21116, 21118)
    ] + [
        {"owner": "hbbs", "protocol": "udp", "port": 21116, "digest": digest},
        {"owner": "hbbr", "protocol": "tcp", "port": 21117, "digest": digest},
        {"owner": "hbbr", "protocol": "tcp", "port": 21119, "digest": digest},
    ]
    assert module.audit_runtime_listeners(exact, digest)["listener_count"] == 6

    for drifted in (
        exact + [{"owner": "hbbs", "protocol": "tcp", "port": 21114, "digest": digest}],
        [dict(exact[0], owner="foreign")] + exact[1:],
        [dict(exact[0], digest="sha256:" + "0" * 64)] + exact[1:],
    ):
        with pytest.raises(module.EdgeBlocked, match="listener-effective-drift"):
            module.audit_runtime_listeners(drifted, digest)


def test_nft_candidate_is_owned_effective_and_ipv6_deny_first() -> None:
    module = _edge_applier_module()
    candidate = _rendered_nft_candidate(module)
    result = module.validate_nft_candidate(
        candidate,
        contract_digest=module.sha256_file(EDGE_CONTRACT),
        public_interface="ens3",
        template=_nft_template(),
    )
    assert result["public_edge"]["host"] == "atius-srv-1"
    assert result["backend"]["host"] == "horistic-srv"
    assert result["backend"]["native_ingress_source_ipv4"] == "10.11.1.11"
    assert result["translations"] == [
        {"protocol": "tcp", "external_port": 34099, "backend_port": 21115},
        {"protocol": "tcp", "external_port": 34100, "backend_port": 21116},
        {"protocol": "udp", "external_port": 34100, "backend_port": 21116},
        {"protocol": "tcp", "external_port": 34101, "backend_port": 21117},
    ]
    assert result["hooks"] == {
        "edge_prerouting": ["prerouting", "dstnat"],
        "edge_forward": ["forward", "filter"],
        "edge_postrouting": ["postrouting", "srcnat"],
        "direct_native_input": ["input", "filter"],
    }
    lowered = candidate.lower()
    assert "flush ruleset" not in lowered
    assert not any(token in lowered for token in ("k3s", "cni", "flannel", "kube-"))


@pytest.mark.parametrize(
    ("replacement", "blocker"),
    [
        ("ATIUS-PHASE53-EDGE", "nft-ownership-marker-invalid"),
        ("priority dstnat", "nft-priority-invalid"),
        ('iifname "ens3"', "nft-interface-invalid"),
        ("meta nfproto ipv6 meta l4proto tcp", "nft-ipv6-deny-invalid"),
    ],
)
def test_nft_ownership_effective_semantics_fail_on_drift(
    replacement: str, blocker: str
) -> None:
    module = _edge_applier_module()
    candidate = _rendered_nft_candidate(module).replace(replacement, "DRIFT", 1)
    with pytest.raises(module.EdgeBlocked, match=blocker):
        module.validate_nft_candidate(
            candidate,
            contract_digest=module.sha256_file(EDGE_CONTRACT),
            public_interface="ens3",
            template=_nft_template(),
        )


def test_boot_unit_loads_fixed_policy_before_network_pre_and_verifies_readback() -> None:
    assert EDGE_BOOT_SERVICE.is_file(), EDGE_BOOT_SERVICE
    unit = _load_unit(EDGE_BOOT_SERVICE)
    service = unit["Service"]
    encoded = EDGE_BOOT_SERVICE.read_text(encoding="utf-8")
    assert unit["Unit"]["DefaultDependencies"] == "no"
    assert unit["Unit"]["Before"] == "network-pre.target"
    assert unit["Unit"]["Wants"] == "network-pre.target"
    assert service["Type"] == "oneshot"
    assert not any(
        line.startswith("ConditionPath") for line in encoded.splitlines()
    )
    prechecks = [
        line.split("=", 1)[1]
        for line in encoded.splitlines()
        if line.startswith("ExecStartPre=")
    ]
    assert prechecks == [
        "/usr/bin/test -r /etc/atius-rustdesk/phase53-edge.nft",
        "/usr/bin/test -r /etc/atius-rustdesk/phase53-edge.template.nft",
        "/usr/bin/test -r /etc/atius-rustdesk/phase53-edge.json",
        "/usr/bin/test -x /usr/local/libexec/apply-phase53-edge.py",
    ]
    assert "--apply-host-policy-transaction" in service["ExecStart"]
    assert "--snapshot /run/atius-rustdesk-phase53-edge/nft-prestate.json" in service["ExecStart"]
    assert "--restore-host-policy-snapshot" in service["ExecStop"]
    assert "ExecStartPost" not in service
    assert service["RuntimeDirectory"] == "atius-rustdesk-phase53-edge"
    assert service["RuntimeDirectoryMode"] == "0700"
    assert unit["Install"]["WantedBy"] == "network-pre.target"


def test_snapshot_storage_is_bounded_root_only_and_rejects_secret_surfaces(
    tmp_path: Path,
) -> None:
    module = _edge_applier_module()
    destination = tmp_path / "rollback/snapshot.json"
    snapshot = {"revision": "1", "state": {"nft": {}, "oci": {}, "k3s": "digest"}}
    receipt = module.store_bounded_snapshot(destination, snapshot, max_bytes=4096)
    assert receipt["bytes"] <= 4096
    assert destination.stat().st_mode & 0o777 == 0o600
    assert destination.parent.stat().st_mode & 0o777 == 0o700
    assert json.loads(destination.read_text(encoding="utf-8")) == snapshot

    with pytest.raises(module.EdgeBlocked, match="snapshot-too-large"):
        module.store_bounded_snapshot(destination, {"state": "x" * 5000}, max_bytes=100)
    with pytest.raises(module.EdgeBlocked, match="snapshot-secret-surface"):
        module.store_bounded_snapshot(
            destination, {"Authorization": "Bearer fixture-secret"}, max_bytes=4096
        )
    destination.unlink()
    destination.symlink_to(tmp_path / "redirect")
    with pytest.raises(module.EdgeBlocked, match="snapshot-symlink-forbidden"):
        module.store_bounded_snapshot(destination, snapshot, max_bytes=4096)


def test_cas_stale_revision_blocks_before_any_nft_or_oci_mutation() -> None:
    module = _edge_applier_module()
    backend = _FakeEdgeBackend()
    backend.force_stale_revision = True
    transaction = _edge_transaction(module, backend)
    with pytest.raises(module.EdgeBlocked, match="edge-cas-stale"):
        transaction.execute_edge(
            preflight=_phase53_edge_preflight(),
            nft_candidate=_rendered_nft_candidate(module),
            public_interface="ens3",
            oci_candidate=_allowed_oci_pages(),
        )
    assert backend.mutation_count == 0
    assert "nft-apply" not in backend.calls
    assert "oci-apply" not in backend.calls


def test_semantic_rollback_restores_exact_prestate_and_is_idempotent() -> None:
    module = _edge_applier_module()
    backend = _FakeEdgeBackend()
    original = copy.deepcopy(backend.state)
    transaction = _edge_transaction(module, backend)
    result = transaction.execute_edge(
        preflight=_phase53_edge_preflight(),
        nft_candidate=_rendered_nft_candidate(module),
        public_interface="ens3",
        oci_candidate=_allowed_oci_pages(),
    )
    assert result["state"] == "EDGE_POLICY_APPLIED"
    rollback = transaction.rollback_edge()
    assert rollback["state"] == "ROLLED_BACK"
    assert backend.state == original
    assert transaction.rollback_edge() == rollback
    assert backend.state["k3s"] == "k3s-byte-sentinel"


def test_semantic_rollback_concurrent_drift_contains_without_overwrite() -> None:
    module = _edge_applier_module()
    backend = _FakeEdgeBackend()
    transaction = _edge_transaction(module, backend)
    transaction.execute_edge(
        preflight=_phase53_edge_preflight(),
        nft_candidate=_rendered_nft_candidate(module),
        public_interface="ens3",
        oci_candidate=_allowed_oci_pages(),
    )
    backend.force_concurrent_drift = True
    result = transaction.rollback_edge()
    assert result["state"] == "CONTAINED_REQUIRES_MANUAL_RECOVERY"
    assert backend.contained is True
    assert "restore" not in backend.calls


@pytest.mark.parametrize(
    "fault_after",
    ["snapshot", "authorize", "nft-check", "nft-apply", "nft-readback", "oci-apply", "oci-audit"],
)
def test_rollback_fault_boundaries_are_terminal_and_preserve_k3s(
    fault_after: str,
) -> None:
    module = _edge_applier_module()
    backend = _FakeEdgeBackend()
    original = copy.deepcopy(backend.state)
    transaction = _edge_transaction(module, backend, fault_after=fault_after)
    with pytest.raises(module.EdgeBlocked, match=f"fault-injected-{fault_after}"):
        transaction.execute_edge(
            preflight=_phase53_edge_preflight(),
            nft_candidate=_rendered_nft_candidate(module),
            public_interface="ens3",
            oci_candidate=_allowed_oci_pages(),
        )
    assert backend.state == original
    assert backend.state["k3s"] == "k3s-byte-sentinel"
    assert transaction.state in {"ROLLED_BACK", "NEW"}


@pytest.mark.parametrize("surface", ["nft", "oci"])
def test_rollback_recovers_backend_exception_after_partial_write(surface: str) -> None:
    module = _edge_applier_module()
    backend = _FakeEdgeBackend()
    original = copy.deepcopy(backend.state)
    setattr(backend, f"raise_after_{surface}_write", True)
    transaction = _edge_transaction(module, backend)
    with pytest.raises(module.EdgeBlocked, match=f"backend-{surface}-apply-failed"):
        transaction.execute_edge(
            preflight=_phase53_edge_preflight(),
            nft_candidate=_rendered_nft_candidate(module),
            public_interface="ens3",
            oci_candidate=_allowed_oci_pages(),
        )
    assert transaction.state == "ROLLED_BACK"
    assert backend.state == original
    assert backend.mutation_count >= 1


@pytest.mark.parametrize(
    ("failure", "drift"),
    [("restore", False), ("contain", True)],
)
def test_rollback_backend_failure_is_explicitly_blocked(
    failure: str, drift: bool
) -> None:
    module = _edge_applier_module()
    backend = _FakeEdgeBackend()
    transaction = _edge_transaction(module, backend)
    transaction.execute_edge(
        preflight=_phase53_edge_preflight(),
        nft_candidate=_rendered_nft_candidate(module),
        public_interface="ens3",
        oci_candidate=_allowed_oci_pages(),
    )
    backend.force_concurrent_drift = drift
    setattr(backend, f"raise_on_{failure}", True)
    receipt = transaction.rollback_edge()
    assert receipt["state"] == "ROLLBACK_BLOCKED"
    assert receipt["manual_recovery_required"] is True


def test_rollback_restore_cas_blocks_toctou_without_blind_overwrite() -> None:
    module = _edge_applier_module()
    backend = _FakeEdgeBackend()
    transaction = _edge_transaction(module, backend)
    transaction.execute_edge(
        preflight=_phase53_edge_preflight(),
        nft_candidate=_rendered_nft_candidate(module),
        public_interface="ens3",
        oci_candidate=_allowed_oci_pages(),
    )
    backend.race_before_restore = True
    receipt = transaction.rollback_edge()
    assert receipt["state"] == "ROLLBACK_BLOCKED"
    assert backend.contained is True
    assert "restore-if-current" in backend.calls


@pytest.mark.parametrize(
    ("active_fragment", "comment_fragment", "blocker"),
    [
        (
            "type nat hook prerouting priority dstnat; policy accept;",
            "type nat hook prerouting priority dstnat; policy accept;",
            "nft-priority-invalid",
        ),
        (
            'iifname "ens3"',
            'iifname "ens3"',
            "nft-interface-invalid",
        ),
    ],
)
def test_nft_comments_cannot_satisfy_active_semantics(
    active_fragment: str, comment_fragment: str, blocker: str
) -> None:
    module = _edge_applier_module()
    candidate = _rendered_nft_candidate(module).replace(active_fragment, "ACTIVE_DRIFT")
    candidate += "\n# " + " ".join([comment_fragment] * 8) + "\n"
    with pytest.raises(module.EdgeBlocked, match=blocker):
        module.validate_nft_candidate(
            candidate,
            contract_digest=module.sha256_file(EDGE_CONTRACT),
            public_interface="ens3",
            template=_nft_template(),
        )


def test_nft_native_comment_statement_cannot_bypass_priority_validation() -> None:
    module = _edge_applier_module()
    required = "type nat hook prerouting priority dstnat; policy accept;"
    candidate = _rendered_nft_candidate(module).replace(required, "ACTIVE_DRIFT")
    candidate += f'\nadd table inet comment_fixture {{ comment "{required}"; }}\n'
    with pytest.raises(module.EdgeBlocked, match="nft-priority-invalid"):
        module.validate_nft_candidate(
            candidate,
            contract_digest=module.sha256_file(EDGE_CONTRACT),
            public_interface="ens3",
            template=_nft_template(),
        )


def test_nft_backend_semantic_readback_is_independent_from_candidate_echo() -> None:
    module = _edge_applier_module()

    class ForgedReadbackBackend(_FakeEdgeBackend):
        def apply_nft(self, candidate: str, semantics: dict[str, Any]) -> None:
            forged = copy.deepcopy(semantics)
            forged["public_edge"]["host"] = "forged-edge"
            super().apply_nft(candidate, forged)

    backend = ForgedReadbackBackend()
    transaction = _edge_transaction(module, backend)
    with pytest.raises(module.EdgeBlocked, match="nft-semantic-readback-drift"):
        transaction.execute_edge(
            preflight=_phase53_edge_preflight(),
            nft_candidate=_rendered_nft_candidate(module),
            public_interface="ens3",
            oci_candidate=_allowed_oci_pages(),
        )
    assert transaction.state == "ROLLED_BACK"


def test_nft_ipv6_uses_extension_header_safe_meta_l4proto() -> None:
    encoded = EDGE_NFT_POLICY.read_text(encoding="utf-8")
    assert "ip6 nexthdr" not in encoded
    assert "meta nfproto ipv6 meta l4proto tcp" in encoded
    assert "meta nfproto ipv6 meta l4proto udp" in encoded


def test_boot_verifier_is_operational_and_default_cli_is_zero_live(
    tmp_path: Path,
) -> None:
    default = subprocess.run(
        [sys.executable, str(EDGE_APPLIER)],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert default.returncode == 2
    assert json.loads(default.stdout) == {
        "blocker": "explicit-verifier-mode-required",
        "mutation_performed": False,
        "status": "BLOCKED",
    }

    module = _edge_applier_module()
    candidate = tmp_path / "edge.nft"
    candidate.write_text(_rendered_nft_candidate(module), encoding="utf-8")
    semantics = module.validate_nft_candidate(
        candidate.read_text(encoding="utf-8"),
        contract_digest=module.sha256_file(EDGE_CONTRACT),
        public_interface="ens3",
        template=_nft_template(),
    )
    observed = tmp_path / "observed.json"
    observed.write_text(
        json.dumps({"schema_version": 1, "semantics": semantics}), encoding="utf-8"
    )
    verified = subprocess.run(
        [
            sys.executable,
            str(EDGE_APPLIER),
            "--verify-host-policy",
            "--candidate",
            str(candidate),
            "--contract",
            str(EDGE_CONTRACT),
            "--template",
            str(EDGE_NFT_POLICY),
            "--public-interface",
            "ens3",
            "--observed-json",
            str(observed),
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert verified.returncode == 0, verified.stdout
    assert json.loads(verified.stdout) == {
        "mutation_performed": False,
        "semantic_readback_verified": True,
        "status": "PASS",
    }
    service = _load_unit(EDGE_BOOT_SERVICE)["Service"]
    assert "--apply-host-policy-transaction" in service["ExecStart"]
    assert "--contract" in service["ExecStart"]
    assert "ExecStartPost" not in service


def test_nft_library_requires_explicit_template() -> None:
    module = _edge_applier_module()
    with pytest.raises(module.EdgeBlocked, match="nft-template-required"):
        module.validate_nft_candidate(
            _rendered_nft_candidate(module),
            contract_digest=module.sha256_file(EDGE_CONTRACT),
            public_interface="ens3",
        )


@pytest.mark.parametrize(
    ("template", "blocker"),
    [
        (
            _nft_template().replace("ATIUS-PHASE53-EDGE", "FOREIGN-EDGE", 1),
            "nft-template-ownership-marker-invalid",
        ),
        (
            _nft_template().replace("contract-sha256=", "contract-sha256=0", 1),
            "nft-template-contract-digest-invalid",
        ),
    ],
)
def test_nft_template_ownership_and_contract_digest_are_mandatory(
    template: str, blocker: str
) -> None:
    module = _edge_applier_module()
    with pytest.raises(module.EdgeBlocked, match=blocker):
        module.validate_nft_candidate(
            _rendered_nft_candidate(module),
            contract_digest=module.sha256_file(EDGE_CONTRACT),
            public_interface="ens3",
            template=template,
        )


def test_boot_verifier_missing_template_fails_closed(tmp_path: Path) -> None:
    module = _edge_applier_module()
    candidate = tmp_path / "edge.nft"
    candidate.write_text(_rendered_nft_candidate(module), encoding="utf-8")
    observed = tmp_path / "observed.json"
    observed.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "semantics": {
                    "family": "inet",
                    "table": "atius_rustdesk_phase53",
                    "hook": "input",
                    "priority": 300,
                    "public_interface": "ens3",
                    "ipv4_tcp": [21115, 21116, 21117],
                    "ipv4_udp": [21116],
                    "ipv6_denied": [21114, 21115, 21116, 21117, 21118, 21119],
                },
            }
        ),
        encoding="utf-8",
    )
    base_args = [
        sys.executable,
        str(EDGE_APPLIER),
        "--verify-host-policy",
        "--candidate",
        str(candidate),
        "--contract",
        str(EDGE_CONTRACT),
        "--public-interface",
        "ens3",
        "--observed-json",
        str(observed),
    ]
    missing_argument = subprocess.run(
        base_args,
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing_argument.returncode == 2
    assert json.loads(missing_argument.stdout)["blocker"] == "nft-template-required"

    missing_file = subprocess.run(
        [*base_args, "--template", str(tmp_path / "missing.template.nft")],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing_file.returncode == 2
    assert json.loads(missing_file.stdout)["blocker"] == "nft-template-input-invalid"


def test_oci_union_uses_only_expanded_attached_security_lists_and_nsgs() -> None:
    module = _edge_applier_module()
    pages = _allowed_oci_pages()
    pages["pages"][0]["security_lists"].append(
        {
            "id": "sl-unattached-broad",
            "ingress_rules": [_oci_rule("tcp", 21114, 21119)],
        }
    )
    result = module.audit_effective_oci_ingress(pages, _load_strict(EDGE_CONTRACT))
    assert result["security_list_ids"] == ["sl-primary"]

    missing = _allowed_oci_pages()
    missing["pages"][0]["attachments"][0]["security_list_ids"] = ["sl-missing"]
    with pytest.raises(module.EdgeBlocked, match="oci-attachment-unexpanded"):
        module.audit_effective_oci_ingress(missing, _load_strict(EDGE_CONTRACT))


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        ({"source": "10.0.0.0/8"}, "oci-public-source-invalid"),
        ({"source_type": "SERVICE_CIDR_BLOCK"}, "oci-public-source-type-invalid"),
        ({"stateless": True}, "oci-public-stateless-invalid"),
    ],
)
def test_oci_public_proof_validates_source_type_and_statefulness(
    mutation: dict[str, Any], blocker: str
) -> None:
    module = _edge_applier_module()
    pages = _allowed_oci_pages()
    pages["pages"][0]["security_lists"][0]["ingress_rules"][0].update(mutation)
    with pytest.raises(module.EdgeBlocked, match=blocker):
        module.audit_effective_oci_ingress(pages, _load_strict(EDGE_CONTRACT))


def test_oci_rule_count_is_bounded_and_ranges_are_not_expanded() -> None:
    module = _edge_applier_module()
    pages = _allowed_oci_pages()
    pages["pages"][0]["security_lists"][0]["ingress_rules"] = [
        _oci_rule("tcp", 22, 22) for _ in range(module.MAX_OCI_RULES + 1)
    ]
    with pytest.raises(module.EdgeBlocked, match="oci-ingress-rule-limit"):
        module.audit_effective_oci_ingress(pages, _load_strict(EDGE_CONTRACT))
    source = inspect.getsource(module.audit_effective_oci_ingress)
    assert "set(range(" not in source


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        ({"address_observed_at": "2026-07-23T01:58:59Z"}, "address-consensus-stale"),
        (
            {
                "address_consensus": {
                    "oci-edge-vnic-public-ipv4": "2001:db8::8",
                    "edge-vnic-public-ipv4": "2001:db8::8",
                    "reserved-public-ipv4": "2001:db8::8",
                }
            },
            "address-consensus-ipv4-invalid",
        ),
        ({"current_source_head": "d" * 40}, "source-head-drift"),
        (
            {"current_contract_digests": {"phase53-edge.json": "0" * 64}},
            "contract-digest-drift",
        ),
    ],
)
def test_cas_barrier_a_requires_fresh_ipv4_and_current_digests(
    mutation: dict[str, Any], blocker: str
) -> None:
    module = _edge_applier_module()
    preflight = _phase53_edge_preflight()
    preflight.update(mutation)
    with pytest.raises(module.EdgeBlocked, match=blocker):
        module.validate_edge_preflight(
            preflight,
            now=datetime(2026, 7, 23, 2, 1, 30, tzinfo=timezone.utc),
        )


def test_barrier_a_typed_sources_are_fresh_a_only_and_topology_bound() -> None:
    module = _edge_applier_module()
    cases: list[tuple[dict[str, Any], str]] = []

    old = _phase53_edge_preflight()
    old["address_observed_at"] = "2026-07-23T01:58:00Z"
    old["authorization_time"] = "2026-07-23T01:59:00Z"
    for observation in old["address_observations"]:
        observation["observed_at"] = "2026-07-23T01:58:00Z"
    cases.append((old, "address-consensus-stale"))

    future = _phase53_edge_preflight()
    future["address_observations"][0]["observed_at"] = (
        "2026-07-23T02:02:00Z"
    )
    cases.append((future, "address-consensus-stale"))

    dual_stack = _phase53_edge_preflight()
    dual_stack["address_observations"][0]["record_types"] = ["A", "AAAA"]
    cases.append((dual_stack, "address-consensus-invalid"))

    topology_drift = _phase53_edge_preflight()
    topology_drift["address_observations"][0]["topology_id"] = "vnic:unexpected"
    cases.append((topology_drift, "address-consensus-invalid"))

    for preflight, blocker in cases:
        backend = _FakeEdgeBackend()
        transaction = _edge_transaction(module, backend)
        with pytest.raises(module.EdgeBlocked, match=blocker):
            transaction.execute_edge(
                preflight=preflight,
                nft_candidate=_rendered_nft_candidate(module),
                public_interface="ens3",
                oci_candidate=_allowed_oci_pages(),
            )
        assert backend.mutation_count == 0


def test_snapshot_storage_rejects_parent_symlink_shape_secret_values_and_record_overflow(
    tmp_path: Path,
) -> None:
    module = _edge_applier_module()
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    valid = {"revision": "1", "state": {"nft": {}, "oci": {}, "k3s": "digest"}}
    with pytest.raises(module.EdgeBlocked, match="snapshot-parent-symlink-forbidden"):
        module.store_bounded_snapshot(linked_parent / "snapshot.json", valid, max_bytes=4096)

    with pytest.raises(module.EdgeBlocked, match="snapshot-shape-invalid"):
        module.store_bounded_snapshot(
            tmp_path / "shape.json", dict(valid, unexpected=True), max_bytes=4096
        )

    pem = copy.deepcopy(valid)
    pem["state"]["nft"] = {"candidate": "-----BEGIN PRIVATE KEY-----"}
    with pytest.raises(module.EdgeBlocked, match="snapshot-secret-surface"):
        module.store_bounded_snapshot(tmp_path / "pem.json", pem, max_bytes=4096)

    bearer = copy.deepcopy(valid)
    bearer["state"]["nft"] = {"note": "Bearer fixture-secret"}
    with pytest.raises(module.EdgeBlocked, match="snapshot-secret-surface"):
        module.store_bounded_snapshot(tmp_path / "bearer.json", bearer, max_bytes=4096)

    records = copy.deepcopy(valid)
    records["state"]["oci"] = {"rules": [{"id": index} for index in range(4)]}
    with pytest.raises(module.EdgeBlocked, match="snapshot-record-limit"):
        module.store_bounded_snapshot(
            tmp_path / "records.json", records, max_bytes=4096, max_records=3
        )


def _nft_json_rule(
    family: str,
    protocol: str,
    ports: list[int],
    verdict: str,
    *,
    chain: str = "native_edge_input",
) -> dict[str, Any]:
    right: int | dict[str, list[int]] = ports[0] if len(ports) == 1 else {"set": ports}
    protocol_expressions = (
        [
            {
                "match": {
                    "op": "==",
                    "left": {"meta": {"key": "nfproto"}},
                    "right": "ipv6",
                }
            },
            {
                "match": {
                    "op": "==",
                    "left": {"meta": {"key": "l4proto"}},
                    "right": protocol,
                }
            },
        ]
        if family == "ipv6"
        else [
            {
                "match": {
                    "op": "==",
                    "left": {"payload": {"protocol": "ip", "field": "protocol"}},
                    "right": protocol,
                }
            }
        ]
    )
    return {
        "rule": {
            "family": "inet",
            "table": "atius_rustdesk_phase53",
            "chain": chain,
            "expr": [
                {
                    "match": {
                        "op": "==",
                        "left": {"meta": {"key": "iifname"}},
                        "right": "ens3",
                    }
                },
                *protocol_expressions,
                {
                    "match": {
                        "op": "==",
                        "left": {"payload": {"protocol": protocol, "field": "dport"}},
                        "right": right,
                    }
                },
                {"counter": {"packets": 0, "bytes": 0}},
                {verdict: None},
            ],
        }
    }


def _fabricated_meta_ipv4_rule(
    protocol: str, ports: list[int], verdict: str
) -> dict[str, Any]:
    rule = _nft_json_rule("ipv6", protocol, ports, verdict)
    rule["rule"]["expr"][1]["match"]["right"] = "ipv4"
    return rule


def _valid_nft_json_readback() -> dict[str, Any]:
    return {
        "nftables": [
            {"table": {"family": "inet", "name": "atius_rustdesk_phase53"}},
            {
                "chain": {
                    "family": "inet",
                    "table": "atius_rustdesk_phase53",
                    "name": "native_edge_input",
                    "hook": "input",
                    "prio": 300,
                    "policy": "accept",
                }
            },
            _nft_json_rule("ipv6", "tcp", [21114, 21115, 21116, 21117, 21118, 21119], "drop"),
            _nft_json_rule("ipv6", "udp", [21116], "drop"),
            _nft_json_rule("ipv4", "tcp", [21115, 21116, 21117], "accept"),
            _nft_json_rule("ipv4", "udp", [21116], "accept"),
            _nft_json_rule("ipv4", "tcp", [21114, 21118, 21119], "drop"),
        ]
    }


def test_nft_json_readback_accepts_canonical_ipv4_payload_ast() -> None:
    module = _edge_applier_module()
    result = module.semantics_from_nft_json(_valid_nft_json_readback(), "ens3")
    assert result["ipv4_tcp"] == [21115, 21116, 21117]
    assert result["ipv4_udp"] == [21116]


def test_nft_json_readback_rejects_fabricated_meta_ipv4_ast() -> None:
    module = _edge_applier_module()
    payload = _valid_nft_json_readback()
    payload["nftables"][4:] = [
        _fabricated_meta_ipv4_rule("tcp", [21115, 21116, 21117], "accept"),
        _fabricated_meta_ipv4_rule("udp", [21116], "accept"),
        _fabricated_meta_ipv4_rule("tcp", [21114, 21118, 21119], "drop"),
    ]
    with pytest.raises(module.EdgeBlocked, match="nft-live-semantic-readback-drift"):
        module.semantics_from_nft_json(payload, "ens3")


@pytest.mark.parametrize("mutation", ["wrong-chain", "catch-all", "duplicate"])
def test_nft_json_readback_requires_exact_owned_chain_rules(mutation: str) -> None:
    module = _edge_applier_module()
    payload = _valid_nft_json_readback()
    if mutation == "wrong-chain":
        for item in payload["nftables"]:
            if "rule" in item:
                item["rule"]["chain"] = "shadow_chain"
    elif mutation == "catch-all":
        payload["nftables"].append(
            {
                "rule": {
                    "family": "inet",
                    "table": "atius_rustdesk_phase53",
                    "chain": "native_edge_input",
                    "expr": [
                        {
                            "match": {
                                "op": "==",
                                "left": {"meta": {"key": "iifname"}},
                                "right": "ens3",
                            }
                        },
                        {"accept": None},
                    ],
                }
            }
        )
    else:
        payload["nftables"].append(copy.deepcopy(payload["nftables"][-1]))
    with pytest.raises(module.EdgeBlocked, match="nft-live-semantic-readback-drift"):
        module.semantics_from_nft_json(payload, "ens3")


def test_nft_candidate_rejects_extra_relevant_chain_or_rule() -> None:
    module = _edge_applier_module()
    candidate = _rendered_nft_candidate(module).replace(
        "\n}",
        '\n    chain shadow_input { type filter hook input priority 301; policy accept; iifname "ens3" counter accept; }\n}',
        1,
    )
    with pytest.raises(module.EdgeBlocked, match="nft-extra-chain-or-rule"):
        module.validate_nft_candidate(
            candidate,
            contract_digest=module.sha256_file(EDGE_CONTRACT),
            public_interface="ens3",
            template=_nft_template(),
        )


def test_rollback_cas_rejects_same_state_with_new_generation() -> None:
    module = _edge_applier_module()
    backend = _FakeEdgeBackend()
    transaction = _edge_transaction(module, backend)
    transaction.execute_edge(
        preflight=_phase53_edge_preflight(),
        nft_candidate=_rendered_nft_candidate(module),
        public_interface="ens3",
        oci_candidate=_allowed_oci_pages(),
    )
    backend.revision += 1
    receipt = transaction.rollback_edge()
    assert receipt["state"] == "CONTAINED_REQUIRES_MANUAL_RECOVERY"
    assert backend.contained is True
    assert "restore-if-current" not in backend.calls


def test_nft_json_readback_rejects_extra_predicate_inside_expected_rule() -> None:
    module = _edge_applier_module()
    payload = _valid_nft_json_readback()
    rule = payload["nftables"][2]["rule"]
    rule["expr"].insert(
        4,
        {
            "match": {
                "op": "==",
                "left": {"ct": {"key": "state"}},
                "right": "new",
            }
        },
    )
    with pytest.raises(module.EdgeBlocked, match="nft-live-semantic-readback-drift"):
        module.semantics_from_nft_json(payload, "ens3")


def test_nft_candidate_rejects_extra_predicate_on_expected_line() -> None:
    module = _edge_applier_module()
    candidate = _rendered_nft_candidate(module).replace(
        "counter accept\n",
        "counter accept ct state new\n",
        1,
    )
    with pytest.raises(module.EdgeBlocked, match="nft-extra-chain-or-rule"):
        module.validate_nft_candidate(
            candidate,
            contract_digest=module.sha256_file(EDGE_CONTRACT),
            public_interface="ens3",
            template=_nft_template(),
        )


def test_nft_json_readback_rejects_additional_owned_table_chain() -> None:
    module = _edge_applier_module()
    payload = _valid_nft_json_readback()
    payload["nftables"].insert(
        2,
        {
            "chain": {
                "family": "inet",
                "table": "atius_rustdesk_phase53",
                "name": "shadow_input",
                "hook": "input",
                "prio": 301,
                "policy": "accept",
            }
        },
    )
    with pytest.raises(module.EdgeBlocked, match="nft-live-semantic-readback-drift"):
        module.semantics_from_nft_json(payload, "ens3")


def _phase53_digest() -> str:
    return _load_strict(RUNTIME_CONTRACT)["upstream"]["linux_arm64_digest"]


def _tcp_positive(port: int, owner: str, origin_id: str) -> dict[str, Any]:
    backend_port = {34099: 21115, 34100: 21116, 34101: 21117}[port]
    return {
        "attempt_id": f"tcp-{origin_id}-{port}",
        "port": port,
        "connected": True,
        "started_at": "2026-07-23T02:00:35Z",
        "ended_at": "2026-07-23T02:00:40Z",
        "owner": owner,
        "container": f"atius-rustdesk-server-{owner}",
        "cgroup": "atius-rustdesk-phase53.slice",
        "image_digest": _phase53_digest(),
        "socket_port": backend_port,
        "counter_before": 10,
        "counter_after": 11,
        "owner_observed_at": "2026-07-23T02:00:38Z",
    }


def _probe_origin(
    origin_id: str,
    origin_class: str,
    egress_ipv4: str,
    source_ip: str,
    source_port: int,
    *,
    attempt_id: str,
    udp_started: str,
    udp_ended: str,
    udp_captured: str,
) -> dict[str, Any]:
    route = "private" if origin_class == "windows" else "direct"
    identity_seed = "1" if origin_class == "windows" else "2"
    executor_seed = "3" if origin_class == "windows" else "4"
    return {
        "origin_id": origin_id,
        "origin_class": origin_class,
        "attestation": {
            "transaction_id": "phase53-probe-transaction-0001",
            "target": "203.0.113.8",
            "origin_id": origin_id,
            "origin_class": origin_class,
            "host_identity_sha256": f"sha256:{identity_seed * 64}",
            "executor_digest": f"sha256:{executor_seed * 64}",
            "egress_ipv4": egress_ipv4,
            "issued_at": "2026-07-23T02:00:35Z",
        },
        "transport": {
            "selected_route": route,
            "attempts": [
                {
                    "route": route,
                    "ssh_rc": 0,
                    "session_attested": True,
                    "authenticated_envelope": True,
                }
            ],
        },
        "tcp": {
            "positive_control": {
                "port": 22,
                "connected": True,
                "started_at": "2026-07-23T02:00:31Z",
                "ended_at": "2026-07-23T02:00:34Z",
            },
            "positive": [
                _tcp_positive(34099, "hbbs", origin_id),
                _tcp_positive(34100, "hbbs", origin_id),
                _tcp_positive(34101, "hbbr", origin_id),
            ],
            "negative": [
                *[
                {
                    "attempt_id": f"tcp-{origin_id}-{port}",
                    "port": port,
                    "connected": False,
                    "started_at": "2026-07-23T02:00:41Z",
                    "ended_at": "2026-07-23T02:00:42Z",
                    "drop_counter_before": 30,
                    "drop_counter_after": 31,
                }
                for port in (21114, 21115, 21116, 21117, 21118, 21119)
                ],
            ],
        },
        "udp": {
            "attempt_id": attempt_id,
            "started_at": udp_started,
            "ended_at": udp_ended,
            "source_ip": source_ip,
            "source_port": source_port,
            "destination_ip": "203.0.113.8",
            "destination_port": 34100,
            "counter_before": 20,
            "counter_after": 21,
            "capture": {
                "mode": "metadata-only",
                "packet_count": 1,
                "source_ip": source_ip,
                "source_port": source_port,
                "destination_ip": "10.21.1.21",
                "destination_port": 21116,
                "captured_at": udp_captured,
            },
            "owner": {
                "process": "hbbs",
                "container": "atius-rustdesk-server-hbbs",
                "cgroup": "atius-rustdesk-phase53.slice",
                "image_digest": _phase53_digest(),
                "socket_port": 21116,
                "observed_at": udp_captured,
            },
            "disposable_attempt": True,
        },
    }


def _external_probe_bundle() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "transaction_id": "phase53-probe-transaction-0001",
        "target_kind": "public-ipv4",
        "target": "203.0.113.8",
        "started_at": "2026-07-23T02:00:30Z",
        "completed_at": "2026-07-23T02:02:00Z",
        "origins": [
            _probe_origin(
                "GIOVANNI-W11-PC",
                "windows",
                "198.51.100.10",
                "198.51.100.10",
                40101,
                attempt_id="udp-w11-0001",
                udp_started="2026-07-23T02:00:45Z",
                udp_ended="2026-07-23T02:00:55Z",
                udp_captured="2026-07-23T02:00:50Z",
            ),
            _probe_origin(
                "independent-probe-1",
                "independent-public",
                "198.51.100.20",
                "198.51.100.20",
                40202,
                attempt_id="udp-independent-0001",
                udp_started="2026-07-23T02:01:00Z",
                udp_ended="2026-07-23T02:01:10Z",
                udp_captured="2026-07-23T02:01:05Z",
            ),
        ],
    }


def _origin_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "transaction_id": "phase53-probe-transaction-0001",
        "max_age_seconds": 120,
        "origins": [
            {
                "origin_id": "GIOVANNI-W11-PC",
                "origin_class": "windows",
                "host_identity_sha256": "sha256:" + "1" * 64,
                "executor_digest": "sha256:" + "3" * 64,
                "allowed_routes": ["private", "public-native"],
            },
            {
                "origin_id": "independent-probe-1",
                "origin_class": "independent-public",
                "host_identity_sha256": "sha256:" + "2" * 64,
                "executor_digest": "sha256:" + "4" * 64,
                "allowed_routes": ["direct"],
            },
        ],
    }


def _hostname_probe_bundle() -> dict[str, Any]:
    targets: list[dict[str, Any]] = []
    for hostname in (
        "rustdesk.atius.com.br",
        "rustdesk-id.atius.com.br",
        "rustdesk-relay.atius.com.br",
    ):
        origins: list[dict[str, Any]] = []
        for policy, egress in zip(
            _origin_policy()["origins"],
            ("198.51.100.10", "198.51.100.20"),
            strict=True,
        ):
            origins.append(
                {
                    "origin_id": policy["origin_id"],
                    "attestation": {
                        "transaction_id": "phase53-probe-transaction-0001",
                        "target": hostname,
                        "origin_id": policy["origin_id"],
                        "origin_class": policy["origin_class"],
                        "host_identity_sha256": policy["host_identity_sha256"],
                        "executor_digest": policy["executor_digest"],
                        "egress_ipv4": egress,
                        "issued_at": "2026-07-23T02:04:00Z",
                    },
                    "resolved_addresses": ["203.0.113.8"],
                    "record_types": ["A"],
                    "checked_at": "2026-07-23T02:04:10Z",
                    "tcp_positive_ports": [34099, 34100, 34101],
                    "tcp_negative_ports": [21114, 21115, 21116, 21117, 21118, 21119],
                    "udp_external_port": 34100,
                    "udp_backend_port": 21116,
                }
            )
        targets.append({"hostname": hostname, "origins": origins})
    return {
        "schema_version": 1,
        "transaction_id": "phase53-probe-transaction-0001",
        "expected_ipv4": "203.0.113.8",
        "completed_at": "2026-07-23T02:04:20Z",
        "targets": targets,
    }


def _raw(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _validate_probe(module: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return module.validate_external_probe_bytes(
        _raw(payload),
        policy_raw=_raw(_origin_policy()),
        expected_target="203.0.113.8",
        expected_digest=_phase53_digest(),
        now=datetime(2026, 7, 23, 2, 2, 0, tzinfo=timezone.utc),
    ).value_free()


def _barrier_b(module: Any) -> dict[str, Any]:
    preflight = _phase53_edge_preflight()
    observations = copy.deepcopy(preflight["address_observations"])
    for observation in observations:
        observation["observed_at"] = "2026-07-23T02:02:30Z"
    return {
        "schema_version": 1,
        "barrier": "B",
        "address_consensus": copy.deepcopy(preflight["address_consensus"]),
        "address_observations": observations,
        "address_observed_at": "2026-07-23T02:02:30Z",
        "authorization_time": "2026-07-23T02:03:00Z",
        "source_head": preflight["source_head"],
        "contract_digests": copy.deepcopy(preflight["contract_digests"]),
        "attachment_digest": module._semantic_digest(_allowed_oci_pages()),
        "native_record_set": [],
    }


def _set_barrier_observed(barrier: dict[str, Any], value: str) -> None:
    barrier["address_observed_at"] = value
    for observation in barrier["address_observations"]:
        observation["observed_at"] = value


class _FakeDnsEdgeBackend(_FakeEdgeBackend):
    def __init__(self) -> None:
        super().__init__()
        self.dns_revision = 1
        self.dns_records: list[dict[str, Any]] = []
        self.dns_mutation_count = 0
        self.raise_after_dns_write = False
        self.force_dns_stale = False
        self.force_dns_semantic_drift = False
        self.force_dns_readback_drift = False
        self.dns_race_before_restore = False

    def snapshot_dns(self) -> dict[str, Any]:
        self.calls.append("dns-snapshot")
        return {
            "revision": str(self.dns_revision),
            "records": copy.deepcopy(self.dns_records),
        }

    def current_dns_revision(self) -> str:
        self.calls.append("dns-current-revision")
        if self.force_dns_stale:
            return str(self.dns_revision + 1)
        return str(self.dns_revision)

    def apply_dns(
        self, records: list[dict[str, Any]], *, expected_revision: str
    ) -> None:
        self.calls.append("dns-apply")
        if str(self.dns_revision) != str(expected_revision):
            raise RuntimeError("dns-cas-conflict")
        self.dns_records = copy.deepcopy(records)
        self.dns_revision += 1
        self.dns_mutation_count += 1
        if self.raise_after_dns_write:
            raise RuntimeError("dns-partial-write")

    def observe_dns(self) -> dict[str, Any]:
        self.calls.append("dns-observe")
        records = copy.deepcopy(self.dns_records)
        if self.force_dns_semantic_drift and not records:
            records = [
                {
                    "name": "rustdesk.atius.com.br",
                    "type": "TXT",
                    "content": "concurrent",
                    "proxied": False,
                }
            ]
        if self.force_dns_readback_drift and records:
            records[0]["proxied"] = True
        return {
            "revision": str(self.dns_revision),
            "records": records,
        }

    def restore_dns_if_current(
        self, snapshot: dict[str, Any], *, expected_revision: str
    ) -> None:
        self.calls.append("dns-restore-if-current")
        if self.dns_race_before_restore:
            self.dns_revision += 1
        if str(self.dns_revision) != str(expected_revision):
            raise RuntimeError("dns-restore-cas-conflict")
        self.dns_records = copy.deepcopy(snapshot["records"])
        self.dns_revision += 1


def _edge_with_ip_proof(
    module: Any, *, verify_barrier: bool = True
) -> tuple[Any, _FakeDnsEdgeBackend, dict[str, Any]]:
    backend = _FakeDnsEdgeBackend()
    clock = _FakeClock(
        datetime(2026, 7, 23, 2, 1, 30, tzinfo=timezone.utc)
    )
    transaction = _edge_transaction(module, backend, clock=clock)
    transaction.execute_edge(
        preflight=_phase53_edge_preflight(),
        nft_candidate=_rendered_nft_candidate(module),
        public_interface="ens3",
        oci_candidate=_allowed_oci_pages(),
    )
    clock.now = datetime(2026, 7, 23, 2, 2, 0, tzinfo=timezone.utc)
    receipt = transaction.accept_ip_probes(
        _raw(_external_probe_bundle()),
        policy_raw=_raw(_origin_policy()),
    )
    clock.now = datetime(2026, 7, 23, 2, 3, 30, tzinfo=timezone.utc)
    if verify_barrier:
        transaction.revalidate_barrier_b(_raw(_barrier_b(module)))
    return transaction, backend, receipt


def test_probe_strict_json_rejects_duplicate_unknown_and_secret_surfaces() -> None:
    module = _edge_applier_module()
    with pytest.raises(module.EdgeBlocked, match="duplicate-json-key"):
        module.strict_json_bytes(
            b'{"schema_version":1,"schema_version":1}', max_bytes=4096
        )

    unknown = _external_probe_bundle()
    unknown["unexpected"] = True
    with pytest.raises(module.EdgeBlocked, match="probe-schema-invalid"):
        _validate_probe(module, unknown)

    for forbidden in (
        {"nonce": "fixture"},
        {"payload": "fixture"},
        {"argv": ["ssh"]},
        {"Authorization": "Bearer fixture"},
    ):
        unsafe = _external_probe_bundle()
        unsafe["origins"][0]["udp"].update(forbidden)
        with pytest.raises(module.EdgeBlocked, match="probe-secret-surface"):
            _validate_probe(module, unsafe)


@pytest.mark.parametrize(
    ("raw", "blocker"),
    [
        (b'{"outer":{"key":1,"key":2}}', "duplicate-json-key"),
        (b'{"value":NaN}', "json-input-invalid"),
        (b'{"value":Infinity}', "json-input-invalid"),
        (b'["not-an-object"]', "json-input-invalid"),
        (b"\xff", "json-input-invalid"),
        (
            b'{"a":' * 30 + b"0" + b"}" * 30,
            "json-input-too-deep",
        ),
    ],
)
def test_probe_strict_json_rejects_nested_duplicates_constants_and_shape(
    raw: bytes, blocker: str
) -> None:
    module = _edge_applier_module()
    with pytest.raises(module.EdgeBlocked, match=blocker):
        module.strict_json_bytes(raw, max_bytes=4096)


def test_external_probe_receipt_is_two_origin_value_free_and_exact() -> None:
    module = _edge_applier_module()
    receipt = _validate_probe(module, _external_probe_bundle())
    assert receipt == {
        "schema_version": 1,
        "scope": "public-ipv4",
        "transaction_id": "phase53-probe-transaction-0001",
        "target": "203.0.113.8",
        "completed_at": "2026-07-23T02:02:00Z",
        "origin_ids": ["GIOVANNI-W11-PC", "independent-probe-1"],
        "origin_count": 2,
        "transport_routes": [
            {
                "origin_id": "GIOVANNI-W11-PC",
                "selected_route": "private",
                "attempted_routes": ["private"],
            },
            {
                "origin_id": "independent-probe-1",
                "selected_route": "direct",
                "attempted_routes": ["direct"],
            },
        ],
        "tcp_positive_ports": [34099, 34100, 34101],
        "tcp_negative_ports": [21114, 21115, 21116, 21117, 21118, 21119],
        "udp_port": 34100,
        "udp_backend_port": 21116,
        "targets": [
            "public-ipv4",
            "rustdesk.atius.com.br",
            "rustdesk-id.atius.com.br",
            "rustdesk-relay.atius.com.br",
        ],
        "udp_attempt_ids": ["udp-independent-0001", "udp-w11-0001"],
        "secret_material_present": False,
    }
    encoded = json.dumps(receipt).lower()
    assert not any(
        token in encoded
        for token in ("nonce", "payload", "argv", "stdout", "stderr", "authorization")
    )


@pytest.mark.parametrize(
    ("mutator", "blocker"),
    [
        (
            lambda payload: payload["origins"][0]["attestation"].update(
                {"target": "203.0.113.9"}
            ),
            "probe-origin-unattested",
        ),
        (
            lambda payload: payload["origins"][1]["attestation"].update(
                {"egress_ipv4": "198.51.100.10"}
            ),
            "probe-origin-not-distinct",
        ),
        (
            lambda payload: payload["origins"][1]["attestation"].update(
                {"executor_digest": "sha256:" + "0" * 64}
            ),
            "probe-origin-unattested",
        ),
        (
            lambda payload: payload["origins"][0]["tcp"]["positive_control"].update(
                {"connected": False}
            ),
            "probe-tcp-positive-control-failed",
        ),
        (
            lambda payload: payload["origins"][0]["tcp"]["positive"][0].update(
                {"image_digest": "sha256:" + "0" * 64}
            ),
            "probe-tcp-correlation-invalid",
        ),
        (
            lambda payload: payload["origins"][0]["tcp"]["positive"][0].update(
                {"counter_after": 12}
            ),
            "probe-tcp-correlation-invalid",
        ),
        (
            lambda payload: payload["origins"][0]["tcp"]["negative"][0].update(
                {"connected": True}
            ),
            "probe-tcp-forbidden-open",
        ),
        (
            lambda payload: payload["origins"][0]["udp"].update(
                {"counter_after": 22}
            ),
            "probe-udp-counter-invalid",
        ),
        (
            lambda payload: payload["origins"][0]["udp"]["capture"].update(
                {"packet_count": 2}
            ),
            "probe-udp-capture-invalid",
        ),
        (
            lambda payload: payload["origins"][0]["udp"]["capture"].update(
                {"source_port": 49999}
            ),
            "probe-udp-tuple-invalid",
        ),
        (
            lambda payload: payload["origins"][0]["udp"]["owner"].update(
                {"observed_at": "2026-07-23T02:02:00Z"}
            ),
            "probe-udp-owner-invalid",
        ),
        (
            lambda payload: payload["origins"][1]["udp"].update(
                {"attempt_id": "udp-w11-0001"}
            ),
            "probe-udp-replay",
        ),
    ],
)
def test_external_probe_adversarial_matrix_fails_closed(
    mutator: Any, blocker: str
) -> None:
    module = _edge_applier_module()
    payload = _external_probe_bundle()
    mutator(payload)
    with pytest.raises(module.EdgeBlocked, match=blocker):
        _validate_probe(module, payload)


def test_udp_capture_must_be_inside_attempt_window() -> None:
    module = _edge_applier_module()
    payload = _external_probe_bundle()
    payload["origins"][0]["udp"]["capture"]["captured_at"] = (
        "2026-07-23T02:02:00Z"
    )
    with pytest.raises(module.EdgeBlocked, match="probe-udp-window-invalid"):
        _validate_probe(module, payload)


def test_origin_policy_binding_and_udp_windows_reject_spoof_and_ambient_replay() -> None:
    module = _edge_applier_module()
    payload = _external_probe_bundle()
    payload["origins"][1]["attestation"]["transaction_id"] = "other-transaction"
    with pytest.raises(module.EdgeBlocked, match="probe-origin-unattested"):
        _validate_probe(module, payload)

    payload = _external_probe_bundle()
    policy = _origin_policy()
    duplicated_identity = policy["origins"][0]["host_identity_sha256"]
    policy["origins"][1]["host_identity_sha256"] = duplicated_identity
    payload["origins"][1]["attestation"][
        "host_identity_sha256"
    ] = duplicated_identity
    with pytest.raises(module.EdgeBlocked, match="probe-origin-not-distinct"):
        module.validate_external_probe_bytes(
            _raw(payload),
            policy_raw=_raw(policy),
            expected_target="203.0.113.8",
            expected_digest=_phase53_digest(),
            now=datetime(2026, 7, 23, 2, 2, 0, tzinfo=timezone.utc),
        )

    payload = _external_probe_bundle()
    payload["origins"][1]["udp"].update(
        {
            "started_at": "2026-07-23T02:00:50Z",
            "ended_at": "2026-07-23T02:01:00Z",
        }
    )
    payload["origins"][1]["udp"]["capture"][
        "captured_at"
    ] = "2026-07-23T02:00:55Z"
    payload["origins"][1]["udp"]["owner"][
        "observed_at"
    ] = "2026-07-23T02:00:55Z"
    with pytest.raises(module.EdgeBlocked, match="probe-udp-window-overlap"):
        _validate_probe(module, payload)


class _FakeWindowsRouteRunner:
    def __init__(
        self,
        module: Any,
        private_rc: int,
        public_rc: int = 0,
        *,
        private_attested: bool | None = None,
    ) -> None:
        self.module = module
        self.private_rc = private_rc
        self.public_rc = public_rc
        self.private_attested = (
            private_rc == 0 if private_attested is None else private_attested
        )
        self.calls: list[str] = []

    def __call__(self, route: str) -> Any:
        self.calls.append(route)
        rc = self.private_rc if route == "private" else self.public_rc
        attested = self.private_attested if route == "private" else rc == 0
        return self.module.RouteResult(rc, attested, attested)


def test_windows_private_first_fallback_is_only_for_ssh_rc255() -> None:
    module = _edge_applier_module()
    unavailable = _FakeWindowsRouteRunner(module, 255, 255)
    with pytest.raises(
        module.EdgeBlocked, match="windows-origin-unavailable-after-fallback"
    ):
        module.run_windows_private_first(unavailable)
    assert unavailable.calls == ["private", "public-native"]

    functional_failure = _FakeWindowsRouteRunner(module, 1, 0)
    with pytest.raises(module.EdgeBlocked, match="windows-private-probe-failed"):
        module.run_windows_private_first(functional_failure)
    assert functional_failure.calls == ["private"]

    authenticated_255 = _FakeWindowsRouteRunner(
        module, 255, 0, private_attested=True
    )
    with pytest.raises(module.EdgeBlocked, match="windows-private-probe-failed"):
        module.run_windows_private_first(authenticated_255)
    assert authenticated_255.calls == ["private"]

    private_ok = _FakeWindowsRouteRunner(module, 0, 0)
    assert module.run_windows_private_first(private_ok) == {
        "selected_route": "private",
        "attempts": [
            {
                "route": "private",
                "ssh_rc": 0,
                "session_attested": True,
                "authenticated_envelope": True,
            }
        ],
    }
    assert private_ok.calls == ["private"]


def test_barrier_b_is_post_ip_fresh_and_equal_to_barrier_a() -> None:
    module = _edge_applier_module()
    transaction, backend, receipt = _edge_with_ip_proof(module)
    result = transaction.publish_dns_last()
    assert result["state"] == "DNS_PUBLISHED"
    assert result["records"] == [
        {
            "name": hostname,
            "type": "A",
            "content": "203.0.113.8",
            "proxied": False,
        }
        for hostname in (
            "rustdesk.atius.com.br",
            "rustdesk-id.atius.com.br",
            "rustdesk-relay.atius.com.br",
        )
    ]
    assert backend.dns_records == result["records"]
    assert backend.calls.index("dns-apply") > backend.calls.index("oci-apply")


@pytest.mark.parametrize(
    ("mutator", "blocker"),
    [
        (
            lambda barrier: barrier["address_consensus"].update(
                {"edge-vnic-public-ipv4": "203.0.113.9"}
            ),
            "barrier-b-address-drift",
        ),
        (
            lambda barrier: _set_barrier_observed(
                barrier, "2026-07-23T01:59:00Z"
            ),
            "barrier-b-stale",
        ),
        (
            lambda barrier: _set_barrier_observed(
                barrier, "2026-07-23T02:01:59Z"
            ),
            "barrier-b-before-ip-proof",
        ),
        (
            lambda barrier: barrier.update({"attachment_digest": "0" * 64}),
            "barrier-b-attachment-drift",
        ),
        (
            lambda barrier: barrier.update(
                {
                    "native_record_set": [
                        {
                            "type": "AAAA",
                            "name": "rustdesk.atius.com.br",
                            "content": "2001:db8::8",
                            "proxied": False,
                        }
                    ]
                }
            ),
            "barrier-b-dns-not-closed",
        ),
    ],
)
def test_barrier_b_drift_staleness_and_order_block_before_dns(
    mutator: Any, blocker: str
) -> None:
    module = _edge_applier_module()
    transaction, backend, receipt = _edge_with_ip_proof(
        module, verify_barrier=False
    )
    barrier = _barrier_b(module)
    mutator(barrier)
    with pytest.raises(module.EdgeBlocked, match=blocker):
        transaction.revalidate_barrier_b(_raw(barrier))
    assert backend.dns_mutation_count == 0


def test_dns_is_unreachable_before_two_origin_ip_proof_and_cas() -> None:
    module = _edge_applier_module()
    backend = _FakeDnsEdgeBackend()
    transaction = _edge_transaction(module, backend)
    transaction.execute_edge(
        preflight=_phase53_edge_preflight(),
        nft_candidate=_rendered_nft_candidate(module),
        public_interface="ens3",
        oci_candidate=_allowed_oci_pages(),
    )
    with pytest.raises(module.EdgeBlocked, match="barrier-b-required-before-dns"):
        transaction.publish_dns_last()
    assert backend.dns_mutation_count == 0

    transaction, backend, receipt = _edge_with_ip_proof(module)
    backend.force_dns_stale = True
    with pytest.raises(module.EdgeBlocked, match="dns-cas-stale"):
        transaction.publish_dns_last()
    assert backend.dns_mutation_count == 0


def test_dns_partial_write_rolls_back_exactly_and_is_idempotent() -> None:
    module = _edge_applier_module()
    transaction, backend, receipt = _edge_with_ip_proof(module)
    backend.raise_after_dns_write = True
    with pytest.raises(module.EdgeBlocked, match="backend-dns-apply-failed"):
        transaction.publish_dns_last()
    assert backend.dns_records == []
    assert backend.calls.index("contain") < backend.calls.index(
        "dns-restore-if-current"
    )
    rollback = transaction.rollback_dns()
    assert rollback["state"] == "DNS_ROLLED_BACK"
    assert transaction.rollback_dns() == rollback


def test_dns_semantic_cas_and_restore_race_fail_closed() -> None:
    module = _edge_applier_module()
    transaction, backend, _ = _edge_with_ip_proof(module)
    backend.force_dns_semantic_drift = True
    with pytest.raises(module.EdgeBlocked, match="dns-cas-semantic-drift"):
        transaction.publish_dns_last()
    assert backend.dns_mutation_count == 0

    transaction, backend, _ = _edge_with_ip_proof(module)
    backend.raise_after_dns_write = True
    backend.dns_race_before_restore = True
    with pytest.raises(module.EdgeBlocked, match="backend-dns-apply-failed"):
        transaction.publish_dns_last()
    rollback = transaction.rollback_dns()
    assert rollback["state"] == "DNS_ROLLBACK_BLOCKED"
    assert backend.contained is True
    assert backend.dns_records != []


def test_dns_postwrite_semantic_drift_contains_and_restores_exactly() -> None:
    module = _edge_applier_module()
    transaction, backend, _ = _edge_with_ip_proof(module)
    backend.force_dns_readback_drift = True
    with pytest.raises(module.EdgeBlocked, match="dns-semantic-readback-drift"):
        transaction.publish_dns_last()
    assert backend.contained is True
    assert backend.dns_records == []


def test_hostname_proof_is_internal_state_and_failure_rolls_back_all() -> None:
    module = _edge_applier_module()
    transaction, backend, _ = _edge_with_ip_proof(module)
    transaction.publish_dns_last()
    transaction.clock.now = datetime(
        2026, 7, 23, 2, 4, 30, tzinfo=timezone.utc
    )
    receipt = transaction.accept_hostname_probes(
        _raw(_hostname_probe_bundle()),
        policy_raw=_raw(_origin_policy()),
    )
    assert receipt["scope"] == "public-hostnames"
    assert receipt["hostname_count"] == 3
    assert transaction.state == "HOSTNAME_PROBES_VERIFIED"

    transaction, backend, _ = _edge_with_ip_proof(module)
    transaction.publish_dns_last()
    transaction.clock.now = datetime(
        2026, 7, 23, 2, 4, 30, tzinfo=timezone.utc
    )
    invalid = _hostname_probe_bundle()
    invalid["targets"][0]["origins"][0]["record_types"] = ["A", "AAAA"]
    with pytest.raises(module.EdgeBlocked, match="hostname-probe-invalid"):
        transaction.accept_hostname_probes(
            _raw(invalid),
            policy_raw=_raw(_origin_policy()),
        )
    assert backend.dns_records == []
    assert backend.contained is True
    assert transaction.state == "ROLLED_BACK"


def test_dns_concurrent_drift_contains_without_destructive_restore() -> None:
    module = _edge_applier_module()
    transaction, backend, receipt = _edge_with_ip_proof(module)
    transaction.publish_dns_last()
    backend.dns_records.append(
        {
            "name": "rustdesk.atius.com.br",
            "type": "TXT",
            "content": "concurrent",
            "proxied": False,
        }
    )
    backend.dns_revision += 1
    receipt = transaction.rollback_dns()
    assert receipt["state"] == "CONTAINED_REQUIRES_MANUAL_RECOVERY"
    assert backend.contained is True
    assert "dns-restore-if-current" not in backend.calls


def test_probe_scripts_are_offline_value_free_and_powershell_has_no_disk_surface(
    tmp_path: Path,
) -> None:
    assert EDGE_PROBE.is_file(), EDGE_PROBE
    assert EDGE_PROBE_PS1.is_file(), EDGE_PROBE_PS1
    python_source = EDGE_PROBE.read_text(encoding="utf-8")
    powershell_source = EDGE_PROBE_PS1.read_text(encoding="utf-8")
    assert "explicit-offline-observation-required" in python_source
    assert "--validate-observation" in python_source
    assert "ConvertFrom-Json" in powershell_source
    assert "ConvertTo-Json -Compress" in powershell_source
    for forbidden in (
        "Start-Transcript",
        "Stop-Transcript",
        "Out-File",
        "Set-Content",
        "Add-Content",
        "Tee-Object",
        "Test-NetConnection",
        "Invoke-WebRequest",
    ):
        assert forbidden not in powershell_source
    lowered = powershell_source.lower()
    for forbidden in (
        "[io.file]",
        "system.io.",
        "redirectstandardoutput",
        "redirectstandarderror",
        "new-temporaryfile",
        "export-",
        "transcript",
        "invoke-webrequest",
        "test-netconnection",
        " > ",
        " 2>",
    ):
        assert forbidden not in lowered

    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    default = subprocess.run(
        [sys.executable, str(EDGE_PROBE)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert default.returncode == 2
    assert json.loads(default.stdout) == {
        "blocker": "explicit-offline-observation-required",
        "network_performed": False,
        "status": "BLOCKED",
    }
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before

    pwsh = shutil.which("pwsh")
    if pwsh:
        observation = {
            "schema_version": 1,
            "transaction_id": "phase53-probe-transaction-0001",
            "target_kind": "public-ipv4",
            "target": "203.0.113.8",
            "started_at": "2026-07-23T02:00:30Z",
            "completed_at": "2026-07-23T02:02:00Z",
            "origins": [],
        }
        result = subprocess.run(
            [
                pwsh,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(EDGE_PROBE_PS1),
                "-ObservationJson",
                json.dumps(observation),
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["transaction_id"] == observation[
            "transaction_id"
        ]
        assert (
            sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
            == before
        )


def _phase53_authority_observation(
    *, observed_at: str = "2098-12-31T23:59:00Z"
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for host in ("atius-srv-2", "atius-srv-3"):
        samples.extend(
            {
                "host": host,
                "observed_at": observed_at,
                "placement_state": "NO-GO",
                "zero_cleanup_performed": False,
            }
            for _ in range(2)
        )
    samples.extend(
        {
            "host": "horistic-srv",
            "observed_at": observed_at,
            "placement_state": "GO",
            "raw_capacity_state": "CURRENT",
            "capacity_finalize_state": "CURRENT",
            "zero_cleanup_performed": False,
        }
        for _ in range(2)
    )
    return {
        "schema_version": 1,
        "observed_at": observed_at,
        "ttl_seconds": 3600,
        "read_only": True,
        "synthetic": False,
        "mutation_performed": False,
        "secret_material_present": False,
        "topology": {
            "state": "CURRENT",
            "public_edge_host": "atius-srv-1",
            "public_ipv4": "137.131.140.20",
            "public_vnic_private_ipv4": "10.0.0.238",
            "route_vnic_private_ipv4": "10.11.1.11",
            "backend_host": "horistic-srv",
            "backend_private_ipv4": "10.21.1.21",
            "backend_ingress_source_ipv4": "10.11.1.11",
        },
        "supply": {
            "state": "CURRENT",
            "immutable_reference": (
                "docker.io/rustdesk/rustdesk-server@sha256:"
                + "1" * 64
            ),
        },
        "capacity_samples": samples,
        "vault_public_fingerprint": {
            "vault_path": "kv/atius/rustdesk/server",
            "public_fingerprint_sha256": "2" * 64,
            "value_free": True,
        },
        "provider": {
            "prestates": {
                surface: {
                    "kind": "prestate",
                    "surface": surface,
                    "revision": f"{surface}-revision",
                    "mutation_performed": False,
                }
                for surface in ("host", "oci", "cloudflare", "apache")
            },
            "previews": {
                surface: {
                    "kind": "preview",
                    "surface": surface,
                    "confirmation_sha256": hashlib.sha256(
                        surface.encode("utf-8")
                    ).hexdigest(),
                    "mutation_performed": False,
                }
                for surface in ("host", "oci", "cloudflare", "apache")
            },
        },
    }


def test_05e_successor_attestation_binds_frozen_phase52() -> None:
    module = _authority_builder_module()
    result = module.validate_frozen_phase52(REPO)
    assert result["source_freeze_commit"] == (
        "6bb2e0abad5cad3eb1ff750bcb92130c06ee0f6c"
    )
    assert result["attestation_commit"] == (
        "e552c876f32cc87bb0d97b71308056f30423c452"
    )
    assert result["closeout_commit"] == (
        "11fa627fdd27c7032f0029cd594bc2e1241e20bb"
    )
    assert result["reviewer_ids"] == [
        "fresh-reviewer-52-08-e",
        "fresh-reviewer-52-08-f",
    ]
    assert result["historical_replay"] is False
    assert result["historical_rebaseline"] is False
    assert result["authorizes_live"] is False


def test_05e_descendant_source_binding_rejects_drift() -> None:
    module = _binding_checker_module()
    payload = _load_strict(EXECUTION_SOURCE_SCOPE)
    paths = module.validate_execution_source_scope_payload(payload)
    assert len(paths) == 34
    assert module.EXECUTION_SOURCE_COMMIT_PATHS == tuple(
        sorted(EXPECTED_EXECUTION_SOURCE_COMMIT_PATHS)
    )


def test_05e_read_only_backend_has_no_write_capability() -> None:
    backend = _live_backend_module()
    builder = _authority_builder_module()
    fields = set(backend.ReadOnlyProviderBundle.__dataclass_fields__)
    assert fields == {
        "read_topology",
        "read_supply",
        "read_capacity",
        "read_vault_public_fingerprint",
        "read_provider_prestates",
        "preview_provider_changes",
        "capabilities",
    }
    assert not fields.intersection(
        {
            "apply",
            "mutate",
            "contain",
            "containment",
            "rollback",
            "restore",
            "runtime",
            "providers",
        }
    )
    mapping = MappingProxyType(
        {"outer": MappingProxyType({"sequence": (3, 2, 1)})}
    )
    assert builder.canonical_bytes(mapping) == (
        b'{"outer":{"sequence":[3,2,1]}}'
    )
    assert builder.canonical_bytes(mapping) == builder.canonical_bytes(mapping)
    for unsafe, blocker in (
        ({"blob": b"bytes"}, "bytes-forbidden"),
        ({"password": "value"}, "secret-key-forbidden"),
        ({"verdict": "PASS"}, "stored-verdict-forbidden"),
    ):
        with pytest.raises(builder.AuthorityPlanBlocked, match=blocker):
            builder.canonical_bytes(unsafe)


def test_05e_operation_plan_writes_exact_six_artifacts_and_rejects_public_vnic_backend_source(
    tmp_path: Path,
) -> None:
    module = _authority_builder_module()
    observation = _phase53_authority_observation()
    receipt = {
        "05D2H_summary_commit": "3" * 40,
        "quarantine_manifest_sha256": "4" * 64,
        "generation_id": "5" * 64,
        "canonical_seven_absent_sha256": "6" * 64,
        "canonical_paths_absent": True,
    }
    payloads = module.build_authority_payloads(
        observation=observation,
        source_binding={
            "execution_source_commit": "7" * 40,
            "execution_source_tree_sha256": "8" * 64,
            "manifest_paths": list(EXPECTED_EXECUTION_SOURCE_PATHS),
        },
        phase52=module.validate_frozen_phase52(REPO),
        housekeeping_receipt=receipt,
        now=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc),
    )
    output = tmp_path / "authority"
    module.promote_authority_generation(output, payloads)
    assert sorted(path.name for path in output.iterdir()) == sorted(
        module.AUTHORITY_FILENAMES
    )
    assert json.loads(
        (output / "edge-forwarder-operation-plan.json").read_text(encoding="utf-8")
    )["status"] == "AWAITING_OWNER_HASH_APPROVAL"
    for boundary in range(1, 6):
        partial = tmp_path / f"partial-{boundary}"
        with pytest.raises(
            module.AuthorityPlanBlocked, match="injected-promotion-failure"
        ):
            module.promote_authority_generation(
                partial, payloads, fail_after=boundary
            )
        with pytest.raises(module.AuthorityPlanBlocked):
            module.validate_authority_generation(partial)

    drift = copy.deepcopy(observation)
    drift["topology"]["backend_ingress_source_ipv4"] = "10.0.0.238"
    with pytest.raises(
        module.AuthorityPlanBlocked, match="public-vnic-backend-source-forbidden"
    ):
        module.validate_authority_observation(
            drift, now=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc)
        )


def test_05e_capacity_current_requires_six_ordered_samples() -> None:
    module = _authority_builder_module()
    observation = _phase53_authority_observation()
    module.validate_authority_observation(
        observation, now=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc)
    )
    observation["capacity_samples"][1], observation["capacity_samples"][2] = (
        observation["capacity_samples"][2],
        observation["capacity_samples"][1],
    )
    with pytest.raises(module.AuthorityPlanBlocked, match="capacity-sample-order-invalid"):
        module.validate_authority_observation(
            observation, now=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc)
        )


def test_05e_awaiting_owner_is_exit_zero_without_owner_or_journal(
    tmp_path: Path,
) -> None:
    module = _authority_builder_module()
    operation_plan = {
        "schema_version": 1,
        "status": "AWAITING_OWNER_HASH_APPROVAL",
        "operation_plan_sha256": "a" * 64,
        "execution_source_commit": "b" * 40,
        "execution_source_tree_sha256": "c" * 64,
        "expires_at": "2099-01-01T00:00:00Z",
        "mutation_performed": False,
        "secret_material_present": False,
    }
    result = module.awaiting_owner_result(operation_plan)
    assert result["status"] == "AWAITING_OWNER_HASH_APPROVAL"
    assert result["exit_code"] == 0
    assert result["owner_record_created"] is False
    assert result["journal_created"] is False
    assert result["provider_constructed"] is False
    assert list(tmp_path.iterdir()) == []


def test_05e_strict_validator_accepts_authority_and_live_set_with_immutable_source() -> None:
    validator = _load_python_module(
        REPO / "modules/rustdesk-fleet/tools/validate_phase53_live_evidence.py",
        "phase53_strict_live_evidence",
    )
    assert validator.AUTHORITY_NAMES == (
        "topology-discovery.json",
        "phase52-successor-attestation.json",
        "candidate-admission.json",
        "capacity-current.json",
        "preflight.json",
        "edge-forwarder-operation-plan.json",
        "edge-forwarder-owner-approval.json",
    )
    assert validator.LIVE_NAMES == (
        "deploy-transaction.json",
        "edge-probes.json",
        "ops-api-probes.json",
        "lifecycle.json",
        "rollback-drill.json",
        "restore-production-transaction.json",
        "direct-relay-metrics.json",
    )
    assert "compatibility-pending.json" not in validator.AUTHORITY_NAMES


def test_05e_housekeeping_receipt_is_explicit_current_and_symlink_safe(
    tmp_path: Path,
) -> None:
    module = _authority_builder_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_fixture(repo, "init", "-q")
    _git_fixture(repo, "config", "user.name", "Phase53 Test")
    _git_fixture(repo, "config", "user.email", "phase53@example.invalid")
    d2d = repo / module.D2D_SUMMARY_PATH
    d2d.parent.mkdir(parents=True)
    d2d.write_text("source summary\n", encoding="utf-8")
    _git_fixture(repo, "add", "--", str(module.D2D_SUMMARY_PATH))
    _git_fixture(repo, "commit", "-qm", "05D2D summary")
    d2d_commit = _git_fixture(repo, "rev-parse", "HEAD")
    d2h = repo / module.D2H_SUMMARY_PATH
    d2h.write_text("housekeeping summary\n", encoding="utf-8")
    _git_fixture(repo, "add", "--", str(module.D2H_SUMMARY_PATH))
    _git_fixture(repo, "commit", "-qm", "05D2H summary")
    d2h_commit = _git_fixture(repo, "rev-parse", "HEAD")

    root = tmp_path / "quarantine"
    generation = root / ("d" * 64)
    generation.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)
    os.chmod(generation, 0o700)
    rows = []
    for index, relative in enumerate(module.CANONICAL_05F_PATHS):
        backup = generation / f"{index}.json"
        backup.write_text(relative, encoding="utf-8")
        os.chmod(backup, 0o600)
        rows.append(
            {
                "source": relative,
                "backup": str(backup),
                "size": backup.stat().st_size,
                "sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
            }
        )
    manifest = generation / "manifest.json"
    manifest.write_bytes(
        module.canonical_bytes(
            {
                "status": "complete",
                "generation_id": "d" * 64,
                "inventory_sha256": "d" * 64,
                "canonical_paths": list(module.CANONICAL_05F_PATHS),
                "moved_paths": list(module.CANONICAL_05F_PATHS),
                "files": rows,
            }
        )
    )
    os.chmod(manifest, 0o600)
    pointer = root / "current-phase53.json"
    pointer.write_bytes(
        module.canonical_bytes(
            {
                "manifest_path": str(manifest),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "generation_id": "d" * 64,
            }
        )
    )
    os.chmod(pointer, 0o600)
    d2h.write_text(
        "quarantine_manifest_sha256: "
        f"{hashlib.sha256(manifest.read_bytes()).hexdigest()}\n"
        f"generation_id: {'d' * 64}\n"
        "canonical_paths_absent: true\n",
        encoding="utf-8",
    )
    _git_fixture(repo, "add", "--", str(module.D2H_SUMMARY_PATH))
    _git_fixture(repo, "commit", "--amend", "--no-edit", "-q")
    d2h_commit = _git_fixture(repo, "rev-parse", "HEAD")
    receipt = module.validate_housekeeping_receipt(
        repo=repo,
        summary_path=d2h,
        quarantine_pointer=pointer,
        expected_05d2d_summary_commit=d2d_commit,
        quarantine_root=root,
    )
    assert receipt["05D2H_summary_commit"] == d2h_commit
    assert receipt["canonical_paths_absent"] is True
    pointer.unlink()
    pointer.symlink_to(manifest)
    with pytest.raises(module.AuthorityPlanBlocked, match="housekeeping-pointer-invalid"):
        module.validate_housekeeping_receipt(
            repo=repo,
            summary_path=d2h,
            quarantine_pointer=pointer,
            expected_05d2d_summary_commit=d2d_commit,
            quarantine_root=root,
        )


def test_05e_owner_approval_requires_explicit_response() -> None:
    module = _authority_builder_module()
    plan = {
        "operation_plan_sha256": "a" * 64,
        "execution_source_commit": "b" * 40,
        "execution_source_tree_sha256": "c" * 64,
        "expires_at": "2099-01-01T00:00:00Z",
        "risk_acknowledgement_required": True,
        "rollback_acknowledgement_required": True,
    }
    with pytest.raises(module.AuthorityPlanBlocked, match="owner-response-invalid"):
        module.build_owner_approval({}, plan, now=datetime(2098, 1, 1, tzinfo=timezone.utc))


def test_05e_owner_approval_hash_and_expiry_are_current() -> None:
    module = _authority_builder_module()
    plan = {
        "operation_plan_sha256": "a" * 64,
        "execution_source_commit": "b" * 40,
        "execution_source_tree_sha256": "c" * 64,
        "expires_at": "2099-01-01T00:00:00Z",
        "risk_acknowledgement_required": True,
        "rollback_acknowledgement_required": True,
    }
    response = {
        "owner": "Giovanni Muniz",
        "decision": "approve",
        "operation_plan_sha256": "a" * 64,
        "expires_at": "2098-06-01T00:00:00Z",
        "risk_acknowledged": True,
        "rollback_acknowledged": True,
    }
    approval = module.build_owner_approval(
        response, plan, now=datetime(2098, 1, 1, tzinfo=timezone.utc)
    )
    assert approval["operation_plan_sha256"] == plan["operation_plan_sha256"]
    response["operation_plan_sha256"] = "d" * 64
    with pytest.raises(module.AuthorityPlanBlocked, match="owner-plan-hash-mismatch"):
        module.build_owner_approval(
            response, plan, now=datetime(2098, 1, 1, tzinfo=timezone.utc)
        )


def test_05e_no_auto_apply_after_owner_record(tmp_path: Path) -> None:
    module = _authority_builder_module()
    source = inspect.getsource(module)
    assert "build_phase53_apply_backend" not in source
    assert "RuntimeProvider" not in source
    assert "ApplyProviderBundle" not in source
    output = tmp_path / "owner.json"
    module.write_owner_record(
        output,
        {
            "schema_version": 1,
            "owner": "Giovanni Muniz",
            "decision": "approve",
            "operation_plan_sha256": "a" * 64,
            "execution_source_commit": "b" * 40,
            "execution_source_tree_sha256": "c" * 64,
            "expires_at": "2099-01-01T00:00:00Z",
            "risk_acknowledged": True,
            "rollback_acknowledged": True,
            "response_sha256": "d" * 64,
            "secret_material_present": False,
            "mutation_performed": False,
        },
    )
    assert [item.name for item in tmp_path.iterdir()] == ["owner.json"]


def test_05f_new_process_revalidates_authority_before_journal(
    tmp_path: Path,
) -> None:
    module = _live_gate_module()
    calls: list[str] = []
    with pytest.raises(module.GateBlocked, match="authority-revalidation-failed"):
        module.execute_revalidated_apply_transaction(
            authority_validator=lambda: False,
            journal_dir=tmp_path / "journals",
            provider_factory=lambda: calls.append("provider"),
        )
    assert calls == []
    assert not (tmp_path / "journals").exists()


def test_05f_full_sequence_is_single_transaction(tmp_path: Path) -> None:
    module = _live_gate_module()
    calls: list[str] = []
    result = module.execute_apply_transaction(
        journal_dir=tmp_path,
        operation_plan_sha256="1" * 64,
        approval_sha256="2" * 64,
        execution_source_commit="3" * 40,
        execution_source_tree_sha256="4" * 64,
        adapters={
            stage: (lambda stage=stage: calls.append(stage) or {"stage": stage})
            for stage in module.FULL_TRANSACTION_SEQUENCE
        },
        stage="full",
    )
    assert calls == list(module.FULL_TRANSACTION_SEQUENCE)
    assert len(
        {
            result["apply_transaction_id"],
            result["rollback_transaction_id"],
            result["restore_production_transaction_id"],
        }
    ) == 3


def test_05f_lifecycle_and_two_origin_probes_are_bound() -> None:
    module = _live_gate_module()
    assert module.FULL_TRANSACTION_SEQUENCE.index("ip-probes") < (
        module.FULL_TRANSACTION_SEQUENCE.index("dns-publication")
    )
    assert module.FULL_TRANSACTION_SEQUENCE.index("hostname-probes") < (
        module.FULL_TRANSACTION_SEQUENCE.index("lifecycle")
    )
    assert tuple(module.FULL_TRANSACTION_SEQUENCE).count("lifecycle") == 1


def test_05f_immutable_rollback_and_distinct_restore_transaction(
    tmp_path: Path,
) -> None:
    module = _live_gate_module()
    result = module.execute_apply_transaction(
        journal_dir=tmp_path,
        operation_plan_sha256="1" * 64,
        approval_sha256="2" * 64,
        execution_source_commit="3" * 40,
        execution_source_tree_sha256="4" * 64,
        adapters={
            stage: (lambda stage=stage: {"stage": stage})
            for stage in module.FULL_TRANSACTION_SEQUENCE
        },
        stage="full",
    )
    rollback = tmp_path / result["rollback_journal"]
    before = rollback.read_bytes()
    assert result["rollback_transaction_id"] != result[
        "restore_production_transaction_id"
    ]
    assert rollback.read_bytes() == before


def test_05f_zero_cleanup_migration_and_stale_output_prestate_remain_untouched(
    tmp_path: Path,
) -> None:
    module = _authority_builder_module()
    observation = _phase53_authority_observation()
    before = copy.deepcopy(observation)
    module.validate_authority_observation(
        observation, now=datetime(2098, 12, 31, 23, 59, tzinfo=timezone.utc)
    )
    assert observation == before
    assert all(
        item["zero_cleanup_performed"] is False
        for item in observation["capacity_samples"]
    )
    assert "10.31.1.31" not in json.dumps(observation, sort_keys=True)
    assert list(tmp_path.iterdir()) == []
