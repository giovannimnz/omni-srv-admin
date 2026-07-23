#!/usr/bin/env python3
"""Read-only Ubuntu Pro/ESM fleet inventory for G18 Phase 28.

The collector intentionally keeps all probes in an allowlist and writes only
redacted Markdown. It must not read Ubuntu Pro token contents or run package,
service, Landscape, PM2, XRDP, or webhook mutations.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / ".planning/workstreams/runtime-trust-codex-delivery-convergence"
    / "phases/28-g18-ubuntu-pro-esm-fleet-gates/28-01-G18-INVENTORY.md"
)
ALLOWED_HOSTS = ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv")
TOKEN_PATHS = (
    "/home/ubuntu/secrets/ubuntu-pro-token.txt",
    "/home/ubuntu/ubuntu-pro-token.txt",
)
SERVICE_NAMES = (
    "landscape-client",
    "xrdp",
    "xrdp-sesman",
    "pm2-ubuntu",
    "k3s",
    "k3s-agent",
)


MUTATION_PATTERNS = (
    re.compile(
        r"\bapt(?:-get)?\s+"
        r"(?:update|upgrade|full-upgrade|dist-upgrade|install|remove|purge|"
        r"autoremove|autoclean|clean)\b",
        re.I,
    ),
    re.compile(
        r"\bsystemctl\s+"
        r"(?:start|stop|restart|reload|enable|disable|mask|unmask|daemon-reload)\b",
        re.I,
    ),
    re.compile(r"\bservice\s+\S+\s+(?:start|stop|restart|reload)\b", re.I),
    re.compile(
        r"\bpro\s+(?:attach|detach|enable|disable|refresh|auto-attach|config|fix)\b",
        re.I,
    ),
    re.compile(r"\blandscape-config\s+(?!--is-registered\b)", re.I),
    re.compile(
        r"\bpm2\s+(?:start|stop|restart|reload|delete|kill|save|resurrect|flush)\b",
        re.I,
    ),
    re.compile(r"(?:^|\s)(?:curl|http)\b[^\n]*-X\s*POST\b", re.I),
    re.compile(r"(?:^|\s)http\b[^\n]*\sPOST\b", re.I),
    re.compile(r"\bwget\b[^\n]*--post", re.I),
)


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
ACCOUNT_OR_CONTRACT_RE = re.compile(r"\b[ac]A[A-Za-z0-9_-]{12,}\b")
TOKEN_LIKE_RE = re.compile(r"\b[A-Za-z0-9_]{32,}\b")


@dataclass(frozen=True)
class Probe:
    name: str
    category: str
    command: str


PROBES = (
    Probe(
        "hostname",
        "host identity",
        "hostnamectl --static 2>/dev/null || hostname",
    ),
    Probe(
        "os_release",
        "host identity",
        "if [ -r /etc/os-release ]; then . /etc/os-release; "
        'printf "%s\\n" "${PRETTY_NAME:-unknown}"; '
        "else lsb_release -ds 2>/dev/null || uname -s; fi",
    ),
    Probe("kernel", "host identity", "uname -r"),
    Probe(
        "ubuntu_pro_client",
        "ubuntu pro package",
        "dpkg-query -W -f='${Version}\\n' ubuntu-pro-client 2>/dev/null || true",
    ),
    Probe("pro_status_json", "ubuntu pro status", "pro status --format json 2>&1"),
    Probe(
        "token_files",
        "token file metadata only",
        "for p in /home/ubuntu/secrets/ubuntu-pro-token.txt "
        "/home/ubuntu/ubuntu-pro-token.txt; do "
        'if [ -e "$p" ]; then stat -c "%n|%U|%G|%a|%s|%F" "$p"; '
        'else printf "%s|missing|-|-|0|missing\\n" "$p"; fi; '
        "done",
    ),
    Probe(
        "apt_sources",
        "apt source metadata only",
        "for p in /etc/apt/sources.list /etc/apt/sources.list.d/*; do "
        '[ -f "$p" ] || continue; '
        'case "$p" in *.list|*.sources|*.list.distUpgrade|*.sources.distUpgrade) '
        'stat -c "%n|%U|%G|%a|%s" "$p";; esac; '
        "done",
    ),
    Probe("upgradable", "apt cached upgradable list", "apt list --upgradable 2>/dev/null || true"),
    Probe("held_packages", "apt held packages", "apt-mark showhold 2>/dev/null || true"),
    Probe(
        "reboot_required",
        "reboot marker",
        '[ -f /var/run/reboot-required ] && printf "yes\\n" || printf "no\\n"',
    ),
    Probe(
        "disk",
        "disk capacity",
        "for p in / /boot /var; do "
        "df -P -B1 \"$p\" 2>/dev/null | "
        "awk -v p=\"$p\" 'NR==2 {print p \"|\" $1 \"|\" $2 \"|\" $3 \"|\" $4 \"|\" $5 \"|\" $6}'; "
        "done",
    ),
    Probe(
        "services",
        "sensitive service state",
        "for s in landscape-client xrdp xrdp-sesman pm2-ubuntu k3s k3s-agent; do "
        'a="$(systemctl is-active "$s" 2>/dev/null || true)"; '
        'e="$(systemctl is-enabled "$s" 2>/dev/null || true)"; '
        'printf "%s|%s|%s\\n" "$s" "${a:-unknown}" "${e:-unknown}"; '
        "done",
    ),
    Probe(
        "landscape",
        "landscape read-only registration check",
        "if command -v landscape-config >/dev/null 2>&1; then "
        'if [ -r /etc/landscape/client.conf ]; then '
        "landscape-config --is-registered >/dev/null 2>&1; "
        'printf "registered_exit=%s\\n" "$?"; '
        'elif [ -e /etc/landscape/client.conf ]; then '
        'printf "client_conf=unreadable\\n"; '
        'else printf "client_conf=missing\\n"; fi; '
        'else printf "landscape-config=missing\\n"; fi; '
        "if command -v landscape-client >/dev/null 2>&1; then "
        "landscape-client --version 2>&1 | head -n 1; fi",
    ),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_scalar(value: str) -> str:
    value = value.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_host_inventory(host: str) -> dict[str, Any]:
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"host {host!r} is outside the G18 allowlist")
    path = ROOT / "inventory" / "hosts" / f"{host}.yaml"
    if not path.exists():
        raise FileNotFoundError(path)

    result: dict[str, Any] = {"id": host, "path": str(path.relative_to(ROOT))}
    section: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = clean_scalar(value)
            if value == "":
                section = key
                result.setdefault(section, {})
            else:
                section = None
                result[key] = value
        elif indent == 2 and section and ":" in line:
            key, value = line.split(":", 1)
            bucket = result.setdefault(section, {})
            if isinstance(bucket, dict):
                bucket[key.strip()] = clean_scalar(value)
    return result


def parse_hosts_arg(value: str) -> list[str]:
    hosts = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [host for host in hosts if host not in ALLOWED_HOSTS]
    if unknown:
        allowed = ", ".join(ALLOWED_HOSTS)
        raise ValueError(f"unsupported host(s): {', '.join(unknown)}; allowed: {allowed}")
    return hosts


def validate_probe_command(command: str) -> None:
    checked_command = command.replace("command -v landscape-config", "command-v-lc")
    for pattern in MUTATION_PATTERNS:
        if pattern.search(checked_command):
            raise ValueError(f"mutation command rejected: {command}")


def validate_all_probes() -> None:
    for probe in PROBES:
        validate_probe_command(probe.command)


def redact_text(value: str) -> str:
    value = EMAIL_RE.sub("<redacted-email>", value)
    value = ACCOUNT_OR_CONTRACT_RE.sub("<redacted-account-or-contract-id>", value)
    value = TOKEN_LIKE_RE.sub("<redacted-token-like>", value)
    return value


def redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            lowered = key.lower()
            if any(term in lowered for term in ("email", "account", "contract", "token")):
                if child in (None, "", [], {}):
                    redacted[key] = child
                else:
                    redacted[key] = "<redacted>"
            else:
                redacted[key] = redact_json(child)
        return redacted
    if isinstance(value, list):
        return [redact_json(child) for child in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def find_key(value: Any, names: set[str]) -> Any | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in names:
                return child
        for child in value.values():
            found = find_key(child, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_key(child, names)
            if found is not None:
                return found
    return None


def has_key_fragment(value: Any, fragments: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            if any(fragment in lowered for fragment in fragments) and child not in (None, "", [], {}):
                return True
            if has_key_fragment(child, fragments):
                return True
    elif isinstance(value, list):
        return any(has_key_fragment(child, fragments) for child in value)
    return False


def extract_services_from_pro(value: Any) -> dict[str, str]:
    services: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            name = node.get("name") or node.get("service") or node.get("serviceName")
            if isinstance(name, str):
                lowered = name.lower()
                if lowered in {"esm-apps", "esm-infra", "landscape"}:
                    status = (
                        node.get("status")
                        or node.get("available")
                        or node.get("enabled")
                        or node.get("entitled")
                        or node.get("description")
                        or "present"
                    )
                    services[lowered] = str(status)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return services


def parse_pro_status(stdout: str, exit_code: int) -> dict[str, Any]:
    parsed: Any | None = None
    attached: Any | None = None
    services: dict[str, str] = {}
    account_present = False
    contract_present = False
    parse_error: str | None = None
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
            attached = find_key(parsed, {"attached"})
            account_present = has_key_fragment(parsed, ("account", "email"))
            contract_present = has_key_fragment(parsed, ("contract", "subscription"))
            services = extract_services_from_pro(parsed)
        except json.JSONDecodeError as exc:
            parse_error = f"{exc.__class__.__name__}: {exc}"
    return {
        "exit_code": exit_code,
        "attached": attached,
        "account_identity_present": account_present,
        "contract_identity_present": contract_present,
        "services": services,
        "parse_error": parse_error,
        "redacted_json": redact_json(parsed) if parsed is not None else None,
        "redacted_output": redact_text(stdout.strip()[:2000]),
    }


def split_probe_fields(line: str) -> list[str]:
    if "|" in line:
        return line.split("|")
    if "\\t" in line:
        return line.split("\\t")
    return line.split("\t")


def parse_token_files(stdout: str) -> list[dict[str, str]]:
    rows = []
    for line in stdout.splitlines():
        parts = split_probe_fields(line)
        if len(parts) != 6:
            continue
        path, owner, group, mode, size, file_type = parts
        rows.append(
            {
                "path": path,
                "present": "yes" if owner != "missing" else "no",
                "owner": owner if owner != "missing" else "-",
                "group": group,
                "mode": mode,
                "size_bytes": size,
                "type": file_type,
            }
        )
    return rows


def source_type(path: str) -> str:
    if path.endswith(".sources") or path.endswith(".sources.distUpgrade"):
        return "DEB822"
    if path.endswith(".list") or path.endswith(".list.distUpgrade"):
        return "one-line"
    return "unknown"


def parse_apt_sources(stdout: str) -> list[dict[str, str]]:
    rows = []
    for line in stdout.splitlines():
        parts = split_probe_fields(line)
        if len(parts) != 5:
            continue
        path, owner, group, mode, size = parts
        rows.append(
            {
                "path": path,
                "type": source_type(path),
                "owner": owner,
                "group": group,
                "mode": mode,
                "size_bytes": size,
            }
        )
    return rows


def parse_upgradable(stdout: str) -> dict[str, Any]:
    packages = []
    esm_apps = 0
    esm_infra = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Listing..."):
            continue
        packages.append(line)
        lowered = line.lower()
        if "esm-infra" in lowered or "infra-security" in lowered:
            esm_infra += 1
        elif "esm-apps" in lowered or "apps-security" in lowered or "+esm" in lowered:
            esm_apps += 1
    return {
        "total": len(packages),
        "esm_apps": esm_apps,
        "esm_infra": esm_infra,
        "non_esm": max(len(packages) - esm_apps - esm_infra, 0),
        "sample": [redact_text(item) for item in packages[:20]],
    }


def parse_disk(stdout: str) -> list[dict[str, Any]]:
    rows = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = split_probe_fields(line)
        if len(parts) != 7:
            continue
        label, filesystem, size, used, available, percent, mount = parts
        try:
            percent_value = int(percent.rstrip("%"))
        except ValueError:
            percent_value = -1
        status = "ok"
        if percent_value >= 90:
            status = "blocker"
        elif percent_value >= 80:
            status = "warning"
        rows.append(
            {
                "filesystem": filesystem,
                "size_bytes": size,
                "used_bytes": used,
                "available_bytes": available,
                "used_percent": percent,
                "path": label,
                "mount": mount,
                "status": status,
            }
        )
    return rows


def parse_services(stdout: str) -> list[dict[str, str]]:
    rows = []
    for line in stdout.splitlines():
        parts = split_probe_fields(line)
        if len(parts) < 3:
            continue
        rows.append({"service": parts[0], "active": parts[1] or "-", "enabled": parts[2] or "-"})
    return rows


def parse_landscape(stdout: str) -> dict[str, str]:
    result = {"registered": "unknown", "version": "-", "client_conf": "unknown"}
    for line in stdout.splitlines():
        if line.startswith("registered_exit="):
            exit_code = line.split("=", 1)[1].strip()
            result["registered"] = "yes" if exit_code == "0" else "no"
            result["client_conf"] = "readable"
        elif line.startswith("client_conf=unreadable"):
            result["registered"] = "permission-limited"
            result["client_conf"] = "unreadable"
        elif line.startswith("client_conf=missing"):
            result["registered"] = "client config missing"
            result["client_conf"] = "missing"
        elif line.startswith("landscape-config=missing"):
            result["registered"] = "not installed"
            result["client_conf"] = "not installed"
        elif line.strip():
            result["version"] = redact_text(line.strip())
    return result


def short_identifier(value: Any) -> str:
    if not value:
        return "-"
    text = str(value)
    if len(text) <= 18:
        return redact_text(text)
    return f"{text[:12]}...{text[-8:]}"


def run_probe(target: str, probe: Probe) -> dict[str, Any]:
    validate_probe_command(probe.command)
    args = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "NumberOfPasswordPrompts=0",
        "-o",
        "ConnectTimeout=10",
        target,
        probe.command,
    ]
    try:
        completed = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=35,
            check=False,
        )
        return {
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": redact_text(completed.stderr.strip()[:2000]),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": "ssh probe timed out after 35s",
        }


def collect_host(host: str) -> dict[str, Any]:
    inventory = load_host_inventory(host)
    access = inventory.get("access", {})
    target = access.get("ssh") if isinstance(access, dict) else None
    if not target:
        raise ValueError(f"{host} inventory is missing access.ssh")

    probes = {probe.name: run_probe(str(target), probe) for probe in PROBES}
    pro_status = parse_pro_status(
        probes["pro_status_json"]["stdout"], probes["pro_status_json"]["exit_code"]
    )
    backup = inventory.get("backup", {}) if isinstance(inventory.get("backup"), dict) else {}
    oci = inventory.get("oci", {}) if isinstance(inventory.get("oci"), dict) else {}
    return {
        "host": host,
        "inventory": inventory,
        "target": target,
        "vpn_ip": access.get("vpn_ip", "-") if isinstance(access, dict) else "-",
        "public_ip": access.get("public_ip", "-") if isinstance(access, dict) else "-",
        "pro_status": pro_status,
        "token_files": parse_token_files(probes["token_files"]["stdout"]),
        "apt_sources": parse_apt_sources(probes["apt_sources"]["stdout"]),
        "upgradable": parse_upgradable(probes["upgradable"]["stdout"]),
        "held_packages": [
            redact_text(line.strip())
            for line in probes["held_packages"]["stdout"].splitlines()
            if line.strip()
        ],
        "reboot_required": probes["reboot_required"]["stdout"].strip() or "unknown",
        "disk": parse_disk(probes["disk"]["stdout"]),
        "services": parse_services(probes["services"]["stdout"]),
        "landscape": parse_landscape(probes["landscape"]["stdout"]),
        "hostname": redact_text(probes["hostname"]["stdout"].strip() or "-"),
        "os_release": redact_text(probes["os_release"]["stdout"].strip() or "-"),
        "kernel": redact_text(probes["kernel"]["stdout"].strip() or "-"),
        "ubuntu_pro_client": redact_text(probes["ubuntu_pro_client"]["stdout"].strip() or "-"),
        "oci": {
            "last_snapshot_id": short_identifier(oci.get("last_snapshot_id")),
            "last_snapshot_at": oci.get("last_snapshot_at", "-"),
            "routine_schedule": oci.get("routine_schedule", "-"),
        },
        "gdrive_base": backup.get("gdrive_base", "-"),
        "probe_errors": {
            name: data["stderr"]
            for name, data in probes.items()
            if data["exit_code"] not in (0,) and data["stderr"]
        },
    }


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["-" for _ in headers]]
    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        output.append("| " + " | ".join(redact_text(str(cell)) for cell in row) + " |")
    return "\n".join(output)


def blockers_for_host(host: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    pro_status = host["pro_status"]
    if pro_status["exit_code"] != 0:
        blockers.append("`pro status --format json` did not exit cleanly")
    if pro_status.get("attached") not in (True, "yes", "true", "attached"):
        blockers.append("Ubuntu Pro attached state is not confirmed true")
    for service in ("esm-apps", "esm-infra"):
        state = str(pro_status["services"].get(service, "")).lower()
        if not state or ("enable" not in state and "yes" not in state and "true" not in state):
            blockers.append(f"{service} enabled state is not confirmed")
    if not any(row["present"] == "yes" for row in host["token_files"]):
        blockers.append("no Ubuntu Pro token file found at approved paths")
    if not host["apt_sources"]:
        blockers.append("no apt source metadata returned")
    if any(row.get("status") == "blocker" for row in host["disk"]):
        blockers.append("one or more required filesystems are at >=90% usage")
    if host["reboot_required"] == "yes":
        blockers.append("reboot-required marker is present")
    if host["oci"]["last_snapshot_id"] == "-":
        blockers.append("OCI snapshot metadata missing from repo inventory")
    if host["gdrive_base"] == "-":
        blockers.append("GDrive backup base missing from repo inventory")
    return blockers


def render_host_section(host: dict[str, Any]) -> str:
    pro = host["pro_status"]
    services = pro["services"]
    blockers = blockers_for_host(host)
    lines = [
        f"## {host['host']}",
        "",
        md_table(
            ["Field", "Value"],
            [
                ["inventory target", host["target"]],
                ["vpn ip", host["vpn_ip"]],
                ["public ip", host["public_ip"]],
                ["remote hostname", host["hostname"]],
                ["OS", host["os_release"]],
                ["kernel", host["kernel"]],
                ["ubuntu-pro-client", host["ubuntu_pro_client"]],
                ["Ubuntu Pro attached", pro.get("attached", "unknown")],
                ["account identity", "present/redacted" if pro["account_identity_present"] else "not reported"],
                ["contract identity", "present/redacted" if pro["contract_identity_present"] else "not reported"],
                ["esm-apps", services.get("esm-apps", "not reported")],
                ["esm-infra", services.get("esm-infra", "not reported")],
                ["Landscape registration", host["landscape"]["registered"]],
                ["Landscape client.conf", host["landscape"].get("client_conf", "unknown")],
                ["Landscape client", host["landscape"]["version"]],
                ["reboot required", host["reboot_required"]],
            ],
        ),
        "",
        "### Token file metadata",
        "",
        "Token contents were not read, hashed, copied, or printed.",
        "",
        md_table(
            ["Path", "Present", "Owner", "Group", "Mode", "Bytes", "Type"],
            [
                [
                    row["path"],
                    row["present"],
                    row["owner"],
                    row["group"],
                    row["mode"],
                    row["size_bytes"],
                    row["type"],
                ]
                for row in host["token_files"]
            ],
        ),
        "",
        "### Apt sources",
        "",
        md_table(
            ["Path", "Format", "Owner", "Group", "Mode", "Bytes"],
            [
                [
                    row["path"],
                    row["type"],
                    row["owner"],
                    row["group"],
                    row["mode"],
                    row["size_bytes"],
                ]
                for row in host["apt_sources"]
            ],
        ),
        "",
        "### Upgradable packages",
        "",
        md_table(
            ["Total", "ESM Apps", "ESM Infra", "Non-ESM"],
            [
                [
                    host["upgradable"]["total"],
                    host["upgradable"]["esm_apps"],
                    host["upgradable"]["esm_infra"],
                    host["upgradable"]["non_esm"],
                ]
            ],
        ),
        "",
        "Sample (first 20 cached entries, redacted):",
        "",
    ]
    if host["upgradable"]["sample"]:
        lines.extend(f"- `{item}`" for item in host["upgradable"]["sample"])
    else:
        lines.append("- none reported")
    lines.extend(
        [
            "",
            "### Held packages",
            "",
        ]
    )
    if host["held_packages"]:
        lines.extend(f"- `{item}`" for item in host["held_packages"])
    else:
        lines.append("- none reported")
    lines.extend(
        [
            "",
            "### Disk capacity",
            "",
            md_table(
                ["Path", "Mount", "Used", "Available bytes", "Status"],
                [
                    [
                        row["path"],
                        row["mount"],
                        row["used_percent"],
                        row["available_bytes"],
                        row["status"],
                    ]
                    for row in host["disk"]
                ],
            ),
            "",
            "### Sensitive service state",
            "",
            md_table(
                ["Service", "Active", "Enabled"],
                [[row["service"], row["active"], row["enabled"]] for row in host["services"]],
            ),
            "",
            "### Backup and snapshot manifest",
            "",
            md_table(
                ["Input", "Value"],
                [
                    ["OCI last snapshot", host["oci"]["last_snapshot_id"]],
                    ["OCI last snapshot at", host["oci"]["last_snapshot_at"]],
                    ["OCI routine schedule", host["oci"]["routine_schedule"]],
                    ["GDrive backup base", host["gdrive_base"]],
                ],
            ),
            "",
            "### Blockers for Phase 29 mutation gate",
            "",
        ]
    )
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- none from read-only inventory")
    if host["probe_errors"]:
        lines.extend(["", "### Probe errors", ""])
        for name, stderr in sorted(host["probe_errors"].items()):
            lines.append(f"- `{name}`: {stderr or 'non-zero exit'}")
    return "\n".join(lines)


def render_report(hosts: list[dict[str, Any]], dry_run_commands: bool = False) -> str:
    generated_at = utc_now()
    command_rows = [[probe.category, f"`{probe.command}`"] for probe in PROBES]
    host_rows = [
        [host["host"], host["target"], host["vpn_ip"], host["public_ip"], host["inventory"]["path"]]
        for host in hosts
    ]
    sections = [
        "# Phase 28 Plan 01: G18 Ubuntu Pro/ESM Inventory",
        "",
        f"**Generated:** {generated_at}",
        "**Requirements:** G18-01, G18-02",
        "**Mode:** read-only/prep only",
        "",
        "No live mutation executed. This report was generated with SSH read-only probes only; "
        "it did not run apt upgrade/full-upgrade/autoremove/install/remove, package cache refresh, "
        "XRDP/RDP restart, PM2 restart, Landscape mutation, Ubuntu Pro attach/detach/refresh/enable, "
        "or webhook POST.",
        "",
        "## Fleet targets",
        "",
        md_table(["Host", "SSH target", "VPN IP", "Public IP", "Inventory file"], host_rows),
        "",
        "## Command classes used",
        "",
        md_table(["Category", "Command"], command_rows),
        "",
        "## Redaction policy",
        "",
        "- Ubuntu Pro account emails, account IDs, contract IDs, and token-like values are redacted before Markdown output.",
        "- Ubuntu Pro token files are audited with `stat` metadata only: path, presence, owner, group, mode, byte size, and file type.",
        "- Token contents are never read, hashed, copied, or printed.",
        "- Apt source contents are not copied; only filename, inferred format, owner, group, mode, and byte size are reported.",
        "",
        "## Phase 29 gate inputs",
        "",
        "- Confirm each host has Ubuntu Pro attached, `esm-apps` enabled, and `esm-infra` enabled.",
        "- Confirm account/contract identity is present but keep the exact values out of docs and logs.",
        "- Confirm token file metadata is present at an approved path before any detach/attach fallback.",
        "- Confirm OCI snapshot metadata and GDrive backup base exist before any live apt mutation.",
        "- Resolve any disk, reboot-required, SSH, Pro, Landscape, XRDP, PM2, or K3s blocker listed per host.",
    ]
    if dry_run_commands:
        sections.extend(["", "## Dry-run command listing only", ""])
        sections.append("No SSH probes were executed in this mode.")
    else:
        for host in hosts:
            sections.extend(["", render_host_section(host)])
    return "\n".join(sections).rstrip() + "\n"


def run_self_test() -> None:
    validate_all_probes()
    rejected = [
        "sudo apt upgrade -y",
        "apt-get update",
        "systemctl restart xrdp",
        "pro attach token",
        "pro refresh",
        "landscape-config --silent",
        "pm2 restart all",
        "curl -X POST https://example.invalid/webhook",
    ]
    for command in rejected:
        try:
            validate_probe_command(command)
        except ValueError:
            continue
        raise AssertionError(f"mutation command was not rejected: {command}")

    sample = (
        "email giovannimunizds@example.com "
        "account aACjgTUlPaemUk68kWpiA_T_pc_BvVmGrSbZaqbHSTVY "
        "contract cAeDPAsrfIYX2-3JMWGJW6cuB48P6m-r_KOMfHsauiJ8 "
        "token bd5ee0cc50950db5de548cec91d026a8d014db2bc1a3d191e9472bdb5b12641a"
    )
    redacted = redact_text(sample)
    for secret in (
        "giovannimunizds@example.com",
        "aACjgTUlPaemUk68kWpiA_T_pc_BvVmGrSbZaqbHSTVY",
        "cAeDPAsrfIYX2-3JMWGJW6cuB48P6m-r_KOMfHsauiJ8",
        "bd5ee0cc50950db5de548cec91d026a8d014db2bc1a3d191e9472bdb5b12641a",
    ):
        if secret in redacted:
            raise AssertionError(f"redaction leaked: {secret}")

    parse_hosts_arg(",".join(ALLOWED_HOSTS))
    try:
        parse_hosts_arg("atius-srv-1,evil-host")
    except ValueError:
        pass
    else:
        raise AssertionError("host allowlist accepted an unsupported host")

    token_probe = next(probe.command for probe in PROBES if probe.name == "token_files")
    for forbidden in ("cat ", "sha", "md5", "openssl", "base64"):
        if forbidden in token_probe:
            raise AssertionError(f"token probe may read or derive token contents: {forbidden}")
    parsed_tokens = parse_token_files(
        "/home/ubuntu/secrets/ubuntu-pro-token.txt\tubuntu\tubuntu\t600\t30\tregular file\n"
    )
    if parsed_tokens[0]["size_bytes"] != "30" or "content" in parsed_tokens[0]:
        raise AssertionError("token parser stores more than metadata")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run local safety tests and exit")
    parser.add_argument(
        "--dry-run-commands",
        action="store_true",
        help="print the read-only SSH command allowlist without connecting",
    )
    parser.add_argument(
        "--hosts",
        default=",".join(ALLOWED_HOSTS),
        help="comma-separated host allowlist subset (default: all G18 SRVs)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT.relative_to(ROOT)),
        help="Markdown output path",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.self_test:
        run_self_test()
        print("self-test: ok")
        return 0

    validate_all_probes()
    try:
        hosts = parse_hosts_arg(args.hosts)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run_commands:
        inventories = []
        for host in hosts:
            inventory = load_host_inventory(host)
            access = inventory.get("access", {})
            inventories.append(
                {
                    "host": host,
                    "inventory": inventory,
                    "target": access.get("ssh", "-") if isinstance(access, dict) else "-",
                    "vpn_ip": access.get("vpn_ip", "-") if isinstance(access, dict) else "-",
                    "public_ip": access.get("public_ip", "-") if isinstance(access, dict) else "-",
                }
            )
        print(render_report(inventories, dry_run_commands=True), end="")
        return 0

    collected = [collect_host(host) for host in hosts]
    report = render_report(collected)
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(str(output.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
