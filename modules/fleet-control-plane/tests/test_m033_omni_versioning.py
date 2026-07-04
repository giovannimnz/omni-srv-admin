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
from omni.fleet_versioning import collect_omni_version  # noqa: E402


def fake_git_runner(argv: list[str], cwd: Path | None, timeout: int):
    command = " ".join(argv)
    if argv[:3] == ["git", "rev-parse", "--abbrev-ref"]:
        return 0, "main\n", ""
    if argv[:2] == ["git", "rev-parse"]:
        if argv[-1] == "HEAD":
            return 0, "abc123\n", ""
        return 0, "def456\n", ""
    if argv[:3] == ["git", "status", "--porcelain"]:
        return 0, "", ""
    if argv[:3] == ["git", "describe", "--tags"]:
        return 0, "v0.1.0\n", ""
    return 127, "", command


def test_collect_omni_version_reads_repo_state(tmp_path):
    init_file = tmp_path / "cli" / "omni"
    init_file.mkdir(parents=True)
    (init_file / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")

    payload = collect_omni_version(
        "atius-srv-1",
        repo_root=tmp_path,
        github_repo="giovannimnz/omni-srv-admin",
        desired_version="0.1.0",
        track_branch="main",
        runner=fake_git_runner,
    )

    assert payload["installed_version"] == "0.1.0"
    assert payload["git_branch"] == "main"
    assert payload["git_commit"] == "abc123"
    assert payload["github_version"] == "0.1.0"
    assert payload["github_commit"] == "def456"
    assert payload["git_dirty"] is False


def test_queue_self_update_dry_run_uses_matrix(tmp_path, monkeypatch):
    matrix = {
        "component": "omni-srv-admin",
        "github_repo": "giovannimnz/omni-srv-admin",
        "desired_version": "0.1.0",
        "target_hosts": ["atius-srv-1", "giovanni-w11-pc"],
        "hosts": {
            "atius-srv-1": {
                "repo_dir": "/home/ubuntu/GitHub/omni-srv-admin",
                "track_branch": "main",
                "command_key": "omni.self-update.linux",
                "scheduler": "omni-fleet-agent.service",
            },
            "giovanni-w11-pc": {
                "repo_dir": "C:\\Users\\muniz\\Documents\\GitHub\\omni-srv-admin",
                "track_branch": "main",
                "command_key": "omni.self-update.windows",
                "scheduler": "OmniFleetAgent",
            },
        },
    }

    def fake_load_host(host_id: str):
        return (
            tmp_path / f"{host_id}.yaml",
            {
                "id": host_id,
                "platform": {"os": "windows-11" if host_id == "giovanni-w11-pc" else "ubuntu-24.04"},
            },
            host_id,
        )

    monkeypatch.setattr(fleet_module, "load_omni_version_matrix", lambda source: matrix)
    monkeypatch.setattr(fleet_module, "_load_host", fake_load_host)

    result = CliRunner().invoke(fleet_module.fleet, ["queue-self-update", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["desired_version"] == "0.1.0"
    assert [item["command_key"] for item in payload["plans"]] == [
        "omni.self-update.linux",
        "omni.self-update.windows",
    ]
