"""fleet — multi-host inventory and control-plane contracts."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from .db_runtime import default_fleet_db_env, load_env_file, run_sql
from .fleet_collectors import collect_programs
from .fleet_governance import DEFAULT_MANAGED_APPS_SOURCE, load_managed_apps_profile
from .fleet_security import collect_security_report
from .fleet_versioning import (
    DEFAULT_OMNI_VERSION_MATRIX,
    _normalize_version,
    apply_omni_self_update,
    collect_omni_version,
    load_omni_version_matrix,
)

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", str(Path(__file__).resolve().parents[2])))
HOSTS_DIR = REPO / "inventory" / "hosts"
LEGACY_HOSTS_DIR = REPO / "hosts"
FLEET_LOG_DIR = Path(os.environ.get("OMNI_FLEET_LOG_DIR", str(Path.home() / ".logs" / "fleet")))
HEARTBEAT_DIR = FLEET_LOG_DIR / "heartbeats"
TELEMETRY_DIR = FLEET_LOG_DIR / "telemetry"
PROGRAMS_DIR = FLEET_LOG_DIR / "programs"
SECURITY_DIR = FLEET_LOG_DIR / "security"
VERSIONS_DIR = FLEET_LOG_DIR / "versions"
AUDIT_EVENTS = FLEET_LOG_DIR / "audit-events.jsonl"
FLEET_DB_ENV = default_fleet_db_env()
FLEET_AGENT_VERSION = "0.2.3"
PGBOUNCER_ENDPOINT = ("10.11.1.11", "6432")
PGBOUNCER_LEGACY_ENDPOINTS = (("10.100.100.1", "6432"),)
PKI_CA_HOST_ID = "atius-srv-1"
PKI_PROGRAM = "internal-service-pki"
PKI_DESIRED_VERSION = "service-ca-v1"
PKI_CA_BASE = "/var/lib/omni-srv-admin/pki"
PKI_TLS_BASE = "/etc/omni-srv-admin/tls"
PKI_WINDOWS_TLS_BASE = "C:/ProgramData/omni-srv-admin/tls"
PKI_WINDOWS_TRUST_STORE = "Cert:/CurrentUser/Root"
PKI_CA_FILES = (
    "/usr/local/share/ca-certificates/atius-vpn-service-root-ca.crt",
    "/usr/local/share/ca-certificates/atius-vpn-service-issuing-ca.crt",
)
PKI_COMMAND_STAGES = (
    "preflight",
    "init-ca",
    "ensure-key-csr",
    "issue-host",
    "install-ca",
    "install-leaf",
    "reconcile",
    "verify",
)

REQUIRED_HOST_FIELDS = (
    "id",
    "role",
    "owner",
    "status",
)

REQUIRED_NESTED_FIELDS = (
    ("access", "ssh"),
    ("platform", "provider"),
    ("platform", "os"),
    ("platform", "arch"),
)

SENSITIVE_KEYS = {"secret_ref", "token", "password", "serial", "license_key"}

LOCAL_COMMANDS: dict[str, dict[str, Any]] = {
    "omni.noop": {
        "description": "Safe no-op used for agent executor validation.",
        "argv": [sys.executable, "-c", "print('omni.noop ok')"],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": ["atius-srv-1", "atius-srv-2", "atius-srv-3"],
    },
    "omni.fleet.heartbeat": {
        "description": "Internal heartbeat and telemetry collection.",
        "internal": "heartbeat",
        "default_profile": "interactive",
        "requires_approval": False,
        "allowed_host_ids": ["atius-srv-1", "atius-srv-2", "atius-srv-3"],
    },
    "omni.resource.snapshot": {
        "description": "Collect local resource-governor snapshot when available.",
        "argv": ["python3", "{repo}/modules/srv1-ops/scripts/resource-governor-snapshot.py"],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": ["atius-srv-1"],
    },
    "omni.self-update.linux": {
        "description": "Apply approved omni-srv-admin update on Linux host checkout.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "agent",
            "self-update-runner",
            "--host",
            "{host_id}",
            "--desired-version",
            "{desired_version}",
        ],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": ["atius-srv-1", "atius-srv-2", "atius-srv-3"],
    },
    "omni.self-update.windows": {
        "description": "Apply approved omni-srv-admin update on Windows host checkout.",
        "argv": [
            "python",
            "-m",
            "omni",
            "fleet",
            "agent",
            "self-update-runner",
            "--host",
            "{host_id}",
            "--desired-version",
            "{desired_version}",
        ],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": ["giovanni-w11-pc"],
    },
    "omni.trust-pki.preflight": {
        "description": "Read-only local preflight for internal service PKI onboarding.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "preflight",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": False,
        "allowed_host_ids": [],
    },
    "omni.trust-pki.init-ca": {
        "description": "Initialize the internal service PKI CA on the CA host.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "init-ca",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": [PKI_CA_HOST_ID],
    },
    "omni.trust-pki.ensure-key-csr": {
        "description": "Ensure local host private key and CSR for internal service PKI.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "ensure-key-csr",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": [],
    },
    "omni.trust-pki.issue-host": {
        "description": "Sign one host CSR from the internal service PKI CA host.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "issue-host",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": [PKI_CA_HOST_ID],
    },
    "omni.trust-pki.install-ca": {
        "description": "Install the internal service PKI CA chain into the local trust store.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "install-ca",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": [],
    },
    "omni.trust-pki.install-leaf": {
        "description": "Install the signed internal service PKI leaf and chain locally.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "install-leaf",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": [],
    },
    "omni.trust-pki.verify": {
        "description": "Verify local internal service PKI material and trust.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "verify",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": False,
        "allowed_host_ids": [],
    },
    "omni.trust-pki.reconcile": {
        "description": "Compare local internal service PKI leaf SANs with desired inventory SANs.",
        "argv": [
            "python3",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "reconcile",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": False,
        "allowed_host_ids": [],
    },
    "omni.trust-pki.windows.preflight": {
        "description": "Read-only Windows preflight for internal service PKI trust client onboarding.",
        "argv": [
            "python",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "preflight",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": False,
        "allowed_host_ids": ["giovanni-w11-pc"],
    },
    "omni.trust-pki.windows.install-ca": {
        "description": "Install the internal service PKI CA chain into the Windows CurrentUser trust store.",
        "argv": [
            "python",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "install-ca",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": True,
        "allowed_host_ids": ["giovanni-w11-pc"],
    },
    "omni.trust-pki.windows.verify": {
        "description": "Verify Windows internal service PKI trust-client material.",
        "argv": [
            "python",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "verify",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": False,
        "allowed_host_ids": ["giovanni-w11-pc"],
    },
    "omni.trust-pki.windows.reconcile": {
        "description": "Compare Windows internal service PKI trust-client material with desired inventory.",
        "argv": [
            "python",
            "-m",
            "omni",
            "fleet",
            "trust-pki",
            "agent-runner",
            "reconcile",
            "--host",
            "{host_id}",
            "--json",
        ],
        "default_profile": "interactive",
        "requires_approval": False,
        "allowed_host_ids": ["giovanni-w11-pc"],
    },
}


def _simple_yaml_value(text: str, key: str, default: str = "") -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip().strip('"') or default
    return default


def _scalar(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if value in {"[]", "{}"}:
        return ""
    return value


def _simple_yaml(text: str) -> dict[str, Any]:
    """Parse the inventory subset used by inventory/hosts/*.yaml.

    This is intentionally small: one-level maps, top-level lists and scalar
    values. If PyYAML is installed, use it; otherwise keep the CLI dependency
    footprint at stdlib + click.
    """
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text) or {}
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        pass

    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            data[key] = _scalar(value) if value else None
            continue
        if current_key is None:
            continue
        if indent == 2 and line.startswith("- "):
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(_scalar(line[2:]))
            continue
        if indent == 2 and ":" in line:
            key, value = line.split(":", 1)
            if not isinstance(data.get(current_key), dict):
                data[current_key] = {}
            data[current_key][key.strip()] = _scalar(value)
    return data


@click.group(name="fleet")
def fleet() -> None:
    """Inventário multi-host e contratos do Fleet Control Plane."""


def _hosts_dir() -> Path:
    return HOSTS_DIR if HOSTS_DIR.exists() else LEGACY_HOSTS_DIR


def _host_path(host_id: str) -> Path:
    hosts_dir = _hosts_dir()
    path = hosts_dir / f"{host_id}.yaml"
    if path.exists():
        return path
    matches = sorted(hosts_dir.glob(f"*{host_id}*.yaml")) if hosts_dir.exists() else []
    if matches:
        return matches[0]
    raise click.ClickException(f"host não encontrado: {host_id}")


def _load_host(host_id: str) -> tuple[Path, dict[str, Any], str]:
    path = _host_path(host_id)
    text = path.read_text()
    data = _simple_yaml(text)
    if not data:
        raise click.ClickException(f"host inválido ou vazio: {path}")
    return path, data, text


def _nested(data: dict[str, Any], section: str, key: str, default: str = "") -> str:
    value = data.get(section)
    if isinstance(value, dict):
        nested_value = value.get(key)
        return str(nested_value) if nested_value not in {None, ""} else default
    return default


def _host_id(data: dict[str, Any], fallback: str) -> str:
    return str(data.get("id") or fallback)


def _inventory_host_records(*, syncable_only: bool = False) -> list[tuple[str, Path, dict[str, Any], str]]:
    hosts_dir = _hosts_dir()
    if not hosts_dir.exists():
        return []
    records: list[tuple[str, Path, dict[str, Any], str]] = []
    for path in sorted(hosts_dir.glob("*.yaml")):
        text = path.read_text()
        data = _simple_yaml(text)
        if not data:
            continue
        if syncable_only and str(data.get("status") or "").lower() == "template":
            continue
        records.append((_host_id(data, path.stem), path, data, text))
    return records


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _inventory_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repo_relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _inet_or_none(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw or raw.upper() == "TBD":
        return None
    try:
        ipaddress.ip_address(raw)
    except ValueError:
        return None
    return raw


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({item for item in values if item})


def _host_aliases(host: dict[str, Any]) -> list[str]:
    aliases = host.get("aliases")
    if not isinstance(aliases, list):
        return []
    return [str(item).strip() for item in aliases if str(item).strip()]


def _pki_service_tls_config(host: dict[str, Any]) -> dict[str, Any]:
    pki = host.get("pki")
    if not isinstance(pki, dict):
        return {}
    service_tls = pki.get("service_tls")
    return service_tls if isinstance(service_tls, dict) else {}


def _pki_platform_os(host: dict[str, Any]) -> str:
    return str(_nested(host, "platform", "os", "")).lower()


def _pki_is_windows_platform(host: dict[str, Any]) -> bool:
    return "windows" in _pki_platform_os(host)


def _pki_service_tls_mode(host: dict[str, Any]) -> str:
    config = _pki_service_tls_config(host)
    raw = str(config.get("mode") or "").strip().lower()
    aliases = {
        "client": "trust-client",
        "trust-only": "trust-client",
        "ca-only": "trust-client",
        "server": "leaf",
    }
    if raw:
        return aliases.get(raw, raw)
    if _pki_is_windows_platform(host):
        return "trust-client"
    return "leaf"


def _pki_access(host: dict[str, Any]) -> dict[str, Any]:
    access = host.get("access")
    return access if isinstance(access, dict) else {}


def _pki_ip_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, tuple):
        items = list(value)
    elif value is None:
        items = []
    else:
        items = [value]
    parsed: list[str] = []
    for item in items:
        ip_value = _inet_or_none(item)
        if ip_value:
            parsed.append(ip_value)
    return parsed


def _primary_private_ip(access: dict[str, Any]) -> str | None:
    return _inet_or_none(access.get("oci_private_ip")) or _inet_or_none(access.get("vpn_ip"))


def _pki_sans(host_id: str, host: dict[str, Any]) -> dict[str, list[str]]:
    access = _pki_access(host)
    config = _pki_service_tls_config(host)
    aliases = _host_aliases(host)
    dns_names = [host_id, f"{host_id}.atius.internal"]
    for alias in aliases:
        dns_names.extend([alias, f"{alias}.atius.internal"])
    ip_names: list[str] = []
    for key in ("oci_private_ip", "vpn_ip", "legacy_vpn_ip", "public_ip", "tailscale_ip"):
        ip_names.extend(_pki_ip_list(access.get(key)))
    for key in ("vpn_ips", "legacy_vpn_ips"):
        ip_names.extend(_pki_ip_list(access.get(key)))
    explicit_sans = config.get("sans")
    if isinstance(explicit_sans, list):
        for item in explicit_sans:
            raw = str(item).strip()
            if _inet_or_none(raw):
                ip_names.append(raw)
            elif raw:
                dns_names.append(raw)
    elif isinstance(explicit_sans, dict):
        for item in explicit_sans.get("dns", []) if isinstance(explicit_sans.get("dns"), list) else []:
            raw = str(item).strip()
            if raw:
                dns_names.append(raw)
        for item in explicit_sans.get("ip", []) if isinstance(explicit_sans.get("ip"), list) else []:
            raw = _inet_or_none(item)
            if raw:
                ip_names.append(raw)
    return {"dns": _unique_sorted(dns_names), "ip": _unique_sorted(ip_names)}


def _normal_sans(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {"dns": [], "ip": []}
    dns = [str(item).strip() for item in value.get("dns", []) if str(item).strip()] if isinstance(value.get("dns"), list) else []
    ip_values: list[str] = []
    for item in value.get("ip", []) if isinstance(value.get("ip"), list) else []:
        parsed = _inet_or_none(item)
        if parsed:
            ip_values.append(parsed)
    return {"dns": _unique_sorted(dns), "ip": _unique_sorted(ip_values)}


def _parse_san_json(raw: str) -> dict[str, list[str]]:
    if not raw.strip():
        return {"dns": [], "ip": []}
    try:
        return _normal_sans(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"SAN JSON inválido: {exc}") from exc


def _parse_openssl_san_text(text: str) -> dict[str, list[str]]:
    dns: list[str] = []
    ip_values: list[str] = []
    for raw in text.replace("\n", ",").split(","):
        item = raw.strip()
        if item.startswith("DNS:"):
            dns.append(item.split(":", 1)[1].strip())
        elif item.startswith("IP Address:"):
            parsed = _inet_or_none(item.split(":", 1)[1].strip())
            if parsed:
                ip_values.append(parsed)
    return {"dns": _unique_sorted(dns), "ip": _unique_sorted(ip_values)}


def _cert_sans_from_file(cert_file: Path) -> dict[str, list[str]]:
    if not cert_file.exists():
        raise click.ClickException(f"certificado não encontrado: {cert_file}")
    try:
        completed = subprocess.run(
            ["openssl", "x509", "-in", str(cert_file), "-noout", "-ext", "subjectAltName"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise click.ClickException("openssl não encontrado para ler SANs do certificado") from exc
    if completed.returncode != 0:
        raise click.ClickException(_redact_text(completed.stderr.strip() or "falha ao ler certificado"))
    return _parse_openssl_san_text(completed.stdout)


def _pki_san_drift(desired: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    desired_sans = _normal_sans(desired)
    observed_sans = _normal_sans(observed or {})
    missing_dns = sorted(set(desired_sans["dns"]) - set(observed_sans["dns"]))
    extra_dns = sorted(set(observed_sans["dns"]) - set(desired_sans["dns"]))
    missing_ip = sorted(set(desired_sans["ip"]) - set(observed_sans["ip"]))
    extra_ip = sorted(set(observed_sans["ip"]) - set(desired_sans["ip"]))
    needs_rotation = bool(missing_dns or extra_dns or missing_ip or extra_ip)
    return {
        "status": "drift" if needs_rotation else "in-sync",
        "needs_rotation": needs_rotation,
        "desired": desired_sans,
        "observed": observed_sans,
        "missing": {"dns": missing_dns, "ip": missing_ip},
        "extra": {"dns": extra_dns, "ip": extra_ip},
    }


def _pki_host_paths(host_id: str, host: dict[str, Any] | None = None) -> dict[str, Any]:
    config = _pki_service_tls_config(host or {})
    if host and _pki_is_windows_platform(host):
        base = str(config.get("local_store") or PKI_WINDOWS_TLS_BASE).replace("\\", "/").rstrip("/")
        host_base = f"{base}/{host_id}"
        ca_dir = f"{base}/ca"
        return {
            "host_tls_dir": host_base,
            "private_key": f"{host_base}/client.key.pem",
            "csr": f"{host_base}/client.csr.pem",
            "leaf_cert": f"{host_base}/client.crt.pem",
            "leaf_chain": f"{host_base}/chain.crt.pem",
            "ca_chain": f"{ca_dir}/ca-chain.crt.pem",
            "peer_dir": f"{base}/peers",
            "ca_base": ca_dir,
            "ca_files": [
                f"{ca_dir}/atius-vpn-service-root-ca.crt",
                f"{ca_dir}/atius-vpn-service-issuing-ca.crt",
            ],
            "trust_store": str(config.get("trust_store") or PKI_WINDOWS_TRUST_STORE),
        }
    host_base = f"{PKI_TLS_BASE}/{host_id}"
    return {
        "host_tls_dir": host_base,
        "private_key": f"{host_base}/server.key.pem",
        "csr": f"{host_base}/server.csr.pem",
        "leaf_cert": f"{host_base}/server.crt.pem",
        "leaf_chain": f"{host_base}/chain.crt.pem",
        "ca_chain": f"{PKI_TLS_BASE}/ca-chain.crt.pem",
        "peer_dir": f"{PKI_TLS_BASE}/peers",
        "ca_base": PKI_CA_BASE,
        "ca_files": list(PKI_CA_FILES),
        "trust_store": "/etc/ssl/certs",
    }


def _pki_host_identity(host_id: str, host: dict[str, Any], *, source: str) -> dict[str, Any]:
    access = _pki_access(host)
    ssh_target = str(access.get("ssh") or "").strip()
    if not ssh_target:
        vpn_ip = _primary_private_ip(access)
        if vpn_ip:
            ssh_target = f"ubuntu@{vpn_ip}"
    if not ssh_target:
        raise click.ClickException(f"host {host_id} sem access.ssh/vpn_ip para PKI")
    config = _pki_service_tls_config(host)
    mode = _pki_service_tls_mode(host)
    paths = _pki_host_paths(host_id, host)
    return {
        "host": host_id,
        "source": source,
        "ssh": ssh_target,
        "role": str(host.get("role") or ""),
        "status": str(host.get("status") or ""),
        "platform_os": _pki_platform_os(host),
        "aliases": _host_aliases(host),
        "sans": _pki_sans(host_id, host),
        "paths": paths,
        "ca_host": PKI_CA_HOST_ID,
        "service_tls_enabled": bool(config.get("enabled", mode != "disabled")),
        "service_tls_mode": mode,
        "trust_store": str(config.get("trust_store") or paths.get("trust_store") or ""),
        "auto_update": bool(config.get("auto_update", False)),
    }


def _load_db_host(host_id: str, *, env: dict[str, str]) -> dict[str, Any]:
    host_lit = _sql_literal(host_id)
    record = _psql_json(
        f"""
SELECT jsonb_build_object(
    'id', h.id,
    'role', h.role,
    'owner', h.owner,
    'status', h.status,
    'aliases', COALESCE(profile.value->'aliases', '[]'::jsonb),
    'access', jsonb_build_object(
        'ssh', h.ssh_target,
        'vpn_ip', h.vpn_ip::text,
        'vpn_ips', COALESCE(profile.value #> '{{access,vpn_ips}}', '[]'::jsonb),
        'oci_private_ip', profile.value #>> '{{access,oci_private_ip}}',
        'public_ip', h.public_ip::text,
        'legacy_vpn_ip', profile.value #>> '{{access,legacy_vpn_ip}}',
        'legacy_vpn_ips', COALESCE(profile.value #> '{{access,legacy_vpn_ips}}', '[]'::jsonb),
        'tailscale_ip', profile.value #>> '{{access,tailscale_ip}}'
    ),
    'platform', jsonb_build_object(
        'provider', h.provider,
        'os', h.os,
        'arch', h.arch
    ),
    'pki', COALESCE(profile.value->'pki', '{{}}'::jsonb)
)
FROM "TbHosts" h
LEFT JOIN "TbConfigItems" profile
  ON profile.host_id = h.id AND profile.key = 'inventory.host.profile'
WHERE h.id = {host_lit};
""",
        env=env,
    )
    if not record:
        raise click.ClickException(f"host não encontrado no DbOmniFleet: {host_id}")
    return record


def _load_pki_host(host_id: str, *, source: str, env: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
    if source == "db":
        return "db", _load_db_host(host_id, env=env or _db_env())
    try:
        path, host, _ = _load_host(host_id)
        return "inventory", host
    except click.ClickException:
        if source == "inventory":
            raise
    return "db", _load_db_host(host_id, env=env or _db_env())


def _pki_inventory_host_ids() -> list[str]:
    host_ids: list[str] = []
    for host_id, _, data, _ in _inventory_host_records(syncable_only=True):
        if str(data.get("status") or "").lower() != "active":
            continue
        config = _pki_service_tls_config(data)
        if config.get("enabled") is True or host_id.startswith("atius-srv-") or host_id.endswith("-srv"):
            host_ids.append(host_id)
    return host_ids


def _pki_inventory_host_data(host_id: str) -> dict[str, Any]:
    try:
        _, host, _ = _load_host(host_id)
        return host
    except click.ClickException:
        return {}


def _pki_command_key(action: str, identity: dict[str, Any]) -> str:
    if "windows" in str(identity.get("platform_os") or "") and action in {"preflight", "install-ca", "verify", "reconcile"}:
        return f"omni.trust-pki.windows.{action}"
    return f"omni.trust-pki.{action}"


def _pki_agent_args(action: str, identity: dict[str, Any], *, execute: bool) -> list[str]:
    args: list[str] = []
    if action == "issue-host":
        args.extend(["--target-host", str(identity["host"])])
    if action in {"ensure-key-csr", "issue-host", "reconcile"}:
        args.extend(["--san-json", json.dumps(identity["sans"], sort_keys=True)])
    if execute and action in {"init-ca", "ensure-key-csr", "issue-host", "install-ca", "install-leaf"}:
        args.append("--execute")
    return args


def _pki_plan_command(
    action: str,
    identity: dict[str, Any],
    *,
    priority: int,
    execute: bool,
    target_host: str | None = None,
) -> dict[str, Any]:
    host_id = str(identity["host"])
    return {
        "stage": action,
        "target_host": target_host or host_id,
        "command_key": _pki_command_key(action, identity),
        "command_args": _pki_agent_args(action, identity, execute=execute),
        "priority": priority,
    }


def _pki_command_plan(identity: dict[str, Any], *, execute: bool) -> list[dict[str, Any]]:
    host_id = str(identity["host"])
    if identity.get("service_tls_mode") == "trust-client":
        return [
            _pki_plan_command("preflight", identity, priority=40, execute=execute),
            _pki_plan_command("install-ca", identity, priority=43, execute=execute),
            _pki_plan_command("verify", identity, priority=45, execute=execute),
        ]
    return [
        _pki_plan_command("preflight", identity, priority=40, execute=execute),
        _pki_plan_command("ensure-key-csr", identity, priority=41, execute=execute),
        _pki_plan_command("issue-host", identity, priority=42, execute=execute, target_host=PKI_CA_HOST_ID),
        _pki_plan_command("install-ca", identity, priority=43, execute=execute),
        _pki_plan_command("install-leaf", identity, priority=44, execute=execute),
        _pki_plan_command("verify", identity, priority=45, execute=execute),
    ]


def _pki_rotation_plan(identity: dict[str, Any], *, execute: bool, include_ca: bool = False) -> list[dict[str, Any]]:
    host_id = str(identity["host"])
    if identity.get("service_tls_mode") == "trust-client":
        return [
            _pki_plan_command("preflight", identity, priority=50, execute=execute),
            _pki_plan_command("install-ca", identity, priority=53, execute=execute),
            _pki_plan_command("verify", identity, priority=55, execute=execute),
        ]
    commands = [
        _pki_plan_command("preflight", identity, priority=50, execute=execute),
        _pki_plan_command("ensure-key-csr", identity, priority=51, execute=execute),
        _pki_plan_command("issue-host", identity, priority=52, execute=execute, target_host=PKI_CA_HOST_ID),
    ]
    if include_ca:
        commands.append(
            _pki_plan_command("install-ca", identity, priority=53, execute=execute)
        )
    commands.extend(
        [
            _pki_plan_command("install-leaf", identity, priority=54, execute=execute),
            _pki_plan_command("verify", identity, priority=55, execute=execute),
        ]
    )
    return commands


def _pki_render_host(host_id: str, *, source: str, env: dict[str, str] | None = None, execute: bool = False) -> dict[str, Any]:
    loaded_source, host = _load_pki_host(host_id, source=source, env=env)
    resolved_host = _host_id(host, host_id)
    identity = _pki_host_identity(resolved_host, host, source=loaded_source)
    identity["commands"] = _pki_command_plan(identity, execute=execute)
    return identity


def _queue_update_record(
    *,
    host_id: str,
    program: str,
    desired_version: str,
    command_key: str,
    command_args: list[str],
    requested_by: str,
    requested_from_host: str,
    approve: bool,
    priority: int,
    dry_run_payload: dict[str, Any],
    env: dict[str, str],
) -> dict[str, Any]:
    approval_state = "approved" if approve else "pending"
    execution_state = "queued" if approve else "not-started"
    _command_template(command_key, host_id=host_id, env=env)
    approved_by_sql = _sql_literal(requested_by) if approve else "NULL"
    approved_at_sql = "now()" if approve else "NULL"
    idempotency = f"{host_id}:{program}:{desired_version}:{command_key}:{json.dumps(command_args, sort_keys=True)}"
    query = f"""
WITH program AS (
    INSERT INTO "TbPrograms" (host_id, name, install_type, current_version, source, managed_by, update_policy, observed_at)
    VALUES ({_sql_literal(host_id)}, {_sql_literal(program)}, 'omni-module', NULL, 'trust-pki', 'omni-srv-admin', 'plan-first', now())
    ON CONFLICT (host_id, name, install_type) DO UPDATE SET
        source = EXCLUDED.source,
        managed_by = EXCLUDED.managed_by,
        update_policy = EXCLUDED.update_policy,
        observed_at = now()
    RETURNING id
),
plan AS (
    INSERT INTO "TbUpdatePlans" (
        host_id, program_id, desired_version, dry_run_output, approval_state,
        approved_by, approved_at,
        execution_state, target_command, command_args, execution_profile,
        requested_by, requested_from_host, priority, idempotency_key
    )
    SELECT
        {_sql_literal(host_id)}, program.id, {_sql_literal(desired_version)},
        {_json_literal(dry_run_payload)}::jsonb, {_sql_literal(approval_state)},
        {approved_by_sql}, {approved_at_sql},
        {_sql_literal(execution_state)}, {_sql_literal(command_key)}, {_json_literal(command_args)}::jsonb,
        'interactive', {_sql_literal(requested_by)}, {_sql_literal(requested_from_host)}, {int(priority)},
        encode(digest({_sql_literal(idempotency)}, 'sha256'), 'hex')
    FROM program
    ON CONFLICT (idempotency_key) DO UPDATE SET
        dry_run_output = EXCLUDED.dry_run_output,
        approval_state = EXCLUDED.approval_state,
        approved_by = EXCLUDED.approved_by,
        approved_at = EXCLUDED.approved_at,
        execution_state = CASE
            WHEN "TbUpdatePlans".execution_state IN ('succeeded', 'claimed', 'running') THEN "TbUpdatePlans".execution_state
            ELSE EXCLUDED.execution_state
        END,
        updated_at = now()
    RETURNING id, host_id, desired_version, approval_state, execution_state, target_command, command_args, priority, created_at
)
SELECT jsonb_build_object(
    'id', id,
    'host', host_id,
    'desired_version', desired_version,
    'approval_state', approval_state,
    'execution_state', execution_state,
    'target_command', target_command,
    'command_args', command_args,
    'priority', priority,
    'created_at', created_at
) FROM plan;
"""
    record = _psql_json(query, env=env)
    return record or {}


def _emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            click.echo(f"{key}:")
            click.echo(json.dumps(value, indent=2, sort_keys=True))
        else:
            click.echo(f"{key}: {value}")


def _redact_text(value: str) -> str:
    lowered = value.lower()
    if any(key in lowered for key in SENSITIVE_KEYS):
        return "***REDACTED***"
    return value


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if key in SENSITIVE_KEYS else _redact(nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _append_audit_event(event: dict[str, Any]) -> None:
    AUDIT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_EVENTS.open("a", encoding="utf-8").write(json.dumps(_redact(event), sort_keys=True) + "\n")


def _load_env_file(path: Path = FLEET_DB_ENV) -> dict[str, str]:
    try:
        return load_env_file(path)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


def _db_env(path: Path = FLEET_DB_ENV) -> dict[str, str]:
    loaded = _load_env_file(path)
    host = loaded.get("PGHOST", "")
    port = loaded.get("PGPORT", "")
    allowed_pgbouncer_endpoints = (PGBOUNCER_ENDPOINT, *PGBOUNCER_LEGACY_ENDPOINTS)
    if (host, port) not in allowed_pgbouncer_endpoints:
        legacy = ", ".join(f"{item[0]}:{item[1]}" for item in PGBOUNCER_LEGACY_ENDPOINTS)
        raise click.ClickException(
            f"DB endpoint inválido para fleet: {host}:{port}; esperado PgBouncer "
            f"{PGBOUNCER_ENDPOINT[0]}:{PGBOUNCER_ENDPOINT[1]}"
            + (f" (legado permitido durante cutover: {legacy})" if legacy else "")
        )
    required = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER")
    missing = [key for key in required if not loaded.get(key)]
    if missing:
        raise click.ClickException(f"fleet DB env incompleto: {','.join(missing)}")
    local_hostname = socket.gethostname().lower()
    if (
        (loaded.get("PGHOST"), loaded.get("PGPORT")) in allowed_pgbouncer_endpoints
        and local_hostname.startswith("atius-srv-1")
    ):
        # PgBouncer is the declared fleet endpoint, but on SRV-1 it is bound
        # to loopback. Local omni commands should still read DbOmniFleet.
        loaded = {**loaded, "OMNI_FLEET_DB_DECLARED_HOST": loaded["PGHOST"], "PGHOST": "127.0.0.1"}
    return {**os.environ, **loaded}


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _json_literal(value: Any) -> str:
    return _sql_literal(json.dumps(value, sort_keys=True, default=str))


def _psql(query: str, *, env: dict[str, str] | None = None, timeout: int = 20) -> str:
    psql_env = _db_env() if env is None else env
    try:
        return run_sql(query, env=psql_env, timeout=timeout)
    except RuntimeError as exc:
        raise click.ClickException(_redact_text(str(exc))) from exc


def _psql_json(query: str, *, env: dict[str, str] | None = None, timeout: int = 20) -> Any:
    output = _psql(query, env=env, timeout=timeout)
    if not output:
        return None
    return json.loads(output.splitlines()[-1])


def _default_host_id() -> str:
    env_host = os.environ.get("OMNI_HOST_ID")
    if env_host:
        return env_host
    hostname = socket.gethostname().lower()
    alias_map: dict[str, str] = {}
    hosts_dir = _hosts_dir()
    if hosts_dir.exists():
        for path in sorted(hosts_dir.glob("*.yaml")):
            data = _simple_yaml(path.read_text())
            host_id = _host_id(data, path.stem)
            alias_map[host_id.lower()] = host_id
            for alias in data.get("aliases", []) if isinstance(data.get("aliases"), list) else []:
                alias_map[str(alias).lower()] = host_id
    return alias_map.get(hostname, hostname)


def _proc_pressure(resource: str) -> dict[str, float | None]:
    path = Path("/proc/pressure") / resource
    result: dict[str, float | None] = {"some_avg10": None, "full_avg10": None}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        scope = parts[0]
        for part in parts[1:]:
            if part.startswith("avg10="):
                try:
                    result[f"{scope}_avg10"] = float(part.split("=", 1)[1])
                except ValueError:
                    result[f"{scope}_avg10"] = None
    return result


def _meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    path = Path("/proc/meminfo")
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        key, raw = line.split(":", 1)
        amount = raw.strip().split()[0]
        try:
            values[key] = int(amount) * 1024
        except ValueError:
            continue
    return values


def _diskstats() -> dict[str, int]:
    path = Path("/proc/diskstats")
    totals = {"read_bytes": 0, "write_bytes": 0}
    if not path.exists():
        return totals
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        device = parts[2]
        if device.startswith(("loop", "ram", "sr")):
            continue
        try:
            sectors_read = int(parts[5])
            sectors_written = int(parts[9])
        except ValueError:
            continue
        totals["read_bytes"] += sectors_read * 512
        totals["write_bytes"] += sectors_written * 512
    return totals


def _service_health() -> dict[str, str]:
    candidates = [
        "omni-fleet-agent.service",
        "resource-governor-watchdog.service",
        "resource-governor-patcher.service",
        "pgbouncer.service",
        "postgresql.service",
    ]
    health: dict[str, str] = {}
    for unit in candidates:
        try:
            completed = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (FileNotFoundError, OSError):
            return health
        state = completed.stdout.strip() or "unknown"
        if completed.returncode == 0 or state not in {"unknown", "inactive"}:
            health[unit] = state
    return health


def _resource_health(load_1m: float | None, cpu_count: int, memory_used_pct: float | None, disk_used_pct: float | None) -> str:
    if disk_used_pct is not None and disk_used_pct >= 95:
        return "critical"
    if memory_used_pct is not None and memory_used_pct >= 92:
        return "critical"
    if load_1m is not None and load_1m >= max(cpu_count * 3, 6):
        return "critical"
    if disk_used_pct is not None and disk_used_pct >= 88:
        return "degraded"
    if memory_used_pct is not None and memory_used_pct >= 85:
        return "degraded"
    if load_1m is not None and load_1m >= max(cpu_count * 2, 4):
        return "degraded"
    return "healthy"


def _collect_telemetry(host_id: str) -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    load_1m = load_5m = load_15m = None
    try:
        load_1m, load_5m, load_15m = os.getloadavg()
    except (AttributeError, OSError):
        pass
    mem = _meminfo()
    mem_total = mem.get("MemTotal")
    mem_available = mem.get("MemAvailable")
    swap_total = mem.get("SwapTotal")
    swap_free = mem.get("SwapFree")
    memory_used_pct = None
    swap_used_pct = None
    if mem_total and mem_available is not None:
        memory_used_pct = round(((mem_total - mem_available) / mem_total) * 100, 2)
    if swap_total:
        swap_used_pct = round(((swap_total - (swap_free or 0)) / swap_total) * 100, 2)
    disk = shutil.disk_usage("/")
    disk_used_pct = round((disk.used / disk.total) * 100, 2)
    uptime_seconds = None
    uptime_path = Path("/proc/uptime")
    if uptime_path.exists():
        try:
            uptime_seconds = int(float(uptime_path.read_text().split()[0]))
        except (ValueError, IndexError):
            uptime_seconds = None
    health = _resource_health(load_1m, cpu_count, memory_used_pct, disk_used_pct)
    return {
        "host": host_id,
        "agent_version": FLEET_AGENT_VERSION,
        "status": health,
        "health": health,
        "last_contact": _now(),
        "hostname": socket.gethostname(),
        "cpu": {
            "count": cpu_count,
            "load_1m": round(load_1m, 2) if load_1m is not None else None,
            "load_5m": round(load_5m, 2) if load_5m is not None else None,
            "load_15m": round(load_15m, 2) if load_15m is not None else None,
            "pressure": _proc_pressure("cpu"),
        },
        "memory": {
            "total_bytes": mem_total,
            "available_bytes": mem_available,
            "used_percent": memory_used_pct,
            "swap_used_percent": swap_used_pct,
            "pressure": _proc_pressure("memory"),
        },
        "disk": {
            "root_total_bytes": disk.total,
            "root_used_bytes": disk.used,
            "root_free_bytes": disk.free,
            "root_used_percent": disk_used_pct,
            "io": _diskstats(),
            "pressure": _proc_pressure("io"),
        },
        "service_health": _service_health(),
        "uptime_seconds": uptime_seconds,
        "generated_at": _now(),
    }


def _save_heartbeat_cache(payload: dict[str, Any]) -> None:
    host_id = str(payload["host"])
    _write_json(HEARTBEAT_DIR / f"{host_id}.json", payload)
    _write_json(TELEMETRY_DIR / f"{host_id}.json", payload)


def _write_heartbeat_db(payload: dict[str, Any], *, env: dict[str, str] | None = None) -> None:
    host_id = str(payload["host"])
    cpu = payload.get("cpu", {}) if isinstance(payload.get("cpu"), dict) else {}
    memory = payload.get("memory", {}) if isinstance(payload.get("memory"), dict) else {}
    disk = payload.get("disk", {}) if isinstance(payload.get("disk"), dict) else {}
    disk_io = disk.get("io", {}) if isinstance(disk.get("io"), dict) else {}
    query = f"""
INSERT INTO "TbNodes" (host_id, install_mode, agent_version, health_status, last_heartbeat_at, last_heartbeat)
VALUES ({_sql_literal(host_id)}, CASE WHEN {_sql_literal(host_id)} = 'atius-srv-1' THEN 'server' ELSE 'node' END,
        {_sql_literal(FLEET_AGENT_VERSION)}, {_sql_literal(payload.get("health"))}, now(), {_json_literal(payload)}::jsonb)
ON CONFLICT (host_id) DO UPDATE SET
    agent_version = EXCLUDED.agent_version,
    health_status = EXCLUDED.health_status,
    last_heartbeat_at = EXCLUDED.last_heartbeat_at,
    last_heartbeat = EXCLUDED.last_heartbeat,
    updated_at = now();

INSERT INTO "TbNodeTelemetry" (
    host_id, observer_host_id, agent_id, health_status, cpu_count, load_1m, load_5m, load_15m,
    memory_total_bytes, memory_available_bytes, memory_used_percent, swap_used_percent,
    disk_root_total_bytes, disk_root_used_bytes, disk_root_used_percent,
    disk_read_bytes, disk_write_bytes, service_health, raw
) VALUES (
    {_sql_literal(host_id)}, {_sql_literal(host_id)}, {_sql_literal(socket.gethostname())}, {_sql_literal(payload.get("health"))},
    {int(cpu.get("count") or 0)}, {cpu.get("load_1m") if cpu.get("load_1m") is not None else "NULL"},
    {cpu.get("load_5m") if cpu.get("load_5m") is not None else "NULL"},
    {cpu.get("load_15m") if cpu.get("load_15m") is not None else "NULL"},
    {memory.get("total_bytes") if memory.get("total_bytes") is not None else "NULL"},
    {memory.get("available_bytes") if memory.get("available_bytes") is not None else "NULL"},
    {memory.get("used_percent") if memory.get("used_percent") is not None else "NULL"},
    {memory.get("swap_used_percent") if memory.get("swap_used_percent") is not None else "NULL"},
    {disk.get("root_total_bytes") if disk.get("root_total_bytes") is not None else "NULL"},
    {disk.get("root_used_bytes") if disk.get("root_used_bytes") is not None else "NULL"},
    {disk.get("root_used_percent") if disk.get("root_used_percent") is not None else "NULL"},
    {disk_io.get("read_bytes") if disk_io.get("read_bytes") is not None else "NULL"},
    {disk_io.get("write_bytes") if disk_io.get("write_bytes") is not None else "NULL"},
    {_json_literal(payload.get("service_health", {}))}::jsonb,
    {_json_literal(payload)}::jsonb
);
"""
    _psql(query, env=env)


def _write_program_observations_db(payload: dict[str, Any], *, env: dict[str, str] | None = None) -> None:
    statements: list[str] = []
    for record in payload.get("programs", []):
        if not isinstance(record, dict):
            continue
        host_id = str(record.get("host") or payload.get("host") or "")
        name = str(record.get("name") or "")
        install_type = str(record.get("install_type") or "unknown")
        if not host_id or not name:
            continue
        manager = str(record.get("manager") or "unknown")
        current_version = str(record.get("current_version") or "unknown")
        source = str(record.get("source") or manager)
        statements.append(
            f"""
WITH program AS (
    INSERT INTO "TbPrograms" (host_id, name, install_type, current_version, source, managed_by, update_policy, observed_at)
    VALUES ({_sql_literal(host_id)}, {_sql_literal(name)}, {_sql_literal(install_type)},
            {_sql_literal(current_version)}, {_sql_literal(source)}, {_sql_literal('collector:' + manager)}, 'plan-first', now())
    ON CONFLICT (host_id, name, install_type) DO UPDATE SET
        current_version = EXCLUDED.current_version,
        source = EXCLUDED.source,
        managed_by = EXCLUDED.managed_by,
        observed_at = now()
    RETURNING id
)
INSERT INTO "TbVersions" (program_id, current_version, desired_version, policy, pinned, updated_at)
SELECT id, {_sql_literal(current_version)}, NULL, 'observed', false, now()
FROM program;
"""
        )
    if statements:
        _psql("\n".join(statements), env=env)


def _write_omni_version_db(payload: dict[str, Any], *, env: dict[str, str] | None = None) -> None:
    host_id = str(payload.get("host") or "")
    component = str(payload.get("component") or "omni-srv-admin")
    if not host_id:
        raise click.ClickException("payload de versão sem host")
    query = f"""
INSERT INTO "TbVersion" (
    host_id, component, installed_version, git_branch, git_commit, git_dirty,
    github_version, github_commit, source, observed_at, metadata
) VALUES (
    {_sql_literal(host_id)},
    {_sql_literal(component)},
    {_sql_literal(payload.get("installed_version"))},
    {_sql_literal(payload.get("git_branch"))},
    {_sql_literal(payload.get("git_commit"))},
    {'true' if bool(payload.get("git_dirty")) else 'false'},
    {_sql_literal(payload.get("github_version"))},
    {_sql_literal(payload.get("github_commit"))},
    {_sql_literal(payload.get("source") or "omni-fleet-agent")},
    now(),
    {_json_literal(payload.get("metadata", {}))}::jsonb
)
ON CONFLICT (host_id, component) DO UPDATE SET
    installed_version = EXCLUDED.installed_version,
    git_branch = EXCLUDED.git_branch,
    git_commit = EXCLUDED.git_commit,
    git_dirty = EXCLUDED.git_dirty,
    github_version = EXCLUDED.github_version,
    github_commit = EXCLUDED.github_commit,
    source = EXCLUDED.source,
    observed_at = now(),
    metadata = EXCLUDED.metadata;
"""
    _psql(query, env=env)


def _omni_command_key_for_host(host: dict[str, Any]) -> str:
    platform_os = _nested(host, "platform", "os", "").lower()
    if "windows" in platform_os:
        return "omni.self-update.windows"
    return "omni.self-update.linux"


def _write_profile_db(profile: dict[str, Any], *, env: dict[str, str] | None = None) -> None:
    profile_id = str(profile["profile_id"])
    statements = [
        f"""
INSERT INTO "TbDesiredStateProfiles" (id, title, scope, owner, status, source, metadata)
VALUES (
    {_sql_literal(profile_id)}, {_sql_literal(profile.get("title"))}, {_sql_literal(profile.get("scope"))},
    {_sql_literal(profile.get("owner"))}, {_sql_literal(profile.get("status"))}, {_sql_literal(profile.get("source"))},
    {_json_literal(profile.get("metadata", {}))}::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    scope = EXCLUDED.scope,
    owner = EXCLUDED.owner,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    metadata = EXCLUDED.metadata,
    updated_at = now();

DELETE FROM "TbDesiredStateRules"
WHERE profile_id = {_sql_literal(profile_id)};
"""
    ]
    for rule in profile.get("rules", []):
        if not isinstance(rule, dict):
            continue
        statements.append(
            f"""
INSERT INTO "TbDesiredStateRules" (
    profile_id, target_kind, target_name, rule_mode, desired_version,
    manager, source, selector, assertions, metadata
) VALUES (
    {_sql_literal(profile_id)}, {_sql_literal(rule.get("target_kind"))}, {_sql_literal(rule.get("target_name"))},
    {_sql_literal(rule.get("rule_mode"))}, {_sql_literal(rule.get("desired_version"))},
    {_sql_literal(rule.get("manager"))}, {_sql_literal(rule.get("source"))},
    {_json_literal(rule.get("selector", {}))}::jsonb,
    {_json_literal(rule.get("assertions", {}))}::jsonb,
    {_json_literal(rule.get("metadata", {}))}::jsonb
);
"""
        )
    _psql("\n".join(statements), env=env)


def _write_security_report_db(report: dict[str, Any], *, env: dict[str, str] | None = None) -> None:
    query = f"""
INSERT INTO "TbSecurityFindings" (
    host_id, source, finding_type, package_name, cve_id, usn_id,
    priority, origin, status, fix_available, evidence
) VALUES (
    {_sql_literal(report.get("host"))}, 'ubuntu-pro-client', 'summary', NULL, NULL, NULL,
    NULL, NULL, 'observed', NULL, {_json_literal(_redact(report))}::jsonb
);
"""
    _psql(query, env=env)


def _command_template(command_key: str, *, host_id: str | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    if env is not None:
        query = f"""
SELECT jsonb_build_object(
    'command_key', command_key,
    'description', description,
    'invocation', local_invocation,
    'default_profile', default_profile,
    'requires_approval', requires_approval,
    'timeout_seconds', timeout_seconds,
    'allowed_host_ids', allowed_host_ids,
    'metadata', metadata,
    'enabled', enabled
)
FROM "TbFleetCommands"
WHERE command_key = {_sql_literal(command_key)} AND enabled = true;
"""
        record = _psql_json(query, env=env)
        if record:
            if str(record.get("invocation") or "").startswith("internal:"):
                record["internal"] = str(record["invocation"]).split(":", 1)[1]
            allowed = record.get("allowed_host_ids") or []
            if host_id and allowed and host_id not in allowed:
                raise click.ClickException(f"comando {command_key} não permitido para {host_id}")
            return record
    if command_key in LOCAL_COMMANDS:
        record = {"command_key": command_key, **LOCAL_COMMANDS[command_key]}
        allowed = record.get("allowed_host_ids") or []
        if host_id and allowed and host_id not in allowed:
            raise click.ClickException(f"comando {command_key} não permitido para {host_id}")
        return record
    raise click.ClickException(f"comando não permitido pelo fleet agent: {command_key}")


def _render_argv(template: dict[str, Any], plan: dict[str, Any], command_args: list[str]) -> list[str]:
    if "argv" in template:
        raw_argv = template["argv"]
        argv = [str(item) for item in raw_argv]
    else:
        invocation = str(template.get("invocation") or "")
        if not invocation:
            raise click.ClickException(f"comando sem invocation: {template.get('command_key')}")
        argv = shlex.split(invocation)
    if len(argv) >= 2 and Path(argv[0]).name in {"sh", "bash"} and argv[1] == "-c":
        raise click.ClickException("fleet agent recusa shell string; registre argv/script allowlisted")
    values = {
        "repo": str(REPO),
        "host_id": str(plan.get("host_id") or plan.get("host") or ""),
        "desired_version": str(plan.get("desired_version") or ""),
    }
    rendered = [item.format(**values) for item in argv]
    rendered.extend(command_args)
    return rendered


def _execute_plan(plan: dict[str, Any], *, apply_changes: bool, env: dict[str, str] | None = None) -> dict[str, Any]:
    host_id = str(plan.get("host_id") or plan.get("host") or _default_host_id())
    command_key = str(plan.get("target_command") or plan.get("command_key") or "")
    if not command_key:
        raise click.ClickException("update plan sem target_command/command_key")
    command_args = plan.get("command_args") or []
    if isinstance(command_args, str):
        command_args = json.loads(command_args)
    if not isinstance(command_args, list):
        raise click.ClickException("command_args deve ser lista JSON")
    template = _command_template(command_key, host_id=host_id, env=env)
    approval_state = str(plan.get("approval_state") or "pending")
    if template.get("requires_approval", True) and approval_state != "approved":
        raise click.ClickException(f"update plan não aprovado: {approval_state}")
    if template.get("internal") == "heartbeat":
        payload = _collect_telemetry(host_id)
        _save_heartbeat_cache(payload)
        if apply_changes and env is not None:
            _write_heartbeat_db(payload, env=env)
        return {
            "plan_id": plan.get("id"),
            "host": host_id,
            "command_key": command_key,
            "status": "succeeded",
            "dry_run": not apply_changes,
            "stdout": "heartbeat collected",
            "stderr": "",
            "returncode": 0,
            "telemetry_health": payload["health"],
            "finished_at": _now(),
        }
    argv = _render_argv(template, plan, [str(item) for item in command_args])
    if not apply_changes:
        return {
            "plan_id": plan.get("id"),
            "host": host_id,
            "command_key": command_key,
            "status": "planned",
            "dry_run": True,
            "argv": argv,
            "finished_at": _now(),
        }
    timeout = int(template.get("timeout_seconds") or 900)
    started = _now()
    completed = subprocess.run(
        argv,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "OMNI_SRV_ADMIN": str(REPO), "PYTHONPATH": str(REPO / "cli")},
    )
    status = "succeeded" if completed.returncode == 0 else "failed"
    return {
        "plan_id": plan.get("id"),
        "host": host_id,
        "command_key": command_key,
        "status": status,
        "dry_run": False,
        "returncode": completed.returncode,
        "stdout": _redact_text(completed.stdout[-4000:]),
        "stderr": _redact_text(completed.stderr[-4000:]),
        "started_at": started,
        "finished_at": _now(),
    }


def _claim_next_plan(host_id: str, *, env: dict[str, str]) -> dict[str, Any] | None:
    owner = f"{socket.gethostname()}:{os.getpid()}"
    query = f"""
WITH candidate AS (
    SELECT id
    FROM "TbUpdatePlans"
    WHERE host_id = {_sql_literal(host_id)}
      AND approval_state = 'approved'
      AND approved_by IS NOT NULL
      AND approved_at IS NOT NULL
      AND execution_state IN ('queued', 'retry')
      AND (lease_expires_at IS NULL OR lease_expires_at < now())
    ORDER BY priority ASC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
),
claimed AS (
    UPDATE "TbUpdatePlans" p
    SET execution_state = 'claimed',
        lease_owner = {_sql_literal(owner)},
        executor_host_id = {_sql_literal(host_id)},
        lease_expires_at = now() + interval '5 minutes',
        attempt_count = attempt_count + 1,
        started_at = COALESCE(started_at, now()),
        updated_at = now()
    FROM candidate
    WHERE p.id = candidate.id
    RETURNING p.*
)
SELECT COALESCE(
    (SELECT jsonb_build_object(
        'id', id,
        'host_id', host_id,
        'desired_version', desired_version,
        'approval_state', approval_state,
        'execution_state', execution_state,
        'target_command', target_command,
        'command_args', command_args,
        'execution_profile', execution_profile,
        'lease_owner', lease_owner
    ) FROM claimed),
    'null'::jsonb
);
"""
    return _psql_json(query, env=env)


def _finish_plan_db(plan_id: str, result: dict[str, Any], *, env: dict[str, str]) -> None:
    execution_state = "succeeded" if result.get("status") == "succeeded" else "failed"
    query = f"""
UPDATE "TbUpdatePlans"
SET execution_state = {_sql_literal(execution_state)},
    execution_output = {_json_literal(_redact(result))}::jsonb,
    finished_at = now(),
    lease_owner = NULL,
    lease_expires_at = NULL,
    updated_at = now()
WHERE id = {_sql_literal(plan_id)}::uuid;

INSERT INTO "TbAuditEvents" (actor, host_id, action, target, result, metadata)
VALUES (
    {_sql_literal("omni-fleet-agent")},
    {_sql_literal(result.get("host"))},
    'update-plan.execute',
    {_sql_literal(result.get("command_key"))},
    {_sql_literal(execution_state)},
    {_json_literal(_redact(result))}::jsonb
);
"""
    _psql(query, env=env)


def _monitor_payload(*, use_db: bool) -> dict[str, Any]:
    hosts_dir = _hosts_dir()
    hosts: list[dict[str, Any]] = []
    db_error = None
    if use_db:
        try:
            query = """
WITH latest_telemetry AS (
    SELECT DISTINCT ON (host_id)
        host_id, observed_at, health_status, load_1m, load_5m,
        memory_used_percent, disk_root_used_percent, disk_read_bytes, disk_write_bytes,
        service_health
    FROM "TbNodeTelemetry"
    ORDER BY host_id, observed_at DESC
)
SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'host', h.id,
    'role', h.role,
    'status', COALESCE(n.health_status, h.status),
    'last_contact', n.last_heartbeat_at,
    'agent_version', n.agent_version,
    'load_1m', lt.load_1m,
    'load_5m', lt.load_5m,
    'memory_used_percent', lt.memory_used_percent,
    'disk_root_used_percent', lt.disk_root_used_percent,
    'disk_read_bytes', lt.disk_read_bytes,
    'disk_write_bytes', lt.disk_write_bytes,
    'service_health', COALESCE(lt.service_health, '{}'::jsonb)
) ORDER BY h.id), '[]'::jsonb)
FROM "TbHosts" h
LEFT JOIN "TbNodes" n ON n.host_id = h.id
LEFT JOIN latest_telemetry lt ON lt.host_id = h.id;
"""
            hosts = _psql_json(query) or []
        except Exception as exc:  # local fallback keeps monitoring useful during DB outage
            db_error = _redact_text(str(exc))
    if not hosts and hosts_dir.exists():
        for path in sorted(hosts_dir.glob("*.yaml")):
            data = _simple_yaml(path.read_text())
            heartbeat = _heartbeat_payload(data, path)
            hosts.append(
                {
                    "host": heartbeat["host"],
                    "role": data.get("role", "?"),
                    "status": heartbeat["status"],
                    "last_contact": heartbeat["last_contact"],
                    "agent_version": heartbeat["agent_version"],
                    "load_1m": None,
                    "load_5m": None,
                    "memory_used_percent": None,
                    "disk_root_used_percent": None,
                    "service_health": heartbeat["service_health"],
                }
            )
    return {
        "source": "database" if use_db and not db_error else "local-cache",
        "db_error": db_error,
        "host_count": len(hosts),
        "hosts": hosts,
        "generated_at": _now(),
    }


def _install_plan(mode: str, host: dict[str, Any], path: Path) -> dict[str, Any]:
    host_id = _host_id(host, path.stem)
    shared_steps = [
        "validate inventory projection",
        "write audit event with actor, host, action and target",
        "run only after explicit operator approval",
    ]
    if mode == "server":
        steps = [
            "install control-plane package and service unit",
            "provision PostgreSQL owned by the control-plane server",
            "apply versioned migrations from modules/fleet-control-plane/migrations",
            "configure PgBouncer as the only client/node database endpoint",
            "enable logical dump/restore runbook before first production data",
            "import inventory/hosts as the source-of-truth projection",
        ]
    else:
        steps = [
            "install lightweight omni fleet node agent",
            "configure node to reach the control-plane database through PgBouncer",
            "register heartbeat timer and local status collector",
            "register program inventory collector",
            "refuse direct PostgreSQL connection strings",
            "execute only approved update plans",
        ]
    return {
        "mode": mode,
        "host": host_id,
        "inventory_file": str(path),
        "dry_run": True,
        "apply_supported": False,
        "status": "planned",
        "steps": steps + shared_steps,
        "rollback": [
            "stop and disable the generated service unit",
            "remove PgBouncer client credentials for the host",
            "mark node inactive in control-plane state",
            "keep audit events and logical dumps for review",
        ],
        "blocked_until": [
            "storage for secrets/license material is approved outside git/log/vault",
            "host preflight is confirmed immediately before live execution",
            "operator approves CLI-only vs API+CLI implementation shape",
        ],
    }


def _heartbeat_payload(host: dict[str, Any], path: Path) -> dict[str, Any]:
    host_id = _host_id(host, path.stem)
    heartbeat_file = HEARTBEAT_DIR / f"{host_id}.json"
    status = "offline"
    last_contact = None
    health = "missing-heartbeat"
    agent_version = "not-installed"
    disk = None
    memory = None
    service_health = {}
    uptime = None
    if heartbeat_file.exists():
        try:
            heartbeat = json.loads(heartbeat_file.read_text())
            status = str(heartbeat.get("status") or "unknown")
            last_contact = heartbeat.get("last_contact")
            health = str(heartbeat.get("health") or "unknown")
            agent_version = str(heartbeat.get("agent_version") or "unknown")
            disk = heartbeat.get("disk")
            memory = heartbeat.get("memory")
            service_health = heartbeat.get("service_health") if isinstance(heartbeat.get("service_health"), dict) else {}
            uptime = heartbeat.get("uptime_seconds") or heartbeat.get("uptime")
        except Exception:
            status = "degraded"
            health = "invalid-heartbeat-file"
    return {
        "host": host_id,
        "agent_version": agent_version,
        "os": _nested(host, "platform", "os", "unknown"),
        "arch": _nested(host, "platform", "arch", "unknown"),
        "uptime": uptime,
        "disk": disk,
        "memory": memory,
        "service_health": service_health,
        "status": status,
        "health": health,
        "last_contact": last_contact,
        "generated_at": _now(),
    }


def _program_records(host: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    host_id = _host_id(host, path.stem)
    records = []
    modules = host.get("modules") if isinstance(host.get("modules"), list) else []
    for module in modules:
        records.append(
            {
                "host": host_id,
                "program": str(module),
                "kind": "omni-module",
                "install_type": "omni-module",
                "current_version": "unknown",
                "desired_version": "inventory-managed",
                "source": "inventory/hosts",
                "managed_by": "omni-srv-admin",
                "update_policy": "plan-first",
            }
        )
    apps = host.get("apps")
    if apps is None:
        apps = []
    if not isinstance(apps, list):
        apps = []
    for app in apps:
        if not isinstance(app, dict):
            continue
        app_id = str(app.get("id") or app.get("name") or "")
        if not app_id:
            continue
        record: dict[str, object] = {
            "host": host_id,
            "program": app_id,
            "kind": "app",
            "runtime": str(app.get("runtime") or "unknown"),
            "install_type": str(app.get("install_type") or "unknown"),
            "current_version": str(app.get("current_version") or "unknown"),
            "desired_version": str(app.get("desired_version") or "inventory-managed"),
            "source": str(app.get("source") or "inventory/hosts"),
            "managed_by": str(app.get("managed_by") or "omni-srv-admin"),
            "update_policy": str(app.get("update_policy") or "plan-first"),
            "last_audited": str(app.get("last_audited") or ""),
        }
        if app.get("public_url"):
            record["public_url"] = str(app["public_url"])
        if app.get("healthcheck_url"):
            record["healthcheck_url"] = str(app["healthcheck_url"])
        if app.get("unit"):
            record["unit"] = str(app["unit"])
        if app.get("compose"):
            record["compose"] = str(app["compose"])
        if app.get("image"):
            record["image"] = str(app["image"])
        if app.get("notes"):
            notes = app["notes"]
            note_list: list[str] = list(notes) if isinstance(notes, list) else [str(notes)]
            record["notes"] = note_list
        records.append(record)
    return records


def _host_apps(host: dict[str, Any]) -> list[dict[str, Any]]:
    apps = host.get("apps")
    if not isinstance(apps, list):
        return []
    return [item for item in apps if isinstance(item, dict)]


def _host_forks(host: dict[str, Any]) -> list[dict[str, Any]]:
    forks = host.get("forks")
    if not isinstance(forks, list):
        return []
    return [item for item in forks if isinstance(item, dict)]


def _host_database_contract(host: dict[str, Any]) -> dict[str, Any]:
    database = host.get("database")
    return database if isinstance(database, dict) else {}


def _host_inventory_profile(host: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in host.items()
        if key not in {"apps", "forks", "database", "modules"}
    }


def _host_inventory_payload(path: Path, host: dict[str, Any], raw_text: str) -> dict[str, Any]:
    access = host.get("access") if isinstance(host.get("access"), dict) else {}
    platform = host.get("platform") if isinstance(host.get("platform"), dict) else {}
    return {
        "id": _host_id(host, path.stem),
        "role": str(host.get("role") or "unknown"),
        "owner": str(host.get("owner") or "unknown"),
        "status": str(host.get("status") or "unknown"),
        "provider": str(platform.get("provider") or "unknown"),
        "os": str(platform.get("os") or "unknown"),
        "arch": str(platform.get("arch") or "unknown"),
        "ssh_target": str(access.get("ssh") or "") or None,
        "vpn_ip": _primary_private_ip(access),
        "public_ip": _inet_or_none(access.get("public_ip")),
        "inventory_file": _repo_relative_path(path),
        "inventory_hash": _inventory_hash(raw_text),
    }


def _app_payload(host_id: str, app: dict[str, Any]) -> dict[str, Any] | None:
    app_id = str(app.get("id") or app.get("name") or "").strip()
    if not app_id:
        return None
    payload = {
        "host_id": host_id,
        "app_id": app_id,
        "canonical_product_id": str(app.get("canonical_product_id") or app_id),
        "runtime": app.get("runtime"),
        "install_type": app.get("install_type"),
        "install_path": app.get("install_path") or app.get("source_repo_path"),
        "source_url": app.get("source"),
        "public_url": app.get("public_url"),
        "healthcheck_url": app.get("healthcheck_url"),
        "unit": app.get("unit"),
        "managed_by": str(app.get("managed_by") or "omni-srv-admin"),
        "update_policy": app.get("update_policy"),
        "desired_version": app.get("desired_version"),
        "current_version": app.get("current_version"),
        "state": app.get("desired_state") or "observed",
        "metadata": {
            key: value
            for key, value in app.items()
            if key
            not in {
                "id",
                "name",
                "canonical_product_id",
                "runtime",
                "install_type",
                "install_path",
                "source_repo_path",
                "source",
                "public_url",
                "healthcheck_url",
                "unit",
                "managed_by",
                "update_policy",
                "desired_version",
                "current_version",
                "desired_state",
            }
        },
    }
    return payload


def _fork_payload(host_id: str, fork: dict[str, Any]) -> dict[str, Any] | None:
    fork_id = str(fork.get("id") or "").strip()
    if not fork_id:
        return None
    payload = {
        "host_id": host_id,
        "fork_id": fork_id,
        "canonical_product_id": str(fork.get("canonical_product_id") or fork_id),
        "sync_project": fork.get("sync_project"),
        "local_path": fork.get("local_path"),
        "upstream_url": fork.get("upstream"),
        "sync_manifest": fork.get("sync_manifest"),
        "runtime_app_id": fork.get("runtime_app_id"),
        "managed_by": str(fork.get("managed_by") or "omni-srv-admin"),
        "state": fork.get("state") or "observed",
        "metadata": {
            key: value
            for key, value in fork.items()
            if key
            not in {
                "id",
                "canonical_product_id",
                "sync_project",
                "local_path",
                "upstream",
                "sync_manifest",
                "runtime_app_id",
                "managed_by",
                "state",
            }
        },
    }
    return payload


def _upsert_inventory_host(path: Path, host: dict[str, Any], raw_text: str, *, env: dict[str, str]) -> dict[str, Any]:
    payload = _host_inventory_payload(path, host, raw_text)
    _psql(
        f"""
INSERT INTO "TbHosts" (
    id, role, owner, status, provider, os, arch, ssh_target, vpn_ip,
    public_ip, inventory_file, inventory_hash, updated_at
) VALUES (
    {_sql_literal(payload["id"])},
    {_sql_literal(payload["role"])},
    {_sql_literal(payload["owner"])},
    {_sql_literal(payload["status"])},
    {_sql_literal(payload["provider"])},
    {_sql_literal(payload["os"])},
    {_sql_literal(payload["arch"])},
    {_sql_literal(payload["ssh_target"])},
    {_sql_literal(payload["vpn_ip"])},
    {_sql_literal(payload["public_ip"])},
    {_sql_literal(payload["inventory_file"])},
    {_sql_literal(payload["inventory_hash"])},
    now()
)
ON CONFLICT (id) DO UPDATE SET
    role = EXCLUDED.role,
    owner = EXCLUDED.owner,
    status = EXCLUDED.status,
    provider = EXCLUDED.provider,
    os = EXCLUDED.os,
    arch = EXCLUDED.arch,
    ssh_target = EXCLUDED.ssh_target,
    vpn_ip = EXCLUDED.vpn_ip,
    public_ip = EXCLUDED.public_ip,
    inventory_file = EXCLUDED.inventory_file,
    inventory_hash = EXCLUDED.inventory_hash,
    updated_at = now();
""",
        env=env,
    )
    return payload


def _upsert_customization_policy(
    *,
    host_id: str | None,
    scope_type: str,
    target_id: str,
    canonical_product_id: str | None,
    lane: str,
    policy_type: str,
    owner_module: str,
    entrypoint: str | None,
    enabled: bool,
    metadata: dict[str, Any],
    env: dict[str, str],
) -> None:
    conflict = """
ON CONFLICT (scope_type, target_id, lane, owner_module, policy_type)
WHERE host_id IS NULL
DO UPDATE SET
    canonical_product_id = EXCLUDED.canonical_product_id,
    entrypoint = EXCLUDED.entrypoint,
    enabled = EXCLUDED.enabled,
    metadata = EXCLUDED.metadata,
    updated_at = now();
"""
    if host_id is not None:
        conflict = """
ON CONFLICT (host_id, scope_type, target_id, lane, owner_module, policy_type)
DO UPDATE SET
    canonical_product_id = EXCLUDED.canonical_product_id,
    entrypoint = EXCLUDED.entrypoint,
    enabled = EXCLUDED.enabled,
    metadata = EXCLUDED.metadata,
    updated_at = now();
"""
    _psql(
        f"""
INSERT INTO "TbCustomizationPolicies" (
    host_id, scope_type, target_id, canonical_product_id, lane, policy_type,
    owner_module, entrypoint, enabled, metadata, updated_at
) VALUES (
    {_sql_literal(host_id)},
    {_sql_literal(scope_type)},
    {_sql_literal(target_id)},
    {_sql_literal(canonical_product_id)},
    {_sql_literal(lane)},
    {_sql_literal(policy_type)},
    {_sql_literal(owner_module)},
    {_sql_literal(entrypoint)},
    {'true' if enabled else 'false'},
    {_json_literal(metadata)}::jsonb,
    now()
)
{conflict}
""",
        env=env,
    )


def _sync_registry_host(host_id: str, *, env: dict[str, str]) -> dict[str, Any]:
    path, host, raw_text = _load_host(host_id)
    resolved_host = _host_id(host, path.stem)
    _upsert_inventory_host(path, host, raw_text, env=env)
    apps = [payload for item in _host_apps(host) if (payload := _app_payload(resolved_host, item))]
    forks = [payload for item in _host_forks(host) if (payload := _fork_payload(resolved_host, item))]
    database = _host_database_contract(host)
    modules = host.get("modules") if isinstance(host.get("modules"), list) else []
    profile = _host_inventory_profile(host)

    app_ids = [payload["app_id"] for payload in apps]
    fork_ids = [payload["fork_id"] for payload in forks]

    if app_ids:
        keep_apps = ", ".join(_sql_literal(item) for item in app_ids)
        _psql(
            f'DELETE FROM "TbManagedApps" WHERE host_id = {_sql_literal(resolved_host)} AND app_id NOT IN ({keep_apps});',
            env=env,
        )
    else:
        _psql(f'DELETE FROM "TbManagedApps" WHERE host_id = {_sql_literal(resolved_host)};', env=env)

    if fork_ids:
        keep_forks = ", ".join(_sql_literal(item) for item in fork_ids)
        _psql(
            f'DELETE FROM "TbManagedForks" WHERE host_id = {_sql_literal(resolved_host)} AND fork_id NOT IN ({keep_forks});',
            env=env,
        )
    else:
        _psql(f'DELETE FROM "TbManagedForks" WHERE host_id = {_sql_literal(resolved_host)};', env=env)

    _psql(
        f"""DELETE FROM "TbCustomizationPolicies"
WHERE host_id = {_sql_literal(resolved_host)}
  AND metadata->>'source' = 'inventory-sync';""",
        env=env,
    )

    for payload in apps:
        _psql(
            f"""
INSERT INTO "TbManagedApps" (
    host_id, app_id, canonical_product_id, runtime, install_type, install_path,
    source_url, public_url, healthcheck_url, unit, managed_by, update_policy,
    desired_version, current_version, state, metadata, observed_at, updated_at
) VALUES (
    {_sql_literal(payload["host_id"])},
    {_sql_literal(payload["app_id"])},
    {_sql_literal(payload["canonical_product_id"])},
    {_sql_literal(payload["runtime"])},
    {_sql_literal(payload["install_type"])},
    {_sql_literal(payload["install_path"])},
    {_sql_literal(payload["source_url"])},
    {_sql_literal(payload["public_url"])},
    {_sql_literal(payload["healthcheck_url"])},
    {_sql_literal(payload["unit"])},
    {_sql_literal(payload["managed_by"])},
    {_sql_literal(payload["update_policy"])},
    {_sql_literal(payload["desired_version"])},
    {_sql_literal(payload["current_version"])},
    {_sql_literal(payload["state"])},
    {_json_literal(payload["metadata"])}::jsonb,
    now(),
    now()
)
ON CONFLICT (host_id, app_id) DO UPDATE SET
    canonical_product_id = EXCLUDED.canonical_product_id,
    runtime = EXCLUDED.runtime,
    install_type = EXCLUDED.install_type,
    install_path = EXCLUDED.install_path,
    source_url = EXCLUDED.source_url,
    public_url = EXCLUDED.public_url,
    healthcheck_url = EXCLUDED.healthcheck_url,
    unit = EXCLUDED.unit,
    managed_by = EXCLUDED.managed_by,
    update_policy = EXCLUDED.update_policy,
    desired_version = EXCLUDED.desired_version,
    current_version = EXCLUDED.current_version,
    state = EXCLUDED.state,
    metadata = EXCLUDED.metadata,
    observed_at = now(),
    updated_at = now();
""",
            env=env,
        )
        if payload["metadata"].get("customization_entrypoint"):
            _upsert_customization_policy(
                host_id=resolved_host,
                scope_type="app",
                target_id=payload["app_id"],
                canonical_product_id=payload["canonical_product_id"],
                lane="managed-apps",
                policy_type="runtime",
                owner_module="modules/managed-apps",
                entrypoint=str(payload["metadata"]["customization_entrypoint"]),
                enabled=True,
                metadata={"source": "inventory-sync"},
                env=env,
            )

    for payload in forks:
        _psql(
            f"""
INSERT INTO "TbManagedForks" (
    host_id, fork_id, canonical_product_id, sync_project, local_path,
    upstream_url, sync_manifest, runtime_app_id, managed_by, state, metadata,
    observed_at, updated_at
) VALUES (
    {_sql_literal(payload["host_id"])},
    {_sql_literal(payload["fork_id"])},
    {_sql_literal(payload["canonical_product_id"])},
    {_sql_literal(payload["sync_project"])},
    {_sql_literal(payload["local_path"])},
    {_sql_literal(payload["upstream_url"])},
    {_sql_literal(payload["sync_manifest"])},
    {_sql_literal(payload["runtime_app_id"])},
    {_sql_literal(payload["managed_by"])},
    {_sql_literal(payload["state"])},
    {_json_literal(payload["metadata"])}::jsonb,
    now(),
    now()
)
ON CONFLICT (host_id, fork_id) DO UPDATE SET
    canonical_product_id = EXCLUDED.canonical_product_id,
    sync_project = EXCLUDED.sync_project,
    local_path = EXCLUDED.local_path,
    upstream_url = EXCLUDED.upstream_url,
    sync_manifest = EXCLUDED.sync_manifest,
    runtime_app_id = EXCLUDED.runtime_app_id,
    managed_by = EXCLUDED.managed_by,
    state = EXCLUDED.state,
    metadata = EXCLUDED.metadata,
    observed_at = now(),
    updated_at = now();
""",
            env=env,
        )
        _upsert_customization_policy(
            host_id=resolved_host,
            scope_type="fork",
            target_id=payload["fork_id"],
            canonical_product_id=payload["canonical_product_id"],
            lane="fork-sync",
            policy_type="sync",
            owner_module="modules/fork-sync",
            entrypoint=payload["sync_manifest"],
            enabled=True,
            metadata={"source": "inventory-sync"},
            env=env,
        )
        for component in payload["metadata"].get("components", []) if isinstance(payload["metadata"].get("components"), list) else []:
            if not isinstance(component, dict) or not component.get("id") or not component.get("sync_manifest"):
                continue
            _upsert_customization_policy(
                host_id=resolved_host,
                scope_type="component",
                target_id=str(component["id"]),
                canonical_product_id=payload["canonical_product_id"],
                lane="fork-sync",
                policy_type="sync",
                owner_module="modules/fork-sync",
                entrypoint=str(component["sync_manifest"]),
                enabled=True,
                metadata={"source": "inventory-sync", "component": component},
                env=env,
            )

    config_items = {
        "inventory.host.profile": profile,
        "inventory.host.apps": apps,
        "inventory.host.forks": forks,
        "inventory.host.database": database,
        "inventory.host.modules": modules,
    }
    config_keys = sorted(config_items.keys())
    if config_keys:
        keep_keys = ", ".join(_sql_literal(item) for item in config_keys)
        _psql(
            f'DELETE FROM "TbConfigItems" WHERE host_id = {_sql_literal(resolved_host)} AND key IN ({keep_keys});',
            env=env,
        )
    for key, value in config_items.items():
        _psql(
            f"""
INSERT INTO "TbConfigItems" (host_id, key, value, value_type, source, description, updated_by)
VALUES (
    {_sql_literal(resolved_host)},
    {_sql_literal(key)},
    {_json_literal(value)}::jsonb,
    'json',
    'inventory-sync',
    'Inventory mirror from omni-srv-admin host YAML',
    'omni-srv-admin'
);
""",
            env=env,
        )

    return {
        "host": resolved_host,
        "host_written": True,
        "apps_written": len(apps),
        "forks_written": len(forks),
        "database_written": bool(database),
        "config_items_written": len(config_items),
        "policies_written": len(
            [item for item in apps if item["metadata"].get("customization_entrypoint")]
        )
        + len(forks)
        + sum(
            len(item["metadata"].get("components", []))
            for item in forks
            if isinstance(item["metadata"].get("components"), list)
        ),
    }


def _registry_show_host(host_id: str, *, env: dict[str, str]) -> dict[str, Any]:
    host_lit = _sql_literal(host_id)
    payload = _psql_json(
        f"""
SELECT jsonb_build_object(
    'host', {host_lit},
    'apps', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'app_id', app_id,
                'canonical_product_id', canonical_product_id,
                'runtime', runtime,
                'install_type', install_type,
                'install_path', install_path,
                'source_url', source_url,
                'public_url', public_url,
                'healthcheck_url', healthcheck_url,
                'unit', unit,
                'managed_by', managed_by,
                'update_policy', update_policy,
                'desired_version', desired_version,
                'current_version', current_version,
                'state', state,
                'metadata', metadata
            ) ORDER BY app_id
        )
        FROM "TbManagedApps" WHERE host_id = {host_lit}
    ), '[]'::jsonb),
    'forks', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
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
            ) ORDER BY fork_id
        )
        FROM "TbManagedForks" WHERE host_id = {host_lit}
    ), '[]'::jsonb),
    'policies', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'scope_type', scope_type,
                'target_id', target_id,
                'canonical_product_id', canonical_product_id,
                'lane', lane,
                'policy_type', policy_type,
                'owner_module', owner_module,
                'entrypoint', entrypoint,
                'enabled', enabled,
                'metadata', metadata
            ) ORDER BY lane, scope_type, target_id
        )
        FROM "TbCustomizationPolicies" WHERE host_id = {host_lit}
    ), '[]'::jsonb),
    'inventory_mirror', COALESCE((
        SELECT jsonb_object_agg(key, value)
        FROM "TbConfigItems"
        WHERE host_id = {host_lit}
          AND key IN ('inventory.host.profile', 'inventory.host.apps', 'inventory.host.forks', 'inventory.host.database', 'inventory.host.modules')
    ), '{{}}'::jsonb)
);
""",
        env=env,
    )
    return payload or {"host": host_id, "apps": [], "forks": [], "policies": [], "inventory_mirror": {}}


@fleet.group("registry")
def registry() -> None:
    """Registry DB for apps/forks/customization policies."""


@registry.command("sync")
@click.option("--host", "host_ids", multiple=True, help="Host do inventário. Repetível.")
@click.option("--all", "all_hosts", is_flag=True, help="Sincroniza todos os hosts inventariados.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def registry_sync(host_ids: tuple[str, ...], all_hosts: bool, json_output: bool) -> None:
    """Espelha apps/forks/database do inventário para o DbOmniFleet."""
    selected = list(host_ids)
    if not selected:
        if not all_hosts:
            raise click.ClickException("use --host <id> ou --all")
        selected = [host_id for host_id, _, _, _ in _inventory_host_records(syncable_only=True)]
    env = _db_env()
    results = [_sync_registry_host(host_id, env=env) for host_id in selected]
    _emit({"target": "DbOmniFleet", "results": results, "generated_at": _now()}, json_output)


@registry.command("show")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def registry_show(host_id: str, json_output: bool) -> None:
    """Lê apps/forks/policies registrados no DbOmniFleet para um host."""
    payload = _registry_show_host(host_id, env=_db_env())
    _emit(payload, json_output)


@registry.command("upsert-policy")
@click.option("--host", "host_id", default=None, help="Host alvo; omita para policy global.")
@click.option("--scope-type", required=True, type=click.Choice(["global", "host", "app", "fork", "component"]))
@click.option("--target-id", required=True, help="ID do app/fork/component.")
@click.option("--canonical-product-id", default=None, help="Produto canônico.")
@click.option("--lane", required=True, type=click.Choice(["managed-apps", "fork-sync", "runtime-hook", "source-patch"]))
@click.option("--policy-type", default="reapply", show_default=True, type=click.Choice(["reapply", "postinstall", "sync", "runtime", "inventory-mirror"]))
@click.option("--owner-module", required=True, help="Módulo owner (ex: modules/fleet).")
@click.option("--entrypoint", default=None, help="Script/manifest/entrypoint.")
@click.option("--enabled/--disabled", default=True, show_default=True)
@click.option("--metadata-json", default="{}", help="Objeto JSON com metadados.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def registry_upsert_policy(
    host_id: str | None,
    scope_type: str,
    target_id: str,
    canonical_product_id: str | None,
    lane: str,
    policy_type: str,
    owner_module: str,
    entrypoint: str | None,
    enabled: bool,
    metadata_json: str,
    json_output: bool,
) -> None:
    """Escreve uma customization policy diretamente no DbOmniFleet."""
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--metadata-json inválido: {exc}") from exc
    if not isinstance(metadata, dict):
        raise click.ClickException("--metadata-json deve ser um objeto JSON")
    env = _db_env()
    _upsert_customization_policy(
        host_id=host_id,
        scope_type=scope_type,
        target_id=target_id,
        canonical_product_id=canonical_product_id,
        lane=lane,
        policy_type=policy_type,
        owner_module=owner_module,
        entrypoint=entrypoint,
        enabled=enabled,
        metadata=metadata,
        env=env,
    )
    _emit(
        {
            "target": "DbOmniFleet",
            "host": host_id,
            "scope_type": scope_type,
            "target_id": target_id,
            "lane": lane,
            "policy_type": policy_type,
            "owner_module": owner_module,
            "enabled": enabled,
        },
        json_output,
    )


@fleet.command("list")
def list_hosts() -> None:
    """Lista hosts cadastrados em inventory/hosts/*.yaml."""
    hosts_dir = _hosts_dir()
    if not hosts_dir.exists():
        click.echo(f"hosts dir missing: {HOSTS_DIR}")
        return
    rows = []
    for path in sorted(hosts_dir.glob("*.yaml")):
        text = path.read_text()
        rows.append((
            _simple_yaml_value(text, "id", path.stem),
            _simple_yaml_value(text, "role", "?"),
            _simple_yaml_value(text, "status", "?"),
            path.name,
        ))
    click.echo(f"{len(rows)} host(s) em {hosts_dir}")
    for host_id, role, status, file_name in rows:
        click.echo(f"{host_id:24} {role:22} {status:10} {file_name}")


@fleet.command("show")
@click.argument("host_id")
def show_host(host_id: str) -> None:
    """Mostra o YAML de um host."""
    path = _host_path(host_id)
    click.echo(path.read_text())


@fleet.command("validate-inventory")
@click.option("--json", "json_output", is_flag=True, help="Emite resultado em JSON.")
def validate_inventory(json_output: bool) -> None:
    """Valida campos mínimos do inventário host-by-host."""
    hosts_dir = _hosts_dir()
    if not hosts_dir.exists():
        raise click.ClickException(f"hosts dir missing: {HOSTS_DIR}")

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    for path in sorted(hosts_dir.glob("*.yaml")):
        text = path.read_text()
        data = _simple_yaml(text)
        host_id = _host_id(data, path.stem)
        if host_id in seen:
            duplicate_ids.add(host_id)
        seen.add(host_id)
        missing = [field for field in REQUIRED_HOST_FIELDS if not data.get(field)]
        for section, key in REQUIRED_NESTED_FIELDS:
            if not _nested(data, section, key):
                missing.append(f"{section}.{key}")
        results.append(
            {
                "host": host_id,
                "file": str(path),
                "status": "ok" if not missing else "invalid",
                "missing": missing,
            }
        )

    for result in results:
        if result["host"] in duplicate_ids:
            result["status"] = "invalid"
            result["missing"] = [*result["missing"], "duplicate id"]

    payload = {
        "hosts_dir": str(hosts_dir),
        "host_count": len(results),
        "valid": all(result["status"] == "ok" for result in results),
        "results": results,
    }
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["valid"]:
            raise click.ClickException("inventário inválido")
        return
    click.echo(f"{payload['host_count']} host(s) em {hosts_dir}")
    for result in results:
        suffix = "" if result["status"] == "ok" else f" missing={','.join(result['missing'])}"
        click.echo(f"{result['host']:24} {result['status']}{suffix}")
    if not payload["valid"]:
        raise click.ClickException("inventário inválido")


@fleet.group("trust-pki")
def trust_pki() -> None:
    """PKI interna de serviços para hosts cadastrados no Omni Fleet."""


@trust_pki.command("plan")
@click.option("--host", "host_ids", multiple=True, help="Host alvo. Repetível; default: todos ativos no inventário.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_plan(host_ids: tuple[str, ...], source: str, json_output: bool) -> None:
    """Renderiza o rollout PKI sem enfileirar ou mutar hosts."""
    targets = list(host_ids) or _pki_inventory_host_ids()
    rendered = [_pki_render_host(host_id, source=source, execute=False) for host_id in targets]
    payload = {
        "resource": "omni.fleet.trust-pki",
        "mode": "plan",
        "dry_run": True,
        "ca_host": PKI_CA_HOST_ID,
        "host_count": len(rendered),
        "hosts": rendered,
        "generated_at": _now(),
        "notes": [
            "trust stores receive the internal service CA chain, never peer leafs as root CAs",
            "host private keys stay on the owning host",
            "run onboard-host --db to queue this through DbOmniFleet/TbUpdatePlans",
        ],
    }
    _emit(payload, json_output)


@trust_pki.command("render-host")
@click.option("--host", "host_id", required=True, help="Host alvo cadastrado no inventário/DB.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_render_host(host_id: str, source: str, json_output: bool) -> None:
    """Mostra SANs, caminhos e comandos PKI para um host."""
    _emit(_pki_render_host(host_id, source=source, execute=False), json_output)


@trust_pki.command("preflight")
@click.option("--host", "host_ids", multiple=True, help="Host alvo. Repetível; default: todos ativos no inventário.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_preflight(host_ids: tuple[str, ...], source: str, json_output: bool) -> None:
    """Preflight local do plano PKI; não acessa nem muta hosts remotos."""
    targets = list(host_ids) or _pki_inventory_host_ids()
    hosts = []
    for host_id in targets:
        rendered = _pki_render_host(host_id, source=source, execute=False)
        host_checks = {
            "host": rendered["host"],
            "source": rendered["source"],
            "ssh": rendered["ssh"],
            "has_vpn_or_public_ip": bool(rendered["sans"]["ip"]),
            "has_dns_san": bool(rendered["sans"]["dns"]),
            "status": "ok" if rendered["sans"]["ip"] and rendered["sans"]["dns"] else "invalid",
        }
        hosts.append(host_checks)
    payload = {
        "resource": "omni.fleet.trust-pki",
        "mode": "preflight",
        "dry_run": True,
        "valid": all(item["status"] == "ok" for item in hosts),
        "hosts": hosts,
        "generated_at": _now(),
    }
    _emit(payload, json_output)
    if not payload["valid"]:
        raise click.ClickException("preflight PKI inválido")


def _trust_pki_queue_payload(
    *,
    command: dict[str, Any],
    identity: dict[str, Any],
    requested_by: str,
    approve: bool,
    env: dict[str, str],
    reason: str | None = None,
    drift: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _queue_update_record(
        host_id=str(command["target_host"]),
        program=PKI_PROGRAM,
        desired_version=PKI_DESIRED_VERSION,
        command_key=str(command["command_key"]),
        command_args=[str(item) for item in command.get("command_args", [])],
        requested_by=requested_by,
        requested_from_host=_default_host_id(),
        approve=approve,
        priority=int(command.get("priority") or 50),
        dry_run_payload={
            "resource": "omni.fleet.trust-pki",
            "source_host": identity["host"],
            "target_host": command["target_host"],
            "stage": command["stage"],
            "command_key": command["command_key"],
            "command_args": command.get("command_args", []),
            "reason": reason,
            "drift": drift,
            "paths": identity["paths"],
            "sans": identity["sans"],
            "generated_at": _now(),
        },
        env=env,
    )


@trust_pki.command("onboard-host")
@click.option("--host", "host_id", required=True, help="Host novo/existente cadastrado no inventário/DB.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--db", "write_db", is_flag=True, help="Insere a sequência em DbOmniFleet/TbUpdatePlans.")
@click.option("--execute", is_flag=True, help="Inclui --execute nos estágios mutáveis enfileirados.")
@click.option("--approve", is_flag=True, help="Cria planos já aprovados; exige --execute e --db.")
@click.option("--requested-by", default=None, help="Ator que solicitou o onboarding.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_onboard_host(
    host_id: str,
    source: str,
    write_db: bool,
    execute: bool,
    approve: bool,
    requested_by: str | None,
    json_output: bool,
) -> None:
    """Renderiza ou enfileira o onboarding PKI completo para um host."""
    if approve and (not execute or not write_db):
        raise click.ClickException("--approve exige --execute e --db")
    env = _db_env() if write_db or source == "db" else None
    identity = _pki_render_host(host_id, source=source, env=env, execute=execute)
    payload = {
        "resource": "omni.fleet.trust-pki",
        "mode": "onboard-host",
        "host": identity["host"],
        "source": identity["source"],
        "db_write": write_db,
        "execute": execute,
        "approval_state": "approved" if approve else "pending",
        "commands": identity["commands"],
        "plans": [],
        "generated_at": _now(),
    }
    if write_db:
        actor = requested_by or os.environ.get("USER", "operator")
        payload["plans"] = [
            _trust_pki_queue_payload(command=command, identity=identity, requested_by=actor, approve=approve, env=env or _db_env())
            for command in identity["commands"]
        ]
    _emit(payload, json_output)


@trust_pki.command("init-ca")
@click.option("--db", "write_db", is_flag=True, help="Insere plano em DbOmniFleet/TbUpdatePlans.")
@click.option("--execute", is_flag=True, help="Inclui --execute no plano mutável.")
@click.option("--approve", is_flag=True, help="Cria plano já aprovado; exige --execute e --db.")
@click.option("--requested-by", default=None, help="Ator que solicitou o plano.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_init_ca(write_db: bool, execute: bool, approve: bool, requested_by: str | None, json_output: bool) -> None:
    """Renderiza ou enfileira a inicialização da CA no host CA."""
    if approve and (not execute or not write_db):
        raise click.ClickException("--approve exige --execute e --db")
    identity = _pki_render_host(PKI_CA_HOST_ID, source="auto", execute=execute)
    command = {
        "stage": "init-ca",
        "target_host": PKI_CA_HOST_ID,
        "command_key": "omni.trust-pki.init-ca",
        "command_args": _pki_agent_args("init-ca", identity, execute=execute),
        "priority": 30,
    }
    payload = {
        "resource": "omni.fleet.trust-pki",
        "mode": "init-ca",
        "db_write": write_db,
        "execute": execute,
        "command": command,
        "paths": identity["paths"],
        "plans": [],
        "generated_at": _now(),
    }
    if write_db:
        payload["plans"] = [
            _trust_pki_queue_payload(
                command=command,
                identity=identity,
                requested_by=requested_by or os.environ.get("USER", "operator"),
                approve=approve,
                env=_db_env(),
            )
        ]
    _emit(payload, json_output)


@trust_pki.command("issue-host")
@click.option("--host", "host_id", required=True, help="Host alvo cujo CSR será assinado pelo host CA.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--db", "write_db", is_flag=True, help="Insere plano em DbOmniFleet/TbUpdatePlans.")
@click.option("--execute", is_flag=True, help="Inclui --execute no plano mutável.")
@click.option("--approve", is_flag=True, help="Cria plano já aprovado; exige --execute e --db.")
@click.option("--requested-by", default=None, help="Ator que solicitou o plano.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_issue_host(
    host_id: str,
    source: str,
    write_db: bool,
    execute: bool,
    approve: bool,
    requested_by: str | None,
    json_output: bool,
) -> None:
    """Renderiza ou enfileira assinatura do leaf de um host no CA host."""
    if approve and (not execute or not write_db):
        raise click.ClickException("--approve exige --execute e --db")
    env = _db_env() if write_db or source == "db" else None
    identity = _pki_render_host(host_id, source=source, env=env, execute=execute)
    command = next(command for command in identity["commands"] if command["stage"] == "issue-host")
    payload = {
        "resource": "omni.fleet.trust-pki",
        "mode": "issue-host",
        "host": identity["host"],
        "db_write": write_db,
        "execute": execute,
        "command": command,
        "plans": [],
        "generated_at": _now(),
    }
    if write_db:
        payload["plans"] = [
            _trust_pki_queue_payload(
                command=command,
                identity=identity,
                requested_by=requested_by or os.environ.get("USER", "operator"),
                approve=approve,
                env=env or _db_env(),
            )
        ]
    _emit(payload, json_output)


@trust_pki.command("install-trust")
@click.option("--host", "host_id", required=True, help="Host alvo ou 'all'.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--db", "write_db", is_flag=True, help="Insere planos em DbOmniFleet/TbUpdatePlans.")
@click.option("--execute", is_flag=True, help="Inclui --execute nos planos mutáveis.")
@click.option("--approve", is_flag=True, help="Cria planos já aprovados; exige --execute e --db.")
@click.option("--requested-by", default=None, help="Ator que solicitou o plano.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_install_trust(
    host_id: str,
    source: str,
    write_db: bool,
    execute: bool,
    approve: bool,
    requested_by: str | None,
    json_output: bool,
) -> None:
    """Renderiza ou enfileira instalação de CA chain e leaf local."""
    if approve and (not execute or not write_db):
        raise click.ClickException("--approve exige --execute e --db")
    targets = _pki_inventory_host_ids() if host_id == "all" else [host_id]
    env = _db_env() if write_db or source == "db" else None
    rendered = []
    plans = []
    actor = requested_by or os.environ.get("USER", "operator")
    for target in targets:
        identity = _pki_render_host(target, source=source, env=env, execute=execute)
        commands = [command for command in identity["commands"] if command["stage"] in {"install-ca", "install-leaf"}]
        rendered.append({"host": identity["host"], "commands": commands})
        if write_db:
            plans.extend(
                _trust_pki_queue_payload(command=command, identity=identity, requested_by=actor, approve=approve, env=env or _db_env())
                for command in commands
            )
    _emit(
        {
            "resource": "omni.fleet.trust-pki",
            "mode": "install-trust",
            "db_write": write_db,
            "execute": execute,
            "hosts": rendered,
            "plans": plans,
            "generated_at": _now(),
        },
        json_output,
    )


@trust_pki.command("verify")
@click.option("--host", "host_id", required=True, help="Host alvo ou 'all'.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_verify(host_id: str, source: str, json_output: bool) -> None:
    """Renderiza comandos e checks esperados para validação PKI."""
    targets = _pki_inventory_host_ids() if host_id == "all" else [host_id]
    hosts = []
    for target in targets:
        identity = _pki_render_host(target, source=source, execute=False)
        verify_command = next(command for command in identity["commands"] if command["stage"] == "verify")
        if identity.get("service_tls_mode") == "trust-client":
            checks = [
                "Windows CurrentUser trust store contains the internal service CA chain",
                "peer public leaf bundle is stored only for audit or pinning evidence",
                "HTTPS verification trusts the CA chain, not peer leafs as root CAs",
            ]
        else:
            checks = [
                "openssl verify uses system trust store",
                "leaf has CA:FALSE",
                "leaf has serverAuth and clientAuth",
                "SAN covers VPN IP and DNS aliases",
                "certificate validity is at least 30 days",
            ]
        hosts.append(
            {
                "host": identity["host"],
                "command": verify_command,
                "checks": checks,
            }
        )
    _emit(
        {
            "resource": "omni.fleet.trust-pki",
            "mode": "verify",
            "dry_run": True,
            "hosts": hosts,
            "generated_at": _now(),
        },
        json_output,
    )


def _observed_sans_from_inputs(observed_san_json: str | None, cert_file: Path | None) -> dict[str, list[str]] | None:
    if observed_san_json:
        return _parse_san_json(observed_san_json)
    if cert_file is not None:
        return _cert_sans_from_file(cert_file)
    return None


@trust_pki.command("reconcile-host")
@click.option("--host", "host_id", required=True, help="Host alvo cadastrado no inventário/DB.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--observed-san-json", default=None, help="SANs observados no certificado atual para comparação offline.")
@click.option("--cert-file", type=click.Path(path_type=Path), default=None, help="Certificado local a comparar com o inventário.")
@click.option("--db", "write_db", is_flag=True, help="Enfileira reconcile read-only no agente local do host.")
@click.option("--approve", is_flag=True, help="Cria o plano read-only já aprovado; exige --db.")
@click.option("--requested-by", default=None, help="Ator que solicitou o reconcile.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_reconcile_host(
    host_id: str,
    source: str,
    observed_san_json: str | None,
    cert_file: Path | None,
    write_db: bool,
    approve: bool,
    requested_by: str | None,
    json_output: bool,
) -> None:
    """Detecta drift de SAN/IP entre inventário/DB e certificado atual."""
    if approve and not write_db:
        raise click.ClickException("--approve exige --db")
    env = _db_env() if write_db or source == "db" else None
    identity = _pki_render_host(host_id, source=source, env=env, execute=False)
    observed = _observed_sans_from_inputs(observed_san_json, cert_file)
    if observed is None:
        drift: dict[str, Any] = {
            "status": "unknown",
            "needs_rotation": None,
            "desired": _normal_sans(identity["sans"]),
            "observed": None,
            "missing": {"dns": [], "ip": []},
            "extra": {"dns": [], "ip": []},
            "note": "provide --observed-san-json, --cert-file, or queue --db for remote agent inspection",
        }
    else:
        drift = _pki_san_drift(identity["sans"], observed)
    command = {
        "stage": "reconcile",
        "target_host": identity["host"],
        "command_key": "omni.trust-pki.reconcile",
        "command_args": _pki_agent_args("reconcile", identity, execute=False),
        "priority": 46,
    }
    plans = []
    if write_db:
        plans.append(
            _trust_pki_queue_payload(
                command=command,
                identity=identity,
                requested_by=requested_by or os.environ.get("USER", "operator"),
                approve=approve,
                env=env or _db_env(),
                reason="reconcile",
                drift=drift,
            )
        )
    _emit(
        {
            "resource": "omni.fleet.trust-pki",
            "mode": "reconcile-host",
            "host": identity["host"],
            "source": identity["source"],
            "db_write": write_db,
            "drift": drift,
            "command": command,
            "plans": plans,
            "generated_at": _now(),
        },
        json_output,
    )


@trust_pki.command("rotate-host")
@click.option("--host", "host_id", required=True, help="Host alvo cadastrado no inventário/DB.")
@click.option("--source", type=click.Choice(["auto", "inventory", "db"]), default="auto", show_default=True)
@click.option("--reason", default="ip-change", show_default=True, help="Motivo auditável da rotação.")
@click.option("--observed-san-json", default=None, help="SANs observados no certificado atual para comparação offline.")
@click.option("--cert-file", type=click.Path(path_type=Path), default=None, help="Certificado local a comparar com o inventário.")
@click.option("--include-ca", is_flag=True, help="Inclui reinstalação da CA chain no plano.")
@click.option("--force", is_flag=True, help="Permite enfileirar mesmo sem drift observado.")
@click.option("--db", "write_db", is_flag=True, help="Insere a sequência em DbOmniFleet/TbUpdatePlans.")
@click.option("--execute", is_flag=True, help="Inclui --execute nos estágios mutáveis enfileirados.")
@click.option("--approve", is_flag=True, help="Cria planos já aprovados; exige --execute e --db.")
@click.option("--requested-by", default=None, help="Ator que solicitou a rotação.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_rotate_host(
    host_id: str,
    source: str,
    reason: str,
    observed_san_json: str | None,
    cert_file: Path | None,
    include_ca: bool,
    force: bool,
    write_db: bool,
    execute: bool,
    approve: bool,
    requested_by: str | None,
    json_output: bool,
) -> None:
    """Reemite o leaf de um host quando o inventário/DB muda SAN/IP."""
    if approve and (not execute or not write_db):
        raise click.ClickException("--approve exige --execute e --db")
    env = _db_env() if write_db or source == "db" else None
    identity = _pki_render_host(host_id, source=source, env=env, execute=execute)
    observed = _observed_sans_from_inputs(observed_san_json, cert_file)
    if observed is None:
        drift: dict[str, Any] = {
            "status": "unknown",
            "needs_rotation": None,
            "desired": _normal_sans(identity["sans"]),
            "observed": None,
            "missing": {"dns": [], "ip": []},
            "extra": {"dns": [], "ip": []},
            "note": "no observed certificate SANs provided; use --force to queue rotation anyway",
        }
    else:
        drift = _pki_san_drift(identity["sans"], observed)
    if write_db and not force and drift.get("needs_rotation") is not True:
        raise click.ClickException("rotação em DB exige drift detectado ou --force")
    commands = _pki_rotation_plan(identity, execute=execute, include_ca=include_ca)
    plans = []
    if write_db:
        actor = requested_by or os.environ.get("USER", "operator")
        plans = [
            _trust_pki_queue_payload(
                command=command,
                identity=identity,
                requested_by=actor,
                approve=approve,
                env=env or _db_env(),
                reason=reason,
                drift=drift,
            )
            for command in commands
        ]
    _emit(
        {
            "resource": "omni.fleet.trust-pki",
            "mode": "rotate-host",
            "host": identity["host"],
            "source": identity["source"],
            "reason": reason,
            "db_write": write_db,
            "execute": execute,
            "force": force,
            "drift": drift,
            "commands": commands,
            "plans": plans,
            "generated_at": _now(),
        },
        json_output,
    )


@trust_pki.command("rollback-plan")
@click.option("--host", "host_id", required=True, help="Host alvo ou 'all'.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_rollback_plan(host_id: str, json_output: bool) -> None:
    """Mostra o rollback esperado sem remover nada."""
    targets = _pki_inventory_host_ids() if host_id == "all" else [host_id]
    hosts = []
    for target in targets:
        identity = _pki_render_host(target, source="auto", execute=False)
        if identity.get("service_tls_mode") == "trust-client":
            steps = [
                "remove ATIUS internal service CA chain from Windows CurrentUser Root only after rollback approval",
                "preserve peer public leaf bundle for audit unless explicitly purged",
                "run trust-pki verify",
            ]
            backup_glob = f"{identity['paths']['host_tls_dir']}/backups/*"
        else:
            steps = [
                "stop service-specific TLS adapters before restoring cert material",
                "restore prior /etc/omni-srv-admin/tls snapshot",
                "restore prior /usr/local/share/ca-certificates ATIUS PKI files",
                "run update-ca-certificates",
                "run trust-pki verify",
            ]
            backup_glob = "/root/.backups/omni-fleet-pki-*"
        hosts.append(
            {
                "host": target,
                "backup_glob": backup_glob,
                "restore_paths": identity["paths"],
                "steps": steps,
            }
        )
    payload = {
        "resource": "omni.fleet.trust-pki",
        "mode": "rollback-plan",
        "dry_run": True,
        "hosts": hosts,
        "generated_at": _now(),
    }
    _emit(payload, json_output)


def _pki_runner_checks(host: dict[str, Any]) -> dict[str, bool]:
    if _pki_is_windows_platform(host):
        return {
            "python": bool(shutil.which("python") or sys.executable),
            "powershell": bool(shutil.which("powershell") or shutil.which("pwsh")),
            "certutil": bool(shutil.which("certutil")),
        }
    return {
        "openssl": bool(shutil.which("openssl")),
        "update_ca_certificates": bool(shutil.which("update-ca-certificates")),
    }


def _pki_script(name: str) -> Path:
    return REPO / "modules" / "fleet-pki" / "scripts" / name


def _pki_script_env() -> dict[str, str]:
    return {
        **os.environ,
        "OMNI_SRV_ADMIN": str(REPO),
        "OMNI_PKI_OPENSSL_CNF": str(REPO / "modules" / "fleet-pki" / "templates" / "openssl-ca.cnf"),
    }


def _pki_run_script(argv: list[str], *, timeout: int = 900) -> dict[str, Any]:
    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() != 0:
        argv = ["sudo", *argv]
    completed = subprocess.run(
        argv,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_pki_script_env(),
    )
    payload: dict[str, Any] = {
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": _redact_text(completed.stdout[-4000:]),
        "stderr": _redact_text(completed.stderr[-4000:]),
    }
    for line in reversed(completed.stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            payload.update(parsed)
            payload.setdefault("status", "ok" if completed.returncode == 0 else "failed")
        break
    if completed.returncode != 0:
        raise click.ClickException(_redact_text(completed.stderr.strip() or completed.stdout.strip() or "PKI script failed"))
    return payload


def _pki_linux_runner_execute(action: str, payload: dict[str, Any], sans: dict[str, Any]) -> dict[str, Any]:
    host_id = str(payload["target_host"])
    paths = payload["paths"]
    host_script = str(_pki_script("omni-fleet-pki-host.sh"))
    bootstrap_script = str(_pki_script("omni-fleet-pki-bootstrap.sh"))
    san_arg = json.dumps(_normal_sans(sans), sort_keys=True)
    if action == "preflight":
        return _pki_run_script([host_script, "preflight"], timeout=120)
    if action == "init-ca":
        return _pki_run_script([bootstrap_script, "init-ca"], timeout=900)
    if action == "ensure-key-csr":
        return _pki_run_script([host_script, "ensure-key-csr", "--host-id", host_id, "--san-json", san_arg], timeout=900)
    if action == "issue-host":
        csr = str(Path(PKI_CA_BASE) / "intake" / f"{host_id}.csr.pem")
        return _pki_run_script([bootstrap_script, "sign-host", "--host-id", host_id, "--csr", csr, "--san-json", san_arg], timeout=900)
    if action == "install-ca":
        root_ca = str(Path(PKI_CA_BASE) / "certs" / "root-ca.crt.pem")
        issuing_ca = str(Path(PKI_CA_BASE) / "certs" / "issuing-ca.crt.pem")
        return _pki_run_script([host_script, "install-ca", "--root-ca", root_ca, "--issuing-ca", issuing_ca], timeout=900)
    if action == "install-leaf":
        cert = str(Path(PKI_CA_BASE) / "certs" / "hosts" / f"{host_id}.crt.pem")
        chain = str(Path(PKI_CA_BASE) / "certs" / "hosts" / f"{host_id}.chain.crt.pem")
        return _pki_run_script([host_script, "install-leaf", "--host-id", host_id, "--cert", cert, "--chain", chain], timeout=900)
    if action == "verify":
        return _pki_run_script([host_script, "verify", "--host-id", host_id], timeout=300)
    raise click.ClickException(f"ação PKI não suportada pelo runner Linux: {action}")


def _pki_windows_import_ca(payload: dict[str, Any]) -> dict[str, Any]:
    paths = payload["paths"]
    ca_files = [Path(str(item)) for item in paths.get("ca_files", [])]
    missing = [str(path) for path in ca_files if not path.exists()]
    if missing:
        raise click.ClickException(f"CA files ausentes para install-ca: {', '.join(missing)}")
    certutil = shutil.which("certutil")
    if not certutil:
        raise click.ClickException("certutil não encontrado para importar CA no Windows")
    imported = []
    for ca_file in ca_files:
        store = "CA" if "issuing" in ca_file.name.lower() else "Root"
        completed = subprocess.run(
            [certutil, "-user", "-addstore", store, str(ca_file)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            raise click.ClickException(_redact_text(completed.stderr.strip() or completed.stdout.strip()))
        imported.append({"file": str(ca_file), "store": f"Cert:\\CurrentUser\\{store}"})
    return {"status": "ok", "action": "install-ca", "imported_ca_files": imported}


def _pki_windows_verify_ca(payload: dict[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    ca_files = [Path(str(item)) for item in payload["paths"].get("ca_files", [])]
    checks["ca_files_present"] = bool(ca_files) and all(path.exists() for path in ca_files)
    checks["trust_store_configured"] = bool(payload["paths"].get("trust_store"))
    certutil = shutil.which("certutil")
    if certutil and checks["ca_files_present"]:
        for ca_file in ca_files:
            thumb = subprocess.run(
                [certutil, "-hashfile", str(ca_file), "SHA256"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            checks[f"hash_readable:{ca_file.name}"] = thumb.returncode == 0
    return checks


@trust_pki.command("agent-runner", hidden=True)
@click.argument("action", type=click.Choice(PKI_COMMAND_STAGES))
@click.option("--host", "host_id", required=True, help="Host local que executa o estágio.")
@click.option("--target-host", default=None, help="Host alvo quando o estágio roda no CA host.")
@click.option("--san-json", default="{}", help="SANs renderizados pelo orquestrador.")
@click.option("--execute", is_flag=True, help="Autoriza estágio mutável local.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def trust_pki_agent_runner(
    action: str,
    host_id: str,
    target_host: str | None,
    san_json: str,
    execute: bool,
    json_output: bool,
) -> None:
    """Runner local allowlisted para o agente; não imprime material secreto."""
    try:
        sans = json.loads(san_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--san-json inválido: {exc}") from exc
    mutating = {"init-ca", "ensure-key-csr", "issue-host", "install-ca", "install-leaf"}
    path_host_id = target_host or host_id
    path_host = _pki_inventory_host_data(path_host_id)
    payload = {
        "resource": "omni.fleet.trust-pki",
        "runner": "agent-runner",
        "action": action,
        "host": host_id,
        "target_host": path_host_id,
        "execute": execute,
        "dry_run": not execute,
        "platform_os": _pki_platform_os(path_host) if path_host else "",
        "service_tls_mode": _pki_service_tls_mode(path_host) if path_host else "leaf",
        "paths": _pki_host_paths(path_host_id, path_host),
        "sans": sans,
        "checks": _pki_runner_checks(path_host),
        "generated_at": _now(),
    }
    if action in mutating and not execute:
        payload["status"] = "planned"
        payload["note"] = "mutating stage rendered only; pass --execute through queued command_args to apply"
    elif action in mutating:
        if payload.get("service_tls_mode") == "trust-client":
            if action != "install-ca":
                raise click.ClickException(f"ação Windows trust-client mutável não suportada: {action}")
            payload.update(_pki_windows_import_ca(payload))
        elif os.name == "posix":
            local_host_id = _default_host_id()
            if local_host_id != host_id:
                payload["status"] = "blocked"
                payload["note"] = "live Linux key/cert mutation must run on the target Linux host"
            else:
                payload.update(_pki_linux_runner_execute(action, payload, sans))
        else:
            payload["status"] = "blocked"
            payload["note"] = "live Linux key/cert mutation must run on the target Linux host"
    elif action == "reconcile":
        leaf_path = Path(str(payload["paths"]["leaf_cert"]))
        try:
            leaf_exists = leaf_path.exists()
        except OSError:
            leaf_exists = False
        if not leaf_exists:
            payload["status"] = "missing-cert"
            payload["drift"] = {
                "status": "missing-cert",
                "needs_rotation": True,
                "desired": _normal_sans(sans),
                "observed": None,
                "missing": _normal_sans(sans),
                "extra": {"dns": [], "ip": []},
            }
        else:
            observed = _cert_sans_from_file(leaf_path)
            payload["drift"] = _pki_san_drift(sans, observed)
            payload["status"] = payload["drift"]["status"]
    else:
        if action == "verify" and payload.get("service_tls_mode") == "trust-client":
            payload["checks"].update(_pki_windows_verify_ca(payload))
        elif os.name == "posix" and action in {"preflight", "verify"}:
            payload.update(_pki_linux_runner_execute(action, payload, sans))
        payload["status"] = "ok" if all(payload["checks"].values()) else "degraded"
    _emit(payload, json_output)
    if payload["status"] == "blocked":
        raise click.ClickException(payload["note"])


@fleet.group("install")
def install() -> None:
    """Planos seguros de instalação server/node do control plane."""


@install.command("server")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--dry-run", is_flag=True, help="Compatibilidade explícita; este é o padrão.")
@click.option("--apply", "apply_changes", is_flag=True, help="Reservado para execução futura aprovada.")
@click.option("--json", "json_output", is_flag=True, help="Emite plano em JSON.")
def install_server(host_id: str, dry_run: bool, apply_changes: bool, json_output: bool) -> None:
    """Gera plano idempotente para instalar o modo server."""
    if apply_changes:
        raise click.ClickException("execução real bloqueada nesta fase; use sem --apply para plano dry-run")
    path, host, _ = _load_host(host_id)
    payload = _install_plan("server", host, path)
    payload["requested_dry_run"] = True if dry_run else True
    _emit(payload, json_output)


@install.command("node")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--dry-run", is_flag=True, help="Compatibilidade explícita; este é o padrão.")
@click.option("--apply", "apply_changes", is_flag=True, help="Reservado para execução futura aprovada.")
@click.option("--json", "json_output", is_flag=True, help="Emite plano em JSON.")
def install_node(host_id: str, dry_run: bool, apply_changes: bool, json_output: bool) -> None:
    """Gera plano idempotente para instalar o modo node."""
    if apply_changes:
        raise click.ClickException("execução real bloqueada nesta fase; use sem --apply para plano dry-run")
    path, host, _ = _load_host(host_id)
    payload = _install_plan("node", host, path)
    payload["requested_dry_run"] = True if dry_run else True
    _emit(payload, json_output)


@fleet.command("heartbeat")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def heartbeat(host_id: str, json_output: bool) -> None:
    """Mostra o contrato de heartbeat/status para um host."""
    path, host, _ = _load_host(host_id)
    _emit(_heartbeat_payload(host, path), json_output)


@fleet.command("programs")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--json", "json_output", is_flag=True, help="Emite registry em JSON.")
def programs(host_id: str, json_output: bool) -> None:
    """Mostra o registry inicial de programas controlados por host."""
    path, host, _ = _load_host(host_id)
    payload = {
        "host": _host_id(host, path.stem),
        "program_count": len(_program_records(host, path)),
        "programs": _program_records(host, path),
        "notes": [
            "use `omni fleet agent collect-programs --host <host> --json` for live read-only observations",
            "desired_version is generated through update plans before execution",
        ],
    }
    _emit(payload, json_output)


def _version_table_rows(host_ids: list[str], *, env: dict[str, str]) -> dict[str, Any]:
    hosts_json = ",".join(_sql_literal(host_id) for host_id in host_ids)
    payload = _psql_json(
        f"""
SELECT COALESCE(jsonb_object_agg(host_id, row_payload), '{{}}'::jsonb)
FROM (
    SELECT
        host_id,
        jsonb_build_object(
            'host', host_id,
            'component', component,
            'installed_version', installed_version,
            'git_branch', git_branch,
            'git_commit', git_commit,
            'git_dirty', git_dirty,
            'github_version', github_version,
            'github_commit', github_commit,
            'observed_at', observed_at,
            'metadata', metadata
        ) AS row_payload
    FROM "TbVersion"
    WHERE component = 'omni-srv-admin'
      AND host_id IN ({hosts_json})
) rows;
""",
        env=env,
    )
    return payload or {}


@fleet.command("version-table")
@click.option("--source", type=click.Path(path_type=Path), default=DEFAULT_OMNI_VERSION_MATRIX, show_default=True)
@click.option("--db", "use_db", is_flag=True, help="Lê observações de TbVersion no DbOmniFleet.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def version_table(source: Path, use_db: bool, json_output: bool) -> None:
    """Mostra a tabela de controle de versão do omni-srv-admin por host."""
    matrix = load_omni_version_matrix(source)
    target_hosts = [str(item) for item in matrix.get("target_hosts", [])]
    observed = _version_table_rows(target_hosts, env=_db_env()) if use_db else {}
    rows: list[dict[str, Any]] = []
    for host_id in target_hosts:
        host_cfg = (matrix.get("hosts") or {}).get(host_id, {})
        live = observed.get(host_id, {}) if isinstance(observed, dict) else {}
        rows.append(
            {
                "host": host_id,
                "track_branch": host_cfg.get("track_branch") or matrix.get("track_branch") or "main",
                "desired_version": host_cfg.get("desired_version") or matrix.get("desired_version"),
                "repo_dir": host_cfg.get("repo_dir"),
                "scheduler": host_cfg.get("scheduler"),
                "command_key": host_cfg.get("command_key"),
                "installed_version": live.get("installed_version"),
                "git_branch": live.get("git_branch"),
                "git_commit": live.get("git_commit"),
                "git_dirty": live.get("git_dirty"),
                "observed_at": live.get("observed_at"),
            }
        )
    payload = {
        "component": matrix.get("component") or "omni-srv-admin",
        "github_repo": matrix.get("github_repo"),
        "desired_version": matrix.get("desired_version"),
        "target_hosts": target_hosts,
        "source": str(source),
        "db": use_db,
        "rows": rows,
        "generated_at": _now(),
    }
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    click.echo(f"component: {payload['component']}")
    click.echo(f"github_repo: {payload['github_repo']}")
    click.echo(f"desired_version: {payload['desired_version']}")
    click.echo(f"{'HOST':20} {'TARGET':10} {'INSTALLED':10} {'BRANCH':18} {'DIRTY':5} {'SCHEDULER'}")
    for row in rows:
        click.echo(
            f"{str(row['host']):20} {str(row['desired_version'] or '-'):10} {str(row['installed_version'] or '-'):10} "
            f"{str(row['git_branch'] or '-'):18} {str(row['git_dirty'] or False):5} {str(row['scheduler'] or '-')}"
        )


@fleet.group("profiles")
def profiles() -> None:
    """Desired-state profiles e seeds de governança."""


@profiles.command("managed-apps")
@click.option("--source", type=click.Path(path_type=Path), default=DEFAULT_MANAGED_APPS_SOURCE, show_default=True)
@click.option("--db", "write_db", is_flag=True, help="Grava profile em DbOmniFleet via PgBouncer.")
@click.option("--json", "json_output", is_flag=True, help="Emite profile em JSON.")
def profiles_managed_apps(source: Path, write_db: bool, json_output: bool) -> None:
    """Renderiza o desired-state profile baseado em modules/managed-apps."""
    profile = load_managed_apps_profile(source)
    profile["db_write"] = write_db
    if write_db:
        _write_profile_db(profile, env=_db_env())
    _append_audit_event(
        {
            "actor": os.environ.get("USER", "operator"),
            "host": _default_host_id(),
            "action": "desired-state.profile.render",
            "target": profile["profile_id"],
            "result": "written" if write_db else "rendered",
            "timestamp": _now(),
            "metadata": {"rule_count": profile["rule_count"], "db_write": write_db},
        }
    )
    _emit(profile, json_output)


@fleet.group("security")
def security() -> None:
    """CVE/USN e Ubuntu Pro security reporting read-only."""


@security.command("report")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--db", "write_db", is_flag=True, help="Grava snapshot em DbOmniFleet via PgBouncer.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def security_report(host_id: str | None, write_db: bool, json_output: bool) -> None:
    """Coleta status CVE/USN local sem aplicar correções."""
    resolved_host = host_id or _default_host_id()
    report = collect_security_report(resolved_host)
    _write_json(SECURITY_DIR / f"{resolved_host}.json", report)
    if write_db:
        _write_security_report_db(report, env=_db_env())
    _append_audit_event(
        {
            "actor": "omni-fleet-agent",
            "host": resolved_host,
            "action": "security.report",
            "target": "ubuntu-pro-client",
            "result": "written" if write_db else "collected",
            "timestamp": report["generated_at"],
            "metadata": {"db_write": write_db, "warning_count": len(report.get("warnings", []))},
        }
    )
    _emit(report, json_output)


@fleet.command("landscape-parity")
@click.option("--json", "json_output", is_flag=True, help="Emite matriz em JSON.")
def landscape_parity(json_output: bool) -> None:
    """Mostra paridade e limites entre Landscape e Omni."""
    rows = [
        {
            "capability": "Ubuntu machine inventory",
            "landscape": "primary UI/API for registered clients",
            "omni": "reviewed source of truth and audit projection",
            "decision": "dual-use; Omni owns identity, Landscape owns Ubuntu-machine operations",
        },
        {
            "capability": "Package visibility",
            "landscape": "package alerts and package activities",
            "omni": "read-only collectors and TbPrograms/TbVersions observations",
            "decision": "both visible; approved mutation remains gated",
        },
        {
            "capability": "CVE/USN prioritization",
            "landscape": "package/security UI evidence",
            "omni": "pro security-status/pro cves snapshots and update-plan queue",
            "decision": "Phase 32 parity report; no automatic fixes",
        },
        {
            "capability": "Desired-state governance",
            "landscape": "repository/package profiles where useful",
            "omni": "TbDesiredStateProfiles/TbDesiredStateRules",
            "decision": "Omni owns fleet policy and audit trail",
        },
        {
            "capability": "Workload administration",
            "landscape": "not Kubernetes workload controller",
            "omni": "not the live workload UI",
            "decision": "K3s/Portainer own workloads",
        },
    ]
    payload = {
        "doc": "docs/fleet/landscape-parity.md",
        "generated_at": _now(),
        "rows": rows,
        "fix_policy": "no automatic fixes; pro fix only through dry-run/manual gate or approved update plan",
    }
    _emit(payload, json_output)


@fleet.command("update-plan")
@click.option("--host", "host_id", required=True, help="Host do inventário.")
@click.option("--program", required=True, help="Programa ou módulo controlado.")
@click.option("--desired-version", required=True, help="Versão desejada.")
@click.option("--dry-run", is_flag=True, help="Compatibilidade explícita; este é o padrão.")
@click.option("--apply", "apply_changes", is_flag=True, help="Reservado para execução futura aprovada.")
@click.option("--json", "json_output", is_flag=True, help="Emite plano em JSON.")
def update_plan(
    host_id: str,
    program: str,
    desired_version: str,
    dry_run: bool,
    apply_changes: bool,
    json_output: bool,
) -> None:
    """Gera update plan auditável sem aplicar mudanças."""
    if apply_changes:
        raise click.ClickException("execução real bloqueada; update plans exigem aprovação explícita")
    path, host, _ = _load_host(host_id)
    host_name = _host_id(host, path.stem)
    payload = {
        "host": host_name,
        "program": program,
        "current_version": "unknown",
        "desired_version": desired_version,
        "dry_run": True if dry_run else True,
        "approval_state": "pending",
        "audit_event_id": None,
        "actions": [
            "collect current version from node agent",
            "compare current vs desired version",
            "render package/service commands",
            "record dry-run output",
            "wait for explicit approval before execution",
        ],
        "status": "planned",
        "generated_at": _now(),
    }
    _emit(payload, json_output)


@fleet.command("queue-update")
@click.option("--host", "host_id", required=True, help="Host alvo do inventário.")
@click.option("--program", required=True, help="Programa ou módulo controlado.")
@click.option("--desired-version", required=True, help="Versão desejada.")
@click.option("--command-key", required=True, help="Chave allowlist em TbFleetCommands.")
@click.option("--args-json", default="[]", help="Lista JSON de argumentos extras para o comando allowlist.")
@click.option("--requested-by", default=None, help="Ator que solicitou o plano.")
@click.option("--approve", is_flag=True, help="Cria já aprovado; use apenas para comandos revisados.")
@click.option("--priority", default=100, show_default=True, help="Menor valor executa antes.")
@click.option("--db", "write_db", is_flag=True, help="Insere em DbOmniFleet via PgBouncer.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def queue_update(
    host_id: str,
    program: str,
    desired_version: str,
    command_key: str,
    args_json: str,
    requested_by: str | None,
    approve: bool,
    priority: int,
    write_db: bool,
    json_output: bool,
) -> None:
    """Cria update plan executável por agent local do host alvo."""
    path, host, _ = _load_host(host_id)
    host_name = _host_id(host, path.stem)
    try:
        command_args = json.loads(args_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--args-json inválido: {exc}") from exc
    if not isinstance(command_args, list):
        raise click.ClickException("--args-json deve ser uma lista JSON")
    approval_state = "approved" if approve else "pending"
    execution_state = "queued" if approve else "not-started"
    payload = {
        "host": host_name,
        "program": program,
        "desired_version": desired_version,
        "target_command": command_key,
        "command_args": command_args,
        "approval_state": approval_state,
        "execution_state": execution_state,
        "priority": priority,
        "requested_by": requested_by or os.environ.get("USER", "operator"),
        "requested_from_host": _default_host_id(),
        "db_write": write_db,
        "generated_at": _now(),
    }
    if not write_db:
        payload["notes"] = [
            "dry-run only; pass --db to insert into DbOmniFleet through PgBouncer",
            "target host executes locally through omni fleet agent once/loop",
        ]
        _emit(payload, json_output)
        return
    env = _db_env()
    _command_template(command_key, host_id=host_name, env=env)
    approved_by_sql = _sql_literal(payload["requested_by"]) if approve else "NULL"
    approved_at_sql = "now()" if approve else "NULL"
    query = f"""
WITH program AS (
    INSERT INTO "TbPrograms" (host_id, name, install_type, current_version, source, managed_by, update_policy, observed_at)
    VALUES ({_sql_literal(host_name)}, {_sql_literal(program)}, 'omni-module', NULL, 'queue-update', 'omni-srv-admin', 'plan-first', now())
    ON CONFLICT (host_id, name, install_type) DO UPDATE SET
        source = EXCLUDED.source,
        managed_by = EXCLUDED.managed_by,
        update_policy = EXCLUDED.update_policy,
        observed_at = now()
    RETURNING id
),
plan AS (
    INSERT INTO "TbUpdatePlans" (
        host_id, program_id, desired_version, dry_run_output, approval_state,
        approved_by, approved_at,
        execution_state, target_command, command_args, execution_profile,
        requested_by, requested_from_host, priority, idempotency_key
    )
    SELECT
        {_sql_literal(host_name)}, program.id, {_sql_literal(desired_version)},
        {_json_literal(payload)}::jsonb, {_sql_literal(approval_state)},
        {approved_by_sql}, {approved_at_sql},
        {_sql_literal(execution_state)}, {_sql_literal(command_key)}, {_json_literal(command_args)}::jsonb,
        'interactive', {_sql_literal(payload["requested_by"])}, {_sql_literal(payload["requested_from_host"])}, {int(priority)},
        encode(digest({_sql_literal(host_name + ':' + program + ':' + desired_version + ':' + command_key + ':' + json.dumps(command_args, sort_keys=True))}, 'sha256'), 'hex')
    FROM program
    ON CONFLICT (idempotency_key) DO UPDATE SET
        dry_run_output = EXCLUDED.dry_run_output,
        approval_state = EXCLUDED.approval_state,
        approved_by = EXCLUDED.approved_by,
        approved_at = EXCLUDED.approved_at,
        execution_state = CASE
            WHEN "TbUpdatePlans".execution_state IN ('succeeded', 'claimed', 'running') THEN "TbUpdatePlans".execution_state
            ELSE EXCLUDED.execution_state
        END,
        updated_at = now()
    RETURNING id, host_id, desired_version, approval_state, execution_state, target_command, command_args, priority, created_at
)
SELECT jsonb_build_object(
    'id', id,
    'host', host_id,
    'desired_version', desired_version,
    'approval_state', approval_state,
    'execution_state', execution_state,
    'target_command', target_command,
    'command_args', command_args,
    'priority', priority,
    'created_at', created_at
) FROM plan;
"""
    record = _psql_json(query, env=env)
    _emit({"db_write": True, "plan": record, "pgbouncer": f"{PGBOUNCER_ENDPOINT[0]}:{PGBOUNCER_ENDPOINT[1]}"}, json_output)


@fleet.command("queue-self-update")
@click.option("--source", type=click.Path(path_type=Path), default=DEFAULT_OMNI_VERSION_MATRIX, show_default=True)
@click.option("--version", "desired_version_override", default=None, help="Override do desired_version do manifest.")
@click.option("--host", "host_ids", multiple=True, help="Host alvo. Repetível. Default: target_hosts do manifest.")
@click.option("--requested-by", default=None, help="Ator que solicitou o plano.")
@click.option("--approve", is_flag=True, help="Cria já aprovado para execução automática.")
@click.option("--priority", default=25, show_default=True, help="Prioridade de fila; menor executa antes.")
@click.option("--db", "write_db", is_flag=True, help="Insere os planos em DbOmniFleet.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def queue_self_update(
    source: Path,
    desired_version_override: str | None,
    host_ids: tuple[str, ...],
    requested_by: str | None,
    approve: bool,
    priority: int,
    write_db: bool,
    json_output: bool,
) -> None:
    """Fila rollout do omni-srv-admin conforme a matriz de versão."""
    matrix = load_omni_version_matrix(source)
    target_hosts = list(host_ids) or [str(item) for item in matrix.get("target_hosts", [])]
    desired_version = _normalize_version(desired_version_override or str(matrix.get("desired_version") or ""))
    if not desired_version:
        raise click.ClickException("desired_version ausente no manifest e nenhum --version informado")
    payload = {
        "component": matrix.get("component") or "omni-srv-admin",
        "github_repo": matrix.get("github_repo"),
        "desired_version": desired_version,
        "target_hosts": target_hosts,
        "requested_by": requested_by or os.environ.get("USER", "operator"),
        "requested_from_host": _default_host_id(),
        "approval_state": "approved" if approve else "pending",
        "db_write": write_db,
        "generated_at": _now(),
        "plans": [],
    }
    if not write_db:
        for host_id in target_hosts:
            path, host, _ = _load_host(host_id)
            host_name = _host_id(host, path.stem)
            host_cfg = (matrix.get("hosts") or {}).get(host_name, {})
            payload["plans"].append(
                {
                    "host": host_name,
                    "desired_version": desired_version,
                    "command_key": host_cfg.get("command_key") or _omni_command_key_for_host(host),
                    "track_branch": host_cfg.get("track_branch") or matrix.get("track_branch") or "main",
                    "repo_dir": host_cfg.get("repo_dir"),
                    "scheduler": host_cfg.get("scheduler"),
                }
            )
        _emit(payload, json_output)
        return

    env = _db_env()
    plans: list[dict[str, Any]] = []
    for host_id in target_hosts:
        path, host, _ = _load_host(host_id)
        host_name = _host_id(host, path.stem)
        host_cfg = (matrix.get("hosts") or {}).get(host_name, {})
        command_key = str(host_cfg.get("command_key") or _omni_command_key_for_host(host))
        track_branch = str(host_cfg.get("track_branch") or matrix.get("track_branch") or "main")
        repo_dir = str(host_cfg.get("repo_dir") or "")
        scheduler = str(host_cfg.get("scheduler") or "")
        _command_template(command_key, host_id=host_name, env=env)
        approved_by_sql = _sql_literal(payload["requested_by"]) if approve else "NULL"
        approved_at_sql = "now()" if approve else "NULL"
        dry_run_payload = {
            "host": host_name,
            "component": "omni-srv-admin",
            "desired_version": desired_version,
            "github_repo": matrix.get("github_repo"),
            "track_branch": track_branch,
            "repo_dir": repo_dir,
            "scheduler": scheduler,
            "target_command": command_key,
            "command_args": [],
            "requested_by": payload["requested_by"],
            "requested_from_host": payload["requested_from_host"],
        }
        query = f"""
WITH program AS (
    INSERT INTO "TbPrograms" (host_id, name, install_type, current_version, source, managed_by, update_policy, observed_at)
    VALUES ({_sql_literal(host_name)}, 'omni-srv-admin', 'git-worktree', NULL,
            {_sql_literal(str(matrix.get("github_repo") or "giovannimnz/omni-srv-admin"))},
            'omni-srv-admin', 'release-auto-update', now())
    ON CONFLICT (host_id, name, install_type) DO UPDATE SET
        source = EXCLUDED.source,
        managed_by = EXCLUDED.managed_by,
        update_policy = EXCLUDED.update_policy,
        observed_at = now()
    RETURNING id
),
version_reset AS (
    DELETE FROM "TbVersions"
    WHERE program_id IN (SELECT id FROM program)
),
version_row AS (
    INSERT INTO "TbVersions" (program_id, current_version, desired_version, policy, pinned, updated_at)
    SELECT program.id, NULL, {_sql_literal(desired_version)}, 'release-auto-update', false, now()
    FROM program
),
plan AS (
    INSERT INTO "TbUpdatePlans" (
        host_id, program_id, desired_version, dry_run_output, approval_state,
        approved_by, approved_at,
        execution_state, target_command, command_args, execution_profile,
        requested_by, requested_from_host, priority, idempotency_key
    )
    SELECT
        {_sql_literal(host_name)}, program.id, {_sql_literal(desired_version)},
        {_json_literal(dry_run_payload)}::jsonb, {_sql_literal('approved' if approve else 'pending')},
        {approved_by_sql}, {approved_at_sql},
        {_sql_literal('queued' if approve else 'not-started')}, {_sql_literal(command_key)}, '[]'::jsonb,
        'interactive', {_sql_literal(payload["requested_by"])}, {_sql_literal(payload["requested_from_host"])}, {int(priority)},
        encode(digest({_sql_literal(host_name + ':omni-srv-admin:' + desired_version + ':' + command_key)}, 'sha256'), 'hex')
    FROM program
    ON CONFLICT (idempotency_key) DO UPDATE SET
        dry_run_output = EXCLUDED.dry_run_output,
        approval_state = EXCLUDED.approval_state,
        approved_by = EXCLUDED.approved_by,
        approved_at = EXCLUDED.approved_at,
        execution_state = CASE
            WHEN "TbUpdatePlans".execution_state IN ('succeeded', 'claimed', 'running') THEN "TbUpdatePlans".execution_state
            ELSE EXCLUDED.execution_state
        END,
        updated_at = now()
    RETURNING id, host_id, desired_version, approval_state, execution_state, target_command, priority, created_at
)
SELECT jsonb_build_object(
    'id', id,
    'host', host_id,
    'desired_version', desired_version,
    'approval_state', approval_state,
    'execution_state', execution_state,
    'target_command', target_command,
    'priority', priority,
    'created_at', created_at
) FROM plan;
"""
        plans.append(_psql_json(query, env=env))

    payload["plans"] = plans
    _emit(payload, json_output)


@fleet.group("agent")
def agent() -> None:
    """Node agent local: heartbeat, telemetria e execução de planos aprovados."""


@agent.command("heartbeat")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--db", "write_db", is_flag=True, help="Grava heartbeat em DbOmniFleet via PgBouncer.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def agent_heartbeat(host_id: str | None, write_db: bool, json_output: bool) -> None:
    """Coleta telemetry local e atualiza cache/DB."""
    resolved_host = host_id or _default_host_id()
    payload = _collect_telemetry(resolved_host)
    _save_heartbeat_cache(payload)
    if write_db:
        _write_heartbeat_db(payload, env=_db_env())
    _append_audit_event(
        {
            "actor": "omni-fleet-agent",
            "host": resolved_host,
            "action": "heartbeat",
            "target": "node-telemetry",
            "result": payload["health"],
            "timestamp": payload["last_contact"],
            "metadata": {"db_write": write_db},
        }
    )
    _emit(payload, json_output)


@agent.command("collect-programs")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--db", "write_db", is_flag=True, help="Grava observações em DbOmniFleet via PgBouncer.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def agent_collect_programs(host_id: str | None, write_db: bool, json_output: bool) -> None:
    """Coleta programas/pacotes/serviços localmente sem mutação."""
    resolved_host = host_id or _default_host_id()
    payload = collect_programs(resolved_host)
    _write_json(PROGRAMS_DIR / f"{resolved_host}.json", payload)
    if write_db:
        _write_program_observations_db(payload, env=_db_env())
    _append_audit_event(
        {
            "actor": "omni-fleet-agent",
            "host": resolved_host,
            "action": "programs.collect",
            "target": "local-read-only-collectors",
            "result": "written" if write_db else "collected",
            "timestamp": payload["generated_at"],
            "metadata": {
                "program_count": payload["program_count"],
                "warning_count": len(payload.get("warnings", [])),
                "db_write": write_db,
            },
        }
    )
    _emit(payload, json_output)


@agent.command("collect-version")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--source", type=click.Path(path_type=Path), default=DEFAULT_OMNI_VERSION_MATRIX, show_default=True)
@click.option("--db", "write_db", is_flag=True, help="Grava observações em TbVersion via PgBouncer.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def agent_collect_version(host_id: str | None, source: Path, write_db: bool, json_output: bool) -> None:
    """Coleta estado local do repo omni-srv-admin sem mutação."""
    resolved_host = host_id or _default_host_id()
    matrix = load_omni_version_matrix(source)
    host_cfg = (matrix.get("hosts") or {}).get(resolved_host, {})
    repo_root = Path(str(host_cfg.get("repo_dir") or REPO))
    payload = collect_omni_version(
        resolved_host,
        repo_root=repo_root,
        github_repo=str(matrix.get("github_repo") or "giovannimnz/omni-srv-admin"),
        desired_version=str(host_cfg.get("desired_version") or matrix.get("desired_version") or ""),
        track_branch=str(host_cfg.get("track_branch") or matrix.get("track_branch") or "main"),
    )
    _write_json(VERSIONS_DIR / f"{resolved_host}.json", payload)
    if write_db:
        _write_omni_version_db(payload, env=_db_env())
    _append_audit_event(
        {
            "actor": "omni-fleet-agent",
            "host": resolved_host,
            "action": "version.collect",
            "target": "TbVersion",
            "result": "written" if write_db else "collected",
            "timestamp": payload["observed_at"],
            "metadata": {"db_write": write_db, "installed_version": payload.get("installed_version")},
        }
    )
    _emit(payload, json_output)


def _run_agent_cycle(
    host_id: str,
    *,
    apply_changes: bool,
    env: dict[str, str] | None = None,
    write_db: bool = True,
) -> dict[str, Any]:
    telemetry = _collect_telemetry(host_id)
    _save_heartbeat_cache(telemetry)
    if write_db and env is not None:
        _write_heartbeat_db(telemetry, env=env)

    version_payload: dict[str, Any] | None = None
    try:
        matrix = load_omni_version_matrix()
        host_cfg = (matrix.get("hosts") or {}).get(host_id, {})
        repo_root = Path(str(host_cfg.get("repo_dir") or REPO))
        version_payload = collect_omni_version(
            host_id,
            repo_root=repo_root,
            github_repo=str(matrix.get("github_repo") or "giovannimnz/omni-srv-admin"),
            desired_version=str(host_cfg.get("desired_version") or matrix.get("desired_version") or ""),
            track_branch=str(host_cfg.get("track_branch") or matrix.get("track_branch") or "main"),
        )
        _write_json(VERSIONS_DIR / f"{host_id}.json", version_payload)
        if write_db and env is not None:
            _write_omni_version_db(version_payload, env=env)
    except Exception as exc:
        _append_audit_event(
            {
                "actor": "omni-fleet-agent",
                "host": host_id,
                "action": "version.collect",
                "target": "TbVersion",
                "result": "degraded",
                "timestamp": _now(),
                "metadata": {"error": _redact_text(str(exc))},
            }
        )

    if env is None:
        return {"cycle": _now(), "host": host_id, "status": "idle", "telemetry": telemetry, "version": version_payload}

    plan = _claim_next_plan(host_id, env=env)
    if not plan:
        return {"cycle": _now(), "host": host_id, "status": "idle", "telemetry": telemetry, "version": version_payload}

    result = _execute_plan(plan, apply_changes=apply_changes, env=env)
    if apply_changes and plan.get("id"):
        _finish_plan_db(str(plan["id"]), result, env=env)
    return {"cycle": _now(), "host": host_id, "status": result.get("status"), "plan": result, "telemetry": telemetry, "version": version_payload}


@agent.command("cycle")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--apply", "apply_changes", is_flag=True, help="Executa planos aprovados; sem isto roda dry-run.")
@click.option("--json", "json_output", is_flag=True, help="Emite resultado em JSON.")
def agent_cycle(host_id: str | None, apply_changes: bool, json_output: bool) -> None:
    """Executa um ciclo único: heartbeat + versão + um plano aprovado."""
    resolved_host = host_id or _default_host_id()
    env = _db_env()
    result = _run_agent_cycle(resolved_host, apply_changes=apply_changes, env=env, write_db=True)
    _emit(result, json_output)


@agent.command("self-update-runner")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--source", type=click.Path(path_type=Path), default=DEFAULT_OMNI_VERSION_MATRIX, show_default=True)
@click.option("--desired-version", required=True, help="Versão/tag desejada.")
@click.option("--json", "json_output", is_flag=True, help="Emite resultado em JSON.")
def agent_self_update_runner(host_id: str | None, source: Path, desired_version: str, json_output: bool) -> None:
    """Runner local allowlisted que aplica update do repo omni-srv-admin."""
    resolved_host = host_id or _default_host_id()
    matrix = load_omni_version_matrix(source)
    host_cfg = (matrix.get("hosts") or {}).get(resolved_host, {})
    repo_root = Path(str(host_cfg.get("repo_dir") or REPO))
    result = apply_omni_self_update(
        resolved_host,
        repo_root=repo_root,
        desired_version=desired_version,
        track_branch=str(host_cfg.get("track_branch") or matrix.get("track_branch") or "main"),
        github_repo=str(matrix.get("github_repo") or "giovannimnz/omni-srv-admin"),
    )
    _append_audit_event(
        {
            "actor": "omni-fleet-agent",
            "host": resolved_host,
            "action": "self-update.run",
            "target": "omni-srv-admin",
            "result": result.get("status"),
            "timestamp": result.get("finished_at"),
            "metadata": result,
        }
    )
    _emit(result, json_output)


@agent.command("once")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--plan-file", type=click.Path(path_type=Path), default=None, help="Executa plano JSON local para teste.")
@click.option("--db", "use_db", is_flag=True, help="Busca plano aprovado em DbOmniFleet via PgBouncer.")
@click.option("--apply", "apply_changes", is_flag=True, help="Executa de fato; sem isto apenas renderiza dry-run.")
@click.option("--json", "json_output", is_flag=True, help="Emite resultado em JSON.")
def agent_once(host_id: str | None, plan_file: Path | None, use_db: bool, apply_changes: bool, json_output: bool) -> None:
    """Executa no máximo um update plan aprovado para este host."""
    resolved_host = host_id or _default_host_id()
    env = _db_env() if use_db else None
    plan: dict[str, Any] | None = None
    if plan_file:
        plan = json.loads(plan_file.read_text())
        plan.setdefault("host_id", resolved_host)
    elif use_db:
        plan = _claim_next_plan(resolved_host, env=env or {})
    else:
        raise click.ClickException("use --plan-file para teste local ou --db para buscar na fila")
    if not plan:
        _emit({"host": resolved_host, "status": "idle", "source": "database" if use_db else "plan-file"}, json_output)
        return
    result = _execute_plan(plan, apply_changes=apply_changes, env=env)
    if use_db and env is not None and apply_changes and plan.get("id"):
        _finish_plan_db(str(plan["id"]), result, env=env)
    _append_audit_event(
        {
            "actor": "omni-fleet-agent",
            "host": resolved_host,
            "action": "update-plan.execute",
            "target": result.get("command_key"),
            "result": result.get("status"),
            "timestamp": result.get("finished_at"),
            "metadata": result,
        }
    )
    _emit(result, json_output)


@agent.command("loop")
@click.option("--host", "host_id", default=None, help="Host id; default usa OMNI_HOST_ID/hostname.")
@click.option("--interval", default=30, show_default=True, help="Intervalo entre ciclos em segundos.")
@click.option("--apply", "apply_changes", is_flag=True, help="Executa planos aprovados; sem isto roda dry-run.")
def agent_loop(host_id: str | None, interval: int, apply_changes: bool) -> None:
    """Loop persistente para systemd: heartbeat + um plano por ciclo."""
    resolved_host = host_id or _default_host_id()
    while True:
        try:
            env = _db_env()
            result = _run_agent_cycle(resolved_host, apply_changes=apply_changes, env=env, write_db=True)
            click.echo(json.dumps(result, sort_keys=True))
        except Exception as exc:
            _append_audit_event(
                {
                    "actor": "omni-fleet-agent",
                    "host": resolved_host,
                    "action": "agent.loop",
                    "target": "DbOmniFleet",
                    "result": "degraded",
                    "timestamp": _now(),
                    "metadata": {"error": _redact_text(str(exc))},
                }
            )
            click.echo(json.dumps({"cycle": _now(), "host": resolved_host, "status": "degraded", "error": _redact_text(str(exc))}, sort_keys=True))
        time.sleep(max(interval, 5))


@fleet.group("monitor")
def monitor() -> None:
    """Visão cross-server de status e recursos da frota."""


@monitor.command("hosts")
@click.option("--db/--local", "use_db", default=True, show_default=True, help="Lê DbOmniFleet; fallback local se indisponível.")
@click.option("--json", "json_output", is_flag=True, help="Emite payload em JSON.")
def monitor_hosts(use_db: bool, json_output: bool) -> None:
    """Mostra como um servidor enxerga os demais via heartbeat/telemetria."""
    payload = _monitor_payload(use_db=use_db)
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    click.echo(f"source: {payload['source']}")
    if payload.get("db_error"):
        click.echo(f"db_error: {payload['db_error']}")
    click.echo(f"{'HOST':24} {'STATUS':10} {'LAST_CONTACT':25} {'LOAD':>6} {'MEM%':>6} {'DISK%':>6}")
    for host in payload["hosts"]:
        click.echo(
            f"{str(host.get('host')):24} {str(host.get('status')):10} "
            f"{str(host.get('last_contact') or '-'):25} "
            f"{str(host.get('load_1m') or '-'):>6} "
            f"{str(host.get('memory_used_percent') or '-'):>6} "
            f"{str(host.get('disk_root_used_percent') or '-'):>6}"
        )


@fleet.command("audit")
@click.option("--host", "host_id", default=None, help="Filtra por host.")
@click.option("--action", default=None, help="Filtra por ação.")
@click.option("--json", "json_output", is_flag=True, help="Emite eventos em JSON.")
def audit(host_id: str | None, action: str | None, json_output: bool) -> None:
    """Lê eventos locais de auditoria quando existirem."""
    events: list[dict[str, Any]] = []
    if AUDIT_EVENTS.exists():
        for line in AUDIT_EVENTS.read_text().splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = {"result": "invalid-json", "raw": _redact_text(line[:120])}
            if host_id and event.get("host") != host_id:
                continue
            if action and event.get("action") != action:
                continue
            events.append(_redact(event))
    payload = {
        "audit_log": str(AUDIT_EVENTS),
        "host": host_id,
        "action": action,
        "event_count": len(events),
        "events": events,
        "schema": {
            "actor": "string",
            "host": "string",
            "action": "string",
            "target": "string",
            "result": "string",
            "timestamp": "RFC3339",
            "metadata": "object",
        },
    }
    _emit(payload, json_output)


@fleet.command("status")
@click.option("--all", "all_hosts", is_flag=True, help="Inclui status de todos os hosts inventariados.")
def status(all_hosts: bool) -> None:
    """Status inicial do módulo fleet."""
    hosts_dir = _hosts_dir()
    click.echo(f"repo:  {REPO}")
    click.echo(f"hosts: {hosts_dir} ({'ok' if hosts_dir.exists() else 'missing'})")
    click.echo(f"legacy_hosts: {LEGACY_HOSTS_DIR} ({'present' if LEGACY_HOSTS_DIR.exists() else 'absent'})")
    click.echo("control_plane: M004 live foundation present; generic --apply remains gated")
    click.echo(f"heartbeat_dir: {HEARTBEAT_DIR}")
    click.echo(f"audit_log: {AUDIT_EVENTS}")
    if all_hosts and hosts_dir.exists():
        click.echo("")
        click.echo(f"{'HOST':24} {'STATUS':10} HEALTH")
        for path in sorted(hosts_dir.glob("*.yaml")):
            data = _simple_yaml(path.read_text())
            payload = _heartbeat_payload(data, path)
            click.echo(f"{payload['host']:24} {payload['status']:10} {payload['health']}")
