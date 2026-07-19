# Wayland upstream sync guards

Updated: 2026-07-13

This fork tracks `FerroxLabs/wayland` but serves a production runtime on
`atius-srv-3` at `https://wayland.atius.com.br/`. Upstream sync must preserve
the srv-3 standalone-source deployment model and the Codex/WebUI customizations
that make that runtime operable.

The public reverse proxy on `atius-srv-1` uses the OCI/DRG backend
`10.13.1.13:25725`. The `10.100.100.0/24` network is reserve fallback only and
must not be selected as the primary path while OCI/DRG is available.

## Do not overwrite these behaviors

- `wayland.service` on `atius-srv-3` runs the source checkout directly through
  `/home/ubuntu/GitHub/wayland/dist-server/server.mjs`, not the packaged app
  binary.
- The post-install/update contract lives in the source repo scripts
  `scripts/atius-*.sh` plus the patch file
  `patches/atius-webui-workspace-visible.patch`.
- The production Codex ACP source is the full-history subtree
  `/home/ubuntu/GitHub/wayland/codex-acp`; runtime must not depend on the retired
  sibling checkout `/home/ubuntu/GitHub/codex-acp`.
- Codex ACP is built and tested only through
  `scripts/atius-build-codex-acp.sh`, which enforces the 20% total CPU ceiling,
  and installed atomically at `/home/ubuntu/.local/bin/codex-acp`.
- OpenClaw and Wayland consume the stable wrapper
  `/home/ubuntu/.local/bin/codex-acp-atius`, never a source-checkout path.
- `scripts/atius-refresh-source-patch.sh` must keep
  `patches/atius-webui-workspace-visible.patch` aligned with the latest ATIUS
  delta against `upstream/main`; protecting the patch file alone is not enough.
- The generated `.atius-overlay/` directory is build output only and must stay
  untracked; source-of-truth is the patch/scripts/docs that recreate it.
- `Conversar na pasta` must stay visible in the WebUI and default to
  `/home/ubuntu/Servers` (`~/Servers` for the `ubuntu` runtime user).
- NFS GitHub mounts under `/home/ubuntu/Servers/<host>/GitHub/...` must keep
  the default hybrid execution guidance: edit on the mount, validate on the
  owner host via its SSH alias and translated owner path.
- `Conversar na pasta` must also open the browser directory picker in WebUI
  mode; it cannot silently depend on the native Electron dialog path.
- The login screen defaults to `pt-BR` when there is no saved language.
- Codex must remain detectable in ACP mode on the server runtime, and the GUID
  model picker must keep the selected model label even before
  `acp.cachedModels` exists.
- Codex ACP models must be shown as base models, with reasoning effort selected
  in a separate adjacent control. Do not reintroduce model rows like
  `gpt-5.5/xhigh` or labels like `GPT-5.5 (xhigh)`.
- Hermes Agent must also expose the same separate reasoning effort control,
  even when its ACP payload does not advertise `reasoning_effort`; Wayland sends
  the selected effort through session config/extra.
- Codex permission mode must include `Custom (config.toml)` /
  `Personalizado(config.toml)`, which leaves the service user's native Codex
  config in control instead of forcing a Wayland sandbox preset.
- The GUID agent pill bar must expose hidden/collapsed agents by accessible
  name, so Hermes/Codex can be selected by keyboard, tests and assistive tools.
- On mobile widths, composer controls and intent pills must wrap visibly instead
  of hiding later options behind unmarked horizontal overflow.
- The left sidebar must not expose a bottom horizontal scrollbar at desktop,
  narrowed desktop, or mobile drawer widths; long recents and footer controls
  must truncate or compact within the sidebar.
- Conversations opened from a project, including projects backed by NFS
  workspaces, must remain visible in the global Recent Chats list and badge and
  grouped under the Project name even when `customWorkspace=false`; team-scoped
  conversations remain isolated from the global sidebar.
- The desktop left sidebar divider must remain a real resize handle that
  persists `wayland:sidebar-width` while preserving the rail snap below the
  collapse threshold.
- Standalone build output must include the MCP stdio scripts copied into
  `dist-server/`; otherwise the runtime startup canary fails.
- Service-shell env loading must skip non-interactive login shells like
  `/usr/sbin/nologin`; the server runtime uses `User=wayland`.
- Optional vendored agent-profile bodies and optional MCP packages must not spam
  startup logs as hard failures.

## Protected paths that carry this behavior

- `.gitignore`
- `AGENTS.md`
- `THIRD-PARTY-NOTICES.md`
- `package.json`
- `atius-overlay.json`
- `codex-acp/`
- `patches/atius-webui-workspace-visible.patch`
- `scripts/atius-apply-source-patch.sh`
- `scripts/atius-build-codex-acp.sh`
- `scripts/atius-verify-codex-acp.sh`
- `scripts/atius-build-renderer-overlay.sh`
- `scripts/atius-postinstall-hook.sh`
- `scripts/atius-refresh-source-patch.sh`
- `scripts/atius-sync-ubuntu-runtime.mjs`
- `scripts/atius-wayland-https-proxy.js`
- `scripts/atius-reapply-renderer-overlay.sh`
- `scripts/atius-update.sh`
- `scripts/install-ubuntu.sh`
- `scripts/build-server.mjs`
- `scripts/build-mcp-servers.js`
- `src/process/agent/acp/AcpDetector.ts`
- `src/process/agent/acp/acpConnectors.ts`
- `src/process/agent/AgentRegistry.ts`
- `src/process/agent/remote/RemoteAgentCore.ts`
- `src/process/bridge/remoteAgentBridge.ts`
- `src/process/acp/compat/typeBridge.ts`
- `src/process/extensions/data/bundle-vendored/agentProfileMerge.ts`
- `src/process/extensions/resolvers/ChannelPluginResolver.ts`
- `src/process/utils/initStorage.ts`
- `src/process/utils/shellEnv.ts`
- `src/process/webserver/routes/apiRoutes.ts`
- `src/process/webserver/config/constants.ts`
- `src/process/webserver/websocket/WebSocketManager.ts`
- `src/renderer/components/layout/Layout.tsx`
- `src/renderer/components/layout/Sider/Sider.module.css`
- `src/renderer/components/layout/Sider/SiderAccordion/SiderAccordionShell.module.css`
- `src/renderer/components/layout/Sider/SiderAccordion/SiderRecentChatsSection.module.css`
- `src/renderer/components/layout/Sider/SiderAccordion/SiderRecentChatsSection.tsx`
- `src/renderer/components/layout/Sider/SiderFooter.tsx`
- `src/renderer/components/layout/Sider/SiderFooter/SiderFooterQuickActions.module.css`
- `src/renderer/components/layout/Sider/index.tsx`
- `src/common/adapter/ipcBridge.ts`
- `src/common/config/storage.ts`
- `src/common/types/codex/codexModes.ts`
- `src/common/types/codex/types/eventData.ts`
- `src/process/task/AcpAgentManager.ts`
- `src/process/task/WCoreManager.ts`
- `src/process/task/claudeConfig.ts`
- `src/process/task/codexConfig.ts`
- `src/process/task/codexStaticModelInfo.ts`
- `src/process/task/hermesConfig.ts`
- `src/renderer/components/agent/AgentModeSelector.tsx`
- `src/renderer/components/agent/MarqueePillLabel.tsx`
- `src/renderer/components/model/modelSelector/EffortSubRow.tsx`
- `src/renderer/components/model/modelSelector/modelSelectorTypes.ts`
- `src/renderer/components/settings/DirectorySelectionModal.tsx`
- `src/renderer/hooks/file/useDirectorySelection.tsx`
- `src/renderer/pages/conversation/GroupedHistory/hooks/useConversationListSync.ts`
- `src/renderer/pages/conversation/GroupedHistory/utils/groupingHelpers.ts`
- `src/renderer/pages/guid/GuidPage.tsx`
- `src/renderer/pages/guid/index.module.css`
- `src/renderer/pages/guid/components/AgentPillBar.tsx`
- `src/renderer/pages/guid/components/GuidActionRow.tsx`
- `src/renderer/pages/guid/components/GuidInputCard.tsx`
- `src/renderer/pages/guid/components/GuidModelSelector.tsx`
- `src/renderer/pages/guid/components/newChatStarter/IntentPillBar.module.css`
- `src/renderer/pages/guid/hooks/useGuidAgentSelection.ts`
- `src/renderer/pages/guid/hooks/useGuidSend.ts`
- `src/renderer/pages/settings/AgentSettings/RemoteAgentManagement.tsx`
- `src/common/types/acpTypes.ts`
- `src/renderer/services/i18n/i18n-keys.d.ts`
- `src/renderer/services/i18n/index.ts`
- `src/renderer/services/i18n/locales/*/agentMode.json`
- `src/renderer/services/i18n/locales/*/conversation.json`
- `src/renderer/styles/layout.css`
- `src/renderer/utils/model/agentModes.ts`
- `tests/unit/AgentPillBar.dom.test.tsx`
- `tests/unit/atiusCodexAcpRuntime.test.ts`
- `tests/unit/acpConnectors.test.ts`
- `tests/unit/AcpAgentManagerSkillInjection.test.ts`
- `tests/unit/WebSocketManager.test.ts`
- `tests/unit/process/task/codexConfigEffort.test.ts`
- `tests/unit/process/task/codexNativeSandbox.test.ts`
- `tests/unit/renderer/GuidActionRow.dom.test.tsx`
- `tests/unit/renderer/AcpConfigSelector.dom.test.tsx`
- `tests/unit/renderer/components/layout/Sider/SiderAccordion/SiderRecentChatsSection.dom.test.tsx`
- `tests/unit/renderer/groupingHelpers.test.ts`
- `tests/unit/renderer/guidModelSelector.dom.test.tsx`
- `tests/unit/RemoteAgentCore.test.ts`
- `tests/unit/RemoteAgentManagement.dom.test.tsx`
- `tests/unit/remoteAgentBridge.test.ts`
- `tests/unit/renderer/guid/firstSafeCuratedModel.test.ts`
- `tests/unit/useGuidSend.dom.test.ts`
- `tests/unit/webserver/detectNetworkContext.test.ts`
- `tests/unit/webserver/cookieOptions.test.ts`
- `docs/README.md`
- `docs/legal/THIRD-PARTY-NOTICES.md`
- `docs/guides/atius-codex-acp.md`
- `docs/guides/atius-fork-runtime.md`
- `src/renderer/services/i18n/locales/*/settings.json`

## Required post-sync checks

Run from `/home/ubuntu/GitHub/wayland` after any upstream merge:

```bash
bash scripts/atius-refresh-source-patch.sh --commit-if-changed
git apply --reverse --check --recount patches/atius-webui-workspace-visible.patch
bash scripts/atius-build-codex-acp.sh --test --force
bash scripts/atius-verify-codex-acp.sh --live
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/atiusCodexAcpRuntime.test.ts tests/unit/acpConnectors.test.ts tests/unit/AcpAgentManagerSkillInjection.test.ts
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/WebSocketManager.test.ts tests/unit/renderer/GuidActionRow.dom.test.tsx
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/renderer/guid/firstSafeCuratedModel.test.ts
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/renderer/components/layout/Sider/SiderAccordion/SiderRecentChatsSection.dom.test.tsx tests/unit/renderer/groupingHelpers.test.ts
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/AgentPillBar.dom.test.tsx tests/unit/renderer/guidModelSelector.dom.test.tsx tests/unit/useGuidSend.dom.test.ts tests/unit/process/task/codexNativeSandbox.test.ts tests/unit/process/task/codexConfigEffort.test.ts
npm run typecheck
bash scripts/atius-build-renderer-overlay.sh
sudo systemctl restart wayland.service
systemctl is-active wayland.service
curl -fsS -o /dev/null -w "http=%{http_code}\n" http://127.0.0.1:25725/
journalctl -u wayland.service --since "5 minutes ago" --no-pager | grep -E "AgentRegistry|found 2 agents|Serving renderer|WebUI running"
```

Expected result:

- patch file refreshed/committed when upstream context drifted,
- embedded adapter has no nested `.git`, Cargo/npm versions match, Rust tests
  pass, and the installed wrapper resolves the embedded build,
- `vitest` passes.
- project conversations appear in the global Recent Chats list and badge,
  grouped under the Project name even with `customWorkspace=false`, while
  team-scoped conversations remain isolated.
- `typecheck` passes.
- `wayland.service` is `active`.
- local HTTP on `127.0.0.1:25725` returns `200`.
- startup logs still show `found 4 agents: Wayland Core, Gemini CLI, Codex, Hermes Agent`.

## Git remote guard

- `origin` is the ATIUS fork: `https://github.com/giovannimnz/wayland.git`.
- `upstream` remains `https://github.com/FerroxLabs/wayland`.
- Do not push srv-3 customizations to `FerroxLabs/wayland`.
- `auto_push` is enabled in the `fork-sync` project because the fork remote now
  exists and `gh`/Git HTTPS auth was validated on `atius-srv-3`.
