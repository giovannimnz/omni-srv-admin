"""manuals — geração e versionamento de manuais de atualização por projeto.

Cada projeto tem 1 manual em `manuals/<project>.md` que documenta:
- Estratégia de merge (passo-a-passo)
- Como adaptar rebrand (se aplicável)
- Como reagir a breaking changes do upstream
- Troubleshooting específico

Manuais são versionados no git junto com sync.yaml. Cada bump de versão do manual
fica no frontmatter. O CLI pode regenerar partes automaticamente baseado em:
- Histórico de sync (logs)
- Diff de mudanças no upstream
- Última versão conhecida
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from fork_sync.core.config import REPO_ROOT, PROJECTS_DIR


MANUALS_DIR = REPO_ROOT / "manuals"


def ensure_manuals_dir() -> Path:
    MANUALS_DIR.mkdir(parents=True, exist_ok=True)
    return MANUALS_DIR


def get_manual_path(project_name: str) -> Path:
    return MANUALS_DIR / f"{project_name}.md"


def manual_exists(project_name: str) -> bool:
    return get_manual_path(project_name).exists()


def generate_manual(project_name: str, regenerate: bool = False) -> dict:
    """Gera manual inicial a partir do sync.yaml + templates."""
    if manual_exists(project_name) and not regenerate:
        return {"status": "exists", "path": str(get_manual_path(project_name))}

    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        raise FileNotFoundError(f"Projeto '{project_name}' não existe")

    sync = project_dir / "sync.yaml"
    cfg = yaml.safe_load(sync.read_text()) if sync.exists() else {}

    upstreams = []
    if isinstance(cfg.get("upstream"), str):
        upstreams.append({"name": cfg.get("project", project_name), "url": cfg["upstream"]})
    elif isinstance(cfg.get("upstreams"), list):
        for u in cfg["upstreams"]:
            upstreams.append({"name": u.get("name", "?"), "url": u.get("url", "?"),
                              "role": u.get("role", "primary")})

    deploy = project_dir / "deploy.yaml"
    has_deploy = deploy.exists()

    today = datetime.now().strftime("%Y-%m-%d")
    manual_path = get_manual_path(project_name)
    ensure_manuals_dir()

    content = f"""---
project: {project_name}
version: 1
created: {today}
last_updated: {today}
generator: fork-sync manuals generate
---

# Manual de Atualização — {project_name}

> Documento vivo. Cada sync/deploy/incidente relevante deve atualizar este manual.
> Versionado no git junto com `sync.yaml`. CLI regenera com `fork-sync manuals regen {project_name}`.

## 1. Visão Geral

- **Projeto:** `{project_name}`
- **Display name:** `{cfg.get('project', project_name)}`
- **Estratégia de merge:** `{cfg.get('merge_strategy', cfg.get('merge', {}).get('strategy', 'merge'))}`
- **Deploy Docker:** {'sim' if has_deploy else 'não'}

## 2. Upstreams

"""
    if not upstreams:
        content += "_Nenhum upstream configurado (repositório independente)._\n\n"
    else:
        content += "| # | Nome | URL | Role |\n|---|------|-----|------|\n"
        for i, u in enumerate(upstreams, 1):
            content += f"| {i} | `{u['name']}` | {u['url']} | {u.get('role', 'primary')} |\n"
        content += "\n"

    content += "## 3. Estratégia de Sync — Passo a Passo\n\n"
    content += _strategy_steps(cfg, has_deploy)
    content += "\n## 4. Paths Protegidos (rebrand)\n\n"
    protected = cfg.get("protected_paths", [])
    if protected:
        content += "Estes paths são preservados em conflito (nunca sobrescritos pelo upstream):\n\n"
        for p in protected:
            content += f"- `{p}`\n"
    else:
        content += "_Nenhum path protegido configurado._\n"
    content += "\n## 5. Como Adaptar o Fork (Rebrand)\n\n"
    content += _rebrand_steps(cfg, project_name)
    content += "\n## 6. Como Reagir a Breaking Changes do Upstream\n\n"
    content += """1. **Verificar release notes do upstream:**
   ```bash
   gh release list --repo <UPSTREAM_URL>
   ```
2. **Comparar últimos N commits:**
   ```bash
   git fetch upstream
   git log --oneline upstream/<branch> -20
   ```
3. **Rodar sync em dry-run:**
   ```bash
   fork-sync sync <PROJETO> --dry-run
   ```
4. **Aplicar mudanças de rebrand (se necessário):**
   - Editar paths protegidos
   - Atualizar este manual (incrementar `version:` no frontmatter)
5. **Sync real:**
   ```bash
   fork-sync sync <PROJETO>
   ```
6. **Validar:**
   - Rodar testes do projeto (se existirem)
   - Verificar rebrand visualmente
   - Commit + push

## 7. Troubleshooting Específico

_Documentar aqui problemas recorrentes deste fork._

"""
    content += f"""## 8. Histórico de Versões do Manual

| Versão | Data | Mudança |
|--------|------|---------|
| 1 | {today} | Geração inicial via `fork-sync manuals generate` |

---

_Mantenha este manual sincronizado com `sync.yaml`. Se mudar a estratégia, regenere:_
```bash
fork-sync manuals regenerate {project_name}
```
"""
    manual_path.write_text(content)
    return {"status": "created", "path": str(manual_path), "version": 1}


def _strategy_steps(cfg: dict, has_deploy: bool) -> str:
    strategy = cfg.get("merge_strategy") or (cfg.get("merge") or {}).get("strategy", "merge")
    steps = [f"1. **Estratégia:** `{strategy}`"]
    if strategy == "custom":
        script = (cfg.get("merge") or {}).get("strategy_script", "")
        steps.append(f"2. **Script custom:** `{script}`")
        steps.append("3. Validar paths antes/depois do script (ver seção 3)")
    elif strategy == "theirs":
        steps.append("2. Conflitos são resolvidos a favor do upstream (rebrand fica em `protected_paths`)")
    elif strategy == "ours":
        steps.append("2. Conflitos são resolvidos a favor do fork (rebrand vence)")
    else:  # merge
        steps.append("2. Merge padrão do git, com `protected_paths` preservando rebrand")

    if has_deploy:
        steps.append("3. **Deploy Docker:** `fork-sync sync <PROJETO> --deploy`")
        steps.append("4. Health check pós-deploy: ver `deploy.yaml.health_endpoint`")
    return "\n".join(steps) + "\n"


def _rebrand_steps(cfg: dict, project_name: str) -> str:
    return f"""Documentar aqui as customizações que diferenciam este fork do upstream:

- **Identidade visual:** logos, cores, naming
- **Funcionalidades extras:** patches próprios
- **Configurações locais:** endpoints, paths
- **i18n:** traduções adicionadas

Para cada item, referenciar o path em `protected_paths` e dar contexto de POR QUE
essa customização existe (issue, ticket, decisão arquitetural).

Exemplo:
- `web/default/public/logo.png` — Logo do Atius, não usar o do new-api upstream
- `i18n/locales/pt-BR.yaml` — Tradução PT-BR adicionada manualmente

Se adicionar rebrand:
1. Adicionar path em `protected_paths` no `sync.yaml`
2. Documentar aqui com justificativa
3. Incrementar `version:` no frontmatter deste manual
"""


def update_manual_section(project_name: str, section: str, content: str) -> dict:
    """Atualiza seção específica do manual (append)."""
    path = get_manual_path(project_name)
    if not path.exists():
        raise FileNotFoundError(f"Manual de {project_name} não existe. Rode: fork-sync manuals generate {project_name}")
    text = path.read_text()
    section_header = f"## {section}"
    if section_header not in text:
        raise ValueError(f"Seção '{section}' não existe no manual. Edite manualmente.")
    new_text = text.replace(
        section_header,
        f"{section_header}\n\n{content}\n",
        1,
    )
    path.write_text(new_text)
    return {"status": "updated", "path": str(path)}


def record_sync(project_name: str, status: str, version: str = "",
                notes: str = "") -> dict:
    """Adiciona entrada ao histórico do manual após sync."""
    if not manual_exists(project_name):
        generate_manual(project_name)
    today = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    entry = f"| {today} | {version or '-'} | {status} | {notes or '-'} |"
    path = get_manual_path(project_name)
    text = path.read_text()

    # Encontrar a tabela de histórico e adicionar entrada
    if "## 8. Histórico" in text:
        # Inserir após o cabeçalho da tabela
        idx = text.index("| Versão | Data | Mudança |")
        # Pular o separador (`|---`)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("|---") and i > 0 and "Versão" in lines[i-1]:
                lines.insert(i + 1, entry)
                break
        path.write_text("\n".join(lines))
    return {"status": "recorded", "entry": entry}


def list_manuals() -> list:
    """Lista todos os manuais com metadados."""
    ensure_manuals_dir()
    manuals = []
    for p in sorted(MANUALS_DIR.glob("*.md")):
        name = p.stem
        text = p.read_text()
        # Extrair frontmatter
        m = re.search(r"^---\n(.*?)\n---", text, re.DOTALL)
        meta = {}
        if m:
            try:
                meta = yaml.safe_load(m.group(1))
            except Exception:
                pass
        meta["name"] = name
        meta["path"] = str(p)
        meta["size_kb"] = round(p.stat().st_size / 1024, 1)
        manuals.append(meta)
    return manuals
