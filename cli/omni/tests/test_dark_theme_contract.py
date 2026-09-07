from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "dark-theme-ubuntu" / "scripts" / "dark-themectl.sh"
WRAPPER = SCRIPT.with_name("dark-themectl-wrapper.sh")


def test_omni_network_tray_defaults_to_current_wg100_interface() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'WG_IFACE = os.environ.get("OMNI_WG_IFACE", "wg100")' in text
    assert 'WG_IFACE = os.environ.get("OMNI_WG_IFACE", "wg0")' not in text


def test_optional_sublime_configuration_does_not_abort_repair() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    function = text.split("configure_sublime_defaults() {", 1)[1].split("\n}", 1)[0]
    assert "return 0" in function


def test_apply_all_does_not_inherit_false_optional_restart_status() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    function = text.split("apply_all() {", 1)[1].split("\n}", 1)[0]
    assert function.rstrip().endswith("return 0")


def test_xrdp_profile_disables_light_locker_autostart() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    function = text.split("apply_autostart() {", 1)[1].split("\n}", 1)[0]
    assert "disable_light_locker" in function
    assert 'X-GNOME-Autostart-enabled=false' in text


def test_light_locker_override_participates_in_backup_and_restore() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    backup = text.split("backup_current() {", 1)[1].split("\n}", 1)[0]
    restore = text.split("restore_latest() {", 1)[1].split("\n}", 1)[0]
    path = '${HOME}/.config/autostart/light-locker.desktop'
    assert f'backup_path "{path}"' in backup
    assert 'home/${USER}/.config/autostart/light-locker.desktop' in restore
    assert "Removido override Omni de light-locker" in restore


def test_dark_environment_rewrites_are_idempotent_and_keep_wg100() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    env_block = text.split("write_env_block() {", 1)[1].split("\n}", 1)[0]
    system_dark = text.split("apply_system_dark() {", 1)[1].split("\n}", 1)[0]
    assert "rstrip()" in env_block
    assert "OMNI_WG_IFACE=wg100" in system_dark
    assert '"OMNI_WG_IFACE=wg100" "environment.d fixa interface WireGuard wg100"' in text


def test_lxpanel_outputs_have_deterministic_modes() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'chmod 0644 "${panel_bg_file}" "${background_panel}" "${panel}" "${status_panel}"' in text


def test_runtime_copy_can_use_canonical_module_assets() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'MODULE_DIR="${OMNI_DARK_MODULE_DIR:-' in text


def test_versioned_runtime_wrapper_uses_installed_copy_and_canonical_assets() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert 'OMNI_DARK_MODULE_DIR="${OMNI_DARK_MODULE_DIR:-$HOME/GitHub/omni-srv-admin/dark-theme-ubuntu}"' in text
    assert 'exec "$HOME/.local/lib/omni-dark-theme/dark-themectl.sh" "$@"' in text


def test_xrdp_watchers_exit_when_their_display_disappears() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    keyboard = text.split("ensure_abnt2_watchdog() {", 1)[1].split("\n}\n\nensure_panel_guard", 1)[0]
    panel = text.split("ensure_panel_guard() {", 1)[1].split("\n}\n\nensure_network_tray", 1)[0]

    guard = "xdpyinfo >/dev/null 2>&1 || exit 0"
    assert guard in keyboard
    assert guard in panel
    assert 'if [ ! -x "${target}" ]' not in keyboard
