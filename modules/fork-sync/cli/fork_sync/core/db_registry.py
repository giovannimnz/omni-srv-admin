"""Read-only access to DbOmniFleet customization registry."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


def _default_env_file() -> Path:
    override = os.environ.get("FORK_SYNC_DB_ENV") or os.environ.get("OMNI_FLEET_DB_ENV")
    if override:
        return Path(override)
    home = Path.home()
    candidates = [Path("/etc/omni-srv-admin/fleet-db.env"), home / ".config" / "omni-srv-admin" / "fleet-db.env"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_env() -> dict[str, str]:
    path = _default_env_file()
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


def _run_sql(query: str, *, timeout: int = 20) -> str:
    env = {**os.environ, **_load_env()}
    if shutil.which("psql"):
        import subprocess

        completed = subprocess.run(
            ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", query],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout).strip())
        return completed.stdout.strip()

    import pg8000.dbapi as pg  # type: ignore

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
        rows = cur.fetchall()
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
    finally:
        conn.close()


def registry_rows_for_project(project_name: str, host_ids: list[str] | None = None) -> list[dict[str, Any]]:
    host_filter = ""
    if host_ids:
        quoted_hosts = ", ".join("'" + host.replace("'", "''") + "'" for host in host_ids)
        host_filter = f" AND host_id IN ({quoted_hosts})"
    project_name_sql = project_name.replace("'", "''")
    output = _run_sql(
        f"""
SELECT COALESCE(jsonb_agg(
    jsonb_build_object(
        'host_id', host_id,
        'fork_id', fork_id,
        'canonical_product_id', canonical_product_id,
        'sync_project', sync_project,
        'local_path', local_path,
        'upstream_url', upstream_url,
        'sync_manifest', sync_manifest,
        'runtime_app_id', runtime_app_id,
        'managed_by', managed_by,
        'state', state,
        'metadata', metadata
    ) ORDER BY host_id, fork_id
), '[]'::jsonb)
FROM "TbManagedForks"
WHERE (
    sync_project = '{project_name_sql}'
    OR sync_manifest LIKE '%/projects/{project_name_sql}/sync.yaml'
)
{host_filter};
"""
    )
    return json.loads(output) if output else []
