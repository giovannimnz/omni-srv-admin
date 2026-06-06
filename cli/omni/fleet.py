"""fleet — multi-host inventory and future orchestration."""
from __future__ import annotations

import os
from pathlib import Path

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", "/home/ubuntu/GitHub/omni-srv-admin"))
HOSTS_DIR = REPO / "hosts"


def _simple_yaml_value(text: str, key: str, default: str = "") -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip().strip('"') or default
    return default


@click.group(name="fleet")
def fleet() -> None:
    """Inventário multi-computacional e futura orquestração remota."""


@fleet.command("list")
def list_hosts() -> None:
    """Lista hosts cadastrados em hosts/*.yaml."""
    if not HOSTS_DIR.exists():
        click.echo(f"hosts dir missing: {HOSTS_DIR}")
        return
    rows = []
    for path in sorted(HOSTS_DIR.glob("*.yaml")):
        text = path.read_text()
        rows.append((
            _simple_yaml_value(text, "id", path.stem),
            _simple_yaml_value(text, "role", "?"),
            _simple_yaml_value(text, "status", "?"),
            path.name,
        ))
    click.echo(f"{len(rows)} host(s) em {HOSTS_DIR}")
    for host_id, role, status, file_name in rows:
        click.echo(f"{host_id:24} {role:22} {status:10} {file_name}")


@fleet.command("show")
@click.argument("host_id")
def show_host(host_id: str) -> None:
    """Mostra o YAML de um host."""
    path = HOSTS_DIR / f"{host_id}.yaml"
    if not path.exists():
        matches = sorted(HOSTS_DIR.glob(f"*{host_id}*.yaml")) if HOSTS_DIR.exists() else []
        if matches:
            path = matches[0]
        else:
            raise click.ClickException(f"host não encontrado: {host_id}")
    click.echo(path.read_text())


@fleet.command("status")
def status() -> None:
    """Status inicial do módulo fleet."""
    click.echo(f"repo:  {REPO}")
    click.echo(f"hosts: {HOSTS_DIR} ({'ok' if HOSTS_DIR.exists() else 'missing'})")
    click.echo("remote execution: planned, not enabled")
