"""fleet — multi-host inventory and control-plane contracts."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", "/home/ubuntu/GitHub/omni-srv-admin"))
HOSTS_DIR = REPO / "inventory" / "hosts"
LEGACY_HOSTS_DIR = REPO / "hosts"
FLEET_LOG_DIR = Path(os.environ.get("OMNI_FLEET_LOG_DIR", "/home/ubuntu/.logs/fleet"))
HEARTBEAT_DIR = FLEET_LOG_DIR / "heartbeats"
TELEMETRY_DIR = FLEET_LOG_DIR / "telemetry"
AUDIT_EVENTS = FLEET_LOG_DIR / "audit-events.jsonl"
FLEET_DB_ENV = Path(os.environ.get("OMNI_FLEET_DB_ENV", "/etc/omni-srv-admin/fleet-db.env"))
FLEET_AGENT_VERSION = "0.2.0"
PGBOUNCER_ENDPOINT = ("10.1.1.1", "6432")

REQUIRED_HOST_FIELDS = (
    "id",
    "role",
    "owner",
    "status",
)

REQUIRED_NESTED_FIELDS = (
    ("access", "ssh"),
    ("platform", "provider"),
    ("platform", "os"),
    ("platform", "arch"),
)

SENSITIVE_KEYS = {"secret_ref", "token", "password", "serial", "license_key"}

LOCAL_COMMANDS: dict[str, dict[str, Any]] = {
    "omni.noop": {
        "description": "Safe no-op used for agent executor validation.",
        "argv": ["python3", "-c", "print('omni.noop ok')"],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": ["atius-srv-1", "atius-srv-2", "atius-srv-3"],
    },
    "omni.fleet.heartbeat": {
        "description": "Internal heartbeat and telemetry collection.",
        "internal": "heartbeat",
        "default_profile": "interactive",
        "requires_approval": False,
        "allowed_host_ids": ["atius-srv-1", "atius-srv-2", "atius-srv-3"],
    },
    "omni.resource.snapshot": {
        "description": "Collect local resource-governor snapshot when available.",
        "argv": ["python3", "{repo}/modules/srv1-ops/scripts/resource-governor-snapshot.py"],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": ["atius-srv-1"],
    },
}


def _simple_yaml_value(text: str, key: str, default: str = "") -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip().strip('"') or default
    return default


def _scalar(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if value in {"[]", "{}"}:
        return ""
    return value


def _simple_yaml(text: str) -> dict[str, Any]:
    """Parse the inventory subset used by inventory/hosts/*.yaml.

    This is intentionally small: one-level maps, top-level lists and scalar
    values. If PyYAML is installed, use it; otherwise keep the CLI dependency
    footprint at stdlib + click.
    """
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text) or {}
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        pass

    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            data[key] = _scalar(value) if value else None
            continue
        if current_key is None:
            continue
        if indent == 2 and line.startswith("- "):
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(_scalar(line[2:]))
            continue
        if indent == 2 and ":" in line:
            key, value = line.split(":", 1)
            if not isinstance(data.get(current_key), dict):
                data[current_key] = {}
            data[current_key][key.strip()] = _scalar(value)
    return data


@click.group(name="fleet")
def fleet() -> None:
    """Inventário multi-host e contratos do Fleet Control Plane."""


def _hosts_dir() -> Path:
    return HOSTS_DIR if HOSTS_DIR.exists() else LEGACY_HOSTS_DIR


def _host_path(host_id: str) -> Path:
    hosts_dir = _hosts_dir()
    path = hosts_dir / f"{host_id}.yaml"
    if path.exists():
        return path
    matches = sorted(hosts_dir.glob(f"*{host_id}*.yaml")) if hosts_dir.exists() else []
    if matches:
        return matches[0]
    raise click.ClickException(f"host não encontrado: {host_id}")


def _load_host(host_id: str) -> tuple[Path, dict[str, Any], str]:
    path = _host_path(host_id)
    text = path.read_text()
    data = _simple_yaml(text)
    if not data:
        raise click.ClickException(f"host inválido ou vazio: {path}")
    return path, data, text


def _nested(data: dict[str, Any], section: str, key: str, default: str = "") -> str:
    value = data.get(section)
    if isinstance(value, dict):
        nested_value = value.get(key)
        return str(nested_value) if nested_value not in {None, ""} else default
    return default


def _host_id(data: dict[str, Any], fallback: str) -> str:
    return str(data.get("id") or fallback)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            click.echo(f"{key}:")
            click.echo(json.dumps(value, indent=2, sort_keys=True))
        else:
            click.echo(f"{key}: {value}")


def _redact_text(value: str) -> str:
    lowered = value.lower()
    if any(key in lowered for key in SENSITIVE_KEYS):
        return "***REDACTED***"
    return value


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if key in SENSITIVE_KEYS else _redact(nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _append_audit_event(event: dict[str, Any]) -> None:
    AUDIT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_EVENTS.open("a", encoding="utf-8").write(json.dumps(_redact(event), sort_keys=True) + "\n")


def _load_env_file(path: Path = FLEET_DB_ENV) -> dict[str, str]:
    if not path.exists():
        raise click.ClickException(f"fleet DB env não encontrado: {path}")
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _db_env(path: Path = FLEET_DB_ENV) -> dict[str, str]:
    loaded = _load_env_file(path)
    host = loaded.get("PGHOST", "")
    port = loaded.get("PGPORT", "")
    if (host, port) != PGBOUNCER_ENDPOINT:
        raise click.ClickException(
            f"DB endpoint inválido para fleet: {host}:{port}; esperado PgBouncer "
            f"{PGBOUNCER_ENDPOINT[0]}:{PGBOUNCER_ENDPOINT[1]}"
        )
    required = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER")
    missing = [key for key in required if not loaded.get(key)]
    if missing:
        raise click.ClickException(f"fleet DB env incompleto: {','.join(missing)}")
    return {**os.environ, **loaded}


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _json_literal(value: Any) -> str:
    return _sql_literal(json.dumps(value, sort_keys=True))


def _psql(query: str, *, env: dict[str, str] | None = None, timeout: int = 20) -> str:
    psql_env = _db_env() if env is None else env
    completed = subprocess.run(
        ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", query],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=psql_env,
    )
    if completed.returncode != 0:
        raise click.ClickException(_redact_text(completed.stderr.strip() or "psql failed"))
    return completed.stdout.strip()


def _psql_json(query: str, *, env: dict[str, str] | None = None, timeout: int = 20) -> Any:
    output = _psql(query, env=env, timeout=timeout)
    if not output:
        return None
    return json.loads(output.splitlines()[-1])


def _default_host_id() -> str:
    env_host = os.environ.get("OMNI_HOST_ID")
    if env_host:
        return env_host
    hostname = socket.gethostname().lower()
    alias_map: dict[str, str] = {}
    hosts_dir = _hosts_dir()
    if hosts_dir.exists():
        for path in sorted(hosts_dir.glob("*.yaml")):
            data = _simple_yaml(path.read_text())
            host_id = _host_id(data, path.stem)
            alias_map[host_id.lower()] = host_id
            for alias in data.get("aliases", []) if isinstance(data.get("aliases"), list) else []:
                alias_map[str(alias).lower()] = host_id
    return alias_map.get(hostname, hostname)


def _proc_pressure(resource: str) -> dict[str, float | None]:
    path = Path("/proc/pressure") / resource
    result: dict[str, float | None] = {"some_avg10": None, "full_avg10": None}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        scope = parts[0]
        for part in parts[1:]:
            if part.startswith("avg10="):
                try:
                    result[f"{scope}_avg10"] = float(part.split("=", 1)[1])
                except ValueError:
                    result[f"{scope}_avg10"] = None
    return result


def _meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    path = Path("/proc/meminfo")
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        key, raw = line.split(":", 1)
        amount = raw.strip().split()[0]
        try:
            values[key] = int(amount) * 1024
        except ValueError:
            continue
    return values


def _diskstats() -> dict[str, int]:
    path = Path("/proc/diskstats")
    totals = {"read_bytes": 0, "write_bytes": 0}
    if not path.exists():
        return totals
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        device = parts[2]
        if device.startswith(("loop", "ram", "sr")):
            continue
        try:
            sectors_read = int(parts[5])
            sectors_written = int(parts[9])
        except ValueError:
            continue
        totals["read_bytes"] += sectors_read * 512
        totals["write_bytes"] += sectors_written * 512
    return totals


def _service_health() -> dict[str, str]:
    candidates = [
        "omni-fleet-agent.service",
        "resource-governor-watchdog.service",
        "resource-governor-patcher.service",
        "pgbouncer.service",
        "postgresql.service",
    ]
    health: dict[str, str] = {}
    for unit in candidates:
        completed = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=3,
        )
        state = completed.stdout.strip() or "unknown"
        if completed.returncode == 0 or state not in {"unknown", "inactive"}:
            health[unit] = state
    return health


def _resource_health(load_1m: float | None, cpu_count: int, memory_used_pct: float | None, disk_used_pct: float | None) -> str:
    if disk_used_pct is not None and disk_used_pct >= 95:
        return "critical"
    if memory_used_pct is not None and memory_used_pct >= 92:
        return "critical"
    if load_1m is not None and load_1m >= max(cpu_count * 3, 6):
        return "critical"
    if disk_used_pct is not None and disk_used_pct >= 88:
        return "degraded"
    if memory_used_pct is not None and memory_used_pct >= 85:
        return "degraded"
    if load_1m is not None and load_1m >= max(cpu_count * 2, 4):
        return "degraded"
    return "healthy"


def _collect_telemetry(host_id: str) -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    load_1m = load_5m = load_15m = None
    try:
        load_1m, load_5m, load_15m = os.getloadavg()
    except OSError:
        pass
    mem = _meminfo()
    mem_total = mem.get("MemTotal")
    mem_available = mem.get("MemAvailable")
    swap_total = mem.get("SwapTotal")
    swap_free = mem.get("SwapFree")
    memory_used_pct = None
    swap_used_pct = None
    if mem_total and mem_available is not None:
        memory_used_pct = round(((mem_total - mem_available) / mem_total) * 100, 2)
    if swap_total:
        swap_used_pct = round(((swap_total - (swap_free or 0)) / swap_total) * 100, 2)
    disk = shutil.disk_usage("/")
    disk_used_pct = round((disk.used / disk.total) * 100, 2)
    uptime_seconds = None
    uptime_path = Path("/proc/uptime")
    if uptime_path.exists():
        try:
            uptime_seconds = int(float(uptime_path.read_text().split()[0]))
        except (ValueError, IndexError):
            uptime_seconds = None
    health = _resource_health(load_1m, cpu_count, memory_used_pct, disk_used_pct)
    return {
        "host": host_id,
        "agent_version": FLEET_AGENT_VERSION,
        "status": health,
        "health": health,
        "last_contact": _now(),
        "hostname": socket.gethostname(),
        "cpu": {
            "count": cpu_count,
            "load_1m": round(load_1m, 2) if load_1m is not None else None,
            "load_5m": round(load_5m, 2) if load_5m is not None else None,
            "load_15m": round(load_15m, 2) if load_15m is not None else None,
            "pressure": _proc_pressure("cpu"),
        },
        "memory": {
            "total_bytes": mem_total,
            "available_bytes": mem_available,
            "used_percent": memory_used_pct,
            "swap_used_percent": swap_used_pct,
            "pressure": _proc_pressure("memory"),
        },
        "disk": {
            "root_total_bytes": disk.total,
            "root_used_bytes": disk.used,
            "root_free_bytes": disk.free,
            "root_used_percent": disk_used_pct,
            "io": _diskstats(),
            "pressure": _proc_pressure("io"),
        },
        "service_health": _service_health(),
        "uptime_seconds": uptime_seconds,
        "generated_at": _now(),
    }


def _save_heartbeat_cache(payload: dict[str, Any]) -> None:
    host_id = str(payload["host"])
    _write_json(HEARTBEAT_DIR / f"{host_id}.json", payload)
    _write_json(TELEMETRY_DIR / f"{host_id}.json", payload)


def _write_heartbeat_db(payload: dict[str, Any], *, env: dict[str, str] | None = None) -> None:
    host_id = str(payload["host"])
    cpu = payload.get("cpu", {}) if isinstance(payload.get("cpu"), dict) else {}
    memory = payload.get("memory", {}) if isinstance(payload.get("memory"), dict) else {}
    disk = payload.get("disk", {}) if isinstance(payload.get("disk"), dict) else {}
    disk_io = disk.get("io", {}) if isinstance(disk.get("io"), dict) else {}
    query = f"""
INSERT INTO "TbNodes" (host_id, install_mode, agent_version, health_status, last_heartbeat_at, last_heartbeat)
VALUES ({_sql_literal(host_id)}, CASE WHEN {_sql_literal(host_id)} = 'atius-srv-1' THEN 'server' ELSE 'node' END,
        {_sql_literal(FLEET_AGENT_VERSION)}, {_sql_literal(payload.get("health"))}, now(), {_json_literal(payload)}::jsonb)
ON CONFLICT (host_id) DO UPDATE SET
    agent_version = EXCLUDED.agent_version,
    health_status = EXCLUDED.health_status,
    last_heartbeat_at = EXCLUDED.last_heartbeat_at,
    last_heartbeat = EXCLUDED.last_heartbeat,
    updated_at = now();

INSERT INTO "TbNodeTelemetry" (
    host_id, observer_host_id, agent_id, health_status, cpu_count, load_1m, load_5m, load_15m,
    memory_total_bytes, memory_available_bytes, memory_used_percent, swap_used_percent,
    disk_root_total_bytes, disk_root_used_bytes, disk_root_used_percent,
    disk_read_bytes, disk_write_bytes, service_health, raw
) VALUES (
    {_sql_literal(host_id)}, {_sql_literal(host_id)}, {_sql_literal(socket.gethostname())}, {_sql_literal(payload.get("health"))},
    {int(cpu.get("count") or 0)}, {cpu.get("load_1m") if cpu.get("load_1m") is not None else "NULL"},
    {cpu.get("load_5m") if cpu.get("load_5m") is not None else "NULL"},
    {cpu.get("load_15m") if cpu.get("load_15m") is not None else "NULL"},
    {memory.get("total_bytes") if memory.get("total_bytes") is not None else "NULL"},
    {memory.get("available_bytes") if memory.get("available_bytes") is not None else "NULL"},
    {memory.get("used_percent") if memory.get("used_percent") is not None else "NULL"},
    {memory.get("swap_used_percent") if memory.get("swap_used_percent") is not None else "NULL"},
    {disk.get("root_total_bytes") if disk.get("root_total_bytes") is not None else "NULL"},
    {disk.get("root_used_bytes") if disk.get("root_used_bytes") is not None else "NULL"},
    {disk.get("root_used_percent") if disk.get("root_used_percent") is not None else "NULL"},
    {disk_io.get("read_bytes") if disk_io.get("read_bytes") is not None else "NULL"},
    {disk_io.get("write_bytes") if disk_io.get("write_bytes") is not None else "NULL"},
    {_json_literal(payload.get("service_health", {}))}::jsonb,
    {_json_literal(payload)}::jsonb
);
"""
    _psql(query, env=env)


def _command_template(command_key: str, *, host_id: str | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    if env is not None:
        query = f"""
SELECT jsonb_build_object(
    'command_key', command_key,
    'description', description,
    'invocation', local_invocation,
    'default_profile', default_profile,
    'requires_approval', requires_approval,
    'timeout_seconds', timeout_seconds,
    'allowed_host_ids', allowed_host_ids,
    'metadata', metadata,
    'enabled', enabled
)
FROM "TbFleetCommands"
WHERE command_key = {_sql_literal(command_key)} AND enabled = true;
"""
        record = _psql_json(query, env=env)
        if record:
            if str(record.get("invocation") or "").startswith("internal:"):
                record["internal"] = str(record["invocation"]).split(":", 1)[1]
            allowed = record.get("allowed_host_ids") or []
            if host_id and allowed and host_id not in allowed:
                raise click.ClickException(f"comando {command_key} não permitido para {host_id}")
            return record
    if command_key in LOCAL_COMMANDS:
        record = {"command_key": command_key, **LOCAL_COMMANDS[command_key]}
        allowed = record.get("allowed_host_ids") or []
        if host_id and allowed and host_id not in allowed:
            raise click.ClickException(f"comando {command_key} não permitido para {host_id}")
        return record
    raise click.ClickException(f"comando não permitido pelo fleet agent: {command_key}")


def _render_argv(template: dict[str, Any], plan: dict[str, Any], command_args: list[str]) -> list[str]:
    if "argv" in template:
        raw_argv = template["argv"]
        argv = [str(item) for item in raw_argv]
    else:
        invocation = str(template.get("invocation") or "")
        if not invocation:
            raise click.ClickException(f"comando sem invocation: {template.get('command_key')}")
        argv = shlex.split(invocation)
    if len(argv) >= 2 and Path(argv[0]).name in {"sh", "bash"} and argv[1] == "-c":
        raise click.ClickException("fleet agent recusa shell string; registre argv/script allowlisted")
    values = {
        "repo": str(REPO),
        "host_id": str(plan.get("host_id") or plan.get("host") or ""),
        "desired_version": str(plan.get("desired_version") or ""),
    }
    rendered = [item.format(**values) for item in argv]
    rendered.extend(command_args)
    return rendered


def _execute_plan(plan: dict[str, Any], *, apply_changes: bool, env: dict[str, str] | None = None) -> dict[str, Any]:
    host_id = str(plan.get("host_id") or plan.get("host") or _default_host_id())
    command_key = str(plan.get("target_command") or plan.get("command_key") or "")
    if not command_key:
        raise click.ClickException("update plan sem target_command/command_key")
    command_args = plan.get("command_args") or []
    if isinstance(command_args, str):
        command_args = json.loads(command_args)
    if not isinstance(command_args, list):
        raise click.ClickException("command_args deve ser lista JSON")
    template = _command_template(command_key, host_id=host_id, env=env)
    approval_state = str(plan.get("approval_state") or "pending")
    if template.get("requires_approval", True) and approval_state != "approved":
        raise click.ClickException(f"update plan não aprovado: {approval_state}")
    if template.get("internal") == "heartbeat":
        payload = _collect_telemetry(host_id)
        _save_heartbeat_cache(payload)
        if apply_changes and env is not None:
            _write_heartbeat_db(payload, env=env)
        return {
            "plan_id": plan.get("id"),
            "host": host_id,
            "command_key": command_key,
            "status": "succeeded",
            "dry_run": not apply_changes,
            "stdout": "heartbeat collected",
            "stderr": "",
            "returncode": 0,
            "telemetry_health": payload["health"],
            "finished_at": _now(),
        }
    argv = _render_argv(template, plan, [str(item) for item in command_args])
    if not apply_changes:
        return {
            "plan_id": plan.get("id"),
            "host": host_id,
            "command_key": command_key,
            "status": "planned",
            "dry_run": True,
            "argv": argv,
            "finished_at": _now(),
        }
    timeout = int(template.get("timeout_seconds") or 900)
    started = _now()
    completed = subprocess.run(
        argv,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "OMNI_SRV_ADMIN": str(REPO), "PYTHONPATH": str(REPO / "cli")},
    )
    status = "succeeded" if completed.returncode == 0 else "failed"
    return {
        "plan_id": plan.get("id"),
        "host": host_id,
        "command_key": command_key,
        "status": status,
        "dry_run": False,
        "returncode": completed.returncode,
        "stdout": _redact_text(completed.stdout[-4000:]),
        "stderr": _redact_text(completed.stderr[-4000:]),
        "started_at": started,
        "finished_at": _now(),
    }


def _claim_next_plan(host_id: str, *, env: dict[str, str]) -> dict[str, Any] | None:
    owner = f"{socket.gethostname()}:{os.getpid()}"
    query = f"""
WITH candidate AS (
    SELECT id
    FROM "TbUpdatePlans"
    WHERE host_id = {_sql_literal(host_id)}
      AND approval_state = 'approved'
      AND approved_by IS NOT NULL
      AND approved_at IS NOT NULL
      AND execution_state IN ('queued', 'retry')
      AND (lease_expires_at IS NULL OR lease_expires_at < now())
    ORDER BY priority ASC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
),
claimed AS (
    UPDATE "TbUpdatePlans" p
    SET execution_state = 'claimed',
        lease_owner = {_sql_literal(owner)},
        executor_host_id = {_sql_literal(host_id)},
        lease_expires_at = now() + interval '5 minutes',
        attempt_count = attempt_count + 1,
        started_at = COALESCE(started_at, now()),
        updated_at = now()
    FROM candidate
    WHERE p.id = candidate.id
    RETURNING p.*
)
SELECT COALESCE(
    (SELECT jsonb_build_object(
        'id', id,
        'host_id', host_id,
        'desired_version', desired_version,
        'approval_state', approval_state,
        'execution_state', execution_state,
        'target_command', target_command,
        'command_args', command_args,
        'execution_profile', execution_profile,
        'lease_owner', lease_owner
    ) FROM claimed),
    'null'::jsonb
);
"""
    return _psql_json(query, env=env)


def _finish_plan_db(plan_id: str, result: dict[str, Any], *, env: dict[str, str]) -> None:
    execution_state = "succeeded" if result.get("status") == "succeeded" else "failed"
    query = f"""
UPDATE "TbUpdatePlans"
SET execution_state = {_sql_literal(execution_state)},
    execution_output = {_json_literal(_redact(result))}::jsonb,
    finished_at = now(),
    lease_owner = NULL,
    lease_expires_at = NULL,
    updated_at = now()
WHERE id = {_sql_literal(plan_id)}::uuid;

INSERT INTO "TbAuditEvents" (actor, host_id, action, target, result, metadata)
VALUES (
    {_sql_literal("omni-fleet-agent")},
    {_sql_literal(result.get("host"))},
    'update-plan.execute',
    {_sql_literal(result.get("command_key"))},
    {_sql_literal(execution_state)},
    {_json_literal(_redact(result))}::jsonb
);
"""
    _psql(query, env=env)


def _monitor_payload(*, use_db: bool) -> dict[str, Any]:
    hosts_dir = _hosts_dir()
    hosts: list[dict[str, Any]] = []
    db_error = None
    if use_db:
        try:
            query = """
WITH latest_telemetry AS (
    SELECT DISTINCT ON (host_id)
        host_id, observed_at, health_status, load_1m, load_5m,
        memory_used_percent, disk_root_used_percent, disk_read_bytes, disk_write_bytes,
        service_health
    FROM "TbNodeTelemetry"
    ORDER BY host_id, observed_at DESC
)
SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'host', h.id,
    'role', h.role,
    'status', COALESCE(n.health_status, h.status),
    'last_contact', n.last_heartbeat_at,
    'agent_version', n.agent_version,
    'load_1m', lt.load_1m,
    'load_5m', lt.load_5m,
    'memory_used_percent', lt.memory_used_percent,
    'disk_root_used_percent', lt.disk_root_used_percent,
    'disk_read_bytes', lt.disk_read_bytes,
    'disk_write_bytes', lt.disk_write_bytes,
    'service_health', COALESCE(lt.service_health, '{}'::jsonb)
) ORDER BY h.id), '[]'::jsonb)
FROM "TbHosts" h
LEFT JOIN "TbNodes" n ON n.host_id = h.id
LEFT JOIN latest_telemetry lt ON lt.host_id = h.id;
"""
            hosts = _psql_json(query) or []
        except Exception as exc:  # local fallback keeps monitoring useful during DB outage
            db_error = _redact_text(str(exc))
    if not hosts and hosts_dir.exists():
        for path in sorted(hosts_dir.glob("*.yaml")):
            data = _simple_yaml(path.read_text())
            heartbeat = _heartbeat_payload(data, path)
            hosts.append(
                {
                    "host": heartbeat["host"],
                    "role": data.get("role", "?"),
                    "status": heartbeat["status"],
                    "last_contact": heartbeat["last_contact"],
                    "agent_version": heartbeat["agent_version"],
                    "load_1m": None,
                    "load_5m": None,
                    "memory_used_percent": None,
                    "disk_root_used_percent": None,
                    "service_health": heartbeat["service_health"],
                }
            )
    return {
        "source": "database" if use_db and not db_error else "local-cache",
        "db_error": db_error,
        "host_count": len(hosts),
        "hosts": hosts,
        "generated_at": _now(),
    }


def _install_plan(mode: str, host: dict[str, Any], path: Path) -> dict[str, Any]:
    host_id = _host_id(host, path.stem)
    shared_steps = [
        "validate inventory projection",
        "write audit event with actor, host, action and target",
        "run only after explicit operator approval",
    ]
    if mode == "server":
        steps = [
            "install control-plane package and service unit",
            "provision PostgreSQL owned by the control-plane server",
            "apply versioned migrations from modules/fleet-control-plane/migrations",
            "configure PgBouncer as the only client/node database endpoint",
            "enable logical dump/restore runbook before first production data",
            "import inventory/hosts as the source-of-truth projection",
        ]
    else:
        steps = [
            "install lightweight omni fleet node agent",
            "configure node to reach the control-plane database through PgBouncer",
            "register heartbeat timer and local status collector",
            "register program inventory collector",
            "refuse direct PostgreSQL connection strings",
            "execute only approved update plans",
        ]
    return {
        "mode": mode,
        "host": host_id,
        "inventory_file": str(path),
        "dry_run": True,
        "apply_supported": False,
        "status": "planned",
        "steps": steps + shared_steps,
        "rollback": [
            "stop and disable the generated service unit",
            "remove PgBouncer client credentials for the host",
            "mark node inactive in control-plane state",
            "keep audit events and logical dumps for review",
        ],
        "blocked_until": [
            "storage for secrets/license material is approved outside git/log/vault",
            "host preflight is confirmed immediately before live execution",
            "operator approves CLI-only vs API+CLI implementation shape",
        ],
    }


def _heartbeat_payload(host: dict[str, Any], path: Path) -> dict[str, Any]:
    host_id = _host_id(host, path.stem)
    heartbeat_file = HEARTBEAT_DIR / f"{host_id}.json"
    status = "offline"
    last_contact = None
    health = "missing-heartbeat"
    agent_version = "not-installed"
    disk = None
    memory = None
    service_health = {}
    uptime = None
    if heartbeat_file.exists():
        try:
            heartbeat = json.loads(heartbeat_file.read_text())
            status = str(heartbeat.get("status") or "unknown")
            last_contact = heartbeat.get("last_contact")
            health = str(heartbeat.get("health") or "unknown")
            agent_version = str(heartbeat.get("agent_version") or "unknown")
            disk = heartbeat.get("disk")
            memory = heartbeat.get("memory")
            service_health = heartbeat.get("service_health") if isinstance(heartbeat.get("service_health"), dict) else {}
            uptime = heartbeat.get("uptime_seconds") or heartbeat.get("uptime")
        except Exception:
            status = "degraded"
            health = "invalid-heartbeat-file"
    return {
        "host": host_id,
        "agent_version": agent_version,
        "os": _nested(host, "platform", "os", "unknown"),
        "arch": _nested(host, "platform", "arch", "unknown"),
        "uptime": uptime,
        "disk": disk,
        "memory": memory,
        "service_health": service_health,
        "status": status,
        "health": health,
        "last_contact": last_contact,
        "generated_at": _now(),
    }


def _program_records(host: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    host_id = _host_id(host, path.stem)
    records = []
    modules = host.get("modules") if isinstance(host.get("modules"), list) else []
    for module in modules:
        records.append(
            {
                "host": host_id,
                "program": str(module),
                "kind": "omni-module",
                "install_type": "omni-module",
                "current_version": "unknown",
                "desired_version": "inventory-managed",
                "source": "inventory/hosts",
                "managed_by": "omni-srv-admin",
                "update_policy": "plan-first",
            }
        )
    apps = host.get("apps")
    if apps is None:
        apps = []
    if not isinstance(apps, list):
        apps = []
    for app in apps:
        if not isinstance(app, dict):
            continue
        app_id = str(app.get("id") or app.get("name") or "")
        if not app_id:
            continue
        record: dict[str, object] = {
            "host": host_id,
            "program": app_id,
            "kind": "app",
            "runtime": str(app.get("runtime") or "unknown"),
            "install_type": str(app.get("install_type") or "unknown"),
            "current_version": str(app.get("current_version") or "unknown"),
            "desired_version": str(app.get("desired_version") or "inventory-managed"),
            "source": str(app.get("source") or "inventory/hosts"),
            "managed_by": str(app.get("managed_by") or "omni-srv-admin"),
            "update_policy": str(app.get("update_policy") or "plan-first"),
            "last_audited": str(app.get("last_audited") or ""),
        }
        if app.get("public_url"):
            record["public_url"] = str(app["public_url"])
        if app.get("healthcheck_url"):
            record["healthcheck_url"] = str(app["healthcheck_url"])
        if app.get("unit"):
            record["unit"] = str(app["unit"])
        if app.get("compose"):
            record["compose"] = str(app["compose"])
        if app.get("image"):
            record["image"] = str(app["image"])
        if app.get("notes"):
            notes = app["notes"]
            note_list: list[str] = list(notes) if isinstance(notes, list) else [str(notes)]
            record["notes"] = note_list
        records.append(record)
    return records


@fleet.command("list")
def list_hosts() -> None:
    """Lista hosts cadastrados em inventory/hosts/*.yaml."""
    hosts_dir = _hosts_dir()
    if not hosts_dir.exists():
        click.echo(f"hosts dir missing: {HOSTS_DIR}")
        return
    rows = []
    for path in sorted(hosts_dir.glob("*.yaml")):
        text = path.read_text()
        rows.append((
            _simple_yaml_value(text, "id", path.stem),
            _simple_yaml_value(text, "role", "?"),
            _simple_yaml_value(text, "status", "?"),
            path.name,
        ))
    click.echo(f"{len(rows)} host(s) em {hosts_dir}")
    for host_id, role, status, file_name in rows:
        click.echo(f"{host_id:24} {role:22} {status:10} {file_name}")


@fleet.command("show")
@click.argument("host_id")
def show_host(host_id: str) -> None:
    """Mostra o YAML de um host."""
    path = _host_path(host_id)
    click.echo(path.read_text())


@fleet.command("validate-inventory")
@click.option("--json", "json_output", is_flag=True, help="Emite resultado em JSON.")
def validate_inventory(json_output: bool) -> None:
    """Valida campos mínimos do inventário host-by-host."""
    hosts_dir = _hosts_dir()
    if not hosts_dir.exists():
        raise click.ClickException(f"hosts dir missing: {HOSTS_DIR}")

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    for path in sorted(hosts_dir.glob("*.yaml")):
        text = path.read_text()
        data = _simple_yaml(text)
        host_id = _host_id(data, path.stem)
        if host_id in seen:
            duplicate_ids.add(host_id)
        seen.add(host_id)
        missing = [field for field in REQUIRED_HOST_FIELDS if not data.get(field)]
        for section, key in REQUIRED_NESTED_FIELDS:
            if not _nested(data, section, key):
                missing.append(f"{section}.{key}")
        results.append(
            {
                "host": host_id,
                "file": str(path),
                "status": "ok" if not missing else "invalid",
                "missing": missing,
            }
        )

    for result in results:
        if result["host"] in duplicate_ids:
            result["status"] = "invalid"
            result["missing"] = [*result["missing"], "duplicate id"]

    payload = {
        "hosts_dir": str(hosts_dir),
        "host_count": len(results),
        "valid": all(result["status"] == "ok" for result in results),
        "results": results,
    }
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["valid"]:
            raise click.ClickException("inventário inválido")
        return
    click.echo(f"{payload['host_count']} host(s) em {hosts_dir}")
    for result in results:
        suffix = "" if result["status"] == "ok" else f" missing={','.join(result['missing'])}"
        click.echo(f"{result['host']:24} {result['status']}{suffix}")
    if not payload["valid"]:
        raise click.ClickException("inventário inválido")


@fleet.group("install")
def install() -> None:
    """Planos seguros de instalação server/node do control plane."""


@install.command("server")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--dry-run", is_flag=True, help="Compatibilidade explícita; este é o padrão.")
@click.option("--apply", "apply_changes", is_flag=True, help="Reservado para execução futura aprovada.")
@click.option("--json", "json_output", is_flag=True, help="Emite plano em JSON.")
def install_server(host_id: str, dry_run: bool, apply_changes: bool, json_output: bool) -> None:
    """Gera plano idempotente para instalar o modo server."""
    if apply_changes:
        raise click.ClickException("execução real bloqueada nesta fase; use sem --apply para plano dry-run")
    path, host, _ = _load_host(host_id)
    payload = _install_plan("server", host, path)
    payload["requested_dry_run"] = True if dry_run else True
    _emit(payload, json_output)


@install.command("node")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--dry-run", is_flag=True, help="Compatibilidade explícita; este é o padrão.")
@click.option("--apply", "apply_changes", is_flag=True, help="Reservado para execução futura aprovada.")
@click.option("--json", "json_output", is_flag=True, help="Emite plano em JSON.")
def install_node(host_id: str, dry_run: bool, apply_changes: bool, json_output: bool) -> None:
    """Gera plano idempotente para instalar o modo node."""
    if apply_changes:
        raise click.ClickException("execução real bloqueada nesta fase; use sem --apply para plano dry-run")
    path, host, _ = _load_host(host_id)
    payload = _install_plan("node", host, path)
    payload["requested_dry_run"] = True if dry_run else True
    _emit(payload, json_output)


@fleet.command("heartbeat")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def heartbeat(host_id: str, json_output: bool) -> None:
    """Mostra o contrato de heartbeat/status para um host."""
    path, host, _ = _load_host(host_id)
    _emit(_heartbeat_payload(host, path), json_output)


@fleet.command("programs")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--json", "json_output", is_flag=True, help="Emite registry em JSON.")
def programs(host_id: str, json_output: bool) -> None:
    """Mostra o registry inicial de programas controlados por host."""
    path, host, _ = _load_host(host_id)
    payload = {
        "host": _host_id(host, path.stem),
        "program_count": len(_program_records(host, path)),
        "programs": _program_records(host, path),
        "notes": [
            "current_version remains unknown until the node agent collector exists",
            "desired_version is generated through update plans before execution",
        ],
    }
    _emit(payload, json_output)


@fleet.command("update-plan")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--program", required=True, help="Programa ou módulo controlado.")
@click.option("--desired-version", required=True, help="Versão desejada.")
@click.option("--dry-run", is_flag=True, help="Compatibilidade explícita; este é o padrão.")
@click.option("--apply", "apply_changes", is_flag=True, help="Reservado para execução futura aprovada.")
@click.option("--json", "json_output", is_flag=True, help="Emite plano em JSON.")
def update_plan(
    host_id: str,
    program: str,
    desired_version: str,
    dry_run: bool,
    apply_changes: bool,
    json_output: bool,
) -> None:
    """Gera update plan auditável sem aplicar mudanças."""
    if apply_changes:
        raise click.ClickException("execução real bloqueada; update plans exigem aprovação explícita")
    path, host, _ = _load_host(host_id)
    host_name = _host_id(host, path.stem)
    payload = {
        "host": host_name,
        "program": program,
        "current_version": "unknown",
        "desired_version": desired_version,
        "dry_run": True if dry_run else True,
        "approval_state": "pending",
        "audit_event_id": None,
        "actions": [
            "collect current version from node agent",
            "compare current vs desired version",
            "render package/service commands",
            "record dry-run output",
            "wait for explicit approval before execution",
        ],
        "status": "planned",
        "generated_at": _now(),
    }
    _emit(payload, json_output)


@fleet.command("queue-update")
@click.option("--host", "host_id", required=True, help="Host alvo do inventário.")
@click.option("--program", required=True, help="Programa ou módulo controlado.")
@click.option("--desired-version", required=True, help="Versão desejada.")
@click.option("--command-key", required=True, help="Chave allowlist em TbFleetCommands.")
@click.option("--args-json", default="[]", help="Lista JSON de argumentos extras para o comando allowlist.")
@click.option("--requested-by", default=None, help="Ator que solicitou o plano.")
@click.option("--approve", is_flag=True, help="Cria já aprovado; use apenas para comandos revisados.")
@click.option("--priority", default=100, show_default=True, help="Menor valor executa antes.")
@click.option("--db", "write_db", is_flag=True, help="Insere em DbOmniFleet via PgBouncer.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def queue_update(
    host_id: str,
    program: str,
    desired_version: str,
    command_key: str,
    args_json: str,
    requested_by: str | None,
    approve: bool,
    priority: int,
    write_db: bool,
    json_output: bool,
) -> None:
    """Cria update plan executável por agent local do host alvo."""
    path, host, _ = _load_host(host_id)
    host_name = _host_id(host, path.stem)
    try:
        command_args = json.loads(args_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--args-json inválido: {exc}") from exc
    if not isinstance(command_args, list):
        raise click.ClickException("--args-json deve ser uma lista JSON")
    approval_state = "approved" if approve else "pending"
    execution_state = "queued" if approve else "not-started"
    payload = {
        "host": host_name,
        "program": program,
        "desired_version": desired_version,
        "target_command": command_key,
        "command_args": command_args,
        "approval_state": approval_state,
        "execution_state": execution_state,
        "priority": priority,
        "requested_by": requested_by or os.environ.get("USER", "operator"),
        "requested_from_host": _default_host_id(),
        "db_write": write_db,
        "generated_at": _now(),
    }
    if not write_db:
        payload["notes"] = [
            "dry-run only; pass --db to insert into DbOmniFleet through PgBouncer",
            "target host executes locally through omni fleet agent once/loop",
        ]
        _emit(payload, json_output)
        return
    env = _db_env()
    _command_template(command_key, host_id=host_name, env=env)
    approved_by_sql = _sql_literal(payload["requested_by"]) if approve else "NULL"
    approved_at_sql = "now()" if approve else "NULL"
    query = f"""
WITH program AS (
    INSERT INTO "TbPrograms" (host_id, name, install_type, current_version, source, managed_by, update_policy, observed_at)
    VALUES ({_sql_literal(host_name)}, {_sql_literal(program)}, 'omni-module', NULL, 'queue-update', 'omni-srv-admin', 'plan-first', now())
    ON CONFLICT (host_id, name, install_type) DO UPDATE SET
        source = EXCLUDED.source,
        managed_by = EXCLUDED.managed_by,
        update_policy = EXCLUDED.update_policy,
        observed_at = now()
    RETURNING id
),
plan AS (
    INSERT INTO "TbUpdatePlans" (
        host_id, program_id, desired_version, dry_run_output, approval_state,
        approved_by, approved_at,
        execution_state, target_command, command_args, execution_profile,
        requested_by, requested_from_host, priority, idempotency_key
    )
    SELECT
        {_sql_literal(host_name)}, program.id, {_sql_literal(desired_version)},
        {_json_literal(payload)}::jsonb, {_sql_literal(approval_state)},
        {approved_by_sql}, {approved_at_sql},
        {_sql_literal(execution_state)}, {_sql_literal(command_key)}, {_json_literal(command_args)}::jsonb,
        'interactive', {_sql_literal(payload["requested_by"])}, {_sql_literal(payload["requested_from_host"])}, {int(priority)},
        encode(digest({_sql_literal(host_name + ':' + program + ':' + desired_version + ':' + command_key + ':' + json.dumps(command_args, sort_keys=True))}, 'sha256'), 'hex')
    FROM program
    ON CONFLICT (idempotency_key) DO UPDATE SET
        dry_run_output = EXCLUDED.dry_run_output,
        approval_state = EXCLUDED.approval_state,
        approved_by = EXCLUDED.approved_by,
        approved_at = EXCLUDED.approved_at,
        execution_state = CASE
            WHEN "TbUpdatePlans".execution_state IN ('succeeded', 'claimed', 'running') THEN "TbUpdatePlans".execution_state
            ELSE EXCLUDED.execution_state
        END,
        updated_at = now()
    RETURNING id, host_id, desired_version, approval_state, execution_state, target_command, command_args, priority, created_at
)
SELECT jsonb_build_object(
    'id', id,
    'host', host_id,
    'desired_version', desired_version,
    'approval_state', approval_state,
    'execution_state', execution_state,
    'target_command', target_command,
    'command_args', command_args,
    'priority', priority,
    'created_at', created_at
) FROM plan;
"""
    record = _psql_json(query, env=env)
    _emit({"db_write": True, "plan": record, "pgbouncer": f"{PGBOUNCER_ENDPOINT[0]}:{PGBOUNCER_ENDPOINT[1]}"}, json_output)


@fleet.group("agent")
def agent() -> None:
    """Node agent local: heartbeat, telemetria e execução de planos aprovados."""


@agent.command("heartbeat")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--db", "write_db", is_flag=True, help="Grava heartbeat em DbOmniFleet via PgBouncer.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def agent_heartbeat(host_id: str | None, write_db: bool, json_output: bool) -> None:
    """Coleta telemetry local e atualiza cache/DB."""
    resolved_host = host_id or _default_host_id()
    payload = _collect_telemetry(resolved_host)
    _save_heartbeat_cache(payload)
    if write_db:
        _write_heartbeat_db(payload, env=_db_env())
    _append_audit_event(
        {
            "actor": "omni-fleet-agent",
            "host": resolved_host,
            "action": "heartbeat",
            "target": "node-telemetry",
            "result": payload["health"],
            "timestamp": payload["last_contact"],
            "metadata": {"db_write": write_db},
        }
    )
    _emit(payload, json_output)


@agent.command("once")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--plan-file", type=click.Path(path_type=Path), default=None, help="Executa plano JSON local para teste.")
@click.option("--db", "use_db", is_flag=True, help="Busca plano aprovado em DbOmniFleet via PgBouncer.")
@click.option("--apply", "apply_changes", is_flag=True, help="Executa de fato; sem isto apenas renderiza dry-run.")
@click.option("--json", "json_output", is_flag=True, help="Emite resultado em JSON.")
def agent_once(host_id: str | None, plan_file: Path | None, use_db: bool, apply_changes: bool, json_output: bool) -> None:
    """Executa no máximo um update plan aprovado para este host."""
    resolved_host = host_id or _default_host_id()
    env = _db_env() if use_db else None
    plan: dict[str, Any] | None = None
    if plan_file:
        plan = json.loads(plan_file.read_text())
        plan.setdefault("host_id", resolved_host)
    elif use_db:
        plan = _claim_next_plan(resolved_host, env=env or {})
    else:
        raise click.ClickException("use --plan-file para teste local ou --db para buscar na fila")
    if not plan:
        _emit({"host": resolved_host, "status": "idle", "source": "database" if use_db else "plan-file"}, json_output)
        return
    result = _execute_plan(plan, apply_changes=apply_changes, env=env)
    if use_db and env is not None and apply_changes and plan.get("id"):
        _finish_plan_db(str(plan["id"]), result, env=env)
    _append_audit_event(
        {
            "actor": "omni-fleet-agent",
            "host": resolved_host,
            "action": "update-plan.execute",
            "target": result.get("command_key"),
            "result": result.get("status"),
            "timestamp": result.get("finished_at"),
            "metadata": result,
        }
    )
    _emit(result, json_output)


@agent.command("loop")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--interval", default=30, show_default=True, help="Intervalo entre ciclos em segundos.")
@click.option("--apply", "apply_changes", is_flag=True, help="Executa planos aprovados; sem isto roda dry-run.")
def agent_loop(host_id: str | None, interval: int, apply_changes: bool) -> None:
    """Loop persistente para systemd: heartbeat + um plano por ciclo."""
    resolved_host = host_id or _default_host_id()
    while True:
        payload = _collect_telemetry(resolved_host)
        _save_heartbeat_cache(payload)
        try:
            env = _db_env()
            _write_heartbeat_db(payload, env=env)
            plan = _claim_next_plan(resolved_host, env=env)
            if plan:
                result = _execute_plan(plan, apply_changes=apply_changes, env=env)
                if apply_changes and plan.get("id"):
                    _finish_plan_db(str(plan["id"]), result, env=env)
                click.echo(json.dumps({"cycle": _now(), "host": resolved_host, "plan": result}, sort_keys=True))
            else:
                click.echo(json.dumps({"cycle": _now(), "host": resolved_host, "status": "idle"}, sort_keys=True))
        except Exception as exc:
            _append_audit_event(
                {
                    "actor": "omni-fleet-agent",
                    "host": resolved_host,
                    "action": "agent.loop",
                    "target": "DbOmniFleet",
                    "result": "degraded",
                    "timestamp": _now(),
                    "metadata": {"error": _redact_text(str(exc))},
                }
            )
            click.echo(json.dumps({"cycle": _now(), "host": resolved_host, "status": "degraded", "error": _redact_text(str(exc))}, sort_keys=True))
        time.sleep(max(interval, 5))


@fleet.group("monitor")
def monitor() -> None:
    """Visão cross-server de status e recursos da frota."""


@monitor.command("hosts")
@click.option("--db/--local", "use_db", default=True, show_default=True, help="Lê DbOmniFleet; fallback local se indisponível.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def monitor_hosts(use_db: bool, json_output: bool) -> None:
    """Mostra como um servidor enxerga os demais via heartbeat/telemetria."""
    payload = _monitor_payload(use_db=use_db)
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    click.echo(f"source: {payload['source']}")
    if payload.get("db_error"):
        click.echo(f"db_error: {payload['db_error']}")
    click.echo(f"{'HOST':24} {'STATUS':10} {'LAST_CONTACT':25} {'LOAD':>6} {'MEM%':>6} {'DISK%':>6}")
    for host in payload["hosts"]:
        click.echo(
            f"{str(host.get('host')):24} {str(host.get('status')):10} "
            f"{str(host.get('last_contact') or '-'):25} "
            f"{str(host.get('load_1m') or '-'):>6} "
            f"{str(host.get('memory_used_percent') or '-'):>6} "
            f"{str(host.get('disk_root_used_percent') or '-'):>6}"
        )


@fleet.command("audit")
@click.option("--host", "host_id", default=None, help="Filtra por host.")
@click.option("--action", default=None, help="Filtra por ação.")
@click.option("--json", "json_output", is_flag=True, help="Emite eventos em JSON.")
def audit(host_id: str | None, action: str | None, json_output: bool) -> None:
    """Lê eventos locais de auditoria quando existirem."""
    events: list[dict[str, Any]] = []
    if AUDIT_EVENTS.exists():
        for line in AUDIT_EVENTS.read_text().splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"result": "invalid-json", "raw": _redact_text(line[:120])}
            if host_id and event.get("host") != host_id:
                continue
            if action and event.get("action") != action:
                continue
            events.append(_redact(event))
    payload = {
        "audit_log": str(AUDIT_EVENTS),
        "host": host_id,
        "action": action,
        "event_count": len(events),
        "events": events,
        "schema": {
            "actor": "string",
            "host": "string",
            "action": "string",
            "target": "string",
            "result": "string",
            "timestamp": "RFC3339",
            "metadata": "object",
        },
    }
    _emit(payload, json_output)


@fleet.command("status")
@click.option("--all", "all_hosts", is_flag=True, help="Inclui status de todos os hosts inventariados.")
def status(all_hosts: bool) -> None:
    """Status inicial do módulo fleet."""
    hosts_dir = _hosts_dir()
    click.echo(f"repo:  {REPO}")
    click.echo(f"hosts: {hosts_dir} ({'ok' if hosts_dir.exists() else 'missing'})")
    click.echo(f"legacy_hosts: {LEGACY_HOSTS_DIR} ({'present' if LEGACY_HOSTS_DIR.exists() else 'absent'})")
    click.echo("control_plane: M004 live foundation present; generic --apply remains gated")
    click.echo(f"heartbeat_dir: {HEARTBEAT_DIR}")
    click.echo(f"audit_log: {AUDIT_EVENTS}")
    if all_hosts and hosts_dir.exists():
        click.echo("")
        click.echo(f"{'HOST':24} {'STATUS':10} HEALTH")
        for path in sorted(hosts_dir.glob("*.yaml")):
            data = _simple_yaml(path.read_text())
            payload = _heartbeat_payload(data, path)
            click.echo(f"{payload['host']:24} {payload['status']:10} {payload['health']}")
