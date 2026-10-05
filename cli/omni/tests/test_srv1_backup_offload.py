from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules/srv1-ops/scripts/offload-dotbackups-to-gdrive.sh"
DAILY_SCRIPT = REPO / "modules/srv1-ops/scripts/backup-srv1-to-gdrive.sh"
QUEUE_SCRIPT = REPO / "modules/fleet-backup/scripts/rclone-fleet-queue.sh"


class BackupOffloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.dot = self.home / ".backups"
        self.backups = self.home / "backups"
        self.remote = self.root / "remote"
        self.bin = self.root / "fake-rclone"
        self.dot.mkdir(parents=True)
        self.backups.mkdir()
        self.remote.mkdir()
        (self.home / ".config/rclone").mkdir(parents=True)
        (self.home / ".config/rclone/rclone.conf").write_text("[giovanni-drive]\ntype = drive\n")
        self.bin.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json, os, pathlib, shutil, sys
                cmd, raw = sys.argv[1], sys.argv[2:]
                args = [value for value in raw if not value.startswith('--')]
                base = pathlib.Path(os.environ['FAKE_REMOTE_ROOT'])
                def target(remote):
                    path = remote.split(':', 1)[-1].lstrip('/')
                    return base / path
                if cmd == 'listremotes':
                    print('giovanni-drive:')
                elif cmd == 'lsd':
                    print('0 2026-01-01 00:00:00 -1 Backup')
                elif cmd == 'rcat':
                    if os.environ.get('FAKE_FAIL_FIRST_RCAT') == '1':
                        marker = base / '.failed-first-rcat'
                        if not marker.exists():
                            marker.write_text('failed')
                            sys.stdin.buffer.read()
                            raise SystemExit(1)
                    out = target(args[0]); out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(sys.stdin.buffer.read())
                elif cmd == 'copyto':
                    out = target(args[1]); out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(args[0], out)
                elif cmd == 'cat':
                    data = target(args[0]).read_bytes()
                    if os.environ.get('FAKE_HASH_MISMATCH') == '1' and not args[0].endswith('.manifest.json'):
                        data += b'mismatch'
                    sys.stdout.buffer.write(data)
                else:
                    raise SystemExit(f'unsupported fake rclone command: {cmd}')
                """
            )
        )
        self.bin.chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_script(self, *, mismatch: bool = False, fail_first_rcat: bool = False) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "HOME_DIR": str(self.home),
                "DOT_SRC": str(self.dot),
                "BACKUPS_SRC": str(self.backups),
                "LOG": str(self.root / "offload.log"),
                "STATE_DIR": str(self.root / "state"),
                "LOCAL_LOCK": str(self.root / "local.lock"),
                "FLEET_LOCK": str(self.root / "fleet.lock"),
                "CONFIG_MODE": "persistent",
                "PERSISTENT_CONFIG": str(self.home / ".config/rclone/rclone.conf"),
                "PRIVILEGE_MODE": "direct",
                "RCLONE_BIN": str(self.bin),
                "FAKE_REMOTE_ROOT": str(self.remote),
                "MIN_AGE_MINUTES": "0",
                "PARTIAL_MIN_AGE_MINUTES": "0",
                "ITEM_DELAY": "0",
                "BWLIMIT_KBPS": "1000000",
                "RETRY_BASE_SECONDS": "0",
            }
        )
        if mismatch:
            env["FAKE_HASH_MISMATCH"] = "1"
        if fail_first_rcat:
            env["FAKE_FAIL_FIRST_RCAT"] = "1"
        return subprocess.run([str(SCRIPT)], env=env, text=True, capture_output=True, timeout=30)

    def test_both_roots_upload_verify_manifest_then_delete(self) -> None:
        (self.dot / "root-owned-shape").mkdir()
        (self.dot / "root-owned-shape/config.txt").write_text("config")
        (self.backups / "snapshot.dump.partial").write_bytes(b"partial-but-aged")

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.dot.iterdir()), [])
        self.assertEqual(list(self.backups.iterdir()), [])
        archives = list(self.remote.rglob("*.tar.gz"))
        manifests = list(self.remote.rglob("*.manifest.json"))
        self.assertEqual(len(archives), 2)
        self.assertEqual(len(manifests), 2)
        self.assertTrue(any("_quarantine" in str(path) for path in archives))
        state = json.loads((self.root / "state/last-run.json").read_text())
        self.assertEqual(state, {"deleted": 2, "exit": 0, "kept": 0, "processed": 2, "skipped": 0, "verified": 2})

    def test_remote_hash_mismatch_keeps_local_item(self) -> None:
        item = self.dot / "must-survive"
        item.mkdir()
        (item / "data.bin").write_bytes(b"important")

        result = self.run_script(mismatch=True)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(item.exists())
        self.assertIn("reason=remote-hash-mismatch", result.stdout)
        self.assertEqual(list(self.remote.rglob("*.manifest.json")), [])

    def test_invalid_source_selector_fails_before_mutation(self) -> None:
        result = subprocess.run([str(SCRIPT), "--source", "elsewhere"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)

    def test_stale_hash_temp_does_not_break_next_item(self) -> None:
        first = self.dot / "first"
        second = self.dot / "second"
        first.write_bytes(b"one")
        second.write_bytes(b"two")
        result = self.run_script(fail_first_rcat=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())

    def test_daily_backup_is_bounded_vault_hydrated_and_fail_closed(self) -> None:
        source = DAILY_SCRIPT.read_text()
        self.assertIn("RCLONE_CONFIG_MODE=\"${RCLONE_CONFIG_MODE:-vault}\"", source)
        self.assertIn("FLEET_LOCK=\"${FLEET_LOCK:-/tmp/rclone-fleet.lock}\"", source)
        self.assertIn("timeout --signal=TERM", source)
        self.assertIn('if [ "$EXIT_CODE" -eq 0 ]; then', source)
        self.assertIn("else\n            local rc=$?", source)

    def test_fleet_queue_propagates_ssh_exit_and_marks_owned_lock(self) -> None:
        source = QUEUE_SCRIPT.read_text()
        self.assertIn("RCLONE_FLEET_LOCK_HELD=1", source)
        self.assertIn('if [ "$rc" -ne 0 ]', source)
        self.assertIn('if [ "$check_rc" -ne 0 ]', source)


if __name__ == "__main__":
    unittest.main()
