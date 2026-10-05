# Full-suite disposition

- Command: governed `python3 -m pytest -q -p no:cacheprovider cli/omni/tests`.
- Result: `156 passed, 2 failed`.
- CloudBeaver focused contract: `5 passed`.
- Failure 1: assertion mismatch in `test_srv1_backup_offload.py` against the pre-existing dirty backup-script lane.
- Failure 2: assertion mismatch in the same test file against the pre-existing dirty rclone-queue lane.
- Neither failure references or executes the CloudBeaver unit, compose, inventory contract, healthcheck, docs, listener or registry update.
- The two source areas were already dirty outside t28 and were not modified during this reconciliation.
- Disposition: `unrelated-existing-suite-residual`; the current owner/intent of those dirty edits was not inferred. Not fixed in t28 to avoid absorbing another active lane.

## Targeted status
```text
 M modules/fleet-backup/scripts/rclone-fleet-queue.sh
 M modules/srv1-ops/scripts/backup-srv1-to-gdrive.sh
?? cli/omni/tests/test_srv1_backup_offload.py
```

## Failure node ids
- `BackupOffloadTests.test_daily_backup_is_bounded_vault_hydrated_and_fail_closed`
- `BackupOffloadTests.test_fleet_queue_propagates_ssh_exit_and_marks_owned_lock`
