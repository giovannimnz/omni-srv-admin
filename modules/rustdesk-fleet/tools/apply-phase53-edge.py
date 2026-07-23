#!/usr/bin/env python3
"""Hermetic Phase 53 edge transaction primitives.

This module deliberately has no live backend and no command-line entry point.
Plan 05 must inject provider/root implementations after its explicit live gate.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
import uuid


OWNED_TABLE = "atius_rustdesk_phase53"
OWNERSHIP_MARKER = "ATIUS-PHASE53-EDGE"
EXPECTED_PRIORITY = 300
MAX_OCI_PAGES = 256
MAX_OCI_OBJECTS = 4096
MAX_OCI_RULES = 4096


class EdgeBlocked(RuntimeError):
    """A fail-closed edge contract violation."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _semantic_digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _walk_sensitive(payload: Any) -> bool:
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
    }
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(item in lowered for item in forbidden):
                return True
            if _walk_sensitive(value):
                return True
    elif isinstance(payload, list):
        return any(_walk_sensitive(value) for value in payload)
    elif isinstance(payload, str):
        lowered = payload.lower()
        if re.search(r"\bbearer\s+\S+", payload, flags=re.IGNORECASE):
            return True
        if "-----begin " in lowered and "private key-----" in lowered:
            return True
    return False


def _record_count(payload: Any) -> int:
    if isinstance(payload, dict):
        return len(payload) + sum(_record_count(value) for value in payload.values())
    if isinstance(payload, list):
        return len(payload) + sum(_record_count(value) for value in payload)
    return 0


def _validate_snapshot_shape(snapshot: dict[str, Any]) -> None:
    if set(snapshot) != {"revision", "state"} or not isinstance(snapshot["revision"], str):
        raise EdgeBlocked("snapshot-shape-invalid")
    state = snapshot.get("state")
    if not isinstance(state, dict) or set(state) != {"nft", "oci", "k3s"}:
        raise EdgeBlocked("snapshot-shape-invalid")


def _has_symlink_ancestor(path: Path) -> bool:
    current = path
    while current != current.parent:
        if current.is_symlink():
            return True
        current = current.parent
    return False


def store_bounded_snapshot(
    destination: Path,
    snapshot: dict[str, Any],
    *,
    max_bytes: int,
    max_records: int = 4096,
) -> dict[str, Any]:
    """Atomically persist a bounded value-free snapshot with root-only modes."""

    if max_bytes <= 0:
        raise EdgeBlocked("snapshot-limit-invalid")
    if max_records <= 0:
        raise EdgeBlocked("snapshot-record-limit")
    if destination.is_symlink():
        raise EdgeBlocked("snapshot-symlink-forbidden")
    if _has_symlink_ancestor(destination.parent):
        raise EdgeBlocked("snapshot-parent-symlink-forbidden")
    if _walk_sensitive(snapshot):
        raise EdgeBlocked("snapshot-secret-surface")
    encoded = _canonical_bytes(snapshot)
    if len(encoded) > max_bytes:
        raise EdgeBlocked("snapshot-too-large")
    _validate_snapshot_shape(snapshot)
    if _record_count(snapshot) > max_records:
        raise EdgeBlocked("snapshot-record-limit")

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination.parent, 0o700)
    temporary = destination.parent / f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        parent_flags = os.O_RDONLY | os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            parent_flags |= os.O_NOFOLLOW
        parent_fd = os.open(destination.parent, parent_flags)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest()}


def _page_objects(pages: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if pages.get("pagination_complete") is not True:
        raise EdgeBlocked("oci-pagination-incomplete")
    page_list = pages.get("pages")
    if not isinstance(page_list, list) or not page_list or len(page_list) > MAX_OCI_PAGES:
        raise EdgeBlocked("oci-pagination-incomplete")

    raw_tokens = [page.get("page_token") for page in page_list if isinstance(page, dict)]
    if (
        len(raw_tokens) != len(page_list)
        or any(not isinstance(token, str) for token in raw_tokens)
        or len(set(raw_tokens)) != len(raw_tokens)
    ):
        raise EdgeBlocked("oci-pagination-token-repeated")

    tokens: set[str] = set()
    security_lists: list[dict[str, Any]] = []
    network_security_groups: list[dict[str, Any]] = []
    attachments: list[dict[str, Any]] = []
    object_count = 0
    for index, page in enumerate(page_list):
        if not isinstance(page, dict):
            raise EdgeBlocked("oci-pagination-incomplete")
        token = page.get("page_token")
        assert isinstance(token, str)
        tokens.add(token)
        expected_next = page_list[index + 1].get("page_token") if index + 1 < len(page_list) else None
        if page.get("next_page") != expected_next:
            raise EdgeBlocked("oci-pagination-incomplete")
        for key, target in (
            ("security_lists", security_lists),
            ("network_security_groups", network_security_groups),
            ("attachments", attachments),
        ):
            values = page.get(key)
            if not isinstance(values, list):
                raise EdgeBlocked("oci-pagination-incomplete")
            target.extend(values)
            object_count += len(values)
            if object_count > MAX_OCI_OBJECTS:
                raise EdgeBlocked("oci-pagination-object-limit")
    return security_lists, network_security_groups, attachments


def audit_effective_oci_ingress(
    pages: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    """Audit the complete effective Security List plus attached NSG union."""

    security_lists, groups, attachments = _page_objects(pages)
    group_by_id = {str(group.get("id")): group for group in groups}
    security_list_by_id = {str(item.get("id")): item for item in security_lists}
    if len(group_by_id) != len(groups) or len(security_list_by_id) != len(security_lists):
        raise EdgeBlocked("oci-attachment-id-ambiguous")
    attached_group_ids = {
        str(group_id)
        for attachment in attachments
        for group_id in attachment.get("nsg_ids", [])
    }
    attached_security_list_ids = {
        str(item_id)
        for attachment in attachments
        for item_id in attachment.get("security_list_ids", [])
    }
    if not attached_group_ids.issubset(group_by_id) or not attached_security_list_ids.issubset(
        security_list_by_id
    ):
        raise EdgeBlocked("oci-attachment-unexpanded")
    effective_security_lists = [security_list_by_id[item_id] for item_id in attached_security_list_ids]
    effective_groups = [group_by_id[item_id] for item_id in attached_group_ids]

    rule_count = 0
    for container in [*security_lists, *groups]:
        rules = container.get("ingress_rules")
        if not isinstance(rules, list):
            raise EdgeBlocked("oci-rule-set-invalid")
        rule_count += len(rules)
        if rule_count > MAX_OCI_RULES:
            raise EdgeBlocked("oci-ingress-rule-limit")

    allowed_tcp = set(contract["public_ipv4_allowed"]["tcp"])
    allowed_udp = set(contract["public_ipv4_allowed"]["udp"])
    forbidden_tcp = set(contract["public_forbidden"]["tcp"])
    observed_tcp: set[int] = set()
    observed_udp: set[int] = set()
    ipv6: set[int] = set()

    phase_ports = (21114, 21115, 21116, 21117, 21118, 21119)
    for container in [*effective_security_lists, *effective_groups]:
        rules = container.get("ingress_rules")
        assert isinstance(rules, list)
        for rule in rules:
            protocol = str(rule.get("protocol", "")).lower()
            family = str(rule.get("family", "")).lower()
            try:
                first = int(rule["port_min"])
                last = int(rule["port_max"])
            except (KeyError, TypeError, ValueError) as exc:
                raise EdgeBlocked("oci-effective-ingress-broad") from exc
            if first < 0 or last > 65535 or first > last:
                raise EdgeBlocked("oci-rule-range-invalid")
            touches_phase = any(first <= port <= last for port in phase_ports)
            if not touches_phase and protocol not in {"all", "any", "*"}:
                continue
            if rule.get("source_type") != "CIDR_BLOCK":
                raise EdgeBlocked("oci-public-source-type-invalid")
            expected_source = "::/0" if family == "ipv6" else "0.0.0.0/0"
            if rule.get("source") != expected_source:
                raise EdgeBlocked("oci-public-source-invalid")
            if rule.get("stateless") is not False:
                raise EdgeBlocked("oci-public-stateless-invalid")
            if protocol in {"all", "any", "*"}:
                raise EdgeBlocked("oci-effective-ingress-broad")
            if family == "ipv6":
                if touches_phase:
                    raise EdgeBlocked("oci-effective-ingress-ipv6")
                continue
            if family != "ipv4" or protocol not in {"tcp", "udp"}:
                continue
            if protocol == "tcp" and any(first <= port <= last for port in forbidden_tcp):
                raise EdgeBlocked("oci-effective-ingress-forbidden")
            allowed = allowed_tcp if protocol == "tcp" else allowed_udp
            touched = {port for port in phase_ports if first <= port <= last}
            if touched - allowed:
                raise EdgeBlocked("oci-effective-ingress-forbidden")
            covered = {port for port in allowed if first <= port <= last}
            if covered:
                (observed_tcp if protocol == "tcp" else observed_udp).update(covered)

    if observed_tcp != allowed_tcp or observed_udp != allowed_udp:
        raise EdgeBlocked("oci-effective-ingress-missing")
    return {
        "pagination_complete": True,
        "security_list_ids": sorted(attached_security_list_ids),
        "network_security_group_ids": sorted(attached_group_ids),
        "attachment_ids": sorted(str(item["id"]) for item in attachments),
        "ipv4_tcp": sorted(observed_tcp),
        "ipv4_udp": sorted(observed_udp),
        "ipv6": sorted(ipv6),
    }


def audit_runtime_listeners(
    observed: list[dict[str, Any]], expected_digest: str
) -> dict[str, Any]:
    required = {
        ("hbbs", "tcp", 21115, expected_digest),
        ("hbbs", "tcp", 21116, expected_digest),
        ("hbbs", "tcp", 21118, expected_digest),
        ("hbbs", "udp", 21116, expected_digest),
        ("hbbr", "tcp", 21117, expected_digest),
        ("hbbr", "tcp", 21119, expected_digest),
    }
    actual = {
        (
            str(item.get("owner")),
            str(item.get("protocol")),
            int(item.get("port", -1)),
            str(item.get("digest")),
        )
        for item in observed
    }
    if actual != required:
        raise EdgeBlocked("listener-effective-drift")
    return {"listener_count": len(actual), "digest": expected_digest}


def render_nft_candidate(template: str, *, public_interface: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,32}", public_interface):
        raise EdgeBlocked("nft-interface-invalid")
    if template.count("__PHASE53_PUBLIC_INTERFACE__") < 1:
        raise EdgeBlocked("nft-interface-placeholder-missing")
    return template.replace("__PHASE53_PUBLIC_INTERFACE__", public_interface)


def _active_nft_source(candidate: str) -> str:
    without_hash_comments = "\n".join(
        line.split("#", 1)[0] for line in candidate.splitlines()
    )
    return re.sub(
        r'\bcomment\s+"(?:[^"\\]|\\.)*"\s*;?', "", without_hash_comments
    )


def validate_nft_candidate(
    candidate: str,
    *,
    contract_digest: str,
    public_interface: str,
) -> dict[str, Any]:
    active = _active_nft_source(candidate)
    lowered = active.lower()
    if OWNERSHIP_MARKER not in candidate:
        raise EdgeBlocked("nft-ownership-marker-invalid")
    if f"contract-sha256={contract_digest}" not in candidate:
        raise EdgeBlocked("nft-contract-digest-invalid")
    if f"table inet {OWNED_TABLE}" not in active:
        raise EdgeBlocked("nft-owned-table-invalid")
    if "flush ruleset" in lowered or any(
        token in lowered for token in ("k3s", "cni", "flannel", "kube-")
    ):
        raise EdgeBlocked("nft-foreign-scope-forbidden")
    if "type filter hook input priority 300; policy accept;" not in active:
        raise EdgeBlocked("nft-priority-invalid")
    interface_clause = f'iifname "{public_interface}"'
    if active.count(interface_clause) < 5:
        raise EdgeBlocked("nft-interface-invalid")
    if "meta nfproto ipv6 meta l4proto tcp tcp dport { 21114, 21115, 21116, 21117, 21118, 21119 } counter drop" not in active:
        raise EdgeBlocked("nft-ipv6-deny-invalid")
    if "meta nfproto ipv6 meta l4proto udp udp dport 21116 counter drop" not in active:
        raise EdgeBlocked("nft-ipv6-deny-invalid")
    if "ip protocol tcp tcp dport { 21115, 21116, 21117 } counter accept" not in active:
        raise EdgeBlocked("nft-ipv4-allow-invalid")
    if "ip protocol udp udp dport 21116 counter accept" not in active:
        raise EdgeBlocked("nft-ipv4-allow-invalid")
    if "ip protocol tcp tcp dport { 21114, 21118, 21119 } counter drop" not in active:
        raise EdgeBlocked("nft-ipv4-forbidden-invalid")
    return {
        "family": "inet",
        "table": OWNED_TABLE,
        "hook": "input",
        "priority": EXPECTED_PRIORITY,
        "public_interface": public_interface,
        "ipv4_tcp": [21115, 21116, 21117],
        "ipv4_udp": [21116],
        "ipv6_denied": [21114, 21115, 21116, 21117, 21118, 21119],
    }


def _parse_utc(value: Any, blocker: str) -> datetime:
    if not isinstance(value, str):
        raise EdgeBlocked(blocker)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EdgeBlocked(blocker) from exc
    if parsed.tzinfo is None:
        raise EdgeBlocked(blocker)
    return parsed.astimezone(timezone.utc)


def validate_edge_preflight(preflight: dict[str, Any]) -> None:
    if preflight.get("phase52_pass_count") != 11 or preflight.get("phase52_check_count") != 11:
        raise EdgeBlocked("phase52-current-pass-required")
    if preflight.get("selected_primary") != "horistic-srv":
        raise EdgeBlocked("selected-primary-invalid")
    consensus = preflight.get("address_consensus")
    if not isinstance(consensus, dict) or set(consensus) != {
        "oci-vnic-public-ipv4",
        "horistic-egress-ipv4",
        "ssh-horistic-srv.atius.com.br-a",
    }:
        raise EdgeBlocked("address-consensus-invalid")
    if len(set(consensus.values())) != 1 or not next(iter(consensus.values()), None):
        raise EdgeBlocked("address-consensus-invalid")
    for value in consensus.values():
        try:
            parsed_address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise EdgeBlocked("address-consensus-ipv4-invalid") from exc
        if not isinstance(parsed_address, ipaddress.IPv4Address):
            raise EdgeBlocked("address-consensus-ipv4-invalid")
    observed_at = _parse_utc(preflight.get("address_observed_at"), "address-consensus-stale")
    authorized_at = _parse_utc(preflight.get("authorization_time"), "address-consensus-stale")
    age = (authorized_at - observed_at).total_seconds()
    if age < 0 or age > 120:
        raise EdgeBlocked("address-consensus-stale")
    source_head = preflight.get("source_head")
    current_source_head = preflight.get("current_source_head")
    if (
        not isinstance(source_head, str)
        or not re.fullmatch(r"[0-9a-f]{40}", source_head)
        or source_head != current_source_head
    ):
        raise EdgeBlocked("source-head-drift")
    contract_digests = preflight.get("contract_digests")
    current_contract_digests = preflight.get("current_contract_digests")
    if (
        not isinstance(contract_digests, dict)
        or not contract_digests
        or contract_digests != current_contract_digests
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in contract_digests.values()
        )
    ):
        raise EdgeBlocked("contract-digest-drift")
    for key, blocker in (
        ("backups_retained", "retained-backups-required"),
        ("dns_closed", "closed-dns-required"),
        ("native_ingress_closed", "closed-native-ingress-required"),
        ("legacy_smokes", "legacy-smokes-required"),
        ("rollback_ready", "rollback-readiness-required"),
    ):
        if preflight.get(key) is not True:
            raise EdgeBlocked(blocker)


def _validate_preflight(preflight: dict[str, Any]) -> None:
    validate_edge_preflight(preflight)


class EdgeTransaction:
    """Pure state machine over an injected backend; performs no I/O itself."""

    def __init__(
        self,
        *,
        contract: dict[str, Any],
        backend: Any,
        fault_after: str | None = None,
    ) -> None:
        self.contract = copy.deepcopy(contract)
        self.backend = backend
        self.fault_after = fault_after
        self.state = "NEW"
        self._prestate: dict[str, Any] | None = None
        self._poststate: dict[str, Any] | None = None
        self._mutated = False
        self._rollback_receipt: dict[str, Any] | None = None

    def _fault(self, boundary: str) -> None:
        if self.fault_after == boundary:
            raise EdgeBlocked(f"fault-injected-{boundary}")

    def snapshot_edge(self) -> dict[str, Any]:
        snapshot = self.backend.snapshot()
        if not isinstance(snapshot, dict) or set(snapshot) != {"revision", "state"}:
            raise EdgeBlocked("edge-snapshot-invalid")
        if len(_canonical_bytes(snapshot)) > 1_048_576:
            raise EdgeBlocked("snapshot-too-large")
        self._prestate = copy.deepcopy(snapshot)
        self.state = "SNAPSHOTTED"
        self._fault("snapshot")
        return copy.deepcopy(snapshot)

    def _require_cas(self, expected_revision: str) -> None:
        try:
            current_revision = self.backend.current_revision()
        except Exception as exc:
            raise EdgeBlocked("edge-cas-read-failed") from exc
        if str(current_revision) != str(expected_revision):
            raise EdgeBlocked("edge-cas-stale")

    def _blocked_receipt(self, blocker: str) -> dict[str, Any]:
        self.state = "ROLLBACK_BLOCKED"
        self._rollback_receipt = {
            "state": self.state,
            "blocker": blocker,
            "manual_recovery_required": True,
        }
        return copy.deepcopy(self._rollback_receipt)

    def _try_containment(self) -> bool:
        try:
            self.backend.contain_owned_ingress()
        except Exception:
            return False
        return True

    def _observe_after_partial_write(self, surface: str) -> None:
        try:
            current = self.backend.observe()
        except Exception:
            self._try_containment()
            self._blocked_receipt(f"backend-{surface}-observe-failed")
            return
        if self._prestate is not None and current.get("state") != self._prestate.get("state"):
            self._mutated = True
            self._poststate = copy.deepcopy(current)
            self.rollback_edge()
        else:
            self._mutated = False
            self.state = "NEW"

    def apply_host_policy(self, candidate: str, public_interface: str) -> dict[str, Any]:
        if self._prestate is None:
            raise EdgeBlocked("edge-snapshot-required")
        semantics = validate_nft_candidate(
            candidate,
            contract_digest=sha256_file(
                Path(__file__).resolve().parents[1] / "contracts/phase53-edge.json"
            ),
            public_interface=public_interface,
        )
        self._require_cas(str(self._prestate["revision"]))
        try:
            self.backend.syntax_check_nft(candidate)
        except Exception as exc:
            raise EdgeBlocked("backend-nft-check-failed") from exc
        self._fault("nft-check")
        try:
            self.backend.apply_nft(candidate, semantics)
        except Exception as exc:
            self._observe_after_partial_write("nft")
            raise EdgeBlocked("backend-nft-apply-failed") from exc
        self._mutated = True
        try:
            self._poststate = self.backend.observe()
        except Exception as exc:
            self._try_containment()
            self._blocked_receipt("backend-nft-readback-failed")
            raise EdgeBlocked("backend-nft-readback-failed") from exc
        self._fault("nft-apply")
        observed = self._poststate["state"]["nft"].get("semantics")
        if observed != semantics:
            raise EdgeBlocked("nft-semantic-readback-drift")
        self._fault("nft-readback")
        self.state = "HOST_POLICY_APPLIED"
        return semantics

    def execute_edge(
        self,
        *,
        preflight: dict[str, Any],
        nft_candidate: str,
        public_interface: str,
        oci_candidate: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            self.snapshot_edge()
            _validate_preflight(preflight)
            self._fault("authorize")
            self.state = "AUTHORIZED"
            host = self.apply_host_policy(nft_candidate, public_interface)
            assert self._poststate is not None
            self._require_cas(str(self._poststate["revision"]))
            try:
                self.backend.apply_oci(oci_candidate)
            except Exception as exc:
                self._observe_after_partial_write("oci")
                raise EdgeBlocked("backend-oci-apply-failed") from exc
            self._mutated = True
            try:
                self._poststate = self.backend.observe()
            except Exception as exc:
                self._try_containment()
                self._blocked_receipt("backend-oci-readback-failed")
                raise EdgeBlocked("backend-oci-readback-failed") from exc
            self._fault("oci-apply")
            oci = audit_effective_oci_ingress(
                self._poststate["state"]["oci"], self.contract
            )
            self._fault("oci-audit")
            if self._prestate["state"].get("k3s") != self._poststate["state"].get("k3s"):
                raise EdgeBlocked("k3s-sentinel-drift")
            self.state = "EDGE_POLICY_APPLIED"
            return {"state": self.state, "host": host, "oci": oci}
        except EdgeBlocked:
            if self._mutated and self._rollback_receipt is None:
                self.rollback_edge()
            else:
                if self._rollback_receipt is None:
                    self.state = "NEW"
            raise
        except Exception as exc:
            if self._mutated and self._rollback_receipt is None:
                self.rollback_edge()
            elif self._rollback_receipt is None:
                self.state = "NEW"
            raise EdgeBlocked("edge-backend-unexpected-failure") from exc

    def rollback_edge(self) -> dict[str, Any]:
        if self._rollback_receipt is not None:
            return copy.deepcopy(self._rollback_receipt)
        if self._prestate is None:
            self.state = "NEW"
            return {"state": self.state}
        try:
            current = self.backend.observe()
        except Exception:
            self._try_containment()
            return self._blocked_receipt("rollback-observe-failed")
        if self._poststate is None or current["state"] != self._poststate["state"]:
            if not self._try_containment():
                return self._blocked_receipt("rollback-containment-failed")
            self.state = "CONTAINED_REQUIRES_MANUAL_RECOVERY"
            self._rollback_receipt = {
                "state": self.state,
                "manual_recovery_required": True,
            }
            return copy.deepcopy(self._rollback_receipt)
        try:
            self.backend.restore_if_current(
                self._prestate, expected_revision=str(current["revision"])
            )
        except Exception:
            self._try_containment()
            return self._blocked_receipt("rollback-restore-failed")
        try:
            restored = self.backend.observe()
        except Exception:
            self._try_containment()
            return self._blocked_receipt("rollback-readback-failed")
        if restored["state"] != self._prestate["state"]:
            self._try_containment()
            return self._blocked_receipt("rollback-semantic-drift")
        self.state = "ROLLED_BACK"
        self._rollback_receipt = {
            "state": self.state,
            "semantic_digest": _semantic_digest(restored["state"]),
            "manual_recovery_required": False,
        }
        return copy.deepcopy(self._rollback_receipt)


def snapshot_edge(transaction: EdgeTransaction) -> dict[str, Any]:
    return transaction.snapshot_edge()


def apply_host_policy(
    transaction: EdgeTransaction, candidate: str, public_interface: str
) -> dict[str, Any]:
    return transaction.apply_host_policy(candidate, public_interface)


def rollback_edge(transaction: EdgeTransaction) -> dict[str, Any]:
    return transaction.rollback_edge()


def _right_values(value: Any) -> tuple[int, ...]:
    if isinstance(value, int):
        return (value,)
    if isinstance(value, dict) and isinstance(value.get("set"), list):
        converted: list[int] = []
        for item in value["set"]:
            if not isinstance(item, int):
                raise EdgeBlocked("nft-live-readback-invalid")
            converted.append(item)
        return tuple(sorted(converted))
    raise EdgeBlocked("nft-live-readback-invalid")


def _normalize_protocol(value: Any) -> str | None:
    if value in {"tcp", 6}:
        return "tcp"
    if value in {"udp", 17}:
        return "udp"
    return None


def _rule_signature(rule: dict[str, Any], public_interface: str) -> tuple[str, str, tuple[int, ...], str] | None:
    interface: str | None = None
    family: str | None = None
    protocol: str | None = None
    ports: tuple[int, ...] | None = None
    verdict: str | None = None
    expressions = rule.get("expr")
    if not isinstance(expressions, list):
        return None
    for expression in expressions:
        if not isinstance(expression, dict):
            continue
        if "accept" in expression:
            verdict = "accept"
        if "drop" in expression:
            verdict = "drop"
        match = expression.get("match")
        if not isinstance(match, dict) or match.get("op") != "==":
            continue
        left = match.get("left")
        right = match.get("right")
        if not isinstance(left, dict):
            continue
        meta = left.get("meta")
        if isinstance(meta, dict):
            key = meta.get("key")
            if key == "iifname" and isinstance(right, str):
                interface = right
            elif key == "nfproto" and right in {"ipv4", "ipv6"}:
                family = str(right)
            elif key == "l4proto":
                protocol = _normalize_protocol(right)
        payload = left.get("payload")
        if isinstance(payload, dict):
            payload_protocol = payload.get("protocol")
            field = payload.get("field")
            if payload_protocol == "ip" and field == "protocol":
                family = "ipv4"
                protocol = _normalize_protocol(right)
            elif field == "dport" and payload_protocol in {"tcp", "udp"}:
                protocol = str(payload_protocol)
                ports = _right_values(right)
    if interface != public_interface or None in {family, protocol, ports, verdict}:
        return None
    assert family is not None and protocol is not None and ports is not None and verdict is not None
    return family, protocol, ports, verdict


def semantics_from_nft_json(payload: dict[str, Any], public_interface: str) -> dict[str, Any]:
    """Derive the owned policy semantics from independent ``nft -j`` output."""

    objects = payload.get("nftables")
    if not isinstance(objects, list):
        raise EdgeBlocked("nft-live-readback-invalid")
    table_ok = False
    chain_ok = False
    signatures: set[tuple[str, str, tuple[int, ...], str]] = set()
    for item in objects:
        if not isinstance(item, dict):
            continue
        table = item.get("table")
        if isinstance(table, dict) and table.get("family") == "inet" and table.get("name") == OWNED_TABLE:
            table_ok = True
        chain = item.get("chain")
        if (
            isinstance(chain, dict)
            and chain.get("family") == "inet"
            and chain.get("table") == OWNED_TABLE
            and chain.get("name") == "native_edge_input"
            and chain.get("hook") == "input"
            and chain.get("prio") == EXPECTED_PRIORITY
            and chain.get("policy") == "accept"
        ):
            chain_ok = True
        rule = item.get("rule")
        if isinstance(rule, dict) and rule.get("family") == "inet" and rule.get("table") == OWNED_TABLE:
            signature = _rule_signature(rule, public_interface)
            if signature is not None:
                signatures.add(signature)
    expected = {
        ("ipv6", "tcp", (21114, 21115, 21116, 21117, 21118, 21119), "drop"),
        ("ipv6", "udp", (21116,), "drop"),
        ("ipv4", "tcp", (21115, 21116, 21117), "accept"),
        ("ipv4", "udp", (21116,), "accept"),
        ("ipv4", "tcp", (21114, 21118, 21119), "drop"),
    }
    if not table_ok or not chain_ok or signatures != expected:
        raise EdgeBlocked("nft-live-semantic-readback-drift")
    return {
        "family": "inet",
        "table": OWNED_TABLE,
        "hook": "input",
        "priority": EXPECTED_PRIORITY,
        "public_interface": public_interface,
        "ipv4_tcp": [21115, 21116, 21117],
        "ipv4_udp": [21116],
        "ipv6_denied": [21114, 21115, 21116, 21117, 21118, 21119],
    }


def _infer_public_interface(candidate: str) -> str:
    active = _active_nft_source(candidate)
    matches = set(re.findall(r'iifname\s+"([A-Za-z0-9_.:-]{1,32})"', active))
    if len(matches) != 1:
        raise EdgeBlocked("nft-interface-invalid")
    return next(iter(matches))


def _collect_live_nft_semantics(public_interface: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["/usr/sbin/nft", "--json", "list", "table", "inet", OWNED_TABLE],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=15,
    )
    if completed.returncode != 0 or len(completed.stdout) > 1_048_576:
        raise EdgeBlocked("nft-live-readback-failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EdgeBlocked("nft-live-readback-invalid") from exc
    if not isinstance(payload, dict):
        raise EdgeBlocked("nft-live-readback-invalid")
    return semantics_from_nft_json(payload, public_interface)


def _verify_host_policy(args: argparse.Namespace) -> dict[str, Any]:
    candidate_path = Path(args.candidate)
    contract_path = Path(args.contract)
    candidate = candidate_path.read_text(encoding="utf-8")
    public_interface = args.public_interface or _infer_public_interface(candidate)
    expected = validate_nft_candidate(
        candidate,
        contract_digest=sha256_file(contract_path),
        public_interface=public_interface,
    )
    if args.observed_json:
        observed_payload = json.loads(Path(args.observed_json).read_text(encoding="utf-8"))
        if (
            not isinstance(observed_payload, dict)
            or set(observed_payload) != {"schema_version", "semantics"}
            or observed_payload.get("schema_version") != 1
            or observed_payload.get("semantics") != expected
        ):
            raise EdgeBlocked("nft-live-semantic-readback-drift")
    else:
        observed = _collect_live_nft_semantics(public_interface)
        if observed != expected:
            raise EdgeBlocked("nft-live-semantic-readback-drift")
    return {
        "mutation_performed": False,
        "semantic_readback_verified": True,
        "status": "PASS",
    }


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else os.sys.argv[1:])
    if "--verify-host-policy" not in arguments:
        print(
            json.dumps(
                {
                    "blocker": "explicit-verifier-mode-required",
                    "mutation_performed": False,
                    "status": "BLOCKED",
                },
                sort_keys=True,
            )
        )
        return 2
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--verify-host-policy", action="store_true")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--public-interface")
    parser.add_argument("--observed-json")
    try:
        args = parser.parse_args(arguments)
        result = _verify_host_policy(args)
    except (EdgeBlocked, OSError, ValueError, json.JSONDecodeError) as exc:
        blocker = str(exc) if isinstance(exc, EdgeBlocked) else "nft-verifier-input-invalid"
        print(
            json.dumps(
                {"blocker": blocker, "mutation_performed": False, "status": "BLOCKED"},
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
