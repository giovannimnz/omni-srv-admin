"""omni routine — CLI para gestão e disparo de rotinas operacionais."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from .routine_engine import RoutineRegistry
from .routine_runner import RoutineRunner, CircuitBreakerError


@click.group(name="routine")
def routine() -> None:
    """Gestão e execução soberana de rotinas operacionais da frota."""


@routine.command("list")
@click.option("--host", "target_host", default=None, help="Filtra rotinas por host alvo.")
@click.option("--json", "json_output", is_flag=True, help="Emite saída em JSON.")
def routine_list(target_host: str | None, json_output: bool) -> None:
    """Lista rotinas cadastradas no catálogo."""
    registry = RoutineRegistry()
    routines = registry.list_routines(host=target_host)

    if json_output:
        payload = [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "target_host": r.target_host,
                "execution_profile": r.execution_profile,
                "timeout_seconds": r.timeout_seconds,
                "command_argv": r.command_argv,
            }
            for r in routines
        ]
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    click.echo(f"{len(routines)} rotina(s) registradas:")
    click.echo(f"{'ID':24} {'HOST':14} {'PROFILE':12} {'NOME'}")
    click.echo("-" * 72)
    for r in routines:
        click.echo(f"{r.id:24} {r.target_host:14} {r.execution_profile:12} {r.name}")


@routine.command("show")
@click.argument("routine_id")
@click.option("--json", "json_output", is_flag=True, help="Emite saída em JSON.")
def routine_show(routine_id: str, json_output: bool) -> None:
    """Exibe detalhes de uma rotina específica."""
    registry = RoutineRegistry()
    r = registry.get_routine(routine_id)
    if not r:
        raise click.ClickException(f"Rotina não encontrada: {routine_id}")

    if json_output:
        payload = {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "target_host": r.target_host,
            "execution_profile": r.execution_profile,
            "timeout_seconds": r.timeout_seconds,
            "command_argv": r.command_argv,
        }
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    click.echo(f"ID:          {r.id}")
    click.echo(f"Nome:        {r.name}")
    click.echo(f"Descrição:   {r.description}")
    click.echo(f"Host:        {r.target_host}")
    click.echo(f"Perfil:      {r.execution_profile}")
    click.echo(f"Timeout:     {r.timeout_seconds}s")
    click.echo(f"Comando:     {' '.join(r.command_argv)}")


@routine.command("run")
@click.argument("routine_id")
@click.option("--apply", is_flag=True, help="Executa de fato; sem esta flag roda em dry-run.")
@click.option("--dry-run", is_flag=True, help="Modo simulação planejado.")
@click.option("--logs-dir", type=click.Path(path_type=Path), default=None, help="Diretório customizado de logs.")
@click.option("--locks-dir", type=click.Path(path_type=Path), default=None, help="Diretório customizado de locks.")
def routine_run(
    routine_id: str,
    apply: bool,
    dry_run: bool,
    logs_dir: Path | None,
    locks_dir: Path | None,
) -> None:
    """Dispara a execução de uma rotina."""
    registry = RoutineRegistry()
    r = registry.get_routine(routine_id)
    if not r:
        raise click.ClickException(f"Rotina não encontrada: {routine_id}")

    is_dry_run = not apply or dry_run
    if is_dry_run:
        click.echo(f"[DRY-RUN] Planejando execução da rotina: {r.id}")
        click.echo(f"Host:        {r.target_host}")
        click.echo(f"Perfil:      {r.execution_profile}")
        click.echo(f"Comando:     {' '.join(r.command_argv)}")
        click.echo("Use --apply para executar.")
        return

    runner = RoutineRunner(logs_dir=logs_dir, locks_dir=locks_dir)
    click.echo(f"Disparando rotina: {r.id} ({r.name})...")
    try:
        run = runner.run(r)
    except CircuitBreakerError as e:
        raise click.ClickException(str(e))

    click.echo(f"STATUS:      {run.state.value}")
    click.echo(f"RUN ID:      {run.id}")
    click.echo(f"EXIT CODE:   {run.exit_code}")
    click.echo(f"DURAÇÃO:     {run.metrics.get('duration_seconds')}s")

    if run.stdout:
        click.echo("\n--- STDOUT (tail) ---")
        click.echo(run.stdout[-1024:])
    if run.stderr:
        click.echo("\n--- STDERR (tail) ---", err=True)
        click.echo(run.stderr[-1024:], err=True)

    if run.state.value == "FAILED":
        raise SystemExit(run.exit_code if run.exit_code is not None else 1)


@routine.command("status")
@click.argument("run_id")
@click.option("--logs-dir", type=click.Path(path_type=Path), default=None, help="Diretório customizado de logs.")
def routine_status(run_id: str, logs_dir: Path | None) -> None:
    """Consulta o status e o tail de logs de uma execução anterior."""
    target_logs = logs_dir or (Path.home() / ".logs" / "routines")
    log_file = target_logs / f"{run_id}.json"
    if not log_file.exists():
        raise click.ClickException(f"Execução não encontrada em {log_file}")

    try:
        data = json.loads(log_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise click.ClickException(f"Falha ao ler log {log_file}: {e}")

    click.echo(f"RUN ID:      {data.get('id')}")
    click.echo(f"ROTINA:      {data.get('routine_id')}")
    click.echo(f"HOST:        {data.get('target_host')}")
    click.echo(f"ESTADO:      {data.get('state')}")
    click.echo(f"EXIT CODE:   {data.get('exit_code')}")
    click.echo(f"DURAÇÃO:     {data.get('metrics', {}).get('duration_seconds')}s")
    if data.get("stdout_tail"):
        click.echo("\n--- STDOUT ---")
        click.echo(data.get("stdout_tail"))
    if data.get("stderr_tail"):
        click.echo("\n--- STDERR ---")
        click.echo(data.get("stderr_tail"))
