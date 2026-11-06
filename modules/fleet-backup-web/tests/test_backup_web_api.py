"""Testes unitários e de integração para Fleet Backup & Schedule Control API."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

CLI_ROOT = Path(__file__).resolve().parents[2] / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))

import pytest
from fastapi.testclient import TestClient

from backend.app import app, _SERVICE
from backend.service import BackupScheduleService, format_bytes


@pytest.fixture
def mock_gdrive_env(tmp_path: Path):
    """Cria estrutura mock do Google Drive com snapshots simulados."""
    srv1_dir = tmp_path / "atius-srv-1" / "Backup" / "databases" / "2026-11-02"
    srv1_dir.mkdir(parents=True, exist_ok=True)

    # Cria dumps simulados
    dump1 = srv1_dir / "globals.sql.gz"
    dump1.write_bytes(b"PG_GLOBALS_SIMULATED_DATA_12345")
    dump2 = srv1_dir / "AtiusDev.dump"
    dump2.write_bytes(b"POSTGRES_ATIUS_DEV_DUMP_DATA_67890")

    # Cria SHA256SUMS
    sha_content = (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  globals.sql.gz\n"
        "ca978112ca1bbdcafac231b39a23dc4da78681f387837b002b8f4b0babd341a7  AtiusDev.dump\n"
    )
    (srv1_dir / "SHA256SUMS").write_text(sha_content, encoding="utf-8")

    # Cria manifest.json
    manifest = {
        "host": "atius-srv-1",
        "date": "2026-11-02",
        "created_at": "2026-11-02T03:30:00Z",
        "status": "SUCCESS",
        "duration_seconds": 45,
    }
    (srv1_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # Injeta no serviço global
    original_root = _SERVICE.gdrive_root
    _SERVICE.gdrive_root = tmp_path
    yield tmp_path
    _SERVICE.gdrive_root = original_root


@pytest.fixture
def client(mock_gdrive_env):
    return TestClient(app)


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert format_bytes(1024) == "1.0 KB"
    assert format_bytes(1048576) == "1.0 MB"
    assert format_bytes(1073741824) == "1.0 GB"


def test_health_endpoint(client: TestClient):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["service"] == "omni-fleet-backup-web"
    assert data["gdrive_accessible"] is True


def test_backup_summary_with_mock_data(client: TestClient):
    res = client.get("/api/v1/backups/summary")
    assert res.status_code == 200
    data = res.json()
    assert "hosts" in data
    assert "atius-srv-1" in data["hosts"]
    srv1 = data["hosts"]["atius-srv-1"]
    assert srv1["status"] == "HEALTHY"
    assert srv1["last_backup_date"] == "2026-11-02"
    assert srv1["dumps_count"] == 2
    assert len(srv1["dumps"]) == 2
    assert srv1["dumps"][0]["filename"] in {"globals.sql.gz", "AtiusDev.dump"}

    # Verifica host sem backup
    srv2 = data["hosts"]["atius-srv-2"]
    assert srv2["status"] == "NO_BACKUP"
    assert srv2["dumps_count"] == 0


def test_host_snapshots_history(client: TestClient):
    res = client.get("/api/v1/backups/hosts/atius-srv-1")
    assert res.status_code == 200
    snaps = res.json()
    assert len(snaps) == 1
    assert snaps[0]["date"] == "2026-11-02"
    assert snaps[0]["dumps_count"] == 2
    assert snaps[0]["status"] == "HEALTHY"


def test_host_snapshots_invalid_host(client: TestClient):
    res = client.get("/api/v1/backups/hosts/unknown-srv")
    assert res.status_code == 400


def test_snapshot_details(client: TestClient):
    res = client.get("/api/v1/backups/hosts/atius-srv-1/2026-11-02")
    assert res.status_code == 200
    details = res.json()
    assert details["host"] == "atius-srv-1"
    assert details["date"] == "2026-11-02"
    assert details["dumps_count"] == 2
    assert details["has_sha256sums"] is True
    assert details["manifest"]["status"] == "SUCCESS"


def test_snapshot_details_not_found(client: TestClient):
    res = client.get("/api/v1/backups/hosts/atius-srv-1/2026-10-01")
    assert res.status_code == 404


def test_download_dump_success(client: TestClient):
    res = client.get("/api/v1/backups/download/atius-srv-1/2026-11-02/globals.sql.gz")
    assert res.status_code == 200
    assert res.content == b"PG_GLOBALS_SIMULATED_DATA_12345"


def test_directory_traversal_blocked(client: TestClient):
    res = client.get("/api/v1/backups/download/atius-srv-1/2026-11-02/..%2F..%2Fetc%2Fpasswd")
    assert res.status_code in {400, 404}


def test_fleet_timers(client: TestClient):
    res = client.get("/api/v1/schedules/timers")
    assert res.status_code == 200
    timers = res.json()
    timer_ids = [t["id"] for t in timers]
    assert "omni-db-backup.timer" in timer_ids
    assert "omni-autoclean.timer" in timer_ids
    assert "omni-fleet-runtime-sync.timer" in timer_ids


def test_schedules_routines(client: TestClient):
    res = client.get("/api/v1/schedules/routines")
    assert res.status_code == 200
    routines = res.json()
    assert isinstance(routines, list)


def test_trigger_backup(client: TestClient):
    res = client.post("/api/v1/backups/trigger", json={"host": "atius-srv-1", "dry_run": True})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ACCEPTED"
    assert data["target"] == "atius-srv-1"


def test_index_page(client: TestClient):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "ATIUS FLEET" in res.text
