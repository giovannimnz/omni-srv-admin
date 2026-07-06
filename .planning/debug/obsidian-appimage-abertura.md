---
status: resolved
trigger: "Analise esse Obsidian, e corrija a abertura dele, a versão instalada é o Appimage para ubuntu ARM"
created: "2026-07-04T22:54:25-03:00"
updated: "2026-07-04T23:05:00-03:00"
---

# Debug Session: obsidian-appimage-abertura

## Symptoms

- expected_behavior: Obsidian ARM64 AppImage opens from launcher/menu/wrapper in the active Ubuntu ARM XRDP session.
- actual_behavior: User reports the opening path is broken and requested analysis/fix.
- error_messages: Not supplied by user; gather from managed-app verification, wrapper logs, desktop files, process state, and live launch.
- timeline: Not supplied by user; compare current install state against managed-app docs and previous known Obsidian AppImage fixes.
- reproduction: Run the managed status/verify commands and launch via the same wrapper/desktop path used by the install.

## Current Focus

- hypothesis: The Obsidian AppImage itself is installed, but opening fails through a launcher/wrapper/runtime integration path such as KDocker timeout, stale desktop entry, missing xrdp-launch, FUSE/AppImage extraction, or Electron/X11 environment.
- test: Inspect managed manifest/installer, current wrapper and desktop entries, run status/verify, then execute the wrapper on the active display with logs captured.
- expecting: One layer reports the concrete failing path; fix should be durable through the managed-app installer or current managed files, not only a one-off launch.
- next_action: complete
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: "2026-07-04T22:55:04-03:00"
  observation: "journalctl --user -u obsidian-aisecondbrain-rest.service showed `fusermount: too many FUSE filesystems mounted`, `Cannot mount AppImage`, and exit status 127 during restart loop."
- timestamp: "2026-07-04T22:59:00-03:00"
  observation: "Found 993 active `/tmp/.mount_Obsidi*` FUSE mounts and stale Electron singleton links under `~/.config/obsidian/` pointing at dead PID 1722225."
- timestamp: "2026-07-04T23:00:00-03:00"
  observation: "`omni managed-apps verify --app obsidian` initially failed because `appearance.json` had no `titlebarStyle`; managed installer restored `titlebarStyle=native`."
- timestamp: "2026-07-04T23:01:00-03:00"
  observation: "Runtime unit was changed from hidden `DISPLAY=:90`/Xvfb dependency to visible `DISPLAY=:1` with `OBSIDIAN_FORCE_EXTRACT_AND_RUN=1`; stale Xvfb user unit was disabled."
- timestamp: "2026-07-04T23:03:00-03:00"
  observation: "Final checks: service active, Xvfb inactive/disabled, FUSE mounts 0, and `wmctrl` shows `obsidian.obsidian` window on display `:1`."
- timestamp: "2026-07-04T23:04:00-03:00"
  observation: "The managed `obsidian-tray` template was also corrected to resolve `/home/ubuntu/.local/bin/obsidian` before the direct AppImage and to treat only current-display X11 windows as already open; this keeps desktop/menu launches on the extraction-safe wrapper and avoids hidden-process no-op behavior."
- timestamp: "2026-07-04T23:05:00-03:00"
  observation: "Residual: `curl -k https://10.1.1.1:27124/` returned connection refused during this pass, so REST API availability was not counted as verified; the verified fix is the visual AppImage opening path on DISPLAY=:1."

## Eliminated

- hypothesis: "Downloaded AppImage is corrupt or wrong architecture."
  reason: "Checksum matched `2a40943a2402cf1f38e71845f294a78d300a78ff21ea4c2103335bca7fbdcbe0`; file is ARM aarch64."
- hypothesis: "Old KDocker command-start wrapper is still installed."
  reason: "`obsidian-tray` uses `kdocker -b -q -w` and managed verification passes."

## Resolution

- root_cause: "The Obsidian user service was opening the AppImage on hidden display `:90` through a failing Xvfb path and repeatedly restarting. That pinned/staled the Electron singleton outside the XRDP session and leaked 993 AppImage FUSE mounts, causing new launches to fail with `Cannot mount AppImage`. The managed tray wrapper also preferred the direct AppImage over the extraction-safe wrapper and used process-level detection that could confuse a hidden/background process with a visible RDP window. The vault appearance default had also drifted away from `titlebarStyle=native`."
- fix: "Stopped the restart loop, unmounted all stale AppImage FUSE mounts, backed up and removed stale singleton metadata, restored the managed AppImage install, changed the REST user unit to open on display `:1` with `OBSIDIAN_FORCE_EXTRACT_AND_RUN=1`, disabled the obsolete Xvfb user unit, and updated the managed installer so generated wrappers default to `APPIMAGE_EXTRACT_AND_RUN=1`, route tray launches through `/home/ubuntu/.local/bin/obsidian`, and only treat current-display X11 windows as already open."
- verification: "`PYTHONPATH=cli python3 -m omni managed-apps verify --app obsidian` passed; `modules/managed-apps/scripts/install-obsidian-arm64-appimage verify` passed; `python3 -m pytest cli/omni/tests/test_managed_apps.py` passed 7/7; `systemd-analyze --user verify` passed; service is active; `wmctrl` shows Obsidian 1.12.7 on display `:1`; FUSE mount count is 0. REST endpoint `https://10.1.1.1:27124/` still returned connection refused and was not treated as part of the opening-path verification."
- files_changed: "modules/srv1-ops/systemd/obsidian-aisecondbrain-rest.service; modules/srv1-ops/README.md; docs/operations/srv1-ops.md; modules/srv1-ops/docs/source-map.md; modules/managed-apps/scripts/install-obsidian-arm64-appimage; cli/omni/tests/test_managed_apps.py; docs/operations/managed-apps.md; docs/operations/ubuntu-arm64-xrdp-desktop-standard.md; modules/managed-apps/README.md; local user unit ~/.config/systemd/user/obsidian-aisecondbrain-rest.service; live wrappers under ~/.local/bin; vault appearance.json restored by managed installer"
