"""agent-content — Git-backed content-pack sync for Hermes/Codex fleet artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

import click
import yaml

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", str(Path(__file__).resolve().parents[2])))
PACKS_ROOT = REPO / "modules" / "agent-content-packs" / "packs"
INDEX_PATH = REPO / "modules" / "agent-content-packs" / "manifest-index.yaml"
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bcfat_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b(?:AIza|AKIA)[A-Za-z0-9_-]{16,}\b"),
)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise click.ClickException(f"yaml não encontrado: {path}") from exc
    except yaml.YAMLError as exc:
        raise click.ClickException(f"yaml inválido: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise click.ClickException(f"yaml inválido (raiz não-dict): {path}")
    return data


def _load_index() -> dict[str, Any]:
    return _load_yaml(INDEX_PATH)


def _manifest_path(pack: str) -> Path:
    index = _load_index()
    entries = index.get("packs")
    if not isinstance(entries, list):
        raise click.ClickException("manifest-index inválido: campo packs ausente")
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == pack:
            manifest = entry.get("manifest")
            if not manifest:
                raise click.ClickException(f"pack sem manifest: {pack}")
            return REPO / str(manifest)
    raise click.ClickException(f"pack não encontrado: {pack}")


def _targets_path(pack: str) -> Path:
    return _manifest_path(pack).with_name("targets.yaml")


def _load_manifest(pack: str) -> dict[str, Any]:
    return _load_yaml(_manifest_path(pack))


def _load_targets(pack: str) -> dict[str, Any]:
    return _load_yaml(_targets_path(pack))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        raise ValueError("frontmatter ausente")
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError("frontmatter sem fechamento")
    parsed = yaml.safe_load(parts[0][4:])
    if not isinstance(parsed, dict):
        raise ValueError("frontmatter inválido")
    return parsed


def _scan_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append(match.group(0)[:12] + "...")
    return hits


def _pack_item_dir(pack: str, item: dict[str, Any]) -> Path:
    source_path = item.get("source_path")
    if not source_path:
        raise click.ClickException(f"item sem source_path: {item.get('name', '?')}")
    return _manifest_path(pack).parent / str(source_path)


def _accessible_home(target: dict[str, Any]) -> Path | None:
    runtime = str(target.get("runtime", ""))
    home = str(target.get("home", ""))
    if runtime == "windows":
        return Path(home)
    if runtime == "wsl":
        distro = str(target.get("distro", ""))
        posix_home = PurePosixPath(home)
        unc = "\\\\wsl.localhost\\" + distro + "\\" + "\\".join(posix_home.parts[1:])
        return Path(unc)
    return None


def _target_runtime(target: dict[str, Any]) -> str:
    return str(target.get("runtime", ""))


def _target_home_str(target: dict[str, Any]) -> str:
    return str(target.get("home", ""))


def _target_root(target: dict[str, Any], rel_path: str) -> Path:
    home_str = _target_home_str(target)
    home_path = Path(home_str) if home_str else Path('.')
    skills_root = str(target.get('skills_root', '') or '')
    slash_root = str(target.get('slash_commands_root', '') or '')
    normalized = rel_path.replace('\\', '/')
    if normalized == 'skills' or normalized.startswith('skills/'):
        suffix = normalized[len('skills/'): ] if normalized.startswith('skills/') else ''
        base = Path(skills_root) if skills_root else (home_path / 'skills')
        return base / suffix if suffix else base
    if normalized == 'slash-commands' or normalized.startswith('slash-commands/'):
        suffix = normalized[len('slash-commands/'): ] if normalized.startswith('slash-commands/') else ''
        base = Path(slash_root) if slash_root else (home_path / 'slash-commands')
        return base / suffix if suffix else base
    return home_path / rel_path


def _relative_posix_path(value: object, *, field: str) -> PurePosixPath:
    """Accept only a normalized, non-empty POSIX-relative manifest path."""
    if not isinstance(value, str) or not value:
        raise click.ClickException(f"{field} inválido: caminho ausente")
    if "\\" in value:
        raise click.ClickException(f"{field} inválido: barras invertidas não são aceitas: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {".", ".."} for part in path.parts):
        raise click.ClickException(f"{field} inválido: exige caminho POSIX relativo normalizado: {value}")
    return path


def _local_destination(home: Path, rel_path: object, *, field: str) -> Path:
    """Resolve a local manifest destination and prove it cannot leave ``home``."""
    rel = _relative_posix_path(rel_path, field=field)
    destination = home.joinpath(*rel.parts)
    try:
        destination.resolve(strict=False).relative_to(home.resolve(strict=False))
    except ValueError as exc:
        raise click.ClickException(f"{field} inválido: destino fora do home configurado") from exc
    return destination


def _validate_sync_paths(items: list[dict[str, Any]], target: dict[str, Any]) -> None:
    """Validate every manifest-controlled write path before any target action."""
    product = str(target.get("product", ""))
    runtime = _target_runtime(target)
    home = _accessible_home(target) if runtime in {"windows", "wsl"} else None
    for item in items:
        if str(item.get("kind")) == "skill-pack":
            files = item.get("files")
            if not isinstance(files, list):
                raise click.ClickException(f"item com files inválidos: {item.get('name')}")
            for entry in files:
                if not isinstance(entry, dict):
                    raise click.ClickException(f"item com arquivo inválido: {item.get('name')}")
                path = _relative_posix_path(entry.get("path"), field=f"files[].path de {item.get('name')}")
                # A skill-pack file is relative to its product source root.
                if path.parts[0] == product:
                    path = PurePosixPath(*path.parts[1:])
                if not path.parts:
                    raise click.ClickException(f"files[].path de {item.get('name')} não pode apontar ao home")
                if home is not None:
                    _local_destination(home, path.as_posix(), field=f"files[].path de {item.get('name')}")
        else:
            rel_path = _install_rel_path(target, item)
            if rel_path is None:
                continue
            _relative_posix_path(rel_path, field=f"install.{product}.rel_path de {item.get('name')}")
            if home is not None:
                _local_destination(home, rel_path, field=f"install.{product}.rel_path de {item.get('name')}")
                mapped = _target_root(target, rel_path)
                try:
                    mapped.resolve(strict=False).relative_to(home.resolve(strict=False))
                except ValueError as exc:
                    raise click.ClickException(
                        f"install.{product}.rel_path de {item.get('name')} resolve fora do home configurado"
                    ) from exc


def _install_rel_path(target: dict[str, Any], item: dict[str, Any]) -> str | None:
    install = item.get('install', {})
    product = str(target.get('product', ''))
    if not isinstance(install, dict):
        return None
    runtime = _target_runtime(target)
    if product == 'codex' and str(item.get('kind')) == 'skill-pack':
        if runtime == 'ssh-linux':
            return 'codex/skills'
        return 'skills'
    entry = install.get(product)
    if isinstance(entry, dict):
        rel = entry.get('rel_path')
        return str(rel) if rel else None
    return None


def _ssh_base_command(target: dict[str, Any]) -> list[str]:
    host = str(target.get("host", ""))
    user = str(target.get("user", ""))
    if not host or not user:
        raise click.ClickException("target ssh-linux sem host/user")
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        f"{user}@{host}",
    ]


def _ssh_run(target: dict[str, Any], command: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    cmd = _ssh_base_command(target) + ["bash", "-lc", shlex.quote(command)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _ssh_backup(target: dict[str, Any], command: str) -> None:
    """Preserve remote content before an SSH replacement, failing closed on error."""
    backup = _ssh_run(target, command, timeout=180)
    if backup.returncode != 0:
        raise click.ClickException(
            f"falha no backup remoto ({target.get('host')}): {backup.stderr.strip()}"
        )


def _ssh_capture_tree(root: Path) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tgz") as handle:
        temp_path = Path(handle.name)
    try:
        with tarfile.open(temp_path, "w:gz") as archive:
            archive.add(root, arcname=root.name)
        return temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def _ssh_extract_tree(target: dict[str, Any], source_root: Path, dest_home: str, rel_path: str) -> None:
    archive_bytes = _ssh_capture_tree(source_root)
    remote_cmd = (
        f"set -euo pipefail; "
        f"mkdir -p {shlex.quote(dest_home)}; "
        f"dest={shlex.quote(str(PurePosixPath(dest_home) / PurePosixPath(rel_path)))}; "
        f"parent=$(dirname \"$dest\"); mkdir -p \"$parent\"; "
        f"tmp=$(mktemp \"$parent/.agent-content-XXXXXX.tgz\"); "
        f"stage=$(mktemp -d \"$parent/.agent-content-stage-XXXXXX\"); "
        f"previous=''; "
        f"cleanup() {{ rm -f \"$tmp\"; rm -rf \"$stage\"; if [ -n \"$previous\" ] && [ ! -e \"$dest\" ]; then mv \"$previous\" \"$dest\"; fi; }}; "
        f"trap cleanup EXIT; "
        f"cat > \"$tmp\"; "
        f"tar -xzf \"$tmp\" -C \"$stage\"; "
        f"base={shlex.quote(source_root.name)}; "
        f"next=\"$stage/$base\"; test -d \"$next\"; "
        f"if [ -e \"$dest\" ]; then previous=$(mktemp -d \"$parent/.agent-content-previous-XXXXXX\"); rmdir \"$previous\"; mv \"$dest\" \"$previous\"; fi; "
        f"mv \"$next\" \"$dest\"; "
        f"if [ -n \"$previous\" ]; then rm -rf \"$previous\"; previous=''; fi"
    )
    proc = subprocess.run(
        _ssh_base_command(target) + ["bash", "-lc", shlex.quote(remote_cmd)],
        input=archive_bytes,
        capture_output=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise click.ClickException(f"falha no extract remoto ({target.get('host')}): {proc.stderr.decode(errors='replace')}")


def _ssh_file_sha256(target: dict[str, Any], remote_path: str) -> tuple[bool, str]:
    cmd = f"if [ -f {shlex.quote(remote_path)} ]; then sha256sum {shlex.quote(remote_path)} | awk '{{print $1}}'; else echo __MISSING__; fi"
    result = _ssh_run(target, cmd, timeout=120)
    if result.returncode != 0:
        return False, ""
    out = result.stdout.strip()
    if out == "__MISSING__":
        return False, ""
    return True, out


def _ssh_skill_pack_roots(source_root: Path, item: dict[str, Any], product: str) -> list[tuple[Path, str]]:
    """Return the explicitly managed top-level roots for an SSH skill-pack.

    A skill-pack is allowed to manage several product roots (for example,
    ``skills`` and ``slash-commands``), but it must never make the product
    home itself a replacement target.  The manifest file list is the authority
    so an untracked directory in a pack cannot expand the remote write scope.
    """
    prefix = PurePosixPath(product)
    roots: set[str] = set()
    files = item.get("files", [])
    if not isinstance(files, list):
        raise click.ClickException(f"item com files inválidos: {item.get('name')}")
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise click.ClickException(f"item com arquivo inválido: {item.get('name')}")
        path = PurePosixPath(entry["path"])
        try:
            relative = path.relative_to(prefix)
        except ValueError:
            continue
        if not relative.parts:
            continue
        roots.add(relative.parts[0])

    if not roots:
        raise click.ClickException(f"skill-pack sem raízes gerenciadas para produto {product}: {item.get('name')}")

    managed_roots: list[tuple[Path, str]] = []
    for root in sorted(roots):
        source = source_root / root
        if not source.is_dir():
            raise click.ClickException(f"raiz gerenciada ausente ou não é diretório: {source}")
        managed_roots.append((source, root))
    return managed_roots


def _item_mappings(pack: str, item: dict[str, Any], target: dict[str, Any]) -> tuple[Path | None, Path | None, list[tuple[Path, Path]]]:
    item_dir = _pack_item_dir(pack, item)
    runtime = _target_runtime(target)
    home = _accessible_home(target)
    if runtime not in {"windows", "wsl", "ssh-linux"}:
        raise click.ClickException(f"runtime não suportado para sync: {target.get('runtime')}")
    product = str(target.get("product", ""))
    kind = str(item.get("kind", "skill"))
    mappings: list[tuple[Path, Path]] = []
    if runtime == "ssh-linux":
        home_path = _target_root(target, '')
    else:
        if home is None:
            raise click.ClickException(f"runtime não suportado para sync local: {target.get('runtime')}")
        home_path = home
    if kind == "skill-pack":
        source_root = item_dir / product
        dest_base = home_path
        if not source_root.exists():
            return source_root, dest_base, []
        for src in sorted(path for path in source_root.rglob("*") if path.is_file()):
            rel = src.relative_to(source_root)
            mappings.append((src, dest_base / rel))
        return source_root, dest_base, mappings
    install = item.get("install", {})
    rel_path = _install_rel_path(target, item)
    if rel_path is None:
        return item_dir, None, []
    dest_root = home_path / str(rel_path)
    for src in sorted(path for path in item_dir.rglob("*") if path.is_file()):
        rel = src.relative_to(item_dir)
        mappings.append((src, dest_root / rel))
    return item_dir, dest_root, mappings


def _validate_item(pack: str, item: dict[str, Any]) -> dict[str, Any]:
    item_dir = _pack_item_dir(pack, item)
    issues: list[str] = []
    files = item.get("files", [])
    if not item_dir.exists():
        return {"name": item.get("name"), "ok": False, "issues": [f"source ausente: {item_dir}"]}
    for file_entry in files:
        rel = file_entry.get("path")
        expected = file_entry.get("sha256")
        if not rel:
            issues.append("entrada de file sem path")
            continue
        path = item_dir / str(rel)
        if not path.exists():
            issues.append(f"arquivo ausente: {rel}")
            continue
        actual = _sha256_file(path)
        if expected and actual != expected:
            issues.append(f"hash divergente: {rel}")
        if path.name == "SKILL.md":
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                frontmatter = _parse_frontmatter(text)
                if not frontmatter.get("name") or not frontmatter.get("description"):
                    issues.append(f"frontmatter incompleto: {rel}")
            except ValueError as exc:
                issues.append(f"frontmatter inválido: {rel}: {exc}")
            secret_hits = _scan_secrets(text)
            if secret_hits:
                issues.append(f"possible secret leak em {rel}: {', '.join(secret_hits)}")
        elif path.suffix.lower() in {".md", ".yaml", ".yml", ".json", ".txt"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            secret_hits = _scan_secrets(text)
            if secret_hits:
                issues.append(f"possible secret leak em {rel}: {', '.join(secret_hits)}")
    if str(item.get("kind")) == "skill-pack":
        has_skill = any(str(f.get("path", "")).endswith("SKILL.md") for f in files)
        if not has_skill:
            issues.append("skill-pack sem SKILL.md em nenhum subtree")
    else:
        required = item.get("required_files", [])
        for req in required:
            if not (item_dir / str(req)).exists():
                issues.append(f"required file ausente: {req}")
    return {"name": item.get("name"), "ok": not issues, "issues": issues, "file_count": len(files)}


def _remote_posix_path(target: dict[str, Any], local_mapped_path: Path) -> str:
    runtime = _target_runtime(target)
    if runtime != "ssh-linux":
        return str(local_mapped_path)
    home_path = PurePosixPath(_target_home_str(target))
    local_home = _accessible_home(target)
    if local_home is not None:
        rel_remote = local_mapped_path.relative_to(local_home).as_posix()
        return str(home_path / PurePosixPath(rel_remote))
    return str(local_mapped_path)


def _compute_diff(pack: str, item: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    runtime = _target_runtime(target)
    source_root, dest_root, mappings = _item_mappings(pack, item, target)
    missing = 0
    changed = 0
    ok = 0
    if runtime == "ssh-linux":
        for src, dst in mappings:
            remote_path = _remote_posix_path(target, dst)
            exists, remote_hash = _ssh_file_sha256(target, remote_path)
            if not exists:
                missing += 1
            elif _sha256_file(src) != remote_hash:
                changed += 1
            else:
                ok += 1
        extra = 0
        status = "noop"
        if missing or changed:
            status = "update" if changed else "new"
        return {
            "item": item.get("name"),
            "status": status,
            "missing": missing,
            "changed": changed,
            "unchanged": ok,
            "extra": extra,
            "mapping_count": len(mappings),
        }
    missing = 0
    changed = 0
    ok = 0
    for src, dst in mappings:
        if not dst.exists():
            missing += 1
        elif _sha256_file(src) != _sha256_file(dst):
            changed += 1
        else:
            ok += 1
    extra = 0
    if dest_root is not None and dest_root.exists() and str(item.get("kind")) != "skill-pack":
        expected = {dst.relative_to(dest_root).as_posix() for _, dst in mappings}
        actual = {p.relative_to(dest_root).as_posix() for p in dest_root.rglob("*") if p.is_file()}
        extra = len(actual - expected)
    status = "noop"
    if missing or changed or extra:
        status = "update" if (changed or extra) else "new"
    return {
        "item": item.get("name"),
        "status": status,
        "missing": missing,
        "changed": changed,
        "unchanged": ok,
        "extra": extra,
        "mapping_count": len(mappings),
    }


def _backup_root(home: Path) -> Path:
    return home / "backups" / "agent-content-sync"


def _copy_tree(src_root: Path, dst_root: Path) -> None:
    dst_root.parent.mkdir(parents=True, exist_ok=True)
    if dst_root.exists():
        shutil.rmtree(dst_root)
    shutil.copytree(src_root, dst_root)


def _backup_file(src: Path, backup_root: Path, relative_to: Path) -> None:
    rel = src.relative_to(relative_to)
    dst = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _rollback_item(result: dict[str, Any]) -> None:
    """Restore one completed local item from its pre-apply journal."""
    rollback = result.get("rollback")
    if not isinstance(rollback, dict) or rollback.get("runtime") != "local":
        return
    backup_root = Path(str(rollback["backup_root"]))
    if rollback["kind"] == "files":
        home = Path(str(rollback["home"]))
        for rel, existed in rollback["entries"]:
            destination = home / rel
            if existed:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_root / rel, destination)
            else:
                _remove_path(destination)
        return
    destination = Path(str(rollback["destination"]))
    _remove_path(destination)
    if rollback["existed"]:
        shutil.copytree(backup_root / "tree", destination)


def _run_validate_command(target: dict[str, Any]) -> dict[str, Any]:
    validate = target.get("validate")
    if not isinstance(validate, dict):
        return {"skipped": True, "reason": "no-validate-command"}
    cmd = validate.get("command")
    if not isinstance(cmd, list) or not cmd:
        return {"skipped": True, "reason": "invalid-validate-command"}
    runtime = _target_runtime(target)
    try:
        if runtime == "windows":
            result = subprocess.run([str(part) for part in cmd], capture_output=True, text=True, timeout=120)
        elif runtime == "wsl":
            distro = str(target.get("distro", ""))
            user = str(target.get("user", ""))
            result = subprocess.run(["wsl.exe", "-d", distro, "-u", user, "--", *[str(part) for part in cmd]], capture_output=True, text=True, timeout=120)
        elif runtime == "ssh-linux":
            command = " ".join(shlex.quote(str(part)) for part in cmd)
            result = _ssh_run(target, command, timeout=180)
        else:
            return {"skipped": True, "reason": f"validate-not-implemented-for-{runtime}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stdout": "", "stderr": ""}
    return {"ok": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def _apply_item(pack: str, item: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    runtime = _target_runtime(target)
    home = _accessible_home(target) if runtime in {"windows", "wsl"} else None
    source_root, dest_root, mappings = _item_mappings(pack, item, target) if runtime in {"windows", "wsl"} else ( _pack_item_dir(pack, item), None, [] )
    if runtime in {"windows", "wsl"}:
        if home is None:
            raise click.ClickException(f"runtime não suportado para apply local: {target.get('runtime')}")
        backup_root = _backup_root(home) / _timestamp() / pack / str(item.get("name")) / "before"
        if str(item.get("kind")) == "skill-pack":
            # ``copy2`` accepts a directory destination and would write below it.
            # A skill-pack manifest controls files only, so reject any existing
            # non-regular node (including symlinks) before creating a backup or
            # changing the target tree.
            for _src, dst in mappings:
                if (dst.exists() or dst.is_symlink()) and (not dst.is_file() or dst.is_symlink()):
                    raise click.ClickException(f"destino de skill-pack não é arquivo: {dst}")
            backup_root.mkdir(parents=True, exist_ok=True)
            entries: list[tuple[str, bool]] = []
            for _src, dst in mappings:
                rel = dst.relative_to(home).as_posix()
                existed = dst.exists()
                entries.append((rel, existed))
                if existed:
                    _backup_file(dst, backup_root, home)
            result = {
                "item": item.get("name"),
                "backup_root": str(backup_root),
                "rollback": {"runtime": "local", "kind": "files", "home": str(home), "backup_root": str(backup_root), "entries": entries},
            }
            try:
                for src, dst in mappings:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                result["post_status"] = _compute_diff(pack, item, target)
            except Exception:
                _rollback_item(result)
                raise
            return result
        else:
            if source_root is None:
                raise click.ClickException(f"item sem source_root: {item.get('name')}")
            if not isinstance(dest_root, Path):
                raise click.ClickException(f"item sem destino resolvido: {item.get('name')}")
            backup_root.mkdir(parents=True, exist_ok=True)
            existed = dest_root.exists()
            if existed:
                shutil.copytree(dest_root, backup_root / "tree")
            result = {
                "item": item.get("name"),
                "backup_root": str(backup_root),
                "rollback": {"runtime": "local", "kind": "tree", "destination": str(dest_root), "backup_root": str(backup_root), "existed": existed},
            }
            try:
                _copy_tree(source_root, dest_root)
                result["post_status"] = _compute_diff(pack, item, target)
            except Exception:
                _rollback_item(result)
                raise
            return result

    if runtime == "ssh-linux":
        # The former SSH implementation swapped source-directory roots. It
        # could publish unlisted files and lacked a journal that could restore
        # every completed destination after a later failure. Keep remote apply
        # fail-closed until a leaf-level remote transaction exists.
        raise click.ClickException(
            "sync --apply para ssh-linux está desabilitado: exige journal/rollback remoto por arquivo"
        )

    raise click.ClickException(f"runtime não suportado para apply: {runtime}")


def _post_status_summary(post: dict[str, Any]) -> str:
    """Render local diffs and SSH apply acknowledgements without assuming shape."""
    if {"missing", "changed", "extra", "unchanged"} <= post.keys():
        return (
            f"post_status={post['status']} missing={post['missing']} "
            f"changed={post['changed']} extra={post['extra']} unchanged={post['unchanged']}"
        )
    return f"post_status={post.get('status', 'unknown')}"


@click.group(name="agent-content")
def agent_content() -> None:
    """Sync de content packs Git-backed para Hermes/Codex."""


@agent_content.command("packs")
def list_packs() -> None:
    index = _load_index()
    packs = index.get("packs", [])
    for entry in packs:
        click.echo(f"{entry.get('name')}: {entry.get('manifest')}")


@agent_content.command("targets")
@click.option("--pack", required=True, help="Nome do pack.")
def list_targets(pack: str) -> None:
    targets = _load_targets(pack).get("targets", {})
    if not isinstance(targets, dict):
        raise click.ClickException("targets inválidos")
    for name, target in targets.items():
        click.echo(f"{name:24} product={target.get('product')} runtime={target.get('runtime')} home={target.get('home')}")


@agent_content.command("validate-pack")
@click.option("--pack", required=True, help="Nome do pack.")
@click.option("--json-output", is_flag=True, help="Saída JSON.")
def validate_pack(pack: str, json_output: bool) -> None:
    manifest = _load_manifest(pack)
    items = manifest.get("items", [])
    results = [_validate_item(pack, item) for item in items if isinstance(item, dict)]
    ok = all(item["ok"] for item in results)
    payload = {"pack": pack, "ok": ok, "results": results}
    if json_output:
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        click.echo(f"pack={pack} ok={ok}")
        for item in results:
            click.echo(f"- {item['name']}: {'OK' if item['ok'] else 'FAIL'}")
            for issue in item.get("issues", []):
                click.echo(f"    * {issue}")
    if not ok:
        raise SystemExit(1)


@agent_content.command("sync")
@click.option("--pack", required=True, help="Nome do pack.")
@click.option("--target", required=True, help="Nome do target.")
@click.option("--item", "item_filter", default=None, help="Filtra um item específico.")
@click.option("--dry-run/--apply", "dry_run", default=True, show_default=True, help="Dry-run por default; --apply grava mudanças.")
@click.option("--json-output", is_flag=True, help="Saída JSON.")
def sync(pack: str, target: str, item_filter: str | None, dry_run: bool, json_output: bool) -> None:
    manifest = _load_manifest(pack)
    targets = _load_targets(pack).get("targets", {})
    if target not in targets:
        raise click.ClickException(f"target não encontrado: {target}")
    target_cfg = targets[target]
    items = [item for item in manifest.get("items", []) if isinstance(item, dict)]
    if item_filter:
        items = [item for item in items if item.get("name") == item_filter]
        if not items:
            raise click.ClickException(f"item não encontrado no pack {pack}: {item_filter}")
    # Validate the complete write set before validation, diffing, SSH, or any
    # local filesystem operation. Manifests are untrusted write instructions.
    _validate_sync_paths(items, target_cfg)
    validation = [_validate_item(pack, item) for item in items]
    failures = [item for item in validation if not item["ok"]]
    if failures:
        payload = {"pack": pack, "target": target, "ok": False, "validation_failures": failures}
        if json_output:
            click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            click.echo(f"pack={pack} target={target} validation=FAIL")
            for item in failures:
                click.echo(f"- {item['name']}")
                for issue in item.get('issues', []):
                    click.echo(f"    * {issue}")
        raise SystemExit(1)
    if dry_run:
        diffs = [_compute_diff(pack, item, target_cfg) for item in items]
        payload = {"pack": pack, "target": target, "mode": "dry-run", "results": diffs}
        if json_output:
            click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            click.echo(f"pack={pack} target={target} mode=dry-run")
            for item in diffs:
                click.echo(f"- {item['item']}: status={item['status']} missing={item['missing']} changed={item['changed']} extra={item['extra']} unchanged={item['unchanged']}")
        return
    applied: list[dict[str, Any]] = []
    try:
        for item in items:
            applied.append(_apply_item(pack, item, target_cfg))
        runtime_validation = _run_validate_command(target_cfg)
    except Exception:
        for result in reversed(applied):
            _rollback_item(result)
        raise
    validation_failed = runtime_validation.get("ok") is not True
    if validation_failed:
        for result in reversed(applied):
            _rollback_item(result)
    payload = {"pack": pack, "target": target, "mode": "apply", "results": applied, "runtime_validation": runtime_validation}
    if json_output:
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        click.echo(f"pack={pack} target={target} mode=apply")
        for item in applied:
            post = item['post_status']
            click.echo(f"- {item['item']}: {_post_status_summary(post)}")
            click.echo(f"    backup={item['backup_root']}")
        click.echo(f"runtime_validation={runtime_validation}")
    if validation_failed:
        raise click.ClickException("sync aplicado, mas a validação do target falhou")


def main() -> None:
    agent_content()
