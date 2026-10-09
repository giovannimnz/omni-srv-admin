#!/usr/bin/env python3
"""
spark-skills-packager.py

Empacota e valida skills do catalogo canonico (~/.gemini/config/skills)
para importacao e consumo no Gemini Spark (https://gemini.google.com/spark/skills).

Suporta:
- Exportacao de SKILL.md isolado ou sanitizado.
- Geracao de bundles .zip tematicos aceitos pelo botao de upload (↑) da UI do Spark.
- Manifest consolidado em JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extrai YAML frontmatter e corpo markdown."""
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return {}, content
    yaml_text, body = match.group(1), match.group(2)
    meta = {}
    for line in yaml_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"\'')
            meta[k] = v
    return meta, body


def sanitize_skill_content(meta: dict, body: str) -> str:
    """Prepara o SKILL.md para o Gemini Spark (removendo tags especificas do runtime local se necessario)."""
    # Remove adaptadores exclusivos do Codex/Hermes/Antigravity interno se existirem
    cleaned_body = re.sub(r"<antigravity_adapter>.*?</antigravity_adapter>", "", body, flags=re.DOTALL)
    cleaned_body = cleaned_body.strip()
    
    name = meta.get("name", "custom-skill")
    desc = meta.get("description", "Habilidade personalizada para o Gemini Spark")
    
    header = f"---\nname: \"{name}\"\ndescription: \"{desc}\"\n---\n\n"
    return header + cleaned_body


def package_skills(skills_dir: Path, out_dir: Path, zip_mode: bool = True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"skills": [], "categories": {}}

    skill_folders = [p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

    print(f"[*] Analisando {len(skill_folders)} pastas em {skills_dir}...")

    bundles = {
        "atius-fleet-ops": ["atius-", "oci-", "codex-", "xrdp-", "cloudflare-", "pwsh-"],
        "gsd-spec-driven": ["gsd-", "osd-", "hsd-"],
        "intelligence-brain": ["brain", "gbrain", "obsidian", "ijfw-", "mempalace"],
        "devtools-automation": ["chrome-", "playwright", "debug-", "test-", "lint", "caveman", "cavecrew"],
    }

    categorized_files: dict[str, list[tuple[str, str]]] = {cat: [] for cat in bundles}
    categorized_files["general"] = []

    count = 0
    for folder in sorted(skill_folders):
        skill_md = folder / "SKILL.md"
        if not skill_md.exists():
            continue
        
        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            meta, body = parse_frontmatter(content)
            name = meta.get("name", folder.name)
            desc = meta.get("description", "")
            
            clean_content = sanitize_skill_content(meta, body)
            count += 1
            
            manifest["skills"].append({
                "name": name,
                "folder": folder.name,
                "description": desc,
            })

            # Alocar na categoria
            assigned = False
            for cat, prefixes in bundles.items():
                if any(p in name for p in prefixes):
                    categorized_files[cat].append((name, clean_content))
                    assigned = True
                    break
            if not assigned:
                categorized_files["general"].append((name, clean_content))

            # Salvar SKILL.md isolado
            single_skill_dir = out_dir / "individual" / name
            single_skill_dir.mkdir(parents=True, exist_ok=True)
            (single_skill_dir / "SKILL.md").write_text(clean_content, encoding="utf-8")

        except Exception as e:
            print(f"[!] Erro ao processar {folder.name}: {e}", file=sys.stderr)

    # Gerar bundles ZIP se solicitado
    if zip_mode:
        zip_dir = out_dir / "bundles"
        zip_dir.mkdir(parents=True, exist_ok=True)
        for cat, items in categorized_files.items():
            if not items:
                continue
            zip_path = zip_dir / f"spark-skills-{cat}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for skill_name, text in items:
                    # Incluir no formato pasta/SKILL.md dentro do zip
                    zf.writestr(f"{skill_name}/SKILL.md", text)
            print(f"[+] Bundle criado: {zip_path.name} ({len(items)} skills)")

    # Salvar manifest
    manifest_path = out_dir / "spark-skills-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Manifest gerado: {manifest_path} ({count} skills processadas)")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Empacota skills para o Gemini Spark")
    default_skills = Path.home() / ".gemini" / "config" / "skills"
    default_out = Path("build/gemini-spark-skills")
    parser.add_argument("--src", type=Path, default=default_skills, help="Diretorio de origem das skills")
    parser.add_argument("--out", type=Path, default=default_out, help="Diretorio de saida")
    parser.add_argument("--no-zip", action="store_true", help="Nao gerar arquivos .zip")
    args = parser.parse_args()

    if not args.src.exists():
        print(f"[!] Diretorio fonte nao existe: {args.src}", file=sys.stderr)
        sys.exit(1)

    package_skills(args.src, args.out, zip_mode=not args.no_zip)


if __name__ == "__main__":
    main()
