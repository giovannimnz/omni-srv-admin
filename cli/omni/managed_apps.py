"""managed-apps — manual app version/source manager for the fleet."""
from __future__ import annotations

import json
import os
import shlex
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from omni.fleet import _db_env, _host_id, _load_host, _nested, _psql_json, _sql_literal


REPO = Path(os.environ.get("OMNI_SRV_ADMIN", str(Path(__file__).resolve().parents[2])))
MANIFEST_PATH = REPO / "modules" / "managed-apps" / "configs" / "programs.json"
SCRIPT_PATH = REPO / "modules" / "managed-apps" / "scripts" / "omni-managed-apps"
OMNI_APP_FIX = Path.home() / ".local" / "bin" / "omni-app-fix"
CONFIG_SECTIONS = ("repositories", "policies", "customizations")


def _run(args: list[str], *, timeout: int = 20, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=check)


def _load_manifest() -> dict[str, Any]:
    try:
        return json.loads(MANIFEST_PATH.read_text())
    except FileNotFoundError as exc:
        raise click.ClickException(f"manifest não encontrado: {MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"manifest JSON inválido: {MANIFEST_PATH}: {exc}") from exc


def _programs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    programs = manifest.get("programs")
    if not isinstance(programs, dict):
        raise click.ClickException("manifest inválido: campo programs ausente")
    return {str(key): value for key, value in programs.items() if isinstance(value, dict)}


def _select_apps(manifest: dict[str, Any], app: str, *, allow_unknown: bool = False) -> list[str]:
    programs = _programs(manifest)
    if app in {"all", "*"}:
        return list(programs)
    selected = [item.strip() for item in app.split(",") if item.strip()]
    unknown = [item for item in selected if item not in programs]
    if unknown:
        if allow_unknown:
            return selected
        raise click.ClickException(f"app não gerenciado: {', '.join(unknown)}")
    return selected


def _select_config_sections(manifest: dict[str, Any], section: str) -> list[str]:
    if section in {"all", "*"}:
        return [name for name in CONFIG_SECTIONS if isinstance(manifest.get(name), dict)]
    selected = [item.strip() for item in section.split(",") if item.strip()]
    unknown = [item for item in selected if item not in CONFIG_SECTIONS]
    if unknown:
        raise click.ClickException(f"seção não gerenciada: {', '.join(unknown)}")
    missing = [item for item in selected if not isinstance(manifest.get(item), dict)]
    if missing:
        raise click.ClickException(f"seção ausente no manifesto: {', '.join(missing)}")
    return selected


def _dpkg_version(package: str) -> tuple[str, str]:
    result = _run(["dpkg-query", "-W", "-f=${Version}\t${Architecture}", package])
    if result.returncode != 0:
        return "", ""
    version, _, arch = result.stdout.strip().partition("\t")
    return version, arch


def _apt_policy(package: str) -> str:
    result = _run(["apt-cache", "policy", package], timeout=15)
    return result.stdout if result.returncode == 0 else ""


def _apt_sources_text() -> str:
    paths = [Path("/etc/apt/sources.list")]
    sources_dir = Path("/etc/apt/sources.list.d")
    if sources_dir.exists():
        paths.extend(sorted(path for path in sources_dir.iterdir() if path.is_file()))
    chunks: list[str] = []
    for path in paths:
        try:
            chunks.append(f"\n# {path}\n{path.read_text(errors='replace')}")
        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            continue
    return "\n".join(chunks)


def _snap_installed(package: str) -> bool:
    if not shutil_which("snap"):
        return False
    result = _run(["snap", "list", package], timeout=10)
    return result.returncode == 0


def shutil_which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _wrapper_status(program: dict[str, Any]) -> dict[str, Any] | None:
    wrapper = program.get("required_wrapper")
    flags = program.get("required_wrapper_flags")
    if not wrapper or not isinstance(flags, list):
        return None
    path = Path(os.path.expanduser(str(wrapper)))
    text = path.read_text(errors="replace") if path.exists() else ""
    missing = [str(flag) for flag in flags if str(flag) not in text]
    return {
        "path": str(path),
        "exists": path.exists(),
        "missing_flags": missing,
        "ok": path.exists() and not missing,
    }


def _policy_status(program: dict[str, Any]) -> dict[str, Any] | None:
    policy_file = program.get("policy_file")
    expected = str(program.get("policy_forcelist_entry") or "")
    if not policy_file or not expected:
        return None
    path = Path(os.path.expanduser(str(policy_file)))
    try:
        payload = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        payload = {}
    entries = payload.get("ExtensionInstallForcelist")
    if not isinstance(entries, list):
        entries = []
    present = expected in [str(item) for item in entries]
    return {
        "path": str(path),
        "exists": path.exists(),
        "expected": expected,
        "present": present,
        "ok": path.exists() and present,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_string_value_status(path_value: str, key: str, expected: str) -> dict[str, Any]:
    path = Path(os.path.expanduser(path_value))
    try:
        payload = json.loads(path.read_text()) if path.exists() else {}
        read_error = ""
    except Exception as exc:
        payload = {}
        read_error = str(exc)
    actual = payload.get(key) if isinstance(payload, dict) else None
    return {
        "path": str(path),
        "exists": path.exists(),
        "key": key,
        "expected": expected,
        "actual": actual,
        "ok": path.exists() and not read_error and actual == expected,
        "read_error": read_error,
    }


def _repository_config_status(name: str, item: dict[str, Any]) -> dict[str, Any]:
    expected = str(item.get("expected_source_contains") or "")
    packages = [str(package) for package in item.get("packages", [])]
    source_text = _apt_sources_text()
    source_file_ok = expected in source_text if expected else True
    package_policy: dict[str, bool] = {}
    for package in packages:
        package_policy[package] = expected in _apt_policy(package) if expected else True
    return {
        "section": "repositories",
        "name": name,
        "kind": item.get("kind"),
        "ok": source_file_ok and all(package_policy.values()),
        "expected_source_contains": expected,
        "source_file_ok": source_file_ok,
        "package_policy": package_policy,
        "notes": item.get("notes", []),
    }


def _file_contains_config_status(section: str, name: str, item: dict[str, Any]) -> dict[str, Any]:
    path = Path(os.path.expanduser(str(item.get("path") or "")))
    try:
        text = path.read_text(errors="replace") if path.exists() else ""
        read_error = ""
    except Exception as exc:
        text = ""
        read_error = str(exc)
    required = [str(value) for value in item.get("required_contains", [])]
    forbidden = [str(value) for value in item.get("forbidden_contains", [])]
    missing = [value for value in required if value not in text]
    forbidden_present = [value for value in forbidden if value in text]
    return {
        "section": section,
        "name": name,
        "kind": item.get("kind"),
        "ok": path.exists() and not read_error and not missing and not forbidden_present,
        "path": str(path),
        "exists": path.exists(),
        "missing_required": missing,
        "forbidden_present": forbidden_present,
        "read_error": read_error,
        "notes": item.get("notes", []),
    }


def _json_policy_config_status(name: str, item: dict[str, Any]) -> dict[str, Any]:
    path = Path(os.path.expanduser(str(item.get("path") or "")))
    try:
        payload = json.loads(path.read_text()) if path.exists() else {}
        read_error = ""
    except Exception as exc:
        payload = {}
        read_error = str(exc)
    missing: dict[str, list[str]] = {}
    mismatched: dict[str, Any] = {}
    must_include = item.get("must_include", {})
    if not isinstance(must_include, dict):
        must_include = {}
    for key, expected in must_include.items():
        actual = payload.get(key)
        if isinstance(expected, list):
            actual_list = actual if isinstance(actual, list) else []
            missing_values = [str(value) for value in expected if str(value) not in [str(item) for item in actual_list]]
            if missing_values:
                missing[str(key)] = missing_values
        elif actual != expected:
            mismatched[str(key)] = {"expected": expected, "actual": actual}
    return {
        "section": "policies",
        "name": name,
        "kind": item.get("kind"),
        "ok": path.exists() and not read_error and not missing and not mismatched,
        "path": str(path),
        "exists": path.exists(),
        "missing": missing,
        "mismatched": mismatched,
        "read_error": read_error,
        "notes": item.get("notes", []),
    }


def _config_status(manifest: dict[str, Any], sections: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in sections:
        entries = manifest.get(section, {})
        if not isinstance(entries, dict):
            continue
        for name, item in entries.items():
            if not isinstance(item, dict):
                rows.append({"section": section, "name": str(name), "ok": False, "error": "manifest item inválido"})
                continue
            kind = item.get("kind")
            if section == "repositories" and kind == "apt-source":
                rows.append(_repository_config_status(str(name), item))
            elif kind == "file-contains":
                rows.append(_file_contains_config_status(section, str(name), item))
            elif kind == "json-policy":
                rows.append(_json_policy_config_status(str(name), item))
            else:
                rows.append({"section": section, "name": str(name), "kind": kind, "ok": False, "error": "kind não suportado"})
    return rows


def _apt_program_status(name: str, program: dict[str, Any]) -> dict[str, Any]:
    packages = [str(item) for item in program.get("packages", [])]
    desired = str(program.get("desired_version") or "")
    primary = str(program.get("primary_package") or packages[0])
    source_contains = str(program.get("desired_source_contains") or "")
    package_status = {}
    for package in packages:
        version, arch = _dpkg_version(package)
        package_status[package] = {
            "installed": bool(version),
            "version": version,
            "arch": arch,
            "desired_version": desired,
            "version_ok": bool(version) and (not desired or version == desired),
        }
    policy = _apt_policy(primary)
    source_ok = source_contains in policy if source_contains else True
    snap_bad = _snap_installed(primary) if "snap" in program.get("forbidden_package_managers", []) else False
    wrapper = _wrapper_status(program)
    checks = [
        all(item["installed"] for item in package_status.values()),
        all(item["version_ok"] for item in package_status.values()),
        source_ok,
        not snap_bad,
    ]
    if wrapper is not None:
        checks.append(bool(wrapper["ok"]))
    return {
        "app": name,
        "kind": program.get("kind"),
        "ok": all(checks),
        "packages": package_status,
        "source_contains": source_contains,
        "source_ok": source_ok,
        "snap_forbidden": "snap" in program.get("forbidden_package_managers", []),
        "snap_installed": snap_bad,
        "wrapper": wrapper,
    }


def _extension_status(name: str, program: dict[str, Any]) -> dict[str, Any]:
    extension_id = str(program.get("extension_id") or "")
    desired = str(program.get("desired_version") or "")
    profile_root = Path(os.path.expanduser(str(program.get("profile_root") or "~/.config/chromium")))
    profile_dir = str(program.get("profile_dir") or "Default")
    extension_base = profile_root / profile_dir / "Extensions" / extension_id
    manifests = sorted(extension_base.glob("*/manifest.json"))
    versions: list[str] = []
    for manifest in manifests:
        try:
            versions.append(str(json.loads(manifest.read_text()).get("version") or ""))
        except Exception:
            versions.append("")
    installed_version = versions[-1] if versions else ""
    wrapper = _wrapper_status(program)
    policy = _policy_status(program)
    ok = bool(installed_version) and (not desired or installed_version == desired)
    if wrapper is not None:
        ok = ok and bool(wrapper["ok"])
    if policy is not None:
        ok = ok and bool(policy["ok"])
    return {
        "app": name,
        "kind": program.get("kind"),
        "ok": ok,
        "extension_id": extension_id,
        "profile": str(profile_root / profile_dir),
        "installed": bool(installed_version),
        "installed_version": installed_version,
        "desired_version": desired,
        "version_ok": bool(installed_version) and (not desired or installed_version == desired),
        "wrapper": wrapper,
        "policy": policy,
    }


def _manual_appimage_status(name: str, program: dict[str, Any]) -> dict[str, Any]:
    install_dir = Path(os.path.expanduser(str(program.get("install_dir") or "")))
    stable = Path(os.path.expanduser(str(program.get("stable_appimage") or install_dir / "Obsidian.AppImage")))
    state_file = Path(os.path.expanduser(str(program.get("state_file") or install_dir / "state" / "current-release.json")))
    desired = str(program.get("desired_version") or "")
    desired_sha = str(program.get("desired_sha256") or "")
    installed_sha = ""
    sha_error = ""
    if stable.exists():
        try:
            installed_sha = _sha256_file(stable.resolve())
        except Exception as exc:
            sha_error = str(exc)
    state: dict[str, Any] = {}
    state_error = ""
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception as exc:
            state_error = str(exc)
    installed_version = str(state.get("version") or "")
    wrapper = _wrapper_status(program)
    appearance_defaults = program.get("appearance_defaults")
    appearance = None
    if isinstance(appearance_defaults, dict):
        appearance = _json_string_value_status(
            str(appearance_defaults.get("path") or ""),
            str(appearance_defaults.get("key") or "titlebarStyle"),
            str(appearance_defaults.get("value") or "native"),
        )
    snap_bad = _snap_installed(str(program.get("primary_package") or name)) if "snap" in program.get("forbidden_package_managers", []) else False
    checks = [
        stable.exists(),
        os.access(stable, os.X_OK),
        not desired or installed_version == desired,
        not desired_sha or installed_sha == desired_sha,
        not state_error,
        not sha_error,
        not snap_bad,
    ]
    if wrapper is not None:
        checks.append(bool(wrapper["ok"]))
    if appearance is not None:
        checks.append(bool(appearance["ok"]))
    return {
        "app": name,
        "kind": program.get("kind"),
        "ok": all(checks),
        "installed": stable.exists(),
        "installed_version": installed_version,
        "desired_version": desired,
        "version_ok": bool(installed_version) and (not desired or installed_version == desired),
        "stable_appimage": str(stable),
        "state_file": str(state_file),
        "sha256": installed_sha,
        "desired_sha256": desired_sha,
        "sha256_ok": bool(installed_sha) and (not desired_sha or installed_sha == desired_sha),
        "sha_error": sha_error,
        "state_error": state_error,
        "source_url": state.get("source_url") or program.get("source_url"),
        "snap_forbidden": "snap" in program.get("forbidden_package_managers", []),
        "snap_installed": snap_bad,
        "wrapper": wrapper,
        "appearance": appearance,
    }


def _manual_deb_status(name: str, program: dict[str, Any]) -> dict[str, Any]:
    install_dir = Path(os.path.expanduser(str(program.get("install_dir") or "")))
    state_file = Path(os.path.expanduser(str(program.get("state_file") or install_dir / "state" / "current-release.json")))
    deb_file = Path(os.path.expanduser(str(program.get("deb_file") or "")))
    package = str(program.get("primary_package") or program.get("package") or name)
    desired = str(program.get("desired_version") or "")
    desired_arch = str(program.get("desired_architecture") or "arm64")
    desired_sha = str(program.get("desired_sha256") or "")
    installed_version, arch = _dpkg_version(package)
    state: dict[str, Any] = {}
    state_error = ""
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception as exc:
            state_error = str(exc)
    deb_sha = ""
    sha_error = ""
    state_sha = str(state.get("sha256") or "")
    state_deb = Path(os.path.expanduser(str(state.get("deb") or ""))) if state.get("deb") else deb_file
    if state_deb.exists():
        try:
            deb_sha = _sha256_file(state_deb)
        except Exception as exc:
            sha_error = str(exc)
    reported_sha = deb_sha or state_sha
    forbidden_snap_names = program.get("forbidden_snap_names")
    if not isinstance(forbidden_snap_names, list):
        forbidden_snap_names = [str(program.get("primary_package") or name)]
    snap_status = {
        str(snap_name): _snap_installed(str(snap_name))
        for snap_name in forbidden_snap_names
    } if "snap" in program.get("forbidden_package_managers", []) else {}
    snap_bad = any(snap_status.values())
    state_ok = bool(state) and state.get("version") == desired and state.get("package") == package
    checks = [
        bool(installed_version),
        not desired or installed_version == desired,
        not desired_arch or arch == desired_arch,
        state_file.exists(),
        state_ok,
        not desired_sha or reported_sha == desired_sha,
        not state_error,
        not sha_error,
        not snap_bad,
    ]
    return {
        "app": name,
        "kind": program.get("kind"),
        "ok": all(checks),
        "installed": bool(installed_version),
        "package": package,
        "installed_version": installed_version,
        "desired_version": desired,
        "version_ok": bool(installed_version) and (not desired or installed_version == desired),
        "arch": arch,
        "desired_architecture": desired_arch,
        "architecture_ok": bool(arch) and (not desired_arch or arch == desired_arch),
        "state_file": str(state_file),
        "state_ok": state_ok,
        "deb_file": str(state_deb),
        "sha256": reported_sha,
        "desired_sha256": desired_sha,
        "sha256_ok": bool(reported_sha) and (not desired_sha or reported_sha == desired_sha),
        "sha_error": sha_error,
        "state_error": state_error,
        "source_url": state.get("source_url") or program.get("source_url"),
        "snap_forbidden": "snap" in program.get("forbidden_package_managers", []),
        "snap_installed": snap_bad,
        "snap_status": snap_status,
    }


def _local_status(manifest: dict[str, Any], selected: list[str]) -> list[dict[str, Any]]:
    programs = _programs(manifest)
    rows = []
    for name in selected:
        program = programs[name]
        if program.get("kind") == "chromium-extension":
            rows.append(_extension_status(name, program))
        elif program.get("kind") == "apt-package-set":
            rows.append(_apt_program_status(name, program))
        elif program.get("kind") == "manual-appimage":
            rows.append(_manual_appimage_status(name, program))
        elif program.get("kind") == "manual-deb":
            rows.append(_manual_deb_status(name, program))
        else:
            rows.append({"app": name, "kind": program.get("kind"), "ok": False, "error": "unsupported kind"})
    return rows


def _emit_rows(rows: list[dict[str, Any]], json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(rows, indent=2, sort_keys=True))
        return
    for row in rows:
        status = "ok" if row.get("ok") else "drift"
        click.echo(f"{row['app']}: {status}")
        if row.get("packages"):
            for package, data in row["packages"].items():
                mark = "ok" if data.get("version_ok") else "drift"
                click.echo(f"  {package}: {data.get('version') or 'not-installed'} ({mark})")
        if row.get("installed_version") is not None:
            mark = "ok" if row.get("version_ok") else "drift"
            click.echo(f"  version: {row.get('installed_version') or 'not-installed'} ({mark})")
        if row.get("package") and not row.get("packages"):
            arch = row.get("arch") or "unknown-arch"
            click.echo(f"  package: {row.get('package')} arch={arch}")
        if row.get("source_contains"):
            click.echo(f"  source: {'ok' if row.get('source_ok') else 'drift'} contains={row.get('source_contains')}")
        if row.get("stable_appimage"):
            click.echo(f"  appimage: {row.get('stable_appimage')}")
        if row.get("deb_file"):
            click.echo(f"  deb: {row.get('deb_file')}")
        if row.get("sha256") is not None:
            click.echo(f"  sha256: {'ok' if row.get('sha256_ok') else 'drift'} {row.get('sha256') or 'missing'}")
        if row.get("snap_forbidden"):
            click.echo(f"  snap: {'installed-forbidden' if row.get('snap_installed') else 'absent'}")
            snap_status = row.get("snap_status")
            if isinstance(snap_status, dict):
                for snap_name, installed in snap_status.items():
                    click.echo(f"    {snap_name}: {'installed-forbidden' if installed else 'absent'}")
        wrapper = row.get("wrapper")
        if isinstance(wrapper, dict):
            click.echo(f"  wrapper: {'ok' if wrapper.get('ok') else 'drift'} {wrapper.get('path')}")
            for flag in wrapper.get("missing_flags") or []:
                click.echo(f"    missing: {flag}")
        policy = row.get("policy")
        if isinstance(policy, dict):
            click.echo(f"  policy: {'ok' if policy.get('ok') else 'drift'} {policy.get('path')}")
        appearance = row.get("appearance")
        if isinstance(appearance, dict):
            click.echo(f"  appearance: {'ok' if appearance.get('ok') else 'drift'} {appearance.get('key')}={appearance.get('actual')!r}")


def _db_registry_rows(host_id: str, selected: list[str]) -> list[dict[str, Any]]:
    if not selected:
        return []
    selected_sql = ", ".join(_sql_literal(item) for item in selected)
    payload = _psql_json(
        f"""
SELECT COALESCE(jsonb_agg(
    jsonb_build_object(
        'app', app_id,
        'canonical_product_id', canonical_product_id,
        'runtime', runtime,
        'install_type', install_type,
        'current_version', current_version,
        'desired_version', desired_version,
        'update_policy', update_policy,
        'public_url', public_url,
        'healthcheck_url', healthcheck_url,
        'managed_by', managed_by,
        'metadata', metadata
    ) ORDER BY app_id
), '[]'::jsonb)
FROM "TbManagedApps"
WHERE host_id = '{host_id.replace("'", "''")}'
  AND app_id IN ({selected_sql});
""",
        env=_db_env(),
    )
    rows = payload if isinstance(payload, list) else []
    manifest = _load_manifest()
    programs = _programs(manifest)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        app_name = str(row.get("app") or "")
        manifest_app = programs.get(app_name, {})
        desired = str(manifest_app.get("desired_version") or row.get("desired_version") or "")
        current = str(row.get("current_version") or "")
        normalized.append(
            {
                **row,
                "desired_version": desired,
                "version_ok": bool(current) and (not desired or current == desired),
                "ok": True if not desired else current == desired,
                "source": "DbOmniFleet",
            }
        )
    return normalized


def _emit_config_rows(rows: list[dict[str, Any]], json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(rows, indent=2, sort_keys=True))
        return
    for row in rows:
        status = "ok" if row.get("ok") else "drift"
        click.echo(f"{row.get('section')}.{row.get('name')}: {status}")
        if row.get("error"):
            click.echo(f"  error: {row['error']}")
        if row.get("path"):
            click.echo(f"  path: {row['path']}")
        if row.get("expected_source_contains"):
            click.echo(f"  source-files: {'ok' if row.get('source_file_ok') else 'drift'} contains={row.get('expected_source_contains')}")
        package_policy = row.get("package_policy")
        if isinstance(package_policy, dict):
            for package, ok in package_policy.items():
                click.echo(f"  apt-policy {package}: {'ok' if ok else 'drift'}")
        for value in row.get("missing_required") or []:
            click.echo(f"  missing: {value}")
        for value in row.get("forbidden_present") or []:
            click.echo(f"  forbidden-present: {value}")
        missing = row.get("missing")
        if isinstance(missing, dict):
            for key, values in missing.items():
                for value in values:
                    click.echo(f"  missing {key}: {value}")
        mismatched = row.get("mismatched")
        if isinstance(mismatched, dict):
            for key, value in mismatched.items():
                click.echo(f"  mismatch {key}: expected={value.get('expected')!r} actual={value.get('actual')!r}")
        if row.get("read_error"):
            click.echo(f"  read-error: {row['read_error']}")


def _post_fix(selected: list[str]) -> int:
    manifest = _load_manifest()
    programs = _programs(manifest)
    rc = 0
    script_apps = [app for app in selected if programs.get(app, {}).get("post_fix_script")]
    for app in script_apps:
        script = REPO / str(programs[app]["post_fix_script"])
        if not script.exists():
            raise click.ClickException(f"post-fix script não encontrado para {app}: {script}")
        click.echo(f"[managed-apps] post-fix {app}: {script}")
        completed = subprocess.run([str(script)], text=True)
        if completed.returncode != 0:
            rc = completed.returncode
    apps = [app for app in selected if app in {"chromium", "firefox"}]
    if apps:
        if not OMNI_APP_FIX.exists():
            raise click.ClickException(f"omni-app-fix não encontrado: {OMNI_APP_FIX}")
        command = [str(OMNI_APP_FIX), "--scope", "local", "--app", ",".join(apps), "--action", "fix"]
        completed = subprocess.run(command, text=True)
        if completed.returncode != 0:
            rc = completed.returncode
    if not script_apps and not apps:
        click.echo("nenhum app selecionado tem post-fix local")
    return rc


def _upgrade_command(manifest: dict[str, Any], selected: list[str]) -> list[str]:
    programs = _programs(manifest)
    packages: list[str] = []
    for name in selected:
        program = programs[name]
        if program.get("kind") == "apt-package-set":
            packages.extend(str(item) for item in program.get("packages", []))
    if not packages:
        return []
    return ["sudo", "apt", "install", "--only-upgrade", *dict.fromkeys(packages)]


def _manual_upgrade_scripts(manifest: dict[str, Any], selected: list[str]) -> list[Path]:
    programs = _programs(manifest)
    scripts: list[Path] = []
    for name in selected:
        program = programs[name]
        if program.get("kind") not in {"manual-appimage", "manual-deb"}:
            continue
        script = program.get("post_fix_script")
        if script:
            scripts.append(REPO / str(script))
    return scripts


REMOTE_PROBE = r'''
import glob
import hashlib
import json
import os
import subprocess
from pathlib import Path
import sys

payload = json.load(sys.stdin)
manifest = payload["manifest"]
selected = payload["selected"]
programs = manifest["programs"]

def run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=20)

def dpkg_version(package):
    result = run(["dpkg-query", "-W", "-f=${Version}\t${Architecture}", package])
    if result.returncode != 0:
        return "", ""
    version, _, arch = result.stdout.strip().partition("\t")
    return version, arch

def which(name):
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None

def snap_installed(package):
    if not which("snap"):
        return False
    return run(["snap", "list", package]).returncode == 0

def apt_policy(package):
    result = run(["apt-cache", "policy", package])
    return result.stdout if result.returncode == 0 else ""

def wrapper_status(program):
    wrapper = program.get("required_wrapper")
    flags = program.get("required_wrapper_flags")
    if not wrapper or not isinstance(flags, list):
        return None
    path = Path(os.path.expanduser(str(wrapper)))
    text = path.read_text(errors="replace") if path.exists() else ""
    missing = [str(flag) for flag in flags if str(flag) not in text]
    return {"path": str(path), "exists": path.exists(), "missing_flags": missing, "ok": path.exists() and not missing}

def policy_status(program):
    policy_file = program.get("policy_file")
    expected = str(program.get("policy_forcelist_entry") or "")
    if not policy_file or not expected:
        return None
    path = Path(os.path.expanduser(str(policy_file)))
    try:
        payload = json.loads(path.read_text()) if path.exists() else {}
    except Exception:
        payload = {}
    entries = payload.get("ExtensionInstallForcelist")
    if not isinstance(entries, list):
        entries = []
    present = expected in [str(item) for item in entries]
    return {"path": str(path), "exists": path.exists(), "expected": expected, "present": present, "ok": path.exists() and present}

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def json_string_value_status(path_value, key, expected):
    path = Path(os.path.expanduser(str(path_value)))
    try:
        payload = json.loads(path.read_text()) if path.exists() else {}
        read_error = ""
    except Exception as exc:
        payload = {}
        read_error = str(exc)
    actual = payload.get(key) if isinstance(payload, dict) else None
    return {"path": str(path), "exists": path.exists(), "key": key, "expected": expected, "actual": actual, "ok": path.exists() and not read_error and actual == expected, "read_error": read_error}

def apt_status(name, program):
    packages = [str(item) for item in program.get("packages", [])]
    desired = str(program.get("desired_version") or "")
    primary = str(program.get("primary_package") or packages[0])
    package_status = {}
    for package in packages:
        version, arch = dpkg_version(package)
        package_status[package] = {"installed": bool(version), "version": version, "arch": arch, "desired_version": desired, "version_ok": bool(version) and (not desired or version == desired)}
    source_contains = str(program.get("desired_source_contains") or "")
    source_ok = source_contains in apt_policy(primary) if source_contains else True
    snap_bad = snap_installed(primary) if "snap" in program.get("forbidden_package_managers", []) else False
    wrapper = wrapper_status(program)
    checks = [all(item["installed"] for item in package_status.values()), all(item["version_ok"] for item in package_status.values()), source_ok, not snap_bad]
    if wrapper is not None:
        checks.append(bool(wrapper["ok"]))
    return {"app": name, "kind": program.get("kind"), "ok": all(checks), "packages": package_status, "source_ok": source_ok, "source_contains": source_contains, "snap_installed": snap_bad, "wrapper": wrapper}

def extension_status(name, program):
    extension_id = str(program.get("extension_id") or "")
    desired = str(program.get("desired_version") or "")
    profile_root = Path(os.path.expanduser(str(program.get("profile_root") or "~/.config/chromium")))
    profile_dir = str(program.get("profile_dir") or "Default")
    manifests = sorted((profile_root / profile_dir / "Extensions" / extension_id).glob("*/manifest.json"))
    versions = []
    for manifest in manifests:
        try:
            versions.append(str(json.loads(manifest.read_text()).get("version") or ""))
        except Exception:
            versions.append("")
    installed_version = versions[-1] if versions else ""
    wrapper = wrapper_status(program)
    policy = policy_status(program)
    ok = bool(installed_version) and (not desired or installed_version == desired)
    if wrapper is not None:
        ok = ok and bool(wrapper["ok"])
    if policy is not None:
        ok = ok and bool(policy["ok"])
    return {"app": name, "kind": program.get("kind"), "ok": ok, "installed": bool(installed_version), "installed_version": installed_version, "desired_version": desired, "version_ok": bool(installed_version) and (not desired or installed_version == desired), "wrapper": wrapper, "policy": policy}

def manual_appimage_status(name, program):
    install_dir = Path(os.path.expanduser(str(program.get("install_dir") or "")))
    stable = Path(os.path.expanduser(str(program.get("stable_appimage") or install_dir / "Obsidian.AppImage")))
    state_file = Path(os.path.expanduser(str(program.get("state_file") or install_dir / "state" / "current-release.json")))
    desired = str(program.get("desired_version") or "")
    desired_sha = str(program.get("desired_sha256") or "")
    installed_sha = ""
    sha_error = ""
    if stable.exists():
        try:
            installed_sha = sha256_file(stable.resolve())
        except Exception as exc:
            sha_error = str(exc)
    state = {}
    state_error = ""
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception as exc:
            state_error = str(exc)
    installed_version = str(state.get("version") or "")
    wrapper = wrapper_status(program)
    appearance = None
    appearance_defaults = program.get("appearance_defaults")
    if isinstance(appearance_defaults, dict):
        appearance = json_string_value_status(appearance_defaults.get("path") or "", appearance_defaults.get("key") or "titlebarStyle", appearance_defaults.get("value") or "native")
    snap_bad = snap_installed(str(program.get("primary_package") or name)) if "snap" in program.get("forbidden_package_managers", []) else False
    checks = [stable.exists(), os.access(stable, os.X_OK), not desired or installed_version == desired, not desired_sha or installed_sha == desired_sha, not state_error, not sha_error, not snap_bad]
    if wrapper is not None:
        checks.append(bool(wrapper["ok"]))
    if appearance is not None:
        checks.append(bool(appearance["ok"]))
    return {"app": name, "kind": program.get("kind"), "ok": all(checks), "installed": stable.exists(), "installed_version": installed_version, "desired_version": desired, "version_ok": bool(installed_version) and (not desired or installed_version == desired), "stable_appimage": str(stable), "state_file": str(state_file), "sha256": installed_sha, "desired_sha256": desired_sha, "sha256_ok": bool(installed_sha) and (not desired_sha or installed_sha == desired_sha), "sha_error": sha_error, "state_error": state_error, "source_url": state.get("source_url") or program.get("source_url"), "snap_installed": snap_bad, "wrapper": wrapper, "appearance": appearance}

def manual_deb_status(name, program):
    install_dir = Path(os.path.expanduser(str(program.get("install_dir") or "")))
    state_file = Path(os.path.expanduser(str(program.get("state_file") or install_dir / "state" / "current-release.json")))
    deb_file = Path(os.path.expanduser(str(program.get("deb_file") or "")))
    package = str(program.get("primary_package") or program.get("package") or name)
    desired = str(program.get("desired_version") or "")
    desired_arch = str(program.get("desired_architecture") or "arm64")
    desired_sha = str(program.get("desired_sha256") or "")
    installed_version, arch = dpkg_version(package)
    state = {}
    state_error = ""
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception as exc:
            state_error = str(exc)
    deb_sha = ""
    sha_error = ""
    state_sha = str(state.get("sha256") or "")
    state_deb = Path(os.path.expanduser(str(state.get("deb") or ""))) if state.get("deb") else deb_file
    if state_deb.exists():
        try:
            deb_sha = sha256_file(state_deb)
        except Exception as exc:
            sha_error = str(exc)
    reported_sha = deb_sha or state_sha
    forbidden_snap_names = program.get("forbidden_snap_names")
    if not isinstance(forbidden_snap_names, list):
        forbidden_snap_names = [str(program.get("primary_package") or name)]
    snap_status = {str(snap_name): snap_installed(str(snap_name)) for snap_name in forbidden_snap_names} if "snap" in program.get("forbidden_package_managers", []) else {}
    snap_bad = any(snap_status.values())
    state_ok = bool(state) and state.get("version") == desired and state.get("package") == package
    checks = [bool(installed_version), not desired or installed_version == desired, not desired_arch or arch == desired_arch, state_file.exists(), state_ok, not desired_sha or reported_sha == desired_sha, not state_error, not sha_error, not snap_bad]
    return {"app": name, "kind": program.get("kind"), "ok": all(checks), "installed": bool(installed_version), "package": package, "installed_version": installed_version, "desired_version": desired, "version_ok": bool(installed_version) and (not desired or installed_version == desired), "arch": arch, "desired_architecture": desired_arch, "architecture_ok": bool(arch) and (not desired_arch or arch == desired_arch), "state_file": str(state_file), "state_ok": state_ok, "deb_file": str(state_deb), "sha256": reported_sha, "desired_sha256": desired_sha, "sha256_ok": bool(reported_sha) and (not desired_sha or reported_sha == desired_sha), "sha_error": sha_error, "state_error": state_error, "source_url": state.get("source_url") or program.get("source_url"), "snap_installed": snap_bad, "snap_status": snap_status}

rows = []
for name in selected:
    program = programs[name]
    if program.get("kind") == "apt-package-set":
        rows.append(apt_status(name, program))
    elif program.get("kind") == "chromium-extension":
        rows.append(extension_status(name, program))
    elif program.get("kind") == "manual-appimage":
        rows.append(manual_appimage_status(name, program))
    elif program.get("kind") == "manual-deb":
        rows.append(manual_deb_status(name, program))
    else:
        rows.append({"app": name, "ok": False, "error": "unsupported kind"})
print(json.dumps(rows, sort_keys=True))
'''


CONFIG_REMOTE_PROBE = r'''
import json
import os
import subprocess
from pathlib import Path
import sys

payload = json.load(sys.stdin)
manifest = payload["manifest"]
sections = payload["sections"]

def run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=20)

def apt_policy(package):
    result = run(["apt-cache", "policy", package])
    return result.stdout if result.returncode == 0 else ""

def apt_sources_text():
    paths = [Path("/etc/apt/sources.list")]
    sources_dir = Path("/etc/apt/sources.list.d")
    if sources_dir.exists():
        paths.extend(sorted(path for path in sources_dir.iterdir() if path.is_file()))
    chunks = []
    for path in paths:
        try:
            chunks.append("\n# " + str(path) + "\n" + path.read_text(errors="replace"))
        except Exception:
            pass
    return "\n".join(chunks)

def repository_status(name, item):
    expected = str(item.get("expected_source_contains") or "")
    packages = [str(package) for package in item.get("packages", [])]
    source_text = apt_sources_text()
    source_file_ok = expected in source_text if expected else True
    package_policy = {}
    for package in packages:
        package_policy[package] = expected in apt_policy(package) if expected else True
    return {"section": "repositories", "name": name, "kind": item.get("kind"), "ok": source_file_ok and all(package_policy.values()), "expected_source_contains": expected, "source_file_ok": source_file_ok, "package_policy": package_policy, "notes": item.get("notes", [])}

def file_contains_status(section, name, item):
    path = Path(os.path.expanduser(str(item.get("path") or "")))
    try:
        text = path.read_text(errors="replace") if path.exists() else ""
        read_error = ""
    except Exception as exc:
        text = ""
        read_error = str(exc)
    required = [str(value) for value in item.get("required_contains", [])]
    forbidden = [str(value) for value in item.get("forbidden_contains", [])]
    missing = [value for value in required if value not in text]
    forbidden_present = [value for value in forbidden if value in text]
    return {"section": section, "name": name, "kind": item.get("kind"), "ok": path.exists() and not read_error and not missing and not forbidden_present, "path": str(path), "exists": path.exists(), "missing_required": missing, "forbidden_present": forbidden_present, "read_error": read_error, "notes": item.get("notes", [])}

def json_policy_status(name, item):
    path = Path(os.path.expanduser(str(item.get("path") or "")))
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
        read_error = ""
    except Exception as exc:
        data = {}
        read_error = str(exc)
    missing = {}
    mismatched = {}
    must_include = item.get("must_include", {})
    if not isinstance(must_include, dict):
        must_include = {}
    for key, expected in must_include.items():
        actual = data.get(key)
        if isinstance(expected, list):
            actual_list = actual if isinstance(actual, list) else []
            missing_values = [str(value) for value in expected if str(value) not in [str(item) for item in actual_list]]
            if missing_values:
                missing[str(key)] = missing_values
        elif actual != expected:
            mismatched[str(key)] = {"expected": expected, "actual": actual}
    return {"section": "policies", "name": name, "kind": item.get("kind"), "ok": path.exists() and not read_error and not missing and not mismatched, "path": str(path), "exists": path.exists(), "missing": missing, "mismatched": mismatched, "read_error": read_error, "notes": item.get("notes", [])}

rows = []
for section in sections:
    entries = manifest.get(section, {})
    if not isinstance(entries, dict):
        continue
    for name, item in entries.items():
        if not isinstance(item, dict):
            rows.append({"section": section, "name": str(name), "ok": False, "error": "manifest item inválido"})
            continue
        kind = item.get("kind")
        if section == "repositories" and kind == "apt-source":
            rows.append(repository_status(str(name), item))
        elif kind == "file-contains":
            rows.append(file_contains_status(section, str(name), item))
        elif kind == "json-policy":
            rows.append(json_policy_status(str(name), item))
        else:
            rows.append({"section": section, "name": str(name), "kind": kind, "ok": False, "error": "kind não suportado"})
print(json.dumps(rows, sort_keys=True))
'''


@click.group(name="managed-apps")
def managed_apps() -> None:
    """Gerencia versões/fontes de apps manuais da fleet."""


@managed_apps.command("manifest")
@click.option("--json", "json_output", is_flag=True, help="Emite o manifesto completo em JSON.")
def manifest_info(json_output: bool) -> None:
    """Mostra o manifesto canônico de apps/políticas gerenciadas."""
    manifest = _load_manifest()
    if json_output:
        click.echo(json.dumps(manifest, indent=2, sort_keys=True))
        return
    click.echo(f"path: {MANIFEST_PATH}")
    click.echo(f"updated_at: {manifest.get('updated_at')}")
    click.echo(f"target_hosts: {', '.join(str(host) for host in manifest.get('target_hosts', []))}")
    for section in (*CONFIG_SECTIONS, "programs"):
        entries = manifest.get(section, {})
        count = len(entries) if isinstance(entries, dict) else 0
        click.echo(f"{section}: {count}")


@managed_apps.command("config-status")
@click.option("--section", default="all", help="Seção, lista separada por vírgula, ou all.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def config_status(section: str, json_output: bool) -> None:
    """Valida repos, policies e customizações locais versus manifesto."""
    manifest = _load_manifest()
    rows = _config_status(manifest, _select_config_sections(manifest, section))
    _emit_config_rows(rows, json_output)


@managed_apps.command("config-verify")
@click.option("--section", default="all", help="Seção, lista separada por vírgula, ou all.")
def config_verify(section: str) -> None:
    """Falha se repo, policy ou customização local divergir do manifesto."""
    manifest = _load_manifest()
    rows = _config_status(manifest, _select_config_sections(manifest, section))
    _emit_config_rows(rows, False)
    if not all(row.get("ok") for row in rows):
        raise click.ClickException("managed-apps config drift detectado")


@managed_apps.command("status")
@click.option("--app", default="all", help="App, lista separada por vírgula, ou all.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def status(app: str, json_output: bool) -> None:
    """Mostra status local versus manifesto."""
    manifest = _load_manifest()
    rows = _local_status(manifest, _select_apps(manifest, app))
    _emit_rows(rows, json_output)


@managed_apps.command("verify")
@click.option("--app", default="all", help="App, lista separada por vírgula, ou all.")
def verify(app: str) -> None:
    """Falha se algum app local divergir do manifesto."""
    manifest = _load_manifest()
    rows = _local_status(manifest, _select_apps(manifest, app))
    _emit_rows(rows, False)
    if not all(row.get("ok") for row in rows):
        raise click.ClickException("managed-apps drift detectado")


@managed_apps.command("fix")
@click.option("--app", default="chromium,firefox", help="App ou lista separada por vírgula.")
def fix(app: str) -> None:
    """Executa pós-fix local para launchers/wrappers gerenciados."""
    manifest = _load_manifest()
    selected = _select_apps(manifest, app)
    raise SystemExit(_post_fix(selected))


@managed_apps.command("upgrade")
@click.option("--app", default="chromium,firefox", help="App ou lista separada por vírgula.")
@click.option("--yes", is_flag=True, help="Executa apt local. Sem isto, mostra plano.")
def upgrade(app: str, yes: bool) -> None:
    """Planeja ou executa upgrade local dos pacotes apt gerenciados."""
    manifest = _load_manifest()
    selected = _select_apps(manifest, app)
    command = _upgrade_command(manifest, selected)
    manual_scripts = _manual_upgrade_scripts(manifest, selected)
    if not command:
        if manual_scripts:
            for script in manual_scripts:
                click.echo(str(script))
            if not yes:
                click.echo("plan-only: use --yes para executar o instalador manual")
                return
            raise SystemExit(_post_fix(selected))
        click.echo("nenhum pacote apt selecionado")
        return
    click.echo(" ".join(shlex.quote(part) for part in command))
    for script in manual_scripts:
        click.echo(f"post-upgrade manual: {script}")
    if not yes:
        click.echo("plan-only: use --yes para executar localmente")
        return
    completed = subprocess.run(command, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    raise SystemExit(_post_fix(selected))


@managed_apps.command("fleet-status")
@click.option("--app", default="all", help="App, lista separada por vírgula, ou all.")
@click.option("--host", "hosts", multiple=True, help="Host do inventário. Default: target_hosts do manifesto.")
@click.option("--db", "use_db", is_flag=True, help="Lê snapshot do DbOmniFleet em vez de probe SSH.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def fleet_status(app: str, hosts: tuple[str, ...], use_db: bool, json_output: bool) -> None:
    """Executa probe remoto via SSH nos hosts selecionados."""
    manifest = _load_manifest()
    selected = _select_apps(manifest, app, allow_unknown=use_db)
    host_ids = list(hosts) or [str(item) for item in manifest.get("target_hosts", [])]
    payloads = []
    for host_id in host_ids:
        path, host, _ = _load_host(host_id)
        ssh_target = _nested(host, "access", "ssh")
        item: dict[str, Any] = {"host": _host_id(host, path.stem), "ssh": ssh_target, "ok": False}
        if use_db:
            rows = _db_registry_rows(item["host"], selected)
            item["apps"] = rows
            item["ok"] = all(row.get("ok") for row in rows) if rows else False
            item["source"] = "DbOmniFleet"
            payloads.append(item)
            continue
        if not ssh_target:
            item["error"] = "ssh target ausente no inventário"
            payloads.append(item)
            continue
        completed = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                ssh_target,
                "python3 -c " + shlex.quote(REMOTE_PROBE),
            ],
            input=json.dumps({"manifest": manifest, "selected": selected}),
            capture_output=True,
            text=True,
            timeout=45,
        )
        if completed.returncode != 0:
            item["error"] = completed.stderr.strip() or completed.stdout.strip() or f"ssh exit {completed.returncode}"
            payloads.append(item)
            continue
        try:
            rows = json.loads(completed.stdout)
        except json.JSONDecodeError:
            item["error"] = "remote probe returned invalid JSON"
            item["stdout"] = completed.stdout[:1000]
            payloads.append(item)
            continue
        item["apps"] = rows
        item["ok"] = all(row.get("ok") for row in rows)
        payloads.append(item)
    if json_output:
        click.echo(json.dumps(payloads, indent=2, sort_keys=True))
        return
    for payload in payloads:
        click.echo(f"{payload['host']}: {'ok' if payload.get('ok') else 'drift'}")
        if payload.get("error"):
            click.echo(f"  error: {payload['error']}")
            continue
        for row in payload.get("apps", []):
            click.echo(f"  {row['app']}: {'ok' if row.get('ok') else 'drift'}")


@managed_apps.command("registry-status")
@click.option("--app", default="all", help="App, lista separada por vírgula, ou all.")
@click.option("--host", "hosts", multiple=True, help="Host do inventário. Default: target_hosts do manifesto.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def registry_status(app: str, hosts: tuple[str, ...], json_output: bool) -> None:
    """Lê apenas o registry de apps do DbOmniFleet."""
    fleet_status.callback(app=app, hosts=hosts, use_db=True, json_output=json_output)


@managed_apps.command("fleet-config-status")
@click.option("--section", default="all", help="Seção, lista separada por vírgula, ou all.")
@click.option("--host", "hosts", multiple=True, help="Host do inventário. Default: target_hosts do manifesto.")
@click.option("--json", "json_output", is_flag=True, help="Emite JSON.")
def fleet_config_status(section: str, hosts: tuple[str, ...], json_output: bool) -> None:
    """Executa probe remoto de repos, policies e customizações."""
    manifest = _load_manifest()
    sections = _select_config_sections(manifest, section)
    host_ids = list(hosts) or [str(item) for item in manifest.get("target_hosts", [])]
    payloads = []
    for host_id in host_ids:
        path, host, _ = _load_host(host_id)
        ssh_target = _nested(host, "access", "ssh")
        item: dict[str, Any] = {"host": _host_id(host, path.stem), "ssh": ssh_target, "ok": False}
        if not ssh_target:
            item["error"] = "ssh target ausente no inventário"
            payloads.append(item)
            continue
        completed = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                ssh_target,
                "python3 -c " + shlex.quote(CONFIG_REMOTE_PROBE),
            ],
            input=json.dumps({"manifest": manifest, "sections": sections}),
            capture_output=True,
            text=True,
            timeout=45,
        )
        if completed.returncode != 0:
            item["error"] = completed.stderr.strip() or completed.stdout.strip() or f"ssh exit {completed.returncode}"
            payloads.append(item)
            continue
        try:
            rows = json.loads(completed.stdout)
        except json.JSONDecodeError:
            item["error"] = "remote config probe returned invalid JSON"
            item["stdout"] = completed.stdout[:1000]
            payloads.append(item)
            continue
        item["config"] = rows
        item["ok"] = all(row.get("ok") for row in rows)
        payloads.append(item)
    if json_output:
        click.echo(json.dumps(payloads, indent=2, sort_keys=True))
        return
    for payload in payloads:
        click.echo(f"{payload['host']}: {'ok' if payload.get('ok') else 'drift'}")
        if payload.get("error"):
            click.echo(f"  error: {payload['error']}")
            continue
        for row in payload.get("config", []):
            click.echo(f"  {row.get('section')}.{row.get('name')}: {'ok' if row.get('ok') else 'drift'}")


@managed_apps.command("install-local-cli")
@click.option("--force", is_flag=True, help="Substitui shim existente.")
def install_local_cli(force: bool) -> None:
    """Instala shim omni-managed-apps em ~/.local/bin."""
    target = Path.home() / ".local" / "bin" / "omni-managed-apps"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if not force:
            raise click.ClickException(f"já existe: {target}; use --force")
        target.unlink()
    target.symlink_to(SCRIPT_PATH)
    click.echo(f"installed: {target} -> {SCRIPT_PATH}")
