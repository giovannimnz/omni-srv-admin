from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).parents[1]
    / "tools"
    / "validate-phase53-dirty-baseline.py"
)
SPEC = importlib.util.spec_from_file_location("phase53_dirty_baseline", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def git(repo: Path, *args: str, input_bytes: bytes | None = None) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return completed.stdout.decode("utf-8").strip()


def run_cli(
    repo: Path,
    command: str,
    baseline: Path,
    *extra: str,
    expected: int = 0,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            command,
            "--repo",
            str(repo),
            "--baseline",
            str(baseline),
            *extra,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == expected
    assert completed.stdout == b""
    assert completed.stderr == b""
    return completed


def write(repo: Path, relative: str, content: str, mode: int = 0o600) -> Path:
    target = repo / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    target.chmod(mode)
    return target


@pytest.fixture
def prepared(tmp_path: Path) -> dict[str, object]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Phase 53 Test")
    git(repo, "config", "user.email", "phase53@example.invalid")
    for index, relative in enumerate(VALIDATOR.CAPTURED_PATHS):
        if relative.endswith("build-phase53-authority-plan.py"):
            continue
        mode = 0o755 if relative.endswith("run-phase53-live-gate.py") else 0o600
        write(repo, relative, f"tracked-base-{index}\n", mode)
    git(repo, "add", "--", *[
        path
        for path in VALIDATOR.CAPTURED_PATHS
        if not path.endswith("build-phase53-authority-plan.py")
    ])
    git(repo, "commit", "-q", "-m", "baseline H")
    h = git(repo, "rev-parse", "HEAD")
    for index, relative in enumerate(VALIDATOR.CAPTURED_PATHS):
        mode = 0o755 if relative.endswith("run-phase53-live-gate.py") else 0o600
        write(repo, relative, f"dirty-{index}\n", mode)
    baseline = repo / next(iter(sorted(VALIDATOR.SOURCE_PATHS)))
    baseline.parent.mkdir(parents=True, exist_ok=True)
    return {"repo": repo, "baseline": baseline, "h": h}


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def rewrite_with_digest(path: Path, payload: dict[str, object]) -> None:
    payload["baseline_sha256"] = VALIDATOR._baseline_digest(payload)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def capture(prepared: dict[str, object]) -> dict[str, object]:
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    run_cli(repo, "capture", baseline)
    assert stat.S_IMODE(baseline.stat().st_mode) == 0o600
    return load(baseline)


def commit_source(
    prepared: dict[str, object], *, extra_path: str | None = None
) -> str:
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    write(
        repo,
        "modules/rustdesk-fleet/tools/validate-phase53-dirty-baseline.py",
        "validator\n",
    )
    write(
        repo,
        "modules/rustdesk-fleet/tests/test_phase53_dirty_baseline.py",
        "tests\n",
    )
    paths = sorted(VALIDATOR.SOURCE_PATHS)
    if extra_path:
        write(repo, extra_path, "extra\n")
        paths.append(extra_path)
    git(repo, "add", "--", *paths)
    git(repo, "commit", "-q", "-m", "source S")
    return git(repo, "rev-parse", "HEAD")


def commit_summary(
    prepared: dict[str, object], source: str, *, extra: bool = False
) -> str:
    repo = prepared["repo"]
    assert isinstance(repo, Path)
    assert git(repo, "rev-parse", "HEAD") == source
    write(repo, VALIDATOR.SUMMARY_PATH, "summary\n")
    paths = [VALIDATOR.SUMMARY_PATH]
    if extra:
        write(repo, "summary-extra.txt", "extra\n")
        paths.append("summary-extra.txt")
    git(repo, "add", "--", *paths)
    git(repo, "commit", "-q", "-m", "summary C")
    return git(repo, "rev-parse", "HEAD")


def test_capture_exact_and_legal_h_s_c_chain(prepared: dict[str, object]) -> None:
    payload = capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    h = prepared["h"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    assert payload["captured_head"] == h
    assert payload["path_count"] == len(VALIDATOR.CAPTURED_PATHS)
    entries = {entry["path"]: entry for entry in payload["paths"]}
    assert set(entries) == set(VALIDATOR.CAPTURED_PATHS)
    assert entries[
        "modules/rustdesk-fleet/tools/build-phase53-authority-plan.py"
    ]["tracked"] is False
    assert entries[
        "modules/rustdesk-fleet/tools/build-phase53-authority-plan.py"
    ]["xy"] == "??"
    for path, entry in entries.items():
        if path.endswith("build-phase53-authority-plan.py"):
            continue
        assert entry["tracked"] is True
        assert entry["xy"] == " M"
    run_cli(repo, "exact", baseline)
    source = commit_source(prepared)
    run_cli(
        repo,
        "ancestor",
        baseline,
        "--source-commit",
        source,
    )
    child = commit_summary(prepared, source)
    run_cli(
        repo,
        "ancestor",
        baseline,
        "--source-commit",
        source,
        "--summary-commit",
        child,
        "--summary-path",
        VALIDATOR.SUMMARY_PATH,
    )


def test_capture_is_create_only(prepared: dict[str, object]) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    before = baseline.read_bytes()
    run_cli(repo, "capture", baseline, expected=1)
    assert baseline.read_bytes() == before


@pytest.mark.parametrize("kind", ["content", "mode", "status"])
def test_exact_rejects_dirty_tuple_drift(
    prepared: dict[str, object], kind: str
) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    path = repo / VALIDATOR.CAPTURED_PATHS[0]
    if kind == "content":
        path.write_text("changed-content\n", encoding="utf-8")
    elif kind == "mode":
        path.chmod(0o644)
    else:
        git(repo, "add", "--", VALIDATOR.CAPTURED_PATHS[0])
    run_cli(repo, "exact", baseline, expected=1)


@pytest.mark.parametrize("kind", ["symlink", "directory"])
def test_rejects_non_regular_or_symlink(
    prepared: dict[str, object], kind: str
) -> None:
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    path = repo / VALIDATOR.CAPTURED_PATHS[0]
    path.unlink()
    if kind == "symlink":
        path.symlink_to(repo / VALIDATOR.CAPTURED_PATHS[1])
    else:
        path.mkdir()
    run_cli(repo, "capture", baseline, expected=1)


def test_two_pass_toctou_mismatch_fails(
    prepared: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = prepared["repo"]
    assert isinstance(repo, Path)
    first = VALIDATOR._observe_pass(repo)
    second = json.loads(json.dumps(first))
    second["paths"][0]["size"] += 1
    observations = iter([first, second])
    monkeypatch.setattr(VALIDATOR, "_observe_pass", lambda _repo: next(observations))
    with pytest.raises(VALIDATOR.ValidationError):
        VALIDATOR._stable_observation(repo)


def test_duplicate_json_key_rejected(prepared: dict[str, object]) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    raw = baseline.read_text(encoding="utf-8")
    baseline.write_text(raw.replace("{", '{"schema_version": 1,', 1), encoding="utf-8")
    run_cli(repo, "exact", baseline, expected=1)


@pytest.mark.parametrize(
    "mutation",
    ["unknown", "missing", "extra_path", "duplicate_path", "timestamp", "digest"],
)
def test_closed_schema_and_digest_rejected(
    prepared: dict[str, object], mutation: str
) -> None:
    payload = capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    if mutation == "unknown":
        payload["stdout"] = "forbidden"
    elif mutation == "missing":
        del payload["path_count"]
    elif mutation == "extra_path":
        extra = dict(payload["paths"][0])
        extra["path"] = "extra"
        payload["paths"].append(extra)
        payload["path_count"] = len(payload["paths"])
    elif mutation == "duplicate_path":
        payload["paths"][-1] = dict(payload["paths"][0])
    elif mutation == "timestamp":
        payload["captured_at"] = "2026-07-27 00:00:00"
    else:
        payload["baseline_sha256"] = "0" * 64
    if mutation != "digest":
        rewrite_with_digest(baseline, payload)
    else:
        baseline.write_text(json.dumps(payload), encoding="utf-8")
    run_cli(repo, "exact", baseline, expected=1)


def test_exact_forbidden_after_source_exists(prepared: dict[str, object]) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    h = prepared["h"]
    assert isinstance(repo, Path) and isinstance(baseline, Path) and isinstance(h, str)
    source = commit_source(prepared)
    baseline_bytes = git(repo, "show", f"{source}:{baseline.relative_to(repo)}")
    git(repo, "tag", "keep-source", source)
    git(repo, "reset", "--hard", "-q", h)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(baseline_bytes + "\n", encoding="utf-8")
    run_cli(repo, "exact", baseline, expected=1)


def test_ancestor_rejects_stale_source_ancestry(
    prepared: dict[str, object]
) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    h = prepared["h"]
    assert isinstance(repo, Path) and isinstance(baseline, Path) and isinstance(h, str)
    source = commit_source(prepared)
    baseline_bytes = baseline.read_bytes()
    git(repo, "tag", "keep-source", source)
    git(repo, "checkout", "-q", "-b", "other", h)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_bytes(baseline_bytes)
    run_cli(
        repo,
        "ancestor",
        baseline,
        "--source-commit",
        source,
        expected=1,
    )


def test_ancestor_rejects_wrong_source_parent(
    prepared: dict[str, object]
) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    git(repo, "commit", "--allow-empty", "-q", "-m", "intervening")
    source = commit_source(prepared)
    run_cli(
        repo,
        "ancestor",
        baseline,
        "--source-commit",
        source,
        expected=1,
    )


def test_ancestor_rejects_merge_source(prepared: dict[str, object]) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    h = prepared["h"]
    assert isinstance(repo, Path) and isinstance(baseline, Path) and isinstance(h, str)
    git(repo, "checkout", "-q", "-b", "side", h)
    git(repo, "commit", "--allow-empty", "-q", "-m", "side")
    side = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "-b", "source", h)
    source = commit_source(prepared)
    tree = git(repo, "rev-parse", f"{source}^{{tree}}")
    merge = git(
        repo,
        "commit-tree",
        tree,
        "-p",
        h,
        "-p",
        side,
        "-m",
        "merge source",
    )
    git(repo, "reset", "--hard", "-q", merge)
    run_cli(
        repo,
        "ancestor",
        baseline,
        "--source-commit",
        merge,
        expected=1,
    )


def test_ancestor_rejects_extra_source_diff(prepared: dict[str, object]) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    source = commit_source(prepared, extra_path="extra-source.txt")
    run_cli(
        repo,
        "ancestor",
        baseline,
        "--source-commit",
        source,
        expected=1,
    )


@pytest.mark.parametrize("missing", ["commit", "path"])
def test_ancestor_rejects_unpaired_summary_args(
    prepared: dict[str, object], missing: str
) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    source = commit_source(prepared)
    extra = ["--summary-path", VALIDATOR.SUMMARY_PATH]
    if missing == "path":
        extra = ["--summary-commit", source]
    run_cli(
        repo,
        "ancestor",
        baseline,
        "--source-commit",
        source,
        *extra,
        expected=1,
    )


def test_ancestor_rejects_extra_summary_diff(
    prepared: dict[str, object]
) -> None:
    capture(prepared)
    repo = prepared["repo"]
    baseline = prepared["baseline"]
    assert isinstance(repo, Path) and isinstance(baseline, Path)
    source = commit_source(prepared)
    child = commit_summary(prepared, source, extra=True)
    run_cli(
        repo,
        "ancestor",
        baseline,
        "--source-commit",
        source,
        "--summary-commit",
        child,
        "--summary-path",
        VALIDATOR.SUMMARY_PATH,
        expected=1,
    )
