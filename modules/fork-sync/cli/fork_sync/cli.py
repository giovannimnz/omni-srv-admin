"""CLI principal do fork-sync.

Comandos:
    projects list|show|add|remove
    sync <project> [--dry-run] [--deploy]
    deploy <project>
    detect <project>
    logs [--project NAME] [--tail N]
    repl               # modo interativo (REPL)
    version
"""

import sys
import json
import shlex
import subprocess
from pathlib import Path

import click

from fork_sync import __version__
from fork_sync.core.config import REPO_ROOT, PROJECTS_DIR
from fork_sync.core.db_registry import registry_rows_for_project
from fork_sync.core.registry import list_projects, load_project, project_exists
from fork_sync.core.sync_runner import run_sync, run_detect, run_deploy
from fork_sync.core.automerge import run_sync_all
from fork_sync.core.container_mirrors import diagnose_container_mirrors
from fork_sync.core.discovery import diagnose_project, auto_heal
from fork_sync.core.manuals import (generate_manual, manual_exists, get_manual_path,
                                    record_sync, list_manuals, update_manual_section)
from fork_sync.core.logrotate import rotate_all, check_disk_usage
from fork_sync.core.release_notes import (generate_release_notes, save_local as save_local_md,
                                          list_local_releases)


_json_output = False
_repl_mode = False


def output(data, message: str = ""):
    """Saída com fallback humano/JSON."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        else:
            click.echo(str(data))


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, (dict, list)) and v:
            click.echo(f"{prefix}{k}:")
            if isinstance(v, dict):
                _print_dict(v, indent + 1)
            else:
                _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0):
    prefix = "  " * indent
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    """Decorator: converte exceções em output JSON/texto estruturado."""
    def wrapper(*args, **kwargs):
        global _json_output
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "not_found"}))
            else:
                click.echo(f"[ERROR] Arquivo não encontrado: {e}", err=True)
            sys.exit(2)
        except RuntimeError as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "runtime_error"}))
            else:
                click.echo(f"[ERROR] {e}", err=True)
            sys.exit(1)
        except click.ClickException:
            raise
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"[FATAL] {type(e).__name__}: {e}", err=True)
            sys.exit(1)
    return wrapper


# ─────────────────────────── grupos de comando ───────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Saída em JSON (machine-readable).")
@click.option("--repo-root", type=click.Path(exists=True), default=None,
              help=f"Raiz do repo fork-sync (default: {REPO_ROOT}).")
@click.pass_context
def cli(ctx, use_json, repo_root):
    """fork-sync — gestão unificada de forks (sync, deploy, versionamento)."""
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["repo_root"] = Path(repo_root).resolve() if repo_root else REPO_ROOT
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ─────────────────────────── projects ───────────────────────────

@cli.group()
def projects():
    """Gerencia projetos (forks) configurados."""


@projects.command("list")
@click.option("--enabled-only", is_flag=True, help="Mostra só projetos ativos.")
@click.option("--db-host", "db_hosts", multiple=True, help="Enriquece com placements do DbOmniFleet para os hosts informados.")
@handle_error
def projects_list(enabled_only, db_hosts):
    """Lista todos os forks configurados."""
    items = list_projects(only_enabled=enabled_only)
    if db_hosts:
        for item in items:
            item["db_registry"] = registry_rows_for_project(item["name"], list(db_hosts))
    output(items, f"{len(items)} projeto(s) configurado(s):")


@projects.command("show")
@click.argument("name")
@click.option("--db-host", "db_hosts", multiple=True, help="Enriquece com placements do DbOmniFleet para os hosts informados.")
@handle_error
def projects_show(name, db_hosts):
    """Mostra detalhes de um projeto (sync.yaml + deploy.yaml se existir)."""
    if not project_exists(name):
        raise FileNotFoundError(f"Projeto '{name}' não encontrado em {PROJECTS_DIR}")
    cfg = load_project(name)
    if db_hosts:
        cfg["db_registry"] = registry_rows_for_project(name, list(db_hosts))
    output(cfg, f"Projeto: {name}")


@projects.command("add")
@click.argument("name")
@click.option("--upstream", required=True, help="URL do upstream (ex: https://github.com/owner/repo).")
@click.option("--fork", "fork_path", required=True, help="Caminho local do fork (ex: ~/GitHub/forks/AionUi).")
@click.option("--branch", default="main", help="Branch alvo (default: main).")
@click.option("--protected-paths", multiple=True, help="Paths protegidos (pode repetir).")
@click.option("--merge-strategy", type=click.Choice(["merge", "ours", "theirs"]), default="merge")
@handle_error
def projects_add(name, upstream, fork_path, branch, protected_paths, merge_strategy):
    """Cria um novo projeto com sync.yaml."""
    project_dir = PROJECTS_DIR / name
    if project_dir.exists():
        raise FileNotFoundError(f"Projeto '{name}' já existe em {project_dir}")
    project_dir.mkdir(parents=True)
    cfg = {
        "project": name,
        "upstream": upstream,
        "upstream_branch": branch,
        "origin_branch": branch,
        "protected_paths": list(protected_paths),
        "merge_strategy": merge_strategy,
        "auto_push": True,
        "notification_level": "all",
        "ai_decision_threshold": "conflicts",
    }
    import yaml
    (project_dir / "sync.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    output(cfg, f"Projeto '{name}' criado em {project_dir}")


@projects.command("remove")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Pula confirmação.")
@handle_error
def projects_remove(name, yes):
    """Remove projeto (deleta diretório projects/<name>/)."""
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        raise FileNotFoundError(f"Projeto '{name}' não encontrado")
    if not yes:
        click.confirm(f"Remover {project_dir}?", abort=True)
    import shutil
    shutil.rmtree(project_dir)
    click.echo(f"Projeto '{name}' removido.")


# ─────────────────────────── sync / detect / deploy ───────────────────────────

@cli.command("sync")
@click.argument("name")
@click.option("--repo-path", default=None, help="Caminho do repo local (override do fork: em sync.yaml).")
@click.option("--dry-run", is_flag=True, help="Simula sem merge/deploy.")
@click.option("--deploy", "with_deploy", is_flag=True, help="Executa deploy após sync.")
@click.option("--json", "use_json", is_flag=True, help="Saída JSON.")
@handle_error
def sync_cmd(name, repo_path, dry_run, with_deploy, use_json):
    """Sincroniza um fork com seu upstream (merge + protected paths + version)."""
    if not project_exists(name):
        raise FileNotFoundError(f"Projeto '{name}' não configurado. Use: fork-sync projects add")
    result = run_sync(name, repo_path=repo_path, dry_run=dry_run, deploy=with_deploy)
    output(result, f"Sync '{name}': {result.get('status', 'unknown')}")


@cli.command("sync-all")
@click.option("--apply", is_flag=True, help="Aplica somente projetos cujo dry-run seja seguro.")
@click.option("--include-paused", is_flag=True, help="Inclui projetos pausados no relatório.")
@handle_error
def sync_all_cmd(apply, include_paused):
    """Dry-run de todos os projetos ativos, com automerge seguro opcional."""
    result = run_sync_all(apply=apply, include_paused=include_paused)
    output(result, f"Sync-all: {result['mode']} ({result['project_count']} projeto(s))")


@cli.command("detect")
@click.argument("name")
@handle_error
def detect_cmd(name):
    """Detecta novo release no upstream do projeto."""
    if not project_exists(name):
        raise FileNotFoundError(f"Projeto '{name}' não configurado")
    result = run_detect(name)
    output(result, f"Detect '{name}': release={'sim' if result.get('new_release') else 'não'}")


@cli.command("deploy")
@click.argument("name")
@click.option("--repo-path", default=None)
@click.option("--dry-run", is_flag=True)
@handle_error
def deploy_cmd(name, repo_path, dry_run):
    """Deploy Docker (buildx + push + restart) — só funciona se deploy.yaml existir."""
    if not project_exists(name):
        raise FileNotFoundError(f"Projeto '{name}' não configurado")
    result = run_deploy(name, repo_path=repo_path, dry_run=dry_run)
    output(result, f"Deploy '{name}': {result.get('status', 'unknown')}")


@cli.group("containers")
def containers():
    """Diagnostica mirrors de containers migrados."""


@containers.command("mirrors")
@handle_error
def containers_mirrors():
    """Lista container_mirror e detecta .git copiado/quebrado."""
    result = diagnose_container_mirrors()
    output(result, f"Container mirrors: {result['mirror_count']} encontrado(s)")


# ─────────────────────────── logs ───────────────────────────

# (logs_cmd definido mais abaixo com suporte a --rotate/--disk)


# ─────────────────────────── version / repl ───────────────────────────

@cli.command("version")
def version_cmd():
    """Mostra versão do fork-sync."""
    output({"version": __version__, "repo_root": str(REPO_ROOT)})


# ─────────────────────────── release (release notes PT-BR) ───────────────────────────

@cli.group()
def release():
    """Gera release notes em PT-BR a partir do upstream."""


def _fork_repo_slug(cfg: dict, name: str) -> str:
    """Resolve o slug do repo do fork.

    Ordem:
    1) cfg.fork_repo (se existir)
    2) basename de cfg.fork (path local do repo)
    3) basename de cfg.target.path (schema v2)
    4) fallback: name
    """
    if cfg.get("fork_repo"):
        return cfg["fork_repo"]
    fork_path = cfg.get("fork")
    if fork_path:
        from pathlib import Path
        return Path(fork_path).name
    target_path = (cfg.get("target") or {}).get("path")
    if target_path:
        from pathlib import Path
        return Path(target_path).name
    return name


@release.command("generate")
@click.argument("name")
@click.option("--upstream-version", required=True, help="Versão upstream (ex: 2.1.10).")
@click.option("--fork-tag", default=None, help="Tag do fork (default: v{upstream_version}-rf{N}).")
@click.option("--rf", "rf_counter", default=1, help="Número do rf counter (default: 1).")
@click.option("--changed-files", multiple=True, help="Arquivos alterados pelo fork (pode repetir).")
@click.option("--no-translate", is_flag=True, help="Não traduzir (mantém inglês).")
@click.option("--save-local", is_flag=True, help="Salvar em manuals/<name>/releases/<tag>.md.")
@handle_error
def release_generate(name, upstream_version, fork_tag, rf_counter, changed_files, no_translate, save_local):
    """Gera release notes em PT-BR pra um projeto."""
    if not project_exists(name):
        raise FileNotFoundError(f"Projeto '{name}' não existe")
    cfg = load_project(name)
    fork_slug = _fork_repo_slug(cfg, name)
    fork_url = f"https://github.com/giovannimnz/{fork_slug}"
    upstream_url = cfg.get("upstream") or (cfg.get("upstreams") or [{}])[0].get("url", "")
    if not upstream_url.startswith("http"):
        raise ValueError(f"upstream inválido em {name}: {upstream_url}")
    if not fork_tag:
        fork_tag = f"v{upstream_version}-rf{rf_counter}"

    result = generate_release_notes(
        project_name=name,
        upstream_version=upstream_version,
        fork_tag=fork_tag,
        upstream_url=upstream_url,
        fork_url=fork_url,
        changed_files=list(changed_files) if changed_files else None,
        translate=not no_translate,
    )

    output_summary = {
        "summary": result["summary"],
        "title": result["title"],
        "body_length": len(result["body"]),
        "fork_url": fork_url,
        "upstream_url": upstream_url,
    }
    output(output_summary, f"Release notes geradas: {result['title']} ({len(result['body'])} chars)")
    click.echo("\n" + "─" * 60)
    click.echo(result["body"])
    click.echo("─" * 60)

    if save_local:
        path = save_local_md(name, fork_tag, result["body"])
        click.echo(f"\n💾 Salvo em: {path}")


@release.command("update")
@click.argument("name")
@click.option("--tag", required=True, help="Tag do fork a atualizar (ex: v2.1.10-rf2).")
@click.option("--repo", default=None, help="Override do repo (default: giovannimnz/<name>).")
@click.option("--no-translate", is_flag=True)
@click.option("--dry-run", is_flag=True, help="Mostra o que faria, sem chamar gh.")
@handle_error
def release_update(name, tag, repo, no_translate, dry_run):
    """Atualiza uma release existente no GitHub com notas em PT-BR geradas.

    Use para sobrescrever releases antigas que tinham doc pobre (1 linha
    "Sync release based on upstream...") com a versão completa.
    """
    if not project_exists(name):
        raise FileNotFoundError(f"Projeto '{name}' não existe")
    cfg = load_project(name)
    fork_slug = _fork_repo_slug(cfg, name)
    fork_url = f"https://github.com/{repo}" if repo else f"https://github.com/giovannimnz/{fork_slug}"
    upstream_url = cfg.get("upstream") or (cfg.get("upstreams") or [{}])[0].get("url", "")
    # Extrair upstream version do tag (vX.Y.Z-rfN → X.Y.Z)
    import re as _re
    m = _re.match(r"^v?(\d+\.\d+\.\d+)", tag)
    if not m:
        raise ValueError(f"Não foi possível extrair versão de '{tag}'. Use formato vX.Y.Z[-rfN].")
    upstream_version = m.group(1)

    result = generate_release_notes(
        project_name=name,
        upstream_version=upstream_version,
        fork_tag=tag,
        upstream_url=upstream_url,
        fork_url=fork_url,
        changed_files=None,
        translate=not no_translate,
    )

    # Validar que a release existe
    out = subprocess.run(
        ["gh", "release", "view", tag, "--repo", fork_url.replace("https://github.com/", ""),
         "--json", "tagName,body"],
        capture_output=True, text=True
    )
    if out.returncode != 0:
        raise FileNotFoundError(
            f"Release '{tag}' não encontrada em {fork_url}.\n"
            f"Use `fork-sync release generate` pra criar nova, não update."
        )
    old_body_len = len(json.loads(out.stdout).get("body", ""))

    click.echo(f"📝 Release atual: {tag}")
    click.echo(f"   body atual: {old_body_len} chars")
    click.echo(f"   body novo:  {len(result['body'])} chars (PT-BR, {result['summary']['highlights_count']} destaques, {result['summary']['commits_count']} commits)")

    if dry_run:
        click.echo("\n[dry-run] Nada alterado. Remova --dry-run pra aplicar.")
        return

    # Salvar body em arquivo temporário e usar gh release edit
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(result["body"])
        body_path = f.name
    try:
        out2 = subprocess.run(
            ["gh", "release", "edit", tag,
             "--repo", fork_url.replace("https://github.com/", ""),
             "--notes-file", body_path],
            capture_output=True, text=True
        )
        if out2.returncode != 0:
            raise RuntimeError(f"gh release edit falhou: {out2.stderr.strip()}")
        click.echo(f"\n✅ Release atualizada: {fork_url}/releases/tag/{tag}")
        click.echo(f"   {old_body_len} → {len(result['body'])} chars (+{len(result['body']) - old_body_len})")
    finally:
        Path(body_path).unlink()


@release.command("list")
@click.argument("name")
@handle_error
def release_list(name):
    """Lista release notes geradas localmente pra um projeto."""
    items = list_local_releases(name)
    output(items, f"{len(items)} release(s) salva(s) localmente para '{name}'")


@release.command("preview")
@click.argument("name")
@click.option("--upstream-version", required=True)
@click.option("--no-translate", is_flag=True)
@handle_error
def release_preview(name, upstream_version, no_translate):
    """Atalho: gera release notes com defaults e mostra (sem salvar)."""
    if not project_exists(name):
        raise FileNotFoundError(f"Projeto '{name}' não existe")
    cfg = load_project(name)
    fork_slug = _fork_repo_slug(cfg, name)
    fork_url = f"https://github.com/giovannimnz/{fork_slug}"
    upstream_url = cfg.get("upstream") or (cfg.get("upstreams") or [{}])[0].get("url", "")
    fork_tag = f"v{upstream_version}-rf1"

    result = generate_release_notes(
        project_name=name,
        upstream_version=upstream_version,
        fork_tag=fork_tag,
        upstream_url=upstream_url,
        fork_url=fork_url,
        changed_files=None,
        translate=not no_translate,
    )
    click.echo(result["body"])


# ─────────────────────────── doctor (diagnóstico geral) ───────────────────────────

@cli.command("doctor")
@click.option("--project", default=None, help="Foca em 1 projeto. Sem flag: diagnóstico global.")
@handle_error
def doctor_cmd(project):
    """Diagnóstico geral: paths, configs, secrets policy, dependências.

    Sem --project: varre todos os projetos (local + remotos + candidatos).
    Com --project: foco em 1 projeto, incluindo auto-heal sugestões.
    """
    import shutil
    issues = []
    info = {
        "repo_root": str(REPO_ROOT),
        "projects_dir": str(PROJECTS_DIR),
        "logs_dir": str(REPO_ROOT / "logs"),
        "manuals_dir": str(REPO_ROOT / "manuals"),
    }
    # Dependências
    for cmd in ["git", "gh", "jq", "bash"]:
        path = shutil.which(cmd)
        info[f"dep_{cmd}"] = path or "❌ MISSING"
        if not path:
            issues.append(f"Dependência '{cmd}' não encontrada no PATH")
    # gh auth
    out = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    info["gh_auth"] = "ok" if out.returncode == 0 else f"❌ {out.stderr.strip()[:60]}"
    if out.returncode != 0:
        issues.append("gh CLI não autenticado")
    # PM2
    pm2 = shutil.which("pm2")
    info["pm2"] = pm2 or "(não instalado — opcional)"
    # Disco de logs
    usage = check_disk_usage()
    info["logs"] = usage
    if usage["total_size_mb"] > 500:
        issues.append(f"Logs ocupando {usage['total_size_mb']}MB — rode `fork-sync logs --rotate`")

    # Diagnóstico de projeto
    project_reports = []
    if project:
        if not project_exists(project):
            issues.append(f"Projeto '{project}' não existe")
        else:
            d = diagnose_project(project)
            project_reports.append(d)
            if d.get("local_status") == "missing":
                issues.append(f"[{project}] fork local sumiu — rode `fork-sync discover {project} --heal`")
            for u in d.get("upstreams", []):
                if not u["exists"]:
                    issues.append(f"[{project}] upstream {u['url']} sumiu — {len(u['candidates'])} candidatos")
    else:
        for p in list_projects(only_enabled=True):
            name = p.get("name")
            d = diagnose_project(name)
            if d.get("local_status") == "missing" or any(not u["exists"] for u in d.get("upstreams", [])):
                project_reports.append(d)
                if d.get("local_status") == "missing":
                    issues.append(f"[{name}] fork local sumiu")
                for u in d.get("upstreams", []):
                    if not u["exists"]:
                        issues.append(f"[{name}] upstream {u['url']} sumiu")

    result = {
        "info": info,
        "issues": issues,
        "project_reports": project_reports,
    }
    summary = f"{len(issues)} issue(s)" if issues else "✅ tudo ok"
    output(result, summary)


# ─────────────────────────── discover (auto-find sumidos) ───────────────────────────

@cli.group()
def discover():
    """Auto-localiza forks/upstreams sumidos via gh search."""


@discover.command("check")
@click.argument("name")
@handle_error
def discover_check(name):
    """Diagnostica 1 projeto: local existe? upstreams respondem? candidatos?"""
    result = diagnose_project(name)
    output(result, f"Diagnóstico '{name}': ver campos local_status e upstreams[].exists")


@discover.command("heal")
@click.argument("name")
@click.option("--apply", is_flag=True, help="Aplica patches (default: dry-run).")
@handle_error
def discover_heal(name, apply):
    """Tenta auto-recuperar fork/upstream sumido. Sem --apply é dry-run."""
    result = auto_heal(name, dry_run=not apply)
    output(result, f"Heal '{name}': {len(result['actions'])} ação(ões)")


# ─────────────────────────── manuals (docs versionadas) ───────────────────────────

@cli.group()
def manuals():
    """Gerencia manuais de atualização por projeto."""


@manuals.command("list")
@handle_error
def manuals_list():
    """Lista todos os manuais com metadados (versão, tamanho, paths)."""
    items = list_manuals()
    output(items, f"{len(items)} manual(is)")


@manuals.command("generate")
@click.argument("name")
@click.option("--regenerate", is_flag=True, help="Sobrescreve manual existente.")
@handle_error
def manuals_generate(name, regenerate):
    """Gera manual inicial (esqueleto) a partir do sync.yaml."""
    result = generate_manual(name, regenerate=regenerate)
    output(result, f"Manual '{name}': {result['status']} → {result['path']}")


@manuals.command("show")
@click.argument("name")
@handle_error
def manuals_show(name):
    """Mostra manual de um projeto (path absoluto)."""
    path = get_manual_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Manual '{name}' não existe. Rode: fork-sync manuals generate {name}")
    click.echo(f"# {path}\n")
    click.echo(path.read_text())


@manuals.command("update")
@click.argument("name")
@click.argument("section")
@click.argument("content")
@handle_error
def manuals_update(name, section, content):
    """Adiciona conteúdo a uma seção do manual."""
    result = update_manual_section(name, section, content)
    output(result, f"Manual '{name}' atualizado")


@manuals.command("record-sync")
@click.argument("name")
@click.option("--status", required=True, help="success | needs_review | failed")
@click.option("--version", default="", help="Versão sincronizada (ex: v2.1.11)")
@click.option("--notes", default="", help="Notas adicionais")
@handle_error
def manuals_record(name, status, version, notes):
    """Registra um sync no histórico do manual."""
    result = record_sync(name, status, version, notes)
    output(result, "Sync registrado no manual")


# ─────────────────────────── logs (rotate / disk) ───────────────────────────

@cli.command("logs")
@click.option("--project", "project", default=None, help="Filtra por projeto.")
@click.option("--tail", default=20, help="Últimas N linhas (default: 20).")
@click.option("--date", default=None, help="Data específica (YYYYMMDD).")
@click.option("--rotate", is_flag=True, help="Rotaciona logs (comprime antigos + limpa velhos).")
@click.option("--apply", is_flag=True, help="Aplica rotação (default: dry-run).")
@click.option("--disk", "show_disk", is_flag=True, help="Mostra uso de disco dos logs.")
@handle_error
def logs_cmd(project, tail, date, rotate, apply, show_disk):
    """Mostra logs OU rotaciona OU mostra uso de disco."""
    if rotate:
        result = rotate_all(dry_run=not apply)
        action = "applied" if apply else "dry-run"
        output(result, f"Rotação de logs ({action}): {len(result['compressed'])} comprimidos, {len(result['deleted'])} removidos")
        return
    if show_disk:
        usage = check_disk_usage()
        output(usage, f"Logs: {usage['total_files']} arquivos, {usage['total_size_mb']}MB")
        return

    # Default: tail do log mais recente
    from datetime import datetime
    log_dir = REPO_ROOT / "logs"
    if not log_dir.exists():
        click.echo("(nenhum log encontrado)")
        return
    pattern = f"sync-{project}-" if project else "sync-"
    files = sorted(log_dir.glob(f"{pattern}*.log*"), reverse=True)
    if date:
        files = [f for f in files if date in f.name]
    if not files:
        click.echo(f"(nenhum log {f'do projeto {project}' if project else ''})")
        return
    latest = files[0]
    # Se .gz, descompacta em memória
    if latest.suffix == ".gz":
        import gzip
        with gzip.open(latest, "rt", errors="replace") as f:
            lines = f.read().splitlines()[-tail:]
    else:
        lines = latest.read_text(errors="replace").splitlines()[-tail:]
    click.echo(f"# {latest.name}")
    click.echo("\n".join(lines))


@cli.command("repl")
@click.option("--api-key", default=None, envvar="FORK_SYNC_API_KEY",
              help="API key (placeholder, REPL local por enquanto).")
def repl_cmd(api_key):
    """Modo interativo (REPL) — padrão CLI-Anything."""
    global _repl_mode
    _repl_mode = True
    from fork_sync.core.repl import run_repl
    run_repl()


def main():
    """Entry point console_scripts."""
    cli()


if __name__ == "__main__":
    main()
