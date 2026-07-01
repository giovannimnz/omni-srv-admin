"""Desired-state profile helpers for Omni Fleet governance."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_MANAGED_APPS_SOURCE = Path("modules/managed-apps/configs/programs.json")


def load_managed_apps_profile(source: Path = DEFAULT_MANAGED_APPS_SOURCE) -> dict[str, Any]:
    data = json.loads(source.read_text())
    rules: list[dict[str, Any]] = []
    for name, spec in sorted((data.get("programs") or {}).items()):
        if not isinstance(spec, dict):
            continue
        rules.append(
            {
                "target_kind": "program",
                "target_name": name,
                "rule_mode": "required",
                "desired_version": spec.get("desired_version"),
                "manager": spec.get("kind", "program"),
                "source": spec.get("desired_source_contains") or spec.get("policy_file") or "managed-apps",
                "selector": {
                    "packages": spec.get("packages", []),
                    "primary_package": spec.get("primary_package"),
                    "forbidden_package_managers": spec.get("forbidden_package_managers", []),
                },
                "assertions": {
                    "required_wrapper": spec.get("required_wrapper"),
                    "required_wrapper_flags": spec.get("required_wrapper_flags", []),
                    "post_fix_script": spec.get("post_fix_script"),
                    "post_fix_app": spec.get("post_fix_app"),
                },
                "metadata": {"notes": spec.get("notes", [])},
            }
        )
    for group_name, group in (
        ("repository", data.get("repositories") or {}),
        ("policy", data.get("policies") or {}),
        ("customization", data.get("customizations") or {}),
    ):
        for name, spec in sorted(group.items()):
            if not isinstance(spec, dict):
                continue
            rules.append(
                {
                    "target_kind": group_name,
                    "target_name": name,
                    "rule_mode": "required",
                    "desired_version": None,
                    "manager": spec.get("kind", group_name),
                    "source": spec.get("path") or spec.get("expected_source_contains") or spec.get("source") or "managed-apps",
                    "selector": {
                        "packages": spec.get("packages", []),
                        "path": spec.get("path"),
                    },
                    "assertions": {
                        "must_include": spec.get("must_include"),
                        "required_contains": spec.get("required_contains", []),
                        "forbidden_contains": spec.get("forbidden_contains", []),
                    },
                    "metadata": {"notes": spec.get("notes", [])},
                }
            )
    return {
        "profile_id": "managed-apps-arm64-desktop",
        "title": "Managed ARM64 desktop/browser apps",
        "scope": "fleet",
        "owner": "omni-srv-admin",
        "status": "active",
        "source": str(source),
        "target_hosts": data.get("target_hosts", []),
        "rule_count": len(rules),
        "rules": rules,
        "metadata": {
            "schema_version": data.get("schema_version"),
            "updated_at": data.get("updated_at"),
            "description": data.get("description"),
        },
    }

