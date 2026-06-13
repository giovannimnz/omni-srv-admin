"""fleet-backup — fila serial de backups rclone multi-server.

Wrapper Click em cima de rclone-fleet-queue.sh. Subcomandos:
  enqueue     enfileira backup de 1 server
  enqueue-all enfileira backup dos 3 servers
  run         processa fila
  status      mostra fila + mounts remotos
  clear       limpa fila
  drain       força execução imediata de 1 server (pula cooldown)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click

SCRIPT = Path(os.environ.get("OMNI_FLEET_BACKUP_SCRIPT", Path.home() / "scripts/rclone-fleet-queue.sh"))


def _run(args: list[str]) -> None:
    """Executa o script bash propagando o exit code."""
    if not SCRIPT.exists():
        raise click.ClickException(f"script não encontrado: {SCRIPT} (rode install-fleet-backup.sh)")
    result = subprocess.run([str(SCRIPT), *args])
    sys.exit(result.returncode)


@click.group(name="fleet-backup")
def fleet_backup() -> None:
    """Fila serial de backups rclone (multi-server, 1 por vez, cooldown 5min)."""


@fleet_backup.command("enqueue")
@click.argument("srv_num", type=click.Choice(["1", "2", "3"]))
@click.argument("snapshot", default=None, required=False)
def enqueue(srv_num: str, snapshot: str | None) -> None:
    """Enfileira backup de SRV_NUM (1|2|3) com SNAPSHOT opcional."""
    args = ["enqueue", srv_num]
    if snapshot:
        args.append(snapshot)
    _run(args)


@fleet_backup.command("enqueue-all")
def enqueue_all() -> None:
    """Enfileira backup dos 3 servers (1, 2, 3) com snapshot manual."""
    for srv in ("1", "2", "3"):
        _run(["enqueue", srv, "fleet-backup"])


@fleet_backup.command("run")
def run() -> None:
    """Processa fila (1 por vez, cooldown 5min entre servers)."""
    _run(["run"])


@fleet_backup.command("status")
def status() -> None:
    """Mostra fila atual + status dos mounts remotos."""
    _run(["status"])


@fleet_backup.command("clear")
def clear() -> None:
    """Limpa fila (remove todos os .job)."""
    _run(["clear"])


@fleet_backup.command("drain")
@click.argument("srv_num", type=click.Choice(["1", "2", "3"]))
def drain(srv_num: str) -> None:
    """Força execução imediata de SRV_NUM (pula cooldown)."""
    _run(["drain", srv_num])
