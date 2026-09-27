"""Omni Routine MCP Adapter - Bridge de Ferramentas para Agentes de IA."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .routine_engine import RoutineRegistry
from .routine_runner import RoutineRunner


class RoutineMcpHandler:
    """Implementa o contrato de MCP tools para orquestração de rotinas por IA."""

    def __init__(
        self,
        logs_dir: Path | None = None,
        locks_dir: Path | None = None,
    ) -> None:
        self.registry = RoutineRegistry()
        self.runner = RoutineRunner(logs_dir=logs_dir, locks_dir=locks_dir)
        self.logs_dir = self.runner.logs_dir

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "omni_routine_list":
            host = arguments.get("host_id")
            routines = self.registry.list_routines(host=host)
            return {
                "routines": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "description": r.description,
                        "target_host": r.target_host,
                        "execution_profile": r.execution_profile,
                        "timeout_seconds": r.timeout_seconds,
                    }
                    for r in routines
                ]
            }

        elif tool_name == "omni_routine_trigger":
            routine_id = arguments.get("routine_id")
            if not routine_id:
                return {"error": "routine_id obrigatório"}

            routine = self.registry.get_routine(routine_id)
            if not routine:
                return {"error": f"rotina não encontrada: {routine_id}"}

            dry_run = arguments.get("dry_run", False)
            if dry_run:
                return {
                    "routine_id": routine.id,
                    "target_host": routine.target_host,
                    "status": "planned",
                    "dry_run": True,
                    "command_argv": routine.command_argv,
                    "execution_profile": routine.execution_profile,
                }

            run = self.runner.run(routine)
            return {
                "run_id": run.id,
                "routine_id": run.routine_id,
                "target_host": run.target_host,
                "state": run.state.value,
                "exit_code": run.exit_code,
                "duration_seconds": run.metrics.get("duration_seconds"),
                "stdout_tail": run.stdout[-1024:] if run.stdout else "",
                "stderr_tail": run.stderr[-1024:] if run.stderr else "",
            }

        elif tool_name == "omni_routine_status":
            run_id = arguments.get("run_id")
            if not run_id:
                return {"error": "run_id obrigatório"}

            log_file = self.logs_dir / f"{run_id}.json"
            if not log_file.exists():
                return {"error": f"execução não encontrada: {run_id}"}

            try:
                data = json.loads(log_file.read_text(encoding="utf-8"))
                return data
            except Exception as e:
                return {"error": f"falha ao ler run log: {e}"}

        return {"error": f"ferramenta MCP desconhecida: {tool_name}"}
