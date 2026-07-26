from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
ADAPTER_PATH = REPO / "modules/fleet-control-plane/scripts/phase54_probe_adapters.py"
SPEC = importlib.util.spec_from_file_location("phase54_probe_adapters", ADAPTER_PATH)
assert SPEC and SPEC.loader
adapters = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = adapters
SPEC.loader.exec_module(adapters)


def _evidence(tmp_path: Path, plan: str, stage: str | None) -> Path:
    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(
            {
                "schema": "phase54.evidence.v1",
                "plan": plan,
                "stage": stage,
                "redacted": True,
            }
        ),
        encoding="utf-8",
    )
    return path


def _spec(plan: str, stage: str | None, check_id: str) -> adapters.AdapterSpec:
    return adapters.REGISTRY[(plan, stage, check_id)]


def test_registry_exactly_covers_every_remote_plan_stage_check() -> None:
    expected = {
        (plan, stage, check_id)
        for plan, stages in adapters.STAGES.items()
        for stage in stages
        for check_id in adapters.BASE_CHECKS[plan]
    }
    assert set(adapters.REGISTRY) == expected
    assert all(
        spec.transport not in {"remote-unimplemented", "stage-contract"}
        for spec in adapters.REGISTRY.values()
    )


def test_list_cli_is_machine_readable_for_every_plan() -> None:
    for plan in adapters.STAGES:
        completed = subprocess.run(
            [sys.executable, str(ADAPTER_PATH), "list", "--plan", plan],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert completed.returncode == 0, (plan, completed.stderr)
        payload = json.loads(completed.stdout)
        assert payload["schema"] == adapters.SCHEMA_COVERAGE
        assert payload["plan"] == plan
        assert payload["status"] == "READY"
        assert {
            (item["stage"], item["check_id"]) for item in payload["keys"]
        } == {
            (stage, check_id)
            for stage in adapters.STAGES[plan]
            for check_id in adapters.BASE_CHECKS[plan]
        }


def test_probe_requires_canonical_hash_bound_evidence(tmp_path: Path, monkeypatch) -> None:
    path = _evidence(tmp_path, "54-02", "preflight")
    raw = path.read_bytes()
    expected_hash = hashlib.sha256(raw).hexdigest()
    spec = _spec("54-02", "preflight", "live_inventory")

    def fake_execute(_spec, evidence, evidence_path, evidence_sha256):
        assert evidence["plan"] == "54-02"
        assert evidence_path == path
        assert evidence_sha256 == expected_hash
        return True, {"evidence_sha256": evidence_sha256}, "req-1", b"owner-readback"

    monkeypatch.setattr(adapters, "_execute", fake_execute)
    payload = adapters._observation(spec, path)
    assert payload["status"] == "PASS"
    assert payload["read_only"] is True
    assert payload["mutation_performed"] is False
    assert payload["secret_material_present"] is False
    assert payload["evidence_sha256"] == expected_hash
    assert payload["normalized"]["evidence_sha256"] == expected_hash
    assert len(payload["observed_sha256"]) == 64

    wrong = _evidence(tmp_path, "54-03", None)
    payload = adapters._observation(spec, wrong)
    assert payload["status"] == "BLOCK"
    assert payload["evidence_sha256"] is None


def test_ssh_wireguard_and_be3_commands_are_fixed_safe_and_read_only() -> None:
    flags = adapters.SSH_FLAGS
    for required in (
        "-n",
        "-T",
        "BatchMode=yes",
        "IdentitiesOnly=yes",
        "ClearAllForwardings=yes",
        "ExitOnForwardFailure=yes",
        "StrictHostKeyChecking=yes",
    ):
        assert required in flags
    assert "StrictHostKeyChecking=no" not in flags

    wg = adapters.SSH_COMMANDS["wireguard"]
    for forbidden in ("dump", "showconf", "private-key", "wg set "):
        assert forbidden not in wg
    for field in (
        "peers",
        "allowed-ips",
        "latest-handshakes",
        "endpoints",
        "transfer",
    ):
        assert field in wg

    be3 = adapters.SSH_COMMANDS["be3_capture"]
    assert adapters.BE3_COMMIT in be3
    assert adapters.BE3_CAPTURE_PATH in be3
    assert "--output" in be3
    assert "chromium" not in be3
    assert "export-be3-native-readonly" not in be3
    assert "password=" not in be3.lower()
    assert "username=" not in be3.lower()


def test_oci_operations_are_fixed_and_security_ids_come_from_hash_bound_evidence(
    tmp_path: Path,
) -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert '"name": "oci_read"' in source
    assert "ATIUS_MCP_TOKEN" in source
    assert "print(token" not in source
    assert "json.dumps(token" not in source
    for operation in (
        "peering.inventory",
        "peering.address_plan",
        "peering.drg_status",
        "network.security_list",
    ):
        assert operation in source

    evidence = _evidence(tmp_path, "54-04", "apply")
    security_id = "ocid1.securitylist.oc1.sa-saopaulo-1.test"
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["operation"] = {"security_list_id": security_id}
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    assert adapters._security_arguments(payload, evidence) == [
        {
            "profile_name": "horistic",
            "region": "sa-saopaulo-1",
            "security_list_id": security_id,
        }
    ]


def test_address_plan_normalization_blocks_10_21_and_wrong_target() -> None:
    good = adapters._normalize_address_plan(
        {
            "applies_live_oci_writes": False,
            "target_ranges": {
                "horistic": {
                    "vcn_cidr": "10.31.0.0/16",
                    "server_subnet_cidr": "10.31.1.0/24",
                    "stable_host_ip": "10.31.1.31",
                    "service_subnet_cidr": "10.31.2.0/24",
                }
            },
            "operation_plan_previews": [{"action": "vcn.create"}],
        }
    )
    spec = _spec("54-03", None, "builder_targets")
    normalized = {"operation": "peering.address_plan", "semantic": good}
    assert adapters._oci_probe_passes(spec, normalized)

    wrong = json.loads(json.dumps(good))
    wrong["target"]["vcn"] = "10.21.0.0/16"
    wrong["target_contains_10_21"] = True
    assert not adapters._oci_probe_passes(
        spec, {"operation": "peering.address_plan", "semantic": wrong}
    )


def test_inventory_and_drg_normalizers_require_real_current_and_routes() -> None:
    inventory = adapters._normalize_inventory(
        {
            "sides": [
                {
                    "profile_name": "horistic",
                    "vcn_cidrs": ["10.21.0.0/16"],
                    "subnet_cidrs": ["10.21.1.0/24"],
                    "current_host_ips": ["10.21.1.21"],
                }
            ]
        }
    )
    assert adapters._oci_probe_passes(
        _spec("54-02", "preflight", "live_inventory"),
        {"operation": "peering.inventory", "semantic": inventory},
    )
    inventory["current_host_ips"] = []
    assert not adapters._oci_probe_passes(
        _spec("54-02", "preflight", "live_inventory"),
        {"operation": "peering.inventory", "semantic": inventory},
    )

    drg = adapters._normalize_drg(
        {
            "applies_live_oci_writes": False,
            "attachments": [
                {
                    "profile_name": "atius1",
                    "attachment_id": "ocid1.drgattachment.x",
                    "vcn_id": "ocid1.vcn.x",
                    "state": "attached_to_central",
                    "blocked": False,
                }
            ],
            "route_tables": [
                {
                    "profile_name": "atius1",
                    "route_table_id": "ocid1.drgroutetable.x",
                    "route_rules": [{"destination": "10.31.0.0/16"}],
                    "blocked": False,
                }
            ],
            "route_distributions": [
                {
                    "profile_name": "atius1",
                    "attachment_id": "ocid1.drgattachment.x",
                    "distribution_id": "ocid1.drgroutedistribution.x",
                    "blocked": False,
                }
            ],
            "blockers": [],
        }
    )
    assert drg["route_tables"][0]["target_cidrs"] == ["10.31.0.0/16"]
    drg["blockers"] = ["missing reverse route"]
    assert not adapters._oci_probe_passes(
        _spec("54-04", "apply", "drg_bidirectional"),
        {"operation": "peering.drg_status", "semantic": drg},
    )


def test_public_ip_baseline_uses_primary_10_0_binding_not_secondary_drg() -> None:
    semantic = {
        "reserved_public_ips": [
            {
                "public_ip_ocid": "ocid1.publicip.baseline",
                "label": "horistic-srv-1",
                "address": adapters.PUBLIC_IP,
                "private_ip_ocid": "ocid1.privateip.primary",
                "lifecycle_state": "ASSIGNED",
                "lifetime": "RESERVED",
            }
        ],
        "private_ips": [
            {
                "private_ip_ocid": "ocid1.privateip.primary",
                "address": adapters.BASELINE_PUBLIC_BINDING,
                "vnic_ocid": "ocid1.vnic.primary",
                "subnet_ocid": "ocid1.subnet.primary",
            },
            {
                "private_ip_ocid": "ocid1.privateip.secondary",
                "address": adapters.CURRENT_HOST,
                "vnic_ocid": "ocid1.vnic.secondary",
                "subnet_ocid": "ocid1.subnet.secondary",
            },
        ],
    }
    normalized = {"operation": "inventory.get", "semantic": semantic}
    spec = _spec("54-02", "preflight", "public_ip_baseline")
    assert adapters._oci_probe_passes(spec, normalized)

    wrong = json.loads(json.dumps(semantic))
    wrong["private_ips"][0]["address"] = adapters.CURRENT_HOST
    assert not adapters._oci_probe_passes(
        spec,
        {"operation": "inventory.get", "semantic": wrong},
    )


def test_security_normalization_is_directional_and_rejects_missing_rules() -> None:
    security_id = "ocid1.securitylist.oc1.test"
    semantic = adapters._normalize_security(
        [
            {
                "ocid": security_id,
                "vcn_id": "ocid1.vcn.oc1.test",
                "lifecycle_state": "AVAILABLE",
                "ingress_security_rules": [
                    {"source": "10.11.0.0/16", "protocol": "all"}
                ],
                "egress_security_rules": [
                    {"destination": "0.0.0.0/0", "protocol": "all"}
                ],
            }
        ],
        [security_id],
    )
    row = semantic["security_lists"][0]
    assert row["ingress"][0]["direction"] == "INGRESS"
    assert row["egress"][0]["direction"] == "EGRESS"
    assert adapters._oci_probe_passes(
        _spec("54-04", "apply", "security_bidirectional"),
        {"operation": "network.security_list", "semantic": semantic},
    )
    semantic["security_lists"][0]["egress"] = []
    assert not adapters._oci_probe_passes(
        _spec("54-04", "apply", "security_bidirectional"),
        {"operation": "network.security_list", "semantic": semantic},
    )


def _dig(marker: str, status: str, answer: str = "", *, aa: bool = False) -> str:
    flags = "qr aa rd ra" if aa else "qr rd ra"
    return (
        f"{marker}\n"
        f";; ->>HEADER<<- opcode: QUERY, status: {status}, id: 1\n"
        f";; flags: {flags}; QUERY: 1, ANSWER: {int(bool(answer))}\n"
        f"{answer}\n"
    )


def _dns_outputs(
    address: str,
    reverse: str,
    *,
    baseline_gap: bool = False,
) -> tuple[bytes, bytes]:
    fqdn = adapters.DNS_NAME
    auth_a = (
        _dig("__AUTH_A__", "NXDOMAIN", aa=False)
        if baseline_gap
        else _dig("__AUTH_A__", "NOERROR", f"{fqdn}. 300 IN A {address}", aa=True)
    )
    auth_ptr = (
        _dig(
            "__AUTH_PTR_CURRENT__"
            if reverse == adapters.DNS_REVERSE_CURRENT
            else "__AUTH_PTR_TARGET__",
            "NXDOMAIN",
            aa=False,
        )
        if baseline_gap
        else _dig(
            "__AUTH_PTR_CURRENT__"
            if reverse == adapters.DNS_REVERSE_CURRENT
            else "__AUTH_PTR_TARGET__",
            "NOERROR",
            f"{reverse}. 300 IN PTR {fqdn}.",
            aa=True,
        )
    )
    auth = "".join(
        [
            auth_a,
            auth_ptr,
            _dig(
                "__AUTH_SOA__",
                "NOERROR",
                "atius.internal. 300 IN SOA ipa.atius.internal. hostmaster.atius.internal. 1 2 3 4 5",
                aa=True,
            ),
            _dig(
                "__AUTH_NS__",
                "NOERROR",
                "atius.internal. 300 IN NS ipa.atius.internal.",
                aa=True,
            ),
            _dig("__AUTH_NX__", "NXDOMAIN", aa=True),
        ]
    )
    resolver = ""
    for server in (adapters.DNS_COREDNS, adapters.DNS_ADGUARD):
        prefix = f"__RESOLVER_{server}_"
        resolver += _dig(f"{prefix}A__", "NOERROR", f"{fqdn}. 300 IN A {address}")
        ptr = (
            "PTR_CURRENT__"
            if reverse == adapters.DNS_REVERSE_CURRENT
            else "PTR_TARGET__"
        )
        resolver += _dig(
            f"{prefix}{ptr}", "NOERROR", f"{reverse}. 300 IN PTR {fqdn}."
        )
        resolver += (
            _dig(f"{prefix}SOA__", "SERVFAIL")
            if baseline_gap and server == adapters.DNS_ADGUARD
            else _dig(
                f"{prefix}SOA__",
                "NOERROR",
                "atius.internal. 300 IN SOA ipa.atius.internal. hostmaster.atius.internal. 1 2 3 4 5",
            )
        )
        resolver += _dig(
            f"{prefix}NS__",
            "NOERROR",
            "atius.internal. 300 IN NS ipa.atius.internal.",
        )
        resolver += _dig(f"{prefix}NX__", "NXDOMAIN")
    return auth.encode(), resolver.encode()


def test_dns_is_owner_specific_and_checks_aa_a_ptr_soa_ns_ttl_nxdomain(
    monkeypatch,
) -> None:
    auth, resolvers = _dns_outputs(
        "10.21.1.21",
        adapters.DNS_REVERSE_CURRENT,
        baseline_gap=True,
    )

    def fake_ssh(owner, command):
        if owner == "srv3":
            return True, auth, "srv3"
        return True, resolvers, "srv1"

    monkeypatch.setattr(adapters, "_ssh", fake_ssh)
    ok, normalized, _, _ = adapters._dns_read(
        _spec("54-02", "preflight", "dns_edge_baseline"), "a" * 64
    )
    assert ok
    assert normalized["authority"]["aa"] is False
    assert normalized["authority"]["a_address"] is None
    assert normalized["authority"]["ptr_owner"] is None
    assert normalized["resolvers"]["a_ptr_complete"] is True
    assert normalized["resolvers"]["a_address"] == "10.21.1.21"
    assert normalized["baseline_gap"]["authority_missing"] == ["A", "PTR"]
    assert normalized["baseline_gap"]["resolver_missing"]["127.0.0.2"] == ["SOA"]
    assert normalized["resolvers"]["nxdomain_count"] == 2
    assert normalized["ttl_min"] == 300

    converged_auth, converged_resolvers = _dns_outputs(
        "10.21.1.21",
        adapters.DNS_REVERSE_CURRENT,
    )
    monkeypatch.setattr(
        adapters,
        "_ssh",
        lambda owner, command: (
            True,
            converged_auth if owner == "srv3" else converged_resolvers,
            owner,
        ),
    )
    assert not adapters._dns_read(
        _spec("54-02", "preflight", "dns_edge_baseline"), "a" * 64
    )[0]

    tampered = resolvers.replace(b"10.21.1.21", b"10.21.1.99", 1)
    monkeypatch.setattr(
        adapters,
        "_ssh",
        lambda owner, command: (
            True,
            auth if owner == "srv3" else tampered,
            owner,
        ),
    )
    assert not adapters._dns_read(
        _spec("54-02", "preflight", "dns_edge_baseline"), "a" * 64
    )[0]

    monkeypatch.setattr(
        adapters,
        "_ssh",
        lambda owner, command: (
            True,
            converged_auth if owner == "srv3" else converged_resolvers,
            owner,
        ),
    )
    assert adapters._dns_read(
        _spec("54-06", "preview", "freeipa_authority"), "a" * 64
    )[0]
    monkeypatch.setattr(
        adapters,
        "_ssh",
        lambda owner, command: (
            True,
            auth if owner == "srv3" else resolvers,
            owner,
        ),
    )
    assert not adapters._dns_read(
        _spec("54-06", "preview", "freeipa_authority"), "a" * 64
    )[0]


def test_backup_probe_requires_hash_mode_manifest_restore_and_offhost(
    monkeypatch,
) -> None:
    def fake_ssh(owner, command):
        for expectation in adapters.BACKUP_EXPECTATIONS.values():
            if expectation["offhost_archive"] and expectation["offhost_archive"] in command:
                return (
                    True,
                    (
                        f"{expectation['offhost_archive']}|"
                        f"{expectation['offhost_sha256']}|600\n"
                    ).encode(),
                    owner,
                )
            if expectation["archive"] in command:
                return (
                    True,
                    (
                        f"{expectation['archive']}|"
                        f"{expectation['archive_sha256']}|{expectation['mode']}\n"
                    ).encode(),
                    owner,
                )
        return False, b"", owner

    monkeypatch.setattr(adapters, "_ssh", fake_ssh)
    ok, normalized, _, _ = adapters._backup_read("b" * 64)
    assert ok
    assert {item["owner"] for item in normalized["backups"]} == {
        "srv1",
        "srv3",
        "offhost",
    }
    assert all(item["offhost_verified"] for item in normalized["backups"])

    def bad_ssh(owner, command):
        ok, output, request = fake_ssh(owner, command)
        if adapters.SRV1_BACKUP_ROOT in command and b"|" in output:
            output = output.replace(
                adapters.BACKUP_EXPECTATIONS["srv1"]["archive_sha256"].encode(),
                b"0" * 64,
            )
        return ok, output, request

    monkeypatch.setattr(adapters, "_ssh", bad_ssh)
    assert not adapters._backup_read("b" * 64)[0]


def _wg_text(*, allowed: str, handshake: int) -> str:
    key = "base64-public-key-material"
    return (
        f"__PEERS__\nwg100\t{key}\n"
        f"__ALLOWED_IPS__\nwg100\t{key}\t{allowed}\n"
        f"__LATEST_HANDSHAKES__\nwg100\t{key}\t{handshake}\n"
        f"__ENDPOINTS__\nwg100\t{key}\t203.0.113.2:51820\n"
        f"__TRANSFER__\nwg100\t{key}\t10\t20\n"
    )


def _wg_two_peer_text(
    *,
    target_handshake: int,
    other_handshake: int,
) -> str:
    target_key = "target-public-key"
    other_key = "other-public-key"
    return (
        f"__PEERS__\nwg100\t{target_key}\nwg100\t{other_key}\n"
        "__ALLOWED_IPS__\n"
        f"wg100\t{target_key}\t10.100.100.11/32\n"
        f"wg100\t{other_key}\t10.100.100.250/32\n"
        "__LATEST_HANDSHAKES__\n"
        f"wg100\t{target_key}\t{target_handshake}\n"
        f"wg100\t{other_key}\t{other_handshake}\n"
        "__ENDPOINTS__\n"
        f"wg100\t{target_key}\t203.0.113.11:51820\n"
        f"wg100\t{other_key}\t203.0.113.250:51820\n"
        "__TRANSFER__\n"
        f"wg100\t{target_key}\t10\t20\n"
        f"wg100\t{other_key}\t30\t40\n"
    )


def test_wireguard_parser_fingerprints_keys_and_enforces_target_freshness() -> None:
    spec = _spec("54-08", "apply", "s20_handshake")
    normalized = adapters._wireguard_normalized(
        _wg_text(allowed="10.100.100.11/32", handshake=int(time.time())),
        spec,
    )
    assert normalized["allowed_ips"] == ["10.100.100.11/32"]
    assert normalized["handshake_fresh"] is True
    assert normalized["raw_keys_present"] is False
    assert "base64-public-key-material" not in json.dumps(normalized)

    stale = adapters._wireguard_normalized(
        _wg_text(allowed="10.100.100.9/32", handshake=1), spec
    )
    assert stale["handshake_fresh"] is False
    assert "10.100.100.11/32" not in stale["allowed_ips"]


def test_wireguard_freshness_is_bound_to_same_peer_that_owns_s20_target(
    monkeypatch,
) -> None:
    spec = _spec("54-08", "apply", "s20_handshake")
    normalized = adapters._wireguard_normalized(
        _wg_two_peer_text(
            target_handshake=1,
            other_handshake=int(time.time()),
        ),
        spec,
    )
    assert normalized["target_peer_count"] == 1
    assert normalized["target_peer"]["allowed_ips"] == ["10.100.100.11/32"]
    assert normalized["target_peer"]["handshake_fresh"] is False
    assert normalized["handshake_fresh"] is False
    assert any(
        peer["handshake_fresh"] is True
        and peer["allowed_ips"] == ["10.100.100.250/32"]
        for peer in normalized["peers"]
    )
    monkeypatch.setattr(
        adapters,
        "_ssh",
        lambda owner, command: (
            True,
            _wg_two_peer_text(
                target_handshake=1,
                other_handshake=int(time.time()),
            ).encode(),
            "srv1",
        ),
    )
    assert not adapters._wireguard_read(spec, "a" * 64)[0]


def _be3_payload(s20_ip: str, *, applies: bool = False) -> dict:
    return {
        "appliesChanges": applies,
        "capture": {"browser": "chromium-headless", "authenticated": True},
        "endpoints": {
            "lanIpAddressReserve": {
                "targets": {
                    "s23": {
                        "mac": "64:1B:2F:C2:DC:A3",
                        "ips": ["192.168.1.10"],
                    },
                    "s20": {
                        "mac": "30:AB:6A:3C:96:D1",
                        "ips": [s20_ip],
                    },
                }
            }
        },
    }


@pytest.mark.parametrize(
    ("plan", "stage", "s20_ip"),
    [
        ("54-07", "preview", "192.168.1.9"),
        ("54-07", "apply", "192.168.1.11"),
        ("54-08", "apply", "192.168.1.11"),
    ],
)
def test_be3_parser_enforces_stage_specific_s23_and_s20(
    plan: str,
    stage: str,
    s20_ip: str,
) -> None:
    normalized = adapters._be3_normalized(
        _be3_payload(s20_ip),
        _spec(plan, stage, adapters.BASE_CHECKS[plan][0]),
    )
    assert normalized["source_commit"] == adapters.BE3_COMMIT
    assert normalized["s23"]["ips"] == ["192.168.1.10"]
    assert normalized["s20"]["expected"] == s20_ip
    assert normalized["applies_changes"] is False


def test_be3_probe_rejects_mutating_capture_and_wrong_s20(monkeypatch) -> None:
    wg = _wg_text(allowed="10.100.100.9/32", handshake=int(time.time())).encode()

    def fake_ssh(owner, command):
        if command == adapters.SSH_COMMANDS["be3_capture"]:
            return True, json.dumps(_be3_payload("192.168.1.9", applies=True)).encode(), "srv1"
        return True, wg, "srv1"

    monkeypatch.setattr(adapters, "_ssh", fake_ssh)
    assert not adapters._be3_wg_read(
        _spec("54-07", "preview", "edge_transaction"), "c" * 64
    )[0]


def test_host_probe_requires_old_ip_pre_cutover_and_target_ip_after(monkeypatch) -> None:
    def fake_ssh_one(target, command):
        address = "10.31.1.31" if "10.31.1.31" in target else "10.21.1.21"
        return True, f"horistic-srv\n{address}\n".encode()

    monkeypatch.setattr(adapters, "_ssh_one", fake_ssh_one)
    pre = adapters._host_read(
        _spec("54-05", "preview", "host_k3s_dual_path"),
        "d" * 64,
        services=False,
    )
    assert pre[0]
    assert pre[1]["required_private_ip"] == "10.21.1.21"
    post = adapters._host_read(
        _spec("54-05", "apply", "host_k3s_dual_path"),
        "d" * 64,
        services=False,
    )
    assert post[0]
    assert post[1]["required_private_ip"] == "10.31.1.31"


def test_graphify_requires_both_fresh_flags_and_relevant_query(monkeypatch) -> None:
    def good_run(argv, timeout=15):
        if argv[-1] == "status":
            return True, b'{"stale":false,"commit_stale":false,"total_nodes":12}'
        return True, b'{"nodes":[{"node":"Phase 54 network gate adapter workstream"}]}'

    monkeypatch.setattr(adapters, "_run", good_run)
    ok, normalized, _, _ = adapters._knowledge_read("e" * 64)
    assert ok
    assert normalized["stale"] is False
    assert normalized["commit_stale"] is False
    assert normalized["total_nodes"] == 12
    assert normalized["query_node_count"] == 1
    assert normalized["relevant_nodes"] is True

    monkeypatch.setattr(
        adapters,
        "_run",
        lambda argv, timeout=15: (
            (True, b'{"stale":false,"commit_stale":true,"total_nodes":12}')
            if argv[-1] == "status"
            else (True, b'{"nodes":[{"node":"Phase 54 network gate adapter"}]}')
        ),
    )
    assert not adapters._knowledge_read("e" * 64)[0]


@pytest.mark.parametrize(
    ("status", "query"),
    [
        (
            b'{"stale":false,"commit_stale":false,"total_nodes":0}',
            b'{"nodes":[{"node":"Phase 54 network gate adapter"}]}',
        ),
        (
            b'{"stale":false,"commit_stale":false,"total_nodes":12}',
            b'{"nodes":[]}',
        ),
        (
            b'{"stale":false,"commit_stale":false,"total_nodes":12}',
            b'{"nodes":[{"node":"Phase 54 unrelated"}]}',
        ),
        (
            b"stale=false commit_stale=false total_nodes=12",
            b'{"nodes":[{"node":"Phase 54 network gate adapter"}]}',
        ),
    ],
)
def test_graphify_empty_irrelevant_or_non_json_payload_blocks(
    monkeypatch,
    status: bytes,
    query: bytes,
) -> None:
    monkeypatch.setattr(
        adapters,
        "_run",
        lambda argv, timeout=15: (
            (True, status) if argv[-1] == "status" else (True, query)
        ),
    )
    assert not adapters._knowledge_read("e" * 64)[0]


def _matrix_oci_payload(check_id: str, residual: str | None = None) -> dict:
    if check_id == "retirement_targets":
        route_values = [residual] if residual else ["10.31.0.0/16"]
        return {
            "evidence_sha256": "f" * 64,
            "operation": "peering.drg_status",
            "semantic": {
                "applies_live_oci_writes": False,
                "attachments": [{"attachment_ocid": "ocid1.drgattachment.x"}],
                "route_tables": [{"target_cidrs": route_values}],
                "route_distributions": [{"distribution_id": "ocid1.dist.x"}],
                "blockers": [],
                "operational_10_21": [residual] if residual else [],
            },
        }
    private_ip = residual or "10.31.1.31"
    return {
        "evidence_sha256": "f" * 64,
        "operation": "inventory.get",
        "semantic": {
            "vcn_cidrs": ["10.31.0.0/16"],
            "subnet_cidrs": ["10.31.1.0/24"],
            "private_ips": [
                {
                    "private_ip_ocid": "ocid1.privateip.target",
                    "address": "10.31.1.31",
                    "vnic_ocid": "ocid1.vnic.target",
                    "subnet_ocid": "ocid1.subnet.target",
                },
                {
                    "private_ip_ocid": "ocid1.privateip.residual",
                    "address": private_ip,
                    "vnic_ocid": "ocid1.vnic.residual",
                    "subnet_ocid": "ocid1.subnet.target",
                },
            ],
            "reserved_public_ips": [
                {
                    "public_ip_ocid": "ocid1.publicip.target",
                    "address": "163.176.232.119",
                    "label": "horistic-srv-1",
                    "lifecycle_state": "ASSIGNED",
                    "private_ip_ocid": "ocid1.privateip.target",
                    "lifetime": "RESERVED",
                }
            ],
            "operational_10_21": [residual] if residual else [],
        },
    }


def _install_matrix_mocks(
    monkeypatch,
    *,
    drg_residual: str | None = None,
    inventory_residual: str | None = None,
    dns_residual: str | None = None,
    host_residual: str | None = None,
) -> None:
    def fake_oci_probe(spec, evidence, evidence_path, evidence_sha256):
        payload = _matrix_oci_payload(
            spec.check_id,
            drg_residual if spec.check_id == "retirement_targets" else inventory_residual,
        )
        payload["evidence_sha256"] = evidence_sha256
        return True, payload, f"oci-{spec.check_id}", b"oci"

    monkeypatch.setattr(adapters, "_oci_probe", fake_oci_probe)
    monkeypatch.setattr(
        adapters,
        "_dns_read",
        lambda spec, evidence_sha256: (
            True,
            {
                "evidence_sha256": evidence_sha256,
                "operational_10_21": [dns_residual] if dns_residual else [],
            },
            "dns",
            b"dns",
        ),
    )
    monkeypatch.setattr(
        adapters,
        "_host_read",
        lambda spec, evidence_sha256, services: (
            True,
            {
                "evidence_sha256": evidence_sha256,
                "private_path": "PASS",
                "public_path": "PASS",
                "operational_10_21": [host_residual] if host_residual else [],
            },
            "host",
            b"host",
        ),
    )


def test_full_matrix_zero_residual_is_hash_bound_and_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    evidence_path = _evidence(tmp_path, "54-10", "preflight")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    _install_matrix_mocks(monkeypatch)
    ok, normalized, _, _ = adapters._matrix_read(
        _spec("54-10", "preflight", "full_matrix"),
        evidence,
        evidence_path,
        evidence_sha,
    )
    assert ok
    assert normalized["evidence_sha256"] == evidence_sha
    assert normalized["operational_10_21"] == []
    assert normalized["residual_live"]["present"] is False
    assert len(normalized["residual_live"]["sha256"]) == 64
    assert len(normalized["live_readback_sha256"]) == 64


@pytest.mark.parametrize(
    ("source", "value"),
    [
        ("drg", "route 10.21.0.0/16"),
        ("inventory", "10.21.1.21"),
        ("dns", "freeipa:A:horistic-srv.atius.internal:10.21.1.21"),
        ("host", "10.21.1.21"),
    ],
)
def test_full_matrix_blocks_any_live_10_21_residual(
    tmp_path: Path,
    monkeypatch,
    source: str,
    value: str,
) -> None:
    evidence_path = _evidence(tmp_path, "54-10", "preflight")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    kwargs = {
        "drg_residual": value if source == "drg" else None,
        "inventory_residual": value if source == "inventory" else None,
        "dns_residual": value if source == "dns" else None,
        "host_residual": value if source == "host" else None,
    }
    _install_matrix_mocks(monkeypatch, **kwargs)
    ok, normalized, _, _ = adapters._matrix_read(
        _spec("54-10", "preflight", "full_matrix"),
        evidence,
        evidence_path,
        evidence_sha,
    )
    assert not ok
    assert normalized["residual_live"]["present"] is True
    assert normalized["residual_live"]["count"] >= 1
    assert normalized["operational_10_21"]


def test_adapter_contains_no_stage_self_assertion_or_raw_key_output() -> None:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    assert "_stage_contract" not in source
    assert '"normalized": normalized' in source
    assert '"evidence_sha256": evidence_sha256' in source
    assert '"read_only": True' in source
    assert '"mutation_performed": False' in source
    assert '"secret_material_present": False' in source
    assert "base64-public-key-material" not in json.dumps(
        adapters._wireguard_normalized(
            _wg_text(allowed="10.100.100.11/32", handshake=int(time.time())),
            _spec("54-08", "apply", "s20_handshake"),
        )
    )
