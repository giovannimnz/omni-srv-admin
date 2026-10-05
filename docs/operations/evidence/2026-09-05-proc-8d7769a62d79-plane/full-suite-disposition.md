# Full-suite disposition

- Command: governed `python3 -m pytest -q -p no:cacheprovider cli/omni/tests`.
- Result: `165 passed, 2 failed`.
- Plane focused contract: `4 passed`.
- CloudBeaver + Jenkins + Plane contracts: `14 passed`.
- Failure 1: assertion mismatch in `test_srv1_backup_offload.py` against the pre-existing dirty backup-script lane.
- Failure 2: assertion mismatch in the same test file against the pre-existing dirty rclone-queue lane.
- Neither failure references or executes Plane source, unit, compose, readiness wrapper, monitor, inventory, registry, volumes, network-boundary probes or documentation.
- Disposition: `unrelated-existing-suite-residual`; not fixed to avoid absorbing another active lane.

## Failed nodes

- `BackupOffloadTests.test_daily_backup_is_bounded_vault_hydrated_and_fail_closed`
- `BackupOffloadTests.test_fleet_queue_propagates_ssh_exit_and_marks_owned_lock`
