from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
from typing import Any

import pytest


OMNI_REPO = Path(__file__).resolve().parents[3]
OCI_ADMIN_REPO = OMNI_REPO.parent / "oci-admin"
PROBE_PATH = (
    OMNI_REPO
    / "modules/fleet-control-plane/tools/oci-admin-guest-probe-v1.py"
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
SPEC = importlib.util.spec_from_file_location("oci_admin_guest_probe_v1", PROBE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def _manifest(runbook_id: str) -> dict[str, Any]:
    return json.loads(
        (MANIFEST_ROOT / MANIFEST_FILES[runbook_id]).read_text(encoding="utf-8")
    )


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
) -> list[str]:
    digest = "sha256:" + "1" * 64
    return [
        "execute",
        "--runbook",
        "phase25.coredns-peer-readback",
        "--version",
        "1",
        "--manifest-digest",
        _manifest("phase25.coredns-peer-readback")["digest"],
        "--target-binding-digest",
        target_binding_digest or digest,
        "--probe-digest",
        probe_digest or probe.self_digest(),
        "--target",
        target,
        "--peer-set-digest",
        peer_set_digest or ("sha256:" + "2" * 64),
        "--projection-digest",
        projection_digest or ("sha256:" + "3" * 64),
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
) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = probe.main(
        argv,
        runner=runner,
        hostname_provider=lambda: hostname,
        resolver=resolver,
        tcp_probe=tcp_probe,
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

        def __init__(self, argv: Any, **kwargs: Any) -> None:
            captured["argv"] = argv
            captured.update(kwargs)

        def communicate(self, timeout: int) -> tuple[bytes, bytes]:
            captured["timeout"] = timeout
            return b"", b""

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


def test_probe_output_is_single_compact_deterministic_sentinel() -> None:
    argv = _render_argv("phase25.wg100-routes", target="atius-srv-1")
    first = _run_main(argv, runner=FakeRunner(), hostname="atius-srv-1")
    second = _run_main(argv, runner=FakeRunner(), hostname="atius-srv-1")

    assert first == second
    assert first[0] == 0
    assert len(first[1].encode()) < 32768
    assert " " not in first[1].split(" ", 1)[1]
    assert os.linesep not in first[1].rstrip("\n")
