"""sync_runner — executa sync/deploy/detect delegando aos scripts bash legados.

Estratégia: o motor Python NÃO substitui o sync.sh. Ele delega, captura stdout/stderr
e converte em resultado estruturado. Benefícios:
- Backward compat 100%: scripts bash continuam funcionando com `bin/sync.sh foo bar`
- Python adiciona: --json, --dry-run cross-cutting, exit codes estruturados
- Um dia, podemos portar a lógica pra Python puro sem quebrar users
"""

import subprocess
import os
from pathlib import Path
from typing import Optional

from fork_sync.core.config import SYNC_SH, DEPLOY_SH, DETECT_SH, REPO_ROOT
from fork_sync.core.registry import load_project, project_exists


def _run_script(script: Path, args: list, cwd: Optional[Path] = None) -> dict:
    """Roda um script bash e captura resultado estruturado."""
    if not script.exists():
        return {
            "status": "error",
            "error": f"script não encontrado: {script}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }
    cmd = ["bash", str(script)] + args
    env = os.environ.copy()
    env.setdefault("FORK_SYNC_ROOT", str(REPO_ROOT))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(cwd) if cwd else str(REPO_ROOT),
            env=env, timeout=600,
        )
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": f"timeout após 600s", "command": " ".join(cmd)}
    except Exception as e:
        return {"status": "error", "error": str(e), "command": " ".join(cmd)}


def run_detect(name: str) -> dict:
    """Detecta novo release."""
    cfg = load_project(name)
    out = _run_script(DETECT_SH, [name, cfg.get("fork", "")])
    # Parse NEW_RELEASE= e VERSION= do stdout
    new_release = False
    version = None
    for line in out.get("stdout", "").splitlines():
        if line.startswith("NEW_RELEASE="):
            new_release = line.split("=", 1)[1].strip().lower() == "true"
        elif line.startswith("VERSION="):
            version = line.split("=", 1)[1].strip()
    out["new_release"] = new_release
    out["version"] = version
    return out


def run_sync(name: str, repo_path: Optional[str] = None,
             dry_run: bool = False, deploy: bool = False) -> dict:
    """Sincroniza fork com upstream."""
    if not project_exists(name):
        raise FileNotFoundError(f"Projeto '{name}' não existe")
    cfg = load_project(name)
    args = [name]
    if repo_path:
        args.append(repo_path)
    elif cfg.get("fork"):
        args.append(cfg["fork"])
    if dry_run:
        args.append("--dry-run")
    if deploy:
        args.append("--deploy")
    return _run_script(SYNC_SH, args)


def run_deploy(name: str, repo_path: Optional[str] = None, dry_run: bool = False) -> dict:
    """Deploy Docker (requer deploy.yaml)."""
    cfg = load_project(name)
    if "deploy" not in cfg and not (Path(cfg.get("path", "")) / "deploy.yaml").exists():
        raise FileNotFoundError(f"Projeto '{name}' não tem deploy.yaml")
    args = [name]
    if repo_path:
        args.append(repo_path)
    elif cfg.get("fork"):
        args.append(cfg["fork"])
    if dry_run:
        args.append("--dry-run")
    return _run_script(DEPLOY_SH, args)
