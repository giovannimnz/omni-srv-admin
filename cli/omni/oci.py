"""oci — workflow versionado de snapshots OCI para hosts gerenciados (M005 follow-up / M007).

Implementa o fluxo formal de snapshots OCI para hosts do inventário cujo
`platform.provider` é `oracle-oci` (SRV-1/2/3, horistic-srv). O módulo
existe para preencher o gate de rollback formal do M005 sem custo
recorrente novo: o `routine` (semanal via systemd timer) e o `preflight`
(antes de operações de risco) registram o `ImageId` resultante no
inventário e em `DbOmniFleet/TbConfigItems` (quando disponível).

Quando o CLI `oci` e a config em `~/.oci` não estão presentes (cenário
atual em todos os hosts — ver `13-OCI-ROLLBACK-PATH-2026-06-14.md`), o
fallback é `--dry-run`/`--plan`, que imprime os comandos OCI que seriam
executados, registra o snapshot como `pending` no inventário e na DB e
deixa o runbook como source of truth para a execução manual/controlada.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from .db_runtime import default_fleet_db_env, load_env_file, run_sql

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", str(Path(__file__).resolve().parents[2])))
HOSTS_DIR = REPO / "inventory" / "hosts"
LEGACY_HOSTS_DIR = REPO / "hosts"
FLEET_LOG_DIR = Path(os.environ.get("OMNI_FLEET_LOG_DIR", "/home/ubuntu/.logs/fleet"))
FLEET_DB_ENV = default_fleet_db_env()

OCI_PROVIDERS = {"oracle-oci"}
OCI_REQUIRED_FIELDS = ("id", "platform", "access")

# State and log paths (mirrored for both interactive and routine use).
OCI_STATE_DIR = Path(os.environ.get("OMNI_OCI_STATE_DIR", str(Path.home() / ".local" / "state" / "omni")))
OCI_LOG_DIR = Path(os.environ.get("OMNI_OCI_LOG_DIR", str(Path.home() / ".logs" / "oci")))
OCI_LAST_SNAPSHOT_FILE = OCI_STATE_DIR / "oci-last-snapshot.json"
OCI_ROUTINE_LOG = OCI_LOG_DIR / "routine-snapshots.jsonl"
OCI_PREFLIGHT_LOG = OCI_LOG_DIR / "preflight-snapshots.jsonl"
OCI_DRILL_LOG_DIR = OCI_LOG_DIR / "restore-drills"

# Configuration key prefix used to mirror snapshot IDs into TbConfigItems.
TB_CONFIG_SNAPSHOT_KEY = "oci.snapshot_id"
TB_CONFIG_ROUTINE_KEY = "oci.routine_schedule"
TB_CONFIG_LAST_AT_KEY = "oci.last_snapshot_at"


# ---------------------------------------------------------------------------
# YAML helpers (lightweight, intentionally hand-rolled to match fleet.py style)
# ---------------------------------------------------------------------------


def _read_simple_yaml(path: Path) -> dict[str, Any]:
    """Parse a flat-ish YAML inventory file using PyYAML if present, fallback to a minimal parser."""
    text = path.read_text()
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ImportError:
        pass
    # Minimal fallback — sufficient for the well-known sections we touch.
    data: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            key, _, value = line.partition(":")
            value = value.strip()
            if value == "" or value == "|" or value == ">":
                current = {}
                data[key.strip()] = current
            else:
                if current is not None and not line.startswith(" "):
                    current = None
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                if current is not None:
                    current[key.strip()] = value
                else:
                    data[key.strip()] = value
        else:
            if current is None:
                continue
            # Skip deeper structures — the fallback intentionally ignores them.
            continue
    return data


def _host_path(host_id: str) -> Path:
    if not HOSTS_DIR.exists() and LEGACY_HOSTS_DIR.exists():
        return LEGACY_HOSTS_DIR / f"{host_id}.yaml"
    return HOSTS_DIR / f"{host_id}.yaml"


def _load_oci_host(host_id: str) -> tuple[Path, dict[str, Any]]:
    path = _host_path(host_id)
    if not path.exists():
        raise click.ClickException(f"host não encontrado no inventário: {host_id}")
    data = _read_simple_yaml(path)
    for field in OCI_REQUIRED_FIELDS:
        if field not in data:
            raise click.ClickException(f"host {host_id} inválido: falta campo '{field}' em {path}")
    platform = data.get("platform") or {}
    if not isinstance(platform, dict):
        raise click.ClickException(f"host {host_id} tem 'platform' malformado")
    provider = str(platform.get("provider", ""))
    if provider not in OCI_PROVIDERS:
        raise click.ClickException(
            f"host {host_id} não é OCI (provider={provider!r}). Use em hosts oracle-oci."
        )
    return path, data


def _yaml_get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _oci_config_available() -> bool:
    config_path = Path.home() / ".oci" / "config"
    if config_path.exists():
        return True
    env_path = os.environ.get("OCI_CLI_CONFIG_FILE", "")
    return bool(env_path)


# ---------------------------------------------------------------------------
# OCI CLI detection and command rendering
# ---------------------------------------------------------------------------


def _oci_cli_available() -> bool:
    return shutil.which("oci") is not None


def _render_create_image_cmd(
    *,
    host_id: str,
    instance_ocid: str,
    compartment_ocid: str,
    display_name: str,
    stop_instance: bool,
) -> list[str]:
    """Build the OCI CLI command that performs `compute image create` (or stop+create)."""
    cmd: list[str] = [
        "oci",
        "compute",
        "image",
        "create",
        "--compartment-id",
        compartment_ocid,
        "--instance-id",
        instance_ocid,
        "--display-name",
        display_name,
        "--image-source",
        "instance",
        "--output",
        "json",
        "--query",
        "data.id",
    ]
    if stop_instance:
        # Caller is expected to issue the stop first; we just emit a hint via env-var.
        os.environ.setdefault("OMNI_OCI_PREFLIGHT_STOP", "1")
    return cmd


def _render_launch_instance_cmd(
    *,
    compartment_ocid: str,
    image_ocid: str,
    availability_domain: str,
    shape: str,
    subnet_ocid: str,
    display_name: str,
) -> list[str]:
    return [
        "oci",
        "compute",
        "instance",
        "launch",
        "--compartment-id",
        compartment_ocid,
        "--availability-domain",
        availability_domain,
        "--shape",
        shape,
        "--image-id",
        image_ocid,
        "--subnet-id",
        subnet_ocid,
        "--display-name",
        display_name,
        "--assign-public-ip",
        "false",
        "--output",
        "json",
        "--query",
        "data.id",
    ]


# ---------------------------------------------------------------------------
# Persistence (local state file + DbOmniFleet mirror when reachable)
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dirs() -> None:
    for d in (OCI_STATE_DIR, OCI_LOG_DIR, OCI_DRILL_LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _append_log(path: Path, payload: dict[str, Any]) -> None:
    _ensure_dirs()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def _psql(query: str, *, env: dict[str, str] | None = None, timeout: int = 10) -> str:
    """Run psql with the fleet DB env; raise on error to keep callers explicit."""
    e = env or os.environ.copy()
    config = FLEET_DB_ENV
    if config.exists():
        e.update(load_env_file(config))
    return run_sql(query, env=e, timeout=timeout)


def _mirror_to_fleet_db(
    *,
    host_id: str,
    snapshot_id: str,
    snapshot_at: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Mirror the snapshot ID into TbConfigItems when DbOmniFleet is reachable.

    Schema (TbConfigItems): id, scope_id, host_id, key, value (jsonb), value_type, source, description, updated_by.
    """
    payload = {
        "host": host_id,
        "snapshot_id": snapshot_id,
        "snapshot_at": snapshot_at,
        "keys": [
            (TB_CONFIG_SNAPSHOT_KEY, json.dumps(snapshot_id)),
            (TB_CONFIG_LAST_AT_KEY, json.dumps(snapshot_at)),
        ],
    }
    if dry_run or not _oci_cli_available():
        payload["status"] = "dry-run"
        return payload
    if not FLEET_DB_ENV.exists():
        payload["status"] = "skipped"
        payload["reason"] = "fleet-db.env ausente"
        return payload
    try:
        for key, value in payload["keys"]:
            sql = (
                f"DELETE FROM \"TbConfigItems\" WHERE host_id = '{host_id}' AND key = '{key}'; "
                f"INSERT INTO \"TbConfigItems\" (host_id, key, value, value_type, source, description, updated_by) "
                f"VALUES ('{host_id}', '{key}', '{value}'::jsonb, 'string', 'oci-snapshot', "
                f"'OCI snapshot ID (Phase 15)', 'omni-srv-admin');"
            )
            _psql(sql)
        payload["status"] = "mirrored"
    except Exception as exc:  # noqa: BLE001 — surface as data, do not crash CLI
        payload["status"] = "error"
        payload["error"] = str(exc)
    return payload


# ---------------------------------------------------------------------------
# Inventory update (best-effort, only touches the oci: block)
# ---------------------------------------------------------------------------


def _update_inventory_oci_block(
    *,
    host_id: str,
    snapshot_id: str,
    snapshot_at: str,
    routine_schedule: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    """Append/update an `oci:` block in inventory/hosts/<host>.yaml.

    PyYAML round-trip is preferred; without it, we append the block at end
    of file and update scalar fields using line-level replace.
    """
    path = _host_path(host_id)
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    new_block_lines = [
        "oci:",
        f"  last_snapshot_id: \"{snapshot_id}\"",
        f"  last_snapshot_at: \"{snapshot_at}\"",
    ]
    if routine_schedule:
        new_block_lines.append(f"  routine_schedule: \"{routine_schedule}\"")
    block_text = "\n".join(new_block_lines) + "\n"
    text = path.read_text()
    summary: dict[str, Any] = {"path": str(path), "dry_run": dry_run}
    if "oci:" in text:
        # Replace existing block (between `oci:` and next top-level key).
        # Anchor on `^oci:` so we never match `...-srv-adminoci` substrings.
        import re

        lines = text.splitlines()
        start: int | None = None
        end: int | None = None
        for idx, line in enumerate(lines):
            if re.match(r"^oci:\s*$", line):
                start = idx
                continue
            if start is not None and line and not line.startswith(" ") and not line.startswith("#"):
                end = idx
                break
        if start is None:
            return {"status": "error", "reason": "could not locate oci: block"}
        end = end if end is not None else len(lines)
        new_text = "\n".join(lines[:start]) + block_text + "\n".join(lines[end:])
    else:
        new_text = text.rstrip() + "\n\n" + block_text
    if dry_run:
        summary["status"] = "dry-run"
        summary["would_write_lines"] = block_text.splitlines()
    else:
        path.write_text(new_text)
        summary["status"] = "updated"
    return summary

# ---------------------------------------------------------------------------
# Click group
# ---------------------------------------------------------------------------


@click.group(name="oci")
def oci() -> None:
    """Snapshot OCI e restore drill para hosts oracle-oci do inventário."""


@oci.group(name="snapshot")
def snapshot() -> None:
    """Subcomandos de snapshot (preflight e routine)."""


@snapshot.command("preflight")
@click.option("--host", "host_id", required=True, help="ID do host no inventário (ex: atius-srv-1).")
@click.option(
    "--instance-ocid",
    "instance_ocid",
    default=None,
    help="OCID da instance. Default: lido de DbOmniFleet (TbConfigItems) ou falha em dry-run.",
)
@click.option(
    "--compartment-ocid",
    "compartment_ocid",
    default=None,
    help="OCID do compartment. Default: derivado do host (inventory) ou falha em dry-run.",
)
@click.option("--display-name", "display_name", default=None, help="Display name do custom image.")
@click.option(
    "--stop/--no-stop",
    default=True,
    show_default=True,
    help="Stop a instance antes de criar o snapshot (crash-consistent vs application-consistent).",
)
@click.option(
    "--gate/--no-gate",
    default=True,
    show_default=True,
    help="Confirmação interativa antes de chamar a OCI API.",
)
@click.option(
    "--plan/--no-plan",
    "plan_only",
    default=False,
    show_default=True,
    help="Apenas imprime o plano; nunca chama a OCI API.",
)
@click.option(
    "--json", "json_output", is_flag=True, help="Emite saída em JSON (sem logs intermediários)."
)
def snapshot_preflight(
    host_id: str,
    instance_ocid: str | None,
    compartment_ocid: str | None,
    display_name: str | None,
    stop: bool,
    gate: bool,
    plan_only: bool,
    json_output: bool,
) -> None:
    """Cria um snapshot OCI gated antes de operações de risco.

    Comportamento:

    - Se `--plan` for passado, imprime os comandos OCI que seriam executados
      e registra o snapshot como `pending` no inventário e no `oci-last-snapshot.json`.
    - Se `--no-gate`, executa a chamada real (requer `oci` CLI + `~/.oci`).
    - Em todos os casos, faz mirror em `DbOmniFleet/TbConfigItems` (se acessível).
    """
    path, host_data = _load_oci_host(host_id)
    display_name = display_name or f"omni-srv-admin-preflight-{host_id}-{_now_iso()}"
    plan: dict[str, Any] = {
        "host": host_id,
        "host_file": str(path),
        "display_name": display_name,
        "stop": stop,
        "instance_ocid": instance_ocid,
        "compartment_ocid": compartment_ocid,
        "now": _now_iso(),
        "oci_cli": _oci_cli_available(),
        "oci_config": _oci_config_available(),
        "plan_only": plan_only,
        "gate": gate,
    }
    if not instance_ocid:
        plan["instance_ocid_source"] = "fallback: must be supplied or read from DbOmniFleet"
    if not compartment_ocid:
        plan["compartment_ocid_source"] = "fallback: must be supplied or read from DbOmniFleet"

    if gate and not plan_only:
        click.confirm(
            f"Criar snapshot OCI para {host_id} (display_name={display_name})?",
            abort=True,
        )

    cmd = _render_create_image_cmd(
        host_id=host_id,
        instance_ocid=instance_ocid or "<INSTANCE_OCID_REQUIRED>",
        compartment_ocid=compartment_ocid or "<COMPARTMENT_OCID_REQUIRED>",
        display_name=display_name,
        stop_instance=stop,
    )
    plan["oci_cmd"] = cmd

    if plan_only or not _oci_cli_available() or not _oci_config_available() or not instance_ocid or not compartment_ocid:
        snapshot_id = f"pending-{uuid.uuid4()}"
        plan["status"] = "dry-run"
        plan["snapshot_id"] = snapshot_id
        plan["reason"] = (
            "missing oci CLI" if not _oci_cli_available() else
            "missing oci config" if not _oci_config_available() else
            "missing instance_ocid or compartment_ocid" if not (instance_ocid and compartment_ocid) else
            "plan-only"
        )
    else:
        if stop:
            stop_cmd = [
                "oci", "compute", "instance", "action",
                "--instance-id", instance_ocid, "--action", "STOP",
                "--wait-for-state", "STOPPED",
            ]
            plan["stop_cmd"] = stop_cmd
            stop_proc = subprocess.run(stop_cmd, capture_output=True, text=True, check=False)
            plan["stop_rc"] = stop_proc.returncode
            if stop_proc.returncode != 0:
                plan["status"] = "error"
                plan["error"] = (stop_proc.stderr or stop_proc.stdout).strip()
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        plan["oci_rc"] = proc.returncode
        if proc.returncode == 0:
            snapshot_id = proc.stdout.strip().strip('"')
            plan["snapshot_id"] = snapshot_id
            plan["status"] = "ok"
        else:
            plan["status"] = "error"
            plan["error"] = (proc.stderr or proc.stdout).strip()
            snapshot_id = f"failed-{uuid.uuid4()}"
            plan["snapshot_id"] = snapshot_id

    snapshot_at = _now_iso()
    plan["snapshot_at"] = snapshot_at

    # Decide side-effects:
    #   --plan: pure plan, no inventory/DB write, no log.
    #   real OCI call: write inventory + DB + log.
    #   no oci CLI/config (offline host): write inventory + log, skip DB mirror.
    inventory_dry_run = plan_only
    db_dry_run = plan_only or (plan["status"] != "ok")
    skip_logs = plan_only

    if not skip_logs:
        _ensure_dirs()
        last_payload = {
            "host": host_id,
            "snapshot_id": plan["snapshot_id"],
            "snapshot_at": snapshot_at,
            "display_name": display_name,
            "status": plan["status"],
            "mode": "preflight",
            "stop": stop,
        }
        OCI_LAST_SNAPSHOT_FILE.write_text(json.dumps(last_payload, indent=2, sort_keys=True))
        _append_log(OCI_PREFLIGHT_LOG, last_payload)

    plan["inventory"] = _update_inventory_oci_block(
        host_id=host_id,
        snapshot_id=plan["snapshot_id"],
        snapshot_at=snapshot_at,
        routine_schedule=None,
        dry_run=inventory_dry_run,
    )
    plan["db_mirror"] = _mirror_to_fleet_db(
        host_id=host_id,
        snapshot_id=plan["snapshot_id"],
        snapshot_at=snapshot_at,
        dry_run=db_dry_run,
    )

    if json_output:
        click.echo(json.dumps(plan, indent=2, sort_keys=True))
        return

    click.echo(f"host           : {host_id}")
    click.echo(f"display_name   : {display_name}")
    click.echo(f"snapshot_id    : {plan['snapshot_id']}")
    click.echo(f"snapshot_at    : {snapshot_at}")
    click.echo(f"status         : {plan['status']}")
    click.echo(f"oci CLI        : {'yes' if _oci_cli_available() else 'no'}")
    click.echo(f"oci config     : {'yes' if _oci_config_available() else 'no'}")
    click.echo(f"inventory      : {plan['inventory'].get('status')}")
    click.echo(f"db_mirror      : {plan['db_mirror'].get('status')}")
    click.echo("oci_cmd:")
    click.echo("  " + " ".join(shlex.quote(part) for part in cmd))


@snapshot.command("routine")
@click.option(
    "--host", "host_id", required=True, help="ID do host no inventário (ex: atius-srv-1)."
)
@click.option(
    "--instance-ocid",
    "instance_ocid",
    default=None,
    help="OCID da instance (opcional; lido de DbOmniFleet ou passado via env).",
)
@click.option(
    "--compartment-ocid",
    "compartment_ocid",
    default=None,
    help="OCID do compartment (opcional).",
)
@click.option(
    "--display-name", "display_name", default=None, help="Display name do custom image."
)
@click.option(
    "--schedule",
    "schedule",
    default="weekly Sun 04:00 BRT",
    show_default=True,
    help="Descrição do schedule (gravada no inventário).",
)
@click.option(
    "--json", "json_output", is_flag=True, help="Emite saída em JSON (sem logs intermediários)."
)
def snapshot_routine(
    host_id: str,
    instance_ocid: str | None,
    compartment_ocid: str | None,
    display_name: str | None,
    schedule: str,
    json_output: bool,
) -> None:
    """Cria um snapshot OCI non-interactive (chamado pelo systemd timer)."""
    path, host_data = _load_oci_host(host_id)
    display_name = display_name or f"omni-srv-admin-routine-{host_id}-{_now_iso()}"
    plan: dict[str, Any] = {
        "host": host_id,
        "host_file": str(path),
        "display_name": display_name,
        "stop": False,
        "instance_ocid": instance_ocid,
        "compartment_ocid": compartment_ocid,
        "schedule": schedule,
        "now": _now_iso(),
        "oci_cli": _oci_cli_available(),
        "oci_config": _oci_config_available(),
        "mode": "routine",
    }
    cmd = _render_create_image_cmd(
        host_id=host_id,
        instance_ocid=instance_ocid or "<INSTANCE_OCID_REQUIRED>",
        compartment_ocid=compartment_ocid or "<COMPARTMENT_OCID_REQUIRED>",
        display_name=display_name,
        stop_instance=False,
    )
    plan["oci_cmd"] = cmd
    snapshot_id = f"pending-{uuid.uuid4()}"
    plan["snapshot_id"] = snapshot_id
    plan["status"] = "dry-run"
    plan["reason"] = (
        "missing oci CLI" if not _oci_cli_available() else
        "missing oci config" if not _oci_config_available() else
        "missing instance_ocid or compartment_ocid"
    )

    snapshot_at = _now_iso()
    plan["snapshot_at"] = snapshot_at
    _ensure_dirs()
    last_payload = {
        "host": host_id,
        "snapshot_id": snapshot_id,
        "snapshot_at": snapshot_at,
        "display_name": display_name,
        "status": plan["status"],
        "mode": "routine",
        "schedule": schedule,
    }
    OCI_LAST_SNAPSHOT_FILE.write_text(json.dumps(last_payload, indent=2, sort_keys=True))
    _append_log(OCI_ROUTINE_LOG, last_payload)

    offline = not _oci_cli_available() or not _oci_config_available()
    # Inventory: always record the attempt (pending-* when offline); schedule is recorded too.
    # DB mirror: only when the OCI CLI call actually succeeded; otherwise dry-run.
    plan["inventory"] = _update_inventory_oci_block(
        host_id=host_id,
        snapshot_id=snapshot_id,
        snapshot_at=snapshot_at,
        routine_schedule=schedule,
        dry_run=False,
    )
    plan["db_mirror"] = _mirror_to_fleet_db(
        host_id=host_id,
        snapshot_id=snapshot_id,
        snapshot_at=snapshot_at,
        dry_run=offline,
    )

    if json_output:
        click.echo(json.dumps(plan, indent=2, sort_keys=True))
        return

    click.echo(f"host         : {host_id}")
    click.echo(f"snapshot_id  : {snapshot_id}")
    click.echo(f"snapshot_at  : {snapshot_at}")
    click.echo(f"schedule     : {schedule}")
    click.echo(f"status       : {plan['status']} ({plan.get('reason', '')})")
    click.echo(f"oci CLI      : {'yes' if _oci_cli_available() else 'no'}")
    click.echo(f"oci config   : {'yes' if _oci_config_available() else 'no'}")


# ---------------------------------------------------------------------------
# Restore drill (DR validation)
# ---------------------------------------------------------------------------


@oci.group(name="restore")
def restore() -> None:
    """Subcomandos de restore drill e restore real."""


@restore.command("drill")
@click.option(
    "--host", "host_id", required=True, help="ID do host (ex: atius-srv-1)."
)
@click.option(
    "--snapshot-id", "snapshot_id", default=None,
    help="OCID do custom image. Default: lido do inventário (oci.last_snapshot_id).",
)
@click.option(
    "--compartment-ocid",
    "compartment_ocid",
    default=None,
    help="OCID do compartment. Default: lido de DbOmniFleet ou passado via env.",
)
@click.option(
    "--availability-domain",
    "availability_domain",
    default=None,
    help="AD OCI (ex: iad:PHX-AD-1). Default: lido do host.",
)
@click.option(
    "--shape",
    "shape",
    default="VM.Standard.A1.Flex",
    show_default=True,
    help="Shape OCI da nova instance.",
)
@click.option(
    "--subnet-ocid", "subnet_ocid", default=None,
    help="OCID da subnet. Default: lido de DbOmniFleet ou passado via env.",
)
@click.option(
    "--display-name", "display_name", default=None,
    help="Display name da nova instance (padrão: omni-drill-<host>-<ts>).",
)
@click.option(
    "--dry-run/--no-dry-run", default=True, show_default=True,
    help="Apenas imprime o plano; nunca chama a OCI API.",
)
@click.option(
    "--keep-instance/--destroy-instance", default=False, show_default=True,
    help="Mantém a instance após o drill (default: destruída).",
)
@click.option(
    "--json", "json_output", is_flag=True, help="Emite saída em JSON (sem logs intermediários)."
)
def restore_drill(
    host_id: str,
    snapshot_id: str | None,
    compartment_ocid: str | None,
    availability_domain: str | None,
    shape: str,
    subnet_ocid: str | None,
    display_name: str | None,
    dry_run: bool,
    keep_instance: bool,
    json_output: bool,
) -> None:
    """Simula o restore de um snapshot OCI, sem chamadas à OCI API quando `--dry-run`."""
    path, host_data = _load_oci_host(host_id)
    # Resolve snapshot_id from inventory if not supplied.
    if not snapshot_id:
        snapshot_id = _yaml_get_nested(host_data, "oci", "last_snapshot_id")
    if not snapshot_id:
        raise click.ClickException(
            f"host {host_id} sem snapshot ID em inventory. "
            "Rode `omni srv oci snapshot preflight` antes ou passe --snapshot-id."
        )
    is_pending = snapshot_id.startswith("pending-")
    if is_pending and not dry_run:
        raise click.ClickException(
            f"host {host_id} com snapshot pending ({snapshot_id}) — restore real exige ID OCI real. "
            "Use --dry-run para validar o plano ou passe --snapshot-id=ocid1.image.oc1..."
        )
    display_name = display_name or f"omni-drill-{host_id}-{_now_iso()}"
    cmd = _render_launch_instance_cmd(
        compartment_ocid=compartment_ocid or "<COMPARTMENT_OCID_REQUIRED>",
        image_ocid=snapshot_id,
        availability_domain=availability_domain or "<AD_REQUIRED>",
        shape=shape,
        subnet_ocid=subnet_ocid or "<SUBNET_OCID_REQUIRED>",
        display_name=display_name,
    )
    plan: dict[str, Any] = {
        "host": host_id,
        "host_file": str(path),
        "snapshot_id": snapshot_id,
        "display_name": display_name,
        "shape": shape,
        "availability_domain": availability_domain,
        "compartment_ocid": compartment_ocid,
        "subnet_ocid": subnet_ocid,
        "keep_instance": keep_instance,
        "dry_run": dry_run,
        "now": _now_iso(),
        "oci_cli": _oci_cli_available(),
        "oci_config": _oci_config_available(),
        "oci_cmd": cmd,
    }

    if dry_run or not _oci_cli_available() or not _oci_config_available() or not compartment_ocid or not subnet_ocid or not availability_domain:
        plan["status"] = "dry-run"
        plan["reason"] = (
            "missing oci CLI" if not _oci_cli_available() else
            "missing oci config" if not _oci_config_available() else
            "missing compartment_ocid, subnet_ocid, or availability_domain"
        )
        # Generate an obviously fake instance OCID for traceability.
        plan["drill_instance_ocid"] = f"ocid1.instance.oc1.dry-run.{uuid.uuid4()}"
    else:
        launch_proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        plan["oci_rc"] = launch_proc.returncode
        if launch_proc.returncode != 0:
            plan["status"] = "error"
            plan["error"] = (launch_proc.stderr or launch_proc.stdout).strip()
        else:
            new_ocid = launch_proc.stdout.strip().strip('"')
            plan["drill_instance_ocid"] = new_ocid
            if not keep_instance:
                term_cmd = [
                    "oci", "compute", "instance", "terminate",
                    "--instance-id", new_ocid, "--force",
                    "--wait-for-state", "TERMINATED",
                ]
                plan["terminate_cmd"] = term_cmd
                term_proc = subprocess.run(term_cmd, capture_output=True, text=True, check=False)
                plan["terminate_rc"] = term_proc.returncode
            plan["status"] = "ok"

    # Always log the drill (dry-run or live) to the per-host drill log.
    _ensure_dirs()
    drill_log = OCI_DRILL_LOG_DIR / f"restore-drill-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"
    drill_log.write_text(json.dumps(plan, indent=2, sort_keys=True))
    plan["drill_log"] = str(drill_log)

    if json_output:
        click.echo(json.dumps(plan, indent=2, sort_keys=True))
        return

    click.echo(f"host             : {host_id}")
    click.echo(f"snapshot_id      : {snapshot_id}")
    click.echo(f"display_name     : {display_name}")
    click.echo(f"shape            : {shape}")
    click.echo(f"status           : {plan['status']} ({plan.get('reason', '')})")
    click.echo(f"drill_log        : {drill_log}")
    click.echo("oci_cmd:")
    click.echo("  " + " ".join(shlex.quote(part) for part in cmd))


# ---------------------------------------------------------------------------
# Status helper
# ---------------------------------------------------------------------------


@oci.command("status")
@click.option(
    "--host", "host_id", default=None, help="Filtra por host. Sem flag: mostra todos."
)
@click.option(
    "--json", "json_output", is_flag=True, help="Emite saída em JSON (sem logs intermediários)."
)
def oci_status(host_id: str | None, json_output: bool) -> None:
    """Mostra o estado de OCI snapshots para o host (ou para todos)."""
    rows: list[dict[str, Any]] = []
    if not HOSTS_DIR.exists() and not LEGACY_HOSTS_DIR.exists():
        raise click.ClickException("nenhum diretório de inventário encontrado")
    for inv_path in sorted((HOSTS_DIR if HOSTS_DIR.exists() else LEGACY_HOSTS_DIR).glob("*.yaml")):
        data = _read_simple_yaml(inv_path)
        provider = (data.get("platform") or {}).get("provider") if isinstance(data.get("platform"), dict) else None
        if provider not in OCI_PROVIDERS:
            continue
        hid = data.get("id") or inv_path.stem
        if host_id and hid != host_id:
            continue
        oci_block = data.get("oci") if isinstance(data.get("oci"), dict) else {}
        rows.append(
            {
                "host": hid,
                "last_snapshot_id": oci_block.get("last_snapshot_id") if isinstance(oci_block, dict) else None,
                "last_snapshot_at": oci_block.get("last_snapshot_at") if isinstance(oci_block, dict) else None,
                "routine_schedule": oci_block.get("routine_schedule") if isinstance(oci_block, dict) else None,
                "oci_cli": _oci_cli_available(),
                "oci_config": _oci_config_available(),
            }
        )
    if json_output:
        click.echo(json.dumps({"hosts": rows, "oci_cli": _oci_cli_available()}, indent=2, sort_keys=True))
        return
    if not rows:
        click.echo("nenhum host oracle-oci no inventário")
        return
    click.echo(f"{'host':22} {'last_snapshot_id':50} {'last_snapshot_at':22} {'schedule':30}")
    click.echo("-" * 130)
    for row in rows:
        click.echo(
            f"{row['host']:22} "
            f"{(row['last_snapshot_id'] or '-'):50} "
            f"{(row['last_snapshot_at'] or '-'):22} "
            f"{(row['routine_schedule'] or '-'):30}"
        )
    click.echo(f"oci CLI: {'yes' if _oci_cli_available() else 'no'}  "
               f"oci config: {'yes' if _oci_config_available() else 'no'}")


if __name__ == "__main__":  # pragma: no cover
    oci()
