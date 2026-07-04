from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from click.testing import CliRunner

REPO = Path(__file__).resolve().parents[3]
os.environ["OMNI_SRV_ADMIN"] = str(REPO)
sys.path.insert(0, str(REPO / "cli"))
sys.path.insert(0, str(REPO / "modules/fleet-control-plane/tools"))

from omni import fleet as fleet_module  # noqa: E402
from validate_m004 import offline_scenarios  # noqa: E402


def invoke_fleet(*args: str):
    runner = CliRunner()
    return runner.invoke(fleet_module.fleet, list(args))


def test_inventory_validation_covers_srv1_srv2_srv3():
    result = invoke_fleet("validate-inventory", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    hosts = {item["host"] for item in payload["results"]}
    assert {"atius-srv-1", "atius-srv-2", "atius-srv-3"}.issubset(hosts)


def test_invalid_inventory_json_returns_non_zero(monkeypatch, tmp_path):
    hosts_dir = tmp_path / "hosts"
    hosts_dir.mkdir()
    (hosts_dir / "broken.yaml").write_text(
        "\n".join(
            [
                "id: broken",
                "role: test",
                "owner: giovanni",
                "status: active",
                "access:",
                "  ssh: ubuntu@127.0.0.1",
                "platform:",
                "  provider: local",
                "  os: ubuntu",
            ]
        )
    )
    monkeypatch.setattr(fleet_module, "HOSTS_DIR", hosts_dir)
    monkeypatch.setattr(fleet_module, "LEGACY_HOSTS_DIR", tmp_path / "legacy")

    result = invoke_fleet("validate-inventory", "--json")

    assert result.exit_code != 0
    payload = json.loads(result.output.split("\nError:", 1)[0])
    assert payload["valid"] is False
    assert payload["results"][0]["missing"] == ["platform.arch"]


def test_server_and_node_install_plans_enforce_pgbouncer_contract():
    server = invoke_fleet("install", "server", "--host", "atius-srv-1", "--json")
    node = invoke_fleet("install", "node", "--host", "atius-srv-2", "--json")

    assert server.exit_code == 0, server.output
    assert node.exit_code == 0, node.output
    server_payload = json.loads(server.output)
    node_payload = json.loads(node.output)
    assert server_payload["mode"] == "server"
    assert node_payload["mode"] == "node"
    assert "configure PgBouncer as the only client/node database endpoint" in server_payload["steps"]
    assert "refuse direct PostgreSQL connection strings" in node_payload["steps"]


def test_apply_is_blocked_for_install_and_update_plan():
    server_apply = invoke_fleet("install", "server", "--host", "atius-srv-1", "--apply")
    update_apply = invoke_fleet(
        "update-plan",
        "--host",
        "atius-srv-1",
        "--program",
        "fork-sync",
        "--desired-version",
        "v4.1",
        "--apply",
    )

    assert server_apply.exit_code != 0
    assert "bloqueada" in server_apply.output or "bloqueada" in str(server_apply.exception)
    assert update_apply.exit_code != 0
    assert "aprovação explícita" in update_apply.output or "aprovação explícita" in str(update_apply.exception)


def test_missing_heartbeat_defaults_to_offline(monkeypatch, tmp_path):
    monkeypatch.setattr(fleet_module, "HEARTBEAT_DIR", tmp_path)
    path, host, _ = fleet_module._load_host("atius-srv-1")

    payload = fleet_module._heartbeat_payload(host, path)

    assert payload["host"] == "atius-srv-1"
    assert payload["status"] == "offline"
    assert payload["health"] == "missing-heartbeat"


def test_heartbeat_reads_existing_node_payload(monkeypatch, tmp_path):
    heartbeat_dir = tmp_path / "heartbeats"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "atius-srv-2.json").write_text(
        json.dumps(
            {
                "status": "healthy",
                "health": "ok",
                "last_contact": "2026-06-13T08:00:00+00:00",
            }
        )
    )
    monkeypatch.setattr(fleet_module, "HEARTBEAT_DIR", heartbeat_dir)
    path, host, _ = fleet_module._load_host("atius-srv-2")

    payload = fleet_module._heartbeat_payload(host, path)

    assert payload["status"] == "healthy"
    assert payload["health"] == "ok"
    assert payload["last_contact"] == "2026-06-13T08:00:00+00:00"


def test_program_registry_projects_inventory_modules():
    result = invoke_fleet("programs", "--host", "atius-srv-1", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    programs = {item["program"] for item in payload["programs"]}
    assert {"srv1-ops", "fork-sync"}.issubset(programs)
    assert {item["update_policy"] for item in payload["programs"]} == {"plan-first"}


def test_audit_command_filters_action_and_redacts_sensitive_values(monkeypatch, tmp_path):
    audit_log = tmp_path / "audit-events.jsonl"
    audit_log.write_text(
        json.dumps(
            {
                "actor": "pytest",
                "host": "atius-srv-1",
                "action": "install-plan",
                "target": "fleet-server",
                "result": "planned",
                "timestamp": "2026-06-13T08:00:00+00:00",
                "metadata": {"secret_ref": "vault://do-not-print", "token": "raw-token"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "actor": "pytest",
                "host": "atius-srv-1",
                "action": "heartbeat",
                "target": "fleet-node",
                "result": "accepted",
                "timestamp": "2026-06-13T08:01:00+00:00",
                "metadata": {},
            }
        )
        + "\n"
        + "{invalid token=raw-token\n"
    )
    monkeypatch.setattr(fleet_module, "AUDIT_EVENTS", audit_log)

    result = invoke_fleet("audit", "--action", "install-plan", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["event_count"] == 1
    assert {"actor", "host", "action", "target", "result", "timestamp", "metadata"}.issubset(payload["schema"])
    assert payload["events"][0]["metadata"]["secret_ref"] == "***REDACTED***"
    assert payload["events"][0]["metadata"]["token"] == "***REDACTED***"


def test_audit_invalid_json_redacts_raw_sensitive_line(monkeypatch, tmp_path):
    audit_log = tmp_path / "audit-events.jsonl"
    audit_log.write_text("{invalid password=raw-password\n")
    monkeypatch.setattr(fleet_module, "AUDIT_EVENTS", audit_log)

    result = invoke_fleet("audit", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["events"][0]["raw"] == "***REDACTED***"


def test_config_requires_pgbouncer_and_denies_direct_node_access():
    config = fleet_module._simple_yaml(
        (REPO / "modules/fleet-control-plane/configs/control-plane.example.yaml").read_text()
    )

    assert config["database"]["database"] == "DbOmniFleet"
    assert config["database"]["logical_owner"] == "omni-srv-admin"
    assert "ops-scopes" in config["database"]["canonical_for"]
    assert "slash-command-registry" in config["database"]["canonical_for"]
    assert config["pgbouncer"]["required_for_clients"] is True
    assert config["pgbouncer"]["listen_host"] == "10.1.1.1"
    assert config["pgbouncer"]["listen_port"] == 6432
    assert "10.1.1.0/24" in config["pgbouncer"]["allowed_client_networks"]
    assert "fleet-nodes" in config["database"]["direct_access"]["denied_for"]
    assert "cli-clients" in config["database"]["direct_access"]["denied_for"]
    assert "control-plane-migrations" in config["database"]["direct_access"]["allowed_for"]
    assert config["ops"]["config_source"] == "database"
    assert {scope["id"] for scope in config["ops"]["scopes"]} == {"srv1-ops", "srv2-ops", "srv3-ops"}
    assert config["slash_commands"]["provider"] == "cli-anything"
    assert "/omni-srv-admin" in config["slash_commands"]["commands"]
    assert config["agent"]["executor"] == "local-node-agent"
    assert config["agent"]["queue_table"] == "TbUpdatePlans"
    assert config["agent"]["telemetry_table"] == "TbNodeTelemetry"
    assert config["agent"]["command_allowlist_table"] == "TbFleetCommands"


def test_migration_schema_has_required_tables_and_secret_refs_only():
    schema = "\n".join(
        path.read_text()
        for path in sorted((REPO / "modules/fleet-control-plane/migrations").glob("*.sql"))
    )

    for table in (
        "TbHosts",
        "TbNodes",
        "TbPrograms",
        "TbVersions",
        "TbVersion",
        "TbUpdatePlans",
        "TbLicenses",
        "TbAuditEvents",
        "TbOpsScopes",
        "TbConfigItems",
        "TbSlashCommands",
        "TbSlashCommandBindings",
        "TbFleetCommands",
        "TbNodeTelemetry",
        "TbNodeResourcePolicies",
    ):
        assert f'CREATE TABLE IF NOT EXISTS "{table}"' in schema
    for column in (
        "target_command TEXT",
        "lease_owner TEXT",
        "lease_expires_at TIMESTAMPTZ",
        "executor_host_id TEXT",
        "idempotency_key TEXT",
        "observer_host_id TEXT",
        "allowed_host_ids JSONB",
        "component TEXT NOT NULL DEFAULT 'omni-srv-admin'",
        "github_version TEXT",
        "github_commit TEXT",
        "git_dirty BOOLEAN NOT NULL DEFAULT false",
    ):
        assert column in schema
    for constraint in (
        "CkTbUpdatePlansApprovalState",
        "CkTbUpdatePlansExecutionState",
        "CkTbUpdatePlansApprovedMetadata",
        "UqTbUpdatePlansIdempotencyKey",
        "IdxTbUpdatePlansAgentQueue",
        "UqTbConfigItemsScopeHostKeyNullSafe",
        "UqTbSlashCommandBindingsNullSafe",
        "UqTbVersionHostComponent",
        "IdxTbVersionGithubVersion",
    ):
        assert constraint in schema
    assert "secret_ref TEXT NOT NULL" in schema
    assert "provider TEXT NOT NULL DEFAULT 'cli-anything'" in schema
    assert "'/omni-srv-admin', 'cli-anything'" in schema
    assert "'omni.noop'" in schema
    assert "'ubuntu-dark-theme.apply'" in schema
    assert '"disabled-until-cli-anything-harness"' in schema
    assert '"config_source":"database"' in schema
    for forbidden in ("license_key", "raw_secret", "password text", "token text", "serial text"):
        assert forbidden not in schema


def test_db_env_rejects_direct_postgres_endpoint(tmp_path):
    env_file = tmp_path / "fleet-db.env"
    env_file.write_text(
        "\n".join(
            [
                "PGHOST=10.1.1.1",
                "PGPORT=8745",
                "PGDATABASE=DbOmniFleet",
                "PGUSER=omni_fleet",
            ]
        )
    )

    try:
        fleet_module._db_env(env_file)
    except Exception as exc:
        assert "esperado PgBouncer 10.1.1.1:6432" in str(exc)
    else:
        raise AssertionError("direct PostgreSQL endpoint should be rejected")


def test_agent_heartbeat_collects_resource_telemetry(monkeypatch, tmp_path):
    heartbeat_dir = tmp_path / "heartbeats"
    telemetry_dir = tmp_path / "telemetry"
    monkeypatch.setattr(fleet_module, "HEARTBEAT_DIR", heartbeat_dir)
    monkeypatch.setattr(fleet_module, "TELEMETRY_DIR", telemetry_dir)
    monkeypatch.setattr(fleet_module, "AUDIT_EVENTS", tmp_path / "audit-events.jsonl")

    result = invoke_fleet("agent", "heartbeat", "--host", "atius-srv-2", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["host"] == "atius-srv-2"
    assert payload["agent_version"] == fleet_module.FLEET_AGENT_VERSION
    assert payload["health"] in {"healthy", "degraded", "critical"}
    assert {"count", "load_1m", "pressure"}.issubset(payload["cpu"])
    assert {"total_bytes", "available_bytes", "used_percent", "pressure"}.issubset(payload["memory"])
    assert {"root_used_percent", "io", "pressure"}.issubset(payload["disk"])
    assert (heartbeat_dir / "atius-srv-2.json").exists()
    assert (telemetry_dir / "atius-srv-2.json").exists()


def test_agent_once_executes_only_approved_allowlisted_plan(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "id": "local-test",
                "host_id": "atius-srv-2",
                "target_command": "omni.noop",
                "command_args": [],
                "approval_state": "approved",
                "desired_version": "noop-v1",
            }
        )
    )

    dry_run = invoke_fleet("agent", "once", "--host", "atius-srv-2", "--plan-file", str(plan), "--json")
    applied = invoke_fleet(
        "agent",
        "once",
        "--host",
        "atius-srv-2",
        "--plan-file",
        str(plan),
        "--apply",
        "--json",
    )

    assert dry_run.exit_code == 0, dry_run.output
    assert json.loads(dry_run.output)["status"] == "planned"
    assert applied.exit_code == 0, applied.output
    payload = json.loads(applied.output)
    assert payload["status"] == "succeeded"
    assert "omni.noop ok" in payload["stdout"]


def test_agent_rejects_pending_unknown_and_wrong_host_commands(tmp_path):
    pending = tmp_path / "pending.json"
    pending.write_text(
        json.dumps(
            {
                "host_id": "atius-srv-2",
                "target_command": "omni.noop",
                "command_args": [],
                "approval_state": "pending",
            }
        )
    )
    unknown = tmp_path / "unknown.json"
    unknown.write_text(
        json.dumps(
            {
                "host_id": "atius-srv-2",
                "target_command": "rm -rf /",
                "command_args": [],
                "approval_state": "approved",
            }
        )
    )
    wrong_host = tmp_path / "wrong-host.json"
    wrong_host.write_text(
        json.dumps(
            {
                "host_id": "atius-srv-3",
                "target_command": "omni.resource.snapshot",
                "command_args": [],
                "approval_state": "approved",
            }
        )
    )

    for plan in (pending, unknown, wrong_host):
        result = invoke_fleet("agent", "once", "--host", "atius-srv-2", "--plan-file", str(plan), "--apply")
        assert result.exit_code != 0


def test_monitor_hosts_falls_back_to_local_cache_when_db_unavailable(monkeypatch, tmp_path):
    heartbeat_dir = tmp_path / "heartbeats"
    heartbeat_dir.mkdir()
    (heartbeat_dir / "atius-srv-3.json").write_text(
        json.dumps(
            {
                "status": "healthy",
                "health": "healthy",
                "agent_version": fleet_module.FLEET_AGENT_VERSION,
                "last_contact": "2026-06-13T12:00:00+00:00",
                "memory": {"used_percent": 51.2},
                "disk": {"root_used_percent": 74.5},
            }
        )
    )
    monkeypatch.setattr(fleet_module, "HEARTBEAT_DIR", heartbeat_dir)

    def fail_db(*args, **kwargs):
        raise RuntimeError("token=raw-secret db down")

    monkeypatch.setattr(fleet_module, "_psql_json", fail_db)

    result = invoke_fleet("monitor", "hosts", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source"] == "local-cache"
    assert payload["db_error"] == "***REDACTED***"
    srv3 = next(host for host in payload["hosts"] if host["host"] == "atius-srv-3")
    assert srv3["status"] == "healthy"


def test_offline_validation_harness_passes_all_contract_scenarios():
    results = offline_scenarios()

    assert {result.status for result in results} == {"PASS"}
    assert {result.id for result in results} == {
        "M004-OFF-01",
        "M004-OFF-02",
        "M004-OFF-03",
        "M004-OFF-04",
        "M004-OFF-05",
        "M004-OFF-06",
        "M004-OFF-07",
    }
