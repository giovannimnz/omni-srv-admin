"""Fleet Backup & Schedule Control Service — Núcleo de regras de negócio."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_HOSTS = ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4"]
CENTRAL_STORAGE_HUB = "atius-srv-4"

VFS_QUOTAS = {
    "atius-srv-1": {"max_size": "3G", "max_age": "6h", "role": "Bancos de Dados Críticos (Postgres, Plane, Router AI)"},
    "atius-srv-2": {"max_size": "10G", "max_age": "24h", "role": "Servidor de Correio e Relays (Mailcow)"},
    "atius-srv-3": {"max_size": "5G", "max_age": "12h", "role": "Vault & Landscape Control-Plane"},
    "atius-srv-4": {"max_size": "30G", "max_age": "48h", "role": "K3s Cluster, Runners & Mailu"},
}

CANONICAL_TIMERS = [
    {
        "id": "omni-db-backup.timer",
        "name": "Backup Diário de Bancos de Dados",
        "schedule": "Diário às 03:30 BRT (06:30 UTC)",
        "cron": "30 3 * * *",
        "target_hosts": ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4"],
        "service_unit": "omni-db-backup.service",
        "script": "/usr/local/bin/backup-databases.sh",
        "retention_days": 14,
        "landscape_script_id": 16,
    },
    {
        "id": "omni-autoclean.timer",
        "name": "Purga e Autoclean Semanal",
        "schedule": "Semanal aos Domingos às 04:00 BRT",
        "cron": "0 4 * * 0",
        "target_hosts": ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4"],
        "service_unit": "omni-autoclean.service",
        "script": "/usr/local/bin/fleet-autoclean-and-log-purge.sh",
        "retention_days": 14,
        "landscape_script_id": 17,
    },
    {
        "id": "omni-fleet-runtime-sync.timer",
        "name": "Sincronização de Runtime da Frota",
        "schedule": "A cada 1 hora",
        "cron": "0 * * * *",
        "target_hosts": ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4"],
        "service_unit": "omni-fleet-runtime-sync.service",
        "script": "/usr/local/bin/fleet-runtime-sync.sh",
        "retention_days": 7,
        "landscape_script_id": None,
    },
    {
        "id": "rclone-fleet-queue.timer",
        "name": "Processador de Fila Rclone Multi-Server",
        "schedule": "A cada 5 minutos",
        "cron": "*/5 * * * *",
        "target_hosts": ["atius-srv-4"],
        "service_unit": "rclone-fleet-queue.service",
        "script": "/usr/local/bin/rclone-fleet-queue.sh",
        "retention_days": None,
        "landscape_script_id": None,
    },
]


def format_bytes(size: int) -> str:
    """Converte bytes para formato legível (KB, MB, GB)."""
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    s = float(size)
    while s >= 1024 and i < len(units) - 1:
        s /= 1024
        i += 1
    return f"{s:.1f} {units[i]}"


class BackupScheduleService:
    """Serviço de inspeção e governança de backups e rotinas da frota."""

    def __init__(self, gdrive_root: Path | None = None) -> None:
        if gdrive_root is not None:
            self.gdrive_root = Path(gdrive_root)
        else:
            env_root = os.environ.get("OMNI_GDRIVE_BACKUP_ROOT")
            self.gdrive_root = Path(env_root) if env_root else Path("/mnt/gdrive/ATIUS-SRV")

    def get_backup_summary(self) -> dict[str, Any]:
        """Gera sumário consolidado da frota de backups."""
        summary: dict[str, Any] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_fleet_size_bytes": 0,
            "total_fleet_size_formatted": "0 B",
            "hosts": {},
        }

        total_bytes = 0

        for host in CANONICAL_HOSTS:
            host_backup_dir = self.gdrive_root / host / "Backup" / "databases"
            host_data: dict[str, Any] = {
                "host_id": host,
                "vfs_quota": VFS_QUOTAS.get(host, {}),
                "status": "NO_BACKUP",
                "last_backup_date": None,
                "last_backup_timestamp": None,
                "latest_manifest": None,
                "total_size_bytes": 0,
                "total_size_formatted": "0 B",
                "dumps_count": 0,
                "snapshots_count": 0,
                "dumps": [],
            }

            if host_backup_dir.is_dir():
                date_dirs = [d for d in host_backup_dir.iterdir() if d.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", d.name)]
                date_dirs.sort(key=lambda d: d.name, reverse=True)
                host_data["snapshots_count"] = len(date_dirs)

                if date_dirs:
                    latest = date_dirs[0]
                    host_data["last_backup_date"] = latest.name

                    manifest_file = latest / "manifest.json"
                    dumps = []
                    snap_bytes = 0

                    if manifest_file.is_file():
                        try:
                            manifest_content = json.loads(manifest_file.read_text(encoding="utf-8"))
                            host_data["latest_manifest"] = manifest_content
                            host_data["last_backup_timestamp"] = manifest_content.get("created_at")
                            if manifest_content.get("status") == "SUCCESS":
                                host_data["status"] = "HEALTHY"
                            else:
                                host_data["status"] = "WARNING"
                        except Exception:
                            host_data["status"] = "WARNING"

                    # Enumera dumps reais na pasta da data
                    sha_map: dict[str, str] = {}
                    sha_file = latest / "SHA256SUMS"
                    if sha_file.is_file():
                        try:
                            for line in sha_file.read_text(encoding="utf-8").splitlines():
                                parts = line.strip().split(maxsplit=1)
                                if len(parts) == 2:
                                    sha_map[parts[1]] = parts[0]
                        except Exception:
                            pass

                    for f in latest.iterdir():
                        if f.is_file() and f.name not in {"manifest.json", "SHA256SUMS"}:
                            f_size = f.stat().st_size
                            snap_bytes += f_size
                            dumps.append({
                                "filename": f.name,
                                "size_bytes": f_size,
                                "size_formatted": format_bytes(f_size),
                                "sha256": sha_map.get(f.name, "N/A"),
                            })

                    dumps.sort(key=lambda x: x["size_bytes"], reverse=True)
                    host_data["dumps"] = dumps
                    host_data["dumps_count"] = len(dumps)
                    host_data["total_size_bytes"] = snap_bytes
                    host_data["total_size_formatted"] = format_bytes(snap_bytes)
                    total_bytes += snap_bytes

                    if host_data["status"] == "NO_BACKUP" and dumps:
                        host_data["status"] = "HEALTHY"

            summary["hosts"][host] = host_data

        summary["total_fleet_size_bytes"] = total_bytes
        summary["total_fleet_size_formatted"] = format_bytes(total_bytes)
        return summary

    def get_host_snapshots(self, host: str) -> list[dict[str, Any]]:
        """Lista histórico cronológico de snapshots de um host."""
        if host not in CANONICAL_HOSTS:
            raise ValueError(f"Host inválido ou desconhecido: {host}")

        host_backup_dir = self.gdrive_root / host / "Backup" / "databases"
        if not host_backup_dir.is_dir():
            return []

        snapshots: list[dict[str, Any]] = []
        date_dirs = [d for d in host_backup_dir.iterdir() if d.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", d.name)]
        date_dirs.sort(key=lambda d: d.name, reverse=True)

        for d in date_dirs:
            snap_bytes = 0
            file_count = 0
            manifest_file = d / "manifest.json"
            manifest = None
            status = "HEALTHY"

            if manifest_file.is_file():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    if manifest.get("status") != "SUCCESS":
                        status = "WARNING"
                except Exception:
                    status = "WARNING"

            for f in d.iterdir():
                if f.is_file() and f.name not in {"manifest.json", "SHA256SUMS"}:
                    snap_bytes += f.stat().st_size
                    file_count += 1

            snapshots.append({
                "date": d.name,
                "size_bytes": snap_bytes,
                "size_formatted": format_bytes(snap_bytes),
                "dumps_count": file_count,
                "status": status,
                "has_manifest": manifest is not None,
                "manifest": manifest,
            })

        return snapshots

    def get_snapshot_details(self, host: str, date: str) -> dict[str, Any]:
        """Obtém detalhes e lista completa de dumps de um snapshot específico."""
        if host not in CANONICAL_HOSTS:
            raise ValueError(f"Host inválido: {host}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise ValueError(f"Formato de data inválido: {date}")

        snapshot_dir = self.gdrive_root / host / "Backup" / "databases" / date
        if not snapshot_dir.is_dir():
            raise FileNotFoundError(f"Snapshot não encontrado para {host} na data {date}")

        sha_map: dict[str, str] = {}
        sha_file = snapshot_dir / "SHA256SUMS"
        if sha_file.is_file():
            try:
                for line in sha_file.read_text(encoding="utf-8").splitlines():
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2:
                        sha_map[parts[1]] = parts[0]
            except Exception:
                pass

        manifest = None
        manifest_file = snapshot_dir / "manifest.json"
        if manifest_file.is_file():
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        dumps = []
        total_size = 0
        for f in snapshot_dir.iterdir():
            if f.is_file() and f.name not in {"manifest.json", "SHA256SUMS"}:
                f_size = f.stat().st_size
                total_size += f_size
                dumps.append({
                    "filename": f.name,
                    "size_bytes": f_size,
                    "size_formatted": format_bytes(f_size),
                    "sha256": sha_map.get(f.name, "N/A"),
                })

        dumps.sort(key=lambda x: x["size_bytes"], reverse=True)

        return {
            "host": host,
            "date": date,
            "total_size_bytes": total_size,
            "total_size_formatted": format_bytes(total_size),
            "dumps_count": len(dumps),
            "dumps": dumps,
            "manifest": manifest,
            "has_sha256sums": sha_file.is_file(),
        }

    def resolve_dump_file_path(self, host: str, date: str, filename: str) -> Path:
        """Resolve e valida o caminho absoluto de um dump prevenindo Directory Traversal."""
        if host not in CANONICAL_HOSTS:
            raise ValueError(f"Host inválido: {host}")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise ValueError(f"Formato de data inválido: {date}")
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"Nome de arquivo suspeito: {filename}")

        target_dir = (self.gdrive_root / host / "Backup" / "databases" / date).resolve()
        file_path = (target_dir / filename).resolve()

        if not str(file_path).startswith(str(target_dir)):
            raise ValueError("Tentativa de directory traversal detectada")
        if not file_path.is_file():
            raise FileNotFoundError(f"Arquivo de dump não encontrado: {filename}")

        return file_path

    def get_fleet_timers(self) -> list[dict[str, Any]]:
        """Retorna a lista canônica de timers e agendamentos da frota."""
        return CANONICAL_TIMERS

    def get_registered_routines(self) -> list[dict[str, Any]]:
        """Retorna rotinas registradas no RoutineEngine."""
        try:
            from omni.routine_engine import RoutineRegistry
            registry = RoutineRegistry()
            routines = registry.list_routines()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "target_host": r.target_host,
                    "execution_profile": r.execution_profile,
                    "timeout_seconds": r.timeout_seconds,
                    "command_argv": r.command_argv,
                }
                for r in routines
            ]
        except Exception:
            return []
