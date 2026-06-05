"""logrotate — rotação, compressão e retenção automática de logs.

Problema: sync gera 1 arquivo por dia/projeto. Em 6 meses: 180+ arquivos. Disco lota.

Estratégia:
- Rotação: diária (ou por tamanho > N MB)
- Compressão: gzip imediato após fechar arquivo do dia
- Retenção: manter últimos N dias (default 30) + últimos M por projeto (default 5)
- Auditoria: linha de header com timestamp + sync_id

Comportamento:
- Idempotente: pode rodar múltiplas vezes sem efeito colateral
- Seguro: nunca deleta arquivo do dia atual
- Configurável: env vars + fork-sync.yaml
"""

import gzip
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fork_sync.core.config import LOGS_DIR


# Configuração default (pode ser sobrescrita por env ou fork-sync.yaml)
DEFAULT_RETENTION_DAYS = int(os.environ.get("FORK_SYNC_LOG_RETENTION_DAYS", "30"))
DEFAULT_KEEP_PER_PROJECT = int(os.environ.get("FORK_SYNC_KEEP_PER_PROJECT", "5"))
DEFAULT_MAX_SIZE_MB = int(os.environ.get("FORK_SYNC_MAX_LOG_SIZE_MB", "50"))


def get_log_files() -> list:
    """Retorna todos os arquivos de log (.log e .log.gz), ordenados por mtime desc."""
    if not LOGS_DIR.exists():
        return []
    files = list(LOGS_DIR.glob("sync-*.log")) + list(LOGS_DIR.glob("sync-*.log.gz"))
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def parse_log_name(path: Path) -> Optional[dict]:
    """Extrai metadados do nome: sync-<project>-<YYYYMMDD>.log[.gz]"""
    import re
    m = re.match(r"sync-([^-]+(?:-[^-]+)*)-(\d{8})\.log(?:\.gz)?$", path.name)
    if not m:
        return None
    return {
        "project": m.group(1),
        "date": datetime.strptime(m.group(2), "%Y%m%d").date(),
        "compressed": path.suffix == ".gz",
    }


def compress_old_logs(dry_run: bool = False) -> list:
    """Comprime logs .log com mais de 1 dia."""
    today = datetime.now().date()
    actions = []
    for f in get_log_files():
        meta = parse_log_name(f)
        if not meta or meta["compressed"]:
            continue
        if meta["date"] >= today:
            continue
        target = f.with_suffix(f.suffix + ".gz")
        if target.exists():
            continue
        actions.append({"file": str(f), "action": "compress", "target": str(target)})
        if not dry_run:
            with open(f, "rb") as src, gzip.open(target, "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst)
            f.unlink()
    return actions


def cleanup_old_logs(retention_days: int = DEFAULT_RETENTION_DAYS,
                     keep_per_project: int = DEFAULT_KEEP_PER_PROJECT,
                     dry_run: bool = False) -> list:
    """Remove logs antigos respeitando retenção global + por projeto.

    Regras:
    - Logs dos últimos `retention_days` dias: sempre mantidos
    - Por projeto: manter pelo menos `keep_per_project` mais recentes
    - Logs do dia atual: nunca removidos
    """
    today = datetime.now().date()
    cutoff = today - timedelta(days=retention_days)

    # Indexar logs por projeto
    by_project: dict = {}
    for f in get_log_files():
        meta = parse_log_name(f)
        if not meta:
            continue
        by_project.setdefault(meta["project"], []).append((meta["date"], f))

    actions = []
    for project, entries in by_project.items():
        # Ordenar por data desc
        entries.sort(key=lambda x: x[0], reverse=True)
        # Sempre manter primeiros `keep_per_project`
        for i, (date, f) in enumerate(entries):
            if date == today:
                continue  # nunca remover hoje
            if i < keep_per_project:
                continue  # manter top N
            if date < cutoff:
                actions.append({
                    "file": str(f),
                    "project": project,
                    "date": date.isoformat(),
                    "reason": f"older than {retention_days} days and beyond top {keep_per_project}",
                    "action": "delete",
                })
                if not dry_run:
                    f.unlink()
    return actions


def check_disk_usage() -> dict:
    """Reporta uso de disco dos logs."""
    total_size = 0
    count = 0
    by_project: dict = {}
    for f in get_log_files():
        size = f.stat().st_size
        total_size += size
        count += 1
        meta = parse_log_name(f)
        if meta:
            p = meta["project"]
            by_project.setdefault(p, {"count": 0, "size": 0})
            by_project[p]["count"] += 1
            by_project[p]["size"] += size
    return {
        "total_files": count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "by_project": {k: {"count": v["count"], "size_mb": round(v["size"] / (1024 * 1024), 2)}
                       for k, v in by_project.items()},
    }


def rotate_all(dry_run: bool = False) -> dict:
    """Pipeline completo: comprimir antigos + limpar velhos."""
    compressed = compress_old_logs(dry_run=dry_run)
    deleted = cleanup_old_logs(dry_run=dry_run)
    return {
        "compressed": compressed,
        "deleted": deleted,
        "dry_run": dry_run,
        "stats": check_disk_usage(),
    }
