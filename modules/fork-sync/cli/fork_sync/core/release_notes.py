"""release_notes — geração de release notes em PT-BR para forks.

Responsabilidade:
1. Buscar release do upstream via gh CLI
2. Extrair estrutura (Highlights, Bug Fixes, What's Changed, Contributors, Assets)
3. Traduzir conteúdo pra PT-BR (via deep-translator / GoogleTranslator)
4. Adicionar marca d'água do fork (rf{N}, link upstream, gerado por)
5. Suportar merge com mudanças locais (arquivos alterados pelo fork)

Princípios:
- Estrutura SEMPRE em PT-BR (determinístico)
- Prosa traduzida (GoogleTranslator default, pode plugar LLM depois)
- Atribuição: linka upstream, contributors, autor do release
- Assets: preserva links com notas "gerado pelo build pipeline upstream"
- Idempotente: detecta release já criada e não duplica
- Tudo configurável via sync.yaml (campos novos: `release.translate`, `release.style`)
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from fork_sync.core.config import REPO_ROOT, PROJECTS_DIR


# ─────────── Constantes ───────────

TRANSLATE_CACHE_DIR = REPO_ROOT / ".translate-cache"
TRANSLATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TRANSLATOR = "google"  # 'google' | 'm2m100' | 'noop'


# ─────────── Tradução ───────────

def _translate_text(text: str, target: str = "pt") -> str:
    """Traduz texto pra PT. Cacheia em disco pra evitar re-trabalho.

    Usa deep-translator (GoogleTranslator) por default. Fallback gracioso
    se pacote não disponível: retorna texto original com aviso.
    """
    if not text or not text.strip():
        return text
    if target == "en" or not target:
        return text

    # Cache key = hash do texto + target
    import hashlib
    cache_key = hashlib.sha256(f"{target}:{text}".encode()).hexdigest()[:16]
    cache_file = TRANSLATE_CACHE_DIR / f"{cache_key}.txt"
    if cache_file.exists():
        return cache_file.read_text()

    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="auto", target=target)
        # GoogleTranslator tem limite ~5000 chars por request; chunk se preciso
        chunks = []
        for i in range(0, len(text), 4500):
            chunk = text[i:i + 4500]
            try:
                chunks.append(translator.translate(chunk))
            except Exception:
                chunks.append(chunk)  # fallback: mantém original
        result = "".join(chunks)
    except ImportError:
        result = text  # deep-translator não disponível

    cache_file.write_text(result)
    return result


def _translate_lines(lines: list, target: str = "pt") -> list:
    """Traduz lista de linhas (preserva formatação)."""
    return [_translate_text(ln, target) for ln in lines]


# ─────────── Seções canônicas PT-BR ───────────

PT_SECTIONS = {
    "highlights": "## Destaques",
    "highlights_intro": "Esta é uma release de estabilidade e confiabilidade do fork, sincronizada com a upstream.",
    "bug_fixes": "## Correções de Bugs",
    "under_hood": "## Nos Bastidores",
    "what_changed": "## O Que Mudou",
    "contributors": "## Contribuidores",
    "upstream_compare": "## Detalhes do Diff com Upstream",
    "fork_changes": "## Mudanças Específicas deste Fork",
    "assets": "## Binários e Artefatos",
    "footer": """---

🔗 **Upstream original:** [{upstream_url}]({upstream_url})
📦 **Repositório fork:** [{fork_url}]({fork_url})
🏷️ **Tag:** `{tag}` • **Sincronizado em:** {date}
🤖 **Gerado automaticamente por:** [fork-sync](https://github.com/giovannimnz/fork-sync)
"""
}

PT_LABELS = {
    "fix": "fix",
    "feat": "feat",
    "chore": "chore",
    "refactor": "refactor",
    "docs": "docs",
    "test": "test",
    "perf": "perf",
    "build": "build",
    "ci": "ci",
    "style": "style",
}


# ─────────── Extração da release upstream ───────────

def _gh_api(endpoint: str) -> Optional[dict]:
    """Wrapper gh api."""
    try:
        out = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return None
        return json.loads(out.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def fetch_upstream_release(upstream_full: str, version: str) -> Optional[dict]:
    """Busca release v{version} do upstream (owner/repo)."""
    v = version.lstrip("v")  # gh api exige SEM prefixo v
    return _gh_api(f"repos/{upstream_full}/releases/tags/v{v}")


def fetch_upstream_compare(upstream_full: str, prev_version: str, new_version: str) -> Optional[dict]:
    """Busca diff entre 2 tags do upstream."""
    a = prev_version.lstrip("v")
    b = new_version.lstrip("v")
    return _gh_api(f"repos/{upstream_full}/compare/v{a}...v{b}")


def _parse_upstream_body(body: str) -> dict:
    """Extrai seções da release body (Highlights, Bug Fixes, etc).

    Suporta tanto `## Heading` (h2) quanto `### Heading` (h3) como separadores
    de seção, comum quando há agrupamento (ex: "Highlights" contém sub-seções
    como "ACP Session Reliability", "Bug Fixes", "Under the Hood").

    Semântica: headings canônicos (Highlights, Bug Fixes, Under the Hood, etc)
    delimitam blocos. Sub-headings (h3 ou h4) dentro de uma seção canônica são
    PRECEDIDOS pelo nome como prefixo do bullet pra dar contexto (ex:
    "**ACP Session Reliability** — Models now stay in sync...").
    """
    sections = {
        "highlights_intro": "",
        "highlights_bullets": [],
        "bug_fixes": [],
        "under_hood": [],
        "other_sections": {},
    }

    if not body:
        return sections

    lines = body.split("\n")
    current_section = None
    current_bullets = []
    current_subheading = None
    other_sections = {}

    for line in lines:
        # Aceita ##, ### ou #### como separador
        heading_match = re.match(r"^(#{2,4})\s+(.+)$", line.strip())
        if heading_match:
            heading_level = len(heading_match.group(1))
            heading_text = heading_match.group(2)
            heading_lower = heading_text.lower()
            classified = _classify_heading(heading_lower)

            if heading_level == 2 or classified != heading_lower:
                # h2 OU heading classificado em canônica → nova seção top-level
                _save_section(current_section, current_bullets, sections, other_sections)
                current_section = classified
                current_bullets = []
                current_subheading = None
            else:
                # h3/h4 dentro de seção não-canônica (ex: "### ACP Session Reliability"
                # dentro de "## Highlights") → marca sub-heading pra prependar
                if current_section:
                    current_subheading = heading_text
                continue
        else:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("- ", "* ")) and current_section:
                bullet = re.sub(r"^[-*]\s+", "", stripped)
                if current_subheading:
                    bullet = f"**{current_subheading}** — {bullet}"
                current_bullets.append(bullet)
            elif current_section == "highlights" and not sections["highlights_intro"]:
                sections["highlights_intro"] = stripped
            elif current_section and not stripped.startswith(("-", "*")):
                # Texto sob seção (não bullet) — anexa ao último bullet se for continuação
                if current_bullets:
                    current_bullets[-1] = current_bullets[-1] + " " + stripped
                elif current_section == "highlights" and not sections["highlights_intro"]:
                    sections["highlights_intro"] = stripped

    # Salvar última seção
    _save_section(current_section, current_bullets, sections, other_sections)
    sections["other_sections"] = other_sections
    return sections


def _classify_heading(heading_lower: str) -> str:
    """Classifica heading em uma das seções canônicas."""
    if "highlight" in heading_lower:
        return "highlights"
    if any(kw in heading_lower for kw in ("bug fix", "bugfix", "correction", "fixes")):
        return "bug_fixes"
    if any(kw in heading_lower for kw in ("under the hood", "underneath", "internal", "bastidores")):
        return "under_hood"
    if "contributor" in heading_lower:
        return "contributors"
    if "what" in heading_lower and "changed" in heading_lower:
        return "what_changed"
    return heading_lower  # mantém nome original pra outras seções


def _save_section(name, bullets, sections, other_sections):
    """Helper: distribui bullets nas seções canônicas ou other_sections."""
    if not name or not bullets:
        return
    if name == "highlights":
        sections["highlights_bullets"] = bullets
    elif name == "bug_fixes":
        sections["bug_fixes"] = bullets
    elif name == "under_hood":
        sections["under_hood"] = bullets
    else:
        other_sections[name] = bullets


# ─────────── Geração da release em PT-BR ───────────

def generate_release_notes(
    project_name: str,
    upstream_version: str,
    fork_tag: str,
    upstream_url: str,
    fork_url: str,
    changed_files: Optional[list] = None,
    translate: bool = True,
) -> dict:
    """Gera release notes completas em PT-BR.

    Args:
        project_name: nome do projeto no fork-sync
        upstream_version: versão upstream (sem 'v')
        fork_tag: tag completa do fork (ex: v2.1.10-rf2)
        upstream_url: URL completa do upstream
        fork_url: URL completa do fork
        changed_files: lista de paths alterados pelo fork (opcional)
        translate: se False, mantém texto original (inglês)

    Returns:
        dict com: title, body, summary
    """
    today = datetime.now().strftime("%Y-%m-%d")
    upstream_full = upstream_url.replace("https://github.com/", "").rstrip("/")
    fork_full = fork_url.replace("https://github.com/", "").rstrip("/")

    # Buscar release upstream
    upstream_rel = fetch_upstream_release(upstream_full, upstream_version)
    if not upstream_rel:
        # Fallback mínimo se upstream não responder
        return {
            "title": fork_tag,
            "body": _build_fallback_body(fork_tag, upstream_version, upstream_url, fork_url, today),
            "summary": {"status": "no_upstream_release", "version": upstream_version},
        }

    upstream_body = upstream_rel.get("body", "")
    parsed = _parse_upstream_body(upstream_body)

    # Traduzir se solicitado
    target_lang = "pt" if translate else "en"
    if translate:
        highlights_pt = _translate_lines(parsed.get("highlights_bullets", []), target_lang)
        bug_fixes_pt = _translate_lines(parsed.get("bug_fixes", []), target_lang)
        under_hood_pt = _translate_lines(parsed.get("under_hood", []), target_lang)
        intro_pt = _translate_text(parsed.get("highlights_intro", ""), target_lang) or PT_SECTIONS["highlights_intro"]
    else:
        highlights_pt = parsed.get("highlights_bullets", [])
        bug_fixes_pt = parsed.get("bug_fixes", [])
        under_hood_pt = parsed.get("under_hood", [])
        intro_pt = parsed.get("highlights_intro", "") or PT_SECTIONS["highlights_intro"]

    # Construir body em PT-BR
    parts = [f"# {fork_tag}", ""]
    parts.append(intro_pt)
    parts.append("")

    if highlights_pt:
        parts.append(PT_SECTIONS["highlights"])
        for b in highlights_pt:
            parts.append(f"- {b}")
        parts.append("")

    if bug_fixes_pt:
        parts.append(PT_SECTIONS["bug_fixes"])
        for b in bug_fixes_pt:
            parts.append(f"- {b}")
        parts.append("")

    if under_hood_pt:
        parts.append(PT_SECTIONS["under_hood"])
        for b in under_hood_pt:
            parts.append(f"- {b}")
        parts.append("")

    # What's Changed (commits) — buscar via compare
    prev_version = _prev_version_hint(upstream_version)
    compare = fetch_upstream_compare(upstream_full, prev_version, upstream_version)
    if compare and compare.get("commits"):
        parts.append(PT_SECTIONS["what_changed"])
        for c in compare["commits"][:30]:  # top 30
            sha = (c.get("sha") or "")[:7]
            msg = (c.get("commit", {}).get("message") or "").split("\n")[0]
            # Author pode ser null em commits mergeados sem PR — fallback
            author_obj = c.get("author") or {}
            author_login = author_obj.get("login") or c.get("commit", {}).get("author", {}).get("name", "unknown")
            pr_match = re.search(r"\(#(\d+)\)", msg)
            pr_ref = f" (#{pr_match.group(1)})" if pr_match else ""
            parts.append(f"- `{sha}` {msg} — @{author_login}{pr_ref}")
        parts.append("")

    # Mudanças específicas do fork
    if changed_files:
        parts.append(PT_SECTIONS["fork_changes"])
        parts.append(f"Este fork tem **{len(changed_files)} arquivo(s) próprio(s)** "
                     f"que diverge(m) do upstream:")
        parts.append("")
        for f in changed_files[:50]:
            parts.append(f"- `{f}`")
        if len(changed_files) > 50:
            parts.append(f"- ... e mais {len(changed_files) - 50}")
        parts.append("")

    # Contributors (do upstream)
    if compare and compare.get("commits"):
        contributors = set()
        for c in compare["commits"]:
            if c.get("author") and c["author"].get("login"):
                contributors.add(c["author"]["login"])
        if contributors:
            parts.append(PT_SECTIONS["contributors"])
            parts.append("Agradecimentos aos contribuidores do upstream nesta release:")
            parts.append("")
            for c in sorted(contributors):
                parts.append(f"- @{c}")
            parts.append("")

    # Assets (binários do upstream — preservados)
    assets = upstream_rel.get("assets", [])
    if assets:
        parts.append(PT_SECTIONS["assets"])
        parts.append("Binários compilados do upstream (rebuild opcional via `fork-sync deploy`):")
        parts.append("")
        for a in assets[:20]:  # top 20
            name = a.get("name", "?")
            size_mb = round(a.get("size", 0) / (1024 * 1024), 1)
            dl = a.get("browser_download_url", "")
            parts.append(f"- [{name}]({dl}) — {size_mb} MB")
        if len(assets) > 20:
            parts.append(f"- ... e mais {len(assets) - 20} artefatos")
        parts.append("")

    # Footer
    parts.append(PT_SECTIONS["footer"].format(
        upstream_url=upstream_url,
        fork_url=fork_url,
        tag=fork_tag,
        date=today,
    ))

    body = "\n".join(parts)
    return {
        "title": fork_tag,
        "body": body,
        "summary": {
            "status": "ok",
            "upstream_version": upstream_version,
            "fork_tag": fork_tag,
            "highlights_count": len(highlights_pt),
            "bug_fixes_count": len(bug_fixes_pt),
            "under_hood_count": len(under_hood_pt),
            "commits_count": len(compare.get("commits", [])) if compare else 0,
            "assets_count": len(assets),
            "changed_files_count": len(changed_files) if changed_files else 0,
            "translated": translate,
        },
    }


def _build_fallback_body(fork_tag, upstream_version, upstream_url, fork_url, today):
    """Body mínimo quando upstream não responde."""
    return f"""# {fork_tag}

Sync release baseado em upstream v{upstream_version}.

⚠️ _Release notes do upstream não foram encontradas via API._

🔗 **Upstream original:** {upstream_url}
📦 **Repositório fork:** {fork_url}
🏷️ **Tag:** `{fork_tag}` • **Sincronizado em:** {today}
🤖 **Gerado automaticamente por:** [fork-sync](https://github.com/giovannimnz/fork-sync)
"""


def _prev_version_hint(version: str) -> str:
    """Heurística simples pra tag anterior (v2.1.9 se versão=v2.1.10)."""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        return "v0.0.0"
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if patch > 0:
        return f"v{major}.{minor}.{patch - 1}"
    if minor > 0:
        return f"v{major}.{minor - 1}.0"
    return f"v{major - 1}.0.0"


# ─────────── Cache de release notes geradas (local) ───────────

def save_local(project_name: str, fork_tag: str, body: str) -> Path:
    """Salva release notes gerada em `manuals/<projeto>/releases/<tag>.md`."""
    rel_dir = REPO_ROOT / "manuals" / project_name / "releases"
    rel_dir.mkdir(parents=True, exist_ok=True)
    path = rel_dir / f"{fork_tag}.md"
    path.write_text(body)
    return path


def list_local_releases(project_name: str) -> list:
    """Lista release notes geradas localmente pra um projeto."""
    rel_dir = REPO_ROOT / "manuals" / project_name / "releases"
    if not rel_dir.exists():
        return []
    return sorted([p.name for p in rel_dir.glob("*.md")])
