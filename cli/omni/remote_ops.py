"""remote-ops — operações remotas em servidores gerenciados via omni-srv-admin.

Uso:
    omni srv list                    # Lista servidores cadastrados
    omni srv status <host>           # Status remoto (disco, uptime, carga)
    omni srv exec <host> <cmd>       # Executa comando via SSH
    omni srv cleanup <host>          # Executa limpeza completa
    omni srv cleanup <host> --dry-run  # Simula limpeza
"""
from __future__ import annotations

import os
import subprocess
import sys
import json
import shlex
from pathlib import Path

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", str(Path(__file__).resolve().parents[2])))
HOSTS_DIR = REPO / "inventory" / "hosts"
SCRIPTS_DIR = REPO / "modules" / "cleanup" / "scripts"
LOCAL_HOST_IDS = {"atius-srv-1", "srv1", "atius"}


def _find_host(host_id: str) -> tuple[Path, str, str]:
    """Encontra host por ID ou alias. Retorna (path, ssh_user@host, id)."""
    hosts_dir = HOSTS_DIR if HOSTS_DIR.exists() else REPO / "hosts"
    
    # Try exact match first
    path = hosts_dir / f"{host_id}.yaml"
    if path.exists():
        return _parse_host(path, host_id)
    
    # Try alias match — scan all YAMLs
    for f in sorted(hosts_dir.glob("*.yaml")):
        text = f.read_text()
        # Check aliases in YAML
        in_aliases = False
        for line in text.splitlines():
            ls = line.strip().strip("-").strip()
            if ls == "aliases:":
                in_aliases = True
                continue
            if in_aliases and ls.startswith("id:"):
                in_aliases = False
                continue
            if in_aliases and ls == host_id:
                return _parse_host(f, host_id)
            if in_aliases and ls.startswith("#"):
                continue
            # Check if it's the next key (not a list item)
            if in_aliases and ":" in ls and not ls.startswith("-"):
                in_aliases = False
    
    # Try fuzzy match
    matches = sorted(hosts_dir.glob(f"*{host_id}*.yaml"))
    if matches:
        return _parse_host(matches[0], host_id)
    
    raise click.ClickException(f"Host não encontrado: {host_id}")


def _parse_host(path: Path, requested_id: str) -> tuple[Path, str, str]:
    """Extrai ssh_target e id de um arquivo YAML."""
    text = path.read_text()
    ssh_val = ""
    host_id_val = path.stem
    for line in text.splitlines():
        ls = line.strip()
        if ls.startswith("ssh:"):
            ssh_val = ls.split(":", 1)[1].strip().strip('"').strip("'")
        if ls.startswith("id:"):
            host_id_val = ls.split(":", 1)[1].strip().strip('"').strip("'")
    if not ssh_val:
        raise click.ClickException(f"Host {path.stem} sem configuração SSH")
    return path, ssh_val, host_id_val


def _yaml_scalar(path: Path, key: str) -> str:
    """Extrai um scalar simples de YAML sem depender de PyYAML."""
    prefix = f"{key}:"
    for line in path.read_text().splitlines():
        ls = line.strip()
        if ls.startswith(prefix):
            return ls.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


def _ssh_candidates(path: Path, ssh_target: str) -> list[str]:
    """Retorna alvos SSH em ordem: inventario, VPN, publico ou publico primeiro via env."""
    user = ssh_target.split("@", 1)[0] if "@" in ssh_target else "ubuntu"
    oci_private_ip = _yaml_scalar(path, "oci_private_ip")
    vpn_ip = _yaml_scalar(path, "vpn_ip")
    public_ip = _yaml_scalar(path, "public_ip")
    prefer_public = os.environ.get("OMNI_SRV_PUBLIC_FIRST", "0") == "1"

    candidates: list[str] = []

    def add(target: str) -> None:
        if target and target not in candidates:
            candidates.append(target)

    if prefer_public and public_ip:
        add(f"{user}@{public_ip}")
    if oci_private_ip:
        add(f"{user}@{oci_private_ip}")
    add(ssh_target)
    if vpn_ip:
        add(f"{user}@{vpn_ip}")
    if public_ip:
        add(f"{user}@{public_ip}")
    return candidates


def _ssh_run(ssh_target: str, cmd: str | list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """Executa comando via SSH e retorna resultado."""
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
    else:
        cmd_str = cmd
    
    full_cmd = [
        "ssh",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        ssh_target,
        "bash",
        "-lc",
        shlex.quote(cmd_str),
    ]
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)


def _ssh_run_any(path: Path, ssh_target: str, cmd: str | list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """Executa via SSH tentando VPN/public fallback quando o alvo primario nao conecta."""
    last: subprocess.CompletedProcess | None = None
    for target in _ssh_candidates(path, ssh_target):
        try:
            result = _ssh_run(target, cmd, timeout=timeout)
        except subprocess.TimeoutExpired:
            last = subprocess.CompletedProcess(args=target, returncode=255, stdout="", stderr="timeout")
            continue
        if result.returncode == 255 and any(s in result.stderr.lower() for s in ("timed out", "no route", "connection refused")):
            last = result
            continue
        return result
    if last is not None:
        return last
    return _ssh_run(ssh_target, cmd, timeout=timeout)


def _run_host(path: Path, ssh_target: str, hid: str, cmd: str, timeout: int = 300) -> subprocess.CompletedProcess:
    """Executa localmente no SRV-1 quando aplicavel, senao por SSH."""
    if hid in LOCAL_HOST_IDS and os.environ.get("OMNI_SRV_FORCE_SSH", "0") != "1":
        return subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=timeout)
    return _ssh_run_any(path, ssh_target, cmd, timeout=timeout)


def _list_hosts() -> list[dict]:
    """Lista todos os hosts do inventário."""
    hosts_dir = HOSTS_DIR if HOSTS_DIR.exists() else REPO / "hosts"
    hosts = []
    for path in sorted(hosts_dir.glob("*.yaml")):
        text = path.read_text()
        data = {"id": path.stem, "role": "", "status": "", "ssh": "", "aliases": ""}
        aliases = []
        in_aliases = False
        for line in text.splitlines():
            ls = line.strip()
            if ls.startswith("ssh:"):
                data["ssh"] = ls.split(":", 1)[1].strip().strip('"').strip("'")
            if ls.startswith("role:"):
                data["role"] = ls.split(":", 1)[1].strip().strip('"')
            if ls.startswith("status:"):
                data["status"] = ls.split(":", 1)[1].strip().strip('"')
            if ls.startswith("id:"):
                data["id"] = ls.split(":", 1)[1].strip().strip('"').strip("'")
            if ls == "aliases:":
                in_aliases = True
                continue
            if in_aliases:
                if ":" in ls and not ls.startswith("-"):
                    in_aliases = False
                elif ls.startswith("- "):
                    aliases.append(ls[2:].strip())
        if aliases:
            data["aliases"] = ", ".join(aliases)
        hosts.append(data)
    return hosts


def _host_ids_for_arg(host_id: str) -> list[str]:
    if host_id != "all":
        return [host_id]
    return [h["id"] for h in _list_hosts() if h.get("status", "") != "retired"]


def _storage_audit_script() -> str:
    return r"""set -uo pipefail
echo "## $(hostname)"
date -Is
if [ -r /etc/os-release ]; then . /etc/os-release; echo "os=$PRETTY_NAME kernel=$(uname -r) arch=$(uname -m)"; fi
echo "-- df"
df -hT / /home 2>/dev/null | sed -n '1,5p'
echo "-- inode"
df -ih / /home 2>/dev/null | sed -n '1,5p'
echo "-- memory"
free -h 2>/dev/null || true
echo "-- apt/dpkg"
ps -eo pid,comm,args | grep -E 'apt|dpkg|unattended|do-release' | grep -v grep || true
echo "-- journal"
journalctl --disk-usage 2>/dev/null || true
echo "-- docker df"
docker system df 2>/dev/null || true
echo "-- podman df"
podman system df 2>/dev/null || true
echo "-- pm2 logs"
du -sh "$HOME/.pm2/logs" 2>/dev/null || true
echo "-- home top"
timeout 45s du -x -h -d1 "$HOME" 2>/dev/null | sort -h | tail -25 || true
echo "-- varlog top"
timeout 20s du -x -h -d1 /var/log 2>/dev/null | sort -h | tail -20 || true
echo "-- container storage"
du -sh "$HOME/.local/share/containers/storage" /var/lib/docker 2>/dev/null || true
echo "-- candidate bulky backups"
find "$HOME" -xdev -maxdepth 1 \( -name 'pre-upgrade-24.04-backup' -o -name 'srv3-disk-relief-before-config-clone-*' -o -name '.config-clone-backups' -o -name '.backups' \) -exec du -sh {} \; 2>/dev/null | sort -h || true
echo "-- large media-ish >100M"
find "$HOME" -xdev -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.webm' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) -size +100M -printf '%s %p\n' 2>/dev/null | sort -n | tail -30 | numfmt --field=1 --to=iec-i --suffix=B || true
"""


def _autoclean_script(dry_run: bool, include_volumes: bool) -> str:
    dry = "1" if dry_run else "0"
    volumes = "1" if include_volumes else "0"
    return rf"""set -uo pipefail
DRY_RUN={dry}
INCLUDE_VOLUMES={volumes}
LOG="$HOME/.logs/omni-fleet-autoclean.log"
mkdir -p "$HOME/.logs"
log() {{ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }}
do_run() {{
  if [ "$DRY_RUN" = "1" ]; then
    log "DRY $*"
  else
    log "RUN $*"
    bash -lc "$*" 2>&1 | tail -20 | tee -a "$LOG" || true
  fi
}}
log "AUTOCLEAN start host=$(hostname) dry_run=$DRY_RUN include_volumes=$INCLUDE_VOLUMES"
log "disk_before=$(df -h / | tail -1 | awk '{{print $3 "/" $2 " used=" $5 " avail=" $4}}')"

log "phase=tmp old top-level entries"
find /tmp -maxdepth 1 -mindepth 1 -mtime +3 \
  ! -name '.X*' ! -name '.ICE*' ! -name '.font*' ! -name '.Test*' \
  ! -name 'systemd-*' ! -name 'snap*' ! -name 'hermes_*' \
  -printf '%kK %p\n' 2>/dev/null | sort -n | tail -25 | tee -a "$LOG" || true
if [ "$DRY_RUN" = "0" ]; then
  find /tmp -maxdepth 1 -mindepth 1 -mtime +3 \
    ! -name '.X*' ! -name '.ICE*' ! -name '.font*' ! -name '.Test*' \
    ! -name 'systemd-*' ! -name 'snap*' ! -name 'hermes_*' \
    -exec rm -rf {{}} + 2>/dev/null || true
fi

log "phase=caches"
for p in \
  "$HOME/.cache/go-build" \
  "$HOME/.cache/codex-update-manager" \
  "$HOME/.cache/ms-playwright" \
  "$HOME/.cache/copilot" \
  "$HOME/.cache/node-gyp" \
  "$HOME/.cache/codex-desktop"; do
  [ -d "$p" ] || continue
  du -sh "$p" 2>/dev/null | tee -a "$LOG" || true
  if [ "$DRY_RUN" = "0" ]; then rm -rf "$p"/* 2>/dev/null || true; fi
done
[ "$DRY_RUN" = "0" ] && command -v pnpm >/dev/null 2>&1 && pnpm store prune 2>&1 | tail -10 | tee -a "$LOG" || true
[ "$DRY_RUN" = "0" ] && command -v pip >/dev/null 2>&1 && pip cache purge 2>&1 | tail -10 | tee -a "$LOG" || true
[ "$DRY_RUN" = "0" ] && [ -d "$HOME/.bun/install/cache" ] && rm -rf "$HOME/.bun/install/cache"/* 2>/dev/null || true

log "phase=logs trim"
for dir in "$HOME/.logs" "$HOME/.pm2/logs"; do
  [ -d "$dir" ] || continue
  find "$dir" -type f \( -name '*.log' -o -name '*.log.*' \) -size +50M -printf '%s %p\n' 2>/dev/null | sort -n | tail -25 | numfmt --field=1 --to=iec-i --suffix=B | tee -a "$LOG" || true
  if [ "$DRY_RUN" = "0" ]; then
    find "$dir" -type f \( -name '*.log' -o -name '*.log.*' \) -size +50M -print0 2>/dev/null | while IFS= read -r -d '' f; do
      tail -c 5242880 "$f" > "$f.tmp" 2>/dev/null && mv "$f.tmp" "$f"
    done
    find "$dir" -type f \( -name '*.log' -o -name '*.log.*' -o -name '*.bak' \) -mtime +15 -delete 2>/dev/null || true
  fi
done
log "phase=xrdp/lightdm/xorg logs"
du -ch /var/log/xrdp.log /var/log/xrdp-sesman.log /var/log/lightdm \
  "$HOME"/.xorgxrdp.*.log "$HOME"/.Xorg.*.log "$HOME"/.xsession-errors \
  2>/dev/null | tail -1 | tee -a "$LOG" || true
if [ "$DRY_RUN" = "0" ]; then
  sudo -n truncate -s 0 /var/log/xrdp.log /var/log/xrdp-sesman.log 2>/dev/null || true
  sudo -n find /var/log/lightdm -type f \( -name '*.log' -o -name '*.log.*' -o -name '*.gz' \) -delete 2>/dev/null || true
  rm -f "$HOME"/.xorgxrdp.*.log "$HOME"/.Xorg.*.log 2>/dev/null || true
  : > "$HOME/.xsession-errors" 2>/dev/null || true
fi

log "phase=containers unused images/networks (no volumes by default)"
if command -v podman >/dev/null 2>&1; then
  podman images -f dangling=true 2>/dev/null | tail -20 | tee -a "$LOG" || true
  [ "$DRY_RUN" = "0" ] && podman image prune -af 2>&1 | tail -10 | tee -a "$LOG" || true
  [ "$DRY_RUN" = "0" ] && podman system prune -f 2>&1 | tail -10 | tee -a "$LOG" || true
  [ "$DRY_RUN" = "0" ] && [ "$INCLUDE_VOLUMES" = "1" ] && podman volume prune -f 2>&1 | tail -10 | tee -a "$LOG" || true
fi
if command -v docker >/dev/null 2>&1; then
  docker images -f dangling=true 2>/dev/null | tail -20 | tee -a "$LOG" || true
  [ "$DRY_RUN" = "0" ] && docker image prune -af 2>&1 | tail -10 | tee -a "$LOG" || true
  [ "$DRY_RUN" = "0" ] && docker builder prune -af 2>&1 | tail -10 | tee -a "$LOG" || true
  [ "$DRY_RUN" = "0" ] && docker container prune -f 2>&1 | tail -10 | tee -a "$LOG" || true
  [ "$DRY_RUN" = "0" ] && docker network prune -f 2>&1 | tail -10 | tee -a "$LOG" || true
  [ "$DRY_RUN" = "0" ] && [ "$INCLUDE_VOLUMES" = "1" ] && docker volume prune -f 2>&1 | tail -10 | tee -a "$LOG" || true
fi

log "phase=journal"
journalctl --disk-usage 2>/dev/null | tee -a "$LOG" || true
if [ "$DRY_RUN" = "0" ]; then
  sudo -n journalctl --vacuum-size=500M 2>&1 | tail -10 | tee -a "$LOG" || log "journal vacuum skipped: sudo unavailable"
fi

log "phase=manual-review bulky backups"
find "$HOME" -xdev -maxdepth 1 \( -name 'pre-upgrade-24.04-backup' -o -name 'srv3-disk-relief-before-config-clone-*' -o -name '.config-clone-backups' -o -name '.backups' \) -exec du -sh {{}} \; 2>/dev/null | sort -h | tee -a "$LOG" || true
log "disk_after=$(df -h / | tail -1 | awk '{{print $3 "/" $2 " used=" $5 " avail=" $4}}')"
log "AUTOCLEAN end"
"""


@click.group(name="srv")
def srv() -> None:
    """Operações remotas em servidores gerenciados."""


@srv.command("list")
def list_servers() -> None:
    """Lista servidores cadastrados no inventário."""
    hosts = _list_hosts()
    if not hosts:
        click.echo("Nenhum host encontrado.")
        return
    click.echo(f"{'ID':20} {'Aliases':24} {'Role':18} {'Status':10} {'SSH':30}")
    click.echo("-" * 105)
    for h in hosts:
        click.echo(f"{h['id']:20} {h['aliases']:24} {h['role']:18} {h['status']:10} {h['ssh']:30}")


@srv.command("status")
@click.argument("host_id")
def remote_status(host_id: str) -> None:
    """Status remoto: disco, uptime, carga, memória."""
    path, ssh_target, hid = _find_host(host_id)
    
    click.echo(f"=== {hid} ===")
    
    commands = {
        "Disco": "df -h / | tail -1 | awk '{print $3, $4, $5}'",
        "Uptime": "uptime -p | cut -d' ' -f2-",
        "Carga": "cat /proc/loadavg | awk '{print $1, $2, $3}'",
        "Memória": "free -h | grep Mem | awk '{print $3, $4}'",
        "Processos": "ps aux | wc -l",
        "Hostname": "hostname",
    }
    
    for label, cmd in commands.items():
        try:
            r = _run_host(path, ssh_target, hid, cmd, timeout=15)
            out = r.stdout.strip()
            click.echo(f"  {label:12} {out}")
        except Exception as e:
            click.echo(f"  {label:12} ERRO: {e}")
    
    try:
        r = _run_host(path, ssh_target, hid, "ls ~/.hermes/sessions/ 2>/dev/null | wc -l", timeout=10)
        click.echo(f"  {'Hermes':12} {r.stdout.strip()} sessions")
    except Exception:
        pass


@srv.command("exec")
@click.argument("host_id")
@click.argument("cmd", nargs=-1, required=True)
@click.option("--timeout", default=300, help="Timeout em segundos.")
def remote_exec(host_id: str, cmd: tuple[str], timeout: int) -> None:
    """Executa comando(s) via SSH no servidor."""
    path, ssh_target, hid = _find_host(host_id)
    cmd_str = " ".join(cmd)
    
    click.echo(f"$ {cmd_str}")
    try:
        r = _run_host(path, ssh_target, hid, cmd_str, timeout=timeout)
        if r.stdout:
            click.echo(r.stdout)
        if r.stderr:
            click.echo(f"stderr: {r.stderr}", err=True)
        raise SystemExit(r.returncode)
    except subprocess.TimeoutExpired:
        raise click.ClickException(f"Comando excedeu timeout de {timeout}s")
    except Exception as e:
        raise click.ClickException(f"Erro SSH: {e}")


@srv.command("cleanup")
@click.argument("host_id")
@click.option("--dry-run", is_flag=True, help="Simula sem modificar.")
@click.option("--phase", default="all", help="Fase: 1=pods, 2=journal, 3=tmp, 4=caches, 5=logs, all")
def remote_cleanup(host_id: str, dry_run: bool, phase: str) -> None:
    """Executa limpeza remota via SSH."""
    path, ssh_target, hid = _find_host(host_id)
    
    click.echo(f"=== Cleanup {hid} (dry-run={'yes' if dry_run else 'no'}, phase={phase}) ===")
    click.echo(f"Host: {ssh_target}")
    
    # Fase 1: Podman/Docker prune
    if phase in ("all", "1"):
        click.echo("--- Fase 1: Container prune ---")
        if dry_run:
            click.echo("  [dry-run] podman image prune -af && podman volume prune -f")
        else:
            for cmd, label in [
                ("podman image prune -f 2>&1 | tail -3", "Podman img"),
                ("podman volume prune -f 2>&1 | tail -3", "Podman vol"),
                ("docker image prune -f 2>&1 | tail -3", "Docker img"),
                ("docker builder prune -f 2>&1 | tail -3", "Docker build"),
            ]:
                try:
                    r = _run_host(path, ssh_target, hid, cmd, timeout=120)
                    out = r.stdout.strip()[:120]
                    if out:
                        click.echo(f"  {label}: {out}")
                except Exception:
                    pass
    
    # Fase 2: Journal vacuum
    if phase in ("all", "2"):
        click.echo("--- Fase 2: Journal vacuum ---")
        if dry_run:
            click.echo("  [dry-run] journalctl --vacuum-size=500M")
        else:
            r = _run_host(path, ssh_target, hid, "sudo journalctl --vacuum-size=500M 2>&1 | tail -3", timeout=60)
            click.echo(f"  {r.stdout.strip()[:200]}")
    
    # Fase 3: /tmp antigos
    if phase in ("all", "3"):
        click.echo("--- Fase 3: /tmp antigos ---")
        if dry_run:
            r = _run_host(path, ssh_target, hid, "find /tmp -maxdepth 1 -mtime +3 ! -name '.X*' -printf '%kK %p\\n' 2>/dev/null | head -10 || echo '(empty)'", timeout=15)
            click.echo(f"  Would remove: {r.stdout.strip()[:300]}")
        else:
            r = _run_host(path, ssh_target, hid, "find /tmp -maxdepth 1 -mtime +3 ! -name '.X*' ! -name '.ICE*' ! -name 'systemd*' ! -name '.font*' ! -name 'snap*' -exec rm -rf {} + 2>/dev/null; echo OK", timeout=60)
            click.echo(f"  {r.stdout.strip()[:100]}")
    
    # Fase 4: Caches
    if phase in ("all", "4"):
        click.echo("--- Fase 4: Caches ---")
        cmds = [
            ("npm", "npm cache clean --force 2>&1 | tail -2 || true"),
            ("pip", "pip cache purge 2>&1 | tail -2 || true"),
            ("npx", "rm -rf ~/.npm/_npx/* ~/.npm/_cacache/* 2>/dev/null; echo OK"),
            ("go-build", "rm -rf ~/.cache/go-build/* 2>/dev/null; echo OK"),
            ("codex-up", "rm -rf ~/.cache/codex-update-manager/* 2>/dev/null; echo OK"),
            ("playwright", "rm -rf ~/.cache/ms-playwright/* 2>/dev/null; echo OK"),
            ("copilot", "rm -rf ~/.cache/copilot/* 2>/dev/null; echo OK"),
            ("node-gyp", "rm -rf ~/.cache/node-gyp/* 2>/dev/null; echo OK"),
        ]
        for label, c in cmds:
            if dry_run:
                continue
            try:
                r = _run_host(path, ssh_target, hid, c, timeout=30)
                out = r.stdout.strip()[:80]
                if out and out != "OK":
                    click.echo(f"  {label:12} {out}")
            except Exception:
                pass
        click.echo("  Caches OK")
    
    # Fase 5: Logs
    if phase in ("all", "5"):
        click.echo("--- Fase 5: Logs antigos ---")
        if dry_run:
            click.echo("  [dry-run] find ~/logs ~/.logs -name '*.log' -mtime +15 -delete")
        else:
            r = _run_host(path, ssh_target, hid, "mkdir -p ~/.logs; find ~/logs ~/.logs -name '*.log' -mtime +15 -delete 2>/dev/null; echo OK", timeout=30)
            click.echo(f"  {r.stdout.strip()[:100]}")
    
    # Resultado
    if not dry_run:
        r = _run_host(path, ssh_target, hid, "df -h / | tail -1 | awk '{print $3, $4, $5}'", timeout=10)
        click.echo(f"\nDisco final: {r.stdout.strip()}")
        click.echo("✓ Cleanup concluído.")
    else:
        click.echo("\nDry-run OK. Remova --dry-run para executar.")


@srv.command("storage-audit")
@click.argument("host_id")
@click.option("--timeout", default=180, help="Timeout por host em segundos.")
def storage_audit(host_id: str, timeout: int) -> None:
    """Auditoria read-only de storage/logs/containers/caches por host ou all."""
    for item in _host_ids_for_arg(host_id):
        path, ssh_target, hid = _find_host(item)
        click.echo(f"\n=== Storage audit {hid} ===")
        r = _run_host(path, ssh_target, hid, _storage_audit_script(), timeout=timeout)
        if r.stdout:
            click.echo(r.stdout.rstrip())
        if r.stderr:
            click.echo(f"stderr: {r.stderr.rstrip()}", err=True)
        if r.returncode != 0:
            click.echo(f"rc={r.returncode}", err=True)


@srv.command("autoclean")
@click.argument("host_id")
@click.option("--apply", "apply_changes", is_flag=True, help="Aplica limpeza segura. Sem isto roda dry-run.")
@click.option("--include-volumes", is_flag=True, help="Inclui prune de volumes sem uso. Desligado por padrão.")
@click.option("--timeout", default=420, help="Timeout por host em segundos.")
def autoclean(host_id: str, apply_changes: bool, include_volumes: bool, timeout: int) -> None:
    """Autoclean seguro de fleet: tmp, caches, logs, dangling images e journal."""
    dry_run = not apply_changes
    for item in _host_ids_for_arg(host_id):
        path, ssh_target, hid = _find_host(item)
        click.echo(f"\n=== Autoclean {hid} (dry-run={'yes' if dry_run else 'no'}, include-volumes={'yes' if include_volumes else 'no'}) ===")
        r = _run_host(path, ssh_target, hid, _autoclean_script(dry_run=dry_run, include_volumes=include_volumes), timeout=timeout)
        if r.stdout:
            click.echo(r.stdout.rstrip())
        if r.stderr:
            click.echo(f"stderr: {r.stderr.rstrip()}", err=True)
        if r.returncode != 0:
            click.echo(f"rc={r.returncode}", err=True)
