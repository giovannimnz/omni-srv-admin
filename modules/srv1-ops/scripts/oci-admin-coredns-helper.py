#!/usr/bin/env python3
"""Closed transactional CoreDNS helper for OCI Admin Phase 25."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from ipaddress import ip_address
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Protocol, Sequence


VERSION = "1"
SENTINEL = "ATIUS_RUNBOOK_RESULT_V1"
MAX_RESULT_BYTES = 49152
MAX_FILE_BYTES = 1048576
MAX_RELOAD_INTERVAL_SECONDS = 60
READBACK_ATTEMPT_BUDGET_SECONDS = 21.0
TARGET_DISPLAY_NAME = "atius-srv-1"
SHORT_NAME = "atius-srv-4"
FQDN = "atius-srv-4.atius.internal"
EXPECTED_ADDRESS = "10.14.1.14"
INSTALLED_HELPER_PATH = Path("/usr/local/libexec/oci-admin-coredns-helper")
BACKUP_ROOT = Path("/var/lib/oci-admin-coredns-helper/backups")

MANIFEST_DIGESTS = {
    "inspect": "sha256:be3fde76bdb4fb9d6e5c8944cb8da79921da2a45c67964265d3a61650b67dc84",
    "apply": "sha256:46e109c4b4909ac401368bfabb123d6e44c30e0ab4bd2bfe95df156c2bae6b60",
    "rollback": "sha256:d15b19e3d09e59b40ea3b8547854f497c5818b89f7faaf7364afe7b211b43de6",
}

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_BACKUP_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,252}[a-z0-9])?")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?")
_SENSITIVE = re.compile(
    r"(?i)(-----BEGIN|bearer\s|password\s*[:=]|secret\s*[:=]|"
    r"api[_-]?key\s*[:=]|token\s*[:=])"
)

_INSPECT_FLAGS = (
    "--manifest-digest",
    "--target-binding-digest",
    "--operation-id",
    "--plan-hash",
    "--source-commit",
    "--source-digest",
    "--projection-digest",
    "--helper-digest",
    "--short-name",
    "--fqdn",
    "--expected-address",
    "--sentinel",
)
_APPLY_FLAGS = (
    "--manifest-digest",
    "--target-binding-digest",
    "--operation-id",
    "--plan-hash",
    "--source-commit",
    "--source-digest",
    "--projection-digest",
    "--discovery-digest",
    "--preimage-digest",
    "--desired-config-digest",
    "--helper-digest",
    "--backup-id",
    "--backup-digest",
    "--short-name",
    "--fqdn",
    "--expected-address",
    "--previous-answer",
    "--sentinel",
)
_ROLLBACK_FLAGS = (
    "--manifest-digest",
    "--target-binding-digest",
    "--operation-id",
    "--plan-hash",
    "--origin-operation-id",
    "--backup-id",
    "--backup-digest",
    "--discovery-digest",
    "--preimage-digest",
    "--desired-config-digest",
    "--helper-digest",
    "--short-name",
    "--fqdn",
    "--previous-answer",
    "--sentinel",
)


class HelperError(RuntimeError):
    """A fail-closed error whose details must never cross the CLI boundary."""


@dataclass(frozen=True)
class InspectRequest:
    manifest_digest: str
    target_binding_digest: str
    operation_id: str
    plan_hash: str
    source_commit: str
    source_digest: str
    projection_digest: str
    helper_digest: str
    short_name: str
    fqdn: str
    expected_address: str
    sentinel: str


@dataclass(frozen=True)
class ApplyRequest:
    manifest_digest: str
    target_binding_digest: str
    operation_id: str
    plan_hash: str
    source_commit: str
    source_digest: str
    projection_digest: str
    discovery_digest: str
    preimage_digest: str
    desired_config_digest: str
    helper_digest: str
    backup_id: str
    backup_digest: str
    short_name: str
    fqdn: str
    expected_address: str
    previous_answer: str
    sentinel: str


@dataclass(frozen=True)
class RollbackRequest:
    manifest_digest: str
    target_binding_digest: str
    operation_id: str
    plan_hash: str
    origin_operation_id: str
    backup_id: str
    backup_digest: str
    discovery_digest: str
    preimage_digest: str
    desired_config_digest: str
    helper_digest: str
    short_name: str
    fqdn: str
    previous_answer: str
    sentinel: str


@dataclass(frozen=True)
class Layout:
    binary_path: str
    version: str
    unit: str
    plugin: str
    config_path: Path
    data_path: Path
    activation_mode: str
    reload_interval_seconds: int


class Runtime(Protocol):
    def validate(self, layout: Layout, staged_path: Path) -> None: ...
    def activate(self, layout: Layout) -> None: ...
    def healthy(self, layout: Layout) -> None: ...
    def readback(
        self, short_name: str, fqdn: str, expected_answer: str
    ) -> list[dict[str, Any]]: ...


def sha256_digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_digest(encoded)


def serialize_result(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    line = f"{SENTINEL} {payload}\n"
    if len(line.encode("utf-8")) > MAX_RESULT_BYTES or _SENSITIVE.search(line):
        raise HelperError("result rejected")
    return line


def _read_pairs(argv: Sequence[str], flags: Sequence[str]) -> dict[str, str]:
    if len(argv) != len(flags) * 2:
        raise HelperError("argument count rejected")
    values: dict[str, str] = {}
    for index, flag in enumerate(flags):
        if argv[index * 2] != flag:
            raise HelperError("argument order rejected")
        value = argv[index * 2 + 1]
        if not value or "\x00" in value or "\n" in value or "\r" in value:
            raise HelperError("argument value rejected")
        values[flag.removeprefix("--").replace("-", "_")] = value
    return values


def _validate_common(request: Any, command: str) -> None:
    if request.manifest_digest != MANIFEST_DIGESTS[command]:
        raise HelperError("manifest rejected")
    for field in (
        "manifest_digest",
        "target_binding_digest",
        "plan_hash",
        "helper_digest",
    ):
        if not _DIGEST.fullmatch(getattr(request, field)):
            raise HelperError("digest rejected")
    if not _IDENTIFIER.fullmatch(request.operation_id):
        raise HelperError("operation rejected")
    if request.sentinel != SENTINEL:
        raise HelperError("sentinel rejected")
    for value in request.__dict__.values():
        if isinstance(value, str) and _SENSITIVE.search(value):
            raise HelperError("sensitive-shaped argument rejected")


def _validate_answer(value: str) -> None:
    if value == "NXDOMAIN":
        return
    try:
        parsed = ip_address(value)
    except ValueError as exc:
        raise HelperError("answer rejected") from exc
    if parsed.version != 4:
        raise HelperError("answer rejected")


def parse_request(argv: Sequence[str]) -> InspectRequest | ApplyRequest | RollbackRequest:
    if not argv:
        raise HelperError("subcommand required")
    command = argv[0]
    if command == "inspect":
        request: Any = InspectRequest(**_read_pairs(argv[1:], _INSPECT_FLAGS))
    elif command == "apply":
        request = ApplyRequest(**_read_pairs(argv[1:], _APPLY_FLAGS))
    elif command == "rollback":
        request = RollbackRequest(**_read_pairs(argv[1:], _ROLLBACK_FLAGS))
    else:
        raise HelperError("subcommand rejected")
    _validate_common(request, command)
    if isinstance(request, (InspectRequest, ApplyRequest)):
        if not _COMMIT.fullmatch(request.source_commit):
            raise HelperError("source commit rejected")
        for field in ("source_digest", "projection_digest"):
            if not _DIGEST.fullmatch(getattr(request, field)):
                raise HelperError("source digest rejected")
    if isinstance(request, (InspectRequest, ApplyRequest, RollbackRequest)):
        if (
            request.short_name != SHORT_NAME
            or request.fqdn != FQDN
            or getattr(request, "expected_address", EXPECTED_ADDRESS)
            != EXPECTED_ADDRESS
        ):
            raise HelperError("record identity rejected")
    if isinstance(request, (ApplyRequest, RollbackRequest)):
        for field in (
            "discovery_digest",
            "preimage_digest",
            "desired_config_digest",
            "backup_digest",
        ):
            if not _DIGEST.fullmatch(getattr(request, field)):
                raise HelperError("transaction digest rejected")
        if not _BACKUP_ID.fullmatch(request.backup_id):
            raise HelperError("backup id rejected")
        _validate_answer(request.previous_answer)
    if isinstance(request, RollbackRequest) and not _IDENTIFIER.fullmatch(
        request.origin_operation_id
    ):
        raise HelperError("origin operation rejected")
    return request


def layout_digest(layout: Layout) -> str:
    config_bytes, _ = _read_regular(layout.config_path, "CoreDNS config")
    return layout_digest_from_config(layout, config_bytes)


def layout_digest_from_config(layout: Layout, config_bytes: bytes) -> str:
    return canonical_digest(
        {
            "binary_path": layout.binary_path,
            "version": layout.version,
            "unit": layout.unit,
            "plugin": layout.plugin,
            "config_path": str(layout.config_path),
            "data_path": str(layout.data_path),
            "activation_mode": layout.activation_mode,
            "reload_interval_seconds": layout.reload_interval_seconds,
            "config_digest": sha256_digest(config_bytes),
        }
    )


def _decode_data(value: bytes) -> list[str]:
    if not 0 < len(value) <= MAX_FILE_BYTES or b"\x00" in value or b"\r" in value:
        raise HelperError("data rejected")
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HelperError("data encoding rejected") from exc
    lines = text.splitlines()
    if any(len(line) > 4096 for line in lines):
        raise HelperError("data line rejected")
    return lines


def _validate_hosts_lines(lines: Sequence[str]) -> None:
    target_rows = 0
    for line in lines:
        content = line.split("#", 1)[0].strip()
        if not content:
            continue
        fields = content.split()
        if len(fields) < 2:
            raise HelperError("hosts row rejected")
        try:
            address = ip_address(fields[0])
        except ValueError as exc:
            raise HelperError("hosts address rejected") from exc
        if address.version != 4 or any(not _HOST.fullmatch(name) for name in fields[1:]):
            raise HelperError("hosts identity rejected")
        if SHORT_NAME in fields[1:] or FQDN in fields[1:]:
            target_rows += 1
    if target_rows > 1:
        raise HelperError("ambiguous target rows")


def _validate_zone_lines(lines: Sequence[str]) -> None:
    if not any(line.strip().lower() == "$origin atius.internal." for line in lines):
        raise HelperError("zone origin rejected")
    target_rows = 0
    for line in lines:
        content = line.split(";", 1)[0].strip()
        if not content or content.startswith("$") or content.startswith("(") or content == ")":
            continue
        fields = content.split()
        upper = [field.upper() for field in fields]
        if "A" in upper:
            index = upper.index("A")
            if index == 0 or index + 1 >= len(fields):
                raise HelperError("zone row rejected")
            try:
                address = ip_address(fields[index + 1])
            except ValueError as exc:
                raise HelperError("zone address rejected") from exc
            if address.version != 4:
                raise HelperError("zone address rejected")
            owner = fields[0].lower().rstrip(".")
            if owner in {SHORT_NAME, FQDN}:
                target_rows += 1
    if target_rows > 1:
        raise HelperError("ambiguous target rows")


def validate_data_bytes(plugin: str, value: bytes) -> None:
    lines = _decode_data(value)
    if plugin == "hosts":
        _validate_hosts_lines(lines)
    elif plugin == "file":
        _validate_zone_lines(lines)
    else:
        raise HelperError("plugin rejected")


def render_desired_data(
    plugin: str,
    preimage: bytes,
    *,
    short_name: str,
    fqdn: str,
    expected_address: str,
) -> bytes:
    if (short_name, fqdn, expected_address) != (SHORT_NAME, FQDN, EXPECTED_ADDRESS):
        raise HelperError("record identity rejected")
    lines = _decode_data(preimage)
    validate_data_bytes(plugin, preimage)
    retained: list[str] = []
    if plugin == "hosts":
        for line in lines:
            fields = line.split("#", 1)[0].split()
            if fields and any(name in {SHORT_NAME, FQDN} for name in fields[1:]):
                continue
            retained.append(line)
        retained.append(f"{EXPECTED_ADDRESS} {SHORT_NAME} {FQDN}")
    elif plugin == "file":
        for line in lines:
            fields = line.split(";", 1)[0].split()
            owner = fields[0].lower().rstrip(".") if fields else ""
            if owner in {SHORT_NAME, FQDN}:
                continue
            retained.append(line)
        retained.append(f"{SHORT_NAME} 60 IN A {EXPECTED_ADDRESS}")
    else:
        raise HelperError("plugin rejected")
    rendered = ("\n".join(retained).rstrip("\n") + "\n").encode("utf-8")
    validate_data_bytes(plugin, rendered)
    return rendered


def _read_regular(path: Path, label: str) -> tuple[bytes, os.stat_result]:
    try:
        before = path.lstat()
    except OSError as exc:
        raise HelperError(f"{label} unavailable") from exc
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or (os.name != "nt" and before.st_nlink != 1)
        or not 0 < before.st_size <= MAX_FILE_BYTES
    ):
        raise HelperError(f"{label} identity rejected")
    try:
        value = path.read_bytes()
        after = path.lstat()
    except OSError as exc:
        raise HelperError(f"{label} unavailable") from exc
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise HelperError(f"{label} changed during read")
    return value, after


def assert_trusted_path(
    path: Path,
    *,
    trust_root: Path,
    trusted_uid: int,
    trusted_gid: int,
    require_executable: bool = False,
) -> None:
    """Reject symlink/writable ancestors before any root path is re-resolved."""
    if not path.is_absolute() or not trust_root.is_absolute():
        raise HelperError("managed path is not absolute")
    try:
        relative = path.relative_to(trust_root)
    except ValueError as exc:
        raise HelperError("managed path escaped trust root") from exc
    current = trust_root
    parts = ("", *relative.parts)
    for index, part in enumerate(parts):
        if part:
            current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise HelperError("managed path unavailable") from exc
        is_leaf = index == len(parts) - 1
        if stat.S_ISLNK(info.st_mode):
            raise HelperError("managed path symlink rejected")
        if is_leaf:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise HelperError("managed file identity rejected")
        elif not stat.S_ISDIR(info.st_mode):
            raise HelperError("managed parent identity rejected")
        if (
            info.st_uid != trusted_uid
            or info.st_gid != trusted_gid
            or stat.S_IMODE(info.st_mode) & 0o022
        ):
            raise HelperError("managed path ownership rejected")
        if is_leaf and require_executable and not stat.S_IMODE(info.st_mode) & 0o111:
            raise HelperError("managed executable mode rejected")


def assert_live_layout_security(layout: Layout) -> None:
    import pwd

    try:
        ubuntu = pwd.getpwnam("ubuntu")
        ocarun = pwd.getpwnam("ocarun")
    except KeyError as exc:
        raise HelperError("managed owner identity unavailable") from exc
    if ubuntu.pw_uid == ocarun.pw_uid:
        raise HelperError("Run Command user owns CoreDNS source")
    for path, executable in (
        (Path(layout.binary_path), True),
        (layout.config_path, False),
        (layout.data_path, False),
    ):
        assert_delegated_trusted_path(
            path,
            trust_root=Path("/"),
            delegated_root=Path("/home/ubuntu"),
            delegated_uid=ubuntu.pw_uid,
            delegated_gid=ubuntu.pw_gid,
            require_executable=executable,
        )


def assert_delegated_trusted_path(
    path: Path,
    *,
    trust_root: Path,
    delegated_root: Path,
    delegated_uid: int,
    delegated_gid: int,
    require_executable: bool = False,
) -> None:
    if not path.is_absolute() or not trust_root.is_absolute() or not delegated_root.is_absolute():
        raise HelperError("managed path is not absolute")
    try:
        relative = path.relative_to(trust_root)
    except ValueError as exc:
        raise HelperError("managed path escaped trust root") from exc
    current = trust_root
    parts = ("", *relative.parts)
    for index, part in enumerate(parts):
        if part:
            current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise HelperError("managed path unavailable") from exc
        is_leaf = index == len(parts) - 1
        delegated = current == delegated_root or delegated_root in current.parents
        allowed_owners = {(0, 0)}
        if delegated:
            allowed_owners.add((delegated_uid, delegated_gid))
        if stat.S_ISLNK(info.st_mode):
            raise HelperError("managed path symlink rejected")
        if is_leaf:
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise HelperError("managed file identity rejected")
        elif not stat.S_ISDIR(info.st_mode):
            raise HelperError("managed parent identity rejected")
        if (info.st_uid, info.st_gid) not in allowed_owners or stat.S_IMODE(info.st_mode) & 0o022:
            raise HelperError("managed path ownership rejected")
        if hasattr(os, "listxattr"):
            try:
                if "system.posix_acl_access" in os.listxattr(current, follow_symlinks=False):
                    raise HelperError("managed path ACL rejected")
            except OSError as exc:
                raise HelperError("managed path ACL unavailable") from exc
        if is_leaf and require_executable and not stat.S_IMODE(info.st_mode) & 0o111:
            raise HelperError("managed executable mode rejected")


def _fsync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_mkdir_tree(
    path: Path,
    *,
    trust_root: Path,
    uid: int,
    gid: int,
    new_mode: int,
) -> None:
    try:
        relative = path.relative_to(trust_root)
    except ValueError as exc:
        raise HelperError("directory path escaped trust root") from exc
    current = trust_root
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != uid
                or info.st_gid != gid
                or stat.S_IMODE(info.st_mode) & 0o022
            ):
                raise HelperError("directory identity rejected")
            continue
        current.mkdir(mode=new_mode)
        if hasattr(os, "chown"):
            os.chown(current, uid, gid)
        _fsync_parent(current)
        _fsync_directory(current)


def _apply_identity(descriptor: int, mode: int, uid: int, gid: int) -> None:
    if hasattr(os, "fchmod"):
        os.fchmod(descriptor, mode)
    if hasattr(os, "fchown"):
        os.fchown(descriptor, uid, gid)


def _stage_bytes(path: Path, value: bytes, identity: os.stat_result) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.stage.", dir=path.parent)
    staged = Path(name)
    try:
        _apply_identity(
            descriptor,
            stat.S_IMODE(identity.st_mode),
            identity.st_uid,
            identity.st_gid,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if not hasattr(os, "fchmod"):
            os.chmod(staged, stat.S_IMODE(identity.st_mode))
        return staged
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        staged.unlink(missing_ok=True)
        raise


def _atomic_write(path: Path, value: bytes, identity: os.stat_result) -> None:
    staged = _stage_bytes(path, value, identity)
    try:
        os.replace(staged, path)
        _fsync_parent(path)
    finally:
        staged.unlink(missing_ok=True)


def _atomic_new(path: Path, value: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        existing, _ = _read_regular(path, "existing immutable file")
        if existing != value:
            raise HelperError("immutable file collision")
        return
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    staged = Path(name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if not hasattr(os, "fchmod"):
            os.chmod(staged, mode)
        try:
            os.link(staged, path)
        except FileExistsError:
            existing, _ = _read_regular(path, "existing immutable file")
            if existing != value:
                raise HelperError("immutable file collision")
        _fsync_parent(path)
    finally:
        staged.unlink(missing_ok=True)


def _ensure_root_storage(path: Path, fixed_root: Path) -> None:
    try:
        path.relative_to(fixed_root)
    except ValueError as exc:
        raise HelperError("backup path escaped fixed root") from exc
    _durable_mkdir_tree(
        path,
        trust_root=Path("/"),
        uid=0,
        gid=0,
        new_mode=0o700,
    )
    _assert_root_storage(path, fixed_root)


def _assert_root_storage(path: Path, fixed_root: Path) -> None:
    try:
        path.relative_to(fixed_root)
    except ValueError as exc:
        raise HelperError("backup path escaped fixed root") from exc
    current = fixed_root
    for part in ("", *path.relative_to(fixed_root).parts):
        if part:
            current = current / part
        info = current.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != 0
            or info.st_gid != 0
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise HelperError("backup directory identity rejected")


class PinnedLayoutIO:
    """Pin CoreDNS parents and perform data operations with openat/renameat."""

    def __init__(self, layout: Layout) -> None:
        self.layout = layout
        self.config_fd = self._open_parent(layout.config_path.parent)
        try:
            self.data_fd = self._open_parent(layout.data_path.parent)
        except BaseException:
            os.close(self.config_fd)
            raise
        self._stages: dict[str, str] = {}

    @staticmethod
    def _open_parent(path: Path) -> int:
        descriptor = os.open(
            path,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        lexical = path.lstat()
        if (
            not stat.S_ISDIR(opened.st_mode)
            or stat.S_ISLNK(lexical.st_mode)
            or (opened.st_dev, opened.st_ino) != (lexical.st_dev, lexical.st_ino)
        ):
            os.close(descriptor)
            raise HelperError("managed parent pin rejected")
        return descriptor

    @staticmethod
    def _read_at(descriptor: int, name: str, label: str) -> tuple[bytes, os.stat_result]:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        file_descriptor = os.open(name, flags, dir_fd=descriptor)
        try:
            before = os.fstat(file_descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or not 0 < before.st_size <= MAX_FILE_BYTES
            ):
                raise HelperError(f"{label} identity rejected")
            chunks: list[bytes] = []
            remaining = MAX_FILE_BYTES + 1
            while remaining > 0:
                chunk = os.read(file_descriptor, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            if remaining <= 0:
                raise HelperError(f"{label} oversized")
            after = os.fstat(file_descriptor)
            lexical = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ) or (lexical.st_dev, lexical.st_ino) != (after.st_dev, after.st_ino):
                raise HelperError(f"{label} changed during read")
            return b"".join(chunks), after
        finally:
            os.close(file_descriptor)

    def read_config(self) -> tuple[bytes, os.stat_result]:
        return self._read_at(self.config_fd, self.layout.config_path.name, "CoreDNS config")

    def read_data(self) -> tuple[bytes, os.stat_result]:
        return self._read_at(self.data_fd, self.layout.data_path.name, "CoreDNS data")

    def stage_data(self, value: bytes, identity: os.stat_result) -> Path:
        name = f".{self.layout.data_path.name}.stage.{secrets.token_hex(16)}"
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            stat.S_IMODE(identity.st_mode),
            dir_fd=self.data_fd,
        )
        try:
            os.fchmod(descriptor, stat.S_IMODE(identity.st_mode))
            os.fchown(descriptor, identity.st_uid, identity.st_gid)
            offset = 0
            while offset < len(value):
                offset += os.write(descriptor, value[offset:])
            os.fsync(descriptor)
        except BaseException:
            try:
                os.unlink(name, dir_fd=self.data_fd)
            except OSError:
                pass
            raise
        finally:
            os.close(descriptor)
        process_path = Path(f"/proc/{os.getpid()}/fd/{self.data_fd}/{name}")
        self._stages[str(process_path)] = name
        return process_path

    def replace_stage(self, staged: Path) -> None:
        name = self._stages.pop(str(staged), None)
        if name is None:
            raise HelperError("staged file identity rejected")
        os.replace(
            name,
            self.layout.data_path.name,
            src_dir_fd=self.data_fd,
            dst_dir_fd=self.data_fd,
        )
        os.fsync(self.data_fd)

    def atomic_data(self, value: bytes, identity: os.stat_result) -> None:
        staged = self.stage_data(value, identity)
        try:
            self.replace_stage(staged)
        finally:
            self.cleanup_stage(staged)

    def cleanup_stage(self, staged: Path) -> None:
        name = self._stages.pop(str(staged), None)
        if name is not None:
            try:
                os.unlink(name, dir_fd=self.data_fd)
            except FileNotFoundError:
                pass

    def close(self) -> None:
        for descriptor in (self.config_fd, self.data_fd):
            os.close(descriptor)


class CoreDNSManager:
    def __init__(
        self,
        *,
        layout: Layout,
        backup_root: Path,
        runtime: Runtime,
        fault_hook: Callable[[str], None] | None = None,
        enforce_root_storage: bool = False,
        security_hook: Callable[[], None] | None = None,
        pinned_io: PinnedLayoutIO | None = None,
    ) -> None:
        if not 0 <= layout.reload_interval_seconds <= MAX_RELOAD_INTERVAL_SECONDS:
            raise HelperError("reload interval exceeds transaction budget")
        self.layout = layout
        self.backup_root = backup_root
        self.runtime = runtime
        self.fault_hook = fault_hook or (lambda _stage: None)
        self.enforce_root_storage = enforce_root_storage
        self.security_hook = security_hook or (lambda: None)
        self.pinned_io = pinned_io

    def _read_config(self) -> tuple[bytes, os.stat_result]:
        if self.pinned_io is not None:
            return self.pinned_io.read_config()
        return _read_regular(self.layout.config_path, "CoreDNS config")

    def _read_data(self) -> tuple[bytes, os.stat_result]:
        if self.pinned_io is not None:
            return self.pinned_io.read_data()
        return _read_regular(self.layout.data_path, "CoreDNS data")

    def _stage_data(self, value: bytes, identity: os.stat_result) -> Path:
        if self.pinned_io is not None:
            return self.pinned_io.stage_data(value, identity)
        return _stage_bytes(self.layout.data_path, value, identity)

    def _replace_stage(self, staged: Path) -> None:
        if self.pinned_io is not None:
            self.pinned_io.replace_stage(staged)
            return
        os.replace(staged, self.layout.data_path)
        _fsync_parent(self.layout.data_path)

    def _cleanup_stage(self, staged: Path) -> None:
        if self.pinned_io is not None:
            self.pinned_io.cleanup_stage(staged)
        else:
            staged.unlink(missing_ok=True)

    def _atomic_data(self, value: bytes, identity: os.stat_result) -> None:
        if self.pinned_io is not None:
            self.pinned_io.atomic_data(value, identity)
        else:
            _atomic_write(self.layout.data_path, value, identity)

    def _discovery_digest(self) -> str:
        config, _ = self._read_config()
        return layout_digest_from_config(self.layout, config)

    def backup_path(self, backup_id: str, backup_digest: str) -> Path:
        if not _BACKUP_ID.fullmatch(backup_id) or not _DIGEST.fullmatch(backup_digest):
            raise HelperError("backup identity rejected")
        return self.backup_root / backup_digest.removeprefix("sha256:") / backup_id / "preimage"

    def _binding_path(self, request: ApplyRequest | RollbackRequest) -> Path:
        return self.backup_path(request.backup_id, request.backup_digest).with_name("binding.json")

    def _binding(self, request: ApplyRequest, identity: os.stat_result) -> dict[str, Any]:
        return {
            "schema": "atius.oci-admin-coredns-backup/v1",
            "backup_id": request.backup_id,
            "backup_digest": request.backup_digest,
            "origin_operation_id": request.operation_id,
            "plan_hash": request.plan_hash,
            "target_binding_digest": request.target_binding_digest,
            "discovery_digest": request.discovery_digest,
            "preimage_digest": request.preimage_digest,
            "desired_config_digest": request.desired_config_digest,
            "helper_digest": request.helper_digest,
            "previous_answer": request.previous_answer,
            "mode": f"{stat.S_IMODE(identity.st_mode):04o}",
            "uid": identity.st_uid,
            "gid": identity.st_gid,
        }

    def _create_backup(
        self, request: ApplyRequest, preimage: bytes, identity: os.stat_result
    ) -> None:
        if sha256_digest(preimage) != request.backup_digest:
            raise HelperError("backup digest rejected")
        path = self.backup_path(request.backup_id, request.backup_digest)
        if self.enforce_root_storage:
            _ensure_root_storage(path.parent, self.backup_root)
        _atomic_new(path, preimage)
        binding = json.dumps(
            self._binding(request, identity),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        _atomic_new(self._binding_path(request), binding)
        if self.enforce_root_storage:
            _ensure_root_storage(path.parent, self.backup_root)
            for stored in (path, self._binding_path(request)):
                info = stored.lstat()
                if info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
                    raise HelperError("backup storage identity rejected")

    def _load_backup(self, request: RollbackRequest) -> tuple[bytes, dict[str, Any]]:
        path = self.backup_path(request.backup_id, request.backup_digest)
        if self.enforce_root_storage:
            _assert_root_storage(path.parent, self.backup_root)
        preimage, _ = _read_regular(path, "backup")
        binding_bytes, _ = _read_regular(self._binding_path(request), "backup binding")
        if self.enforce_root_storage:
            for stored in (path, self._binding_path(request)):
                info = stored.lstat()
                if info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
                    raise HelperError("backup storage identity rejected")
        if sha256_digest(preimage) != request.backup_digest:
            raise HelperError("backup digest mismatch")
        try:
            binding = json.loads(binding_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HelperError("backup binding rejected") from exc
        expected = {
            "backup_id": request.backup_id,
            "backup_digest": request.backup_digest,
            "origin_operation_id": request.origin_operation_id,
            "plan_hash": request.plan_hash,
            "target_binding_digest": request.target_binding_digest,
            "discovery_digest": request.discovery_digest,
            "preimage_digest": request.preimage_digest,
            "desired_config_digest": request.desired_config_digest,
            "helper_digest": request.helper_digest,
            "previous_answer": request.previous_answer,
        }
        if binding.get("schema") != "atius.oci-admin-coredns-backup/v1" or any(
            binding.get(key) != value for key, value in expected.items()
        ):
            raise HelperError("backup binding mismatch")
        return preimage, binding

    def inspect(
        self, request: InspectRequest, *, installed_helper_path: Path
    ) -> dict[str, Any]:
        self.security_hook()
        helper_bytes, _ = _read_regular(installed_helper_path, "helper")
        if sha256_digest(helper_bytes) != request.helper_digest:
            raise HelperError("helper digest mismatch")
        config, _ = self._read_config()
        data, _ = self._read_data()
        before = self.runtime.readback(
            request.short_name,
            request.fqdn,
            "AUTO",
        )
        desired = render_desired_data(
            self.layout.plugin,
            data,
            short_name=request.short_name,
            fqdn=request.fqdn,
            expected_address=request.expected_address,
        )
        return {
            "runbook_id": "phase25.coredns-inspect",
            "version": VERSION,
            "target_display_name": TARGET_DISPLAY_NAME,
            "owner": {"machine_id": TARGET_DISPLAY_NAME, "effective_user": "ocarun"},
            "coredns": {
                "binary_path": self.layout.binary_path,
                "version": self.layout.version,
                "unit": self.layout.unit,
                "plugin": self.layout.plugin,
                "config_path": str(self.layout.config_path),
                "data_path": str(self.layout.data_path),
                "activation_mode": self.layout.activation_mode,
                "reload_interval_seconds": self.layout.reload_interval_seconds,
            },
            "helper": {
                "path": str(INSTALLED_HELPER_PATH),
                "owner": "root",
                "group": "root",
                "mode": "0755",
                "digest": request.helper_digest,
            },
            "preimage": {
                "config_digest": sha256_digest(config),
                "data_digest": sha256_digest(data),
            },
            "desired": {
                "short_name": request.short_name,
                "fqdn": request.fqdn,
                "expected_address": request.expected_address,
                "config_digest": sha256_digest(desired),
            },
            "before_readback": before,
        }

    def _restore(
        self,
        preimage: bytes,
        identity: os.stat_result,
        request: ApplyRequest | RollbackRequest,
    ) -> list[dict[str, Any]]:
        self.security_hook()
        self._atomic_data(preimage, identity)
        restored, _ = self._read_data()
        if sha256_digest(restored) != request.preimage_digest:
            raise HelperError("restored digest mismatch")
        self.runtime.activate(self.layout)
        self.runtime.healthy(self.layout)
        return self._bounded_readback(
            request.short_name, request.fqdn, request.previous_answer
        )

    def _bounded_readback(
        self, short_name: str, fqdn: str, expected_answer: str
    ) -> list[dict[str, Any]]:
        deadline = (
            time.monotonic()
            + float(self.layout.reload_interval_seconds)
            + READBACK_ATTEMPT_BUDGET_SECONDS
            + 5.0
        )
        while True:
            if deadline - time.monotonic() < READBACK_ATTEMPT_BUDGET_SECONDS:
                raise HelperError("DNS readback budget exhausted")
            try:
                return self.runtime.readback(short_name, fqdn, expected_answer)
            except HelperError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)

    def apply(self, request: ApplyRequest) -> dict[str, Any]:
        self.security_hook()
        if request.discovery_digest != self._discovery_digest():
            raise HelperError("discovery drift")
        preimage, identity = self._read_data()
        if sha256_digest(preimage) != request.preimage_digest:
            raise HelperError("preimage drift")
        desired = render_desired_data(
            self.layout.plugin,
            preimage,
            short_name=request.short_name,
            fqdn=request.fqdn,
            expected_address=request.expected_address,
        )
        if sha256_digest(desired) != request.desired_config_digest:
            raise HelperError("desired digest mismatch")
        self.runtime.readback(
            request.short_name, request.fqdn, request.previous_answer
        )
        self._create_backup(request, preimage, identity)
        staged = self._stage_data(desired, identity)
        stages = {
            "validation": "not-run",
            "replace": "not-run",
            "activation": "not-run",
            "health": "not-run",
        }
        current_stage = "validation"
        try:
            self.fault_hook("validation")
            self.runtime.validate(self.layout, staged)
            stages["validation"] = "strict-passed"
            current_stage = "replace"
            self.fault_hook("replace")
            self.security_hook()
            self._replace_stage(staged)
            stages["replace"] = "atomic"
            current_stage = "activation"
            self.fault_hook("activation")
            self.runtime.activate(self.layout)
            stages["activation"] = "completed"
            current_stage = "health"
            self.fault_hook("health")
            self.runtime.healthy(self.layout)
            stages["health"] = "ready"
            current_stage = "readback"
            self.fault_hook("readback")
            readback = self._bounded_readback(
                request.short_name, request.fqdn, request.expected_address
            )
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            if current_stage == "validation":
                stages["validation"] = "failed"
            elif current_stage in stages:
                stages[current_stage] = "failed"
            try:
                readback = self._restore(preimage, identity, request)
            except BaseException as restore_exc:
                raise HelperError("automatic restore proof failed") from restore_exc
            return self._apply_result(
                request,
                status="restored",
                failed_stage=current_stage,
                stages=stages,
                readback=readback,
                restored_digest=sha256_digest(preimage),
            )
        finally:
            self._cleanup_stage(staged)
        return self._apply_result(
            request,
            status="applied",
            failed_stage="none",
            stages=stages,
            readback=readback,
            restored_digest="not-required",
        )

    def _apply_result(
        self,
        request: ApplyRequest,
        *,
        status: str,
        failed_stage: str,
        stages: dict[str, str],
        readback: list[dict[str, Any]],
        restored_digest: str,
    ) -> dict[str, Any]:
        restored = status == "restored"
        return {
            "runbook_id": "phase25.coredns-apply",
            "version": VERSION,
            "target_display_name": TARGET_DISPLAY_NAME,
            "status": status,
            "operation_id": request.operation_id,
            "plan_hash": request.plan_hash,
            "source": {
                "repo_commit": request.source_commit,
                "path": "inventory/hosts/atius-srv-4.yaml",
                "digest": request.source_digest,
                "projection_digest": request.projection_digest,
            },
            "transaction": {
                "backup_id": request.backup_id,
                "backup_digest": request.backup_digest,
                "backup": "created",
                "staged_digest": request.desired_config_digest,
                "stage": "same-filesystem-fsynced",
                "failed_stage": failed_stage,
                "validation": stages["validation"],
                "replace": stages["replace"],
                "activation": stages["activation"],
                "activation_wait": (
                    "bounded"
                    if stages["activation"] in {"completed", "failed"}
                    else "not-run"
                ),
                "health": stages["health"],
                "restore": {
                    "replace": "atomic" if restored else "not-required",
                    "activation": "completed" if restored else "not-required",
                    "health": "ready" if restored else "not-required",
                    "readback": "old-answer-verified" if restored else "not-required",
                    "restored_digest": restored_digest,
                },
            },
            "auto_restore": {
                "performed": restored,
                "reason": f"{failed_stage}-failed" if restored else "not-required",
                "old_answer_verified": restored,
            },
            "readback": readback,
        }

    def rollback(self, request: RollbackRequest) -> dict[str, Any]:
        self.security_hook()
        if request.discovery_digest != self._discovery_digest():
            raise HelperError("discovery drift")
        current, identity = self._read_data()
        if sha256_digest(current) != request.desired_config_digest:
            raise HelperError("current generation drift")
        preimage, binding = self._load_backup(request)
        if sha256_digest(preimage) != request.preimage_digest:
            raise HelperError("preimage digest mismatch")
        identity = _identity_from_binding(identity, binding)
        readback = self._restore(preimage, identity, request)
        return {
            "runbook_id": "phase25.coredns-rollback",
            "version": VERSION,
            "target_display_name": TARGET_DISPLAY_NAME,
            "status": "restored",
            "operation_id": request.operation_id,
            "origin_operation_id": request.origin_operation_id,
            "backup_id": request.backup_id,
            "backup_digest": request.backup_digest,
            "restored_digest": request.preimage_digest,
            "restore": "atomic",
            "activation": "completed",
            "activation_wait": "bounded",
            "health": "ready",
            "readback": readback,
        }


def _identity_from_binding(current: os.stat_result, binding: dict[str, Any]) -> os.stat_result:
    values = list(current)
    if len(values) >= 10:
        values[0] = (values[0] & ~0o7777) | int(binding["mode"], 8)
        values[4] = int(binding["uid"])
        values[5] = int(binding["gid"])
        return os.stat_result(values)
    return current


class LiveRuntime:
    CLEAN_ENV = {"LANG": "C", "LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}

    @staticmethod
    def _run(argv: Sequence[str], *, timeout: float = 15) -> bytes:
        try:
            result = subprocess.run(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=LiveRuntime.CLEAN_ENV,
                shell=False,
                check=False,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HelperError("fixed command failed") from exc
        if result.returncode != 0 or len(result.stdout) + len(result.stderr) > 131072:
            raise HelperError("fixed command failed")
        if _SENSITIVE.search((result.stdout + result.stderr).decode("utf-8", "ignore")):
            raise HelperError("fixed command output rejected")
        return result.stdout

    def validate(self, layout: Layout, staged_path: Path) -> None:
        value, _ = _read_regular(staged_path, "staged CoreDNS data")
        validate_data_bytes(layout.plugin, value)
        _, config_identity = _read_regular(layout.config_path, "CoreDNS config")
        if layout.plugin == "hosts":
            validation_config = (
                f".:0 {{\n    hosts {staged_path} {{\n        fallthrough\n    }}\n}}\n"
            )
        elif layout.plugin == "file":
            validation_config = (
                f"atius.internal.:0 {{\n    file {staged_path}\n}}\n"
            )
        else:
            raise HelperError("plugin rejected")
        temporary_config = _stage_bytes(
            layout.config_path,
            validation_config.encode("utf-8"),
            config_identity,
        )
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                [layout.binary_path, "-conf", str(temporary_config), "-dns.port", "0"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.CLEAN_ENV,
                shell=False,
                close_fds=True,
                start_new_session=True,
            )
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline and process.poll() is None:
                time.sleep(0.05)
            if process.poll() is not None and process.returncode != 0:
                raise HelperError("CoreDNS staged validation failed")
        except OSError as exc:
            raise HelperError("CoreDNS staged validation failed") from exc
        finally:
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError:
                        process.kill()
                    process.wait(timeout=2)
            if process is not None:
                stdout, stderr = process.communicate(timeout=1)
                output = stdout + stderr
                if len(output) > 131072 or _SENSITIVE.search(output.decode("utf-8", "ignore")):
                    raise HelperError("CoreDNS validation output rejected")
            temporary_config.unlink(missing_ok=True)

    def activate(self, layout: Layout) -> None:
        self._run(["/usr/bin/systemctl", "reload-or-restart", layout.unit], timeout=15)

    def healthy(self, layout: Layout) -> None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                self._run(["/usr/bin/systemctl", "is-active", "--quiet", layout.unit], timeout=3)
                return
            except HelperError:
                time.sleep(0.25)
        raise HelperError("CoreDNS health timeout")

    def _query(self, resolver: str, name: str) -> dict[str, Any]:
        address, port = resolver.rsplit(":", 1)
        raw = self._run(
            [
                "/usr/bin/dig", f"@{address}", "-p", port,
                "+time=3", "+tries=1", "+norecurse", "+noall", "+comments", "+answer",
                name, "A",
            ],
            timeout=5,
        )
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise HelperError("DNS output rejected") from exc
        status_match = re.search(r"status:\s*(NOERROR|NXDOMAIN)", text)
        flags_match = re.search(r"flags:\s*([^;]+);", text)
        if not status_match or not flags_match or "aa" not in flags_match.group(1).split():
            raise HelperError("DNS authority rejected")
        records: list[list[str]] = []
        for line in text.splitlines():
            if not line or line.startswith(";"):
                continue
            fields = line.split()
            if len(fields) < 5:
                raise HelperError("DNS record rejected")
            records.append(fields)
        status = status_match.group(1)
        if status == "NXDOMAIN":
            if records:
                raise HelperError("DNS NXDOMAIN answer rejected")
            return {"answer": "NXDOMAIN", "status": "nxdomain"}
        if len(records) != 1:
            raise HelperError("DNS answer cardinality rejected")
        owner, ttl, dns_class, record_type, answer_raw = records[0][:5]
        if (
            owner.rstrip(".").lower() != name.rstrip(".").lower()
            or not ttl.isdigit()
            or dns_class.upper() != "IN"
            or record_type.upper() != "A"
            or len(records[0]) != 5
        ):
            raise HelperError("DNS record identity rejected")
        try:
            answer = ip_address(answer_raw)
        except ValueError as exc:
            raise HelperError("DNS answer rejected") from exc
        if answer.version != 4:
            raise HelperError("DNS answer rejected")
        return {"answer": str(answer), "status": "resolved"}

    def readback(self, short_name: str, fqdn: str, expected_answer: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        observed: list[str] = []
        for role, resolver in (("primary", "10.11.1.11:53"), ("reserve", "10.100.100.1:53")):
            for name in (short_name, fqdn):
                answer = self._query(resolver, name)
                observed.append(answer["answer"])
                rows.append(
                    {
                        "resolver_role": role,
                        "resolver": resolver,
                        "name": name,
                        "record_type": "A",
                        "answer": answer["answer"],
                        "authoritative": True,
                        "status": answer["status"],
                    }
                )
        required = observed[0] if expected_answer == "AUTO" else expected_answer
        if any(answer != required for answer in observed):
            raise HelperError("DNS readback mismatch")
        return rows


_BINARY_CANDIDATES = (Path("/usr/local/bin/coredns"), Path("/usr/bin/coredns"))
_CONFIG_CANDIDATES = (
    Path("/etc/coredns/Corefile"),
    Path("/usr/local/etc/coredns/Corefile"),
    Path("/home/ubuntu/GitHub/vpn-atius/coredns/Corefile"),
)
_DATA_CANDIDATES = tuple(
    parent / name
    for parent in (Path("/etc/coredns"), Path("/usr/local/etc/coredns"), Path("/home/ubuntu/GitHub/vpn-atius/coredns"))
    for name in ("hosts", "hosts.atius", "atius.hosts", "db.atius.internal")
)
_UNIT_CANDIDATES = ("coredns-vpn.service", "coredns.service")


def data_candidates_for_plugin(plugin: str) -> tuple[Path, ...]:
    if plugin == "hosts":
        names = {"hosts", "hosts.atius", "atius.hosts"}
    elif plugin == "file":
        names = {"db.atius.internal"}
    else:
        raise HelperError("plugin rejected")
    return tuple(path for path in _DATA_CANDIDATES if path.name in names)


def activation_mode_from_systemd(can_reload: str) -> str:
    normalized = can_reload.strip().lower()
    if normalized == "yes":
        return "reload"
    if normalized == "no":
        return "restart"
    raise HelperError("CoreDNS CanReload state rejected")


def _one_existing(candidates: Sequence[Path], label: str) -> Path:
    existing = [candidate for candidate in candidates if candidate.is_file() and not candidate.is_symlink()]
    if len(existing) != 1:
        raise HelperError(f"{label} discovery rejected")
    return existing[0]


def discover_live_layout(runtime: LiveRuntime) -> Layout:
    binary = _one_existing(_BINARY_CANDIDATES, "binary")
    config = _one_existing(_CONFIG_CANDIDATES, "config")
    config_bytes, _ = _read_regular(config, "CoreDNS config")
    try:
        config_text = config_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HelperError("CoreDNS config encoding rejected") from exc
    matches: list[tuple[str, Path]] = []
    for plugin in ("hosts", "file"):
        for data in data_candidates_for_plugin(plugin):
            if re.search(rf"(?m)^\s*{plugin}\s+{re.escape(str(data))}(?:\s|\{{|$)", config_text):
                matches.append((plugin, data))
    if len(matches) != 1:
        raise HelperError("CoreDNS plugin discovery rejected")
    plugin, data = matches[0]
    _read_regular(data, "CoreDNS data")
    loaded_units = []
    for unit in _UNIT_CANDIDATES:
        try:
            value = runtime._run(["/usr/bin/systemctl", "show", "-p", "LoadState", "--value", unit], timeout=5)
        except HelperError:
            continue
        if value.decode("ascii", "ignore").strip() == "loaded":
            loaded_units.append(unit)
    if len(loaded_units) != 1:
        raise HelperError("CoreDNS unit discovery rejected")
    can_reload = runtime._run(
        [
            "/usr/bin/systemctl", "show", "-p", "CanReload", "--value",
            loaded_units[0],
        ],
        timeout=5,
    ).decode("ascii", "ignore")
    activation_mode = activation_mode_from_systemd(can_reload)
    version_raw = runtime._run([str(binary), "-version"], timeout=5).decode("ascii", "ignore")
    version_match = _VERSION.search(version_raw)
    if not version_match:
        raise HelperError("CoreDNS version rejected")
    reload_match = re.search(r"(?m)^\s*reload\s+([0-9]+)s\s*$", config_text)
    reload_seconds = int(reload_match.group(1)) if reload_match else 0
    if not 0 <= reload_seconds <= MAX_RELOAD_INTERVAL_SECONDS:
        raise HelperError("CoreDNS reload interval rejected")
    layout = Layout(
        binary_path=str(binary),
        version=version_match.group(0),
        unit=loaded_units[0],
        plugin=plugin,
        config_path=config,
        data_path=data,
        activation_mode=activation_mode,
        reload_interval_seconds=reload_seconds,
    )
    assert_live_layout_security(layout)
    return layout


def _assert_installed_identity(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise HelperError("installed helper unavailable") from exc
    if (
        path != INSTALLED_HELPER_PATH
        or stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != 0
        or info.st_gid != 0
        or stat.S_IMODE(info.st_mode) != 0o755
    ):
        raise HelperError("installed helper identity rejected")


@contextmanager
def _operation_lock() -> Any:
    import fcntl

    lock_path = Path("/run/lock/oci-admin-coredns-helper.lock")
    descriptor = os.open(
        lock_path,
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != 0
            or info.st_gid != 0
        ):
            raise HelperError("operation lock identity rejected")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _execute(request: InspectRequest | ApplyRequest | RollbackRequest) -> tuple[dict[str, Any], int]:
    if os.geteuid() != 0:
        raise HelperError("root required")
    path = Path(__file__).resolve()
    _assert_installed_identity(path)
    helper_bytes, _ = _read_regular(path, "installed helper")
    if sha256_digest(helper_bytes) != request.helper_digest:
        raise HelperError("helper digest mismatch")
    with _operation_lock():
        runtime = LiveRuntime()
        layout = discover_live_layout(runtime)
        pinned_io = PinnedLayoutIO(layout)
        try:
            manager = CoreDNSManager(
                layout=layout,
                backup_root=BACKUP_ROOT,
                runtime=runtime,
                enforce_root_storage=True,
                security_hook=lambda: assert_live_layout_security(layout),
                pinned_io=pinned_io,
            )
            if isinstance(request, InspectRequest):
                return manager.inspect(request, installed_helper_path=path), 0
            if isinstance(request, ApplyRequest):
                result = manager.apply(request)
                return result, 0 if result["status"] == "applied" else 2
            return manager.rollback(request), 0
        finally:
            pinned_io.close()


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077)
    try:
        request = parse_request(list(sys.argv[1:] if argv is None else argv))
        result, exit_code = _execute(request)
        sys.stdout.write(serialize_result(result))
        return exit_code
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        sys.stderr.write("oci-admin-coredns-helper: rejected\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
