"""Tests for Omni Routine Fleet Dispatcher."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from omni.routine_engine import (
    RoutineDefinition,
    RoutineRun,
    RoutineState,
)
from omni.routine_dispatcher import (
    HostRoute,
    HostRouteResolver,
    RoutineDispatcher,
)


@pytest.fixture
def mock_inventory(tmp_path: Path) -> Path:
    hosts_dir = tmp_path / "inventory" / "hosts"
    hosts_dir.mkdir(parents=True, exist_ok=True)

    srv1_yaml = """
id: atius-srv-1
aliases:
  - srv1
access:
  ssh: ubuntu@10.100.100.1
  public_ip: 137.131.190.161
  vpn_ip: 10.100.100.1
  oci_private_ip: 10.11.1.11
"""
    (hosts_dir / "atius-srv-1.yaml").write_text(srv1_yaml.strip(), encoding="utf-8")

    w11_yaml = """
id: giovanni-w11-pc
aliases:
  - w11
access:
  ssh: muniz@10.100.100.8
  vpn_ip: 10.100.100.8
  casa_wan_ssh: muniz@ssh-giovanni-w11-pc.atius.com.br:8122
"""
    (hosts_dir / "giovanni-w11-pc.yaml").write_text(w11_yaml.strip(), encoding="utf-8")

    return hosts_dir


def test_host_route_resolver_resolves_ordered_routes(mock_inventory: Path) -> None:
    resolver = HostRouteResolver(inventory_dir=mock_inventory)
    routes = resolver.resolve_routes("atius-srv-1")

    assert len(routes) == 3
    # 1. DRG / Private IP
    assert routes[0].route_type == "drg_private"
    assert routes[0].user == "ubuntu"
    assert routes[0].host == "10.11.1.11"
    assert routes[0].port == 22

    # 2. WireGuard / VPN IP
    assert routes[1].route_type == "wireguard"
    assert routes[1].user == "ubuntu"
    assert routes[1].host == "10.100.100.1"
    assert routes[1].port == 22

    # 3. Public WAN IP
    assert routes[2].route_type == "public_wan"
    assert routes[2].user == "ubuntu"
    assert routes[2].host == "137.131.190.161"
    assert routes[2].port == 22


def test_host_route_resolver_resolves_alias_and_port(mock_inventory: Path) -> None:
    resolver = HostRouteResolver(inventory_dir=mock_inventory)
    routes = resolver.resolve_routes("w11")

    assert len(routes) == 2
    # 1. WireGuard
    assert routes[0].route_type == "wireguard"
    assert routes[0].host == "10.100.100.8"
    assert routes[0].port == 22

    # 2. Casa WAN SSH with port 8122
    assert routes[1].route_type == "casa_wan"
    assert routes[1].host == "ssh-giovanni-w11-pc.atius.com.br"
    assert routes[1].port == 8122
    assert routes[1].user == "muniz"


def test_dispatch_local(tmp_path: Path) -> None:
    dispatcher = RoutineDispatcher(
        inventory_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        locks_dir=tmp_path / "locks",
        local_hostnames={"localhost", "local", "my-machine"},
    )
    routine = RoutineDefinition(
        id="test:local",
        name="Local Test",
        description="Local execution",
        target_host="local",
        command_argv=["python", "-c", "print('hello local')"],
    )

    run = dispatcher.dispatch(routine)
    assert run.state == RoutineState.COMPLETED
    assert "hello local" in run.stdout


def test_dispatch_remote_ssh_primary_success(mock_inventory: Path, tmp_path: Path) -> None:
    dispatcher = RoutineDispatcher(
        inventory_dir=mock_inventory,
        logs_dir=tmp_path / "logs",
        locks_dir=tmp_path / "locks",
        local_hostnames={"localhost", "local"},
    )
    routine = RoutineDefinition(
        id="test:remote-primary",
        name="Remote Test",
        description="Remote execution",
        target_host="atius-srv-1",
        command_argv=["omni", "status"],
    )

    with patch("subprocess.Popen") as mock_popen:
        proc = MagicMock()
        proc.communicate.return_value = ("remote status ok\n", "")
        proc.returncode = 0
        mock_popen.return_value = proc

        run = dispatcher.dispatch(routine)
        assert run.state == RoutineState.COMPLETED
        assert "remote status ok" in run.stdout
        assert run.metrics.get("route_used") == "drg_private"
        assert run.metrics.get("target_endpoint") == "ubuntu@10.11.1.11:22"

        # Verifica flags estritas de SSH
        args, _ = mock_popen.call_args
        ssh_cmd = args[0]
        assert "BatchMode=yes" in " ".join(ssh_cmd)
        assert "ConnectTimeout=5" in " ".join(ssh_cmd)


def test_dispatch_remote_ssh_fallback_to_wg(mock_inventory: Path, tmp_path: Path) -> None:
    dispatcher = RoutineDispatcher(
        inventory_dir=mock_inventory,
        logs_dir=tmp_path / "logs",
        locks_dir=tmp_path / "locks",
        local_hostnames={"localhost", "local"},
    )
    routine = RoutineDefinition(
        id="test:remote-fallback",
        name="Remote Test",
        description="Remote fallback execution",
        target_host="atius-srv-1",
        command_argv=["omni", "status"],
    )

    # 1ª rota (DRG) falha com timeout (255), 2ª rota (WG) tem sucesso (0)
    proc_fail = MagicMock()
    proc_fail.communicate.return_value = ("", "ssh: connect to host 10.11.1.11 port 22: Connection timed out\n")
    proc_fail.returncode = 255

    proc_ok = MagicMock()
    proc_ok.communicate.return_value = ("wg path success\n", "")
    proc_ok.returncode = 0

    with patch("subprocess.Popen", side_effect=[proc_fail, proc_ok]):
        run = dispatcher.dispatch(routine)
        assert run.state == RoutineState.COMPLETED
        assert "wg path success" in run.stdout
        assert run.metrics.get("route_used") == "wireguard"
        assert len(run.metrics.get("failed_attempts", [])) == 1


def test_dispatch_remote_all_routes_fail(mock_inventory: Path, tmp_path: Path) -> None:
    dispatcher = RoutineDispatcher(
        inventory_dir=mock_inventory,
        logs_dir=tmp_path / "logs",
        locks_dir=tmp_path / "locks",
        local_hostnames={"localhost", "local"},
    )
    routine = RoutineDefinition(
        id="test:remote-all-fail",
        name="Remote Test",
        description="Remote all fail",
        target_host="atius-srv-1",
        command_argv=["omni", "status"],
    )

    proc_fail = MagicMock()
    proc_fail.communicate.return_value = ("", "Connection refused\n")
    proc_fail.returncode = 255

    with patch("subprocess.Popen", return_value=proc_fail):
        run = dispatcher.dispatch(routine)
        assert run.state == RoutineState.FAILED
        assert "Todas as 3 rotas SSH falharam" in run.stderr
        assert len(run.metrics.get("failed_attempts", [])) == 3
