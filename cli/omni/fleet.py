"""fleet — multi-host inventory and control-plane contracts."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", "/home/ubuntu/GitHub/omni-srv-admin"))
HOSTS_DIR = REPO / "inventory" / "hosts"
LEGACY_HOSTS_DIR = REPO / "hosts"
FLEET_LOG_DIR = Path(os.environ.get("OMNI_FLEET_LOG_DIR", "/home/ubuntu/.logs/fleet"))
HEARTBEAT_DIR = FLEET_LOG_DIR / "heartbeats"
AUDIT_EVENTS = FLEET_LOG_DIR / "audit-events.jsonl"

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
    if heartbeat_file.exists():
        try:
            heartbeat = json.loads(heartbeat_file.read_text())
            status = str(heartbeat.get("status") or "unknown")
            last_contact = heartbeat.get("last_contact")
            health = str(heartbeat.get("health") or "unknown")
        except Exception:
            status = "degraded"
            health = "invalid-heartbeat-file"
    return {
        "host": host_id,
        "agent_version": "not-installed",
        "os": _nested(host, "platform", "os", "unknown"),
        "arch": _nested(host, "platform", "arch", "unknown"),
        "uptime": None,
        "disk": None,
        "memory": None,
        "service_health": {},
        "status": status,
        "health": health,
        "last_contact": last_contact,
        "generated_at": _now(),
    }


def _program_records(host: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    host_id = _host_id(host, path.stem)
    modules = host.get("modules") if isinstance(host.get("modules"), list) else []
    records = []
    for module in modules:
        records.append(
            {
                "host": host_id,
                "program": str(module),
                "install_type": "omni-module",
                "current_version": "unknown",
                "desired_version": "inventory-managed",
                "source": "inventory/hosts",
                "managed_by": "omni-srv-admin",
                "update_policy": "plan-first",
            }
        )
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


@fleet.command("audit")
@click.option("--host", "host_id", default=None, help="Filtra por host.")
@click.option("--json", "json_output", is_flag=True, help="Emite eventos em JSON.")
def audit(host_id: str | None, json_output: bool) -> None:
    """Lê eventos locais de auditoria quando existirem."""
    events: list[dict[str, Any]] = []
    if AUDIT_EVENTS.exists():
        for line in AUDIT_EVENTS.read_text().splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"result": "invalid-json", "raw": line[:120]}
            if host_id and event.get("host") != host_id:
                continue
            events.append(event)
    payload = {
        "audit_log": str(AUDIT_EVENTS),
        "host": host_id,
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
    click.echo("control_plane: M004 contracts present; live install blocked until gates pass")
    click.echo(f"heartbeat_dir: {HEARTBEAT_DIR}")
    click.echo(f"audit_log: {AUDIT_EVENTS}")
    if all_hosts and hosts_dir.exists():
        click.echo("")
        click.echo(f"{'HOST':24} {'STATUS':10} HEALTH")
        for path in sorted(hosts_dir.glob("*.yaml")):
            data = _simple_yaml(path.read_text())
            payload = _heartbeat_payload(data, path)
            click.echo(f"{payload['host']:24} {payload['status']:10} {payload['health']}")
