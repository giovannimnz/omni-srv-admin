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
from omni.fleet_collectors import collect_programs, read_only_command_allowlist  # noqa: E402


def fake_runner(argv: list[str], timeout: int):
    command = " ".join(argv)
    if argv[0] == "dpkg-query":
        return 0, "bash\t5.2.21-2ubuntu4\tarm64\n", ""
    if argv[:4] == ["python3", "-m", "pip", "list"]:
        return 0, json.dumps([{"name": "click", "version": "8.1.7"}]), ""
    if argv[:3] == ["npm", "ls", "-g"]:
        return 0, json.dumps({"dependencies": {"wrangler": {"version": "4.0.0"}}}), ""
    if argv[:3] == ["pm2", "jlist"]:
        return 0, json.dumps([{"name": "api", "pm2_env": {"status": "online"}}]), ""
    if argv[:2] == ["systemctl", "list-units"]:
        return 0, "ssh.service loaded active running OpenSSH\n", ""
    if command == "cargo install --list":
        return 0, "zellij v0.44.3:\n    zellij\n", ""
    return 127, "", f"{argv[0]} missing"


def test_collect_programs_normalizes_read_only_outputs():
    payload = collect_programs("atius-srv-1", runner=fake_runner)

    assert payload["host"] == "atius-srv-1"
    names = {record["name"] for record in payload["programs"]}
    assert {"bash", "click", "wrangler", "api", "ssh.service", "zellij"}.issubset(names)
    assert payload["warnings"]


def test_collector_allowlist_has_no_mutating_commands():
    forbidden = ("upgrade", "remove", "refresh", "restart", "fix")
    for argv in read_only_command_allowlist():
        command = " ".join(argv)
        if command == "cargo install --list":
            continue
        assert not any(token in argv for token in forbidden), command


def test_agent_collect_programs_cli_can_be_monkeypatched(monkeypatch, tmp_path):
    monkeypatch.setattr(fleet_module, "PROGRAMS_DIR", tmp_path)
    monkeypatch.setattr(
        fleet_module,
        "collect_programs",
        lambda host: {"host": host, "program_count": 1, "programs": [{"host": host, "name": "x"}], "warnings": [], "generated_at": "now"},
    )

    result = CliRunner().invoke(fleet_module.fleet, ["agent", "collect-programs", "--host", "atius-srv-1", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["program_count"] == 1

