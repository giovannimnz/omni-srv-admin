from __future__ import annotations

import json
import shutil
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
    monkeypatch.setattr(agent_content, "_run_validate_command", lambda _target: {"ok": True, "returncode": 0, "stdout": "", "stderr": ""})
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


def test_ssh_extract_tree_quotes_transactional_remote_command(monkeypatch, tmp_path):
    captured = {}

    class Result:
        returncode = 0
        stderr = b""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(agent_content, "_ssh_capture_tree", lambda _root: b"archive")
    monkeypatch.setattr(agent_content.subprocess, "run", fake_run)
    source_root = tmp_path / "demo-skill"

    agent_content._ssh_extract_tree(
        {"host": "atius-srv-1", "user": "ubuntu"},
        source_root,
        "/home/ubuntu/.codex",
        "skills/demo-skill",
    )

    remote_command = captured["command"][-1]
    assert remote_command.startswith("'")
    assert "stage=$(mktemp -d" in remote_command
    assert "test -d \"$next\"" in remote_command
    assert "rm -rf \"$dest\"" not in remote_command
    assert captured["kwargs"]["input"] == b"archive"


def test_ssh_apply_refuses_skill_pack_extract_when_backup_fails(monkeypatch, tmp_path):
    source_root = tmp_path / "item" / "codex"
    _write(source_root / "skills" / "demo-skill" / "SKILL.md", "# demo\n")
    target = {
        "runtime": "ssh-linux",
        "host": "atius-srv-1",
        "user": "ubuntu",
        "home": "/home/ubuntu/.codex",
        "product": "codex",
    }
    item = {
        "name": "demo-skill",
        "kind": "skill-pack",
        "files": [{"path": "codex/skills/demo-skill/SKILL.md"}],
    }
    extracted = []

    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda _pack, _item: source_root.parent)
    monkeypatch.setattr(agent_content, "_ssh_extract_tree", lambda *_args: extracted.append(True))

    try:
        agent_content._apply_item("demo", item, target)
    except agent_content.click.ClickException as exc:
        assert "desabilitado" in str(exc)
    else:
        raise AssertionError("expected a failed remote backup to abort apply")
    assert extracted == []


def test_ssh_skill_pack_apply_fails_closed_without_touching_unmanaged_content(monkeypatch, tmp_path):
    source_root = tmp_path / "item" / "codex"
    _write(source_root / "skills" / "demo-skill" / "SKILL.md", "# managed skill\n")
    _write(source_root / "slash-commands" / "demo.md", "# managed command\n")
    home = tmp_path / "remote-codex-home"
    _write(home / "config.toml", "keep = true\n")
    _write(home / "unrelated-sentinel.txt", "must survive\n")
    target = {
        "runtime": "ssh-linux",
        "host": "atius-srv-1",
        "user": "ubuntu",
        "home": str(home),
        "product": "codex",
    }
    item = {
        "name": "demo-skill-pack",
        "kind": "skill-pack",
        "files": [
            {"path": "codex/skills/demo-skill/SKILL.md"},
            {"path": "codex/slash-commands/demo.md"},
        ],
    }
    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda _pack, _item: source_root.parent)
    with pytest.raises(agent_content.click.ClickException, match="desabilitado"):
        agent_content._apply_item("demo", item, target)

    assert (home / "unrelated-sentinel.txt").read_text(encoding="utf-8") == "must survive\n"
    assert (home / "config.toml").read_text(encoding="utf-8") == "keep = true\n"
    assert not (home / "skills" / "demo-skill").exists()
    assert not (home / "slash-commands" / "demo.md").exists()


def test_ssh_apply_never_archives_unlisted_source_content(monkeypatch, tmp_path):
    source = tmp_path / "item"
    _write(source / "SKILL.md", "managed\n")
    _write(source / "unlisted" / "secret.md", "must never deploy\n")
    target = {"runtime": "ssh-linux", "host": "example", "user": "ubuntu", "home": "/home/ubuntu/.codex", "product": "codex"}
    item = {"name": "demo", "kind": "skill", "install": {"codex": {"rel_path": "skills/demo"}}}
    captured = []
    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda *_args: source)
    monkeypatch.setattr(agent_content, "_ssh_capture_tree", lambda path: captured.append(path))

    with pytest.raises(agent_content.click.ClickException, match="desabilitado"):
        agent_content._apply_item("demo", item, target)

    assert captured == []


def test_ssh_apply_refuses_regular_item_extract_when_backup_fails(monkeypatch, tmp_path):
    target = {
        "runtime": "ssh-linux",
        "host": "atius-srv-1",
        "user": "ubuntu",
        "home": "/home/ubuntu/.codex",
        "product": "codex",
    }
    item = {
        "name": "demo-item",
        "kind": "skill",
        "install": {"codex": {"rel_path": "skills/demo-item"}},
    }
    extracted = []

    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda _pack, _item: tmp_path / "item")
    monkeypatch.setattr(agent_content, "_ssh_extract_tree", lambda *_args: extracted.append(True))

    try:
        agent_content._apply_item("demo", item, target)
    except agent_content.click.ClickException as exc:
        assert "desabilitado" in str(exc)
    else:
        raise AssertionError("expected a failed remote backup to abort apply")
    assert extracted == []


def test_sync_apply_fails_when_runtime_validation_fails_in_text_and_json(monkeypatch):
    target = {"product": "codex", "runtime": "ssh-linux", "host": "atius-srv-1", "user": "ubuntu"}
    item = {"name": "demo-skill"}
    monkeypatch.setattr(agent_content, "_load_manifest", lambda _pack: {"items": [item]})
    monkeypatch.setattr(agent_content, "_load_targets", lambda _pack: {"targets": {"target": target}})
    monkeypatch.setattr(agent_content, "_validate_item", lambda _pack, _item: {"ok": True})
    monkeypatch.setattr(
        agent_content,
        "_apply_item",
        lambda _pack, _item, _target: {"item": "demo-skill", "backup_root": "/tmp/backup", "post_status": {"status": "applied-ssh"}},
    )

    for runtime_validation in (
        {"ok": False, "returncode": 7, "stdout": "", "stderr": "validator failed"},
        {"ok": False, "error": "validator unavailable", "stdout": "", "stderr": ""},
    ):
        monkeypatch.setattr(agent_content, "_run_validate_command", lambda _target: runtime_validation)
        for json_output in (False, True):
            args = ["sync", "--pack", "demo", "--target", "target", "--apply"]
            if json_output:
                args.append("--json-output")
            result = CliRunner().invoke(agent_content.agent_content, args)
            assert result.exit_code != 0
            assert "validação do target falhou" in result.output
            if json_output:
                payload = json.loads(result.output.split("Error:")[0])
                assert payload["runtime_validation"] == runtime_validation


def test_sync_rolls_back_first_local_item_when_second_item_fails(monkeypatch, tmp_path):
    home = tmp_path / "home"
    sources = {"first": tmp_path / "source-first", "second": tmp_path / "source-second"}
    _write(home / "skills" / "first" / "old.txt", "old-first\n")
    _write(sources["first"] / "new.txt", "new-first\n")
    _write(sources["second"] / "new.txt", "new-second\n")
    target = {"product": "codex", "runtime": "windows", "home": str(home)}
    items = [
        {"name": name, "kind": "skill", "install": {"codex": {"rel_path": f"skills/{name}"}}}
        for name in ("first", "second")
    ]
    monkeypatch.setattr(agent_content, "_load_manifest", lambda _pack: {"items": items})
    monkeypatch.setattr(agent_content, "_load_targets", lambda _pack: {"targets": {"target": target}})
    monkeypatch.setattr(agent_content, "_validate_item", lambda *_args: {"ok": True})
    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda _pack, item: sources[item["name"]])
    real_apply = agent_content._apply_item

    def fail_second(pack, item, target_cfg):
        if item["name"] == "second":
            raise OSError("second item extraction failed")
        return real_apply(pack, item, target_cfg)

    monkeypatch.setattr(agent_content, "_apply_item", fail_second)
    result = CliRunner().invoke(agent_content.agent_content, ["sync", "--pack", "demo", "--target", "target", "--apply"])
    assert result.exit_code != 0
    assert (home / "skills" / "first" / "old.txt").read_text() == "old-first\n"
    assert not (home / "skills" / "first" / "new.txt").exists()


def test_sync_rolls_back_local_item_when_validator_fails(monkeypatch, tmp_path):
    home = tmp_path / "home"
    source = tmp_path / "source"
    _write(home / "skills" / "demo" / "old.txt", "old\n")
    _write(source / "new.txt", "new\n")
    target = {"product": "codex", "runtime": "windows", "home": str(home), "validate": {"command": ["false"]}}
    item = {"name": "demo", "kind": "skill", "install": {"codex": {"rel_path": "skills/demo"}}}
    monkeypatch.setattr(agent_content, "_load_manifest", lambda _pack: {"items": [item]})
    monkeypatch.setattr(agent_content, "_load_targets", lambda _pack: {"targets": {"target": target}})
    monkeypatch.setattr(agent_content, "_validate_item", lambda *_args: {"ok": True})
    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda *_args: source)
    monkeypatch.setattr(agent_content, "_run_validate_command", lambda _target: {"ok": False, "stderr": "validator failed"})
    result = CliRunner().invoke(agent_content.agent_content, ["sync", "--pack", "demo", "--target", "target", "--apply"])
    assert result.exit_code != 0
    assert (home / "skills" / "demo" / "old.txt").read_text() == "old\n"
    assert not (home / "skills" / "demo" / "new.txt").exists()


@pytest.mark.parametrize(
    ("item", "fragment"),
    [
        ({"name": "demo", "kind": "skill", "install": {"codex": {"rel_path": "../.ssh"}}}, "install.codex.rel_path"),
        ({"name": "demo", "kind": "skill-pack", "files": [{"path": "codex/../escape/SKILL.md"}]}, "files[].path"),
    ],
)
def test_sync_rejects_manifest_traversal_before_validation(monkeypatch, tmp_path, item, fragment):
    target = {"product": "codex", "runtime": "windows", "home": str(tmp_path / "home")}
    monkeypatch.setattr(agent_content, "_load_manifest", lambda _pack: {"items": [item]})
    monkeypatch.setattr(agent_content, "_load_targets", lambda _pack: {"targets": {"target": target}})
    called = False

    def should_not_validate(*_args):
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(agent_content, "_validate_item", should_not_validate)
    result = CliRunner().invoke(agent_content.agent_content, ["sync", "--pack", "demo", "--target", "target"])
    assert result.exit_code != 0
    assert fragment in result.output
    assert called is False


def test_sync_rejects_local_product_root_outside_home(monkeypatch, tmp_path):
    target = {
        "product": "codex", "runtime": "windows", "home": str(tmp_path / "home"),
        "skills_root": str(tmp_path / "outside"),
    }
    item = {"name": "demo", "kind": "skill", "install": {"codex": {"rel_path": "skills/demo"}}}
    monkeypatch.setattr(agent_content, "_load_manifest", lambda _pack: {"items": [item]})
    monkeypatch.setattr(agent_content, "_load_targets", lambda _pack: {"targets": {"target": target}})
    result = CliRunner().invoke(agent_content.agent_content, ["sync", "--pack", "demo", "--target", "target"])
    assert result.exit_code != 0
    assert "fora do home" in result.output


def test_remote_posix_path_for_ssh_target():
    target = {'runtime': 'ssh-linux', 'host': 'atius-srv-1', 'user': 'ubuntu', 'home': '/home/ubuntu/.hermes'}
    local = Path('/tmp/example/SKILL.md')
    out = agent_content._remote_posix_path(target, local)
    assert out.replace('\\', '/') == '/tmp/example/SKILL.md'


def test_post_status_summary_accepts_ssh_apply_shape():
    assert agent_content._post_status_summary({'status': 'applied-ssh'}) == 'post_status=applied-ssh'
