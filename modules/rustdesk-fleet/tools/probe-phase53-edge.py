#!/usr/bin/env python3
"""Hermetic Phase 53 external-probe validator.

The module never opens sockets, starts SSH, or writes evidence. Collectors pass
bounded raw JSON bytes plus a pinned origin policy; only value-free frozen
receipts leave the validator.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import re
import sys
from typing import Any, Callable


class ProbeBlocked(RuntimeError):
    """A fail-closed probe-contract violation."""

    def __init__(self, blocker: str, receipt: dict[str, Any] | None = None) -> None:
        super().__init__(blocker)
        self.receipt = receipt


def _duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeBlocked("duplicate-json-key")
        result[key] = value
    return result


def _invalid_constant(_: str) -> None:
    raise ProbeBlocked("json-input-invalid")


def _shape_limits(value: Any, *, depth: int = 0) -> int:
    if depth > 24:
        raise ProbeBlocked("json-input-too-deep")
    if isinstance(value, dict):
        count = 1
        for key, nested in value.items():
            if not isinstance(key, str) or len(key) > 128:
                raise ProbeBlocked("json-input-invalid")
            count += _shape_limits(nested, depth=depth + 1)
    elif isinstance(value, list):
        count = 1 + sum(
            _shape_limits(nested, depth=depth + 1) for nested in value
        )
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ProbeBlocked("json-input-invalid")
    else:
        count = 1
    if count > 4096:
        raise ProbeBlocked("json-input-too-many-items")
    return count


def strict_json_bytes(raw: bytes, *, max_bytes: int = 1_048_576) -> dict[str, Any]:
    """Parse one bounded strict JSON object, preserving duplicate-key evidence."""

    if max_bytes <= 0 or len(raw) > max_bytes:
        raise ProbeBlocked("json-input-too-large")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_keys,
            parse_constant=_invalid_constant,
        )
    except ProbeBlocked:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProbeBlocked("json-input-invalid") from exc
    if not isinstance(payload, dict):
        raise ProbeBlocked("json-input-invalid")
    _shape_limits(payload)
    return payload


def _exact(value: Any, keys: set[str], blocker: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProbeBlocked(blocker)
    return value


def _utc(value: Any, blocker: str) -> datetime:
    if not isinstance(value, str):
        raise ProbeBlocked(blocker)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProbeBlocked(blocker) from exc
    if result.tzinfo is None:
        raise ProbeBlocked(blocker)
    return result.astimezone(timezone.utc)


def _digest(value: Any, blocker: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ProbeBlocked(blocker)
    return value


def _contains_sensitive(value: Any) -> bool:
    forbidden = {
        "authorization",
        "token",
        "secret",
        "private_key",
        "payload",
        "nonce",
        "argv",
        "stdout",
        "stderr",
        "credential",
        "headers",
        "environment",
    }
    if isinstance(value, dict):
        return any(
            any(word in str(key).lower() for word in forbidden)
            or _contains_sensitive(nested)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive(nested) for nested in value)
    if isinstance(value, str):
        lowered = value.lower()
        return bool(
            re.search(r"\bbearer\s+\S+", value, flags=re.IGNORECASE)
            or ("-----begin " in lowered and "private key-----" in lowered)
        )
    return False


@dataclass(frozen=True)
class RouteResult:
    rc: int
    session_attested: bool
    authenticated_envelope: bool


@dataclass(frozen=True)
class VerifiedProbeReceipt:
    transaction_id: str
    target: str
    completed_at: str
    origin_ids: tuple[str, str]
    transport_routes: tuple[tuple[str, str, tuple[str, ...]], ...]
    udp_attempt_ids: tuple[str, str]
    authorization_digest: str

    def value_free(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "scope": "public-ipv4",
            "transaction_id": self.transaction_id,
            "target": self.target,
            "completed_at": self.completed_at,
            "origin_ids": list(self.origin_ids),
            "origin_count": 2,
            "transport_routes": [
                {
                    "origin_id": origin,
                    "selected_route": selected,
                    "attempted_routes": list(routes),
                }
                for origin, selected, routes in self.transport_routes
            ],
            "tcp_positive_ports": [21115, 21116, 21117],
            "tcp_negative_ports": [21114, 21118, 21119],
            "udp_port": 21116,
            "udp_attempt_ids": list(self.udp_attempt_ids),
            "secret_material_present": False,
        }


@dataclass(frozen=True)
class VerifiedHostnameReceipt:
    transaction_id: str
    hostname: str
    expected_ipv4: str
    completed_at: str
    origin_ids: tuple[str, str]

    def value_free(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "scope": "public-hostname",
            "transaction_id": self.transaction_id,
            "hostname": self.hostname,
            "expected_ipv4": self.expected_ipv4,
            "completed_at": self.completed_at,
            "origin_ids": list(self.origin_ids),
            "origin_count": 2,
            "tcp_positive_ports": [21115, 21116, 21117],
            "tcp_negative_ports": [21114, 21118, 21119],
            "secret_material_present": False,
        }


def run_windows_private_first(
    run_route: Callable[[str], RouteResult],
) -> dict[str, Any]:
    """Select the Windows route without confusing remote exit 255 with SSH loss."""

    attempts: list[dict[str, Any]] = []
    try:
        private = run_route("private")
    except Exception as exc:
        raise ProbeBlocked(
            "windows-private-probe-failed",
            {"selected_route": None, "attempts": attempts},
        ) from exc
    if not isinstance(private, RouteResult) or type(private.rc) is not int:
        raise ProbeBlocked(
            "windows-private-probe-failed",
            {"selected_route": None, "attempts": attempts},
        )
    attempts.append(
        {
            "route": "private",
            "ssh_rc": private.rc,
            "session_attested": private.session_attested,
            "authenticated_envelope": private.authenticated_envelope,
        }
    )
    if private.rc == 0 and private.session_attested and private.authenticated_envelope:
        return {"selected_route": "private", "attempts": attempts}
    if (
        private.rc != 255
        or private.session_attested
        or private.authenticated_envelope
    ):
        raise ProbeBlocked(
            "windows-private-probe-failed",
            {"selected_route": None, "attempts": attempts},
        )
    try:
        public = run_route("public-native")
    except Exception as exc:
        raise ProbeBlocked(
            "windows-origin-unavailable-after-fallback",
            {"selected_route": None, "attempts": attempts},
        ) from exc
    if not isinstance(public, RouteResult) or type(public.rc) is not int:
        raise ProbeBlocked(
            "windows-origin-unavailable-after-fallback",
            {"selected_route": None, "attempts": attempts},
        )
    attempts.append(
        {
            "route": "public-native",
            "ssh_rc": public.rc,
            "session_attested": public.session_attested,
            "authenticated_envelope": public.authenticated_envelope,
        }
    )
    if not (
        public.rc == 0
        and public.session_attested
        and public.authenticated_envelope
    ):
        raise ProbeBlocked(
            "windows-origin-unavailable-after-fallback",
            {"selected_route": None, "attempts": attempts},
        )
    return {"selected_route": "public-native", "attempts": attempts}


def _policy(raw: bytes) -> tuple[str, int, dict[str, dict[str, Any]]]:
    value = _exact(
        strict_json_bytes(raw, max_bytes=65_536),
        {"schema_version", "transaction_id", "max_age_seconds", "origins"},
        "probe-policy-invalid",
    )
    if (
        value["schema_version"] != 1
        or not isinstance(value["transaction_id"], str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,96}", value["transaction_id"])
        or type(value["max_age_seconds"]) is not int
        or not 1 <= value["max_age_seconds"] <= 300
        or not isinstance(value["origins"], list)
        or len(value["origins"]) != 2
    ):
        raise ProbeBlocked("probe-policy-invalid")
    origins: dict[str, dict[str, Any]] = {}
    for raw_origin in value["origins"]:
        origin = _exact(
            raw_origin,
            {
                "origin_id",
                "origin_class",
                "host_identity_sha256",
                "executor_digest",
                "allowed_routes",
            },
            "probe-policy-invalid",
        )
        origin_id = origin["origin_id"]
        if (
            not isinstance(origin_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{3,96}", origin_id)
            or origin["origin_class"] not in {"windows", "independent-public"}
            or not isinstance(origin["allowed_routes"], list)
            or not origin["allowed_routes"]
            or any(
                route not in {"private", "public-native", "direct"}
                for route in origin["allowed_routes"]
            )
        ):
            raise ProbeBlocked("probe-policy-invalid")
        _digest(origin["host_identity_sha256"], "probe-policy-invalid")
        _digest(origin["executor_digest"], "probe-policy-invalid")
        if origin_id in origins:
            raise ProbeBlocked("probe-policy-invalid")
        origins[origin_id] = origin
    if {item["origin_class"] for item in origins.values()} != {
        "windows",
        "independent-public",
    }:
        raise ProbeBlocked("probe-policy-invalid")
    windows = [
        key for key, item in origins.items() if item["origin_class"] == "windows"
    ]
    if windows != ["GIOVANNI-W11-PC"]:
        raise ProbeBlocked("probe-policy-invalid")
    return value["transaction_id"], value["max_age_seconds"], origins


def _transport(
    raw: Any, *, origin_class: str, allowed_routes: list[str]
) -> tuple[str, tuple[str, ...]]:
    value = _exact(raw, {"selected_route", "attempts"}, "probe-transport-invalid")
    if not isinstance(value["attempts"], list):
        raise ProbeBlocked("probe-transport-invalid")
    attempts: list[dict[str, Any]] = []
    for raw_attempt in value["attempts"]:
        attempt = _exact(
            raw_attempt,
            {
                "route",
                "ssh_rc",
                "session_attested",
                "authenticated_envelope",
            },
            "probe-transport-invalid",
        )
        if (
            attempt["route"] not in allowed_routes
            or type(attempt["ssh_rc"]) is not int
            or type(attempt["session_attested"]) is not bool
            or type(attempt["authenticated_envelope"]) is not bool
        ):
            raise ProbeBlocked("probe-transport-invalid")
        attempts.append(attempt)
    private = [
        {
            "route": "private",
            "ssh_rc": 0,
            "session_attested": True,
            "authenticated_envelope": True,
        }
    ]
    fallback = [
        {
            "route": "private",
            "ssh_rc": 255,
            "session_attested": False,
            "authenticated_envelope": False,
        },
        {
            "route": "public-native",
            "ssh_rc": 0,
            "session_attested": True,
            "authenticated_envelope": True,
        },
    ]
    direct = [
        {
            "route": "direct",
            "ssh_rc": 0,
            "session_attested": True,
            "authenticated_envelope": True,
        }
    ]
    valid = (
        origin_class == "windows"
        and (
            (value["selected_route"] == "private" and attempts == private)
            or (value["selected_route"] == "public-native" and attempts == fallback)
        )
    ) or (
        origin_class == "independent-public"
        and value["selected_route"] == "direct"
        and attempts == direct
    )
    if not valid:
        raise ProbeBlocked(
            "probe-windows-transport-invalid"
            if origin_class == "windows"
            else "probe-transport-invalid"
        )
    return value["selected_route"], tuple(item["route"] for item in attempts)


def _tcp(raw: Any, *, digest: str, started: datetime, ended: datetime) -> None:
    value = _exact(
        raw, {"positive_control", "positive", "negative"}, "probe-tcp-schema-invalid"
    )
    control = _exact(
        value["positive_control"],
        {"port", "connected", "started_at", "ended_at"},
        "probe-tcp-schema-invalid",
    )
    if (
        type(control["port"]) is not int
        or not 1 <= control["port"] <= 65535
        or control["connected"] is not True
        or not started
        <= _utc(control["started_at"], "probe-tcp-window-invalid")
        < _utc(control["ended_at"], "probe-tcp-window-invalid")
        <= ended
    ):
        raise ProbeBlocked("probe-tcp-positive-control-failed")
    owners = {21115: "hbbs", 21116: "hbbs", 21117: "hbbr"}
    positive = value["positive"]
    if not isinstance(positive, list) or len(positive) != 3:
        raise ProbeBlocked("probe-tcp-correlation-invalid")
    seen: set[int] = set()
    for raw_item in positive:
        item = _exact(
            raw_item,
            {
                "attempt_id",
                "port",
                "connected",
                "started_at",
                "ended_at",
                "owner",
                "container",
                "cgroup",
                "image_digest",
                "socket_port",
                "counter_before",
                "counter_after",
                "owner_observed_at",
            },
            "probe-tcp-correlation-invalid",
        )
        port = item["port"]
        item_started = _utc(item["started_at"], "probe-tcp-correlation-invalid")
        item_ended = _utc(item["ended_at"], "probe-tcp-correlation-invalid")
        owner_at = _utc(item["owner_observed_at"], "probe-tcp-correlation-invalid")
        if (
            type(port) is not int
            or port not in owners
            or port in seen
            or not isinstance(item["attempt_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,96}", item["attempt_id"])
            or item["connected"] is not True
            or item["owner"] != owners[port]
            or item["container"] != f"atius-rustdesk-server-{owners[port]}"
            or item["cgroup"] != "atius-rustdesk-phase53.slice"
            or item["image_digest"] != digest
            or item["socket_port"] != port
            or type(item["counter_before"]) is not int
            or type(item["counter_after"]) is not int
            or item["counter_after"] - item["counter_before"] != 1
            or not started <= item_started <= owner_at <= item_ended <= ended
        ):
            raise ProbeBlocked("probe-tcp-correlation-invalid")
        seen.add(port)
    if seen != set(owners):
        raise ProbeBlocked("probe-tcp-correlation-invalid")
    negative = value["negative"]
    expected_negative = {21114, 21118, 21119}
    if not isinstance(negative, list) or len(negative) != 3:
        raise ProbeBlocked("probe-tcp-forbidden-open")
    seen_negative: set[int] = set()
    for raw_item in negative:
        item = _exact(
            raw_item,
            {
                "attempt_id",
                "port",
                "connected",
                "started_at",
                "ended_at",
                "drop_counter_before",
                "drop_counter_after",
            },
            "probe-tcp-schema-invalid",
        )
        port = item["port"]
        if (
            type(port) is not int
            or port not in expected_negative
            or port in seen_negative
            or item["connected"] is not False
            or not isinstance(item["attempt_id"], str)
            or type(item["drop_counter_before"]) is not int
            or type(item["drop_counter_after"]) is not int
            or item["drop_counter_after"] - item["drop_counter_before"] != 1
            or not started
            <= _utc(item["started_at"], "probe-tcp-window-invalid")
            < _utc(item["ended_at"], "probe-tcp-window-invalid")
            <= ended
        ):
            raise ProbeBlocked("probe-tcp-forbidden-open")
        seen_negative.add(port)
    if seen_negative != expected_negative:
        raise ProbeBlocked("probe-tcp-forbidden-open")


def _udp(
    raw: Any, *, target: str, digest: str, started: datetime, ended: datetime
) -> tuple[str, tuple[str, int, str, int], tuple[datetime, datetime]]:
    item = _exact(
        raw,
        {
            "attempt_id",
            "started_at",
            "ended_at",
            "source_ip",
            "source_port",
            "destination_ip",
            "destination_port",
            "counter_before",
            "counter_after",
            "capture",
            "owner",
            "disposable_attempt",
        },
        "probe-udp-schema-invalid",
    )
    attempt_id = item["attempt_id"]
    window_start = _utc(item["started_at"], "probe-udp-window-invalid")
    window_end = _utc(item["ended_at"], "probe-udp-window-invalid")
    if (
        not isinstance(attempt_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,96}", attempt_id)
        or item["disposable_attempt"] is not True
        or not started <= window_start < window_end <= ended
        or type(item["counter_before"]) is not int
        or type(item["counter_after"]) is not int
        or item["counter_after"] - item["counter_before"] != 1
    ):
        raise ProbeBlocked(
            "probe-udp-counter-invalid"
            if type(item["counter_before"]) is int
            and type(item["counter_after"]) is int
            else "probe-udp-attempt-invalid"
        )
    try:
        source = ipaddress.ip_address(item["source_ip"])
        destination = ipaddress.ip_address(item["destination_ip"])
    except ValueError as exc:
        raise ProbeBlocked("probe-udp-tuple-invalid") from exc
    if (
        not isinstance(source, ipaddress.IPv4Address)
        or not isinstance(destination, ipaddress.IPv4Address)
        or str(destination) != target
        or str(source) == target
        or type(item["source_port"]) is not int
        or not 1 <= item["source_port"] <= 65535
        or item["destination_port"] != 21116
    ):
        raise ProbeBlocked("probe-udp-tuple-invalid")
    capture = _exact(
        item["capture"],
        {
            "mode",
            "packet_count",
            "source_ip",
            "source_port",
            "destination_ip",
            "destination_port",
            "captured_at",
        },
        "probe-udp-capture-invalid",
    )
    captured = _utc(capture["captured_at"], "probe-udp-window-invalid")
    if (
        capture["source_ip"] != item["source_ip"]
        or capture["source_port"] != item["source_port"]
        or capture["destination_ip"] != item["destination_ip"]
        or capture["destination_port"] != item["destination_port"]
    ):
        raise ProbeBlocked("probe-udp-tuple-invalid")
    if (
        capture["mode"] != "metadata-only"
        or capture["packet_count"] != 1
        or not window_start <= captured <= window_end
    ):
        raise ProbeBlocked(
            "probe-udp-window-invalid"
            if not window_start <= captured <= window_end
            else "probe-udp-capture-invalid"
        )
    owner = _exact(
        item["owner"],
        {
            "process",
            "container",
            "cgroup",
            "image_digest",
            "socket_port",
            "observed_at",
        },
        "probe-udp-owner-invalid",
    )
    owner_at = _utc(owner["observed_at"], "probe-udp-owner-invalid")
    if owner != {
        "process": "hbbs",
        "container": "atius-rustdesk-server-hbbs",
        "cgroup": "atius-rustdesk-phase53.slice",
        "image_digest": digest,
        "socket_port": 21116,
        "observed_at": owner["observed_at"],
    } or not window_start <= owner_at <= window_end:
        raise ProbeBlocked("probe-udp-owner-invalid")
    return (
        attempt_id,
        (str(source), item["source_port"], str(destination), 21116),
        (window_start, window_end),
    )


def validate_external_probe_bytes(
    raw: bytes,
    *,
    policy_raw: bytes,
    expected_target: str,
    expected_digest: str,
    now: datetime,
) -> VerifiedProbeReceipt:
    """Validate raw observations against pinned origin identities and a trusted clock."""

    payload = strict_json_bytes(raw)
    if _contains_sensitive(payload):
        raise ProbeBlocked("probe-secret-surface")
    transaction_id, max_age, policies = _policy(policy_raw)
    root = _exact(
        payload,
        {
            "schema_version",
            "transaction_id",
            "target_kind",
            "target",
            "started_at",
            "completed_at",
            "origins",
        },
        "probe-schema-invalid",
    )
    try:
        target = ipaddress.ip_address(root["target"])
        expected = ipaddress.ip_address(expected_target)
    except ValueError as exc:
        raise ProbeBlocked("probe-target-invalid") from exc
    _digest(expected_digest, "probe-target-invalid")
    started = _utc(root["started_at"], "probe-window-invalid")
    completed = _utc(root["completed_at"], "probe-window-invalid")
    current = now.astimezone(timezone.utc) if now.tzinfo else None
    if (
        root["schema_version"] != 1
        or root["transaction_id"] != transaction_id
        or root["target_kind"] != "public-ipv4"
        or not isinstance(target, ipaddress.IPv4Address)
        or target != expected
    ):
        raise ProbeBlocked("probe-target-invalid")
    if (
        current is None
        or started >= completed
        or completed > current
        or (current - completed).total_seconds() > max_age
    ):
        raise ProbeBlocked("probe-window-invalid")
    origins = root["origins"]
    if not isinstance(origins, list) or len(origins) != 2:
        raise ProbeBlocked("probe-origin-count-invalid")

    origin_ids: list[str] = []
    egresses: list[str] = []
    identities: list[str] = []
    attempts: list[str] = []
    tuples: list[tuple[str, int, str, int]] = []
    udp_windows: list[tuple[datetime, datetime]] = []
    routes: list[tuple[str, str, tuple[str, ...]]] = []
    for raw_origin in origins:
        origin = _exact(
            raw_origin,
            {"origin_id", "origin_class", "attestation", "transport", "tcp", "udp"},
            "probe-origin-schema-invalid",
        )
        policy = policies.get(origin["origin_id"])
        if policy is None or origin["origin_class"] != policy["origin_class"]:
            raise ProbeBlocked("probe-origin-unattested")
        attestation = _exact(
            origin["attestation"],
            {
                "transaction_id",
                "target",
                "origin_id",
                "origin_class",
                "host_identity_sha256",
                "executor_digest",
                "egress_ipv4",
                "issued_at",
            },
            "probe-origin-unattested",
        )
        issued = _utc(attestation["issued_at"], "probe-origin-unattested")
        try:
            egress = ipaddress.ip_address(attestation["egress_ipv4"])
        except ValueError as exc:
            raise ProbeBlocked("probe-origin-unattested") from exc
        if (
            attestation["transaction_id"] != transaction_id
            or attestation["target"] != expected_target
            or attestation["origin_id"] != origin["origin_id"]
            or attestation["origin_class"] != origin["origin_class"]
            or attestation["host_identity_sha256"]
            != policy["host_identity_sha256"]
            or attestation["executor_digest"] != policy["executor_digest"]
            or not isinstance(egress, ipaddress.IPv4Address)
            or str(egress) == expected_target
            or not started <= issued <= completed
        ):
            raise ProbeBlocked("probe-origin-unattested")
        selected, attempted = _transport(
            origin["transport"],
            origin_class=origin["origin_class"],
            allowed_routes=policy["allowed_routes"],
        )
        _tcp(origin["tcp"], digest=expected_digest, started=started, ended=completed)
        attempt, tuple_value, udp_window = _udp(
            origin["udp"],
            target=expected_target,
            digest=expected_digest,
            started=started,
            ended=completed,
        )
        origin_ids.append(origin["origin_id"])
        egresses.append(str(egress))
        identities.append(attestation["host_identity_sha256"])
        attempts.append(attempt)
        tuples.append(tuple_value)
        udp_windows.append(udp_window)
        routes.append((origin["origin_id"], selected, attempted))
    if set(origin_ids) != set(policies):
        raise ProbeBlocked("probe-origin-classes-invalid")
    if len(set(egresses)) != 2 or len(set(identities)) != 2:
        raise ProbeBlocked("probe-origin-not-distinct")
    if len(set(attempts)) != 2 or len(set(tuples)) != 2:
        raise ProbeBlocked("probe-udp-replay")
    ordered_windows = sorted(udp_windows)
    if ordered_windows[0][1] >= ordered_windows[1][0]:
        raise ProbeBlocked("probe-udp-window-overlap")
    route_receipt = tuple(sorted(routes))
    sorted_ids = tuple(sorted(origin_ids))
    sorted_attempts = tuple(sorted(attempts))
    authorization = {
        "transaction_id": transaction_id,
        "target": expected_target,
        "completed_at": root["completed_at"],
        "origin_ids": sorted_ids,
        "transport_routes": route_receipt,
        "udp_attempt_ids": sorted_attempts,
    }
    digest = hashlib.sha256(
        json.dumps(
            authorization, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return VerifiedProbeReceipt(
        transaction_id=transaction_id,
        target=expected_target,
        completed_at=root["completed_at"],
        origin_ids=(sorted_ids[0], sorted_ids[1]),
        transport_routes=route_receipt,
        udp_attempt_ids=(sorted_attempts[0], sorted_attempts[1]),
        authorization_digest=digest,
    )


def validate_hostname_probe_bytes(
    raw: bytes,
    *,
    policy_raw: bytes,
    expected_hostname: str,
    expected_ipv4: str,
    now: datetime,
) -> VerifiedHostnameReceipt:
    """Validate post-publication hostname resolution from the same pinned origins."""

    payload = strict_json_bytes(raw, max_bytes=262_144)
    if _contains_sensitive(payload):
        raise ProbeBlocked("probe-secret-surface")
    transaction_id, max_age, policies = _policy(policy_raw)
    root = _exact(
        payload,
        {
            "schema_version",
            "transaction_id",
            "hostname",
            "expected_ipv4",
            "completed_at",
            "origins",
        },
        "hostname-probe-schema-invalid",
    )
    completed = _utc(root["completed_at"], "hostname-probe-window-invalid")
    current = now.astimezone(timezone.utc) if now.tzinfo else None
    try:
        expected = ipaddress.ip_address(expected_ipv4)
    except ValueError as exc:
        raise ProbeBlocked("hostname-probe-target-invalid") from exc
    if (
        root["schema_version"] != 1
        or root["transaction_id"] != transaction_id
        or root["hostname"] != expected_hostname
        or root["expected_ipv4"] != expected_ipv4
        or not isinstance(expected, ipaddress.IPv4Address)
        or current is None
        or completed > current
        or (current - completed).total_seconds() > max_age
        or not isinstance(root["origins"], list)
        or len(root["origins"]) != 2
    ):
        raise ProbeBlocked("hostname-probe-target-invalid")
    origin_ids: list[str] = []
    egresses: list[str] = []
    identities: list[str] = []
    for raw_origin in root["origins"]:
        origin = _exact(
            raw_origin,
            {
                "origin_id",
                "attestation",
                "resolved_addresses",
                "record_types",
                "checked_at",
                "tcp_positive_ports",
                "tcp_negative_ports",
            },
            "hostname-probe-schema-invalid",
        )
        policy = policies.get(origin["origin_id"])
        attestation = _exact(
            origin["attestation"],
            {
                "transaction_id",
                "target",
                "origin_id",
                "origin_class",
                "host_identity_sha256",
                "executor_digest",
                "egress_ipv4",
                "issued_at",
            },
            "hostname-probe-unattested",
        )
        if policy is None:
            raise ProbeBlocked("hostname-probe-unattested")
        checked = _utc(origin["checked_at"], "hostname-probe-window-invalid")
        issued = _utc(attestation["issued_at"], "hostname-probe-unattested")
        try:
            egress = ipaddress.ip_address(attestation["egress_ipv4"])
        except ValueError as exc:
            raise ProbeBlocked("hostname-probe-unattested") from exc
        if (
            attestation["transaction_id"] != transaction_id
            or attestation["target"] != expected_hostname
            or attestation["origin_id"] != origin["origin_id"]
            or attestation["origin_class"] != policy["origin_class"]
            or attestation["host_identity_sha256"]
            != policy["host_identity_sha256"]
            or attestation["executor_digest"] != policy["executor_digest"]
            or not isinstance(egress, ipaddress.IPv4Address)
            or origin["resolved_addresses"] != [expected_ipv4]
            or origin["record_types"] != ["A"]
            or origin["tcp_positive_ports"] != [21115, 21116, 21117]
            or origin["tcp_negative_ports"] != [21114, 21118, 21119]
            or issued > checked
            or checked > completed
            or (completed - checked).total_seconds() > max_age
        ):
            raise ProbeBlocked("hostname-probe-invalid")
        origin_ids.append(origin["origin_id"])
        egresses.append(str(egress))
        identities.append(attestation["host_identity_sha256"])
    if (
        set(origin_ids) != set(policies)
        or len(set(egresses)) != 2
        or len(set(identities)) != 2
    ):
        raise ProbeBlocked("hostname-probe-origin-not-distinct")
    ordered = tuple(sorted(origin_ids))
    return VerifiedHostnameReceipt(
        transaction_id=transaction_id,
        hostname=expected_hostname,
        expected_ipv4=expected_ipv4,
        completed_at=root["completed_at"],
        origin_ids=(ordered[0], ordered[1]),
    )


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-observation", action="store_true")
    parser.add_argument("--target")
    parser.add_argument("--digest")
    parser.add_argument("--policy-json")
    parser.add_argument("--now")
    args = parser.parse_args(argv)
    if not args.validate_observation:
        _emit(
            {
                "status": "BLOCKED",
                "blocker": "explicit-offline-observation-required",
                "network_performed": False,
            }
        )
        return 2
    try:
        if not all((args.target, args.digest, args.policy_json, args.now)):
            raise ProbeBlocked("probe-cli-arguments-required")
        receipt = validate_external_probe_bytes(
            sys.stdin.buffer.read(1_048_577),
            policy_raw=args.policy_json.encode("utf-8"),
            expected_target=args.target,
            expected_digest=args.digest,
            now=_utc(args.now, "probe-cli-now-invalid"),
        )
    except (ProbeBlocked, OSError) as exc:
        _emit(
            {
                "status": "BLOCKED",
                "blocker": str(exc),
                "network_performed": False,
            }
        )
        return 2
    _emit(receipt.value_free())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
