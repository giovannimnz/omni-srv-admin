#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_DIR="${MODULE_DIR}/config_files"
THEME_DIR="${MODULE_DIR}/themes"
FONT_DIR="${MODULE_DIR}/fonts"
PROFILE="${LXDE_PROFILE:-LXDE}"
BACKUP_BASE="${BACKUP_BASE:-${HOME}/.backups/omni-dark-theme}"
PANEL_BG="${OMNI_LXPANEL_BG:-#101214}"
DESKTOP_BG="${OMNI_DESKTOP_BG:-#05070a}"

INSTALL_PACKAGES=0
WITH_SUBLIME=0
WITH_ZSH=0
RESTART_SESSION=0
BACKUP_DIR=""

if [ -t 1 ]; then
  GREEN=$'\033[0;32m'
  YELLOW=$'\033[1;33m'
  RED=$'\033[0;31m'
  NC=$'\033[0m'
else
  GREEN=""
  YELLOW=""
  RED=""
  NC=""
fi

log() {
  printf '%s\n' "$*"
}

ok() {
  printf '%sOK%s   %s\n' "${GREEN}" "${NC}" "$*"
}

warn() {
  printf '%sWARN%s %s\n' "${YELLOW}" "${NC}" "$*"
}

fail() {
  printf '%sFAIL%s %s\n' "${RED}" "${NC}" "$*" >&2
}

usage() {
  cat <<'EOF'
Uso:
  dark-themectl.sh status
  dark-themectl.sh validate
  dark-themectl.sh apply [--install-packages] [--with-sublime] [--with-zsh] [--restart-session]
  dark-themectl.sh repair [--install-packages] [--restart-session]
  dark-themectl.sh restore-latest [BACKUP_DIR]

Comandos:
  status          Mostra estado atual sem modificar.
  validate        Valida LXDE/Openbox/GTK/painel/autostart/fontes.
  apply           Aplica o tema dark completo com backup previo.
  repair          Reaplica o visual e o painel sem forcar apps opcionais.
  restore-latest  Restaura o backup mais recente de ~/.backups/omni-dark-theme.

Opcoes:
  --install-packages  Instala dependencias faltantes via apt.
  --with-sublime      Garante Sublime Text pelo repo oficial.
  --with-zsh          Garante zsh/oh-my-zsh sem sobrescrever .zshrc inteira.
  --restart-session   Recarrega lxpanel/openbox/pcmanfm na sessao atual.
EOF
}

run_sudo() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

package_missing() {
  ! dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q 'install ok installed'
}

install_packages() {
  local packages=(
    lxsession
    lxpanel
    pcmanfm
    openbox
    obconf
    lxappearance
    greybird-gtk-theme
    gtk2-engines-pixbuf
    python3-gi
    gir1.2-gtk-3.0
    gsettings-desktop-schemas
    dconf-cli
    dconf-service
    xdg-desktop-portal
    xdg-desktop-portal-gtk
    network-manager-gnome
    copyq
    xscreensaver
    x11-xkb-utils
    imagemagick
    fontconfig
    fonts-dejavu-core
    libxml2-utils
    desktop-file-utils
    libgtk-3-bin
    libgtk-4-bin
    qt5-gtk-platformtheme
    wmctrl
    xdotool
    curl
    gpg
    git
  )

  if [ "${WITH_ZSH}" -eq 1 ]; then
    packages+=(zsh)
  fi

  local missing=()
  local pkg
  for pkg in "${packages[@]}"; do
    if package_missing "$pkg"; then
      missing+=("$pkg")
    fi
  done

  if [ "${#missing[@]}" -eq 0 ]; then
    ok "Dependencias apt ja instaladas"
    return 0
  fi

  log "Instalando dependencias apt: ${missing[*]}"
  run_sudo apt-get update -qq
  run_sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
}

install_sublime() {
  if need_cmd subl || ! package_missing sublime-text; then
    ok "Sublime Text ja instalado"
    return 0
  fi

  if ! package_missing sublime-text; then
    ok "Sublime Text ja instalado"
    return 0
  fi

  log "Instalando Sublime Text pelo repo oficial"
  install_packages
  run_sudo install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://download.sublimetext.com/sublimehq-pub.gpg \
    | gpg --dearmor \
    | run_sudo tee /etc/apt/keyrings/sublimehq-archive.gpg >/dev/null
  echo "deb [signed-by=/etc/apt/keyrings/sublimehq-archive.gpg] https://download.sublimetext.com/ apt/stable/" \
    | run_sudo tee /etc/apt/sources.list.d/sublime-text.list >/dev/null
  run_sudo apt-get update -qq
  run_sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y sublime-text
}

begin_backup() {
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  BACKUP_DIR="${BACKUP_BASE}/${stamp}"
  mkdir -p "${BACKUP_DIR}"
  {
    printf 'created_at=%s\n' "$(date -Is)"
    printf 'host=%s\n' "$(hostname)"
    printf 'user=%s\n' "${USER:-unknown}"
    printf 'module=%s\n' "${MODULE_DIR}"
  } >"${BACKUP_DIR}/MANIFEST.env"
  ok "Backup criado em ${BACKUP_DIR}"
}

backup_path() {
  local src="$1"
  [ -e "${src}" ] || return 0
  [ -n "${BACKUP_DIR}" ] || begin_backup
  local rel="${src#/}"
  local dst="${BACKUP_DIR}/${rel}"
  mkdir -p "$(dirname "${dst}")"
  cp -a "${src}" "${dst}"
}

backup_current() {
  begin_backup
  backup_path "${HOME}/.gtkrc-2.0"
  backup_path "${HOME}/.zshrc"
  backup_path "${HOME}/.config/gtk-3.0/settings.ini"
  backup_path "${HOME}/.config/gtk-3.0/gtk.css"
  backup_path "${HOME}/.config/environment.d/10-omni-dark.conf"
  backup_path "${HOME}/.config/xdg-desktop-portal/lxde-portals.conf"
  backup_path "${HOME}/.config/lxsession/${PROFILE}/desktop.conf"
  backup_path "${HOME}/.config/lxsession/${PROFILE}/autostart"
  backup_path "${HOME}/.config/autostart/nm-applet.desktop"
  backup_path "${HOME}/.config/lxpanel/${PROFILE}/panel-background.xpm"
  backup_path "${HOME}/.config/lxpanel/${PROFILE}/panels/00-background"
  backup_path "${HOME}/.config/lxpanel/${PROFILE}/panels/panel"
  backup_path "${HOME}/.config/lxpanel/${PROFILE}/panels/status-right"
  backup_path "${HOME}/.xsessionrc"
  backup_path "${HOME}/.profile"
  backup_path "${HOME}/.local/bin/omni-network-tray.py"
  backup_path "${HOME}/.local/share/icons/omni-dark-theme"
  backup_path "${HOME}/.config/openbox/lxde-rc.xml"
  backup_path "${HOME}/.config/pcmanfm/${PROFILE}/desktop-items-0.conf"
  backup_path "${HOME}/.config/Code/User/settings.json"
  backup_path "${HOME}/.config/chromium-flags.conf"
  backup_path "${HOME}/.config/brave-flags.conf"
  backup_path "${HOME}/.config/electron-flags.conf"
}

install_fonts() {
  if [ ! -d "${FONT_DIR}" ]; then
    warn "Diretorio de fontes ausente: ${FONT_DIR}"
    return 0
  fi

  run_sudo install -d -m 0755 /usr/local/share/fonts/apple
  local font
  while IFS= read -r -d '' font; do
    run_sudo install -m 0644 "${font}" "/usr/local/share/fonts/apple/$(basename "${font}")"
  done < <(find "${FONT_DIR}" -type f \( -iname '*.ttf' -o -iname '*.otf' \) -print0)
  fc-cache -f >/dev/null 2>&1 || run_sudo fc-cache -f >/dev/null
  ok "Fontes Apple/Tahoma aplicadas"
}

apply_gtk() {
  mkdir -p "${HOME}/.config/gtk-3.0" "${HOME}/.config/lxsession/${PROFILE}"
  install -m 0644 "${CONFIG_DIR}/gtkrc-2.0" "${HOME}/.gtkrc-2.0"
  install -m 0644 "${CONFIG_DIR}/gtk-3.0-settings.ini" "${HOME}/.config/gtk-3.0/settings.ini"
  install -m 0644 "${CONFIG_DIR}/gtk-3.0.css" "${HOME}/.config/gtk-3.0/gtk.css"
  install -m 0644 "${CONFIG_DIR}/desktop.conf" "${HOME}/.config/lxsession/${PROFILE}/desktop.conf"
  ok "GTK2/GTK3/LXSession dark aplicados"
}

set_gsettings_if_possible() {
  local schema="$1"
  local key="$2"
  local value="$3"
  if need_cmd gsettings && gsettings list-schemas | grep -Fxq "${schema}" && gsettings list-keys "${schema}" | grep -Fxq "${key}"; then
    gsettings set "${schema}" "${key}" "${value}" >/dev/null 2>&1 || true
  fi
}

write_env_block() {
  local file="$1"
  mkdir -p "$(dirname "${file}")"
  touch "${file}"
  sed -i '/^# omni dark system env begin$/,/^# omni dark system env end$/d' "${file}"
  cat >>"${file}" <<EOF

# omni dark system env begin
export XDG_CURRENT_DESKTOP="\${XDG_CURRENT_DESKTOP:-LXDE}"
export DESKTOP_SESSION="\${DESKTOP_SESSION:-LXDE}"
export GTK_THEME="Greybird-dark"
export GTK2_RC_FILES="${HOME}/.gtkrc-2.0"
export QT_QPA_PLATFORMTHEME="gtk3"
# omni dark system env end
EOF
}

ensure_dark_system_helper() {
  local target="${HOME}/.local/bin/omni-dark-system-env.sh"
  mkdir -p "$(dirname "${target}")"
  cat >"${target}" <<EOF
#!/usr/bin/env bash
set -u

export XDG_CURRENT_DESKTOP="\${XDG_CURRENT_DESKTOP:-LXDE}"
export DESKTOP_SESSION="\${DESKTOP_SESSION:-LXDE}"
export GTK_THEME="\${GTK_THEME:-Greybird-dark}"
export GTK2_RC_FILES="\${GTK2_RC_FILES:-${HOME}/.gtkrc-2.0}"
export QT_QPA_PLATFORMTHEME="\${QT_QPA_PLATFORMTHEME:-gtk3}"

if command -v gsettings >/dev/null 2>&1 && gsettings list-schemas | grep -Fxq org.gnome.desktop.interface; then
  gsettings set org.gnome.desktop.interface color-scheme "'prefer-dark'" >/dev/null 2>&1 || true
  gsettings set org.gnome.desktop.interface gtk-theme "'Greybird-dark'" >/dev/null 2>&1 || true
  gsettings set org.gnome.desktop.interface icon-theme "'nuoveXT2'" >/dev/null 2>&1 || true
  gsettings set org.gnome.desktop.interface cursor-theme "'DMZ-White'" >/dev/null 2>&1 || true
  gsettings set org.gnome.desktop.interface font-name "'SF Pro Display 10'" >/dev/null 2>&1 || true
fi

if command -v dbus-update-activation-environment >/dev/null 2>&1; then
  dbus-update-activation-environment --systemd DISPLAY XAUTHORITY XDG_CURRENT_DESKTOP DESKTOP_SESSION GTK_THEME GTK2_RC_FILES QT_QPA_PLATFORMTHEME >/dev/null 2>&1 || true
fi

case "\${1:-}" in
  --restart-portal)
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user restart xdg-desktop-portal-gtk.service xdg-desktop-portal.service >/dev/null 2>&1 || true
    fi
    ;;
esac
EOF
  chmod 0755 "${target}"
}

apply_system_dark() {
  export XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-LXDE}"
  export DESKTOP_SESSION="${DESKTOP_SESSION:-LXDE}"
  export GTK_THEME="Greybird-dark"
  export GTK2_RC_FILES="${HOME}/.gtkrc-2.0"
  export QT_QPA_PLATFORMTHEME="gtk3"

  mkdir -p "${HOME}/.config/environment.d" "${HOME}/.config/xdg-desktop-portal"
  cat >"${HOME}/.config/environment.d/10-omni-dark.conf" <<EOF
XDG_CURRENT_DESKTOP=LXDE
DESKTOP_SESSION=LXDE
GTK_THEME=Greybird-dark
GTK2_RC_FILES=${HOME}/.gtkrc-2.0
QT_QPA_PLATFORMTHEME=gtk3
EOF

  cat >"${HOME}/.config/xdg-desktop-portal/lxde-portals.conf" <<'EOF'
[preferred]
default=gtk
org.freedesktop.impl.portal.Settings=gtk
EOF

  write_env_block "${HOME}/.xsessionrc"
  write_env_block "${HOME}/.profile"
  ensure_dark_system_helper

  set_gsettings_if_possible org.gnome.desktop.interface color-scheme "'prefer-dark'"
  set_gsettings_if_possible org.gnome.desktop.interface gtk-theme "'Greybird-dark'"
  set_gsettings_if_possible org.gnome.desktop.interface icon-theme "'nuoveXT2'"
  set_gsettings_if_possible org.gnome.desktop.interface cursor-theme "'DMZ-White'"
  set_gsettings_if_possible org.gnome.desktop.interface font-name "'SF Pro Display 10'"

  if need_cmd dbus-update-activation-environment; then
    dbus-update-activation-environment --systemd DISPLAY XAUTHORITY XDG_CURRENT_DESKTOP DESKTOP_SESSION GTK_THEME GTK2_RC_FILES QT_QPA_PLATFORMTHEME >/dev/null 2>&1 || true
  fi
  if need_cmd systemctl && [ -n "${DISPLAY:-}" ]; then
    systemctl --user restart xdg-desktop-portal-gtk.service xdg-desktop-portal.service >/dev/null 2>&1 || true
  fi
  ok "System dark aplicado para GTK/GSettings/portal/Qt"
}

apply_openbox() {
  mkdir -p "${HOME}/.themes/Dark-Onyx/openbox-3" "${HOME}/.config/openbox"
  cp -a "${THEME_DIR}/Dark-Onyx/openbox-3/." "${HOME}/.themes/Dark-Onyx/openbox-3/"
  install -m 0644 "${CONFIG_DIR}/lxde-rc.xml" "${HOME}/.config/openbox/lxde-rc.xml"
  if need_cmd xmllint; then
    xmllint --noout "${HOME}/.config/openbox/lxde-rc.xml"
  fi
  ok "Openbox Dark-Onyx aplicado"
}

set_ini_key() {
  local file="$1"
  local key="$2"
  local value="$3"
  mkdir -p "$(dirname "${file}")"
  if [ ! -f "${file}" ]; then
    printf '[*]\n' >"${file}"
  fi

  local tmp
  tmp="$(mktemp)"
  awk -v section='[*]' -v key="${key}" -v value="${value}" '
    BEGIN { insec = 0; done = 0; seen = 0 }
    $0 == section {
      if (insec && !done) {
        print key "=" value
        done = 1
      }
      insec = 1
      seen = 1
      print
      next
    }
    /^\[/ && insec {
      if (!done) {
        print key "=" value
        done = 1
      }
      insec = 0
    }
    insec && index($0, key "=") == 1 {
      if (!done) {
        print key "=" value
        done = 1
      }
      next
    }
    { print }
    END {
      if (!seen) {
        print section
        print key "=" value
      } else if (insec && !done) {
        print key "=" value
      }
    }
  ' "${file}" >"${tmp}"
  mv "${tmp}" "${file}"
}

apply_pcmanfm_desktop() {
  local file="${HOME}/.config/pcmanfm/${PROFILE}/desktop-items-0.conf"
  set_ini_key "${file}" "wallpaper_mode" "color"
  set_ini_key "${file}" "wallpaper_common" "1"
  set_ini_key "${file}" "desktop_bg" "${DESKTOP_BG}"
  set_ini_key "${file}" "desktop_fg" "#f8fafc"
  set_ini_key "${file}" "desktop_shadow" "#000000"
  set_ini_key "${file}" "desktop_font" "SF Pro Display 12"
  set_ini_key "${file}" "show_wm_menu" "0"
  set_ini_key "${file}" "show_documents" "0"
  set_ini_key "${file}" "show_trash" "1"
  set_ini_key "${file}" "show_mounts" "0"
  ok "PCManFM desktop dark aplicado sem apagar posicoes de icones"
}

ensure_abnt2_watchdog() {
  local target="${HOME}/.local/bin/setxkbmap-abnt2.sh"
  mkdir -p "$(dirname "${target}")"
  if [ ! -x "${target}" ]; then
    cat >"${target}" <<'EOF'
#!/bin/sh
apply_abnt2() {
    command -v setxkbmap >/dev/null 2>&1 || return 0
    setxkbmap -model pc105 -layout br -variant abnt2 -option -option lv3:ralt_switch >/dev/null 2>&1 || true
}
case "${1:-}" in
    --watch)
        lock_file="/tmp/setxkbmap-abnt2-${USER:-ubuntu}.lock"
        exec 9>"$lock_file" || exit 0
        flock -n 9 || exit 0
        while :; do
            apply_abnt2
            sleep 5
        done
        ;;
    *)
        apply_abnt2
        ;;
esac
EOF
    chmod 0755 "${target}"
  fi
}

ensure_panel_guard() {
  local target="${HOME}/.local/bin/omni-lxde-panel-guard.sh"
  mkdir -p "$(dirname "${target}")"
  cat >"${target}" <<'EOF'
#!/usr/bin/env bash
set -u

panel_height="${OMNI_LXPANEL_HEIGHT:-38}"

screen_size() {
  if command -v xrandr >/dev/null 2>&1; then
    xrandr --current 2>/dev/null | awk '
      / connected/ {
        for (i = 1; i <= NF; i++) {
          if ($i ~ /^[0-9]+x[0-9]+\+/) {
            split($i, p, /[x+]/)
            print p[1], p[2]
            exit
          }
        }
      }'
    return
  fi
  if command -v xdpyinfo >/dev/null 2>&1; then
    xdpyinfo 2>/dev/null | awk '/dimensions:/ { split($2, p, "x"); print p[1], p[2]; exit }'
  fi
}

fix_once() {
  pgrep -u "${USER:-ubuntu}" -x lxpanel >/dev/null 2>&1 || setsid -f lxpanel --profile LXDE >/tmp/omni-dark-theme-lxpanel.log 2>&1 || true
  command -v wmctrl >/dev/null 2>&1 || return 0
  set -- $(screen_size)
  [ "$#" -ge 2 ] || return 0
  width="$1"
  max_width="$(wmctrl -lG 2>/dev/null | awk '$0 ~ / panel$/ && $5 > max { max = $5 } END { print max + 0 }')"
  [ "${max_width:-0}" -ge $((width - 8)) ] || return 0
  command -v xdotool >/dev/null 2>&1 || return 0
  wmctrl -lG 2>/dev/null \
    | awk -v width="$width" '$0 ~ / panel$/ && $5 < width - 8 { print $1 }' \
    | while read -r id; do
        xdotool windowraise "$id" >/dev/null 2>&1 || true
      done
}

case "${1:-}" in
  --watch)
    lock_file="/tmp/omni-lxde-panel-guard-${USER:-ubuntu}.lock"
    exec 9>"$lock_file" || exit 0
    flock -n 9 || exit 0
    while :; do
      fix_once
      sleep 5
    done
    ;;
  *)
    fix_once
    ;;
esac
EOF
  chmod 0755 "${target}"
}

ensure_network_tray() {
  local target="${HOME}/.local/bin/omni-network-tray.py"
  mkdir -p "$(dirname "${target}")"
  cat >"${target}" <<'PY'
#!/usr/bin/env python3
import fcntl
import os
import re
import socket
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


ORACLE_IFACE = os.environ.get("OMNI_ORACLE_IFACE") or ""
WG_IFACE = os.environ.get("OMNI_WG_IFACE", "wg0")
ICON_DIR = os.path.expanduser("~/.local/share/icons/omni-dark-theme")
LOCK_PATH = f"/tmp/omni-network-tray-{os.environ.get('USER', 'ubuntu')}.lock"


def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def default_iface():
    out = run(["ip", "route", "show", "default"])
    for line in out.splitlines():
        parts = line.split()
        if "dev" in parts:
            return parts[parts.index("dev") + 1]
    return "enp0s6"


def iface_state(iface):
    try:
        return open(f"/sys/class/net/{iface}/operstate", encoding="utf-8").read().strip()
    except Exception:
        return "missing"


def iface_ipv4(iface):
    out = run(["ip", "-br", "-4", "addr", "show", "dev", iface])
    parts = out.split()
    return parts[2] if len(parts) >= 3 else "-"


def default_gw(iface):
    out = run(["ip", "route", "show", "default", "dev", iface])
    for line in out.splitlines():
        parts = line.split()
        if "via" in parts:
            return parts[parts.index("via") + 1]
    return "-"


def wg_rows(kind):
    out = run(["sudo", "-n", "wg", "show", WG_IFACE, kind])
    rows = []
    for line in out.splitlines():
        parts = line.split()
        if parts:
            rows.append(parts)
    return rows


def fmt_age(epoch_text):
    try:
        epoch = int(epoch_text)
    except Exception:
        return "sem handshake"
    if epoch <= 0:
        return "sem handshake"
    delta = max(0, int(time.time()) - epoch)
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}min"
    return f"{delta // 3600}h"


def fmt_bytes(value):
    try:
        size = float(value)
    except Exception:
        return "-"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.1f}{units[idx]}"


def network_status():
    oracle_iface = ORACLE_IFACE or default_iface()
    oracle_state = iface_state(oracle_iface)
    oracle_ip = iface_ipv4(oracle_iface)
    oracle_gw = default_gw(oracle_iface)
    oracle_ok = oracle_state == "up" and oracle_ip != "-"

    wg_state = iface_state(WG_IFACE)
    wg_ip = iface_ipv4(WG_IFACE)
    hs_rows = wg_rows("latest-handshakes")
    tx_rows = wg_rows("transfer")
    active_ages = [fmt_age(row[1]) for row in hs_rows if len(row) >= 2 and row[1] != "0"]
    wg_active = bool(active_ages) and wg_state in ("up", "unknown")
    transfer = ""
    if tx_rows and len(tx_rows[0]) >= 3:
        transfer = f" rx {fmt_bytes(tx_rows[0][1])} / tx {fmt_bytes(tx_rows[0][2])}"

    hostname = socket.gethostname()
    oracle_line = f"Oracle OCI: {'OK' if oracle_ok else 'ERRO'} {oracle_iface} {oracle_state} {oracle_ip} gw {oracle_gw}"
    wg_line = f"WireGuard: {'OK' if wg_active else 'ERRO'} {WG_IFACE} {wg_state} {wg_ip}; peers ativos {len(active_ages)}/{len(hs_rows)}"
    if active_ages:
        wg_line += f"; ultimo {min(active_ages, key=len)}"
    wg_line += transfer
    tooltip = f"{hostname}\n{oracle_line}\n{wg_line}\nNetworkManager: ignorado; interfaces unmanaged"

    if oracle_ok and wg_active:
        icon_file = os.path.join(ICON_DIR, "omni-network-ok.svg")
        fallback_icon = "network-vpn"
    elif oracle_ok:
        icon_file = os.path.join(ICON_DIR, "omni-network-wired.svg")
        fallback_icon = "network-wired"
    else:
        icon_file = os.path.join(ICON_DIR, "omni-network-error.svg")
        fallback_icon = "network-error"
    return icon_file if os.path.exists(icon_file) else "", fallback_icon, tooltip, oracle_ok, wg_active


class OmniNetworkTray:
    def __init__(self):
        self.icon = Gtk.StatusIcon()
        self.icon.set_title("Omni Network")
        self.icon.set_visible(True)
        self.icon.connect("popup-menu", self.popup_menu)
        self.icon.connect("activate", self.refresh)
        self.menu = Gtk.Menu()
        self.refresh_item = Gtk.MenuItem(label="Atualizar")
        self.refresh_item.connect("activate", self.refresh)
        self.quit_item = Gtk.MenuItem(label="Sair")
        self.quit_item.connect("activate", lambda *_: Gtk.main_quit())
        self.menu.append(self.refresh_item)
        self.menu.append(self.quit_item)
        self.menu.show_all()
        self.refresh()
        GLib.timeout_add_seconds(10, self.refresh)

    def popup_menu(self, icon, button, activate_time):
        self.menu.popup(None, None, None, None, button, activate_time)

    def refresh(self, *_):
        icon_file, fallback_icon, tooltip, _, _ = network_status()
        if icon_file:
            self.icon.set_from_file(icon_file)
        else:
            self.icon.set_from_icon_name(fallback_icon)
        self.icon.set_tooltip_text(tooltip)
        return True


def main():
    if "--once" in sys.argv:
        icon_file, fallback_icon, tooltip, oracle_ok, wg_active = network_status()
        print(f"icon={os.path.basename(icon_file) if icon_file else fallback_icon}")
        print(tooltip)
        return 0 if oracle_ok and wg_active else 1

    lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0

    Gtk.init(sys.argv)
    OmniNetworkTray()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
  chmod 0755 "${target}"
}

ensure_autostart_line() {
  local file="$1"
  local line="$2"
  grep -Fxq "${line}" "${file}" || printf '%s\n' "${line}" >>"${file}"
}

install_network_icons() {
  local icon_dir="${HOME}/.local/share/icons/omni-dark-theme"
  mkdir -p "${icon_dir}"
  local icon
  for icon in omni-network-ok.svg omni-network-wired.svg omni-network-error.svg; do
    if [ -f "${CONFIG_DIR}/${icon}" ]; then
      install -m 0644 "${CONFIG_DIR}/${icon}" "${icon_dir}/${icon}"
    else
      warn "Icone ausente em ${CONFIG_DIR}/${icon}"
    fi
  done
  ok "Icones Omni Network dark instalados"
}

disable_networkmanager_applet() {
  local override="${HOME}/.config/autostart/nm-applet.desktop"
  mkdir -p "$(dirname "${override}")"
  cat >"${override}" <<'EOF'
[Desktop Entry]
Type=Application
Name=Network
Comment=Disabled by Omni Dark Theme; OCI and WireGuard are unmanaged by NetworkManager
Exec=nm-applet
Hidden=true
NoDisplay=true
X-GNOME-Autostart-enabled=false
X-Omni-Managed=dark-theme-ubuntu
EOF
  ok "nm-applet XDG autostart desabilitado"
}

apply_autostart() {
  local file="${HOME}/.config/lxsession/${PROFILE}/autostart"
  mkdir -p "$(dirname "${file}")"
  touch "${file}"
  ensure_abnt2_watchdog
  ensure_panel_guard
  install_network_icons
  ensure_network_tray
  disable_networkmanager_applet

  sed -i \
    -e '/^@lxpanel --profile LXDE$/d' \
    -e '/^@pcmanfm --desktop --profile LXDE$/d' \
    -e '/^@xscreensaver -no-splash$/d' \
    -e '/^@nm-applet\b/d' \
    -e '\#^@.*/omni-network-tray\.py#d' \
    -e '/^@copyq\b/d' \
    -e '/^@setxkbmap\b/d' \
    -e '/^@xmodmap\b/d' \
    -e '\#^@.*/omni-dark-system-env\.sh#d' \
    -e '\#^@.*/setxkbmap-abnt2\.sh#d' \
    -e '\#^@.*/omni-lxde-panel-guard\.sh#d' \
    "${file}"

  ensure_autostart_line "${file}" "@lxpanel --profile ${PROFILE}"
  ensure_autostart_line "${file}" "@pcmanfm --desktop --profile ${PROFILE}"
  ensure_autostart_line "${file}" "@xscreensaver -no-splash"
  ensure_autostart_line "${file}" "@copyq --start-server"
  ensure_autostart_line "${file}" "@${HOME}/.local/bin/omni-network-tray.py"
  ensure_autostart_line "${file}" "@${HOME}/.local/bin/omni-dark-system-env.sh --restart-portal"
  ensure_autostart_line "${file}" "@${HOME}/.local/bin/setxkbmap-abnt2.sh --watch"
  ensure_autostart_line "${file}" "@${HOME}/.local/bin/omni-lxde-panel-guard.sh --watch"
  ok "LXDE autostart saneado"
}

desktop_file_exists() {
  local id="$1"
  [ -f "${HOME}/.local/share/applications/${id}" ] && return 0
  [ -f "/usr/local/share/applications/${id}" ] && return 0
  [ -f "/usr/share/applications/${id}" ] && return 0
  [ -f "/var/lib/snapd/desktop/applications/${id}" ] && return 0
  return 1
}

add_launcher_if_exists() {
  local -n target="$1"
  shift
  local id
  for id in "$@"; do
    if desktop_file_exists "${id}"; then
      target+=("${id}")
      return 0
    fi
  done
  return 1
}

lxpanel_plugin_exists() {
  local name="$1"
  local dir
  for dir in /usr/lib/*/lxpanel/plugins /usr/lib/lxpanel/plugins; do
    [ -f "${dir}/${name}.so" ] && return 0
  done
  return 1
}

write_panel() {
  local panels_dir="${HOME}/.config/lxpanel/${PROFILE}/panels"
  local background_panel="${panels_dir}/00-background"
  local panel="${panels_dir}/panel"
  local status_panel="${panels_dir}/status-right"
  local panel_bg_file="${HOME}/.config/lxpanel/${PROFILE}/panel-background.xpm"
  local status_width="${OMNI_LXPANEL_STATUS_WIDTH:-300}"
  mkdir -p "${panels_dir}"
  cat >"${panel_bg_file}" <<EOF
/* XPM */
static char * omni_lxpanel_background[] = {
"1 1 1 1",
"  c ${PANEL_BG}",
" "
};
EOF

  local stale_dir=""
  while IFS= read -r stale_panel; do
    if [ -z "${stale_dir}" ]; then
      stale_dir="${BACKUP_DIR:-${BACKUP_BASE}/$(date +%Y%m%d-%H%M%S)}/lxpanel-stale-panels"
      mkdir -p "${stale_dir}"
    fi
    mv "${stale_panel}" "${stale_dir}/"
  done < <(find "${panels_dir}" -maxdepth 1 -type f ! -name 00-background ! -name panel ! -name status-right)

  rm -f "${background_panel}" "${panel}" "${status_panel}"

  local launchers=()
  add_launcher_if_exists launchers pcmanfm.desktop
  add_launcher_if_exists launchers chromium.desktop chromium_chromium.desktop google-chrome.desktop firefox.desktop
  add_launcher_if_exists launchers code.desktop
  add_launcher_if_exists launchers sublime_text.desktop
  add_launcher_if_exists launchers codex-desktop.desktop
  add_launcher_if_exists launchers hermes-os-dev.desktop
  add_launcher_if_exists launchers lxterminal.desktop
  add_launcher_if_exists launchers obsidian.desktop
  add_launcher_if_exists launchers org.gnome.Screenshot.desktop gnome-screenshot.desktop

  cat >"${background_panel}" <<EOF
# lxpanel full-width background panel. Managed by omni-srv-admin/dark-theme-ubuntu.

Global {
  edge=bottom
  align=left
  margin=0
  widthtype=percent
  width=100
  height=38
  transparent=0
  tintcolor=${PANEL_BG}
  alpha=0
  setdocktype=1
  setpartialstrut=1
  autohide=0
  heightwhenhidden=0
  usefontcolor=1
  fontcolor=#f8fafc
  background=1
  backgroundfile=${panel_bg_file}
}
Plugin {
  type=space
  expand=1
  Config {
    Size=2
  }
}
EOF

  {
    cat <<EOF
# lxpanel <profile> config file. Managed by omni-srv-admin/dark-theme-ubuntu.

Global {
  edge=bottom
  align=left
  margin=0
  widthtype=percent
  width=100
  height=38
  transparent=0
  tintcolor=${PANEL_BG}
  alpha=0
  setdocktype=1
  setpartialstrut=0
  autohide=0
  heightwhenhidden=0
  usefontcolor=1
  fontcolor=#f8fafc
  background=1
  backgroundfile=${panel_bg_file}
}
EOF

    cat <<'EOF'
Plugin {
  type=space
  Config {
    Size=2
  }
}
Plugin {
  type=menu
  Config {
    image=/usr/share/lxde/images/lxde-icon.png
    system {
    }
    separator {
    }
    item {
      command=run
    }
    separator {
    }
    item {
      image=gnome-logout
      command=logout
    }
  }
}
Plugin {
  type=launchbar
  Config {
EOF

    local id
    for id in "${launchers[@]}"; do
      cat <<EOF
    Button {
      id=${id}
    }
EOF
    done

    cat <<'EOF'
  }
}
Plugin {
  type=space
  Config {
    Size=4
  }
}
Plugin {
  type=wincmd
  Config {
    Button1=iconify
    Button2=shade
  }
}
Plugin {
  type=space
  Config {
    Size=4
  }
}
Plugin {
  type=pager
  Config {
  }
}
Plugin {
  type=space
  Config {
    Size=4
  }
}
Plugin {
  type=taskbar
  expand=0
  Config {
    tooltips=1
    IconsOnly=0
    AcceptSkipPager=1
    ShowIconified=1
    ShowMapped=1
    ShowAllDesks=0
    UseMouseWheel=1
    UseUrgencyHint=1
    FlatButton=1
    MaxTaskWidth=120
    spacing=1
  }
}
EOF
  } >"${panel}"

  {
    cat <<EOF
# lxpanel status panel. Managed by omni-srv-admin/dark-theme-ubuntu.

Global {
  edge=bottom
  align=right
  margin=0
  widthtype=pixel
  width=${status_width}
  height=38
  transparent=0
  tintcolor=${PANEL_BG}
  alpha=0
  setdocktype=1
  setpartialstrut=0
  autohide=0
  heightwhenhidden=0
  usefontcolor=1
  fontcolor=#f8fafc
  background=1
  backgroundfile=${panel_bg_file}
}
EOF

    cat <<'EOF'
Plugin {
  type=space
  Config {
    Size=6
  }
}
Plugin {
  type=cpu
  Config {
  }
}
Plugin {
  type=space
  Config {
    Size=4
  }
}
Plugin {
  type=xkb
  Config {
    Model=pc105
    LayoutsList=br
    VariantsList=abnt2
    ToggleOpt=grp:shift_caps_toggle
    KeepSysLayouts=1
    DisplayType=0
    FlagSize=3
  }
}
Plugin {
  type=tray
  Config {
  }
}
EOF

    if lxpanel_plugin_exists volume; then
      cat <<'EOF'
Plugin {
  type=volume
  Config {
  }
}
EOF
    elif lxpanel_plugin_exists volumealsa; then
      cat <<'EOF'
Plugin {
  type=volumealsa
  Config {
  }
}
EOF
    fi

    cat <<'EOF'
Plugin {
  type=dclock
  Config {
    ClockFmt=%R
    TooltipFmt=%A %x
    BoldFont=0
    IconOnly=0
    CenterText=0
  }
}
Plugin {
  type=launchbar
  Config {
    Button {
      id=lxde-screenlock.desktop
    }
    Button {
      id=lxde-logout.desktop
    }
  }
}
EOF
  } >"${status_panel}"

  ok "LXPanel refeito com fundo full-width, painel esquerdo e status-right"
}

configure_electron_keyboard() {
  mkdir -p "${HOME}/.config/Code/User"
  local vscode="${HOME}/.config/Code/User/settings.json"
  if need_cmd python3; then
    python3 - "${vscode}" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {}
except Exception:
    data = {}
data["keyboard.dispatch"] = "keyCode"
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  fi

  local flags_file
  for flags_file in "${HOME}/.config/chromium-flags.conf" "${HOME}/.config/brave-flags.conf" "${HOME}/.config/electron-flags.conf"; do
    touch "${flags_file}"
    grep -Fxq -- "--gtk-version=4" "${flags_file}" || printf '%s\n' "--gtk-version=4" >>"${flags_file}"
  done
  ok "AltGr/Electron preservado"
}

configure_sublime_defaults() {
  if [ -f /usr/share/applications/sublime_text.desktop ]; then
    xdg-mime default sublime_text.desktop text/plain >/dev/null 2>&1 || true
    run_sudo sed -i 's/Categories=TextEditor;Development;/Categories=Utility;TextEditor;Development;/g' /usr/share/applications/sublime_text.desktop
    ok "Sublime configurado como editor padrao de texto"
  fi
}

configure_zsh() {
  [ "${WITH_ZSH}" -eq 1 ] || return 0
  if ! need_cmd zsh; then
    warn "zsh ausente; rode com --install-packages"
    return 0
  fi

  if [ ! -d "${HOME}/.oh-my-zsh" ] && need_cmd curl; then
    RUNZSH=no CHSH=no KEEP_ZSHRC=yes sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" >/dev/null
  fi

  local custom="${ZSH_CUSTOM:-${HOME}/.oh-my-zsh/custom}"
  if [ -d "${custom}" ] && need_cmd git; then
    [ -d "${custom}/plugins/zsh-syntax-highlighting" ] || git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "${custom}/plugins/zsh-syntax-highlighting" >/dev/null 2>&1 || true
    [ -d "${custom}/plugins/zsh-autosuggestions" ] || git clone https://github.com/zsh-users/zsh-autosuggestions "${custom}/plugins/zsh-autosuggestions" >/dev/null 2>&1 || true
  fi

  if [ ! -f "${HOME}/.zshrc" ]; then
    install -m 0644 "${CONFIG_DIR}/.zshrc" "${HOME}/.zshrc"
  elif ! grep -q "omni dark theme zsh block" "${HOME}/.zshrc"; then
    cat >>"${HOME}/.zshrc" <<'EOF'

# omni dark theme zsh block
export ZSH_THEME="${ZSH_THEME:-robbyrussell}"
if type git_prompt_info >/dev/null 2>&1; then
  PROMPT='%{$fg[green]%}%n@%m%{$reset_color%}:%{$fg[blue]%}%~%{$reset_color%} $(git_prompt_info)➜ '
fi
EOF
  fi

  if [ "$(basename "${SHELL:-}")" != "zsh" ] && need_cmd chsh; then
    run_sudo chsh -s "$(command -v zsh)" "${USER}" || warn "Nao consegui trocar shell padrao para zsh"
  fi
  ok "Zsh verificado"
}

has_live_display() {
  [ -n "${DISPLAY:-}" ] || return 1
  need_cmd xdpyinfo || return 1
  xdpyinfo >/dev/null 2>&1
}

screen_width() {
  if need_cmd xrandr; then
    xrandr --current 2>/dev/null | awk '
      / connected/ {
        for (i = 1; i <= NF; i++) {
          if ($i ~ /^[0-9]+x[0-9]+\+/) {
            split($i, p, /[x+]/)
            print p[1]
            exit
          }
        }
      }'
    return
  fi
  if need_cmd xdpyinfo; then
    xdpyinfo 2>/dev/null | awk '/dimensions:/ { split($2, p, "x"); print p[1]; exit }'
  fi
}

force_panel_geometry() {
  if ! has_live_display || ! need_cmd wmctrl; then
    return 0
  fi
  "${HOME}/.local/bin/omni-lxde-panel-guard.sh" || true
}

restart_session_components() {
  if ! has_live_display; then
    warn "Sem DISPLAY X acessivel; as mudancas entram no proximo login"
    return 0
  fi

  log "Recarregando LXDE no DISPLAY=${DISPLAY}. Isso pode piscar a area de trabalho, mas nao reinicia XRDP."
  setxkbmap -model pc105 -layout br -variant abnt2 -option -option lv3:ralt_switch >/dev/null 2>&1 || true
  openbox --reconfigure >/dev/null 2>&1 || true
  pkill -x lxpanel >/dev/null 2>&1 || true
  sleep 1
  setsid -f lxpanel --profile "${PROFILE}" >/tmp/omni-dark-theme-lxpanel.log 2>&1 || true
  sleep 2
  if ! pgrep -u "${USER}" -x lxpanel >/dev/null; then
    warn "lxpanel nao permaneceu rodando; veja /tmp/omni-dark-theme-lxpanel.log"
  fi
  force_panel_geometry
  if need_cmd pcmanfm; then
    pcmanfm --desktop-off >/dev/null 2>&1 || true
    sleep 1
    setsid -f pcmanfm --desktop --profile "${PROFILE}" >/tmp/omni-dark-theme-pcmanfm.log 2>&1 || true
    sleep 1
    pgrep -u "${USER}" -x pcmanfm >/dev/null || setsid -f pcmanfm --desktop --profile "${PROFILE}" >/tmp/omni-dark-theme-pcmanfm.log 2>&1 || true
  fi
  pkill -x nm-applet >/dev/null 2>&1 || true
  pkill -f "${HOME}/.local/bin/omni-network-tray.py" >/dev/null 2>&1 || true
  sleep 1
  DISPLAY="${DISPLAY}" setsid -f "${HOME}/.local/bin/omni-network-tray.py" >/tmp/omni-network-tray.log 2>&1 || true
  pgrep -u "${USER}" -x copyq >/dev/null || nohup copyq --start-server >/dev/null 2>&1 &
  ok "Sessao LXDE recarregada"
}

apply_all() {
  backup_current
  [ "${INSTALL_PACKAGES}" -eq 1 ] && install_packages
  [ "${WITH_SUBLIME}" -eq 1 ] && install_sublime
  install_fonts
  apply_gtk
  apply_system_dark
  apply_openbox
  apply_pcmanfm_desktop
  apply_autostart
  write_panel
  configure_electron_keyboard
  configure_sublime_defaults
  configure_zsh
  [ "${RESTART_SESSION}" -eq 1 ] && restart_session_components
}

check_contains() {
  local file="$1"
  local needle="$2"
  local label="$3"
  if [ -f "${file}" ] && grep -Fq "${needle}" "${file}"; then
    ok "${label}"
    return 0
  fi
  fail "${label}"
  return 1
}

check_not_contains() {
  local file="$1"
  local needle="$2"
  local label="$3"
  if [ -f "${file}" ] && grep -Fq "${needle}" "${file}"; then
    fail "${label}"
    return 1
  fi
  ok "${label}"
  return 0
}

check_gsettings_value() {
  local schema="$1"
  local key="$2"
  local expected="$3"
  local label="$4"
  local value=""
  local attempt
  for attempt in 1 2 3; do
    if need_cmd gsettings && gsettings list-schemas | grep -Fxq "${schema}"; then
      value="$(gsettings get "${schema}" "${key}" 2>/dev/null || true)"
      if [ "${value}" = "${expected}" ]; then
        ok "${label}"
        return 0
      fi
    fi
    sleep 1
  done
  fail "${label}"
  return 1
}

check_command_output_contains() {
  local label="$1"
  local needle="$2"
  shift 2
  local output
  output="$("$@" 2>/dev/null || true)"
  if grep -Fq "${needle}" <<<"${output}"; then
    ok "${label}"
    return 0
  fi
  fail "${label}"
  return 1
}

check_portal_color_scheme() {
  if ! has_live_display || ! need_cmd gdbus || ! need_cmd timeout; then
    warn "Portal color-scheme nao validado sem DISPLAY/gdbus/timeout"
    return 0
  fi
  local output
  output="$(timeout 8s gdbus call --session --dest org.freedesktop.portal.Desktop --object-path /org/freedesktop/portal/desktop --method org.freedesktop.portal.Settings.Read org.freedesktop.appearance color-scheme 2>/dev/null || true)"
  if grep -Fq "uint32 1" <<<"${output}"; then
    ok "Portal org.freedesktop.appearance color-scheme=prefer-dark"
    return 0
  fi
  fail "Portal org.freedesktop.appearance color-scheme=prefer-dark; output=${output:-timeout/empty}"
  return 1
}

validate() {
  local errors=0
  local desktop="${HOME}/.config/lxsession/${PROFILE}/desktop.conf"
  local gtk3="${HOME}/.config/gtk-3.0/settings.ini"
  local background_panel="${HOME}/.config/lxpanel/${PROFILE}/panels/00-background"
  local panel="${HOME}/.config/lxpanel/${PROFILE}/panels/panel"
  local status_panel="${HOME}/.config/lxpanel/${PROFILE}/panels/status-right"
  local autostart="${HOME}/.config/lxsession/${PROFILE}/autostart"
  local nm_override="${HOME}/.config/autostart/nm-applet.desktop"
  local openbox_rc="${HOME}/.config/openbox/lxde-rc.xml"
  local pcmanfm="${HOME}/.config/pcmanfm/${PROFILE}/desktop-items-0.conf"
  local env_file="${HOME}/.config/environment.d/10-omni-dark.conf"
  local portal_conf="${HOME}/.config/xdg-desktop-portal/lxde-portals.conf"

  check_contains "${desktop}" "sNet/ThemeName=Greybird-dark" "LXSession usa Greybird-dark" || errors=$((errors + 1))
  check_contains "${gtk3}" "gtk-application-prefer-dark-theme=1" "GTK3 prefer-dark habilitado" || errors=$((errors + 1))
  check_gsettings_value org.gnome.desktop.interface color-scheme "'prefer-dark'" "GSettings color-scheme prefer-dark" || errors=$((errors + 1))
  check_gsettings_value org.gnome.desktop.interface gtk-theme "'Greybird-dark'" "GSettings gtk-theme Greybird-dark" || errors=$((errors + 1))
  check_contains "${env_file}" "GTK_THEME=Greybird-dark" "environment.d exporta GTK_THEME dark" || errors=$((errors + 1))
  check_contains "${env_file}" "QT_QPA_PLATFORMTHEME=gtk3" "environment.d faz Qt seguir GTK" || errors=$((errors + 1))
  check_contains "${HOME}/.xsessionrc" "export GTK_THEME=\"Greybird-dark\"" "xsessionrc exporta GTK_THEME dark" || errors=$((errors + 1))
  check_contains "${portal_conf}" "org.freedesktop.impl.portal.Settings=gtk" "Portal LXDE usa backend GTK para Settings" || errors=$((errors + 1))
  check_portal_color_scheme || errors=$((errors + 1))
  if has_live_display && need_cmd gtk-query-settings; then
    check_command_output_contains "GTK3 runtime ve prefer-dark TRUE" "gtk-application-prefer-dark-theme: TRUE" env DISPLAY="${DISPLAY}" GTK_THEME=Greybird-dark gtk-query-settings || errors=$((errors + 1))
  fi
  if has_live_display && need_cmd gtk4-query-settings; then
    check_command_output_contains "GTK4 runtime ve tema Greybird-dark" 'gtk-theme-name: "Greybird-dark"' env DISPLAY="${DISPLAY}" GTK_THEME=Greybird-dark gtk4-query-settings || errors=$((errors + 1))
  fi
  if [ -f "${HOME}/.config/gtk-3.0/gtk.css" ] && grep -Fq '!important' "${HOME}/.config/gtk-3.0/gtk.css"; then
    fail "GTK3 CSS sem sintaxe legada invalida"
    errors=$((errors + 1))
  else
    ok "GTK3 CSS sem sintaxe legada invalida"
  fi
  check_contains "${HOME}/.gtkrc-2.0" "gtk-theme-name=\"Greybird-dark\"" "GTK2 usa Greybird-dark" || errors=$((errors + 1))
  check_contains "${openbox_rc}" "<name>Dark-Onyx</name>" "Openbox usa Dark-Onyx" || errors=$((errors + 1))
  check_contains "${background_panel}" "background=1" "LXPanel usa asset de fundo escuro" || errors=$((errors + 1))
  check_contains "${background_panel}" "panel-background.xpm" "LXPanel referencia panel-background.xpm" || errors=$((errors + 1))
  check_contains "${background_panel}" "expand=1" "LXPanel tem fundo full-width elastico" || errors=$((errors + 1))
  check_contains "${status_panel}" "type=tray" "LXPanel status-right tem system tray" || errors=$((errors + 1))
  check_contains "${status_panel}" "type=cpu" "LXPanel status-right tem mini monitor CPU" || errors=$((errors + 1))
  check_contains "${status_panel}" "type=xkb" "LXPanel status-right tem indicador ABNT2" || errors=$((errors + 1))
  check_contains "${panel}" "type=taskbar" "LXPanel tem taskbar" || errors=$((errors + 1))
  if grep -Eq 'type=volume|type=volumealsa' "${status_panel}" 2>/dev/null; then
    ok "LXPanel status-right tem controle de volume compativel"
  else
    fail "LXPanel status-right tem controle de volume compativel"
    errors=$((errors + 1))
  fi
  check_contains "${status_panel}" "type=dclock" "LXPanel status-right tem relogio" || errors=$((errors + 1))
  check_contains "${autostart}" "@lxpanel --profile ${PROFILE}" "autostart inicia lxpanel" || errors=$((errors + 1))
  check_contains "${autostart}" "@pcmanfm --desktop --profile ${PROFILE}" "autostart inicia desktop PCManFM" || errors=$((errors + 1))
  check_contains "${autostart}" "@${HOME}/.local/bin/omni-network-tray.py" "autostart inicia indicador Omni Network" || errors=$((errors + 1))
  check_not_contains "${autostart}" "@nm-applet" "autostart nao inicia nm-applet unmanaged" || errors=$((errors + 1))
  check_contains "${nm_override}" "Hidden=true" "XDG autostart desabilita nm-applet unmanaged" || errors=$((errors + 1))
  check_contains "${autostart}" "@${HOME}/.local/bin/omni-dark-system-env.sh --restart-portal" "autostart aplica system dark/portal" || errors=$((errors + 1))
  check_contains "${autostart}" "@${HOME}/.local/bin/setxkbmap-abnt2.sh --watch" "autostart fixa ABNT2" || errors=$((errors + 1))
  check_contains "${pcmanfm}" "desktop_bg=${DESKTOP_BG}" "PCManFM desktop escuro" || errors=$((errors + 1))

  if need_cmd fc-match && fc-match 'SF Pro Display' | grep -Fq 'SF-Pro-Display'; then
    ok "SF Pro Display disponivel"
  else
    fail "SF Pro Display disponivel"
    errors=$((errors + 1))
  fi

  if [ -x "${HOME}/.local/bin/omni-network-tray.py" ]; then
    if "${HOME}/.local/bin/omni-network-tray.py" --once >/tmp/omni-network-tray-validate.log 2>&1; then
      ok "Omni Network detecta Oracle OCI e WireGuard"
    else
      fail "Omni Network detecta Oracle OCI e WireGuard; veja /tmp/omni-network-tray-validate.log"
      errors=$((errors + 1))
    fi
  else
    fail "Omni Network instalado"
    errors=$((errors + 1))
  fi

  if [ -f "${HOME}/.local/share/icons/omni-dark-theme/omni-network-ok.svg" ]; then
    ok "Omni Network usa icone dark custom"
  else
    fail "Omni Network usa icone dark custom"
    errors=$((errors + 1))
  fi

  if has_live_display; then
    if pgrep -u "${USER}" -x nm-applet >/dev/null 2>&1; then
      if [ "${RESTART_SESSION}" -eq 1 ]; then
        fail "nm-applet runtime ausente"
        errors=$((errors + 1))
      else
        warn "nm-applet ainda roda nesta sessao; use repair --restart-session para trocar pelo Omni Network sem reiniciar XRDP"
      fi
    else
      ok "nm-applet runtime ausente"
    fi
  fi

  if need_cmd xmllint && [ -f "${openbox_rc}" ]; then
    if xmllint --noout "${openbox_rc}" >/dev/null 2>&1; then
      ok "Openbox XML valido"
    else
      fail "Openbox XML valido"
      errors=$((errors + 1))
    fi
  fi

  if has_live_display && need_cmd wmctrl; then
    local panel_count
    panel_count="$(wmctrl -lG 2>/dev/null | awk '$0 ~ / panel$/ { count++ } END { print count + 0 }')"
    if [ "${panel_count}" -ge 3 ]; then
      ok "LXPanel runtime tem fundo + painel esquerdo + status-right"
    else
      fail "LXPanel runtime tem fundo + painel esquerdo + status-right; count=${panel_count}"
      errors=$((errors + 1))
    fi

    local screen_w max_panel_w
    screen_w="$(screen_width || true)"
    max_panel_w="$(wmctrl -lG 2>/dev/null | awk '$0 ~ / panel$/ && $5 > max { max = $5 } END { print max + 0 }')"
    if [[ "${screen_w}" =~ ^[0-9]+$ ]] && [ "${max_panel_w:-0}" -ge $((screen_w - 8)) ]; then
      ok "LXPanel runtime cobre toda largura inferior"
    else
      fail "LXPanel runtime cobre toda largura inferior; screen=${screen_w:-?} max_panel=${max_panel_w:-0}"
      errors=$((errors + 1))
    fi
  fi

  if [ "${errors}" -gt 0 ]; then
    fail "${errors} validacao(oes) falharam"
    return 1
  fi
  ok "Dark Ubuntu validado"
}

status() {
  log "Dark Ubuntu LXDE/XRDP"
  log "Host: $(hostname)"
  log "OS: $(. /etc/os-release && printf '%s' "${PRETTY_NAME}")"
  log "User: ${USER:-unknown}"
  log "Display: ${DISPLAY:-none}"
  log "Desktop: ${XDG_CURRENT_DESKTOP:-unknown}/${DESKTOP_SESSION:-unknown}"
  log "Module: ${MODULE_DIR}"
  log ""
  local f
  for f in \
    "${HOME}/.config/lxsession/${PROFILE}/desktop.conf" \
    "${HOME}/.config/gtk-3.0/settings.ini" \
    "${HOME}/.config/environment.d/10-omni-dark.conf" \
    "${HOME}/.config/xdg-desktop-portal/lxde-portals.conf" \
    "${HOME}/.config/autostart/nm-applet.desktop" \
    "${HOME}/.gtkrc-2.0" \
    "${HOME}/.xsessionrc" \
    "${HOME}/.local/share/icons/omni-dark-theme/omni-network-ok.svg" \
    "${HOME}/.config/lxpanel/${PROFILE}/panel-background.xpm" \
    "${HOME}/.config/lxpanel/${PROFILE}/panels/00-background" \
    "${HOME}/.config/lxpanel/${PROFILE}/panels/panel" \
    "${HOME}/.config/lxpanel/${PROFILE}/panels/status-right" \
    "${HOME}/.config/openbox/lxde-rc.xml" \
    "${HOME}/.config/pcmanfm/${PROFILE}/desktop-items-0.conf" \
    "${HOME}/.config/lxsession/${PROFILE}/autostart"; do
    if [ -e "${f}" ]; then
      printf 'OK      %s\n' "${f}"
    else
      printf 'MISSING %s\n' "${f}"
    fi
  done
  log ""
  validate || true
}

restore_latest() {
  local source="${1:-}"
  if [ -z "${source}" ]; then
    source="$(find "${BACKUP_BASE}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -n 1 || true)"
  fi
  if [ -z "${source}" ] || [ ! -d "${source}" ]; then
    fail "Nenhum backup encontrado em ${BACKUP_BASE}"
    return 1
  fi

  local rel
  for rel in \
    "home/${USER}/.gtkrc-2.0" \
    "home/${USER}/.zshrc" \
    "home/${USER}/.config/gtk-3.0/settings.ini" \
    "home/${USER}/.config/gtk-3.0/gtk.css" \
    "home/${USER}/.config/environment.d/10-omni-dark.conf" \
    "home/${USER}/.config/xdg-desktop-portal/lxde-portals.conf" \
    "home/${USER}/.config/autostart/nm-applet.desktop" \
    "home/${USER}/.config/lxsession/${PROFILE}/desktop.conf" \
    "home/${USER}/.config/lxsession/${PROFILE}/autostart" \
    "home/${USER}/.config/lxpanel/${PROFILE}/panel-background.xpm" \
    "home/${USER}/.config/lxpanel/${PROFILE}/panels/00-background" \
    "home/${USER}/.config/lxpanel/${PROFILE}/panels/panel" \
    "home/${USER}/.config/lxpanel/${PROFILE}/panels/status-right" \
    "home/${USER}/.config/openbox/lxde-rc.xml" \
    "home/${USER}/.config/pcmanfm/${PROFILE}/desktop-items-0.conf" \
    "home/${USER}/.xsessionrc" \
    "home/${USER}/.profile" \
    "home/${USER}/.local/share/icons/omni-dark-theme" \
    "home/${USER}/.config/Code/User/settings.json" \
    "home/${USER}/.config/chromium-flags.conf" \
    "home/${USER}/.config/brave-flags.conf" \
    "home/${USER}/.config/electron-flags.conf"; do
    if [ -e "${source}/${rel}" ]; then
      mkdir -p "$(dirname "/${rel}")"
      cp -a "${source}/${rel}" "/${rel}"
      ok "Restaurado /${rel}"
    fi
  done

  local nm_override="${HOME}/.config/autostart/nm-applet.desktop"
  local nm_backup="${source}/home/${USER}/.config/autostart/nm-applet.desktop"
  if [ ! -e "${nm_backup}" ] && [ -f "${nm_override}" ] && grep -Fq "X-Omni-Managed=dark-theme-ubuntu" "${nm_override}"; then
    rm -f "${nm_override}"
    ok "Removido override Omni de nm-applet"
  fi

  local icon_dir="${HOME}/.local/share/icons/omni-dark-theme"
  local icon_backup="${source}/home/${USER}/.local/share/icons/omni-dark-theme"
  if [ ! -e "${icon_backup}" ] && [ -d "${icon_dir}" ]; then
    rm -rf "${icon_dir}"
    ok "Removidos icones Omni Network"
  fi

  [ "${RESTART_SESSION}" -eq 1 ] && restart_session_components
}

parse_options() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --install-packages)
        INSTALL_PACKAGES=1
        ;;
      --with-sublime)
        WITH_SUBLIME=1
        ;;
      --with-zsh)
        WITH_ZSH=1
        ;;
      --restart-session)
        RESTART_SESSION=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        break
        ;;
    esac
    shift
  done
  REMAINING_ARGS=("$@")
}

main() {
  local command="${1:-status}"
  shift || true
  parse_options "$@"

  case "${command}" in
    status)
      status
      ;;
    validate)
      validate
      ;;
    apply)
      apply_all
      validate
      ;;
    repair)
      WITH_SUBLIME=0
      WITH_ZSH=0
      apply_all
      validate
      ;;
    restore-latest)
      restore_latest "${REMAINING_ARGS[0]:-}"
      validate || true
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      fail "Comando desconhecido: ${command}"
      usage
      exit 2
      ;;
  esac
}

main "$@"
