---
name: notebooklm-bridge-auto-login
description: "Slash command Hermes /notebooklm-bridge-auto-login para auto-login seguro NotebookLM via Camofox + Bitwarden CLI senha/TOTP."
triggers: [/notebooklm-bridge-auto-login]
---

# /notebooklm-bridge-auto-login

Usar Camofox/Hermes como navegador primario. Chrome DevTools/CDP e fallback secundario e exige aprovacao explicita.

## Pre-condicoes

```bash
export NOTEBOOKLM_GOOGLE_BW_ITEM_ID="<item-id-do-bitwarden>"
export NOTEBOOKLM_GOOGLE_ACCOUNT="<email-google-alvo>"
```

Para execucao nao interativa, deixar o runner chamar `bw unlock --passwordenv`:

```bash
export NOTEBOOKLM_BW_MASTER_PASS_ENV=BW_MASTER_PASS
export BW_MASTER_PASS="<senha-mestre-do-bitwarden>"
export NOTEBOOKLM_BW_LOCK_AFTER=1
```

## Comando

Preferir o runner instalado no host:

```bash
notebooklm-auto-login
```

Fluxo manual equivalente:

```bash
cd /home/ubuntu/GitHub/notebooklm-obsidian-bridge
uv run python execution/nlm_camofox_auth.py auto-login --fallback-mode auto
uv run python execution/nlm_auth_check.py --write-run
```

## Automacao

- Usar snapshot/ref e selectors Playwright do Camofox para localizar e focar elementos.
- Gravar `element-map.json` sanitizado no run dir para auditoria do ultimo estado visual.
- Usar coordenadas como fallback somente no display fixo de `CAMOFOX_BROWSER_DISPLAY`, `1366x768`, janela maximizada.
- Coordenadas base: `account_card=(1214,383)`, `email_field=(940,405)`, `password_field=(940,405)`, `totp_field=(940,405)`, `password_method=(470,455)`, `try_another_way=(1010,585)`, `next_button=(1160,585)`.
- Usar `--fallback-mode playwright-only` para desativar coordenadas ou `--fallback-mode xdotool-only` para forcar o mapa fixo.

## Regras

- Nunca pedir ou imprimir senha/TOTP.
- Nao registrar `BW_SESSION`.
- Nao registrar `BW_MASTER_PASS` nem o valor apontado por `NOTEBOOKLM_BW_MASTER_PASS_ENV`.
- Para senha/TOTP, o bridge digita via `xdotool --file -`, nao pelo endpoint `/type`.
- Nao embutir senha/TOTP em `evaluate`, selector, argv, logs ou docs.
- Reportar `password_submitted`, `totp_submitted`, `requires_manual` e `manual_reason`.
- Depois de `notebooklm-auto-login`, limpar a env de senha mestre e o ponteiro quando eles tiverem sido definidos na sessao do operador.
- Chave de seguranca/passkey/captcha/celular exige conclusao manual pelo noVNC.
