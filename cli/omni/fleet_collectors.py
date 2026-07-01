"""Read-only local collectors for Omni Fleet program observations."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Callable

CollectorRunner = Callable[[list[str], int], tuple[int, str, str]]

DEFAULT_TIMEOUT = 8
COLLECTOR_VERSION = "0.1.0"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_command(argv: list[str], timeout: int = DEFAULT_TIMEOUT) -> tuple[int, str, str]:
    binary = argv[0]
    if "/" not in binary and shutil.which(binary) is None:
        return 127, "", f"{binary}: command not found"
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _record(
    *,
    host: str,
    name: str,
    install_type: str,
    manager: str,
    current_version: str | None = None,
    source: str | None = None,
    raw_ref: str | None = None,
    confidence: str = "observed",
    observed_at: str,
) -> dict[str, Any]:
    return {
        "host": host,
        "name": name,
        "install_type": install_type,
        "manager": manager,
        "current_version": current_version or "unknown",
        "source": source or manager,
        "observed_at": observed_at,
        "raw_ref": raw_ref or "",
        "confidence": confidence,
    }


def _safe_json(text: str) -> Any:
    if not text.strip():
        return None
    return json.loads(text)


def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for record in records:
        key = (
            str(record.get("host")),
            str(record.get("name")),
            str(record.get("install_type")),
            str(record.get("manager")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def _call(
    argv: list[str],
    *,
    warnings: list[str],
    runner: CollectorRunner,
    timeout: int = DEFAULT_TIMEOUT,
) -> str | None:
    try:
        returncode, stdout, stderr = runner(argv, timeout)
    except subprocess.TimeoutExpired:
        warnings.append(f"{argv[0]} timed out")
        return None
    except Exception as exc:
        warnings.append(f"{argv[0]} failed: {exc}")
        return None
    if returncode == 127:
        warnings.append(f"{argv[0]} missing")
        return None
    if returncode != 0:
        detail = (stderr or stdout).strip().splitlines()
        suffix = f": {detail[0][:160]}" if detail else ""
        warnings.append(f"{' '.join(argv[:2])} exited {returncode}{suffix}")
        return None
    return stdout


def _collect_dpkg(host: str, observed_at: str, runner: CollectorRunner, warnings: list[str]) -> list[dict[str, Any]]:
    stdout = _call(
        ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n"],
        warnings=warnings,
        runner=runner,
    )
    if stdout is None:
        return []
    records = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name, version, arch = parts[:3]
        records.append(
            _record(
                host=host,
                name=name,
                install_type="deb",
                manager="apt",
                current_version=version,
                source="dpkg-query",
                raw_ref=f"arch={arch}",
                observed_at=observed_at,
            )
        )
    return records


def _collect_snap(host: str, observed_at: str, runner: CollectorRunner, warnings: list[str]) -> list[dict[str, Any]]:
    stdout = _call(["snap", "list"], warnings=warnings, runner=runner)
    if stdout is None:
        return []
    records = []
    for index, line in enumerate(stdout.splitlines()):
        if index == 0 and line.lower().startswith("name"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        records.append(
            _record(
                host=host,
                name=parts[0],
                install_type="snap",
                manager="snap",
                current_version=parts[1],
                source="snap list",
                raw_ref=" ".join(parts[2:]),
                observed_at=observed_at,
            )
        )
    return records


def _collect_json_package_list(
    *,
    host: str,
    observed_at: str,
    runner: CollectorRunner,
    warnings: list[str],
    argv: list[str],
    manager: str,
    install_type: str,
    source: str,
) -> list[dict[str, Any]]:
    stdout = _call(argv, warnings=warnings, runner=runner)
    if stdout is None:
        return []
    try:
        data = _safe_json(stdout)
    except json.JSONDecodeError as exc:
        warnings.append(f"{manager} json parse failed: {exc}")
        return []
    records = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            records.append(
                _record(
                    host=host,
                    name=str(name),
                    install_type=install_type,
                    manager=manager,
                    current_version=str(item.get("version") or "unknown"),
                    source=source,
                    observed_at=observed_at,
                )
            )
    return records


def _collect_npm(host: str, observed_at: str, runner: CollectorRunner, warnings: list[str]) -> list[dict[str, Any]]:
    stdout = _call(["npm", "ls", "-g", "--depth=0", "--json"], warnings=warnings, runner=runner)
    if stdout is None:
        return []
    try:
        data = _safe_json(stdout) or {}
    except json.JSONDecodeError as exc:
        warnings.append(f"npm json parse failed: {exc}")
        return []
    deps = data.get("dependencies") if isinstance(data, dict) else {}
    records = []
    if isinstance(deps, dict):
        for name, meta in deps.items():
            version = meta.get("version") if isinstance(meta, dict) else None
            records.append(
                _record(
                    host=host,
                    name=str(name),
                    install_type="npm-global",
                    manager="npm",
                    current_version=str(version or "unknown"),
                    source="npm ls -g",
                    observed_at=observed_at,
                )
            )
    return records


def _collect_pnpm(host: str, observed_at: str, runner: CollectorRunner, warnings: list[str]) -> list[dict[str, Any]]:
    stdout = _call(["pnpm", "list", "-g", "--depth=0", "--json"], warnings=warnings, runner=runner)
    if stdout is None:
        return []
    try:
        data = _safe_json(stdout)
    except json.JSONDecodeError as exc:
        warnings.append(f"pnpm json parse failed: {exc}")
        return []
    records = []
    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        deps = item.get("dependencies")
        if isinstance(deps, dict):
            for name, meta in deps.items():
                version = meta.get("version") if isinstance(meta, dict) else None
                records.append(
                    _record(
                        host=host,
                        name=str(name),
                        install_type="pnpm-global",
                        manager="pnpm",
                        current_version=str(version or "unknown"),
                        source="pnpm list -g",
                        observed_at=observed_at,
                    )
                )
    return records


def _collect_cargo(host: str, observed_at: str, runner: CollectorRunner, warnings: list[str]) -> list[dict[str, Any]]:
    stdout = _call(["cargo", "install", "--list"], warnings=warnings, runner=runner)
    if stdout is None:
        return []
    records = []
    for line in stdout.splitlines():
        if not line or line.startswith(" ") or not line.endswith(":"):
            continue
        head = line[:-1]
        parts = head.split()
        if len(parts) < 2:
            continue
        version = parts[1].lstrip("v")
        records.append(
            _record(
                host=host,
                name=parts[0],
                install_type="cargo-bin",
                manager="cargo",
                current_version=version,
                source="cargo install --list",
                observed_at=observed_at,
            )
        )
    return records


def _collect_pm2(host: str, observed_at: str, runner: CollectorRunner, warnings: list[str]) -> list[dict[str, Any]]:
    stdout = _call(["pm2", "jlist"], warnings=warnings, runner=runner)
    if stdout is None:
        return []
    try:
        data = _safe_json(stdout) or []
    except json.JSONDecodeError as exc:
        warnings.append(f"pm2 json parse failed: {exc}")
        return []
    records = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
            if not name:
                continue
            records.append(
                _record(
                    host=host,
                    name=str(name),
                    install_type="pm2-process",
                    manager="pm2",
                    current_version=str(item.get("version") or env.get("version") or "unknown"),
                    source="pm2 jlist",
                    raw_ref=str(env.get("pm_exec_path") or env.get("status") or ""),
                    observed_at=observed_at,
                )
            )
    return records


def _collect_systemd(host: str, observed_at: str, runner: CollectorRunner, warnings: list[str]) -> list[dict[str, Any]]:
    stdout = _call(
        ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain", "--no-legend"],
        warnings=warnings,
        runner=runner,
    )
    if stdout is None:
        return []
    records = []
    for line in stdout.splitlines():
        parts = line.split()
        if not parts or not parts[0].endswith(".service"):
            continue
        records.append(
            _record(
                host=host,
                name=parts[0],
                install_type="systemd-service",
                manager="systemd",
                current_version=parts[2] if len(parts) > 2 else "unknown",
                source="systemctl list-units",
                raw_ref=" ".join(parts[1:4]),
                confidence="state",
                observed_at=observed_at,
            )
        )
    return records


def _json_lines_or_array(text: str) -> list[dict[str, Any]]:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        data = json.loads(stripped)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
    except json.JSONDecodeError:
        pass
    items = []
    for line in stripped.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items


def _collect_containers(host: str, observed_at: str, runner: CollectorRunner, warnings: list[str], engine: str) -> list[dict[str, Any]]:
    records = []
    ps_stdout = _call([engine, "ps", "--all", "--format=json"], warnings=warnings, runner=runner)
    if ps_stdout:
        for item in _json_lines_or_array(ps_stdout):
            name = item.get("Names") or item.get("Name") or item.get("names")
            image = item.get("Image") or item.get("image")
            if not name:
                continue
            records.append(
                _record(
                    host=host,
                    name=str(name),
                    install_type=f"{engine}-container",
                    manager=engine,
                    current_version=str(item.get("Status") or item.get("State") or "unknown"),
                    source=f"{engine} ps",
                    raw_ref=str(image or ""),
                    confidence="state",
                    observed_at=observed_at,
                )
            )
    images_stdout = _call([engine, "images", "--format=json"], warnings=warnings, runner=runner)
    if images_stdout:
        for item in _json_lines_or_array(images_stdout):
            repo = item.get("Repository") or item.get("repository")
            tag = item.get("Tag") or item.get("tag") or "latest"
            if not repo or repo == "<none>":
                continue
            records.append(
                _record(
                    host=host,
                    name=str(repo),
                    install_type=f"{engine}-image",
                    manager=engine,
                    current_version=str(tag),
                    source=f"{engine} images",
                    raw_ref=str(item.get("ID") or item.get("Id") or ""),
                    observed_at=observed_at,
                )
            )
    return records


def collect_programs(host: str, runner: CollectorRunner | None = None) -> dict[str, Any]:
    """Collect local program/package/service/container observations.

    All commands are read-only. Missing tools produce warnings instead of
    failing the whole collection.
    """
    observed_at = _now()
    command_runner = runner or _run_command
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    records.extend(_collect_dpkg(host, observed_at, command_runner, warnings))
    records.extend(_collect_snap(host, observed_at, command_runner, warnings))
    records.extend(
        _collect_json_package_list(
            host=host,
            observed_at=observed_at,
            runner=command_runner,
            warnings=warnings,
            argv=["python3", "-m", "pip", "list", "--format=json"],
            manager="pip",
            install_type="python-package",
            source="python3 -m pip list",
        )
    )
    records.extend(
        _collect_json_package_list(
            host=host,
            observed_at=observed_at,
            runner=command_runner,
            warnings=warnings,
            argv=["uv", "pip", "list", "--format=json"],
            manager="uv",
            install_type="python-package",
            source="uv pip list",
        )
    )
    records.extend(_collect_npm(host, observed_at, command_runner, warnings))
    records.extend(_collect_pnpm(host, observed_at, command_runner, warnings))
    records.extend(_collect_cargo(host, observed_at, command_runner, warnings))
    records.extend(_collect_pm2(host, observed_at, command_runner, warnings))
    records.extend(_collect_systemd(host, observed_at, command_runner, warnings))
    records.extend(_collect_containers(host, observed_at, command_runner, warnings, "podman"))
    records.extend(_collect_containers(host, observed_at, command_runner, warnings, "docker"))
    records = _dedupe(records)
    return {
        "host": host,
        "collector_version": COLLECTOR_VERSION,
        "program_count": len(records),
        "programs": records,
        "warnings": warnings,
        "generated_at": observed_at,
    }


def read_only_command_allowlist() -> list[list[str]]:
    """Return collector command templates for tests and audit docs."""
    return [
        ["dpkg-query", "-W", "-f=${Package}\\t${Version}\\t${Architecture}\\n"],
        ["snap", "list"],
        ["python3", "-m", "pip", "list", "--format=json"],
        ["uv", "pip", "list", "--format=json"],
        ["npm", "ls", "-g", "--depth=0", "--json"],
        ["pnpm", "list", "-g", "--depth=0", "--json"],
        ["cargo", "install", "--list"],
        ["pm2", "jlist"],
        ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain", "--no-legend"],
        ["podman", "ps", "--all", "--format=json"],
        ["podman", "images", "--format=json"],
        ["docker", "ps", "--all", "--format=json"],
        ["docker", "images", "--format=json"],
    ]

