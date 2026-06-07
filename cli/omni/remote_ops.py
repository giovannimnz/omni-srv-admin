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
from pathlib import Path

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", "/home/ubuntu/GitHub/omni-srv-admin"))
HOSTS_DIR = REPO / "inventory" / "hosts"
SCRIPTS_DIR = REPO / "modules" / "cleanup" / "scripts"


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


def _ssh_run(ssh_target: str, cmd: str | list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    """Executa comando via SSH e retorna resultado."""
    if isinstance(cmd, list):
        cmd_str = " ".join(cmd)
    else:
        cmd_str = cmd
    
    full_cmd = ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", ssh_target, cmd_str]
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)


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
            r = _ssh_run(ssh_target, cmd, timeout=15)
            out = r.stdout.strip()
            click.echo(f"  {label:12} {out}")
        except Exception as e:
            click.echo(f"  {label:12} ERRO: {e}")
    
    try:
        r = _ssh_run(ssh_target, "ls ~/.hermes/sessions/ 2>/dev/null | wc -l", timeout=10)
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
        r = _ssh_run(ssh_target, cmd_str, timeout=timeout)
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
                ("podman image prune -af 2>&1 | tail -3", "Podman img"),
                ("podman volume prune -f 2>&1 | tail -3", "Podman vol"),
                ("docker system prune -af --volumes 2>&1 | tail -3", "Docker"),
            ]:
                try:
                    r = _ssh_run(ssh_target, cmd, timeout=120)
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
            r = _ssh_run(ssh_target, "sudo journalctl --vacuum-size=500M 2>&1 | tail -3", timeout=60)
            click.echo(f"  {r.stdout.strip()[:200]}")
    
    # Fase 3: /tmp antigos
    if phase in ("all", "3"):
        click.echo("--- Fase 3: /tmp antigos ---")
        if dry_run:
            r = _ssh_run(ssh_target, "find /tmp -maxdepth 1 -mtime +3 ! -name '.X*' -printf '%kK %p\\n' 2>/dev/null | head -10 || echo '(empty)'", timeout=15)
            click.echo(f"  Would remove: {r.stdout.strip()[:300]}")
        else:
            r = _ssh_run(ssh_target, "find /tmp -maxdepth 1 -mtime +3 ! -name '.X*' ! -name '.ICE*' ! -name 'systemd*' ! -name '.font*' ! -name 'snap*' -exec rm -rf {} + 2>/dev/null; echo OK", timeout=60)
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
                r = _ssh_run(ssh_target, c, timeout=30)
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
            r = _ssh_run(ssh_target, "mkdir -p ~/.logs; find ~/logs ~/.logs -name '*.log' -mtime +15 -delete 2>/dev/null; echo OK", timeout=30)
            click.echo(f"  {r.stdout.strip()[:100]}")
    
    # Resultado
    if not dry_run:
        r = _ssh_run(ssh_target, "df -h / | tail -1 | awk '{print $3, $4, $5}'", timeout=10)
        click.echo(f"\nDisco final: {r.stdout.strip()}")
        click.echo("✓ Cleanup concluído.")
    else:
        click.echo("\nDry-run OK. Remova --dry-run para executar.")
