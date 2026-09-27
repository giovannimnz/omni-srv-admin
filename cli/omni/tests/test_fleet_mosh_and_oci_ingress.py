"""Tests for Mosh Port Range Governance (60001-60999/udp) and OCI Ingress / Domain Parity.

Verifies:
- All inventory host YAMLs declare mosh with port range '60001-60999/udp'.
- iptables-backup-v4.conf contains the canonical rule for UDP 60001:60999.
- docs/network/mosh-port-governance.md accurately reflects fleet state.
- Dual domain parity between oci.atius.com.br and oci.atius.io.
"""

from __future__ import annotations

from pathlib import Path
import yaml
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INVENTORY_HOSTS_DIR = REPO_ROOT / "inventory" / "hosts"
IPTABLES_BACKUP_FILE = REPO_ROOT / "iptables" / "iptables-backup-v4.conf"
MOSH_DOC_FILE = REPO_ROOT / "docs" / "network" / "mosh-port-governance.md"
OCI_ADMIN_DEPLOY_DIR = REPO_ROOT.parent / "oci-admin" / "deploy" / "apache"

MANAGED_HOSTS = [
    "atius-srv-1.yaml",
    "atius-srv-2.yaml",
    "atius-srv-3.yaml",
    "atius-srv-4.yaml",
    "horistic-srv.yaml",
]


def test_inventory_hosts_declare_mosh_port_range() -> None:
    for host_file in MANAGED_HOSTS:
        path = INVENTORY_HOSTS_DIR / host_file
        assert path.exists(), f"Inventory file {host_file} missing"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        apps = data.get("apps", [])
        mosh_app = next((app for app in apps if app.get("id") == "mosh"), None)
        assert mosh_app is not None, f"Host {host_file} does not declare app 'mosh'"
        assert mosh_app.get("port_range") == "60001-60999/udp", (
            f"Host {host_file} mosh port_range is {mosh_app.get('port_range')}, expected 60001-60999/udp"
        )


def test_iptables_backup_declares_mosh_udp_range() -> None:
    assert IPTABLES_BACKUP_FILE.exists(), "iptables-backup-v4.conf missing"
    content = IPTABLES_BACKUP_FILE.read_text(encoding="utf-8")
    assert "--dport 60001:60999" in content
    assert "MOSH_SERVER_UDP_RANGE" in content


def test_mosh_governance_doc_exists_and_accurate() -> None:
    assert MOSH_DOC_FILE.exists(), "docs/network/mosh-port-governance.md missing"
    content = MOSH_DOC_FILE.read_text(encoding="utf-8")
    assert "60001 a 60999" in content
    assert "atius-srv-1" in content
    assert "atius-srv-2" in content
    assert "atius-srv-3" in content
    assert "atius-srv-4" in content
    assert "horistic-srv" in content


def test_oci_admin_dual_domain_parity() -> None:
    com_br_conf = OCI_ADMIN_DEPLOY_DIR / "oci.atius.com.br.conf"
    io_conf = OCI_ADMIN_DEPLOY_DIR / "oci.atius.io.conf"

    assert com_br_conf.exists(), "oci.atius.com.br.conf missing"
    assert io_conf.exists(), "oci.atius.io.conf missing"

    content_br = com_br_conf.read_text(encoding="utf-8")
    content_io = io_conf.read_text(encoding="utf-8")

    assert "ServerName oci.atius.com.br" in content_br
    assert "ServerName oci.atius.io" in content_io

    # Both must proxy /sso and / to identical targets
    assert "ProxyPass /sso http://127.0.0.1:3015/sso" in content_br
    assert "ProxyPass /sso http://127.0.0.1:3015/sso" in content_io
    assert "ProxyPass / http://10.13.1.13:8080/" in content_br
    assert "ProxyPass / http://10.13.1.13:8080/" in content_io
