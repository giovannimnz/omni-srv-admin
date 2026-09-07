"""Resumable and serialized SRV-1 GDrive backup contracts."""

from pathlib import Path
import json
import os
import stat
import subprocess
import sys


REPO = Path(__file__).resolve().parents[3]
STATE = REPO / "modules/srv1-ops/scripts/backup-gdrive-state.py"
BACKUP = REPO / "modules/srv1-ops/scripts/backup-srv1-to-gdrive.sh"
DAILY_SERVICE = REPO / "modules/srv1-ops/systemd/backup-srv1-daily.service"
QUEUE = REPO / "modules/fleet-backup/scripts/rclone-fleet-queue.sh"
QUEUE_SERVICE = REPO / "modules/fleet-backup/systemd/rclone-fleet-queue.service"
INSTALLER = REPO / "modules/fleet-backup/scripts/install-fleet-backup.sh"


def run_state(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STATE), "--state", str(tmp_path / "state.json"), *args],
        text=True,
        capture_output=True,
    )


def test_state_is_atomic_resumable_and_mode_0600(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    assert run_state(tmp_path, "init", "--snapshot-id", "2026-09-05_042520", "--destination", "remote:snapshot").returncode == 0
    assert stat.S_IMODE(state.stat().st_mode) == 0o600
    assert run_state(tmp_path, "is-complete", "--label", "github").returncode == 1
    assert run_state(tmp_path, "begin", "--label", "github").returncode == 0
    assert run_state(tmp_path, "retry", "--label", "github", "--error-class", "rate-limit", "--exit-code", "75").returncode == 0
    first = json.loads(state.read_text())
    assert first["snapshot_id"] == "2026-09-05_042520"
    assert first["status"] == "retryable"
    assert first["attempts"]["github"] == 1
    assert run_state(tmp_path, "begin", "--label", "github").returncode == 0
    assert run_state(tmp_path, "copy-complete", "--label", "github").returncode == 0
    assert run_state(tmp_path, "is-copied", "--label", "github").returncode == 0
    assert run_state(tmp_path, "is-complete", "--label", "github").returncode == 1
    assert run_state(tmp_path, "complete", "--label", "github").returncode == 0
    assert run_state(tmp_path, "is-complete", "--label", "github").returncode == 0
    assert run_state(tmp_path, "finalize").returncode == 0
    final = json.loads(state.read_text())
    assert final["status"] == "complete"
    assert final["completed_at"]
    assert not list(tmp_path.glob(".state.json.*"))


def test_state_can_quarantine_a_pre_remediation_partial(tmp_path: Path) -> None:
    assert run_state(tmp_path, "init", "--snapshot-id", "2026-09-05_042520", "--destination", "remote:snapshot").returncode == 0
    assert run_state(tmp_path, "quarantine", "--label", "github", "--error-class", "pre-remediation-partial", "--exit-code", "75").returncode == 0
    data = json.loads((tmp_path / "state.json").read_text())
    assert data["status"] == "quarantined"
    assert data["last_error_class"] == "pre-remediation-partial"
    assert run_state(tmp_path, "is-complete", "--label", "github").returncode == 1
    status = run_state(tmp_path, "status")
    assert status.returncode == 0
    assert status.stdout.strip() == "quarantined"


def test_config_validation_requires_dedicated_oauth_client(tmp_path: Path) -> None:
    config = tmp_path / "rclone.conf"
    config.write_text("[giovanni-drive]\ntype = drive\nscope = drive\ntoken = token-value\n")
    missing = run_state(
        tmp_path,
        "validate-config",
        "--config",
        str(config),
        "--remote",
        "giovanni-drive",
    )
    assert missing.returncode == 1
    assert json.loads(missing.stdout)["dedicated_oauth_client"] is False

    config.write_text(
        "[giovanni-drive]\n"
        "type = drive\n"
        "scope = drive\n"
        "client_id = client-id-value\n"
        "client_secret = client-secret-value\n"
        "token = token-value\n"
    )
    ready = run_state(
        tmp_path,
        "validate-config",
        "--config",
        str(config),
        "--remote",
        "giovanni-drive",
    )
    assert ready.returncode == 0
    assert json.loads(ready.stdout) == {
        "dedicated_oauth_client": True,
        "remote": "giovanni-drive",
    }


def test_backup_uses_stable_snapshot_state_and_one_attempt_per_run() -> None:
    source = BACKUP.read_text()
    assert "set -euo pipefail" in source
    assert 'BACKUP_SNAPSHOT_ID:-$(date +%Y-%m-%d_%H%M%S)' in source
    assert 'backup-gdrive-state.py' in source
    assert 'RCLONE_ATTEMPTS_PER_RUN:-1' in source
    assert 'return 75' in source
    assert 'source file is being updated' in source
    assert '--exclude="**/.planning/graphs/**"' in source
    assert '--exclude="**/graphify-out/**"' in source
    assert '--exclude="**/.obsidian/workspace*.json"' in source
    assert '--exclude="**/data/postgres_data/**"' in source
    assert '--exclude="/Atius-Capital/ats/config/.env"' in source
    assert '--exclude="/Atius-Capital/horistic/config/.env"' in source
    assert "--retries=1" in source
    assert "--low-level-retries=2" in source
    assert 'RCLONE_TPSLIMIT="${RCLONE_TPSLIMIT:-4}"' in source
    assert 'RCLONE_PACER_MIN_SLEEP="${RCLONE_PACER_MIN_SLEEP:-1s}"' in source
    assert '--tpslimit="$RCLONE_TPSLIMIT"' in source
    assert '--drive-pacer-min-sleep="$RCLONE_PACER_MIN_SLEEP"' in source
    assert "pre-backup-cleanup" in source
    assert 'EXPECTED_HOST="${BACKUP_EXPECTED_HOST:-atius-srv-1}"' in source
    assert 'SCRIPT_PATH=$(readlink -f "${BASH_SOURCE[0]}")' in source
    assert "rclone check" in source
    assert "rclone sync" in source
    assert "--checksum" in source
    assert source.count("--links") >= 2
    assert "--one-way" not in source
    assert "--size-only" not in source
    assert "state copy-complete" in source
    assert "state invalidate-copy" in source
    assert "RESUME copy-complete" in source
    assert '--exclude="state.db*"' in source
    assert '--exclude="sessions/**"' in source
    assert 'EXCLUDE_LOGS=(' in source
    assert '--exclude="**/*.log"' in source
    assert "ROTATE protect-unverified" in source
    assert 'data.get("status") == "complete"' in source
    assert 'completed_rotation_file' in source
    assert 'BACKUP_ALREADY_COMPLETE' in source
    assert 'FAIL quarantined snapshot=' in source
    assert "dedicated OAuth client required" in source
    assert "dedicated-oauth-client-missing" in source
    before_state = source.split("set -uo pipefail", 1)[0]
    assert "/home/ubuntu/.local/bin/cleanup-local.sh" not in before_state
    cleanup_run = '"$PRE_BACKUP_CLEANUP" >> "$HOME/.logs/pre-backup-cleanup.log" 2>&1 || true'
    assert cleanup_run not in source
    assert "pre-backup-cleanup-failed" in source


def test_daily_service_enqueues_instead_of_running_rclone_backup_directly() -> None:
    source = DAILY_SERVICE.read_text()
    assert "rclone-fleet-queue.sh enqueue 1" in source
    assert "backup-srv1-to-gdrive.sh" not in source
    assert "TimeoutStartSec=5min" in source
    assert "ConditionHost=atius-srv-1*" in source


def test_queue_preserves_snapshot_id_and_retry_state() -> None:
    source = QUEUE.read_text()
    assert 'BACKUP_SNAPSHOT_ID=\\"$snap\\"' in source
    assert "RCLONE_FLEET_LOCK_HELD=1 BACKUP_SNAPSHOT_ID=" in source
    assert "retry_snap=" not in source
    assert '"retry_count"' in source
    assert 'MAX_JOB_RUNTIME="${RCLONE_FLEET_MAX_JOB_RUNTIME:-6900}"' in source
    assert "SKIP non-orchestrator" in source
    assert "return 75" in source
    assert '[ "$rc" -eq 124 ]' in source
    assert '[ "$rc" -eq 137 ]' in source
    assert '[ "$rc" -eq 143 ]' in source
    assert "bash -o pipefail -c" in source
    assert ".abandoned" in source
    assert 'requested_snap:-$(date +%Y-%m-%d_%H%M%S)' in source
    assert 'RCLONE_FLEET_HOLD_FILE' in source
    assert "SKIP hold-active" in source
    assert "ConditionHost=atius-srv-1*" in QUEUE_SERVICE.read_text()


def test_queue_service_has_outer_deadline_above_job_budget() -> None:
    source = QUEUE_SERVICE.read_text()
    assert "TimeoutStartSec=2h" in source
    assert "KillMode=control-group" in source


def test_daily_timer_does_not_start_service_as_dependency() -> None:
    source = (REPO / "modules/srv1-ops/systemd/backup-srv1-daily.timer").read_text()
    assert "Requires=backup-srv1-daily.service" not in source
    assert "Unit=backup-srv1-daily.service" in source


def test_queue_retryable_keeps_same_job_and_snapshot(tmp_path: Path) -> None:
    queue = tmp_path / "queue"
    fake = tmp_path / "backup.sh"
    marker = tmp_path / "marker"
    fake.write_text(
        "#!/bin/bash\n"
        "printf '%s' \"$BACKUP_SNAPSHOT_ID\" > \"$MARKER\"\n"
        "exit 75\n"
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "RCLONE_FLEET_QUEUE_DIR": str(queue),
        "RCLONE_FLEET_LOG": str(tmp_path / "fleet.log"),
        "RCLONE_FLEET_STATUS_FILE": str(tmp_path / "status.json"),
        "RCLONE_FLEET_LOCK": str(tmp_path / "fleet.lock"),
        "RCLONE_FLEET_LOCAL_BACKUP_SCRIPT": str(fake),
        "RCLONE_FLEET_MAX_JOB_RUNTIME": "30",
        "RCLONE_FLEET_HOLD_FILE": str(tmp_path / "absent-hold"),
        "MARKER": str(marker),
    }
    snapshot = "2026-09-05_042520"
    assert subprocess.run(["bash", str(QUEUE), "enqueue", "1", snapshot], env=env).returncode == 0
    assert subprocess.run(["bash", str(QUEUE), "run"], env=env).returncode == 0

    job = queue / f"srv1-{snapshot}.job"
    data = json.loads(job.read_text())
    assert data["snapshot"] == snapshot
    assert data["status"] == "retryable"
    assert data["retry_count"] == 1
    assert marker.read_text() == snapshot
    assert not list(queue.glob("*retry*.job"))


def test_queue_hold_is_successful_noop_and_preserves_job(tmp_path: Path) -> None:
    queue = tmp_path / "queue"
    hold = tmp_path / "queue.hold"
    marker = tmp_path / "called"
    fake = tmp_path / "backup.sh"
    fake.write_text(f"#!/bin/bash\ntouch {marker}\n")
    fake.chmod(0o755)
    env = {
        **os.environ,
        "RCLONE_FLEET_QUEUE_DIR": str(queue),
        "RCLONE_FLEET_LOG": str(tmp_path / "fleet.log"),
        "RCLONE_FLEET_STATUS_FILE": str(tmp_path / "status.json"),
        "RCLONE_FLEET_LOCK": str(tmp_path / "fleet.lock"),
        "RCLONE_FLEET_LOCAL_BACKUP_SCRIPT": str(fake),
        "RCLONE_FLEET_HOLD_FILE": str(hold),
    }
    hold.write_text("dedicated oauth client required\n")
    assert subprocess.run(
        ["bash", str(QUEUE), "enqueue", "1", "held-snapshot"], env=env
    ).returncode == 0
    assert subprocess.run(["bash", str(QUEUE), "run"], env=env).returncode == 0
    assert (queue / "srv1-held-snapshot.job").exists()
    assert not marker.exists()
    assert "SKIP hold-active" in (tmp_path / "fleet.log").read_text()


def test_installer_enables_queue_only_on_srv1() -> None:
    source = INSTALLER.read_text()
    assert 'if [ "$SRV_NUM" = "1" ]; then' in source
    assert "disable --now rclone-fleet-queue.timer" in source


def test_retired_offload_is_srv1_only_serialized_and_bounded() -> None:
    script = (REPO / "modules/srv1-ops/scripts/offload-retired-artifacts-to-gdrive.sh").read_text()
    service = (REPO / "modules/srv1-ops/systemd/offload-retired-artifacts-to-gdrive.service").read_text()
    timer = (REPO / "modules/srv1-ops/systemd/offload-retired-artifacts-to-gdrive.timer").read_text()
    assert 'RETIRED_OFFLOAD_EXPECTED_HOST:-atius-srv-1' in script
    assert 'FLEET_LOCK="${FLEET_LOCK:-/tmp/rclone-fleet.lock}"' in script
    assert "SKIP fleet-lock-held" in script
    assert 'RCLONE_FLEET_HOLD_FILE' in script
    assert "SKIP fleet-hold-active" in script
    assert "ConditionHost=atius-srv-1*" in service
    assert "Slice=omni-transfers.slice" in service
    assert "TimeoutStartSec=2h" in service
    assert "Requires=" not in timer
    assert "Unit=offload-retired-artifacts-to-gdrive.service" in timer


def test_dotbackups_offload_preserves_live_resource_hardening() -> None:
    service = (REPO / "modules/srv1-ops/systemd/offload-dotbackups-to-gdrive.service").read_text()
    assert "ConditionHost=atius-srv-1*" in service
    assert "Slice=omni-transfers.slice" in service
    assert "CPUQuota=80%" in service
    assert "TimeoutStartSec=12h" in service
    assert "TimeoutStopSec=5min" in service
    assert "KillMode=control-group" in service
