from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import subprocess
import sys

from click.testing import CliRunner

from omni import managed_apps


REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "modules" / "managed-apps" / "configs" / "programs.json"
INSTALLER = REPO / "modules" / "managed-apps" / "scripts" / "install-obsidian-arm64-appimage"
GK_INSTALLER = REPO / "modules" / "managed-apps" / "scripts" / "install-gitkraken-gk-arm64-deb"
BROWSER_RECONCILER = REPO / "modules" / "managed-apps" / "scripts" / "browser-default-reconciler.py"
BROWSER_INSTALLER = REPO / "modules" / "managed-apps" / "scripts" / "install-browser-default-reconciler"
BROWSER_SYSTEMD = REPO / "modules" / "managed-apps" / "systemd"


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
    assert "Window frame style" not in text
    assert "--no-sandbox" in text
    assert "snap install" not in text


def test_obsidian_installer_materializes_and_validates_xrdp_launcher() -> None:
    text = INSTALLER.read_text()

    assert "write_xrdp_launch" in text
    assert 'XRDP_LAUNCH="$HOME/.local/bin/xrdp-launch"' in text
    assert "DISPLAY=:1" in text
    assert 'XAUTHORITY="${HOME}/.Xauthority"' in text
    assert 'chmod 755 "$XRDP_LAUNCH"' in text
    assert '[ -x "$XRDP_LAUNCH" ]' in text
    assert 'desktop-file-validate "$HOME/Desktop/obsidian.desktop"' in text


def test_obsidian_tray_docks_existing_window_id_not_command_start_timeout() -> None:
    text = INSTALLER.read_text()

    assert "OBSIDIAN_TRAY_WAIT_SECONDS" in text
    assert "first_obsidian_window" in text
    assert 'kdocker -b -q -w "$wid"' in text
    assert "KDocker skipped: no Obsidian window" in text
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


def _load_browser_reconciler():
    spec = importlib.util.spec_from_file_location("browser_default_reconciler", BROWSER_RECONCILER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_browser_default_reconciler_preserves_codex_and_unrelated_entries() -> None:
    module = _load_browser_reconciler()
    source = """# prefix\n\n[Default Applications]\ntext/html=chatgpt.desktop\nx-scheme-handler/http=brave-browser.desktop\nx-scheme-handler/http=chatgpt.desktop\nx-scheme-handler/codex=chatgpt.desktop\napplication/pdf=org.pwmt.zathura.desktop\n\n[Added Associations]\ntext/plain=mousepad.desktop;\n"""

    output, changed = module.reconcile_text(source, "google-chrome.desktop")

    assert changed is True
    assert output.count("text/html=google-chrome.desktop") == 1
    assert output.count("x-scheme-handler/http=google-chrome.desktop") == 1
    assert output.count("x-scheme-handler/https=google-chrome.desktop") == 1
    assert "x-scheme-handler/codex=chatgpt.desktop" in output
    assert "application/pdf=org.pwmt.zathura.desktop" in output
    assert "[Added Associations]\ntext/plain=mousepad.desktop;" in output
    second, changed_again = module.reconcile_text(output, "google-chrome.desktop")
    assert changed_again is False
    assert second == output


def test_browser_default_reconciler_cli_writes_mode_and_state(tmp_path: Path) -> None:
    mime = tmp_path / "mimeapps.list"
    state = tmp_path / "state.json"
    lock = tmp_path / "lock"
    mime.write_text("[Default Applications]\ntext/html=chatgpt.desktop\nx-scheme-handler/codex=chatgpt.desktop\n")
    mime.chmod(0o664)

    result = subprocess.run(
        [sys.executable, str(BROWSER_RECONCILER), "--mimeapps", str(mime), "--state", str(state), "--lock", str(lock), "--browser-desktop", "google-chrome.desktop"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert mime.stat().st_mode & 0o777 == 0o664
    data = json.loads(state.read_text())
    assert data["status"] == "success"
    assert data["browser_desktop"] == "google-chrome.desktop"
    assert data["handlers"] == {
        "text/html": "google-chrome.desktop",
        "x-scheme-handler/http": "google-chrome.desktop",
        "x-scheme-handler/https": "google-chrome.desktop",
        "x-scheme-handler/codex": "chatgpt.desktop",
    }
    assert state.stat().st_mode & 0o777 == 0o600


def test_browser_default_reconciler_systemd_layers_and_hardening() -> None:
    service = (BROWSER_SYSTEMD / "browser-default-reconciler.service").read_text()
    path = (BROWSER_SYSTEMD / "browser-default-reconciler.path").read_text()
    timer = (BROWSER_SYSTEMD / "browser-default-reconciler.timer").read_text()
    assert "EnvironmentFile=-%h/.config/omni/browser-default-reconciler.env" in service
    assert "browser-default-reconciler.py" in service
    assert "NoNewPrivileges=true" in service
    assert "ProtectSystem=strict" in service
    assert "ProtectKernelModules=true" not in service
    assert "ReadWritePaths=%h/.config/mimeapps.list %h/.local/state/omni" in service
    assert "PathChanged=%h/.config/mimeapps.list" in path
    assert "Unit=browser-default-reconciler.service" in path
    assert "OnUnitActiveSec=1min" in timer
    assert "Persistent=true" in timer


def test_browser_default_reconciler_installer_is_backup_first_and_host_configurable() -> None:
    text = BROWSER_INSTALLER.read_text()
    assert "browser-default-reconciler.env" in text
    assert "BROWSER_DESKTOP" in text
    assert ".backups" in text
    assert "SHA256SUMS" in text
    assert "browser-default-reconciler-restore" in text
    assert "restore_test=PASS" in text
    assert "browser-default-reconciler.path" in text
    assert "browser-default-reconciler.timer" in text
    assert "reset-failed browser-default-reconciler.service" in text
    assert "enable --now browser-default-reconciler.path browser-default-reconciler.timer" in text
