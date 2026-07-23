"""Deterministic compatibility fixtures for immutable Phase 52 evidence tests."""

from __future__ import annotations

from datetime import datetime, timezone
import sys
from typing import Iterator

import pytest


_PHASE52_STATIC_REPORT_TESTS = frozenset(
    {
        "test_report_builds_exact_pass_check_set_from_current_horistic_primary",
        "test_report_rejects_duplicate_stale_self_hash_secret_and_stored_verdict_drift",
        "test_report_outputs_are_atomic_parity_and_topology_is_ready",
        "test_pass_report_promotes_exact_phase52_ledger_rows",
    }
)
_PHASE52_REPORT_CURRENT_AT = datetime(2026, 7, 22, 22, 16, 34, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _pin_immutable_phase52_report_observation_window(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Keep static report semantics independent from expiry of committed live samples."""
    if request.node.name not in _PHASE52_STATIC_REPORT_TESTS:
        yield
        return

    validator = sys.modules.get("validate_phase52")
    if validator is None:
        raise RuntimeError("validate_phase52 test module is not loaded")
    original = validator._is_current

    def is_current_at_gate(timestamp: object, max_age: int, now: datetime | None = None) -> bool:
        del now
        return original(timestamp, max_age, _PHASE52_REPORT_CURRENT_AT)

    monkeypatch.setattr(validator, "_is_current", is_current_at_gate)
    yield
