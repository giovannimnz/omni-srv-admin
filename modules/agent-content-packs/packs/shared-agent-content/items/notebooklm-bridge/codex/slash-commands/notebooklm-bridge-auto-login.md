# /notebooklm-bridge-auto-login

Renova auth do NotebookLM no Camofox usando senha e TOTP do Bitwarden CLI.

Pré-condição:

```bash
export NOTEBOOKLM_GOOGLE_BW_ITEM_ID="<item-id-do-bitwarden>"
export NOTEBOOKLM_GOOGLE_ACCOUNT="<email-google-alvo>"
```

Para execução não interativa:

```bash
export NOTEBOOKLM_BW_MASTER_PASS_ENV=BW_MASTER_PASS
export BW_MASTER_PASS="<senha-mestre-do-bitwarden>"
export NOTEBOOKLM_BW_LOCK_AFTER=1
```

Rodar:

```bash
notebooklm-auto-login
unset BW_MASTER_PASS NOTEBOOKLM_BW_MASTER_PASS_ENV
```

Manual equivalente:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/nlm_camofox_auth.py auto-login --fallback-mode auto
uv run python execution/nlm_auth_check.py --write-run
```

Contrato visual:

- Camofox primário no display de `CAMOFOX_BROWSER_DISPLAY`.
- Resolução fixa `1366x768`, noVNC em `resize=scale`.
- Janela maximizada.
- Playwright/Camofox mapeia refs/selectors; `xdotool` é fallback de coordenada e canal de digitação de senha/TOTP.

Se o Google exigir chave de segurança, passkey, captcha, confirmação no celular ou recovery flow, abrir o noVNC e concluir manualmente:

```bash
uv run python execution/nlm_camofox_auth.py import-state
uv run python execution/nlm_auth_check.py --write-run
```

Reportar:

- run_dir do `auto-login`;
- `fallback_mode`, `element_map_path` e `static_coordinate_map`;
- se `password_submitted` e `totp_submitted` foram `true`;
- se `requires_manual` apareceu e qual `manual_reason`;
- run_dir do `auth-check`;
- confirmação de que nenhum segredo foi impresso e nenhum upload real foi feito.
