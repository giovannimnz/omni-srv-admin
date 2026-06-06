"""omni — CLI unificada para administração de servidores e gestão de forks.

Uso:
    omni fork-sync projects list
    omni admin status
    omni deploy list
    omni backup create /path
    omni version
"""

import os
import sys
import json
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path

import click
from omni import __version__
from omni.xrdp_abnt2 import xrdp_abnt2
from omni.srv1_ops import srv1_ops


@click.group()
def cli():
    """omni — administração de servidores e gestão de forks."""


cli.add_command(xrdp_abnt2)
cli.add_command(srv1_ops)


# ═══════════════════════════════════════════════════════════════
# fork-sync subcommand
# ═══════════════════════════════════════════════════════════════

try:
    from fork_sync.cli import cli as fork_sync_group
    cli.add_command(fork_sync_group, "fork-sync")
except ImportError:
    @cli.group(name="fork-sync")
    def fork_sync_stub():
        """Gestão de forks (instale fork-sync pkg para ativar)."""
        click.echo("fork-sync package não encontrado. Instale: pip install -e modules/fork-sync/cli/")


# ═══════════════════════════════════════════════════════════════
# admin subcommand
# ═══════════════════════════════════════════════════════════════

@cli.group()
def admin():
    """Administração do servidor: status, health, services, processes."""


def _sys_env():
    """Retorna env com LC_ALL=C para parsing consistente."""
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    return env


@admin.command("status")
def admin_status():
    """Visão geral do servidor: uptime, CPU, memória, disco."""
    env = _sys_env()
    data = {}


    # Uptime
    try:
        out = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5, env=env)
        data["uptime"] = out.stdout.strip()
    except Exception:
        data["uptime"] = "N/A"

    # Load
    try:
        out = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5, env=env)
        parts = out.stdout.split("load average:")
        data["load"] = parts[1].strip() if len(parts) > 1 else "N/A"
    except Exception:
        data["load"] = "N/A"

    # Memory
    try:
        out = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5, env=env)
        mem_line = [l for l in out.stdout.split("\n") if l.lower().startswith("mem")]
        if mem_line:
            parts = mem_line[0].split()
            data["memory"] = {"total": parts[1], "used": parts[2], "free": parts[3]}
    except Exception:
        data["memory"] = "N/A"

    # Disk
    try:
        out = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5, env=env)
        disk_line = [l for l in out.stdout.split("\n") if l.endswith("/")]
        if disk_line:
            parts = disk_line[0].split()
            data["disk"] = {"total": parts[1] if len(parts) > 1 else "N/A",
                            "used": parts[2] if len(parts) > 2 else "N/A",
                            "avail": parts[3] if len(parts) > 3 else "N/A",
                            "use_pct": parts[4] if len(parts) > 4 else "N/A"}
    except Exception:
        data["disk"] = "N/A"

    # Sysinfo
    try:
        out = subprocess.run(["uname", "-a"], capture_output=True, text=True, timeout=5)
        data["kernel"] = out.stdout.strip()
    except Exception:
        data["kernel"] = "N/A"

    click.echo(f"Uptime:  {data['uptime']}")
    click.echo(f"Load:    {data['load']}")
    mem = data["memory"]
    if isinstance(mem, dict):
        click.echo(f"Mem:     {mem['used']} / {mem['total']} (free: {mem['free']})")
    disk = data["disk"]
    if isinstance(disk, dict):
        click.echo(f"Disk:    {disk['used']} / {disk['total']} ({disk['use_pct']} used)")
    click.echo(f"Kernel:  {data['kernel']}")


@admin.command("health")
def admin_health():
    """Health checks básicos: ping, portas, serviços chave."""
    checks = []

    # DNS resolve
    try:
        out = subprocess.run(["ping", "-c1", "-W2", "google.com"],
                             capture_output=True, text=True, timeout=5)
        checks.append({"check": "dns/ping", "status": "ok" if out.returncode == 0 else "fail"})
    except Exception:
        checks.append({"check": "dns/ping", "status": "fail"})

    # Portas chave
    for port, name in [(80, "HTTP"), (443, "HTTPS"), (22, "SSH")]:
        try:
            out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
            found = f":{port} " in out.stdout
            checks.append({"check": f"port:{port} ({name})", "status": "ok" if found else "down"})
        except Exception:
            checks.append({"check": f"port:{port} ({name})", "status": "unknown"})

    # Relatar
    failed = [c for c in checks if c["status"] != "ok"]
    for c in checks:
        icon = "✓" if c["status"] == "ok" else "✗"
        click.echo(f"  {icon} {c['check']}: {c['status']}")

    if failed:
        click.echo(f"\n⚠ {len(failed)} check(s) com falha")
    else:
        click.echo("\n✅ Todos os checks OK")


@admin.command()
@click.argument("name", required=False, default=None)
def services(name):
    """Lista serviços systemd. Se NAME passado, mostra status + logs."""
    if name:
        # Status de 1 serviço
        try:
            out = subprocess.run(["systemctl", "status", name, "--no-pager", "-l"],
                                 capture_output=True, text=True, timeout=10)
            click.echo(out.stdout[:3000])
        except Exception as e:
            click.echo(f"[ERROR] {e}", err=True)
        return

    # Listar todos
    try:
        out = subprocess.run(["systemctl", "list-units", "--type=service", "--no-pager"],
                             capture_output=True, text=True, timeout=10)
        lines = out.stdout.split("\n")
        header = True
        for line in lines:
            if header and "LOAD" in line:
                header = False
                click.echo(line)
                click.echo("-" * 80)
                continue
            if not header and line.strip() and not line.startswith("● "):
                click.echo(line)
    except Exception as e:
        click.echo(f"[ERROR] {e}", err=True)


@admin.command("processes")
@click.option("--sort", default="cpu", help="Ordenar por: cpu, mem, pid (default: cpu)")
@click.option("--limit", default=15, help="Número de processos (default: 15)")
def admin_processes(sort, limit):
    """Top-like: processos por uso de CPU ou memória."""
    env = _sys_env()
    sort_flag = "-%cpu" if sort == "cpu" else "-pmem"
    try:
        out = subprocess.run(
            ["ps", f"--sort={sort_flag}", "--no-headers", "-eo", "pid,%cpu,pmem,rss,comm"],
            capture_output=True, text=True, timeout=5, env=env
        )
        lines = [l for l in out.stdout.strip().split("\n") if l.strip()]
        click.echo(f"{'PID':>7} {'%CPU':>5} {'PMEM':>5} {'RSS':>8} COMMAND")
        click.echo("-" * 50)
        for line in lines[:limit]:
            click.echo(line)
    except Exception as e:
        click.echo(f"[ERROR] {e}", err=True)


# ═══════════════════════════════════════════════════════════════
# deploy subcommand
# ═══════════════════════════════════════════════════════════════

@cli.group()
def deploy():
    """Deploy de projetos: lista projetos com deploy configurado, executa deploy."""


@deploy.command("list")
def deploy_list():
    """Lista projetos que têm deploy configurado."""
    try:
        from fork_sync.core.registry import list_projects
        projects = list_projects()
        with_deploy = []
        for p in projects:
            name = p.get("name") or p.get("project", "?")
            has = p.get("has_deploy", False)
            if has:
                with_deploy.append(name)
        if with_deploy:
            click.echo(f"{len(with_deploy)} projeto(s) com deploy configurado:")
            for name in with_deploy:
                click.echo(f"  - {name}")
        else:
            click.echo("Nenhum projeto com deploy configurado.")
    except ImportError:
        click.echo("fork-sync lib não encontrada. pip install -e modules/fork-sync/cli/")


@deploy.command()
@click.argument("name")
@click.option("--dry-run", is_flag=True, help="Simula deploy sem executar.")
@click.option("--repo-path", default=None, help="Caminho do repo (override).")
def run(name, dry_run, repo_path):
    """Executa deploy de um projeto (wrapping fork-sync deploy)."""
    try:
        from fork_sync.cli import deploy_cmd
        from click.testing import CliRunner
        runner = CliRunner()
        args = [name]
        if dry_run:
            args.append("--dry-run")
        if repo_path:
            args.extend(["--repo-path", repo_path])
        result = runner.invoke(deploy_cmd, args)
        if result.exit_code != 0:
            click.echo(f"Deploy falhou: {result.output}", err=True)
            sys.exit(result.exit_code)
        click.echo(result.output)
    except ImportError:
        click.echo("fork-sync lib não encontrada. pip install -e modules/fork-sync/cli/")


# ═══════════════════════════════════════════════════════════════
# backup subcommand
# ═══════════════════════════════════════════════════════════════

BACKUP_DIR = Path(os.environ.get("OMNI_BACKUP_DIR", Path.home() / "backups"))


@cli.group()
def backup():
    """Backup/restore de dados e configurações do servidor."""


@backup.command("list")
@click.option("--json", "use_json", is_flag=True, help="Saída JSON.")
def backup_list(use_json):
    """Lista backups disponíveis no diretório de backup."""
    if not BACKUP_DIR.exists():
        click.echo("Nenhum diretório de backup encontrado.")
        return

    backups = sorted(BACKUP_DIR.glob("*.tar.gz"), reverse=True)
    if not backups:
        click.echo("Nenhum backup encontrado.")
        return

    entries = []
    for b in backups:
        size_mb = b.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        entries.append({"name": b.name, "size_mb": round(size_mb, 2), "date": mtime})

    if use_json:
        click.echo(json.dumps(entries, indent=2))
    else:
        click.echo(f"{len(entries)} backup(s) em {BACKUP_DIR}:")
        for e in entries:
            click.echo(f"  {e['date']}  {e['size_mb']:>7.2f}MB  {e['name']}")


@backup.command("create")
@click.argument("path", type=click.Path(exists=True))
@click.option("--name", default=None, help="Nome do backup (default: basename do path).")
@click.option("--exclude", multiple=True, help="Padrão a excluir (pode repetir).")
def backup_create(path, name, exclude):
    """Cria backup tar.gz de um diretório ou arquivo."""
    path_obj = Path(path).resolve()
    if not name:
        name = path_obj.name

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{name}-{timestamp}.tar.gz"
    backup_path = BACKUP_DIR / backup_name

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    click.echo(f"Criando backup de {path_obj}...")
    click.echo(f"Destino: {backup_path}")

    try:
        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(path_obj, arcname=path_obj.name, filter=None)
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        click.echo(f"Backup criado: {backup_name} ({size_mb:.2f}MB)")
    except PermissionError:
        click.echo("[WARN] Acessos negados em alguns arquivos. Tentando com filter...", err=True)
        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(path_obj, arcname=path_obj.name)
            size_mb = backup_path.stat().st_size / (1024 * 1024)
            click.echo(f"Backup criado: {backup_name} ({size_mb:.2f}MB)")
        except Exception as e2:
            click.echo(f"[ERROR] Falha ao criar backup: {e2}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"[ERROR] Falha ao criar backup: {e}", err=True)


@backup.command("restore")
@click.argument("backup_file", type=click.Path(exists=True))
@click.option("--dest", default=None, help="Diretório destino (default: atual).")
@click.option("--yes", is_flag=True, help="Pular confirmação.")
def backup_restore(backup_file, dest, yes):
    """Restaura um backup tar.gz."""
    backup_path = Path(backup_file).resolve()
    dest_path = Path(dest).resolve() if dest else Path.cwd()

    if not yes:
        click.confirm(f"Restaurar {backup_path.name} em {dest_path}?", abort=True)

    click.echo(f"Restaurando {backup_path.name}...")
    try:
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(path=dest_path)
        click.echo(f"✅ Restaurado em {dest_path}")
    except Exception as e:
        click.echo(f"[ERROR] Falha ao restaurar: {e}", err=True)
        sys.exit(1)


@backup.command("status")
def backup_status():
    """Status do diretório de backups: tamanho total, contagem, último."""
    if not BACKUP_DIR.exists():
        click.echo("Nenhum diretório de backup encontrado.")
        return

    backups = sorted(BACKUP_DIR.glob("*.tar.gz"), reverse=True)
    total_size = sum(b.stat().st_size for b in BACKUP_DIR.rglob("*"))
    total_size_mb = total_size / (1024 * 1024)

    click.echo(f"Dir:     {BACKUP_DIR}")
    click.echo(f"Total:   {total_size_mb:.1f}MB em {len(backups)} backup(s)")

    if backups:
        latest = backups[0]
        size_mb = latest.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        click.echo(f"Último:  {latest.name} ({size_mb:.2f}MB, {mtime})")


# ═══════════════════════════════════════════════════════════════
# version
# ═══════════════════════════════════════════════════════════════

@cli.command("version")
def version_cmd():
    """Mostra versão do omni CLI."""
    click.echo(f"omni v{__version__}")


def main():
    cli()
