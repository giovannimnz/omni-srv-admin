"""Shared fleet DB runtime helpers."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def default_fleet_db_env() -> Path:
    override = os.environ.get("OMNI_FLEET_DB_ENV")
    if override:
        return Path(override)

    home = Path.home()
    candidates: list[Path] = []
    if os.name == "nt":
        candidates.extend(
            [
                home / ".config" / "omni-srv-admin" / "fleet-db.env",
                home / "AppData" / "Local" / "omni-srv-admin" / "fleet-db.env",
            ]
        )
    candidates.extend(
        [
            Path("/etc/omni-srv-admin/fleet-db.env"),
            home / ".config" / "omni-srv-admin" / "fleet-db.env",
        ]
    )
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.R_OK):
            return candidate
    return candidates[0]


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        raise RuntimeError(f"fleet DB env não encontrado: {path}")
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def psql_available() -> bool:
    return shutil.which("psql") is not None


def run_sql(query: str, *, env: dict[str, str], timeout: int = 20) -> str:
    if psql_available():
        import subprocess

        completed = subprocess.run(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"],
            capture_output=True,
            text=True,
            input=query,
            timeout=timeout,
            env=env,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout).strip())
        return completed.stdout.strip()

    try:
        import pg8000.dbapi as pg  # type: ignore
    except ImportError as exc:  # pragma: no cover - env specific
        raise RuntimeError(
            "psql não disponível e pg8000 não instalado — configure o client PostgreSQL local"
        ) from exc

    ssl_context: bool | None = None
    if env.get("PGSSLMODE", "").lower() not in {"", "disable"}:
        ssl_context = True

    conn = pg.connect(
        user=env["PGUSER"],
        password=env.get("PGPASSWORD"),
        host=env["PGHOST"],
        port=int(env["PGPORT"]),
        database=env["PGDATABASE"],
        ssl_context=ssl_context,
        timeout=timeout,
    )
    try:
        cur = conn.cursor()
        cur.execute(query)
        if cur.description:
            rows = cur.fetchall()
            conn.commit()
            return "\n".join(
                "\t".join(
                    ""
                    if value is None
                    else json.dumps(value)
                    if isinstance(value, (dict, list))
                    else str(value)
                    for value in row
                )
                for row in rows
            )
        conn.commit()
        return ""
    finally:
        conn.close()
