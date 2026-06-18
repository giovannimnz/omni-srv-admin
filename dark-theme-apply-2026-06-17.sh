#!/usr/bin/env bash
# Apply dark-theme-ubuntu/config_files/ to /home/horistic/ on HORISTIC-SRV-1.
# NO restart-session. Backup first to ~/.backups/dark-theme-apply-2026-06-17/.
set -u

SRC="/home/ubuntu/GitHub/omni-srv-admin/dark-theme-ubuntu/config_files"
BACKUP_ROOT="/home/horistic/.backups/dark-theme-apply-2026-06-17"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${BACKUP_ROOT}/${TS}"

PAIRS=(
  "gtkrc-2.0                                       /home/horistic/.gtkrc-2.0"
  "gtk-3.0-settings.ini                            /home/horistic/.config/gtk-3.0/settings.ini"
  "gtk-3.0.css                                     /home/horistic/.config/gtk-3.0/gtk.css"
  "desktop.conf                                    /home/horistic/.config/lxsession/LXDE/desktop.conf"
  "lxde-rc.xml                                     /home/horistic/.config/openbox/lxde-rc.xml"
  "panel                                           /home/horistic/.config/lxpanel/LXDE/panels/panel"
  "00-background                                   /home/horistic/.config/lxpanel/LXDE/panels/00-background"
  "status-right                                    /home/horistic/.config/lxpanel/LXDE/panels/status-right"
  "panel-background.xpm                            /home/horistic/.config/lxpanel/LXDE/panel-background.xpm"
  "omni-network-error.svg                          /home/horistic/.local/share/icons/omni-dark-theme/omni-network-error.svg"
  "omni-network-ok.svg                             /home/horistic/.local/share/icons/omni-dark-theme/omni-network-ok.svg"
  "omni-network-wired.svg                          /home/horistic/.local/share/icons/omni-dark-theme/omni-network-wired.svg"
)

mkdir -p "${BACKUP_DIR}"
echo "BACKUP_DIR=${BACKUP_DIR}"

# 1. Backup existing files
for line in "${PAIRS[@]}"; do
  src_name="${line%% *}"
  dst="${line##* }"
  if [ -e "${dst}" ]; then
    rel="${dst#/home/horistic/}"
    bdst="${BACKUP_DIR}/${rel}"
    mkdir -p "$(dirname "${bdst}")"
    cp -a "${dst}" "${bdst}"
    echo "BAK  ${dst}  ->  ${bdst}"
  else
    echo "SKIP ${dst} (missing)"
  fi
done

# 2. Apply: ensure parent dirs exist, then install -m 0644
APPLY_RC=0
for line in "${PAIRS[@]}"; do
  src_name="${line%% *}"
  dst="${line##* }"
  src="${SRC}/${src_name}"
  if [ ! -f "${src}" ]; then
    echo "FAIL  source missing: ${src}"
    APPLY_RC=1
    continue
  fi
  mkdir -p "$(dirname "${dst}")"
  if install -m 0644 "${src}" "${dst}"; then
    echo "APPLY ${dst}  <-  ${src}"
  else
    echo "FAIL  install: ${dst}"
    APPLY_RC=1
  fi
done

# 3. md5 after
echo
echo "=== md5 AFTER ==="
for line in "${PAIRS[@]}"; do
  src_name="${line%% *}"
  dst="${line##* }"
  if [ -e "${dst}" ]; then
    md5sum "${dst}"
  else
    echo "MISSING  ${dst}"
  fi
done

echo
echo "APPLY_RC=${APPLY_RC}"
exit ${APPLY_RC}
