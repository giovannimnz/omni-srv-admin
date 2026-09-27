"""Testes TDD para o Omni Routine Engine - Wave 1 Core Contracts."""
import json
import time
from pathlib import Path
import pytest

from omni.routine_engine import (
    RoutineDefinition,
    RoutineRegistry,
    RoutineRun,
    RoutineState,
    RoutineStateError,
    LocalLockManager,
    MultiPatternRedactor,
)


def test_routine_definition_validation():
    routine = RoutineDefinition(
        id="srv1:backup-gdrive",
        name="Backup SRV-1 para GDrive",
        description="Backup operacional diário rclone para o Google Drive",
        target_host="atius-srv-1",
        command_argv=["omni", "srv1-ops", "run", "backup-gdrive"],
        execution_profile="builds",
        timeout_seconds=900,
        concurrency_policy="skip",
    )
    assert routine.id == "srv1:backup-gdrive"
    assert routine.execution_profile == "builds"
    assert routine.timeout_seconds == 900
    assert routine.concurrency_policy == "skip"


def test_routine_registry_builtins():
    registry = RoutineRegistry()
    routines = registry.list_routines()
    assert len(routines) >= 5

    # Checar se rotinas críticas da frota existem no catálogo padrão
    ids = [r.id for r in routines]
    assert "srv1:backup-gdrive" in ids
    assert "srv1:sync-vault" in ids
    assert "srv1:cleanup-local" in ids
    assert "srv1:resource-audit" in ids
    assert "fleet:pki-verify" in ids

    # Buscar por id
    r = registry.get_routine("srv1:backup-gdrive")
    assert r is not None
    assert r.target_host == "atius-srv-1"
    assert r.execution_profile == "builds"


def test_state_machine_valid_transitions():
    run = RoutineRun(
        routine_id="srv1:sync-vault",
        target_host="atius-srv-1",
        execution_profile="transfers",
    )
    assert run.state == RoutineState.PENDING
    assert run.started_at is None
    assert run.finished_at is None

    run.transition_to(RoutineState.RUNNING)
    assert run.state == RoutineState.RUNNING
    assert run.started_at is not None

    run.transition_to(RoutineState.COMPLETED, exit_code=0)
    assert run.state == RoutineState.COMPLETED
    assert run.finished_at is not None
    assert run.exit_code == 0


def test_state_machine_invalid_transition_raises():
    run = RoutineRun(
        routine_id="srv1:sync-vault",
        target_host="atius-srv-1",
        execution_profile="transfers",
    )
    # Não pode saltar de PENDING direto para COMPLETED sem RUNNING
    with pytest.raises(RoutineStateError):
        run.transition_to(RoutineState.COMPLETED)

    # Não pode transitar a partir de estado terminal
    run.transition_to(RoutineState.RUNNING)
    run.transition_to(RoutineState.FAILED, exit_code=1)
    with pytest.raises(RoutineStateError):
        run.transition_to(RoutineState.RUNNING)


def test_local_lock_manager_mutual_exclusion(tmp_path: Path):
    lock_mgr = LocalLockManager(locks_dir=tmp_path)
    routine_id = "srv1:test-routine"

    # Primeiro acquire deve ter sucesso
    handle1 = lock_mgr.acquire(routine_id, timeout_seconds=60)
    assert handle1 is not None
    assert handle1.is_active

    # Segundo acquire para a mesma rotina deve falhar
    handle2 = lock_mgr.acquire(routine_id, timeout_seconds=60)
    assert handle2 is None

    # Liberar primeiro lock
    handle1.release()
    assert not handle1.is_active

    # Agora terceiro acquire deve funcionar
    handle3 = lock_mgr.acquire(routine_id, timeout_seconds=60)
    assert handle3 is not None
    handle3.release()


def test_local_lock_manager_stale_lock_recovery(tmp_path: Path):
    lock_mgr = LocalLockManager(locks_dir=tmp_path)
    routine_id = "srv1:stale-routine"
    lock_file = tmp_path / "srv1_stale-routine.lock"

    # Criar lock expirado manualmente no passado
    stale_data = {
        "pid": 999999,
        "routine_id": routine_id,
        "acquired_at": time.time() - 300,
        "expires_at": time.time() - 100,  # já expirou há 100s
    }
    lock_file.write_text(json.dumps(stale_data), encoding="utf-8")

    # Lock manager deve detectar expiração e recuperar
    handle = lock_mgr.acquire(routine_id, timeout_seconds=60)
    assert handle is not None
    assert handle.is_active
    handle.release()


def test_multipattern_redactor():
    redactor = MultiPatternRedactor()

    # Preservar logs inofensivos mesmo contendo substring "token" ou "serial"
    harmless_log = "Serializing payload for token refresh request to endpoint /api/v1/auth"
    assert redactor.redact(harmless_log) == harmless_log

    # Mascarar Header Bearer
    auth_header_log = "Sending Authorization: Bearer abc123def456xyz789SECRETTOKEN to server"
    sanitized = redactor.redact(auth_header_log)
    assert "abc123def456xyz789SECRETTOKEN" not in sanitized
    assert "Bearer [REDACTED_AUTH_TOKEN]" in sanitized

    # Mascarar chave PEM
    pem_key = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1mZ...fakekeycontent...xyz987\n"
        "-----END RSA PRIVATE KEY-----"
    )
    pem_log = f"Loaded private key:\n{pem_key}\nReady to sign."
    sanitized_pem = redactor.redact(pem_log)
    assert "MIIEowIBAAKCAQEA" not in sanitized_pem
    assert "[REDACTED_PRIVATE_KEY]" in sanitized_pem

    # Mascarar chaves API Cloudflare / Vault
    cf_log = 'CF_GLOBAL_API_KEY="9876543210abcdef9876543210abcdef"'
    sanitized_cf = redactor.redact(cf_log)
    assert "9876543210abcdef9876543210abcdef" not in sanitized_cf
    assert "[REDACTED_SECRET]" in sanitized_cf
