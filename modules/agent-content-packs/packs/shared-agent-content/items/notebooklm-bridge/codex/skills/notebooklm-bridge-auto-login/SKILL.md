---
name: notebooklm-bridge-auto-login
description: "Auto-login seguro do NotebookLM no Camofox usando senha e TOTP do Bitwarden CLI. Usar para /notebooklm-bridge-auto-login ou quando Giovanni pedir login automatico com Bitwarden/TOTP."
---

# NotebookLM Bridge Auto-login

Usar somente com Camofox/Hermes como navegador primário. Chrome DevTools/CDP segue como fallback secundário e exige aprovação explícita.

## Pré-condições

```bash
export NOTEBOOKLM_GOOGLE_BW_ITEM_ID="<item-id-do-bitwarden>"
export NOTEBOOKLM_GOOGLE_ACCOUNT="<email-google-alvo>"
```

Para execução não interativa, deixar o runner chamar `bw unlock --passwordenv`:

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

## Automação

- Usar snapshot/ref e selectors Playwright do Camofox para localizar e focar elementos.
- Usar `element-map.json` sanitizado para auditoria do último estado visual.
- Usar coordenadas como fallback somente no display fixo de `CAMOFOX_BROWSER_DISPLAY`, `1366x768`, janela maximizada.
- Coordenadas base: `account_card=(1214,383)`, `email_field=(940,405)`, `password_field=(940,405)`, `totp_field=(940,405)`, `password_method=(470,455)`, `try_another_way=(1010,585)`, `next_button=(1160,585)`.
- Usar `--fallback-mode playwright-only` para desativar coordenadas ou `--fallback-mode xdotool-only` para forçar o mapa fixo.

## Regras de Segurança

- Nunca pedir ou imprimir senha/TOTP.
- Não registrar `BW_SESSION`.
- Não registrar `BW_MASTER_PASS` nem o valor apontado por `NOTEBOOKLM_BW_MASTER_PASS_ENV`.
- Não usar endpoint Camofox `/type` para senha/TOTP; o bridge digita via `xdotool --file -`.
- Não embutir senha/TOTP em expressão `evaluate`, selector, argv, logs ou docs.
- Reportar booleanos e motivo manual (`password_submitted`, `totp_submitted`, `requires_manual`, `manual_reason`) sem expor segredo.
- Depois de `notebooklm-auto-login`, limpar a env de senha mestre e o ponteiro quando eles tiverem sido definidos na sessão do operador.
- Se Google exigir chave de segurança/passkey/captcha/celular, parar e pedir conclusão manual pelo noVNC.

## Limite

Chave de segurança física e passkey/WebAuthn não são TOTP. O Bitwarden CLI não substitui uma chave FIDO conectada ao browser; o fluxo apenas tenta escolher senha/TOTP e detecta quando precisa de intervenção manual.
