"""Testes TDD para o Omni Routine Runner - Wave 2 SRE Guardrails."""
import os
import subprocess
import time
from pathlib import Path
import pytest

from omni.routine_engine import RoutineDefinition, RoutineRegistry, RoutineState, MultiPatternRedactor
from omni.routine_runner import RoutineRunner, CircuitBreakerError


def test_runner_executes_simple_command_successfully(tmp_path: Path):
    runner = RoutineRunner(logs_dir=tmp_path / "logs", locks_dir=tmp_path / "locks")
    routine = RoutineDefinition(
        id="test:echo",
        name="Teste Echo",
        description="Echo teste",
        target_host="local",
        command_argv=["python", "-c", "print('hello routine')"],
        execution_profile="interactive",
    )
    run = runner.run(routine)
    assert run.state == RoutineState.COMPLETED
    assert run.exit_code == 0
    assert "hello routine" in run.stdout
    assert run.finished_at is not None
    assert run.started_at is not None
    assert run.metrics.get("duration_seconds", 0) >= 0


def test_runner_enforces_cpu_quota_wrapper():
    runner = RoutineRunner()
    # Em Linux, perfil 'builds' deve envelopar com cgroup ou nice
    wrapped_cmd = runner._build_system_command(
        ["make", "build"],
        execution_profile="builds",
        target_os="linux"
    )
    wrapped_str = " ".join(wrapped_cmd)
    assert "omni-builds.slice" in wrapped_str or "nice" in wrapped_str


def test_runner_timeout_terminates_process_group(tmp_path: Path):
    runner = RoutineRunner(logs_dir=tmp_path / "logs", locks_dir=tmp_path / "locks")
    routine = RoutineDefinition(
        id="test:timeout",
        name="Teste Timeout",
        description="Comando demorado",
        target_host="local",
        # sleep 10 segundos com timeout de 1 segundo
        command_argv=["python", "-c", "import time; time.sleep(10)"],
        timeout_seconds=1,
    )
    run = runner.run(routine)
    assert run.state == RoutineState.FAILED
    assert run.exit_code == -1
    assert "timeout" in run.stderr.lower()


def test_runner_circuit_breaker_trips_after_failures(tmp_path: Path):
    runner = RoutineRunner(
        logs_dir=tmp_path / "logs",
        locks_dir=tmp_path / "locks",
        circuit_breaker_threshold=3,
        circuit_breaker_cooldown=60,
    )
    failing_routine = RoutineDefinition(
        id="test:failing",
        name="Teste Falha",
        description="Comando com erro",
        target_host="local",
        command_argv=["python", "-c", "import sys; sys.exit(42)"],
    )

    # 3 falhas consecutivas
    for _ in range(3):
        r = runner.run(failing_routine)
        assert r.state == RoutineState.FAILED

    # Na 4ª tentativa, o Circuit Breaker deve impedir a execução imediatamente
    with pytest.raises(CircuitBreakerError):
        runner.run(failing_routine)


def test_runner_sanitizes_output_before_persistence(tmp_path: Path):
    runner = RoutineRunner(logs_dir=tmp_path / "logs", locks_dir=tmp_path / "locks")
    leaking_routine = RoutineDefinition(
        id="test:leak",
        name="Teste Vazamento",
        description="Comando emitindo token",
        target_host="local",
        command_argv=["python", "-c", "print('Authorization: Bearer mysecrettoken123456789')"],
    )
    run = runner.run(leaking_routine)
    assert run.state == RoutineState.COMPLETED
    assert "mysecrettoken123456789" not in run.stdout
    assert "Bearer [REDACTED_AUTH_TOKEN]" in run.stdout
