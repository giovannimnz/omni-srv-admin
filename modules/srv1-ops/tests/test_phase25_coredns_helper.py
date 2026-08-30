from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap
from typing import Any

import pytest


OMNI_REPO = Path(__file__).resolve().parents[3]
HELPER_PATH = OMNI_REPO / "modules/srv1-ops/scripts/oci-admin-coredns-helper.py"
INSTALLER_PATH = OMNI_REPO / "modules/srv1-ops/scripts/install-oci-admin-coredns-helper.sh"
SUDOERS_PATH = OMNI_REPO / "modules/srv1-ops/configs/101-oci-admin-coredns-run-command.sudoers"


def _load_helper() -> Any:
    assert HELPER_PATH.is_file(), "Phase 25 CoreDNS helper has not been implemented"
    spec = importlib.util.spec_from_file_location("oci_admin_coredns_helper", HELPER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


class FakeRuntime:
    def __init__(self, helper: Any, layout: Any) -> None:
        self.helper = helper
        self.layout = layout
        self.validated: list[Path] = []
        self.activations = 0
        self.health_checks = 0
        self.readbacks: list[str] = []

    def validate(self, layout: Any, staged_path: Path) -> None:
        assert layout == self.layout
        assert staged_path.parent == layout.data_path.parent
        assert staged_path.is_file()
        self.helper.validate_data_bytes(layout.plugin, staged_path.read_bytes())
        self.validated.append(staged_path)

    def activate(self, layout: Any) -> None:
        assert layout == self.layout
        self.activations += 1

    def healthy(self, layout: Any) -> None:
        assert layout == self.layout
        self.health_checks += 1

    def readback(self, short_name: str, fqdn: str, expected_answer: str) -> list[dict[str, Any]]:
        assert (short_name, fqdn) == ("atius-srv-4", "atius-srv-4.atius.internal")
        if expected_answer == "AUTO":
            expected_answer = "NXDOMAIN"
        self.readbacks.append(expected_answer)
        status = "nxdomain" if expected_answer == "NXDOMAIN" else "resolved"
        return [
            {
                "resolver_role": role,
                "resolver": resolver,
                "name": name,
                "record_type": "A",
                "answer": expected_answer,
                "authoritative": True,
                "status": status,
            }
            for role, resolver in (("primary", "10.11.1.11:53"), ("reserve", "10.100.100.1:53"))
            for name in (short_name, fqdn)
        ]


def _layout(helper: Any, root: Path) -> Any:
    config_path = root / "etc/coredns/Corefile"
    data_path = root / "etc/coredns/hosts.atius"
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(b".:53 {\n    hosts /etc/coredns/hosts.atius {\n        reload 5s\n    }\n}\n")
    data_path.write_bytes(b"10.11.1.11 atius-srv-1 atius-srv-1.atius.internal\n")
    data_path.chmod(0o640)
    return helper.Layout(
        binary_path="/usr/local/bin/coredns",
        version="1.12.0",
        unit="coredns-vpn.service",
        plugin="hosts",
        config_path=config_path,
        data_path=data_path,
        activation_mode="reload",
        reload_interval_seconds=5,
    )


def _inspect_request(helper: Any) -> Any:
    return helper.InspectRequest(
        manifest_digest=helper.MANIFEST_DIGESTS["inspect"],
        target_binding_digest="sha256:" + "1" * 64,
        operation_id="phase25-inspect",
        plan_hash="sha256:" + "2" * 64,
        source_commit="3" * 40,
        source_digest="sha256:" + "4" * 64,
        projection_digest="sha256:" + "5" * 64,
        helper_digest="sha256:" + "6" * 64,
        sentinel=helper.SENTINEL,
    )


def _apply_request(helper: Any, layout: Any) -> Any:
    preimage = layout.data_path.read_bytes()
    desired = helper.render_desired_data(
        layout.plugin, preimage, short_name="atius-srv-4", fqdn="atius-srv-4.atius.internal", expected_address="10.14.1.14"
    )
    preimage_digest = _digest(preimage)
    return helper.ApplyRequest(
        manifest_digest=helper.MANIFEST_DIGESTS["apply"],
        target_binding_digest="sha256:" + "1" * 64,
        operation_id="phase25-apply",
        plan_hash="sha256:" + "2" * 64,
        source_commit="3" * 40,
        source_digest="sha256:" + "4" * 64,
        projection_digest="sha256:" + "5" * 64,
        discovery_digest=helper.layout_digest(layout),
        preimage_digest=preimage_digest,
        desired_config_digest=_digest(desired),
        helper_digest="sha256:" + "6" * 64,
        backup_id="phase25-backup-001",
        backup_digest=preimage_digest,
        short_name="atius-srv-4",
        fqdn="atius-srv-4.atius.internal",
        expected_address="10.14.1.14",
        previous_answer="NXDOMAIN",
        sentinel=helper.SENTINEL,
    )


def _manager(helper: Any, root: Path, *, fault_stage: str | None = None) -> tuple[Any, Any, Any]:
    layout = _layout(helper, root)
    runtime = FakeRuntime(helper, layout)
    fired = False

    def fault(stage: str) -> None:
        nonlocal fired
        if stage == fault_stage and not fired:
            fired = True
            raise helper.HelperError(f"injected {stage}")

    manager = helper.CoreDNSManager(
        layout=layout,
        backup_root=root / "var/lib/oci-admin-coredns-helper/backups",
        runtime=runtime,
        fault_hook=fault,
    )
    return manager, runtime, layout


def test_helper_cli_accepts_only_exact_manifest_bound_argv() -> None:
    helper = _load_helper()
    request = _inspect_request(helper)
    argv = [
        "inspect", "--manifest-digest", request.manifest_digest,
        "--target-binding-digest", request.target_binding_digest,
        "--operation-id", request.operation_id,
        "--plan-hash", request.plan_hash,
        "--source-commit", request.source_commit,
        "--source-digest", request.source_digest,
        "--projection-digest", request.projection_digest,
        "--helper-digest", request.helper_digest,
        "--sentinel", request.sentinel,
    ]
    assert helper.parse_request(argv) == request
    for candidate in (
        ["execute", *argv[1:]],
        [*argv, "--config-path", "/tmp/Corefile"],
        [*argv, "--unit", "caller.service"],
        [*argv, "--command", "id"],
        [*argv[:-1], "wrong-sentinel"],
        [*argv[:4], "sha256:" + "A" * 64, *argv[5:]],
        [*argv[:6], "bad;id", *argv[7:]],
    ):
        with pytest.raises(helper.HelperError):
            helper.parse_request(candidate)


def test_inspect_reports_fixed_layout_preimage_and_exact_authoritative_rows(tmp_path: Path) -> None:
    helper = _load_helper()
    manager, runtime, layout = _manager(helper, tmp_path)
    request = _inspect_request(helper)
    request = helper.InspectRequest(**{**request.__dict__, "helper_digest": _digest(HELPER_PATH.read_bytes())})
    result = manager.inspect(request, installed_helper_path=HELPER_PATH)
    assert set(result) == {"runbook_id", "version", "target_display_name", "owner", "coredns", "helper", "preimage", "before_readback"}
    assert result["target_display_name"] == "atius-srv-1"
    assert result["owner"] == {"machine_id": "atius-srv-1", "effective_user": "ocarun"}
    assert result["coredns"]["unit"] == "coredns-vpn.service"
    assert result["coredns"]["plugin"] == "hosts"
    assert result["preimage"] == {"config_digest": _digest(layout.config_path.read_bytes()), "data_digest": _digest(layout.data_path.read_bytes())}
    assert len(result["before_readback"]) == 4
    assert all(row["authoritative"] is True for row in result["before_readback"])
    assert runtime.readbacks == ["NXDOMAIN"]


def test_apply_is_same_filesystem_atomic_and_preserves_identity(tmp_path: Path) -> None:
    helper = _load_helper()
    manager, runtime, layout = _manager(helper, tmp_path)
    request = _apply_request(helper, layout)
    before = layout.data_path.stat()
    result = manager.apply(request)
    after = layout.data_path.stat()
    desired = helper.render_desired_data("hosts", b"10.11.1.11 atius-srv-1 atius-srv-1.atius.internal\n", short_name=request.short_name, fqdn=request.fqdn, expected_address=request.expected_address)
    assert result["status"] == "applied"
    assert result["transaction"]["stage"] == "same-filesystem-fsynced"
    assert result["transaction"]["replace"] == "atomic"
    assert result["transaction"]["backup"] == "created"
    assert layout.data_path.read_bytes() == desired
    assert stat.S_IMODE(after.st_mode) == stat.S_IMODE(before.st_mode)
    assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)
    backup = manager.backup_path(request.backup_id, request.backup_digest)
    assert backup.is_file() and _digest(backup.read_bytes()) == request.backup_digest
    assert runtime.validated and runtime.activations == 1 and runtime.health_checks == 1
    assert runtime.readbacks == ["10.14.1.14"]


@pytest.mark.parametrize("failure_stage", ["validation", "replace", "activation", "health", "readback"])
def test_apply_failure_self_restores_and_proves_old_answer(tmp_path: Path, failure_stage: str) -> None:
    helper = _load_helper()
    manager, runtime, layout = _manager(helper, tmp_path, fault_stage=failure_stage)
    request = _apply_request(helper, layout)
    preimage = layout.data_path.read_bytes()
    before = layout.data_path.stat()
    result = manager.apply(request)
    after = layout.data_path.stat()
    assert result["status"] == "restored"
    assert result["transaction"]["failed_stage"] == failure_stage
    assert result["transaction"]["restore"] == {"replace": "atomic", "activation": "completed", "health": "ready", "readback": "old-answer-verified", "restored_digest": _digest(preimage)}
    assert result["auto_restore"] == {"performed": True, "reason": f"{failure_stage}-failed", "old_answer_verified": True}
    assert layout.data_path.read_bytes() == preimage
    assert stat.S_IMODE(after.st_mode) == stat.S_IMODE(before.st_mode)
    assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)
    assert runtime.readbacks[-1] == "NXDOMAIN"


def test_rollback_accepts_only_bound_backup_and_restores_preimage(tmp_path: Path) -> None:
    helper = _load_helper()
    manager, runtime, layout = _manager(helper, tmp_path)
    apply_request = _apply_request(helper, layout)
    preimage = layout.data_path.read_bytes()
    assert manager.apply(apply_request)["status"] == "applied"
    request = helper.RollbackRequest(
        manifest_digest=helper.MANIFEST_DIGESTS["rollback"], target_binding_digest=apply_request.target_binding_digest,
        operation_id="phase25-rollback", plan_hash=apply_request.plan_hash, origin_operation_id=apply_request.operation_id,
        backup_id=apply_request.backup_id, backup_digest=apply_request.backup_digest,
        discovery_digest=apply_request.discovery_digest, preimage_digest=apply_request.preimage_digest,
        desired_config_digest=apply_request.desired_config_digest, helper_digest=apply_request.helper_digest,
        short_name=apply_request.short_name, fqdn=apply_request.fqdn, previous_answer=apply_request.previous_answer,
        sentinel=helper.SENTINEL,
    )
    result = manager.rollback(request)
    assert result["status"] == "restored" and result["restore"] == "atomic"
    assert result["restored_digest"] == _digest(preimage)
    assert layout.data_path.read_bytes() == preimage and runtime.readbacks[-1] == "NXDOMAIN"
    wrong = helper.RollbackRequest(**{**request.__dict__, "backup_digest": "sha256:" + "f" * 64})
    with pytest.raises(helper.HelperError):
        manager.rollback(wrong)


def test_hosts_and_file_rendering_are_closed_and_deterministic() -> None:
    helper = _load_helper()
    hosts = b"# retained\n10.14.1.99 atius-srv-4 old.alias\n"
    rendered_hosts = helper.render_desired_data("hosts", hosts, short_name="atius-srv-4", fqdn="atius-srv-4.atius.internal", expected_address="10.14.1.14")
    assert rendered_hosts == b"# retained\n10.14.1.14 atius-srv-4 atius-srv-4.atius.internal\n"
    helper.validate_data_bytes("hosts", rendered_hosts)
    zone = b"$ORIGIN atius.internal.\n@ 60 IN SOA ns hostmaster 1 60 60 60 60\n"
    rendered_zone = helper.render_desired_data("file", zone, short_name="atius-srv-4", fqdn="atius-srv-4.atius.internal", expected_address="10.14.1.14")
    assert b"atius-srv-4 60 IN A 10.14.1.14\n" in rendered_zone
    helper.validate_data_bytes("file", rendered_zone)
    with pytest.raises(helper.HelperError):
        helper.render_desired_data("hosts", b"10.14.1.14 atius-srv-4\n10.14.1.15 atius-srv-4.atius.internal\n", short_name="atius-srv-4", fqdn="atius-srv-4.atius.internal", expected_address="10.14.1.14")


def test_result_serialization_is_single_compact_sentinel() -> None:
    helper = _load_helper()
    line = helper.serialize_result({"z": 1, "a": "ok"})
    assert line == f'{helper.SENTINEL} {json.dumps({"a": "ok", "z": 1}, separators=(",", ":"), sort_keys=True)}\n'
    assert len(line.encode("utf-8")) <= helper.MAX_RESULT_BYTES


def _wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    relative = resolved.as_posix().split(":", 1)[1].lstrip("/")
    return f"/mnt/{drive}/{relative}"


def _bash(command: str, *args: str) -> subprocess.CompletedProcess[str]:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", suffix=".sh", delete=False
        ) as stream:
            stream.write("#!/usr/bin/env bash\n")
            stream.write(command)
            stream.write("\n")
            temporary_path = Path(stream.name)
        return subprocess.run(
            ["bash", _wsl_path(temporary_path), *args],
            check=False,
            text=True,
            capture_output=True,
            timeout=60,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _installer_harness(body: str) -> subprocess.CompletedProcess[str]:
    setup = r"""
set -euo pipefail
workspace=$(mktemp -d /tmp/oci-admin-coredns-installer-test.XXXXXX)
case "$workspace" in /tmp/oci-admin-coredns-installer-test.*) ;; *) exit 91 ;; esac
trap 'rm -rf -- "$workspace"' EXIT
source_repo="$workspace/source"
test_root="$workspace/root"
mkdir -p "$source_repo/modules/srv1-ops/scripts"
mkdir -p "$source_repo/modules/srv1-ops/configs"
mkdir -p "$test_root"
cp -- "$1" "$source_repo/modules/srv1-ops/scripts/oci-admin-coredns-helper.py"
cp -- "$2" "$source_repo/modules/srv1-ops/scripts/install-oci-admin-coredns-helper.sh"
cp -- "$3" "$source_repo/modules/srv1-ops/configs/101-oci-admin-coredns-run-command.sudoers"
git -C "$source_repo" init -q
git -C "$source_repo" config user.email phase25-test@atius.invalid
git -C "$source_repo" config user.name phase25-test
git -C "$source_repo" config commit.gpgsign false
git -C "$source_repo" add modules/srv1-ops/scripts/oci-admin-coredns-helper.py
git -C "$source_repo" add modules/srv1-ops/scripts/install-oci-admin-coredns-helper.sh
git -C "$source_repo" add modules/srv1-ops/configs/101-oci-admin-coredns-run-command.sudoers
git -C "$source_repo" commit -q -m fixture
source_commit=$(git -C "$source_repo" rev-parse HEAD)
helper_sha="sha256:$(sha256sum "$source_repo/modules/srv1-ops/scripts/oci-admin-coredns-helper.py" | awk '{print $1}')"
sudoers_sha="sha256:$(sha256sum "$source_repo/modules/srv1-ops/configs/101-oci-admin-coredns-run-command.sudoers" | awk '{print $1}')"
installer="$source_repo/modules/srv1-ops/scripts/install-oci-admin-coredns-helper.sh"
installer_args=(
  --expected-commit "$source_commit"
  --expected-helper-sha256 "$helper_sha"
  --expected-sudoers-sha256 "$sudoers_sha"
  --run-command-user ocarun
)
"""
    return _bash(
        setup + "\n" + textwrap.dedent(body),
        _wsl_path(HELPER_PATH),
        _wsl_path(INSTALLER_PATH),
        _wsl_path(SUDOERS_PATH),
    )


def test_installer_and_sudoers_contract_is_closed_and_syntax_valid() -> None:
    assert INSTALLER_PATH.is_file(), "Phase 25 CoreDNS installer has not been implemented"
    assert SUDOERS_PATH.is_file(), "Phase 25 CoreDNS sudoers has not been implemented"
    installer = INSTALLER_PATH.read_text(encoding="utf-8")
    sudoers = SUDOERS_PATH.read_text(encoding="utf-8")
    normalized = sudoers.replace("\\:", ":")

    assert "install|rollback" in installer
    assert "--expected-commit" in installer
    assert "--expected-helper-sha256" in installer
    assert "--expected-sudoers-sha256" in installer
    assert "--run-command-user ocarun" in installer
    assert "rollback --receipt" in installer
    assert "--root" not in installer
    assert "--source" not in installer
    assert "--command" not in installer
    assert "/usr/local/libexec/oci-admin-coredns-helper" in installer
    assert "/etc/sudoers.d/101-oci-admin-coredns-run-command" in installer
    assert "root:root" in installer and "0755" in installer and "0440" in installer
    assert "bash" in installer and "-n" in installer
    assert "ast.parse" in installer
    assert "visudo" in installer and "-cf" in installer and "-c" in installer
    assert "os.replace" in installer and "fsync" in installer

    assert "Defaults:ocarun env_reset" in sudoers
    assert "Defaults:ocarun !setenv" in sudoers
    assert "ocarun ALL=(root) NOPASSWD:" in sudoers
    assert "/usr/local/libexec/oci-admin-coredns-helper inspect" in sudoers
    assert "/usr/local/libexec/oci-admin-coredns-helper apply" in sudoers
    assert "/usr/local/libexec/oci-admin-coredns-helper rollback" in sudoers
    assert "/bin/sh" not in sudoers and "/bin/bash" not in sudoers
    assert "/usr/bin/python" not in sudoers and "SETENV" not in sudoers
    for digest in _load_helper().MANIFEST_DIGESTS.values():
        assert digest in normalized

    syntax = _bash("bash -n \"$1\" && /usr/sbin/visudo -cf \"$2\"", _wsl_path(INSTALLER_PATH), _wsl_path(SUDOERS_PATH))
    assert syntax.returncode == 0, syntax.stderr or syntax.stdout


def test_installer_fake_root_install_and_rollback_absent_preimages() -> None:
    result = _installer_harness(
        r"""
export OCI_ADMIN_COREDNS_INTERNAL_TESTING=1
export OCI_ADMIN_COREDNS_TEST_ROOT="$test_root"
source "$installer"
coredns_installer_main install "${installer_args[@]}" >"$workspace/install.json"
helper_dest="$test_root/usr/local/libexec/oci-admin-coredns-helper"
sudoers_dest="$test_root/etc/sudoers.d/101-oci-admin-coredns-run-command"
[[ -f "$helper_dest" && ! -L "$helper_dest" ]]
[[ -f "$sudoers_dest" && ! -L "$sudoers_dest" ]]
[[ $(stat -c '%a' "$helper_dest") == 755 ]]
[[ $(stat -c '%a' "$sudoers_dest") == 440 ]]
[[ "sha256:$(sha256sum "$helper_dest" | awk '{print $1}')" == "$helper_sha" ]]
[[ "sha256:$(sha256sum "$sudoers_dest" | awk '{print $1}')" == "$sudoers_sha" ]]
grep -q '^ATIUS_COREDNS_INSTALL_RECEIPT_V1 ' "$workspace/install.json"
receipt=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).read().split(" ",1)[1])["receipt_id"])' "$workspace/install.json")
coredns_installer_main rollback --receipt "$receipt" >"$workspace/rollback.json"
[[ ! -e "$helper_dest" && ! -L "$helper_dest" ]]
[[ ! -e "$sudoers_dest" && ! -L "$sudoers_dest" ]]
grep -q '"status":"rolled-back"' "$workspace/rollback.json"
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_restores_exact_present_preimages() -> None:
    result = _installer_harness(
        r"""
helper_dest="$test_root/usr/local/libexec/oci-admin-coredns-helper"
sudoers_dest="$test_root/etc/sudoers.d/101-oci-admin-coredns-run-command"
mkdir -p "$(dirname "$helper_dest")" "$(dirname "$sudoers_dest")"
printf '#!/bin/sh\nexit 7\n' >"$helper_dest"
printf 'Defaults env_reset\n' >"$sudoers_dest"
chmod 0700 "$helper_dest"
chmod 0400 "$sudoers_dest"
before_helper=$(sha256sum "$helper_dest" | awk '{print $1}')
before_sudoers=$(sha256sum "$sudoers_dest" | awk '{print $1}')
export OCI_ADMIN_COREDNS_INTERNAL_TESTING=1
export OCI_ADMIN_COREDNS_TEST_ROOT="$test_root"
source "$installer"
coredns_installer_main install "${installer_args[@]}" >"$workspace/install.json"
receipt=$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).read().split(" ",1)[1])["receipt_id"])' "$workspace/install.json")
coredns_installer_main rollback --receipt "$receipt" >/dev/null
[[ $(sha256sum "$helper_dest" | awk '{print $1}') == "$before_helper" ]]
[[ $(sha256sum "$sudoers_dest" | awk '{print $1}') == "$before_sudoers" ]]
[[ $(stat -c '%a' "$helper_dest") == 700 ]]
[[ $(stat -c '%a' "$sudoers_dest") == 400 ]]
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_failure_stages_leave_no_partial_replacement() -> None:
    result = _installer_harness(
        r"""
for stage in preimage helper-stage sudoers-stage helper-replace sudoers-replace global-visudo readback; do
  stage_root="$workspace/root-$stage"
  mkdir -p "$stage_root"
  (
    export OCI_ADMIN_COREDNS_INTERNAL_TESTING=1
    export OCI_ADMIN_COREDNS_TEST_ROOT="$stage_root"
    export OCI_ADMIN_COREDNS_TEST_FAIL_STAGE="$stage"
    source "$installer"
    set +e
    coredns_installer_main install "${installer_args[@]}" >"$workspace/$stage.json" 2>"$workspace/$stage.err"
    rc=$?
    set -e
    [[ $rc -eq 2 ]]
  )
  [[ ! -e "$stage_root/usr/local/libexec/oci-admin-coredns-helper" ]]
  [[ ! -e "$stage_root/etc/sudoers.d/101-oci-admin-coredns-run-command" ]]
  grep -q '"status":"failed-restored"' "$workspace/$stage.json"
  grep -q '^oci-admin-coredns-installer: rejected$' "$workspace/$stage.err"
done
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_installer_rejects_commit_digest_path_and_environment_override() -> None:
    result = _installer_harness(
        r"""
export OCI_ADMIN_COREDNS_INTERNAL_TESTING=1
export OCI_ADMIN_COREDNS_TEST_ROOT="$test_root"
source "$installer"
set +e
coredns_installer_main install --expected-commit "${source_commit%?}0" --expected-helper-sha256 "$helper_sha" --expected-sudoers-sha256 "$sudoers_sha" --run-command-user ocarun >/dev/null 2>&1
bad_commit=$?
coredns_installer_main install "${installer_args[@]}" --root /tmp/caller >/dev/null 2>&1
bad_path=$?
coredns_installer_main rollback --receipt '../../escape' >/dev/null 2>&1
bad_receipt=$?
set -e
[[ $bad_commit -ne 0 && $bad_path -eq 64 && $bad_receipt -eq 64 ]]
[[ -z $(find "$test_root" -mindepth 1 -print -quit) ]]
"""
    )
    assert result.returncode == 0, result.stderr or result.stdout

    public = _bash(
        'OCI_ADMIN_COREDNS_INTERNAL_TESTING=1 OCI_ADMIN_COREDNS_TEST_ROOT=/tmp/caller "$1" install --expected-commit "$2" --expected-helper-sha256 "$3" --expected-sudoers-sha256 "$4" --run-command-user ocarun',
        _wsl_path(INSTALLER_PATH),
        "0" * 40,
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    )
    assert public.returncode == 64
