"""XRDP ABNT2 guard commands for omni.

Mantém o host Ubuntu/XRDP fixo em Português Brasil ABNT2.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

import click

try:
    import grp
except ModuleNotFoundError:  # pragma: no cover - Windows test environment
    grp = None

try:
    import pwd
except ModuleNotFoundError:  # pragma: no cover - Windows test environment
    pwd = None


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "modules" / "xrdp-abnt2"
FILES_DIR = MODULE_DIR / "files"
DEFAULT_USER = os.environ.get("SUDO_USER") or os.environ.get("USER") or "ubuntu"

CANONICAL = {
    "xrdp_keyboard": FILES_DIR / "xrdp_keyboard.ini",
    "km_abnt2": FILES_DIR / "km-abnt2.ini",
    "startwm": FILES_DIR / "startwm.sh",
    "apt_hook": FILES_DIR / "99xrdp-abnt2-keyboard",
    "fix_script": FILES_DIR / "fix-xrdp-abnt2-keyboard",
    "watchdog": FILES_DIR / "setxkbmap-abnt2.sh",
}

SYSTEM_TARGETS = {
    "xrdp_keyboard": Path("/etc/xrdp/xrdp_keyboard.ini"),
    "km_00000409": Path("/etc/xrdp/km-00000409.ini"),
    "km_00010416": Path("/etc/xrdp/km-00010416.ini"),
    "km_0000080a": Path("/etc/xrdp/km-0000080a.ini"),
    "km_0000f010": Path("/etc/xrdp/km-0000f010.ini"),
    "startwm": Path("/etc/xrdp/startwm.sh"),
    "apt_hook": Path("/etc/apt/apt.conf.d/99xrdp-abnt2-keyboard"),
    "fix_script": Path("/usr/local/sbin/fix-xrdp-abnt2-keyboard"),
    "share_xrdp_keyboard": Path("/usr/local/share/xrdp-abnt2/xrdp_keyboard.ini"),
    "share_km_abnt2": Path("/usr/local/share/xrdp-abnt2/km-abnt2.ini"),
    "share_startwm": Path("/usr/local/share/xrdp-abnt2/startwm.sh"),
}

REQUIRED_LAYOUT_SNIPPETS = [
    "rdp_layout_br_abnt2_alt=0x0000F010",
    "rdp_layout_latam=0x0000080A",
    "rdp_layout_br_abnt2=0x00010416",
    "rdp_layout_us=br(abnt2)",
    "rdp_layout_br_abnt2_alt=br(abnt2)",
    "rdp_layout_latam=br(abnt2)",
    "rdp_layout_br_abnt2=br(abnt2)",
]

PREREQUISITE_PACKAGES = [
    "xrdp",
    "xorgxrdp",
    "tigervnc-common",
    "tigervnc-standalone-server",
    "tigervnc-tools",
    "dbus-x11",
    "freerdp2-x11",
    "lxde",
    "lxhotkey-plugin-openbox",
]

PREREQUISITE_COMMANDS = {
    "dbus-launch": "dbus-x11",
    "Xvnc": "tigervnc-standalone-server",
    "startlxde": "lxde",
    "xfreerdp": "freerdp2-x11",
}

REQUIRED_SYSTEMD_UNITS = ("xrdp", "xrdp-sesman")


@click.group(name="xrdp-abnt2")
def xrdp_abnt2() -> None:
    """XRDP keyboard guard: força Português Brasil ABNT2."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _user_home(username: str) -> Path:
    if pwd is None:
        return Path("/home") / username
    try:
        return Path(pwd.getpwnam(username).pw_dir)
    except KeyError:
        return Path("/home") / username


def _user_group(username: str) -> str:
    if pwd is None or grp is None:
        return username
    try:
        user = pwd.getpwnam(username)
        return grp.getgrgid(user.pw_gid).gr_name
    except KeyError:
        return username


def _watchdog_target(username: str) -> Path:
    return _user_home(username) / ".local" / "bin" / "setxkbmap-abnt2.sh"


def _run(args: list[str], *, dry_run: bool = False, env: dict[str, str] | None = None) -> None:
    if dry_run:
        click.echo("DRY  " + " ".join(args))
        return
    subprocess.run(args, check=True, env=env)


def _normalized_bytes(src: Path) -> bytes:
    return src.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _install_file(src: Path, dst: Path, mode: str, owner: str, group: str, dry_run: bool) -> None:
    if dry_run:
        _run(["install", "-o", owner, "-g", group, "-m", mode, str(src), str(dst)], dry_run=True)
        return

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(_normalized_bytes(src))
        tmp_path = Path(tmp.name)

    try:
        _run(["install", "-o", owner, "-g", group, "-m", mode, str(tmp_path), str(dst)])
    finally:
        tmp_path.unlink(missing_ok=True)


def _ensure_root() -> None:
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise click.ClickException("install requer root. Rode: sudo omni xrdp-abnt2 install --yes")


def _copy_if_exists(src: Path, backup_dir: Path) -> None:
    if src.exists():
        rel = str(src).lstrip("/")
        dst = backup_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _installed_packages() -> set[str]:
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Package}\n"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _missing_packages() -> list[str]:
    installed = _installed_packages()
    return [pkg for pkg in PREREQUISITE_PACKAGES if pkg not in installed]


def _command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def _systemctl_state(mode: str, unit: str) -> str:
    result = subprocess.run(
        ["systemctl", mode, unit],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else "unknown"


def _ensure_packages(dry_run: bool) -> list[str]:
    missing = _missing_packages()
    if not missing:
        return []

    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    _run(["apt-get", "update"], dry_run=dry_run, env=env)
    _run(["apt-get", "install", "-y", *missing], dry_run=dry_run, env=env)
    return missing


def _backup_current(username: str, dry_run: bool) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = _user_home(username) / ".backups" / f"xrdp-abnt2-{stamp}"
    paths = list(SYSTEM_TARGETS.values()) + [_watchdog_target(username), Path("/etc/default/keyboard")]
    if dry_run:
        click.echo(f"DRY  backup -> {backup_dir}")
        for p in paths:
            if p.exists():
                click.echo(f"DRY  save {p}")
        return backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    for p in paths:
        _copy_if_exists(p, backup_dir)
    return backup_dir


def _target_specs(username: str) -> list[tuple[Path, Path, str, str, str]]:
    user_group = _user_group(username)
    return [
        (CANONICAL["xrdp_keyboard"], SYSTEM_TARGETS["share_xrdp_keyboard"], "644", "root", "root"),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["share_km_abnt2"], "644", "root", "root"),
        (CANONICAL["startwm"], SYSTEM_TARGETS["share_startwm"], "755", "root", "root"),
        (CANONICAL["fix_script"], SYSTEM_TARGETS["fix_script"], "755", "root", "root"),
        (CANONICAL["apt_hook"], SYSTEM_TARGETS["apt_hook"], "644", "root", "root"),
        (CANONICAL["watchdog"], _watchdog_target(username), "755", username, user_group),
        (CANONICAL["xrdp_keyboard"], SYSTEM_TARGETS["xrdp_keyboard"], "644", "nobody", "nogroup"),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["km_00000409"], "644", "nobody", "nogroup"),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["km_00010416"], "644", "nobody", "nogroup"),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["km_0000080a"], "644", "nobody", "nogroup"),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["km_0000f010"], "644", "nobody", "nogroup"),
        (CANONICAL["startwm"], SYSTEM_TARGETS["startwm"], "755", "nobody", "nogroup"),
    ]


def _check_files_exist(paths: Iterable[Path]) -> list[str]:
    missing = []
    for p in paths:
        if not p.exists():
            missing.append(str(p))
    return missing


def _validation(username: str) -> tuple[bool, list[str], list[str]]:
    ok: list[str] = []
    fail: list[str] = []

    missing_assets = _check_files_exist(CANONICAL.values())
    if missing_assets:
        fail.append("assets ausentes: " + ", ".join(missing_assets))
    else:
        ok.append("assets canônicos presentes")

    bad_canonical_line_endings = [
        str(path)
        for path in CANONICAL.values()
        if path.exists() and b"\r" in path.read_bytes()
    ]
    if bad_canonical_line_endings:
        fail.append("assets canônicos com CRLF: " + ", ".join(bad_canonical_line_endings))
    else:
        ok.append("assets canônicos em LF")

    missing_packages = _missing_packages()
    if missing_packages:
        fail.append("pacotes faltando: " + ", ".join(missing_packages))
    else:
        ok.append("pacotes pré-requisito presentes")

    missing_commands = [
        f"{command} (pacote {package})"
        for command, package in PREREQUISITE_COMMANDS.items()
        if not _command_exists(command)
    ]
    if missing_commands:
        fail.append("comandos ausentes: " + ", ".join(missing_commands))
    else:
        ok.append("comandos pré-requisito presentes")

    live_required = list(SYSTEM_TARGETS.values()) + [_watchdog_target(username)]
    missing_live = _check_files_exist(live_required)
    if missing_live:
        fail.append("arquivos instalados ausentes: " + ", ".join(missing_live))
    else:
        ok.append("arquivos instalados presentes")

    bad_live_line_endings = [
        str(path)
        for path in live_required
        if path.exists() and path.is_file() and b"\r" in path.read_bytes()
    ]
    if bad_live_line_endings:
        fail.append("arquivos live com CRLF: " + ", ".join(bad_live_line_endings))
    else:
        ok.append("arquivos live em LF")

    for unit in REQUIRED_SYSTEMD_UNITS:
        enabled_state = _systemctl_state("is-enabled", unit)
        active_state = _systemctl_state("is-active", unit)
        if enabled_state == "enabled":
            ok.append(f"service {unit} enabled")
        else:
            fail.append(f"service {unit} não está enabled ({enabled_state})")
        if active_state == "active":
            ok.append(f"service {unit} active")
        else:
            fail.append(f"service {unit} não está active ({active_state})")

    keyboard = SYSTEM_TARGETS["xrdp_keyboard"]
    if keyboard.exists():
        text = keyboard.read_text(errors="replace")
        missing_snippets = [s for s in REQUIRED_LAYOUT_SNIPPETS if s not in text]
        if missing_snippets:
            fail.append("xrdp_keyboard.ini sem: " + ", ".join(missing_snippets))
        else:
            ok.append("xrdp_keyboard.ini mapeia Windows RDP -> br(abnt2)")

    km_paths = [
        SYSTEM_TARGETS["km_00000409"],
        SYSTEM_TARGETS["km_00010416"],
        SYSTEM_TARGETS["km_0000080a"],
        SYSTEM_TARGETS["km_0000f010"],
        SYSTEM_TARGETS["share_km_abnt2"],
    ]
    existing_km = [p for p in km_paths if p.exists()]
    if len(existing_km) == len(km_paths):
        hashes = {_sha256(p) for p in existing_km}
        if len(hashes) == 1 and next(iter(hashes)) == _sha256(CANONICAL["km_abnt2"]):
            ok.append("todos os keymaps críticos são ABNT2 idêntico")
        else:
            fail.append("hashes dos keymaps críticos divergem")

    hook = SYSTEM_TARGETS["apt_hook"]
    if hook.exists():
        hook_text = hook.read_text(errors="replace")
        if "/usr/local/sbin/fix-xrdp-abnt2-keyboard" in hook_text:
            ok.append("hook APT/DPKG aponta para reparador")
        else:
            fail.append("hook APT/DPKG não aponta para reparador")

    return (len(fail) == 0, ok, fail)


@xrdp_abnt2.command("paths")
@click.option("--user", "username", default=DEFAULT_USER, show_default=True)
def paths_cmd(username: str) -> None:
    """Lista assets canônicos e destinos instalados."""
    click.echo(f"Module: {MODULE_DIR}")
    click.echo("\nAssets:")
    for name, path in CANONICAL.items():
        click.echo(f"  {name:20} {path}")
    click.echo("\nTargets:")
    for name, path in SYSTEM_TARGETS.items():
        click.echo(f"  {name:20} {path}")
    click.echo(f"  watchdog_user        {_watchdog_target(username)}")


@xrdp_abnt2.command("status")
@click.option("--user", "username", default=DEFAULT_USER, show_default=True)
def status_cmd(username: str) -> None:
    """Mostra estado instalado sem modificar nada."""
    click.echo("XRDP ABNT2 Guard")
    click.echo(f"Module: {MODULE_DIR}")
    for name, path in {**SYSTEM_TARGETS, "watchdog_user": _watchdog_target(username)}.items():
        if path.exists():
            st = path.stat()
            mode = oct(st.st_mode & 0o777)[2:]
            try:
                sha = _sha256(path)[:12]
            except Exception:
                sha = "-"
            click.echo(f"  OK      {name:20} {mode:>3} {st.st_size:>7} {sha} {path}")
        else:
            click.echo(f"  MISSING {name:20} {path}")

    installed_packages = _installed_packages()
    click.echo("\nPackages:")
    for pkg in PREREQUISITE_PACKAGES:
        status = "OK" if pkg in installed_packages else "MISSING"
        click.echo(f"  {status:7} {pkg}")

    click.echo("\nCommands:")
    for command, package in PREREQUISITE_COMMANDS.items():
        resolved = shutil.which(command)
        status = "OK" if resolved else "MISSING"
        suffix = resolved or f"pacote esperado: {package}"
        click.echo(f"  {status:7} {command:12} {suffix}")

    click.echo("\nServices:")
    for unit in REQUIRED_SYSTEMD_UNITS:
        enabled_state = _systemctl_state("is-enabled", unit)
        active_state = _systemctl_state("is-active", unit)
        click.echo(f"  {unit:12} enabled={enabled_state:10} active={active_state}")


@xrdp_abnt2.command("validate")
@click.option("--user", "username", default=DEFAULT_USER, show_default=True)
def validate_cmd(username: str) -> None:
    """Valida a instalação live contra os assets canônicos."""
    success, ok, fail = _validation(username)
    for item in ok:
        click.echo(f"OK   {item}")
    for item in fail:
        click.echo(f"FAIL {item}", err=True)
    if not success:
        raise click.ClickException("XRDP ABNT2 Guard inválido")
    click.echo("PASS XRDP ABNT2 Guard validado")


@xrdp_abnt2.command("diff")
@click.option("--user", "username", default=DEFAULT_USER, show_default=True)
def diff_cmd(username: str) -> None:
    """Mostra diff entre assets canônicos e arquivos instalados."""
    pairs = [
        (CANONICAL["xrdp_keyboard"], SYSTEM_TARGETS["share_xrdp_keyboard"]),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["share_km_abnt2"]),
        (CANONICAL["startwm"], SYSTEM_TARGETS["share_startwm"]),
        (CANONICAL["xrdp_keyboard"], SYSTEM_TARGETS["xrdp_keyboard"]),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["km_00000409"]),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["km_00010416"]),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["km_0000080a"]),
        (CANONICAL["km_abnt2"], SYSTEM_TARGETS["km_0000f010"]),
        (CANONICAL["startwm"], SYSTEM_TARGETS["startwm"]),
        (CANONICAL["apt_hook"], SYSTEM_TARGETS["apt_hook"]),
        (CANONICAL["fix_script"], SYSTEM_TARGETS["fix_script"]),
        (CANONICAL["watchdog"], _watchdog_target(username)),
    ]
    any_diff = False
    for src, dst in pairs:
        if not dst.exists():
            click.echo(f"MISSING {dst}")
            any_diff = True
            continue
        src_lines = src.read_text(errors="replace").splitlines(keepends=True)
        dst_lines = dst.read_text(errors="replace").splitlines(keepends=True)
        diff = list(difflib.unified_diff(src_lines, dst_lines, fromfile=str(src), tofile=str(dst)))
        if diff:
            any_diff = True
            click.echo("".join(diff), nl=False)
    if not any_diff:
        click.echo("CLEAN assets canônicos == instalação live")


@xrdp_abnt2.command("install")
@click.option("--user", "username", default=DEFAULT_USER, show_default=True, help="Usuário da sessão XRDP.")
@click.option("--yes", is_flag=True, help="Confirma instalação sem prompt.")
@click.option("--dry-run", is_flag=True, help="Mostra ações sem escrever.")
@click.option("--skip-packages", is_flag=True, help="Não instala pacotes pré-requisito; só reaplica assets.")
def install_cmd(username: str, yes: bool, dry_run: bool, skip_packages: bool) -> None:
    """Instala/reaplica o guard XRDP ABNT2 com backup prévio."""
    if not dry_run:
        _ensure_root()
    missing_assets = _check_files_exist(CANONICAL.values())
    if missing_assets:
        raise click.ClickException("assets ausentes: " + ", ".join(missing_assets))
    if not yes and not dry_run:
        click.confirm("Instalar/reaplicar XRDP ABNT2 Guard agora?", abort=True)

    backup_dir = _backup_current(username, dry_run=dry_run)
    click.echo(f"Backup: {backup_dir}")

    if skip_packages:
        click.echo("Pacotes pré-requisito: SKIPPED")
    else:
        installed_now = _ensure_packages(dry_run=dry_run)
        if installed_now:
            click.echo("Pacotes pré-requisito garantidos: " + ", ".join(installed_now))
        else:
            click.echo("Pacotes pré-requisito já presentes")

    _run(["install", "-d", "-o", "root", "-g", "root", "-m", "755", "/usr/local/share/xrdp-abnt2"], dry_run=dry_run)
    _run(["install", "-d", "-o", "root", "-g", "root", "-m", "755", "/usr/local/sbin"], dry_run=dry_run)
    home_bin = _watchdog_target(username).parent
    user_group = _user_group(username)
    _run(["install", "-d", "-o", username, "-g", user_group, "-m", "755", str(home_bin)], dry_run=dry_run)

    for src, dst, mode, owner, group in _target_specs(username):
        _install_file(src, dst, mode, owner, group, dry_run=dry_run)

    for unit in REQUIRED_SYSTEMD_UNITS:
        _run(["systemctl", "enable", unit], dry_run=dry_run)

    if dry_run:
        click.echo("DRY-RUN concluído. Nenhum arquivo foi escrito.")
        return

    click.echo("Instalação aplicada. Não reiniciei xrdp; reconecta via RDP para pegar nova sessão.")
    success, ok, fail = _validation(username)
    for item in ok:
        click.echo(f"OK   {item}")
    for item in fail:
        click.echo(f"FAIL {item}", err=True)
    if not success:
        raise click.ClickException("instalado, mas validação falhou")
    click.echo("PASS XRDP ABNT2 Guard instalado e validado")


if __name__ == "__main__":
    xrdp_abnt2()
