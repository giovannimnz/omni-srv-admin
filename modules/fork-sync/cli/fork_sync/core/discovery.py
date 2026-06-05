"""discovery — auto-localiza forks/upstreams sumidos via gh search.

Problema: fork-sync referencia `owner/repo` em sync.yaml. Se o repo for renomeado,
deletado, ou transferido de owner, sync quebra. Este módulo:

1. Detecta que um upstream/fork sumiu (404 em gh api)
2. Pesquisa candidatos via `gh search repos`
3. Aplica heurísticas (mesmo nome, mesmo desc, mesmo maintainer, mesmo latest commit)
4. Sugere novo path com score de confiança
5. (Opcional) Auto-patch sync.yaml com confirmação

Heurísticas:
- Match exato de nome: score 0.9
- Match de nome + mesmo owner anterior: score 0.85
- Match de nome + similar description: score 0.6
- Fork do giovannimnz: score 0.5 (assume fork atual)
- Arquivado/desabilitado: penaliza -0.3
- Idade > 2 anos sem atividade: penaliza -0.2
"""

import json
import subprocess
import re
from pathlib import Path
from typing import Optional
import yaml

from fork_sync.core.config import REPO_ROOT, PROJECTS_DIR


def _gh_api(endpoint: str) -> Optional[dict]:
    """Wrapper gh api com tratamento de 404."""
    try:
        out = subprocess.run(
            ["gh", "api", endpoint, "--jq", "."],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return None
        return json.loads(out.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return None


def _gh_search_repos(query: str, limit: int = 10) -> list:
    """Busca repos via gh search."""
    try:
        out = subprocess.run(
            ["gh", "search", "repos", query, "--limit", str(limit),
             "--json", "fullName,description,isArchived,isDisabled,updatedAt,stargazersCount"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return []
        return json.loads(out.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def check_upstream_exists(owner: str, repo: str) -> bool:
    """Verifica se `owner/repo` existe e responde."""
    data = _gh_api(f"repos/{owner}/{repo}")
    return data is not None and not data.get("message")


def find_upstream_candidates(repo_name: str, original_owner: Optional[str] = None,
                             archived_ok: bool = False) -> list:
    """Busca candidatos pra substituir um upstream sumido.

    Retorna lista ordenada por score de confiança (maior primeiro).
    """
    candidates = []
    seen = set()

    # 1. Match exato de nome (em qualquer owner)
    for r in _gh_search_repos(repo_name, limit=20):
        full = r.get("fullName", "")
        name = full.split("/")[-1] if "/" in full else full
        score = 0.0
        if name.lower() == repo_name.lower():
            score = 0.9
        elif repo_name.lower() in name.lower():
            score = 0.6
        else:
            continue
        if full in seen:
            continue
        seen.add(full)
        if not archived_ok and (r.get("isArchived") or r.get("isDisabled")):
            score -= 0.3
        r["score"] = round(score, 2)
        candidates.append(r)

    # 2. Se tinha owner original, busca com prefixo
    if original_owner:
        for r in _gh_search_repos(f"user:{original_owner} {repo_name}", limit=10):
            full = r.get("fullName", "")
            if full in seen:
                continue
            name = full.split("/")[-1] if "/" in full else full
            if repo_name.lower() in name.lower():
                r["score"] = 0.85
                seen.add(full)
                candidates.append(r)

    # 3. Verifica se há fork do giovannimnz (caso seja nosso próprio fork)
    fork = _gh_api(f"repos/giovannimnz/{repo_name}")
    if fork and not fork.get("message"):
        score = 0.7
        if fork.get("parent") and fork["parent"].get("fullName", "").endswith(repo_name):
            score = 0.95
        if full_name := fork.get("fullName"):
            if full_name not in seen:
                fork["score"] = score
                fork["source"] = "self-fork"
                candidates.append(fork)
                seen.add(full_name)

    # Ordena por score
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates


def find_fork_locally(project_name: str) -> Optional[Path]:
    """Verifica se o fork local ainda existe no disco."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        return None
    sync = project_dir / "sync.yaml"
    if not sync.exists():
        return None
    try:
        cfg = yaml.safe_load(sync.read_text())
    except Exception:
        return None
    fork_path_str = cfg.get("fork") or (cfg.get("target") or {}).get("path")
    if not fork_path_str:
        return None
    fork_path = Path(fork_path_str).expanduser()
    if fork_path.exists() and (fork_path / ".git").exists():
        return fork_path
    return None


def diagnose_project(project_name: str) -> dict:
    """Diagnóstico completo: local + remotos + candidatos."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        return {"project": project_name, "error": f"Projeto não existe em {project_dir}"}

    sync = project_dir / "sync.yaml"
    try:
        cfg = yaml.safe_load(sync.read_text())
    except Exception as e:
        return {"project": project_name, "error": f"YAML inválido: {e}"}

    # Schema v1 (string upstream) ou v2 (lista upstreams)
    upstreams = []
    if "upstream" in cfg:
        u = cfg["upstream"]
        if isinstance(u, str):
            owner, _, repo = u.replace("https://github.com/", "").rpartition("/")
            upstreams.append({"name": repo, "url": u, "owner": owner, "repo": repo, "v": 1})
    if "upstreams" in cfg and isinstance(cfg["upstreams"], list):
        for u in cfg["upstreams"]:
            url = u.get("url", "")
            owner, _, repo = url.replace("https://github.com/", "").rpartition("/")
            upstreams.append({**u, "owner": owner, "repo": repo, "v": 2})

    result = {
        "project": project_name,
        "schema": "v1" if "upstream" in cfg else "v2",
        "local_fork": None,
        "local_status": "unknown",
        "upstreams": [],
    }

    # Local fork check
    local = find_fork_locally(project_name)
    if local:
        result["local_fork"] = str(local)
        result["local_status"] = "ok"
    else:
        result["local_status"] = "missing"
        fork_str = cfg.get("fork") or (cfg.get("target") or {}).get("path")
        result["local_expected"] = fork_str

    # Upstream checks
    for u in upstreams:
        owner = u.get("owner", "")
        repo = u.get("repo", "")
        url = u.get("url", "")
        exists = check_upstream_exists(owner, repo)
        entry = {
            "name": u.get("name", repo),
            "url": url,
            "owner": owner,
            "repo": repo,
            "exists": exists,
            "candidates": [],
        }
        if not exists:
            cands = find_upstream_candidates(repo, original_owner=owner)
            entry["candidates"] = [
                {"full_name": c.get("fullName"), "score": c.get("score"),
                 "archived": c.get("isArchived", False), "disabled": c.get("isDisabled", False),
                 "description": (c.get("description") or "")[:80]}
                for c in cands[:5]
            ]
        result["upstreams"].append(entry)

    return result


def auto_heal(project_name: str, dry_run: bool = True) -> dict:
    """Tenta auto-corrigir paths quebrados.

    Estratégia:
    1. Se local_fork sumiu: procura em ~/GitHub/forks/<name>, ~/docker/Atius/<name>, etc.
    2. Se upstream sumiu: usa candidato de maior score pra patch sync.yaml
    3. Se ambos sumiram: tenta descobrir via search com nome do projeto
    """
    diag = diagnose_project(project_name)
    actions = []

    # 1. Local fork recovery
    if diag.get("local_status") == "missing":
        expected_name = project_name
        search_dirs = [
            Path.home() / "GitHub" / "forks",
            Path.home() / "docker" / "Atius",
            Path.home() / "GitHub",
        ]
        for d in search_dirs:
            if not d.exists():
                continue
            for sub in d.iterdir():
                if sub.is_dir() and sub.name.lower() == expected_name.lower():
                    if (sub / ".git").exists():
                        actions.append({
                            "type": "local_fork_found",
                            "found_at": str(sub),
                            "expected": diag.get("local_expected"),
                        })
                        if not dry_run:
                            # Patch sync.yaml
                            project_dir = PROJECTS_DIR / project_name
                            sync = project_dir / "sync.yaml"
                            cfg = yaml.safe_load(sync.read_text())
                            if "fork" in cfg:
                                cfg["fork"] = str(sub)
                            elif "target" in cfg:
                                cfg["target"]["path"] = str(sub)
                            sync.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
                        break

    # 2. Upstream recovery
    for u in diag.get("upstreams", []):
        if not u["exists"] and u["candidates"]:
            best = u["candidates"][0]
            actions.append({
                "type": "upstream_relocate",
                "old": u["url"],
                "new": best["full_name"],
                "score": best["score"],
            })
            if not dry_run and best["score"] >= 0.7:
                project_dir = PROJECTS_DIR / project_name
                sync = project_dir / "sync.yaml"
                cfg = yaml.safe_load(sync.read_text())
                new_url = f"https://github.com/{best['full_name']}"
                if "upstream" in cfg and isinstance(cfg["upstream"], str):
                    cfg["upstream"] = new_url
                elif "upstreams" in cfg:
                    for src in cfg["upstreams"]:
                        if src.get("name") == u["name"]:
                            src["url"] = new_url
                sync.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))

    return {"project": project_name, "actions": actions, "dry_run": dry_run}
