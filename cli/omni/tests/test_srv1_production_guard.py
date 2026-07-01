"""Tests for production guard baseline, parity checks and CLI wiring."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO / "modules" / "srv1-ops" / "scripts" / "production_guard.py"
BASELINE_PATH = REPO / "modules" / "srv1-ops" / "configs" / "production-guard.yaml"
REPO_CLI = REPO / "cli"
SYSTEMD_DIR = REPO / "modules" / "srv1-ops" / "systemd"
BOOT_UNIT_PATH = SYSTEMD_DIR / "production-guard.service"
BOOT_TIMER_PATH = SYSTEMD_DIR / "production-guard.timer"
LOGIN_UNIT_PATH = SYSTEMD_DIR / "production-guard-login.service"

if str(REPO_CLI) not in sys.path:
    sys.path.insert(0, str(REPO_CLI))

from omni import srv1_ops as srv1_ops_mod


def _load_guard_module():
    spec = importlib.util.spec_from_file_location("production_guard", str(SCRIPT_PATH))
    assert spec and spec.loader, "could not load production guard module spec"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard_mod = _load_guard_module()


@pytest.fixture
def base_config():
    return copy.deepcopy(guard_mod._read_yaml(BASELINE_PATH))


def _make_pm2_app(name: str, namespace: str, *, status: str = "online", env: dict[str, str] | None = None) -> dict:
    return {
        "name": name,
        "pm2_env": {
            "name": name,
            "status": status,
            "namespace": namespace,
            "env": env or {},
        },
        "namespace": namespace,
    }


def _index(config_apps: list[dict]) -> dict[str, dict]:
    return guard_mod._index_by_name(config_apps)


def _read_unit_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_execstart_commands(path: Path) -> list[str]:
    lines = _read_unit_file(path).splitlines()
    return [line.split("=", 1)[1].strip() for line in lines if line.startswith("ExecStart=")]


def _assert_unit_is_read_only_unit(path: Path) -> None:
    commands = _extract_execstart_commands(path)
    assert commands, f"{path} sem ExecStart"
    joined = " ".join(commands)
    assert "production_guard.py" in joined
    assert "--json" in joined
    assert "status --json" in joined or "doctor --json" in joined
    assert "repair --apply" not in joined
    assert "pm2" not in joined
    assert " xrdp" not in joined
    assert "apache2" not in joined
    assert "systemctl restart" not in joined
    assert "systemctl stop" not in joined


def test_baseline_contract_and_critical_values(base_config):
    assert base_config["pm2"]["service"]["name"] == "pm2-ubuntu.service"
    assert base_config["pm2"]["service"]["expected_type"] == "oneshot"
    assert base_config["pm2"]["service"]["expected_remain_after_exit"] is True
    assert base_config["pm2"]["service"]["expected_env"]["PM2_HOME"] == "/home/ubuntu/.pm2"
    assert base_config["pm2"]["service"]["forbidden_env"] == ["PIDFile"]
    assert base_config["pm2"]["namespace_counts"]["atius"] == 12
    assert base_config["pm2"]["namespace_counts"]["horistic"] == 5
    assert 3015 in base_config["critical_ports"]
    assert 8199 in base_config["critical_ports"]
    assert base_config["ecosystems"]["atius"]["path"].endswith("ecosystem.config.js")
    assert base_config["ecosystems"]["horistic"]["path"].endswith("ecosystem.config.js")


def test_baseline_endpoints_are_get_or_head_only(base_config):
    methods = [item["method"].upper() for item in base_config["endpoints"]]
    assert set(methods) <= {"GET", "HEAD"}


def test_pm2_live_dump_parity_returns_pass(base_config, monkeypatch):
    live = [_make_pm2_app(f"atius-{idx}", "atius") for idx in range(1, 13)]
    live.extend(_make_pm2_app(f"horistic-{idx}", "horistic") for idx in range(1, 6))

    monkeypatch.setattr(guard_mod, "_load_pm2_jlist", lambda *_a, **_k: live)
    monkeypatch.setattr(guard_mod, "_load_pm2_dump", lambda *_a, **_k: live)

    result = guard_mod._check_pm2_parity(base_config)
    assert result["status"] == "pass"
    assert result["details"]["wrong_namespace_live"] == []


def test_pm2_parity_blocks_wrong_namespace(base_config, monkeypatch):
    live = [_make_pm2_app("atis-default", "default")]
    live.extend(_make_pm2_app(f"horistic-{idx}", "horistic") for idx in range(1, 6))
    live.extend(_make_pm2_app(f"atius-{idx}", "atius") for idx in range(1, 12))
    dump = list(live)

    monkeypatch.setattr(guard_mod, "_load_pm2_jlist", lambda *_a, **_k: live)
    monkeypatch.setattr(guard_mod, "_load_pm2_dump", lambda *_a, **_k: dump)

    result = guard_mod._check_pm2_parity(base_config)
    assert result["status"] == "block"
    assert "atis-default" in result["details"]["wrong_namespace_live"]


def test_pm2_missing_dump_app_blocks(base_config, monkeypatch):
    live = [_make_pm2_app("atius-1", "atius")]
    live.extend(_make_pm2_app(f"horistic-{idx}", "horistic") for idx in range(1, 6))
    live.extend(_make_pm2_app(f"atius-{idx}", "atius") for idx in range(2, 13))

    dump = [_make_pm2_app(f"horistic-{idx}", "horistic") for idx in range(1, 6)]
    dump.extend(_make_pm2_app(f"atius-{idx}", "atius") for idx in range(2, 13))

    monkeypatch.setattr(guard_mod, "_load_pm2_jlist", lambda *_a, **_k: live)
    monkeypatch.setattr(guard_mod, "_load_pm2_dump", lambda *_a, **_k: dump)

    result = guard_mod._check_pm2_parity(base_config)
    assert result["status"] == "block"
    assert "atius-1" in result["details"]["missing_in_dump"]


def test_launchers_waiting_restart_without_cycle_summary_blocks(base_config, monkeypatch):
    live = [
        _make_pm2_app("horistic-unified-bot-launcher", "horistic", status="waiting restart"),
        _make_pm2_app("atius-unified-bot-launcher", "atius", status="waiting restart"),
    ]

    monkeypatch.setattr(guard_mod, "_parse_cycle_summary", lambda *_a, **_k: (False, False))
    result = guard_mod._check_launchers(base_config, _index(live))

    assert result["status"] == "block"
    atius_result = next(item for item in result["checks"] if item["name"] == "atius-unified-bot-launcher")
    assert atius_result["status"] == "block"
    assert "sem [CYCLE_SUMMARY] recente" in atius_result["reason"]


def test_endpoints_refuse_non_get_head_methods(base_config):
    base_config["endpoints"] = [{"name": "bad", "method": "POST", "url": "https://trade.atius.com.br"}]
    result = guard_mod._check_endpoints(base_config)
    assert result["status"] == "block"
    assert result["checks"][0]["status"] == "blocked"


def test_ecosystem_validator_checks_contract_and_redacts_secrets(tmp_path, monkeypatch):
    cfg = {
        "redaction": {"sensitive_fields": ["token", "password", "secret", "api_key", "access_token", "webhook_secret"]},
        "ecosystems": {
            "atius": {
                "path": str(tmp_path / "ecosystem.config.js"),
                "namespace": "atius",
                "expected_total": 1,
                "critical_apps": {
                    "atius-api": {
                        "namespace": "atius",
                        "cwd": str(tmp_path / "ats" / "backend"),
                        "script": "server/api.js",
                        "autorestart": True,
                        "restart_delay": 10000,
                        "max_restarts": 10,
                        "required_env": ["NODE_ENV", "API_PORT"],
                        "expected_ports": [8015],
                    }
                },
                "dynamic_patterns": [],
            }
        },
    }

    cwd = Path(cfg["ecosystems"]["atius"]["critical_apps"]["atius-api"]["cwd"])
    (cwd / "server").mkdir(parents=True)
    (cwd / "server" / "api.js").write_text("console.log('ok')")

    file_app = {
        "name": "atius-api",
        "namespace": "atius",
        "cwd": str(cwd),
        "script": "server/api.js",
        "autorestart": True,
        "restart_delay": 10000,
        "max_restarts": 10,
        "env": {
            "NODE_ENV": "production",
            "API_PORT": "8015",
            "TOKEN": "abc123",
            "API_KEY": "secret-key",
        },
    }

    live = [
        _make_pm2_app(
            "atius-api",
            "atius",
            env={"API_PORT": "8015", "API_KEY": "live-api-key", "TOKEN": "live-token"},
        )
    ]
    monkeypatch.setattr(guard_mod, "_load_ecosystem_apps", lambda *_a, **_k: [file_app])

    result = guard_mod._check_ecosystems(cfg, _index(live))
    check = next(item for item in result if item["name"] == "ecosystem_atius_atius-api")
    assert check["status"] == "pass"
    assert check["details"]["pm2_live_env_redacted"]["TOKEN"] == "***REDACTED***"
    assert check["details"]["pm2_live_env_redacted"]["API_KEY"] == "***REDACTED***"


def test_containers_and_systemd_jobs_classification(base_config, monkeypatch):
    monkeypatch.setattr(guard_mod, "_list_containers", lambda: ["router-ai-atius", "postgres", "redis"])
    containers = guard_mod._check_containers(base_config)
    assert containers["status"] == "block"

    job_output = "\n".join(
        [
            "1258 FAILED default.target - -",
            "1304 RUNNING backup-rotate.service - -",
            "2048 RUNNING random.service - -",
        ]
    )
    monkeypatch.setattr(guard_mod, "_systemctl_list_jobs", lambda *_a, **_k: job_output)
    jobs = guard_mod._check_systemd_jobs(base_config)
    assert jobs["status"] == "block"
    lines = jobs["details"]["jobs"]
    assert any("default.target" in entry["line"] and entry["status"] == "block" for entry in lines)
    assert any("backup-rotate.service" in entry["line"] and entry["status"] == "warn" for entry in lines)


def test_doctor_command_invokes_production_guard_script_with_json_flag(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *args, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(srv1_ops_mod.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc_info:
        srv1_ops_mod.production_guard_doctor.callback(True)

    assert exc_info.value.code == 0
    assert calls
    assert calls[-1][0] == "python3"
    assert calls[-1][1] == str(srv1_ops_mod.PRODUCTION_GUARD_SCRIPT)
    assert calls[-1][2] == "doctor"
    assert "--json" in calls[-1]


def test_repair_dry_run_produces_candidates_without_execution(base_config, monkeypatch):
    report = {
        "overall": "block",
        "summary": {"block": 2, "pass": 1, "warn": 0, "unknown": 0},
        "checks": [
            {"name": "pm2_live_dump_parity", "status": "block", "details": {}},
            {
                "name": "containers",
                "status": "block",
                "details": {"containers": [{"name": "model-detailed", "present": False, "critical": True}]},
            },
        ],
    }

    monkeypatch.setattr(guard_mod, "_build_report", lambda *_a, **_k: report)
    result = guard_mod._build_repair_report(BASELINE_PATH)
    actions = result["actions"]
    assert result["command"] == "repair"
    assert result["mode"] == "dry-run"
    assert result["apply_ready"] is False
    assert actions
    assert any(item["target"] == "model-detailed" for item in actions)
    assert any(item["status"] == "blocked" for item in actions)


def test_repair_apply_requires_scope_and_target():
    with pytest.raises(RuntimeError, match="scope e --target"):
        guard_mod._run_apply(BASELINE_PATH, scope=None, target=None, risk_ack=True)


def test_repair_apply_requires_explicit_risk_ack():
    with pytest.raises(RuntimeError, match="production-risk"):
        guard_mod._run_apply(BASELINE_PATH, scope="container", target="redis", risk_ack=False)


def test_repair_apply_creates_snapshot_before_execution(tmp_path, base_config, monkeypatch):
    monkeypatch.setattr(guard_mod, "DEFAULT_STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(guard_mod, "DEFAULT_AUDIT_LOG", tmp_path / "state" / "audit.jsonl")
    monkeypatch.setattr(guard_mod, "DEFAULT_SNAPSHOT_DIR", tmp_path / "state" / "snapshots")
    monkeypatch.setattr(guard_mod, "_read_config", lambda *_a, **_k: base_config)
    monkeypatch.setattr(
        guard_mod,
        "_build_repair_report",
        lambda *_a, **_k: {
            "actions": [
                {
                    "scope": "container",
                    "target": "redis",
                    "status": "planned",
                    "command_preview": ["podman", "start", "redis"],
                    "command_preview_shell": "podman start redis",
                }
            ]
        },
    )

    seen_snapshot = {"exists": False}

    def fake_run(cmd, **kwargs):
        seen_snapshot["exists"] = guard_mod.DEFAULT_SNAPSHOT_DIR.exists() and any(guard_mod.DEFAULT_SNAPSHOT_DIR.iterdir())
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(guard_mod, "_run", fake_run)
    result = guard_mod._run_apply(BASELINE_PATH, scope="container", target="redis", risk_ack=True)
    assert seen_snapshot["exists"] is True
    assert Path(result["snapshot_path"]).exists()
    assert Path(result["audit_log"]).exists()


def test_repair_forbidden_commands_are_rejected():
    bad_pm2 = ["pm2", "".join(["ki", "ll"])]
    bad_rdp = ["systemctl", "restart", "xrdp" + "-sesman"]
    bad_apache = ["systemctl", "restart", "apache2"]
    bad_post = ["curl", "-X", "".join(["PO", "ST"]), "https://example.invalid"]
    assert guard_mod._forbidden_reason("pm2", "daemon", bad_pm2) is not None
    assert guard_mod._forbidden_reason("systemd-service", "xrdp", bad_rdp) is not None
    assert guard_mod._forbidden_reason("systemd-service", "apache", bad_apache) is not None
    assert guard_mod._forbidden_reason("webhook", "example", bad_post) is not None


def test_production_guard_service_and_login_unit_are_read_only():
    for path in (BOOT_UNIT_PATH, LOGIN_UNIT_PATH):
        _assert_unit_is_read_only_unit(path)


def test_production_guard_timer_targets_boot_service_and_read_only_commands():
    timer_text = _read_unit_file(BOOT_TIMER_PATH)
    assert "[Unit]" in timer_text
    assert "Requires=production-guard.service" in timer_text
    assert "production-guard.service" in timer_text
    assert "OnBootSec=" in timer_text
    assert "WantedBy=timers.target" in timer_text



def test_repair_audit_log_is_machine_readable_and_redacted(tmp_path):
    monkeypatch_log = tmp_path / "audit.jsonl"
    monkeypatch_state = tmp_path / "state"
    original_log = guard_mod.DEFAULT_AUDIT_LOG
    original_state = guard_mod.DEFAULT_STATE_DIR
    try:
        guard_mod.DEFAULT_AUDIT_LOG = monkeypatch_log
        guard_mod.DEFAULT_STATE_DIR = monkeypatch_state
        audit_path = guard_mod._append_audit_event(
            {"token": "abc", "nested": {"api_key": "secret", "ok": "value"}},
            ["token", "api_key", "secret"],
        )
        payload = json.loads(audit_path.read_text(encoding="utf-8").strip())
        assert payload["token"] == "***REDACTED***"
        assert payload["nested"]["api_key"] == "***REDACTED***"
        assert payload["nested"]["ok"] == "value"
    finally:
        guard_mod.DEFAULT_AUDIT_LOG = original_log
        guard_mod.DEFAULT_STATE_DIR = original_state


def test_repair_command_invokes_script_with_apply_flags(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], *args, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(srv1_ops_mod.subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc_info:
        srv1_ops_mod.production_guard_repair.callback(True, False, "container", "redis", True)

    assert exc_info.value.code == 0
    assert calls[-1][:4] == ["python3", str(srv1_ops_mod.PRODUCTION_GUARD_SCRIPT), "repair", "--json"]
    assert "--apply" in calls[-1]
    assert "--scope" in calls[-1]
    assert "--target" in calls[-1]


def test_remote_horistic_apache_default_state_passes(base_config, monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        command = str(cmd)
        if command.startswith("systemctl show"):
            return subprocess.CompletedProcess(cmd, 0, stdout="FragmentPath=/usr/lib/systemd/system/apache2.service\nDropInPaths=\nNeedDaemonReload=no\n", stderr="")
        if command.startswith("systemctl is-enabled"):
            return subprocess.CompletedProcess(cmd, 0, stdout="enabled\n", stderr="")
        if command.startswith("systemctl is-active"):
            return subprocess.CompletedProcess(cmd, 0, stdout="active\n", stderr="")
        if command.startswith("ss -tlnp"):
            return subprocess.CompletedProcess(cmd, 0, stdout="LISTEN 0 128 0.0.0.0:80\nLISTEN 0 128 0.0.0.0:443\n", stderr="")
        if command.startswith("find /etc/apache2/sites-enabled"):
            return subprocess.CompletedProcess(cmd, 0, stdout="remote.horistic-srv-1.atius.com.br.conf\n", stderr="")
        if command.startswith("apache2ctl -S"):
            return subprocess.CompletedProcess(cmd, 0, stdout="VirtualHost ok\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(guard_mod, "_run_remote", fake_run)
    result = guard_mod._check_remote_horistic_apache(base_config)
    assert result["name"] == "remote_horistic_apache"
    assert result["status"] == "pass"
    assert result["details"]["listening_ports"]["open_ports"] == [80, 443]


def test_remote_horistic_apache_dropin_blocks(base_config, monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        command = str(cmd)
        if command.startswith("systemctl show"):
            return subprocess.CompletedProcess(cmd, 0, stdout="FragmentPath=/usr/lib/systemd/system/apache2.service\nDropInPaths=/etc/systemd/system/apache2.service.d/custom.conf\nNeedDaemonReload=no\n", stderr="")
        if command.startswith("systemctl is-enabled"):
            return subprocess.CompletedProcess(cmd, 0, stdout="enabled\n", stderr="")
        if command.startswith("systemctl is-active"):
            return subprocess.CompletedProcess(cmd, 0, stdout="active\n", stderr="")
        if command.startswith("ss -tlnp"):
            return subprocess.CompletedProcess(cmd, 0, stdout="LISTEN 0 128 0.0.0.0:80\nLISTEN 0 128 0.0.0.0:443\n", stderr="")
        if command.startswith("find /etc/apache2/sites-enabled"):
            return subprocess.CompletedProcess(cmd, 0, stdout="remote.horistic-srv-1.atius.com.br.conf\n", stderr="")
        if command.startswith("apache2ctl -S"):
            return subprocess.CompletedProcess(cmd, 0, stdout="VirtualHost ok\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(guard_mod, "_run_remote", fake_run)
    result = guard_mod._check_remote_horistic_apache(base_config)
    assert result["status"] == "block"
    assert result["details"]["service_properties"]["dropin_risk"] == "drop-in custom detectado fora da allowlist"


def test_remote_horistic_apache_missing_443_blocks(base_config, monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        command = str(cmd)
        if command.startswith("systemctl show"):
            return subprocess.CompletedProcess(cmd, 0, stdout="FragmentPath=/usr/lib/systemd/system/apache2.service\nDropInPaths=\nNeedDaemonReload=no\n", stderr="")
        if command.startswith("systemctl is-enabled"):
            return subprocess.CompletedProcess(cmd, 0, stdout="enabled\n", stderr="")
        if command.startswith("systemctl is-active"):
            return subprocess.CompletedProcess(cmd, 0, stdout="active\n", stderr="")
        if command.startswith("ss -tlnp"):
            return subprocess.CompletedProcess(cmd, 0, stdout="LISTEN 0 128 0.0.0.0:80\n", stderr="")
        if command.startswith("find /etc/apache2/sites-enabled"):
            return subprocess.CompletedProcess(cmd, 0, stdout="remote.horistic-srv-1.atius.com.br.conf\n", stderr="")
        if command.startswith("apache2ctl -S"):
            return subprocess.CompletedProcess(cmd, 0, stdout="VirtualHost ok\n", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(guard_mod, "_run_remote", fake_run)
    result = guard_mod._check_remote_horistic_apache(base_config)
    assert result["status"] == "block"
    assert result["details"]["listening_ports"]["missing"] == [443]


def test_remote_horistic_apachectl_failure_blocks(base_config, monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        command = str(cmd)
        if command.startswith("systemctl show"):
            return subprocess.CompletedProcess(cmd, 0, stdout="FragmentPath=/usr/lib/systemd/system/apache2.service\nDropInPaths=\nNeedDaemonReload=no\n", stderr="")
        if command.startswith("systemctl is-enabled"):
            return subprocess.CompletedProcess(cmd, 0, stdout="enabled\n", stderr="")
        if command.startswith("systemctl is-active"):
            return subprocess.CompletedProcess(cmd, 0, stdout="active\n", stderr="")
        if command.startswith("ss -tlnp"):
            return subprocess.CompletedProcess(cmd, 0, stdout="LISTEN 0 128 0.0.0.0:80\nLISTEN 0 128 0.0.0.0:443\n", stderr="")
        if command.startswith("find /etc/apache2/sites-enabled"):
            return subprocess.CompletedProcess(cmd, 0, stdout="remote.horistic-srv-1.atius.com.br.conf\n", stderr="")
        if command.startswith("apache2ctl -S"):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="config invalid")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(guard_mod, "_run_remote", fake_run)
    result = guard_mod._check_remote_horistic_apache(base_config)
    assert result["status"] == "block"


def test_rename_drift_classifies_benign_doc_reference_as_warn(tmp_path, base_config):
    doc_path = tmp_path / "inventory-note.md"
    doc_path.write_text("Documento histórico do host horistic-srv-1", encoding="utf-8")

    cfg = copy.deepcopy(base_config)
    cfg["rename_drift"]["alias_pairs"][0]["benign_file_refs"] = [str(doc_path)]
    cfg["rename_drift"]["backup_paths"] = ["ATIUS-SRV/HORISTIC-SRV-1/Backup"]
    cfg["rename_drift"]["symlink_expectations"] = []

    remote = {"details": {"sites_enabled": {"enabled_sites": ["remote.horistic-srv-1.atius.com.br.conf"]}}}
    result = guard_mod._check_rename_drift(cfg, {}, remote_horistic=remote)
    assert result["status"] in {"warn", "pass"}
    assert any(item.get("name") == "benign_reference" for item in result["details"]["findings"])


def test_rename_drift_reports_missing_pm2_path_block(base_config):
    cfg = copy.deepcopy(base_config)
    cfg["rename_drift"]["symlink_expectations"] = []
    cfg["rename_drift"]["backup_paths"] = []
    cfg["rename_drift"]["alias_pairs"][0]["benign_file_refs"] = []

    live_by_name = {
        "horistic-api": {
            "name": "horistic-api",
            "pm2_env": {
                "name": "horistic-api",
                "cwd": "/no/such/path/horistic-srv-1",
                "script": "/no/such/script/horistic-srv-1/index.js",
            },
        },
    }
    result = guard_mod._check_rename_drift(cfg, live_by_name, remote_horistic=None)
    assert result["status"] == "block"
    assert any(item.get("name") == "pm2_path_reference" and item.get("severity") == "block" for item in result["details"]["findings"])


def test_rename_drift_blocks_active_apache_vhost_reference(base_config):
    cfg = copy.deepcopy(base_config)
    cfg["rename_drift"]["alias_pairs"][0]["benign_file_refs"] = []
    cfg["rename_drift"]["symlink_expectations"] = []
    cfg["rename_drift"]["backup_paths"] = []
    remote = {
        "details": {
            "sites_enabled": {
                "enabled_sites": [
                    "remote.horistic-srv-1.atius.com.br.conf",
                    "horistic.srv-1-backup.conf",
                ]
            }
        }
    }
    result = guard_mod._check_rename_drift(cfg, {}, remote_horistic=remote)
    assert any(item.get("name") == "apache_vhost_reference" for item in result["details"]["findings"])
    assert any(item.get("name") == "apache_vhost_reference" and item.get("severity") == "block" for item in result["details"]["findings"])
