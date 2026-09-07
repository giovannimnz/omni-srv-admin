"""Regression contracts for the serialized rclone fleet queue."""

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "fleet-backup" / "scripts" / "rclone-fleet-queue.sh"


def test_global_lock_contention_is_a_successful_noop() -> None:
    source = SCRIPT.read_text()
    block = source.split('if ! flock -n 9; then', 1)[1].split('fi', 1)[0]
    assert 'SKIP outro worker' in block
    assert 'return 0' in block
    assert 'return 1' not in block


def test_queue_passes_fleet_lock_ownership_to_backup_child() -> None:
    source = SCRIPT.read_text()
    assert 'RCLONE_FLEET_LOCK_HELD=1 BACKUP_SNAPSHOT_ID=' in source
    assert 'bash \\\"\\$SCRIPT\\\"' in source
    assert 'find "$QUEUE_DIR" -maxdepth 1' in source
