# Ubuntu ARM64 XRDP Desktop Standard

Canonical standard for all Giovanni-managed Ubuntu ARM64 servers with human RDP/XRDP access:

- `atius-srv-1`
- `atius-srv-2`
- `atius-srv-3`
- `horistic-srv`

## Scope

Apply this standard to every Ubuntu 24.04+ ARM64 host that exposes an LXDE/XRDP desktop.

The standard has two required layers and one conditional desktop polish layer:

1. XRDP keyboard guard from `modules/xrdp-abnt2/`.
2. LXDE/XRDP dark desktop from `dark-theme-ubuntu/`.
3. If Obsidian is installed on the host, keep the same Obsidian desktop polish validated first on `atius-srv-1`: `titlebarStyle=native` plus the `obsidian-tray` wrapper that docks an existing window with `kdocker -b -q -w`.

## Ubuntu 24+ Default Contract

When a new remote server is Ubuntu 24.04+ and will expose a human XRDP
desktop, this baseline is mandatory by default.

Required inventory declaration:

```yaml
platform:
  os: ubuntu-24.04
  arch: arm64
  desktop: lxde-xrdp
modules:
  - xrdp-abnt2
notes:
  desktop_standard: "ubuntu-arm64-xrdp-desktop-standard is mandatory here."
```

Required operational contract:

1. The host has a repo clone at `~/GitHub/omni-srv-admin`.
2. `sudo omni xrdp-abnt2 install --yes` is the canonical persistent patch entrypoint.
3. `dark-theme-ubuntu/scripts/dark-themectl.sh repair --install-packages --restart-session` is the canonical LXDE/XRDP desktop repair path.
4. `xrdp` and `xrdp-sesman` remain `enabled` and `active`.
5. XRDP helper scripts and text assets remain `LF`, not `CRLF`.
6. `freerdp2-x11` remains installed so any host can run peer smoke via `xfreerdp`.
7. The APT/DPKG hook persists the keyboard fix across package operations.

Default acceptance criteria for any Ubuntu 24.04+ XRDP host:

- `python3 cli/omni/xrdp_abnt2.py validate --user "$USER"` returns `PASS`
- `command -v xfreerdp` resolves
- `systemctl is-enabled xrdp xrdp-sesman` returns `enabled`
- `systemctl is-active xrdp xrdp-sesman` returns `active`
- an XRDP session resolves to `br` / `abnt2`

## XRDP Keyboard

The keyboard standard is Brazilian Portuguese ABNT2 for every RDP layout sent by Windows clients used in this fleet.

Required mappings:

- `0x00000409` -> `br(abnt2)`
- `0x00010416` -> `br(abnt2)`
- `0x0000F010` -> `br(abnt2)`
- `0x0000080A` -> `br(abnt2)`

Required XRDP `0.9.24` scancode translation contract:

- the X server may report `evdev`, but `xrdp/lang.c` consumes `xfree86/base`
  keymap indexes in `km-*.ini`
- `Up=Key98`, `Left=Key100`, `Right=Key102`, `Down=Key104`
- `Insert=Key106`, `Delete=Key107`, `Print Screen=Key111`
- physical ABNT_C1 slash key is `Key123` with `/`, `?`, `°`, `¿`
- do not validate extended keys against the live evdev offsets
  `111/113/114/116/119`; that mismatch reproduces arrows taking screenshots
  and Delete acting as Print Screen

Required live files:

```text
/etc/default/keyboard
/etc/xrdp/xrdp_keyboard.ini
/etc/xrdp/km-00000409.ini
/etc/xrdp/km-00010416.ini
/etc/xrdp/km-0000080a.ini
/etc/xrdp/km-0000f010.ini
/etc/xrdp/startwm.sh
/usr/local/share/xrdp-abnt2/xrdp_keyboard.ini
/usr/local/share/xrdp-abnt2/km-abnt2.ini
/usr/local/share/xrdp-abnt2/startwm.sh
/usr/local/sbin/fix-xrdp-abnt2-keyboard
/etc/apt/apt.conf.d/99xrdp-abnt2-keyboard
/etc/systemd/system/xrdp-abnt2-reconcile.service
/etc/systemd/system/xrdp-abnt2-reconcile.timer
~/.local/bin/setxkbmap-abnt2.sh
```

Required package baseline on every XRDP desktop host:

- `xrdp`
- `xorgxrdp`
- `tigervnc-common`
- `tigervnc-standalone-server`
- `tigervnc-tools`
- `dbus-x11`
- `freerdp2-x11`
- `lxde`
- `lxhotkey-plugin-openbox`

`freerdp2-x11` is part of the standard so any server can run peer smoke
validation with `xfreerdp`, not just `atius-srv-1`.

Apply:

```bash
cd ~/GitHub/omni-srv-admin
sudo -n python3 cli/omni/xrdp_abnt2.py install --user "$USER" --yes
```

The install command is the canonical persistent patch entrypoint. It guarantees
the package baseline, normalizes textual XRDP assets to `LF`, reinstalls the
APT/DPKG repair hook, refreshes `/usr/local/share/xrdp-abnt2/`, and ensures
`xrdp` + `xrdp-sesman` remain enabled.

Validate:

```bash
python3 cli/omni/xrdp_abnt2.py validate --user "$USER"
python3 cli/omni/xrdp_abnt2.py diff --user "$USER"
systemctl is-enabled xrdp-abnt2-reconcile.timer
systemctl is-active xrdp-abnt2-reconcile.timer
DISPLAY=:1 XAUTHORITY="$HOME/.Xauthority" setxkbmap -query
command -v xfreerdp
```

## Dark Desktop

The desktop standard is the `dark-theme-ubuntu` LXDE/XRDP profile:

- Greybird-dark for GTK/LXSession.
- Dark-Onyx for Openbox.
- dark PCManFM desktop.
- split LXPanel with `00-background`, `panel`, and `status-right`.
- ABNT2 watchdog in LXDE autostart.
- Omni Network tray instead of `nm-applet` for OCI/WireGuard unmanaged interfaces.
- CopyQ, xdg-desktop-portal settings, and dark app environment.

Apply:

```bash
cd ~/GitHub/omni-srv-admin/dark-theme-ubuntu
./scripts/dark-themectl.sh repair --install-packages --restart-session
```

Use `repair`, not `apply --with-sublime --with-zsh`, for fleet-wide theme rollout unless the host explicitly needs optional Sublime/zsh provisioning.

Validate:

```bash
cd ~/GitHub/omni-srv-admin/dark-theme-ubuntu
./scripts/dark-themectl.sh validate
```

## Obsidian Desktop Polish

Apply this only on hosts where Obsidian is actually installed.

Required behavior:

- `~/GitHub/obsidian-vault/AiSecondBrain/.obsidian/appearance.json` contains `titlebarStyle=native`.
- `~/.local/bin/obsidian` launches the stable AppImage with `--no-sandbox`.
- `~/.local/bin/obsidian-tray` waits for a real `obsidian.obsidian` window and docks it with `kdocker -b -q -w <window_id>`.
- The old `kdocker -n -q -- Obsidian.AppImage` path must not exist.

Canonical reference:

```bash
cd ~/GitHub/omni-srv-admin
python3 cli/omni/managed_apps.py status --app obsidian
python3 cli/omni/managed_apps.py verify --app obsidian
```

If drift exists, repair it from the managed helper:

```bash
cd ~/GitHub/omni-srv-admin
python3 cli/omni/managed_apps.py fix --app obsidian
```

## Rollout Contract

Before writing:

```bash
hostname
whoami
uname -m
. /etc/os-release && echo "$PRETTY_NAME"
test -d ~/GitHub/omni-srv-admin
```

For each host:

1. Sync the reviewed repo files to `~/GitHub/omni-srv-admin`.
2. Normalize line endings on Linux after copying from Windows.
3. Run syntax checks:

```bash
python3 -m py_compile cli/omni/xrdp_abnt2.py
sh -n modules/xrdp-abnt2/files/fix-xrdp-abnt2-keyboard \
  modules/xrdp-abnt2/files/startwm.sh \
  modules/xrdp-abnt2/files/setxkbmap-abnt2.sh
bash -n dark-theme-ubuntu/scripts/dark-themectl.sh
```

4. Install the keyboard guard.
5. Apply the dark desktop repair.
6. Validate both modules.
7. If Obsidian is installed on the host, verify the managed wrapper/titlebar defaults and repair them only if drift exists.
8. Do not restart `xrdp` or `xrdp-sesman` unless explicitly approved.
   The installed reconciliation timer only reapplies files through
   `fix-xrdp-abnt2-keyboard`; it does not restart either service.
9. If a live XRDP display exists, `--restart-session` may restart LXDE panel/Openbox/PCManFM only; this can flicker the desktop but should not drop RDP.

## Required Logging

Every fleet rollout or incident touching this standard must be recorded only in the authoritative SRV-1 knowledge stack:

- Obsidian vault on `atius-srv-1`.
- GBrain on `atius-srv-1`.

Minimum record:

- hosts changed.
- commands executed.
- backup paths.
- validation results.
- unresolved risks.

Do not treat the local Windows clone at `C:\Users\muniz\Documents\GitHub\obsidian-vault\ideaverse` as the source of truth. It is cache/fallback only; if anything lands there during a session, promote it to the SRV-1 Obsidian/GBrain authority and keep future logging there.
