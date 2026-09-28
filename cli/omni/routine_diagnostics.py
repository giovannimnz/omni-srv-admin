"""Omni Routine SRE Diagnostics & Auto-Healing Governor."""
from __future__ import annotations

import enum
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .routine_engine import RoutineRun, RoutineState


class ErrorCategory(str, enum.Enum):
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    BINARY_NOT_FOUND = "BINARY_NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    LOCK_HELD = "LOCK_HELD"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    CIRCUIT_BREAKER_TRIPPED = "CIRCUIT_BREAKER_TRIPPED"
    GENERIC_ERROR = "GENERIC_ERROR"


@dataclass
class DiagnosticResult:
    category: ErrorCategory
    is_fatal: bool
    remediation_hint: str
    raw_summary: str


class RoutineDiagnostics:
    """Motor de análise causal de falhas operacionais."""

    def diagnose_run(self, run: RoutineRun) -> DiagnosticResult:
        stderr = (run.stderr or "").lower()
        stdout = (run.stdout or "").lower()
        combined = f"{stderr}\n{stdout}"
        exit_code = run.exit_code

        # 1. Lock ativo
        if run.state == RoutineState.SKIPPED and ("lock ativo" in combined or "já está em execução" in combined):
            return DiagnosticResult(
                category=ErrorCategory.LOCK_HELD,
                is_fatal=False,
                remediation_hint="Aguarde o lock ativo expirar ou certifique-se de que não há processo zumbi bloqueando.",
                raw_summary="Execução ignorada devido a lock ativo concorrente.",
            )

        # 2. Binário não encontrado
        if exit_code == 127 or "not found" in combined or "não é reconhecido" in combined or "no such file or directory" in combined:
            return DiagnosticResult(
                category=ErrorCategory.BINARY_NOT_FOUND,
                is_fatal=True,
                remediation_hint="Verifique se o binário ou comando está instalado e no PATH do host alvo.",
                raw_summary="Comando ou binário não localizado no host alvo.",
            )

        # 3. Permissão negada
        if exit_code == 126 or "permission denied" in combined or "acesso negado" in combined:
            return DiagnosticResult(
                category=ErrorCategory.PERMISSION_DENIED,
                is_fatal=True,
                remediation_hint="Permissão negada. Ajuste permissões chmod/chown ou verifique privilégios do usuário.",
                raw_summary="Permissão insuficiente para execução do comando.",
            )

        # 4. Timeout de execução do comando
        if exit_code == 124 or "timeout de" in combined or "timeout expired" in combined:
            return DiagnosticResult(
                category=ErrorCategory.EXECUTION_TIMEOUT,
                is_fatal=False,
                remediation_hint="Timeout de execução excedido. Verifique contenção de CPU ou expanda timeout_seconds.",
                raw_summary="A rotina demorou mais que o tempo limite configurado.",
            )

        # 5. Falha de rede / SSH
        if (
            exit_code == 255
            or "connection timed out" in combined
            or "connection refused" in combined
            or "no route to host" in combined
            or "todas as" in combined and "rotas ssh falharam" in combined
        ):
            return DiagnosticResult(
                category=ErrorCategory.NETWORK_TIMEOUT,
                is_fatal=True,
                remediation_hint="Falha de conexão ou timeout SSH/Rede. Verifique rotas WireGuard, DRG e status do host alvo.",
                raw_summary="Host alvo inalcançável por todas as rotas configuradas.",
            )

        # 6. Circuit breaker ativo
        if "circuit breaker ativo" in combined:
            return DiagnosticResult(
                category=ErrorCategory.CIRCUIT_BREAKER_TRIPPED,
                is_fatal=False,
                remediation_hint="Cooldown do circuit breaker em vigor. Aguarde o período de resfriamento anti-storm.",
                raw_summary="Execução barrada temporariamente por falhas consecutivas.",
            )

        # 7. Erro genérico
        return DiagnosticResult(
            category=ErrorCategory.GENERIC_ERROR,
            is_fatal=False,
            remediation_hint="Inspecione os logs detalhados da rotina para mais evidências.",
            raw_summary=f"Execução falhou com código de saída {exit_code}.",
        )


@dataclass
class RemediationDecision:
    permitted: bool
    attempt_number: int
    status: str  # 'PERMITTED', 'BLOCKED_AUTO_HEAL'
    quarantine_remaining_seconds: int
    reason: str


class AutoHealGovernor:
    """Governança e rate budget estrito de auto-cura para prevenir loops infinitos de agentes de IA."""

    def __init__(
        self,
        state_file: Path | None = None,
        max_attempts_per_window: int = 3,
        window_seconds: int = 900,
        quarantine_seconds: int = 1800,
    ) -> None:
        if state_file is not None:
            self.state_file = Path(state_file)
        else:
            self.state_file = Path.home() / ".local" / "state" / "omni" / "auto_heal.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        self.max_attempts = max_attempts_per_window
        self.window_seconds = window_seconds
        self.quarantine_seconds = quarantine_seconds

    def _load_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        try:
            temp_file = self.state_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
            temp_file.replace(self.state_file)
        except OSError:
            pass

    def request_remediation(self, routine_id: str) -> RemediationDecision:
        state = self._load_state()
        data = state.get(routine_id, {})
        now = time.time()

        quarantine_until = float(data.get("quarantine_until", 0))
        if now < quarantine_until:
            remaining = int(quarantine_until - now)
            return RemediationDecision(
                permitted=False,
                attempt_number=0,
                status="BLOCKED_AUTO_HEAL",
                quarantine_remaining_seconds=remaining,
                reason=f"Rotina em quarentena de auto-cura. Bloqueada por mais {remaining}s para evitar loop de IA.",
            )

        # Limpar tentativas fora da janela deslizante
        cutoff = now - self.window_seconds
        valid_attempts = [t for t in data.get("attempts", []) if t >= cutoff]

        if len(valid_attempts) >= self.max_attempts:
            # Ativa quarentena
            quarantine_until = now + self.quarantine_seconds
            data["attempts"] = valid_attempts
            data["quarantine_until"] = quarantine_until
            state[routine_id] = data
            self._save_state(state)

            return RemediationDecision(
                permitted=False,
                attempt_number=len(valid_attempts) + 1,
                status="BLOCKED_AUTO_HEAL",
                quarantine_remaining_seconds=self.quarantine_seconds,
                reason=f"Limite de auto-cura excedido ({len(valid_attempts)} tentativas em {self.window_seconds}s). Quarentena de {self.quarantine_seconds}s ativada.",
            )

        return RemediationDecision(
            permitted=True,
            attempt_number=len(valid_attempts) + 1,
            status="PERMITTED",
            quarantine_remaining_seconds=0,
            reason="Tentativa de remediação autorizada dentro do orçamento operacional.",
        )

    def record_attempt(self, routine_id: str) -> None:
        state = self._load_state()
        data = state.setdefault(routine_id, {"attempts": [], "quarantine_until": 0})
        now = time.time()
        cutoff = now - self.window_seconds
        valid_attempts = [t for t in data.get("attempts", []) if t >= cutoff]
        valid_attempts.append(now)
        data["attempts"] = valid_attempts
        self._save_state(state)

    def record_success(self, routine_id: str) -> None:
        state = self._load_state()
        if routine_id in state:
            state[routine_id] = {"attempts": [], "quarantine_until": 0}
            self._save_state(state)
