"""Omni Routine Runner - Executor Blindado com SRE Guardrails e Limitação de CPU."""
from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .routine_engine import (
    LocalLockManager,
    LockHandle,
    MultiPatternRedactor,
    RoutineDefinition,
    RoutineRun,
    RoutineState,
)


class CircuitBreakerError(Exception):
    """Lançada quando a rotina atinge o limite de falhas consecutivas e entra em cooldown."""


class RoutineRunner:
    """Executor soberano de rotinas com contenção de CPU, locks e isolamento de processo."""

    def __init__(
        self,
        logs_dir: Path | None = None,
        locks_dir: Path | None = None,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_cooldown: float = 60.0,
    ) -> None:
        if logs_dir is not None:
            self.logs_dir = Path(logs_dir)
        else:
            self.logs_dir = Path.home() / ".logs" / "routines"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.lock_mgr = LocalLockManager(locks_dir=locks_dir)
        self.redactor = MultiPatternRedactor()
        self.threshold = circuit_breaker_threshold
        self.cooldown = circuit_breaker_cooldown
        # routine_id -> {"failures": int, "tripped_until": float}
        self._circuit_breakers: dict[str, dict[str, Any]] = {}

    def _check_circuit_breaker(self, routine_id: str) -> None:
        cb = self._circuit_breakers.get(routine_id)
        if not cb:
            return
        now = time.time()
        if cb.get("failures", 0) >= self.threshold:
            tripped_until = cb.get("tripped_until", 0)
            if now < tripped_until:
                remaining = int(tripped_until - now)
                raise CircuitBreakerError(
                    f"Circuit breaker ativo para '{routine_id}': {cb['failures']} falhas consecutivas. "
                    f"Bloqueado por mais {remaining}s para evitar command storm."
                )
            else:
                # Cooldown expirou, resetar
                self._circuit_breakers[routine_id] = {"failures": 0, "tripped_until": 0}

    def _record_outcome(self, routine_id: str, success: bool) -> None:
        cb = self._circuit_breakers.setdefault(routine_id, {"failures": 0, "tripped_until": 0})
        if success:
            cb["failures"] = 0
            cb["tripped_until"] = 0
        else:
            cb["failures"] += 1
            if cb["failures"] >= self.threshold:
                cb["tripped_until"] = time.time() + self.cooldown

    def _build_system_command(
        self,
        argv: list[str],
        execution_profile: str,
        target_os: str | None = None,
    ) -> list[str]:
        current_os = (target_os or platform.system()).lower()

        # No Linux, se perfil for 'builds' ou intensivo, envelopar com cgroup/nice
        if "linux" in current_os and execution_profile == "builds":
            # Preferir systemd-run na slice de 20% CPU se disponível
            if Path("/run/systemd/system").exists():
                return [
                    "systemd-run",
                    "--user",
                    "--slice=omni-builds.slice",
                    "--scope",
                    "--",
                    "nice",
                    "-n",
                    "19",
                    *argv,
                ]
            else:
                return ["nice", "-n", "19", *argv]

        return argv

    def run(self, routine: RoutineDefinition, extra_env: dict[str, str] | None = None) -> RoutineRun:
        self._check_circuit_breaker(routine.id)

        run = RoutineRun(
            routine_id=routine.id,
            target_host=routine.target_host,
            execution_profile=routine.execution_profile,
        )

        # Adquirir lock local para evitar sobreposição
        lock = self.lock_mgr.acquire(routine.id, timeout_seconds=routine.timeout_seconds)
        if not lock:
            run.transition_to(RoutineState.SKIPPED)
            run.stderr = f"Execução ignorada: rotina '{routine.id}' já está em execução (lock ativo)."
            return run

        try:
            run.transition_to(RoutineState.RUNNING)
            cmd = self._build_system_command(routine.command_argv, routine.execution_profile)

            env = {**os.environ}
            if extra_env:
                env.update(extra_env)

            is_windows = platform.system().lower() == "windows"
            popen_kwargs: dict[str, Any] = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "env": env,
            }

            if is_windows:
                # Prevenir janela visível no Windows
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                # Isolamento de Process Group no Unix/Linux
                popen_kwargs["start_new_session"] = True

            start_t = time.time()
            try:
                proc = subprocess.Popen(cmd, **popen_kwargs)
            except (FileNotFoundError, PermissionError) as e:
                run.transition_to(RoutineState.FAILED, exit_code=127)
                run.stderr = f"[ERROR] Falha ao iniciar processo: {e}"
                run.metrics["duration_seconds"] = 0.0
                self._record_outcome(routine.id, success=False)
                self._save_run_log(run)
                return run

            try:
                stdout, stderr = proc.communicate(timeout=routine.timeout_seconds)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                # Matar todo o grupo de processos
                if is_windows:
                    proc.kill()
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                        time.sleep(0.5)
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                stdout, stderr = proc.communicate()
                exit_code = -1
                stderr = (stderr or "") + f"\n[ERROR] Timeout de {routine.timeout_seconds}s excedido."

            duration = round(time.time() - start_t, 3)
            sanitized_stdout = self.redactor.redact(stdout or "")
            sanitized_stderr = self.redactor.redact(stderr or "")

            run.stdout = sanitized_stdout
            run.stderr = sanitized_stderr
            run.metrics["duration_seconds"] = duration

            if exit_code == 0:
                run.transition_to(RoutineState.COMPLETED, exit_code=0)
                self._record_outcome(routine.id, success=True)
            else:
                run.transition_to(RoutineState.FAILED, exit_code=exit_code)
                self._record_outcome(routine.id, success=False)

            self._save_run_log(run)
            return run

        finally:
            lock.release()

    def _save_run_log(self, run: RoutineRun) -> None:
        try:
            log_file = self.logs_dir / f"{run.id}.json"
            payload = {
                "id": run.id,
                "routine_id": run.routine_id,
                "target_host": run.target_host,
                "state": run.state.value,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "exit_code": run.exit_code,
                "metrics": run.metrics,
                "stdout_tail": run.stdout[-4096:] if run.stdout else "",
                "stderr_tail": run.stderr[-4096:] if run.stderr else "",
            }
            log_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass
