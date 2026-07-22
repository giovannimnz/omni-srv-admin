from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock


MODULE = Path(__file__).resolve().parents[1]
COPY_SCRIPT = MODULE / "scripts/rclone-copy-verified-phase52.sh"
HYDRATOR = MODULE / "scripts/atius-rclone-vault-hydrate"
FETCH_SCRIPT = MODULE / "scripts/rclone-fetch-verified-phase52.sh"
INSTALLER = MODULE / "scripts/install-fleet-backup.sh"
STATE_HELPER = MODULE / "scripts/phase52-install-state.py"
MAP = MODULE / "configs/fleet-backup-map.yaml"
PREFIX = "giovanni-drive:ATIUS-SRV/HORISTIC-SRV/Backup/RustDesk/phase52/backup-b/"


class Phase52BackupBTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="phase52-backup-b-"))
        self.tmpfs = Path(tempfile.mkdtemp(prefix="phase52-rclone-", dir="/dev/shm"))
        self.bin_dir = self.work / "bin"
        self.bin_dir.mkdir()
        self.tool_dir = self.work / "tools"
        self.tool_dir.mkdir(mode=0o700)
        self.copy_script = self.tool_dir / COPY_SCRIPT.name
        shutil.copy2(COPY_SCRIPT, self.copy_script)
        self.copy_script.chmod(0o700)
        fake_hydrator = self.tool_dir / "atius-rclone-vault-hydrate"
        fake_hydrator.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
[[ $1 == --materialize && $2 == --output-dir && -n $3 && $# == 3 ]]
out=$3
[[ ${FAKE_HYDRATOR_FAIL:-0} == 0 ]] || exit 2
[[ ${FAKE_HYDRATOR_SKIP_CONFIG:-0} == 0 ]] || exit 0
printf 'secret-sentinel-config\\n' > "$out/rclone.conf"
chmod "${FAKE_HYDRATOR_CONFIG_MODE:-600}" "$out/rclone.conf"
if [[ ${FAKE_HYDRATOR_HARDLINK:-0} == 1 ]]; then ln "$out/rclone.conf" "$out/config-hardlink"; fi
python3 - "$out" <<'PY'
import hashlib, json, os, pathlib
root = pathlib.Path(os.sys.argv[1])
config = root / 'rclone.conf'
info = config.stat()
payload = {
  'schema': 'atius-rclone-vault-provenance-v2',
  'status': 'PASS',
  'materialized_by': 'atius-rclone-vault-hydrate',
  'profile': 'rclone-giovanni-drive-phase52',
  'protocol': 'rclone-giovanni-drive-phase52-v1',
  'vault_path': 'kv/atius/fleet-backup/rclone/giovanni-drive',
  'field': 'rclone_conf',
  'config_basename': config.name,
  'config_device': info.st_dev,
  'config_inode': info.st_ino,
  'config_uid': os.getuid(),
  'config_mode': '0600',
  'config_size_bytes': info.st_size,
  'approved_remote': 'giovanni-drive',
  'secret_material_present': False,
}
field = os.environ.get('FAKE_HYDRATOR_BAD_FIELD')
if field == 'digest': payload['config_size_bytes'] += 1
if field == 'inode': payload['config_inode'] += 1
if field == 'remote': payload['approved_remote'] = 'lookalike-drive'
marker = root / '.atius-rclone-vault-provenance.json'
marker.write_text(json.dumps(payload, sort_keys=True) + '\\n')
marker.chmod(0o600)
PY
""",
            encoding="utf-8",
        )
        fake_hydrator.chmod(0o700)
        self.remote_root = self.work / "remote"
        self.remote_root.mkdir()
        self.calls = self.work / "calls"
        fake_rclone = self.bin_dir / "rclone"
        fake_rclone.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
verb=$1
shift
{
  printf '%s' "$verb"
  printf '\\t%s' "$@"
  printf '\\n'
} >> "$FAKE_RCLONE_CALLS"
case "$verb" in
  copyto)
    [[ ${FAKE_RCLONE_FAIL_COPY:-0} == 0 ]] || exit 42
    if [[ -n ${FAKE_RCLONE_SWAP_SOURCE:-} ]]; then
      printf 'swapped-source' > "$FAKE_RCLONE_SWAP_SOURCE"
      chmod 600 "$FAKE_RCLONE_SWAP_SOURCE"
    fi
    if [[ ${FAKE_RCLONE_MUTATE_USED_CONFIG:-0} == 1 ]]; then
      args=("$@")
      for ((i=0; i<${#args[@]}; i++)); do
        if [[ ${args[$i]} == --config ]]; then
          printf 'swapped-config' > "${args[$((i+1))]}"
          chmod 600 "${args[$((i+1))]}"
        fi
      done
    fi
    cp -- "$1" "$FAKE_RCLONE_ROOT/object"
    ;;
  cat)
    [[ ${FAKE_RCLONE_FAIL_CAT:-0} == 0 ]] || exit 43
    if [[ ${FAKE_RCLONE_SLEEP_CAT:-0} == 1 ]]; then sleep 3; fi
    if [[ ${FAKE_RCLONE_CORRUPT:-0} == 1 ]]; then
      printf 'corrupt'
    else
      cat "$FAKE_RCLONE_ROOT/object"
    fi
    ;;
  *) exit 91 ;;
esac
""",
            encoding="utf-8",
        )
        fake_rclone.chmod(0o755)
        self.archive = self.work / "backup-b.tar"
        self._write_archive(self.archive)

    def tearDown(self) -> None:
        shutil.rmtree(self.work)
        shutil.rmtree(self.tmpfs)

    @staticmethod
    def _write_archive(path: Path, names: tuple[str, ...] = ("db_v2.sqlite3",)) -> None:
        source = path.with_suffix(".sqlite")
        source.write_bytes(b"SQLite format 3\x00phase52-test")
        source.chmod(0o600)
        with tarfile.open(path, "w:") as archive:
            for name in names:
                info = tarfile.TarInfo(name)
                info.size = source.stat().st_size
                info.mode = 0o600
                with source.open("rb") as handle:
                    archive.addfile(info, handle)
        path.chmod(0o600)
        source.unlink()

    def _env(self, **overrides: str) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{self.bin_dir}:{env['PATH']}",
                "FAKE_RCLONE_ROOT": str(self.remote_root),
                "FAKE_RCLONE_CALLS": str(self.calls),
                "XDG_RUNTIME_DIR": str(self.tmpfs),
            }
        )
        env.update(overrides)
        return env

    def _run_copy(self, destination: str | None = None, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(self.copy_script),
                "--source",
                str(self.archive),
                "--destination",
                destination or f"{PREFIX}backup-b-test.tar",
                "--expected-size-bytes",
                str(self.archive.stat().st_size),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=self._env(**env),
        )

    def _install_fixture(self, name: str, *, previous: bool = True) -> tuple[Path, Path]:
        home = self.work / name
        home.mkdir(mode=0o700)
        if previous:
            target = home / ".local/bin/rclone-copy-verified-phase52"
            target.parent.mkdir(parents=True, mode=0o700)
            target.write_text("previous-version\n", encoding="utf-8")
            target.chmod(0o755)
        completed = subprocess.run(
            [str(INSTALLER), "--host", "horistic-srv", "--phase52-only"],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        match = re.search(r"rollback_state=(\S+)", completed.stdout)
        self.assertIsNotNone(match)
        return home, Path(match.group(1))

    @staticmethod
    def _installed_targets(home: Path) -> list[Path]:
        return [
            home / ".local/bin/rclone-copy-verified-phase52",
            home / ".local/bin/rclone-fetch-verified-phase52",
            home / ".local/bin/atius-rclone-vault-hydrate",
            home / ".config/atius/fleet-backup/fleet-backup-map.yaml",
        ]

    @staticmethod
    def _load_state_helper():
        spec = importlib.util.spec_from_file_location("phase52_install_state_test", STATE_HELPER)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_copyto_and_remote_rehash_are_required(self) -> None:
        completed = self._run_copy()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["operation"], "copy-only")
        self.assertTrue(payload["verified_copy"])
        self.assertEqual(payload["local_sha256"], payload["remote_sha256"])
        self.assertEqual(
            payload["retention"],
            {
                "retain_until": "phase57-pass-plus-30-days",
                "deletion_requires_new_explicit_approval": True,
            },
        )
        self.assertFalse(payload["secret_material_present"])
        self.assertNotIn("secret-sentinel-config", completed.stdout + completed.stderr)
        verbs = [line.split("\t", 1)[0] for line in self.calls.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(verbs, ["copyto", "cat"])

    def test_upload_failure_blocks_and_does_not_attempt_cat(self) -> None:
        completed = self._run_copy(FAKE_RCLONE_FAIL_COPY="1")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["blocker"], "rclone-copy-failed")
        verbs = [line.split("\t", 1)[0] for line in self.calls.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(verbs, ["copyto"])

    def test_hash_mismatch_blocks_without_secret_output(self) -> None:
        completed = self._run_copy(FAKE_RCLONE_CORRUPT="1")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["blocker"], "rclone-rehash-failed")
        self.assertNotIn("secret-sentinel-config", completed.stdout + completed.stderr)

    def test_cat_failure_and_timeout_block_and_cleanup_snapshots(self) -> None:
        failed = self._run_copy(FAKE_RCLONE_FAIL_CAT="1")
        self.assertEqual(failed.returncode, 2)
        self.assertEqual(json.loads(failed.stdout)["blocker"], "rclone-rehash-failed")
        self.assertEqual(list(self.tmpfs.glob("rustdesk-phase52-backup-b.*")), [])

        self.calls.unlink()
        started = time.monotonic()
        timed_out = self._run_copy(
            FAKE_RCLONE_SLEEP_CAT="1",
            PHASE52_RCLONE_TIMEOUT_SECONDS="1",
        )
        self.assertLess(time.monotonic() - started, 2.5)
        self.assertEqual(timed_out.returncode, 2)
        self.assertEqual(json.loads(timed_out.stdout)["blocker"], "rclone-rehash-failed")
        self.assertEqual(list(self.tmpfs.glob("rustdesk-phase52-backup-b.*")), [])

    def test_original_swaps_cannot_change_private_snapshots(self) -> None:
        completed = self._run_copy(FAKE_RCLONE_SWAP_SOURCE=str(self.archive))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["source_snapshot_private"])
        self.assertTrue(payload["config_provenance_verified"])
        self.assertEqual(self.archive.read_text(encoding="utf-8"), "swapped-source")
        self.assertEqual(list(self.tmpfs.glob("rustdesk-phase52-backup-b.*")), [])
        self._write_archive(self.archive)
        changed_config = self._run_copy(FAKE_RCLONE_MUTATE_USED_CONFIG="1")
        self.assertEqual(changed_config.returncode, 2)
        self.assertEqual(json.loads(changed_config.stdout)["blocker"], "rclone-config-snapshot-changed")

    def test_destination_outside_allowlist_blocks_before_rclone(self) -> None:
        completed = self._run_copy("giovanni-drive:ATIUS-SRV/SRV-1/forbidden.tar")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["blocker"], "destination-outside-allowlist")
        self.assertFalse(self.calls.exists())

    def test_nested_destination_blocks_before_rclone(self) -> None:
        completed = self._run_copy(f"{PREFIX}nested/backup.tar")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["blocker"], "destination-outside-allowlist")
        self.assertFalse(self.calls.exists())

    def test_non_state_only_archive_blocks(self) -> None:
        self._write_archive(self.archive, ("db_v2.sqlite3", "extra.env"))
        completed = self._run_copy()
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["blocker"], "source-not-state-only")
        self.assertFalse(self.calls.exists())

    def test_source_and_hydrated_config_hardlinks_are_rejected(self) -> None:
        archive_link = self.work / "archive-hardlink.tar"
        os.link(self.archive, archive_link)
        completed = self._run_copy()
        self.assertEqual(json.loads(completed.stdout)["blocker"], "source-identity-invalid")
        archive_link.unlink()

        completed = self._run_copy(FAKE_HYDRATOR_HARDLINK="1")
        self.assertEqual(json.loads(completed.stdout)["blocker"], "hydrated-rclone-config-identity-invalid")

    def test_config_provenance_binds_size_inode_and_remote(self) -> None:
        for field in ("digest", "inode", "remote"):
            completed = self._run_copy(FAKE_HYDRATOR_BAD_FIELD=field)
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(json.loads(completed.stdout)["blocker"], "rclone-provenance-invalid")
            self.assertFalse(self.calls.exists())

    def test_symlinked_source_parent_or_hydrator_is_rejected(self) -> None:
        real_source_parent = self.work / "real-source"
        real_source_parent.mkdir(mode=0o700)
        real_archive = real_source_parent / "backup.tar"
        self._write_archive(real_archive)
        source_link_parent = self.work / "source-link"
        source_link_parent.symlink_to(real_source_parent, target_is_directory=True)
        original_archive = self.archive
        self.archive = source_link_parent / "backup.tar"
        try:
            completed = self._run_copy()
        finally:
            self.archive = original_archive
        self.assertEqual(json.loads(completed.stdout)["blocker"], "source-not-canonical-regular")

        hydrator = self.tool_dir / "atius-rclone-vault-hydrate"
        real_hydrator = self.tool_dir / "real-hydrator"
        hydrator.rename(real_hydrator)
        hydrator.symlink_to(real_hydrator.name)
        try:
            completed = self._run_copy()
        finally:
            hydrator.unlink()
            real_hydrator.rename(hydrator)
        self.assertEqual(json.loads(completed.stdout)["blocker"], "canonical-hydrator-missing")

    def test_source_and_config_modes_are_enforced(self) -> None:
        self.archive.chmod(0o644)
        completed = self._run_copy()
        self.assertEqual(json.loads(completed.stdout)["blocker"], "source-identity-invalid")
        self.archive.chmod(0o600)
        completed = self._run_copy(FAKE_HYDRATOR_CONFIG_MODE="644")
        self.assertEqual(json.loads(completed.stdout)["blocker"], "hydrated-rclone-config-identity-invalid")

    def test_public_interface_rejects_arbitrary_config(self) -> None:
        arbitrary = self.work / "arbitrary.conf"
        arbitrary.write_text("untrusted\n", encoding="utf-8")
        arbitrary.chmod(0o600)
        completed = subprocess.run(
            [str(self.copy_script), "--source", str(self.archive), "--destination", f"{PREFIX}x.tar", "--config", str(arbitrary)],
            text=True,
            capture_output=True,
            check=False,
            env=self._env(),
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertFalse(self.calls.exists())

    def test_canonical_production_hydrator_remains_blocked(self) -> None:
        production_dir = self.work / "production-tools"
        production_dir.mkdir(mode=0o700)
        production_uploader = production_dir / COPY_SCRIPT.name
        production_hydrator = production_dir / HYDRATOR.name
        shutil.copy2(COPY_SCRIPT, production_uploader)
        shutil.copy2(HYDRATOR, production_hydrator)
        production_uploader.chmod(0o700)
        production_hydrator.chmod(0o700)
        completed = subprocess.run(
            [str(production_uploader), "--source", str(self.archive), "--destination", f"{PREFIX}blocked.tar", "--expected-size-bytes", str(self.archive.stat().st_size)],
            text=True,
            capture_output=True,
            check=False,
            env=self._env(),
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["blocker"], "rclone-hydration-blocked")

    def test_missing_config_blocks_before_rclone(self) -> None:
        completed = self._run_copy(FAKE_HYDRATOR_SKIP_CONFIG="1")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["blocker"], "hydrated-rclone-config-missing")
        self.assertFalse(self.calls.exists())

    def test_hydrator_fails_closed_without_approved_binding(self) -> None:
        home = self.work / "home"
        helper = home / ".local/bin/atius-vault-phase52-client"
        helper.parent.mkdir(parents=True)
        helper.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
        helper.chmod(0o700)
        completed = subprocess.run(
            [str(HYDRATOR), "--materialize", "--output-dir", str(self.tmpfs)],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "status": "BLOCKED",
                "blocker": "vault-profile-invalid",
                "config_materialized": False,
                "config_storage": "tmpfs-required",
                "secret_material_present": False,
            },
        )
        self.assertEqual(list(home.rglob("rclone.conf")), [])

    def test_phase52_installer_is_home_aware_timer_free_and_reversible(self) -> None:
        home = self.work / "install-home"
        previous = home / ".local/bin/rclone-copy-verified-phase52"
        previous.parent.mkdir(parents=True)
        previous.write_text("previous-version\n", encoding="utf-8")
        previous.chmod(0o755)

        dry_run = subprocess.run(
            [str(INSTALLER), "--host", "horistic-srv", "--phase52-only", "--dry-run"],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertIn(str(home), dry_run.stdout)
        self.assertIn("timer_action=none", dry_run.stdout)
        self.assertEqual(previous.read_text(encoding="utf-8"), "previous-version\n")

        installed = subprocess.run(
            [str(INSTALLER), "--host", "horistic-srv", "--phase52-only"],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(installed.returncode, 0, installed.stderr)
        state_match = re.search(r"rollback_state=(\S+)", installed.stdout)
        self.assertIsNotNone(state_match)
        state_dir = Path(state_match.group(1))
        self.assertTrue(state_dir.is_dir())
        self.assertEqual(previous.stat().st_mode & 0o777, 0o700)
        self.assertTrue((home / ".local/bin/atius-rclone-vault-hydrate").is_file())
        self.assertTrue((home / ".config/atius/fleet-backup/fleet-backup-map.yaml").is_file())
        self.assertFalse((home / ".config/systemd/user").exists())

        rolled_back = subprocess.run(
            [str(INSTALLER), "--rollback", str(state_dir)],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
        self.assertEqual(previous.read_text(encoding="utf-8"), "previous-version\n")
        self.assertEqual(previous.stat().st_mode & 0o777, 0o755)
        self.assertFalse((home / ".local/bin/atius-rclone-vault-hydrate").exists())
        self.assertFalse((home / ".config/atius/fleet-backup/fleet-backup-map.yaml").exists())

        consumed = subprocess.run(
            [str(INSTALLER), "--rollback", str(state_dir)],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(consumed.returncode, 2)
        self.assertEqual(json.loads(consumed.stdout)["blocker"], "manifest-header")

    def test_installer_rejects_symlinked_target_parent_in_dry_run(self) -> None:
        home = self.work / "symlink-home"
        home.mkdir(mode=0o700)
        outside = self.work / "outside-local"
        outside.mkdir(mode=0o700)
        (home / ".local").symlink_to(outside, target_is_directory=True)
        completed = subprocess.run(
            [str(INSTALLER), "--host", "horistic-srv", "--phase52-only", "--dry-run"],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("BLOCKED", completed.stdout)
        self.assertEqual(list(outside.iterdir()), [])

    def test_installer_rejects_symlinked_local_state_before_mkdir(self) -> None:
        home = self.work / "state-symlink-home"
        (home / ".local").mkdir(parents=True, mode=0o700)
        outside = self.work / "outside-state"
        outside.mkdir(mode=0o700)
        (home / ".local/state").symlink_to(outside, target_is_directory=True)
        completed = subprocess.run(
            [str(INSTALLER), "--host", "horistic-srv", "--phase52-only"],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(list(outside.iterdir()), [])

    def test_rollback_rejects_truncated_traversal_and_generation_drift_before_mutation(self) -> None:
        mutations = (
            ("truncated", lambda state, payload: state.joinpath("manifest.json").write_text("{", encoding="utf-8")),
            (
                "traversal",
                lambda state, payload: (
                    payload["targets"][0].__setitem__("backup_basename", "../previous-0"),
                    state.joinpath("manifest.json").write_text(json.dumps(payload) + "\n", encoding="utf-8"),
                ),
            ),
            (
                "generation",
                lambda state, payload: state.joinpath(".generation").write_text("0" * 32 + "\n", encoding="ascii"),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                home, state = self._install_fixture(f"manifest-{label}")
                targets = self._installed_targets(home)
                before = [target.read_bytes() for target in targets]
                payload = json.loads((state / "manifest.json").read_text(encoding="utf-8"))
                mutate(state, payload)
                completed = subprocess.run(
                    [str(INSTALLER), "--rollback", str(state)],
                    text=True,
                    capture_output=True,
                    check=False,
                    env={**os.environ, "HOME": str(home)},
                )
                self.assertEqual(completed.returncode, 2)
                self.assertEqual([target.read_bytes() for target in targets], before)

    def test_rollback_rejects_incomplete_manifest_corrupt_backup_and_stale_target(self) -> None:
        for label in ("incomplete", "backup", "stale"):
            with self.subTest(label=label):
                home, state = self._install_fixture(f"rollback-{label}")
                targets = self._installed_targets(home)
                payload = json.loads((state / "manifest.json").read_text(encoding="utf-8"))
                if label == "incomplete":
                    payload["targets"].pop()
                    (state / "manifest.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")
                elif label == "backup":
                    (state / "previous-0").write_text("corrupt\n", encoding="utf-8")
                else:
                    targets[1].write_text("stale-local-edit\n", encoding="utf-8")
                    targets[1].chmod(0o700)
                before = [target.read_bytes() for target in targets]
                completed = subprocess.run(
                    [str(INSTALLER), "--rollback", str(state)],
                    text=True,
                    capture_output=True,
                    check=False,
                    env={**os.environ, "HOME": str(home)},
                )
                self.assertEqual(completed.returncode, 2)
                self.assertEqual([target.read_bytes() for target in targets], before)

    def test_install_and_rollback_interruptions_are_atomic(self) -> None:
        helper = self._load_state_helper()
        module_dir = MODULE

        home = self.work / "interrupt-install"
        home.mkdir(mode=0o700)
        generation = "1" * 32
        state = home / f".local/state/atius-fleet-backup/phase52-{generation}"
        helper.capture(home, module_dir, state, generation)
        original_replace = os.replace
        raised = False

        def interrupt_second_install(source, destination):
            nonlocal raised
            if not raised and Path(destination).name == "atius-rclone-vault-hydrate":
                raised = True
                original_replace(source, destination)
                raise helper.TransactionInterrupted("test-install-interrupt")
            return original_replace(source, destination)

        with mock.patch.object(helper.os, "replace", side_effect=interrupt_second_install):
            with self.assertRaises(helper.TransactionInterrupted):
                helper.install(home, module_dir, state)
        self.assertTrue(raised)
        self.assertTrue(all(not target.exists() for target in self._installed_targets(home)))
        self.assertEqual(json.loads((state / "manifest.json").read_text())["status"], "captured")

        helper.install(home, module_dir, state)
        targets = self._installed_targets(home)
        before = [(target.read_bytes(), target.stat().st_ino) for target in targets]
        raised = False

        def interrupt_second_stash(source, destination):
            nonlocal raised
            if not raised and Path(destination).name == ".rollback-current-1":
                raised = True
                original_replace(source, destination)
                raise helper.TransactionInterrupted("test-rollback-interrupt")
            return original_replace(source, destination)

        with mock.patch.object(helper.os, "replace", side_effect=interrupt_second_stash):
            with self.assertRaises(helper.TransactionInterrupted):
                helper.rollback(home, state)
        self.assertTrue(raised)
        self.assertEqual([(target.read_bytes(), target.stat().st_ino) for target in targets], before)
        self.assertEqual(json.loads((state / "manifest.json").read_text())["status"], "installed")

    def test_post_manifest_replace_exceptions_compensate_from_reality(self) -> None:
        helper = self._load_state_helper()
        home = self.work / "post-manifest"
        home.mkdir(mode=0o700)
        generation = "2" * 32
        state = home / f".local/state/atius-fleet-backup/phase52-{generation}"
        helper.capture(home, MODULE, state, generation)
        original_replace = os.replace
        raised = False

        def fail_after_install_manifest(source, destination):
            nonlocal raised
            result = original_replace(source, destination)
            if not raised and Path(destination) == state / "manifest.json":
                payload = json.loads((state / "manifest.json").read_text())
                if payload["status"] == "installed":
                    raised = True
                    raise helper.TransactionInterrupted("after-install-manifest")
            return result

        with mock.patch.object(helper.os, "replace", side_effect=fail_after_install_manifest):
            with self.assertRaises(helper.TransactionInterrupted):
                helper.install(home, MODULE, state)
        self.assertTrue(raised)
        self.assertTrue(all(not target.exists() for target in self._installed_targets(home)))
        self.assertEqual(json.loads((state / "manifest.json").read_text())["status"], "captured")

        helper.install(home, MODULE, state)
        before = [(path.read_bytes(), path.stat().st_ino) for path in self._installed_targets(home)]
        raised = False

        def fail_after_consumed_manifest(source, destination):
            nonlocal raised
            result = original_replace(source, destination)
            if not raised and Path(destination) == state / "manifest.json":
                payload = json.loads((state / "manifest.json").read_text())
                if payload["status"] == "consumed":
                    raised = True
                    raise helper.TransactionInterrupted("after-consumed-manifest")
            return result

        with mock.patch.object(helper.os, "replace", side_effect=fail_after_consumed_manifest):
            with self.assertRaises(helper.TransactionInterrupted):
                helper.rollback(home, state)
        self.assertTrue(raised)
        self.assertEqual(
            [(path.read_bytes(), path.stat().st_ino) for path in self._installed_targets(home)], before
        )
        self.assertEqual(json.loads((state / "manifest.json").read_text())["status"], "installed")

    def test_legacy_installer_contract_remains_present(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        legacy = text.split("[[ -z \"$requested_host\" && \"$dry_run\" == false ]] || usage", 1)[1]
        self.assertIn('install -m 755 "$SCRIPTS_DIR/rclone-fleet-queue.sh"', legacy)
        self.assertIn("systemctl --user enable rclone-fleet-queue.timer", legacy)
        self.assertIn("systemctl --user start rclone-fleet-queue.timer", legacy)

    def test_legacy_installer_executes_with_local_fakes(self) -> None:
        home = self.work / "legacy-home"
        home.mkdir(mode=0o700)
        fake_bin = self.work / "legacy-bin"
        fake_bin.mkdir(mode=0o700)
        (fake_bin / "hostname").write_text("#!/bin/sh\nprintf 'atius-srv-1\\n'\n", encoding="utf-8")
        systemctl_log = self.work / "systemctl.log"
        (fake_bin / "systemctl").write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FAKE_SYSTEMCTL_LOG\"\n",
            encoding="utf-8",
        )
        (fake_bin / "hostname").chmod(0o700)
        (fake_bin / "systemctl").chmod(0o700)
        completed = subprocess.run(
            [str(INSTALLER)],
            text=True,
            capture_output=True,
            check=False,
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "FAKE_SYSTEMCTL_LOG": str(systemctl_log),
            },
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue((home / "scripts/rclone-fleet-queue.sh").is_file())
        self.assertTrue((home / ".config/systemd/user/rclone-fleet-queue.service").is_file())
        self.assertTrue((home / ".config/systemd/user/rclone-fleet-queue.timer").is_file())
        self.assertTrue((home / ".local/bin/rclone-fleet-queue").is_symlink())
        self.assertEqual(
            systemctl_log.read_text(encoding="utf-8").splitlines(),
            [
                "--user daemon-reload",
                "--user enable rclone-fleet-queue.timer",
                "--user start rclone-fleet-queue.timer",
            ],
        )

    def test_legacy_fleet_map_is_unchanged_and_phase52_is_separate(self) -> None:
        text = MAP.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^  - srv_num: ([123])$", text, re.MULTILINE), ["1", "2", "3"])
        self.assertIn("phase52_copy_only:", text)
        self.assertIn(f"backup_target_prefix: {PREFIX}", text)
        self.assertIn("install_timer: false", text)

    def test_uploader_contains_no_destructive_rclone_verb(self) -> None:
        text = COPY_SCRIPT.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\brclone\s+(delete|purge|move|sync|cleanup)\b", text))
        self.assertIn("rclone copyto", text)
        self.assertIn("rclone cat", text)
        self.assertIn("--transfers 1", text)
        self.assertIn("--checkers 1", text)
        self.assertIn("--bwlimit", text)
        self.assertIn('timeout "$timeout_seconds"', text)

    def test_gate_a_hydrator_uses_exact_profile_and_one_remote(self) -> None:
        home = self.work / "gate-a-home"
        helper = home / ".local/bin/atius-vault-phase52-client"
        helper.parent.mkdir(parents=True, mode=0o700)
        helper.write_text(
            "#!/usr/bin/env python3\n"
            "import json,sys\n"
            "request=json.load(sys.stdin)\n"
            "assert request == {'references':[{'vault_path':'kv/atius/fleet-backup/rclone/giovanni-drive','field':'rclone_conf'}]}\n"
            "value='[giovanni-drive]\\ntype = drive\\ntoken = fixture-token\\n'\n"
            "print(json.dumps({'request_count':1,'values':{'kv/atius/fleet-backup/rclone/giovanni-drive#rclone_conf':value}}))\n",
            encoding="utf-8",
        )
        helper.chmod(0o700)
        completed = subprocess.run(
            [str(HYDRATOR), "--materialize", "--output-dir", str(self.tmpfs)],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["profile"], "rclone-giovanni-drive-phase52")
        self.assertEqual(payload["approved_remote"], "giovanni-drive")
        self.assertFalse(payload["secret_material_present"])
        self.assertNotIn("fixture-token", completed.stdout + completed.stderr)
        self.assertEqual(
            (self.tmpfs / "rclone.conf").read_text(encoding="utf-8").splitlines()[0],
            "[giovanni-drive]",
        )

    def test_gate_a_fetcher_is_bounded_atomic_and_delete_free(self) -> None:
        self.assertTrue(FETCH_SCRIPT.is_file())
        text = FETCH_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("--expected-sha256", text)
        self.assertIn("rclone cat", text)
        self.assertIn("DESTINATION_PREFIX", text)
        self.assertNotRegex(text, r"rclone\s+(delete|purge|move|sync|cleanup)\b")

    def test_gate_a_corrective_provenance_contains_no_config_or_secret_digest(self) -> None:
        hydrate = HYDRATOR.read_text(encoding="utf-8")
        copy = COPY_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("config_sha256", hydrate)
        self.assertNotIn("config_sha256", copy)
        self.assertIn("vault_path", hydrate)
        self.assertIn("rclone-giovanni-drive-phase52", hydrate)

    def test_gate_a_corrective_copy_and_fetch_enforce_expected_size_and_four_gib_limit(self) -> None:
        for path in (COPY_SCRIPT, FETCH_SCRIPT):
            text = path.read_text(encoding="utf-8")
            self.assertIn("4294967296", text)
            self.assertIn("--expected-size-bytes", text)
        fetch = FETCH_SCRIPT.read_text(encoding="utf-8")
        self.assertTrue("mktemp" in fetch or "O_EXCL" in fetch)
        self.assertIn("stream-size-exceeded", fetch)

    def test_gate_a_fetcher_streams_to_exclusive_stage_and_verifies_size_hash(self) -> None:
        fetcher = self.tool_dir / FETCH_SCRIPT.name
        shutil.copy2(FETCH_SCRIPT, fetcher)
        fetcher.chmod(0o700)
        shutil.copy2(self.archive, self.remote_root / "object")
        output_dir = self.work / "restore-output"
        output_dir.mkdir(mode=0o700)
        output = output_dir / "backup-b.tar"
        digest = __import__("hashlib").sha256(self.archive.read_bytes()).hexdigest()
        env = self._env()
        completed = subprocess.run(
            [str(fetcher), "--source", f"{PREFIX}backup-b-test.tar", "--expected-sha256", digest,
             "--expected-size-bytes", str(self.archive.stat().st_size), "--output", str(output)],
            text=True, capture_output=True, check=False, env=env,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(output.read_bytes(), self.archive.read_bytes())
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(completed.stdout)["status"], "PASS")

        oversized_output = output_dir / "oversized.tar"
        oversized = subprocess.run(
            [str(fetcher), "--source", f"{PREFIX}backup-b-test.tar", "--expected-sha256", digest,
             "--expected-size-bytes", str(self.archive.stat().st_size - 1), "--output", str(oversized_output)],
            text=True, capture_output=True, check=False, env=env,
        )
        self.assertEqual(oversized.returncode, 2)
        self.assertEqual(json.loads(oversized.stdout)["blocker"], "stream-size-exceeded")
        self.assertFalse(oversized_output.exists())
        self.assertEqual(list(output_dir.glob(".phase52-fetch.*")), [])

    def test_gate_a_third_cycle_rclone_parsers_suppress_all_parse_exceptions_and_streams(self) -> None:
        hydrate = HYDRATOR.read_text(encoding="utf-8")
        copy = COPY_SCRIPT.read_text(encoding="utf-8")
        fetch = FETCH_SCRIPT.read_text(encoding="utf-8")
        for text in (hydrate, copy, fetch):
            self.assertIn("rclone_parse_blocked", text)
            self.assertIn("stderr_suppressed", text)
        self.assertIn("configparser.Error", hydrate)
        self.assertIn("tarfile.TarError", copy)

    def test_gate_a_third_cycle_fetch_stage_has_no_pathname_reopen_race(self) -> None:
        text = FETCH_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("tempfile.mkstemp", text)
        self.assertIn("os.link", text)
        self.assertIn("follow_symlinks=False", text)
        self.assertNotIn("os.open(path,os.O_WRONLY|os.O_TRUNC)", text)
        self.assertNotIn("mv -n", text)


if __name__ == "__main__":
    unittest.main()
