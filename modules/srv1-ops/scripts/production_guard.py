#!/usr/bin/env python3
"""Read-only Production Guard for ATS/Horistic.

Usage:
    python3 production_guard.py status --json
    python3 production_guard.py doctor --json
    python3 production_guard.py repair --dry-run --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import socket
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request


SCRIPT = Path(__file__).resolve()
MODULE = SCRIPT.parent.parent
DEFAULT_BASELINE_PATH = MODULE / "configs" / "production-guard.yaml"
DEFAULT_PM2_HOME = Path("/home/ubuntu/.pm2")
DEFAULT_DUMP_PATH = DEFAULT_PM2_HOME / "dump.pm2"
DEFAULT_PM2_BIN = "/home/ubuntu/.nvm/versions/node/v24.13.1/lib/node_modules/pm2/bin/pm2"
DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "omni" / "production-guard"
DEFAULT_AUDIT_LOG = DEFAULT_STATE_DIR / "audit.jsonl"
DEFAULT_SNAPSHOT_DIR = DEFAULT_STATE_DIR / "snapshots"

Status = str

STATUS_ORDER = {
    "pass": 0,
    "warn": 1,
    "unknown": 2,
    "block": 3,
}

APPLY_BLOCKING_PREFIXES = ("ecosystem_", "runtime_app_")
SAFE_SYSTEMD_SERVICES = {
    "resource-governor-watchdog.service",
    "resource-governor-patcher.service",
}
SAFE_SYSTEMD_TIMERS = {
    "inviolable-watchdog.timer",
    "resource-governor-watchdog.timer",
    "resource-governor-snapshot.timer",
    "resource-governor-audit.timer",
}


class RepairAction:
    def __init__(
        self,
        *,
        scope: str,
        target: str,
        status: str,
        reason: str,
        risk: str,
        side_effect: str,
        rollback_hint: str,
        command: list[str],
        blocked_reason: str | None = None,
        snapshot_required: bool = True,
    ) -> None:
        self.scope = scope
        self.target = target
        self.status = status
        self.reason = reason
        self.risk = risk
        self.side_effect = side_effect
        self.rollback_hint = rollback_hint
        self.command = command
        self.blocked_reason = blocked_reason
        self.snapshot_required = snapshot_required


def _to_status(values: list[Status]) -> Status:
    if not values:
        return "pass"
    worst = max(values, key=lambda value: STATUS_ORDER.get(value, 0))
    return worst


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_yaml(path: Path) -> dict[str, Any]:
    import yaml  # type: ignore

    data = path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(data)
    if not isinstance(loaded, dict):
        raise RuntimeError(f"baseline inválido: {path}")
    return loaded


def _run(cmd: list[str], *, env: dict[str, str] | None = None, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _run_remote(cmd: str, target: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return _run(["ssh", target, cmd], timeout=timeout)


def _run_json(cmd: list[str], *, env: dict[str, str] | None = None, timeout: int = 10) -> Any:
    completed = _run(cmd, env=env, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)} ({completed.returncode}): {completed.stderr.strip()}")
    try:
        return json.loads(completed.stdout.strip() or "null")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid json from {' '.join(cmd)}: {exc}") from exc


def _parse_key_value_output(raw: str, *wanted: str) -> dict[str, str]:
    data: dict[str, str] = {}
    wanted_set = set(wanted)
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not wanted or key in wanted_set:
            data[key.strip()] = value.strip()
    return data


def _systemctl_property(scope: str, unit: str, prop: str) -> str:
    cmd = ["systemctl", "show", unit, f"--property={prop}", "--value"]
    if scope == "user":
        cmd.insert(1, "--user")
    completed = _run(cmd)
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _systemctl_is_active(scope: str, unit: str) -> str:
    cmd = ["systemctl", "is-active", unit]
    if scope == "user":
        cmd.insert(1, "--user")
    completed = _run(cmd)
    if completed.returncode == 0:
        return completed.stdout.strip()
    return completed.stdout.strip() or completed.stderr.strip() or "unknown"


def _systemctl_list_timers(scope: str) -> str:
    cmd = ["systemctl", "list-timers", "--all", "--no-pager", "--plain"]
    if scope == "user":
        cmd.insert(1, "--user")
    completed = _run(cmd)
    return completed.stdout if completed.returncode == 0 else ""


def _systemctl_list_jobs(scope: str) -> str:
    cmd = ["systemctl", "list-jobs", "--no-pager", "--plain"]
    if scope == "user":
        cmd.insert(1, "--user")
    completed = _run(cmd)
    return completed.stdout if completed.returncode == 0 else ""


def _list_containers() -> list[str]:
    completed = _run(["podman", "ps", "--format", "{{.Names}}"])
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _load_pm2_jlist(pm2_bin: str | None = None) -> list[dict[str, Any]]:
    return _run_json([pm2_bin or DEFAULT_PM2_BIN, "jlist"])


def _load_pm2_dump(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, list):
        return []
    return parsed


def _load_ecosystem_apps(path: Path) -> list[dict[str, Any]]:
    js_loader = (
        "const p = process.argv[2];\n"
        "const cfg = require(p);\n"
        "const apps = Array.isArray(cfg) ? cfg : (cfg && Array.isArray(cfg.apps) ? cfg.apps : []);\n"
        "if (!Array.isArray(apps)) { console.log('[]'); process.exit(0); }\n"
        "console.log(JSON.stringify(apps));\n"
    )
    completed = _run(["node", "-e", js_loader, str(path)], timeout=20)
    if completed.returncode != 0:
        raise RuntimeError(f"unable to parse ecosystem: {path}")
    loaded = json.loads(completed.stdout or "[]")
    if isinstance(loaded, list):
        return [item for item in loaded if isinstance(item, dict)]
    return []


def _read_config(path: Path) -> dict[str, Any]:
    data = _read_yaml(path)
    return data


def _redact_sensitive(value: str, redaction_patterns: list[str]) -> str:
    lowered = value.lower()
    if any(item in lowered for item in redaction_patterns):
        return "***REDACTED***"
    return value


def _redact_dict(data: Any, redaction_patterns: list[str]) -> Any:
    if isinstance(data, dict):
        return {key: ( "***REDACTED***" if isinstance(key, str) and any(
            pat in key.lower() for pat in redaction_patterns
        ) else _redact_dict(value, redaction_patterns)) for key, value in data.items()}
    if isinstance(data, list):
        return [_redact_dict(item, redaction_patterns) for item in data]
    if isinstance(data, str):
        return _redact_sensitive(data, redaction_patterns)
    return data


def _pm2_app_namespace(app: dict[str, Any]) -> str:
    env = app.get("pm2_env", {}) if isinstance(app.get("pm2_env"), dict) else {}
    ns = env.get("namespace")
    if isinstance(ns, str) and ns.strip():
        return ns.strip()
    ns2 = app.get("namespace")
    if isinstance(ns2, str) and ns2.strip():
        return ns2.strip()
    return "default"


def _extract_pm2_name(app: dict[str, Any]) -> str:
    env = app.get("pm2_env", {}) if isinstance(app.get("pm2_env"), dict) else {}
    return str(env.get("name") or app.get("name") or "")


def _extract_pm2_status(app: dict[str, Any]) -> str:
    env = app.get("pm2_env", {}) if isinstance(app.get("pm2_env"), dict) else {}
    return str(env.get("status") or "unknown")


def _extract_pm2_restart_count(app: dict[str, Any]) -> int:
    env = app.get("pm2_env", {}) if isinstance(app.get("pm2_env"), dict) else {}
    value = env.get("restart_time", 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _make_item(name: str, status: Status, summary: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"name": name, "status": status, "summary": summary}
    if details is not None:
        item["details"] = details
    return item


def _index_by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for item in items:
        name = _extract_pm2_name(item)
        if name:
            by_name[name] = item
    return by_name


def _check_pm2_boot_contract(config: dict[str, Any]) -> dict[str, Any]:
    cfg = config["pm2"]["service"]
    unit = cfg["name"]
    scope = cfg.get("scope", "system")
    properties = {
        "Type": _systemctl_property(scope, unit, "Type"),
        "RemainAfterExit": _systemctl_property(scope, unit, "RemainAfterExit"),
        "ActiveState": _systemctl_property(scope, unit, "ActiveState"),
        "ExecStart": _systemctl_property(scope, unit, "ExecStart"),
        "Environment": _systemctl_property(scope, unit, "Environment"),
        "PIDFile": _systemctl_property(scope, unit, "PIDFile"),
    }
    statuses: list[Status] = []
    reasons: list[str] = []

    if properties["Type"] != cfg.get("expected_type"):
        statuses.append("block")
        reasons.append("systemd Type fora do esperado")
    else:
        statuses.append("pass")

    expected_remain = str(cfg.get("expected_remain_after_exit", False)).lower()
    if properties["RemainAfterExit"].lower() != expected_remain:
        statuses.append("block")
        reasons.append("RemainAfterExit fora do esperado")
    else:
        statuses.append("pass")

    env = properties["Environment"]
    env_map: dict[str, str] = {}
    for item in env.split():
        if "=" in item:
            k, v = item.split("=", 1)
            env_map[k.strip()] = v.strip().strip("\"'")
    for key, value in cfg.get("expected_env", {}).items():
        if env_map.get(key, "") != value:
            statuses.append("block")
            reasons.append(f"{key} não encontrado em Environment")
    for forbidden in cfg.get("forbidden_env", []):
        if forbidden in env_map:
            statuses.append("block")
            reasons.append(f"{forbidden} proibido para unit de boot")
        elif forbidden in properties["ExecStart"]:
            statuses.append("block")
            reasons.append(f"{forbidden} proibido para unit de boot")
        else:
            statuses.append("pass")

    expected_exec = cfg.get("expected_execstart_contains", [])
    for snippet in expected_exec:
        if snippet not in properties["ExecStart"]:
            statuses.append("block")
            reasons.append("ExecStart não contém contrato esperado")
        else:
            statuses.append("pass")

    status = _to_status(statuses)
    return _make_item(
        name="pm2_boot_unit",
        status=status,
        summary="PM2 unit: " + (", ".join(reasons) if reasons else "contrato no padrão"),
        details={
            "unit": unit,
            "scope": scope,
            "properties": properties,
        },
    )


def _check_pm2_parity(config: dict[str, Any]) -> dict[str, Any]:
    pm2_cfg = config["pm2"]
    bin_path = pm2_cfg.get("binary", DEFAULT_PM2_BIN)
    dump_path = Path(pm2_cfg.get("dump_path", str(DEFAULT_DUMP_PATH)))
    try:
        live = _load_pm2_jlist(str(bin_path))
        if not isinstance(live, list):
            raise RuntimeError("pm2 jlist não retornou lista")
    except Exception as exc:
        live = []
        live_error = str(exc)
    else:
        live_error = ""

    dump = _load_pm2_dump(dump_path)

    live_by_name = _index_by_name(live)
    dump_by_name = _index_by_name(dump)
    expected_counts = pm2_cfg.get("namespace_counts", {})

    live_counts: dict[str, int] = {}
    dump_counts: dict[str, int] = {}
    wrong_namespace_live: list[str] = []
    missing_live: list[str] = []
    missing_dump: list[str] = []

    for item in live:
        ns = _pm2_app_namespace(item)
        live_counts[ns] = live_counts.get(ns, 0) + 1
        name = _extract_pm2_name(item)
        if name and ns == "default":
            wrong_namespace_live.append(name)

    for item in dump:
        ns = _pm2_app_namespace(item)
        dump_counts[ns] = dump_counts.get(ns, 0) + 1
        name = _extract_pm2_name(item)
        if name and ns == "default":
            # dump can be stale; classify as block so no drift is hidden.
            if name not in wrong_namespace_live:
                wrong_namespace_live.append(name)

    for name in live_by_name:
        if name not in dump_by_name:
            missing_dump.append(name)
    for name in dump_by_name:
        if name not in live_by_name:
            missing_live.append(name)

    statuses: list[Status] = []
    details: dict[str, Any] = {
        "expected_namespace_counts": expected_counts,
        "live_namespace_counts": live_counts,
        "dump_namespace_counts": dump_counts,
        "missing_in_dump": missing_dump[:10],
        "missing_in_live": missing_live[:10],
        "wrong_namespace_live": wrong_namespace_live,
    }
    if live_error:
        statuses.append("unknown")
        details["error"] = live_error
    else:
        statuses.append("pass")

    for namespace, expected in expected_counts.items():
        if live_counts.get(namespace, 0) != expected:
            statuses.append("block")
            details[f"{namespace}_live_count"] = f"esperado {expected} / encontrado {live_counts.get(namespace, 0)}"
        if dump_counts.get(namespace, 0) != expected:
            statuses.append("block")
            details[f"{namespace}_dump_count"] = f"esperado {expected} / encontrado {dump_counts.get(namespace, 0)}"

    if missing_live:
        statuses.append("block")
    if missing_dump:
        statuses.append("block")
    if wrong_namespace_live:
        statuses.append("block")

    status = _to_status(statuses)
    reasons = []
    if missing_live or missing_dump:
        reasons.append("diffência entre pm2 live x dump")
    if wrong_namespace_live:
        reasons.append("apps em namespace default")
    if not reasons:
        reasons.append("live, dump e namespaces coerentes")

    return _make_item("pm2_live_dump_parity", status, ", ".join(reasons), details)


def _parse_cycle_summary(
    app_name: str,
    config: dict[str, Any],
) -> tuple[bool, bool]:
    """Returns (found_summary, has_fatals)."""
    launcher_cfg = config["pm2"]["launchers"]
    patterns = launcher_cfg.get("cycle_summary_patterns", [])
    fatal_patterns = launcher_cfg.get("cycle_summary_fatal_patterns", [])
    log_root = DEFAULT_PM2_HOME / "logs"
    candidates = [log_root / f"{app_name}-out.log", log_root / f"{app_name}-error.log"]
    found = False
    has_fatal = False
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(re.search(pat, text, re.IGNORECASE) for pat in patterns):
            found = True
            if any(re.search(pat, text, re.IGNORECASE) for pat in fatal_patterns):
                has_fatal = True
    return found, has_fatal


def _check_launchers(config: dict[str, Any], live_by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    launcher_cfg = config["pm2"]["launchers"]
    allowed = set(launcher_cfg.get("allow_waiting_restart", []))
    stale_window = timedelta(minutes=int(launcher_cfg.get("cycle_summary_window_minutes", 15)))
    now = _now()

    statuses: list[Status] = []
    launcher_status: list[dict[str, Any]] = []
    for name in sorted(allowed):
        app = live_by_name.get(name, {})
        if not app:
            statuses.append("block")
            launcher_status.append({"name": name, "status": "block", "reason": "app não em runtime"})
            continue
        pm2_status = _extract_pm2_status(app)
        if pm2_status == "online":
            statuses.append("pass")
            launcher_status.append({"name": name, "status": "online"})
            continue
        if pm2_status != "waiting restart":
            statuses.append("warn")
            launcher_status.append({"name": name, "status": pm2_status, "reason": "estado não esperado"})
            continue

        found_summary, has_fatal = _parse_cycle_summary(name, config)
        if has_fatal:
            statuses.append("block")
            launcher_status.append({"name": name, "status": "block", "pm2_status": pm2_status, "reason": "summary apresenta falhas críticas"})
            continue
        if not found_summary:
            statuses.append("block")
            launcher_status.append({"name": name, "status": "block", "pm2_status": pm2_status, "reason": "sem [CYCLE_SUMMARY] recente"})
            continue

        # sem timestamp confiável de ciclo, usa mtime do log principal.
        out_file = DEFAULT_PM2_HOME / "logs" / f"{name}-out.log"
        if not out_file.exists():
            statuses.append("warn")
            launcher_status.append({"name": name, "status": "warn", "pm2_status": pm2_status, "reason": "sumário encontrado sem mtime de arquivo"})
            continue
        age = now - datetime.fromtimestamp(out_file.stat().st_mtime, tz=timezone.utc)
        if age > stale_window:
            statuses.append("warn")
            launcher_status.append({"name": name, "status": "warn", "pm2_status": pm2_status, "reason": "sumário antigo"})
        else:
            statuses.append("pass")
            launcher_status.append({"name": name, "status": "pass", "pm2_status": pm2_status, "reason": "waiting restart aceito com ciclo recente"})

    status = _to_status(statuses)
    item = _make_item(
        "launcher_health",
        status,
        "validação de launchers one-shot concluída",
        {"checks": launcher_status},
    )
    item["checks"] = launcher_status
    return item


def _normalize_path(base: Path, value: str) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


def _alias_variants(alias: str) -> set[str]:
    alias = str(alias)
    variants = {alias}
    if "-" in alias:
        variants.add(alias.replace("-", ".", 1))
    if "." in alias:
        variants.add(alias.replace(".", "-", 1))
    return variants


def _get_expected_apps(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    apps: dict[str, dict[str, Any]] = {}
    for section in config.get("ecosystems", {}).values():
        apps.update(section.get("critical_apps", {}))
    return apps


def _check_remote_horistic_apache(config: dict[str, Any]) -> dict[str, Any]:
    remote_cfg = config.get("remote_checks", {}).get("horistic", {})
    if not remote_cfg:
        return _make_item("remote_horistic_apache", "warn", "remote check do Horistic não configurado", {"enabled": False})

    alias_pairs = config.get("rename_drift", {}).get("alias_pairs", [])
    aliases = [str(item.get("from", "")) for item in alias_pairs if item.get("from")]
    alias_variants = set()
    for alias in aliases:
        alias_variants.update(_alias_variants(alias))

    ssh_target = str(remote_cfg.get("ssh", "")).strip()
    if not ssh_target:
        return _make_item("remote_horistic_apache", "block", "SSH remoto não configurado para Horistic", {"enabled": False})

    service = str(remote_cfg.get("service", "apache2"))
    expected_fragment = str(remote_cfg.get("expected_fragment_path", "/lib/systemd/system/apache2.service"))
    required_sites = [str(item) for item in remote_cfg.get("expected_sites_enabled", [])]
    required_ports = [int(item) for item in remote_cfg.get("required_listen_ports", [80, 443])]
    legacy_sites = set(str(item) for item in remote_cfg.get("legacy_sites_allowlist", []))

    checks: dict[str, Any] = {"ssh": ssh_target, "site_aliases": aliases}
    statuses: list[Status] = []

    show_cmd = f"systemctl show {service} -p FragmentPath -p DropInPaths -p NeedDaemonReload"
    is_enabled_cmd = f"systemctl is-enabled {service}"
    is_active_cmd = f"systemctl is-active {service}"
    listen_cmd = "ss -tlnp | grep -E ':(80|443) '"
    sites_cmd = "find /etc/apache2/sites-enabled -maxdepth 1 -type l -o -type f"
    apache2ctl_cmd = "apache2ctl -S"

    commands = {
        "service_properties": show_cmd,
        "is-enabled": is_enabled_cmd,
        "is-active": is_active_cmd,
        "listening_ports": listen_cmd,
        "sites_enabled": sites_cmd,
        "apache2ctl": apache2ctl_cmd,
    }

    for key, command in commands.items():
        try:
            completed = _run_remote(command, ssh_target, timeout=10)
            checks[key] = {
                "status": "pass" if completed.returncode == 0 else "error",
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
        except Exception as exc:
            checks[key] = {"status": "error", "error": str(exc)}

    service_properties = checks.get("service_properties", {})
    if service_properties.get("status") == "error":
        statuses.append("block")
    else:
        properties = _parse_key_value_output(
            str(service_properties.get("stdout", "")),
            "FragmentPath",
            "DropInPaths",
            "NeedDaemonReload",
        )
        checks["service_properties"]["properties"] = properties

        if properties.get("FragmentPath") != expected_fragment:
            statuses.append("block")
            checks["service_properties"]["reason"] = "fragmento do unit inesperado"
        else:
            statuses.append("pass")

        dropin_paths = [item.strip() for item in str(properties.get("DropInPaths", "")).split(":") if item.strip()]
        allowed_dropins = [str(item) for item in remote_cfg.get("allowed_dropin_paths", [])]
        if dropin_paths and any(path not in allowed_dropins for path in dropin_paths):
            statuses.append("block")
            checks["service_properties"]["reason"] = "drop-in custom detectado fora da allowlist"
            checks["service_properties"]["dropin_risk"] = checks["service_properties"]["reason"]
        else:
            statuses.append("pass")

    is_enabled = checks["is-enabled"]
    if is_enabled.get("status") != "pass" or is_enabled.get("stdout") not in {"enabled", "enabled-runtime"}:
        statuses.append("block")
    else:
        statuses.append("pass")

    is_active = checks["is-active"]
    if is_active.get("status") != "pass" or is_active.get("stdout") != "active":
        statuses.append("block")
    else:
        statuses.append("pass")

    listen = checks["listening_ports"]
    open_ports = set()
    if listen.get("status") == "pass":
        for line in str(listen.get("stdout", "")).splitlines():
            match = re.search(r":(\d+)(?:\s|$)", line.strip())
            if not match:
                continue
            try:
                open_ports.add(int(match.group(1)))
            except ValueError:
                pass
    missing_ports = [port for port in required_ports if port not in open_ports]
    checks["listening_ports"]["open_ports"] = sorted(open_ports)
    if missing_ports:
        statuses.append("block")
        checks["listening_ports"]["missing"] = missing_ports
    else:
        statuses.append("pass")

    sites = checks["sites_enabled"]
    enabled_sites = [line.strip() for line in str(sites.get("stdout", "")).splitlines() if line.strip()]
    enabled_site_names = [Path(line).name for line in enabled_sites]
    checks["sites_enabled"]["enabled_sites"] = enabled_sites
    checks["sites_enabled"]["enabled_site_names"] = enabled_site_names
    missing_sites = [site for site in required_sites if site not in enabled_site_names]
    if not enabled_sites:
        statuses.append("warn")
        checks["sites_enabled"]["reason"] = "sem vhosts em sites-enabled"
    elif missing_sites:
        statuses.append("warn")
        checks["sites_enabled"]["missing"] = missing_sites
    else:
        statuses.append("pass")

    legacy_hits = [
        site
        for site in enabled_site_names
        for alias in alias_variants
        if alias and alias in site and site not in legacy_sites
    ]
    if legacy_hits:
        statuses.append("block")
        checks["sites_enabled"]["legacy_alias_hits"] = legacy_hits
    else:
        statuses.append("pass")

    apache2ctl = checks["apache2ctl"]
    if apache2ctl.get("status") != "pass":
        statuses.append("block")
    else:
        checks["apache2ctl"]["status_code"] = "pass"
        statuses.append("pass")

    checks["required_ports"] = required_ports
    checks["expected_sites"] = required_sites
    checks["legacy_sites_allowlist"] = sorted(legacy_sites)

    return _make_item(
        "remote_horistic_apache",
        _to_status(statuses),
        "checagem remota de Apache no horistic-srv",
        checks,
    )


def _check_rename_drift(
    config: dict[str, Any],
    live_by_name: dict[str, dict[str, Any]],
    remote_horistic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    drift_cfg = config.get("rename_drift", {})
    alias_pairs = drift_cfg.get("alias_pairs", [])
    if not alias_pairs:
        return _make_item("rename_drift", "warn", "configuração de drift não encontrada", {"findings": []})

    findings: list[dict[str, Any]] = []
    statuses: list[Status] = []
    remote_sites = list(
        (remote_horistic or {}).get("details", {}).get("sites_enabled", {}).get("enabled_sites", [])
    )
    legacy_sites = set(str(item) for item in config.get("remote_checks", {}).get("horistic", {}).get("legacy_sites_allowlist", []))

    for pair in alias_pairs:
        old_alias = str(pair.get("from", "")).strip()
        new_alias = str(pair.get("to", "")).strip() or old_alias
        if not old_alias:
            continue
        alias_variants = _alias_variants(old_alias)

        legacy_file_refs = [str(item) for item in pair.get("benign_file_refs", [])]
        for path_text in legacy_file_refs:
            path = Path(path_text)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if old_alias in text:
                findings.append({
                    "name": "benign_reference",
                    "severity": "warn",
                    "alias": old_alias,
                    "path": str(path),
                    "evidence": "referência histórica",
                    "suggestion": "documentação/backup histórico, sem ação automática",
                })
                statuses.append("warn")

        for site in remote_sites:
            if any(alias in str(site) for alias in alias_variants) and str(site) not in legacy_sites:
                findings.append({
                    "name": "apache_vhost_reference",
                    "severity": "block",
                    "alias": old_alias,
                    "path": str(site),
                    "suggestion": f"substituir referência ativa por {new_alias}",
                })
                statuses.append("block")

        for path_text in [
            item for item in drift_cfg.get("backup_paths", []) if isinstance(item, str)
        ]:
            if old_alias in path_text:
                findings.append({
                    "name": "backup_path_reference",
                    "severity": "warn",
                    "alias": old_alias,
                    "path": path_text,
                    "evidence": "caminho legado de backup",
                    "suggestion": "atualizar mapeamento de backup somente se houver uso ativo",
                })
                statuses.append("warn")

    for app_name, app in live_by_name.items():
        pm2_env = app.get("pm2_env") if isinstance(app.get("pm2_env"), dict) else {}
        candidate_paths = [
            str(item)
            for item in (
                pm2_env.get("cwd", ""),
                pm2_env.get("script", ""),
                pm2_env.get("pm_cwd", ""),
                pm2_env.get("pm_exec_path", ""),
                app.get("script", ""),
            )
            if isinstance(item, str) and item
        ]

        for pair in alias_pairs:
            old_alias = str(pair.get("from", "")).strip()
            if not old_alias:
                continue
            alias_variants = _alias_variants(old_alias)
            for value in candidate_paths:
                if not any(alias in value for alias in alias_variants):
                    continue
                exists = Path(value).exists()
                findings.append({
                    "name": "pm2_path_reference",
                    "severity": "block" if not exists else "warn",
                    "alias": old_alias,
                    "app": app_name,
                    "path": value,
                    "exists": exists,
                    "suggestion": "sincronizar caminho para a base atual" if not exists else "validar se atualização é segura",
                })
                statuses.append("block" if not exists else "warn")

    for item in drift_cfg.get("symlink_expectations", []):
        old_path = Path(str(item.get("from", "")))
        expected_target = Path(str(item.get("to", "")))
        if not old_path.exists():
            findings.append({
                "name": "symlink_check",
                "severity": "pass",
                "path": str(old_path),
                "status": "path_legacy_ausente",
            })
            statuses.append("pass")
            continue
        if not old_path.is_symlink():
            findings.append({
                "name": "symlink_check",
                "severity": "warn",
                "path": str(old_path),
                "status": "nao_eh_symlink",
                "suggestion": "esperava-se symlink legado em revisão",
            })
            statuses.append("warn")
            continue

        target = old_path.resolve()
        if expected_target and expected_target not in target.parents and str(target) != str(expected_target):
            findings.append({
                "name": "symlink_check",
                "severity": "block",
                "path": str(old_path),
                "target": str(target),
                "suggestion": "corrigir symlink legado antes de aplicar",
            })
            statuses.append("block")
        else:
            findings.append({
                "name": "symlink_check",
                "severity": "pass",
                "path": str(old_path),
                "target": str(target),
            })
            statuses.append("pass")

    status = _to_status(statuses or ["pass"])
    if not findings:
        findings.append({
            "name": "rename_drift",
            "severity": "pass",
            "evidence": "sem drift de rename ativo",
            "suggestion": "nenhum patch automático aplicado",
        })
        status = "pass"

    return _make_item(
        "rename_drift",
        status,
        "detector de rename drift (sem mutação)",
        {"findings": findings},
    )


def _check_ecosystems(config: dict[str, Any], live_by_name: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    sensitive = list(config.get("redaction", {}).get("sensitive_fields", []))
    ecosystem_cfg = config.get("ecosystems", {})

    expected_apps = _get_expected_apps(config)
    expected_namespace_counts: dict[str, int] = {}
    for section in ecosystem_cfg.values():
        expected_namespace_counts[section.get("namespace", "default")] = section.get("expected_total", 0)

    for namespace, section in ecosystem_cfg.items():
        path = Path(section.get("path", ""))
        try:
            apps = _load_ecosystem_apps(path)
        except Exception as exc:
            checks.append(_make_item(
                f"ecosystem_{namespace}",
                "block",
                "não foi possível ler ecosystem",
                {"error": str(exc), "path": str(path)},
            ))
            continue

        by_name = {str(item.get("name")): item for item in apps if item.get("name")}
        for app_name, spec in section.get("critical_apps", {}).items():
            spec = dict(spec)
            file_app = by_name.get(app_name)
            live_app = live_by_name.get(app_name)
            app_statuses: list[Status] = []
            details: dict[str, Any] = {
                "namespace": namespace,
                "app": app_name,
                "path": str(path),
            }
            if file_app is None:
                checks.append(_make_item(
                    f"ecosystem_{namespace}_{app_name}",
                    "block",
                    "app ausente no ecosystem",
                    details,
                ))
                continue

            cwd = Path(file_app.get("cwd", spec.get("cwd", "")))
            script = str(file_app.get("script", ""))
            if not cwd.exists():
                app_statuses.append("block")
                details["cwd"] = {"expected": str(cwd), "state": "missing"}
            else:
                app_statuses.append("pass")
                details["cwd"] = {"expected": str(cwd), "state": "exists"}

            script_path = _normalize_path(cwd if cwd.exists() else Path(file_app.get("cwd", "")), script)
            if script_path is None or not script_path.exists():
                # script absolute may not exist by design in some cases; still classify as warn.
                app_statuses.append("warn")
                details["script"] = {"expected": str(script_path or script), "state": "missing"}
            else:
                app_statuses.append("pass")
                details["script"] = {"expected": str(script_path), "state": "exists"}

            for field in ("namespace", "autorestart", "restart_delay", "max_restarts"):
                expected_value = spec.get(field)
                if expected_value is None:
                    continue
                value = file_app.get(field)
                if value != expected_value:
                    app_statuses.append("block")
                    details[field] = {"expected": expected_value, "found": value}
                else:
                    app_statuses.append("pass")

            if file_app and isinstance(file_app.get("env"), dict):
                required = spec.get("required_env", [])
                env = {k: str(v) for k, v in file_app.get("env", {}).items()}
                for key in required:
                    if key not in env:
                        app_statuses.append("block")
                        details.setdefault("env", {})[key] = {"found": False}
                    else:
                        details.setdefault("env", {})[key] = {"found": True}
            else:
                app_statuses.append("warn")
                details["env"] = {"found": False, "reason": "arquivo não possui env no baseline"}

            if live_app is not None and isinstance(live_app.get("pm2_env"), dict):
                live_env = live_app.get("pm2_env", {}).get("env", {})
                if isinstance(live_env, dict):
                    for port in spec.get("expected_ports", []):
                        if str(port) not in {str(value) for value in live_env.values()}:
                            app_statuses.append("warn")
                            details.setdefault("live", {})[str(port)] = "missing"
                        else:
                            details.setdefault("live", {})[str(port)] = "found"
                details["pm2_live_env_redacted"] = _redact_dict(live_env, sensitive)
                if _pm2_app_namespace(live_app) != spec.get("namespace"):
                    app_statuses.append("block")
                    details["namespace"] = {
                        "expected": spec.get("namespace"),
                        "found": _pm2_app_namespace(live_app),
                    }
            else:
                app_statuses.append("warn")
                details["pm2_env"] = "not-found"

            checks.append(_make_item(
                f"ecosystem_{namespace}_{app_name}",
                _to_status(app_statuses),
                "app no ecossistema validado",
                details,
            ))

        # dynamic patterns keep a loose signal for known bot fleets.
        for pattern in section.get("dynamic_patterns", []):
            pattern_compiled = re.compile(pattern)
            matched = [name for name in live_by_name if pattern_compiled.match(name)]
            expected_total = int(section.get("expected_total", len(matched)))
            details_dynamic = {
                "pattern": pattern,
                "matched": matched[:20],
                "expected_min": expected_namespace_counts.get(namespace, 0),
            }
            status = "pass" if len(matched) >= expected_total else "warn"
            checks.append(_make_item(
                f"ecosystem_{namespace}_pattern_{pattern}",
                status,
                "contagem parcial de apps dinâmicos",
                details_dynamic,
            ))

    # verify expected critical apps list exists in runtime too
    for app_name in expected_apps:
        if app_name not in live_by_name:
            checks.append(_make_item(
                f"runtime_app_{app_name}",
                "warn",
                "app esperado sem instância em jlist",
                {"name": app_name},
            ))

    return checks


def _check_local_ports(config: dict[str, Any]) -> dict[str, Any]:
    statuses: list[Status] = []
    checks: list[dict[str, Any]] = []
    for port in config.get("critical_ports", []):
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=1):
                statuses.append("pass")
                checks.append({"port": int(port), "status": "open"})
        except OSError:
            statuses.append("warn")
            checks.append({"port": int(port), "status": "closed"})
    return _make_item(
        "critical_local_ports",
        _to_status(statuses),
        "checagem de portas críticas em localhost",
        {"ports": checks},
    )


def _probe_endpoint(url: str, method: str, timeout: int = 5) -> tuple[Status, int, str]:
    req = urllib.request.Request(url, method=method.upper(), headers={"User-Agent": "omni-production-guard/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=None) as response:
            code = int(response.status)
            if 200 <= code < 400:
                return "pass", code, "ok"
            return "warn", code, f"status {code}"
    except urllib.error.HTTPError as exc:
        return "warn", exc.code, str(exc)
    except Exception as exc:
        return "warn", 0, str(exc)


def _check_endpoints(config: dict[str, Any]) -> list[dict[str, Any]]:
    endpoints = config.get("endpoints", [])
    checks: list[dict[str, Any]] = []
    statuses: list[Status] = []
    for item in endpoints:
        method = str(item.get("method", "GET")).upper()
        name = str(item.get("name", item.get("url", "unknown")))
        url = str(item.get("url", ""))
        if method not in {"GET", "HEAD"}:
            statuses.append("block")
            checks.append({"name": name, "method": method, "status": "blocked"})
            continue
        status, code, message = _probe_endpoint(url, method=method)
        statuses.append(status)
        checks.append({"name": name, "method": method, "status": status, "status_code": code, "message": message})
    item = _make_item(
        "public_endpoints",
        _to_status(statuses),
        "checagem de endpoints GET/HEAD",
        {"checks": checks},
    )
    item["checks"] = checks
    return item


def _check_containers(config: dict[str, Any]) -> dict[str, Any]:
    running = set(_list_containers())
    statuses: list[Status] = []
    checks: list[dict[str, Any]] = []
    for item in config.get("containers", {}).get("required", []):
        name = item["name"]
        critical = bool(item.get("critical", True))
        exists = name in running
        if exists:
            status = "pass"
            if not critical:
                status = "pass"
        else:
            status = "block" if critical else "warn"
        statuses.append(status)
        checks.append({"name": name, "present": exists, "critical": critical})
    return _make_item("containers", _to_status(statuses), "containers required classificados", {"containers": checks})


def _check_systemd_entities(config: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for svc in config.get("systemd", {}).get("services", []):
        name = str(svc["name"])
        scope = str(svc.get("scope", "system"))
        expected = str(svc.get("expected_status", "active"))
        actual = _systemctl_is_active(scope, name)
        status: Status = "pass" if actual == expected else svc.get("criticality", "warn")
        if actual == "unknown":
            status = "unknown"
        elif actual != expected and status not in {"block", "warn"}:
            status = "warn"
        results.append(_make_item(f"service:{scope}:{name}", status, f"status={actual}", {"expected": expected}))

    for timer in config.get("systemd", {}).get("timers", []):
        name = str(timer["name"])
        scope = str(timer.get("scope", "user"))
        timer_output = _systemctl_list_timers(scope)
        has_timer = name in timer_output
        status: Status = "pass" if has_timer else timer.get("criticality", "warn")
        if status not in {"pass", "block", "warn"}:
            status = "warn"
        results.append(_make_item(f"timer:{scope}:{name}", status, f"exists={has_timer}", {"found": has_timer}))

    return results


def _check_systemd_jobs(config: dict[str, Any]) -> dict[str, Any]:
    output = _systemctl_list_jobs("user")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    checks: list[dict[str, Any]] = []
    statuses: list[Status] = []
    critical = [re.compile(item) for item in config.get("systemd", {}).get("jobs", {}).get("critical_blockers", [])]
    noisy = [re.compile(item) for item in config.get("systemd", {}).get("jobs", {}).get("noisy", [])]
    for line in lines:
        entry = {"line": line, "status": "pass"}
        if any(regex.search(line) for regex in critical):
            entry["status"] = "block"
            statuses.append("block")
        elif any(regex.search(line) for regex in noisy):
            entry["status"] = "warn"
            statuses.append("warn")
        else:
            statuses.append("pass")
        checks.append(entry)
    if not lines:
        statuses.append("pass")
    return _make_item("systemd_jobs", _to_status(statuses), "classificação de jobs do systemd", {"jobs": checks})


def _build_summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "block": 0, "unknown": 0}
    for item in checks:
        counts.setdefault(item["status"], 0)
        counts[item["status"]] += 1
    return counts


def _find_check(report: dict[str, Any], name: str) -> dict[str, Any] | None:
    for item in report.get("checks", []):
        if item.get("name") == name:
            return item
    return None


def _has_apply_blockers(report: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for item in report.get("checks", []):
        name = str(item.get("name", ""))
        status = str(item.get("status", ""))
        if status != "block":
            continue
        if name in {"pm2_boot_unit", "pm2_live_dump_parity", "launcher_health", "containers", "systemd_jobs"}:
            blockers.append(name)
            continue
        if name.startswith(APPLY_BLOCKING_PREFIXES):
            blockers.append(name)
    return blockers


def _command_preview(command: list[str], redaction_fields: list[str]) -> list[str]:
    return [str(_redact_sensitive(part, redaction_fields)) for part in command]


def _command_preview_shell(command: list[str], redaction_fields: list[str]) -> str:
    return shlex.join(_command_preview(command, redaction_fields))


def _ecosystem_for_app(config: dict[str, Any], app_name: str) -> tuple[str, Path] | None:
    for namespace, section in config.get("ecosystems", {}).items():
        if app_name in section.get("critical_apps", {}):
            return namespace, Path(str(section.get("path", "")))
    return None


def _forbidden_reason(scope: str, target: str, command: list[str]) -> str | None:
    lowered = [part.lower() for part in command]
    joined = " ".join(lowered)
    if scope == "pm2" and target == "save":
        return "pm2 save só pode aparecer como proposta bloqueada enquanto a saúde não estiver verde."
    if len(lowered) >= 2 and lowered[0] == "pm2" and lowered[1] == "kill":
        return "Ação proibida: derruba o daemon do PM2."
    if "xrdp" in lowered or any(part == ("xrdp" + "-sesman") for part in lowered):
        return "Ação proibida: toca serviços de RDP/XRDP."
    if "apache2" in lowered:
        return "Ação proibida: mutação de Apache está fora do escopo."
    if any(part.upper() == "POST" for part in command):
        return "Ação proibida: webhook POST real."
    if joined.startswith("systemctl restart") or joined.startswith("systemctl stop"):
        return "Ação proibida: restart/stop de serviços não permitidos."
    return None


def _action_to_dict(action: RepairAction, redaction_fields: list[str]) -> dict[str, Any]:
    payload = {
        "scope": action.scope,
        "target": action.target,
        "status": action.status,
        "reason": action.reason,
        "risk": action.risk,
        "side_effect": action.side_effect,
        "rollback_hint": action.rollback_hint,
        "snapshot_required": action.snapshot_required,
        "command_preview": _command_preview(action.command, redaction_fields),
        "command_preview_shell": _command_preview_shell(action.command, redaction_fields),
    }
    if action.blocked_reason:
        payload["blocked_reason"] = action.blocked_reason
    return payload


def _append_audit_event(payload: dict[str, Any], redaction_fields: list[str]) -> Path:
    DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)
    audit_payload = _redact_dict(payload, redaction_fields)
    with DEFAULT_AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return DEFAULT_AUDIT_LOG


def _write_snapshot(selected: dict[str, Any], report: dict[str, Any], redaction_fields: list[str]) -> Path:
    DEFAULT_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_path = DEFAULT_SNAPSHOT_DIR / f"snapshot-{_now().strftime('%Y%m%dT%H%M%SZ')}.json"
    snapshot_payload = {
        "timestamp": _now().isoformat(),
        "selected_action": selected,
        "report_overall": report.get("overall"),
        "report_summary": report.get("summary"),
    }
    snapshot_path.write_text(
        json.dumps(_redact_dict(snapshot_payload, redaction_fields), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot_path


def _candidate_status(blocked_reason: str | None) -> str:
    return "blocked" if blocked_reason else "planned"


def _plan_repair_actions(config: dict[str, Any], report: dict[str, Any]) -> list[RepairAction]:
    redaction_fields = [str(item) for item in config.get("redaction", {}).get("sensitive_fields", [])]
    del redaction_fields
    blockers = _has_apply_blockers(report)
    apply_gate_reason = ""
    if blockers:
        apply_gate_reason = "Apply bloqueado até resolver findings críticos da Phase 24."

    actions: list[RepairAction] = []

    parity = _find_check(report, "pm2_live_dump_parity") or {}
    if parity.get("status") == "block":
        actions.append(
            RepairAction(
                scope="pm2",
                target="save",
                status="blocked",
                reason="Sincronizar dump do PM2 só faz sentido depois de live/dump/namespaces ficarem coerentes.",
                risk="high",
                side_effect="Persistiria drift incorreto no dump se executado agora.",
                rollback_hint="Não aplicar; corrigir parity primeiro.",
                command=["pm2", "save"],
                blocked_reason="live/dump/namespaces ainda não estão saudáveis",
            )
        )

    containers = _find_check(report, "containers") or {}
    for item in containers.get("details", {}).get("containers", []):
        if item.get("present"):
            continue
        blocked_reason = apply_gate_reason if blockers else _forbidden_reason("container", str(item.get("name")), ["podman", "start", str(item.get("name"))])
        actions.append(
            RepairAction(
                scope="container",
                target=str(item.get("name")),
                status=_candidate_status(blocked_reason),
                reason="Container conhecido ausente no runtime atual.",
                risk="medium",
                side_effect="Pode iniciar workload de container conhecido.",
                rollback_hint=f"Usar podman stop {item.get('name')} se o start causar efeito indesejado.",
                command=["podman", "start", str(item.get("name"))],
                blocked_reason=blocked_reason,
            )
        )

    for check in report.get("checks", []):
        name = str(check.get("name", ""))
        status = str(check.get("status", ""))
        if status != "block":
            continue
        if name.startswith("service:user:"):
            unit = name.split(":", 2)[2]
            if unit not in SAFE_SYSTEMD_SERVICES:
                continue
            command = ["systemctl", "--user", "start", unit]
            blocked_reason = apply_gate_reason if blockers else _forbidden_reason("systemd-service", unit, command)
            actions.append(
                RepairAction(
                    scope="systemd-service",
                    target=unit,
                    status=_candidate_status(blocked_reason),
                    reason="Serviço user allowlisted está fora do estado esperado.",
                    risk="low",
                    side_effect="Aciona start do serviço user sem restart.",
                    rollback_hint=f"Usar systemctl --user stop {unit} se necessário.",
                    command=command,
                    blocked_reason=blocked_reason,
                )
            )
        if name.startswith("timer:user:"):
            unit = name.split(":", 2)[2]
            if unit not in SAFE_SYSTEMD_TIMERS:
                continue
            command = ["systemctl", "--user", "start", unit]
            blocked_reason = apply_gate_reason if blockers else _forbidden_reason("systemd-timer", unit, command)
            actions.append(
                RepairAction(
                    scope="systemd-timer",
                    target=unit,
                    status=_candidate_status(blocked_reason),
                    reason="Timer user allowlisted não apareceu no estado esperado.",
                    risk="low",
                    side_effect="Aciona o timer user sem restart de sessão.",
                    rollback_hint=f"Usar systemctl --user stop {unit} se necessário.",
                    command=command,
                    blocked_reason=blocked_reason,
                )
            )
        if name.startswith("runtime_app_"):
            app_name = name.removeprefix("runtime_app_")
            ecosystem_info = _ecosystem_for_app(config, app_name)
            if ecosystem_info is None:
                continue
            namespace, ecosystem_path = ecosystem_info
            command = [DEFAULT_PM2_BIN, "start", str(ecosystem_path), "--only", app_name]
            blocked_reason = apply_gate_reason
            if not blocked_reason and (_find_check(report, "pm2_live_dump_parity") or {}).get("status") == "block":
                blocked_reason = "namespace/live/dump precisa estar saudável antes de start de app PM2"
            if not blocked_reason and (_find_check(report, "launcher_health") or {}).get("status") == "block":
                blocked_reason = "launchers ou ciclo PM2 ainda apresentam blockers"
            if not blocked_reason:
                blocked_reason = _forbidden_reason("pm2-app", app_name, command)
            actions.append(
                RepairAction(
                    scope="pm2-app",
                    target=app_name,
                    status=_candidate_status(blocked_reason),
                    reason=f"App crítica do namespace {namespace} está ausente do runtime.",
                    risk="medium",
                    side_effect="Pode iniciar apenas a app crítica selecionada no ecosystem canônico.",
                    rollback_hint=f"Usar pm2 stop {app_name} se o start precisar ser revertido.",
                    command=command,
                    blocked_reason=blocked_reason,
                )
            )

    if not actions:
        actions.append(
            RepairAction(
                scope="report",
                target="noop",
                status="blocked" if blockers else "planned",
                reason="Nenhuma ação segura foi inferida a partir dos findings atuais.",
                risk="low",
                side_effect="Sem execução; apenas orientação operacional.",
                rollback_hint="Não se aplica.",
                command=["true"],
                blocked_reason=apply_gate_reason or None,
                snapshot_required=False,
            )
        )

    return actions


def _build_repair_report(config_path: Path, *, scope: str | None = None, target: str | None = None) -> dict[str, Any]:
    config = _read_config(config_path)
    report = _build_report("doctor", config_path)
    redaction_fields = [str(item) for item in config.get("redaction", {}).get("sensitive_fields", [])]
    actions = _plan_repair_actions(config, report)
    if scope:
        actions = [item for item in actions if item.scope == scope]
    if target:
        actions = [item for item in actions if item.target == target]
    blockers = _has_apply_blockers(report)
    return {
        "command": "repair",
        "mode": "dry-run",
        "timestamp": _now().isoformat(),
        "overall": "block" if blockers else "pass",
        "apply_ready": not blockers,
        "apply_blockers": blockers,
        "summary_pt_br": [
            "planejar reparos em dry-run",
            "bloquear apply enquanto a saúde estiver crítica",
            "redigir previews e auditoria",
        ],
        "report_summary": report.get("summary", {}),
        "actions": [_action_to_dict(item, redaction_fields) for item in actions],
        "redaction_fields": redaction_fields,
    }


def _select_apply_action(repair_report: dict[str, Any], scope: str, target: str) -> dict[str, Any]:
    for action in repair_report.get("actions", []):
        if action.get("scope") == scope and action.get("target") == target:
            return action
    raise RuntimeError(f"nenhuma ação encontrada para scope={scope} target={target}")


def _run_apply(
    config_path: Path,
    *,
    scope: str | None,
    target: str | None,
    risk_ack: bool,
) -> dict[str, Any]:
    if not scope or not target:
        raise RuntimeError("apply exige --scope e --target")
    if not risk_ack:
        raise RuntimeError("apply exige --yes-i-understand-production-risk")

    config = _read_config(config_path)
    redaction_fields = [str(item) for item in config.get("redaction", {}).get("sensitive_fields", [])]
    repair_report = _build_repair_report(config_path, scope=scope, target=target)
    action = _select_apply_action(repair_report, scope, target)
    if action.get("status") != "planned":
        raise RuntimeError(str(action.get("blocked_reason") or "ação não está liberada para apply"))

    forbidden_reason = _forbidden_reason(scope, target, [str(part) for part in action.get("command_preview", [])])
    if forbidden_reason:
        raise RuntimeError(forbidden_reason)

    snapshot_path = _write_snapshot(action, repair_report, redaction_fields)
    command = [str(part) for part in action.get("command_preview", [])]
    completed = _run(command, timeout=30)
    audit_path = _append_audit_event(
        {
            "timestamp": _now().isoformat(),
            "event": "apply",
            "scope": scope,
            "target": target,
            "snapshot_path": str(snapshot_path),
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
        redaction_fields,
    )
    return {
        "command": "repair",
        "mode": "apply",
        "timestamp": _now().isoformat(),
        "scope": scope,
        "target": target,
        "snapshot_path": str(snapshot_path),
        "audit_log": str(audit_path),
        "returncode": completed.returncode,
        "stdout": _redact_sensitive(completed.stdout, redaction_fields),
        "stderr": _redact_sensitive(completed.stderr, redaction_fields),
    }


def _build_report(mode: str, config_path: Path = DEFAULT_BASELINE_PATH) -> dict[str, Any]:
    config = _read_config(config_path)
    checks: list[dict[str, Any]] = []
    checks.append(_check_pm2_boot_contract(config))
    checks.append(_check_pm2_parity(config))
    live = []
    try:
        live = _load_pm2_jlist(str(config["pm2"].get("binary", DEFAULT_PM2_BIN)))
        if not isinstance(live, list):
            live = []
    except Exception:
        live = []
    checks.append(_check_launchers(config, _index_by_name(live)))
    checks.extend(_check_ecosystems(config, _index_by_name(live)))
    remote = _check_remote_horistic_apache(config)
    checks.append(remote)
    checks.append(_check_rename_drift(config, _index_by_name(live), remote_horistic=remote))
    checks.append(_check_local_ports(config))
    checks.append(_check_endpoints(config))
    checks.append(_check_containers(config))
    checks.extend(_check_systemd_entities(config))
    checks.append(_check_systemd_jobs(config))

    if mode == "status":
        checks = [item for item in checks if item["name"] != "systemd_jobs"]

    overall = _to_status([item["status"] for item in checks])
    summary = _build_summary(checks)
    redaction = [str(item) for item in config.get("redaction", {}).get("sensitive_fields", [])]
    return {
        "command": mode,
        "timestamp": _now().isoformat(),
        "overall": overall,
        "summary": summary,
        "summary_pt_br": [
            "checar de PM2/namespace",
            "checar ecosystems",
            "checar portas e endpoints",
            "checar containers/sistema",
        ],
        "checks": checks,
        "redaction_fields": redaction,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="production guard read-only")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "doctor"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--json", action="store_true", help="Emite JSON")
        sub.add_argument("--config", default=str(DEFAULT_BASELINE_PATH))

    repair = subparsers.add_parser("repair")
    repair.add_argument("--json", action="store_true", help="Emite JSON")
    repair.add_argument("--config", default=str(DEFAULT_BASELINE_PATH))
    repair.add_argument("--dry-run", action="store_true", help="Mostra o plano sem executar comandos.")
    repair.add_argument("--apply", action="store_true", help="Executa uma ação allowlisted após checkpoint explícito.")
    repair.add_argument("--scope", help="Escopo exato da ação permitida.")
    repair.add_argument("--target", help="Target exato da ação permitida.")
    repair.add_argument(
        "--yes-i-understand-production-risk",
        dest="risk_ack",
        action="store_true",
        help="Checkpoint explícito para produção.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config_path = Path(args.config)
    if args.command == "repair":
        if args.apply:
            report = _run_apply(
                config_path,
                scope=getattr(args, "scope", None),
                target=getattr(args, "target", None),
                risk_ack=bool(getattr(args, "risk_ack", False)),
            )
            if args.json:
                print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
            else:
                print(f"command=repair mode=apply scope={report['scope']} target={report['target']} rc={report['returncode']}")
            return int(report["returncode"])
        report = _build_repair_report(
            config_path,
            scope=getattr(args, "scope", None),
            target=getattr(args, "target", None),
        )
        if args.json:
            print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
        else:
            print(f"command=repair mode=dry-run apply_ready={report['apply_ready']}")
            for item in report["actions"]:
                print(f"- {item['scope']}:{item['target']} [{item['status']}] {item['reason']}")
        return 0

    report = _build_report(args.command, config_path)
    if args.json:
        print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    else:
        print(f"command={report['command']} overall={report['overall']}")
        for item in report["checks"]:
            print(f"- {item['name']}: {item['status']} | {item['summary']}")
    return 0 if report["overall"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
