"""Testes TDD para Omni Routine CLI e MCP Adapters - Wave 3."""
import json
from pathlib import Path
from click.testing import CliRunner
import pytest

from omni.routine import routine as routine_cmd
from omni.routine_mcp import RoutineMcpHandler


def test_cli_routine_list():
    runner = CliRunner()
    result = runner.invoke(routine_cmd, ["list"])
    assert result.exit_code == 0
    assert "srv1:backup-gdrive" in result.output
    assert "srv1:sync-vault" in result.output

    # Testar saída JSON
    result_json = runner.invoke(routine_cmd, ["list", "--json"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.output)
    assert isinstance(data, list)
    assert any(item["id"] == "srv1:backup-gdrive" for item in data)


def test_cli_routine_run_dry_run():
    runner = CliRunner()
    result = runner.invoke(routine_cmd, ["run", "srv1:backup-gdrive", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.output
    assert "srv1:backup-gdrive" in result.output


def test_cli_routine_run_apply(tmp_path: Path, monkeypatch):
    import sys
    from omni.routine_engine import RoutineDefinition, RoutineRegistry

    # Monkeypatch get_routine para retornar comando nativo multiplataforma
    orig_get = RoutineRegistry.get_routine

    def fake_get_routine(self, routine_id: str):
        r = orig_get(self, routine_id)
        if r and routine_id == "srv1:resource-audit":
            return RoutineDefinition(
                id=r.id,
                name=r.name,
                description=r.description,
                target_host=r.target_host,
                command_argv=[sys.executable, "-c", "print('audit ok')"],
                execution_profile=r.execution_profile,
                timeout_seconds=r.timeout_seconds,
            )
        return r

    monkeypatch.setattr(RoutineRegistry, "get_routine", fake_get_routine)

    runner = CliRunner()
    result = runner.invoke(
        routine_cmd,
        ["run", "srv1:resource-audit", "--apply", "--local", "--logs-dir", str(tmp_path / "logs"), "--locks-dir", str(tmp_path / "locks")]
    )
    assert result.exit_code == 0
    assert "STATUS:      COMPLETED" in result.output
    assert "audit ok" in result.output


def test_cli_routine_status(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    fake_run = {
        "id": "run-12345",
        "routine_id": "srv1:sync-vault",
        "target_host": "atius-srv-1",
        "state": "COMPLETED",
        "started_at": 1727450000.0,
        "finished_at": 1727450010.0,
        "exit_code": 0,
        "metrics": {"duration_seconds": 10.0},
        "stdout_tail": "Sync OK",
        "stderr_tail": ""
    }
    (logs_dir / "run-12345.json").write_text(json.dumps(fake_run), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(routine_cmd, ["status", "run-12345", "--logs-dir", str(logs_dir)])
    assert result.exit_code == 0
    assert "COMPLETED" in result.output
    assert "srv1:sync-vault" in result.output


def test_mcp_routine_handler_tools(tmp_path: Path):
    handler = RoutineMcpHandler(logs_dir=tmp_path / "logs", locks_dir=tmp_path / "locks")
    
    # 1. Ferramenta omni_routine_list
    list_res = handler.call_tool("omni_routine_list", {})
    assert "routines" in list_res
    assert any(r["id"] == "srv1:backup-gdrive" for r in list_res["routines"])

    # 2. Ferramenta omni_routine_trigger (dry_run)
    trigger_res = handler.call_tool("omni_routine_trigger", {"routine_id": "srv1:backup-gdrive", "dry_run": True})
    assert trigger_res["status"] == "planned"
    assert trigger_res["dry_run"] is True

    # 3. Ferramenta omni_routine_status
    (tmp_path / "logs" / "run-abc.json").write_text(
        json.dumps({"id": "run-abc", "state": "COMPLETED", "routine_id": "test"}),
        encoding="utf-8"
    )
    status_res = handler.call_tool("omni_routine_status", {"run_id": "run-abc"})
    assert status_res["state"] == "COMPLETED"


def test_cli_routine_diagnose(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(routine_cmd, ["diagnose", "srv1:backup-gdrive", "--logs-dir", str(tmp_path / "logs")])
    assert result.exit_code == 0
    assert "DIAGNÓSTICO: srv1:backup-gdrive" in result.output
    assert "Circuit Breaker: OK" in result.output
    assert "Status Auto-Cura: PERMITTED" in result.output

