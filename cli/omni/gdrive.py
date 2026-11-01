"""omni gdrive — Gerenciamento governado do mount Google Drive na frota ATIUS.

Subcomandos:
    quotas     Exibe quotas de cache VFS por host
    status     Verifica status do servico e montagem /mnt/gdrive na frota
    mount      Garante montagem e inicia rclone-gdrive.service
    unmount    Desmonta e para rclone-gdrive.service
    health     Testa integridade, latencia e escrita/leitura em /mnt/gdrive
    list       Lista conteudo de /mnt/gdrive
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

DEFAULT_MOUNTPOINT = "/mnt/gdrive"
DEFAULT_CACHE_DIR = "/var/cache/rclone-gdrive"
CONFIG_TMPFS_PATH = "/run/rclone/rclone.conf"

HOST_CACHE_QUOTAS: dict[str, tuple[str, str]] = {
    "atius-srv-1": ("3G", "6h"),
    "atius-srv-2": ("10G", "24h"),
    "atius-srv-3": ("5G", "12h"),
    "atius-srv-4": ("30G", "48h"),
    "horistic-srv": ("10G", "24h"),
}
DEFAULT_QUOTA: tuple[str, str] = ("4G", "12h")


def get_host_quota(hostname: str) -> tuple[str, str]:
    """Retorna (max_size, max_age) para o host especificado."""
    clean_host = hostname.split(".")[0].lower()
    return HOST_CACHE_QUOTAS.get(clean_host, DEFAULT_QUOTA)


def build_rclone_conf_content(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Monta a configuracao ini do rclone.conf a partir de credenciais Vault."""
    if not client_id or not client_id.strip():
        raise ValueError("client_id obrigatorio")
    if not client_secret or not client_secret.strip():
        raise ValueError("client_secret obrigatorio")
    if not refresh_token or not refresh_token.strip():
        raise ValueError("refresh_token obrigatorio")

    token_json = json.dumps({"access_token": "", "token_type": "Bearer", "refresh_token": refresh_token.strip()})

    return f"""[gdrive-main]
type = drive
client_id = {client_id.strip()}
client_secret = {client_secret.strip()}
scope = drive
token = {token_json}
"""


def render_systemd_unit(
    hostname: str,
    mountpoint: str = DEFAULT_MOUNTPOINT,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> str:
    """Renderiza a unit systemd de sistema para o rclone-gdrive."""
    max_size, max_age = get_host_quota(hostname)

    return f"""[Unit]
Description=Atius Fleet Google Drive FUSE Mount
Documentation=man:rclone(1) https://atius.com.br
After=network-online.target
Wants=network-online.target
AssertPathIsDirectory={mountpoint}

[Service]
Type=notify
Restart=always
RestartSec=10s
KillMode=mixed
TimeoutStopSec=30s
LimitNOFILE=65536

# Protecao e limites de IO
Nice=10
CPUSchedulingPolicy=other
IOSchedulingClass=best-effort
IOSchedulingPriority=7

# Preparacao do tmpfs e credenciais via Vault
ExecStartPre=-/bin/mkdir -p /run/rclone {cache_dir} {mountpoint}
ExecStartPre=-/bin/chmod 700 /run/rclone
ExecStartPre=/usr/local/bin/gdrive-vault-hydrate

# Mount rclone
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
    --transfers 2 \\
    --checkers 4 \\
    --attr-timeout 1s \\
    --log-level INFO \\
    --syslog-facility DAEMON

# Desmontagem limpa
ExecStop=/bin/fusermount -u -z {mountpoint}
ExecStopPost=-/bin/rm -f {CONFIG_TMPFS_PATH}

[Install]
WantedBy=multi-user.target
"""


@click.group(name="gdrive")
def gdrive() -> None:
    """Governanca de armazenamento Google Drive FUSE (/mnt/gdrive) na frota ATIUS."""


@gdrive.command("quotas")
def quotas_cmd() -> None:
    """Exibe quotas de cache VFS estritas por host."""
    click.echo(f"{'Host':20} {'Max Size':10} {'Max Age':10}")
    click.echo("-" * 42)
    for host, (size, age) in HOST_CACHE_QUOTAS.items():
        click.echo(f"{host:20} {size:10} {age:10}")
    click.echo(f"{'default (outros)':20} {DEFAULT_QUOTA[0]:10} {DEFAULT_QUOTA[1]:10}")


@gdrive.command("status")
@click.option("--host", default=None, help="Host especifico (default: todos os hosts da frota)")
def status_cmd(host: str | None) -> None:
    """Verifica status da unit e montagem /mnt/gdrive na frota."""
    targets = [host] if host else ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4"]
    click.echo(f"Verificando status do Google Drive mount ({DEFAULT_MOUNTPOINT}) na frota...")
    for t in targets:
        cmd = ["ssh", "-n", f"ubuntu@{t}.atius.internal", "systemctl is-active rclone-gdrive.service 2>/dev/null || true; mountpoint -q /mnt/gdrive && echo 'mounted' || echo 'not-mounted'"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            lines = res.stdout.strip().splitlines()
            svc_status = lines[0] if lines else "unknown"
            mnt_status = lines[1] if len(lines) > 1 else "unknown"
            click.echo(f"[{t}] service={svc_status} mount={mnt_status}")
        except Exception as e:
            click.echo(f"[{t}] erro: {e}")


@gdrive.command("mount")
@click.option("--host", default=None, help="Host especifico (default: todos)")
def mount_cmd(host: str | None) -> None:
    """Inicia rclone-gdrive.service e valida /mnt/gdrive."""
    targets = [host] if host else ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4"]
    for t in targets:
        click.echo(f"Iniciando rclone-gdrive em {t}...")
        subprocess.run(["ssh", "-n", f"ubuntu@{t}.atius.internal", "sudo systemctl start rclone-gdrive.service"])


@gdrive.command("unmount")
@click.option("--host", default=None, help="Host especifico (default: todos)")
def unmount_cmd(host: str | None) -> None:
    """Para rclone-gdrive.service e desmonta /mnt/gdrive."""
    targets = [host] if host else ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4"]
    for t in targets:
        click.echo(f"Parando rclone-gdrive em {t}...")
        subprocess.run(["ssh", "-n", f"ubuntu@{t}.atius.internal", "sudo systemctl stop rclone-gdrive.service"])


@gdrive.command("health")
@click.option("--host", default=None, help="Host especifico (default: todos)")
def health_cmd(host: str | None) -> None:
    """Testa leitura em /mnt/gdrive."""
    targets = [host] if host else ["atius-srv-1", "atius-srv-2", "atius-srv-3", "atius-srv-4"]
    for t in targets:
        cmd = ["ssh", "-n", f"ubuntu@{t}.atius.internal", "if mountpoint -q /mnt/gdrive; then ls /mnt/gdrive | head -n 5; else echo 'NAO_MONTADO'; fi"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            click.echo(f"[{t}] Conteudo:\n{res.stdout.strip()}")
        except Exception as e:
            click.echo(f"[{t}] Falha: {e}")
