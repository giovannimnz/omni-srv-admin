from __future__ import annotations

import sys
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


def test_guard_covers_current_br_layout_and_critical_keys() -> None:
    assert "km_00000416" in xrdp_abnt2_mod.SYSTEM_TARGETS
    text = xrdp_abnt2_mod.CANONICAL["km_abnt2"].read_text(encoding="utf-8")
    for snippet in xrdp_abnt2_mod.REQUIRED_KEYMAP_SNIPPETS:
        assert snippet in text


def test_fleet_xrdp_hosts_declare_xrdp_abnt2_module() -> None:
    for host in ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv"):
        text = (REPO / "inventory" / "hosts" / f"{host}.yaml").read_text(encoding="utf-8")
        assert "- xrdp-abnt2" in text, f"{host} must declare xrdp-abnt2 in inventory"
