"""Omni Routine Engine - Núcleo de Modelos, Estados, Locks e Sanitização."""
from __future__ import annotations

import enum
import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class RoutineState(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class RoutineStateError(Exception):
    """Lançada em transições de estado ilegais."""


_VALID_TRANSITIONS: dict[RoutineState, set[RoutineState]] = {
    RoutineState.PENDING: {RoutineState.QUEUED, RoutineState.RUNNING, RoutineState.SKIPPED, RoutineState.CANCELLED, RoutineState.FAILED},
    RoutineState.QUEUED: {RoutineState.CLAIMED, RoutineState.RUNNING, RoutineState.CANCELLED, RoutineState.SKIPPED},
    RoutineState.CLAIMED: {RoutineState.RUNNING, RoutineState.CANCELLED},
    RoutineState.RUNNING: {RoutineState.COMPLETED, RoutineState.FAILED, RoutineState.CANCELLED},
    # Estados terminais
    RoutineState.COMPLETED: set(),
    RoutineState.FAILED: set(),
    RoutineState.CANCELLED: set(),
    RoutineState.SKIPPED: set(),
}


@dataclass
class RoutineDefinition:
    id: str
    name: str
    description: str
    target_host: str
    command_argv: list[str]
    execution_profile: str = "interactive"  # 'builds', 'transfers', 'interactive'
    timeout_seconds: int = 900
    concurrency_policy: str = "skip"  # 'skip', 'queue', 'replace'
    max_retries: int = 0
    retry_delay_seconds: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutineRun:
    routine_id: str
    target_host: str
    execution_profile: str = "interactive"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: RoutineState = RoutineState.PENDING
    started_at: float | None = None
    finished_at: float | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    attempt_count: int = 0

    def transition_to(self, new_state: RoutineState, exit_code: int | None = None) -> None:
        allowed = _VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise RoutineStateError(
                f"Transição de estado inválida: {self.state.value} -> {new_state.value}"
            )
        now = time.time()
        if new_state == RoutineState.RUNNING and self.started_at is None:
            self.started_at = now
        elif new_state in {RoutineState.COMPLETED, RoutineState.FAILED, RoutineState.CANCELLED, RoutineState.SKIPPED}:
            self.finished_at = now
            if exit_code is not None:
                self.exit_code = exit_code

        self.state = new_state


@dataclass
class LockHandle:
    routine_id: str
    lock_path: Path
    expires_at: float
    is_active: bool = True

    def release(self) -> None:
        if not self.is_active:
            return
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
        except OSError:
            pass
        finally:
            self.is_active = False


class LocalLockManager:
    """Gerenciador de exclusão mútua local com suporte a timeout e expiração atômica."""

    def __init__(self, locks_dir: Path | None = None) -> None:
        if locks_dir is not None:
            self.locks_dir = Path(locks_dir)
        else:
            self.locks_dir = Path.home() / ".local" / "state" / "omni" / "locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    def _lock_file_path(self, routine_id: str) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", routine_id)
        return self.locks_dir / f"{safe_name}.lock"

    def acquire(self, routine_id: str, timeout_seconds: int = 900) -> LockHandle | None:
        lock_file = self._lock_file_path(routine_id)
        now = time.time()
        expires_at = now + timeout_seconds

        # Se o arquivo já existe, verificar se está expirado (stale)
        if lock_file.exists():
            try:
                data = json.loads(lock_file.read_text(encoding="utf-8"))
                file_expires = float(data.get("expires_at", 0))
                if now < file_expires:
                    # Lock ainda válido e ativo por outro processo
                    return None
            except Exception:
                # Arquivo corrompido, tratar como stale
                pass

        # Gravar lock atomicamente
        lock_payload = {
            "pid": os.getpid(),
            "routine_id": routine_id,
            "acquired_at": now,
            "expires_at": expires_at,
        }
        try:
            temp_file = lock_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(lock_payload), encoding="utf-8")
            temp_file.replace(lock_file)
            return LockHandle(routine_id=routine_id, lock_path=lock_file, expires_at=expires_at)
        except OSError:
            return None


class MultiPatternRedactor:
    """Sanitizador determinístico de segredos, preservando logs operacionais normais."""

    PEM_PATTERN = re.compile(
        r"-----BEGIN[ A-Z_-]+KEY-----[\s\S]+?-----END[ A-Z_-]+KEY-----"
    )
    BEARER_PATTERN = re.compile(
        r"(?i)\b(bearer)\s+([a-zA-Z0-9_\-\.]{16,})\b"
    )
    SECRET_ASSIGN_PATTERN = re.compile(
        r'(?i)\b(CF_GLOBAL_API_KEY|ATIUS_MCP_TOKEN|PGPASSWORD|API_KEY|SECRET_KEY|PASSWORD)\s*([:=])\s*(["\']?)([^"\'\s]{8,})\3'
    )

    def redact(self, text: str) -> str:
        if not text:
            return text

        # 1. Chaves privadas PEM
        sanitized = self.PEM_PATTERN.sub("[REDACTED_PRIVATE_KEY]", text)

        # 2. Authorization Bearer
        sanitized = self.BEARER_PATTERN.sub(r"\1 [REDACTED_AUTH_TOKEN]", sanitized)

        # 3. Atribuições de chaves/senhas
        sanitized = self.SECRET_ASSIGN_PATTERN.sub(r"\1\2\3[REDACTED_SECRET]\3", sanitized)

        return sanitized


class RoutineRegistry:
    """Catálogo centralizado de rotinas conhecidas da frota ATIUS."""

    def __init__(self) -> None:
        self._routines: dict[str, RoutineDefinition] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        builtins = [
            RoutineDefinition(
                id="srv1:backup-gdrive",
                name="Backup SRV-1 para GDrive",
                description="Backup rclone diário do ATIUS-SRV-1 para o Google Drive com verificação",
                target_host="atius-srv-1",
                command_argv=["omni", "srv1-ops", "run", "backup-gdrive"],
                execution_profile="builds",
                timeout_seconds=1800,
            ),
            RoutineDefinition(
                id="srv1:sync-vault",
                name="Sincronização Obsidian & GBrain",
                description="Sincroniza git do Obsidian vault AiSecondBrain e dump incremental do GBrain",
                target_host="atius-srv-1",
                command_argv=["omni", "srv1-ops", "run", "sync-vault"],
                execution_profile="transfers",
                timeout_seconds=300,
            ),
            RoutineDefinition(
                id="srv1:cleanup-local",
                name="Cleanup Semanal e Retenção",
                description="Purga caches obsoletos e impõe retenção de 15 dias em ~/.logs",
                target_host="atius-srv-1",
                command_argv=["omni", "srv1-ops", "run", "cleanup-local"],
                execution_profile="interactive",
                timeout_seconds=600,
            ),
            RoutineDefinition(
                id="srv1:resource-audit",
                name="Auditoria de Recursos e CPU",
                description="Audita limites de cgroups, hotspots de build e integridade do resource governor",
                target_host="atius-srv-1",
                command_argv=["omni", "srv1-ops", "resources", "audit"],
                execution_profile="interactive",
                timeout_seconds=300,
            ),
            RoutineDefinition(
                id="fleet:pki-verify",
                name="Verificação de Certificados PKI",
                description="Verifica validade e SANs dos certificados TLS internos na frota",
                target_host="atius-srv-1",
                command_argv=["omni", "fleet", "trust-pki", "verify", "--host", "atius-srv-1"],
                execution_profile="interactive",
                timeout_seconds=300,
            ),
        ]
        for b in builtins:
            self.register(b)

    def register(self, routine: RoutineDefinition) -> None:
        self._routines[routine.id] = routine

    def get_routine(self, routine_id: str) -> RoutineDefinition | None:
        return self._routines.get(routine_id)

    def list_routines(self, host: str | None = None) -> list[RoutineDefinition]:
        routines = list(self._routines.values())
        if host:
            routines = [r for r in routines if r.target_host == host]
        return routines
