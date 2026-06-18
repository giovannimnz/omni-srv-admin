---
phase: 19
milestone: M008
title: "Fleet Standardization — hostnames, chromium, dark theme"
date: 2026-06-17
status: complete
plans: 2
hosts:
  - atius-srv-1 (10.1.1.1)
  - atius-srv-2 (10.1.1.2)
  - atius-srv-3 (10.1.1.7)
  - horistic-srv-1 (10.1.1.3 / 163.176.232.119)
---

# Phase 19 — Fleet Standardization

## Goal

Padronizar 4 hosts ATIUS:
1. Hostnames lowercase
2. Chromium 149.x via PPA xtradeb/apps
3. Atalho `~/Desktop/chromium.desktop` + menu Internet
4. Dark theme LXDE canônico do SRV-1 replicado

## Plans

| Plan | Status | Descrição |
|------|--------|-----------|
| 19-01 | ✅ DONE | hostname + PPA + chromium + desktop shortcut + dark theme (sem restart-session) |
| 19-02 | ✅ DONE | hotfix definitivo dos atalhos LXDE/XRDP via `xrdp-launch`; remove `.desktop` inválido e Chromium snap/transitional |

## Resultado

### Hotfix 19-02 (2026-06-17)

O primeiro patch de atalhos deixou arquivos `.desktop` inválidos com
`Exec=env "DISPLAY=:1" "XAUTHORITY=*** ...` e aspas sem fechamento. O estado
final foi corrigido em `19-02-DESKTOP-SHORTCUTS-HOTFIX-2026-06-17.md`:

- `~/.local/bin/xrdp-launch` define `DISPLAY=:1` e `XAUTHORITY=$HOME/.Xauthority`.
- Atalhos Chromium/Firefox/Obsidian usam `Exec=<home>/.local/bin/xrdp-launch ...`.
- `desktop-file-validate` passa nos atalhos dos 3 ATIUS e do HORISTIC.
- Chromium 149.0.7827.114 apt real validado nos 4 hosts; sem snap Chromium.
- Obsidian real restaurado no SRV-2; Xvfb smoke carregou `obsidian.asar` nos 3 ATIUS.
- PCManFM recarregado nos 3 ATIUS sem reiniciar XRDP.

### Hostnames

| Host | Antes | Depois |
|------|-------|--------|
| 10.1.1.1 | `ATIUS-SRV-1` | `atius-srv-1` ✅ |
| 10.1.1.2 | `ATIUS-SRV-2` | `atius-srv-2` ✅ |
| 10.1.1.7 | `ATIUS-SRV-3` | `atius-srv-3` ✅ |
| 10.1.1.3 | `horistic-srv-1` | `horistic-srv-1` (já era) ✅ |

### Chromium

| Host | Antes | Depois | Método |
|------|-------|--------|--------|
| SRV-1 | 149.0.7827.102-1xtradeb1.2204.1 (.deb) | 149.0.7827.114-1xtradeb1.2404.1 (.deb) | `apt install --only-upgrade` |
| SRV-2 | snap chromium | 149.0.7827.114 (.deb) | `snap remove chromium` + `apt install chromium` |
| SRV-3 | snap chromium | 149.0.7827.114 (.deb) | `snap remove chromium` + `apt install chromium` |
| horistic-srv-1 | snap chromium | 149.0.7827.114 (.deb) | `snap remove chromium` + `apt install chromium` |

PPA xtradeb/apps: habilitado nos 4 hosts. No SRV-1 já existia o `.list`; nos outros 3 foi criado. Formato: `deb https://ppa.launchpadcontent.net/xtradeb/apps/ubuntu/ noble main` (NÃO jammy — Ubuntu 24.04 = noble, e o pacote jammy tem deps impossíveis no noble).

### Atalhos

| Host | ~/Desktop/chromium.desktop | /usr/share/applications/chromium.desktop (menu Internet) |
|------|----------------------------|-------------------------------------------------------------|
| SRV-1 | criado ✅ | já existia ✅ |
| SRV-2 | criado ✅ | já existia ✅ |
| SRV-3 | criado ✅ | já existia ✅ |
| horistic-srv-1 | criado em `/home/horistic/Desktop/chromium.desktop` ✅ | já existia ✅ |

### Dark theme

| File | SRV-1 (canônico) | SRV-2 (pré) | SRV-2 (pós) | SRV-3 (pré) | SRV-3 (pós) | horistic (pré) | horistic (pós) |
|------|------------------|-------------|-------------|-------------|-------------|----------------|---------------|
| `~/.gtkrc-2.0` | f7891825 | 4a73c354 | f7891825 ✅ | 4a73c354 | f7891825 ✅ | 4a73c354 | f7891825 ✅ |
| `~/.config/gtk-3.0/settings.ini` | 18743cba | 18743cba (já OK) | 18743cba ✅ | b7a284c2 | 18743cba ✅ | 3f530f1a | 18743cba ✅ |
| `~/.config/lxsession/LXDE/desktop.conf` | 7ffabad4 | e6c14b39 | 7ffabad4 ✅ | e6c14b39 | 7ffabad4 ✅ | e6c14b39 | 7ffabad4 ✅ |
| `~/.config/openbox/lxde-rc.xml` | adcd300f | adcd300f (já OK) | adcd300f ✅ | adcd300f (já OK) | adcd300f ✅ | adcd300f (já OK) | adcd300f ✅ |
| `~/.config/lxpanel/LXDE/panels/panel` | d07cba7e | (missing) | d07cba7e ✅ | d07cba7e (já OK) | d07cba7e ✅ | 6fcb9147 | d07cba7e ✅ |
| `~/.config/lxpanel/LXDE/panels/00-background` | e5c23c4d | (missing) | e5c23c4d ✅ | (missing) | e5c23c4d ✅ | (missing) | e5c23c4d ✅ |
| `~/.config/lxpanel/LXDE/panels/status-right` | 90b1dc23 | (missing) | 90b1dc23 ✅ | (missing) | 90b1dc23 ✅ | (missing) | 90b1dc23 ✅ |
| `~/.config/lxpanel/LXDE/panel-background.xpm` | ed45c038 | (missing) | ed45c038 ✅ | (missing) | ed45c038 ✅ | (missing) | ed45c038 ✅ |
| `~/.local/share/icons/omni-dark-theme/omni-network-*.svg` | 96f98dc5/7c1dbd14/aa22c8a3 | (não copiado) | (não copiado) | (não copiado) | (não copiado) | (missing) | 96f98dc5/7c1dbd14/aa22c8a3 ✅ |

Theme está em disco mas **NÃO ativo visualmente** porque NÃO rodamos `--restart-session` (RDP ativo seria derrubado). User precisa fazer logout/login OU restart manual do LXDE.

## Lição aprendida

### PPA xtradeb no Noble

- O user adicionou PPA no Jammy (22.04). Quando o SRV-1 migrou para Noble, o `noble main` ficou desabilitado (não há deps para noble na versão jammy).
- O PPA xtradeb/apps TEM versão Noble (`dists/noble/main/binary-arm64/Packages.xz`), mas precisa ser habilitada separadamente.
- Workaround aplicado: em SRV-1, `sed` descomentou as linhas `noble main`; nos outros 3, criado do zero com `add-apt-repository` ou manualmente.

### Apt-key no Noble

- Ubuntu 24.04 (Noble) DEPRECOU `apt-key` (warning: "Key is stored in legacy trusted.gpg keyring"). Funciona, mas gera warning.
- Workaround: `gpg --dearmor` para `/etc/apt/trusted.gpg.d/xtradeb.gpg` e usar `signed-by=` no source.list.
- Não aplicado agora (warning é cosmético, mas será corrigido em 18-09 docs).

### GPG key correta do PPA xtradeb

- Briefing original pediu `0E3F0440E825C30AB1ACBC95` (errada).
- Chave correta: `82BB6851C64F6880` (descoberta via `apt-key adv --recv-keys` no SRV-2 e confirmada nos outros).

### chromium-snap → chromium-deb (transitional)

- SRV-2/3/horistic tinham `chromium-browser` (transitional pkg → snap) + `chromium` snap. `apt install chromium` puxa o transitional mas em SRV-2/3 o apt resolvia para snap.
- Solução: `snap remove chromium` (remove o snap) + `apt install chromium chromium-common chromium-sandbox` (instala o .deb).

### Dark theme canônico

- O `dark-theme-ubuntu/config_files/` é a fonte canônica (md5 `2aaa9120...` no total). Sincronizado do SRV-1 para os outros 3 via rsync.
- O `dark-themectl.sh apply` é o método oficial mas reinicia LXDE. Para preservar sessão RDP, copiei os arquivos manualmente com `cp -a` + backup pré-flight em `.backups/dark-theme-apply-2026-06-17/`.

## Cross-refs

- `18-PLAN.md`, `18-06-EXECUTION-2026-06-17.md` (phase anterior)
- `dark-theme-ubuntu/config_files/` (canônico)
- `~/.backups/phase-19-fleet-std-2026-06-17/` (snapshots hostname+tema)
- `~/.backups/dark-theme-apply-2026-06-17/` (backups pré-theme apply)
- `60-LOGS/2026-06-17-phase-19-fleet-std-execution.md` (vault log)
- `30-RECURSOS/operations/ATIUS-FLEET-NETWORK-PORT-MAP.md` §7 (ESM Apps)
- `inventory/hosts/atius-srv-{1,2,3}.yaml` (canônico host inventory — needs update)

## Pendente

- ~~Manual LXDE restart pelo user (logout/login) pra PCManFM recarregar atalhos~~ — resolvido por recarga controlada `pcmanfm --desktop-off` + `setsid -f pcmanfm --desktop`.
- Tema visual pode ainda exigir logout/login se algum painel GTK antigo estiver cacheado; os atalhos já foram recarregados.
- **G18-1 apt upgrade esm-apps+infra** (gate explícito, espera autorização)
- **18-09 docs** (canonical ubuntu-pro-fleet.md + watchdog cron)
- **Inventory update** em `inventory/hosts/*.yaml` (hostname lowercase)
