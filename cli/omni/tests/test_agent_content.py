from __future__ import annotations

import json
import os
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


def test_transaction_timestamps_are_collision_resistant() -> None:
    first = agent_content._timestamp()
    second = agent_content._timestamp()
    assert first != second
    assert len(first.split("-")) >= 5


@pytest.mark.parametrize("value", ["../outside", "/etc/passwd", "skills/../../root", "./skill"])
def test_safe_relative_path_rejects_traversal_and_absolute_paths(value: str) -> None:
    with pytest.raises(agent_content.click.ClickException, match="path inseguro"):
        agent_content._safe_relative_path(value, "test")


def test_manifest_index_rejects_manifest_escape(tmp_path, monkeypatch) -> None:
    index = tmp_path / "manifest-index.yaml"
    _write(index, "version: 1\npacks:\n  - name: demo\n    manifest: ../outside.yaml\n")
    monkeypatch.setattr(agent_content, "REPO", tmp_path)
    monkeypatch.setattr(agent_content, "INDEX_PATH", index)
    with pytest.raises(agent_content.click.ClickException, match="path inseguro"):
        agent_content._manifest_path("demo")


def test_validate_item_rejects_undeclared_file(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    pack_dir = repo / "modules" / "agent-content-packs" / "packs" / "hermes-skills"
    item_dir = pack_dir / "items" / "demo-skill"
    _write(item_dir / "SKILL.md", "---\nname: demo-skill\ndescription: demo\n---\n")
    _write(item_dir / "undeclared.txt", "must not ship")
    _write(repo / "modules" / "agent-content-packs" / "manifest-index.yaml", "version: 1\npacks:\n  - name: hermes-skills\n    manifest: modules/agent-content-packs/packs/hermes-skills/manifest.yaml\n")
    _write(pack_dir / "manifest.yaml", "version: 1\npack: hermes-skills\nitems:\n  - name: demo-skill\n    kind: skill\n    source_path: items/demo-skill\n    files:\n      - path: SKILL.md\n    required_files: [SKILL.md]\n    install:\n      hermes:\n        rel_path: skills/demo-skill\n")
    monkeypatch.setattr(agent_content, "REPO", repo)
    monkeypatch.setattr(agent_content, "PACKS_ROOT", pack_dir.parent)
    monkeypatch.setattr(agent_content, "INDEX_PATH", repo / "modules" / "agent-content-packs" / "manifest-index.yaml")

    result = agent_content._validate_item(
        "hermes-skills",
        agent_content._load_manifest("hermes-skills")["items"][0],
    )

    assert result["ok"] is False
    assert "arquivo não declarado no manifest: undeclared.txt" in result["issues"]


def test_validate_item_rejects_source_symlinks(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    pack_dir = repo / "modules" / "agent-content-packs" / "packs" / "hermes-skills"
    item_dir = pack_dir / "items" / "demo-skill"
    outside = tmp_path / "outside.md"
    _write(outside, "secret outside tree")
    item_dir.mkdir(parents=True)
    (item_dir / "SKILL.md").symlink_to(outside)
    _write(repo / "modules" / "agent-content-packs" / "manifest-index.yaml", "version: 1\npacks:\n  - name: hermes-skills\n    manifest: modules/agent-content-packs/packs/hermes-skills/manifest.yaml\n")
    _write(pack_dir / "manifest.yaml", "version: 1\npack: hermes-skills\nitems:\n  - name: demo-skill\n    kind: skill\n    source_path: items/demo-skill\n    files:\n      - path: SKILL.md\n    required_files: [SKILL.md]\n    install:\n      hermes:\n        rel_path: skills/demo-skill\n")
    monkeypatch.setattr(agent_content, "REPO", repo)
    monkeypatch.setattr(agent_content, "PACKS_ROOT", pack_dir.parent)
    monkeypatch.setattr(agent_content, "INDEX_PATH", repo / "modules" / "agent-content-packs" / "manifest-index.yaml")

    result = agent_content._validate_item(
        "hermes-skills",
        agent_content._load_manifest("hermes-skills")["items"][0],
    )

    assert result["ok"] is False
    assert any("symlink proibido" in issue for issue in result["issues"])


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


def test_ssh_base_command_supports_host_specific_identity_file():
    command = agent_content._ssh_base_command(
        {
            "runtime": "ssh-linux",
            "host": "10.14.1.14",
            "user": "ubuntu",
            "identity_file": "~/.ssh/id_oracle",
        }
    )

    assert command[-1] == "ubuntu@10.14.1.14"
    assert "IdentitiesOnly=yes" in command
    assert str(Path.home() / ".ssh" / "id_oracle") in command


def test_remote_posix_path_for_ssh_target():
    target = {'runtime': 'ssh-linux', 'host': 'atius-srv-1', 'user': 'ubuntu', 'home': '/home/ubuntu/.hermes'}
    local = Path('/tmp/example/SKILL.md')
    out = agent_content._remote_posix_path(target, local)
    assert out.replace('\\', '/') == '/tmp/example/SKILL.md'


def test_post_status_summary_accepts_ssh_apply_shape():
    assert agent_content._post_status_summary({'status': 'applied-ssh'}) == 'post_status=applied-ssh'


def test_linux_local_runtime_applies_and_validates(tmp_path, monkeypatch):
    item_dir = tmp_path / "items" / "demo"
    _write(item_dir / "SKILL.md", "demo\n")
    home = tmp_path / "home"
    marker = tmp_path / "validated"
    validator = tmp_path / "validate.sh"
    validator.write_text(f"#!/bin/sh\ntouch {marker}\n")
    validator.chmod(0o755)
    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda *_args: item_dir)

    target = {
        "runtime": "linux-local",
        "product": "hermes",
        "home": str(home),
        "skills_root": str(home / "skills"),
        "validate": {"command": [str(validator)]},
    }
    item = {
        "name": "demo",
        "kind": "skill",
        "install": {"hermes": {"rel_path": "skills/demo"}},
    }

    result = agent_content._apply_item("hermes-skills", item, target)
    validation = agent_content._run_validate_command(target)
    assert (home / "skills/demo/SKILL.md").read_text() == "demo\n"
    assert result["post_status"]["status"] == "noop"
    assert validation["ok"] is True
    assert marker.exists()


def test_linux_local_runtime_rolls_back_when_validation_fails(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    pack_dir = repo / "modules/agent-content-packs/packs/hermes-skills"
    item_dir = pack_dir / "items/demo"
    _write(item_dir / "SKILL.md", "new\n")
    import hashlib
    sha = hashlib.sha256((item_dir / "SKILL.md").read_bytes()).hexdigest()
    _write(repo / "modules/agent-content-packs/manifest-index.yaml", "version: 1\npacks:\n  - name: hermes-skills\n    manifest: modules/agent-content-packs/packs/hermes-skills/manifest.yaml\n")
    _write(pack_dir / "manifest.yaml", f"version: 1\npack: hermes-skills\nitems:\n  - name: demo\n    kind: skill\n    products: [hermes]\n    platforms: [linux]\n    source_path: items/demo\n    required_files: [SKILL.md]\n    files:\n      - path: SKILL.md\n        sha256: {sha}\n        bytes: 4\n    install:\n      hermes:\n        rel_path: skills/demo\n")
    home = tmp_path / "home"
    _write(home / "skills/demo/SKILL.md", "old\n")
    validator = tmp_path / "fail.sh"
    validator.write_text("#!/bin/sh\nexit 9\n")
    validator.chmod(0o755)
    _write(pack_dir / "targets.yaml", f"version: 1\ntargets:\n  local:\n    product: hermes\n    runtime: linux-local\n    home: {home}\n    skills_root: {home / 'skills'}\n    validate:\n      command: [{validator}]\n")
    monkeypatch.setattr(agent_content, "REPO", repo)
    monkeypatch.setattr(agent_content, "PACKS_ROOT", repo / "modules/agent-content-packs/packs")
    monkeypatch.setattr(agent_content, "INDEX_PATH", repo / "modules/agent-content-packs/manifest-index.yaml")

    result = CliRunner().invoke(agent_content.agent_content, ["sync", "--pack", "hermes-skills", "--target", "local", "--apply", "--json-output"])
    assert result.exit_code != 0
    assert (home / "skills/demo/SKILL.md").read_text() == "old\n"


def test_linux_local_skill_pack_rolls_back_partial_copy_failure(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write(source / "one.txt", "new-one\n")
    _write(source / "two.txt", "new-two\n")
    home = tmp_path / "home"
    _write(home / "one.txt", "old-one\n")
    _write(home / "two.txt", "old-two\n")
    mappings = [(source / "one.txt", home / "one.txt"), (source / "two.txt", home / "two.txt")]
    original = agent_content.shutil.copy2
    calls = 0

    def fail_second(src, dst, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("injected partial copy failure")
        return original(src, dst, *args, **kwargs)

    monkeypatch.setattr(agent_content, "_item_mappings", lambda *_args: (source, home, mappings))
    monkeypatch.setattr(agent_content.shutil, "copy2", fail_second)
    with pytest.raises(OSError, match="injected partial copy failure"):
        agent_content._apply_item(
            "demo",
            {"name": "demo", "kind": "skill-pack"},
            {"runtime": "linux-local", "product": "hermes", "home": str(home)},
        )
    assert (home / "one.txt").read_text() == "old-one\n"
    assert (home / "two.txt").read_text() == "old-two\n"
    assert not list(home.glob(".*.agent-content-*"))


def test_linux_local_rejects_symlink_destination(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write(source / "SKILL.md", "payload\n")
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    _write(outside, "protected\n")
    (home / "skills").mkdir(parents=True)
    (home / "skills/demo").symlink_to(outside)
    monkeypatch.setattr(agent_content, "_item_mappings", lambda *_args: (source, home / "skills/demo", [(source / "SKILL.md", home / "skills/demo/SKILL.md")]))
    with pytest.raises(agent_content.click.ClickException, match="inseguro|symlink"):
        agent_content._apply_item(
            "demo",
            {"name": "demo", "kind": "skill"},
            {"runtime": "linux-local", "product": "hermes", "home": str(home)},
        )
    assert outside.read_text() == "protected\n"


def test_local_tree_backup_and_rollback_preserve_internal_symlinks(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "target.txt").write_text("target\n")
    (source / "link.txt").symlink_to("target.txt")
    backup = tmp_path / "backup"
    agent_content._copy_tree(source, backup)
    assert (backup / "link.txt").is_symlink()
    destination = tmp_path / "destination"
    agent_content._rollback_local_item({"mode":"tree","destination":str(destination),"backup":str(backup),"existed":True})
    assert (destination / "link.txt").is_symlink()
    assert os.readlink(destination / "link.txt") == "target.txt"


def test_linux_local_skill_pack_rejects_symlink_parent(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write(source / "SKILL.md", "payload\n")
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    outside.mkdir()
    (home / "skills").mkdir(parents=True)
    (home / "skills/demo").symlink_to(outside, target_is_directory=True)
    destination = home / "skills/demo/SKILL.md"
    monkeypatch.setattr(agent_content, "_item_mappings", lambda *_args: (source, home, [(source / "SKILL.md", destination)]))
    with pytest.raises(agent_content.click.ClickException, match="symlink proibido"):
        agent_content._apply_item(
            "demo",
            {"name": "demo", "kind": "skill-pack"},
            {"runtime": "linux-local", "product": "hermes", "home": str(home)},
        )
    assert not (outside / "SKILL.md").exists()


def test_ssh_apply_uses_staging_backup_and_post_write_verification(tmp_path, monkeypatch):
    item_dir = tmp_path / "items" / "demo"
    _write(item_dir / "SKILL.md", "demo")
    commands: list[str] = []
    extracts: list[tuple[Path, str, str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda *_args: item_dir)
    monkeypatch.setattr(
        agent_content,
        "_ssh_extract_tree",
        lambda _target, source, home, rel: extracts.append((source, home, rel)),
    )
    monkeypatch.setattr(
        agent_content,
        "_ssh_run",
        lambda _target, command, timeout=120: (commands.append(command) or Result()),
    )
    monkeypatch.setattr(
        agent_content,
        "_compute_diff",
        lambda *_args: {
            "item": "demo",
            "status": "noop",
            "missing": 0,
            "changed": 0,
            "unchanged": 1,
            "extra": 0,
        },
    )

    result = agent_content._apply_item(
        "codex-skills",
        {
            "name": "demo",
            "kind": "skill",
            "install": {"codex": {"rel_path": "skills/demo"}},
        },
        {
            "runtime": "ssh-linux",
            "host": "atius-srv-4",
            "user": "ubuntu",
            "home": "/home/ubuntu/.codex",
            "skills_root": "/home/ubuntu/.codex/skills",
            "product": "codex",
        },
    )

    assert extracts[0][2] == "stage/tree"
    assert "backups/agent-content-sync" in commands[0]
    assert "mv \"$dest\" \"$before/tree\"" in commands[0]
    assert 'touch "$before/READY"' in commands[0]
    assert result["post_status"]["status"] == "noop"
    assert result["_rollback"]["mode"] == "tree"


def test_ssh_apply_rolls_back_when_post_write_hash_differs(tmp_path, monkeypatch):
    item_dir = tmp_path / "items" / "demo"
    _write(item_dir / "SKILL.md", "demo")
    rollbacks: list[dict[str, str]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda *_args: item_dir)
    monkeypatch.setattr(agent_content, "_ssh_extract_tree", lambda *_args: None)
    monkeypatch.setattr(agent_content, "_ssh_run", lambda *_args, **_kwargs: Result())
    monkeypatch.setattr(
        agent_content,
        "_compute_diff",
        lambda *_args: {"item": "demo", "status": "update", "missing": 0, "changed": 1, "unchanged": 0, "extra": 0},
    )
    monkeypatch.setattr(
        agent_content,
        "_ssh_rollback_item",
        lambda _target, rollback: rollbacks.append(rollback),
    )

    with pytest.raises(agent_content.click.ClickException, match="rollback aplicado"):
        agent_content._apply_item(
            "codex-skills",
            {"name": "demo", "kind": "skill", "install": {"codex": {"rel_path": "skills/demo"}}},
            {"runtime": "ssh-linux", "host": "atius-srv-4", "user": "ubuntu", "home": "/home/ubuntu/.codex", "product": "codex"},
        )

    assert rollbacks


def test_ssh_apply_rolls_back_when_post_write_verification_raises(tmp_path, monkeypatch):
    item_dir = tmp_path / "items/demo"
    _write(item_dir / "SKILL.md", "demo")
    rollbacks = []
    class Result:
        returncode = 0
        stdout = stderr = ""
    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda *_: item_dir)
    monkeypatch.setattr(agent_content, "_ssh_extract_tree", lambda *_: None)
    monkeypatch.setattr(agent_content, "_ssh_run", lambda *_args, **_kwargs: Result())
    monkeypatch.setattr(agent_content, "_compute_diff", lambda *_: (_ for _ in ()).throw(TimeoutError("verify timeout")))
    monkeypatch.setattr(agent_content, "_ssh_rollback_item", lambda _target, rollback: rollbacks.append(rollback))
    with pytest.raises(TimeoutError, match="verify timeout"):
        agent_content._apply_item(
            "codex-skills",
            {"name":"demo","kind":"skill","install":{"codex":{"rel_path":"skills/demo"}}},
            {"runtime":"ssh-linux","host":"atius-srv-4","user":"ubuntu","home":"/home/ubuntu/.codex","product":"codex"},
        )
    assert rollbacks[0]["mode"] == "tree"


def test_ssh_rollback_never_removes_destination_without_preimage(monkeypatch):
    commands: list[str] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        agent_content,
        "_ssh_run",
        lambda _target, command, timeout=120: (commands.append(command) or Result()),
    )

    agent_content._ssh_rollback_item(
        {"runtime": "ssh-linux", "host": "atius-srv-4", "user": "ubuntu"},
        {
            "mode": "tree",
            "backup_root": "/home/ubuntu/.codex/backups/demo/before",
            "remote_dest": "/home/ubuntu/.codex/skills/demo",
        },
    )

    command = commands[0]
    assert 'if [ -e "$before/tree" ] || [ -L "$before/tree" ]' in command
    assert 'elif [ -f "$before/ABSENT" ]' in command
    assert 'else exit 0' in command
    assert 'cp -a "$before/tree" "$dest"' in command


def test_ssh_apply_tree_installs_remote_error_trap_before_preimage_move(tmp_path, monkeypatch):
    item_dir = tmp_path / "items" / "demo"
    _write(item_dir / "SKILL.md", "demo")
    commands: list[str] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(agent_content, "_pack_item_dir", lambda *_args: item_dir)
    monkeypatch.setattr(agent_content, "_ssh_extract_tree", lambda *_args: None)
    monkeypatch.setattr(
        agent_content,
        "_ssh_run",
        lambda _target, command, timeout=120: (commands.append(command) or Result()),
    )
    monkeypatch.setattr(
        agent_content,
        "_compute_diff",
        lambda *_args: {"item": "demo", "status": "noop", "missing": 0, "changed": 0, "unchanged": 1, "extra": 0},
    )

    agent_content._apply_item(
        "codex-skills",
        {"name": "demo", "kind": "skill", "install": {"codex": {"rel_path": "skills/demo"}}},
        {"runtime": "ssh-linux", "host": "atius-srv-4", "user": "ubuntu", "home": "/home/ubuntu/.codex", "product": "codex"},
    )

    command = commands[0]
    assert "rollback_tree()" in command
    assert command.index("trap ") < command.index('mv "$dest" "$before/tree"')


def test_shared_agent_content_declares_srv4_targets_used_by_workflow() -> None:
    targets = agent_content._load_targets("shared-agent-content")["targets"]

    assert targets["srv4-hermes-default"] == {
        "product": "hermes",
        "runtime": "ssh-linux",
        "host": "atius-srv-4",
        "user": "ubuntu",
        "identity_file": "/home/ubuntu/.ssh/id_oracle",
        "home": "/home/ubuntu/.hermes",
        "skills_root": "/home/ubuntu/.hermes/skills",
        "validate": {"command": ["/home/ubuntu/.local/bin/hermes", "skills", "list"]},
    }
    assert targets["srv4-codex-default"]["product"] == "codex"
    assert targets["srv4-codex-default"]["identity_file"] == "/home/ubuntu/.ssh/id_oracle"
    workflow = (REPO / "modules/agent-content-packs/scripts/agent-content-workflow.sh").read_text()
    assert "srv4-hermes-default" in workflow
    assert "srv4-codex-default" in workflow


def test_oci_bootstrap_documents_safe_http_and_compose_contracts() -> None:
    skill = (
        REPO
        / "modules/agent-content-packs/packs/codex-skills/items"
        / "oci-arm64-new-server-bootstrap/SKILL.md"
    ).read_text()

    assert "Never pipe a long HTTP body from `curl` into `head`" in skill
    assert "`curl -o <temporary-file>`" in skill
    assert "`~/.local/bin/podman-compose`" in skill
    assert "`podman-compose==1.6.0`" in skill
    assert "`PYTHONNOUSERSITE=1 /usr/bin/podman-compose --version`" in skill
