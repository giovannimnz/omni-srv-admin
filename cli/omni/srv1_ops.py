"""srv1-ops — operações locais centralizadas do ATIUS-SRV-1."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", "/home/ubuntu/GitHub/omni-srv-admin"))
MODULE = REPO / "modules" / "srv1-ops"
SCRIPTS = MODULE / "scripts"
LOG_DIR = Path(os.environ.get("OMNI_LOG_DIR", str(Path.home() / ".logs")))

SCRIPT_MAP = {
    "sync-vault": SCRIPTS / "sync-vault.sh",
    "backup-gdrive": SCRIPTS / "backup-srv1-to-gdrive.sh",
    "offload-dotbackups": SCRIPTS / "offload-dotbackups-to-gdrive.sh",
    "cleanup-local": SCRIPTS / "cleanup-local.sh",
    "backup-smb": SCRIPTS / "backup-to-smb.sh",
    "atius-web-health": SCRIPTS / "atius-web-healthcheck.sh",
}


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> int:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(cmd, cwd=str(Path.home()), env=merged_env)
    return proc.returncode


@click.group(name="srv1-ops")
def srv1_ops() -> None:
    """Operações locais do ATIUS-SRV-1 gerenciadas pelo omni-srv-admin."""


@srv1_ops.command("list")
def list_ops() -> None:
    """Lista scripts operacionais gerenciados pelo módulo."""
    click.echo(f"module: {MODULE}")
    click.echo(f"logs:   {LOG_DIR}")
    for name, path in SCRIPT_MAP.items():
        status = "ok" if path.exists() else "missing"
        click.echo(f"{name:18} {status:8} {path}")


@srv1_ops.command("run")
@click.argument("name", type=click.Choice(sorted(SCRIPT_MAP.keys())))
@click.option("--dry-run", is_flag=True, help="Define DRY_RUN=1 quando suportado.")
def run_op(name: str, dry_run: bool) -> None:
    """Executa um script operacional por nome."""
    path = SCRIPT_MAP[name]
    if not path.exists():
        raise click.ClickException(f"script não encontrado: {path}")
    env = {"DRY_RUN": "1"} if dry_run else None
    raise SystemExit(_run([str(path)], env=env))


@srv1_ops.command("logs")
@click.option("--limit", default=20, show_default=True, help="Linhas por log.")
def logs(limit: int) -> None:
    """Mostra tail dos logs operacionais em ~/.logs."""
    if not LOG_DIR.exists():
        click.echo(f"sem diretório de logs: {LOG_DIR}")
        return
    logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        click.echo(f"sem *.log em {LOG_DIR}")
        return
    for log in logs[:8]:
        click.echo(f"\n==> {log}")
        subprocess.run(["tail", f"-{limit}", str(log)], check=False)


@srv1_ops.command("status")
def status() -> None:
    """Status rápido: timers, logs, scripts e GDrive skeleton."""
    click.echo(f"module: {MODULE} ({'ok' if MODULE.exists() else 'missing'})")
    click.echo(f"logs:   {LOG_DIR} ({'ok' if LOG_DIR.exists() else 'missing'})")
    env = os.environ.copy()
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/1001")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1001/bus")
    subprocess.run(["systemctl", "--user", "list-timers", "--all"], check=False, env=env)
