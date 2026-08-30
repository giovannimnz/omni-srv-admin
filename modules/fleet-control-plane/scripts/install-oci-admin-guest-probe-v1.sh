#!/usr/bin/env bash
# modes: preview|install|rollback
# Production installs are fixed root:root 0755 (helper), root:root 0440 (sudoers),
# and root:root 0400 (host attestation).
# Fixed destinations: /usr/local/libexec/oci-admin-guest-probe-v1 and
# /etc/sudoers.d/102-oci-admin-guest-probe-v1 plus
# /etc/oci-admin-guest-probe-v1/attestation.json.
set -euo pipefail
set +x
IFS=$'\n\t'
umask 077

INSTALL_RECEIPT_SENTINEL='ATIUS_GUEST_PROBE_INSTALL_RECEIPT_V1'
SANITIZED_ERROR='oci-admin-guest-probe-installer-v1: rejected'

_usage() {
  printf '%s\n' \
    'usage: install-oci-admin-guest-probe-v1.sh <preview|install|rollback> --expected-source-commit COMMIT --expected-helper-sha256 SHA256 --expected-sudoers-sha256 SHA256 --expected-attestation-sha256 SHA256 --host-id HOST --rollback-receipt-id ID' >&2
  return 64
}

_internal_test=false
_destination_root=/
_failure_stage=''
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then
  if [[ ${OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING:-} == 1 ]]; then
    _internal_test=true
    _destination_root=${OCI_ADMIN_GUEST_PROBE_TEST_ROOT:-}
    _failure_stage=${OCI_ADMIN_GUEST_PROBE_TEST_FAIL_STAGE:-}
    [[ $_destination_root == /tmp/oci-admin-guest-probe-test.*/* ]] || return 64
    [[ -d $_destination_root && ! -L $_destination_root ]] || return 64
  elif [[ -n ${OCI_ADMIN_GUEST_PROBE_TEST_ROOT:-}${OCI_ADMIN_GUEST_PROBE_TEST_FAIL_STAGE:-} ]]; then
    return 64
  fi
elif [[ -n ${OCI_ADMIN_GUEST_PROBE_INTERNAL_TESTING:-}${OCI_ADMIN_GUEST_PROBE_TEST_ROOT:-}${OCI_ADMIN_GUEST_PROBE_TEST_FAIL_STAGE:-} ]]; then
  printf '%s\n' "$SANITIZED_ERROR" >&2
  exit 64
fi

_script_dir=$(unset CDPATH; cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
_repo_root=$(cd -- "$_script_dir/../../.." && pwd -P)

guest_probe_installer_main() {
  (($# == 13)) || { _usage; return 64; }
  local mode=$1
  shift
  [[ $mode == preview || $mode == install || $mode == rollback ]] || { _usage; return 64; }
  [[ $1 == --expected-source-commit ]] || { _usage; return 64; }
  local expected_source_commit=$2
  [[ $3 == --expected-helper-sha256 ]] || { _usage; return 64; }
  local expected_helper_sha256=$4
  [[ $5 == --expected-sudoers-sha256 ]] || { _usage; return 64; }
  local expected_sudoers_sha256=$6
  [[ $7 == --expected-attestation-sha256 ]] || { _usage; return 64; }
  local expected_attestation_sha256=$8
  [[ $9 == --host-id ]] || { _usage; return 64; }
  local host_id=${10}
  [[ ${11} == --rollback-receipt-id ]] || { _usage; return 64; }
  local rollback_receipt_id=${12}

  [[ $expected_source_commit =~ ^[0-9a-f]{40}$ ]] || { _usage; return 64; }
  [[ $expected_helper_sha256 =~ ^sha256:[0-9a-f]{64}$ ]] || { _usage; return 64; }
  [[ $expected_sudoers_sha256 =~ ^sha256:[0-9a-f]{64}$ ]] || { _usage; return 64; }
  [[ $expected_attestation_sha256 =~ ^sha256:[0-9a-f]{64}$ ]] || { _usage; return 64; }
  case $host_id in
    atius-srv-1|atius-srv-2|atius-srv-3|atius-srv-4|horistic-srv) ;;
    *) _usage; return 64 ;;
  esac
  [[ $rollback_receipt_id =~ ^[a-z0-9][a-z0-9._-]{2,63}$ ]] || { _usage; return 64; }

  local rc
  local restore_errexit=false
  [[ $- == *e* ]] && restore_errexit=true
  set +e
  /usr/bin/python3 -I - \
    "$mode" \
    "$_repo_root" \
    "$_destination_root" \
    "$expected_source_commit" \
    "$expected_helper_sha256" \
    "$expected_sudoers_sha256" \
    "$expected_attestation_sha256" \
    "$host_id" \
    "$rollback_receipt_id" \
    "$_internal_test" \
    "$_failure_stage" 3<&0 <<'PY'
from __future__ import annotations

import ast
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


(
    mode,
    repo_root_raw,
    destination_root_raw,
    expected_source_commit,
    expected_helper_sha256,
    expected_sudoers_sha256,
    expected_attestation_sha256,
    host_id,
    receipt_id,
    internal_test_raw,
    failure_stage,
) = sys.argv[1:]

SENTINEL = "ATIUS_GUEST_PROBE_INSTALL_RECEIPT_V1"
CLEAN_ENV = {"LANG": "C", "LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}
ALLOWED_FAILURE_STAGES = {
    "",
    "preimage",
    "helper-stage",
    "attestation-stage",
    "sudoers-stage",
    "helper-replace",
    "attestation-replace",
    "sudoers-replace",
    "global-visudo",
    "readback",
}


class InstallerError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def digest_file(path: Path) -> str:
    try:
        return digest_bytes(path.read_bytes())
    except OSError as exc:
        raise InstallerError("managed file unavailable") from exc


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def regular_file(path: Path, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise InstallerError(f"{label} unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise InstallerError(f"{label} identity drift")
    return info


def ensure_safe_chain(path: Path, root: Path, *, create: bool, final_mode: int = 0o755) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise InstallerError("path escaped fixed root") from exc
    current = root
    root_info = root.lstat()
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise InstallerError("destination root is unsafe")
    for index, part in enumerate(relative.parts):
        current = current / part
        if lexists(current):
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise InstallerError("destination parent chain is unsafe")
        elif create:
            current.mkdir(mode=final_mode if index == len(relative.parts) - 1 else 0o755)
        else:
            return


def fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_bytes(path: Path, data: bytes, mode_value: int, uid: int, gid: int) -> None:
    ensure_safe_chain(path.parent, destination_root, create=True)
    if lexists(path):
        regular_file(path, "atomic target")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode_value)
        os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = -1
        os.replace(temporary, path)
        fsync_parent(path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def stage_bytes(path: Path, data: bytes, mode_value: int, uid: int, gid: int) -> Path:
    ensure_safe_chain(path.parent, destination_root, create=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.stage.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode_value)
        os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return temporary
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def run_checked(argv: list[str]) -> bytes:
    result = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=CLEAN_ENV,
        shell=False,
        check=False,
        timeout=15,
    )
    if result.returncode != 0 or len(result.stdout) + len(result.stderr) > 131072:
        raise InstallerError("fixed validation command failed")
    return result.stdout


def validate_python(path: Path) -> None:
    try:
        ast.parse(path.read_bytes(), filename=path.name)
    except (OSError, SyntaxError) as exc:
        raise InstallerError("helper syntax validation failed") from exc


def validate_python_bytes(data: bytes) -> None:
    try:
        ast.parse(data, filename="oci-admin-guest-probe-v1.py")
    except SyntaxError as exc:
        raise InstallerError("helper syntax validation failed") from exc


def validate_sudoers(path: Path) -> None:
    run_checked(["/usr/sbin/visudo", "-cf", str(path)])


def validate_sudoers_bytes(data: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix="oci-admin-guest-probe-sudoers.")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = -1
        os.chmod(temporary, 0o440)
        validate_sudoers(temporary)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def validate_global_sudoers() -> None:
    if internal_test:
        if lexists(sudoers_destination):
            regular_file(sudoers_destination, "installed sudoers")
            validate_sudoers(sudoers_destination)
        else:
            validate_sudoers(sudoers_source)
    else:
        run_checked(["/usr/sbin/visudo", "-c"])


def git_output(arguments: list[str]) -> str:
    raw = run_checked(["/usr/bin/git", "-C", str(repo_root), *arguments])
    try:
        return raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise InstallerError("source git output invalid") from exc


def read_pinned_source(path: Path, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InstallerError(f"{label} unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or not 1 <= before.st_size <= 1048576
        ):
            raise InstallerError(f"{label} identity drift")
        chunks: list[bytes] = []
        remaining = 1048577
        while remaining > 0:
            chunk = os.read(descriptor, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if remaining <= 0:
            raise InstallerError(f"{label} is oversized")
        after = os.fstat(descriptor)
        current = path.lstat()
        if (
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino)
        ):
            raise InstallerError(f"{label} changed during verification")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def verify_sources() -> tuple[bytes, bytes]:
    for source in (helper_source, sudoers_source, installer_source):
        regular_file(source, "managed source")
    head = git_output(["rev-parse", "--verify", "HEAD"])
    if head != expected_source_commit:
        raise InstallerError("source commit mismatch")
    tracked = git_output(
        [
            "ls-files",
            "--error-unmatch",
            str(helper_source.relative_to(repo_root)),
            str(sudoers_source.relative_to(repo_root)),
            str(installer_source.relative_to(repo_root)),
        ]
    ).splitlines()
    if len(tracked) != 3:
        raise InstallerError("managed source is not tracked")
    dirty = git_output(
        [
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            str(helper_source.relative_to(repo_root)),
            str(sudoers_source.relative_to(repo_root)),
            str(installer_source.relative_to(repo_root)),
        ]
    )
    if dirty:
        raise InstallerError("managed source is dirty")
    helper_bytes = read_pinned_source(helper_source, "helper source")
    sudoers_bytes = read_pinned_source(sudoers_source, "sudoers source")
    if digest_bytes(helper_bytes) != expected_helper_sha256:
        raise InstallerError("helper source digest mismatch")
    if digest_bytes(sudoers_bytes) != expected_sudoers_sha256:
        raise InstallerError("sudoers source digest mismatch")
    validate_python_bytes(helper_bytes)
    validate_sudoers_bytes(sudoers_bytes)
    return helper_bytes, sudoers_bytes


def read_attestation_input() -> bytes:
    chunks: list[bytes] = []
    remaining = 65537
    while remaining > 0:
        chunk = os.read(3, min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    if remaining <= 0:
        raise InstallerError("attestation input is oversized")
    raw = b"".join(chunks)
    if not raw:
        raise InstallerError("attestation input is missing")
    return raw


def validate_attestation_input(raw: bytes, helper_bytes: bytes) -> tuple[bytes, str]:
    namespace: dict[str, Any] = {
        "__name__": "oci_admin_guest_probe_validator",
        "__file__": str(helper_source),
    }
    try:
        exec(compile(helper_bytes, str(helper_source), "exec"), namespace)
        binding = namespace["validate_attestation_bytes"](
            raw,
            expected_digest=expected_attestation_sha256,
            expected_target=host_id,
        )
        canonical_bytes = binding["canonical_bytes"]
        digest = binding["digest"]
    except BaseException as exc:
        raise InstallerError("attestation validation failed") from exc
    if not isinstance(canonical_bytes, bytes) or digest != expected_attestation_sha256:
        raise InstallerError("attestation validation failed")
    return canonical_bytes, digest_bytes(canonical_bytes)


def preimage(path: Path, label: str, backup_directory: Path | None) -> dict[str, Any]:
    ensure_safe_chain(path.parent, destination_root, create=False)
    if not lexists(path):
        return {"state": "ABSENT"}
    info = regular_file(path, f"{label} preimage")
    data = path.read_bytes()
    record: dict[str, Any] = {
        "state": "PRESENT",
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": format(stat.S_IMODE(info.st_mode), "04o"),
        "digest": digest_bytes(data),
    }
    if backup_directory is not None:
        backup = backup_directory / f"{label}.preimage"
        atomic_bytes(backup, data, 0o600, install_uid, install_gid)
        record["backup"] = backup.name
    return record


def installed_readback(path: Path, expected_digest: str, expected_mode: int) -> dict[str, Any]:
    info = regular_file(path, "installed target")
    digest = digest_file(path)
    if (
        digest != expected_digest
        or stat.S_IMODE(info.st_mode) != expected_mode
        or info.st_uid != install_uid
        or info.st_gid != install_gid
    ):
        raise InstallerError("installed readback mismatch")
    return {
        "state": "PRESENT",
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": format(stat.S_IMODE(info.st_mode), "04o"),
        "digest": digest,
    }


def restored_readback(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    if expected["state"] == "ABSENT":
        if lexists(path):
            raise InstallerError("absence was not restored")
        return {"state": "ABSENT"}
    info = regular_file(path, "restored target")
    actual = {
        "state": "PRESENT",
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mode": format(stat.S_IMODE(info.st_mode), "04o"),
        "digest": digest_file(path),
    }
    expected_public = {key: expected[key] for key in ("state", "uid", "gid", "mode", "digest")}
    if actual != expected_public:
        raise InstallerError("preimage readback mismatch")
    return actual


def restore(path: Path, record: dict[str, Any], backup_directory: Path) -> None:
    if record["state"] == "ABSENT":
        if lexists(path):
            regular_file(path, "rollback target")
            path.unlink()
            fsync_parent(path)
        return
    backup_name = record.get("backup")
    if not isinstance(backup_name, str) or not re.fullmatch(r"[a-z]+\.preimage", backup_name):
        raise InstallerError("rollback backup reference invalid")
    backup = backup_directory / backup_name
    regular_file(backup, "rollback backup")
    if digest_file(backup) != record["digest"]:
        raise InstallerError("rollback backup digest mismatch")
    mode_value = int(record["mode"], 8)
    atomic_bytes(path, backup.read_bytes(), mode_value, record["uid"], record["gid"])


def make_receipt(
    *,
    receipt_mode: str,
    status: str,
    preimages: dict[str, Any],
    readback: dict[str, Any],
    rollback_status: str,
    attestation_file_sha256: str,
) -> dict[str, Any]:
    body = {
        "schema": "atius.oci-admin-guest-probe-install-receipt/v1",
        "mode": receipt_mode,
        "status": status,
        "host_id": host_id,
        "source_commit": expected_source_commit,
        "rollback_receipt_id": receipt_id,
        "sources": {
            "helper_sha256": expected_helper_sha256,
            "sudoers_sha256": expected_sudoers_sha256,
            "attestation_sha256": expected_attestation_sha256,
            "attestation_file_sha256": attestation_file_sha256,
        },
        "preimages": preimages,
        "readback": readback,
        "rollback": {"status": rollback_status},
    }
    body["receipt_digest"] = digest_bytes(canonical(body))
    return body


def emit(receipt: dict[str, Any]) -> None:
    sys.stdout.write(f"{SENTINEL} {canonical(receipt).decode('utf-8')}\n")


def write_state(payload: dict[str, Any]) -> None:
    atomic_bytes(state_path, canonical(payload) + b"\n", 0o600, install_uid, install_gid)


def load_state() -> dict[str, Any]:
    info = regular_file(state_path, "install state")
    if stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != install_uid or info.st_gid != install_gid:
        raise InstallerError("install state identity drift")
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallerError("install state invalid") from exc
    required = {
        "schema",
        "status",
        "host_id",
        "source_commit",
        "receipt_id",
        "helper_sha256",
        "sudoers_sha256",
        "attestation_sha256",
        "attestation_file_sha256",
        "preimages",
        "install_receipt",
        "rollback_receipt",
    }
    if not isinstance(payload, dict) or set(payload) != required or payload["schema"] != 1:
        raise InstallerError("install state shape drift")
    identity = (
        payload["host_id"],
        payload["source_commit"],
        payload["receipt_id"],
        payload["helper_sha256"],
        payload["sudoers_sha256"],
        payload["attestation_sha256"],
    )
    expected = (
        host_id,
        expected_source_commit,
        receipt_id,
        expected_helper_sha256,
        expected_sudoers_sha256,
        expected_attestation_sha256,
    )
    if identity != expected:
        raise InstallerError("install state identity mismatch")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(payload["attestation_file_sha256"])):
        raise InstallerError("install state attestation file digest is invalid")
    if set(payload["preimages"]) != {"helper", "sudoers", "attestation"}:
        raise InstallerError("install state preimages invalid")
    return payload


def store_receipt(receipt: dict[str, Any]) -> None:
    digest = receipt["receipt_digest"].removeprefix("sha256:")
    receipt_path = receipt_directory / f"receipt-{digest}.json"
    if lexists(receipt_path):
        regular_file(receipt_path, "stored receipt")
        if receipt_path.read_bytes() != canonical(receipt) + b"\n":
            raise InstallerError("receipt digest collision")
        return
    atomic_bytes(receipt_path, canonical(receipt) + b"\n", 0o600, install_uid, install_gid)


def inject(stage: str) -> None:
    if failure_stage == stage:
        raise InstallerError("injected stage failure")


internal_test = internal_test_raw == "true"
if failure_stage not in ALLOWED_FAILURE_STAGES or (failure_stage and not internal_test):
    raise SystemExit(2)
repo_root = Path(repo_root_raw).resolve()
destination_root = Path(destination_root_raw).resolve()
if internal_test:
    if not re.fullmatch(r"/tmp/oci-admin-guest-probe-test\.[^/]+/[^/]+", str(destination_root)):
        raise SystemExit(2)
elif destination_root != Path("/"):
    raise SystemExit(2)
if not destination_root.is_dir() or destination_root.is_symlink():
    raise SystemExit(2)
if mode != "preview" and not internal_test and os.geteuid() != 0:
    raise SystemExit(2)

helper_source = repo_root / "modules/fleet-control-plane/tools/oci-admin-guest-probe-v1.py"
sudoers_source = repo_root / "modules/fleet-control-plane/configs/102-oci-admin-guest-probe-v1.sudoers"
installer_source = repo_root / "modules/fleet-control-plane/scripts/install-oci-admin-guest-probe-v1.sh"
helper_destination = destination_root / "usr/local/libexec/oci-admin-guest-probe-v1"
sudoers_destination = destination_root / "etc/sudoers.d/102-oci-admin-guest-probe-v1"
attestation_destination = destination_root / "etc/oci-admin-guest-probe-v1/attestation.json"
state_root = destination_root / "var/lib/oci-admin-guest-probe-v1"
receipt_directory = state_root / "receipts" / receipt_id
backup_directory = receipt_directory / "preimages"
state_path = receipt_directory / "state.json"
install_uid = destination_root.stat().st_uid if internal_test else 0
install_gid = destination_root.stat().st_gid if internal_test else 0


def preview() -> int:
    helper_bytes, _ = verify_sources()
    _, attestation_file_sha256 = validate_attestation_input(
        read_attestation_input(), helper_bytes
    )
    preimages = {
        "helper": preimage(helper_destination, "helper", None),
        "sudoers": preimage(sudoers_destination, "sudoers", None),
        "attestation": preimage(attestation_destination, "attestation", None),
    }
    receipt = make_receipt(
        receipt_mode="preview",
        status="preview",
        preimages=preimages,
        readback={},
        rollback_status="not-run",
        attestation_file_sha256=attestation_file_sha256,
    )
    emit(receipt)
    return 0


def prepare_control_plane() -> int:
    def ensure_control_directory(path: Path) -> None:
        existed = lexists(path)
        ensure_safe_chain(path, destination_root, create=True, final_mode=0o700)
        info = path.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or (existed and stat.S_IMODE(info.st_mode) != 0o700)
            or (existed and (info.st_uid != install_uid or info.st_gid != install_gid))
        ):
            raise InstallerError("control directory identity drift")
        if not existed:
            os.chmod(path, 0o700)
            os.chown(path, install_uid, install_gid)

    ensure_control_directory(state_root)
    ensure_control_directory(state_root / "receipts")
    ensure_control_directory(receipt_directory)
    ensure_control_directory(backup_directory)
    lock_path = state_root / "installer.lock"
    lock_existed = lexists(lock_path)
    descriptor = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    lock_info = os.fstat(descriptor)
    if (
        not stat.S_ISREG(lock_info.st_mode)
        or lock_info.st_nlink != 1
        or (
            lock_existed
            and (
                stat.S_IMODE(lock_info.st_mode) != 0o600
                or lock_info.st_uid != install_uid
                or lock_info.st_gid != install_gid
            )
        )
    ):
        os.close(descriptor)
        raise InstallerError("control lock identity drift")
    os.fchmod(descriptor, 0o600)
    os.fchown(descriptor, install_uid, install_gid)
    return descriptor


def install() -> int:
    helper_source_bytes, sudoers_source_bytes = verify_sources()
    attestation_source_bytes, attestation_file_sha256 = validate_attestation_input(
        read_attestation_input(), helper_source_bytes
    )
    lock_descriptor = prepare_control_plane()
    with os.fdopen(lock_descriptor, "rb+", closefd=True):
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        if lexists(state_path):
            state = load_state()
            if state["status"] == "installed":
                if attestation_file_sha256 != state["attestation_file_sha256"]:
                    raise InstallerError("attestation receipt identity mismatch")
                installed_readback(helper_destination, expected_helper_sha256, 0o755)
                installed_readback(sudoers_destination, expected_sudoers_sha256, 0o440)
                installed_readback(
                    attestation_destination,
                    state["attestation_file_sha256"],
                    0o400,
                )
                emit(state["install_receipt"])
                return 0
            if state["status"] in {"prepared", "failed-restored"}:
                restore(helper_destination, state["preimages"]["helper"], backup_directory)
                restore(sudoers_destination, state["preimages"]["sudoers"], backup_directory)
                restore(
                    attestation_destination,
                    state["preimages"]["attestation"],
                    backup_directory,
                )
                validate_global_sudoers()
            raise InstallerError("receipt is not reusable for install")

        preimages = {
            "helper": preimage(helper_destination, "helper", backup_directory),
            "sudoers": preimage(sudoers_destination, "sudoers", backup_directory),
            "attestation": preimage(
                attestation_destination, "attestation", backup_directory
            ),
        }
        state = {
            "schema": 1,
            "status": "prepared",
            "host_id": host_id,
            "source_commit": expected_source_commit,
            "receipt_id": receipt_id,
            "helper_sha256": expected_helper_sha256,
            "sudoers_sha256": expected_sudoers_sha256,
            "attestation_sha256": expected_attestation_sha256,
            "attestation_file_sha256": attestation_file_sha256,
            "preimages": preimages,
            "install_receipt": None,
            "rollback_receipt": None,
        }
        write_state(state)
        helper_stage: Path | None = None
        attestation_stage: Path | None = None
        sudoers_stage: Path | None = None
        try:
            inject("preimage")
            helper_stage = stage_bytes(
                helper_destination,
                helper_source_bytes,
                0o755,
                install_uid,
                install_gid,
            )
            validate_python(helper_stage)
            inject("helper-stage")
            attestation_stage = stage_bytes(
                attestation_destination,
                attestation_source_bytes,
                0o400,
                install_uid,
                install_gid,
            )
            inject("attestation-stage")
            sudoers_stage = stage_bytes(
                sudoers_destination,
                sudoers_source_bytes,
                0o440,
                install_uid,
                install_gid,
            )
            validate_sudoers(sudoers_stage)
            inject("sudoers-stage")
            os.replace(helper_stage, helper_destination)
            helper_stage = None
            fsync_parent(helper_destination)
            inject("helper-replace")
            os.replace(attestation_stage, attestation_destination)
            attestation_stage = None
            fsync_parent(attestation_destination)
            inject("attestation-replace")
            os.replace(sudoers_stage, sudoers_destination)
            sudoers_stage = None
            fsync_parent(sudoers_destination)
            inject("sudoers-replace")
            validate_global_sudoers()
            inject("global-visudo")
            readback = {
                "helper": installed_readback(
                    helper_destination, expected_helper_sha256, 0o755
                ),
                "sudoers": installed_readback(
                    sudoers_destination, expected_sudoers_sha256, 0o440
                ),
                "attestation": installed_readback(
                    attestation_destination, attestation_file_sha256, 0o400
                ),
            }
            inject("readback")
        except BaseException:
            if helper_stage is not None:
                helper_stage.unlink(missing_ok=True)
            if attestation_stage is not None:
                attestation_stage.unlink(missing_ok=True)
            if sudoers_stage is not None:
                sudoers_stage.unlink(missing_ok=True)
            restore(helper_destination, preimages["helper"], backup_directory)
            restore(sudoers_destination, preimages["sudoers"], backup_directory)
            restore(
                attestation_destination,
                preimages["attestation"],
                backup_directory,
            )
            validate_global_sudoers()
            restored = {
                "helper": restored_readback(helper_destination, preimages["helper"]),
                "sudoers": restored_readback(sudoers_destination, preimages["sudoers"]),
                "attestation": restored_readback(
                    attestation_destination, preimages["attestation"]
                ),
            }
            failure_receipt = make_receipt(
                receipt_mode="install",
                status="failed-restored",
                preimages=preimages,
                readback=restored,
                rollback_status="restored",
                attestation_file_sha256=attestation_file_sha256,
            )
            state["status"] = "failed-restored"
            state["rollback_receipt"] = failure_receipt
            write_state(state)
            store_receipt(failure_receipt)
            emit(failure_receipt)
            return 2

        install_receipt = make_receipt(
            receipt_mode="install",
            status="installed",
            preimages=preimages,
            readback=readback,
            rollback_status="available",
            attestation_file_sha256=attestation_file_sha256,
        )
        state["status"] = "installed"
        state["install_receipt"] = install_receipt
        write_state(state)
        store_receipt(install_receipt)
        emit(install_receipt)
        return 0


def rollback() -> int:
    verify_sources()
    lock_descriptor = prepare_control_plane()
    with os.fdopen(lock_descriptor, "rb+", closefd=True):
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        state = load_state()
        if state["status"] == "rolled-back":
            restored_readback(helper_destination, state["preimages"]["helper"])
            restored_readback(sudoers_destination, state["preimages"]["sudoers"])
            restored_readback(
                attestation_destination, state["preimages"]["attestation"]
            )
            emit(state["rollback_receipt"])
            return 0
        if state["status"] == "installed":
            installed_readback(helper_destination, expected_helper_sha256, 0o755)
            installed_readback(sudoers_destination, expected_sudoers_sha256, 0o440)
            installed_readback(
                attestation_destination,
                state["attestation_file_sha256"],
                0o400,
            )
        elif state["status"] == "failed-restored":
            restored_readback(helper_destination, state["preimages"]["helper"])
            restored_readback(sudoers_destination, state["preimages"]["sudoers"])
            restored_readback(
                attestation_destination, state["preimages"]["attestation"]
            )
        else:
            raise InstallerError("rollback state is invalid")
        state["status"] = "rolling-back"
        write_state(state)
        restore(helper_destination, state["preimages"]["helper"], backup_directory)
        restore(sudoers_destination, state["preimages"]["sudoers"], backup_directory)
        restore(
            attestation_destination,
            state["preimages"]["attestation"],
            backup_directory,
        )
        validate_global_sudoers()
        readback = {
            "helper": restored_readback(helper_destination, state["preimages"]["helper"]),
            "sudoers": restored_readback(sudoers_destination, state["preimages"]["sudoers"]),
            "attestation": restored_readback(
                attestation_destination, state["preimages"]["attestation"]
            ),
        }
        receipt = make_receipt(
            receipt_mode="rollback",
            status="rolled-back",
            preimages=state["preimages"],
            readback=readback,
            rollback_status="restored",
            attestation_file_sha256=state["attestation_file_sha256"],
        )
        state["status"] = "rolled-back"
        state["rollback_receipt"] = receipt
        write_state(state)
        store_receipt(receipt)
        emit(receipt)
        return 0


try:
    if mode == "preview":
        exit_code = preview()
    elif mode == "install":
        exit_code = install()
    elif mode == "rollback":
        exit_code = rollback()
    else:
        exit_code = 2
except BaseException:
    exit_code = 2
raise SystemExit(exit_code)
PY
  rc=$?
  if $restore_errexit; then
    set -e
  else
    set +e
  fi
  if ((rc != 0)); then
    printf '%s\n' "$SANITIZED_ERROR" >&2
  fi
  return "$rc"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  guest_probe_installer_main "$@"
fi
