# Wayland Managed Runtime

## Ownership

- runtime de `wayland.atius.com.br` é administrado a partir do `omni-srv-admin`
- source repo permanece `~/GitHub/wayland`
- listener atual do runtime: `0.0.0.0:25725`
- rebuild/reapply pós-update fica em `modules/fleet/scripts/`
- source/upstream lane fica em `modules/fork-sync/projects/wayland/sync.yaml`
- inventário do `atius-srv-3` deve refletir `apps:` + `forks:` para o mesmo produto

## Commands

```bash
cd ~/GitHub/omni-srv-admin
bash modules/fleet/scripts/wayland-srv3-postinstall-hook.sh
bash modules/fleet/scripts/wayland-srv3-update.sh
bash modules/fleet/scripts/wayland-srv3-update.sh --pull
```

## Guarantees

- botão pré-chat `Conversar na pasta` visível no WebUI
- diretório padrão de `Conversar na pasta`: `/home/ubuntu/Servers` (`~/Servers`)
- workspaces NFS em `/home/ubuntu/Servers/<host>/GitHub/...` usam modo híbrido
  por padrão: edita no mount e valida no host dono via alias SSH canônico
- Projects e grupos de Recent Chats mostram o computador dono à direita; a
  bolinha verde exige path local disponível ou mount NFS real ativo
- idioma padrão da tela de login: `Português (Brasil)` quando não existe
  preferência salva
- runtime source-standalone em `~/GitHub/wayland/dist-server/server.mjs`
- `WAYLAND_DISABLE_AUTO_UPDATE=1` sempre ativo neste deployment
- merge com upstream deve preservar `protected_paths` do projeto `wayland`
- menu lateral esquerdo sem scrollbar horizontal em desktop/mobile drawer
- divisor do menu lateral esquerdo redimensiona e persiste `wayland:sidebar-width`

## Validation Baseline

- `https://wayland.atius.com.br/api/auth/status` -> `200`
- `http://127.0.0.1:25725/api/auth/status` no `atius-srv-3` -> `200`
- usuário WebUI `giovanni`; a senha é carregada do Vault profile `gsd-web-login`
  (`kv/atius/gsd/web-login`) e nunca deve ser registrada neste repo
- login público com a credencial hidratada do Vault -> sucesso
- `/api/auth/user` -> `200` com cookie de sessão
- validações de browser usam Chromium headless via Chrome DevTools; Playwright é
  fallback, não o caminho primário

## Headroom

O plano de integração do Headroom no Codex usado pelo Wayland está em
`docs/operations/WAYLAND-CODEX-HEADROOM-PLAN.md`. O contrato principal é
preservar `Wayland -> codex-acp -> codex`; Headroom entra no transporte do
Codex, não substitui o adapter ACP.
