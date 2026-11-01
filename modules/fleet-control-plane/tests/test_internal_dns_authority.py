from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "modules/fleet-control-plane/scripts/reconcile-internal-dns-authority.py"
FIXTURES_PATH = REPO_ROOT / "modules/fleet-control-plane/tests/fixtures/internal-dns-authority.json"
CONFIG_PATH = REPO_ROOT / "modules/fleet-control-plane/configs/internal-dns-authority.yaml"

spec = importlib.util.spec_from_file_location("reconcile_internal_dns_authority", SCRIPT_PATH)
assert spec and spec.loader
reconciler = importlib.util.module_from_spec(spec)
sys.modules["reconcile_internal_dns_authority"] = reconciler
spec.loader.exec_module(reconciler)

AuthorityConfig = reconciler.AuthorityConfig
HostIdentity = reconciler.HostIdentity
ReleaseGate = reconciler.ReleaseGate


def test_schema_loads_canonical_inventory_hosts_and_exact_zones():
    cfg = AuthorityConfig.load(CONFIG_PATH)
    assert cfg.domain == "atius.internal"
    assert len(cfg.forward_zones) == 1
    assert "atius.internal" in cfg.forward_zones
    assert len(cfg.reverse_zones) == 4
    assert "1.11.10.in-addr.arpa" in cfg.reverse_zones
    assert "1.12.10.in-addr.arpa" in cfg.reverse_zones
    assert "1.13.10.in-addr.arpa" in cfg.reverse_zones
    assert "1.21.10.in-addr.arpa" in cfg.reverse_zones

    host_map = {h.id: h.ip for h in cfg.hosts}
    assert host_map["atius-srv-1"] == "10.11.1.11"
    assert host_map["atius-srv-2"] == "10.12.1.12"
    assert host_map["atius-srv-3"] == "10.13.1.13"
    assert host_map["horistic-srv"] == "10.21.1.21"


def test_prohibits_invalid_zero_subnet_and_legacy_paths():
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    forbidden = fixtures["forbidden_hosts_sample"]
    cfg = AuthorityConfig.load(CONFIG_PATH)

    for item in forbidden:
        h = HostIdentity(id=item["id"], fqdn=item["fqdn"], ip=item["ip"], owner=item["owner"])
        with pytest.raises(ValueError, match="Prohibited IP pattern matched"):
            h.validate(list(cfg.forbidden_ip_patterns))


def test_release_gate_evaluates_exact_ida_requirements_and_phase_48():
    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    gate_data = fixtures["valid_release_gate"]
    gate = ReleaseGate(**gate_data)
    assert gate.evaluate() is True

    # Tampered gate with failed requirement must fail closed
    tampered_data = dict(gate_data)
    tampered_data["ida_requirements"] = dict(gate_data["ida_requirements"])
    tampered_data["ida_requirements"]["IDA-05"] = "FAIL"
    assert ReleaseGate(**tampered_data).evaluate() is False


def test_cli_help_and_compile():
    with pytest.raises(SystemExit) as exc:
        reconciler.main(["--help"])
    assert exc.value.code == 0

    assert reconciler.main(["plan", "--layer", "endpoint", "--target", "atius-srv-3"]) == 0
    assert reconciler.main(["verify", "--layer", "preflight"]) == 0
    assert reconciler.main([]) == 0
