# Managed Apps Operations

`managed-apps` pins manually managed desktop/browser/CLI apps for SRV-1, SRV-2, SRV-3 and Horistic.

Source of truth:

```text
modules/managed-apps/configs/programs.json
```

Boundary:

- `managed-apps` owns installed programs, wrappers, policies, post-install fixups
  and runtime customizations for packaged/manual apps.
- `fork-sync` owns source forks that follow upstream and preserve code deltas.
- If one product has both forms, inventory must record both:
  - `apps:` for the installed runtime
  - `forks:` for the source/upstream lane

Cross-reference:

- `docs/operations/customization-governance.md`
- `docs/operations/wayland-managed-runtime.md`

Local checks:

```bash
omni managed-apps status --app brave-browser,chromium,firefox,obsidian,gitkraken,bitwarden-chromium-extension
omni managed-apps verify --app brave-browser,chromium,firefox,obsidian,gitkraken,bitwarden-chromium-extension
```

Local repair after apt upgrades:

```bash
omni managed-apps fix --app brave-browser
omni managed-apps fix --app chromium,firefox
omni managed-apps fix --app obsidian
omni managed-apps fix --app gitkraken
```

Upgrade plan and execution:

```bash
omni managed-apps upgrade --app chromium,firefox
omni managed-apps upgrade --app chromium,firefox --yes
omni managed-apps upgrade --app obsidian
omni managed-apps upgrade --app obsidian --yes
omni managed-apps upgrade --app gitkraken
omni managed-apps upgrade --app gitkraken --yes
```

Fleet probe:

```bash
omni managed-apps fleet-status --app brave-browser,chromium,firefox --host atius-srv-1 --host atius-srv-2 --host atius-srv-3 --host horistic-srv
```

Managed repo/policy/customization checks:

```bash
omni managed-apps manifest
omni managed-apps config-status
omni managed-apps config-verify
omni managed-apps fleet-config-status
```

Managed surfaces:

- `repositories`: apt source expectations and apt policy evidence. Current required source is `xtradeb/apps` for `chromium` and `firefox`.
- Brave Browser is managed from the official Brave APT repository at `brave-browser-apt-release.s3.brave.com` with `arch=arm64`.
- `policies`: browser policy files. Current Chromium policy force-installs Bitwarden from Chrome Web Store through `/etc/chromium/policies/managed/omni-bitwarden.json`.
- Chromium browser defaults policy is stored at `/etc/chromium/policies/managed/omni-browser-defaults.json` and managed from `modules/managed-apps/policies/chromium/omni-browser-defaults.json`.
- `customizations`: local launcher/wrapper and desktop policy files, including `/usr/local/bin` and `/usr/bin` wrappers for `chrome`, `google-chrome` and `google-chrome-stable` -> Brave, `/home/ubuntu/.local/bin/chromium-normal-window`, `/etc/chromium.d/extensions`, PCManFM `quick_exec=1`, the Firefox normal launcher, and Obsidian `titlebarStyle=native`.
- `programs`: concrete package/extension/manual artifact versions and post-upgrade fix hooks.

Rules:

- Do not install Snap for `brave-browser`, `chromium`, `firefox`, `obsidian` or `gitkraken`.
- Keep `chrome`, `google-chrome` and `google-chrome-stable` as wrappers/aliases to Brave on ARM64 hosts unless Google Chrome ARM64 is explicitly approved.
- Keep `chromium` and `firefox` from `xtradeb/apps` unless a new source is explicitly approved.
- Keep Chromium launchers routed through `/home/ubuntu/.local/bin/chromium-normal-window`.
- Keep Chromium flags `--disable-gpu --disable-gpu-rasterization --disable-features=Vulkan,VulkanFromANGLE,SidePanel`.
- Keep Bitwarden installed from Chrome Web Store by policy:
  `/etc/chromium/policies/managed/omni-bitwarden.json`
- Keep Chromium default search and startup/homepage by policy:
  `/etc/chromium/policies/managed/omni-browser-defaults.json`
- Do not copy Bitwarden vault/profile data into logs, docs or git.
- Do not persist Brave Sync phrases in logs, docs, repo, shell startup files or the managed-apps manifest.

## Obsidian ARM64 AppImage

Managed install:

```bash
modules/managed-apps/scripts/install-obsidian-arm64-appimage
omni managed-apps status --app obsidian
omni managed-apps verify --app obsidian
```

Upgrade plan and apply:

```bash
omni managed-apps upgrade --app obsidian
omni managed-apps upgrade --app obsidian --yes
```

Required source and layout:

- Source: official Obsidian GitHub releases only, `obsidianmd/obsidian-releases`.
- Asset: `Obsidian-<version>-arm64.AppImage`; no `.deb`, no Snap.
- Install root: `/home/ubuntu/GitHub/Programs/obsidian`.
- Stable launcher target: `/home/ubuntu/GitHub/Programs/obsidian/Obsidian.AppImage`.
- Wrapper: `/home/ubuntu/.local/bin/obsidian` launches the AppImage with `--no-sandbox` and defaults to `APPIMAGE_EXTRACT_AND_RUN=1` to avoid stale AppImage FUSE mount exhaustion on the ARM64 XRDP host. Set `OBSIDIAN_USE_FUSE=1` only for controlled FUSE troubleshooting.
- Tray wrapper: `/home/ubuntu/.local/bin/obsidian-tray` must start through `/home/ubuntu/.local/bin/obsidian`, wait for a real `obsidian.obsidian` X11 window, then dock with `kdocker -b -q -w <window_id>`.
- Desktop/menu launchers stay routed through `/home/ubuntu/.local/bin/xrdp-launch`.

Default appearance applied during install:

```json
{
  "titlebarStyle": "native"
}
```

The installer writes this into `~/GitHub/obsidian-vault/AiSecondBrain/.obsidian/appearance.json`. This maps to **Settings -> Appearance -> Advanced -> Window frame style -> Native frame** and prevents the hidden-frame titlebar artifact seen in LXDE/XRDP near the minimize button. A full Obsidian restart is required for the setting to take effect.

Troubleshooting: KDocker timeout after reboot

- Symptom: a KDocker dialog says `Could not find a matching window for ... Obsidian.AppImage in the specified time: 5 seconds`.
- Cause: the old `obsidian-tray --tray-only` path used `kdocker -n -q -- Obsidian.AppImage --no-sandbox`; after boot, the AppImage can take longer than KDocker's default 5-second command-start window to create the X11 window.
- Durable fix: run `omni managed-apps fix --app obsidian` or `modules/managed-apps/scripts/install-obsidian-arm64-appimage`; the generated tray wrapper waits up to `OBSIDIAN_TRAY_WAIT_SECONDS` seconds, defaults to `90`, and attaches KDocker by existing window id with `kdocker -b -q -w`.
- Failure behavior: if no Obsidian window appears, the wrapper logs to `~/.local/state/obsidian-tray/obsidian-tray.log` and exits without opening a graphical KDocker warning.
- Verify: `omni managed-apps verify --app obsidian` must fail if `~/.local/bin/obsidian-tray` contains the old `kdocker -n -q` command-start pattern.

Troubleshooting: AppImage FUSE mount exhaustion

- Symptom: Obsidian exits or loops without opening, and `journalctl --user -u obsidian-aisecondbrain-rest.service` shows `fusermount: too many FUSE filesystems mounted` or `Cannot mount AppImage`.
- Cause: repeated direct AppImage starts can leave many stale `/tmp/.mount_Obsidi*` FUSE mounts on this ARM64/XRDP host.
- Durable fix: run `omni managed-apps fix --app obsidian` or `modules/managed-apps/scripts/install-obsidian-arm64-appimage`; the generated wrapper runs the AppImage extracted by default and avoids creating new FUSE mounts.

## GitKraken ARM64 Deb

Managed install:

```bash
modules/managed-apps/scripts/install-gitkraken-gk-arm64-deb
omni managed-apps status --app gitkraken
omni managed-apps verify --app gitkraken
```

Upgrade plan and apply:

```bash
omni managed-apps upgrade --app gitkraken
omni managed-apps upgrade --app gitkraken --yes
```

Required source and layout:

- Source: official GitKraken GitHub releases only, `gitkraken/gk-cli`.
- Asset: `gk_<version>_linux_arm64.deb`; no Snap and no PPA.
- Current managed asset: `gk_3.1.68_linux_arm64.deb`.
- Debian package: `gk`.
- Install root/state: `/home/ubuntu/GitHub/Programs/gitkraken`.
- State file: `/home/ubuntu/GitHub/Programs/gitkraken/state/current-release.json`.
- Status must record the installed `dpkg` version and architecture for every probed host.

GitKraken safety rules:

- Do not use the Snap `gitkraken` package after this managed `.deb` path is adopted.
- Do not replace this with a generic GitKraken website download; bump the manifest and installer from the official `gitkraken/gk-cli` release asset.

Obsidian safety rules:

- Preserve `~/GitHub/obsidian-vault/AiSecondBrain`; do not copy note contents into logs, docs or git.
- Back up launcher/config metadata under `/var/backups/omni-managed-apps/obsidian-<timestamp>` before mutation.
- Do not restart XRDP and do not open a second RDP session for validation.

## Brave Browser

Managed install:

```bash
modules/managed-apps/scripts/install-brave-browser
omni managed-apps status --app brave-browser
omni managed-apps config-status --section repositories,customizations
```

Required local surfaces:

- `/etc/apt/sources.list.d/brave-browser-release.list`
- `/usr/share/keyrings/brave-browser-archive-keyring.gpg`
- `/usr/local/bin/chrome`
- `/usr/local/bin/google-chrome`
- `/usr/local/bin/google-chrome-stable`
- `/usr/bin/chrome`
- `/usr/bin/google-chrome`
- `/usr/bin/google-chrome-stable`
- `/etc/profile.d/chrome-brave-alias.sh`

Fleet validation:

```bash
omni managed-apps fleet-status --app brave-browser
omni managed-apps fleet-config-status --section repositories,customizations
```

Brave Sync setup helper:

```bash
install -m 0600 /path/to/trusted-sync-phrase /tmp/brave-sync-code

BRAVE_SYNC_CODE_FILE=/tmp/brave-sync-code \
  BRAVE_SYNC_MODE=apply-ui \
  BRAVE_SYNC_DISPLAY=:1.0 \
  BRAVE_SYNC_XAUTHORITY="$HOME/.Xauthority" \
  modules/managed-apps/scripts/brave-sync-setup

rm -f /tmp/brave-sync-code
```

Use the active XRDP/X11 session and its `DBUS_SESSION_BUS_ADDRESS` when Sync needs the desktop keyring. Do not run this through a new RDP connection.

Operational notes:

- Prefer `BRAVE_SYNC_MODE=apply-ui` for existing profiles. It handles Brave's native confirmation dialogs and the reset/re-join path.
- The helper uses Secret Service/libsecret for `Brave Safe Storage` when `secret-tool` is available.
- The helper persists `sync.keep_everything_synced=true` and primary sync data-type prefs before launch.
- Do not pass the Sync phrase in shell history or docs. Use `BRAVE_SYNC_CODE_FILE` or `BRAVE_SYNC_CODE_STDIN=1`.

Sync validation:

```bash
BRAVE_SYNC_MODE=diagnose \
  BRAVE_SYNC_URL=chrome://sync-internals \
  BRAVE_SYNC_DISPLAY=:1.0 \
  BRAVE_SYNC_XAUTHORITY="$HOME/.Xauthority" \
  modules/managed-apps/scripts/brave-sync-setup
```

Expected healthy fields:

- `Transport State Active`
- `Sync Feature Enabled true`
- `Server Connection OK`
- `Sync First-Time Setup Complete true`
- `Explicit Passphrase true`
- `Passphrase Required false`
- `Brave Sync Passphrase is set true`
- `OS encryption available true`

## Chromium Google defaults

Managed policy:

```text
/etc/chromium/policies/managed/omni-browser-defaults.json
```

Source file:

```text
modules/managed-apps/policies/chromium/omni-browser-defaults.json
```

Required values:

- `DefaultSearchProviderEnabled=true`
- `DefaultSearchProviderName=Google`
- `DefaultSearchProviderSearchURL=https://www.google.com.br/search?q={searchTerms}`
- `DefaultSearchProviderSuggestURL=https://www.google.com.br/complete/search?output=chrome&q={searchTerms}`
- `HomepageLocation=https://google.com.br`
- `HomepageIsNewTabPage=false`
- `RestoreOnStartup=4`
- `RestoreOnStartupURLs=["https://google.com.br"]`
- `ShowHomeButton=true`

Validate locally and across fleet:

```bash
omni managed-apps config-verify --section policies
omni managed-apps fleet-config-status --section policies
```

## Chromium / Bitwarden SidePanel decision

`SidePanel` is a Chromium/Chrome browser feature and extension API that lets an extension open UI in the browser side panel instead of a normal popup/tab. Bitwarden `2026.5.1` exposes this capability in Chromium.

Observed issue on 2026-06-24:

- Chromium xtradeb `149.0.7827.155-1xtradeb1.2404.1` on ARM64/LXDE/XRDP crashed the Bitwarden extension popup.
- Direct test of `chrome-extension://nngceckbapebfimnlniiiahkandclblb/popup/index.html` without mitigation ended as `Aw, Snap`.
- Launching Chromium with `--disable-features=Vulkan,VulkanFromANGLE,SidePanel` made the Bitwarden target open normally.

Interpretation:

- `SidePanel` is the Bitwarden-specific mitigation.
- `--disable-gpu`, `--disable-gpu-rasterization`, and disabling `Vulkan,VulkanFromANGLE` are broader XRDP/ARM64 Chromium stability mitigations, not Bitwarden-only.
- This was reproduced on the xtradeb Chromium build present on the fleet. It is not proven to be exclusive to xtradeb; it can be a Chromium 149 ARM64/Linux regression, a build/packaging interaction, or an XRDP renderer interaction.
- A different non-Snap upstream build might not reproduce the bug, but no approved official Ubuntu/Debian ARM64 Chromium source was validated here. Snap remains forbidden.

Rollback test when Chromium or Bitwarden changes:

```bash
cp /home/ubuntu/.local/bin/chromium-normal-window /tmp/chromium-normal-window.test
sed -i 's/,SidePanel//' /tmp/chromium-normal-window.test
/tmp/chromium-normal-window.test about:blank
```

Then validate Bitwarden visually/CDP before removing `SidePanel` from the managed wrapper and manifest. Test `SidePanel` removal separately from GPU/Vulkan flags.

References:

- Chrome Side Panel extension API: <https://developer.chrome.com/docs/extensions/reference/api/sidePanel>
- Chrome extension alternative installation/policy source: <https://developer.chrome.com/docs/extensions/how-to/distribute/install-extensions>
- Chromium command-line flags guidance: <https://www.chromium.org/developers/how-tos/run-chromium-with-flags/>
