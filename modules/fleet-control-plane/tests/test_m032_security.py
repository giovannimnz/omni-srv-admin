from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from click.testing import CliRunner

REPO = Path(__file__).resolve().parents[3]
os.environ["OMNI_SRV_ADMIN"] = str(REPO)
sys.path.insert(0, str(REPO / "cli"))

from omni import fleet as fleet_module  # noqa: E402
from omni.fleet_security import collect_security_report  # noqa: E402


def fake_runner(argv: list[str], timeout: int):
    if argv[:2] == ["pro", "status"]:
        return 0, json.dumps({"attached": True}), ""
    if argv[:2] == ["pro", "security-status"]:
        return 0, json.dumps({"summary": {"num_installed_packages": 10, "ua": {"attached": True}}}), ""
    if argv[:2] == ["pro", "cves"]:
        return 0, json.dumps({"cves": []}), ""
    return 127, "", "missing"


def test_security_report_collects_pro_json_without_mutation():
    report = collect_security_report("atius-srv-1", runner=fake_runner)

    assert report["host"] == "atius-srv-1"
    assert report["mutation"] == "none"
    assert report["summary"]["num_installed_packages"] == 10


def test_landscape_parity_cli_reports_boundaries():
    result = CliRunner().invoke(fleet_module.fleet, ["landscape-parity", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    decisions = " ".join(row["decision"] for row in payload["rows"])
    assert "no automatic fixes" in payload["fix_policy"]
    assert "Omni owns" in decisions

