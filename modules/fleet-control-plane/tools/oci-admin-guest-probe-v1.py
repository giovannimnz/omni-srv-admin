#!/usr/bin/env python3
"""Closed, read-only guest probe for the six OCI Admin Phase 25 runbooks."""

from __future__ import annotations

from collections import namedtuple
from hashlib import sha256
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from time import monotonic
from typing import Any, Callable, Mapping, Sequence


VERSION = "1"
SENTINEL = "ATIUS_RUNBOOK_RESULT_V1"
MAX_RESULT_BYTES = 32768
MAX_COMMAND_OUTPUT_BYTES = 131072
MAX_ATTESTATION_BYTES = 65536
MAX_COMMAND_TIMEOUT_SECONDS = 10
TCP_TIMEOUT_SECONDS = 3
SANITIZED_ERROR_LINE = "oci-admin-guest-probe-v1: rejected\n"

IP_BINARY = "/usr/sbin/ip"
PODMAN_BINARY = "/usr/bin/podman"
PING_BINARY = "/usr/bin/ping"
DIG_BINARY = "/usr/bin/dig"
GETENT_BINARY = "/usr/bin/getent"
ATTESTATION_PATH = Path("/etc/oci-admin-guest-probe-v1/attestation.json")

IP_ADDRESS_COMMAND = (IP_BINARY, "-j", "-4", "address", "show")
IP_ROUTE_COMMAND = (IP_BINARY, "-j", "-4", "route", "show", "table", "all")
PODMAN_LIST_COMMAND = (PODMAN_BINARY, "network", "ls", "--format", "json")
PODMAN_INSPECT_PREFIX = (PODMAN_BINARY, "network", "inspect")
DIG_PREFIX = (
    DIG_BINARY,
    "+time=3",
    "+tries=1",
    "+noall",
    "+comments",
    "+answer",
)

CLEAN_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
}

EXPECTED_HOST_ADDRESSES = {
    "atius-srv-1": "10.11.1.11",
    "atius-srv-2": "10.12.1.12",
    "atius-srv-3": "10.13.1.13",
    "atius-srv-4": "10.14.1.14",
    "horistic-srv": "10.21.1.21",
}
ATTESTED_PEER_ORDER = ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv")
ATTESTED_PEER_PROFILES = {
    "atius-srv-1": "atius1",
    "atius-srv-2": "atius2",
    "atius-srv-3": "atius3",
    "horistic-srv": "horistic",
}

LOCKED_TCP_ENDPOINTS = (
    ("10.11.1.11", 53),
    ("10.11.1.11", 6432),
    ("10.11.1.11", 27124),
    ("10.11.1.11", 2379),
    ("10.11.1.11", 2380),
    ("10.13.1.13", 8088),
    ("10.13.1.13", 8202),
    ("10.13.1.13", 8203),
    ("10.13.1.13", 2379),
    ("10.13.1.13", 2380),
    ("10.21.1.21", 3115),
)

K3S_NETWORKS = (
    IPv4Network("10.42.0.0/16"),
    IPv4Network("10.43.0.0/16"),
)
K3S_INTERFACES = frozenset({"cni0", "flannel.1", "kube-ipvs0"})
RFC1918_NETWORKS = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
_SAFE_NAME = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
_SAFE_PROTOCOL = re.compile(r"[A-Za-z0-9_.-]{1,32}")
_SAFE_PODMAN_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_LATENCY = re.compile(rb"time[=<]([0-9]+(?:\.[0-9]+)?)\s*ms")
_SENSITIVE = re.compile(
    r"(?i)(-----BEGIN|bearer\s|password\s*[:=]|secret\s*[:=]|"
    r"api[_-]?key\s*[:=]|token\s*[:=]|AKIA[0-9A-Z]{16})"
)
_SHELL_TOKENS = (";", "|", "&", "$", "`", "<", ">", "\r", "\n", "\x00")

CommandResult = namedtuple("CommandResult", "returncode stdout stderr")
RunbookContract = namedtuple(
    "RunbookContract",
    "manifest_digest result_fields targets result_schema",
)


class ProbeError(RuntimeError):
    """Sanitized fail-closed rejection."""


def _route_schema(runbook_id: str, kind: str) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["runbook_id", "version", "target_display_name", "rows"],
        "properties": {
            "runbook_id": {"type": "string", "const": runbook_id},
            "version": {"type": "string", "const": "1"},
            "target_display_name": {"type": "string", "maxLength": 64},
            "rows": {
                "type": "array",
                "maxItems": 64,
                "items": {
                    "type": "object",
                    "required": ["kind", "destination", "device", "read_only"],
                    "properties": {
                        "kind": {"type": "string", "const": kind},
                        "destination": {"type": "string", "maxLength": 128},
                        "gateway": {"type": "string", "maxLength": 64},
                        "device": {"type": "string", "maxLength": 64},
                        "source": {"type": "string", "maxLength": 64},
                        "protocol": {"type": "string", "maxLength": 32},
                        "metric": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 2147483647,
                        },
                        "read_only": {"type": "boolean", "const": True},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }


REACHABILITY_SCHEMA = {
    "type": "object",
    "required": ["runbook_id", "version", "target_display_name", "rows"],
    "properties": {
        "runbook_id": {"type": "string", "const": "phase25.reachability"},
        "version": {"type": "string", "const": "1"},
        "target_display_name": {"type": "string", "maxLength": 64},
        "rows": {
            "type": "array",
            "maxItems": 64,
            "items": {
                "type": "object",
                "required": ["kind", "peer", "address", "probe", "ok", "status"],
                "properties": {
                    "kind": {"type": "string", "const": "reachability"},
                    "peer": {
                        "type": "string",
                        "enum": [
                            "atius-srv-1",
                            "atius-srv-2",
                            "atius-srv-3",
                            "atius-srv-4",
                            "horistic-srv",
                        ],
                    },
                    "address": {"type": "string", "maxLength": 255},
                    "probe": {"type": "string", "enum": ["icmp", "dns", "tcp"]},
                    "ok": {"type": "boolean"},
                    "status": {
                        "type": "string",
                        "enum": ["reachable", "unreachable", "unknown"],
                    },
                    "latency_ms": {"type": "integer", "minimum": 0, "maximum": 60000},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

COREDNS_SCHEMA = {
    "type": "object",
    "required": [
        "runbook_id",
        "version",
        "target_display_name",
        "peer_set_digest",
        "attestation_digest",
        "rows",
    ],
    "properties": {
        "runbook_id": {
            "type": "string",
            "const": "phase25.coredns-peer-readback",
        },
        "version": {"type": "string", "const": "1"},
        "target_display_name": {
            "type": "string",
            "enum": [
                "atius-srv-1",
                "atius-srv-2",
                "atius-srv-3",
                "horistic-srv",
            ],
        },
        "peer_set_digest": {
            "type": "string",
            "pattern": "^sha256:[0-9a-f]{64}$",
        },
        "attestation_digest": {
            "type": "string",
            "pattern": "^sha256:[0-9a-f]{64}$",
        },
        "rows": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": [
                    "resolver_role",
                    "resolver",
                    "name",
                    "record_type",
                    "answer",
                    "authoritative",
                    "status",
                ],
                "properties": {
                    "resolver_role": {
                        "type": "string",
                        "enum": ["primary", "reserve"],
                    },
                    "resolver": {
                        "type": "string",
                        "enum": ["10.11.1.11:53", "10.100.100.1:53"],
                    },
                    "name": {
                        "type": "string",
                        "enum": ["atius-srv-4", "atius-srv-4.atius.internal"],
                    },
                    "record_type": {"type": "string", "const": "A"},
                    "answer": {"type": "string", "const": "10.14.1.14"},
                    "authoritative": {"type": "boolean", "const": True},
                    "status": {"type": "string", "const": "resolved"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

_ROUTE_TARGETS = ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv")
_ALL_TARGETS = (
    "atius-srv-4",
    "atius-srv-1",
    "atius-srv-2",
    "atius-srv-3",
    "horistic-srv",
)
_RESULT_FIELDS = ("runbook_id", "version", "target_display_name", "rows")

PINNED_RUNBOOKS = {
    "phase25.wg100-routes": RunbookContract(
        "sha256:9164882a74ffa123ddaae79acba0c0abaad5c465f968ea61f7747f3c3cf025d9",
        _RESULT_FIELDS,
        _ROUTE_TARGETS,
        _route_schema("phase25.wg100-routes", "wg100_route"),
    ),
    "phase25.k3s-routes": RunbookContract(
        "sha256:9393edee3f0a04daa447bb93781d28196691622133e37f516299ce4a30d12423",
        _RESULT_FIELDS,
        _ROUTE_TARGETS,
        _route_schema("phase25.k3s-routes", "k3s_route"),
    ),
    "phase25.podman-routes": RunbookContract(
        "sha256:51ed6d3faa653fa67076d01ade327815550b7198bdff5efb5956b90df1f789c4",
        _RESULT_FIELDS,
        _ROUTE_TARGETS,
        _route_schema("phase25.podman-routes", "podman_route"),
    ),
    "phase25.lan-routes": RunbookContract(
        "sha256:d6d8801eb5b7e178dc3337c291eb9dc989b87b787f9cd422397e65a4f66aafb6",
        _RESULT_FIELDS,
        _ROUTE_TARGETS,
        _route_schema("phase25.lan-routes", "lan_route"),
    ),
    "phase25.reachability": RunbookContract(
        "sha256:a499d0b95c45e91f59ceeed50ea9ddeb81fa2bf2ad7425a81b878cd4adf79764",
        _RESULT_FIELDS,
        _ALL_TARGETS,
        REACHABILITY_SCHEMA,
    ),
    "phase25.coredns-peer-readback": RunbookContract(
        "sha256:7b71d4fd9742fc6ca509a2d3e702367c0269fc27fc446ba63b942928004a8510",
        (
            "runbook_id",
            "version",
            "target_display_name",
            "peer_set_digest",
            "attestation_digest",
            "rows",
        ),
        _ROUTE_TARGETS,
        COREDNS_SCHEMA,
    ),
}

_ARGUMENT_FLAGS = {
    "phase25.wg100-routes": (
        "--runbook",
        "--version",
        "--manifest-digest",
        "--target",
        "--max-rows",
        "--sentinel",
    ),
    "phase25.k3s-routes": (
        "--runbook",
        "--version",
        "--manifest-digest",
        "--target",
        "--max-rows",
        "--sentinel",
    ),
    "phase25.podman-routes": (
        "--runbook",
        "--version",
        "--manifest-digest",
        "--target",
        "--max-rows",
        "--sentinel",
    ),
    "phase25.lan-routes": (
        "--runbook",
        "--version",
        "--manifest-digest",
        "--target",
        "--max-rows",
        "--sentinel",
    ),
    "phase25.reachability": (
        "--runbook",
        "--version",
        "--manifest-digest",
        "--target",
        "--peers",
        "--probe-count",
        "--sentinel",
    ),
    "phase25.coredns-peer-readback": (
        "--runbook",
        "--version",
        "--manifest-digest",
        "--target-binding-digest",
        "--probe-digest",
        "--attestation-digest",
        "--target",
        "--peer-set-digest",
        "--projection-digest",
        "--short-name",
        "--fqdn",
        "--expected-address",
        "--primary-resolver",
        "--reserve-resolver",
        "--sentinel",
    ),
}


def canonical_manifest_digest(manifest: Mapping[str, Any]) -> str:
    canonical = dict(manifest)
    canonical.pop("digest", None)
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def validate_attestation_document(
    document: Mapping[str, Any],
    *,
    expected_digest: str | None = None,
    expected_target: str | None = None,
) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise ProbeError("attestation must be an object")
    payload = dict(document)
    if set(payload) != {
        "schema",
        "version",
        "target_binding_preimage",
        "target_peer_preimage",
        "peer_set_preimage",
        "projection_preimage",
        "digests",
        "digest",
    }:
        raise ProbeError("attestation fields are not exact")
    if (
        payload["schema"] != "atius.oci-admin-guest-probe-attestation/v1"
        or payload["version"] != "1"
    ):
        raise ProbeError("attestation schema is invalid")
    projection = payload["projection_preimage"]
    if not isinstance(projection, Mapping) or set(projection) != {
        "schema",
        "source",
        "records",
        "resolvers",
    }:
        raise ProbeError("projection preimage is invalid")
    source = projection["source"]
    if (
        projection["schema"] != "atius.internal-dns-projection-attestation/v1"
        or not isinstance(source, Mapping)
        or set(source) != {"authority", "repo_commit", "path", "digest"}
        or source["authority"] != "omni-srv-admin"
        or not _COMMIT.fullmatch(str(source["repo_commit"]))
        or source["path"] != "inventory/hosts/atius-srv-4.yaml"
        or not _DIGEST.fullmatch(str(source["digest"]))
    ):
        raise ProbeError("projection source is invalid")
    expected_records = [
        {"name": "atius-srv-4", "type": "A", "value": "10.14.1.14"},
        {
            "name": "atius-srv-4.atius.internal",
            "type": "A",
            "value": "10.14.1.14",
        },
    ]
    expected_resolvers = [
        {"role": "primary", "address": "10.11.1.11", "port": 53},
        {"role": "reserve", "address": "10.100.100.1", "port": 53},
    ]
    if projection["records"] != expected_records or projection["resolvers"] != expected_resolvers:
        raise ProbeError("projection contract has drifted")
    peers = payload["peer_set_preimage"]
    if not isinstance(peers, list) or len(peers) != 4:
        raise ProbeError("peer set preimage is incomplete")
    peer_fields = {
        "role",
        "profile_name",
        "region",
        "compartment_id",
        "instance_id",
        "display_name",
        "private_ip",
        "source_repo_commit",
        "source_path",
        "source_digest",
    }
    for name, peer in zip(ATTESTED_PEER_ORDER, peers, strict=True):
        if not isinstance(peer, Mapping) or set(peer) != peer_fields:
            raise ProbeError("peer preimage fields are not exact")
        if (
            peer["role"] != "dns-peer"
            or peer["profile_name"] != ATTESTED_PEER_PROFILES[name]
            or peer["region"] != "sa-saopaulo-1"
            or peer["display_name"] != name
            or peer["private_ip"] != EXPECTED_HOST_ADDRESSES[name]
            or not str(peer["compartment_id"]).startswith("ocid1.compartment.")
            or not str(peer["instance_id"]).startswith("ocid1.instance.")
            or peer["source_repo_commit"] != source["repo_commit"]
            or peer["source_path"] != f"inventory/hosts/{name}.yaml"
            or not _DIGEST.fullmatch(str(peer["source_digest"]))
        ):
            raise ProbeError("peer preimage identity is invalid")
    target_peer = payload["target_peer_preimage"]
    if not isinstance(target_peer, Mapping) or dict(target_peer) not in [dict(item) for item in peers]:
        raise ProbeError("target peer is not in attested fanout")
    if expected_target is not None and target_peer["display_name"] != expected_target:
        raise ProbeError("attestation target mismatch")
    binding = payload["target_binding_preimage"]
    if not isinstance(binding, Mapping) or set(binding) != {
        "target_role",
        "profile_name",
        "region",
        "compartment_id",
        "instance_id",
        "display_name",
        "source_repo_commit",
        "source_path",
        "source_digest",
        "projection_digest",
    }:
        raise ProbeError("target binding preimage fields are not exact")
    expected_binding = {
        "target_role": target_peer["role"],
        "profile_name": target_peer["profile_name"],
        "region": target_peer["region"],
        "compartment_id": target_peer["compartment_id"],
        "instance_id": target_peer["instance_id"],
        "display_name": target_peer["display_name"],
        "source_repo_commit": source["repo_commit"],
        "source_path": source["path"],
        "source_digest": source["digest"],
        "projection_digest": _canonical_digest(projection),
    }
    if dict(binding) != expected_binding:
        raise ProbeError("target binding preimage is inconsistent")
    expected_digests = {
        "target_binding": _canonical_digest(binding),
        "peer_set": _canonical_digest(peers),
        "projection": _canonical_digest(projection),
    }
    if not isinstance(payload["digests"], Mapping) or dict(payload["digests"]) != expected_digests:
        raise ProbeError("attestation preimage digests are invalid")
    base = {key: value for key, value in payload.items() if key != "digest"}
    digest = _canonical_digest(base)
    if payload["digest"] != digest or (expected_digest is not None and digest != expected_digest):
        raise ProbeError("attestation digest mismatch")
    canonical_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8") + b"\n"
    return {
        "document": payload,
        "canonical_bytes": canonical_bytes,
        "digest": digest,
        "target_binding_digest": expected_digests["target_binding"],
        "peer_set_digest": expected_digests["peer_set"],
        "projection_digest": expected_digests["projection"],
    }


def validate_attestation_bytes(
    raw: bytes,
    *,
    expected_digest: str | None = None,
    expected_target: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_ATTESTATION_BYTES:
        raise ProbeError("attestation size is invalid")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ProbeError) as exc:
        raise ProbeError("attestation JSON is invalid") from exc
    return validate_attestation_document(
        document,
        expected_digest=expected_digest,
        expected_target=expected_target,
    )


def load_installed_attestation() -> bytes:
    try:
        info = ATTESTATION_PATH.lstat()
        if (
            ATTESTATION_PATH.is_symlink()
            or not ATTESTATION_PATH.is_file()
            or info.st_nlink != 1
            or info.st_uid != 0
            or info.st_gid != 0
            or (info.st_mode & 0o777) != 0o400
            or not 1 <= info.st_size <= MAX_ATTESTATION_BYTES
        ):
            raise ProbeError("installed attestation identity is invalid")
        return ATTESTATION_PATH.read_bytes()
    except OSError as exc:
        raise ProbeError("installed attestation is unavailable") from exc


def self_digest() -> str:
    try:
        raw = Path(__file__).read_bytes()
    except OSError as exc:
        raise ProbeError("probe source is unavailable") from exc
    return f"sha256:{sha256(raw).hexdigest()}"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ProbeError("duplicate JSON key")
        value[key] = item
    return value


def _json_bytes(raw: bytes, *, max_items: int | None = None) -> Any:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ProbeError) as exc:
        raise ProbeError("invalid command JSON") from exc
    if max_items is not None and isinstance(value, list) and len(value) > max_items:
        raise ProbeError("command row bound exceeded")
    return value


def _safe_string(value: Any, *, pattern: re.Pattern[str], maximum: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise ProbeError("unsafe normalized string")
    if not pattern.fullmatch(value) or _SENSITIVE.search(value):
        raise ProbeError("unsafe normalized string")
    return value


def _safe_ipv4(value: Any) -> str:
    if not isinstance(value, str) or _SENSITIVE.search(value):
        raise ProbeError("invalid IPv4 value")
    try:
        parsed = ip_address(value)
    except ValueError as exc:
        raise ProbeError("invalid IPv4 value") from exc
    if not isinstance(parsed, IPv4Address):
        raise ProbeError("invalid IPv4 value")
    return str(parsed)


def validate_schema(value: Any, schema: Mapping[str, Any], *, path: str = "result") -> None:
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            raise ProbeError(f"{path} must be an object")
        properties = schema.get("properties") or {}
        missing = [key for key in schema.get("required") or [] if key not in value]
        if missing:
            raise ProbeError(f"{path} is incomplete")
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ProbeError(f"{path} is not closed")
        for key, item in value.items():
            if key in properties:
                validate_schema(item, properties[key], path=f"{path}.{key}")
    elif expected == "array":
        if not isinstance(value, list):
            raise ProbeError(f"{path} must be an array")
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise ProbeError(f"{path} is too short")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ProbeError(f"{path} is too long")
        for index, item in enumerate(value):
            validate_schema(item, schema.get("items") or {}, path=f"{path}[{index}]")
    elif expected == "string":
        if not isinstance(value, str):
            raise ProbeError(f"{path} must be a string")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ProbeError(f"{path} is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ProbeError(f"{path} is too long")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ProbeError(f"{path} does not match")
        if any(ord(char) < 32 for char in value) or _SENSITIVE.search(value):
            raise ProbeError(f"{path} is unsafe")
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ProbeError(f"{path} must be an integer")
        if "minimum" in schema and value < schema["minimum"]:
            raise ProbeError(f"{path} is too small")
        if "maximum" in schema and value > schema["maximum"]:
            raise ProbeError(f"{path} is too large")
    elif expected == "boolean":
        if not isinstance(value, bool):
            raise ProbeError(f"{path} must be a boolean")
    else:
        raise ProbeError(f"{path} uses an unsupported schema")
    if "const" in schema and value != schema["const"]:
        raise ProbeError(f"{path} constant mismatch")
    if "enum" in schema and value not in schema["enum"]:
        raise ProbeError(f"{path} is not allowlisted")


def _ordered_arguments(argv: Sequence[str]) -> dict[str, str]:
    if not isinstance(argv, Sequence) or isinstance(argv, (str, bytes)):
        raise ProbeError("argv is invalid")
    tokens = list(argv)
    if (
        len(tokens) < 3
        or tokens[0] != "execute"
        or tokens[1] != "--runbook"
        or not all(isinstance(token, str) and token for token in tokens)
    ):
        raise ProbeError("invocation is invalid")
    if sum(len(token.encode("utf-8")) for token in tokens) > 4096:
        raise ProbeError("invocation is oversized")
    if any(any(marker in token for marker in _SHELL_TOKENS) for token in tokens):
        raise ProbeError("invocation is unsafe")
    runbook_id = tokens[2]
    flags = _ARGUMENT_FLAGS.get(runbook_id)
    if flags is None or len(tokens) != 1 + (2 * len(flags)):
        raise ProbeError("runbook is not allowlisted")
    values: dict[str, str] = {}
    for index, flag in enumerate(flags):
        flag_index = 1 + (index * 2)
        if tokens[flag_index] != flag:
            raise ProbeError("argument order is invalid")
        values[flag] = tokens[flag_index + 1]
    return values


def _bounded_int(value: str, *, minimum: int, maximum: int) -> int:
    if not re.fullmatch(r"[0-9]+", value):
        raise ProbeError("integer argument is invalid")
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        raise ProbeError("integer argument is out of range")
    return parsed


def parse_invocation(argv: Sequence[str]) -> dict[str, Any]:
    values = _ordered_arguments(argv)
    runbook_id = values["--runbook"]
    contract = PINNED_RUNBOOKS[runbook_id]
    if (
        values["--version"] != VERSION
        or values["--manifest-digest"] != contract.manifest_digest
        or values["--sentinel"] != SENTINEL
    ):
        raise ProbeError("runbook identity mismatch")
    target = values["--target"]
    if target not in contract.targets:
        raise ProbeError("target is not allowlisted")
    parsed: dict[str, Any] = {
        "runbook_id": runbook_id,
        "target": target,
        "contract": contract,
    }
    if runbook_id.endswith("-routes"):
        parsed["max_rows"] = _bounded_int(values["--max-rows"], minimum=1, maximum=64)
    elif runbook_id == "phase25.reachability":
        expected_peers = (
            "atius-srv-1,atius-srv-2,atius-srv-3,horistic-srv"
            if target == "atius-srv-4"
            else "atius-srv-4"
        )
        if values["--peers"] != expected_peers:
            raise ProbeError("peer fanout mismatch")
        parsed["peers"] = tuple(expected_peers.split(","))
        parsed["probe_count"] = _bounded_int(
            values["--probe-count"], minimum=1, maximum=3
        )
    else:
        for flag in (
            "--target-binding-digest",
            "--probe-digest",
            "--attestation-digest",
            "--peer-set-digest",
            "--projection-digest",
        ):
            if not _DIGEST.fullmatch(values[flag]):
                raise ProbeError("digest argument is invalid")
        if values["--probe-digest"] != self_digest():
            raise ProbeError("probe digest mismatch")
        fixed = {
            "--short-name": "atius-srv-4",
            "--fqdn": "atius-srv-4.atius.internal",
            "--expected-address": "10.14.1.14",
            "--primary-resolver": "10.11.1.11:53",
            "--reserve-resolver": "10.100.100.1:53",
        }
        if any(values[flag] != expected for flag, expected in fixed.items()):
            raise ProbeError("CoreDNS projection is not fixed")
        parsed.update(
            {
                "target_binding_digest": values["--target-binding-digest"],
                "attestation_digest": values["--attestation-digest"],
                "peer_set_digest": values["--peer-set-digest"],
                "projection_digest": values["--projection-digest"],
            }
        )
    return parsed


def _allowed_command(argv: tuple[str, ...]) -> bool:
    if argv in {IP_ADDRESS_COMMAND, IP_ROUTE_COMMAND, PODMAN_LIST_COMMAND}:
        return True
    if (
        len(argv) == 4
        and argv[:3] == PODMAN_INSPECT_PREFIX
        and _SAFE_PODMAN_NAME.fullmatch(argv[3])
    ):
        return True
    if (
        len(argv) == 9
        and argv[0] == PING_BINARY
        and argv[1:3] == ("-n", "-c")
        and argv[4:8] == ("-W", "1", "-w", "5")
    ):
        try:
            return 1 <= int(argv[3]) <= 3 and argv[8] in EXPECTED_HOST_ADDRESSES.values()
        except ValueError:
            return False
    if (
        len(argv) == 3
        and argv[:2] == (GETENT_BINARY, "ahostsv4")
        and argv[2] in EXPECTED_HOST_ADDRESSES
    ):
        return True
    if len(argv) == 11 and argv[:6] == DIG_PREFIX:
        return (
            argv[6] in {"@10.11.1.11", "@10.100.100.1"}
            and argv[7:9] == ("-p", "53")
            and argv[9] in {"atius-srv-4", "atius-srv-4.atius.internal"}
            and argv[10] == "A"
        )
    return False


def subprocess_runner(argv: tuple[str, ...], timeout_seconds: int) -> CommandResult:
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=dict(CLEAN_ENVIRONMENT),
        close_fds=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise ProbeError("command timed out") from exc
    return CommandResult(process.returncode, stdout, stderr)


def _checked_run(
    runner: Callable[[tuple[str, ...], int], CommandResult],
    argv: tuple[str, ...],
    *,
    timeout_seconds: int,
    require_success: bool = True,
) -> CommandResult:
    if not _allowed_command(argv) or not 1 <= timeout_seconds <= MAX_COMMAND_TIMEOUT_SECONDS:
        raise ProbeError("command is not allowlisted")
    result = runner(argv, timeout_seconds)
    if not isinstance(result, tuple) or len(result) != 3:
        raise ProbeError("command result is invalid")
    if isinstance(result.returncode, bool) or not isinstance(result.returncode, int):
        raise ProbeError("command status is invalid")
    if not isinstance(result.stdout, bytes) or not isinstance(result.stderr, bytes):
        raise ProbeError("command output is invalid")
    if (
        len(result.stdout) > MAX_COMMAND_OUTPUT_BYTES
        or len(result.stderr) > MAX_COMMAND_OUTPUT_BYTES
        or len(result.stdout) + len(result.stderr) > MAX_COMMAND_OUTPUT_BYTES
    ):
        raise ProbeError("command output is oversized")
    if require_success and result.returncode != 0:
        raise ProbeError("command failed")
    return result


def _attest_target(
    target: str,
    *,
    runner: Callable[[tuple[str, ...], int], CommandResult],
    hostname_provider: Callable[[], str],
) -> None:
    try:
        hostname = hostname_provider().strip().lower().split(".", 1)[0]
    except Exception as exc:
        raise ProbeError("hostname attestation failed") from exc
    if hostname != target:
        raise ProbeError("hostname attestation failed")
    result = _checked_run(runner, IP_ADDRESS_COMMAND, timeout_seconds=5)
    payload = _json_bytes(result.stdout, max_items=64)
    if not isinstance(payload, list):
        raise ProbeError("address attestation is invalid")
    addresses: set[str] = set()
    for interface in payload:
        if not isinstance(interface, dict):
            raise ProbeError("address attestation is invalid")
        info = interface.get("addr_info", [])
        if not isinstance(info, list) or len(info) > 64:
            raise ProbeError("address attestation is invalid")
        for item in info:
            if isinstance(item, dict) and item.get("family") == "inet":
                addresses.add(_safe_ipv4(item.get("local")))
    if EXPECTED_HOST_ADDRESSES[target] not in addresses:
        raise ProbeError("private address attestation failed")


def _podman_networks(
    runner: Callable[[tuple[str, ...], int], CommandResult],
) -> tuple[tuple[str, str, IPv4Network, str | None], ...]:
    listed = _checked_run(runner, PODMAN_LIST_COMMAND, timeout_seconds=5)
    payload = _json_bytes(listed.stdout, max_items=32)
    if not isinstance(payload, list):
        raise ProbeError("Podman network list is invalid")
    names: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ProbeError("Podman network list is invalid")
        name = row.get("Name", row.get("name"))
        names.append(_safe_string(name, pattern=_SAFE_PODMAN_NAME, maximum=64))
    if len(names) != len(set(names)):
        raise ProbeError("Podman network names are duplicated")
    networks: list[tuple[str, str, IPv4Network, str | None]] = []
    for name in sorted(names):
        command = (*PODMAN_INSPECT_PREFIX, name)
        inspected = _checked_run(runner, command, timeout_seconds=5)
        document = _json_bytes(inspected.stdout, max_items=1)
        if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict):
            raise ProbeError("Podman network inspection is invalid")
        item = document[0]
        inspected_name = item.get("name", item.get("Name"))
        if inspected_name != name:
            raise ProbeError("Podman network identity mismatch")
        device = item.get("network_interface", item.get("NetworkInterface")) or name
        device = _safe_string(device, pattern=_SAFE_NAME, maximum=64)
        subnets = item.get("subnets", item.get("Subnets"))
        if not isinstance(subnets, list) or len(subnets) > 32:
            raise ProbeError("Podman network subnet list is invalid")
        for subnet in subnets:
            if not isinstance(subnet, dict):
                raise ProbeError("Podman network subnet is invalid")
            value = subnet.get("subnet", subnet.get("Subnet"))
            try:
                network = ip_network(value, strict=False)
            except (TypeError, ValueError) as exc:
                raise ProbeError("Podman network subnet is invalid") from exc
            if not isinstance(network, IPv4Network):
                raise ProbeError("Podman network subnet is invalid")
            gateway_value = subnet.get("gateway", subnet.get("Gateway"))
            gateway = _safe_ipv4(gateway_value) if gateway_value else None
            networks.append((name, device, network, gateway))
    if len(networks) > 64:
        raise ProbeError("Podman network row bound exceeded")
    return tuple(networks)


def _normalized_route(entry: Mapping[str, Any], *, kind: str) -> dict[str, Any] | None:
    destination_value = entry.get("dst")
    if destination_value in {None, "default"}:
        return None
    try:
        destination = ip_network(destination_value, strict=False)
    except (TypeError, ValueError) as exc:
        raise ProbeError("route destination is invalid") from exc
    if not isinstance(destination, IPv4Network):
        return None
    device = _safe_string(entry.get("dev"), pattern=_SAFE_NAME, maximum=64)
    row: dict[str, Any] = {
        "kind": kind,
        "destination": str(destination),
        "device": device,
        "read_only": True,
    }
    if entry.get("gateway"):
        row["gateway"] = _safe_ipv4(entry["gateway"])
    if entry.get("prefsrc"):
        row["source"] = _safe_ipv4(entry["prefsrc"])
    if entry.get("protocol"):
        row["protocol"] = _safe_string(
            entry["protocol"], pattern=_SAFE_PROTOCOL, maximum=32
        )
    if "metric" in entry:
        metric = entry["metric"]
        if isinstance(metric, bool) or not isinstance(metric, int) or not 0 <= metric <= 2147483647:
            raise ProbeError("route metric is invalid")
        row["metric"] = metric
    return row


def _is_k3s_route(network: IPv4Network, device: str) -> bool:
    return device in K3S_INTERFACES or device.startswith("flannel.") or any(
        network.subnet_of(expected) for expected in K3S_NETWORKS
    )


def _is_podman_route(
    network: IPv4Network,
    device: str,
    podman_networks: Sequence[tuple[str, str, IPv4Network, str | None]],
) -> bool:
    return (
        device.startswith(("podman", "cni-podman", "br-"))
        or any(device == item[1] for item in podman_networks)
        or any(network.subnet_of(item[2]) for item in podman_networks)
    )


def collect_routes(
    runbook_id: str,
    max_rows: int,
    runner: Callable[[tuple[str, ...], int], CommandResult],
) -> list[dict[str, Any]]:
    if runbook_id == "phase25.podman-routes":
        rows = [
            {
                "kind": "podman_route",
                "destination": str(network),
                **({"gateway": gateway} if gateway else {}),
                "device": device,
                "source": name,
                "read_only": True,
            }
            for name, device, network, gateway in _podman_networks(runner)
        ]
    else:
        podman_networks = (
            _podman_networks(runner) if runbook_id == "phase25.lan-routes" else ()
        )
        result = _checked_run(runner, IP_ROUTE_COMMAND, timeout_seconds=5)
        payload = _json_bytes(result.stdout, max_items=256)
        if not isinstance(payload, list):
            raise ProbeError("route list is invalid")
        rows = []
        for item in payload:
            if not isinstance(item, dict):
                raise ProbeError("route row is invalid")
            destination_value = item.get("dst")
            if destination_value in {None, "default"}:
                continue
            try:
                network = ip_network(destination_value, strict=False)
            except (TypeError, ValueError) as exc:
                raise ProbeError("route destination is invalid") from exc
            if not isinstance(network, IPv4Network):
                continue
            device = _safe_string(item.get("dev"), pattern=_SAFE_NAME, maximum=64)
            is_wg100 = device == "wg100"
            is_k3s = _is_k3s_route(network, device)
            is_podman = _is_podman_route(network, device, podman_networks)
            selected = False
            kind = ""
            if runbook_id == "phase25.wg100-routes":
                selected, kind = is_wg100, "wg100_route"
            elif runbook_id == "phase25.k3s-routes":
                selected, kind = is_k3s and not is_wg100, "k3s_route"
            elif runbook_id == "phase25.lan-routes":
                scope = item.get("scope")
                selected = (
                    not is_wg100
                    and not is_k3s
                    and not is_podman
                    and (
                        network.is_link_local
                        or scope == "link"
                        or any(network.subnet_of(expected) for expected in RFC1918_NETWORKS)
                    )
                )
                kind = "lan_route"
            if selected:
                normalized = _normalized_route(item, kind=kind)
                if normalized is not None:
                    rows.append(normalized)
    encoded_rows = {
        json.dumps(row, sort_keys=True, separators=(",", ":")): row for row in rows
    }
    ordered = [encoded_rows[key] for key in sorted(encoded_rows)]
    return ordered[:max_rows]


def _getent_resolver(
    name: str,
    runner: Callable[[tuple[str, ...], int], CommandResult],
) -> tuple[str, ...]:
    result = _checked_run(
        runner,
        (GETENT_BINARY, "ahostsv4", name),
        timeout_seconds=5,
        require_success=False,
    )
    if result.returncode != 0:
        return ()
    try:
        lines = result.stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ProbeError("resolver output is invalid") from exc
    if len(lines) > 32:
        raise ProbeError("resolver answer bound exceeded")
    values = sorted({_safe_ipv4(line.split()[0]) for line in lines if line.split()})
    if len(values) > 16:
        raise ProbeError("resolver answer bound exceeded")
    return tuple(values)


def _default_tcp_probe(address: str, port: int, timeout_seconds: int) -> tuple[bool, int]:
    started = monotonic()
    try:
        connection = socket.create_connection((address, port), timeout=timeout_seconds)
    except OSError:
        return False, 0
    try:
        latency = min(60000, max(0, round((monotonic() - started) * 1000)))
        return True, latency
    finally:
        connection.close()


def _ping_command(address: str, count: int) -> tuple[str, ...]:
    return (PING_BINARY, "-n", "-c", str(count), "-W", "1", "-w", "5", address)


def _ping_latency(raw: bytes) -> int | None:
    matches = _LATENCY.findall(raw)
    if not matches:
        return None
    try:
        value = round(float(matches[-1]))
    except ValueError:
        return None
    return min(60000, max(0, value))


def collect_reachability(
    *,
    peers: Sequence[str],
    probe_count: int,
    runner: Callable[[tuple[str, ...], int], CommandResult],
    resolver: Callable[[str], Sequence[str]],
    tcp_probe: Callable[[str, int, int], tuple[bool, int]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    peer_set = set(peers)
    if len(peer_set) != len(peers) or not peer_set <= set(EXPECTED_HOST_ADDRESSES):
        raise ProbeError("peer fanout is invalid")
    for peer in peers:
        address = EXPECTED_HOST_ADDRESSES[peer]
        ping = _checked_run(
            runner,
            _ping_command(address, probe_count),
            timeout_seconds=5,
            require_success=False,
        )
        ping_ok = ping.returncode == 0
        ping_row: dict[str, Any] = {
            "kind": "reachability",
            "peer": peer,
            "address": address,
            "probe": "icmp",
            "ok": ping_ok,
            "status": "reachable" if ping_ok else "unreachable",
        }
        latency = _ping_latency(ping.stdout)
        if latency is not None:
            ping_row["latency_ms"] = latency
        rows.append(ping_row)

        try:
            resolved = tuple(_safe_ipv4(item) for item in resolver(peer))
            if len(resolved) > 16:
                raise ProbeError("resolver answer bound exceeded")
            dns_ok = address in resolved
            dns_status = "reachable" if dns_ok else "unreachable"
        except ProbeError:
            raise
        except Exception:
            dns_ok, dns_status = False, "unknown"
        rows.append(
            {
                "kind": "reachability",
                "peer": peer,
                "address": address,
                "probe": "dns",
                "ok": dns_ok,
                "status": dns_status,
            }
        )

    address_to_peer = {value: key for key, value in EXPECTED_HOST_ADDRESSES.items()}
    for address, port in LOCKED_TCP_ENDPOINTS:
        peer = address_to_peer[address]
        if peer not in peer_set:
            continue
        try:
            ok, latency = tcp_probe(address, port, TCP_TIMEOUT_SECONDS)
            if not isinstance(ok, bool) or isinstance(latency, bool) or not isinstance(latency, int):
                raise ProbeError("TCP result is invalid")
            if not 0 <= latency <= 60000:
                raise ProbeError("TCP latency is invalid")
            status = "reachable" if ok else "unreachable"
        except ProbeError:
            raise
        except Exception:
            ok, latency, status = False, 0, "unknown"
        row = {
            "kind": "reachability",
            "peer": peer,
            "address": f"{address}:{port}",
            "probe": "tcp",
            "ok": ok,
            "status": status,
        }
        if ok:
            row["latency_ms"] = latency
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (row["peer"], row["probe"], row["address"]),
    )


def dig_command(resolver: str, name: str) -> tuple[str, ...]:
    address, port = resolver.rsplit(":", 1)
    return (*DIG_PREFIX, f"@{address}", "-p", port, name, "A")


def _parse_dig(raw: bytes, *, expected_address: str, expected_name: str) -> None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProbeError("DNS output is invalid") from exc
    if _SENSITIVE.search(text):
        raise ProbeError("DNS output is unsafe")
    header = next((line for line in text.splitlines() if "status:" in line), "")
    flags = next((line for line in text.splitlines() if line.startswith(";; flags:")), "")
    if "status: NOERROR" not in header or not re.search(r"\baa\b", flags):
        raise ProbeError("DNS answer is not authoritative")
    answers: list[str] = []
    for line in text.splitlines():
        if line.startswith(";;") or not line.strip():
            continue
        fields = line.split()
        if (
            len(fields) >= 5
            and fields[-2] == "A"
            and fields[0].rstrip(".") == expected_name
        ):
            answers.append(_safe_ipv4(fields[-1]))
    if answers != [expected_address]:
        raise ProbeError("DNS answer mismatch")


def collect_coredns(
    *,
    runner: Callable[[tuple[str, ...], int], CommandResult],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    resolvers = (
        ("primary", "10.11.1.11:53"),
        ("reserve", "10.100.100.1:53"),
    )
    names = ("atius-srv-4", "atius-srv-4.atius.internal")
    for resolver_role, resolver in resolvers:
        for name in names:
            result = _checked_run(
                runner,
                dig_command(resolver, name),
                timeout_seconds=5,
            )
            _parse_dig(
                result.stdout,
                expected_address="10.14.1.14",
                expected_name=name,
            )
            rows.append(
                {
                    "resolver_role": resolver_role,
                    "resolver": resolver,
                    "name": name,
                    "record_type": "A",
                    "answer": "10.14.1.14",
                    "authoritative": True,
                    "status": "resolved",
                }
            )
    return rows


def _build_payload(
    invocation: Mapping[str, Any],
    *,
    runner: Callable[[tuple[str, ...], int], CommandResult],
    resolver: Callable[[str], Sequence[str]],
    tcp_probe: Callable[[str, int, int], tuple[bool, int]],
) -> dict[str, Any]:
    runbook_id = invocation["runbook_id"]
    target = invocation["target"]
    if runbook_id.endswith("-routes"):
        rows = collect_routes(runbook_id, invocation["max_rows"], runner)
    elif runbook_id == "phase25.reachability":
        rows = collect_reachability(
            peers=invocation["peers"],
            probe_count=invocation["probe_count"],
            runner=runner,
            resolver=resolver,
            tcp_probe=tcp_probe,
        )
    else:
        rows = collect_coredns(runner=runner)
    payload: dict[str, Any] = {
        "runbook_id": runbook_id,
        "version": VERSION,
        "target_display_name": target,
    }
    if runbook_id == "phase25.coredns-peer-readback":
        payload["peer_set_digest"] = invocation["peer_set_digest"]
        payload["attestation_digest"] = invocation["attestation_digest"]
    payload["rows"] = rows
    validate_schema(payload, invocation["contract"].result_schema)
    if tuple(payload) != invocation["contract"].result_fields:
        raise ProbeError("result fields are not allowlisted")
    return payload


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[[tuple[str, ...], int], CommandResult] | None = None,
    hostname_provider: Callable[[], str] | None = None,
    resolver: Callable[[str], Sequence[str]] | None = None,
    tcp_probe: Callable[[str, int, int], tuple[bool, int]] | None = None,
    attestation_loader: Callable[[], bytes] | None = None,
    stdout: Any | None = None,
    stderr: Any | None = None,
) -> int:
    runner = runner or subprocess_runner
    hostname_provider = hostname_provider or socket.gethostname
    resolver = resolver or (lambda name: _getent_resolver(name, runner))
    tcp_probe = tcp_probe or _default_tcp_probe
    attestation_loader = attestation_loader or load_installed_attestation
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        invocation = parse_invocation(sys.argv[1:] if argv is None else argv)
        _attest_target(
            invocation["target"],
            runner=runner,
            hostname_provider=hostname_provider,
        )
        if invocation["runbook_id"] == "phase25.coredns-peer-readback":
            attestation = validate_attestation_bytes(
                attestation_loader(),
                expected_digest=invocation["attestation_digest"],
                expected_target=invocation["target"],
            )
            if (
                attestation["target_binding_digest"]
                != invocation["target_binding_digest"]
                or attestation["peer_set_digest"] != invocation["peer_set_digest"]
                or attestation["projection_digest"] != invocation["projection_digest"]
            ):
                raise ProbeError("attestation preimages do not match invocation")
        payload = _build_payload(
            invocation,
            runner=runner,
            resolver=resolver,
            tcp_probe=tcp_probe,
        )
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        line = f"{SENTINEL} {encoded}\n"
        if len(line.encode("utf-8")) > MAX_RESULT_BYTES:
            raise ProbeError("result is oversized")
    except Exception:
        stderr.write(SANITIZED_ERROR_LINE)
        return 2
    stdout.write(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
