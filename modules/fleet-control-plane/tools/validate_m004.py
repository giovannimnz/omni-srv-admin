#!/usr/bin/env python3
"""Validate M004 Fleet Control Plane contracts and optional live host probes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", Path(__file__).resolve().parents[3]))
CLI_DIR = REPO / "cli"
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))
os.environ.setdefault("OMNI_SRV_ADMIN", str(REPO))
PYTHON = sys.executable

from omni import fleet as fleet_module  # noqa: E402

TARGET_HOSTS = ("atius-srv-1", "atius-srv-2", "atius-srv-3")
SERVER_HOST = "atius-srv-1"
NODE_HOSTS = ("atius-srv-2", "atius-srv-3")
FLEET_DATABASE = "DbOmniFleet"
SYNCABLE_INVENTORY_HOSTS = tuple(
    host_id for host_id, _, _, _ in fleet_module._inventory_host_records(syncable_only=True)
)
FLEET_TABLES = (
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
    "TbManagedApps",
    "TbManagedForks",
    "TbCustomizationPolicies",
)


@dataclass
class ScenarioResult:
    id: str
    title: str
    status: str
    scope: str
    evidence: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)


def _load_host(host_id: str) -> tuple[Path, dict[str, Any]]:
    path, data, _ = fleet_module._load_host(host_id)
    return path, data


def _nested(data: dict[str, Any], section: str, key: str, default: str = "") -> str:
    return fleet_module._nested(data, section, key, default)


def _ok(id_: str, title: str, scope: str, evidence: list[str] | None = None) -> ScenarioResult:
    return ScenarioResult(id_, title, "PASS", scope, evidence or [])


def _fail(id_: str, title: str, scope: str, evidence: list[str] | None = None) -> ScenarioResult:
    return ScenarioResult(id_, title, "FAIL", scope, evidence or [])


def _blocked(id_: str, title: str, scope: str, evidence: list[str] | None = None) -> ScenarioResult:
    return ScenarioResult(id_, title, "BLOCKED", scope, evidence or [])


def _warn(id_: str, title: str, scope: str, evidence: list[str] | None = None) -> ScenarioResult:
    return ScenarioResult(id_, title, "WARN", scope, evidence or [])


def _parse_count_evidence(lines: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in lines:
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        if raw.isdigit():
            counts[key] = int(raw)
    return counts


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    completed = subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "OMNI_SRV_ADMIN": str(REPO), "PYTHONPATH": str(CLI_DIR)},
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _ssh(target: str, remote_cmd: str, timeout: int = 20) -> tuple[int, str, str, str]:
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
        target,
        remote_cmd,
    ]
    code, stdout, stderr = _run(cmd, timeout=timeout)
    return code, stdout, stderr, " ".join(cmd)


def _scenario_inventory() -> ScenarioResult:
    missing: list[str] = []
    evidence: list[str] = []
    for host_id in TARGET_HOSTS:
        path, host = _load_host(host_id)
        host_missing = [
            field_name
            for field_name in fleet_module.REQUIRED_HOST_FIELDS
            if not host.get(field_name)
        ]
        for section, key in fleet_module.REQUIRED_NESTED_FIELDS:
            if not _nested(host, section, key):
                host_missing.append(f"{section}.{key}")
        if host_missing:
            missing.append(f"{host_id}: {','.join(host_missing)}")
        evidence.append(
            f"{host_id}: role={host.get('role')} ssh={_nested(host, 'access', 'ssh')} "
            f"vpn={_nested(host, 'access', 'vpn_ip')} os={_nested(host, 'platform', 'os')}"
        )
        evidence.append(f"{host_id}: inventory_file={path}")
    if missing:
        return _fail("M004-OFF-01", "SRV1/SRV2/SRV3 inventory source-of-truth", "offline", missing)
    return _ok("M004-OFF-01", "SRV1/SRV2/SRV3 inventory source-of-truth", "offline", evidence)


def _scenario_roles() -> ScenarioResult:
    evidence: list[str] = []
    server_path, server = _load_host(SERVER_HOST)
    server_plan = fleet_module._install_plan("server", server, server_path)
    evidence.append(f"{SERVER_HOST}: mode={server_plan['mode']} steps={len(server_plan['steps'])}")
    if "configure PgBouncer as the only client/node database endpoint" not in server_plan["steps"]:
        return _fail("M004-OFF-02", "server/master plan owns PostgreSQL and PgBouncer", "offline", evidence)
    for host_id in NODE_HOSTS:
        path, host = _load_host(host_id)
        node_plan = fleet_module._install_plan("node", host, path)
        evidence.append(f"{host_id}: mode={node_plan['mode']} steps={len(node_plan['steps'])}")
        if "refuse direct PostgreSQL connection strings" not in node_plan["steps"]:
            return _fail("M004-OFF-02", "node/slave plans reject direct PostgreSQL", "offline", evidence)
    return _ok("M004-OFF-02", "master/server + node/slave install plan matrix", "offline", evidence)


def _scenario_cli_contracts() -> ScenarioResult:
    commands = [
        [PYTHON, "-m", "omni", "fleet", "validate-inventory", "--json"],
        [PYTHON, "-m", "omni", "fleet", "install", "server", "--host", SERVER_HOST, "--json"],
        [PYTHON, "-m", "omni", "fleet", "install", "node", "--host", "atius-srv-2", "--json"],
        [
            PYTHON,
            "-m",
            "omni",
            "fleet",
            "update-plan",
            "--host",
            SERVER_HOST,
            "--program",
            "fork-sync",
            "--desired-version",
            "v4.1",
            "--json",
        ],
    ]
    evidence: list[str] = []
    rendered: list[str] = []
    for cmd in commands:
        code, stdout, stderr = _run(cmd)
        rendered.append(" ".join(cmd))
        if code != 0:
            return _fail("M004-OFF-03", "safe CLI dry-run contracts execute", "offline", [*evidence, stderr])
        payload = json.loads(stdout)
        evidence.append(f"{' '.join(cmd[:5])}: keys={','.join(sorted(payload.keys())[:6])}")
    blocked_cmd = [
        PYTHON,
        "-m",
        "omni",
        "fleet",
        "install",
        "server",
        "--host",
        SERVER_HOST,
        "--apply",
    ]
    code, _, stderr = _run(blocked_cmd)
    rendered.append(" ".join(blocked_cmd))
    if code == 0:
        return _fail("M004-OFF-03", "--apply must remain blocked in M004", "offline", evidence)
    evidence.append(f"--apply blocked: {stderr.splitlines()[-1] if stderr else 'non-zero'}")
    result = _ok("M004-OFF-03", "safe CLI dry-run contracts execute", "offline", evidence)
    result.commands = rendered
    return result


def _scenario_schema_and_pgbouncer() -> ScenarioResult:
    schema = "\n".join(
        path.read_text()
        for path in sorted((REPO / "modules/fleet-control-plane/migrations").glob("*.sql"))
    )
    config = fleet_module._simple_yaml(
        (REPO / "modules/fleet-control-plane/configs/control-plane.example.yaml").read_text()
    )
    missing_tables = [
        table for table in FLEET_TABLES if f'CREATE TABLE IF NOT EXISTS "{table}"' not in schema
    ]
    database = config.get("database", {}) if isinstance(config.get("database"), dict) else {}
    pgbouncer = config.get("pgbouncer", {}) if isinstance(config.get("pgbouncer"), dict) else {}
    direct_access = database.get("direct_access", {}) if isinstance(database.get("direct_access"), dict) else {}
    denied = direct_access.get("denied_for", [])
    evidence = [
        f"database={database.get('database')}",
        f"tables={','.join(FLEET_TABLES)}",
        f"pgbouncer.required_for_clients={pgbouncer.get('required_for_clients')}",
        f"pgbouncer.listen_host={pgbouncer.get('listen_host')}",
        f"pgbouncer.listen_port={pgbouncer.get('listen_port')}",
        f"database.direct_access.denied_for={denied}",
        "ops_config_source=database",
        "slash_commands.provider=cli-anything",
    ]
    if missing_tables:
        return _fail("M004-OFF-04", "PostgreSQL schema contains all FCP tables", "offline", missing_tables)
    if pgbouncer.get("required_for_clients") is not True:
        return _fail("M004-OFF-04", "PgBouncer is mandatory for clients", "offline", evidence)
    if pgbouncer.get("listen_host") != "10.1.1.1" or pgbouncer.get("listen_port") != 6432:
        return _fail("M004-OFF-04", "PgBouncer listens on private fleet endpoint", "offline", evidence)
    if "fleet-nodes" not in denied or "cli-clients" not in denied:
        return _fail("M004-OFF-04", "direct PostgreSQL access denied for nodes/clients", "offline", evidence)
    if '"config_source":"database"' not in schema or "provider TEXT NOT NULL DEFAULT 'cli-anything'" not in schema:
        return _fail("M004-OFF-04", "ops configs and slash commands must be database-backed", "offline", evidence)
    if database.get("database") != FLEET_DATABASE:
        return _fail("M004-OFF-04", "database name uses Db prefix and CamelCase", "offline", evidence)
    licenses_block = schema.split('CREATE TABLE IF NOT EXISTS "TbLicenses"', 1)[1].split(");", 1)[0]
    license_columns = {
        line.strip().split(" ", 1)[0]
        for line in licenses_block.splitlines()
        if line.strip() and not line.strip().startswith(("constraint", "primary", "unique"))
    }
    forbidden_license_columns = {"license_key", "raw_secret", "password", "token", "serial"}
    if forbidden_license_columns.intersection(license_columns):
        return _fail("M004-OFF-04", "license schema must use secret_ref only", "offline", evidence)
    return _ok("M004-OFF-04", "PostgreSQL + PgBouncer + license + ops/config/slash schema contract", "offline", evidence)


def _scenario_heartbeat_programs_audit() -> ScenarioResult:
    evidence: list[str] = []
    original_heartbeat_dir = fleet_module.HEARTBEAT_DIR
    with tempfile.TemporaryDirectory(prefix="omni-m004-heartbeats-") as temp_dir:
        fleet_module.HEARTBEAT_DIR = Path(temp_dir)
        try:
            for host_id in TARGET_HOSTS:
                path, host = _load_host(host_id)
                heartbeat = fleet_module._heartbeat_payload(host, path)
                if heartbeat["status"] != "offline" or heartbeat["health"] != "missing-heartbeat":
                    return _fail("M004-OFF-05", "missing heartbeat defaults to offline", "offline", [str(heartbeat)])
                evidence.append(f"{host_id}: heartbeat={heartbeat['status']}/{heartbeat['health']}")
        finally:
            fleet_module.HEARTBEAT_DIR = original_heartbeat_dir
    srv1_path, srv1 = _load_host(SERVER_HOST)
    programs = fleet_module._program_records(srv1, srv1_path)
    program_names = {record["program"] for record in programs}
    if "fork-sync" not in program_names or "srv1-ops" not in program_names:
        return _fail("M004-OFF-05", "program registry projects inventory modules", "offline", sorted(program_names))
    code, stdout, stderr = _run([PYTHON, "-m", "omni", "fleet", "audit", "--json"])
    if code != 0:
        return _fail("M004-OFF-05", "audit command exposes event schema", "offline", [stderr])
    audit = json.loads(stdout)
    schema_keys = set(audit.get("schema", {}).keys())
    required = {"actor", "host", "action", "target", "result", "timestamp", "metadata"}
    if not required.issubset(schema_keys):
        return _fail("M004-OFF-05", "audit schema contains required fields", "offline", sorted(schema_keys))
    evidence.append(f"srv1_programs={','.join(sorted(program_names))}")
    evidence.append(f"audit_schema={','.join(sorted(schema_keys))}")
    return _ok("M004-OFF-05", "heartbeat + program registry + audit contracts", "offline", evidence)


def _scenario_future_integration() -> ScenarioResult:
    docs = "\n".join(
        [
            (REPO / "docs/fleet/control-plane.md").read_text(),
            (REPO / ".planning/phases/12-omni-fleet-control-plane/12-CONTEXT.md").read_text(),
        ]
    )
    evidence = []
    for token in ("Podman", "K3s", "inventory", "status", "program", "audit"):
        if token not in docs:
            return _fail("M004-OFF-06", "future Podman/K3s contract is documented", "offline", [f"missing {token}"])
        evidence.append(f"found={token}")
    return _ok("M004-OFF-06", "future Podman/K3s contract is documented", "offline", evidence)


def _scenario_agent_executor_monitoring() -> ScenarioResult:
    schema = "\n".join(
        path.read_text()
        for path in sorted((REPO / "modules/fleet-control-plane/migrations").glob("*.sql"))
    )
    required_tokens = [
        "TbFleetCommands",
        "TbNodeTelemetry",
        "TbNodeResourcePolicies",
        "lease_owner",
        "lease_expires_at",
        "executor_host_id",
        "idempotency_key",
        "CkTbUpdatePlansApprovedMetadata",
        "UqTbUpdatePlansIdempotencyKey",
    ]
    missing = [token for token in required_tokens if token not in schema]
    if missing:
        return _fail("M004-OFF-07", "agent executor + monitoring schema is present", "offline", missing)

    direct_env = Path(tempfile.gettempdir()) / "omni-m004-direct-postgres.env"
    direct_env.write_text(
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
        fleet_module._db_env(direct_env)
        return _fail("M004-OFF-07", "agent refuses direct PostgreSQL endpoint", "offline", ["direct endpoint accepted"])
    except Exception as exc:
        pgbouncer_evidence = str(exc)

    dry_run = fleet_module._execute_plan(
        {
            "id": "offline-noop",
            "host_id": "atius-srv-2",
            "target_command": "omni.noop",
            "command_args": [],
            "approval_state": "approved",
            "desired_version": "noop-v1",
        },
        apply_changes=False,
    )
    if dry_run["status"] != "planned":
        return _fail("M004-OFF-07", "approved allowlisted plan renders locally", "offline", [str(dry_run)])
    try:
        fleet_module._execute_plan(
            {
                "host_id": "atius-srv-2",
                "target_command": "omni.noop",
                "command_args": [],
                "approval_state": "pending",
            },
            apply_changes=True,
        )
        return _fail("M004-OFF-07", "pending plan is rejected", "offline", ["pending accepted"])
    except Exception as exc:
        pending_evidence = str(exc)

    telemetry = fleet_module._collect_telemetry("atius-srv-2")
    for section in ("cpu", "memory", "disk", "service_health"):
        if section not in telemetry:
            return _fail("M004-OFF-07", "resource telemetry contains load inputs", "offline", [f"missing {section}"])
    evidence = [
        "schema=agent-executor-monitoring",
        f"pgbouncer_guard={pgbouncer_evidence}",
        f"dry_run={dry_run['status']}",
        f"pending_guard={pending_evidence}",
        f"telemetry_health={telemetry['health']}",
    ]
    return _ok("M004-OFF-07", "agent executor, PgBouncer guard and fleet monitoring contract", "offline", evidence)


def offline_scenarios() -> list[ScenarioResult]:
    return [
        _scenario_inventory(),
        _scenario_roles(),
        _scenario_cli_contracts(),
        _scenario_schema_and_pgbouncer(),
        _scenario_heartbeat_programs_audit(),
        _scenario_future_integration(),
        _scenario_agent_executor_monitoring(),
    ]


def _live_host_identity(host_id: str) -> ScenarioResult:
    _, host = _load_host(host_id)
    target = _nested(host, "access", "ssh")
    if not target or target == "TBD":
        return _blocked(f"M004-LIVE-ID-{host_id}", f"{host_id} SSH target available", "live", ["ssh target missing"])
    cmd = (
        "set -eu; "
        "printf 'host='; hostname; "
        "printf 'arch='; uname -m; "
        "printf 'os='; . /etc/os-release && printf '%s\\n' \"$PRETTY_NAME\"; "
        "printf 'ips='; hostname -I"
    )
    code, stdout, stderr, rendered = _ssh(target, cmd)
    result = _ok if code == 0 else _fail
    scenario = result(f"M004-LIVE-ID-{host_id}", f"{host_id} read-only SSH identity", "live", stdout.splitlines() or [stderr])
    scenario.commands = [rendered]
    return scenario


def _live_repo_presence(host_id: str) -> ScenarioResult:
    _, host = _load_host(host_id)
    target = _nested(host, "access", "ssh")
    if not target or target == "TBD":
        return _blocked(f"M004-LIVE-REPO-{host_id}", f"{host_id} omni-srv-admin repo installed", "live")
    remote = (
        "set -eu; "
        "repo=\"$HOME/GitHub/omni-srv-admin\"; "
        "test -d \"$repo/.git\"; "
        "cd \"$repo\"; "
        "PYTHONPATH=cli python3 -m omni --help >/tmp/omni-m004-cli-smoke.out; "
        "echo repo=$repo; "
        "echo branch=$(git branch --show-current); "
        "echo head=$(git rev-parse --short HEAD); "
        "echo status_count=$(git status --porcelain | wc -l); "
        "echo cli_smoke=PASS"
    )
    code, stdout, stderr, rendered = _ssh(target, remote, timeout=20)
    evidence = stdout.splitlines() or [stderr]
    result = _ok if code == 0 and any("cli_smoke=PASS" in line for line in evidence) else _fail
    scenario = result(
        f"M004-LIVE-REPO-{host_id}",
        f"{host_id} omni-srv-admin repo installed and CLI works",
        "live",
        evidence,
    )
    scenario.commands = [rendered]
    return scenario


def _live_mesh_ping(source_id: str, target_id: str) -> ScenarioResult:
    _, source = _load_host(source_id)
    _, target = _load_host(target_id)
    ssh_target = _nested(source, "access", "ssh")
    vpn_ip = _nested(target, "access", "vpn_ip")
    if not ssh_target or ssh_target == "TBD" or not vpn_ip:
        return _blocked(f"M004-LIVE-MESH-{source_id}-{target_id}", f"{source_id} -> {target_id} VPN ping", "live")
    remote = f"ping -c 1 -W 2 {vpn_ip} >/dev/null && echo ok || echo fail"
    code, stdout, stderr, rendered = _ssh(ssh_target, remote, timeout=12)
    status = _ok if code == 0 and "ok" in stdout else _fail
    scenario = status(
        f"M004-LIVE-MESH-{source_id}-{target_id}",
        f"{source_id} -> {target_id} VPN ping",
        "live",
        [stdout or stderr],
    )
    scenario.commands = [rendered]
    return scenario


def _live_pgbouncer_server() -> ScenarioResult:
    _, host = _load_host(SERVER_HOST)
    target = _nested(host, "access", "ssh")
    remote = (
        "set +e; "
        "echo services=$(systemctl is-active postgresql pgbouncer 2>/dev/null | paste -sd, -); "
        "echo listeners=$(ss -ltn 2>/dev/null | awk '{print $4}' | grep -E '(:8745|:5432|:6432)$' | paste -sd, -); "
        "if command -v pg_isready >/dev/null 2>&1; then pg_isready -h 127.0.0.1 -p 6432; else echo pg_isready=missing; fi"
    )
    code, stdout, stderr, rendered = _ssh(target, remote)
    evidence = stdout.splitlines() or [stderr]
    scenario = _blocked(
        "M004-LIVE-PGB-01",
        "server/master PgBouncer listener and PostgreSQL readiness",
        "live",
        evidence,
    )
    if code != 0:
        scenario.status = "FAIL"
    elif any("10.1.1.1:6432" in line for line in evidence):
        scenario.status = "PASS"
    scenario.commands = [rendered]
    return scenario


def _live_node_pgbouncer_path(node_id: str) -> ScenarioResult:
    _, node = _load_host(node_id)
    _, server = _load_host(SERVER_HOST)
    ssh_target = _nested(node, "access", "ssh")
    server_ip = _nested(server, "access", "vpn_ip")
    remote = (
        "set +e; "
        f"if command -v nc >/dev/null 2>&1; then nc -vz -w2 {server_ip} 6432; "
        f"else timeout 3 bash -lc '</dev/tcp/{server_ip}/6432'; fi; "
        "echo rc=$?"
    )
    code, stdout, stderr, rendered = _ssh(ssh_target, remote, timeout=12)
    evidence = stdout.splitlines() or [stderr]
    scenario = _blocked(
        f"M004-LIVE-PGB-{node_id}",
        f"{node_id} node/slave reaches server PgBouncer endpoint only",
        "live",
        evidence,
    )
    if code != 0:
        scenario.status = "FAIL"
    elif any(line == "rc=0" for line in evidence):
        scenario.status = "PASS"
    scenario.commands = [rendered]
    return scenario


def _live_fleet_db_query(host_id: str) -> ScenarioResult:
    _, host = _load_host(host_id)
    target = _nested(host, "access", "ssh")
    if not target or target == "TBD":
        return _blocked(f"M004-LIVE-DB-{host_id}", f"{host_id} queries {FLEET_DATABASE} through PgBouncer", "live")
    remote = (
        "set -eu; "
        ". /etc/omni-srv-admin/fleet-db.env; "
        "export PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSSLMODE; "
        "echo endpoint=${PGHOST}:${PGPORT}/${PGDATABASE}; "
        "test \"${PGHOST}:${PGPORT}\" = \"10.1.1.1:6432\"; "
        "psql -Atc \"select current_database() || chr(58) || current_user\"; "
        "psql -Atc \"select 'TbHosts=' || count(*) from \\\"TbHosts\\\" union all select 'TbNodes=' || count(*) from \\\"TbNodes\\\" order by 1\"; "
        "psql -Atc \"select 'TbOpsScopes=' || count(*) from \\\"TbOpsScopes\\\" union all select 'TbConfigItems=' || count(*) from \\\"TbConfigItems\\\" union all select 'TbSlashCommands=' || count(*) from \\\"TbSlashCommands\\\" union all select 'TbSlashCommandBindings=' || count(*) from \\\"TbSlashCommandBindings\\\" union all select 'TbFleetCommands=' || count(*) from \\\"TbFleetCommands\\\" union all select 'TbNodeResourcePolicies=' || count(*) from \\\"TbNodeResourcePolicies\\\" union all select 'TbNodeTelemetry=' || count(*) from \\\"TbNodeTelemetry\\\" union all select 'TbManagedApps=' || count(*) from \\\"TbManagedApps\\\" union all select 'TbManagedForks=' || count(*) from \\\"TbManagedForks\\\" union all select 'TbCustomizationPolicies=' || count(*) from \\\"TbCustomizationPolicies\\\" order by 1\""
    )
    code, stdout, stderr, rendered = _ssh(target, remote, timeout=20)
    evidence = stdout.splitlines() or [stderr]
    counts = _parse_count_evidence(evidence)
    has_expected_rows = (
        counts.get("TbHosts", 0) >= len(SYNCABLE_INVENTORY_HOSTS)
        and counts.get("TbNodes", 0) >= 3
        and counts.get("TbOpsScopes", 0) >= 3
        and counts.get("TbConfigItems", 0) >= len(SYNCABLE_INVENTORY_HOSTS) * 5
        and counts.get("TbSlashCommands", 0) >= 7
        and counts.get("TbSlashCommandBindings", 0) >= 18
        and counts.get("TbFleetCommands", 0) >= 4
        and counts.get("TbNodeResourcePolicies", 0) >= 3
        and counts.get("TbManagedApps", 0) >= 1
        and counts.get("TbManagedForks", 0) >= 1
        and counts.get("TbCustomizationPolicies", 0) >= 1
    )
    expected = {
        f"endpoint=10.1.1.1:6432/{FLEET_DATABASE}",
        f"{FLEET_DATABASE}:omni_fleet",
    }
    result = _ok if code == 0 and expected.issubset(set(evidence)) and has_expected_rows else _fail
    scenario = result(
        f"M004-LIVE-DB-{host_id}",
        f"{host_id} queries central {FLEET_DATABASE} DB through PgBouncer",
        "live",
        evidence,
    )
    scenario.commands = [rendered]
    return scenario


def _live_node_direct_postgres_blocked(node_id: str) -> ScenarioResult:
    _, node = _load_host(node_id)
    _, server = _load_host(SERVER_HOST)
    ssh_target = _nested(node, "access", "ssh")
    server_ip = _nested(server, "access", "vpn_ip")
    remote = (
        "set +e; "
        f"if command -v nc >/dev/null 2>&1; then nc -vz -w2 {server_ip} 8745; "
        f"else timeout 3 bash -lc '</dev/tcp/{server_ip}/8745'; fi; "
        "echo rc=$?"
    )
    code, stdout, stderr, rendered = _ssh(ssh_target, remote, timeout=12)
    evidence = stdout.splitlines() or [stderr]
    scenario = _ok(
        f"M004-LIVE-PG-DIRECT-{node_id}",
        f"{node_id} cannot reach direct PostgreSQL port 8745 on server",
        "live",
        evidence,
    )
    if code != 0:
        scenario.status = "FAIL"
    elif any(line == "rc=0" for line in evidence):
        scenario.status = "FAIL"
    scenario.commands = [rendered]
    return scenario


def live_scenarios() -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    for host_id in TARGET_HOSTS:
        results.append(_live_host_identity(host_id))
        results.append(_live_repo_presence(host_id))
    for source_id in TARGET_HOSTS:
        for target_id in TARGET_HOSTS:
            if source_id != target_id:
                results.append(_live_mesh_ping(source_id, target_id))
    results.append(_live_pgbouncer_server())
    for host_id in TARGET_HOSTS:
        results.append(_live_fleet_db_query(host_id))
    for host_id in NODE_HOSTS:
        results.append(_live_node_pgbouncer_path(host_id))
        results.append(_live_node_direct_postgres_blocked(host_id))
    return results


def _print_text(results: list[ScenarioResult]) -> None:
    for result in results:
        print(f"{result.status:7} {result.id:28} {result.title}")
        for evidence in result.evidence[:6]:
            print(f"        {evidence}")


def _summary(results: list[ScenarioResult]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "repo": str(REPO),
        "target_hosts": TARGET_HOSTS,
        "server_host": SERVER_HOST,
        "node_hosts": NODE_HOSTS,
        "counts": counts,
        "overall": "FAIL" if counts.get("FAIL") else "PASS_WITH_BLOCKED" if counts.get("BLOCKED") else "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Run SSH, repo, network and read-only DB probes against SRV1/SRV2/SRV3.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args()

    results = offline_scenarios()
    if args.live:
        results.extend(live_scenarios())

    payload = {"summary": _summary(results), "results": [asdict(result) for result in results]}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_text(results)
        print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 1 if payload["summary"]["counts"].get("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
