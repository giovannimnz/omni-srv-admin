# Managed Apps

Manual version manager for desktop/browser apps that must stay aligned across the Atius/Horistic ARM64 fleet.

Canonical manifest:

```text
modules/managed-apps/configs/programs.json
```

Current managed set:

- `chromium`: xtradeb/apps apt package set, snap forbidden, wrapper must disable `SidePanel` for Bitwarden stability.
- `firefox`: xtradeb/apps apt package, snap forbidden, normal XRDP launcher.
- `bitwarden-chromium-extension`: Chrome Web Store extension in Chromium profile; fixed by Chromium compatibility flags, not by replacing vault data.

Commands:

```bash
omni managed-apps manifest
omni managed-apps status --app chromium,firefox,bitwarden-chromium-extension
omni managed-apps verify --app chromium,firefox,bitwarden-chromium-extension
omni managed-apps config-status
omni managed-apps config-verify
omni managed-apps fix --app chromium,firefox
omni managed-apps upgrade --app chromium,firefox          # plan only
omni managed-apps upgrade --app chromium,firefox --yes    # local apt upgrade + post-fix
omni managed-apps fleet-status --app chromium,firefox --host atius-srv-1 --host atius-srv-2
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

Current Chromium browser defaults:

- Policy file: `/etc/chromium/policies/managed/omni-browser-defaults.json`
- Default search provider: Google
- Search URL: `https://www.google.com.br/search?q={searchTerms}`
- Homepage/startup URL: `https://google.com.br`

Current Chromium note:

- `SidePanel` is disabled because Bitwarden `2026.5.1` crashed on Chromium xtradeb `149.0.7827.155-1xtradeb1.2404.1` in XRDP.
- GPU/Vulkan flags are broader XRDP/ARM64 Chromium stability flags, not Bitwarden-only.
- Snap remains forbidden; do not replace this with Ubuntu Snap Chromium/Firefox.
