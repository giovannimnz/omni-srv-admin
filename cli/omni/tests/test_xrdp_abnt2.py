from __future__ import annotations

import json
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

from click.testing import CliRunner

REPO = Path(__file__).resolve().parents[3]
REPO_CLI = REPO / "cli"

if str(REPO_CLI) not in sys.path:
    sys.path.insert(0, str(REPO_CLI))

from omni import xrdp_abnt2 as xrdp_abnt2_mod


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

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


def test_xrdp_override_validator_rejects_conflicting_duplicates_in_either_order() -> None:
    expected = xrdp_abnt2_mod.REQUIRED_XRDP_OVERRIDES["xrdp.override_keyboard_type"]
    for values in ((expected, "0x07"), ("0x07", expected), (expected, expected)):
        original = "[Globals]\n" + "\n".join(
            f"xrdp.override_keyboard_type={value}" for value in values
        ) + "\n"

        errors = xrdp_abnt2_mod._globals_missing_overrides(original)

        assert f"xrdp.override_keyboard_type={expected}" in errors


def test_xrdp_override_repair_normalizes_duplicates_deterministically() -> None:
    expected_lines = {
        f"{key}={value}" for key, value in xrdp_abnt2_mod.REQUIRED_XRDP_OVERRIDES.items()
    }
    rendered_variants = []
    for values in (("0x04", "0x07"), ("0x07", "0x04")):
        original = "[Globals]\n" + "\n".join(
            f"xrdp.override_keyboard_type={value}" for value in values
        ) + "\n"
        rendered = xrdp_abnt2_mod._render_xrdp_overrides(original)
        rendered_variants.append(rendered)
        assert xrdp_abnt2_mod._globals_missing_overrides(rendered) == []
        for expected in expected_lines:
            assert rendered.splitlines().count(expected) == 1

    assert rendered_variants[0] == rendered_variants[1]


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


def test_reconciler_snapshots_duplicate_globals_before_normalizing(tmp_path: Path) -> None:
    source_script = xrdp_abnt2_mod.CANONICAL["fix_script"].read_text(encoding="utf-8")
    duplicate_cases = (
        "xrdp.override_keyboard_type=0x04\nxrdp.override_keyboard_type=0x07\n",
        "xrdp.override_keyboard_type=0x04\nxrdp.override_keyboard_type=0x04\n",
    )

    for index, duplicate in enumerate(duplicate_cases):
        case_root = tmp_path / f"case-{index}"
        src = case_root / "src"
        dst = case_root / "etc-xrdp"
        backups = case_root / "backups"
        src.mkdir(parents=True)
        dst.mkdir(parents=True)
        for name, content in (
            ("xrdp_keyboard.ini", "keyboard\n"),
            ("km-abnt2.ini", "keymap\n"),
            ("startwm.sh", "#!/bin/sh\n"),
        ):
            _write(src / name, content)
        _write(dst / "xrdp_keyboard.ini", "keyboard\n")
        _write(dst / "startwm.sh", "#!/bin/sh\n")
        for keymap in (
            "km-00000409.ini",
            "km-00000416.ini",
            "km-00010416.ini",
            "km-0000080a.ini",
            "km-0000f010.ini",
        ):
            _write(dst / keymap, "keymap\n")
        original_ini = (
            "[Globals]\n"
            + duplicate
            + "xrdp.override_keyboard_subtype=0x00\n"
            + "xrdp.override_keylayout=0x00000416\n\n[Logging]\nLogLevel=INFO\n"
        )
        _write(dst / "xrdp.ini", original_ini)

        rendered = source_script.replace(
            'src="/usr/local/share/xrdp-abnt2"', f'src="{src}"'
        ).replace('dst="/etc/xrdp"', f'dst="{dst}"').replace(
            'backup_root="/var/backups/xrdp-abnt2-reconcile"',
            f'backup_root="{backups}"',
        )
        rendered = rendered.replace("install -d -o root -g root -m", "install -d -m")
        rendered = rendered.replace("install -o nobody -g nogroup -m", "install -m")
        rendered = rendered.replace("install -o root -g root -m", "install -m")
        script = case_root / "fix-xrdp-abnt2-keyboard"
        _write(script, rendered)
        script.chmod(0o755)

        subprocess.run([str(script)], check=True, text=True, capture_output=True)

        snapshots = list(backups.iterdir())
        assert len(snapshots) == 1
        assert (snapshots[0] / "xrdp.ini").read_text(encoding="utf-8") == original_ini
        normalized = (dst / "xrdp.ini").read_text(encoding="utf-8")
        assert normalized.count("xrdp.override_keyboard_type=0x04") == 1
        assert "xrdp.override_keyboard_type=0x07" not in normalized


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
            {
                "Result": "success",
                "ExecMainStatus": "0",
                "ExecMainStartTimestampMonotonic": "123456789",
            }
            if unit == xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT
            else {"NextElapseUSecRealtime": "Fri 2026-08-29 12:00:00 -03"}
        ),
    )
    assert xrdp_abnt2_mod._reconcile_timer_errors() == []

    monkeypatch.setattr(xrdp_abnt2_mod, "_systemctl_state", lambda _mode, _unit: "inactive")
    assert len(xrdp_abnt2_mod._reconcile_timer_errors()) == 2


def test_reconciliation_timer_accepts_monotonic_next_trigger(monkeypatch) -> None:
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_state",
        lambda mode, _unit: "enabled" if mode == "is-enabled" else "active",
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_properties",
        lambda unit, *_properties: (
            {
                "Result": "success",
                "ExecMainStatus": "0",
                "ExecMainStartTimestampMonotonic": "123456789",
            }
            if unit == xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT
            else {
                "NextElapseUSecRealtime": "",
                "NextElapseUSecMonotonic": "1h 12min",
            }
        ),
    )

    assert xrdp_abnt2_mod._reconcile_timer_errors() == []


def test_reconciliation_timer_rejects_never_run_service(monkeypatch) -> None:
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_state",
        lambda mode, _unit: "enabled" if mode == "is-enabled" else "active",
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_properties",
        lambda unit, *_properties: (
            {"Result": "success", "ExecMainStatus": "0", "ExecMainStartTimestampMonotonic": "0"}
            if unit == xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT
            else {"NextElapseUSecRealtime": "Fri 2026-08-29 12:00:00 -03"}
        ),
    )

    errors = xrdp_abnt2_mod._reconcile_timer_errors()
    assert any("ainda não executou" in error for error in errors)


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


def _prepare_install_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(xrdp_abnt2_mod, "_ensure_root", lambda: None)
    monkeypatch.setattr(xrdp_abnt2_mod, "_check_files_exist", lambda _paths: [])
    monkeypatch.setattr(xrdp_abnt2_mod, "_missing_packages", lambda: [])
    monkeypatch.setattr(xrdp_abnt2_mod, "_backup_current", lambda _username, dry_run: tmp_path / "backup")
    monkeypatch.setattr(xrdp_abnt2_mod, "_ensure_packages", lambda dry_run: [])
    monkeypatch.setattr(xrdp_abnt2_mod, "_watchdog_target", lambda _username: tmp_path / "home" / ".local" / "bin" / "watchdog")
    monkeypatch.setattr(xrdp_abnt2_mod, "_user_group", lambda _username: "users")
    monkeypatch.setattr(xrdp_abnt2_mod, "_target_specs", lambda _username: [])
    monkeypatch.setattr(xrdp_abnt2_mod, "_apply_xrdp_overrides", lambda dry_run: None)
    monkeypatch.setattr(xrdp_abnt2_mod, "_restore_backup", lambda _backup: None)


def test_install_requires_package_opt_in_before_any_mutation(monkeypatch, tmp_path: Path) -> None:
    mutations = []
    monkeypatch.setattr(xrdp_abnt2_mod, "_ensure_root", lambda: None)
    monkeypatch.setattr(xrdp_abnt2_mod, "_check_files_exist", lambda _paths: [])
    monkeypatch.setattr(xrdp_abnt2_mod, "_missing_packages", lambda: ["xrdp", "lxde"])
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_backup_current",
        lambda *_args, **_kwargs: mutations.append("backup"),
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_ensure_packages",
        lambda **_kwargs: mutations.append("apt"),
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_run",
        lambda args, **_kwargs: mutations.append(args),
    )

    result = CliRunner().invoke(
        xrdp_abnt2_mod.xrdp_abnt2,
        ["install", "--user", "ubuntu", "--yes"],
    )

    assert result.exit_code != 0
    assert "--install-packages" in result.output
    assert mutations == []


def test_package_opt_in_is_explicit_nonrollbackable_boundary(monkeypatch, tmp_path: Path) -> None:
    _prepare_install_command(monkeypatch, tmp_path)
    events = []
    monkeypatch.setattr(xrdp_abnt2_mod, "_missing_packages", lambda: ["xrdp"])
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_ensure_packages",
        lambda dry_run: events.append(("apt", dry_run)) or ["xrdp"],
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_backup_current",
        lambda _username, dry_run: events.append(("backup", dry_run)) or tmp_path / "backup",
    )
    monkeypatch.setattr(xrdp_abnt2_mod, "_install_steps", lambda *_args, **_kwargs: None)

    result = CliRunner().invoke(
        xrdp_abnt2_mod.xrdp_abnt2,
        ["install", "--user", "ubuntu", "--yes", "--install-packages"],
    )

    assert result.exit_code == 0, result.output
    assert events == [("apt", False), ("backup", False)]
    assert "não será revertida" in result.output


def test_install_help_marks_package_boundary_and_skip_deprecation() -> None:
    result = CliRunner().invoke(xrdp_abnt2_mod.xrdp_abnt2, ["install", "--help"])
    normalized_help = " ".join(result.output.split())

    assert result.exit_code == 0
    assert "--install-packages" in normalized_help
    assert "não reversível" in normalized_help
    assert "--skip-packages" in normalized_help
    assert "Deprecated/no-op" in normalized_help


def test_install_runs_reconciler_once_before_validating_fresh_timer(monkeypatch, tmp_path: Path) -> None:
    _prepare_install_command(monkeypatch, tmp_path)
    commands: list[list[str]] = []
    reconciled = False

    def fake_run(args, *, dry_run=False, env=None):
        nonlocal reconciled
        assert dry_run is False
        commands.append(args)
        if args == ["systemctl", "start", xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT]:
            reconciled = True

    def fake_validation(_username):
        assert reconciled, "fresh install must reconcile before validating"
        return True, ["timer reconciled"], []

    monkeypatch.setattr(xrdp_abnt2_mod, "_run", fake_run)
    monkeypatch.setattr(xrdp_abnt2_mod, "_validation", fake_validation)

    result = CliRunner().invoke(xrdp_abnt2_mod.xrdp_abnt2, ["install", "--user", "ubuntu", "--yes"])

    assert result.exit_code == 0, result.output
    assert ["systemctl", "enable", "--now", xrdp_abnt2_mod.RECONCILE_TIMER_UNIT] in commands
    assert ["systemctl", "start", xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT] in commands
    assert not any(command[:2] == ["systemctl", "restart"] for command in commands)


def test_install_propagates_first_reconciler_failure_before_validation(monkeypatch, tmp_path: Path) -> None:
    _prepare_install_command(monkeypatch, tmp_path)
    validated = False

    def fake_run(args, *, dry_run=False, env=None):
        if args == ["systemctl", "start", xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT]:
            raise subprocess.CalledProcessError(1, args)

    def fake_validation(_username):
        nonlocal validated
        validated = True
        return True, [], []

    restored = []
    monkeypatch.setattr(xrdp_abnt2_mod, "_run", fake_run)
    monkeypatch.setattr(xrdp_abnt2_mod, "_restore_backup", lambda backup: restored.append(backup))
    monkeypatch.setattr(xrdp_abnt2_mod, "_validation", fake_validation)

    result = CliRunner().invoke(xrdp_abnt2_mod.xrdp_abnt2, ["install", "--user", "ubuntu", "--yes"])

    assert result.exit_code != 0
    assert isinstance(result.exception, subprocess.CalledProcessError)
    assert validated is False
    assert restored == [tmp_path / "backup"]


def test_late_validation_failure_rolls_back_without_restarting_xrdp(monkeypatch, tmp_path: Path) -> None:
    _prepare_install_command(monkeypatch, tmp_path)
    commands = []
    restored = []
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_run",
        lambda args, **_kwargs: commands.append(args),
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_validation",
        lambda _username: (False, [], ["injected late failure"]),
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_restore_backup",
        lambda backup: restored.append(backup),
    )

    result = CliRunner().invoke(
        xrdp_abnt2_mod.xrdp_abnt2,
        ["install", "--user", "ubuntu", "--yes"],
    )

    assert result.exit_code != 0
    assert restored == [tmp_path / "backup"]
    assert not any(command[:2] == ["systemctl", "restart"] for command in commands)


def test_backup_manifest_records_exact_metadata_and_all_unit_state(monkeypatch, tmp_path: Path) -> None:
    existing = tmp_path / "etc" / "xrdp" / "startwm.sh"
    absent = tmp_path / "etc" / "xrdp" / "new.ini"
    _write(existing, "original\n")
    existing.chmod(0o751)
    original = existing.lstat()
    monkeypatch.setattr(xrdp_abnt2_mod, "_ensure_root", lambda: None)
    monkeypatch.setattr(xrdp_abnt2_mod, "_user_home", lambda _username: tmp_path / "home")
    monkeypatch.setattr(xrdp_abnt2_mod, "_rollback_paths", lambda _username: [existing, absent])
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_systemctl_state",
        lambda mode, unit: f"{mode}:{unit}",
    )
    chowns = []
    monkeypatch.setattr(
        xrdp_abnt2_mod.os,
        "chown",
        lambda path, uid, gid, **_kwargs: chowns.append((Path(path), uid, gid)),
    )

    backup = xrdp_abnt2_mod._backup_current("ubuntu", dry_run=False)
    manifest = json.loads((backup / "rollback-manifest.json").read_text())

    existing_entry = next(entry for entry in manifest["files"] if entry["path"] == str(existing))
    assert existing_entry == {
        "path": str(existing),
        "existed": True,
        "st_mode": original.st_mode,
        "st_uid": original.st_uid,
        "st_gid": original.st_gid,
    }
    assert next(entry for entry in manifest["files"] if entry["path"] == str(absent)) == {
        "path": str(absent),
        "existed": False,
    }
    assert set(manifest["units"]) == set(xrdp_abnt2_mod.ROLLBACK_SYSTEMD_UNITS)
    assert stat.S_IMODE((backup / "rollback-manifest.json").stat().st_mode) == 0o600
    assert chowns[-1][1:] == (0, 0)


def test_restore_backup_restores_exact_metadata_and_all_unit_state(monkeypatch, tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    destination = tmp_path / "etc" / "xrdp" / "startwm.sh"
    _write(destination, "new\n")
    source = backup / str(destination).lstrip("/")
    _write(source, "old\n")
    expected_mode = stat.S_IFREG | 0o4751
    expected_uid = 123
    expected_gid = 456
    units = {
        "xrdp": {"enabled": "disabled", "active": "active"},
        "xrdp-sesman": {"enabled": "enabled", "active": "active"},
        xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT: {
            "enabled": "static",
            "active": "inactive",
        },
        xrdp_abnt2_mod.RECONCILE_TIMER_UNIT: {
            "enabled": "enabled",
            "active": "active",
        },
    }
    manifest = {
        "username": "ubuntu",
        "files": [
            {
                "path": str(destination),
                "existed": True,
                "st_mode": expected_mode,
                "st_uid": expected_uid,
                "st_gid": expected_gid,
            },
            {"path": str(tmp_path / "new-file"), "existed": False},
        ],
        "units": units,
    }
    _write(backup / "rollback-manifest.json", json.dumps(manifest))
    _write(tmp_path / "new-file", "remove me\n")
    commands = []
    chowns = []
    monkeypatch.setattr(xrdp_abnt2_mod, "_ensure_root", lambda: None)
    monkeypatch.setattr(
        xrdp_abnt2_mod,
        "_rollback_paths",
        lambda _username: [destination, tmp_path / "new-file"],
    )
    monkeypatch.setattr(
        xrdp_abnt2_mod.os,
        "chown",
        lambda path, uid, gid, **_kwargs: (
            chowns.append((Path(path), uid, gid)),
            Path(path).chmod(stat.S_IMODE(Path(path).stat().st_mode) & ~0o6000),
        ),
    )
    monkeypatch.setattr(xrdp_abnt2_mod, "_run", lambda args, **_kwargs: commands.append(args))

    xrdp_abnt2_mod._restore_backup(backup)

    assert destination.read_text() == "old\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o4751
    assert chowns == [(chowns[0][0], expected_uid, expected_gid)]
    assert not (tmp_path / "new-file").exists()
    assert ["systemctl", "daemon-reload"] in commands
    assert ["systemctl", "disable", "xrdp"] in commands
    assert ["systemctl", "start", "xrdp"] in commands
    assert ["systemctl", "enable", "xrdp-sesman"] in commands
    assert ["systemctl", "start", "xrdp-sesman"] in commands
    assert ["systemctl", "disable", xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT] in commands
    assert ["systemctl", "stop", xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT] in commands
    assert ["systemctl", "enable", xrdp_abnt2_mod.RECONCILE_TIMER_UNIT] in commands
    assert ["systemctl", "start", xrdp_abnt2_mod.RECONCILE_TIMER_UNIT] in commands
    assert not any(command[:2] == ["systemctl", "restart"] for command in commands)


def test_fresh_install_rollback_stops_new_reconcile_units_before_removing_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    units = {
        "xrdp": {"enabled": "enabled", "active": "active"},
        "xrdp-sesman": {"enabled": "enabled", "active": "active"},
        xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT: {
            "enabled": "not-found",
            "active": "inactive",
        },
        xrdp_abnt2_mod.RECONCILE_TIMER_UNIT: {
            "enabled": "not-found",
            "active": "inactive",
        },
    }
    _write(
        backup / "rollback-manifest.json",
        json.dumps({"username": "ubuntu", "files": [], "units": units}),
    )
    commands = []
    monkeypatch.setattr(xrdp_abnt2_mod, "_ensure_root", lambda: None)
    monkeypatch.setattr(xrdp_abnt2_mod, "_rollback_paths", lambda _username: [])
    monkeypatch.setattr(xrdp_abnt2_mod, "_run", lambda args, **_kwargs: commands.append(args))

    xrdp_abnt2_mod._restore_backup(backup)

    daemon_reload_index = commands.index(["systemctl", "daemon-reload"])
    assert commands.index(
        ["systemctl", "stop", xrdp_abnt2_mod.RECONCILE_TIMER_UNIT]
    ) < daemon_reload_index
    assert commands.index(
        ["systemctl", "disable", xrdp_abnt2_mod.RECONCILE_TIMER_UNIT]
    ) < daemon_reload_index
    assert commands.index(
        ["systemctl", "stop", xrdp_abnt2_mod.RECONCILE_SERVICE_UNIT]
    ) < daemon_reload_index
    assert not any(command[:2] == ["systemctl", "restart"] for command in commands)


def test_fleet_xrdp_hosts_declare_xrdp_abnt2_module() -> None:
    for host in ("atius-srv-1", "atius-srv-2", "atius-srv-3", "horistic-srv"):
        text = (REPO / "inventory" / "hosts" / f"{host}.yaml").read_text(encoding="utf-8")
        assert "- xrdp-abnt2" in text, f"{host} must declare xrdp-abnt2 in inventory"
