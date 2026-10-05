"""CloudBeaver inventory contract for the SRV-1 Podman runtime."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[3]
INVENTORY = REPO / "inventory/hosts/atius-srv-1.yaml"
CLOUDFLARE_DOC = REPO / "docs/CLOUDFLARE.md"
PORT_MAP = REPO / "docs/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md"
ANALYZER = REPO / "modules/srv1-ops/scripts/server-analysis.py"
CANONICAL_UNIT = REPO / "modules/srv1-ops/systemd/container-cloudbeaver.service"
CANONICAL_COMPOSE = REPO / "modules/srv1-ops/configs/cloudbeaver-podman-compose.yml"
HEALTHCHECK = REPO / "modules/srv1-ops/scripts/cloudbeaver-healthcheck.sh"
HEALTHCHECK_UNIT = REPO / "modules/srv1-ops/systemd/cloudbeaver-healthcheck.service"
HEALTHCHECK_TIMER = REPO / "modules/srv1-ops/systemd/cloudbeaver-healthcheck.timer"


def _cloudbeaver() -> dict:
    host = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    rows = [app for app in host["apps"] if app.get("id") == "cloudbeaver"]
    assert len(rows) == 1
    return rows[0]


def test_cloudbeaver_inventory_matches_canonical_srv1_runtime() -> None:
    app = _cloudbeaver()

    assert app["runtime"] == "podman"
    assert app["install_type"] == "systemd-user-podman-container"
    assert app["unit"] == "container-cloudbeaver.service"
    assert app["image"] == "docker.io/dbeaver/cloudbeaver:26.1.0"
    assert app["compose"] == "~/GitHub/containers/cloudbeaver/podman-compose.yml"
    assert app["public_url"] == "https://db.atius.com.br/"
    assert app["healthcheck_url"] == "http://127.0.0.1:8978/status"
    assert app["ports"] == ["127.0.0.1:8978:8978"]
    assert app["volumes"] == [
        "~/GitHub/containers/cloudbeaver/workspace_recent:/opt/cloudbeaver/workspace:rw"
    ]
    assert app["cpus"] == 2
    assert app["network"] == "srv1-podman-v2"
    assert app["current_version"] == "26.1.0"
    assert app["desired_version"] == "26.1.0"
    assert app["last_audited"] == "2026-09-05"


def test_cloudbeaver_canonical_runtime_is_loopback_only() -> None:
    unit = CANONICAL_UNIT.read_text(encoding="utf-8")
    compose = CANONICAL_COMPOSE.read_text(encoding="utf-8")
    compose_document = yaml.safe_load(compose)

    assert "-p 127.0.0.1:8978:8978" in unit
    assert "-p 8978:8978" not in unit
    assert "SuccessExitStatus=143" in unit
    assert compose_document["services"]["cloudbeaver"]["ports"] == [
        "127.0.0.1:8978:8978"
    ]
    for source in (unit, compose):
        assert "docker.io/dbeaver/cloudbeaver:26.1.0" in source
        assert "srv1-podman-v2" in source
        assert "workspace_recent:/opt/cloudbeaver/workspace" in source


def test_cloudbeaver_healthcheck_is_read_only_and_scheduled() -> None:
    healthcheck = HEALTHCHECK.read_text(encoding="utf-8")
    service = HEALTHCHECK_UNIT.read_text(encoding="utf-8")
    timer = HEALTHCHECK_TIMER.read_text(encoding="utf-8")

    assert "http://127.0.0.1:8978/status" in healthcheck
    assert "https://db.atius.com.br/" in healthcheck
    assert "127.0.0.1:8978" in healthcheck
    assert "systemctl --user show container-cloudbeaver.service" in healthcheck
    assert "/usr/bin/podman inspect" not in healthcheck
    assert "systemctl restart" not in healthcheck
    assert "podman restart" not in healthcheck
    assert "ExecStart=/home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/cloudbeaver-healthcheck.sh" in service
    assert "OnUnitActiveSec=5min" in timer
    assert "Persistent=true" in timer


def test_cloudbeaver_docs_do_not_publish_retired_hostname() -> None:
    combined = CLOUDFLARE_DOC.read_text(encoding="utf-8") + PORT_MAP.read_text(
        encoding="utf-8"
    )

    assert "cloudbeaver.atius.com.br" not in combined
    assert "db.atius.com.br" in combined
    assert "docker.io/dbeaver/cloudbeaver:26.1.0" in combined


def test_server_analysis_has_no_legacy_cloudbeaver_docker_recovery() -> None:
    source = ANALYZER.read_text(encoding="utf-8")

    assert "KNOWN_FIXES = {}" in source
    assert "/home/ubuntu/docker/infra/cloudbeaver" not in source
    assert "docker run -d --name cloudbeaver" not in source
