"""Tests for cli/omni/oci.py — dry-run, state machine, and parser safety.

These tests do not require the OCI CLI or any network access. They
cover the offline path that is the current state of every host in
the inventory, plus the safety guard added in Phase 15 (substring
match in `notes.vault_project` previously corrupted inventory yamls).
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

# Make `omni` importable without installing the egg.
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "cli"))

from omni import oci as oci_mod  # noqa: E402


@pytest.fixture()
def tmp_inventory(tmp_path, monkeypatch):
    """Point oci_mod at a temp inventory dir + temp state/log dirs."""
    inv = tmp_path / "inventory" / "hosts"
    inv.mkdir(parents=True)
    state = tmp_path / "state"
    log = tmp_path / "logs"
    monkeypatch.setattr(oci_mod, "HOSTS_DIR", inv)
    monkeypatch.setattr(oci_mod, "OCI_STATE_DIR", state)
    monkeypatch.setattr(oci_mod, "OCI_LOG_DIR", log)
    monkeypatch.setattr(oci_mod, "OCI_DRILL_LOG_DIR", log / "restore-drills")
    monkeypatch.setattr(oci_mod, "OCI_LAST_SNAPSHOT_FILE", state / "oci-last-snapshot.json")
    return inv


HOST_YAML = """\
id: srv-test-1
access:
  ssh: ubuntu@10.1.1.1
platform:
  provider: oracle-oci
  os: ubuntu-24.04
  arch: arm64
notes:
  vault_project: 20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin
"""


def _write_host(inv: Path, host_id: str = "srv-test-1", body: str = HOST_YAML) -> Path:
    p = inv / f"{host_id}.yaml"
    p.write_text(body)
    return p


def test_load_oci_host_basic(tmp_inventory):
    p = _write_host(tmp_inventory)
    path, data = oci_mod._load_oci_host("srv-test-1")
    assert path == p
    assert data["id"] == "srv-test-1"
    assert data["platform"]["provider"] == "oracle-oci"


def test_load_oci_host_rejects_non_oci(tmp_inventory):
    body = HOST_YAML.replace("oracle-oci", "aws-ec2")
    _write_host(tmp_inventory, body=body)
    with pytest.raises(Exception) as ei:
        oci_mod._load_oci_host("srv-test-1")
    assert "não é OCI" in str(ei.value)


def test_load_oci_host_missing_field(tmp_inventory):
    body = HOST_YAML.replace("access:\n  ssh: ubuntu@10.1.1.1\n", "")
    _write_host(tmp_inventory, body=body)
    with pytest.raises(Exception) as ei:
        oci_mod._load_oci_host("srv-test-1")
    assert "falta campo" in str(ei.value)


def test_update_inventory_oci_block_appends(tmp_inventory):
    _write_host(tmp_inventory)
    res = oci_mod._update_inventory_oci_block(
        host_id="srv-test-1",
        snapshot_id="pending-abc",
        snapshot_at="2026-06-18T00:00:00Z",
        routine_schedule="weekly Sun 04:00 BRT",
        dry_run=False,
    )
    assert res["status"] == "updated"
    p = tmp_inventory / "srv-test-1.yaml"
    text = p.read_text()
    assert "oci:" in text
    assert "pending-abc" in text
    # ensure the notes.vault_project line was not corrupted
    assert "20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin" in text
    assert "omni-srv-adminoci:" not in text


def test_update_inventory_oci_block_replaces_in_place(tmp_inventory):
    _write_host(tmp_inventory)
    oci_mod._update_inventory_oci_block(
        host_id="srv-test-1",
        snapshot_id="pending-first",
        snapshot_at="2026-06-18T00:00:00Z",
        routine_schedule="weekly Sun 04:00 BRT",
        dry_run=False,
    )
    oci_mod._update_inventory_oci_block(
        host_id="srv-test-1",
        snapshot_id="pending-second",
        snapshot_at="2026-06-18T00:05:00Z",
        routine_schedule=None,
        dry_run=False,
    )
    text = (tmp_inventory / "srv-test-1.yaml").read_text()
    assert "pending-second" in text
    assert "pending-first" not in text
    # still one `oci:` block (no duplication)
    assert len(re.findall(r"^oci:\s*$", text, re.MULTILINE)) == 1
    # and notes still intact
    assert "20-PROJETOS/21-PROJETOS-ATIVOS/omni-srv-admin" in text
    assert "omni-srv-adminoci:" not in text


def test_status_table_lists_oci_hosts(tmp_inventory, capsys):
    _write_host(tmp_inventory, "srv-test-1")
    _write_host(tmp_inventory, "srv-test-2", HOST_YAML.replace("srv-test-1", "srv-test-2"))
    oci_mod.oci_status.callback(host_id=None, json_output=False)
    out = capsys.readouterr().out
    assert "srv-test-1" in out
    assert "srv-test-2" in out


def test_status_json_shape(tmp_inventory, capsys):
    _write_host(tmp_inventory)
    oci_mod.oci_status.callback(host_id=None, json_output=True)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "hosts" in data
    assert "oci_cli" in data
    assert data["hosts"][0]["host"] == "srv-test-1"


def test_routine_offline_dry_run(tmp_inventory, capsys):
    _write_host(tmp_inventory)
    oci_mod.snapshot_routine.callback(
        host_id="srv-test-1",
        instance_ocid=None,
        compartment_ocid=None,
        display_name=None,
        schedule="weekly Sun 04:00 BRT",
        json_output=False,
    )
    out = capsys.readouterr().out
    assert "status       : dry-run" in out
    # inventory must be updated with the pending id
    text = (tmp_inventory / "srv-test-1.yaml").read_text()
    assert "last_snapshot_id" in text
    assert "pending-" in text
    # log file should exist
    log = oci_mod.OCI_ROUTINE_LOG
    assert log.exists()
    last_line = log.read_text().strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert payload["mode"] == "routine"
    assert payload["status"] == "dry-run"


def test_preflight_plan_only(tmp_inventory, capsys):
    _write_host(tmp_inventory)
    oci_mod.snapshot_preflight.callback(
        host_id="srv-test-1",
        instance_ocid=None,
        compartment_ocid=None,
        display_name=None,
        stop=True,
        gate=False,
        plan_only=True,
        json_output=True,
    )
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["status"] == "dry-run"
    assert data["plan_only"] is True
    assert data["snapshot_id"].startswith("pending-")
    # --plan must NOT touch the inventory
    text = (tmp_inventory / "srv-test-1.yaml").read_text()
    assert "oci:" not in text
    assert "last_snapshot_id" not in text


def test_restore_drill_rejects_pending_when_live(tmp_inventory):
    _write_host(tmp_inventory)
    oci_mod._update_inventory_oci_block(
        host_id="srv-test-1",
        snapshot_id="pending-fake",
        snapshot_at="2026-06-18T00:00:00Z",
        routine_schedule="weekly Sun 04:00 BRT",
        dry_run=False,
    )
    with pytest.raises(Exception) as ei:
        oci_mod.restore_drill.callback(
            host_id="srv-test-1",
            snapshot_id=None,
            compartment_ocid=None,
            availability_domain=None,
            shape="VM.Standard.A1.Flex",
            subnet_ocid=None,
            display_name=None,
            dry_run=False,
            keep_instance=False,
            json_output=False,
        )
    assert "pending" in str(ei.value).lower()


def test_restore_drill_dry_run_with_pending(tmp_inventory):
    _write_host(tmp_inventory)
    oci_mod._update_inventory_oci_block(
        host_id="srv-test-1",
        snapshot_id="pending-fake",
        snapshot_at="2026-06-18T00:00:00Z",
        routine_schedule=None,
        dry_run=False,
    )
    oci_mod.restore_drill.callback(
        host_id="srv-test-1",
        snapshot_id=None,
        compartment_ocid=None,
        availability_domain=None,
        shape="VM.Standard.A1.Flex",
        subnet_ocid=None,
        display_name=None,
        dry_run=True,
        keep_instance=False,
        json_output=True,
    )
    drill_log = next(oci_mod.OCI_DRILL_LOG_DIR.glob("restore-drill-*.log"))
    payload = json.loads(drill_log.read_text())
    assert payload["status"] == "dry-run"
    assert payload["snapshot_id"] == "pending-fake"
    assert "oci compute instance launch" in " ".join(payload["oci_cmd"])


def test_restore_drill_accepts_explicit_real_id(tmp_inventory):
    _write_host(tmp_inventory)
    oci_mod.restore_drill.callback(
        host_id="srv-test-1",
        snapshot_id="ocid1.image.oc1.iad.aaaaaaaEXAMPLE",
        compartment_ocid=None,
        availability_domain=None,
        shape="VM.Standard.A1.Flex",
        subnet_ocid=None,
        display_name=None,
        dry_run=True,
        keep_instance=False,
        json_output=True,
    )
    drill_log = next(oci_mod.OCI_DRILL_LOG_DIR.glob("restore-drill-*.log"))
    payload = json.loads(drill_log.read_text())
    assert payload["snapshot_id"] == "ocid1.image.oc1.iad.aaaaaaaEXAMPLE"
