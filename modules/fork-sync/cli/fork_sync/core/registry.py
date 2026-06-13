"""registry — listagem e carregamento de projetos (forks)."""

from pathlib import Path
import yaml

from fork_sync.core.config import PROJECTS_DIR


def _project_enabled(data: dict) -> bool:
    """Return False for configs explicitly paused/disabled."""
    if str(data.get("enabled", True)).lower() == "false":
        return False
    if str(data.get("paused", False)).lower() == "true":
        return False
    return True


def list_projects(only_enabled: bool = False) -> list:
    """Lista todos os projetos com sync.yaml."""
    if not PROJECTS_DIR.exists():
        return []
    items = []
    for p in sorted(PROJECTS_DIR.iterdir()):
        if not p.is_dir():
            continue
        sync = p / "sync.yaml"
        if not sync.exists():
            continue
        try:
            data = yaml.safe_load(sync.read_text())
        except Exception as e:
            items.append({"name": p.name, "error": f"YAML parse failed: {e}"})
            continue
        if only_enabled and not _project_enabled(data):
            continue
        deploy = p / "deploy.yaml"
        data["name"] = p.name
        data["path"] = str(p)
        data["enabled"] = _project_enabled(data)
        data["has_deploy"] = deploy.exists()
        data["submodules"] = list(_detect_submodules(p))
        items.append(data)
    return items


def _detect_submodules(project_dir: Path) -> list:
    """Detecta se há .gitmodules ao lado do sync.yaml (submódulo opcional)."""
    gitmodules = project_dir / ".gitmodules"
    if not gitmodules.exists():
        return []
    out = []
    cur = {}
    for line in gitmodules.read_text().splitlines():
        if line.strip().startswith("[submodule"):
            if cur:
                out.append(cur)
            cur = {}
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            cur[k.strip()] = v.strip()
    if cur:
        out.append(cur)
    return out


def load_project(name: str) -> dict:
    """Carrega sync.yaml + deploy.yaml (se existir) de um projeto."""
    p = PROJECTS_DIR / name
    sync = p / "sync.yaml"
    if not sync.exists():
        raise FileNotFoundError(f"sync.yaml não encontrado em {p}")
    data = yaml.safe_load(sync.read_text())
    data["name"] = name
    data["path"] = str(p)
    deploy = p / "deploy.yaml"
    if deploy.exists():
        data["deploy"] = yaml.safe_load(deploy.read_text())
    return data


def project_exists(name: str) -> bool:
    return (PROJECTS_DIR / name / "sync.yaml").exists()
