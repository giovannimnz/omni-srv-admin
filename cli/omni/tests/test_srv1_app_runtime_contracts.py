"""Contracts for recovered SRV-1 Podman applications."""

from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[3]
APPS = REPO / "modules" / "srv1-ops" / "apps"
INVENTORY = yaml.safe_load((REPO / "inventory" / "hosts" / "atius-srv-1.yaml").read_text())


def _app(app_id: str) -> dict:
    return next(item for item in INVENTORY["apps"] if item["id"] == app_id)


def test_recovered_app_sources_exist_and_match_inventory() -> None:
    for app_id in ("cloudbeaver", "jenkins", "plane"):
        app = _app(app_id)
        assert (REPO / app["source_unit"]).is_file()
        assert (REPO / app["source_compose"]).is_file()

    rustdesk = _app("rustdesk-server")
    source_root = REPO / rustdesk["source_root"]
    for name in (
        "atius-rustdesk-server-hbbs.container",
        "atius-rustdesk-server-hbbr.container",
        "atius-rustdesk-phase53.slice",
        "ensure-rustdesk-runtime.py",
        "10-runtime-preflight.conf",
        "atius-rustdesk-edge.nft",
        "atius-rustdesk-edge.service",
        "atius-rustdesk-edge-guard.service",
        "atius-rustdesk-edge-guard.timer",
    ):
        assert (source_root / name).is_file()


def test_jenkins_uses_official_image_and_canonical_atius_repo() -> None:
    app = _app("jenkins")
    unit = (REPO / app["source_unit"]).read_text()
    compose = (REPO / app["source_compose"]).read_text()

    assert app["image"] == "docker.io/jenkins/jenkins:2.541.3-jdk17"
    assert "localhost/jenkins:podman-latest" not in unit + compose
    assert "/home/ubuntu/GitHub/Atius-Capital/ats:/workspace/atius:ro" in unit + compose
    assert "/home/ubuntu/GitHub/atius:/workspace/atius" not in unit + compose


def test_cloudbeaver_is_version_pinned_and_uses_db_domain() -> None:
    app = _app("cloudbeaver")
    source = (REPO / app["source_unit"]).read_text() + (REPO / app["source_compose"]).read_text()

    assert app["image"] == "docker.io/dbeaver/cloudbeaver:26.1.0"
    assert app["public_url"] == "https://db.atius.com.br/"
    assert "localhost/cloudbeaver:podman-latest" not in source


def test_plane_healthcheck_fails_on_connection_refusal() -> None:
    app = _app("plane")
    compose = yaml.safe_load((REPO / app["source_compose"]).read_text())
    command = compose["services"]["space"]["healthcheck"]["test"][1]

    assert "grep -Eq" in command
    assert "|| exit 0" not in command
    assert app["notes"][1].startswith("Plane volumes use plane-app_*")


def test_rustdesk_inventory_matches_public_and_private_contract() -> None:
    app = _app("rustdesk-server")
    assert app["pinned_tag"] == "localhost/atius-rustdesk-server:1.1.15-pinned"
    assert app["public_ports"] == [
        "34100/tcp -> 21115/tcp",
        "34125/tcp+udp -> 21116/tcp+udp",
        "34126/tcp -> 21117/tcp",
    ]
    assert app["public_native_ports_state"] == "blocked"
    assert app["identity_medium"] == "tmpfs"


def test_runtime_contract_tree_contains_no_secret_files() -> None:
    forbidden = {
        ".env",
        "auth.json",
        "state.db",
        "credentials.xml",
        "id_ed25519",
        "id_ed25519.pub",
        "db_v2.sqlite3",
    }
    assert not [path for path in APPS.rglob("*") if path.is_file() and path.name in forbidden]
