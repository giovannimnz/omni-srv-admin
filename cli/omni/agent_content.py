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
    _safe_identifier(pack, "pack")
    index = _load_index()
    entries = index.get("packs")
    if not isinstance(entries, list):
        raise click.ClickException("manifest-index inválido: campo packs ausente")
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == pack:
            manifest = entry.get("manifest")
            if not manifest:
                raise click.ClickException(f"pack sem manifest: {pack}")
            rel = _safe_relative_path(manifest, f"manifest de {pack}")
            return _contained_path(REPO, rel, f"manifest de {pack}")
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
    return (
        datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        + f"-{os.getpid()}-{os.urandom(4).hex()}"
    )


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


def _safe_relative_path(value: Any, label: str) -> PurePosixPath:
    raw = str(value or "").strip().replace("\\", "/")
    lexical_parts = raw.split("/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in lexical_parts):
        raise click.ClickException(f"path inseguro em {label}: {value!r}")
    return path


def _safe_identifier(value: Any, label: str) -> str:
    raw = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", raw):
        raise click.ClickException(f"identificador inseguro em {label}: {value!r}")
    return raw


def _contained_path(root: Path, rel: PurePosixPath, label: str) -> Path:
    root_resolved = root.resolve()
    candidate = root.joinpath(*rel.parts)
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise click.ClickException(f"symlink proibido em {label}: {current}")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root_resolved):
        raise click.ClickException(f"path escapa do root em {label}: {candidate}")
    return candidate


def _assert_tree_has_no_symlinks(root: Path, label: str) -> None:
    if root.is_symlink():
        raise click.ClickException(f"symlink proibido em {label}: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise click.ClickException(f"symlink proibido em {label}: {path}")


def _pack_item_dir(pack: str, item: dict[str, Any]) -> Path:
    source_path = item.get("source_path")
    if not source_path:
        raise click.ClickException(f"item sem source_path: {item.get('name', '?')}")
    root = _manifest_path(pack).parent
    rel = _safe_relative_path(source_path, f"source_path de {item.get('name', '?')}")
    return _contained_path(root, rel, f"source_path de {item.get('name', '?')}")


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
    if runtime == "linux-local":
        return Path(home).expanduser()
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
    safe_rel = _safe_relative_path(rel_path, "install.rel_path") if rel_path else PurePosixPath()
    normalized = safe_rel.as_posix() if rel_path else ''
    if normalized == 'skills' or normalized.startswith('skills/'):
        suffix = normalized[len('skills/'): ] if normalized.startswith('skills/') else ''
        base = Path(skills_root) if skills_root else (home_path / 'skills')
        return base / suffix if suffix else base
    if normalized == 'slash-commands' or normalized.startswith('slash-commands/'):
        suffix = normalized[len('slash-commands/'): ] if normalized.startswith('slash-commands/') else ''
        base = Path(slash_root) if slash_root else (home_path / 'slash-commands')
        return base / suffix if suffix else base
    if not rel_path:
        return home_path
    return home_path.joinpath(*safe_rel.parts)


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
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
    ]
    identity_file = str(target.get("identity_file", "")).strip()
    if identity_file:
        command.extend(["-o", "IdentitiesOnly=yes", "-i", os.path.expanduser(identity_file)])
    command.append(f"{user}@{host}")
    return command


def _ssh_run(target: dict[str, Any], command: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    cmd = _ssh_base_command(target) + ["bash", "-lc", shlex.quote(command)]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


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
        f"tmp=$(mktemp /tmp/agent-content-XXXXXX.tgz); "
        f"cat > \"$tmp\"; "
        f"mkdir -p {shlex.quote(dest_home)}; "
        f"dest={shlex.quote(str(PurePosixPath(dest_home) / PurePosixPath(rel_path)))}; "
        f"rm -rf \"$dest\"; mkdir -p \"$(dirname \"$dest\")\"; "
        f"tar -xzf \"$tmp\" -C \"$(dirname \"$dest\")\"; "
        f"base={shlex.quote(source_root.name)}; "
        f"if [ \"$(dirname \"$dest\")/$base\" != \"$dest\" ]; then mv \"$(dirname \"$dest\")/$base\" \"$dest\"; fi; "
        f"rm -f \"$tmp\""
    )
    proc = subprocess.run(_ssh_base_command(target) + ["bash", "-lc", remote_cmd], input=archive_bytes, capture_output=True, timeout=300)
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


def _item_mappings(pack: str, item: dict[str, Any], target: dict[str, Any]) -> tuple[Path | None, Path | None, list[tuple[Path, Path]]]:
    item_dir = _pack_item_dir(pack, item)
    if item_dir.exists():
        _assert_tree_has_no_symlinks(item_dir, f"source tree de {item.get('name', '?')}")
    runtime = _target_runtime(target)
    home = _accessible_home(target)
    if runtime not in {"windows", "wsl", "ssh-linux", "linux-local"}:
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
    safe_rel = _safe_relative_path(rel_path, f"install.rel_path de {item.get('name', '?')}")
    dest_root = home_path.joinpath(*safe_rel.parts)
    for src in sorted(path for path in item_dir.rglob("*") if path.is_file()):
        rel = src.relative_to(item_dir)
        mappings.append((src, dest_root / rel))
    return item_dir, dest_root, mappings


def _validate_item(pack: str, item: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    try:
        _safe_identifier(item.get("name"), "item.name")
    except click.ClickException as exc:
        issues.append(str(exc))
    try:
        item_dir = _pack_item_dir(pack, item)
    except click.ClickException as exc:
        return {"name": item.get("name"), "ok": False, "issues": [str(exc)]}
    files = item.get("files", [])
    if not item_dir.exists():
        return {"name": item.get("name"), "ok": False, "issues": [f"source ausente: {item_dir}"]}
    try:
        _assert_tree_has_no_symlinks(item_dir, f"source tree de {item.get('name', '?')}")
    except click.ClickException as exc:
        issues.append(str(exc))
    declared_paths: set[str] = set()
    for file_entry in files:
        rel = file_entry.get("path")
        expected = file_entry.get("sha256")
        if not rel:
            issues.append("entrada de file sem path")
            continue
        try:
            safe_rel = _safe_relative_path(rel, f"files[].path de {item.get('name', '?')}")
            path = _contained_path(item_dir, safe_rel, f"files[].path de {item.get('name', '?')}")
            declared_paths.add(safe_rel.as_posix())
        except click.ClickException as exc:
            issues.append(str(exc))
            continue
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
    actual_paths = {
        path.relative_to(item_dir).as_posix()
        for path in item_dir.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    for extra in sorted(actual_paths - declared_paths):
        issues.append(f"arquivo não declarado no manifest: {extra}")
    if str(item.get("kind")) == "skill-pack":
        has_skill = any(str(f.get("path", "")).endswith("SKILL.md") for f in files)
        if not has_skill:
            issues.append("skill-pack sem SKILL.md em nenhum subtree")
    else:
        required = item.get("required_files", [])
        for req in required:
            try:
                safe_req = _safe_relative_path(req, f"required_files de {item.get('name', '?')}")
                required_path = _contained_path(item_dir, safe_req, f"required_files de {item.get('name', '?')}")
            except click.ClickException as exc:
                issues.append(str(exc))
                continue
            if not required_path.exists():
                issues.append(f"required file ausente: {req}")
    install = item.get("install", {})
    if isinstance(install, dict):
        for product, entry in install.items():
            if isinstance(entry, dict) and entry.get("rel_path"):
                try:
                    _safe_relative_path(entry["rel_path"], f"install.{product}.rel_path de {item.get('name', '?')}")
                except click.ClickException as exc:
                    issues.append(str(exc))
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
    shutil.copytree(src_root, dst_root, symlinks=True)


def _backup_file(src: Path, backup_root: Path, relative_to: Path) -> None:
    rel = src.relative_to(relative_to)
    dst = backup_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _rollback_local_item(rollback: dict[str, Any]) -> None:
    mode = str(rollback["mode"])
    if mode == "tree":
        destination = Path(rollback["destination"])
        backup = Path(rollback["backup"])
        shutil.rmtree(destination, ignore_errors=True)
        if rollback.get("existed") and backup.exists():
            shutil.copytree(backup, destination, symlinks=True)
        return
    if mode == "files":
        for path in rollback.get("written", []):
            candidate = Path(path)
            if candidate.is_symlink() or candidate.is_file():
                candidate.unlink(missing_ok=True)
        home = Path(rollback["home"])
        backup_root = Path(rollback["backup_root"])
        for raw in rollback.get("backups", []):
            source = Path(raw)
            destination = home / source.relative_to(backup_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return
    raise click.ClickException(f"rollback local desconhecido: {mode}")


def _assert_local_destination_safe(home: Path, destination: Path) -> None:
    home = home.resolve()
    try:
        destination.relative_to(home)
    except ValueError as exc:
        raise click.ClickException(f"destino local fora do home: {destination}") from exc
    cursor = destination
    while cursor != home:
        if cursor.is_symlink():
            raise click.ClickException(f"symlink proibido no destino local: {cursor}")
        cursor = cursor.parent
    if destination.exists() and not destination.is_file() and not destination.is_dir():
        raise click.ClickException(f"destino local não regular: {destination}")


def _run_validate_command(target: dict[str, Any]) -> dict[str, Any]:
    validate = target.get("validate")
    if not isinstance(validate, dict):
        return {"skipped": True, "reason": "no-validate-command"}
    cmd = validate.get("command")
    if not isinstance(cmd, list) or not cmd:
        return {"skipped": True, "reason": "invalid-validate-command"}
    runtime = _target_runtime(target)
    try:
        if runtime in {"windows", "linux-local"}:
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


def _ssh_require_success(result: subprocess.CompletedProcess[str], action: str) -> None:
    if result.returncode == 0:
        return
    detail = (result.stderr or result.stdout or "sem saída").strip()
    raise click.ClickException(f"{action} falhou no target SSH: {detail}")


def _ssh_rollback_item(target: dict[str, Any], rollback: dict[str, str]) -> None:
    mode = rollback["mode"]
    backup_root = rollback["backup_root"]
    if mode == "tree":
        remote_dest = rollback["remote_dest"]
        command = (
            "set -euo pipefail; "
            f"dest={shlex.quote(remote_dest)}; before={shlex.quote(backup_root)}; "
            'if [ -e "$before/tree" ] || [ -L "$before/tree" ]; then '
            'rm -rf "$dest"; mkdir -p "$(dirname "$dest")"; cp -a "$before/tree" "$dest"; '
            'elif [ -f "$before/ABSENT" ]; then rm -rf "$dest"; else exit 0; fi; '
            'rm -f "$before/READY"; touch "$before/ROLLED_BACK"'
        )
    elif mode == "files":
        dest_home = rollback["dest_home"]
        command = (
            "set -euo pipefail; "
            f"home={shlex.quote(dest_home)}; before={shlex.quote(backup_root)}; "
            'if [ ! -f "$before/READY" ]; then exit 0; fi; '
            'if [ -f "$before/absent.list" ]; then '
            'while IFS= read -r -d "" rel; do rm -f -- "$home/$rel"; done < "$before/absent.list"; fi; '
            'test -f "$before/files.tgz"; tar -xzf "$before/files.tgz" -C "$home"; '
            'rm -f "$before/READY"; touch "$before/ROLLED_BACK"'
        )
    else:
        raise click.ClickException(f"rollback SSH desconhecido: {mode}")
    _ssh_require_success(_ssh_run(target, command, timeout=300), "rollback")


def _apply_ssh_item(pack: str, item: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    dest_home = _target_home_str(target)
    item_name = _safe_identifier(item.get("name"), "item.name")
    transaction_root = str(
        PurePosixPath(dest_home)
        / "backups"
        / "agent-content-sync"
        / _timestamp()
        / pack
        / item_name
    )
    backup_root = str(PurePosixPath(transaction_root) / "before")

    if str(item.get("kind")) == "skill-pack":
        source_root = _pack_item_dir(pack, item) / str(target.get("product"))
        if not source_root.exists():
            raise click.ClickException(f"source_root ausente: {source_root}")
        stage = str(PurePosixPath(transaction_root) / "stage" / "payload")
        _ssh_extract_tree(target, source_root, transaction_root, "stage/payload")
        rollback = {
            "mode": "files",
            "backup_root": backup_root,
            "dest_home": dest_home,
        }
        command = (
            "set -euo pipefail; "
            f"home={shlex.quote(dest_home)}; stage={shlex.quote(stage)}; before={shlex.quote(backup_root)}; "
            'mkdir -p "$home" "$before"; '
            'find "$stage" -type f -printf "%P\\0" > "$before/entries.list"; '
            ': > "$before/existing.list"; : > "$before/absent.list"; '
            'while IFS= read -r -d "" rel; do '
            'if [ -e "$home/$rel" ] || [ -L "$home/$rel" ]; then '
            'printf "%s\\0" "$rel" >> "$before/existing.list"; '
            'else printf "%s\\0" "$rel" >> "$before/absent.list"; fi; '
            'done < "$before/entries.list"; '
            'if [ -s "$before/existing.list" ]; then '
            'tar -C "$home" --null -T "$before/existing.list" -czf "$before/files.tgz"; '
            'else tar -C "$home" -czf "$before/files.tgz" --files-from /dev/null; fi; '
            'rollback_files() { '
            'while IFS= read -r -d "" rel; do rm -f -- "$home/$rel"; done < "$before/absent.list"; '
            'tar -xzf "$before/files.tgz" -C "$home"; rm -f "$before/READY"; touch "$before/ROLLED_BACK"; }; '
            "trap 'rc=$?; if [ \"$rc\" -ne 0 ] && [ -f \"$before/READY\" ]; then rollback_files; fi; exit \"$rc\"' EXIT; "
            'touch "$before/READY"; '
            'while IFS= read -r -d "" rel; do '
            'dest="$home/$rel"; tmp="$dest.agent-content.$$"; mkdir -p "$(dirname "$dest")"; '
            'rm -rf "$tmp"; cp -a "$stage/$rel" "$tmp"; mv -Tf "$tmp" "$dest"; '
            'done < "$before/entries.list"; rm -rf "$stage"; trap - EXIT'
        )
    else:
        source_root = _pack_item_dir(pack, item)
        install = item.get("install", {})
        product = str(target.get("product", ""))
        if not isinstance(install, dict) or product not in install:
            raise click.ClickException(f"item sem install para produto {product}: {item_name}")
        rel_path = str(install[product].get("rel_path"))
        remote_dest = str(PurePosixPath(str(_target_root(target, rel_path)).replace("\\", "/")))
        stage = str(PurePosixPath(transaction_root) / "stage" / "tree")
        _ssh_extract_tree(target, source_root, transaction_root, "stage/tree")
        rollback = {
            "mode": "tree",
            "backup_root": backup_root,
            "remote_dest": remote_dest,
        }
        command = (
            "set -euo pipefail; "
            f"dest={shlex.quote(remote_dest)}; stage={shlex.quote(stage)}; before={shlex.quote(backup_root)}; "
            'mkdir -p "$before" "$(dirname "$dest")"; '
            'rollback_tree() { '
            'if [ -e "$before/tree" ] || [ -L "$before/tree" ]; then '
            'rm -rf "$dest"; cp -a "$before/tree" "$dest"; '
            'elif [ -f "$before/ABSENT" ]; then rm -rf "$dest"; fi; '
            'rm -f "$before/READY"; touch "$before/ROLLED_BACK"; }; '
            "trap 'rc=$?; if [ \"$rc\" -ne 0 ]; then rollback_tree; fi; exit \"$rc\"' EXIT; "
            'if [ -e "$dest" ] || [ -L "$dest" ]; then mv "$dest" "$before/tree"; '
            'else touch "$before/ABSENT"; fi; '
            'touch "$before/READY"; mv "$stage" "$dest"'
            '; trap - EXIT'
        )

    result = _ssh_run(target, command, timeout=300)
    if result.returncode != 0:
        try:
            _ssh_rollback_item(target, rollback)
        except click.ClickException:
            pass
        _ssh_require_success(result, "apply")

    try:
        post_status = _compute_diff(pack, item, target)
    except Exception:
        _ssh_rollback_item(target, rollback)
        raise
    if post_status["status"] != "noop":
        _ssh_rollback_item(target, rollback)
        raise click.ClickException(
            f"verificação pós-write falhou para {item_name}; rollback aplicado: {post_status}"
        )
    return {
        "item": item_name,
        "backup_root": backup_root,
        "post_status": post_status,
        "_rollback": rollback,
    }


def _apply_item(pack: str, item: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    runtime = _target_runtime(target)
    if runtime == "ssh-linux":
        return _apply_ssh_item(pack, item, target)
    home = _accessible_home(target) if runtime in {"windows", "wsl", "linux-local"} else None
    source_root, dest_root, mappings = _item_mappings(pack, item, target) if runtime in {"windows", "wsl", "linux-local"} else ( _pack_item_dir(pack, item), None, [] )
    if runtime in {"windows", "wsl", "linux-local"}:
        if home is None:
            raise click.ClickException(f"runtime não suportado para apply local: {target.get('runtime')}")
        backup_root = _backup_root(home) / _timestamp() / pack / str(item.get("name")) / "before"
        backup_root.mkdir(parents=True, exist_ok=True)
        if str(item.get("kind")) == "skill-pack":
            backed_up: list[str] = []
            for _src, dst in mappings:
                _assert_local_destination_safe(home, dst)
                if dst.exists() and not dst.is_file():
                    raise click.ClickException(f"destino local inseguro para skill-pack: {dst}")
                if dst.exists() and dst.is_file():
                    _backup_file(dst, backup_root, home)
                    backed_up.append(str(backup_root / dst.relative_to(home)))
            rollback = {
                "mode": "files",
                "home": str(home),
                "backup_root": str(backup_root),
                "backups": backed_up,
                "written": [str(dst) for _, dst in mappings],
            }
            try:
                for src, dst in mappings:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    temp = dst.with_name(f".{dst.name}.agent-content-{os.getpid()}")
                    temp.unlink(missing_ok=True)
                    shutil.copy2(src, temp)
                    temp.replace(dst)
            except Exception:
                for _src, dst in mappings:
                    dst.with_name(f".{dst.name}.agent-content-{os.getpid()}").unlink(missing_ok=True)
                _rollback_local_item(rollback)
                raise
        else:
            if source_root is None:
                raise click.ClickException(f"item sem source_root: {item.get('name')}")
            if not isinstance(dest_root, Path):
                raise click.ClickException(f"item sem destino resolvido: {item.get('name')}")
            _assert_local_destination_safe(home, dest_root)
            existed = dest_root.exists()
            backup_target = backup_root / dest_root.name
            if existed:
                if backup_target.exists():
                    shutil.rmtree(backup_target)
                shutil.copytree(dest_root, backup_target, symlinks=True)
            rollback = {
                "mode": "tree",
                "destination": str(dest_root),
                "backup": str(backup_target),
                "existed": existed,
            }
            try:
                _copy_tree(source_root, dest_root)
            except Exception:
                _rollback_local_item(rollback)
                raise
        try:
            diff = _compute_diff(pack, item, target)
        except Exception:
            _rollback_local_item(rollback)
            raise
        if diff["status"] != "noop":
            _rollback_local_item(rollback)
            raise click.ClickException(f"verificação pós-write local falhou; rollback aplicado: {diff}")
        return {"item": item.get("name"), "backup_root": str(backup_root), "post_status": diff, "_rollback": rollback}

    raise click.ClickException(f"runtime não suportado para apply: {runtime}")


def _post_status_summary(post: dict[str, Any]) -> str:
    """Render local diffs and SSH acknowledgements without assuming shape."""
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
        if runtime_validation.get("ok") is False:
            raise click.ClickException(
                f"validação do runtime falhou após apply: {runtime_validation}"
            )
    except Exception:
        if _target_runtime(target_cfg) == "ssh-linux":
            for result in reversed(applied):
                rollback = result.get("_rollback")
                if isinstance(rollback, dict):
                    _ssh_rollback_item(target_cfg, rollback)
        elif _target_runtime(target_cfg) in {"windows", "wsl", "linux-local"}:
            for result in reversed(applied):
                rollback = result.get("_rollback")
                if isinstance(rollback, dict):
                    _rollback_local_item(rollback)
        raise
    public_applied = [
        {key: value for key, value in result.items() if key != "_rollback"}
        for result in applied
    ]
    payload = {"pack": pack, "target": target, "mode": "apply", "results": public_applied, "runtime_validation": runtime_validation}
    if json_output:
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        click.echo(f"pack={pack} target={target} mode=apply")
        for item in public_applied:
            post = item['post_status']
            click.echo(f"- {item['item']}: {_post_status_summary(post)}")
            click.echo(f"    backup={item['backup_root']}")
        click.echo(f"runtime_validation={runtime_validation}")


def main() -> None:
    agent_content()
