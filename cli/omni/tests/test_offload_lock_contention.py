"""Fail-closed lock and deletion contracts for backup offload."""

from pathlib import Path
import json
import os
import shutil
import socket
import subprocess


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "srv1-ops" / "scripts" / "offload-dotbackups-to-gdrive.sh"


def _base_env(tmp_path: Path, fake_rclone: Path) -> dict[str, str]:
    home = tmp_path / "home"
    (home / ".backups").mkdir(parents=True)
    return {
        **os.environ,
        "OFFLOAD_EXPECTED_HOST": socket.gethostname().split(".")[0],
        "HOME_DIR": str(home),
        "DOT_SRC": str(home / ".backups"),
        "BACKUPS_SRC": str(home / "backups"),
        "LOG": str(tmp_path / "offload.log"),
        "STATE_DIR": str(tmp_path / "state"),
        "LOCAL_LOCK": str(tmp_path / "local.lock"),
        "FLEET_LOCK": str(tmp_path / "fleet.lock"),
        "RCLONE_BIN": str(fake_rclone),
        "LOCK_WAIT": "1",
        "DELETE_AFTER_VERIFY": "0",
        "QUARANTINE_ROOT_BASE": str(tmp_path / "quarantine"),
        "PRIVILEGE_MODE": "direct",
    }


def test_offload_uses_bounded_locks_and_retryable_state() -> None:
    source = SCRIPT.read_text()
    assert 'FLEET_LOCK="${FLEET_LOCK:-/tmp/rclone-fleet.lock}"' in source
    assert 'flock -w "$LOCK_WAIT"' in source
    assert 'write_last_run 75 "retryable" "fleet-lock-timeout"' in source
    assert 'write_last_run 75 "retryable" "local-lock-timeout"' in source
    assert 'RCLONE_FLEET_HOLD_FILE' in source
    assert "SKIP fleet-hold-active" in source
    assert 'APPROVED_REMOTE="giovanni-drive:"' in source
    assert '[ "$REMOTE" = "$APPROVED_REMOTE" ]' in source
    assert 'DRY_RUN="${DRY_RUN:-0}"' in source
    assert "open-handle scan failed" in source
    assert "raise SystemExit(2)" in source


def test_lock_contention_exits_retryable_without_starting_rclone(tmp_path: Path) -> None:
    marker = tmp_path / "rclone-called"
    fake_rclone = tmp_path / "rclone"
    fake_rclone.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n")
    fake_rclone.chmod(0o755)
    env = _base_env(tmp_path, fake_rclone)

    holder = subprocess.Popen(["flock", env["FLEET_LOCK"], "sleep", "10"])
    try:
        result = subprocess.run(
            ["bash", str(SCRIPT), "--dry-run"],
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
        )
    finally:
        holder.terminate()
        holder.wait(timeout=5)

    assert result.returncode == 75, result.stderr
    assert "fleet-lock-timeout" in result.stdout
    status = json.loads((Path(env["STATE_DIR"]) / "last-run.json").read_text())
    assert status["status"] == "retryable"
    assert status["reason"] == "fleet-lock-timeout"
    assert not marker.exists()


def test_external_hold_exits_success_before_locks_or_rclone(tmp_path: Path) -> None:
    hold = tmp_path / "queue.hold"
    hold.write_text("dedicated oauth client required\n")
    marker = tmp_path / "rclone-called"
    fake_rclone = tmp_path / "rclone"
    fake_rclone.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n")
    fake_rclone.chmod(0o755)
    env = _base_env(tmp_path, fake_rclone)
    env["RCLONE_FLEET_HOLD_FILE"] = str(hold)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"],
        env=env,
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 0
    assert "SKIP fleet-hold-active" in result.stdout
    assert not marker.exists()


def test_dry_run_with_real_item_survives_set_e_and_never_calls_rclone(tmp_path: Path) -> None:
    marker = tmp_path / "rclone-called"
    fake_rclone = tmp_path / "rclone"
    fake_rclone.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n")
    fake_rclone.chmod(0o755)
    env = _base_env(tmp_path, fake_rclone)
    item = Path(env["DOT_SRC"]) / "sample"
    item.mkdir()
    (item / "data.txt").write_text("payload\n")
    old = __import__("time").time() - 7200
    os.utime(item / "data.txt", (old, old))
    os.utime(item, (old, old))

    result = subprocess.run(
        ["bash", str(SCRIPT), "--dry-run", "--source", "dotbackups"],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "DRY root=dotbackups item=sample" in result.stdout
    assert not marker.exists()


def test_offload_source_guards_quarantine_and_manifest_readback_are_fail_closed() -> None:
    source = SCRIPT.read_text()
    assert 'approved_dot="$(realpath -m "/home/ubuntu/.backups")"' in source
    assert 'approved_backups="$(realpath -m "/home/ubuntu/backups")"' in source
    assert 'reason=unapproved-delete-root' in source
    assert "quarantine_item()" in source
    assert "restore_quarantined_item()" in source
    assert "src_dir_fd=sfd,dst_dir_fd=cfd" in source
    assert "src_dir_fd=qfd,dst_dir_fd=sfd" in source
    assert "os.O_NOFOLLOW" in source
    assert "$QUIESCENCE_REASON-after-quarantine" in source
    assert "$QUIESCENCE_REASON-before-delete" in source
    assert "has_open_handles()" in source
    assert "has_nested_mount()" in source
    assert "quiescence_gate()" in source
    assert "mount-scan-failed" in source
    assert "open-handle-scan-failed" in source
    assert "/proc/self/mountinfo" in source
    assert "proc/'map_files'" in source
    assert "QUARANTINE_ROOT_BASE" in source
    assert 'priv tar -C "$parent"' in source
    assert '(cd "$parent" && priv tar' not in source
    assert "config show" in source
    assert "approved-remote-backend" in source
    assert "if not moved:" in source
    assert "os.rmdir(child,dir_fd=bfd)" in source
    assert 'reason=quarantine-base-unsafe' in source
    assert 'quarantine_root="$(quarantine_item "$item" "$src")"' in source
    assert 'snapshot "$quarantined"' in source
    assert 'remote_meta "$mdest"' in source
    assert 'delete_item "$quarantined" "$quarantine_root"' in source
    assert source.count('priv rmdir -- "$quarantine_root"') >= 4


def test_quarantine_base_symlink_blocks_before_archive_upload(tmp_path: Path) -> None:
    fake_rclone = tmp_path / "rclone"
    rclone_log = tmp_path / "rclone.log"
    fake_rclone.write_text(
        "#!/bin/sh\n"
        'cmd="$1"; shift\n'
        'case "$cmd" in\n'
        "  listremotes) printf 'giovanni-drive:\\n'; exit 0 ;;\n"
        "  config) printf 'type = drive\\n'; exit 0 ;;\n"
        "  lsd) exit 0 ;;\n"
        '  *) printf "%s\\n" "$cmd" >> "$RCLONE_LOG"; exit 99 ;;\n'
        "esac\n"
    )
    fake_rclone.chmod(0o755)
    env = _base_env(tmp_path, fake_rclone)
    env.update(
        {
            "CONFIG_MODE": "persistent",
            "PERSISTENT_CONFIG": str(tmp_path / "rclone.conf"),
            "MIN_AGE_MINUTES": "0",
            "RCLONE_LOG": str(rclone_log),
        }
    )
    Path(env["PERSISTENT_CONFIG"]).write_text("[giovanni-drive]\ntype = local\n")
    source = Path(env["DOT_SRC"])
    item = source / "sample"
    item.mkdir()
    (item / "data.txt").write_text("payload\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    Path(env["QUARANTINE_ROOT_BASE"]).symlink_to(outside, target_is_directory=True)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--source", "dotbackups", "--keep-local"],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 1, result.stderr
    assert "reason=quarantine-base-unsafe" in result.stdout
    assert item.is_dir()
    assert not rclone_log.exists()


def test_keep_local_restore_collision_is_a_failed_run(tmp_path: Path) -> None:
    store = tmp_path / "remote"
    store.mkdir()
    fake_rclone = tmp_path / "rclone"
    fake_rclone.write_text(
        "#!/bin/sh\n"
        'cmd="$1"; shift\n'
        'case "$cmd" in\n'
        "  listremotes) printf 'giovanni-drive:\\n' ;;\n"
        "  config) printf 'type = drive\\n' ;;\n"
        "  lsd) exit 0 ;;\n"
        '  rcat) cat > "$RCLONE_STORE/archive"; mkdir -p "$DOT_SRC/sample"; printf collision > "$DOT_SRC/sample/new.txt" ;;\n'
        '  cat) case "$1" in *.manifest.json) cat "$RCLONE_STORE/manifest" ;; *) cat "$RCLONE_STORE/archive" ;; esac ;;\n'
        '  copyto) cp "$1" "$RCLONE_STORE/manifest" ;;\n'
        "  *) exit 99 ;;\n"
        "esac\n"
    )
    fake_rclone.chmod(0o755)
    env = _base_env(tmp_path, fake_rclone)
    env.update(
        {
            "CONFIG_MODE": "persistent",
            "PERSISTENT_CONFIG": str(tmp_path / "rclone.conf"),
            "MIN_AGE_MINUTES": "0",
            "ITEM_DELAY": "0",
            "RETRY_BASE_SECONDS": "0",
            "RCLONE_STORE": str(store),
        }
    )
    Path(env["PERSISTENT_CONFIG"]).write_text("[giovanni-drive]\ntype = drive\n")
    item = Path(env["DOT_SRC"]) / "sample"
    item.mkdir()
    (item / "data.txt").write_text("payload\n")

    result = subprocess.run(
        ["bash", str(SCRIPT), "--source", "dotbackups", "--keep-local"],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stderr
    assert "reason=restore-collision" in result.stdout
    state = json.loads((Path(env["STATE_DIR"]) / "last-run.json").read_text())
    assert state["status"] == "failed"
    assert (item / "new.txt").read_text() == "collision"
    quarantine = Path(env["QUARANTINE_ROOT_BASE"])
    assert list(quarantine.glob("item.*/sample/data.txt"))
    shutil.rmtree(quarantine)
