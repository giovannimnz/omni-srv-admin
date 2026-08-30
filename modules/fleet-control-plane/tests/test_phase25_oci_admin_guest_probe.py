from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
from time import monotonic
from typing import Any

import pytest


OMNI_REPO = Path(__file__).resolve().parents[3]
OCI_ADMIN_REPO = OMNI_REPO.parent / "oci-admin"
PROBE_PATH = (
    OMNI_REPO
    / "modules/fleet-control-plane/tools/oci-admin-guest-probe-v1.py"
)
INSTALLER_PATH = (
    OMNI_REPO
    / "modules/fleet-control-plane/scripts/install-oci-admin-guest-probe-v1.sh"
)
SUDOERS_PATH = (
    OMNI_REPO
    / "modules/fleet-control-plane/configs/102-oci-admin-guest-probe-v1.sudoers"
)
MANIFEST_ROOT = OCI_ADMIN_REPO / "app/guest_runbooks/phase25"
MANIFEST_FILES = {
    "phase25.wg100-routes": "wg100-routes-v1.json",
    "phase25.k3s-routes": "k3s-routes-v1.json",
    "phase25.podman-routes": "podman-routes-v1.json",
    "phase25.lan-routes": "lan-routes-v1.json",
    "phase25.reachability": "reachability-v1.json",
    "phase25.coredns-peer-readback": "coredns-peer-readback-v1.json",
}

assert PROBE_PATH.is_file(), "Phase 25 guest probe source has not been implemented"
assert INSTALLER_PATH.is_file(), "Phase 25 guest probe installer has not been implemented"
assert SUDOERS_PATH.is_file(), "Phase 25 guest probe sudoers has not been implemented"
SPEC = importlib.util.spec_from_file_location("oci_admin_guest_probe_v1", PROBE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def _manifest(runbook_id: str) -> dict[str, Any]:
    return json.loads(
        (MANIFEST_ROOT / MANIFEST_FILES[runbook_id]).read_text(encoding="utf-8")
    )


def _canonical_digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _attestation_document(target: str = "atius-srv-1") -> dict[str, Any]:
    source = {
        "authority": "omni-srv-admin",
        "repo_commit": "1" * 40,
        "path": "inventory/hosts/atius-srv-4.yaml",
        "digest": "sha256:" + "b" * 64,
    }
    peers = [
        {
            "role": "dns-peer",
            "profile_name": profile,
            "region": "sa-saopaulo-1",
            "compartment_id": f"ocid1.compartment.oc1..{name.replace('-', '')}",
            "instance_id": f"ocid1.instance.oc1.sa-saopaulo-1.{name.replace('-', '')}",
            "display_name": name,
            "private_ip": address,
            "source_repo_commit": source["repo_commit"],
            "source_path": f"inventory/hosts/{name}.yaml",
            "source_digest": "sha256:" + "c" * 64,
        }
        for name, profile, address in (
            ("atius-srv-1", "atius1", "10.11.1.11"),
            ("atius-srv-2", "atius2", "10.12.1.12"),
            ("atius-srv-3", "atius3", "10.13.1.13"),
            ("horistic-srv", "horistic", "10.21.1.21"),
        )
    ]
    target_peer = next(item for item in peers if item["display_name"] == target)
    projection = {
        "schema": "atius.internal-dns-projection-attestation/v1",
        "source": source,
        "records": [
            {"name": "atius-srv-4", "type": "A", "value": "10.14.1.14"},
            {
                "name": "atius-srv-4.atius.internal",
                "type": "A",
                "value": "10.14.1.14",
            },
        ],
        "resolvers": [
            {"role": "primary", "address": "10.11.1.11", "port": 53},
            {"role": "reserve", "address": "10.100.100.1", "port": 53},
        ],
    }
    projection_digest = _canonical_digest(projection)
    target_binding = {
        "target_role": target_peer["role"],
        "profile_name": target_peer["profile_name"],
        "region": target_peer["region"],
        "compartment_id": target_peer["compartment_id"],
        "instance_id": target_peer["instance_id"],
        "display_name": target_peer["display_name"],
        "source_repo_commit": source["repo_commit"],
        "source_path": source["path"],
        "source_digest": source["digest"],
        "projection_digest": projection_digest,
    }
    base = {
        "schema": "atius.oci-admin-guest-probe-attestation/v1",
        "version": "1",
        "target_binding_preimage": target_binding,
        "target_peer_preimage": target_peer,
        "peer_set_preimage": peers,
        "projection_preimage": projection,
        "digests": {
            "target_binding": _canonical_digest(target_binding),
            "peer_set": _canonical_digest(peers),
            "projection": projection_digest,
        },
    }
    return {**base, "digest": _canonical_digest(base)}


def _render_argv(
    runbook_id: str,
    *,
    target: str,
    max_rows: int = 64,
    probe_count: int = 3,
) -> list[str]:
    manifest = _manifest(runbook_id)
    peers = (
        "atius-srv-1,atius-srv-2,atius-srv-3,horistic-srv"
        if target == "atius-srv-4"
        else "atius-srv-4"
    )
    values = {
        "manifest.digest": manifest["digest"],
        "target.display_name": target,
        "target.peer_csv": peers,
        "params.max_rows": str(max_rows),
        "params.probe_count": str(probe_count),
    }
    rendered: list[str] = []
    for token in manifest["argv_template"][1:]:
        if token.startswith("{") and token.endswith("}"):
            token = values[token[1:-1]]
        rendered.append(token)
    return rendered


def _coredns_argv(
    *,
    target: str = "atius-srv-1",
    target_binding_digest: str | None = None,
    probe_digest: str | None = None,
    peer_set_digest: str | None = None,
    projection_digest: str | None = None,
    attestation_digest: str | None = None,
) -> list[str]:
    attestation = _attestation_document(target)
    return [
        "execute",
        "--runbook",
        "phase25.coredns-peer-readback",
        "--version",
        "1",
        "--manifest-digest",
        _manifest("phase25.coredns-peer-readback")["digest"],
        "--target-binding-digest",
        target_binding_digest or attestation["digests"]["target_binding"],
        "--probe-digest",
        probe_digest or probe.self_digest(),
        "--attestation-digest",
        attestation_digest or attestation["digest"],
        "--target",
        target,
        "--peer-set-digest",
        peer_set_digest or attestation["digests"]["peer_set"],
        "--projection-digest",
        projection_digest or attestation["digests"]["projection"],
        "--short-name",
        "atius-srv-4",
        "--fqdn",
        "atius-srv-4.atius.internal",
        "--expected-address",
        "10.14.1.14",
        "--primary-resolver",
        "10.11.1.11:53",
        "--reserve-resolver",
        "10.100.100.1:53",
        "--sentinel",
        "ATIUS_RUNBOOK_RESULT_V1",
    ]


def _command_result(stdout: bytes = b"", *, returncode: int = 0) -> Any:
    return probe.CommandResult(returncode=returncode, stdout=stdout, stderr=b"")


def _addresses_payload(address: str) -> bytes:
    return json.dumps(
        [
            {
                "ifname": "enp1s0",
                "addr_info": [
                    {"family": "inet", "local": address, "scope": "global"}
                ],
            }
        ]
    ).encode()


ROUTE_FIXTURE = json.dumps(
    [
        {
            "dst": "10.100.100.0/24",
            "dev": "wg100",
            "prefsrc": "10.100.100.1",
            "protocol": "kernel",
            "metric": 10,
        },
        {
            "dst": "10.42.0.0/16",
            "dev": "cni0",
            "prefsrc": "10.42.0.1",
            "protocol": "kernel",
        },
        {
            "dst": "10.89.53.0/24",
            "dev": "podman0",
            "prefsrc": "10.89.53.1",
            "protocol": "kernel",
        },
        {
            "dst": "10.11.0.0/16",
            "gateway": "10.11.1.1",
            "dev": "enp1s0",
            "prefsrc": "10.11.1.11",
            "protocol": "static",
        },
        {
            "dst": "169.254.0.0/16",
            "dev": "enp1s0",
            "scope": "link",
            "protocol": "kernel",
        },
        {
            "dst": "127.0.0.0/8",
            "dev": "lo",
            "scope": "host",
            "protocol": "kernel",
        },
    ]
).encode()


class FakeRunner:
    def __init__(self, *, address: str = "10.11.1.11") -> None:
        self.address = address
        self.calls: list[tuple[tuple[str, ...], int]] = []
        self.overrides: dict[tuple[str, ...], Any] = {}

    def __call__(self, argv: tuple[str, ...], timeout_seconds: int) -> Any:
        self.calls.append((argv, timeout_seconds))
        if argv in self.overrides:
            return self.overrides[argv]
        if argv == probe.IP_ADDRESS_COMMAND:
            return _command_result(_addresses_payload(self.address))
        if argv == probe.IP_ROUTE_COMMAND:
            return _command_result(ROUTE_FIXTURE)
        if argv == probe.PODMAN_LIST_COMMAND:
            return _command_result(b'[{"Name":"podman","NetworkInterface":"podman0"}]')
        if argv[:3] == probe.PODMAN_INSPECT_PREFIX:
            return _command_result(
                b'[{"name":"podman","network_interface":"podman0",'
                b'"subnets":[{"subnet":"10.89.53.0/24",'
                b'"gateway":"10.89.53.1"}]}]'
            )
        if argv and argv[0] == probe.PING_BINARY:
            return _command_result(b"1 packets transmitted, 1 received, time=7.4 ms")
        if argv and argv[0] == probe.GETENT_BINARY:
            name = argv[-1]
            address = probe.EXPECTED_HOST_ADDRESSES[name]
            return _command_result(f"{address} STREAM {name}\n".encode())
        if argv and argv[0] == probe.DIG_BINARY:
            name = argv[-2]
            return _command_result(
                (
                    ";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1\n"
                    ";; flags: qr aa rd ra; QUERY: 1, ANSWER: 1\n"
                    f"{name}. 60 IN A 10.14.1.14\n"
                ).encode()
            )
        raise AssertionError(f"unexpected command: {argv!r}")


def _run_main(
    argv: list[str],
    *,
    runner: FakeRunner,
    hostname: str,
    resolver: Any | None = None,
    tcp_probe: Any | None = None,
    attestation_loader: Any | None = None,
) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = probe.main(
        argv,
        runner=runner,
        hostname_provider=lambda: hostname,
        resolver=resolver,
        tcp_probe=tcp_probe,
        attestation_loader=(
            attestation_loader
            or (lambda: json.dumps(_attestation_document(hostname)).encode())
        ),
        identity_validator=lambda: None,
        stdout=stdout,
        stderr=stderr,
    )
    return code, stdout.getvalue(), stderr.getvalue()


def _payload(stdout: str) -> dict[str, Any]:
    prefix = "ATIUS_RUNBOOK_RESULT_V1 "
    assert stdout.startswith(prefix)
    assert stdout.count("\n") == 1
    return json.loads(stdout[len(prefix) :])


def test_manifest_probe_pins_all_six_independent_contracts() -> None:
    assert set(probe.PINNED_RUNBOOKS) == set(MANIFEST_FILES)
    for runbook_id in MANIFEST_FILES:
        manifest = _manifest(runbook_id)
        contract = probe.PINNED_RUNBOOKS[runbook_id]
        assert probe.canonical_manifest_digest(manifest) == manifest["digest"]
        assert contract.manifest_digest == manifest["digest"]
        assert contract.result_schema == manifest["result"]["schema"]
        assert contract.result_fields == tuple(manifest["result"]["allowlisted_fields"])
        expected_targets = tuple(
            member["display_name"]
            for member in manifest.get("targets", {}).get("members", [])
        )
        if runbook_id == "phase25.coredns-peer-readback":
            expected_targets = (
                "atius-srv-1",
                "atius-srv-2",
                "atius-srv-3",
                "horistic-srv",
            )
        assert contract.targets == expected_targets


@pytest.mark.parametrize(
    ("runbook_id", "kind", "destinations"),
    [
        ("phase25.wg100-routes", "wg100_route", {"10.100.100.0/24"}),
        ("phase25.k3s-routes", "k3s_route", {"10.42.0.0/16"}),
        ("phase25.podman-routes", "podman_route", {"10.89.53.0/24"}),
        (
            "phase25.lan-routes",
            "lan_route",
            {"10.11.0.0/16", "169.254.0.0/16"},
        ),
    ],
)
def test_probe_route_collectors_are_disjoint_and_schema_closed(
    runbook_id: str,
    kind: str,
    destinations: set[str],
) -> None:
    runner = FakeRunner()
    code, stdout, stderr = _run_main(
        _render_argv(runbook_id, target="atius-srv-1"),
        runner=runner,
        hostname="atius-srv-1",
    )

    assert code == 0
    assert stderr == ""
    result = _payload(stdout)
    assert {row["kind"] for row in result["rows"]} == {kind}
    assert {row["destination"] for row in result["rows"]} == destinations
    assert all(row["read_only"] is True for row in result["rows"])
    probe.validate_schema(result, probe.PINNED_RUNBOOKS[runbook_id].result_schema)


def test_probe_reachability_uses_only_locked_bidirectional_matrix() -> None:
    runner = FakeRunner(address="10.14.1.14")
    resolved = {
        "atius-srv-1": ("10.11.1.11",),
        "atius-srv-2": ("10.12.1.12",),
        "atius-srv-3": ("10.13.1.13",),
        "horistic-srv": ("10.21.1.21",),
    }
    tcp_calls: list[tuple[str, int, int]] = []

    def tcp_probe(address: str, port: int, timeout_seconds: int) -> tuple[bool, int]:
        tcp_calls.append((address, port, timeout_seconds))
        return True, 4

    code, stdout, stderr = _run_main(
        _render_argv("phase25.reachability", target="atius-srv-4"),
        runner=runner,
        hostname="atius-srv-4",
        resolver=lambda name: resolved[name],
        tcp_probe=tcp_probe,
    )

    assert code == 0
    assert stderr == ""
    result = _payload(stdout)
    assert {row["peer"] for row in result["rows"]} == set(resolved)
    assert {(address, port) for address, port, _ in tcp_calls} == set(
        probe.LOCKED_TCP_ENDPOINTS
    )
    assert {timeout for _, _, timeout in tcp_calls} == {probe.TCP_TIMEOUT_SECONDS}
    assert {row["probe"] for row in result["rows"]} == {"icmp", "dns", "tcp"}
    ping_calls = [call for call, _ in runner.calls if call[0] == probe.PING_BINARY]
    assert all(call[4:8] == ("-W", "1", "-w", "5") for call in ping_calls)


def test_probe_default_dns_uses_fixed_getent_command_under_clean_runner() -> None:
    runner = FakeRunner(address="10.14.1.14")
    code, stdout, stderr = _run_main(
        _render_argv("phase25.reachability", target="atius-srv-4"),
        runner=runner,
        hostname="atius-srv-4",
        tcp_probe=lambda address, port, timeout: (True, 1),
    )

    assert code == 0
    assert stderr == ""
    assert _payload(stdout)["runbook_id"] == "phase25.reachability"
    getent_calls = [call for call, _ in runner.calls if call[0] == probe.GETENT_BINARY]
    assert getent_calls == [
        (probe.GETENT_BINARY, "ahostsv4", "atius-srv-1"),
        (probe.GETENT_BINARY, "ahostsv4", "atius-srv-2"),
        (probe.GETENT_BINARY, "ahostsv4", "atius-srv-3"),
        (probe.GETENT_BINARY, "ahostsv4", "horistic-srv"),
    ]


def test_probe_coredns_readback_uses_four_exact_authoritative_queries() -> None:
    runner = FakeRunner()
    argv = _coredns_argv()
    code, stdout, stderr = _run_main(
        argv,
        runner=runner,
        hostname="atius-srv-1",
    )

    assert code == 0
    assert stderr == ""
    result = _payload(stdout)
    assert result["attestation_digest"] == _attestation_document()["digest"]
    assert len(result["rows"]) == 4
    assert {(row["resolver"], row["name"]) for row in result["rows"]} == {
        ("10.11.1.11:53", "atius-srv-4"),
        ("10.11.1.11:53", "atius-srv-4.atius.internal"),
        ("10.100.100.1:53", "atius-srv-4"),
        ("10.100.100.1:53", "atius-srv-4.atius.internal"),
    }
    assert all(row["authoritative"] is True for row in result["rows"])
    dig_calls = [call for call, _ in runner.calls if call[0] == probe.DIG_BINARY]
    assert len(dig_calls) == 4
    assert all(call[: len(probe.DIG_PREFIX)] == probe.DIG_PREFIX for call in dig_calls)


def test_probe_deny_coredns_answer_for_wrong_owner_name() -> None:
    runner = FakeRunner()
    command = probe.dig_command("10.11.1.11:53", "atius-srv-4")
    runner.overrides[command] = _command_result(
        b";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1\n"
        b";; flags: qr aa rd ra; QUERY: 1, ANSWER: 1\n"
        b"attacker.invalid. 60 IN A 10.14.1.14\n"
    )
    code, stdout, stderr = _run_main(
        _coredns_argv(),
        runner=runner,
        hostname="atius-srv-1",
    )

    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE


@pytest.mark.parametrize(
    "mutate",
    [
        lambda argv: [*argv, "--extra", "value"],
        lambda argv: [argv[0], "--target", "atius-srv-1", *argv[1:]],
        lambda argv: [*argv[:3], "phase25.unknown", *argv[4:]],
        lambda argv: [*argv[:7], "sha256:" + "0" * 64, *argv[8:]],
        lambda argv: [*argv[:9], "evil;id", *argv[10:]],
        lambda argv: [*argv, "/tmp/caller-controlled"],
    ],
)
def test_probe_deny_unknown_digest_target_path_shell_and_extra_args(mutate: Any) -> None:
    runner = FakeRunner()
    argv = mutate(_render_argv("phase25.wg100-routes", target="atius-srv-1"))
    code, stdout, stderr = _run_main(
        argv,
        runner=runner,
        hostname="atius-srv-1",
    )

    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE
    assert runner.calls == []


def test_probe_deny_target_identity_mismatch_before_collection() -> None:
    runner = FakeRunner(address="10.12.1.12")
    code, stdout, stderr = _run_main(
        _render_argv("phase25.wg100-routes", target="atius-srv-1"),
        runner=runner,
        hostname="atius-srv-1",
    )

    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE
    assert [call for call, _ in runner.calls] == [probe.IP_ADDRESS_COMMAND]


def test_probe_deny_unknown_peer_and_caller_port() -> None:
    runner = FakeRunner(address="10.14.1.14")
    argv = _render_argv("phase25.reachability", target="atius-srv-4")
    argv[argv.index("--peers") + 1] = "atius-srv-1,attacker"
    argv.extend(["--port", "22"])

    code, stdout, stderr = _run_main(
        argv,
        runner=runner,
        hostname="atius-srv-4",
        resolver=lambda name: (),
        tcp_probe=lambda address, port, timeout: (False, 0),
    )
    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE
    assert runner.calls == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("--target-binding-digest", "sha256:bad"),
        ("--probe-digest", "sha256:" + "9" * 64),
        ("--attestation-digest", "sha256:bad"),
        ("--peer-set-digest", "sha256:bad"),
        ("--projection-digest", "sha256:bad"),
    ],
)
def test_probe_deny_coredns_forged_digests(field: str, value: str) -> None:
    runner = FakeRunner()
    argv = _coredns_argv()
    argv[argv.index(field) + 1] = value
    code, stdout, stderr = _run_main(argv, runner=runner, hostname="atius-srv-1")

    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE
    assert runner.calls == []


def test_probe_deny_hash_consistent_but_semantically_forged_attestation() -> None:
    runner = FakeRunner()
    forged = _attestation_document()
    forged["projection_preimage"]["records"][0]["value"] = "203.0.113.7"
    forged["digests"]["projection"] = _canonical_digest(
        forged["projection_preimage"]
    )
    forged["target_binding_preimage"]["projection_digest"] = forged["digests"][
        "projection"
    ]
    forged["digests"]["target_binding"] = _canonical_digest(
        forged["target_binding_preimage"]
    )
    base = {key: value for key, value in forged.items() if key != "digest"}
    forged["digest"] = _canonical_digest(base)
    argv = _coredns_argv(
        target_binding_digest=forged["digests"]["target_binding"],
        projection_digest=forged["digests"]["projection"],
        attestation_digest=forged["digest"],
    )

    code, stdout, stderr = _run_main(
        argv,
        runner=runner,
        hostname="atius-srv-1",
        attestation_loader=lambda: json.dumps(forged).encode(),
    )
    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE
    assert [call for call, _ in runner.calls] == [probe.IP_ADDRESS_COMMAND]


def test_probe_deny_oversized_and_secret_shaped_subprocess_output() -> None:
    runner = FakeRunner()
    runner.overrides[probe.IP_ROUTE_COMMAND] = _command_result(
        b"A" * (probe.MAX_COMMAND_OUTPUT_BYTES + 1)
    )
    code, stdout, stderr = _run_main(
        _render_argv("phase25.wg100-routes", target="atius-srv-1"),
        runner=runner,
        hostname="atius-srv-1",
    )
    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE

    runner = FakeRunner()
    secret_fixture = json.dumps(
        [{"dst": "10.100.100.0/24", "dev": "AKIAABCDEFGHIJKLMNOP"}]
    ).encode()
    runner.overrides[probe.IP_ROUTE_COMMAND] = _command_result(secret_fixture)
    code, stdout, stderr = _run_main(
        _render_argv("phase25.wg100-routes", target="atius-srv-1"),
        runner=runner,
        hostname="atius-srv-1",
    )
    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE


def test_probe_deny_forged_schema_and_oversized_result(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = FakeRunner()

    def forged(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"kind": "wg100_route", "unexpected": "field"}]

    monkeypatch.setattr(probe, "collect_routes", forged)
    code, stdout, stderr = _run_main(
        _render_argv("phase25.wg100-routes", target="atius-srv-1"),
        runner=runner,
        hostname="atius-srv-1",
    )
    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE

    monkeypatch.setattr(
        probe,
        "MAX_RESULT_BYTES",
        len("ATIUS_RUNBOOK_RESULT_V1 {}\n"),
    )
    code, stdout, stderr = _run_main(
        _render_argv("phase25.wg100-routes", target="atius-srv-1"),
        runner=FakeRunner(),
        hostname="atius-srv-1",
    )
    assert code != 0
    assert stdout == ""
    assert stderr == probe.SANITIZED_ERROR_LINE


def test_probe_ignores_caller_environment_and_subprocess_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakePopen:
        returncode = 0
        pid = 12345

        def __init__(self, argv: Any, **kwargs: Any) -> None:
            captured["argv"] = argv
            captured.update(kwargs)
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()

        def wait(self, timeout: float) -> int:
            captured["timeout"] = timeout
            return self.returncode

        def poll(self) -> int:
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setenv("PATH", "/tmp/attacker")
    monkeypatch.setenv("LD_PRELOAD", "/tmp/attacker.so")
    monkeypatch.setattr(probe.subprocess, "Popen", FakePopen)

    result = probe.subprocess_runner(("/usr/bin/true",), 1)

    assert result.returncode == 0
    assert captured["shell"] is False
    assert captured["env"] == probe.CLEAN_ENVIRONMENT
    assert "LD_PRELOAD" not in captured["env"]
    assert captured["stdin"] is probe.subprocess.DEVNULL
    assert captured["stdout"] is probe.subprocess.PIPE
    assert captured["stderr"] is probe.subprocess.PIPE
    assert captured["start_new_session"] is True
    assert captured["bufsize"] == 0


def test_probe_kills_real_oversized_emitter_before_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "Queue(maxsize=4)" in PROBE_PATH.read_text(encoding="utf-8")
    monkeypatch.setattr(probe, "MAX_COMMAND_OUTPUT_BYTES", 4096)
    started = monotonic()
    with pytest.raises(probe.ProbeError):
        probe.subprocess_runner(
            (
                sys.executable,
                "-c",
                "import os\nwhile True: os.write(1, b'x' * 8192)",
            ),
            5,
        )
    assert monotonic() - started < 2


def test_probe_output_is_single_compact_deterministic_sentinel() -> None:
    argv = _render_argv("phase25.wg100-routes", target="atius-srv-1")
    first = _run_main(argv, runner=FakeRunner(), hostname="atius-srv-1")
    second = _run_main(argv, runner=FakeRunner(), hostname="atius-srv-1")

    assert first == second
    assert first[0] == 0
    assert len(first[1].encode()) < 32768
    assert " " not in first[1].split(" ", 1)[1]
    assert os.linesep not in first[1].rstrip("\n")


def _wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    relative = resolved.as_posix().split(":", 1)[1].lstrip("/")
    return f"/mnt/{drive}/{relative}"


def _bash(command: str, *args: str) -> subprocess.CompletedProcess[str]:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            suffix=".sh",
            delete=False,
        ) as stream:
            stream.write("#!/usr/bin/env bash\n")
            stream.write(command)
            stream.write("\n")
            temporary_path = Path(stream.name)
        return subprocess.run(
            ["bash", _wsl_path(temporary_path), *args],
            check=False,
            text=True,
            capture_output=True,
            timeout=60,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _installer_harness(body: str) -> subprocess.CompletedProcess[str]:
    setup = r"""
set -euo pipefail
workspace=$(mktemp -d /tmp/oci-admin-guest-probe-test.XXXXXX)
case "$workspace" in /tmp/oci-admin-guest-probe-test.*) ;; *) exit 91 ;; esac
trap 'rm -rf -- "$workspace"' EXIT
source_repo="$workspace/source"
test_root="$workspace/root"
mkdir -p "$source_repo/modules/fleet-control-plane/tools"
mkdir -p "$source_repo/modules/fleet-control-plane/scripts"
mkdir -p "$source_repo/modules/fleet-control-plane/configs"
mkdir -p "$test_root"
cp -- "$1" "$source_repo/modules/fleet-control-plane/tools/oci-admin-guest-probe-v1.py"
cp -- "$2" "$source_repo/modules/fleet-control-plane/scripts/install-oci-admin-guest-probe-v1.sh"
cp -- "$3" "$source_repo/modules/fleet-control-plane/configs/102-oci-admin-guest-probe-v1.sudoers"
cp -- "$4" "$workspace/attestation.json"
git -C "$source_repo" init -q
git -C "$source_repo" config user.email phase25-test@atius.invalid
git -C "$source_repo" config user.name phase25-test
git -C "$source_repo" config commit.gpgsign false
git -C "$source_repo" add modules/fleet-control-plane/tools/oci-admin-guest-probe-v1.py
git -C "$source_repo" add modules/fleet-control-plane/scripts/install-oci-admin-guest-probe-v1.sh
git -C "$source_repo" add modules/fleet-control-plane/configs/102-oci-admin-guest-probe-v1.sudoers
git -C "$source_repo" commit -q -m fixture
source_commit=$(git -C "$source_repo" rev-parse HEAD)
helper_sha="sha256:$(sha256sum "$source_repo/modules/fleet-control-plane/tools/oci-admin-guest-probe-v1.py" | awk '{print $1}')"
sudoers_sha="sha256:$(sha256sum "$source_repo/modules/fleet-control-plane/configs/102-oci-admin-guest-probe-v1.sudoers" | awk '{print $1}')"
attestation_sha=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["digest"])' "$workspace/attestation.json")
installer="$source_repo/modules/fleet-control-plane/scripts/install-oci-admin-guest-probe-v1.sh"
installer_args=(
  --expected-source-commit "$source_commit"
  --expected-helper-sha256 "$helper_sha"
  --expected-sudoers-sha256 "$sudoers_sha"
  --expected-attestation-sha256 "$attestation_sha"
  --host-id atius-srv-1
  --rollback-receipt-id phase25-test-receipt
)
"""
    attestation_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            suffix=".json",
            delete=False,
        ) as stream:
            stream.write(
                json.dumps(
                    _attestation_document(),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
            attestation_path = Path(stream.name)
        return _bash(
            setup + "\n" + textwrap.dedent(body),
            _wsl_path(PROBE_PATH),
            _wsl_path(INSTALLER_PATH),
            _wsl_path(SUDOERS_PATH),
            _wsl_path(attestation_path),
        )
    finally:
        if attestation_path is not None:
            attestation_path.unlink(missing_ok=True)


def test_installer_probe_contract_is_closed_and_sudoers_is_least_privilege() -> None:
    installer = INSTALLER_PATH.read_text(encoding="utf-8")
    sudoers = SUDOERS_PATH.read_text(encoding="utf-8")
    normalized_sudoers = sudoers.replace("\\:", ":")

    assert "preview|install|rollback" in installer
    assert "--expected-source-commit" in installer
    assert "--expected-helper-sha256" in installer
    assert "--expected-sudoers-sha256" in installer
    assert "--expected-attestation-sha256" in installer
    assert "--host-id" in installer
    assert "--rollback-receipt-id" in installer
    assert "--root" not in installer
    assert "--source" not in installer
    assert "/usr/local/libexec/oci-admin-guest-probe-v1" in installer
    assert "/etc/sudoers.d/102-oci-admin-guest-probe-v1" in installer
    assert "/etc/oci-admin-guest-probe-v1/attestation.json" in installer
    assert "visudo" in installer and "-cf" in installer and "-c" in installer
    assert "root:root" in installer
    assert "0755" in installer and "0440" in installer and "0400" in installer
    assert "ABSENT" in installer

    assert "Defaults:ocarun env_reset" in sudoers
    assert "Defaults:ocarun !setenv" in sudoers
    assert "ocarun ALL=(root) NOPASSWD:" in sudoers
    assert "/usr/local/libexec/oci-admin-guest-probe-v1 execute" in sudoers
    assert "/bin/sh" not in sudoers
    assert "/bin/bash" not in sudoers
    assert "/usr/bin/python" not in sudoers
    for runbook_id, filename in MANIFEST_FILES.items():
        manifest = json.loads((MANIFEST_ROOT / filename).read_text(encoding="utf-8"))
        assert runbook_id in normalized_sudoers
        assert manifest["digest"] in normalized_sudoers

    syntax = _bash("visudo -cf \"$1\"", _wsl_path(SUDOERS_PATH))
    assert syntax.returncode == 0, syntax.stderr


def test_probe_rejects_world_writable_attestation_parent_chain() -> None:
    result = _bash(
        r"""
set -euo pipefail
root=$(mktemp -d /tmp/oci-admin-guest-probe-parent.XXXXXX)
trap 'rm -rf -- "$root"' EXIT
mkdir -p "$root/etc/oci-admin-guest-probe-v1"
chmod 0777 "$root/etc/oci-admin-guest-probe-v1"
printf '{}\n' >"$root/etc/oci-admin-guest-probe-v1/attestation.json"
chmod 0400 "$root/etc/oci-admin-guest-probe-v1/attestation.json"
set +e
python3 - "$1" "$root" <<'PY'
import importlib.util,os,pathlib,sys
spec=importlib.util.spec_from_file_location('probe_parent_test',sys.argv[1])
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
try:
 module.read_root_owned_file(
  pathlib.Path(sys.argv[2])/'etc/oci-admin-guest-probe-v1/attestation.json',
  expected_mode=0o400,max_bytes=65536,root=pathlib.Path(sys.argv[2]),
  expected_uid=os.getuid(),expected_gid=os.getgid())
except module.ProbeError:
 raise SystemExit(0)
raise SystemExit(1)
PY
rc=$?
set -e
[[ $rc -eq 0 ]]
""",
        _wsl_path(PROBE_PATH),
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_preview_install_rollback_and_idempotency() -> None:
    result = _installer_harness(
        r"""
export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$test_root"
source "$installer"
before=$(find "$test_root" -mindepth 1 -print -quit)
guest_probe_installer_main preview "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/preview.json"
after=$(find "$test_root" -mindepth 1 -print -quit)
[[ -z "$before" && -z "$after" ]]
grep -q '^ATIUS_GUEST_PROBE_INSTALL_RECEIPT_V1 ' "$workspace/preview.json"

guest_probe_installer_main install "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/install-1.json"
helper_dest="$test_root/usr/local/libexec/oci-admin-guest-probe-v1"
sudoers_dest="$test_root/etc/sudoers.d/102-oci-admin-guest-probe-v1"
attestation_dest="$test_root/etc/oci-admin-guest-probe-v1/attestation.json"
[[ -f "$helper_dest" && ! -L "$helper_dest" ]]
[[ -f "$sudoers_dest" && ! -L "$sudoers_dest" ]]
[[ -f "$attestation_dest" && ! -L "$attestation_dest" ]]
[[ $(stat -c '%a' "$helper_dest") == 755 ]]
[[ $(stat -c '%a' "$sudoers_dest") == 440 ]]
[[ $(stat -c '%a' "$attestation_dest") == 400 ]]
[[ "sha256:$(sha256sum "$helper_dest" | awk '{print $1}')" == "$helper_sha" ]]
[[ "sha256:$(sha256sum "$sudoers_dest" | awk '{print $1}')" == "$sudoers_sha" ]]
[[ $(stat -c '%u:%g' "$helper_dest") == "$(id -u):$(id -g)" ]]
[[ $(stat -c '%u:%g' "$sudoers_dest") == "$(id -u):$(id -g)" ]]

guest_probe_installer_main install "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/install-2.json"
cmp -s "$workspace/install-1.json" "$workspace/install-2.json"
guest_probe_installer_main rollback "${installer_args[@]}" >"$workspace/rollback-1.json"
[[ ! -e "$helper_dest" && ! -L "$helper_dest" ]]
[[ ! -e "$sudoers_dest" && ! -L "$sudoers_dest" ]]
[[ ! -e "$attestation_dest" && ! -L "$attestation_dest" ]]
guest_probe_installer_main rollback "${installer_args[@]}" >"$workspace/rollback-2.json"
cmp -s "$workspace/rollback-1.json" "$workspace/rollback-2.json"
grep -q '"status":"rolled-back"' "$workspace/rollback-1.json"
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_restores_exact_present_preimages() -> None:
    result = _installer_harness(
        r"""
helper_dest="$test_root/usr/local/libexec/oci-admin-guest-probe-v1"
sudoers_dest="$test_root/etc/sudoers.d/102-oci-admin-guest-probe-v1"
attestation_dest="$test_root/etc/oci-admin-guest-probe-v1/attestation.json"
mkdir -p "$(dirname "$helper_dest")" "$(dirname "$sudoers_dest")" "$(dirname "$attestation_dest")"
printf '#!/bin/sh\nexit 7\n' >"$helper_dest"
printf 'Defaults env_reset\n' >"$sudoers_dest"
printf '{"legacy":true}\n' >"$attestation_dest"
chmod 0700 "$helper_dest"
chmod 0400 "$sudoers_dest"
chmod 0600 "$attestation_dest"
before_helper=$(sha256sum "$helper_dest" | awk '{print $1}')
before_sudoers=$(sha256sum "$sudoers_dest" | awk '{print $1}')
before_attestation=$(sha256sum "$attestation_dest" | awk '{print $1}')

export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$test_root"
source "$installer"
guest_probe_installer_main install "${installer_args[@]}" <"$workspace/attestation.json" >/dev/null
guest_probe_installer_main rollback "${installer_args[@]}" >"$workspace/rollback.json"
[[ $(sha256sum "$helper_dest" | awk '{print $1}') == "$before_helper" ]]
[[ $(sha256sum "$sudoers_dest" | awk '{print $1}') == "$before_sudoers" ]]
[[ $(sha256sum "$attestation_dest" | awk '{print $1}') == "$before_attestation" ]]
[[ $(stat -c '%a' "$helper_dest") == 700 ]]
[[ $(stat -c '%a' "$sudoers_dest") == 400 ]]
[[ $(stat -c '%a' "$attestation_dest") == 600 ]]
grep -q '"state":"PRESENT"' "$workspace/rollback.json"
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_failure_at_every_stage_restores_absence() -> None:
    result = _installer_harness(
        r"""
for stage in preimage helper-stage attestation-stage sudoers-stage helper-replace attestation-replace sudoers-replace global-visudo readback; do
  stage_root="$workspace/root-$stage"
  mkdir -p "$stage_root"
  (
    export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
    export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$stage_root"
    export OCI_ADMIN_GUEST_PROBE_TEST_FAIL_STAGE="$stage"
    source "$installer"
    set +e
    guest_probe_installer_main install "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/$stage.json" 2>"$workspace/$stage.err"
    rc=$?
    set -e
    [[ $rc -eq 2 ]]
  )
  [[ ! -e "$stage_root/usr/local/libexec/oci-admin-guest-probe-v1" ]]
  [[ ! -e "$stage_root/etc/sudoers.d/102-oci-admin-guest-probe-v1" ]]
  [[ ! -e "$stage_root/etc/oci-admin-guest-probe-v1/attestation.json" ]]
  grep -q '"status":"failed-restored"' "$workspace/$stage.json" || {
    printf 'missing failed receipt for %s\n' "$stage" >&2
    cat "$workspace/$stage.json" >&2
    exit 1
  }
  grep -q '^oci-admin-guest-probe-installer-v1: rejected$' "$workspace/$stage.err" || {
    printf 'missing sanitized error for %s\n' "$stage" >&2
    cat "$workspace/$stage.err" >&2
    exit 1
  }
done
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_denies_public_path_command_and_environment_override() -> None:
    script = _wsl_path(INSTALLER_PATH)
    valid = [
        "preview",
        "--expected-source-commit",
        "0" * 40,
        "--expected-helper-sha256",
        "sha256:" + "1" * 64,
        "--expected-sudoers-sha256",
        "sha256:" + "2" * 64,
        "--expected-attestation-sha256",
        "sha256:" + "3" * 64,
        "--host-id",
        "atius-srv-1",
        "--rollback-receipt-id",
        "phase25-public-deny",
    ]
    path_override = _bash(
        '"$1" "${@:2}" --root /tmp/caller',
        script,
        *valid,
    )
    assert path_override.returncode == 64
    assert "caller" not in path_override.stdout

    command_override = _bash(
        '"$1" "${@:2}" --command id',
        script,
        *valid,
    )
    assert command_override.returncode == 64
    assert "uid=" not in command_override.stdout + command_override.stderr

    environment_override = _bash(
        'OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1 '
        'OCI_ADMIN_GUEST_PROBE_TEST_ROOT=/tmp/caller "$1" "${@:2}"',
        script,
        *valid,
    )
    assert environment_override.returncode == 64


def test_installer_probe_rejects_dirty_source_identity() -> None:
    result = _installer_harness(
        r"""
printf '\n# dirty\n' >>"$source_repo/modules/fleet-control-plane/configs/102-oci-admin-guest-probe-v1.sudoers"
export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$test_root"
source "$installer"
set +e
guest_probe_installer_main preview "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/out" 2>"$workspace/err"
rc=$?
set -e
[[ $rc -eq 2 ]]
[[ ! -s "$workspace/out" ]]
grep -q '^oci-admin-guest-probe-installer-v1: rejected$' "$workspace/err"
[[ -z $(find "$test_root" -mindepth 1 -print -quit) ]]
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_denies_symlink_parent_and_control_dir_drift() -> None:
    result = _installer_harness(
        r"""
outside="$workspace/outside"
mkdir -p "$outside"
mkdir -p "$test_root"
ln -s "$outside" "$test_root/usr"
(
  export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
  export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$test_root"
  source "$installer"
  set +e
  guest_probe_installer_main preview "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/symlink.out" 2>"$workspace/symlink.err"
  rc=$?
  set -e
  [[ $rc -eq 2 ]]
)
[[ ! -s "$workspace/symlink.out" ]]
[[ -z $(find "$outside" -mindepth 1 -print -quit) ]]
rm "$test_root/usr"

state="$test_root/var/lib/oci-admin-guest-probe-v1"
mkdir -p "$state"
chmod 0777 "$state"
(
  export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
  export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$test_root"
  source "$installer"
  set +e
  guest_probe_installer_main install "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/state.out" 2>"$workspace/state.err"
  rc=$?
  set -e
  [[ $rc -eq 2 ]]
)
[[ ! -s "$workspace/state.out" ]]
[[ ! -e "$test_root/usr/local/libexec/oci-admin-guest-probe-v1" ]]
[[ ! -e "$test_root/etc/sudoers.d/102-oci-admin-guest-probe-v1" ]]
[[ ! -e "$test_root/etc/oci-admin-guest-probe-v1/attestation.json" ]]
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_rejects_world_writable_destination_parents() -> None:
    result = _installer_harness(
        r"""
parent_root="$workspace/root-parents"
mkdir -p "$parent_root/usr/local/libexec"
mkdir -p "$parent_root/etc/sudoers.d"
mkdir -p "$parent_root/etc/oci-admin-guest-probe-v1"
chmod 0777 "$parent_root/usr/local/libexec"
chmod 0777 "$parent_root/etc/sudoers.d"
chmod 0777 "$parent_root/etc/oci-admin-guest-probe-v1"
(
  export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
  export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$parent_root"
  source "$installer"
  set +e
  guest_probe_installer_main preview "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/parents.out" 2>"$workspace/parents.err"
  rc=$?
  set -e
  [[ $rc -eq 2 ]]
)
[[ ! -s "$workspace/parents.out" ]]
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_rollback_journal_resumes_every_stage() -> None:
    result = _installer_harness(
        r"""
for stage in rollback-sudoers-closed rollback-helper-restored rollback-attestation-restored rollback-sudoers-restored rollback-validated rollback-readback; do
  stage_root="$workspace/resume-$stage"
  mkdir -p "$stage_root"
  (
    export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
    export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$stage_root"
    source "$installer"
    guest_probe_installer_main install "${installer_args[@]}" <"$workspace/attestation.json" >/dev/null
  )
  (
    export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
    export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$stage_root"
    export OCI_ADMIN_GUEST_PROBE_TEST_FAIL_STAGE="$stage"
    source "$installer"
    set +e
    guest_probe_installer_main rollback "${installer_args[@]}" >"$workspace/$stage.out" 2>"$workspace/$stage.err"
    rc=$?
    set -e
    [[ $rc -eq 2 ]]
  )
  state="$stage_root/var/lib/oci-admin-guest-probe-v1/receipts/phase25-test-receipt/state.json"
  grep -q '"status":"rolling-back"' "$state"
  (
    export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
    export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$stage_root"
    source "$installer"
    guest_probe_installer_main rollback "${installer_args[@]}" >"$workspace/$stage.retry"
    guest_probe_installer_main rollback "${installer_args[@]}" >"$workspace/$stage.repeat"
  )
  cmp -s "$workspace/$stage.retry" "$workspace/$stage.repeat"
  [[ ! -e "$stage_root/usr/local/libexec/oci-admin-guest-probe-v1" ]]
  [[ ! -e "$stage_root/etc/sudoers.d/102-oci-admin-guest-probe-v1" ]]
  [[ ! -e "$stage_root/etc/oci-admin-guest-probe-v1/attestation.json" ]]
done
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_bounds_real_emitter_before_timeout() -> None:
    assert "Queue(maxsize=4)" in INSTALLER_PATH.read_text(encoding="utf-8")
    result = _installer_harness(
        r"""
export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$test_root"
export OCI_ADMIN_GUEST_PROBE_TEST_EMIT_OVERSIZE=1
source "$installer"
started=$(date +%s)
set +e
guest_probe_installer_main preview "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/bound.out" 2>"$workspace/bound.err"
rc=$?
set -e
elapsed=$(($(date +%s)-started))
[[ $rc -eq 2 ]]
[[ $elapsed -lt 3 ]]
[[ ! -s "$workspace/bound.out" ]]
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_git_blob_verification_ignores_malicious_fsmonitor() -> None:
    result = _installer_harness(
        r"""
marker="$workspace/fsmonitor-ran"
monitor="$workspace/fsmonitor.sh"
printf '#!/bin/sh\ntouch %q\nprintf "0\\n"\n' "$marker" >"$monitor"
chmod 0755 "$monitor"
git -C "$source_repo" config core.fsmonitor "$monitor"
export OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING=1
export OCI_ADMIN_GUEST_PROBE_TEST_ROOT="$test_root"
source "$installer"
guest_probe_installer_main preview "${installer_args[@]}" <"$workspace/attestation.json" >"$workspace/git.out"
[[ ! -e "$marker" ]]
grep -q '^ATIUS_GUEST_PROBE_INSTALL_RECEIPT_V1 ' "$workspace/git.out"
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_probe_source_digests_match_files() -> None:
    helper_digest = "sha256:" + hashlib.sha256(PROBE_PATH.read_bytes()).hexdigest()
    sudoers_digest = "sha256:" + hashlib.sha256(SUDOERS_PATH.read_bytes()).hexdigest()
    assert helper_digest == probe.self_digest()
    assert helper_digest in INSTALLER_PATH.read_text(encoding="utf-8") or (
        "--expected-helper-sha256" in INSTALLER_PATH.read_text(encoding="utf-8")
    )
    assert sudoers_digest.startswith("sha256:")
