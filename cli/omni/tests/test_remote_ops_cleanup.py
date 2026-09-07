"""Regression tests for the Podman-only fleet cleanup policy."""

from pathlib import Path
import subprocess
import time

from click.testing import CliRunner

from omni import remote_ops


def test_storage_audit_is_podman_only():
    script = remote_ops._storage_audit_script()

    assert "podman system df" in script
    assert "docker" not in script.lower()
    assert "/var/lib/rancher/k3s" not in script
    assert '20s find "$HOME"' in script
    assert "timeout --signal=TERM --kill-after=2s 10s podman system df" in script
    assert '5s du -sh "$candidate"' in script


def test_autoclean_is_podman_only_and_preserves_tagged_images():
    script = remote_ops._autoclean_script(dry_run=False, include_volumes=False)

    assert "podman image prune -f" in script
    assert "podman image prune -af" not in script
    assert "podman volume prune -f" in script
    assert 'INCLUDE_VOLUMES=0' in script
    assert "docker" not in script.lower()
    assert "crictl" not in script
    assert "k3s ctr" not in script
    assert "/var/lib/rancher/k3s" not in script


def test_autoclean_requires_explicit_volume_opt_in():
    default_script = remote_ops._autoclean_script(
        dry_run=False, include_volumes=False
    )
    opted_in_script = remote_ops._autoclean_script(
        dry_run=False, include_volumes=True
    )

    assert 'INCLUDE_VOLUMES=0' in default_script
    assert 'INCLUDE_VOLUMES=1' in opted_in_script


def test_storage_audit_reports_timeout_and_continues(monkeypatch):
    monkeypatch.setattr(remote_ops, "_host_ids_for_arg", lambda _host: ["atius-srv-1", "atius-srv-2"])
    monkeypatch.setattr(
        remote_ops,
        "_find_host",
        lambda host: (
            remote_ops.REPO / f"inventory/hosts/{host}.yaml",
            "ubuntu@localhost",
            host,
        ),
    )

    def timeout_then_success(_path, _target, host, _script, timeout):
        if host == "atius-srv-1":
            raise subprocess.TimeoutExpired(cmd="audit", timeout=timeout)
        return subprocess.CompletedProcess(args="audit", returncode=0, stdout="SECOND_HOST_OK\n", stderr="")

    monkeypatch.setattr(remote_ops, "_run_host", timeout_then_success)

    result = CliRunner().invoke(
        remote_ops.srv,
        ["storage-audit", "atius-srv-1", "--timeout", "7"],
    )

    assert result.exit_code == 0
    assert "timeout: host excedeu 7s" in result.output
    assert "SECOND_HOST_OK" in result.output
    assert "summary ok=1 remote-error=0 timeout=1 runner-error=0" in result.output


def test_all_targets_only_active_inventory_hosts(monkeypatch):
    monkeypatch.setattr(
        remote_ops,
        "_list_hosts",
        lambda: [
            {"id": "srv-active", "status": "active", "os": "ubuntu-24.04"},
            {"id": "windows", "status": "active", "os": "windows-11"},
            {"id": "srv-planned", "status": "planned", "os": "ubuntu-24.04"},
            {"id": "srv-template", "status": "template", "os": "ubuntu-24.04"},
            {"id": "srv-blocked", "status": "blocked-network-readdress", "os": "ubuntu-24.04"},
            {"id": "srv-retired", "status": "retired", "os": "ubuntu-24.04"},
        ],
    )

    assert remote_ops._host_ids_for_arg("all") == ["srv-active"]
    assert remote_ops._host_ids_for_arg("srv-planned") == ["srv-planned"]


def test_inventory_parser_ignores_nested_id_and_status(tmp_path: Path, monkeypatch) -> None:
    hosts = tmp_path / "hosts"
    hosts.mkdir()
    (hosts / "srv.yaml").write_text(
        "id: srv-top\n"
        "aliases:\n"
        "  - srv\n"
        "role: production\n"
        "access:\n"
        "  ssh: ubuntu@10.0.0.1\n"
        "status: active\n"
        "programs:\n"
        "  - id: nested-program\n"
        "    status: paused\n"
    )
    monkeypatch.setattr(remote_ops, "HOSTS_DIR", hosts)

    assert remote_ops._list_hosts() == [
        {
            "id": "srv-top",
            "role": "production",
            "status": "active",
            "ssh": "ubuntu@10.0.0.1",
            "aliases": "srv",
            "os": "",
        }
    ]
    assert remote_ops._parse_host(hosts / "srv.yaml", "srv") == (
        hosts / "srv.yaml",
        "ubuntu@10.0.0.1",
        "srv-top",
    )


def test_local_timeout_kills_descendant_process_group(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    command = f"sleep 30 & child=$!; printf '%s' \"$child\" > {pid_file}; wait"

    started = time.monotonic()
    try:
        remote_ops._run_host(
            remote_ops.REPO / "inventory/hosts/atius-srv-1.yaml",
            "ubuntu@localhost",
            "atius-srv-1",
            command,
            timeout=0.2,
        )
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError("timeout expected")

    assert time.monotonic() - started < 5
    child_pid = int(pid_file.read_text())
    for _ in range(40):
        if not Path(f"/proc/{child_pid}").exists():
            break
        time.sleep(0.05)
    assert not Path(f"/proc/{child_pid}").exists()


def test_ssh_target_port_and_identity_are_rendered(monkeypatch):
    calls = []
    monkeypatch.setattr(
        remote_ops,
        "_run_process_group",
        lambda argv, timeout: (
            calls.append((argv, timeout))
            or subprocess.CompletedProcess(argv, 0, "ok", "")
        ),
    )

    result = remote_ops._ssh_run(
        "termux@10.100.100.10:8022",
        "printf ok",
        timeout=7,
        identity_file="~/.ssh/id_oracle",
    )

    assert result.returncode == 0
    argv, timeout = calls[0]
    port_index = argv.index("-p")
    assert argv[port_index : port_index + 2] == ["-p", "8022"]
    assert "termux@10.100.100.10" in argv
    assert "IdentitiesOnly=yes" in argv
    assert str(Path.home() / ".ssh/id_oracle") in argv
    assert timeout == 7


def test_inventory_route_order_is_preserved(tmp_path: Path) -> None:
    host = tmp_path / "termux.yaml"
    host.write_text(
        "id: termux\nstatus: active\naccess:\n  ssh: termux@10.0.0.10:8022\n"
        "  ssh_route_order:\n    - termux@10.0.0.10:8022\n    - termux@example.com:8322\n"
        "platform:\n  os: termux\n"
    )

    assert remote_ops._ssh_candidates(host, "termux@10.0.0.10:8022") == [
        "termux@10.0.0.10:8022",
        "termux@example.com:8322",
    ]


def test_srv4_inventory_declares_required_identity_file():
    path = remote_ops.REPO / "inventory/hosts/atius-srv-4.yaml"
    assert remote_ops._inventory(path)["access"]["identity_file"] == "/home/ubuntu/.ssh/id_oracle"


def test_ssh_fallback_probes_routes_but_executes_payload_once(tmp_path: Path, monkeypatch):
    host = tmp_path / "host.yaml"
    host.write_text(
        "id: host\nstatus: active\naccess:\n  ssh: user@primary:22\n"
        "  identity_file: ~/.ssh/id_oracle\n"
        "  ssh_route_order:\n    - user@primary:22\n    - user@fallback:2222\n"
        "platform:\n  os: ubuntu-24.04\n"
    )
    calls = []

    def fake_run(target, command, timeout, *, identity_file=""):
        calls.append((target, command, timeout, identity_file))
        if command == "printf __OMNI_SSH_READY__" and target == "user@primary:22":
            return subprocess.CompletedProcess(target, 255, "", "connection refused")
        if command == "printf __OMNI_SSH_READY__":
            return subprocess.CompletedProcess(target, 0, "__OMNI_SSH_READY__", "")
        return subprocess.CompletedProcess(target, 0, "PAYLOAD_OK", "")

    monkeypatch.setattr(remote_ops, "_ssh_run", fake_run)
    result = remote_ops._ssh_run_any(host, "user@primary:22", "do-side-effect", timeout=30)

    assert result.stdout == "PAYLOAD_OK"
    assert [call[0] for call in calls] == [
        "user@primary:22",
        "user@fallback:2222",
        "user@fallback:2222",
    ]
    assert sum(call[1] == "do-side-effect" for call in calls) == 1
    assert all(call[3] == "~/.ssh/id_oracle" for call in calls)
