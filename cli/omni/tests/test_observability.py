"""Tests for the OMNI observability module (Phase 17 / M005).

Run with: ``pytest cli/omni/tests/test_observability.py`` from the repo root.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omni import observability  # noqa: E402


# ── File-based validation ───────────────────────────────────────────


def test_validate_files_clean(monkeypatch) -> None:
    """The on-disk observability artifacts are present and well-formed."""
    problems = observability.validate_files_only()
    assert problems == [], f"unexpected problems: {problems}"


def test_validate_detects_missing_yaml(tmp_path, monkeypatch) -> None:
    """When the values file is missing, validate should report it."""
    # Point REPO at a tmp dir so the validate walk finds nothing.
    monkeypatch.setattr(observability, "REPO", tmp_path)
    monkeypatch.setattr(observability, "MONITORING_DIR", tmp_path / "monitoring")
    problems = observability.validate_files_only()
    assert any("missing" in p for p in problems)


def test_validate_detects_invalid_json(tmp_path, monkeypatch) -> None:
    """A malformed JSON dashboard should be flagged."""
    monkeypatch.setattr(observability, "REPO", tmp_path)
    monitoring = tmp_path / "monitoring"
    monitoring.mkdir()
    # minimal structure so the other checks pass
    (monitoring / "loki").mkdir()
    (monitoring / "loki" / "values.yaml").write_text("loki: {}\n")
    (monitoring / "alertmanager").mkdir()
    (monitoring / "alertmanager" / "values.yaml").write_text("alertmanager: {}\n")
    (monitoring / "prometheus-rules").mkdir()
    (monitoring / "prometheus-rules" / "x.yaml").write_text("kind: ConfigMap\n")
    (monitoring / "dashboards").mkdir()
    bad = monitoring / "dashboards" / "bad.json"
    bad.write_text("{not json")
    (monitoring / "scripts").mkdir()
    (monitoring / "scripts" / "ok.sh").write_text("#!/bin/sh\n")
    (monitoring / "scripts" / "ok.sh").chmod(0o755)
    monkeypatch.setattr(observability, "MONITORING_DIR", monitoring)
    # also point at the missing kube-prometheus values
    problems = observability.validate_files_only()
    # the bad.json is flagged
    assert any(p.startswith("bad.json:") for p in problems), problems


def test_validate_detects_missing_title_in_dashboard(tmp_path, monkeypatch) -> None:
    """A dashboard JSON without 'title' or 'uid' is flagged."""
    monkeypatch.setattr(observability, "REPO", tmp_path)
    monitoring = tmp_path / "monitoring"
    monitoring.mkdir()
    (monitoring / "loki").mkdir()
    (monitoring / "loki" / "values.yaml").write_text("loki: {}\n")
    (monitoring / "alertmanager").mkdir()
    (monitoring / "alertmanager" / "values.yaml").write_text("alertmanager: {}\n")
    (monitoring / "prometheus-rules").mkdir()
    (monitoring / "prometheus-rules" / "x.yaml").write_text("kind: ConfigMap\n")
    (monitoring / "dashboards").mkdir()
    bad = monitoring / "dashboards" / "no-title.json"
    bad.write_text(json.dumps({"panels": []}))
    (monitoring / "scripts").mkdir()
    (monitoring / "scripts" / "ok.sh").write_text("#!/bin/sh\n")
    (monitoring / "scripts" / "ok.sh").chmod(0o755)
    monkeypatch.setattr(observability, "MONITORING_DIR", monitoring)
    problems = observability.validate_files_only()
    assert any("no-title.json" in p and "missing 'title'" in p for p in problems), problems


def test_validate_detects_non_executable_script(tmp_path, monkeypatch) -> None:
    """A script without the executable bit is flagged."""
    monkeypatch.setattr(observability, "REPO", tmp_path)
    monitoring = tmp_path / "monitoring"
    monitoring.mkdir()
    (monitoring / "loki").mkdir()
    (monitoring / "loki" / "values.yaml").write_text("loki: {}\n")
    (monitoring / "alertmanager").mkdir()
    (monitoring / "alertmanager" / "values.yaml").write_text("alertmanager: {}\n")
    (monitoring / "prometheus-rules").mkdir()
    (monitoring / "prometheus-rules" / "x.yaml").write_text("kind: ConfigMap\n")
    (monitoring / "dashboards").mkdir()
    (monitoring / "scripts").mkdir()
    nox = monitoring / "scripts" / "no-exec.sh"
    nox.write_text("#!/bin/sh\n")
    nox.chmod(0o644)
    monkeypatch.setattr(observability, "MONITORING_DIR", monitoring)
    problems = observability.validate_files_only()
    assert any("no-exec.sh" in p and "not executable" in p for p in problems), problems


# ── Click surface ───────────────────────────────────────────────────


def test_observability_status_unreachable(monkeypatch) -> None:
    """`status` exits non-zero with a red k3s row when the cluster is down."""
    monkeypatch.setattr(observability, "k3s_available", lambda: False)
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(observability.observability, ["status"])
    assert result.exit_code != 0
    assert "k3s" in result.output


def test_observability_validate_clean(monkeypatch) -> None:
    """`validate` exits 0 when no problems are found."""
    monkeypatch.setattr(observability, "validate_files_only", lambda: [])
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(observability.observability, ["validate"])
    assert result.exit_code == 0, result.output
    assert "all observability artifacts present" in result.output


def test_observability_validate_dirty(monkeypatch) -> None:
    """`validate` exits 1 and lists problems when dirty."""
    monkeypatch.setattr(observability, "validate_files_only", lambda: ["fake problem"])
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(observability.observability, ["validate"])
    assert result.exit_code == 1
    assert "fake problem" in result.output


def test_observability_dry_run_renders_helm(monkeypatch) -> None:
    """`dry-run` should print helm/kubectl commands including the values file paths."""
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(observability.observability, ["dry-run"])
    assert result.exit_code == 0, result.output
    assert "helm install omni-monitoring" in result.output
    assert "helm install omni-loki" in result.output
    assert "kube-prometheus-stack-values.yaml" in result.output


def test_observability_config_prints_paths() -> None:
    """`config` should print the module's runtime configuration."""
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(observability.observability, ["config"])
    assert result.exit_code == 0, result.output
    assert "REPO:" in result.output
    assert "KPS_NAMESPACE:        monitoring" in result.output
    assert "PROMETHEUS_PORT:" in result.output


# ── Pod classification ──────────────────────────────────────────────


def test_classify_pod_health_green() -> None:
    pods = [{"status": {"phase": "Running"}} for _ in range(3)]
    status, summary = observability._classify_pod_health(pods)
    assert status == "green"
    assert "3/3 running" in summary


def test_classify_pod_health_yellow() -> None:
    pods = [
        {"status": {"phase": "Running"}},
        {"status": {"phase": "Pending"}},
    ]
    status, summary = observability._classify_pod_health(pods)
    assert status == "yellow"
    assert "1/2 running" in summary
    assert "1 pending" in summary


def test_classify_pod_health_red() -> None:
    pods = [
        {"status": {"phase": "Running"}},
        {"status": {"phase": "CrashLoopBackOff"}},
    ]
    status, summary = observability._classify_pod_health(pods)
    assert status == "red"
    assert "1 failed" in summary


def test_classify_pod_health_empty() -> None:
    status, summary = observability._classify_pod_health([])
    assert status == "red"
    assert "no pods" in summary


# ── K3s + namespace check is properly isolated ──────────────────────


def test_k3s_available_short_circuits(monkeypatch) -> None:
    """When sudo isn't available, k3s_available returns False without crashing."""
    monkeypatch.setattr(observability, "_which_sudo", lambda: None)
    assert observability.k3s_available() is False
