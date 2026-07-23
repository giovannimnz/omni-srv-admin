#!/usr/bin/env python3
"""Hermetic Phase 53 edge transaction primitives.

This module deliberately has no live backend and no command-line entry point.
Plan 05 must inject provider/root implementations after its explicit live gate.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


OWNED_TABLE = "atius_rustdesk_phase53"
OWNERSHIP_MARKER = "ATIUS-PHASE53-EDGE"
EXPECTED_PRIORITY = 300
MAX_OCI_PAGES = 256
MAX_OCI_OBJECTS = 4096


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
    return False


def store_bounded_snapshot(
    destination: Path,
    snapshot: dict[str, Any],
    *,
    max_bytes: int,
) -> dict[str, Any]:
    """Atomically persist a bounded value-free snapshot with root-only modes."""

    if max_bytes <= 0:
        raise EdgeBlocked("snapshot-limit-invalid")
    if destination.is_symlink():
        raise EdgeBlocked("snapshot-symlink-forbidden")
    if _walk_sensitive(snapshot):
        raise EdgeBlocked("snapshot-secret-surface")
    encoded = _canonical_bytes(snapshot)
    if len(encoded) > max_bytes:
        raise EdgeBlocked("snapshot-too-large")

    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        parent_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
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
    group_ids = {str(group.get("id")) for group in groups}
    attached_ids = {
        str(group_id)
        for attachment in attachments
        for group_id in attachment.get("nsg_ids", [])
    }
    if not attached_ids.issubset(group_ids):
        raise EdgeBlocked("oci-attachment-unexpanded")

    allowed_tcp = set(contract["public_ipv4_allowed"]["tcp"])
    allowed_udp = set(contract["public_ipv4_allowed"]["udp"])
    forbidden_tcp = set(contract["public_forbidden"]["tcp"])
    observed_tcp: set[int] = set()
    observed_udp: set[int] = set()
    ipv6: set[int] = set()

    for container in [*security_lists, *groups]:
        rules = container.get("ingress_rules")
        if not isinstance(rules, list):
            raise EdgeBlocked("oci-rule-set-invalid")
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
            ports = set(range(first, last + 1))
            if protocol in {"all", "any", "*"}:
                raise EdgeBlocked("oci-effective-ingress-broad")
            if family == "ipv6":
                phase_ports = ports & set(range(21114, 21120))
                if phase_ports:
                    raise EdgeBlocked("oci-effective-ingress-ipv6")
                continue
            if family != "ipv4" or protocol not in {"tcp", "udp"}:
                continue
            if protocol == "tcp" and ports & forbidden_tcp:
                raise EdgeBlocked("oci-effective-ingress-forbidden")
            allowed = allowed_tcp if protocol == "tcp" else allowed_udp
            phase_ports = ports & set(range(21114, 21120))
            if phase_ports - allowed:
                raise EdgeBlocked("oci-effective-ingress-forbidden")
            if ports & allowed:
                (observed_tcp if protocol == "tcp" else observed_udp).update(ports & allowed)

    if observed_tcp != allowed_tcp or observed_udp != allowed_udp:
        raise EdgeBlocked("oci-effective-ingress-missing")
    return {
        "pagination_complete": True,
        "security_list_ids": sorted(str(item["id"]) for item in security_lists),
        "network_security_group_ids": sorted(str(item["id"]) for item in groups),
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


def validate_nft_candidate(
    candidate: str,
    *,
    contract_digest: str,
    public_interface: str,
) -> dict[str, Any]:
    lowered = candidate.lower()
    if OWNERSHIP_MARKER not in candidate:
        raise EdgeBlocked("nft-ownership-marker-invalid")
    if f"contract-sha256={contract_digest}" not in candidate:
        raise EdgeBlocked("nft-contract-digest-invalid")
    if f"table inet {OWNED_TABLE}" not in candidate:
        raise EdgeBlocked("nft-owned-table-invalid")
    if "flush ruleset" in lowered or any(
        token in lowered for token in ("k3s", "cni", "flannel", "kube-")
    ):
        raise EdgeBlocked("nft-foreign-scope-forbidden")
    if "type filter hook input priority 300; policy accept;" not in candidate:
        raise EdgeBlocked("nft-priority-invalid")
    interface_clause = f'iifname "{public_interface}"'
    if candidate.count(interface_clause) < 5:
        raise EdgeBlocked("nft-interface-invalid")
    if "ip6 nexthdr tcp tcp dport { 21114, 21115, 21116, 21117, 21118, 21119 } counter drop" not in candidate:
        raise EdgeBlocked("nft-ipv6-deny-invalid")
    if "ip6 nexthdr udp udp dport 21116 counter drop" not in candidate:
        raise EdgeBlocked("nft-ipv6-deny-invalid")
    if "ip protocol tcp tcp dport { 21115, 21116, 21117 } counter accept" not in candidate:
        raise EdgeBlocked("nft-ipv4-allow-invalid")
    if "ip protocol udp udp dport 21116 counter accept" not in candidate:
        raise EdgeBlocked("nft-ipv4-allow-invalid")
    if "ip protocol tcp tcp dport { 21114, 21118, 21119 } counter drop" not in candidate:
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


def _validate_preflight(preflight: dict[str, Any]) -> None:
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
    for key, blocker in (
        ("backups_retained", "retained-backups-required"),
        ("dns_closed", "closed-dns-required"),
        ("native_ingress_closed", "closed-native-ingress-required"),
        ("legacy_smokes", "legacy-smokes-required"),
        ("rollback_ready", "rollback-readiness-required"),
    ):
        if preflight.get(key) is not True:
            raise EdgeBlocked(blocker)


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
        if str(self.backend.current_revision()) != str(expected_revision):
            raise EdgeBlocked("edge-cas-stale")

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
        self.backend.syntax_check_nft(candidate)
        self._fault("nft-check")
        self.backend.apply_nft(candidate, semantics)
        self._mutated = True
        self._poststate = self.backend.observe()
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
            self.backend.apply_oci(oci_candidate)
            self._mutated = True
            self._poststate = self.backend.observe()
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
            if self._mutated:
                self.rollback_edge()
            else:
                self.state = "NEW"
            raise

    def rollback_edge(self) -> dict[str, Any]:
        if self._rollback_receipt is not None:
            return copy.deepcopy(self._rollback_receipt)
        if self._prestate is None:
            self.state = "NEW"
            return {"state": self.state}
        current = self.backend.observe()
        if self._poststate is None or current["state"] != self._poststate["state"]:
            self.backend.contain_owned_ingress()
            self.state = "CONTAINED_REQUIRES_MANUAL_RECOVERY"
            self._rollback_receipt = {"state": self.state}
            return copy.deepcopy(self._rollback_receipt)
        self.backend.restore(self._prestate)
        restored = self.backend.observe()
        if restored["state"] != self._prestate["state"]:
            self.backend.contain_owned_ingress()
            self.state = "CONTAINED_REQUIRES_MANUAL_RECOVERY"
        else:
            self.state = "ROLLED_BACK"
        self._rollback_receipt = {
            "state": self.state,
            "semantic_digest": _semantic_digest(restored["state"]),
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
