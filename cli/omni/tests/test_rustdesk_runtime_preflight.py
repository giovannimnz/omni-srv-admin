"""Regression tests for the SRV-1 RustDesk runtime preflight."""

import importlib.util
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "modules" / "srv1-ops" / "apps" / "rustdesk" / "ensure-rustdesk-runtime.py"
DROPIN = REPO / "modules" / "srv1-ops" / "apps" / "rustdesk" / "10-runtime-preflight.conf"


def _load():
    spec = importlib.util.spec_from_file_location("rustdesk_runtime_preflight", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preflight_is_bounded_and_runs_before_every_quadlet_start() -> None:
    source = DROPIN.read_text()
    assert "ExecStartPre=" in source
    assert "--ensure" in source
    assert "StartLimitIntervalSec=300" in source
    assert "StartLimitBurst=3" in source
    assert "RestartSec=30s" in source


def test_preflight_contains_no_secret_values_or_secret_output() -> None:
    source = SCRIPT.read_text()
    assert "secret_material_present" in source
    assert "private_key" in source and "public_key" in source
    assert "print(private" not in source
    assert "print(public" not in source
    assert "environment=" not in source.lower()


def test_ensure_image_is_noop_when_digest_is_present(monkeypatch, tmp_path) -> None:
    module = _load()
    calls: list[list[str]] = []
    monkeypatch.setattr(module, "image_present", lambda *_args: True)
    monkeypatch.setattr(module, "run", lambda command, **_kwargs: calls.append(command))
    assert module.ensure_image(tmp_path / "podman", "example@sha256:digest") is False
    assert calls == []


def test_ensure_image_pulls_exact_digest_when_missing(monkeypatch, tmp_path) -> None:
    module = _load()
    state = {"digest": False, "pin": False}
    calls: list[list[str]] = []

    def present(_podman, image):
        return state["pin"] if image == module.PINNED_TAG else state["digest"]

    def run(command, **_kwargs):
        calls.append(command)
        if command[1] == "pull":
            state["digest"] = True
        elif command[1] == "tag":
            state["pin"] = True
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(module, "image_present", present)
    monkeypatch.setattr(module, "run", run)
    image = "example@sha256:digest"
    assert module.ensure_image(tmp_path / "podman", image) is True
    assert calls == [
        [str(tmp_path / "podman"), "pull", image],
        [str(tmp_path / "podman"), "tag", image, module.PINNED_TAG],
    ]


def test_ensure_image_adds_pin_without_repull(monkeypatch, tmp_path) -> None:
    module = _load()
    calls: list[list[str]] = []
    pin_created = False

    def present(_podman, image):
        return pin_created if image == module.PINNED_TAG else True

    def run(command, **_kwargs):
        nonlocal pin_created
        calls.append(command)
        pin_created = True
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(module, "image_present", present)
    monkeypatch.setattr(module, "run", run)
    image = "example@sha256:digest"
    assert module.ensure_image(tmp_path / "podman", image) is True
    assert calls == [
        [str(tmp_path / "podman"), "tag", image, module.PINNED_TAG]
    ]


def test_existing_identity_rejects_world_readable_files(tmp_path) -> None:
    module = _load()
    identity = tmp_path / "identity"
    identity.mkdir(mode=0o700)
    (identity / "id_ed25519").write_text("x")
    (identity / "id_ed25519.pub").write_text("x")
    (identity / "id_ed25519").chmod(0o644)
    (identity / "id_ed25519.pub").chmod(0o600)
    assert module.existing_identity_valid(identity) is False
