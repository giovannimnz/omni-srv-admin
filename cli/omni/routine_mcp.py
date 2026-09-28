"""Omni Routine MCP Adapter - Bridge de Ferramentas para Agentes de IA."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .routine_engine import RoutineRegistry
from .routine_dispatcher import RoutineDispatcher


class RoutineMcpHandler:
    """Implementa o contrato de MCP tools para orquestração de rotinas por IA."""

    def __init__(
        self,
        logs_dir: Path | None = None,
        locks_dir: Path | None = None,
    ) -> None:
        self.registry = RoutineRegistry()
        self.dispatcher = RoutineDispatcher(logs_dir=logs_dir, locks_dir=locks_dir)
        self.runner = self.dispatcher.local_runner
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

            target_host = arguments.get("target_host") or routine.target_host
            dry_run = arguments.get("dry_run", False)
            if dry_run:
                return {
                    "routine_id": routine.id,
                    "target_host": target_host,
                    "status": "planned",
                    "dry_run": True,
                    "command_argv": routine.command_argv,
                    "execution_profile": routine.execution_profile,
                }

            run = self.dispatcher.dispatch(routine, target_host=target_host)
            return {
                "run_id": run.id,
                "routine_id": run.routine_id,
                "target_host": run.target_host,
                "state": run.state.value,
                "exit_code": run.exit_code,
                "duration_seconds": run.metrics.get("duration_seconds"),
                "route_used": run.metrics.get("route_used"),
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

        elif tool_name == "omni_routine_diagnose":
            from .routine_diagnostics import RoutineDiagnostics, AutoHealGovernor
            from .routine_engine import RoutineRun, RoutineState

            routine_id = arguments.get("routine_id")
            run_id = arguments.get("run_id")

            diagnostics = RoutineDiagnostics()
            governor = AutoHealGovernor()

            cb = self.runner._circuit_breakers.get(routine_id or "", {})
            failures = cb.get("failures", 0)
            tripped_until = cb.get("tripped_until", 0)
            now = __import__("time").time()
            is_active = failures >= self.runner.threshold and now < tripped_until

            last_run = None
            diagnosis_data = None
            if run_id:
                log_file = self.logs_dir / f"{run_id}.json"
                if log_file.exists():
                    try:
                        last_run = json.loads(log_file.read_text(encoding="utf-8"))
                        mock_run = RoutineRun(
                            routine_id=last_run.get("routine_id", routine_id or "unknown"),
                            target_host=last_run.get("target_host", "unknown"),
                            id=last_run.get("id", run_id),
                        )
                        state_val = last_run.get("state", "FAILED")
                        try:
                            mock_run.state = RoutineState(state_val)
                        except ValueError:
                            mock_run.state = RoutineState.FAILED
                        mock_run.exit_code = last_run.get("exit_code")
                        mock_run.stdout = last_run.get("stdout_tail", "")
                        mock_run.stderr = last_run.get("stderr_tail", "")
                        diag = diagnostics.diagnose_run(mock_run)
                        diagnosis_data = {
                            "category": diag.category.value,
                            "is_fatal": diag.is_fatal,
                            "remediation_hint": diag.remediation_hint,
                            "raw_summary": diag.raw_summary,
                        }
                    except Exception:
                        pass

            remediation_decision = None
            if routine_id:
                dec = governor.request_remediation(routine_id)
                remediation_decision = {
                    "permitted": dec.permitted,
                    "attempt_number": dec.attempt_number,
                    "status": dec.status,
                    "quarantine_remaining_seconds": dec.quarantine_remaining_seconds,
                    "reason": dec.reason,
                }

            return {
                "routine_id": routine_id,
                "circuit_breaker": {
                    "tripped": is_active,
                    "failures": failures,
                    "remaining_cooldown_seconds": max(0, int(tripped_until - now)) if is_active else 0,
                },
                "last_run": last_run,
                "diagnosis": diagnosis_data,
                "remediation_decision": remediation_decision,
            }

        return {"error": f"ferramenta MCP desconhecida: {tool_name}"}
