"""Omni Routine Dispatcher - Despachante Multi-Host e Roteamento SSH Resiliente."""
from __future__ import annotations

import os
import platform
import re
import shlex
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .routine_engine import (
    MultiPatternRedactor,
    RoutineDefinition,
    RoutineRun,
    RoutineState,
)
from .routine_runner import RoutineRunner


@dataclass
class HostRoute:
    route_type: str  # 'drg_private', 'wireguard', 'casa_wan', 'public_wan'
    user: str
    host: str
    port: int = 22

    @property
    def endpoint(self) -> str:
        return f"{self.user}@{self.host}:{self.port}"


class HostRouteResolver:
    """Resolve rotas ordenadas de acesso SSH a partir do inventário canônico."""

    def __init__(self, inventory_dir: Path | None = None) -> None:
        if inventory_dir is not None:
            self.inventory_dir = Path(inventory_dir)
        else:
            repo_root = Path(__file__).resolve().parents[2]
            self.inventory_dir = repo_root / "inventory" / "hosts"

    def _parse_ssh_target(self, target_str: str, default_user: str = "ubuntu") -> tuple[str, str, int]:
        user = default_user
        port = 22
        host = target_str

        # user@host
        if "@" in host:
            user, host = host.split("@", 1)

        # host:port
        if ":" in host:
            host_part, port_part = host.split(":", 1)
            try:
                port = int(port_part)
                host = host_part
            except ValueError:
                pass

        return user, host, port

    def _find_host_yaml(self, host_name: str) -> dict[str, Any] | None:
        if not self.inventory_dir.exists():
            return None

        # Busca direta por arquivo
        direct_file = self.inventory_dir / f"{host_name}.yaml"
        if direct_file.exists():
            try:
                return yaml.safe_load(direct_file.read_text(encoding="utf-8")) or {}
            except Exception:
                pass

        # Busca por id ou alias
        for yaml_path in self.inventory_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                if data.get("id") == host_name:
                    return data
                aliases = data.get("aliases", [])
                if host_name in aliases:
                    return data
            except Exception:
                continue

        return None

    def resolve_routes(self, host_name: str) -> list[HostRoute]:
        data = self._find_host_yaml(host_name)
        if not data:
            return []

        access = data.get("access", {})
        default_user = "ubuntu"
        ssh_access = access.get("ssh", "")
        if "@" in ssh_access:
            default_user = ssh_access.split("@")[0]

        routes: list[HostRoute] = []

        # 1. Rota Privada Primária (DRG / OCI Private IP)
        oci_private_ip = access.get("oci_private_ip")
        if oci_private_ip:
            routes.append(
                HostRoute(
                    route_type="drg_private",
                    user=default_user,
                    host=oci_private_ip,
                    port=22,
                )
            )

        # 2. Rota WireGuard / VPN IP
        vpn_ip = access.get("vpn_ip")
        if vpn_ip:
            routes.append(
                HostRoute(
                    route_type="wireguard",
                    user=default_user,
                    host=vpn_ip,
                    port=22,
                )
            )

        # 3. Rota Casa WAN SSH (com porta dedicada)
        casa_wan = access.get("casa_wan_ssh")
        if casa_wan:
            u, h, p = self._parse_ssh_target(casa_wan, default_user=default_user)
            routes.append(
                HostRoute(
                    route_type="casa_wan",
                    user=u,
                    host=h,
                    port=p,
                )
            )
        elif access.get("public_ip"):
            # 4. Rota Pública Direta WAN
            routes.append(
                HostRoute(
                    route_type="public_wan",
                    user=default_user,
                    host=access["public_ip"],
                    port=22,
                )
            )

        return routes


class RoutineDispatcher:
    """Despachante inteligente de rotinas com suporte a execução local e remota multi-caminho."""

    SSH_STRICT_OPTS = [
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=3",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "TCPKeepAlive=no",
    ]

    def __init__(
        self,
        inventory_dir: Path | None = None,
        logs_dir: Path | None = None,
        locks_dir: Path | None = None,
        local_hostnames: set[str] | None = None,
    ) -> None:
        self.resolver = HostRouteResolver(inventory_dir=inventory_dir)
        self.local_runner = RoutineRunner(logs_dir=logs_dir, locks_dir=locks_dir)
        self.redactor = MultiPatternRedactor()

        current_host = socket.gethostname().lower()
        self.local_hostnames = {
            "localhost",
            "127.0.0.1",
            "::1",
            "local",
            current_host,
        }
        if local_hostnames:
            self.local_hostnames.update(h.lower() for h in local_hostnames)

    def _is_local(self, target_host: str) -> bool:
        return target_host.lower() in self.local_hostnames

    def dispatch(
        self,
        routine: RoutineDefinition,
        target_host: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> RoutineRun:
        effective_host = target_host or routine.target_host

        # Se for o host local, delega diretamente ao RoutineRunner
        if self._is_local(effective_host):
            return self.local_runner.run(routine, extra_env=extra_env)

        # Execução Remota via SSH Multi-Rota Fallback
        run = RoutineRun(
            routine_id=routine.id,
            target_host=effective_host,
            execution_profile=routine.execution_profile,
        )
        routes = self.resolver.resolve_routes(effective_host)
        if not routes:
            run.transition_to(RoutineState.FAILED, exit_code=1)
            run.stderr = f"[ERROR] Host '{effective_host}' não localizado no inventário ou sem rotas de acesso SSH configuradas."
            self.local_runner._save_run_log(run)
            return run

        run.transition_to(RoutineState.RUNNING)
        failed_attempts: list[dict[str, Any]] = []
        is_windows = platform.system().lower() == "windows"

        remote_cmd_str = shlex.join(routine.command_argv)

        start_total = time.time()
        for route in routes:
            ssh_cmd = [
                "ssh",
                *self.SSH_STRICT_OPTS,
                "-p", str(route.port),
                f"{route.user}@{route.host}",
                remote_cmd_str,
            ]

            popen_kwargs: dict[str, Any] = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
            }
            if is_windows:
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                popen_kwargs["start_new_session"] = True

            t0 = time.time()
            try:
                proc = subprocess.Popen(ssh_cmd, **popen_kwargs)
                stdout, stderr = proc.communicate(timeout=routine.timeout_seconds)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                exit_code = 124
                stderr = (stderr or "") + f"\n[ERROR] Timeout de {routine.timeout_seconds}s excedido via rota {route.route_type}."
            except Exception as e:
                exit_code = 255
                stdout = ""
                stderr = f"Falha de execução do cliente SSH: {e}"

            elapsed = round(time.time() - t0, 3)

            if exit_code == 0:
                # Sucesso nesta rota!
                run.stdout = self.redactor.redact(stdout or "")
                run.stderr = self.redactor.redact(stderr or "")
                run.metrics["duration_seconds"] = round(time.time() - start_total, 3)
                run.metrics["route_used"] = route.route_type
                run.metrics["target_endpoint"] = route.endpoint
                run.metrics["failed_attempts"] = failed_attempts
                run.transition_to(RoutineState.COMPLETED, exit_code=0)
                self.local_runner._save_run_log(run)
                return run
            else:
                failed_attempts.append({
                    "route_type": route.route_type,
                    "endpoint": route.endpoint,
                    "exit_code": exit_code,
                    "duration_seconds": elapsed,
                    "stderr": self.redactor.redact(stderr or "").strip(),
                })

        # Se todas as rotas falharam
        run.metrics["duration_seconds"] = round(time.time() - start_total, 3)
        run.metrics["failed_attempts"] = failed_attempts
        err_details = "\n".join(
            f"  - [{a['route_type']}] {a['endpoint']} (exit {a['exit_code']}): {a['stderr']}"
            for a in failed_attempts
        )
        run.stderr = (
            f"[ERROR] Todas as {len(routes)} rotas SSH falharam para o host '{effective_host}':\n"
            f"{err_details}"
        )
        run.transition_to(RoutineState.FAILED, exit_code=255)
        self.local_runner._save_run_log(run)
        return run
