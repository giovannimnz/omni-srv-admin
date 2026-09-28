"""Tests for Omni Routine SRE Diagnostics and Healing Controller."""
from __future__ import annotations

import time
from pathlib import Path
import pytest

from omni.routine_engine import RoutineRun, RoutineState
from omni.routine_diagnostics import (
    ErrorCategory,
    RoutineDiagnostics,
    AutoHealGovernor,
)


def test_classify_error_network_timeout() -> None:
    diagnostics = RoutineDiagnostics()
    run = RoutineRun(routine_id="test", target_host="srv1")
    run.transition_to(RoutineState.FAILED, exit_code=255)
    run.stderr = "ssh: connect to host 10.11.1.11 port 22: Connection timed out"

    diag = diagnostics.diagnose_run(run)
    assert diag.category == ErrorCategory.NETWORK_TIMEOUT
    assert diag.is_fatal is True
    assert "timeout" in diag.remediation_hint.lower()


def test_classify_error_binary_not_found() -> None:
    diagnostics = RoutineDiagnostics()
    run = RoutineRun(routine_id="test", target_host="srv1")
    run.transition_to(RoutineState.FAILED, exit_code=127)
    run.stderr = "sh: 1: omni: not found"

    diag = diagnostics.diagnose_run(run)
    assert diag.category == ErrorCategory.BINARY_NOT_FOUND
    assert diag.is_fatal is True
    assert "binário" in diag.remediation_hint.lower() or "caminho" in diag.remediation_hint.lower()


def test_classify_error_permission_denied() -> None:
    diagnostics = RoutineDiagnostics()
    run = RoutineRun(routine_id="test", target_host="srv1")
    run.transition_to(RoutineState.FAILED, exit_code=126)
    run.stderr = "Permission denied: /usr/local/bin/backup.sh"

    diag = diagnostics.diagnose_run(run)
    assert diag.category == ErrorCategory.PERMISSION_DENIED
    assert diag.is_fatal is True


def test_classify_error_lock_held() -> None:
    diagnostics = RoutineDiagnostics()
    run = RoutineRun(routine_id="test", target_host="srv1")
    run.transition_to(RoutineState.SKIPPED)
    run.stderr = "Execução ignorada: rotina 'test' já está em execução (lock ativo)."

    diag = diagnostics.diagnose_run(run)
    assert diag.category == ErrorCategory.LOCK_HELD
    assert diag.is_fatal is False
    assert "lock" in diag.remediation_hint.lower()


def test_classify_error_execution_timeout() -> None:
    diagnostics = RoutineDiagnostics()
    run = RoutineRun(routine_id="test", target_host="srv1")
    run.transition_to(RoutineState.FAILED, exit_code=124)
    run.stderr = "[ERROR] Timeout de 900s excedido."

    diag = diagnostics.diagnose_run(run)
    assert diag.category == ErrorCategory.EXECUTION_TIMEOUT
    assert "timeout" in diag.remediation_hint.lower()


def test_auto_heal_rate_budget_permits_up_to_3_attempts(tmp_path: Path) -> None:
    governor = AutoHealGovernor(
        state_file=tmp_path / "auto_heal.json",
        max_attempts_per_window=3,
        window_seconds=900,
        quarantine_seconds=1800,
    )

    # 3 tentativas devem ser permitidas
    for i in range(1, 4):
        decision = governor.request_remediation("srv1:backup-gdrive")
        assert decision.permitted is True
        assert decision.attempt_number == i
        governor.record_attempt("srv1:backup-gdrive")


def test_auto_heal_blocks_4th_attempt_and_quarantines(tmp_path: Path) -> None:
    governor = AutoHealGovernor(
        state_file=tmp_path / "auto_heal.json",
        max_attempts_per_window=3,
        window_seconds=900,
        quarantine_seconds=1800,
    )

    # Executar 3 tentativas
    for _ in range(3):
        governor.request_remediation("srv1:backup-gdrive")
        governor.record_attempt("srv1:backup-gdrive")

    # 4ª tentativa deve ser bloqueada
    decision = governor.request_remediation("srv1:backup-gdrive")
    assert decision.permitted is False
    assert decision.status == "BLOCKED_AUTO_HEAL"
    assert decision.quarantine_remaining_seconds > 0
    assert "quarentena" in decision.reason.lower()


def test_auto_heal_reset_on_success(tmp_path: Path) -> None:
    governor = AutoHealGovernor(
        state_file=tmp_path / "auto_heal.json",
        max_attempts_per_window=3,
        window_seconds=900,
        quarantine_seconds=1800,
    )

    governor.record_attempt("srv1:backup-gdrive")
    governor.record_attempt("srv1:backup-gdrive")

    # Sucesso na execução limpa o histórico de falhas
    governor.record_success("srv1:backup-gdrive")

    decision = governor.request_remediation("srv1:backup-gdrive")
    assert decision.permitted is True
    assert decision.attempt_number == 1
