#!/usr/bin/env bash
# modes: install|rollback
# Production destinations are fixed root:root 0755 and root:root 0440.
# Fixed helper: /usr/local/libexec/oci-admin-coredns-helper
# Fixed sudoers: /etc/sudoers.d/101-oci-admin-coredns-run-command
# Fixed production installer: /usr/local/sbin/install-oci-admin-coredns-helper
# Fixed production source repo: /home/ubuntu/GitHub/omni-srv-admin
# install --expected-commit COMMIT --expected-helper-sha256 SHA256
#         --expected-sudoers-sha256 SHA256 --run-command-user ocarun
# rollback --receipt RECEIPT_ID
set -euo pipefail
set +x
IFS=$'\n\t'
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

INSTALL_RECEIPT_SENTINEL='ATIUS_COREDNS_INSTALL_RECEIPT_V1'
SANITIZED_ERROR='oci-admin-coredns-installer: rejected'

_usage() {
  printf '%s\n' \
    'usage: install-oci-admin-coredns-helper.sh install --expected-commit COMMIT --expected-helper-sha256 SHA256 --expected-sudoers-sha256 SHA256 --run-command-user ocarun' \
    '   or: install-oci-admin-coredns-helper.sh rollback --receipt RECEIPT_ID' >&2
  return 64
}

_internal_test=false
_destination_root=/
_failure_stage=''
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then
  if [[ ${OCI_ADMIN_COREDNS_INTERNAL_TESTING:-} == 1 ]]; then
    _internal_test=true
    _destination_root=${OCI_ADMIN_COREDNS_TEST_ROOT:-}
    _failure_stage=${OCI_ADMIN_COREDNS_TEST_FAIL_STAGE:-}
    [[ $_destination_root == /tmp/oci-admin-coredns-installer-test.*/* ]] || return 64
    [[ -d $_destination_root && ! -L $_destination_root ]] || return 64
  elif [[ -n ${OCI_ADMIN_COREDNS_TEST_ROOT:-}${OCI_ADMIN_COREDNS_TEST_FAIL_STAGE:-} ]]; then
    return 64
  fi
elif [[ -n ${OCI_ADMIN_COREDNS_INTERNAL_TESTING:-}${OCI_ADMIN_COREDNS_TEST_ROOT:-}${OCI_ADMIN_COREDNS_TEST_FAIL_STAGE:-} ]]; then
  printf '%s\n' "$SANITIZED_ERROR" >&2
  exit 64
fi

_runtime_installer=$(readlink -f -- "${BASH_SOURCE[0]}")
if $_internal_test; then
  _script_dir=$(unset CDPATH; cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
  _repo_root=$(cd -- "$_script_dir/../../.." && pwd -P)
else
  if [[ $_runtime_installer != /usr/local/sbin/install-oci-admin-coredns-helper \
        || -L ${BASH_SOURCE[0]} \
        || $(/usr/bin/stat -c '%U:%G:%a' -- "$_runtime_installer" 2>/dev/null) != root:root:755 ]]; then
    printf '%s\n' "$SANITIZED_ERROR" >&2
    if [[ ${BASH_SOURCE[0]} != "$0" ]]; then return 64; else exit 64; fi
  fi
  _repo_root=/home/ubuntu/GitHub/omni-srv-admin
fi

coredns_installer_main() {
  local mode=${1:-}
  local expected_commit=''
  local expected_helper_sha256=''
  local expected_sudoers_sha256=''
  local run_command_user=''
  local receipt_id=''

  if [[ $mode == install ]]; then
    (($# == 9)) || { _usage; return 64; }
    [[ $2 == --expected-commit ]] || { _usage; return 64; }
    expected_commit=$3
    [[ $4 == --expected-helper-sha256 ]] || { _usage; return 64; }
    expected_helper_sha256=$5
    [[ $6 == --expected-sudoers-sha256 ]] || { _usage; return 64; }
    expected_sudoers_sha256=$7
    [[ $8 == --run-command-user ]] || { _usage; return 64; }
    run_command_user=$9
    [[ $expected_commit =~ ^[0-9a-f]{40}$ ]] || { _usage; return 64; }
    [[ $expected_helper_sha256 =~ ^sha256:[0-9a-f]{64}$ ]] || { _usage; return 64; }
    [[ $expected_sudoers_sha256 =~ ^sha256:[0-9a-f]{64}$ ]] || { _usage; return 64; }
    [[ $run_command_user == ocarun ]] || { _usage; return 64; }
  elif [[ $mode == rollback ]]; then
    (($# == 3)) || { _usage; return 64; }
    [[ $2 == --receipt ]] || { _usage; return 64; }
    receipt_id=$3
    [[ $receipt_id =~ ^phase25-[0-9a-f]{32}$ ]] || { _usage; return 64; }
  else
    _usage
    return 64
  fi

  local restore_errexit=false
  [[ $- == *e* ]] && restore_errexit=true
  set +e
  /usr/bin/python3 -I - \
    "$mode" \
    "$_repo_root" \
    "$_runtime_installer" \
    "$_destination_root" \
    "$expected_commit" \
    "$expected_helper_sha256" \
    "$expected_sudoers_sha256" \
    "$run_command_user" \
    "$receipt_id" \
    "$_internal_test" \
    "$_failure_stage" <<'PY'
from __future__ import annotations

import ast
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any


(
    mode,
    repo_root_raw,
    runtime_installer_raw,
    destination_root_raw,
    expected_commit,
    expected_helper_sha256,
    expected_sudoers_sha256,
    run_command_user,
    receipt_id,
    internal_test_raw,
    failure_stage,
) = sys.argv[1:]

SENTINEL = "ATIUS_COREDNS_INSTALL_RECEIPT_V1"
CLEAN_ENV = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/nonexistent",
    "XDG_CONFIG_HOME": "/nonexistent",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_NO_LAZY_FETCH": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_COUNT": "3",
    "GIT_CONFIG_KEY_0": "core.hooksPath",
    "GIT_CONFIG_VALUE_0": "/dev/null",
    "GIT_CONFIG_KEY_1": "core.fsmonitor",
    "GIT_CONFIG_VALUE_1": "false",
    "GIT_CONFIG_KEY_2": "protocol.file.allow",
    "GIT_CONFIG_VALUE_2": "never",
}
ALLOWED_FAILURE_STAGES = {
    "",
    "preimage",
    "helper-stage",
    "sudoers-stage",
    "helper-replace",
    "sudoers-replace",
    "global-visudo",
    "readback",
    "rollback-sudoers-closed",
    "rollback-helper-restored",
    "rollback-sudoers-restored",
    "rollback-validated",
    "rollback-readback",
}


class InstallerError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def regular_file(path: Path, label: str) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as exc:
        raise InstallerError(f"{label} unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise InstallerError(f"{label} identity rejected")
    return info


def fsync_parent(path: Path) -> None:
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_chain(path: Path, root: Path, *, create: bool, final_mode: int = 0o755) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise InstallerError("fixed path escaped destination root") from exc
    root_info = root.lstat()
    if (
        stat.S_ISLNK(root_info.st_mode)
        or not stat.S_ISDIR(root_info.st_mode)
        or root_info.st_uid != install_uid
        or root_info.st_gid != install_gid
        or stat.S_IMODE(root_info.st_mode) & 0o022
    ):
        raise InstallerError("destination root identity rejected")
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        if lexists(current):
            info = current.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISDIR(info.st_mode)
                or info.st_uid != install_uid
                or info.st_gid != install_gid
                or stat.S_IMODE(info.st_mode) & 0o022
            ):
                raise InstallerError("destination parent identity rejected")
        elif create:
            current.mkdir(mode=final_mode if index == len(relative.parts) - 1 else 0o755)
            os.chown(current, install_uid, install_gid)
            fsync_parent(current)
            fsync_directory(current)
        else:
            return


def stage_bytes(path: Path, value: bytes, mode_value: int, uid: int, gid: int) -> Path:
    ensure_chain(path.parent, destination_root, create=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.stage.", dir=path.parent)
    staged = Path(name)
    try:
        os.fchmod(descriptor, mode_value)
        os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        return staged
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        staged.unlink(missing_ok=True)
        raise


def atomic_bytes(path: Path, value: bytes, mode_value: int, uid: int, gid: int) -> None:
    staged = stage_bytes(path, value, mode_value, uid, gid)
    try:
        os.replace(staged, path)
        fsync_parent(path)
    finally:
        staged.unlink(missing_ok=True)


def run_checked(
    argv: list[str],
    *,
    maximum_bytes: int = 1048576,
    preexec_fn: Any | None = None,
) -> bytes:
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=CLEAN_ENV,
            shell=False,
            check=False,
            timeout=15,
            preexec_fn=preexec_fn,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallerError("fixed validation command failed") from exc
    if result.returncode != 0 or len(result.stdout) + len(result.stderr) > maximum_bytes:
        raise InstallerError("fixed validation command failed")
    return result.stdout


def source_owner_preexec() -> None:
    if os.geteuid() == source_owner_uid and os.getegid() == source_owner_gid:
        return
    os.setgroups([])
    os.setgid(source_owner_gid)
    os.setuid(source_owner_uid)


def git_bytes(arguments: list[str], maximum_bytes: int = 1048576) -> bytes:
    return run_checked(
        ["/usr/bin/git", "-C", str(repo_root), *arguments],
        maximum_bytes=maximum_bytes,
        preexec_fn=source_owner_preexec,
    )


def git_text(arguments: list[str]) -> str:
    try:
        return git_bytes(arguments, 4096).decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise InstallerError("git output rejected") from exc


def read_source(path: Path, label: str) -> bytes:
    info = regular_file(path, label)
    if (
        not 1 <= info.st_size <= 1048576
        or info.st_uid != source_owner_uid
        or info.st_gid != source_owner_gid
        or stat.S_IMODE(info.st_mode) & 0o022
    ):
        raise InstallerError(f"{label} size rejected")
    try:
        value = path.read_bytes()
        after = path.lstat()
    except OSError as exc:
        raise InstallerError(f"{label} unavailable") from exc
    if (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise InstallerError(f"{label} changed during verification")
    return value


def validate_sources() -> tuple[bytes, bytes]:
    helper = read_source(helper_source, "helper source")
    sudoers = read_source(sudoers_source, "sudoers source")
    installer = read_source(installer_source, "installer source")
    runtime_info = regular_file(runtime_installer, "runtime installer")
    runtime_bytes = runtime_installer.read_bytes()
    if not internal_test and (
        runtime_installer != Path("/usr/local/sbin/install-oci-admin-coredns-helper")
        or runtime_info.st_uid != 0
        or runtime_info.st_gid != 0
        or stat.S_IMODE(runtime_info.st_mode) != 0o755
    ):
        raise InstallerError("runtime installer identity rejected")
    if git_text(["rev-parse", "--show-toplevel"]) != str(repo_root):
        raise InstallerError("source repository identity rejected")
    if git_text(["rev-parse", "HEAD"]) != expected_commit:
        raise InstallerError("source commit mismatch")
    committed_installer = b""
    for source, working in ((helper_source, helper), (sudoers_source, sudoers), (installer_source, installer)):
        relative = source.relative_to(repo_root).as_posix()
        committed = git_bytes(["cat-file", "blob", f"{expected_commit}:{relative}"])
        if committed != working:
            raise InstallerError("source differs from expected commit")
        if source == installer_source:
            committed_installer = committed
    if runtime_bytes != committed_installer:
        raise InstallerError("runtime installer differs from expected commit")
    if digest_bytes(helper) != expected_helper_sha256 or digest_bytes(sudoers) != expected_sudoers_sha256:
        raise InstallerError("source digest mismatch")
    try:
        ast.parse(helper, filename=helper_source.name)
    except SyntaxError as exc:
        raise InstallerError("helper syntax rejected") from exc
    run_checked(["/usr/bin/bash", "-n", str(installer_source)], maximum_bytes=4096)
    validate_sudoers_bytes(sudoers)
    return helper, sudoers


def validate_sudoers(path: Path) -> None:
    run_checked(["/usr/sbin/visudo", "-cf", str(path)], maximum_bytes=65536)


def validate_sudoers_bytes(value: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix="oci-admin-coredns-sudoers.")
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o440)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        validate_sudoers(temporary)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)


def validate_global_sudoers() -> None:
    if internal_test:
        if lexists(sudoers_destination):
            validate_sudoers(sudoers_destination)
        else:
            validate_sudoers(sudoers_source)
    else:
        run_checked(["/usr/sbin/visudo", "-c"], maximum_bytes=65536)


def preimage(path: Path, label: str, backup_directory: Path) -> dict[str, Any]:
    if not lexists(path):
        return {"state": "ABSENT"}
    info = regular_file(path, label)
    value = path.read_bytes()
    backup = backup_directory / label
    atomic_bytes(backup, value, 0o600, install_uid, install_gid)
    return {
        "state": "PRESENT",
        "digest": digest_bytes(value),
        "mode": f"{stat.S_IMODE(info.st_mode):04o}",
        "uid": info.st_uid,
        "gid": info.st_gid,
        "backup": backup.name,
    }


def read_control_backup(path: Path) -> bytes:
    info = regular_file(path, "preimage backup")
    if (
        stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != install_uid
        or info.st_gid != install_gid
        or not 1 <= info.st_size <= 1048576
    ):
        raise InstallerError("preimage backup identity rejected")
    return path.read_bytes()


def installed_readback(path: Path, expected_digest: str, expected_mode: int) -> dict[str, Any]:
    info = regular_file(path, "installed file")
    digest = digest_bytes(path.read_bytes())
    if (
        digest != expected_digest
        or stat.S_IMODE(info.st_mode) != expected_mode
        or info.st_uid != install_uid
        or info.st_gid != install_gid
    ):
        raise InstallerError("installed readback mismatch")
    return {
        "state": "PRESENT",
        "digest": digest,
        "mode": f"{expected_mode:04o}",
        "uid": info.st_uid,
        "gid": info.st_gid,
    }


def restore_one(path: Path, label: str, item: dict[str, Any], backup_directory: Path) -> None:
    if item == {"state": "ABSENT"}:
        if lexists(path):
            regular_file(path, label)
            path.unlink()
            fsync_parent(path)
        return
    if set(item) != {"state", "digest", "mode", "uid", "gid", "backup"} or item["state"] != "PRESENT":
        raise InstallerError("preimage metadata rejected")
    backup = backup_directory / item["backup"]
    value = read_control_backup(backup)
    if digest_bytes(value) != item["digest"]:
        raise InstallerError("preimage backup digest mismatch")
    atomic_bytes(path, value, int(item["mode"], 8), int(item["uid"]), int(item["gid"]))


def restored_readback(path: Path, item: dict[str, Any]) -> dict[str, Any]:
    if item == {"state": "ABSENT"}:
        if lexists(path):
            raise InstallerError("absent preimage was not restored")
        return {"state": "ABSENT"}
    info = regular_file(path, "restored file")
    digest = digest_bytes(path.read_bytes())
    if (
        digest != item["digest"]
        or stat.S_IMODE(info.st_mode) != int(item["mode"], 8)
        or info.st_uid != int(item["uid"])
        or info.st_gid != int(item["gid"])
    ):
        raise InstallerError("restored preimage mismatch")
    return {key: item[key] for key in ("state", "digest", "mode", "uid", "gid")}


def write_state(payload: dict[str, Any]) -> None:
    atomic_bytes(state_path, canonical(payload) + b"\n", 0o600, install_uid, install_gid)


def load_state(path: Path) -> dict[str, Any]:
    info = regular_file(path, "install state")
    if (
        stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != install_uid
        or info.st_gid != install_gid
        or not 1 <= info.st_size <= 65536
    ):
        raise InstallerError("install state identity rejected")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallerError("install state rejected") from exc
    required = {
        "schema", "status", "receipt_id", "source_commit", "helper_sha256",
        "sudoers_sha256", "run_command_user", "preimages", "install_receipt",
        "rollback_receipt", "install_stage", "rollback_stage",
    }
    if not isinstance(payload, dict) or set(payload) != required or payload["schema"] != 1:
        raise InstallerError("install state shape rejected")
    if (
        not re.fullmatch(r"phase25-[0-9a-f]{32}", str(payload["receipt_id"]))
        or not re.fullmatch(r"[0-9a-f]{40}", str(payload["source_commit"]))
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(payload["helper_sha256"]))
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(payload["sudoers_sha256"]))
        or payload["run_command_user"] != "ocarun"
        or set(payload["preimages"]) != {"helper", "sudoers"}
        or payload["status"] not in {
            "prepared", "rolling-back", "failed-restored", "installed", "rolled-back"
        }
        or payload["install_stage"] not in {
            "prepared", "helper-replaced", "sudoers-replaced", "validated",
            "readback-complete", "restored",
        }
        or payload["rollback_stage"] not in {
            "not-started", "sudoers-closed", "helper-restored",
            "sudoers-restored", "validated", "readback-complete",
        }
    ):
        raise InstallerError("install state identity rejected")
    return payload


def make_receipt(
    *, receipt_mode: str, status: str, state: dict[str, Any], readback: dict[str, Any]
) -> dict[str, Any]:
    body = {
        "schema": "atius.oci-admin-coredns-install-receipt/v1",
        "mode": receipt_mode,
        "status": status,
        "receipt_id": state["receipt_id"],
        "source_commit": state["source_commit"],
        "run_command_user": state["run_command_user"],
        "sources": {
            "helper_sha256": state["helper_sha256"],
            "sudoers_sha256": state["sudoers_sha256"],
        },
        "preimages": state["preimages"],
        "readback": readback,
        "rollback": {
            "available": status == "installed",
            "restored": status in {"failed-restored", "rolled-back"},
        },
    }
    body["receipt_digest"] = digest_bytes(canonical(body))
    return body


def emit(receipt: dict[str, Any]) -> None:
    sys.stdout.write(f"{SENTINEL} {canonical(receipt).decode('utf-8')}\n")


def inject(stage: str) -> None:
    if failure_stage == stage:
        raise InstallerError("injected failure")


def restore_all(state: dict[str, Any]) -> dict[str, Any]:
    # Close the grant first, restore the helper, then restore the sudoers preimage last.
    stages = [
        "not-started", "sudoers-closed", "helper-restored",
        "sudoers-restored", "validated", "readback-complete",
    ]
    position = stages.index(state["rollback_stage"])
    if position < 1:
        if lexists(sudoers_destination):
            regular_file(sudoers_destination, "sudoers")
            sudoers_destination.unlink()
            fsync_parent(sudoers_destination)
        state["rollback_stage"] = "sudoers-closed"
        write_state(state)
        inject("rollback-sudoers-closed")
    if position < 2:
        restore_one(helper_destination, "helper", state["preimages"]["helper"], backup_directory)
        state["rollback_stage"] = "helper-restored"
        write_state(state)
        inject("rollback-helper-restored")
    if position < 3:
        restore_one(sudoers_destination, "sudoers", state["preimages"]["sudoers"], backup_directory)
        state["rollback_stage"] = "sudoers-restored"
        write_state(state)
        inject("rollback-sudoers-restored")
    if position < 4:
        validate_global_sudoers()
        state["rollback_stage"] = "validated"
        write_state(state)
        inject("rollback-validated")
    readback = {
        "helper": restored_readback(helper_destination, state["preimages"]["helper"]),
        "sudoers": restored_readback(sudoers_destination, state["preimages"]["sudoers"]),
    }
    if position < 5:
        state["rollback_stage"] = "readback-complete"
        write_state(state)
        inject("rollback-readback")
    return readback


internal_test = internal_test_raw == "true"
if failure_stage not in ALLOWED_FAILURE_STAGES or (failure_stage and not internal_test):
    raise SystemExit(64)
repo_root = Path(repo_root_raw).resolve()
runtime_installer = Path(runtime_installer_raw).resolve()
destination_root = Path(destination_root_raw).resolve()
if internal_test:
    if not re.fullmatch(r"/tmp/oci-admin-coredns-installer-test\.[^/]+/[^/]+", str(destination_root)):
        raise SystemExit(64)
elif destination_root != Path("/"):
    raise SystemExit(64)
if not destination_root.is_dir() or destination_root.is_symlink():
    raise SystemExit(64)
if not internal_test and os.geteuid() != 0:
    raise SystemExit(2)
repo_info = repo_root.lstat()
if repo_root.is_symlink() or not repo_root.is_dir() or stat.S_IMODE(repo_info.st_mode) & 0o022:
    raise SystemExit(2)
if not internal_test and repo_info.st_uid == 0:
    raise SystemExit(2)
source_owner_uid = repo_info.st_uid
source_owner_gid = repo_info.st_gid
if not internal_test:
    try:
        user_info = pwd.getpwnam("ocarun")
    except KeyError as exc:
        raise InstallerError("Run Command user unavailable") from exc
    if run_command_user and user_info.pw_name != run_command_user:
        raise InstallerError("Run Command user mismatch")

helper_source = repo_root / "modules/srv1-ops/scripts/oci-admin-coredns-helper.py"
installer_source = repo_root / "modules/srv1-ops/scripts/install-oci-admin-coredns-helper.sh"
sudoers_source = repo_root / "modules/srv1-ops/configs/101-oci-admin-coredns-run-command.sudoers"
helper_destination = destination_root / "usr/local/libexec/oci-admin-coredns-helper"
sudoers_destination = destination_root / "etc/sudoers.d/101-oci-admin-coredns-run-command"
state_root = destination_root / "var/lib/oci-admin-coredns-helper/install"
install_uid = destination_root.stat().st_uid if internal_test else 0
install_gid = destination_root.stat().st_gid if internal_test else 0


def prepare_receipt(receipt: str) -> None:
    global receipt_directory, backup_directory, state_path
    receipt_directory = state_root / "receipts" / receipt
    backup_directory = receipt_directory / "preimages"
    state_path = receipt_directory / "state.json"
    ensure_chain(state_root, destination_root, create=True, final_mode=0o700)
    ensure_chain(state_root / "receipts", destination_root, create=True, final_mode=0o700)
    ensure_chain(receipt_directory, destination_root, create=True, final_mode=0o700)
    ensure_chain(backup_directory, destination_root, create=True, final_mode=0o700)
    for directory in (state_root, state_root / "receipts", receipt_directory, backup_directory):
        info = directory.lstat()
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != install_uid
            or info.st_gid != install_gid
        ):
            raise InstallerError("control directory identity rejected")


def acquire_lock() -> int:
    ensure_chain(state_root, destination_root, create=True, final_mode=0o700)
    lock_path = state_root / "installer.lock"
    descriptor = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(descriptor)
        raise InstallerError("installer lock rejected")
    os.fchmod(descriptor, 0o600)
    os.fchown(descriptor, install_uid, install_gid)
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    return descriptor


def install() -> int:
    if run_command_user != "ocarun":
        raise InstallerError("Run Command user rejected")
    helper, sudoers = validate_sources()
    identity = canonical(
        {
            "source_commit": expected_commit,
            "helper_sha256": expected_helper_sha256,
            "sudoers_sha256": expected_sudoers_sha256,
            "run_command_user": run_command_user,
        }
    )
    current_receipt = "phase25-" + sha256(identity).hexdigest()[:32]
    prepare_receipt(current_receipt)
    lock = acquire_lock()
    try:
        if lexists(state_path):
            state = load_state(state_path)
            if (
                state["receipt_id"] != current_receipt
                or state["source_commit"] != expected_commit
                or state["helper_sha256"] != expected_helper_sha256
                or state["sudoers_sha256"] != expected_sudoers_sha256
                or state["run_command_user"] != run_command_user
            ):
                raise InstallerError("receipt identity mismatch")
            if state["status"] == "installed":
                installed_readback(helper_destination, expected_helper_sha256, 0o755)
                installed_readback(sudoers_destination, expected_sudoers_sha256, 0o440)
                emit(state["install_receipt"])
                return 0
            if state["status"] in {"prepared", "rolling-back"}:
                if state["status"] == "prepared":
                    state["status"] = "rolling-back"
                    state["rollback_stage"] = "not-started"
                    write_state(state)
                restore_all(state)
                state["status"] = "failed-restored"
                state["install_stage"] = "restored"
                state["rollback_stage"] = "readback-complete"
                write_state(state)
            if state["status"] in {"failed-restored", "rolled-back"}:
                restored_readback(helper_destination, state["preimages"]["helper"])
                restored_readback(sudoers_destination, state["preimages"]["sudoers"])
                state["status"] = "prepared"
                state["install_stage"] = "prepared"
                state["install_receipt"] = None
                state["rollback_receipt"] = None
                state["rollback_stage"] = "not-started"
                write_state(state)
            else:
                raise InstallerError("receipt is not reusable")
        else:
            preimages = {
                "helper": preimage(helper_destination, "helper", backup_directory),
                "sudoers": preimage(sudoers_destination, "sudoers", backup_directory),
            }
            validate_global_sudoers()
            state = {
                "schema": 1,
                "status": "prepared",
                "install_stage": "prepared",
                "receipt_id": current_receipt,
                "source_commit": expected_commit,
                "helper_sha256": expected_helper_sha256,
                "sudoers_sha256": expected_sudoers_sha256,
                "run_command_user": run_command_user,
                "preimages": preimages,
                "install_receipt": None,
                "rollback_receipt": None,
                "rollback_stage": "not-started",
            }
            write_state(state)
        helper_stage: Path | None = None
        sudoers_stage: Path | None = None
        try:
            inject("preimage")
            helper_stage = stage_bytes(helper_destination, helper, 0o755, install_uid, install_gid)
            ast.parse(helper_stage.read_bytes(), filename=helper_stage.name)
            inject("helper-stage")
            sudoers_stage = stage_bytes(sudoers_destination, sudoers, 0o440, install_uid, install_gid)
            validate_sudoers(sudoers_stage)
            inject("sudoers-stage")
            os.replace(helper_stage, helper_destination)
            helper_stage = None
            fsync_parent(helper_destination)
            state["install_stage"] = "helper-replaced"
            write_state(state)
            inject("helper-replace")
            os.replace(sudoers_stage, sudoers_destination)
            sudoers_stage = None
            fsync_parent(sudoers_destination)
            state["install_stage"] = "sudoers-replaced"
            write_state(state)
            inject("sudoers-replace")
            validate_global_sudoers()
            state["install_stage"] = "validated"
            write_state(state)
            inject("global-visudo")
            readback = {
                "helper": installed_readback(helper_destination, expected_helper_sha256, 0o755),
                "sudoers": installed_readback(sudoers_destination, expected_sudoers_sha256, 0o440),
            }
            state["install_stage"] = "readback-complete"
            write_state(state)
            inject("readback")
        except BaseException:
            if helper_stage is not None:
                helper_stage.unlink(missing_ok=True)
            if sudoers_stage is not None:
                sudoers_stage.unlink(missing_ok=True)
            state["status"] = "rolling-back"
            state["rollback_stage"] = "not-started"
            write_state(state)
            readback = restore_all(state)
            state["status"] = "failed-restored"
            state["install_stage"] = "restored"
            state["rollback_stage"] = "readback-complete"
            receipt = make_receipt(
                receipt_mode="install", status="failed-restored", state=state, readback=readback
            )
            state["rollback_receipt"] = receipt
            write_state(state)
            emit(receipt)
            return 2
        receipt = make_receipt(
            receipt_mode="install", status="installed", state=state, readback=readback
        )
        state["status"] = "installed"
        state["install_stage"] = "readback-complete"
        state["install_receipt"] = receipt
        write_state(state)
        emit(receipt)
        return 0
    finally:
        os.close(lock)


def rollback() -> int:
    prepare_receipt(receipt_id)
    lock = acquire_lock()
    try:
        state = load_state(state_path)
        if state["receipt_id"] != receipt_id:
            raise InstallerError("receipt identity mismatch")
        if state["status"] == "rolled-back":
            restored_readback(helper_destination, state["preimages"]["helper"])
            restored_readback(sudoers_destination, state["preimages"]["sudoers"])
            emit(state["rollback_receipt"])
            return 0
        if state["status"] == "installed":
            installed_readback(helper_destination, state["helper_sha256"], 0o755)
            installed_readback(sudoers_destination, state["sudoers_sha256"], 0o440)
            state["status"] = "rolling-back"
            state["rollback_stage"] = "not-started"
            write_state(state)
        elif state["status"] == "failed-restored":
            restored_readback(helper_destination, state["preimages"]["helper"])
            restored_readback(sudoers_destination, state["preimages"]["sudoers"])
            state["status"] = "rolling-back"
            state["rollback_stage"] = "readback-complete"
            write_state(state)
        elif state["status"] == "prepared":
            state["status"] = "rolling-back"
            state["rollback_stage"] = "not-started"
            write_state(state)
        elif state["status"] != "rolling-back":
            raise InstallerError("rollback state rejected")
        readback = restore_all(state)
        state["status"] = "rolled-back"
        state["install_stage"] = "restored"
        state["rollback_stage"] = "readback-complete"
        receipt = make_receipt(
            receipt_mode="rollback", status="rolled-back", state=state, readback=readback
        )
        state["rollback_receipt"] = receipt
        write_state(state)
        emit(receipt)
        return 0
    finally:
        os.close(lock)


try:
    exit_code = install() if mode == "install" else rollback()
except BaseException:
    exit_code = 2
raise SystemExit(exit_code)
PY
  local rc=$?
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
  coredns_installer_main "$@"
fi
