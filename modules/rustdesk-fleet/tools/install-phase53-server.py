#!/usr/bin/env python3
"""Transactional, closed-ingress RustDesk server installer for Phase 53."""

from __future__ import annotations

import argparse
import base64
import binascii
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Iterator


DAILY_LOG_BYTES = 134_217_728
LOG_RETENTION_DAYS = 30
MAX_PROCESS_STDOUT = 128 * 1024
MAX_PROCESS_STDERR = 8 * 1024
MAX_SQLITE_BYTES = 4_294_957_056
MUTATION_BOUNDARIES = ("prestate", "identity", "units", "linger", "reload", "start")
SERVER_REFERENCES = (
    ("kv/atius/rustdesk/server", "private_key"),
    ("kv/atius/rustdesk/server", "public_key"),
    ("kv/atius/rustdesk/targets/atius-srv-1", "permanent_password"),
    ("kv/atius/rustdesk/targets/atius-srv-2", "permanent_password"),
    ("kv/atius/rustdesk/targets/atius-srv-3", "permanent_password"),
    ("kv/atius/rustdesk/targets/horistic-srv", "permanent_password"),
    ("kv/atius/rustdesk/targets/giovanni-w11-pc", "permanent_password"),
)
EXPECTED_VALUE_KEYS = {f"{path}#{field}" for path, field in SERVER_REFERENCES}
UNIT_NAMES = (
    "atius-rustdesk-server-hbbs.container",
    "atius-rustdesk-server-hbbr.container",
    "atius-rustdesk-phase53.slice",
    "atius-rustdesk-server-logrotate.service",
    "atius-rustdesk-server-logrotate.timer",
)
SERVICE_UNITS = (
    "atius-rustdesk-server-hbbs.service",
    "atius-rustdesk-server-hbbr.service",
    "atius-rustdesk-server-logrotate.timer",
)
ARCHIVE_RE = re.compile(r"^(hbbs|hbbr)-(\d{8})\.log$")
os.umask(0o077)


def _strict_json_file(path: Path) -> dict[str, Any]:
    """Read a candidate contract without accepting duplicate keys or links."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in items:
            if key in payload:
                raise Phase53ServerBlocked("candidate-contract-duplicate-key")
            payload[key] = value
        return payload

    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or not 0 < info.st_size <= 1_048_576:
            raise Phase53ServerBlocked("candidate-contract-invalid")
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except Phase53ServerBlocked:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase53ServerBlocked("candidate-contract-invalid") from exc
    if not isinstance(payload, dict):
        raise Phase53ServerBlocked("candidate-contract-invalid")
    return payload


def select_runtime_candidate(repo: Path, environ: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Return the successor runtime only with explicit owner-bound admission."""

    environment = os.environ if environ is None else environ
    if environment.get("ADMITTED_PHASE53") != "1":
        return None
    root = repo.resolve(strict=True) / "modules/rustdesk-fleet"
    candidate = _strict_json_file(root / "contracts/phase53-runtime-candidate.json")
    admission = _strict_json_file(root / "evidence/phase53/candidate-admission.json")
    if candidate.get("candidate_status_required") != "ADMITTED_PHASE53":
        raise Phase53ServerBlocked("candidate-contract-state-invalid")
    if admission.get("candidate_status") != "ADMITTED_PHASE53" or admission.get("admission_performed") is not True:
        raise Phase53ServerBlocked("candidate-admission-required")
    if admission.get("live_mutation_performed") is not False:
        raise Phase53ServerBlocked("candidate-live-state-invalid")
    upstream = candidate.get("upstream")
    if not isinstance(upstream, dict) or not isinstance(upstream.get("immutable_reference"), str):
        raise Phase53ServerBlocked("candidate-upstream-invalid")
    return candidate


def relay_endpoint_from_edge_contract(repo: Path) -> str:
    """Derive the public hbbr announcement from the sole edge contract."""

    root = repo.resolve(strict=True) / "modules/rustdesk-fleet"
    edge = _strict_json_file(root / "contracts/phase53-edge.json")
    try:
        records = [
            item
            for item in edge["dns_records"]
            if isinstance(item, dict) and item.get("role") == "relay"
        ]
        mappings = [
            item
            for item in edge["translations"]
            if isinstance(item, dict)
            and item.get("role") == "relay"
            and item.get("protocol") == "tcp"
        ]
        if (
            edge.get("schema_version") != 2
            or edge.get("target")
            != {
                "private_ipv4": "10.21.1.21",
                "reserved_public_ipv4": "137.131.140.20",
            }
            or len(records) != 1
            or len(mappings) != 1
            or records[0]
            != {
                "name": "rustdesk-relay.atius.com.br",
                "role": "relay",
                "type": "A",
                "content": "137.131.140.20",
                "proxied": False,
            }
            or mappings[0]
            != {
                "role": "relay",
                "protocol": "tcp",
                "external_port": 34101,
                "internal_port": 21117,
            }
        ):
            raise Phase53ServerBlocked("edge-contract-invalid")
        return f"{records[0]['name']}:{mappings[0]['external_port']}"
    except (KeyError, TypeError) as exc:
        raise Phase53ServerBlocked("edge-contract-invalid") from exc


class Phase53ServerBlocked(RuntimeError):
    """A fail-closed server transaction blocker."""


Runner = Callable[..., tuple[int, bytes, bytes]]


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.SubprocessError:
        pass


def bounded_process(
    argv: list[str],
    request: bytes | None = None,
    *,
    timeout: float = 30,
    stdout_limit: int = MAX_PROCESS_STDOUT,
) -> tuple[int, bytes, bytes]:
    """Run an argv-only command with stdin isolation, timeout and output ceilings."""
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise Phase53ServerBlocked("command-invalid")
    process: subprocess.Popen[bytes] | None = None
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE if request is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
        if request is not None:
            assert process.stdin is not None
            process.stdin.write(request)
            process.stdin.close()
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, ("stdout", stdout_limit))
        selector.register(process.stderr, selectors.EVENT_READ, ("stderr", MAX_PROCESS_STDERR))
        chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
        sizes = {"stdout": 0, "stderr": 0}
        deadline = time.monotonic() + timeout
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            events = selector.select(remaining)
            if not events:
                raise TimeoutError
            for key, _ in events:
                stream, limit = key.data
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                sizes[stream] += len(chunk)
                if sizes[stream] > limit:
                    raise Phase53ServerBlocked("command-output-too-large")
                chunks[stream].append(chunk)
        remaining = max(0.001, deadline - time.monotonic())
        return process.wait(timeout=remaining), b"".join(chunks["stdout"]), b"".join(chunks["stderr"])
    except Phase53ServerBlocked:
        raise
    except (BrokenPipeError, OSError, subprocess.SubprocessError, TimeoutError) as exc:
        raise Phase53ServerBlocked("command-failed") from exc
    finally:
        selector.close()
        if process is not None:
            _kill_group(process)


def ssh_argv(host: str, remote_argv: list[str]) -> list[str]:
    """Return the only accepted remote transport shape: batch, stdin-safe SSH."""
    if not host or not remote_argv or any("\n" in item for item in remote_argv):
        raise Phase53ServerBlocked("ssh-command-invalid")
    return [
        "ssh",
        "-n",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "--",
        host,
        *remote_argv,
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write(
        path,
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        0o600,
    )


def sqlite_observation(path: Path) -> dict[str, Any]:
    """Return a value-free integrity observation without mutating SQLite state."""
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_SQLITE_BYTES:
        raise Phase53ServerBlocked("sqlite-identity-invalid")
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10) as database:
            integrity = database.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise Phase53ServerBlocked("sqlite-integrity-failed") from exc
    if integrity != ("ok",):
        raise Phase53ServerBlocked("sqlite-integrity-failed")
    return {"sha256": _sha256(path), "size_bytes": info.st_size, "integrity": "ok"}


def _secure_log(path: Path) -> None:
    if not path.exists():
        _atomic_write(path, b"", 0o600)
        return
    info = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise Phase53ServerBlocked("log-identity-invalid")
    os.chmod(path, 0o600)


def enforce_log_bounds(
    log_dir: Path,
    *,
    daily_bytes: int = DAILY_LOG_BYTES,
    retention_days: int = LOG_RETENTION_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rotate only the two authoritative logs and cap each UTC-day archive."""
    if daily_bytes <= 0 or retention_days <= 0:
        raise Phase53ServerBlocked("log-policy-invalid")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise Phase53ServerBlocked("log-timezone-invalid")
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(log_dir, 0o700)
    cutoff = instant.date() - timedelta(days=retention_days)
    deleted = 0
    for path in log_dir.iterdir():
        match = ARCHIVE_RE.fullmatch(path.name)
        if not match:
            continue
        _secure_log(path)
        archive_date = datetime.strptime(match.group(2), "%Y%m%d").date()
        if archive_date < cutoff:
            path.unlink()
            deleted += 1

    stamp = instant.astimezone(timezone.utc).strftime("%Y%m%d")
    archives = {name: log_dir / f"{name}-{stamp}.log" for name in ("hbbs", "hbbr")}
    used_today = 0
    for archive in archives.values():
        if archive.exists():
            _secure_log(archive)
            used_today += archive.stat().st_size
    if used_today > daily_bytes:
        raise Phase53ServerBlocked("log-daily-bound-drift")

    rotated = 0
    for name in ("hbbs", "hbbr"):
        current = log_dir / f"{name}.log"
        _secure_log(current)
        size = current.stat().st_size
        if size:
            remaining = max(0, daily_bytes - used_today)
            amount = min(size, remaining)
            if amount:
                with current.open("rb") as source:
                    source.seek(size - amount)
                    data = source.read(amount)
                archive = archives[name]
                if archive.exists():
                    with archive.open("ab") as output:
                        output.write(data)
                        output.flush()
                        os.fsync(output.fileno())
                else:
                    _atomic_write(archive, data, 0o600)
                used_today += amount
                rotated += amount
            with current.open("r+b") as output:
                output.truncate(0)
                output.flush()
                os.fsync(output.fileno())
    if used_today > daily_bytes:
        raise Phase53ServerBlocked("log-daily-bound-drift")
    return {
        "daily_limit_bytes": daily_bytes,
        "retention_days": retention_days,
        "rotated_bytes": rotated,
        "today_archive_bytes": used_today,
        "deleted_archives": deleted,
        "secret_material_present": False,
    }


class Phase53ServerTransaction:
    """Install and roll back the rootless server domain with public ingress closed."""

    def __init__(
        self,
        *,
        repo: Path,
        home: Path,
        runtime_dir: Path,
        uid: int | None = None,
        command_runner: Runner = bounded_process,
        provider_exchange: Callable[[], dict[str, str]] | None = None,
        tmpfs_checker: Callable[[Path], bool] | None = None,
        fault_after: str | None = None,
    ) -> None:
        self.repo = repo.resolve()
        self.home = home.resolve()
        self.runtime_dir = runtime_dir.resolve()
        self.uid = os.getuid() if uid is None else uid
        self.command_runner = command_runner
        self.provider_exchange = provider_exchange or self._provider_exchange
        self.tmpfs_checker = tmpfs_checker or self._runtime_is_tmpfs
        if fault_after is not None and fault_after not in MUTATION_BOUNDARIES:
            raise Phase53ServerBlocked("fault-boundary-invalid")
        self.fault_after = fault_after
        self.transaction_id = os.urandom(16).hex()
        self.quadlet_dir = self.home / ".config/containers/systemd"
        self.user_unit_dir = self.home / ".config/systemd/user"
        self.state_dir = self.home / ".local/share/atius-rustdesk/server/state"
        self.log_dir = self.home / ".local/state/atius-rustdesk/server/logs"
        self.identity_dir = self.runtime_dir / "atius-rustdesk/server-identity"
        self.rollback_dir = (
            self.home / ".local/share/atius-rustdesk/server/rollback" / self.transaction_id
        )
        self.library_target = self.home / ".local/lib/atius-rustdesk/install-phase53-server.py"
        self.lock_path = self.runtime_dir / "atius-rustdesk/server-install.lock"
        self._prestate: dict[str, Any] | None = None
        self._linger_enabled_by_transaction = False
        self._installed = False
        self._rolled_back = False
        self.runtime_candidate = select_runtime_candidate(self.repo)
        self.relay_endpoint = relay_endpoint_from_edge_contract(self.repo)

    @property
    def _sources(self) -> dict[Path, Path]:
        root = self.repo / "modules/rustdesk-fleet"
        return {
            root / "quadlets/atius-rustdesk-server-hbbs.container": self.quadlet_dir
            / "atius-rustdesk-server-hbbs.container",
            root / "quadlets/atius-rustdesk-server-hbbr.container": self.quadlet_dir
            / "atius-rustdesk-server-hbbr.container",
            root / "systemd/atius-rustdesk-phase53.slice": self.user_unit_dir
            / "atius-rustdesk-phase53.slice",
            root / "systemd/atius-rustdesk-server-logrotate.service": self.user_unit_dir
            / "atius-rustdesk-server-logrotate.service",
            root / "systemd/atius-rustdesk-server-logrotate.timer": self.user_unit_dir
            / "atius-rustdesk-server-logrotate.timer",
            Path(__file__).resolve(): self.library_target,
        }

    def _run(self, argv: list[str], request: bytes | None = None, *, timeout: float = 30) -> bytes:
        code, stdout, stderr = self.command_runner(
            argv, request, timeout=timeout, stdout_limit=MAX_PROCESS_STDOUT
        )
        if code or stderr:
            raise Phase53ServerBlocked("command-contract-failed")
        return stdout

    def _runtime_is_tmpfs(self, path: Path) -> bool:
        stdout = self._run(["stat", "--file-system", "--format=%T", str(path)])
        return stdout.strip() in {b"tmpfs", b"ramfs"}

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Phase53ServerBlocked("transaction-lock-held") from exc
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _checkpoint(self, boundary: str) -> None:
        if self.fault_after == boundary:
            raise Phase53ServerBlocked(f"fault-injected-{boundary}")

    def _linger(self) -> bool:
        output = self._run(
            ["loginctl", "show-user", str(self.uid), "--property=Linger", "--value"]
        ).strip()
        if output not in {b"yes", b"no"}:
            raise Phase53ServerBlocked("linger-state-invalid")
        return output == b"yes"

    def _account(self) -> str:
        if self.home.parent == Path("/home") and self.home.name:
            return self.home.name
        return str(self.uid)

    def snapshot_prestate(self) -> dict[str, Any]:
        if self._prestate is not None:
            return self._prestate
        if self.identity_dir.exists() or self.identity_dir.is_symlink():
            raise Phase53ServerBlocked("runtime-identity-preexists")
        files: dict[str, dict[str, Any]] = {}
        self.rollback_dir.mkdir(parents=True, mode=0o700)
        backup_dir = self.rollback_dir / "unit-prestate"
        backup_dir.mkdir(mode=0o700)
        for index, destination in enumerate(self._sources.values()):
            entry: dict[str, Any] = {"existed": False}
            if destination.exists() or destination.is_symlink():
                info = destination.lstat()
                if destination.is_symlink() or not stat.S_ISREG(info.st_mode):
                    raise Phase53ServerBlocked("unit-prestate-invalid")
                backup = backup_dir / f"{index:02d}.bin"
                _atomic_write(backup, destination.read_bytes(), stat.S_IMODE(info.st_mode))
                entry = {
                    "existed": True,
                    "sha256": _sha256(destination),
                    "mode": stat.S_IMODE(info.st_mode),
                    "backup": backup.name,
                }
            files[str(destination)] = entry
        sqlite_path = self.state_dir / "db_v2.sqlite3"
        sqlite_before = sqlite_observation(sqlite_path) if sqlite_path.is_file() else None
        self._prestate = {
            "schema": "phase53-server-prestate-v1",
            "transaction_id": self.transaction_id,
            "linger": self._linger(),
            "files": files,
            "directories": {
                str(self.state_dir): self.state_dir.is_dir(),
                str(self.log_dir): self.log_dir.is_dir(),
            },
            "sqlite": sqlite_before,
            "secret_material_present": False,
        }
        _atomic_json(self.rollback_dir / "prestate.json", self._prestate)
        return self._prestate

    def _provider_exchange(self) -> dict[str, str]:
        provider = self.home / ".local/bin/rustdesk-vault-provider"
        if not provider.is_file() or provider.is_symlink() or not os.access(provider, os.X_OK):
            raise Phase53ServerBlocked("rustdesk-vault-provider-missing")
        request = json.dumps(
            {
                "references": [
                    {"vault_path": path, "field": field} for path, field in SERVER_REFERENCES
                ]
            },
            separators=(",", ":"),
        ).encode("utf-8")
        output = self._run([str(provider)], request, timeout=30)
        try:
            payload = json.loads(output.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise Phase53ServerBlocked("vault-provider-response-invalid") from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"request_count", "values"}
            or payload.get("request_count") != len(SERVER_REFERENCES)
            or not isinstance(payload.get("values"), dict)
        ):
            raise Phase53ServerBlocked("vault-provider-response-invalid")
        return payload["values"]

    @staticmethod
    def _validate_values(values: dict[str, str]) -> tuple[str, str, str]:
        if set(values) != EXPECTED_VALUE_KEYS or any(
            not isinstance(value, str) or not value for value in values.values()
        ):
            raise Phase53ServerBlocked("vault-value-contract-invalid")
        private = values["kv/atius/rustdesk/server#private_key"]
        public = values["kv/atius/rustdesk/server#public_key"]
        try:
            private_raw = base64.b64decode(private, validate=True)
            public_raw = base64.b64decode(public, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise Phase53ServerBlocked("vault-identity-encoding-invalid") from exc
        if len(private_raw) != 64 or len(public_raw) != 32 or private == public:
            raise Phase53ServerBlocked("vault-identity-encoding-invalid")
        passwords = [
            values[f"{path}#{field}"]
            for path, field in SERVER_REFERENCES
            if field == "permanent_password"
        ]
        if (
            len(passwords) != 5
            or len(set(passwords)) != 5
            or any(
                len(password) != 32
                or not password.startswith("R")
                or not password[1:].isalnum()
                or not password.isascii()
                for password in passwords
            )
        ):
            raise Phase53ServerBlocked("vault-password-contract-invalid")
        fingerprint = hashlib.sha256(public.encode("ascii")).hexdigest()
        return private, public, fingerprint

    def hydrate_identity(self) -> dict[str, Any]:
        if self._prestate is None:
            raise Phase53ServerBlocked("prestate-required")
        if not self.tmpfs_checker(self.runtime_dir):
            raise Phase53ServerBlocked("runtime-not-tmpfs")
        if self.identity_dir.exists() or self.identity_dir.is_symlink():
            raise Phase53ServerBlocked("runtime-identity-preexists")
        private, public, fingerprint = self._validate_values(self.provider_exchange())
        self.identity_dir.mkdir(parents=True, mode=0o700)
        _atomic_write(self.identity_dir / "id_ed25519", private.encode("ascii"), 0o600)
        _atomic_write(self.identity_dir / "id_ed25519.pub", public.encode("ascii"), 0o600)
        return {
            "provider_api": "references-v1",
            "reference_count": len(SERVER_REFERENCES),
            "public_fingerprint": fingerprint,
            "secret_material_present": False,
        }

    def _validate_sources(self) -> None:
        for source in self._sources:
            if not source.is_file() or source.is_symlink():
                raise Phase53ServerBlocked("managed-source-missing")
        quadlets = [
            (self.repo / "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container").read_text(),
            (self.repo / "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbr.container").read_text(),
        ]
        required = ("Network=host", "Pull=never", "NoNewPrivileges=true", "DropCapability=ALL")
        if any(any(item not in quadlet for item in required) for quadlet in quadlets):
            raise Phase53ServerBlocked("quadlet-hardening-invalid")
        if any("PublishPort=" in quadlet or "21114" in quadlet for quadlet in quadlets):
            raise Phase53ServerBlocked("closed-ingress-contract-invalid")
        hbbs_commands = [
            line.removeprefix("Exec=")
            for line in quadlets[0].splitlines()
            if line.startswith("Exec=")
        ]
        if hbbs_commands != [f"hbbs -r {self.relay_endpoint}"]:
            raise Phase53ServerBlocked("hbbs-relay-endpoint-invalid")

    @staticmethod
    def _effective_exec(path: Path) -> tuple[str, ...]:
        try:
            commands = [
                line.removeprefix("Exec=")
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith("Exec=")
            ]
            if len(commands) != 1:
                raise ValueError
            argv = tuple(shlex.split(commands[0], posix=True))
        except (OSError, UnicodeError, ValueError) as exc:
            raise Phase53ServerBlocked("installed-hbbs-command-invalid") from exc
        if not argv or any(not item for item in argv):
            raise Phase53ServerBlocked("installed-hbbs-command-invalid")
        return argv

    def _validate_installed_hbbs(self) -> None:
        source = self.repo / "modules/rustdesk-fleet/quadlets/atius-rustdesk-server-hbbs.container"
        installed = self.quadlet_dir / source.name
        expected = ("hbbs", "-r", self.relay_endpoint)
        if self._effective_exec(source) != expected or self._effective_exec(installed) != expected:
            raise Phase53ServerBlocked("installed-hbbs-command-invalid")

    def _source_bytes(self, source: Path) -> bytes:
        """Render candidate image references only after admission is selected."""

        data = source.read_bytes()
        if self.runtime_candidate is None or source.name not in {
            "atius-rustdesk-server-hbbs.container",
            "atius-rustdesk-server-hbbr.container",
        }:
            return data
        try:
            text = data.decode("utf-8")
            image = self.runtime_candidate["upstream"]["immutable_reference"]
        except (KeyError, TypeError, UnicodeError) as exc:
            raise Phase53ServerBlocked("candidate-upstream-invalid") from exc
        lines = text.splitlines(keepends=True)
        image_lines = [index for index, line in enumerate(lines) if line.startswith("Image=")]
        if len(image_lines) != 1:
            raise Phase53ServerBlocked("quadlet-image-line-invalid")
        newline = "\n" if lines[image_lines[0]].endswith("\n") else ""
        lines[image_lines[0]] = f"Image={image}{newline}"
        return "".join(lines).encode("utf-8")

    def render_and_verify_units(self) -> dict[str, Any]:
        if self._prestate is None:
            raise Phase53ServerBlocked("prestate-required")
        self._validate_sources()
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        for source, destination in self._sources.items():
            mode = 0o700 if destination == self.library_target else 0o600
            _atomic_write(destination, self._source_bytes(source), mode)
        self._validate_installed_hbbs()
        self._run(
            [
                "systemd-analyze",
                "--user",
                "verify",
                str(self.user_unit_dir / "atius-rustdesk-phase53.slice"),
                str(self.user_unit_dir / "atius-rustdesk-server-logrotate.service"),
                str(self.user_unit_dir / "atius-rustdesk-server-logrotate.timer"),
            ]
        )
        return {
            "managed_file_count": len(self._sources),
            "public_ingress_opened": False,
            "client_domain_touched": False,
            "secret_material_present": False,
        }

    def _verify_sqlite_unchanged(self) -> None:
        assert self._prestate is not None
        before = self._prestate["sqlite"]
        database = self.state_dir / "db_v2.sqlite3"
        after = sqlite_observation(database) if database.is_file() else None
        if before != after:
            raise Phase53ServerBlocked("sqlite-state-drift")

    def _verify_effective_runtime(self) -> None:
        expected = {
            "atius-rustdesk-phase53.slice": ("80%", "1073741824"),
            "atius-rustdesk-server-hbbs.service": ("35%", "469762048"),
            "atius-rustdesk-server-hbbr.service": ("35%", "402653184"),
        }
        for unit, (cpu, memory) in expected.items():
            output = self._run(
                [
                    "systemctl",
                    "--user",
                    "show",
                    unit,
                    "--property=CPUQuotaPerSecUSec,MemoryMax,Slice",
                    "--value",
                ]
            ).decode("ascii", "strict")
            if output and (cpu not in output or memory not in output):
                raise Phase53ServerBlocked("effective-cgroup-invalid")
        sockets = self._run(["ss", "-Hlnut"]).decode("ascii", "strict")
        if sockets and ":21114" in sockets:
            raise Phase53ServerBlocked("forbidden-listener-present")

    def install_closed(self) -> dict[str, Any]:
        """Install server units and start only host-local listeners; edge remains closed."""
        with self._exclusive():
            try:
                prestate = self.snapshot_prestate()
                self._checkpoint("prestate")
                identity = self.hydrate_identity()
                self._checkpoint("identity")
                units = self.render_and_verify_units()
                self._checkpoint("units")
                if not prestate["linger"]:
                    self._run(["sudo", "-n", "loginctl", "enable-linger", self._account()])
                    self._linger_enabled_by_transaction = True
                self._checkpoint("linger")
                self._run(["systemctl", "--user", "daemon-reload"])
                self._checkpoint("reload")
                self._run(["systemctl", "--user", "start", *SERVICE_UNITS])
                self._installed = True
                self._checkpoint("start")
                self._verify_effective_runtime()
                self._verify_sqlite_unchanged()
                return {
                    "transaction_id": self.transaction_id,
                    "identity": identity,
                    "units": units,
                    "linger_changed": self._linger_enabled_by_transaction,
                    "ingress": "closed",
                    "secret_material_present": False,
                }
            except Exception:
                self.rollback_server()
                raise

    def rollback_server(self) -> dict[str, Any]:
        """Idempotently restore exact managed-file and linger pre-state."""
        if self._rolled_back:
            return {"terminal": True, "state": "ROLLED_BACK", "secret_material_present": False}
        if self._installed:
            self._run(["systemctl", "--user", "stop", *reversed(SERVICE_UNITS)])
        if self._prestate is not None:
            files = self._prestate["files"]
            backup_dir = self.rollback_dir / "unit-prestate"
            for destination_text, entry in files.items():
                destination = Path(destination_text)
                if entry["existed"]:
                    backup = backup_dir / entry["backup"]
                    _atomic_write(destination, backup.read_bytes(), int(entry["mode"]))
                    if _sha256(destination) != entry["sha256"]:
                        raise Phase53ServerBlocked("rollback-unit-restore-failed")
                else:
                    destination.unlink(missing_ok=True)
            if self._linger_enabled_by_transaction:
                self._run(["sudo", "-n", "loginctl", "disable-linger", self._account()])
                self._linger_enabled_by_transaction = False
            self._verify_sqlite_unchanged()
        if self.identity_dir.exists() and self.identity_dir.is_dir() and not self.identity_dir.is_symlink():
            for name in ("id_ed25519", "id_ed25519.pub"):
                (self.identity_dir / name).unlink(missing_ok=True)
            self.identity_dir.rmdir()
        if self._prestate is not None:
            for directory in (self.log_dir, self.state_dir):
                existed = self._prestate["directories"][str(directory)]
                if not existed and directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
        self._run(["systemctl", "--user", "daemon-reload"])
        self._rolled_back = True
        receipt = {
            "terminal": True,
            "state": "ROLLED_BACK",
            "linger_restored": True,
            "client_domain_touched": False,
            "legacy_domain_touched": False,
            "secret_material_present": False,
        }
        if self.rollback_dir.exists():
            _atomic_json(self.rollback_dir / "rollback-receipt.json", receipt)
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rotate-logs", action="store_true")
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path.home() / ".local/state/atius-rustdesk/server/logs",
    )
    args = parser.parse_args()
    if not args.rotate_logs:
        parser.error("no action selected; live installation is orchestrated by Phase 53 Plan 05")
    try:
        result = enforce_log_bounds(args.log_dir)
    except (OSError, Phase53ServerBlocked, ValueError):
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
