"""PM2 dump persistence must not retain globally inherited secrets."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "srv1-ops" / "scripts" / "pm2-dump-sanitizer.py"
SYSTEMD = REPO / "modules" / "srv1-ops" / "systemd"


def _load():
    spec = importlib.util.spec_from_file_location("pm2_dump_sanitizer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture():
    inherited = {
        "DATABASE_URI": "postgresql://example.invalid/db",
        "GSD_WEB_LOGIN_USERNAME": "operator",
        "GSD_WEB_LOGIN_PASSWORD": "secret-value",
        "DB_PASSWORD": "db-value",
        "KEEP": "yes",
    }
    return [
        {"name": "web", "env": dict(inherited), "pm2_env": {"name": "web", "env": dict(inherited)}},
        {
            "name": "bybit-account-1002",
            "env": dict(inherited),
            "pm2_env": {"name": "bybit-account-1002", "env": dict(inherited)},
        },
    ]


def test_document_removes_global_inheritance_and_scopes_db_password() -> None:
    module = _load()
    document, removed = module.sanitize_document(_fixture())
    assert removed > 0
    for app in document:
        for container in (app, app["env"], app["pm2_env"], app["pm2_env"]["env"]):
            assert "DATABASE_URI" not in container
            assert "GSD_WEB_LOGIN_USERNAME" not in container
            assert "GSD_WEB_LOGIN_PASSWORD" not in container
            assert container.get("KEEP") in {None, "yes"}
    assert "DB_PASSWORD" not in document[0]["env"]
    assert document[1]["env"]["DB_PASSWORD"] == "db-value"


def test_file_write_is_atomic_valid_json_and_mode_0600(tmp_path: Path) -> None:
    module = _load()
    dump = tmp_path / "dump.pm2"
    dump.write_text(json.dumps(_fixture()))
    dump.chmod(0o664)
    result = module.sanitize_file(dump)
    assert result["status"] == "changed"
    assert dump.stat().st_mode & 0o777 == 0o600
    data = json.loads(dump.read_text())
    assert data[0]["env"]["KEEP"] == "yes"
    assert "GSD_WEB_LOGIN_PASSWORD" not in dump.read_text()
    second = module.sanitize_file(dump)
    assert second["status"] == "noop"


def test_systemd_path_and_timer_provide_layered_reconciliation() -> None:
    service = (SYSTEMD / "pm2-dump-sanitizer.service").read_text()
    path = (SYSTEMD / "pm2-dump-sanitizer.path").read_text()
    timer = (SYSTEMD / "pm2-dump-sanitizer.timer").read_text()
    assert "pm2-dump-sanitizer.py" in service
    assert "NoNewPrivileges=true" in service
    assert "PathChanged=%h/.pm2/dump.pm2" in path
    assert "PathChanged=%h/.pm2/dump.pm2.bak" in path
    assert "OnUnitActiveSec=1min" in timer
    assert "Persistent=true" in timer


def test_cli_sanitizes_dump_and_writes_state(tmp_path: Path) -> None:
    dump = tmp_path / "dump.pm2"
    state = tmp_path / "state.json"
    dump.write_text(json.dumps(_fixture()))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dump",
            str(dump),
            "--lock",
            str(tmp_path / "lock"),
            "--state",
            str(state),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(state.read_text())["status"] == "success"
    assert "GSD_WEB_LOGIN_PASSWORD" not in dump.read_text()
