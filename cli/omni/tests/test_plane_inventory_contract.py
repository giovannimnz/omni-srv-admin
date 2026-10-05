"""Plane SRV-1 recovery, readiness, and network-boundary contracts."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[3]
INVENTORY = REPO / "inventory/hosts/atius-srv-1.yaml"
UNIT = REPO / "modules/srv1-ops/systemd/plane-podman.service"
COMPOSE = REPO / "modules/srv1-ops/configs/plane-podman-compose.yaml"
STACK_UP = REPO / "modules/srv1-ops/scripts/plane-stack-up.sh"
HEALTHCHECK = REPO / "modules/srv1-ops/scripts/plane-healthcheck.sh"
HEALTHCHECK_UNIT = REPO / "modules/srv1-ops/systemd/plane-healthcheck.service"
HEALTHCHECK_TIMER = REPO / "modules/srv1-ops/systemd/plane-healthcheck.timer"


def _plane() -> dict:
    host = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    rows = [app for app in host["apps"] if app.get("id") == "plane"]
    assert len(rows) == 1
    return rows[0]


def test_plane_inventory_matches_canonical_runtime() -> None:
    app = _plane()

    assert app["runtime"] == "podman"
    assert app["install_type"] == "systemd-user-podman-compose"
    assert app["unit"] == "plane-podman.service"
    assert app["compose"] == "~/GitHub/containers/plane-app/podman-compose.yaml"
    assert app["public_url"] == "https://plane.atius.com.br/"
    assert app["healthcheck_url"] == "http://127.0.0.1:8090/api/v1/users/me/"
    assert app["ports"] == [
        "127.0.0.1:8080:80",
        "127.0.0.1:8090:80",
    ]
    assert app["network"] == "atius"
    assert app["current_version"] == "1.3.1"
    assert app["desired_version"] == "1.3.1"
    assert app["last_audited"] == "2026-09-27"
    assert app["migrations"] == 162
    assert app["container_count"] == 12


def test_plane_source_is_loopback_only() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))

    assert compose["services"]["web"]["ports"] == ["127.0.0.1:8080:80"]
    assert compose["services"]["proxy"]["ports"] == ["127.0.0.1:8090:80"]
    assert "plane-db" not in compose["services"]
    assert compose["services"]["plane-minio"]["volumes"] == [
        "uploads:/export",
        "minio_data:/data",
    ]
    assert "minio_data" in compose["volumes"]
    assert "healthcheck" not in compose["services"]["space"]
    assert compose["networks"]["atius"]["external"] is True
    assert len(compose["services"]) == 12


def test_plane_unit_waits_for_migrator_and_api_readiness() -> None:
    unit = UNIT.read_text(encoding="utf-8")
    stack_up = STACK_UP.read_text(encoding="utf-8")

    assert "ExecStart=/home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/plane-stack-up.sh" in unit
    assert "TimeoutStartSec=2100" in unit
    assert "SuccessExitStatus=143" in unit
    assert "UMask=0077" in unit
    assert "podman-compose --podman-path /usr/bin/podman --env-file .env -f podman-compose.yaml down" in unit
    assert "podman-compose" in stack_up
    assert "plane-app_migrator_1" in stack_up
    assert "exited:0" in stack_up
    assert "http://127.0.0.1:8090/api/v1/users/me/" in stack_up
    assert "http://127.0.0.1:8090/setup/" in stack_up
    assert "http://127.0.0.1:8090/" in stack_up
    assert "http://127.0.0.1:8090/spaces/" in stack_up
    assert "PLANE_READY_OK" in stack_up
    assert stack_up.index("plane-app_migrator_1") < stack_up.index(
        "http://127.0.0.1:8090/api/v1/users/me/"
    )


def test_plane_healthcheck_is_read_only_and_scheduled() -> None:
    healthcheck = HEALTHCHECK.read_text(encoding="utf-8")
    service = HEALTHCHECK_UNIT.read_text(encoding="utf-8")
    timer = HEALTHCHECK_TIMER.read_text(encoding="utf-8")

    assert "systemctl --user show plane-podman.service" in healthcheck
    assert "127.0.0.1:8080" in healthcheck
    assert "127.0.0.1:8090" in healthcheck
    assert "http://127.0.0.1:8090/api/v1/users/me/" in healthcheck
    assert "https://plane.atius.com.br/api/v1/users/me/" in healthcheck
    assert "http://127.0.0.1:8090/spaces/" in healthcheck
    assert "https://plane.atius.com.br/spaces/" in healthcheck
    assert "systemctl restart" not in healthcheck
    assert "podman restart" not in healthcheck
    assert "podman-compose" not in healthcheck
    assert "/usr/bin/podman" not in healthcheck
    assert "ExecStart=/home/ubuntu/GitHub/omni-srv-admin/modules/srv1-ops/scripts/plane-healthcheck.sh" in service
    assert "OnUnitActiveSec=5min" in timer
    assert "Persistent=true" in timer
