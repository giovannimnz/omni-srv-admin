# Wayland upstream sync guards

Updated: 2026-07-04

This fork tracks `FerroxLabs/wayland` but serves a production runtime on
`atius-srv-3` at `https://wayland.atius.com.br/`. Upstream sync must preserve
the srv-3 standalone-source deployment model and the Codex/WebUI customizations
that make that runtime operable.

## Do not overwrite these behaviors

- `wayland.service` on `atius-srv-3` runs the source checkout directly through
  `/home/ubuntu/GitHub/wayland/dist-server/server.mjs`, not the packaged app
  binary.
- The post-install/update contract lives in the source repo scripts
  `scripts/atius-*.sh` plus the patch file
  `patches/atius-webui-workspace-visible.patch`.
- The generated `.atius-overlay/` directory is build output only and must stay
  untracked; source-of-truth is the patch/scripts/docs that recreate it.
- `Conversar na pasta` must stay visible in the WebUI and default to
  `/home/ubuntu/GitHub`.
- The login screen defaults to `pt-BR` when there is no saved language.
- Codex must remain detectable in ACP mode on the server runtime, and the GUID
  model picker must keep the selected model label even before
  `acp.cachedModels` exists.
- Standalone build output must include the MCP stdio scripts copied into
  `dist-server/`; otherwise the runtime startup canary fails.
- Service-shell env loading must skip non-interactive login shells like
  `/usr/sbin/nologin`; the server runtime uses `User=wayland`.
- Optional vendored agent-profile bodies and optional MCP packages must not spam
  startup logs as hard failures.

## Protected paths that carry this behavior

- `.gitignore`
- `package.json`
- `atius-overlay.json`
- `patches/atius-webui-workspace-visible.patch`
- `scripts/atius-apply-source-patch.sh`
- `scripts/atius-build-renderer-overlay.sh`
- `scripts/atius-postinstall-hook.sh`
- `scripts/atius-reapply-renderer-overlay.sh`
- `scripts/atius-update.sh`
- `scripts/install-ubuntu.sh`
- `scripts/build-server.mjs`
- `scripts/build-mcp-servers.js`
- `src/process/agent/acp/AcpDetector.ts`
- `src/process/extensions/data/bundle-vendored/agentProfileMerge.ts`
- `src/process/extensions/resolvers/ChannelPluginResolver.ts`
- `src/process/utils/initStorage.ts`
- `src/process/utils/shellEnv.ts`
- `src/process/webserver/routes/apiRoutes.ts`
- `src/renderer/components/settings/DirectorySelectionModal.tsx`
- `src/renderer/hooks/file/useDirectorySelection.tsx`
- `src/renderer/pages/guid/components/GuidActionRow.tsx`
- `src/renderer/pages/guid/components/GuidModelSelector.tsx`
- `src/renderer/services/i18n/index.ts`
- `tests/unit/renderer/guid/firstSafeCuratedModel.test.ts`
- `docs/README.md`
- `docs/guides/atius-fork-runtime.md`

## Required post-sync checks

Run from `/home/ubuntu/GitHub/wayland` after any upstream merge:

```bash
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/renderer/guid/firstSafeCuratedModel.test.ts
npm run typecheck
bash scripts/atius-build-renderer-overlay.sh
sudo systemctl restart wayland.service
systemctl is-active wayland.service
curl -fsS -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:25808/
journalctl -u wayland.service --since "5 minutes ago" --no-pager | grep -E "AgentRegistry|found 3 agents|Serving renderer|WebUI running"
```

Expected result:

- `vitest` passes.
- `typecheck` passes.
- `wayland.service` is `active`.
- local HTTP on `127.0.0.1:25808` returns `200`.
- startup logs still show `found 3 agents: Wayland Core, Gemini CLI, Codex`.

## Git remote guard

- As of 2026-07-04 there is no published `giovannimnz/wayland` repo visible via
  GitHub search, and `gh auth status` on `atius-srv-3` reports an invalid token.
- Do not push srv-3 customizations to `FerroxLabs/wayland`.
- Preferred local layout is `upstream=FerroxLabs/wayland` and `origin` reserved
  for the eventual Giovanni fork URL.
