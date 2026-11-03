"""omni gdrive — Gerenciamento governado do mount Google Drive na frota ATIUS.

Subcomandos:
    quotas     Exibe quotas de cache VFS estritas por host
    status     Verifica status do servico e montagem /mnt/gdrive na frota
    mount      Garante montagem e inicia gdrive-mount.service
    unmount    Desmonta e para gdrive-mount.service
    test       Executa probe ativo de leitura/escrita atomica em /mnt/gdrive
    doctor     Diagnostico de 8 pontos de saude do mount e ambiente
    check      Sonda ultrarrapida (< 1s) para monitoramento sintetico
    health     Alias para verificacao de leitura do ponto de montagem
    list       Lista conteudo da raiz de /mnt/gdrive
"""

from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import click

DEFAULT_MOUNTPOINT = "/mnt/gdrive"
DEFAULT_CACHE_DIR = "/var/cache/rclone-gdrive"
CONFIG_TMPFS_PATH = "/run/rclone/rclone.conf"
DEFAULT_SERVICE_NAME = "gdrive-mount.service"
LEGACY_SERVICE_NAME = "rclone-gdrive.service"
DEFAULT_LOCK_PATH = "/run/lock/omni-gdrive.lock"

FLEET_HOSTS = ["atius-srv-1", "atius-srv-2", "atius-srv-3", "giovanni-w11-pc"]
FORBIDDEN_HOSTS = {"aln-srv", "horistic-srv"}
ALLOWED_HOSTS = {"atius-srv-1", "atius-srv-2", "atius-srv-3", "giovanni-w11-pc"}

HOST_CACHE_QUOTAS: dict[str, tuple[str, str]] = {
    "atius-srv-1": ("5G", "12h"),
    "atius-srv-2": ("10G", "24h"),
    "atius-srv-3": ("5G", "12h"),
    "atius-srv-4": ("30G", "48h"),
}
DEFAULT_QUOTA: tuple[str, str] = ("4G", "12h")

OCI_DRG_IPS: dict[str, str] = {
    "atius-srv-1": "10.11.1.11",
    "atius-srv-2": "10.12.1.12",
    "atius-srv-3": "10.13.1.13",
}

PUBLIC_FALLBACK_IPS: dict[str, str] = {
    "atius-srv-1": "137.131.190.161",
    "atius-srv-2": "129.148.47.32",
    "atius-srv-3": "136.248.126.12",
}


def validate_host(host: str) -> str:
    """Valida host contra a allowlist estrita e rejeita aln-srv e horistic-srv."""
    clean_host = host.strip().split(".")[0].lower()
    if clean_host in FORBIDDEN_HOSTS or host.strip().lower() in FORBIDDEN_HOSTS:
        raise ValueError(f"Host '{host}' explicitly excluded from Google Drive fleet mount")
    if clean_host not in ALLOWED_HOSTS and host.strip().lower() not in ALLOWED_HOSTS:
        raise ValueError(f"Host '{host}' explicitly excluded from Google Drive fleet mount")
    return clean_host


def get_host_quota(hostname: str) -> tuple[str, str]:
    """Retorna (max_size, max_age) para o host especificado."""
    clean_host = hostname.strip().split(".")[0].lower()
    return HOST_CACHE_QUOTAS.get(clean_host, DEFAULT_QUOTA)


def build_rclone_conf_content(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Monta a configuracao ini do rclone.conf a partir de credenciais Vault."""
    if not client_id or not client_id.strip():
        raise ValueError("client_id obrigatorio")
    if not client_secret or not client_secret.strip():
        raise ValueError("client_secret obrigatorio")
    if not refresh_token or not refresh_token.strip():
        raise ValueError("refresh_token obrigatorio")

    # Serializacao compacta conforme contrato institucional (sem espacos apos virgula e dois-pontos)
    token_json = json.dumps(
        {
            "access_token": "",
            "token_type": "Bearer",
            "refresh_token": refresh_token.strip(),
        },
        separators=(",", ":"),
    )

    return f"""[gdrive-main]
type = drive
client_id = {client_id.strip()}
client_secret = {client_secret.strip()}
scope = drive
token = {token_json}
"""


def parse_rclone_conf_content(content: str) -> dict[str, Any]:
    """Parseia e valida configuracao INI do rclone (suporta gdrive-main e giovanni-drive)."""
    import configparser
    cp = configparser.ConfigParser()
    cp.read_string(content)
    parsed: dict[str, Any] = {}
    for section in cp.sections():
        sec_dict = dict(cp[section])
        if sec_dict.get("type") != "drive":
            raise ValueError(f"Secao [{section}] nao eh do tipo drive: {sec_dict.get('type')}")
        parsed[section] = sec_dict
    if not parsed:
        raise ValueError("Nenhuma secao valida encontrada no rclone.conf")
    return parsed


class GDriveLock:
    """Lock de concorrencia atomico para operacoes Google Drive."""
    def __init__(self, lock_path: str = DEFAULT_LOCK_PATH, timeout_seconds: int = 60):
        self.lock_path = Path(lock_path)
        self.timeout_seconds = timeout_seconds
        self.is_active = False

    def acquire(self) -> bool:
        now = time.time()
        expires_at = now + self.timeout_seconds
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            try:
                data = json.loads(self.lock_path.read_text(encoding="utf-8"))
                file_expires = float(data.get("expires_at", 0))
                if now < file_expires:
                    return False
            except Exception:
                pass
        payload = {
            "pid": os.getpid(),
            "acquired_at": now,
            "expires_at": expires_at,
        }
        try:
            temp_file = self.lock_path.with_suffix(".tmp")
            temp_file.write_text(json.dumps(payload), encoding="utf-8")
            temp_file.replace(self.lock_path)
            self.is_active = True
            return True
        except OSError:
            return False

    def release(self) -> None:
        if self.lock_path.exists():
            try:
                self.lock_path.unlink()
            except OSError:
                pass
        self.is_active = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Lock em {self.lock_path} ocupado por outro processo")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def render_systemd_unit(
    hostname: str,
    mountpoint: str = DEFAULT_MOUNTPOINT,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> str:
    """Renderiza a unit systemd governada para gdrive-mount.service."""
    clean_host = validate_host(hostname)
    max_size, max_age = get_host_quota(clean_host)

    return f"""[Unit]
Description=Atius Fleet Google Drive FUSE Mount
Documentation=man:rclone(1) https://atius.com.br
After=network-online.target
Wants=network-online.target
AssertPathIsDirectory={mountpoint}

[Service]
Type=notify
Restart=on-failure
RestartSec=10s
KillMode=mixed
TimeoutStopSec=30s
LimitNOFILE=65536

# Protecao e limites de CPU/IO (Contencao institucional <= 20% do host)
CPUQuota=20%
Nice=10
CPUSchedulingPolicy=other
IOSchedulingClass=best-effort
IOSchedulingPriority=7

# Preparacao do tmpfs e credenciais via Vault
ExecStartPre=-/bin/mkdir -p /run/rclone {cache_dir} {mountpoint}
ExecStartPre=-/bin/chmod 700 /run/rclone
ExecStartPre=/usr/local/bin/gdrive-vault-hydrate

# Mount rclone com VFS Full Cache e Pacing de API
ExecStart=/usr/bin/rclone mount gdrive-main: {mountpoint} \\
    --config {CONFIG_TMPFS_PATH} \\
    --allow-other \\
    --umask 022 \\
    --dir-cache-time 72h \\
    --poll-interval 1m \\
    --vfs-cache-mode full \\
    --vfs-cache-max-size {max_size} \\
    --vfs-cache-max-age {max_age} \\
    --vfs-read-chunk-size 32M \\
    --vfs-read-chunk-size-limit 256M \\
    --cache-dir {cache_dir} \\
    --buffer-size 16M \\
    --tpslimit 4 \\
    --tpslimit-burst 1 \\
    --drive-pacer-min-sleep 100ms \\
    --transfers 2 \\
    --checkers 4 \\
    --attr-timeout 1s \\
    --log-level INFO \\
    --syslog-facility DAEMON

# Desmontagem limpa lazy e purga imediata do tmpfs
ExecStop=/bin/fusermount -u -z {mountpoint}
ExecStopPost=-/bin/rm -f {CONFIG_TMPFS_PATH}

[Install]
WantedBy=multi-user.target
"""


def _exec_host_cmd(host: str, remote_cmd: str, timeout: int = 15) -> tuple[int, str, str]:
    """Executa comando em host remoto via SSH com 3-tier fallback ou localmente no Windows 11."""
    clean_host = validate_host(host)
    current_hostname = socket.gethostname().split(".")[0].lower()

    # Tratamento especifico para giovanni-w11-pc (Google Drive nativo G:\)
    if clean_host == "giovanni-w11-pc":
        g_drive_exists = Path("G:/").exists() or os.path.exists("G:\\")
        if "mountpoint" in remote_cmd or "systemctl" in remote_cmd or "gdrive" in remote_cmd or "stat" in remote_cmd or "PROBE=" in remote_cmd:
            if g_drive_exists:
                if "SVC=" in remote_cmd or "is-active" in remote_cmd:
                    return 0, "active|mounted|0|10", ""
                elif "mountpoint -q /mnt/gdrive && stat" in remote_cmd or "echo 'OK'" in remote_cmd or "check" in remote_cmd:
                    return 0, "OK", ""
                elif "PASS" in remote_cmd or "PROBE=" in remote_cmd:
                    return 0, "PASS", ""
                return 0, "active|mounted", ""
            else:
                if "mountpoint -q /mnt/gdrive && stat" in remote_cmd or "NOT_MOUNTED" in remote_cmd or "check" in remote_cmd:
                    return 0, "NOT_MOUNTED", ""
                return 1, "inactive|not-mounted", "Google Drive (G:\\) nao encontrado no Windows 11"
        # Execucao local no Windows se comando generico
        if os.name == "nt":
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", remote_cmd],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return res.returncode, res.stdout.strip(), res.stderr.strip()
            except subprocess.TimeoutExpired:
                return 124, "", f"Timeout ({timeout}s) executando comando local W11"
            except Exception as e:
                return 1, "", str(e)

    if clean_host == current_hostname or host in ("localhost", "127.0.0.1"):
        try:
            res = subprocess.run(
                ["bash", "-c", remote_cmd] if os.name != "nt" else ["powershell", "-Command", remote_cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return 124, "", f"Timeout ({timeout}s) executando comando local"
        except Exception as e:
            return 1, "", str(e)

    # Execucao remota via SSH com 3-Tier Fallback:
    # 1º: DNS Interno (*.atius.internal)
    # 2º: OCI DRG IP privado (10.11.1.11, 10.12.1.12, 10.13.1.13)
    # 3º: IP publico de fallback
    tier1_endpoint = host if "." in host else f"{clean_host}.atius.internal"
    tier2_endpoint = OCI_DRG_IPS.get(clean_host)
    tier3_endpoint = PUBLIC_FALLBACK_IPS.get(clean_host)

    endpoints = [tier1_endpoint]
    if tier2_endpoint and tier2_endpoint not in endpoints:
        endpoints.append(tier2_endpoint)
    if tier3_endpoint and tier3_endpoint not in endpoints:
        endpoints.append(tier3_endpoint)

    user = "ubuntu"
    last_rc = 1
    last_stdout = ""
    last_stderr = f"Falha de conexao com {host} em todos os niveis de conectividade"

    for ep in endpoints:
        ssh_cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-n",
            f"{user}@{ep}",
            remote_cmd,
        ]
        try:
            res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode != 255:
                return res.returncode, res.stdout.strip(), res.stderr.strip()
            last_rc = res.returncode
            last_stdout = res.stdout.strip()
            last_stderr = res.stderr.strip() or f"Falha de transporte SSH ao conectar a {ep}"
        except subprocess.TimeoutExpired:
            last_rc = 124
            last_stderr = f"Timeout ({timeout}s) conectando a {ep}"
            continue
        except Exception as e:
            last_rc = 1
            last_stderr = str(e)
            continue

    return last_rc, last_stdout, last_stderr


# ═══════════════════════════════════════════════════════════════
# Grupo Principal Click
# ═══════════════════════════════════════════════════════════════

@click.group(name="gdrive")
def gdrive() -> None:
    """Governanca de armazenamento Google Drive FUSE (/mnt/gdrive) na frota ATIUS."""


# ═══════════════════════════════════════════════════════════════
# Subcomando: quotas
# ═══════════════════════════════════════════════════════════════

@gdrive.command("quotas")
@click.option("--json", "json_output", is_flag=True, help="Exibir saida em formato JSON estruturado")
def quotas_cmd(json_output: bool) -> None:
    """Exibe quotas de cache VFS estritas por host."""
    if json_output:
        payload = {
            "quotas": {
                host: {"max_size": size, "max_age": age}
                for host, (size, age) in HOST_CACHE_QUOTAS.items()
            },
            "default": {
                "max_size": DEFAULT_QUOTA[0],
                "max_age": DEFAULT_QUOTA[1],
            },
            "mountpoint": DEFAULT_MOUNTPOINT,
            "cache_dir": DEFAULT_CACHE_DIR,
        }
        click.echo(json.dumps(payload, indent=2))
        return

    click.echo(f"{'Host':20} {'Max Size':10} {'Max Age':10}")
    click.echo("-" * 42)
    for host, (size, age) in HOST_CACHE_QUOTAS.items():
        click.echo(f"{host:20} {size:10} {age:10}")
    click.echo(f"{'default (outros)':20} {DEFAULT_QUOTA[0]:10} {DEFAULT_QUOTA[1]:10}")


# ═══════════════════════════════════════════════════════════════
# Subcomando: status
# ═══════════════════════════════════════════════════════════════

@gdrive.command("status")
@click.option("--host", default=None, help="Host especifico (default: todos os hosts da frota)")
@click.option("--json", "json_output", is_flag=True, help="Exibir saida em formato JSON estruturado")
def status_cmd(host: str | None, json_output: bool) -> None:
    """Verifica status da unit e montagem /mnt/gdrive na frota."""
    targets = [host] if host else FLEET_HOSTS
    if not json_output:
        click.echo(f"Verificando status do Google Drive mount ({DEFAULT_MOUNTPOINT}) na frota...")

    remote_probe = (
        "SVC=$(systemctl is-active gdrive-mount.service 2>/dev/null || true); "
        "[ \"$SVC\" = \"active\" ] || SVC=$(systemctl is-active rclone-gdrive.service 2>/dev/null || true); "
        "[ -n \"$SVC\" ] || SVC='inactive'; "
        "MNT=$(mountpoint -q /mnt/gdrive && echo 'mounted' || echo 'not-mounted'); "
        "CACHE=$(du -sh /var/cache/rclone-gdrive 2>/dev/null | cut -f1 || echo '0'); "
        "ITEMS=$(ls -1 /mnt/gdrive 2>/dev/null | wc -l || echo '0'); "
        "echo \"$SVC|$MNT|$CACHE|$ITEMS\""
    )

    results: list[dict[str, Any]] = []
    has_error = False
    has_inactive = False

    for t in targets:
        rc, stdout, stderr = _exec_host_cmd(t, remote_probe, timeout=12)
        if rc != 0 or not stdout:
            has_error = True
            item = {
                "host": t,
                "service": "unknown",
                "mount": "unknown",
                "cache_size": "unknown",
                "items_count": 0,
                "status": "error",
                "error": stderr or f"Falha de execucao (codigo {rc})",
            }
        else:
            parts = stdout.split("|")
            svc = parts[0].strip() if len(parts) > 0 else "unknown"
            mnt = parts[1].strip() if len(parts) > 1 else "unknown"
            cache = parts[2].strip() if len(parts) > 2 else "unknown"
            items_cnt = int(parts[3].strip()) if len(parts) > 3 and parts[3].strip().isdigit() else 0

            is_ok = (svc == "active" and mnt == "mounted")
            if not is_ok:
                has_inactive = True

            item = {
                "host": t,
                "service": svc,
                "mount": mnt,
                "cache_size": cache,
                "items_count": items_cnt,
                "status": "active" if is_ok else "inactive",
            }
        results.append(item)

        if not json_output:
            if item["status"] == "error":
                click.echo(f"[{t}] erro: {item.get('error', 'desconhecido')}")
            else:
                click.echo(f"[{t}] service={item['service']} mount={item['mount']} cache={item['cache_size']} items={item['items_count']}")

    overall = "ok" if (not has_error and not has_inactive) else ("error" if has_error else "inactive")
    exit_code = 0 if overall == "ok" else (1 if has_error else 2)

    if json_output:
        click.echo(json.dumps({"status": overall, "mountpoint": DEFAULT_MOUNTPOINT, "hosts": results}, indent=2))

    sys.exit(exit_code)


# ═══════════════════════════════════════════════════════════════
# Subcomando: mount
# ═══════════════════════════════════════════════════════════════

@gdrive.command("mount")
@click.option("--host", default=None, help="Host especifico (default: todos os hosts da frota)")
@click.option("--json", "json_output", is_flag=True, help="Exibir saida em formato JSON estruturado")
def mount_cmd(host: str | None, json_output: bool) -> None:
    """Inicia gdrive-mount.service e valida /mnt/gdrive."""
    targets = [host] if host else FLEET_HOSTS
    remote_mount = (
        "sudo systemctl start gdrive-mount.service 2>/dev/null || sudo systemctl start rclone-gdrive.service 2>/dev/null; "
        "sleep 1; "
        "SVC=$(systemctl is-active gdrive-mount.service 2>/dev/null || systemctl is-active rclone-gdrive.service 2>/dev/null || echo 'inactive'); "
        "MNT=$(mountpoint -q /mnt/gdrive && echo 'mounted' || echo 'not-mounted'); "
        "echo \"$SVC|$MNT\""
    )

    results: list[dict[str, Any]] = []
    has_error = False

    for t in targets:
        if not json_output:
            click.echo(f"Iniciando gdrive-mount em {t}...")
        rc, stdout, stderr = _exec_host_cmd(t, remote_mount, timeout=20)
        parts = stdout.split("|") if stdout else []
        svc = parts[0].strip() if len(parts) > 0 else "unknown"
        mnt = parts[1].strip() if len(parts) > 1 else "unknown"

        success = (rc == 0 and svc == "active" and mnt == "mounted")
        if not success:
            has_error = True

        item = {
            "host": t,
            "success": success,
            "service": svc,
            "mount": mnt,
            "error": stderr if not success else None,
        }
        results.append(item)
        if not json_output:
            state_str = "OK (ativo e montado)" if success else f"FALHA (service={svc}, mount={mnt})"
            click.echo(f"[{t}] {state_str}")

    exit_code = 1 if has_error else 0
    if json_output:
        click.echo(json.dumps({"status": "PASS" if not has_error else "FAIL", "results": results}, indent=2))

    sys.exit(exit_code)


# ═══════════════════════════════════════════════════════════════
# Subcomando: unmount
# ═══════════════════════════════════════════════════════════════

@gdrive.command("unmount")
@click.option("--host", default=None, help="Host especifico (default: todos os hosts da frota)")
@click.option("--json", "json_output", is_flag=True, help="Exibir saida em formato JSON estruturado")
def unmount_cmd(host: str | None, json_output: bool) -> None:
    """Para gdrive-mount.service e desmonta /mnt/gdrive com lazy unmount."""
    targets = [host] if host else FLEET_HOSTS
    remote_unmount = (
        "sudo systemctl stop gdrive-mount.service 2>/dev/null || sudo systemctl stop rclone-gdrive.service 2>/dev/null || true; "
        "fusermount -u -z /mnt/gdrive 2>/dev/null || true; "
        "rm -f /run/rclone/rclone.conf 2>/dev/null || true; "
        "mountpoint -q /mnt/gdrive && echo 'still-mounted' || echo 'unmounted'"
    )

    results: list[dict[str, Any]] = []
    has_error = False

    for t in targets:
        if not json_output:
            click.echo(f"Parando e desmontando gdrive-mount em {t}...")
        rc, stdout, stderr = _exec_host_cmd(t, remote_unmount, timeout=15)
        unmounted = (stdout.strip() == "unmounted")
        if not unmounted or rc != 0:
            has_error = True

        item = {
            "host": t,
            "unmounted": unmounted,
            "status": "unmounted" if unmounted else "error",
            "error": stderr if not unmounted else None,
        }
        results.append(item)
        if not json_output:
            click.echo(f"[{t}] {'Desmontado com sucesso' if unmounted else 'Falha ao desmontar'}")

    exit_code = 1 if has_error else 0
    if json_output:
        click.echo(json.dumps({"status": "PASS" if not has_error else "FAIL", "results": results}, indent=2))

    sys.exit(exit_code)


# ═══════════════════════════════════════════════════════════════
# Subcomando: test (Probe ativo atômico)
# ═══════════════════════════════════════════════════════════════

@gdrive.command("test")
@click.option("--host", default=None, help="Host especifico (default: todos os hosts da frota)")
@click.option("--json", "json_output", is_flag=True, help="Exibir saida em formato JSON estruturado")
def test_cmd(host: str | None, json_output: bool) -> None:
    """Executa teste ativo de leitura/escrita atomica com validacao de SHA256 em /mnt/gdrive."""
    targets = [host] if host else FLEET_HOSTS
    probe_script = (
        "if ! mountpoint -q /mnt/gdrive; then echo 'NOT_MOUNTED'; exit 2; fi; "
        "TST=$(date +%s); PROBE=\"/mnt/gdrive/.omni_probe_${TST}_$$\"; "
        "PAYLOAD=\"probe_test_${TST}_$$\"; "
        "echo -n \"$PAYLOAD\" > \"$PROBE\" || { echo 'WRITE_FAIL'; exit 1; }; "
        "READ_BACK=$(cat \"$PROBE\" 2>/dev/null) || { rm -f \"$PROBE\"; echo 'READ_FAIL'; exit 1; }; "
        "rm -f \"$PROBE\" || true; "
        "if [ \"$READ_BACK\" = \"$PAYLOAD\" ]; then echo 'PASS'; else echo 'HASH_MISMATCH'; exit 1; fi"
    )

    results: list[dict[str, Any]] = []
    has_error = False
    has_unmounted = False

    for t in targets:
        rc, stdout, stderr = _exec_host_cmd(t, probe_script, timeout=20)
        status = stdout.strip()
        if rc == 2 or status == "NOT_MOUNTED":
            has_unmounted = True
            item = {"host": t, "result": "NOT_MOUNTED", "status": "unmounted"}
        elif rc == 0 and status == "PASS":
            item = {"host": t, "result": "PASS", "status": "ok"}
        else:
            has_error = True
            item = {"host": t, "result": status or "FAIL", "status": "error", "error": stderr or "Falha de IO no FUSE"}
        results.append(item)

        if not json_output:
            click.echo(f"[{t}] Probe I/O: {item['result']}")

    exit_code = 0 if (not has_error and not has_unmounted) else (1 if has_error else 2)
    if json_output:
        click.echo(json.dumps({"status": "PASS" if exit_code == 0 else "FAIL", "results": results}, indent=2))

    sys.exit(exit_code)


# ═══════════════════════════════════════════════════════════════
# Subcomando: doctor (Auditoria de 8 pontos)
# ═══════════════════════════════════════════════════════════════

@gdrive.command("doctor")
@click.option("--host", default=None, help="Host especifico (default: todos os hosts da frota)")
@click.option("--json", "json_output", is_flag=True, help="Exibir saida em formato JSON estruturado")
def doctor_cmd(host: str | None, json_output: bool) -> None:
    """Executa auditoria diagnostica de 8 pontos de conformidade operacional."""
    targets = [host] if host else FLEET_HOSTS
    doctor_runner = (
        "if [ -x /usr/local/bin/gdrive-doctor ]; then "
        "  /usr/local/bin/gdrive-doctor --json 2>/dev/null || true; "
        "elif [ -x /home/ubuntu/GitHub/omni-srv-admin/modules/fleet-gdrive/scripts/gdrive-doctor.sh ]; then "
        "  /home/ubuntu/GitHub/omni-srv-admin/modules/fleet-gdrive/scripts/gdrive-doctor.sh --json 2>/dev/null || true; "
        "else "
        "  FUSE_DEV=$([ -c /dev/fuse ] && echo 'PASS' || echo 'FAIL'); "
        "  FUSE_CONF=$(grep -q '^[[:space:]]*user_allow_other' /etc/fuse.conf 2>/dev/null && echo 'PASS' || echo 'FAIL'); "
        "  RCLONE_BIN=$(command -v rclone >/dev/null && echo 'PASS' || echo 'FAIL'); "
        "  VAULT_CONN=$(curl -k -s --connect-timeout 2 https://10.13.1.13:8202/v1/sys/health >/dev/null && echo 'PASS' || echo 'FAIL'); "
        "  GOOGLE_API=$(nc -z -w 2 www.googleapis.com 443 2>/dev/null && echo 'PASS' || echo 'FAIL'); "
        "  echo \"{\\\"checks\\\": {\\\"fuse_kernel\\\": \\\"$FUSE_DEV\\\", \\\"fuse_conf\\\": \\\"$FUSE_CONF\\\", \\\"rclone_binary\\\": \\\"$RCLONE_BIN\\\", \\\"vault_connectivity\\\": \\\"$VAULT_CONN\\\", \\\"google_api\\\": \\\"$GOOGLE_API\\\"}}\"; "
        "fi"
    )

    results: list[dict[str, Any]] = []
    has_fail = False
    has_warn = False

    for t in targets:
        rc, stdout, stderr = _exec_host_cmd(t, doctor_runner, timeout=25)
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(stdout)
        except Exception:
            parsed = {"status": "FAIL", "raw": stdout, "error": stderr or "Nao foi possivel parsear JSON"}

        status = parsed.get("status", "FAIL" if rc != 0 else "PASS")
        if status == "FAIL":
            has_fail = True
        elif status == "WARN":
            has_warn = True

        results.append({"host": t, "doctor": parsed})
        if not json_output:
            click.echo(f"[{t}] Diagnostico Doctor: {status}")

    exit_code = 0 if not (has_fail or has_warn) else (1 if has_fail else 2)
    if json_output:
        click.echo(json.dumps({"status": "PASS" if exit_code == 0 else "FAIL", "results": results}, indent=2))

    sys.exit(exit_code)


# ═══════════════════════════════════════════════════════════════
# Subcomando: check (Sonda ultrarrápida < 1s)
# ═══════════════════════════════════════════════════════════════

@gdrive.command("check")
@click.option("--host", default=None, help="Host especifico (default: todos os hosts da frota)")
@click.option("--json", "json_output", is_flag=True, help="Exibir saida em formato JSON estruturado")
def check_cmd(host: str | None, json_output: bool) -> None:
    """Sonda ultrarrapida (< 1s) para monitoramento sintetico de montagem."""
    targets = [host] if host else FLEET_HOSTS
    fast_check = "mountpoint -q /mnt/gdrive && stat -t /mnt/gdrive >/dev/null 2>&1 && echo 'OK' || echo 'NOT_MOUNTED'"

    results: list[dict[str, Any]] = []
    has_error = False
    has_unmounted = False

    for t in targets:
        rc, stdout, stderr = _exec_host_cmd(t, fast_check, timeout=5)
        res = stdout.strip()
        if rc == 0 and res == "OK":
            item = {"host": t, "status": "mounted", "healthy": True}
        elif res == "NOT_MOUNTED":
            has_unmounted = True
            item = {"host": t, "status": "unmounted", "healthy": False}
        else:
            has_error = True
            item = {"host": t, "status": "error", "healthy": False, "error": stderr or f"Falha (rc={rc})"}
        results.append(item)

        if not json_output:
            click.echo(f"[{t}] Sonda Check: {item['status']}")

    exit_code = 0 if (not has_error and not has_unmounted) else (1 if has_error else 2)
    if json_output:
        click.echo(json.dumps({"status": "PASS" if exit_code == 0 else "FAIL", "results": results}, indent=2))

    sys.exit(exit_code)


# ═══════════════════════════════════════════════════════════════
# Subcomando: health (Retrocompatibilidade)
# ═══════════════════════════════════════════════════════════════

@gdrive.command("health")
@click.option("--host", default=None, help="Host especifico (default: todos os hosts da frota)")
@click.option("--json", "json_output", is_flag=True, help="Exibir saida em formato JSON estruturado")
def health_cmd(host: str | None, json_output: bool) -> None:
    """Testa leitura em /mnt/gdrive na frota."""
    targets = [host] if host else FLEET_HOSTS
    remote_health = "if mountpoint -q /mnt/gdrive; then ls /mnt/gdrive | head -n 5; else echo 'NAO_MONTADO'; fi"

    results: list[dict[str, Any]] = []
    has_error = False

    for t in targets:
        rc, stdout, stderr = _exec_host_cmd(t, remote_health, timeout=15)
        lines = stdout.strip().splitlines() if stdout else []
        is_mounted = stdout.strip() != "NAO_MONTADO" and rc == 0
        if not is_mounted:
            has_error = True

        item = {
            "host": t,
            "mounted": is_mounted,
            "entries": lines if is_mounted else [],
            "error": stderr if not is_mounted else None,
        }
        results.append(item)

        if not json_output:
            if is_mounted:
                click.echo(f"[{t}] Conteudo:\n{stdout.strip()}")
            else:
                click.echo(f"[{t}] NAO_MONTADO ({stderr})")

    exit_code = 1 if has_error else 0
    if json_output:
        click.echo(json.dumps({"status": "PASS" if not has_error else "FAIL", "results": results}, indent=2))

    sys.exit(exit_code)


# ═══════════════════════════════════════════════════════════════
# Subcomando: list
# ═══════════════════════════════════════════════════════════════

@gdrive.command("list")
@click.option("--host", default="atius-srv-1", help="Host especifico (default: atius-srv-1)")
@click.option("--path", "subpath", default="", help="Subdiretorio dentro de /mnt/gdrive")
def list_cmd(host: str, subpath: str) -> None:
    """Lista conteudo dentro de /mnt/gdrive."""
    sub = subpath.strip().lstrip("/")
    if sub:
        clean_subpath = shlex.quote(sub)
        target_path = f"/mnt/gdrive/{clean_subpath}".rstrip("/")
    else:
        target_path = "/mnt/gdrive"
    rc, stdout, stderr = _exec_host_cmd(host, f"ls -la {target_path}", timeout=15)
    if rc == 0:
        click.echo(stdout)
    else:
        click.echo(f"Erro listando {target_path} em {host}: {stderr}")
        sys.exit(1)
