from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def test_m007_schema_contains_managed_registry_tables() -> None:
    schema = (REPO / "modules/fleet-control-plane/migrations/0007_customization_registry.sql").read_text()

    for table in ("TbManagedApps", "TbManagedForks", "TbCustomizationPolicies"):
        assert f'CREATE TABLE IF NOT EXISTS "{table}"' in schema

    for constraint in (
        "UqTbManagedAppsHostApp",
        "UqTbManagedForksHostFork",
        "UqTbCustomizationPoliciesHostScope",
        "UqTbCustomizationPoliciesGlobalScope",
        "CkTbCustomizationPoliciesScopeType",
        "CkTbCustomizationPoliciesLane",
        "CkTbCustomizationPoliciesPolicyType",
    ):
        assert constraint in schema

    assert "/omni-customizations" in schema
    assert "target_program" in schema
    assert "target_path" in schema
    assert "invocation" in schema


def test_srv1_inventory_models_router_as_canonical_product() -> None:
    text = (REPO / "inventory/hosts/atius-srv-1.yaml").read_text()

    assert "canonical_product_id: router-ai-atius" in text
    assert "sync_project: atius-router" in text
    assert "runtime_app_id: router-ai-atius" in text
    assert "components:" in text
    assert "id: atius-router-docs" in text


def test_fleet_registry_code_uses_live_policy_constraint_names() -> None:
    text = (REPO / "cli/omni/fleet.py").read_text()

    assert "UqTbCustomizationPoliciesScope" not in text
    assert "inventory.host.profile" in text
