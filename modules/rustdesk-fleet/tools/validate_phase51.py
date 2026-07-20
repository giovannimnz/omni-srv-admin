#!/usr/bin/env python3
"""Fail-closed Phase 51 RustDesk contract validator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    category: str
    path: str
    location: str


@dataclass
class CheckResult:
    id: str
    status: str
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


def load_json_strict(path: Path) -> Any:
    raise NotImplementedError("strict JSON loading is not implemented")


def validate_repo_path(repo: Path, candidate: Path) -> Path:
    raise NotImplementedError("repository path validation is not implemented")


def validate_scope(payload: dict[str, Any], source: str = "scope.json") -> list[CheckResult]:
    raise NotImplementedError("scope contract validation is not implemented")

