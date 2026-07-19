---
project: wayland
version: 5
created: 2026-07-04
last_updated: 2026-07-19
owner_module: omni-srv-admin/modules/fork-sync
---

# Manual de Atualização — wayland

## 1. Objetivo

`wayland` é o checkout source-of-truth do runtime servido em
`https://wayland.atius.com.br/` no `atius-srv-3`. O runtime é standalone-source:
o serviço systemd executa `dist-server/server.mjs` construído a partir do
checkout local, com patch/source overlay próprio da ATIUS.

O caminho de produção é Cloudflare -> Apache no OCI/DRG `10.11.1.11`
(`atius-srv-1`) -> backend Wayland no OCI/DRG `10.13.1.13:25725`
(`atius-srv-3`). A rede `10.100.100.0/24` é fallback de reserva e nunca deve
ser escolhida enquanto o caminho OCI/DRG estiver disponível.

## 2. Source of Truth

| Item | Path |
|---|---|
| Config do projeto | `projects/wayland/sync.yaml` |
| Guard rail operacional | `projects/wayland/UPSTREAM-SYNC-GUARDS.md` |
| Fork local | `/home/ubuntu/GitHub/wayland` |
| Runtime systemd | `wayland.service` |
| Entry-point do runtime | `/home/ubuntu/GitHub/wayland/dist-server/server.mjs` |
| Upstream | `https://github.com/FerroxLabs/wayland` |
| Fork GitHub | `https://github.com/giovannimnz/wayland` |

## 3. Estado atual

- O runtime ativo roda com `User=ubuntu`, `PORT=25725`,
  `CODEX_HOME=/home/ubuntu/.codex`, `HERMES_HOME=/home/ubuntu/.hermes` e
  `WAYLAND_DISABLE_AUTO_UPDATE=1`.
- `Conversar na pasta` fica visível no WebUI e usa `/home/ubuntu/Servers` (`~/Servers`) como
  diretório inicial.
- Workspaces NFS em `/home/ubuntu/Servers/<host>/GitHub/...` agora carregam um
  contrato híbrido por padrão: o agente edita no mount e usa o alias SSH do
  host dono para validar em `/home/ubuntu/GitHub/...` ou
  `/home/horistic/GitHub/...`, conforme o mount.
- Sem preferência salva, a tela de login entra em `pt-BR`.
- A detecção do servidor oferece apenas os CLIs canônicos `Codex` e
  `Hermes Agent`; Gemini CLI permanece desativado.
- A página GUID reúne modelo, esforço, velocidade, reset e Power avançado em
  um único menu compacto. Comandos GSD continuam comandos `/` ou `$` e não são
  promovidos a agentes runtime.
- O agente remoto Codex usa `wss://codex-acp.atius.com.br/gateway`, token do
  Vault e device pairing OpenClaw; o transporte chega ao fork `codex-acp` no
  usuário `ubuntu`.
- O modo de permissão do Codex inclui `Custom (config.toml)` /
  `Personalizado(config.toml)`, que deixa o Codex usar o `config.toml` nativo
  do usuário de serviço em vez de uma predefinição Wayland.
- No mobile, os controles do composer e os intent pills quebram linha de forma
  visível; não dependem de scroll horizontal escondido.
- Chats abertos a partir de projetos, inclusive em workspaces NFS, permanecem
  visíveis na lista e no badge global de Recent Chats e agrupados sob o nome do
  projeto mesmo com `customWorkspace=false`; chats de team continuam isolados
  da lateral global.
- Cards de Projects e cabeçalhos de pasta em Recent Chats exibem o computador
  dono à direita. A bolinha verde aparece apenas quando o path local existe ou
  há um mount NFS real ativo; o placeholder `autofs` isolado não conta como
  conectado.
- O fork remoto existe em `https://github.com/giovannimnz/wayland`.
- `origin` do checkout local aponta para esse fork, e `upstream` permanece em
  `FerroxLabs/wayland`.

## 4. Rotina de sync

Dry-run:

```bash
cd /home/ubuntu/GitHub/omni-srv-admin
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync --json sync wayland --dry-run
```

Apply:

```bash
cd /home/ubuntu/GitHub/omni-srv-admin
PYTHONPATH=modules/fork-sync/cli python3 -m fork_sync sync wayland
```

`auto_push` fica `true`: merges seguros do `fork-sync` podem publicar no fork
`giovannimnz/wayland` automaticamente depois do ciclo de `post_sync`.

## 5. Protected paths

Os paths protegidos carregam 6 grupos de customização:

1. Runtime standalone source:
   `package.json`, `scripts/build-server.mjs`, `scripts/build-mcp-servers.js`,
   `scripts/install-ubuntu.sh`, `scripts/atius-*.sh`, `atius-overlay.json`.
2. Patch/source overlay do WebUI:
   `patches/atius-webui-workspace-visible.patch`,
   `src/renderer/components/settings/DirectorySelectionModal.tsx`,
   `src/renderer/hooks/file/useDirectorySelection.tsx`,
   `src/renderer/pages/guid/components/GuidActionRow.tsx`,
   `src/process/webserver/websocket/WebSocketManager.ts`,
   `tests/unit/WebSocketManager.test.ts`,
   `tests/unit/renderer/GuidActionRow.dom.test.tsx`.
3. Codex ACP e boot/runtime hardening:

   - source of truth: full-history subtree
     `/home/ubuntu/GitHub/wayland/codex-acp`;
   - build/test/install: `scripts/atius-build-codex-acp.sh`, sob o limite de
     20% da CPU total;
   - runtime entrypoint: `/home/ubuntu/.local/bin/codex-acp-atius`;
   - o checkout irmão `/home/ubuntu/GitHub/codex-acp` foi aposentado e nao pode
     voltar a ser dependencia do Wayland ou OpenClaw;
   `src/process/agent/acp/AcpDetector.ts`,
   `src/process/utils/shellEnv.ts`,
   `src/process/webserver/routes/apiRoutes.ts`,
   `src/process/extensions/resolvers/ChannelPluginResolver.ts`,
   `src/process/extensions/data/bundle-vendored/agentProfileMerge.ts`,
   `src/process/utils/initStorage.ts`,
   `src/common/types/codex/codexModes.ts`,
   `src/process/task/AcpAgentManager.ts`,
   `src/process/task/codexConfig.ts`,
   `src/process/task/hermesConfig.ts`,
   `src/renderer/components/agent/AgentModeSelector.tsx`,
   `src/renderer/components/agent/MarqueePillLabel.tsx`,
   `tests/unit/AcpAgentManagerSkillInjection.test.ts`,
   `src/renderer/pages/guid/GuidPage.tsx`,
   `src/renderer/pages/guid/components/GuidModelSelector.tsx`,
   `src/renderer/pages/guid/hooks/useGuidAgentSelection.ts`,
   `src/renderer/pages/guid/hooks/useGuidSend.ts`,
   `src/renderer/utils/model/agentModes.ts`,
   `src/renderer/services/i18n/index.ts`,
   `tests/unit/renderer/guid/firstSafeCuratedModel.test.ts`.
4. GUID UI/responsividade:
   `src/renderer/components/layout/Layout.tsx`,
   `src/renderer/components/layout/Sider/Sider.module.css`,
   `src/renderer/components/layout/Sider/SiderAccordion/SiderAccordionShell.module.css`,
   `src/renderer/components/layout/Sider/SiderAccordion/SiderRecentChatsSection.module.css`,
   `src/renderer/components/layout/Sider/SiderAccordion/SiderRecentChatsSection.tsx`,
   `src/renderer/components/layout/Sider/SiderFooter.tsx`,
   `src/renderer/components/layout/Sider/SiderFooter/SiderFooterQuickActions.module.css`,
   `src/renderer/components/layout/Sider/index.tsx`,
   `src/renderer/pages/conversation/GroupedHistory/hooks/useConversationListSync.ts`,
   `src/renderer/pages/conversation/GroupedHistory/index.tsx`,
   `src/renderer/pages/conversation/GroupedHistory/utils/groupingHelpers.ts`,
   `src/renderer/components/workspace/WorkspaceComputerIndicator.tsx`,
   `src/renderer/hooks/useWorkspaceComputerStatuses.ts`,
   `src/renderer/pages/projects/ProjectsListPage.tsx`,
   `src/renderer/pages/projects/components/ProjectCard.tsx`,
   `src/common/utils/workspaceComputer.ts`,
   `src/process/bridge/projectBridge.ts`,
   `src/process/services/workspaceComputerStatus.ts`,
   `src/renderer/pages/guid/components/AgentPillBar.tsx`,
   `src/renderer/pages/guid/index.module.css`,
   `src/renderer/pages/guid/components/newChatStarter/IntentPillBar.module.css`,
   `src/renderer/styles/layout.css`,
   `tests/unit/AgentPillBar.dom.test.tsx`,
   `tests/unit/renderer/components/layout/Sider/SiderAccordion/SiderRecentChatsSection.dom.test.tsx`,
   `tests/unit/renderer/groupingHelpers.test.ts`,
   `tests/unit/workspaceComputerStatus.test.ts`,
   `tests/unit/WorkspaceComputerIndicator.dom.test.tsx`,
   `tests/unit/renderer/guidModelSelector.dom.test.tsx`,
   `tests/unit/useGuidSend.dom.test.ts`.
5. i18n da personalização:
   `src/renderer/services/i18n/i18n-keys.d.ts`,
   `src/renderer/services/i18n/locales/*/agentMode.json`,
   `src/renderer/services/i18n/locales/*/conversation.json`.
6. Documentação do fork:
   `design-qa.md`, `docs/README.md`, `docs/guides/atius-fork-runtime.md`,
   `.gitignore`.

## 6. Patch refresh

Além de proteger os arquivos, o lane agora também atualiza a personalização
reaplicável. O script canônico é:

```bash
bash scripts/atius-build-codex-acp.sh --test --force
bash scripts/atius-verify-codex-acp.sh --live
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/atiusCodexAcpRuntime.test.ts tests/unit/acpConnectors.test.ts
bash scripts/atius-refresh-source-patch.sh
```

Ele regenera `patches/atius-webui-workspace-visible.patch` a partir do delta
atual entre `HEAD` e `upstream/main`, limitado aos arquivos protegidos que o
auto-patcher sabe reaplicar. Esse patch agora cobre o browser picker, modelo
separado de esforço, `config.toml` mode, Hermes effort e correções mobile da
GUID, incluindo sidebar sem overflow horizontal, resize persistido e chats de
projeto preservados e agrupados pelo projeto na lista global de Recent Chats,
incluindo o indicador do computador dono e seu status de mount.

No `fork-sync`, o `post_sync` roda:

```bash
bash scripts/atius-refresh-source-patch.sh --commit-if-changed
```

Se o merge com upstream mexer no contexto do patch, o arquivo é atualizado e
checkpointado em commit local antes do rebuild do runtime.

## 7. Rebuild e pós-sync

Após merge real, o `post_sync` roda:

```bash
bash scripts/atius-postinstall-hook.sh
```

Esse hook:

- garante ACL/permissões para `User=wayland`;
- escreve o override `wayland.service.d/atius-overlay.conf`;
- rebuilda renderer + `dist-server`;
- reinicia `wayland.service`.

## 8. Validações pós-sync

```bash
cd /home/ubuntu/GitHub/wayland
bash scripts/atius-refresh-source-patch.sh --commit-if-changed
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/WebSocketManager.test.ts tests/unit/renderer/GuidActionRow.dom.test.tsx
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/renderer/guid/firstSafeCuratedModel.test.ts
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/renderer/components/layout/Sider/SiderAccordion/SiderRecentChatsSection.dom.test.tsx tests/unit/renderer/groupingHelpers.test.ts
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/workspaceComputerStatus.test.ts tests/unit/WorkspaceComputerIndicator.dom.test.tsx
NODE_OPTIONS=--max-old-space-size=4096 ./node_modules/.bin/vitest run tests/unit/AcpAgentManagerSkillInjection.test.ts tests/unit/AgentPillBar.dom.test.tsx tests/unit/renderer/guidModelSelector.dom.test.tsx tests/unit/useGuidSend.dom.test.ts tests/unit/process/task/codexNativeSandbox.test.ts tests/unit/process/task/codexConfigEffort.test.ts
npm run typecheck
bash scripts/atius-build-renderer-overlay.sh
sudo systemctl restart wayland.service
systemctl is-active wayland.service
curl -fsS -o /dev/null -w "http=%{http_code}\n" http://10.13.1.13:25725/
journalctl -u wayland.service --since "5 minutes ago" --no-pager | grep -E "AgentRegistry|found 2 agents|Serving renderer|WebUI running"
```

## 9. Guardrails

- Não commitar `.atius-overlay/`; é artefato gerado.
- Não apontar `origin` para `FerroxLabs/wayland` quando o objetivo for publicar
  customização ATIUS.
- Não manter `patches/atius-webui-workspace-visible.patch` stale; regenere com
  `scripts/atius-refresh-source-patch.sh` sempre que mudar a personalização do
  browser picker, sidebar ou Recent Chats.
- Não remover `protected_paths` só porque upstream convergiu visualmente; validar
  antes o comportamento em `wayland.atius.com.br`.
- Não trocar o post-install hook do runtime sem atualizar o inventário do
  `atius-srv-3` e `docs/operations/wayland-managed-runtime.md`.

## 10. Histórico do manual

| Versão | Data | Mudança |
|--------|------|---------|
| 1 | 2026-07-04 | Criação inicial do lane `wayland` no fork-sync |
| 2 | 2026-07-05 | Proteção da GUID com modelo/esforço separados, Hermes effort, Codex `config.toml`, acessibilidade do AgentPillBar e mobile wrap |
| 3 | 2026-07-19 | Proteção de chats de projeto na lista global de Recent Chats e dos testes focados correspondentes |
| 4 | 2026-07-19 | Agrupamento de chats sob o nome do Project mesmo quando o workspace NFS foi criado com `customWorkspace=false` |
| 5 | 2026-07-19 | Computador dono e status conectado nos cards de Projects e grupos de Recent Chats |
| 6 | 2026-07-19 | Indicador conectado alinhado visualmente ao Codex, com verde de sucesso explícito, 8 px e QA headless preservado no fork |
