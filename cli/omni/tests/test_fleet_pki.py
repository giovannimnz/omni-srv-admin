from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from click.testing import CliRunner

REPO = Path(__file__).resolve().parents[3]
os.environ["OMNI_SRV_ADMIN"] = str(REPO)
sys.path.insert(0, str(REPO / "cli"))

from omni import fleet as fleet_module  # noqa: E402


def invoke_fleet(*args: str):
    runner = CliRunner()
    return runner.invoke(fleet_module.fleet, list(args))


def test_render_host_uses_horistic_ssh_and_sans():
    result = invoke_fleet("trust-pki", "render-host", "--host", "horistic-srv", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["host"] == "horistic-srv"
    assert payload["ssh"] == "horistic@10.100.100.4"
    assert "horistic-srv" in payload["sans"]["dns"]
    assert "horistic" in payload["sans"]["dns"]
    assert "10.100.100.4" in payload["sans"]["ip"]
    assert "100.102.126.61" in payload["sans"]["ip"]


def test_render_host_srv3_uses_current_vpn_ip_only():
    result = invoke_fleet("trust-pki", "render-host", "--host", "atius-srv-3", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "10.100.100.3" in payload["sans"]["ip"]


def test_default_plan_includes_windows_trust_client_for_auto_update():
    result = invoke_fleet("trust-pki", "plan", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    hosts = {item["host"]: item for item in payload["hosts"]}
    assert "giovanni-w11-pc" in hosts
    w11 = hosts["giovanni-w11-pc"]
    assert w11["status"] == "active"
    assert w11["service_tls_enabled"] is True
    assert w11["service_tls_mode"] == "trust-client"
    assert w11["auto_update"] is True
    assert w11["trust_store"] == "Cert:\\CurrentUser\\Root"
    assert "10.100.100.8" in w11["sans"]["ip"]
    assert [command["stage"] for command in w11["commands"]] == ["preflight", "install-ca", "verify"]
    assert [command["command_key"] for command in w11["commands"]] == [
        "omni.trust-pki.windows.preflight",
        "omni.trust-pki.windows.install-ca",
        "omni.trust-pki.windows.verify",
    ]
    assert "C:/Users/muniz/.local/share/omni-service-pki" in w11["paths"]["host_tls_dir"]


def test_onboard_host_dry_run_renders_full_sequence_without_secret_material():
    result = invoke_fleet("trust-pki", "onboard-host", "--host", "horistic-srv", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    stages = [command["stage"] for command in payload["commands"]]
    assert stages == ["preflight", "ensure-key-csr", "issue-host", "install-ca", "install-leaf", "verify"]
    issue = next(command for command in payload["commands"] if command["stage"] == "issue-host")
    assert issue["target_host"] == fleet_module.PKI_CA_HOST_ID
    serialized = json.dumps(payload)
    assert "BEGIN PRIVATE KEY" not in serialized
    assert "password" not in serialized.lower()
    assert "token" not in serialized.lower()


def test_onboard_host_approve_requires_execute_and_db():
    result = invoke_fleet("trust-pki", "onboard-host", "--host", "horistic-srv", "--approve")

    assert result.exit_code != 0
    assert "--approve exige --execute e --db" in result.output or "--approve exige --execute e --db" in str(result.exception)


def test_reconcile_host_detects_ip_san_drift():
    observed = json.dumps({"dns": ["horistic-srv", "horistic"], "ip": ["10.1.1.44"]})

    result = invoke_fleet(
        "trust-pki",
        "reconcile-host",
        "--host",
        "horistic-srv",
        "--observed-san-json",
        observed,
        "--json",
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["drift"]["status"] == "drift"
    assert payload["drift"]["needs_rotation"] is True
    assert "10.100.100.4" in payload["drift"]["missing"]["ip"]
    assert "10.1.1.44" in payload["drift"]["extra"]["ip"]


def test_rotate_host_renders_ip_change_sequence_without_ca_reinstall():
    observed = json.dumps({"dns": ["horistic-srv", "horistic"], "ip": ["10.1.1.44"]})

    result = invoke_fleet(
        "trust-pki",
        "rotate-host",
        "--host",
        "horistic-srv",
        "--observed-san-json",
        observed,
        "--json",
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["reason"] == "ip-change"
    assert payload["drift"]["needs_rotation"] is True
    assert [command["stage"] for command in payload["commands"]] == [
        "preflight",
        "ensure-key-csr",
        "issue-host",
        "install-leaf",
        "verify",
    ]


def test_install_trust_all_includes_windows_ca_update_only():
    result = invoke_fleet("trust-pki", "install-trust", "--host", "all", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    hosts = {item["host"]: item for item in payload["hosts"]}
    assert "giovanni-w11-pc" in hosts
    assert hosts["giovanni-w11-pc"]["commands"] == [
        {
            "stage": "install-ca",
            "target_host": "giovanni-w11-pc",
            "command_key": "omni.trust-pki.windows.install-ca",
            "command_args": [],
            "priority": 43,
        }
    ]


def test_rotate_host_db_requires_drift_or_force(monkeypatch):
    monkeypatch.setattr(fleet_module, "_db_env", lambda: {"PGHOST": "10.100.100.1", "PGPORT": "6432"})

    result = invoke_fleet("trust-pki", "rotate-host", "--host", "horistic-srv", "--db")

    assert result.exit_code != 0
    assert "rotação em DB exige drift detectado ou --force" in result.output or "rotação em DB exige drift detectado ou --force" in str(result.exception)


def test_db_source_renders_host_from_db(monkeypatch):
    def fake_db_env():
        return {"PGHOST": "10.100.100.1", "PGPORT": "6432"}

    def fake_psql_json(query, *, env=None, timeout=20):  # noqa: ARG001
        assert '"TbHosts"' in query
        return {
            "id": "new-srv",
            "role": "worker",
            "owner": "giovanni",
            "status": "active",
            "aliases": ["new"],
            "access": {
                "ssh": "ubuntu@10.100.100.55",
                "vpn_ip": "10.100.100.55",
                "legacy_vpn_ips": ["10.1.1.55"],
                "public_ip": None,
            },
            "platform": {"provider": "oracle-oci", "os": "ubuntu-24.04", "arch": "arm64"},
            "pki": {"service_tls": {"enabled": True}},
        }

    monkeypatch.setattr(fleet_module, "_db_env", fake_db_env)
    monkeypatch.setattr(fleet_module, "_psql_json", fake_psql_json)

    result = invoke_fleet("trust-pki", "render-host", "--host", "new-srv", "--source", "db", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source"] == "db"
    assert payload["ssh"] == "ubuntu@10.100.100.55"
    assert "10.100.100.55" in payload["sans"]["ip"]
    assert "10.1.1.55" in payload["sans"]["ip"]


def test_trust_pki_command_templates_are_allowlisted_argv_arrays():
    host_for = {
        "omni.trust-pki.init-ca": fleet_module.PKI_CA_HOST_ID,
        "omni.trust-pki.issue-host": fleet_module.PKI_CA_HOST_ID,
    }
    for command_key in (
        "omni.trust-pki.preflight",
        "omni.trust-pki.init-ca",
        "omni.trust-pki.ensure-key-csr",
        "omni.trust-pki.issue-host",
        "omni.trust-pki.install-ca",
        "omni.trust-pki.install-leaf",
        "omni.trust-pki.reconcile",
        "omni.trust-pki.verify",
        "omni.trust-pki.windows.preflight",
        "omni.trust-pki.windows.install-ca",
        "omni.trust-pki.windows.reconcile",
        "omni.trust-pki.windows.verify",
    ):
        host_id = "giovanni-w11-pc" if ".windows." in command_key else host_for.get(command_key, "horistic-srv")
        template = fleet_module._command_template(command_key, host_id=host_id)
        assert isinstance(template["argv"], list)
        argv = fleet_module._render_argv(template, {"host_id": host_id}, [])
        assert not (Path(argv[0]).name in {"sh", "bash"} and len(argv) > 1 and argv[1] == "-c")


def test_agent_runner_blocks_linux_live_mutation_from_non_target_platform():
    result = invoke_fleet(
        "trust-pki",
        "agent-runner",
        "ensure-key-csr",
        "--host",
        "horistic-srv",
        "--execute",
        "--json",
    )

    assert result.exit_code != 0
    assert "target Linux host" in result.output or "target Linux host" in str(result.exception)


def test_phase_44_02_scripts_are_present_and_backup_aware():
    scripts_dir = REPO / "modules" / "fleet-pki" / "scripts"
    bootstrap = scripts_dir / "omni-fleet-pki-bootstrap.sh"
    host = scripts_dir / "omni-fleet-pki-host.sh"
    matrix = scripts_dir / "verify-fleet-pki-matrix.sh"

    assert bootstrap.exists()
    assert host.exists()
    assert matrix.exists()
    assert "/root/.backups" in bootstrap.read_text()
    assert "/root/.backups" in host.read_text()
    assert "BEGIN PRIVATE KEY" not in bootstrap.read_text()
    assert "BEGIN PRIVATE KEY" not in host.read_text()
    assert "s_server" in matrix.read_text()
    assert "-verify_ip" in matrix.read_text()
    assert "-verify_hostname" in matrix.read_text()


def test_agent_runner_reconcile_reports_missing_cert_without_mutation():
    desired = json.dumps({"dns": ["horistic-srv"], "ip": ["10.100.100.4"]})

    result = invoke_fleet(
        "trust-pki",
        "agent-runner",
        "reconcile",
        "--host",
        "horistic-srv",
        "--san-json",
        desired,
        "--json",
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "missing-cert"
    assert payload["drift"]["needs_rotation"] is True
