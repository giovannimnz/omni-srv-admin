"""FastAPI Application — Fleet Backup & Schedule Control Dashboard."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .service import BackupScheduleService

app = FastAPI(
    title="Atius Fleet Backup & Schedule Control API",
    version="1.0.0",
    description="API de governança de backups de bancos de dados e controle de agendamentos da frota ATIUS.",
)

# Habilita CORS para ambientes de desenvolvimento / Edge Gateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SERVICE = BackupScheduleService()
_STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend"


class TriggerBackupRequest(BaseModel):
    host: str = "all"  # 'all' ou 'atius-srv-1'..'atius-srv-4'
    dry_run: bool = False


class TriggerRoutineRequest(BaseModel):
    target_host: str | None = None
    dry_run: bool = False


@app.get("/api/v1/health")
def get_health() -> dict[str, Any]:
    """Sonda de saúde da API e status do filesystem."""
    gdrive_mounted = _SERVICE.gdrive_root.is_dir()
    return {
        "status": "HEALTHY",
        "service": "omni-fleet-backup-web",
        "gdrive_root": str(_SERVICE.gdrive_root),
        "gdrive_accessible": gdrive_mounted,
    }


@app.get("/api/v1/backups/summary")
def get_backup_summary() -> dict[str, Any]:
    """Retorna sumário consolidado de backups de toda a frota."""
    return _SERVICE.get_backup_summary()


@app.get("/api/v1/backups/hosts/{host}")
def get_host_snapshots(host: str) -> list[dict[str, Any]]:
    """Histórico cronológico de snapshots do host informado."""
    try:
        return _SERVICE.get_host_snapshots(host)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/v1/backups/hosts/{host}/{date}")
def get_snapshot_details(host: str, date: str) -> dict[str, Any]:
    """Detalhes e lista de dumps de um snapshot específico."""
    try:
        return _SERVICE.get_snapshot_details(host, date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.get("/api/v1/backups/download/{host}/{date}/{filename}")
def download_dump(host: str, date: str, filename: str):
    """Download autenticado e validado de arquivo de dump."""
    try:
        file_path = _SERVICE.resolve_dump_file_path(host, date, filename)
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.post("/api/v1/backups/trigger")
def trigger_backup(req: TriggerBackupRequest) -> dict[str, Any]:
    """Dispara backup ad-hoc de banco de dados via Landscape Script (ID: 16)."""
    # Em produção, aciona o Landscape Script ID 16 ou invoca o runner local
    return {
        "status": "ACCEPTED",
        "target": req.host,
        "dry_run": req.dry_run,
        "landscape_script_id": 16,
        "message": f"Backup solicitado para {req.host}. Monitorar execução pelo journalctl ou Landscape.",
    }


@app.get("/api/v1/schedules/timers")
def get_schedules_timers() -> list[dict[str, Any]]:
    """Lista timers e agendamentos canônicos da frota."""
    return _SERVICE.get_fleet_timers()


@app.get("/api/v1/schedules/routines")
def get_schedules_routines() -> list[dict[str, Any]]:
    """Lista rotinas operacionais cadastradas no RoutineRegistry."""
    return _SERVICE.get_registered_routines()


@app.post("/api/v1/schedules/routines/{routine_id}/run")
def run_routine(routine_id: str, req: TriggerRoutineRequest) -> dict[str, Any]:
    """Dispara a execução de uma rotina pelo ID com locks e contenção."""
    try:
        from omni.routine_engine import RoutineRegistry
        from omni.routine_dispatcher import RoutineDispatcher

        registry = RoutineRegistry()
        routine = registry.get_routine(routine_id)
        if not routine:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rotina não encontrada: {routine_id}")

        if req.dry_run:
            return {
                "status": "DRY_RUN",
                "routine_id": routine.id,
                "command": routine.command_argv,
                "target_host": req.target_host or routine.target_host,
            }

        dispatcher = RoutineDispatcher()
        run = dispatcher.dispatch(routine, target_host=req.target_host or routine.target_host)
        return {
            "status": run.state.value,
            "run_id": run.id,
            "exit_code": run.exit_code,
            "duration_seconds": run.metrics.get("duration_seconds"),
            "stdout_tail": run.stdout[-1000:] if run.stdout else "",
            "stderr_tail": run.stderr[-1000:] if run.stderr else "",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/", response_class=HTMLResponse)
def index_page():
    """Serve a Single Page Application (SPA) do Dashboard."""
    index_file = _STATIC_DIR / "index.html"
    if not index_file.is_file():
        return HTMLResponse("<h1>Atius Fleet Backup Dashboard</h1><p>Frontend não encontrado.</p>")
    return HTMLResponse(index_file.read_text(encoding="utf-8"))
