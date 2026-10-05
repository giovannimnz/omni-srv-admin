# Full-suite disposition

- Command: governed `python3 -m pytest -q -p no:cacheprovider cli/omni/tests`.
- Result final: `161 passed, 2 failed`.
- Jenkins focused contract: `5 passed`.
- Combined CloudBeaver + Jenkins container contracts: `10 passed`.
- Failure 1: assertion mismatch in `test_srv1_backup_offload.py` against the pre-existing dirty backup-script lane.
- Failure 2: assertion mismatch in the same test file against the pre-existing dirty rclone-queue lane.
- Neither failure references or executes the Jenkins unit, compose, inventory contract, healthcheck, docs, ports, mounts, registry update or network-boundary probes.
- The three failed-lane paths were already dirty and are disjoint from t29.
- Disposition: `unrelated-existing-suite-residual`; not fixed to avoid absorbing another active lane.

## Failed nodes

- `BackupOffloadTests.test_daily_backup_is_bounded_vault_hydrated_and_fail_closed`
- `BackupOffloadTests.test_fleet_queue_propagates_ssh_exit_and_marks_owned_lock`

## Dirty paths outside t29

```text
M modules/fleet-backup/scripts/rclone-fleet-queue.sh
M modules/srv1-ops/scripts/backup-srv1-to-gdrive.sh
?? cli/omni/tests/test_srv1_backup_offload.py
```
