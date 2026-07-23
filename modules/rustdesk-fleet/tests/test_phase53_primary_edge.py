from __future__ import annotations

import copy
import configparser
import base64
import importlib.util
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
        ("tools/rustdesk-ops-api.py", "53-03"),
        ("tools/apply-phase53-edge.py", "53-04"),
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
