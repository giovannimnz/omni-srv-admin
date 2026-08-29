from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

REPO = Path(__file__).resolve().parents[3]
REPO_CLI = REPO / "cli"
if str(REPO_CLI) not in sys.path:
    sys.path.insert(0, str(REPO_CLI))

from omni import agent_content  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_validate_pack_passes_for_hermes_skills(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    pack_dir = repo / "modules" / "agent-content-packs" / "packs" / "hermes-skills"
    item_dir = pack_dir / "items" / "demo-skill"
    _write(item_dir / "SKILL.md", "---\nname: demo-skill\ndescription: demo\n---\n\n# demo\n")
    _write(repo / "modules" / "agent-content-packs" / "manifest-index.yaml", "version: 1\npacks:\n  - name: hermes-skills\n    manifest: modules/agent-content-packs/packs/hermes-skills/manifest.yaml\n")
    import hashlib
    sha = hashlib.sha256((item_dir / "SKILL.md").read_bytes()).hexdigest()
    _write(pack_dir / "manifest.yaml", f"version: 1\npack: hermes-skills\nitems:\n  - name: demo-skill\n    kind: skill\n    products: [hermes]\n    platforms: [windows, linux]\n    source_path: items/demo-skill\n    required_files: [SKILL.md]\n    files:\n      - path: SKILL.md\n        sha256: {sha}\n        bytes: 0\n")
    monkeypatch.setattr(agent_content, "REPO", repo)
    monkeypatch.setattr(agent_content, "PACKS_ROOT", repo / "modules" / "agent-content-packs" / "packs")
    monkeypatch.setattr(agent_content, "INDEX_PATH", repo / "modules" / "agent-content-packs" / "manifest-index.yaml")
    result = CliRunner().invoke(agent_content.agent_content, ["validate-pack", "--pack", "hermes-skills", "--json-output"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True


def test_sync_dry_run_reports_missing_files(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    pack_dir = repo / "modules" / "agent-content-packs" / "packs" / "hermes-skills"
    item_dir = pack_dir / "items" / "demo-skill"
    _write(item_dir / "SKILL.md", "---\nname: demo-skill\ndescription: demo\n---\n\n# demo\n")
    _write(repo / "modules" / "agent-content-packs" / "manifest-index.yaml", "version: 1\npacks:\n  - name: hermes-skills\n    manifest: modules/agent-content-packs/packs/hermes-skills/manifest.yaml\n")
    import hashlib
    sha = hashlib.sha256((item_dir / "SKILL.md").read_bytes()).hexdigest()
    _write(pack_dir / "manifest.yaml", f"version: 1\npack: hermes-skills\nitems:\n  - name: demo-skill\n    kind: skill\n    category: devops\n    products: [hermes]\n    platforms: [windows, linux]\n    source_path: items/demo-skill\n    required_files: [SKILL.md]\n    files:\n      - path: SKILL.md\n        sha256: {sha}\n        bytes: 0\n    install:\n      hermes:\n        rel_path: skills/devops/demo-skill\n")
    home = tmp_path / "home"
    _write(pack_dir / "targets.yaml", f"version: 1\ntargets:\n  local:\n    product: hermes\n    runtime: windows\n    profile: default\n    home: {home.as_posix()}\n    skills_root: {(home / 'skills').as_posix()}\n")
    monkeypatch.setattr(agent_content, "REPO", repo)
    monkeypatch.setattr(agent_content, "PACKS_ROOT", repo / "modules" / "agent-content-packs" / "packs")
    monkeypatch.setattr(agent_content, "INDEX_PATH", repo / "modules" / "agent-content-packs" / "manifest-index.yaml")
    result = CliRunner().invoke(agent_content.agent_content, ["sync", "--pack", "hermes-skills", "--target", "local", "--json-output"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["results"][0]["missing"] == 1


def test_sync_apply_copies_files_and_creates_backup(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    pack_dir = repo / "modules" / "agent-content-packs" / "packs" / "hermes-skills"
    item_dir = pack_dir / "items" / "demo-skill"
    _write(item_dir / "SKILL.md", "---\nname: demo-skill\ndescription: demo\n---\n\n# demo\n")
    _write(repo / "modules" / "agent-content-packs" / "manifest-index.yaml", "version: 1\npacks:\n  - name: hermes-skills\n    manifest: modules/agent-content-packs/packs/hermes-skills/manifest.yaml\n")
    import hashlib
    sha = hashlib.sha256((item_dir / "SKILL.md").read_bytes()).hexdigest()
    _write(pack_dir / "manifest.yaml", f"version: 1\npack: hermes-skills\nitems:\n  - name: demo-skill\n    kind: skill\n    category: devops\n    products: [hermes]\n    platforms: [windows, linux]\n    source_path: items/demo-skill\n    required_files: [SKILL.md]\n    files:\n      - path: SKILL.md\n        sha256: {sha}\n        bytes: 0\n    install:\n      hermes:\n        rel_path: skills/devops/demo-skill\n")
    home = tmp_path / "home"
    dest = home / "skills" / "devops" / "demo-skill"
    _write(dest / "SKILL.md", "---\nname: old\ndescription: old\n---\n")
    _write(pack_dir / "targets.yaml", f"version: 1\ntargets:\n  local:\n    product: hermes\n    runtime: windows\n    profile: default\n    home: {home.as_posix()}\n    skills_root: {(home / 'skills').as_posix()}\n")
    monkeypatch.setattr(agent_content, "REPO", repo)
    monkeypatch.setattr(agent_content, "PACKS_ROOT", repo / "modules" / "agent-content-packs" / "packs")
    monkeypatch.setattr(agent_content, "INDEX_PATH", repo / "modules" / "agent-content-packs" / "manifest-index.yaml")
    result = CliRunner().invoke(agent_content.agent_content, ["sync", "--pack", "hermes-skills", "--target", "local", "--apply", "--json-output"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert (dest / "SKILL.md").exists()
    assert "demo-skill" in (dest / "SKILL.md").read_text(encoding="utf-8")
    backup_root = Path(payload["results"][0]["backup_root"])
    assert backup_root.exists()


def test_run_validate_command_ssh_linux(monkeypatch):
    calls = []
    def fake_ssh_run(target, command, timeout=120):
        calls.append((target, command, timeout))
        class R:
            returncode = 0
            stdout = 'ok\n'
            stderr = ''
        return R()
    monkeypatch.setattr(agent_content, '_ssh_run', fake_ssh_run)
    target = {'runtime': 'ssh-linux', 'host': 'atius-srv-1', 'user': 'ubuntu', 'validate': {'command': ['/home/ubuntu/.local/bin/hermes', 'skills', 'list']}}
    result = agent_content._run_validate_command(target)
    assert result['ok'] is True
    assert calls


def test_remote_posix_path_for_ssh_target():
    target = {'runtime': 'ssh-linux', 'host': 'atius-srv-1', 'user': 'ubuntu', 'home': '/home/ubuntu/.hermes'}
    local = Path('/tmp/example/SKILL.md')
    out = agent_content._remote_posix_path(target, local)
    assert out.replace('\\', '/') == '/tmp/example/SKILL.md'


def test_post_status_summary_accepts_ssh_apply_shape():
    assert agent_content._post_status_summary({'status': 'applied-ssh'}) == 'post_status=applied-ssh'


def test_ssh_apply_fails_closed_before_any_remote_write(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(agent_content, "_ssh_run", lambda *_args, **_kwargs: calls.append("ssh"))
    monkeypatch.setattr(
        agent_content,
        "_ssh_extract_tree",
        lambda *_args, **_kwargs: calls.append("extract"),
    )

    with pytest.raises(agent_content.click.ClickException, match="desabilitado"):
        agent_content._apply_item(
            "codex-skills",
            {"name": "xrdp-abnt2-fleet", "kind": "skill"},
            {
                "runtime": "ssh-linux",
                "host": "atius-srv-2",
                "user": "ubuntu",
                "home": "/home/ubuntu/.codex",
                "product": "codex",
            },
        )

    assert calls == []
