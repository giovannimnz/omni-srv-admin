# Managed Apps Operations

`managed-apps` pins manually managed browser apps for SRV-1, SRV-2, SRV-3 and Horistic.

Source of truth:

```text
modules/managed-apps/configs/programs.json
```

Local checks:

```bash
omni managed-apps status --app chromium,firefox,bitwarden-chromium-extension
omni managed-apps verify --app chromium,firefox,bitwarden-chromium-extension
```

Local repair after apt upgrades:

```bash
omni managed-apps fix --app chromium,firefox
```

Upgrade plan and execution:

```bash
omni managed-apps upgrade --app chromium,firefox
omni managed-apps upgrade --app chromium,firefox --yes
```

Fleet probe:

```bash
omni managed-apps fleet-status --app chromium,firefox --host atius-srv-1 --host atius-srv-2 --host atius-srv-3 --host horistic-srv
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
- `policies`: browser policy files. Current Chromium policy force-installs Bitwarden from Chrome Web Store through `/etc/chromium/policies/managed/omni-bitwarden.json`.
- Chromium browser defaults policy is stored at `/etc/chromium/policies/managed/omni-browser-defaults.json` and managed from `modules/managed-apps/policies/chromium/omni-browser-defaults.json`.
- `customizations`: local launcher/wrapper and desktop policy files, including `/home/ubuntu/.local/bin/chromium-normal-window`, `/etc/chromium.d/extensions`, PCManFM `quick_exec=1`, and the Firefox normal launcher.
- `programs`: concrete package/extension versions and post-upgrade fix hooks.

Rules:

- Do not install Snap for `chromium` or `firefox`.
- Keep `chromium` and `firefox` from `xtradeb/apps` unless a new source is explicitly approved.
- Keep Chromium launchers routed through `/home/ubuntu/.local/bin/chromium-normal-window`.
- Keep Chromium flags `--disable-gpu --disable-gpu-rasterization --disable-features=Vulkan,VulkanFromANGLE,SidePanel`.
- Keep Bitwarden installed from Chrome Web Store by policy:
  `/etc/chromium/policies/managed/omni-bitwarden.json`
- Keep Chromium default search and startup/homepage by policy:
  `/etc/chromium/policies/managed/omni-browser-defaults.json`
- Do not copy Bitwarden vault/profile data into logs, docs or git.

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
