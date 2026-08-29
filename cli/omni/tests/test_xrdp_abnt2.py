from __future__ import annotations

import sys
import subprocess
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
REPO_CLI = REPO / "cli"

if str(REPO_CLI) not in sys.path:
    sys.path.insert(0, str(REPO_CLI))

from omni import xrdp_abnt2 as xrdp_abnt2_mod

def test_required_packages_cover_fleet_xrdp_desktop_parity() -> None:
    expected = {
        "xrdp",
        "xorgxrdp",
        "tigervnc-common",
        "tigervnc-standalone-server",
        "tigervnc-tools",
        "dbus-x11",
        "freerdp2-x11",
        "lxde",
        "lxhotkey-plugin-openbox",
    }

    assert expected <= set(xrdp_abnt2_mod.PREREQUISITE_PACKAGES)


def test_required_commands_cover_smoke_and_session_prereqs() -> None:
    assert xrdp_abnt2_mod.PREREQUISITE_COMMANDS["xfreerdp"] == "freerdp2-x11"
    assert xrdp_abnt2_mod.PREREQUISITE_COMMANDS["dbus-launch"] == "dbus-x11"
    assert xrdp_abnt2_mod.PREREQUISITE_COMMANDS["Xvnc"] == "tigervnc-standalone-server"
    assert xrdp_abnt2_mod.PREREQUISITE_COMMANDS["startlxde"] == "lxde"


def test_normalized_bytes_rewrites_crlf_and_bare_cr(tmp_path: Path) -> None:
    sample = tmp_path / "sample.sh"
    sample.write_bytes(b"line1\r\nline2\rline3\n")

    assert xrdp_abnt2_mod._normalized_bytes(sample) == b"line1\nline2\nline3\n"


def test_canonical_assets_are_lf_only() -> None:
    for name, path in xrdp_abnt2_mod.CANONICAL.items():
        raw = path.read_bytes()
        assert b"\r" not in raw, f"{name} must be LF-only in repo: {path}"


def test_noneditable_package_includes_xrdp_assets(tmp_path: Path) -> None:
    cli_dir = REPO / "cli"
    build_base = tmp_path / "build"
    result = subprocess.run(
        [sys.executable, "setup.py", "build_py", "--build-lib", str(build_base)],
        cwd=cli_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    package_assets = build_base / "omni" / "assets" / "xrdp-abnt2"
    assert (package_assets / "km-abnt2.ini").is_file()
    assert (package_assets / "xrdp-abnt2-reconcile.timer").is_file()

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); import omni.xrdp_abnt2 as x; "
            "assert x.FILES_DIR == x._PACKAGE_FILES_DIR and x.CANONICAL['km_abnt2'].is_file()",
            str(build_base),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr

    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    wheel_build = subprocess.run(
        [sys.executable, "setup.py", "bdist_wheel", "--dist-dir", str(wheel_dir)],
        cwd=cli_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert wheel_build.returncode == 0, wheel_build.stderr
    with zipfile.ZipFile(next(wheel_dir.glob("*.whl"))) as wheel:
        assert "omni/assets/xrdp-abnt2/km-abnt2.ini" in wheel.namelist()
        assert "omni/assets/xrdp-abnt2/xrdp-abnt2-reconcile.timer" in wheel.namelist()


def test_xrdp_overrides_are_idempotent_and_replace_commented_defaults() -> None:
    original = """[Globals]
#xrdp.override_keyboard_type=0x04
#xrdp.override_keyboard_subtype=0x01
#xrdp.override_keylayout=0x00000409

[Logging]
LogLevel=INFO
"""

    rendered = xrdp_abnt2_mod._render_xrdp_overrides(original)

    assert rendered == xrdp_abnt2_mod._render_xrdp_overrides(rendered)
    for key, value in xrdp_abnt2_mod.REQUIRED_XRDP_OVERRIDES.items():
        assert f"{key}={value}" in rendered
    assert "[Logging]\nLogLevel=INFO" in rendered


def test_xrdp_overrides_require_globals_and_ignore_other_sections() -> None:
    original = """[Globals]
port=3389

[Logging]
xrdp.override_keyboard_type=0x04
xrdp.override_keyboard_subtype=0x00
xrdp.override_keylayout=0x00000416
"""

    assert xrdp_abnt2_mod._globals_missing_overrides(original) == [
        "xrdp.override_keyboard_type=0x04",
        "xrdp.override_keyboard_subtype=0x00",
        "xrdp.override_keylayout=0x00000416",
    ]
    rendered = xrdp_abnt2_mod._render_xrdp_overrides(original)
    assert xrdp_abnt2_mod._globals_missing_overrides(rendered) == []
    assert rendered.count("xrdp.override_keyboard_type=0x04") == 2


def test_guard_covers_current_br_layout_and_critical_keys() -> None:
    assert "km_00000416" in xrdp_abnt2_mod.SYSTEM_TARGETS
    text = xrdp_abnt2_mod.CANONICAL["km_abnt2"].read_text(encoding="utf-8")
    assert xrdp_abnt2_mod._keymap_contract_errors(text) == []
    assert xrdp_abnt2_mod._rdp_scancode_smoke(text) == []


def test_keymap_uses_xrdp_0924_xfree86_indexes_not_live_evdev_offsets() -> None:
    sections = xrdp_abnt2_mod._parse_keymap_text(
        xrdp_abnt2_mod.CANONICAL["km_abnt2"].read_text(encoding="utf-8")
    )

    for values in sections.values():
        assert values["Key98"] == "65362:0"   # Up, not Key111
        assert values["Key100"] == "65361:0"  # Left, not Key113
        assert values["Key102"] == "65363:0"  # Right, not Key114
        assert values["Key104"] == "65364:0"  # Down, not Key116
        assert values["Key107"] == "65535:127"  # Delete, not Key119
        assert values["Key111"] == "65377:0"  # Print Screen


def test_abnt_c1_slash_has_all_modifier_levels() -> None:
    sections = xrdp_abnt2_mod._parse_keymap_text(
        xrdp_abnt2_mod.CANONICAL["km_abnt2"].read_text(encoding="utf-8")
    )

    for section, expected in xrdp_abnt2_mod.REQUIRED_ABNT_SECTION_VALUES.items():
        assert sections[section]["Key123"] == expected["Key123"]


def test_watchdog_clears_options_before_reapplying_altgr() -> None:
    text = xrdp_abnt2_mod.CANONICAL["watchdog"].read_text(encoding="utf-8")
    assert "-option '' -option lv3:ralt_switch" in text
    assert "-option -option" not in text


def test_reconciliation_timer_never_restarts_xrdp() -> None:
    service = xrdp_abnt2_mod.CANONICAL["reconcile_service"].read_text(encoding="utf-8")
    timer = xrdp_abnt2_mod.CANONICAL["reconcile_timer"].read_text(encoding="utf-8")
    assert "ExecStart=/usr/local/sbin/fix-xrdp-abnt2-keyboard" in service
    assert "systemctl restart" not in service.lower()
    assert "OnUnitActiveSec=1h" in timer
    assert "RandomizedDelaySec=15min" in timer
    repairer = xrdp_abnt2_mod.CANONICAL["fix_script"].read_text(encoding="utf-8")
    assert 'backup_root="/var/backups/xrdp-abnt2-reconcile"' in repairer
    assert "max_backups=8" in repairer


def test_reconciliation_timer_requires_enabled_and_active(monkeypatch) -> None:
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_state",
        lambda mode, unit: "enabled" if mode == "is-enabled" else "active",
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_properties",
        lambda unit, *_properties: (
            {"Result": "success", "ExecMainStatus": "0"}
            if unit == xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT
            else {"NextElapseUSecRealtime": "Fri 2026-08-29 12:00:00 -03"}
        ),
    )
    assert xrdp_abnt2_mod._reconcile_timer_errors() == []

    monkeypatch.setattr(xrdp_abnt2_mod, "_systemctl_state", lambda _mode, _unit: "inactive")
    assert len(xrdp_abnt2_mod._reconcile_timer_errors()) == 2


def test_reconciliation_timer_rejects_failed_service_or_missing_next_trigger(monkeypatch) -> None:
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_state",
        lambda mode, _unit: "enabled" if mode == "is-enabled" else "active",
    )

    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_properties",
        lambda unit, *_properties: (
            {"Result": "failed", "ExecMainStatus": "1"}
            if unit == xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT
            else {"NextElapseUSecRealtime": ""}
        ),
    )

    errors = xrdp_abnt2_mod._reconcile_timer_errors()
    assert any("não concluiu com sucesso" in error for error in errors)
    assert any("não tem próximo disparo" in error for error in errors)


def test_fleet_xrdp_hosts_declare_xrdp_abnt2_module() -> None:
    for host in ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv"):
        text = (REPO / "inventory" / "hosts" / f"{host}.yaml").read_text(encoding="utf-8")
        assert "- xrdp-abnt2" in text, f"{host} must declare xrdp-abnt2 in inventory"
