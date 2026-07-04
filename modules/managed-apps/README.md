# Managed Apps

Manual version manager for desktop/browser/CLI apps that must stay aligned across the Atius/Horistic ARM64 fleet.

Canonical manifest:

```text
modules/managed-apps/configs/programs.json
```

Boundary:

- This module owns installed-program governance.
- Upstream-following source forks belong to `modules/fork-sync/`.
- If a product has both a runtime and a fork/worktree, keep both in inventory:
  - `apps:` for the installed runtime
  - `forks:` for the source/upstream lane

Current managed set:

- `brave-browser`: official Brave APT repository, snap forbidden, `chrome`, `google-chrome` and `google-chrome-stable` wrappers point to Brave in `/usr/local/bin` and `/usr/bin`.
- `chromium`: xtradeb/apps apt package set, snap forbidden, wrapper must disable `SidePanel` for Bitwarden stability.
- `firefox`: xtradeb/apps apt package, snap forbidden, normal XRDP launcher.
- `obsidian`: official ARM64 AppImage from Obsidian GitHub releases, snap forbidden, installed under `/home/ubuntu/GitHub/Programs/obsidian`.
- `gitkraken`: official ARM64 `.deb` asset from `gitkraken/gk-cli` GitHub releases, snap forbidden, installed as Debian package `gk` with state under `/home/ubuntu/GitHub/Programs/gitkraken`.
- `bitwarden-chromium-extension`: Chrome Web Store extension in Chromium profile; fixed by Chromium compatibility flags, not by replacing vault data.

Commands:

```bash
omni managed-apps manifest
omni managed-apps status --app chromium,firefox,obsidian,bitwarden-chromium-extension
omni managed-apps verify --app chromium,firefox,obsidian,bitwarden-chromium-extension
omni managed-apps config-status
omni managed-apps config-verify
omni managed-apps status --app brave-browser
omni managed-apps fix --app brave-browser
omni managed-apps fix --app chromium,firefox
omni managed-apps fix --app obsidian
omni managed-apps upgrade --app chromium,firefox          # plan only
omni managed-apps upgrade --app chromium,firefox --yes    # local apt upgrade + post-fix
omni managed-apps upgrade --app obsidian                  # manual AppImage plan only
omni managed-apps upgrade --app obsidian --yes            # run official AppImage installer
omni managed-apps status --app gitkraken
omni managed-apps verify --app gitkraken
omni managed-apps upgrade --app gitkraken                 # manual .deb plan only
omni managed-apps upgrade --app gitkraken --yes           # download and install official ARM64 .deb
omni managed-apps fleet-status --app brave-browser --host atius-srv-1 --host atius-srv-2
omni managed-apps fleet-config-status
```

Install the standalone CLI shim:

```bash
omni managed-apps install-local-cli --force
omni-managed-apps status --app chromium
```

Managed surfaces:

- `programs`: package/extension versions, source expectations and post-upgrade repairs.
- `repositories`: apt source and `apt-cache policy` checks.
- `policies`: managed browser policy JSON and Chromium extension policy files.
- `customizations`: wrappers, desktop launchers, PCManFM behavior and Chromium extension loading guardrails.

Current Brave note:

- Install from the official Brave APT repository with `arch=arm64`.
- `/usr/local/bin/{chrome,google-chrome,google-chrome-stable}` and `/usr/bin/{chrome,google-chrome,google-chrome-stable}` are local wrappers that execute `/usr/bin/brave-browser`.
- `/etc/profile.d/chrome-brave-alias.sh` adds aliases for `chrome`, `google-chrome` and `google-chrome-stable` in interactive shells.
- Brave Sync setup must not persist the sync phrase in repo, docs, logs, shell startup files or managed-apps manifest.
- Use `modules/managed-apps/scripts/brave-sync-setup` with the active X11/XRDP display; do not open a second RDP session for Sync setup.
- Preferred Sync mode is `BRAVE_SYNC_MODE=apply-ui`, because Brave may show native JavaScript confirmation dialogs that block direct WebUI calls.
- The helper bootstraps `Brave Safe Storage` through Secret Service/libsecret when `secret-tool` and the user DBus are available.
- The helper persists `sync.keep_everything_synced=true` and the primary sync data-type prefs before launching Brave.
- For validation, use `BRAVE_SYNC_MODE=diagnose BRAVE_SYNC_URL=chrome://sync-internals`; `sync-internals` needs a longer startup wait before `Transport State` becomes stable.

Current Chromium browser defaults:

- Policy file: `/etc/chromium/policies/managed/omni-browser-defaults.json`
- Default search provider: Google
- Search URL: `https://www.google.com.br/search?q={searchTerms}`
- Homepage/startup URL: `https://google.com.br`

Current Chromium note:

- `SidePanel` is disabled because Bitwarden `2026.5.1` crashed on Chromium xtradeb `149.0.7827.155-1xtradeb1.2404.1` in XRDP.
- GPU/Vulkan flags are broader XRDP/ARM64 Chromium stability flags, not Bitwarden-only.
- Snap remains forbidden; do not replace this with Ubuntu Snap Chromium/Firefox.

Current Obsidian note:

- Installer: `modules/managed-apps/scripts/install-obsidian-arm64-appimage`
- Source: `https://github.com/obsidianmd/obsidian-releases/releases`, accepting only assets ending in `arm64.AppImage`.
- Stable path: `/home/ubuntu/GitHub/Programs/obsidian/Obsidian.AppImage`.
- The installer sets `~/GitHub/obsidian-vault/AiSecondBrain/.obsidian/appearance.json` with `titlebarStyle=native`.
- `titlebarStyle=native` is the module default for Obsidian installs. It maps to Obsidian's `Window frame style -> Native frame` and avoids the hidden-frame titlebar artifact in LXDE/XRDP.
- Obsidian requires a full app restart after changing the window frame style.
- The `obsidian-tray --tray-only` autostart wrapper must not use `kdocker -n -q -- Obsidian.AppImage`; it must wait for an `obsidian.obsidian` window and attach KDocker by window id with `kdocker -b -q -w <window_id>`.
- If Obsidian does not create a window during boot, the wrapper logs to `~/.local/state/obsidian-tray/obsidian-tray.log` and exits without showing a KDocker dialog.

Current GitKraken note:

- Installer: `modules/managed-apps/scripts/install-gitkraken-gk-arm64-deb`
- Source: `https://github.com/gitkraken/gk-cli/releases`, accepting only assets ending in `linux_arm64.deb`.
- Current asset: `gk_3.1.68_linux_arm64.deb`.
- Debian package: `gk` version `3.1.68`, architecture `arm64`.
- State file: `/home/ubuntu/GitHub/Programs/gitkraken/state/current-release.json`.
- Snap `gitkraken` is forbidden after the managed `.deb` path is adopted.
