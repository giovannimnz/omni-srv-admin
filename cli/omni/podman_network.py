"""podman-network — fleet-wide podman networking standard CLI.

Subcommands:
  drift     — show drift across all 3 SRVs (containers.conf + netavark + aardvark + systemd-resolved)
  apply N   — apply the standard to one server (N=1, 2, or 3)
  smoke N   — validate aardvark + DNS on one server
  standard  — print the canonical one-page standard

All subcommands are thin wrappers over scripts in
modules/fleet/podman-network/scripts/. The CLI exists so the
omni-srv-admin style (one entry point, uniform help) covers the
podman networking ops too.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click

REPO = Path(os.environ.get("OMNI_SRV_ADMIN", "/home/ubuntu/GitHub/omni-srv-admin"))
MODULE = REPO / "modules" / "fleet" / "podman-network"
SCRIPTS = MODULE / "scripts"


def _run(script: str, *args: str, host: str | None = None) -> int:
    """Run a script from the module's scripts/ dir."""
    cmd = [str(SCRIPTS / script), *args]
    if host:
        click.echo(f"$ {' '.join(cmd)}  (on {host})", err=True)
    else:
        click.echo(f"$ {' '.join(cmd)}", err=True)
    return subprocess.call(cmd)


@click.group()
def podman_network() -> None:
    """Fleet-wide podman networking standard (containers.conf + netavark + aardvark)."""


@podman_network.command("drift")
def drift() -> None:
    """Show podman networking drift across all 3 SRVs (comparison table)."""
    sys.exit(_run("drift-detect.sh"))


@podman_network.command("apply")
@click.argument("server", type=click.IntRange(1, 3))
def apply(server: int) -> None:
    """Apply the podman networking standard to one SRV (N=1, 2, or 3).

    Idempotent. Backs up containers.conf before any change. Does NOT
    migrate systemd-managed services between networks (use the
    network-migration reference + manual sed for that).
    """
    click.echo(f"=== Applying podman-fleet-standardize to SRV-{server} ===", err=True)
    rc = _run("apply-standardize.sh", str(server))
    if rc == 0:
        click.echo(f"=== OK. Now run: omni podman-network smoke {server} ===", err=True)
    sys.exit(rc)


@podman_network.command("smoke")
@click.argument("server", type=click.IntRange(1, 3))
def smoke(server: int) -> None:
    """Validate aardvark + DNS on one SRV (N=1, 2, or 3).

    Runs a short-lived alpine container, checks that:
    - aardvark-dns comes up
    - /etc/resolv.conf has the correct nameserver
    - self-lookup resolves
    - external lookup resolves (via systemd-resolved forwarding)
    """
    click.echo(f"=== Smoke test SRV-{server} ===", err=True)
    sys.exit(_run("smoke-test.sh", str(server)))


@podman_network.command("standard")
def standard() -> None:
    """Print the canonical one-page podman networking standard."""
    standard_path = MODULE / "STANDARD.md"
    if standard_path.exists():
        click.echo(standard_path.read_text())
    else:
        click.echo(f"ERROR: {standard_path} not found", err=True)
        sys.exit(1)
