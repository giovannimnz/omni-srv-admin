from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from omni import managed_apps


REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "modules" / "managed-apps" / "configs" / "programs.json"
INSTALLER = REPO / "modules" / "managed-apps" / "scripts" / "install-obsidian-arm64-appimage"
GK_INSTALLER = REPO / "modules" / "managed-apps" / "scripts" / "install-gitkraken-gk-arm64-deb"


def test_obsidian_manifest_declares_native_titlebar_default() -> None:
    manifest = json.loads(MANIFEST.read_text())
    obsidian = manifest["programs"]["obsidian"]

    assert obsidian["kind"] == "manual-appimage"
    assert obsidian["accepted_asset_suffix"] == "arm64.AppImage"
    assert "snap" in obsidian["forbidden_package_managers"]
    assert obsidian["post_fix_script"] == "modules/managed-apps/scripts/install-obsidian-arm64-appimage"
    assert obsidian["appearance_defaults"] == {
        "path": "~/GitHub/obsidian-vault/AiSecondBrain/.obsidian/appearance.json",
        "key": "titlebarStyle",
        "value": "native",
    }


def test_obsidian_installer_applies_native_titlebar_default() -> None:
    text = INSTALLER.read_text()

    assert "obsidianmd/obsidian-releases" in text
    assert "arm64.AppImage" in text
    assert ".titlebarStyle = \"native\"" in text
    assert "APPIMAGE_EXTRACT_AND_RUN=1" in text
    assert "OBSIDIAN_USE_FUSE" in text
    assert "Window frame style" not in text
    assert "--no-sandbox" in text
    assert "snap install" not in text


def test_obsidian_tray_docks_existing_window_id_not_command_start_timeout() -> None:
    text = INSTALLER.read_text()

    assert "OBSIDIAN_TRAY_WAIT_SECONDS" in text
    assert "first_obsidian_window" in text
    assert 'kdocker -b -q -w "$wid"' in text
    assert "KDocker skipped: no Obsidian window" in text
    assert "obsidian_running() {\n  command -v wmctrl" in text
    assert text.index('"$HOME/.local/bin/obsidian"') < text.index('"/home/ubuntu/GitHub/Programs/obsidian/Obsidian.AppImage"')
    assert "kdocker -n -q --" not in text


def test_obsidian_upgrade_plan_uses_manual_installer(monkeypatch) -> None:
    manifest = {
        "programs": {
            "obsidian": {
                "kind": "manual-appimage",
                "post_fix_script": "modules/managed-apps/scripts/install-obsidian-arm64-appimage",
            }
        }
    }
    monkeypatch.setattr(managed_apps, "_load_manifest", lambda: manifest)

    result = CliRunner().invoke(managed_apps.managed_apps, ["upgrade", "--app", "obsidian"])

    assert result.exit_code == 0
    assert "install-obsidian-arm64-appimage" in result.output
    assert "plan-only" in result.output


def test_gitkraken_manifest_declares_official_arm64_deb_source() -> None:
    manifest = json.loads(MANIFEST.read_text())
    gitkraken = manifest["programs"]["gitkraken"]

    assert gitkraken["kind"] == "manual-deb"
    assert gitkraken["package"] == "gk"
    assert gitkraken["desired_version"] == "3.1.68"
    assert gitkraken["desired_architecture"] == "arm64"
    assert gitkraken["accepted_asset_suffix"] == "linux_arm64.deb"
    assert gitkraken["source_repository"] == "https://github.com/gitkraken/gk-cli/releases"
    assert gitkraken["source_url"].endswith("/gk_3.1.68_linux_arm64.deb")
    assert gitkraken["forbidden_snap_names"] == ["gitkraken"]
    assert "snap" in gitkraken["forbidden_package_managers"]
    assert gitkraken["post_fix_script"] == "modules/managed-apps/scripts/install-gitkraken-gk-arm64-deb"


def test_gitkraken_installer_uses_github_deb_and_state_file() -> None:
    text = GK_INSTALLER.read_text()

    assert "gitkraken/gk-cli/releases" in text
    assert "gk_${VERSION}_linux_arm64.deb" in text
    assert "dpkg-deb -f" in text
    assert "apt-get install -y" in text
    assert "current-release.json" in text
    assert "snap install" not in text


def test_gitkraken_upgrade_plan_uses_manual_deb_installer(monkeypatch) -> None:
    manifest = {
        "programs": {
            "gitkraken": {
                "kind": "manual-deb",
                "post_fix_script": "modules/managed-apps/scripts/install-gitkraken-gk-arm64-deb",
            }
        }
    }
    monkeypatch.setattr(managed_apps, "_load_manifest", lambda: manifest)

    result = CliRunner().invoke(managed_apps.managed_apps, ["upgrade", "--app", "gitkraken"])

    assert result.exit_code == 0
    assert "install-gitkraken-gk-arm64-deb" in result.output
    assert "plan-only" in result.output
