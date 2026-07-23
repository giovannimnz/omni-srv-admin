---
phase: 19
plan: 19-02
title: "Desktop shortcuts hotfix — LXDE/XRDP"
date: 2026-06-17
status: complete
hosts:
  - atius-srv-1
  - atius-srv-2
  - atius-srv-3
  - horistic-srv-1
---

# Phase 19 — Desktop Shortcuts Hotfix

## Root Cause

O patch anterior de atalhos gravou `.desktop` inválidos:

```ini
Exec=env "DISPLAY=:1" "XAUTHORITY=*** /usr/bin/chromium %U
```

O valor ficou com aspas sem fechamento e com `***` literal no lugar do
`XAUTHORITY`. O `desktop-file-validate` acusava erro de quote aberto; por isso o
PCManFM/LXDE mostrava "entrada inválida" e recusava abrir Chromium, Firefox e
Obsidian.

## Correção Aplicada

- Criado wrapper por usuário:
  - ATIUS: `/home/ubuntu/.local/bin/xrdp-launch`
  - HORISTIC: `/home/horistic/.local/bin/xrdp-launch`
- Wrapper define `DISPLAY=:1` e `XAUTHORITY=$HOME/.Xauthority` quando ausentes.
- Atalhos reescritos sem `env`/quotes/glob:
  - `~/Desktop/chromium.desktop`
  - `~/.local/share/applications/chromium.desktop`
  - `~/Desktop/firefox.desktop`
  - `~/.local/share/applications/firefox.desktop`
  - `~/Desktop/obsidian.desktop` e local app nos 3 ATIUS
- Duplicatas removidas para backup:
  - `chromium-browser.desktop`
  - `google-chrome.desktop` quebrado no SRV-1 (`/opt/chromium/chrome`)
  - atalhos Obsidian no HORISTIC, porque não há Obsidian instalado lá.
- Remanescentes não-browser também corrigidos nos 3 ATIUS:
  - `hermes-app.desktop` mantido só se o binário real existe; caso contrário,
    movido para backup.
  - `sublime-text.desktop` passou a chamar o `subl` real do host via
    `xrdp-launch`.
  - `claude-code-url-handler.desktop` vazio foi movido para backup.
- SRV-2 recebeu a instalação Obsidian ARM64 real em
  `/home/ubuntu/snap/obsidian/common/`, copiada do SRV-1.
- `chromium-browser` transitional (`2:1snap1-0ubuntu2`) purgado do SRV-3 e
  HORISTIC; SRV-2 já estava só em estado `rc` e foi purgado no hotfix.
- `/etc/hosts` dos 4 hosts normalizado para nomes SRV/HORISTIC lowercase.

## Validação

- `desktop-file-validate`: PASS para atalhos Chromium, Firefox e Obsidian.
- `desktop-file-validate`: PASS para todos os `.desktop` visíveis do Desktop
  nos 3 ATIUS após corrigir Hermes/Sublime e remover o handler vazio.
- Chromium apt real:
  - SRV-1/2/3/HORISTIC: `Chromium 149.0.7827.114 built on Ubuntu 24.04.4 LTS`
  - `snap list`: sem `chromium` nos 4 hosts.
- Smoke Chromium via wrapper:
  - SRV-1/2/3/HORISTIC: `--headless=new --dump-dom` retornou `<p>ok</p>`.
- Smoke Obsidian via Xvfb:
  - SRV-1/2/3: log `Loaded main app package .../obsidian.asar`; timeout 124
    esperado porque o app GUI fica aberto.
- PCManFM/LXDE recarregado nos 3 ATIUS com `pcmanfm --desktop-off` + `setsid -f
  ... pcmanfm --desktop --profile LXDE`; XRDP não foi reiniciado.
- HORISTIC não tinha sessão LXDE/PCManFM ativa; atalhos em disco foram
  corrigidos mesmo assim.

## Backups

- SRV-1: `/home/ubuntu/.backups/desktop-shortcuts-hostname-2026-06-17-20260617-124654`
- SRV-2: `/home/ubuntu/.backups/desktop-shortcuts-hostname-2026-06-17-20260617-124654`
- SRV-3: `/home/ubuntu/.backups/desktop-shortcuts-hostname-2026-06-17-20260617-154654`
- HORISTIC: `/home/horistic/.backups/desktop-shortcuts-hostname-2026-06-17-20260617-124655`
- Extra ATIUS: `~/.backups/desktop-shortcuts-extra-2026-06-17-*`
- Handler vazio: `~/.backups/desktop-shortcuts-invalid-localapps-2026-06-17-*`

## Estado Final

- Hosts ATIUS finais: `atius-srv-1`, `atius-srv-2`, `atius-srv-3`.
- HORISTIC hostname: `horistic-srv-1`.
- Desktop dos 3 ATIUS mantém somente:
  - `chromium.desktop`
  - `firefox.desktop`
  - `obsidian.desktop`
  - atalhos extras válidos quando o binário existe (`sublime-text.desktop`,
    `hermes-app.desktop`, `lxterminal.desktop`)
- HORISTIC mantém somente:
  - `chromium.desktop`
  - `firefox.desktop`
