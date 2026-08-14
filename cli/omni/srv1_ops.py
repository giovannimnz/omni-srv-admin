"""srv1-ops — operações locais centralizadas do ATIUS-SRV-1."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", str(Path(__file__).resolve().parents[2])))
MODULE = REPO / "modules" / "srv1-ops"
SCRIPTS = MODULE / "scripts"
LOG_DIR = Path(os.environ.get("OMNI_LOG_DIR", str(Path.home() / ".logs")))
RESOURCE_CONFIG = MODULE / "configs" / "resource-governor.env"
LIVE_SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
RESOURCE_RUNTIME_CONFIG = Path.home() / ".config" / "omni" / "resource-governor.runtime.env"
RESOURCE_WATCHDOG_STATE = Path.home() / ".local" / "state" / "omni" / "resource-governor-watchdog.json"
RESOURCE_HYGIENE_STATE_DIR = Path.home() / ".local" / "state" / "omni"

SCRIPT_MAP = {
    "sync-vault": SCRIPTS / "sync-vault.sh",
    "backup-gdrive": SCRIPTS / "backup-srv1-to-gdrive.sh",
    "offload-dotbackups": SCRIPTS / "offload-dotbackups-to-gdrive.sh",
    "cleanup-local": SCRIPTS / "cleanup-local.sh",
    "backup-smb": SCRIPTS / "backup-to-smb.sh",
    "atius-web-health": SCRIPTS / "atius-web-healthcheck.sh",
    "resource-status": SCRIPTS / "resource-governor-status.py",
    "resource-snapshot": SCRIPTS / "resource-governor-snapshot.py",
    "resource-audit": SCRIPTS / "resource-governor-audit.py",
    "resource-watchdog": SCRIPTS / "resource-governor-watchdog.py",
    "resource-hygiene": SCRIPTS / "resource-governor-hygiene-queue.py",
    "resource-doctor": SCRIPTS / "resource-governor-doctor.py",
    "resource-reconcile-legacy": SCRIPTS / "resource-governor-reconcile-legacy.sh",
    "cgroup-init": SCRIPTS / "resource-governor-cgroup-init.sh",
    "patcher": SCRIPTS / "resource-governor-patcher.py",
}
PRODUCTION_GUARD_SCRIPT = SCRIPTS / "production_guard.py"

RESOURCE_PROFILE_KEYS = {
    "builds": "BUILDS",
    "interactive": "INTERACTIVE",
    "transfers": "TRANSFERS",
}

RESOURCE_PROFILE_DESCRIPTIONS = {
    "builds": "compiladores, podman build, next build, cargo, make",
    "interactive": "VSCode, Obsidian, Electron/Codex Desktop quando precisa limitar",
    "transfers": "rclone, rsync, backups, offloads",
}

RESOURCE_DEFAULTS = {
    "RG_ROOT_DEVICE": "/dev/sda",
    "RG_LOG_DIR": str(Path.home() / ".logs" / "resource-governor"),
    "RG_POST_BUILD_CLEANUP_DELAY": "5m",
    "RG_POST_BUILD_SNAPSHOT_DELAY": "15m",
    "RG_POST_BUILD_AUDIT_DELAY": "35m",
    "RG_RUNTIME_OVERRIDE_FILE": str(RESOURCE_RUNTIME_CONFIG),
    "RG_WATCHDOG_STATE_FILE": str(RESOURCE_WATCHDOG_STATE),
    "RG_PROFILE_BUILDS_SERIALIZE": "1",
    "RG_PROFILE_BUILDS_QUEUE_TIMEOUT_SEC": "7200",
    "RG_PROFILE_BUILDS_LOCK_FILE": str(RESOURCE_HYGIENE_STATE_DIR / "resource-governor-builds.lock"),
    "RG_ADMISSION_STRUCTURAL_FAIL_CLOSED": "1",
}

RESOURCE_UNIT_NAMES = [
    "omni-builds.slice",
    "omni-interactive.slice",
    "omni-transfers.slice",
    "resource-governor-snapshot.service",
    "resource-governor-snapshot.timer",
    "resource-governor-audit.service",
    "resource-governor-audit.timer",
    "resource-governor-doctor.service",
    "resource-governor-doctor.timer",
    "resource-governor-post-build-cleanup.service",
    "resource-governor-post-build-cleanup.timer",
    "resource-governor-post-build-snapshot.service",
    "resource-governor-post-build-snapshot.timer",
    "resource-governor-post-build-audit.timer",
    "resource-governor-watchdog.service",
    "resource-governor-watchdog.timer",
    "resource-governor-cgroup-init.service",
    "resource-governor-patcher.service",
    "inviolable-watchdog.service",
    "inviolable-watchdog.timer",
]

RESOURCE_ENABLE_TIMERS = [
    "resource-governor-snapshot.timer",
    "resource-governor-audit.timer",
    "resource-governor-doctor.timer",
    "resource-governor-watchdog.timer",
    "inviolable-watchdog.timer",
]

RESOURCE_ENABLE_SERVICES = [
    "resource-governor-cgroup-init.service",
    "resource-governor-watchdog.service",
    "resource-governor-patcher.service",
]

RISKY_EXECUTABLES = {
    "docker",
    "podman",
    "make",
    "cargo",
    "rustc",
    "go",
    "gcc",
    "g++",
    "clang",
    "bun",
    "npm",
    "pnpm",
    "yarn",
    "vite",
    "next",
    "playwright",
    "pip",
    "uv",
}


def _run(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | str | None = None,
) -> int:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(cmd, cwd=str(cwd or Path.home()), env=merged_env)
    return proc.returncode


def _user_systemd_env() -> dict[str, str]:
    env = os.environ.copy()
    runtime_dir = f"/run/user/{os.getuid()}"
    # Desktop/XRDP sessions can export their own session bus under /tmp while
    # omitting XDG_RUNTIME_DIR.  systemctl/systemd-run --user must talk to the
    # systemd user manager on its canonical runtime bus instead.
    env["XDG_RUNTIME_DIR"] = runtime_dir
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"
    return env


def _load_key_value_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _resource_config() -> dict[str, str]:
    data = RESOURCE_DEFAULTS.copy()
    data.update(_load_key_value_file(RESOURCE_CONFIG))
    runtime_override = Path(os.path.expanduser(data.get("RG_RUNTIME_OVERRIDE_FILE", str(RESOURCE_RUNTIME_CONFIG))))
    data.update(_load_key_value_file(runtime_override))
    return data


def _host_cpu_count() -> int:
    return os.cpu_count() or 1


def _profile_cpu_quota(config: dict[str, str], prefix: str) -> str:
    total_pct = config.get(prefix + "CPU_TOTAL_PCT", "")
    if total_pct:
        quota = float(total_pct) * _host_cpu_count()
        return f"{quota:g}%"
    return config.get(prefix + "CPU_QUOTA", "")


def _resource_profile(config: dict[str, str], profile: str) -> dict[str, Any]:
    key = RESOURCE_PROFILE_KEYS[profile]
    prefix = f"RG_PROFILE_{key}_"
    root_device = config.get("RG_ROOT_DEVICE", "/dev/sda")
    props: list[tuple[str, str]] = []
    scalar_map = {
        "CPUQuota": _profile_cpu_quota(config, prefix),
        "CPUWeight": config.get(prefix + "CPU_WEIGHT", ""),
        "MemoryHigh": config.get(prefix + "MEMORY_HIGH", ""),
        "MemoryMax": config.get(prefix + "MEMORY_MAX", ""),
        "MemorySwapMax": config.get(prefix + "MEMORY_SWAP_MAX", ""),
        "IOWeight": config.get(prefix + "IO_WEIGHT", ""),
        "TasksMax": config.get(prefix + "TASKS_MAX", ""),
    }
    for name, value in scalar_map.items():
        if value:
            props.append((name, value))
    read_bw = config.get(prefix + "IO_READ_BW", "")
    write_bw = config.get(prefix + "IO_WRITE_BW", "")
    if root_device and read_bw:
        props.append(("IOReadBandwidthMax", f"{root_device} {read_bw}"))
    if root_device and write_bw:
        props.append(("IOWriteBandwidthMax", f"{root_device} {write_bw}"))
    return {
        "slice": config.get(prefix + "SLICE", f"omni-{profile}.slice"),
        "props": props,
    }


def _is_risky_command(profile: str, command: tuple[str, ...]) -> bool:
    if profile == "builds":
        return True
    if not command:
        return False
    joined = " ".join(command)
    if any(token in joined for token in (" build", " install", " compile", " cargo ", " make ")):
        return True
    return command[0] in RISKY_EXECUTABLES


def _docker_build_warning(command: tuple[str, ...]) -> str | None:
    if len(command) >= 2 and command[0] == "docker" and command[1] == "build":
        return "docker build roda no dockerd root; user scope não limita o builder. Preferir podman build ou estratégia root-level com cgroup-parent."
    if len(command) >= 3 and command[0] == "docker" and command[1] == "buildx" and command[2] == "build":
        return "docker buildx build roda no builder root; user scope não limita o builder. Preferir podman build ou builder dedicado com cgroup-parent."
    if len(command) >= 3 and command[0] == "docker" and command[1] == "compose" and command[2] == "build":
        return "docker compose build herda a limitação do dockerd root; usar podman onde possível ou builder dedicado."
    return None


def _schedule_post_workload_hygiene(config: dict[str, str], reason: str) -> list[str]:
    del config  # Delays are versioned in the three stable timer units.
    proc = subprocess.run(
        ["python3", str(SCRIPT_MAP["resource-hygiene"]), "request", "--reason", reason],
        capture_output=True,
        text=True,
        check=False,
        env=_user_systemd_env(),
    )
    output = (proc.stdout or proc.stderr).strip().splitlines()
    if proc.returncode != 0:
        output.append(f"queue failed rc={proc.returncode}")
    return output or ["queue returned no output"]


def _purge_legacy_post_build_units(*, dry_run: bool, env: dict[str, str]) -> list[str]:
    proc = subprocess.run(
        ["systemctl", "--user", "list-units", "omni-post-build-*", "--all", "--no-legend", "--plain"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    units = sorted({line.split()[0] for line in proc.stdout.splitlines() if line.split()})
    if not units:
        return ["legacy transient post-build units: none"]
    if dry_run:
        return [f"DRY stop/reset {len(units)} legacy transient post-build units"]
    for offset in range(0, len(units), 40):
        batch = units[offset : offset + 40]
        subprocess.run(["systemctl", "--user", "stop", *batch], check=False, env=env)
    failed_services = [unit for unit in units if unit.endswith(".service")]
    for offset in range(0, len(failed_services), 40):
        batch = failed_services[offset : offset + 40]
        subprocess.run(["systemctl", "--user", "reset-failed", *batch], check=False, env=env)
    return [f"stopped/reset {len(units)} legacy transient post-build units"]


def _resource_timers() -> list[str]:
    return RESOURCE_ENABLE_TIMERS.copy()


def _copy_resource_units(*, dry_run: bool) -> list[str]:
    copied: list[str] = []
    for name in RESOURCE_UNIT_NAMES:
        src = MODULE / "systemd" / name
        dst = LIVE_SYSTEMD_DIR / name
        if dry_run:
            copied.append(f"DRY copy {src} -> {dst}")
            continue
        LIVE_SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text())
        copied.append(f"copy {src} -> {dst}")
    return copied


def _install_resource_units(*, dry_run: bool, run_audit_now: bool) -> list[str]:
    env = _user_systemd_env()
    actions = _copy_resource_units(dry_run=dry_run)
    actions.extend(_purge_legacy_post_build_units(dry_run=dry_run, env=env))
    if dry_run:
        actions.append("DRY systemctl --user daemon-reload")
        actions.append("DRY systemctl --user reset-failed resource governor services/timers")
        for timer in RESOURCE_ENABLE_TIMERS:
            actions.append(f"DRY systemctl --user enable --now {timer}")
        actions.append("DRY systemctl --user start resource-governor-snapshot.service")
        for service in RESOURCE_ENABLE_SERVICES:
            suffix = " (daemon)" if service.endswith(("watchdog.service", "patcher.service")) else ""
            actions.append(f"DRY systemctl --user enable --now {service}{suffix}")
        if run_audit_now:
            actions.append("DRY systemctl --user start resource-governor-audit.service")
        return actions

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, env=env)
    subprocess.run(
        ["systemctl", "--user", "reset-failed", *[name for name in RESOURCE_UNIT_NAMES if name.endswith((".service", ".timer"))]],
        check=False,
        env=env,
    )
    actions.append("reset-failed resource governor services/timers")
    for timer in RESOURCE_ENABLE_TIMERS:
        subprocess.run(["systemctl", "--user", "enable", "--now", timer], check=False, env=env)
        actions.append(f"enable-now {timer}")
    subprocess.run(["systemctl", "--user", "start", "resource-governor-snapshot.service"], check=False, env=env)
    actions.append("start resource-governor-snapshot.service")
    for service in RESOURCE_ENABLE_SERVICES:
        subprocess.run(["systemctl", "--user", "enable", "--now", service], check=False, env=env)
        suffix = " (daemon)" if service.endswith(("watchdog.service", "patcher.service")) else ""
        actions.append(f"enable-now {service}{suffix}")
    if run_audit_now:
        subprocess.run(["systemctl", "--user", "start", "resource-governor-audit.service"], check=False, env=env)
        actions.append("start resource-governor-audit.service")
    return actions


@click.group(name="srv1-ops")
def srv1_ops() -> None:
    """Operações locais do ATIUS-SRV-1 gerenciadas pelo omni-srv-admin."""


@srv1_ops.command("list")
def list_ops() -> None:
    """Lista scripts operacionais gerenciados pelo módulo."""
    click.echo(f"module: {MODULE}")
    click.echo(f"logs:   {LOG_DIR}")
    for name, path in SCRIPT_MAP.items():
        status = "ok" if path.exists() else "missing"
        click.echo(f"{name:18} {status:8} {path}")


@srv1_ops.command("run")
@click.argument("name", type=click.Choice(sorted(SCRIPT_MAP.keys())))
@click.option("--dry-run", is_flag=True, help="Define DRY_RUN=1 quando suportado.")
def run_op(name: str, dry_run: bool) -> None:
    """Executa um script operacional por nome."""
    path = SCRIPT_MAP[name]
    if not path.exists():
        raise click.ClickException(f"script não encontrado: {path}")
    env = {"DRY_RUN": "1"} if dry_run else None
    if name == "resource-audit":
        raise SystemExit(
            _run(
                ["systemctl", "--user", "start", "resource-governor-audit.service"],
                env=_user_systemd_env(),
            )
        )
    if name.startswith("resource-") and path.suffix == ".py":
        raise SystemExit(_run(["python3", str(path)], env=env))
    raise SystemExit(_run([str(path)], env=env))


@srv1_ops.command("logs")
@click.option("--limit", default=20, show_default=True, help="Linhas por log.")
def logs(limit: int) -> None:
    """Mostra tail dos logs operacionais em ~/.logs."""
    if not LOG_DIR.exists():
        click.echo(f"sem diretório de logs: {LOG_DIR}")
        return
    logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        click.echo(f"sem *.log em {LOG_DIR}")
        return
    for log in logs[:8]:
        click.echo(f"\n==> {log}")
        subprocess.run(["tail", f"-{limit}", str(log)], check=False)


@srv1_ops.command("status")
def status() -> None:
    """Status rápido: timers, logs, scripts e GDrive skeleton."""
    click.echo(f"module: {MODULE} ({'ok' if MODULE.exists() else 'missing'})")
    click.echo(f"logs:   {LOG_DIR} ({'ok' if LOG_DIR.exists() else 'missing'})")
    click.echo(f"resource-config: {RESOURCE_CONFIG} ({'ok' if RESOURCE_CONFIG.exists() else 'missing'})")
    subprocess.run(["systemctl", "--user", "list-timers", "--all"], check=False, env=_user_systemd_env())


def _run_production_guard(command: str, *, json_output: bool = False, extra_args: list[str] | None = None) -> None:
    if not PRODUCTION_GUARD_SCRIPT.exists():
        raise click.ClickException(f"script não encontrado: {PRODUCTION_GUARD_SCRIPT}")
    args = ["python3", str(PRODUCTION_GUARD_SCRIPT), command]
    if json_output:
        args.append("--json")
    if extra_args:
        args.extend(extra_args)
    raise SystemExit(_run(args))


@srv1_ops.group("production-guard")
def production_guard() -> None:
    """Validador read-only de PM2/elements de boot para ATS e Horistic."""


@production_guard.command("status")
@click.option("--json/--no-json", "json_output", default=False, show_default=True, help="Emite JSON")
def production_guard_status(json_output: bool) -> None:
    """Executa `production_guard status --json`."""
    _run_production_guard("status", json_output=json_output)


@production_guard.command("doctor")
@click.option("--json/--no-json", "json_output", default=False, show_default=True, help="Emite JSON")
def production_guard_doctor(json_output: bool) -> None:
    """Executa `production_guard doctor --json`."""
    _run_production_guard("doctor", json_output=json_output)


@production_guard.command("repair")
@click.option("--json/--no-json", "json_output", default=False, show_default=True, help="Emite JSON")
@click.option("--dry-run/--apply", "dry_run", default=True, show_default=True, help="Dry-run por default; apply exige checkpoint explícito.")
@click.option("--scope", help="Escopo exato da ação permitida.")
@click.option("--target", help="Target exato da ação permitida.")
@click.option(
    "--yes-i-understand-production-risk",
    "risk_ack",
    is_flag=True,
    help="Confirma explicitamente o risco de produção para liberar apply.",
)
def production_guard_repair(
    json_output: bool,
    dry_run: bool,
    scope: str | None,
    target: str | None,
    risk_ack: bool,
) -> None:
    """Executa `production_guard repair` com gate explícito para apply."""
    extra_args: list[str] = ["--dry-run"] if dry_run else ["--apply"]
    if scope:
        extra_args.extend(["--scope", scope])
    if target:
        extra_args.extend(["--target", target])
    if risk_ack:
        extra_args.append("--yes-i-understand-production-risk")
    _run_production_guard("repair", json_output=json_output, extra_args=extra_args)


@srv1_ops.group("resources")
def resources() -> None:
    """Governança de recursos, wraps cgroup/systemd e observabilidade local."""


@resources.command("profiles")
def resource_profiles() -> None:
    """Mostra os perfis de limitação disponíveis."""
    config = _resource_config()
    click.echo(f"config: {RESOURCE_CONFIG}")
    click.echo(f"root-device: {config.get('RG_ROOT_DEVICE', '/dev/sda')}")
    click.echo(f"logs: {config.get('RG_LOG_DIR')}")
    for profile in ("builds", "interactive", "transfers"):
        pdata = _resource_profile(config, profile)
        click.echo("")
        click.echo(f"[{profile}] {RESOURCE_PROFILE_DESCRIPTIONS[profile]}")
        click.echo(f"slice: {pdata['slice']}")
        for name, value in pdata["props"]:
            click.echo(f"  - {name}={value}")


@resources.command("run")
@click.argument("profile", type=click.Choice(sorted(RESOURCE_PROFILE_KEYS.keys())))
@click.option("--dry-run", is_flag=True, help="Só mostra o systemd-run montado.")
@click.option("--schedule-hygiene/--no-schedule-hygiene", default=None, help="Agenda cleanup+snapshot+audit pós-workload quando fizer sentido.")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def resource_run(profile: str, dry_run: bool, schedule_hygiene: bool | None, command: tuple[str, ...]) -> None:
    """Roda um comando dentro de um profile de recursos.

    Exemplo:
        omni srv1-ops resources run builds -- podman build -t my-app .
    """
    if not command:
        raise click.ClickException("faltou o comando após --")

    config = _resource_config()
    pdata = _resource_profile(config, profile)
    cmd = [
        "systemd-run",
        "--user",
        "--scope",
        "--collect",
        "--same-dir",
        f"--slice={pdata['slice']}",
    ]
    for name, value in pdata["props"]:
        cmd.extend(["-p", f"{name}={value}"])
    if profile == "builds" and config.get("RG_PROFILE_BUILDS_SERIALIZE", "1") == "1":
        lock_path = Path(os.path.expanduser(config["RG_PROFILE_BUILDS_LOCK_FILE"]))
        queue_timeout = config.get("RG_PROFILE_BUILDS_QUEUE_TIMEOUT_SEC", "7200")
        cmd.extend(["/usr/bin/flock", f"--wait={queue_timeout}", str(lock_path)])
    cmd.extend(command)

    warning = _docker_build_warning(command)
    if warning:
        click.echo(f"WARN: {warning}", err=True)

    risky = _is_risky_command(profile, command)
    should_schedule = risky if schedule_hygiene is None else schedule_hygiene
    if os.environ.get("OMNI_RESOURCE_HYGIENE_ACTIVE") == "1":
        should_schedule = False

    click.echo(f"profile: {profile}")
    click.echo(f"slice:   {pdata['slice']}")
    click.echo(f"cmd:     {shlex.join(cmd)}")
    if dry_run:
        if should_schedule:
            click.echo(
                "post-run hygiene: cleanup-local(build-hygiene) + snapshot + audit "
                f"em +{config.get('RG_POST_BUILD_CLEANUP_DELAY')} / +{config.get('RG_POST_BUILD_SNAPSHOT_DELAY')} / +{config.get('RG_POST_BUILD_AUDIT_DELAY')}"
            )
        return

    # systemd 249 user instance bug: CPUQuota/IO*BandwidthMax não são escritos
    # nos cgroups. Forçamos limites via cgroup-init antes de rodar.
    _run(["bash", str(SCRIPT_MAP["cgroup-init"])], env=_user_systemd_env())

    if profile == "builds" and config.get("RG_ADMISSION_STRUCTURAL_FAIL_CLOSED", "1") == "1":
        admission_rc = _run(
            ["python3", str(SCRIPT_MAP["resource-doctor"]), "--admission"],
            env=_user_systemd_env(),
        )
        if admission_rc != 0:
            raise click.ClickException(
                "admission gate recusou o build: execute `omni srv1-ops resources doctor` "
                "e corrija as falhas estruturais antes de continuar"
            )

    if profile == "builds" and config.get("RG_PROFILE_BUILDS_SERIALIZE", "1") == "1":
        Path(os.path.expanduser(config["RG_PROFILE_BUILDS_LOCK_FILE"])).parent.mkdir(parents=True, exist_ok=True)

    rc = _run(cmd, env=_user_systemd_env(), cwd=Path.cwd())
    if should_schedule:
        scheduled = _schedule_post_workload_hygiene(config, reason=f"profile={profile}")
        click.echo("post-run hygiene:")
        for item in scheduled:
            click.echo(f"  - {item}")
    raise SystemExit(rc)


@resources.command("status")
def resource_status() -> None:
    """Mostra status do resource governor e últimos snapshots."""
    raise SystemExit(_run(["python3", str(SCRIPT_MAP["resource-status"])]))


@resources.command("snapshot")
def resource_snapshot() -> None:
    """Gera snapshot leve agora."""
    raise SystemExit(_run(["python3", str(SCRIPT_MAP["resource-snapshot"])]))


@resources.command("audit")
def resource_audit() -> None:
    """Gera audit pesado agora, contido na slice e protegido por singleton."""
    raise SystemExit(_run(["systemctl", "--user", "start", "resource-governor-audit.service"], env=_user_systemd_env()))


@resources.command("queue")
@click.option("--json-output", is_flag=True, help="Exibe o estado da fila em JSON.")
def resource_queue(json_output: bool) -> None:
    """Mostra a fila coalescente de hygiene pós-build."""
    cmd = ["python3", str(SCRIPT_MAP["resource-hygiene"]), "status"]
    if json_output:
        cmd.append("--json")
    raise SystemExit(_run(cmd, env=_user_systemd_env()))


@resources.command("watchdog")
def resource_watchdog() -> None:
    """Roda o watchdog uma vez agora."""
    raise SystemExit(_run(["python3", str(SCRIPT_MAP["resource-watchdog"])]))


@resources.command("doctor")
@click.option("--json-output", is_flag=True, help="Emite o relatório estruturado em JSON.")
@click.option("--admission", is_flag=True, help="Retorna erro se um novo build não puder ser admitido.")
def resource_doctor(json_output: bool, admission: bool) -> None:
    """Valida quota, conflitos legados, escapes, fila, audit e pressão."""
    cmd = ["python3", str(SCRIPT_MAP["resource-doctor"])]
    if json_output:
        cmd.append("--json")
    if admission:
        cmd.append("--admission")
    raise SystemExit(_run(cmd, env=_user_systemd_env()))


@resources.command("install")
@click.option("--dry-run", is_flag=True, help="Mostra copy/enable sem aplicar.")
@click.option("--run-audit-now/--no-run-audit-now", default=True, help="Roda audit inicial após instalar timers.")
def resource_install(dry_run: bool, run_audit_now: bool) -> None:
    """Instala as slices/timers/serviços do resource governor no systemd user live."""
    actions = _install_resource_units(dry_run=dry_run, run_audit_now=run_audit_now)
    click.echo(f"live-systemd-dir: {LIVE_SYSTEMD_DIR}")
    for item in actions:
        click.echo(f"- {item}")


@resources.command("reconcile-legacy")
@click.option("--apply", is_flag=True, help="Aplica após backup; sem esta flag é dry-run.")
def resource_reconcile_legacy(apply: bool) -> None:
    """Remove o scanner per-PID e o fan-out timestampado legados."""
    cmd = [str(SCRIPT_MAP["resource-reconcile-legacy"])]
    if apply:
        cmd.append("--apply")
    raise SystemExit(_run(cmd, env=_user_systemd_env()))


@resources.command("logs")
@click.option("--limit", default=40, show_default=True, help="Linhas por arquivo.")
def resource_logs(limit: int) -> None:
    """Mostra tail dos logs do resource governor."""
    log_dir = Path(os.path.expanduser(_resource_config().get("RG_LOG_DIR", str(Path.home() / ".logs" / "resource-governor"))))
    if not log_dir.exists():
        click.echo(f"sem diretório de logs: {log_dir}")
        return
    files = []
    for name in ("watchdog.log", "latest.txt", "latest-audit.txt"):
        path = log_dir / name
        if path.exists():
            files.append(path)
    if not files:
        click.echo(f"sem logs esperados em {log_dir}")
        return
    for path in files:
        click.echo(f"\n==> {path}")
        subprocess.run(["tail", f"-{limit}", str(path)], check=False)
