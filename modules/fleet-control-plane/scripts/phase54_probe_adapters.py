#!/usr/bin/env python3
"""Fixed, read-only owner adapters for the Phase 54 gate.

The caller selects only a registered plan/stage/check tuple. Hosts, operations,
commands, and transport policy are constants in this module; evidence never
controls execution. Output is a redacted observation, never raw owner output.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


SCHEMA_OBSERVATION = "phase54.check-observation.v1"
SCHEMA_COVERAGE = "phase54.adapter-coverage.v1"
MCP_ENDPOINT = "https://mcp.atius.com.br/oci-admin"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PHASE_DIR = (
    REPO_ROOT
    / ".planning/workstreams/network-horistic-readdress/phases"
    / "54-migra-o-integral-de-rede-oci-drg-do-horistic-para-10-31-e-re"
)
BE3_COMMIT = "24f2562af086625b0678c4573f1c03a77270fc22"
BE3_OWNER_REPO = "/home/ubuntu/GitHub/vpn-atius/home-proxy"
BE3_CAPTURE_PATH = "modules/home-router-be3/scripts/capture-be3-lan-readonly.mjs"
BE3_CAPTURE_OUTPUT = "/var/tmp/phase54-be3-readonly.json"
SRV1_BACKUP_ROOT = "/var/backups/omni-srv-admin/phase54/20260726T041249Z-srv1"
SRV3_BACKUP_ROOT = "/var/backups/omni-srv-admin/phase54/20260726T041546Z-srv3"
BE3_OFFHOST_BACKUP = (
    "/home/ubuntu/.local/state/home-router-be3/backups/phase54/"
    "be3-native-20260726T052404Z.bin"
)
BACKUP_EXPECTATIONS: dict[str, dict[str, str]] = {
    "srv1": {
        "root": SRV1_BACKUP_ROOT,
        "manifest": f"{SRV1_BACKUP_ROOT}/SHA256SUMS",
        "restore": f"{SRV1_BACKUP_ROOT}/restore-staging",
        "archive": f"{SRV1_BACKUP_ROOT}/coredns/coredns.tar",
        "archive_sha256": "5bcf242294a97636f41ebc00780fb1b7b32246bb2c408cd4cc9409fb3542b9be",
        "offhost_owner": "srv3",
        "offhost_archive": (
            "/var/backups/omni-srv-admin/phase54/off-host/srv1/"
            "20260726T041249Z-srv1/20260726T041249Z-srv1.tar"
        ),
        "offhost_sha256": "2f120b50be4c6f63f432753f4a30d4b7895f98632f7547467606f985f7d8869f",
        "mode": "600",
    },
    "srv3": {
        "root": SRV3_BACKUP_ROOT,
        "manifest": f"{SRV3_BACKUP_ROOT}/SHA256SUMS",
        "restore": f"{SRV3_BACKUP_ROOT}/restore-staging",
        "archive": (
            f"{SRV3_BACKUP_ROOT}/freeipa-native/"
            "ipa-full-2026-07-26-04-17-35/ipa-full.tar"
        ),
        "archive_sha256": "e537458856b9aeee9f0f86030717d2c0e54fbf953adbc391f44351f18cdeeef1",
        "offhost_owner": "srv1",
        "offhost_archive": (
            "/var/backups/omni-srv-admin/phase54/off-host/srv3/"
            "20260726T041546Z-srv3/20260726T041546Z-srv3.tar"
        ),
        "offhost_sha256": "0de8b8391a4770dd8a13342b660cea56ba049b736228a3ab8de0f7301e97cfb1",
        "mode": "600",
    },
    "offhost": {
        "root": str(pathlib.PurePosixPath(BE3_OFFHOST_BACKUP).parent),
        "manifest": "",
        "restore": "",
        "archive": BE3_OFFHOST_BACKUP,
        "archive_sha256": "866adbef8a1434622f0b4028ddaf5b5bd76afaeafc246e7a576b675c889cb781",
        "offhost_owner": "",
        "offhost_archive": "",
        "offhost_sha256": "",
        "mode": "600",
    },
}
DNS_NAME = "horistic-srv.atius.internal"
DNS_REVERSE_TARGET = "31.1.31.10.in-addr.arpa"
DNS_REVERSE_CURRENT = "21.1.21.10.in-addr.arpa"
DNS_AUTHORITY = "10.89.53.10"
DNS_COREDNS = "10.11.1.11"
DNS_ADGUARD = "127.0.0.2"
PUBLIC_IP = "163.176.232.119"
CURRENT_VCN = "10.21.0.0/16"
CURRENT_SUBNET = "10.21.1.0/24"
CURRENT_HOST = "10.21.1.21"
TARGET_VCN = "10.31.0.0/16"
TARGET_SUBNET = "10.31.1.0/24"
TARGET_HOST = "10.31.1.31"
ATIUS_VCNS = ("10.11.0.0/16", "10.12.0.0/16", "10.13.0.0/16")
MAX_CAPTURE = 1024 * 1024

STAGES: dict[str, tuple[str | None, ...]] = {
    "54-02": ("preflight", "preview", "approval", "apply"),
    "54-03": (None,),
    "54-04": ("preview", "approval", "apply"),
    "54-05": ("preview", "approval", "apply"),
    "54-06": ("preview", "approval", "apply"),
    "54-07": ("preview", "approval", "apply"),
    "54-08": ("preview", "approval", "apply", "sync"),
    "54-09": ("stability", "preview", "approval", "apply"),
    "54-10": ("preflight", "sync"),
}
BASE_CHECKS: dict[str, tuple[str, ...]] = {
    "54-02": (
        "live_inventory",
        "backup_restore_staging",
        "public_ip_baseline",
        "dns_edge_baseline",
    ),
    "54-03": ("builder_receipt", "builder_targets", "vcn_architecture"),
    "54-04": ("target_network", "drg_bidirectional", "security_bidirectional"),
    "54-05": ("vnic_private_ip", "host_k3s_dual_path", "public_ip_binding"),
    "54-06": ("freeipa_authority", "resolver_forwarding", "service_matrix"),
    "54-07": ("edge_transaction", "s23_unchanged", "s20_target"),
    "54-08": ("device_receipts", "s20_handshake", "dual_ssh_paths"),
    "54-09": ("stable_readbacks", "retirement_targets", "retirement_approval"),
    "54-10": ("retirement_readback", "full_matrix", "knowledge_receipts"),
}
STAGE_CHECK = {
    "preflight": "stage_preflight",
    "stability": "stage_stability",
    "preview": "operation_plan_preview",
    "approval": "typed_approval",
    "apply": "apply_receipt",
    "sync": "knowledge_sync",
}

SSH_FLAGS = (
    "-n",
    "-T",
    "-o",
    "BatchMode=yes",
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "ClearAllForwardings=yes",
    "-o",
    "ExitOnForwardFailure=yes",
    "-o",
    "StrictHostKeyChecking=yes",
    "-o",
    "ConnectTimeout=8",
    "-o",
    "ConnectionAttempts=1",
)
SSH_OWNERS: dict[str, tuple[str, ...]] = {
    "srv1": ("ubuntu@10.11.1.11", "ubuntu@10.100.100.1"),
    "srv3": ("ubuntu@10.13.1.13", "ubuntu@10.100.100.3"),
    "horistic": (
        "horistic@10.31.1.31",
        "horistic@10.21.1.21",
        "horistic@ssh-horistic-srv.atius.com.br",
    ),
}
SSH_COMMANDS = {
    "identity": "LC_ALL=C hostname; ip -json address show",
    "dns_authority": (
        "LC_ALL=C command -v dig >/dev/null; "
        f"printf '__AUTH_A__\\n'; dig +time=3 +tries=1 +norecurse @{DNS_AUTHORITY} {DNS_NAME} A; "
        f"printf '__AUTH_PTR_CURRENT__\\n'; dig +time=3 +tries=1 +norecurse @{DNS_AUTHORITY} {DNS_REVERSE_CURRENT} PTR; "
        f"printf '__AUTH_PTR_TARGET__\\n'; dig +time=3 +tries=1 +norecurse @{DNS_AUTHORITY} {DNS_REVERSE_TARGET} PTR; "
        f"printf '__AUTH_SOA__\\n'; dig +time=3 +tries=1 +norecurse @{DNS_AUTHORITY} atius.internal SOA; "
        f"printf '__AUTH_NS__\\n'; dig +time=3 +tries=1 +norecurse @{DNS_AUTHORITY} atius.internal NS; "
        f"printf '__AUTH_NX__\\n'; dig +time=3 +tries=1 +norecurse @{DNS_AUTHORITY} "
        "phase54-does-not-exist.atius.internal A"
    ),
    "dns_resolvers": (
        "LC_ALL=C command -v dig >/dev/null; "
        f"for server in {DNS_COREDNS} {DNS_ADGUARD}; do "
        "printf '__RESOLVER_%s_A__\\n' \"$server\"; "
        f"dig +time=3 +tries=1 @$server {DNS_NAME} A; "
        "printf '__RESOLVER_%s_PTR_CURRENT__\\n' \"$server\"; "
        f"dig +time=3 +tries=1 @$server {DNS_REVERSE_CURRENT} PTR; "
        "printf '__RESOLVER_%s_PTR_TARGET__\\n' \"$server\"; "
        f"dig +time=3 +tries=1 @$server {DNS_REVERSE_TARGET} PTR; "
        "printf '__RESOLVER_%s_SOA__\\n' \"$server\"; "
        "dig +time=3 +tries=1 @$server atius.internal SOA; "
        "printf '__RESOLVER_%s_NS__\\n' \"$server\"; "
        "dig +time=3 +tries=1 @$server atius.internal NS; "
        "printf '__RESOLVER_%s_NX__\\n' \"$server\"; "
        "dig +time=3 +tries=1 @$server "
        "phase54-does-not-exist.atius.internal A; done"
    ),
    "services": (
        "LC_ALL=C systemctl is-active k3s apache2 2>/dev/null; "
        "ip -json address show; ss -H -lnt"
    ),
    "wireguard": (
        "set -eu; LC_ALL=C; "
        "printf '__PEERS__\\n'; sudo -n wg show all peers; "
        "printf '__ALLOWED_IPS__\\n'; sudo -n wg show all allowed-ips; "
        "printf '__LATEST_HANDSHAKES__\\n'; sudo -n wg show all latest-handshakes; "
        "printf '__ENDPOINTS__\\n'; sudo -n wg show all endpoints; "
        "printf '__TRANSFER__\\n'; sudo -n wg show all transfer"
    ),
    "be3_capability": (
        f"LC_ALL=C git -C {BE3_OWNER_REPO} cat-file -e "
        f"{BE3_COMMIT}:{BE3_CAPTURE_PATH}"
    ),
    "be3_capture": (
        "set -eu; umask 077; "
        "tmp=$(mktemp -d /var/tmp/phase54-be3.XXXXXX); "
        "trap 'rm -rf \"$tmp\"' EXIT; "
        f"git -C {BE3_OWNER_REPO} archive {BE3_COMMIT} "
        "modules/home-router-be3 | tar -x -C \"$tmp\"; "
        f"if [ -d {BE3_OWNER_REPO}/modules/home-router-be3/node_modules ]; then "
        f"ln -s {BE3_OWNER_REPO}/modules/home-router-be3/node_modules "
        "\"$tmp/modules/home-router-be3/node_modules\"; fi; "
        "eval \"$(\"$HOME/.local/bin/atius-vault-env\" home-router-be3)\"; "
        "BE3_CAPTURE_TRANSPORT=phase54-owner-ssh-headless "
        "node \"$tmp/modules/home-router-be3/scripts/capture-be3-lan-readonly.mjs\" "
        "--target-mode edge --timeout-ms 20000 --output \"$tmp/evidence.json\" "
        ">/dev/null; "
        "unset HOME_ROUTER_USERNAME HOME_ROUTER_PASSWORD; "
        "cat \"$tmp/evidence.json\""
    ),
}


@dataclass(frozen=True)
class AdapterSpec:
    plan: str
    stage: str | None
    check_id: str
    owner: str
    transport: str


def _required(plan: str, stage: str | None) -> tuple[str, ...]:
    return BASE_CHECKS[plan] + ((STAGE_CHECK[stage],) if stage else ())


def _transport(check_id: str) -> tuple[str, str]:
    if check_id in {
        "live_inventory",
        "public_ip_baseline",
        "builder_receipt",
        "builder_targets",
        "vcn_architecture",
        "target_network",
        "drg_bidirectional",
        "security_bidirectional",
        "vnic_private_ip",
        "public_ip_binding",
        "retirement_targets",
        "retirement_approval",
    }:
        return "oci-admin", "oci-mcp"
    if check_id == "backup_restore_staging":
        return "srv1/srv3", "backup-ssh"
    if check_id in {"freeipa_authority", "resolver_forwarding", "dns_edge_baseline"}:
        return "srv1/srv3", "dns-ssh"
    if check_id in {"edge_transaction", "s23_unchanged", "s20_target"}:
        return "srv1/be3", "be3-wg"
    if check_id in {"s20_handshake", "device_receipts"}:
        return "srv1", "wireguard-ssh"
    if check_id in {"host_k3s_dual_path", "dual_ssh_paths"}:
        return "horistic", "horistic-ssh"
    if check_id in {"service_matrix"}:
        return "horistic", "service-ssh"
    if check_id in {"stable_readbacks", "retirement_readback", "full_matrix"}:
        return "multi-owner", "matrix"
    if check_id == "knowledge_receipts":
        return "repo", "knowledge"
    return "repo", "stage-contract"


def _registry() -> dict[tuple[str, str | None, str], AdapterSpec]:
    result: dict[tuple[str, str | None, str], AdapterSpec] = {}
    for plan, stages in STAGES.items():
        for stage in stages:
            for check_id in BASE_CHECKS[plan]:
                owner, transport = _transport(check_id)
                result[(plan, stage, check_id)] = AdapterSpec(
                    plan, stage, check_id, owner, transport
                )
    return result


REGISTRY = _registry()


def _fixed_executable(name: str) -> str:
    path = shutil.which(name)
    return str(pathlib.Path(path).resolve()) if path else f"/missing/{name}"


def _run(argv: list[str], timeout: int = 15) -> tuple[bool, bytes]:
    if not argv or not pathlib.Path(argv[0]).is_absolute():
        return False, b""
    try:
        child_env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TMPDIR": "/var/tmp",
        }
        for name in ("HOME", "CODEX_HOME"):
            if os.environ.get(name):
                child_env[name] = os.environ[name]
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=False,
            timeout=timeout,
            shell=False,
            stdin=subprocess.DEVNULL,
            env=child_env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, b""
    output = completed.stdout + completed.stderr
    return completed.returncode == 0 and len(output) <= MAX_CAPTURE, output[:MAX_CAPTURE]


def _ssh(owner: str, command: str) -> tuple[bool, bytes, str]:
    ssh = _fixed_executable("ssh")
    for target in SSH_OWNERS[owner]:
        ok, output = _run([ssh, *SSH_FLAGS, target, command], timeout=20)
        if ok:
            return True, output, target.split("@", 1)[-1]
    if owner == "srv3":
        nested_flags = (
            "-n -T -o BatchMode=yes -o IdentitiesOnly=yes "
            "-o ClearAllForwardings=yes -o StrictHostKeyChecking=yes "
            "-o ConnectTimeout=8"
        )
        nested = (
            f"ssh {nested_flags} ubuntu@10.13.1.13 "
            f"{shlex.quote(command)}"
        )
        ok, output = _run(
            [
                _fixed_executable("ssh"),
                *SSH_FLAGS,
                SSH_OWNERS["srv1"][0],
                nested,
            ],
            timeout=30,
        )
        if ok:
            return True, output, "10.13.1.13-via-srv1"
    return False, b"", "unreachable"


def _ssh_one(target: str, command: str) -> tuple[bool, bytes]:
    return _run(
        [_fixed_executable("ssh"), *SSH_FLAGS, target, command],
        timeout=20,
    )


def _horistic_dual(
    spec: AdapterSpec,
    command: str,
) -> tuple[bool, bytes, str]:
    private_result: tuple[bool, bytes] = (False, b"")
    private_target = "unreachable"
    for target in SSH_OWNERS["horistic"][:2]:
        private_result = _ssh_one(target, command)
        if private_result[0]:
            private_target = target.split("@", 1)[-1]
            break
    public = _ssh_one(SSH_OWNERS["horistic"][2], command)
    raw = private_result[1] + public[1]
    text = raw.decode("utf-8", "replace")
    target_required = bool(
        spec.plan in {"54-08", "54-09", "54-10"}
        or (spec.plan == "54-05" and spec.stage == "apply")
    )
    address_ok = "10.31.1.31" in text if target_required else bool(text)
    service_ok = bool(
        spec.transport != "service-ssh"
        or (text.count("active") >= 2 and "10.31.1.31" in text)
    )
    passed = private_result[0] and public[0] and address_ok and service_ok
    return (
        passed,
        raw if passed else b"",
        f"{private_target}+ssh-horistic-srv.atius.com.br",
    )


def _vault_token() -> str | None:
    inherited = os.environ.get("ATIUS_MCP_TOKEN")
    if inherited:
        return inherited
    ok, output, _ = _ssh(
        "srv3",
        "sudo -n /usr/local/sbin/atius-vault-export-env atius-mcp",
    )
    if not ok:
        return None
    match = re.search(
        rb"(?:export[ \t]+)?ATIUS_MCP_TOKEN=(?:'([^']+)'|\"([^\"]+)\"|([^\r\n ]+))",
        output,
    )
    if not match:
        return None
    raw = next(group for group in match.groups() if group is not None)
    return raw.decode("utf-8", "strict")


def _post_json(
    payload: dict[str, Any],
    token: str,
    *,
    session_id: str | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Host": "mcp.atius.com.br",
        "User-Agent": "curl/8.5.0",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(
        MCP_ENDPOINT,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(MAX_CAPTURE + 1)
            return response.status, body, dict(response.headers.items())
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, b"", {}


def _mcp_payload(body: bytes) -> dict[str, Any] | None:
    if len(body) > MAX_CAPTURE:
        return None
    try:
        value = json.loads(body)
        return value if isinstance(value, dict) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        for line in body.splitlines():
            if line.startswith(b"data:"):
                try:
                    value = json.loads(line[5:].strip())
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(value, dict):
                    return value
    return None


def _mcp_result_data(payload: dict[str, Any]) -> Any:
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                try:
                    return json.loads(item["text"])
                except json.JSONDecodeError:
                    return item["text"]
    return result


def _oci_read(
    operation: str = "context.show",
    check_id: str = "capability",
    arguments: dict[str, Any] | None = None,
) -> tuple[bool, Any, str, bytes]:
    token = _vault_token()
    if not token:
        return False, None, "missing-token", b""
    status, body, headers = _post_json(
        {
            "jsonrpc": "2.0",
            "id": "phase54-initialize",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "phase54-gate", "version": "1"},
            },
        },
        token,
    )
    session = next(
        (value for key, value in headers.items() if key.lower() == "mcp-session-id"),
        None,
    )
    if status not in {200, 201} or _mcp_payload(body) is None:
        return False, None, "initialize", b""
    _post_json(
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        token,
        session_id=session,
    )
    status, body, _ = _post_json(
        {
            "jsonrpc": "2.0",
            "id": f"phase54-{check_id}",
            "method": "tools/call",
            "params": {
                "name": "oci_read",
                "arguments": {
                    "operation": operation,
                    "arguments": arguments or {},
                },
            },
        },
        token,
        session_id=session,
    )
    payload = _mcp_payload(body)
    data = _mcp_result_data(payload) if payload else None
    serialized = json.dumps(data, sort_keys=True, default=str) if data is not None else ""
    mutation_free = not any(
        token in serialized.lower()
        for token in ('"mutation_performed": true', '"mutations_attempted": true')
    )
    semantic = bool(serialized and mutation_free)
    if operation == "peering.address_plan":
        semantic = semantic and all(
            literal in serialized
            for literal in ("10.31.0.0/16", "10.31.1.0/24", "10.31.1.31")
        )
    passed = bool(
        status == 200
        and payload
        and payload.get("id") == f"phase54-{check_id}"
        and "error" not in payload
        and semantic
    )
    return passed, data if passed else None, f"phase54-{check_id}", body if passed else b""


def _read_evidence(
    spec: AdapterSpec,
    evidence_path: pathlib.Path,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw = evidence_path.read_bytes()
        parsed = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    valid = bool(
        isinstance(parsed, dict)
        and parsed.get("schema") == "phase54.evidence.v1"
        and parsed.get("plan") == spec.plan
        and parsed.get("stage") == spec.stage
    )
    return (
        parsed if valid else None,
        hashlib.sha256(raw).hexdigest() if valid else None,
    )


def _walk(value: Any) -> list[Any]:
    values = [value]
    if isinstance(value, dict):
        for item in value.values():
            values.extend(_walk(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(_walk(item))
    return values


def _strings(value: Any) -> set[str]:
    return {item for item in _walk(value) if isinstance(item, str)}


def _ocids(value: Any, resource: str) -> list[str]:
    prefix = f"ocid1.{resource}."
    return sorted(item for item in _strings(value) if item.startswith(prefix))


def _referenced_documents(
    evidence: dict[str, Any],
    evidence_path: pathlib.Path,
) -> list[dict[str, Any]]:
    documents = [evidence]
    allowed_root = evidence_path.parent.resolve()
    for item in _walk(evidence):
        if not isinstance(item, str) or not item.endswith(".json"):
            continue
        candidate = pathlib.Path(item)
        if not candidate.is_absolute():
            repo_candidate = REPO_ROOT / candidate
            candidate = repo_candidate if repo_candidate.exists() else allowed_root / candidate
        try:
            resolved = candidate.resolve()
            resolved.relative_to(allowed_root)
        except (OSError, ValueError):
            continue
        try:
            parsed = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            documents.append(parsed)
    return documents


def _security_arguments(
    evidence: dict[str, Any],
    evidence_path: pathlib.Path,
) -> list[dict[str, str]]:
    ids: set[str] = set()
    for document in _referenced_documents(evidence, evidence_path):
        ids.update(_ocids(document, "securitylist"))
    return [
        {
            "profile_name": "horistic",
            "region": "sa-saopaulo-1",
            "security_list_id": identifier,
        }
        for identifier in sorted(ids)
    ]


def _normalize_inventory(data: dict[str, Any]) -> dict[str, Any]:
    sides = data.get("sides")
    if not isinstance(sides, list):
        sides = data.get("inventory_sides")
    horistic = next(
        (
            item
            for item in sides
            if isinstance(item, dict)
            and item.get("profile_name", item.get("label")) == "horistic"
        ),
        {},
    ) if isinstance(sides, list) else {}
    strings = _strings(horistic)
    return {
        "profile_name": "horistic",
        "vcn_cidrs": sorted(
            set(horistic.get("vcn_cidrs", []))
            | {item for item in strings if re.fullmatch(r"10\.\d+\.0\.0/16", item)}
        ),
        "subnet_cidrs": sorted(
            set(horistic.get("subnet_cidrs", []))
            | {item for item in strings if re.fullmatch(r"10\.\d+\.1\.0/24", item)}
        ),
        "current_host_ips": sorted(
            set(horistic.get("current_host_ips", []))
            | {item for item in strings if item in {CURRENT_HOST, TARGET_HOST}}
        ),
        "vcn_ocids": _ocids(horistic, "vcn"),
        "subnet_ocids": _ocids(horistic, "subnet"),
        "reserved_public_labels": sorted(horistic.get("reserved_public_ips", [])),
        "blocked": data.get("blocked"),
    }


def _normalize_address_plan(data: dict[str, Any]) -> dict[str, Any]:
    ranges = data.get("target_ranges")
    target = ranges.get("horistic") if isinstance(ranges, dict) else None
    previews = data.get("operation_plan_previews")
    return {
        "applies_live_oci_writes": data.get("applies_live_oci_writes"),
        "target": {
            "vcn": target.get("vcn_cidr") if isinstance(target, dict) else None,
            "subnet": (
                target.get("server_subnet_cidr") if isinstance(target, dict) else None
            ),
            "private_ip": (
                target.get("stable_host_ip") if isinstance(target, dict) else None
            ),
            "service_subnet": (
                target.get("service_subnet_cidr") if isinstance(target, dict) else None
            ),
        },
        "target_contains_10_21": any(
            item.startswith("10.21.") for item in _strings(target)
        ),
        "preview_count": len(previews) if isinstance(previews, list) else 0,
    }


def _normalize_drg(data: dict[str, Any]) -> dict[str, Any]:
    attachments = data.get("attachments")
    route_tables = data.get("route_tables")
    distributions = data.get("route_distributions")
    normalized_attachments = [
        {
            "profile_name": item.get("profile_name"),
            "attachment_ocid": item.get("attachment_id"),
            "vcn_ocid": item.get("vcn_id"),
            "state": item.get("state"),
            "blocked": item.get("blocked"),
        }
        for item in attachments
        if isinstance(item, dict)
    ] if isinstance(attachments, list) else []
    normalized_routes = [
        {
            "profile_name": item.get("profile_name"),
            "route_table_ocid": item.get(
                "route_table_id", item.get("drg_route_table_id")
            ),
            "target_cidrs": sorted(
                value
                for value in _strings(item)
                if re.fullmatch(r"\d+\.\d+\.\d+\.\d+/\d+", value)
            ),
            "blocked": item.get("blocked"),
        }
        for item in route_tables
        if isinstance(item, dict)
    ] if isinstance(route_tables, list) else []
    normalized_distributions = [
        {
            "profile_name": item.get("profile_name"),
            "attachment_ocid": item.get("attachment_id"),
            "distribution_id": item.get("distribution_id"),
            "imported_cidrs": sorted(item.get("imported_cidrs", [])),
            "blocked": item.get("blocked"),
        }
        for item in distributions
        if isinstance(item, dict)
    ] if isinstance(distributions, list) else []
    return {
        "applies_live_oci_writes": data.get("applies_live_oci_writes"),
        "central_drg_ocid": (
            data.get("central_target", {}).get("drg_id")
            if isinstance(data.get("central_target"), dict)
            else None
        ),
        "attachments": normalized_attachments,
        "route_tables": normalized_routes,
        "route_distributions": normalized_distributions,
        "ready_for_operation_plans": data.get("ready_for_operation_plans"),
        "blockers": data.get("blockers"),
        "operational_10_21": sorted(
            item
            for item in _strings(data)
            if re.search(r"(?<!\d)10\.21\.\d+\.\d+(?:/\d+)?(?!\d)", item)
        ),
    }


def _normalize_security(
    rows: list[dict[str, Any]],
    argument_ocids: list[str],
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row.get("security_list"), dict):
            row = row["security_list"]
        elif isinstance(row.get("resource"), dict):
            row = row["resource"]
        ingress = row.get("ingress_security_rules")
        egress = row.get("egress_security_rules")
        normalized.append(
            {
                "security_list_ocid": row.get("ocid"),
                "vcn_ocid": row.get("vcn_id"),
                "lifecycle_state": row.get("lifecycle_state"),
                "ingress": [
                    {
                        "source": item.get("source"),
                        "protocol": item.get("protocol"),
                        "direction": "INGRESS",
                    }
                    for item in ingress
                    if isinstance(item, dict)
                ] if isinstance(ingress, list) else [],
                "egress": [
                    {
                        "destination": item.get("destination"),
                        "protocol": item.get("protocol"),
                        "direction": "EGRESS",
                    }
                    for item in egress
                    if isinstance(item, dict)
                ] if isinstance(egress, list) else [],
            }
        )
    return {
        "argument_security_list_ocids": sorted(argument_ocids),
        "security_lists": normalized,
    }


def _normalize_full_inventory(data: dict[str, Any]) -> dict[str, Any]:
    network = data.get("network")
    if not isinstance(network, dict):
        network = {}
    return {
        "profile_name": "horistic",
        "vcn_cidrs": sorted(
            item.get("metadata", {}).get("cidr_block")
            for item in network.get("vcns", [])
            if isinstance(item, dict)
            and isinstance(item.get("metadata"), dict)
            and isinstance(item["metadata"].get("cidr_block"), str)
        ),
        "subnet_cidrs": sorted(
            item.get("metadata", {}).get("cidr_block")
            for item in network.get("subnets", [])
            if isinstance(item, dict)
            and isinstance(item.get("metadata"), dict)
            and isinstance(item["metadata"].get("cidr_block"), str)
        ),
        "vnics": [
            {
                "vnic_ocid": item.get("ocid"),
                "private_ip": item.get("metadata", {}).get("private_ip"),
                "public_ip": item.get("metadata", {}).get("public_ip"),
                "subnet_ocid": item.get("metadata", {}).get("subnet_id"),
            }
            for item in network.get("vnics", [])
            if isinstance(item, dict) and isinstance(item.get("metadata"), dict)
        ],
        "private_ips": [
            {
                "private_ip_ocid": item.get("ocid"),
                "address": item.get("display_name"),
                "vnic_ocid": item.get("metadata", {}).get("vnic_id"),
                "subnet_ocid": item.get("metadata", {}).get("subnet_id"),
            }
            for item in network.get("private_ips", [])
            if isinstance(item, dict) and isinstance(item.get("metadata"), dict)
        ],
        "reserved_public_ips": [
            {
                "public_ip_ocid": item.get("ocid"),
                "label": item.get("display_name"),
                "address": item.get("metadata", {}).get("ip_address"),
                "private_ip_ocid": item.get("metadata", {}).get("private_ip_id"),
                "lifecycle_state": item.get("metadata", {}).get("lifecycle_state"),
                "lifetime": item.get("metadata", {}).get("lifetime"),
            }
            for item in network.get("reserved_public_ips", [])
            if isinstance(item, dict) and isinstance(item.get("metadata"), dict)
        ],
        "operational_10_21": sorted(
            item
            for item in _strings(data)
            if re.search(r"(?<!\d)10\.21\.\d+\.\d+(?:/\d+)?(?!\d)", item)
        ),
    }


def _oci_probe(
    spec: AdapterSpec,
    evidence: dict[str, Any],
    evidence_path: pathlib.Path,
    evidence_sha256: str,
) -> tuple[bool, dict[str, Any], str, bytes]:
    operation = {
        "live_inventory": "peering.inventory",
        "public_ip_baseline": "inventory.get",
        "builder_receipt": "peering.address_plan",
        "builder_targets": "peering.address_plan",
        "vcn_architecture": "peering.address_plan",
        "target_network": "peering.address_plan",
        "drg_bidirectional": "peering.drg_status",
        "security_bidirectional": "network.security_list",
        "vnic_private_ip": "inventory.get",
        "public_ip_binding": "inventory.get",
        "retirement_targets": "peering.drg_status",
        "retirement_approval": "peering.drg_status",
    }[spec.check_id]
    common_args: dict[str, Any] = {}
    if operation == "inventory.get":
        common_args = {
            "mode": "all",
            "profile_name": "horistic",
            "region": "sa-saopaulo-1",
        }
    rows: list[dict[str, Any]] = []
    request_ids: list[str] = []
    raw_parts: list[bytes] = []
    arguments_used: list[dict[str, Any]] = []
    if operation == "network.security_list":
        argument_sets = _security_arguments(evidence, evidence_path)
        if not argument_sets:
            return False, {}, "missing-security-list-ocids", b""
    else:
        argument_sets = [common_args]
    for index, arguments in enumerate(argument_sets):
        ok, data, request_id, raw = _oci_read(
            operation,
            f"{spec.check_id}-{index}",
            arguments,
        )
        if not ok or not isinstance(data, dict):
            return False, {}, request_id, b""
        rows.append(data)
        request_ids.append(request_id)
        raw_parts.append(raw)
        arguments_used.append(arguments)
    if operation == "peering.inventory":
        semantic = _normalize_inventory(rows[0])
    elif operation == "peering.address_plan":
        semantic = _normalize_address_plan(rows[0])
    elif operation == "peering.drg_status":
        semantic = _normalize_drg(rows[0])
    elif operation == "network.security_list":
        semantic = _normalize_security(
            rows,
            [item["security_list_id"] for item in arguments_used],
        )
    else:
        semantic = _normalize_full_inventory(rows[0])
    normalized = {
        "evidence_sha256": evidence_sha256,
        "operation": operation,
        "arguments_sha256": hashlib.sha256(
            json.dumps(arguments_used, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "semantic": semantic,
    }
    raw = b"".join(raw_parts)
    return True, normalized, "+".join(request_ids), raw


def _backup_command(expectation: dict[str, str], *, tar_archive: bool) -> str:
    archive = shlex.quote(expectation["archive"])
    root = shlex.quote(expectation["root"])
    command = (
        "set -eu; LC_ALL=C; "
        f"sudo -n test -d {root}; sudo -n test -f {archive}; "
        f"actual=$(sudo -n sha256sum {archive} | cut -d' ' -f1); "
        f"mode=$(sudo -n stat -c %a {archive}); "
        f"test \"$actual\" = {expectation['archive_sha256']}; "
        f"test \"$mode\" = {expectation['mode']}; "
    )
    if expectation["manifest"]:
        manifest = shlex.quote(expectation["manifest"])
        command += (
            f"sudo -n test -f {manifest}; "
            f"sudo -n sh -c 'cd {root} && sha256sum -c SHA256SUMS >/dev/null'; "
        )
    if tar_archive:
        command += f"sudo -n tar -tf {archive} | sed -n '1p' >/dev/null; "
    if expectation["restore"]:
        restore = shlex.quote(expectation["restore"])
        command += (
            f"sudo -n test -d {restore}; "
            f"sudo -n find {restore} -mindepth 1 -print -quit | grep -q .; "
        )
    command += (
        f"printf '%s|%s|%s\\n' {shlex.quote(expectation['archive'])} "
        '"$actual" "$mode"'
    )
    return command


def _offhost_command(expectation: dict[str, str]) -> str:
    archive = shlex.quote(expectation["offhost_archive"])
    return (
        "set -eu; LC_ALL=C; "
        f"sudo -n test -f {archive}; "
        f"actual=$(sudo -n sha256sum {archive} | cut -d' ' -f1); "
        f"mode=$(sudo -n stat -c %a {archive}); "
        f"test \"$actual\" = {expectation['offhost_sha256']}; "
        'test "$mode" = 600; '
        f"sudo -n tar -tf {archive} | sed -n '1p' >/dev/null; "
        f"printf '%s|%s|%s\\n' {archive} \"$actual\" \"$mode\""
    )


def _triplet(output: bytes) -> tuple[str, str, str] | None:
    rows = [
        line.split("|")
        for line in output.decode("utf-8", "replace").splitlines()
        if line.count("|") == 2
    ]
    if not rows or len(rows[-1]) != 3:
        return None
    return rows[-1][0], rows[-1][1], rows[-1][2]


def _backup_read(evidence_sha256: str) -> tuple[bool, dict[str, Any], str, bytes]:
    results = {
        owner: _ssh(
            "srv1" if owner == "offhost" else owner,
            _backup_command(expectation, tar_archive=owner != "offhost"),
        )
        for owner, expectation in BACKUP_EXPECTATIONS.items()
    }
    offhost_results = {
        owner: _ssh(expectation["offhost_owner"], _offhost_command(expectation))
        for owner, expectation in BACKUP_EXPECTATIONS.items()
        if expectation["offhost_archive"]
    }
    normalized_rows: list[dict[str, Any]] = []
    raw = b""
    passed = True
    request_ids: list[str] = []
    for owner, (ok, output, request_id) in results.items():
        raw += output
        request_ids.append(request_id)
        expectation = BACKUP_EXPECTATIONS[owner]
        parsed = _triplet(output)
        row_ok = bool(
            ok
            and parsed
            and parsed[0] == expectation["archive"]
            and parsed[1] == expectation["archive_sha256"]
            and parsed[2] == expectation["mode"]
        )
        offhost_ok = True
        offhost_parsed: tuple[str, str, str] | None = None
        if owner in offhost_results:
            oh_ok, oh_output, oh_request = offhost_results[owner]
            raw += oh_output
            request_ids.append(oh_request)
            offhost_parsed = _triplet(oh_output)
            offhost_ok = bool(
                oh_ok
                and offhost_parsed
                and offhost_parsed[0] == expectation["offhost_archive"]
                and offhost_parsed[1] == expectation["offhost_sha256"]
                and offhost_parsed[2] == "600"
            )
        passed = passed and row_ok and offhost_ok
        normalized_rows.append(
            {
                "owner": owner,
                "root": expectation["root"],
                "archive": expectation["archive"],
                "archive_sha256": parsed[1] if parsed else None,
                "mode": parsed[2] if parsed else None,
                "manifest_verified": bool(row_ok and expectation["manifest"]),
                "tar_list_verified": bool(row_ok and owner != "offhost"),
                "isolated_restore_staging": bool(row_ok and expectation["restore"]),
                "offhost_archive": expectation["offhost_archive"] or None,
                "offhost_sha256": offhost_parsed[1] if offhost_parsed else None,
                "offhost_verified": offhost_ok,
            }
        )
    return (
        passed,
        {"evidence_sha256": evidence_sha256, "backups": normalized_rows},
        "+".join(request_ids),
        raw if passed else b"",
    )


def _dns_expected(spec: AdapterSpec) -> tuple[str, str]:
    post_cutover = bool(
        spec.plan in {"54-07", "54-08", "54-09", "54-10"}
        or (spec.plan == "54-06" and spec.stage == "apply")
    )
    return (
        (TARGET_HOST, DNS_REVERSE_TARGET)
        if post_cutover
        else (CURRENT_HOST, DNS_REVERSE_CURRENT)
    )


def _dig_sections(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    current: str | None = None
    rows: list[str] = []
    for line in text.splitlines():
        if re.fullmatch(r"__[A-Z0-9_.:-]+__", line):
            if current is not None:
                result[current] = "\n".join(rows)
            current, rows = line, []
        elif current is not None:
            rows.append(line)
    if current is not None:
        result[current] = "\n".join(rows)
    return result


def _dig_status(section: str) -> str | None:
    match = re.search(r"status:\s*([A-Z]+)", section)
    return match.group(1) if match else None


def _dig_flags(section: str) -> set[str]:
    match = re.search(r"flags:\s*([^;]+);", section)
    return set(match.group(1).split()) if match else set()


def _answer_ttls(section: str) -> list[int]:
    return [
        int(value)
        for value in re.findall(r"(?m)^\S+\s+(\d+)\s+IN\s+\S+\s+", section)
    ]


def _dns_read(
    spec: AdapterSpec,
    evidence_sha256: str,
) -> tuple[bool, dict[str, Any], str, bytes]:
    authority = _ssh("srv3", SSH_COMMANDS["dns_authority"])
    resolvers = _ssh("srv1", SSH_COMMANDS["dns_resolvers"])
    auth_sections = _dig_sections(authority[1].decode("utf-8", "replace"))
    resolver_sections = _dig_sections(resolvers[1].decode("utf-8", "replace"))
    expected_address, expected_reverse = _dns_expected(spec)
    auth_a = auth_sections.get("__AUTH_A__", "")
    auth_ptr_key = (
        "__AUTH_PTR_TARGET__"
        if expected_reverse == DNS_REVERSE_TARGET
        else "__AUTH_PTR_CURRENT__"
    )
    auth_ptr = auth_sections.get(auth_ptr_key, "")
    authority_matrix = {
        "server": DNS_AUTHORITY,
        "aa": all(
            "aa" in _dig_flags(auth_sections.get(key, ""))
            for key in ("__AUTH_A__", auth_ptr_key, "__AUTH_SOA__", "__AUTH_NS__")
        ),
        "nxdomain": _dig_status(auth_sections.get("__AUTH_NX__", "")) == "NXDOMAIN",
        "a_address": expected_address if expected_address in auth_a else None,
        "ptr_owner": expected_reverse if expected_reverse in auth_ptr else None,
        "soa": bool(re.search(r"\sSOA\s", auth_sections.get("__AUTH_SOA__", ""))),
        "ns": bool(re.search(r"\sNS\s", auth_sections.get("__AUTH_NS__", ""))),
    }
    resolver_ok = True
    resolver_nxdomain = 0
    ttl_values = _answer_ttls(auth_a) + _answer_ttls(auth_ptr)
    for server in (DNS_COREDNS, DNS_ADGUARD):
        prefix = f"__RESOLVER_{server}_"
        a_section = resolver_sections.get(f"{prefix}A__", "")
        ptr_suffix = "PTR_TARGET__" if expected_reverse == DNS_REVERSE_TARGET else "PTR_CURRENT__"
        ptr_section = resolver_sections.get(f"{prefix}{ptr_suffix}", "")
        soa_section = resolver_sections.get(f"{prefix}SOA__", "")
        ns_section = resolver_sections.get(f"{prefix}NS__", "")
        nx_section = resolver_sections.get(f"{prefix}NX__", "")
        resolver_ok = bool(
            resolver_ok
            and _dig_status(a_section) == "NOERROR"
            and expected_address in a_section
            and _dig_status(ptr_section) == "NOERROR"
            and expected_reverse in ptr_section
            and _dig_status(soa_section) == "NOERROR"
            and re.search(r"\sSOA\s", soa_section)
            and _dig_status(ns_section) == "NOERROR"
            and re.search(r"\sNS\s", ns_section)
            and _dig_status(nx_section) == "NXDOMAIN"
        )
        resolver_nxdomain += int(_dig_status(nx_section) == "NXDOMAIN")
        ttl_values.extend(_answer_ttls(a_section))
        ttl_values.extend(_answer_ttls(ptr_section))
    resolver_matrix = {
        "servers": [DNS_COREDNS, DNS_ADGUARD],
        "nxdomain_count": resolver_nxdomain,
        "a_address": expected_address if resolver_ok else None,
        "ptr_owner": expected_reverse if resolver_ok else None,
        "soa": resolver_ok,
        "ns": resolver_ok,
    }
    legacy_records: list[str] = []
    if CURRENT_HOST in auth_a:
        legacy_records.append(f"freeipa:A:{DNS_NAME}:{CURRENT_HOST}")
    auth_current_ptr = auth_sections.get("__AUTH_PTR_CURRENT__", "")
    if (
        _dig_status(auth_current_ptr) == "NOERROR"
        and DNS_NAME in auth_current_ptr
    ):
        legacy_records.append(
            f"freeipa:PTR:{DNS_REVERSE_CURRENT}:{DNS_NAME}"
        )
    for server in (DNS_COREDNS, DNS_ADGUARD):
        prefix = f"__RESOLVER_{server}_"
        resolver_a = resolver_sections.get(f"{prefix}A__", "")
        resolver_current_ptr = resolver_sections.get(
            f"{prefix}PTR_CURRENT__", ""
        )
        if CURRENT_HOST in resolver_a:
            legacy_records.append(f"{server}:A:{DNS_NAME}:{CURRENT_HOST}")
        if (
            _dig_status(resolver_current_ptr) == "NOERROR"
            and DNS_NAME in resolver_current_ptr
        ):
            legacy_records.append(
                f"{server}:PTR:{DNS_REVERSE_CURRENT}:{DNS_NAME}"
            )
    passed = bool(
        authority[0]
        and resolvers[0]
        and authority_matrix["aa"]
        and authority_matrix["nxdomain"]
        and authority_matrix["a_address"] == expected_address
        and authority_matrix["ptr_owner"] == expected_reverse
        and authority_matrix["soa"]
        and authority_matrix["ns"]
        and resolver_ok
        and resolver_nxdomain == 2
        and ttl_values
        and min(ttl_values) > 0
    )
    return (
        passed,
        {
            "evidence_sha256": evidence_sha256,
            "expected_address": expected_address,
            "expected_reverse": expected_reverse,
            "authority": authority_matrix,
            "resolvers": resolver_matrix,
            "ttl_min": min(ttl_values) if ttl_values else None,
            "operational_10_21": sorted(set(legacy_records)),
        },
        f"{authority[2]}+{resolvers[2]}",
        authority[1] + resolvers[1] if passed else b"",
    )


def _fingerprint_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()[:24]


def _marker_sections(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if re.fullmatch(r"__[A-Z_]+__", line):
            current = line
            result[current] = []
        elif current is not None and line.strip():
            result[current].append(line)
    return result


def _wireguard_normalized(text: str, spec: AdapterSpec) -> dict[str, Any]:
    sections = _marker_sections(text)
    peer_rows: dict[str, dict[str, Any]] = {}

    def peer(raw_key: str) -> dict[str, Any]:
        fingerprint = _fingerprint_key(raw_key)
        return peer_rows.setdefault(
            fingerprint,
            {
                "fingerprint": fingerprint,
                "allowed_ips": set(),
                "handshake_epoch": 0,
                "endpoint_present": False,
                "transfer_present": False,
            },
        )

    for line in sections.get("__PEERS__", []):
        fields = line.split("\t")
        if len(fields) == 2:
            peer(fields[1])
    for line in sections.get("__ALLOWED_IPS__", []):
        fields = line.split("\t")
        if len(fields) >= 3:
            peer(fields[1])["allowed_ips"].update(
                item.strip()
                for item in fields[2].split(",")
                if re.fullmatch(r"\d+\.\d+\.\d+\.\d+/\d+", item.strip())
            )
    for line in sections.get("__LATEST_HANDSHAKES__", []):
        fields = line.split("\t")
        if len(fields) == 3 and fields[2].isdigit():
            peer(fields[1])["handshake_epoch"] = int(fields[2])
    for line in sections.get("__ENDPOINTS__", []):
        fields = line.split("\t")
        if len(fields) == 3:
            peer(fields[1])["endpoint_present"] = fields[2] not in {"(none)", ""}
    for line in sections.get("__TRANSFER__", []):
        fields = line.split("\t")
        if len(fields) == 4 and fields[2].isdigit() and fields[3].isdigit():
            peer(fields[1])["transfer_present"] = True
    require_fresh = spec.plan in {"54-08", "54-09", "54-10"}
    now = int(time.time())
    normalized_peers = []
    for row in peer_rows.values():
        epoch = int(row["handshake_epoch"])
        normalized_peers.append(
            {
                "fingerprint": row["fingerprint"],
                "allowed_ips": sorted(row["allowed_ips"]),
                "handshake_epoch": epoch,
                "handshake_fresh": bool(epoch and 0 <= now - epoch <= 600),
                "endpoint_present": row["endpoint_present"],
                "transfer_present": row["transfer_present"],
            }
        )
    normalized_peers.sort(key=lambda item: item["fingerprint"])
    target_peers = [
        item
        for item in normalized_peers
        if "10.100.100.11/32" in item["allowed_ips"]
    ]
    target_peer = target_peers[0] if len(target_peers) == 1 else None
    allowed_ips = sorted(
        {
            allowed
            for item in normalized_peers
            for allowed in item["allowed_ips"]
        }
    )
    return {
        "peer_fingerprints": [
            item["fingerprint"] for item in normalized_peers
        ],
        "peers": normalized_peers,
        "allowed_ips": allowed_ips,
        "handshake_latest_epoch": (
            target_peer["handshake_epoch"] if target_peer else 0
        ),
        "handshake_fresh_required": require_fresh,
        "handshake_fresh": bool(
            target_peer and target_peer["handshake_fresh"]
        ),
        "endpoints_present": bool(
            target_peer and target_peer["endpoint_present"]
        ),
        "transfers_present": bool(
            target_peer and target_peer["transfer_present"]
        ),
        "target_peer_count": len(target_peers),
        "target_peer": target_peer,
        "raw_keys_present": False,
    }


def _be3_normalized(data: dict[str, Any], spec: AdapterSpec) -> dict[str, Any]:
    endpoints = data.get("endpoints")
    reserve = (
        endpoints.get("lanIpAddressReserve")
        if isinstance(endpoints, dict)
        else None
    )
    targets = reserve.get("targets") if isinstance(reserve, dict) else None
    s23 = targets.get("s23") if isinstance(targets, dict) else {}
    s20 = targets.get("s20") if isinstance(targets, dict) else {}
    target_stage = bool(
        spec.plan in {"54-08", "54-09", "54-10"}
        or (spec.plan == "54-07" and spec.stage == "apply")
    )
    expected_s20 = "192.168.1.11" if target_stage else "192.168.1.9"
    return {
        "source_commit": BE3_COMMIT,
        "headless": data.get("capture", {}).get("browser") == "chromium-headless",
        "authenticated": data.get("capture", {}).get("authenticated") is True,
        "applies_changes": data.get("appliesChanges"),
        "s23": {
            "mac": s23.get("mac"),
            "ips": sorted(s23.get("ips", [])),
            "expected": "192.168.1.10",
        },
        "s20": {
            "mac": s20.get("mac"),
            "ips": sorted(s20.get("ips", [])),
            "expected": expected_s20,
        },
    }


def _be3_wg_read(
    spec: AdapterSpec,
    evidence_sha256: str,
) -> tuple[bool, dict[str, Any], str, bytes]:
    capture = _ssh("srv1", SSH_COMMANDS["be3_capture"])
    wg = _ssh("srv1", SSH_COMMANDS["wireguard"])
    try:
        capture_json = json.loads(capture[1])
    except (UnicodeDecodeError, json.JSONDecodeError):
        capture_json = None
    be3 = _be3_normalized(capture_json, spec) if isinstance(capture_json, dict) else {}
    wireguard = _wireguard_normalized(wg[1].decode("utf-8", "replace"), spec)
    expected_s20 = be3.get("s20", {}).get("expected")
    be3_ok = bool(
        capture[0]
        and be3.get("headless") is True
        and be3.get("authenticated") is True
        and be3.get("applies_changes") is False
        and be3.get("s23", {}).get("mac") == "64:1B:2F:C2:DC:A3"
        and be3.get("s23", {}).get("ips") == ["192.168.1.10"]
        and be3.get("s20", {}).get("mac") == "30:AB:6A:3C:96:D1"
        and be3.get("s20", {}).get("ips") == [expected_s20]
    )
    wg_ok = bool(wg[0] and wireguard["peer_fingerprints"])
    if spec.plan in {"54-08", "54-09", "54-10"}:
        wg_ok = bool(
            wg_ok
            and "10.100.100.11/32" in wireguard["allowed_ips"]
            and wireguard["target_peer_count"] == 1
            and wireguard["handshake_fresh"]
        )
    return (
        be3_ok and wg_ok,
        {
            "evidence_sha256": evidence_sha256,
            "be3": be3,
            "wireguard": wireguard,
        },
        f"{capture[2]}+{wg[2]}",
        capture[1] + wg[1] if be3_ok and wg_ok else b"",
    )


def _wireguard_read(
    spec: AdapterSpec,
    evidence_sha256: str,
) -> tuple[bool, dict[str, Any], str, bytes]:
    result = _ssh("srv1", SSH_COMMANDS["wireguard"])
    normalized = _wireguard_normalized(result[1].decode("utf-8", "replace"), spec)
    passed = bool(
        result[0]
        and normalized["peer_fingerprints"]
        and "10.100.100.11/32" in normalized["allowed_ips"]
        and normalized["target_peer_count"] == 1
        and normalized["handshake_fresh"]
    )
    return (
        passed,
        {"evidence_sha256": evidence_sha256, "wireguard": normalized},
        result[2],
        result[1] if passed else b"",
    )


def _target_host_required(spec: AdapterSpec) -> bool:
    return bool(
        spec.plan in {"54-08", "54-09", "54-10"}
        or (spec.plan == "54-05" and spec.stage == "apply")
        or spec.plan in {"54-06", "54-07"}
    )


def _host_read(
    spec: AdapterSpec,
    evidence_sha256: str,
    *,
    services: bool,
) -> tuple[bool, dict[str, Any], str, bytes]:
    command = SSH_COMMANDS["services" if services else "identity"]
    private_targets = (
        SSH_OWNERS["horistic"][:1]
        if _target_host_required(spec)
        else SSH_OWNERS["horistic"][1:2]
    )
    private: tuple[bool, bytes] = (False, b"")
    private_name = "unreachable"
    for target in private_targets:
        private = _ssh_one(target, command)
        if private[0]:
            private_name = target.split("@", 1)[-1]
            break
    public = _ssh_one(SSH_OWNERS["horistic"][2], command)
    required_ip = TARGET_HOST if _target_host_required(spec) else CURRENT_HOST
    private_text = private[1].decode("utf-8", "replace")
    public_text = public[1].decode("utf-8", "replace")
    observed_private_ips = sorted(
        set(
            re.findall(
                r"(?<![\d.])10\.\d+\.\d+\.\d+(?![\d.])",
                private_text,
            )
        )
    )
    observed_public_ips = sorted(
        set(
            re.findall(
                r"(?<![\d.])(?:10\.\d+\.\d+\.\d+|"
                r"163\.176\.232\.119)(?![\d.])",
                public_text,
            )
        )
    )
    services_state = {
        "k3s": "active" if re.search(r"(?m)^active$", public_text) else None,
        "apache2": (
            "active" if len(re.findall(r"(?m)^active$", public_text)) >= 2 else None
        ),
    }
    passed = bool(
        private[0]
        and public[0]
        and required_ip in private_text
        and (not services or services_state == {"k3s": "active", "apache2": "active"})
    )
    normalized: dict[str, Any] = {
        "evidence_sha256": evidence_sha256,
        "private_path": "PASS" if private[0] and required_ip in private_text else "BLOCK",
        "public_path": "PASS" if public[0] else "BLOCK",
        "required_private_ip": required_ip,
        "observed_private_ips": observed_private_ips,
        "observed_public_ips": observed_public_ips,
        "operational_10_21": sorted(
            {
                item
                for item in observed_private_ips + observed_public_ips
                if item.startswith("10.21.")
            }
        ),
    }
    if services:
        normalized["services"] = services_state
    return (
        passed,
        normalized,
        f"{private_name}+ssh-horistic-srv.atius.com.br",
        private[1] + public[1] if passed else b"",
    )


def _json_document(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _graph_total_nodes(status: Any) -> int:
    if not isinstance(status, dict):
        return 0
    for key in ("total_nodes", "node_count", "nodes_count"):
        value = status.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    nodes = status.get("nodes")
    if isinstance(nodes, int) and not isinstance(nodes, bool):
        return nodes
    if isinstance(nodes, list):
        return len(nodes)
    for value in status.values():
        nested = _graph_total_nodes(value)
        if nested:
            return nested
    return 0


def _json_bool(value: Any, key: str) -> bool | None:
    if isinstance(value, dict):
        if isinstance(value.get(key), bool):
            return value[key]
        for item in value.values():
            nested = _json_bool(item, key)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = _json_bool(item, key)
            if nested is not None:
                return nested
    return None


def _graph_query_nodes(query: Any) -> list[Any]:
    if isinstance(query, list):
        return query
    if not isinstance(query, dict):
        return []
    for key in ("nodes", "results", "matches", "items"):
        value = query.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _graph_query_nodes(value)
            if nested:
                return nested
    for value in query.values():
        nested = _graph_query_nodes(value)
        if nested:
            return nested
    return []


def _graph_relevant(nodes: list[Any]) -> bool:
    if not nodes:
        return False
    material = json.dumps(nodes, sort_keys=True, default=str).lower()
    phase = "phase 54" in material or "phase54" in material
    routing = any(
        term in material
        for term in ("adapter", "network gate", "network-gate", "workstream")
    )
    return phase and routing


def _knowledge_read(
    evidence_sha256: str,
) -> tuple[bool, dict[str, Any], str, bytes]:
    wrapper = REPO_ROOT / "scripts/graphify-sync.sh"
    status_ok, status_raw = _run([str(wrapper.resolve()), "status"], timeout=30)
    query_text = "phase54_network_gate"
    query_ok, query_raw = _run(
        [str(wrapper.resolve()), "query", query_text],
        timeout=30,
    )
    status = _json_document(status_raw)
    query = _json_document(query_raw)
    commit_fresh = _json_bool(status, "commit_stale") is False
    graph_fresh = _json_bool(status, "stale") is False
    total_nodes = _graph_total_nodes(status)
    nodes = _graph_query_nodes(query)
    relevant = _graph_relevant(nodes)
    passed = bool(
        status_ok
        and query_ok
        and graph_fresh
        and commit_fresh
        and total_nodes > 0
        and nodes
        and relevant
    )
    return (
        passed,
        {
            "evidence_sha256": evidence_sha256,
            "stale": not graph_fresh,
            "commit_stale": not commit_fresh,
            "total_nodes": total_nodes,
            "query_node_count": len(nodes),
            "relevant_nodes": relevant,
            "query": query_text,
        },
        "graphify-status+query",
        status_raw + query_raw if passed else b"",
    )


def _oci_probe_passes(spec: AdapterSpec, normalized: dict[str, Any]) -> bool:
    semantic = normalized.get("semantic")
    if not isinstance(semantic, dict):
        return False
    if spec.check_id == "live_inventory":
        return bool(
            normalized.get("operation") == "peering.inventory"
            and CURRENT_VCN in semantic.get("vcn_cidrs", [])
            and CURRENT_SUBNET in semantic.get("subnet_cidrs", [])
            and CURRENT_HOST in semantic.get("current_host_ips", [])
        )
    if spec.check_id in {
        "builder_receipt",
        "builder_targets",
        "vcn_architecture",
        "target_network",
    }:
        return bool(
            normalized.get("operation") == "peering.address_plan"
            and semantic.get("target")
            == {
                "vcn": TARGET_VCN,
                "subnet": TARGET_SUBNET,
                "private_ip": TARGET_HOST,
                "service_subnet": "10.31.2.0/24",
            }
            and semantic.get("applies_live_oci_writes") is False
            and semantic.get("target_contains_10_21") is False
        )
    if spec.check_id in {
        "drg_bidirectional",
        "retirement_targets",
        "retirement_approval",
    }:
        return bool(
            normalized.get("operation") == "peering.drg_status"
            and semantic.get("applies_live_oci_writes") is False
            and semantic.get("attachments")
            and semantic.get("route_tables")
            and semantic.get("route_distributions")
            and not semantic.get("blockers")
        )
    if spec.check_id == "security_bidirectional":
        rows = semantic.get("security_lists")
        ids = semantic.get("argument_security_list_ocids")
        return bool(
            normalized.get("operation") == "network.security_list"
            and isinstance(rows, list)
            and rows
            and isinstance(ids, list)
            and len(rows) == len(ids)
            and all(
                row.get("security_list_ocid") in ids
                and row.get("lifecycle_state") == "AVAILABLE"
                and row.get("ingress")
                and row.get("egress")
                for row in rows
                if isinstance(row, dict)
            )
        )
    if spec.check_id in {"public_ip_baseline", "public_ip_binding", "vnic_private_ip"}:
        expected = TARGET_HOST if _target_host_required(spec) else CURRENT_HOST
        public = semantic.get("reserved_public_ips")
        private = semantic.get("private_ips")
        binding_ids = {
            item.get("private_ip_ocid")
            for item in public
            if isinstance(item, dict)
            and item.get("address") == PUBLIC_IP
            and item.get("lifetime") == "RESERVED"
        } if isinstance(public, list) else set()
        return bool(
            normalized.get("operation") == "inventory.get"
            and binding_ids
            and any(
                isinstance(item, dict)
                and item.get("private_ip_ocid") in binding_ids
                and item.get("address") == expected
                for item in private
            )
        ) if isinstance(private, list) else False
    return False


def _operational_10_21(
    sources: dict[str, dict[str, Any]],
) -> list[str]:
    residuals: set[str] = set()
    pattern = re.compile(r"(?<!\d)10\.21\.\d+\.\d+(?:/\d+)?(?!\d)")
    for source, document in sources.items():
        explicit = document.get("operational_10_21")
        if isinstance(explicit, list):
            residuals.update(
                f"{source}:{item}"
                for item in explicit
                if isinstance(item, str) and item
            )
        for item in _strings(document):
            residuals.update(
                f"{source}:{match.group(0)}"
                for match in pattern.finditer(item)
            )
    return sorted(residuals)


def _matrix_read(
    spec: AdapterSpec,
    evidence: dict[str, Any],
    evidence_path: pathlib.Path,
    evidence_sha256: str,
) -> tuple[bool, dict[str, Any], str, bytes]:
    drg_spec = AdapterSpec(
        spec.plan, spec.stage, "retirement_targets", "oci-admin", "oci-mcp"
    )
    drg_transport_ok, drg, drg_request, drg_raw = _oci_probe(
        drg_spec, evidence, evidence_path, evidence_sha256
    )
    inventory_spec = AdapterSpec(
        spec.plan, spec.stage, "vnic_private_ip", "oci-admin", "oci-mcp"
    )
    inventory_transport_ok, inventory, inventory_request, inventory_raw = _oci_probe(
        inventory_spec, evidence, evidence_path, evidence_sha256
    )
    oci_ok = bool(
        drg_transport_ok
        and inventory_transport_ok
        and _oci_probe_passes(drg_spec, drg)
        and _oci_probe_passes(inventory_spec, inventory)
    )
    dns_ok, dns, dns_request, dns_raw = _dns_read(spec, evidence_sha256)
    host_ok, host, host_request, host_raw = _host_read(
        spec, evidence_sha256, services=False
    )
    live_sources = {
        "oci.drg": drg.get("semantic", {}),
        "oci.inventory": inventory.get("semantic", {}),
        "dns": dns,
        "host": host,
    }
    residuals = _operational_10_21(live_sources)
    readback_material = json.dumps(
        live_sources,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    requires_zero_residual = spec.plan == "54-10"
    passed = bool(
        oci_ok
        and dns_ok
        and host_ok
        and (not requires_zero_residual or not residuals)
    )
    return (
        passed,
        {
            "evidence_sha256": evidence_sha256,
            "matrix_complete": passed,
            "oci": "PASS" if oci_ok else "BLOCK",
            "dns": "PASS" if dns_ok else "BLOCK",
            "host_private": host.get("private_path"),
            "host_public": host.get("public_path"),
            "operational_10_21": residuals,
            "residual_live": {
                "present": bool(residuals),
                "count": len(residuals),
                "sha256": hashlib.sha256(
                    json.dumps(
                        residuals,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest(),
            },
            "live_readback_sha256": hashlib.sha256(
                readback_material
            ).hexdigest(),
        },
        (
            f"{drg_request}+{inventory_request}+"
            f"{dns_request}+{host_request}"
        ),
        drg_raw + inventory_raw + dns_raw + host_raw if passed else b"",
    )


def _execute(
    spec: AdapterSpec,
    evidence: dict[str, Any],
    evidence_path: pathlib.Path,
    evidence_sha256: str,
) -> tuple[bool, dict[str, Any], str, bytes]:
    if spec.transport == "oci-mcp":
        result = _oci_probe(spec, evidence, evidence_path, evidence_sha256)
        return (
            result[0] and _oci_probe_passes(spec, result[1]),
            result[1],
            result[2],
            result[3],
        )
    if spec.transport == "dns-ssh":
        return _dns_read(spec, evidence_sha256)
    if spec.transport == "backup-ssh":
        return _backup_read(evidence_sha256)
    if spec.transport == "horistic-ssh":
        return _host_read(spec, evidence_sha256, services=False)
    if spec.transport == "service-ssh":
        return _host_read(spec, evidence_sha256, services=True)
    if spec.transport == "wireguard-ssh":
        return _wireguard_read(spec, evidence_sha256)
    if spec.transport == "be3-wg":
        return _be3_wg_read(spec, evidence_sha256)
    if spec.transport == "matrix":
        return _matrix_read(spec, evidence, evidence_path, evidence_sha256)
    if spec.transport == "knowledge":
        return _knowledge_read(evidence_sha256)
    return False, {"evidence_sha256": evidence_sha256}, "unsupported", b""


def _observation(spec: AdapterSpec, evidence_path: pathlib.Path) -> dict[str, Any]:
    evidence, evidence_sha256 = _read_evidence(spec, evidence_path)
    if evidence is None or evidence_sha256 is None:
        return {
            "schema": SCHEMA_OBSERVATION,
            "probe_id": spec.check_id,
            "status": "BLOCK",
            "read_only": True,
            "mutation_performed": False,
            "secret_material_present": False,
            "owner": spec.owner,
            "transport": spec.transport,
            "request_id": "invalid-canonical-evidence",
            "observed_sha256": hashlib.sha256(b"invalid-evidence").hexdigest(),
            "evidence_sha256": None,
            "normalized": {},
        }
    passed, normalized, request_id, raw = _execute(
        spec, evidence, evidence_path, evidence_sha256
    )
    return {
        "schema": SCHEMA_OBSERVATION,
        "probe_id": spec.check_id,
        "status": "PASS" if passed else "BLOCK",
        "read_only": True,
        "mutation_performed": False,
        "secret_material_present": False,
        "owner": spec.owner,
        "transport": spec.transport,
        "request_id": request_id,
        "observed_sha256": hashlib.sha256(
            raw or json.dumps(normalized, sort_keys=True).encode()
        ).hexdigest(),
        "evidence_sha256": evidence_sha256,
        "normalized": normalized,
    }


def _coverage(plan: str) -> dict[str, Any]:
    keys = [
        {"stage": stage, "check_id": check_id}
        for candidate, stage, check_id in REGISTRY
        if candidate == plan
    ]
    return {
        "schema": SCHEMA_COVERAGE,
        "plan": plan,
        "status": "READY" if keys else "BLOCK",
        "keys": keys,
    }


def _smoke(plan: str) -> dict[str, Any]:
    probes: list[tuple[str, Any]] = []
    if plan == "54-02":
        probes.extend(
            [
                ("oci-mcp-context.show", lambda: _oci_read()[0]),
                (
                    "srv1-strict-ssh",
                    lambda: _ssh("srv1", SSH_COMMANDS["identity"])[0],
                ),
                (
                    "srv3-strict-ssh",
                    lambda: _ssh("srv3", SSH_COMMANDS["identity"])[0],
                ),
                (
                    "dns-via-owners",
                    lambda: (
                        _ssh("srv1", "command -v dig >/dev/null")[0]
                        and _ssh("srv3", "command -v dig >/dev/null")[0]
                    ),
                ),
                (
                    "be3-owner-cli-pin",
                    lambda: _ssh("srv1", SSH_COMMANDS["be3_capability"])[0],
                ),
            ]
        )
    else:
        transports = {
            spec.transport
            for spec in REGISTRY.values()
            if spec.plan == plan and spec.transport != "stage-contract"
        }
        capability_spec = {
            "oci-mcp": lambda: _oci_read()[0],
            "dns-ssh": lambda: (
                _ssh("srv1", "command -v dig >/dev/null")[0]
                and _ssh("srv3", "command -v dig >/dev/null")[0]
            ),
            "backup-ssh": lambda: (
                _ssh("srv1", SSH_COMMANDS["identity"])[0]
                and _ssh("srv3", SSH_COMMANDS["identity"])[0]
            ),
            "horistic-ssh": lambda: any(
                _ssh_one(target, "LC_ALL=C hostname")[0]
                for target in SSH_OWNERS["horistic"]
            ),
            "service-ssh": lambda: any(
                _ssh_one(target, "LC_ALL=C command -v systemctl >/dev/null")[0]
                for target in SSH_OWNERS["horistic"]
            ),
            "wireguard-ssh": lambda: _ssh("srv1", SSH_COMMANDS["wireguard"])[0],
            "be3-wg": lambda: _ssh("srv1", SSH_COMMANDS["be3_capability"])[0],
            "matrix": lambda: (
                _oci_read()[0]
                and _ssh("srv1", "command -v dig >/dev/null")[0]
                and any(
                    _ssh_one(target, "LC_ALL=C hostname")[0]
                    for target in SSH_OWNERS["horistic"]
                )
            ),
            "knowledge": lambda: pathlib.Path(
                pathlib.Path(__file__).resolve().parents[3]
                / "scripts/graphify-sync.sh"
            ).is_file(),
        }
        for transport in sorted(transports):
            probes.append((transport, capability_spec[transport]))
    checks: list[tuple[str, bool]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(probes))) as pool:
        futures = [(check_id, pool.submit(probe)) for check_id, probe in probes]
        for check_id, future in futures:
            try:
                checks.append((check_id, bool(future.result(timeout=50))))
            except (TimeoutError, OSError):
                checks.append((check_id, False))
    passed = bool(checks and all(result for _, result in checks))
    return {
        "schema": "phase54.adapter-smoke.v1",
        "plan": plan,
        "status": "PASS" if passed else "BLOCK",
        "checks": [{"id": check_id, "status": "PASS" if ok else "BLOCK"} for check_id, ok in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("list", "smoke"):
        item = subparsers.add_parser(mode)
        item.add_argument("--plan", required=True, choices=tuple(STAGES))
    probe = subparsers.add_parser("probe")
    probe.add_argument("--plan", required=True, choices=tuple(STAGES))
    probe.add_argument("--stage", required=True)
    probe.add_argument("--probe-id", required=True)
    probe.add_argument("--evidence", required=True)
    args = parser.parse_args()
    if args.mode == "list":
        payload = _coverage(args.plan)
    elif args.mode == "smoke":
        payload = _smoke(args.plan)
    else:
        stage = None if args.stage == "none" else args.stage
        spec = REGISTRY.get((args.plan, stage, args.probe_id))
        if spec is None:
            payload = {
                "schema": SCHEMA_OBSERVATION,
                "probe_id": args.probe_id,
                "status": "BLOCK",
            }
        else:
            payload = _observation(spec, pathlib.Path(args.evidence))
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return 0 if payload.get("status") in {"PASS", "READY"} else 2


if __name__ == "__main__":
    sys.exit(main())
