from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "reconcile-codex-agents-policy.py"
SPEC = importlib.util.spec_from_file_location("codex_agents_policy", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_reconcile_appends_once_and_is_idempotent() -> None:
    original = b"# Project instructions\n"
    first, changed = MODULE.reconcile_bytes(original)
    second, changed_again = MODULE.reconcile_bytes(first)

    assert changed is True
    assert changed_again is False
    assert second == first
    assert first.count(MODULE.START) == 1
    assert first.count(MODULE.END) == 1


def test_reconcile_replaces_existing_block_and_preserves_surroundings() -> None:
    original = b"before\n" + MODULE.START + b"\nold\n" + MODULE.END + b"\nafter\n"
    updated, changed = MODULE.reconcile_bytes(original)

    assert changed is True
    assert updated.startswith(b"before\n")
    assert updated.endswith(b"\nafter\n")
    assert b"old" not in updated
    assert updated.count(MODULE.START) == 1


def test_reconcile_rejects_incomplete_or_duplicate_markers() -> None:
    for content in (
        MODULE.START + b"\n",
        MODULE.END + b"\n",
        MODULE.START + b"\n" + MODULE.START + b"\n" + MODULE.END,
    ):
        try:
            MODULE.reconcile_bytes(content)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid markers must fail closed")


def test_discover_skips_dependencies_and_symlinks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    dependency = project / "node_modules" / "pkg"
    project.mkdir()
    dependency.mkdir(parents=True)
    (project / "AGENTS.md").write_text("project", encoding="utf-8")
    (dependency / "AGENTS.md").write_text("dependency", encoding="utf-8")
    (project / "linked.md").symlink_to(project / "AGENTS.md")

    found = MODULE.discover(None, [tmp_path])

    assert found == [(project / "AGENTS.md").resolve()]
