"""remote-manager — mounts, remote folders, and desktop Places labels."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote, unquote

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", str(Path(__file__).resolve().parents[2])))
REMOTES_DIR = REPO / "inventory" / "remotes"
DEFAULT_BOOKMARKS = Path.home() / ".config" / "gtk-3.0" / "bookmarks"


def _read_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line or raw.startswith(" "):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def _remote_path(remote_id: str) -> Path:
    path = REMOTES_DIR / f"{remote_id}.yaml"
    if path.exists():
        return path
    matches = sorted(REMOTES_DIR.glob(f"*{remote_id}*.yaml")) if REMOTES_DIR.exists() else []
    if matches:
        return matches[0]
    raise click.ClickException(f"remote não encontrado: {remote_id}")


def _bookmark_uri(path: Path) -> str:
    return "file://" + quote(str(path), safe="/")


def _parse_bookmark_line(line: str) -> tuple[str, str | None]:
    parts = line.rstrip("\n").split(" ", 1)
    uri = parts[0]
    label = parts[1] if len(parts) > 1 else None
    return uri, label


def _replace_yaml_scalar(path: Path, key: str, value: str) -> None:
    lines = path.read_text().splitlines()
    prefix = f"{key}:"
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{key}: {value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}: {value}")
    path.write_text("\n".join(lines) + "\n")


@click.group(name="remote-manager")
def remote_manager() -> None:
    """Gerencia mapeamentos remotos, mounts e labels em Places/PCManFM."""


@remote_manager.command("list")
def list_remotes() -> None:
    """Lista remotes cadastrados em inventory/remotes/*.yaml."""
    if not REMOTES_DIR.exists():
        click.echo(f"remotes dir missing: {REMOTES_DIR}")
        return
    rows = []
    for path in sorted(REMOTES_DIR.glob("*.yaml")):
        data = _read_simple_yaml(path)
        rows.append((
            data.get("id", path.stem),
            data.get("host_id", "?"),
            data.get("type", "?"),
            data.get("display_label", ""),
            data.get("mount_path", ""),
        ))
    click.echo(f"{len(rows)} remote(s) em {REMOTES_DIR}")
    for remote_id, host_id, rtype, label, mount_path in rows:
        click.echo(f"{remote_id:22} {host_id:14} {rtype:8} label={label:16} mount={mount_path}")


@remote_manager.command("show")
@click.argument("remote_id")
def show_remote(remote_id: str) -> None:
    """Mostra o YAML de um remote."""
    click.echo(_remote_path(remote_id).read_text())


@remote_manager.command("places")
@click.option("--bookmarks", type=click.Path(path_type=Path), default=DEFAULT_BOOKMARKS, show_default=True)
def places(bookmarks: Path) -> None:
    """Lista entradas GTK bookmarks usadas pelo PCManFM/LXDE Places."""
    if not bookmarks.exists():
        click.echo(f"bookmarks missing: {bookmarks}")
        return
    for line in bookmarks.read_text().splitlines():
        uri, label = _parse_bookmark_line(line)
        path = unquote(uri.replace("file://", "")) if uri.startswith("file://") else uri
        click.echo(f"{label or '':18} {path}")


@remote_manager.command("rename-label")
@click.argument("remote_id")
@click.argument("new_label")
@click.option("--bookmarks", type=click.Path(path_type=Path), default=DEFAULT_BOOKMARKS, show_default=True)
@click.option("--dry-run", is_flag=True, help="Mostra o que mudaria sem gravar.")
def rename_label(remote_id: str, new_label: str, bookmarks: Path, dry_run: bool) -> None:
    """Renomeia só o label visual do remote em GTK/PCManFM Places.

    Exemplo:
        omni remote-manager rename-label srv1-shared-smb Shared

    Isso altera a entrada `file:///home/ubuntu/Shared_smb Shared_smb` para
    `file:///home/ubuntu/Shared_smb Shared`. O mount path continua estável.
    """
    remote_file = _remote_path(remote_id)
    data = _read_simple_yaml(remote_file)
    mount_path = Path(data.get("mount_path", ""))
    if not mount_path:
        raise click.ClickException(f"remote sem mount_path: {remote_file}")
    uri = _bookmark_uri(mount_path)

    lines = bookmarks.read_text().splitlines() if bookmarks.exists() else []
    new_line = f"{uri} {new_label}"
    changed = False
    output_lines: list[str] = []

    for line in lines:
        current_uri, _label = _parse_bookmark_line(line)
        if current_uri == uri:
            output_lines.append(new_line)
            changed = True
        else:
            output_lines.append(line)

    if not changed:
        output_lines.append(new_line)

    click.echo(f"remote:     {remote_id}")
    click.echo(f"mount_path: {mount_path}")
    click.echo(f"bookmarks:  {bookmarks}")
    click.echo(f"label:      {data.get('display_label', '')} -> {new_label}")
    click.echo(f"action:     {'dry-run' if dry_run else 'write'}")

    if dry_run:
        click.echo(new_line)
        return

    bookmarks.parent.mkdir(parents=True, exist_ok=True)
    bookmarks.write_text("\n".join(output_lines) + "\n")
    _replace_yaml_scalar(remote_file, "display_label", new_label)
    click.echo("ok: label atualizado; mount path preservado")


@remote_manager.command("status")
def status() -> None:
    """Status dos remotes cadastrados e paths principais."""
    click.echo(f"repo:    {REPO}")
    click.echo(f"remotes: {REMOTES_DIR} ({'ok' if REMOTES_DIR.exists() else 'missing'})")
    click.echo(f"gtk:     {DEFAULT_BOOKMARKS} ({'ok' if DEFAULT_BOOKMARKS.exists() else 'missing'})")
    for path in sorted(REMOTES_DIR.glob("*.yaml")) if REMOTES_DIR.exists() else []:
        data = _read_simple_yaml(path)
        mount = Path(data.get("mount_path", "/__missing__"))
        click.echo(f"{data.get('id', path.stem):22} mount={'ok' if mount.exists() else 'missing'} label={data.get('display_label', '')}")
