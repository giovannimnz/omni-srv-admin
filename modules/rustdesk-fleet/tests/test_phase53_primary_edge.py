from __future__ import annotations

import copy
import configparser
import base64
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[3]
CONTRACT_DIR = REPO / "modules/rustdesk-fleet/contracts"
RUNTIME_CONTRACT = CONTRACT_DIR / "phase53-runtime.json"
EDGE_CONTRACT = CONTRACT_DIR / "phase53-edge.json"
OPS_API_CONTRACT = CONTRACT_DIR / "phase53-ops-api.json"
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
EDGE_NFT_POLICY = REPO / "modules/rustdesk-fleet/nftables/atius-rustdesk-phase53.nft"
EDGE_BOOT_SERVICE = REPO / "modules/rustdesk-fleet/systemd/atius-rustdesk-phase53-edge.service"


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
            "hostnames",
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
    assert payload["schema_version"] == 1
    assert payload["primary_host"] == "horistic-srv"
    assert payload["hostnames"] == {
        "native": "rustdesk.atius.com.br",
        "operations": "rustdesk-ops.atius.com.br",
    }
    assert payload["public_ipv4_allowed"] == {"tcp": [21115, 21116, 21117], "udp": [21116]}
    assert payload["public_forbidden"] == {
        "tcp": [21114, 21118, 21119],
        "unexpected": "all-other-phase53-exposure",
    }
    assert payload["ipv6_policy"] == {"rustdesk": "deny-all", "aaaa_record": False}

    consensus = payload["address_consensus"]
    _assert_keys(consensus, {"required_equal_sources", "mismatch_action"})
    assert consensus["required_equal_sources"] == [
        "oci-vnic-public-ipv4",
        "horistic-egress-ipv4",
        "ssh-horistic-srv.atius.com.br-a",
    ]
    assert consensus["mismatch_action"] == "block-before-write"

    ingress = payload["effective_ingress"]
    _assert_keys(ingress, {"host_policy", "oci_policy", "union_audit_required", "broad_allow_action"})
    assert ingress["host_policy"] == "owned-nftables-scope"
    assert ingress["oci_policy"] == "security-lists-plus-attached-nsgs"
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
    _assert_keys(probes, {"origins", "tcp", "udp_correlation", "same_host_allowed"})
    assert probes["origins"][0] == "GIOVANNI-W11-PC-private-first"
    assert len(probes["origins"]) == 2
    assert probes["same_host_allowed"] is False
    assert probes["tcp"] == {
        "positive": [21115, 21116, 21117],
        "negative": [21114, 21118, 21119],
        "targets": ["public-ipv4", "native-hostname"],
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
    for path in (RUNTIME_CONTRACT, EDGE_CONTRACT, OPS_API_CONTRACT):
        assert path.is_file(), path
        _load_strict(path)


def test_contract_schema_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
    with pytest.raises(DuplicateKeyError, match="duplicate JSON key"):
        _load_strict(path)


def test_runtime_contract_schema_and_resource_arithmetic() -> None:
    _validate_runtime(_load_strict(RUNTIME_CONTRACT))


def test_edge_contract_schema_and_dns_last_order() -> None:
    _validate_edge(_load_strict(EDGE_CONTRACT))


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
) -> Any:
    home = tmp_path / "home"
    runtime = tmp_path / "run-user-1000"
    home.mkdir()
    runtime.mkdir()
    return module.Phase53ServerTransaction(
        repo=REPO,
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
        ("evidence/phase53/deploy-transaction.json", "53-05"),
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
        "edge": {
            "ipv4_tcp": edge["public_ipv4_allowed"]["tcp"],
            "ipv4_udp": edge["public_ipv4_allowed"]["udp"],
            "ipv6": [],
            "forbidden_not_open": edge["public_forbidden"]["tcp"],
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
        ({"edge": {"ipv4_tcp": [21114]}}, "effective-edge-policy"),
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
                        "ingress_rules": [_oci_rule("tcp", 21115, 21117)],
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
                        "ingress_rules": [_oci_rule("udp", 21116, 21116)],
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
            "oci-vnic-public-ipv4": "203.0.113.8",
            "horistic-egress-ipv4": "203.0.113.8",
            "ssh-horistic-srv.atius.com.br-a": "203.0.113.8",
        },
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


def _edge_transaction(module: Any, backend: Any, **kwargs: Any) -> Any:
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
        "ipv4_tcp": [21115, 21116, 21117],
        "ipv4_udp": [21116],
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
    assert result == {
        "family": "inet",
        "table": "atius_rustdesk_phase53",
        "hook": "input",
        "priority": 300,
        "public_interface": "ens3",
        "ipv4_tcp": [21115, 21116, 21117],
        "ipv4_udp": [21116],
        "ipv6_denied": [21114, 21115, 21116, 21117, 21118, 21119],
    }
    lowered = candidate.lower()
    assert "flush ruleset" not in lowered
    assert not any(token in lowered for token in ("k3s", "cni", "flannel", "kube-"))


@pytest.mark.parametrize(
    ("replacement", "blocker"),
    [
        ("ATIUS-PHASE53-EDGE", "nft-ownership-marker-invalid"),
        ("priority 300", "nft-priority-invalid"),
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
    assert "/usr/sbin/nft --check --file /etc/atius-rustdesk/phase53-edge.nft" in encoded
    assert service["ExecStart"] == "/usr/sbin/nft --file /etc/atius-rustdesk/phase53-edge.nft"
    assert "--verify-host-policy" in service["ExecStartPost"]
    assert (
        "--template /etc/atius-rustdesk/phase53-edge.template.nft"
        in service["ExecStartPost"]
    )
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
            "type filter hook input priority 300; policy accept;",
            "type filter hook input priority 300; policy accept;",
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
    required = "type filter hook input priority 300; policy accept;"
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
            forged["priority"] = 0
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
    assert "--contract" in _load_unit(EDGE_BOOT_SERVICE)["Service"]["ExecStartPost"]


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
                    "oci-vnic-public-ipv4": "2001:db8::8",
                    "horistic-egress-ipv4": "2001:db8::8",
                    "ssh-horistic-srv.atius.com.br-a": "2001:db8::8",
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
        module.validate_edge_preflight(preflight)


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
